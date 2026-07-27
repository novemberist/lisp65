#!/usr/bin/env python3
"""Bind the completed Link-57 C2-lite hardware pre-smoke.

This is deliberately an evidence-only tool.  It reads the already captured
product, transcripts and memory images, checks the promised relationships and
writes one receipt.  It never invokes a compiler, linker or device tool.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LATENCY = ROOT / "build/c2.2/hardware-presmoke-link57-keymap-nullary/latency"
PRODUCT_DIR = (
    ROOT
    / "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2"
)
RECEIPT = (
    ROOT
    / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json"
)

PRODUCT_SHA256 = "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8"
ELF_SHA256 = "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950"
NESTED_C2D_SHA256 = "0080b48e0764745eda33055dcda3963fd2558fd3ccf95314a882c7909a77926c"
RUNSTOP_C2D_SHA256 = "2f6f787f89db5a23f01eac7d9cbaeba486621960a9000eb0595ca4a99ee3fd5d"


class ReceiptError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReceiptError(message)


def regular(path: Path, label: str) -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ReceiptError(f"missing {label}: {path}: {exc}") from exc
    require(
        stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
        f"{label} must be a symlink-free regular file: {path}",
    )
    return path.read_bytes()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(regular(path, "hash input"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def binding(path: Path, label: str) -> dict[str, Any]:
    data = regular(path, label)
    return {
        "path": rel(path),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"invalid {label}: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def text(path: Path, label: str) -> str:
    try:
        return regular(path, label).decode("utf-8")
    except UnicodeError as exc:
        raise ReceiptError(f"invalid UTF-8 in {label}: {path}: {exc}") from exc


def little_u16(path: Path, label: str) -> int:
    data = regular(path, label)
    require(len(data) == 2, f"{label} must contain one u16: {path}")
    return int.from_bytes(data, "little")


def same_pair(before: Path, after: Path, expected_sha: str, label: str) -> None:
    before_data = regular(before, f"{label} before")
    after_data = regular(after, f"{label} after")
    require(before_data == after_data, f"{label} changed")
    require(sha256_bytes(before_data) == expected_sha, f"{label} identity drift")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    try:
        temporary.replace(path)
        path.chmod(0o444)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    product = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg"
    elf = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg.elf"
    structural = (
        ROOT
        / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json"
    )
    deployment = (
        ROOT / "build/c2.2/hardware-presmoke-link57-keymap-nullary/deployment.json"
    )
    result_path = LATENCY / "result.json"
    contract = ROOT / "config/c2-hot-refill-hardware-presmoke.json"
    lite_contract = ROOT / "config/c2-lite-execution-contract.json"
    transient_contract = ROOT / "config/c2-transient-handle-contract.json"

    require(sha256(product) == PRODUCT_SHA256, "product identity drift")
    require(sha256(elf) == ELF_SHA256, "ELF identity drift")
    result = load_json(result_path, "latency result")
    require(result.get("product_sha256") == PRODUCT_SHA256, "latency/product drift")
    require(result.get("status") == "pass-receipt-less", "latency result is not green")
    measurement = result.get("measurement")
    require(isinstance(measurement, dict), "latency measurement missing")
    require(
        measurement.get("boot_to_repl", {}).get("frames") == 943,
        "boot frame observation drift",
    )
    require(
        measurement.get("definition_first_call", {}).get("frames") == 0
        and measurement.get("definition_first_call", {}).get("result") == "t",
        "cold nullary observation drift",
    )
    require(
        measurement.get("warm_second_call", {}).get("frames") == 1
        and measurement.get("warm_second_call", {}).get("result") == "t",
        "warm nullary observation drift",
    )

    argument_text = text(LATENCY / "published_argument_call.txt", "argument transcript")
    native_text = text(LATENCY / "native_session_measure.txt", "native transcript")
    gc_text = text(LATENCY / "gc_fill_measure.txt", "GC transcript")
    nested_text = text(LATENCY / "nested_eval.txt", "nested-eval transcript")
    runstop_text = text(LATENCY / "runstop_result.txt", "RUN/STOP transcript")
    resume_text = text(LATENCY / "post_freezer_resume.txt", "post-Freezer transcript")
    generation_text = text(
        LATENCY / "post_freezer_generation_state.txt", "generation transcript"
    )
    require("(1 31 99)" in argument_text, "argument-call tuple missing")
    require("(%c2n 43 97)" in native_text, "native-session tuple missing")
    require("(t 131 213)" in gc_text, "GC workload tuple missing")
    require("(eval(quote(%c2h)))" in nested_text and "\n t" in nested_text,
            "nested eval did not return t")
    require("*** stopped (run/stop)" in runstop_text, "RUN/STOP result missing")
    require("\n 9" in resume_text, "post-Freezer arithmetic result missing")
    require("(1 4)" in generation_text, "post-Freezer family/generation state missing")

    same_pair(
        LATENCY / "c2d-before-nested.bin",
        LATENCY / "c2d-after-nested.bin",
        NESTED_C2D_SHA256,
        "nested-eval C2D",
    )
    same_pair(
        LATENCY / "c2d-before-runstop.bin",
        LATENCY / "c2d-after-runstop.bin",
        RUNSTOP_C2D_SHA256,
        "RUN/STOP C2D",
    )

    bank2_before = regular(LATENCY / "freezer-before-bank2.bin", "Bank-2 before")
    bank2_after = regular(LATENCY / "freezer-after-bank2.bin", "Bank-2 after")
    bank3_before = regular(LATENCY / "freezer-before-bank3.bin", "Bank-3 before")
    bank3_after = regular(LATENCY / "freezer-after-bank3.bin", "Bank-3 after")
    require(len(bank2_before) == len(bank2_after) == 65536, "Bank-2 span drift")
    require(len(bank3_before) == len(bank3_after) == 65536, "Bank-3 span drift")
    require(bank2_before == bank2_after, "Bank-2 changed across Freezer")
    require(bank3_before == bank3_after, "Bank-3 changed across Freezer")

    e000_before = regular(LATENCY / "freezer-before-e000.bin", "$E000 before")
    e000_after = regular(LATENCY / "freezer-after-e000.bin", "$E000 after")
    require(len(e000_before) == len(e000_after) == 8192, "$E000 span drift")
    e000_diffs = [
        0xE000 + offset
        for offset, (left, right) in enumerate(zip(e000_before, e000_after))
        if left != right
    ]
    require(
        e000_diffs == [0xFF83, 0xFF84, 0xFF86],
        f"unexpected Freezer $E000 differences: {e000_diffs}",
    )

    gc_before = little_u16(LATENCY / "gc-runs-before-fill.bin", "GC-before")
    gc_post_all = little_u16(LATENCY / "gc-runs-post-all.bin", "GC-post-all")
    require(gc_before == 3, "GC-before counter drift")
    require(gc_post_all >= 5, "post-run GC counter does not corroborate progress")
    # The immediate post-workload value was read as 5 during the hardware run.
    # Its two-byte file was later overwritten by an accidental local `xxd`
    # output operation.  Never pretend the remaining file is raw evidence.
    gc_after_observed = 5
    gc_collections = gc_after_observed - gc_before
    require(gc_collections == 2, "GC collection delta drift")
    transient = load_json(transient_contract, "transient-handle contract")
    blocks_per_collection = transient.get("gc_measurement_requirement", {}).get(
        "high_edge_projection_blocks_per_collection"
    )
    require(blocks_per_collection == 96, "GC blockread contract drift")

    lite = load_json(lite_contract, "C2-lite execution contract")
    core_identity = lite.get("hardware_prerequisite", {}).get(
        "device_core_version"
    )
    require(core_identity == "git-03b24c6b", "device-core contract drift")

    evidence_paths = {
        "structural_receipt": structural,
        "deployment": deployment,
        "latency_result": result_path,
        "hardware_contract": contract,
        "c2_lite_contract": lite_contract,
        "transient_handle_contract": transient_contract,
        "m65_tool": ROOT / "tools/m65tools/m65",
        "cold_transcript": LATENCY / "definition_first_call.txt",
        "warm_transcript": LATENCY / "warm_second_call.txt",
        "argument_transcript": LATENCY / "published_argument_call.txt",
        "native_transcript": LATENCY / "native_session_measure.txt",
        "gc_transcript": LATENCY / "gc_fill_measure.txt",
        "nested_transcript": LATENCY / "nested_eval.txt",
        "runstop_transcript": LATENCY / "runstop_result.txt",
        "post_freezer_transcript": LATENCY / "post_freezer_resume.txt",
        "generation_transcript": LATENCY / "post_freezer_generation_state.txt",
        "keymap_post_sample_screen": LATENCY / "keymap-after-physical-sample.png",
        "nested_c2d_before": LATENCY / "c2d-before-nested.bin",
        "nested_c2d_after": LATENCY / "c2d-after-nested.bin",
        "runstop_c2d_before": LATENCY / "c2d-before-runstop.bin",
        "runstop_c2d_after": LATENCY / "c2d-after-runstop.bin",
        "freezer_bank2_before": LATENCY / "freezer-before-bank2.bin",
        "freezer_bank2_after": LATENCY / "freezer-after-bank2.bin",
        "freezer_bank3_before": LATENCY / "freezer-before-bank3.bin",
        "freezer_bank3_after": LATENCY / "freezer-after-bank3.bin",
        "freezer_e000_before": LATENCY / "freezer-before-e000.bin",
        "freezer_e000_after": LATENCY / "freezer-after-e000.bin",
        "gc_counter_before": LATENCY / "gc-runs-before-fill.bin",
        "gc_counter_post_all": LATENCY / "gc-runs-post-all.bin",
    }
    bindings = {
        name: binding(path, name.replace("_", " "))
        for name, path in evidence_paths.items()
    }
    bindings["product"] = binding(product, "product")
    bindings["elf"] = binding(elf, "ELF")

    corrupted_gc_after = LATENCY / "gc-runs-after-fill.bin"
    excluded_gc_binding = binding(
        corrupted_gc_after, "excluded overwritten GC-after artifact"
    )

    receipt: dict[str, Any] = {
        "format": "lisp65-c2-lite-v6-link57-hardware-presmoke-attempt2-v1",
        "recorded_on": "2026-07-23",
        "status": "pass-receipt-less-hardware-presmoke-latency-healing-green",
        "claim_limit": (
            "Receipt-less hardware pre-smoke evidence for Link 57 only. "
            "This closes the two-attempt nullary latency question but is not "
            "promotion, acceptance, release or a general performance claim. "
            "Argument, native and GC timings are informative end-to-end "
            "envelopes, not isolated primitive or transport costs."
        ),
        "product_identity": {
            "product_sha256": PRODUCT_SHA256,
            "elf_sha256": ELF_SHA256,
            "structural_status": load_json(structural, "structural receipt").get(
                "status"
            ),
        },
        "device": {
            "contract_bound_core_identity": core_identity,
            "core_identity_this_run": (
                "not independently reread; this run continued on the same "
                "device/session established by the C2-lite metal proof"
            ),
            "live_tool_identity": "m65 20260722.00-develo-c5bf0cc",
        },
        "accounting": {
            "line1_product_first_red_budget": "2/3",
            "latency_attempts_before_this_run": "1/2",
            "latency_attempts_after_this_run": "2/2",
            "this_run_consumed_latency_attempt": 1,
            "latency_question": "closed-pass",
            "new_product_links_during_presmoke": 0,
        },
        "rows": {
            "boot_to_repl": {
                "status": "pass",
                "frames": 943,
                "nominal_milliseconds": 18860,
                "limit_frames": 1500,
                "classification": "regression-watch",
            },
            "definition_first_call_nullary": {
                "status": "pass",
                "result": "t",
                "start_frame": 165,
                "end_frame": 165,
                "frames": 0,
                "target_frames": 15,
                "hard_limit_frames": 16,
            },
            "warm_second_call_nullary": {
                "status": "pass",
                "result": "t",
                "start_frame": 251,
                "end_frame": 252,
                "frames": 1,
                "limit_frames": 10,
            },
            "published_call_with_argument": {
                "status": "informative-red-position",
                "result": "1",
                "start_frame": 31,
                "end_frame": 99,
                "frames": 68,
                "nominal_milliseconds": 1360,
                "limit": "none",
                "claim": (
                    "The general argument case still pays the full top-level "
                    "ceremony and is a named C2.3/1.2 planning position."
                ),
            },
            "chip_refill_observations": {
                "status": "informative",
                "bytecode": {
                    "frames": [0, 1],
                    "basis": "cold/warm published-nullary end-to-end calls",
                    "isolated_single_refill_claim": "not-made",
                },
                "native": {
                    "result": "%c2n",
                    "start_frame": 43,
                    "end_frame": 97,
                    "frames": 54,
                    "nominal_milliseconds": 1080,
                    "basis": "nested append transaction using Session native slices",
                    "isolated_single_refill_claim": "not-made",
                },
            },
            "gc_blockreads_and_frames": {
                "status": "measured-no-acceptance-limit",
                "workload": "%c2gcfill 400",
                "result": "t",
                "start_frame": 131,
                "end_frame": 213,
                "workload_envelope_frames": 82,
                "nominal_milliseconds": 1640,
                "gc_runs_before": gc_before,
                "gc_runs_after_observed": gc_after_observed,
                "collections": gc_collections,
                "blockreads_per_collection": blocks_per_collection,
                "blockreads_executed": gc_collections * blocks_per_collection,
                "isolated_frames_per_collection_claim": "not-made",
                "evidence_caveat": (
                    "The immediate two-byte after-capture was accidentally "
                    "overwritten later by a local display command.  The value "
                    "5 is the contemporaneous hardware observation; the raw "
                    "before value 3 and later raw value 10 are bound.  The "
                    "damaged file is explicitly excluded below."
                ),
            },
            "freezer_identity": {
                "status": "pass",
                "bank2_bytes": len(bank2_before),
                "bank2_sha256": sha256_bytes(bank2_before),
                "bank3_bytes": len(bank3_before),
                "bank3_sha256": sha256_bytes(bank3_before),
                "e000_bytes": len(e000_before),
                "e000_preserved_bytes": len(e000_before) - len(e000_diffs),
                "e000_expected_volatile_addresses": [
                    f"0x{address:04x}" for address in e000_diffs
                ],
                "volatile_meaning": [
                    "frame-counter-low",
                    "frame-counter-high",
                    "sourceless-irq-counter",
                ],
                "post_return_arithmetic": 9,
                "post_return_family_generation": [1, 4],
            },
            "nested_eval": {
                "status": "pass",
                "form": "(eval '(%c2h))",
                "result": "t",
                "c2d_before_after_sha256": NESTED_C2D_SHA256,
                "directory_growth_bytes": 0,
            },
            "runstop_rollback": {
                "status": "pass",
                "result": "*** stopped (run/stop)",
                "repl_survived": True,
                "c2d_before_after_sha256": RUNSTOP_C2D_SHA256,
                "directory_growth_bytes": 0,
            },
            "generation": {
                "status": "qualified-partial-hardware-observation",
                "boot_session_state_after_freezer": [1, 4],
                "freezer_preserved_both_chip_planes": True,
                "destructive_restage_stale_handle_negative": "not-run",
                "claim_limit": (
                    "Generation invalidation remains freshly structural- and "
                    "mutation-gated for Link 57; this presmoke did not force a "
                    "separate destructive restage on hardware."
                ),
            },
            "physical_keymap": {
                "status": "pass-operator-confirmed",
                "operator_confirmation": (
                    "Alex confirmed all three points in chat on 2026-07-23."
                ),
                "control_space": "mark action visible",
                "meta_x": "command launcher opened without inserting x",
                "control_x_control_c": "editor exited to usable REPL",
            },
        },
        "excluded_evidence": {
            "gc_after_fill_raw_capture": {
                **excluded_gc_binding,
                "status": "excluded-corrupted-after-capture",
                "reason": (
                    "A later `xxd input output` display command treated this "
                    "path as an output and overwrote the original two bytes."
                ),
            }
        },
        "bindings": bindings,
        "value_string": (
            f"link57={PRODUCT_SHA256} boot=943f/18860ms<=1500f "
            "cold-nullary=0f<=16f warm-nullary=1f<=10f "
            "argument=68f/no-limit native-transaction=54f/no-limit "
            "gc=82f-envelope/2-collections/192-blockreads "
            "freezer=bank2+bank3+8189of8192-e000-pass "
            "nested=pass-zero-growth runstop=pass-zero-growth "
            "keymap=3of3-operator-confirmed generation-restage-negative=not-run "
            "latency-attempts=2of2 latency-question=PASS acceptance=not-claimed"
        ),
    }

    atomic_json(RECEIPT, receipt)
    print(
        "c2-link57-latency-attempt2-hardware-receipt: PASS "
        f"receipt={rel(RECEIPT)} product={PRODUCT_SHA256} "
        "cold=0 warm=1 argument=68 native=54 gc=82/2/192 "
        "freezer=pass nested=pass runstop=pass keymap=3/3"
    )


if __name__ == "__main__":
    main()
