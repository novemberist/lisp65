#!/usr/bin/env python3
"""Bind Link 32's receipt-less nested-eval hardware first red.

This is deliberately a diagnosis-only tool.  It validates the immutable
Link-32 product/deployment, the hardware transcripts, the captured C2D plane
and the captured Session-Attic prefix.  It does not build or alter product
bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link32-preinstall-island-guard"
LATENCY = PRESMOKE / "latency"
STRUCTURAL = EVIDENCE / "c2.2-product-link32-preinstall-island-guard-structural-receipt.json"
OUTPUT = EVIDENCE / "c2.2-product-link32-nested-eval-hardware-first-red-diagnosis.json"
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
C2D_CAPTURE = PRESMOKE / "first-red-c2d-bank5.bin"
ATTIC_CAPTURE = PRESMOKE / "first-red-session-attic.bin"
PRODUCT = LINK / "lisp65-c2-substitution-linked.prg"
PRODUCT_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"

C2D_HEADER_BYTES = 48
C2D_IMAGE_BYTES = 32
C2D_IMAGES_OFFSET = 48
C2D_TOTAL_BYTES = 33840


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u24(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def counts(data: bytes) -> dict[str, int]:
    require(len(data) >= C2D_HEADER_BYTES and data[:5] == b"C2D\0\x03",
            "not a C2D-v3 plane")
    return {
        "images": u16(data, 12),
        "entries": u16(data, 16),
        "resolutions": u16(data, 20),
        "roots": u16(data, 24),
    }


def image(data: bytes, slot: int) -> dict[str, int]:
    at = C2D_IMAGES_OFFSET + slot * C2D_IMAGE_BYTES
    require(at + C2D_IMAGE_BYTES <= len(data), "C2D image record out of range")
    return {
        "slot": slot,
        "source_kind": data[at],
        "flags": data[at + 1],
        "source_slot": data[at + 2],
        "reserved": data[at + 3],
        "generation": u16(data, at + 4),
        "directory_base": u16(data, at + 6),
        "entries": u16(data, at + 8),
        "resolution_base": u16(data, at + 10),
        "resolutions": u16(data, at + 12),
        "root_base": u16(data, at + 14),
        "roots": u16(data, at + 16),
        "code_offset": u24(data, at + 18),
        "code_length": u16(data, at + 21),
        "metadata_offset": u24(data, at + 23),
        "metadata_length": u16(data, at + 26),
        "combined_crc32": u32(data, at + 28),
    }


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"missing function signature: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"missing function body: {signature}")
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start:pos + 1]
    raise DiagnosisError(f"unterminated function body: {signature}")


def transcript(name: str) -> tuple[Path, str]:
    path = LATENCY / f"{name}.txt"
    return path, path.read_text(encoding="utf-8", errors="replace")


def validate_sources() -> dict[str, Any]:
    eval_c_path = ROOT / "src/eval.c"
    runtime_path = ROOT / "src/c2_product_runtime.c"
    overlay_path = ROOT / "src/vm_runtime_overlay.c"
    interrupt_path = ROOT / "src/interrupt.c"
    eval_lisp_path = ROOT / "lib/dialect-v2/eval-runtime.lisp"

    eval_c = eval_c_path.read_text(encoding="utf-8")
    runtime = runtime_path.read_text(encoding="utf-8")
    overlay = overlay_path.read_text(encoding="utf-8")
    interrupt = interrupt_path.read_text(encoding="utf-8")
    eval_lisp = eval_lisp_path.read_text(encoding="utf-8")

    install = function_body(runtime, "obj c2_product_install(")
    begin = function_body(overlay, "vm_runtime_overlay_status vm_runtime_overlay_transaction_begin(")
    abort = function_body(overlay, "vm_runtime_overlay_status vm_runtime_overlay_abort_cleanup(")
    install_obj = function_body(eval_c, "static obj lcc_install_obj(")
    abort_jump = function_body(interrupt, "static void lisp_abort_jump(")

    ordered = [
        "vm_runtime_overlay_transaction_begin(",
        "c2_append_begin(length, &before, &main)",
        "result = vm_run_dir((int)main, 0, 0)",
        "c2_append_rollback(&before)",
    ]
    positions = [install.find(token) for token in ordered]
    require(all(pos >= 0 for pos in positions) and positions == sorted(positions),
            "C2 install transaction/execute/rollback ordering drift")
    final_end = install.find("vm_runtime_overlay_transaction_end()", positions[-1])
    require(final_end > positions[-1],
            "C2 install final transaction_end does not follow rollback")
    require("RTOV_TRANSACTION_ACTIVE()" in begin
            and "return VM_RUNTIME_OVERLAY_ERR_BUSY" in begin,
            "nested transaction rejection drift")
    require("vm_status = VM_BADOPCODE; return NIL;" in install,
            "nested transaction failure mapping drift")
    require("result = c2_product_install(fnlist, defname);" in install_obj
            and "vm_check_status();" in install_obj,
            "C2 install error-to-abort bridge drift")
    require("vm_runtime_overlay_abort_cleanup();" in abort_jump
            and "longjmp(lisp_toplevel, 1);" in abort_jump,
            "central abort landing drift")
    require("rtov_transaction_invalidate();" in abort
            and "c2_append" not in abort,
            "abort cleanup unexpectedly owns C2 append rollback")
    require("(defun eval (form)" in eval_lisp and "(lcc-run form)" in eval_lisp,
            "public Lisp eval routing drift")
    require("return eval_vm_native_apply_checked(fn, l);" in eval_c,
            "public C eval-to-lcc routing drift")

    return {
        "sources": [
            binding(eval_c_path), binding(runtime_path), binding(overlay_path),
            binding(interrupt_path), binding(eval_lisp_path),
        ],
        "ordered_install_seam": ordered + ["vm_runtime_overlay_transaction_end() after rollback"],
        "nested_begin_rejects_active_transaction": True,
        "vm_error_longjmps_before_outer_rollback": True,
        "abort_cleanup_invalidates_overlay_trust_but_has_no_c2_append_rollback": True,
    }


def build() -> dict[str, Any]:
    structural = load(STRUCTURAL)
    deployment = load(PRESMOKE / "deployment.json")
    initial = INITIAL_C2D.read_bytes()
    captured = C2D_CAPTURE.read_bytes()
    attic = ATTIC_CAPTURE.read_bytes()

    require(structural.get("status") == "passed-new-product-identity-hardware-not-run",
            "Link-32 structural status drift")
    require(structural.get("product_identity", {}).get("product", {}).get("sha256")
            == PRODUCT_SHA, "Link-32 structural product identity drift")
    require(sha(PRODUCT) == PRODUCT_SHA, "Link-32 product bytes drift")
    require(deployment.get("status") == "ready-receipt-less"
            and deployment.get("new_product_links") == 0,
            "deployment claim drift")
    require(deployment.get("product", {}).get("sha256") == PRODUCT_SHA,
            "deployment product identity drift")
    require(len(captured) == 65536 and len(initial) == C2D_TOTAL_BYTES,
            "C2D capture or initial plane length drift")
    require(len(attic) == 1024, "Session-Attic capture length drift")

    before = counts(initial)
    after = counts(captured)
    require(before == {"images": 6, "entries": 588, "resolutions": 2264, "roots": 283},
            f"initial C2D census drift: {before}")
    require(after == {"images": 9, "entries": 591, "resolutions": 2278, "roots": 285},
            f"first-red C2D census drift: {after}")
    require({key: after[key] - before[key] for key in before} ==
            {"images": 3, "entries": 3, "resolutions": 14, "roots": 2},
            "post-first-red C2D delta drift")

    appended = [image(captured, slot) for slot in range(6, 9)]
    expected_shapes = [
        (1, 0, 1, 0, 0, 9, 46),
        (1, 1, 1, 7, 1, 48, 114),
        (1, 2, 1, 7, 1, 48, 114),
    ]
    payloads: list[bytes] = []
    for record, shape in zip(appended, expected_shapes):
        actual = (record["source_kind"], record["source_slot"], record["entries"],
                  record["resolutions"], record["roots"], record["code_length"],
                  record["metadata_length"])
        require(actual == shape, f"session image shape drift: {actual} != {shape}")
        require(record["flags"] == record["reserved"] == 0
                and record["generation"] == 1,
                "session image flags/generation drift")
        code_start = record["code_offset"]
        meta_start = record["metadata_offset"]
        require(code_start + record["code_length"] <= len(attic)
                and meta_start + record["metadata_length"] <= len(attic),
                "captured Session-Attic prefix does not cover image")
        payload = (attic[code_start:code_start + record["code_length"]]
                   + attic[meta_start:meta_start + record["metadata_length"]])
        payloads.append(payload)
        calculated = zlib.crc32(payload) & 0xFFFFFFFF
        require(calculated == record["combined_crc32"],
                f"session image CRC mismatch at slot {record['slot']}")
        record["calculated_crc32"] = calculated
        record["crc_matches_captured_attic"] = True
        record["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    require(payloads[1] == payloads[2],
            "two failed identical eval wrappers are not byte-identical")

    boot_path, boot = transcript("boot_counter")
    setup_path, setup = transcript("definition_setup")
    cold_path, cold = transcript("definition_first_call")
    warm_path, warm = transcript("warm_second_call")
    direct_path, direct = transcript("direct-defined-call-diagnostic")
    timing = LATENCY / "direct-defined-call-diagnostic-timing.json"
    timing_json = load(timing)

    require("(3 117 3)" in boot, "stable boot counter result drift")
    require("(defun %c2h()(quote t))" in setup and "%c2h" in setup,
            "definition setup did not succeed")
    require(cold.count("*** vm: bad bytecode") == 1,
            "cold nested eval first-red transcript drift")
    require(warm.count("*** vm: bad bytecode") == 2,
            "warm nested eval first-red transcript drift")
    require("(%c2h)" in direct and "\n t" in direct,
            "direct defined call did not return t")
    require(timing_json.get("status") == "pass",
            "direct correctness diagnostic did not complete")

    source_evidence = validate_sources()
    capacity = structural.get("capacity", {})
    require(capacity.get("bank0_text_headroom_bytes") == 10
            and capacity.get("bank0_ordinary_bss_headroom_bytes") == 19
            and capacity.get("resident_island", {}).get("headroom_bytes") == 109
            and capacity.get("runtime_overlay_slices", {}).get("minimum_headroom_bytes") == 11
            and capacity.get("e000", {}).get("future_margin_bytes") == 386
            and capacity.get("e000", {}).get("growth_policy") == "closed-to-new-tenants",
            "Link-32 capacity-wall binding drift")

    return {
        "format": "lisp65-c2-product-link32-nested-eval-hardware-first-red-diagnosis-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-receipt-less-hardware-presmoke-stopped",
        "scope": {
            "candidate_product_sha256": PRODUCT_SHA,
            "structural_receipt": binding(STRUCTURAL),
            "deployment": binding(PRESMOKE / "deployment.json"),
            "product": binding(PRODUCT),
            "new_product_links_after_first_red": 0,
            "product_source_changes_after_first_red": 0,
            "remaining_hardware_cases": "not-run",
        },
        "hardware_observation": {
            "boot_to_repl_regression_watch": {
                "stable_counter_result": "(3 117 3)",
                "upper_bound_frames": 885,
                "upper_bound_milliseconds": 17700,
                "limit_frames": 1500,
                "result": "within regression-watch limit",
                "claim_limit": (
                    "The stable owned-counter read followed prompt polling and virtual "
                    "input. It is an upper bound, not an exact banner-to-prompt time."
                ),
                "transcript": binding(boot_path),
            },
            "definition_setup": {
                "form": "(defun %c2h()(quote t))",
                "result": "%c2h",
                "transcript": binding(setup_path),
            },
            "cold_definition_first_call": {
                "form": "(let((a(peek 215 250)))(let((r(eval(quote(%c2h)))))(list r a(peek 215 250))))",
                "result": "*** vm: bad bytecode",
                "limit_frames": 16,
                "elapsed_frames": "not-measured-correctness-failed-first",
                "transcript": binding(cold_path),
            },
            "warm_second_call": {
                "form": "identical nested eval form",
                "result": "*** vm: bad bytecode",
                "limit_frames": 10,
                "elapsed_frames": "not-measured-correctness-failed-first",
                "transcript": binding(warm_path),
            },
            "direct_defined_call_diagnostic": {
                "form": "(%c2h)",
                "result": "t",
                "meaning": (
                    "The named definition and its emitted C2 image execute correctly when "
                    "the outer transient wrapper calls it directly; the failure is specific "
                    "to nested public eval/install."
                ),
                "transcript": binding(direct_path),
                "harness_completion_only_not_latency": binding(timing),
            },
        },
        "runtime_evidence": {
            "initial_c2d": binding(INITIAL_C2D),
            "captured_c2d_bank5": binding(C2D_CAPTURE),
            "captured_session_attic_prefix": binding(ATTIC_CAPTURE),
            "counts_before": before,
            "counts_after_definition_and_two_failed_nested_evals": after,
            "delta": {key: after[key] - before[key] for key in before},
            "appended_images": appended,
            "interpretation": {
                "slot_6": "one valid persistent %c2h definition image",
                "slots_7_8": (
                    "two byte-identical transient outer eval wrappers that were published "
                    "but not rolled back after the nested install aborted"
                ),
                "crc_claim": (
                    "All three active session-image records match the captured Session-Attic "
                    "code+metadata bytes exactly; staging/emission integrity is not the first red."
                ),
            },
        },
        "static_evidence": source_evidence,
        "root_cause": {
            "primary": (
                "Every non-atomic public eval routes through lcc-run and c2_product_install. "
                "The outer top-level transient install begins one authenticated overlay "
                "transaction, appends its wrapper, and keeps that transaction active while "
                "vm_run_dir executes the wrapper. A public eval inside that wrapper re-enters "
                "c2_product_install. The inner transaction_begin rejects the already-active "
                "transaction as BUSY; c2_product_install maps that failure to VM_BADOPCODE."
            ),
            "abort_leak": (
                "lcc_install_obj converts VM_BADOPCODE to a top-level longjmp before the outer "
                "c2_product_install can call c2_append_rollback. The central abort cleanup "
                "invalidates and wipes runtime-overlay transaction state but owns no C2D append "
                "checkpoint. Each failed nested eval therefore leaves its already-published "
                "outer transient wrapper active, exactly matching the observed +1 image/+1 "
                "entry/+7 resolutions/+1 root per failure."
            ),
            "why_direct_call_passes": (
                "A top-level wrapper that calls %c2h directly does not start an inner compiler "
                "transaction. It completes and reaches the ordinary outer rollback path."
            ),
            "class": "nested C2 append lifetime and non-local abort rollback contract gap",
        },
        "affected_claims": {
            "link32_structural_receipt": "remains valid structural evidence",
            "hardware_correctness": "first red on nested public eval",
            "performance": "not measured; neither the 15/16-frame nor <=10-frame limit was evaluated",
            "promotion": "blocked",
            "hardware_acceptance": "not claimed",
        },
        "bounded_next_contract_probe": {
            "authorization": "not granted by this diagnosis; product work remains stopped",
            "scope": "nested C2 append, persistence and non-local abort semantics",
            "required_cases": [
                "nested transient eval succeeds without leaking an image, entry, resolution or root",
                "identical warm nested eval repeats with zero count growth",
                "error/longjmp at every supported nesting depth restores exact C2D, export, root and Attic-watermark state",
                "nested persistent definition semantics are explicit: survive the outer transient atomically or fail closed before publication",
                "eval, eval-string and load entry seams each exercise the nested contract; compile-string is classified against the same contract",
                "generation change invalidates every active nested checkpoint fail-closed",
                "nesting depth is bounded and overflow is rejected before mutation",
            ],
            "must_not_do": [
                "merely allow a second overlay transaction_begin without defining C2D rollback ownership",
                "let an outer rollback erase or overwrite a newer persistent definition",
                "let longjmp clean only overlay trust while leaving a transient C2D suffix",
                "claim latency before the correctness cycle completes",
            ],
            "capacity_first": {
                "bank0_text_headroom_bytes": 10,
                "ordinary_bank0_bss_headroom_bytes": 19,
                "resident_island_headroom_bytes": 109,
                "runtime_slice_minimum_headroom_bytes": 11,
                "e000_headroom_bytes": 386,
                "e000_growth_policy": "closed-to-new-tenants",
                "rule": (
                    "Any resident cost is a triage event; Boot-family lifetime substitution "
                    "is the pre-named first candidate. No successor product link precedes a "
                    "green contract and capacity/placement probe."
                ),
            },
        },
        "claim_limit": (
            "This diagnosis binds one receipt-less Link-32 hardware first red and read-only "
            "post-stop memory/source evidence. It is not hardware acceptance, promotion, "
            "capacity authorization or permission to implement a fix."
        ),
    }


def main() -> int:
    receipt = build()
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if OUTPUT.exists():
        if OUTPUT.read_bytes() == encoded:
            verb = "CHECK PASS"
        elif os.environ.get("LISP65_REPLACE_UNSEALED_DIAGNOSIS") == "1":
            OUTPUT.write_bytes(encoded)
            os.chmod(OUTPUT, 0o444)
            verb = "REPLACED UNSEALED DIAGNOSIS"
        else:
            raise DiagnosisError("existing diagnosis receipt drift")
    else:
        OUTPUT.write_bytes(encoded)
        os.chmod(OUTPUT, 0o444)
        verb = "PASS"
    print(f"c2-link32-nested-eval-first-red: {verb} output={OUTPUT.relative_to(ROOT)}")
    print(f"c2-link32-nested-eval-first-red: receipt_sha256={sha(OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
