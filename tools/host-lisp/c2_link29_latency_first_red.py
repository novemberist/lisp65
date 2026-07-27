#!/usr/bin/env python3
"""Bind the receipt-less Link-29 latency first red to exact product evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/product-link-29-direct-entry-encoding"
DEPLOY = ROOT / "build/c2.2/hardware-presmoke-link29-direct-entry-encoding"
CAPTURE = DEPLOY / "first-red-latency/c2d-after-two-identical-forms.bin"
INITIAL_C2D = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
STRUCTURAL = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.2-product-link29-direct-entry-encoding-structural-receipt.json")
OUTPUT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
          "c2.2-product-link29-latency-hardware-first-red-diagnosis.json")


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


def slices(path: Path) -> dict[str, dict[str, Any]]:
    value = load(path)
    rows = value.get("slices")
    require(isinstance(rows, list), f"missing slices: {path}")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get("name"), str),
                f"bad slice row: {path}")
        require(row["name"] not in result, f"duplicate slice: {row['name']}")
        result[row["name"]] = row
    return result


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u24(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def literal_census() -> dict[str, Any]:
    c2d = INITIAL_C2D.read_bytes()
    shelf = SHELF.read_bytes()
    require(len(c2d) == 33840 and c2d[:5] == b"C2D\0\x03",
            "initial C2D-v3 drift")
    rows: list[dict[str, Any]] = []
    per_image: list[dict[str, int]] = []
    for image in range(u16(c2d, 12)):
        image_at = 48 + image * 32
        require(c2d[image_at] == 0 and c2d[image_at + 1] == 0,
                "static image unexpectedly uses the session source")
        directory_base = u16(c2d, image_at + 6)
        count = u16(c2d, image_at + 8)
        metadata = u24(c2d, image_at + 23)
        header = shelf[metadata:metadata + 24]
        require(header[:4] == b"C2I\0" and u16(header, 10) == count,
                "C2I metadata/header census drift")
        entries_offset = u16(header, 14)
        strings_offset = u16(header, 18)
        string_bytes = u16(header, 20)
        image_rows = []
        for local in range(count):
            entry_at = metadata + entries_offset + local * 16
            entry = shelf[entry_at:entry_at + 16]
            require(len(entry) == 16, "truncated C2I entry")
            name_offset = u16(entry, 8)
            name = f"image{image}:{local}"
            if name_offset != 0xFFFF:
                require(name_offset < string_bytes, "entry name offset outside string pool")
                at = metadata + strings_offset + name_offset
                length = u16(shelf, at)
                name = shelf[at + 2:at + 2 + length].decode("ascii")
            row = {
                "ordinal": directory_base + local,
                "image": image,
                "name": name,
                "literal_words": entry[7],
                "code_bytes": u16(entry, 3),
            }
            rows.append(row); image_rows.append(row)
        per_image.append({
            "image": image,
            "entries": len(image_rows),
            "entries_with_literals": sum(row["literal_words"] > 0 for row in image_rows),
            "literal_words": sum(row["literal_words"] for row in image_rows),
        })
    by_name = {row["name"]: row for row in rows}
    required_names = ("%banner-separator", "%banner-run", "%repl-banner",
                      "lcc-run", "%c2-compile-form")
    require(all(name in by_name for name in required_names),
            "key hot-refill entry census drift")
    return {
        "entries": len(rows),
        "entries_with_nonempty_literal_tables": sum(
            row["literal_words"] > 0 for row in rows),
        "literal_words": sum(row["literal_words"] for row in rows),
        "maximum_literal_words_per_entry": max(row["literal_words"] for row in rows),
        "per_image": per_image,
        "key_entries": [by_name[name] for name in required_names],
    }


def source_contract() -> dict[str, Any]:
    runtime = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    vm = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    overlay = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    required = {
        "hot_refill_routes_through_phase13": (
            "c2_overlay_call(LISP65_C2_PHASE_13_SLOT, &materialize)" in runtime),
        "nested_call_restores_caller_buffer": "BUF_ENSURE_MINE(pcur)" in vm,
        "catalog_verifier_runs_for_every_exec": (
            "verifier_index = 0;" in overlay
            and "++verifier_index != LISP65_RUNTIME_OVERLAY_APPLICATION_SLOT_BASE"
            in overlay),
        "payload_crc_runs_for_every_exec": (
            "rtov_crc_mem((const uint8_t *)RTOV_TARGET, rtov_loaded_len)"
            in overlay),
        "window_wiped_after_every_exec": "if (!rtov_wipe())" in overlay,
    }
    require(all(required.values()), f"source-path contract drift: {required}")
    return required


def transport_model(session: dict[str, dict[str, Any]],
                    target_names: list[str]) -> dict[str, Any]:
    catalog = int(session["catalog-verifier"]["file_size"])
    record = int(session["record-verifier"]["file_size"])
    target = sum(int(session[name]["file_size"]) for name in target_names)
    calls = len(target_names)
    verifier_payload = calls * (catalog + record)
    catalog_header = calls * 32
    catalog_directory = calls * len(session) * 32
    crc_bytes = verifier_payload + target + catalog_header + catalog_directory
    wiped = verifier_payload + target
    return {
        "overlay_calls": calls,
        "target_payload_bytes": target,
        "repeated_verifier_payload_bytes": verifier_payload,
        "repeated_catalog_header_crc_bytes": catalog_header,
        "repeated_catalog_directory_crc_bytes": catalog_directory,
        "minimum_crc_input_bytes": crc_bytes,
        "minimum_wipe_memset_bytes": wiped,
        "minimum_wipe_verify_bytes": wiped,
        "minimum_cpu_byte_visits_crc_plus_wipe": crc_bytes + 2 * wiped,
        "excluded_from_model": [
            "compiler VM execution and all phase-13 hot-literal refills",
            "phase-internal C2D, Shelf and Session DMA reads",
            "reader, printer, screen and VM dispatch work",
            "emitter literal traversal and additional emitted functions",
        ],
    }


def build() -> dict[str, Any]:
    structural = load(STRUCTURAL)
    deployment = load(DEPLOY / "deployment.json")
    session_path = LINK / "runtime-overlays-session-final.json"
    boot_path = LINK / "runtime-overlays-boot-final.json"
    session = slices(session_path)
    boot = slices(boot_path)
    require(structural.get("status") == "passed-structural-closure-hardware-pending",
            "Link-29 structural status drift")
    candidate = structural.get("candidate", {})
    product_sha = candidate.get("product_sha256")
    require(product_sha == "01c6b8ff25072349e353973c0e66f239eb89efc30de4ac742bd19ef54a9bdb0c",
            "Link-29 product identity drift")
    require(deployment.get("product", {}).get("sha256") == product_sha,
            "deployment/product identity mismatch")
    capture = CAPTURE.read_bytes()
    require(len(capture) == 33840 and capture[:4] == b"C2D\0" and capture[4] == 3,
            "latency capture is not the exact C2D-v3 plane")
    c2d = {
        "version": capture[4],
        "generation": u16(capture, 10),
        "images": u16(capture, 12),
        "entries": u16(capture, 16),
        "resolutions": u16(capture, 20),
        "roots": u16(capture, 24),
        "total_bytes": u16(capture, 36),
    }
    require(c2d == {"version": 3, "generation": 1, "images": 6,
                    "entries": 588, "resolutions": 2264, "roots": 283,
                    "total_bytes": 33840}, f"unexpected post-form C2D: {c2d}")

    emitter = [
        "c2-emit-prepare", "c2-emit-name", "c2-emit-literal-append",
        "c2-emit-code", "c2-emit-final-meta", "c2-emit-final-crc",
    ]
    append_before_decode = [
        "c2-append-envelope", "c2-append-crc", "c2-append-metadata",
        "c2-append-capacity", "c2-append-stage", "c2-append-image",
        "c2-append-entries",
    ]
    decode = [f"c2-decode-{name}" for name in
              ("04", "05", "06a", "06b", "07", "08", "09", "10", "11", "12")]
    publish = ["c2-append-header", "c2-append-publish-names",
               "c2-append-publish-cells"]
    rollback = ["c2-append-rollback"]
    minimum_install = emitter + append_before_decode + decode + publish + rollback
    require(len(minimum_install) == 27 and all(name in session for name in minimum_install),
            "minimum transient-install schedule drift")
    boot_decode = [f"c2-decode-{name}" for name in
                   ("00", "00b", "01", "02a", "02b", "03")]
    require(all(name in boot for name in boot_decode), "boot schedule drift")
    source = source_contract()
    census = literal_census()
    island_base = 395
    island_annex = 260
    record_size = int(session["record-verifier"]["file_size"])

    return {
        "format": "lisp65-c2-product-link29-latency-hardware-first-red-diagnosis-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-receipt-less-hardware-presmoke-stopped",
        "scope": {
            "candidate_product_sha256": product_sha,
            "structural_receipt": binding(STRUCTURAL),
            "deployment": binding(DEPLOY / "deployment.json"),
            "new_product_links_after_first_red": 0,
            "product_source_changes_after_first_red": 0,
        },
        "inputs": {
            "product_runtime": binding(ROOT / "src/c2_product_runtime.c"),
            "vm": binding(ROOT / "src/vm.c"),
            "overlay_transport": binding(ROOT / "src/vm_runtime_overlay.c"),
            "phase13": binding(ROOT / "scripts/c2-stream-v2-decoder.c"),
            "session_family_manifest": binding(session_path),
            "boot_family_manifest": binding(boot_path),
            "initial_c2d": binding(INITIAL_C2D),
            "immutable_shelf": binding(SHELF),
        },
        "observation": {
            "boot_to_repl_seconds_approx": 30,
            "banner_completion_seconds_approx": 5,
            "first_form": "(+ 1 2)",
            "first_result": "3",
            "first_result_latency_seconds_approx": 5,
            "second_form": "(+ 1 2)",
            "second_result": "3",
            "second_result_latency_seconds_approx": 5,
            "correctness_correction": "passed-first-arithmetic-smoke",
            "latency": "failed-no-warm-speedup",
            "sequence_stopped_immediately": True,
            "remaining_presmoke_cases": "not-run",
        },
        "runtime_capture": {
            "mode": "read-only C2D snapshot after both identical forms",
            "file": binding(CAPTURE),
            "header": c2d,
            "interpretation": (
                "Both anonymous session images completed rollback. Counts equal the six-image "
                "static baseline, so the repeated latency is not session-plane growth or leakage."
            ),
        },
        "static_transport_accounting": {
            "source_contract": source,
            "minimum_anonymous_single_function_install": transport_model(session, minimum_install),
            "minimum_install_schedule": minimum_install,
            "cold_decode_before_any_bytecode_execution": {
                "boot_family": transport_model(boot, boot_decode),
                "session_family": transport_model(session, decode),
                "overlay_calls_total": len(boot_decode) + len(decode),
            },
            "phase13_per_hot_refill": transport_model(session, ["c2-decode-13"]),
            "hot_refill_literal_census": census,
            "phase13_dynamic_multiplicity": (
                "Every C2 object load whose initial/refill span overlaps a non-empty literal "
                "table calls the full phase-13 transport. Nested calls overwrite vm_codebuf; "
                "BUF_ENSURE_MINE then reloads and may rematerialize the caller. The exact dynamic "
                "count was not instrumented in Link 29 and is deliberately not fabricated."
            ),
        },
        "root_cause": {
            "primary": (
                "The hot-window refill seam routes literal materialization through a complete "
                "runtime-overlay authentication on every qualifying code-object load. That "
                "transport reloads and CRC-checks the catalog verifier, rechecks the complete "
                "36-record directory, reloads and CRC-checks the record verifier, then reloads, "
                "CRC-checks and wipes phase 13. Static banner execution exercises this path "
                "without any session append, independently isolating it from append publication."
            ),
            "secondary_floor": (
                "A minimal anonymous one-function install performs at least 27 additional full "
                "overlay authentications. This is real but cannot by itself explain the slow "
                "static banner; it must be remeasured after the hot-refill defect is removed."
            ),
            "not_the_direct_entry_fix": (
                "The direct-entry correction is functionally successful: both forms return 3. "
                "Its phase-12 scan affects cold decode and one suffix decode per append, whereas "
                "the same five-second symptom appears during static banner execution."
            ),
            "why_second_call_is_not_warm": (
                "Transient append is intentionally rolled back and vm_codebuf is a single-owner "
                "128-byte cache clobbered by nested calls; no cross-form literal-window cache exists."
            ),
        },
        "bounded_fix_proposal": {
            "one_truth_cut": (
                "Make the refill seam materialize hot literals directly from the already decoded, "
                "generation-bound C2D resolution/root planes using the existing "
                "c2_stream_product_child_value helper. Refactor phase 13 to delegate to the same "
                "helper so product refill and proof phase do not duplicate descriptor semantics."
            ),
            "checks_preserved": [
                "entry literal-count and range bounds",
                "descriptor read and kind-dependent root indirection",
                "root ordinal bounds and nonzero even heap-pointer validation",
                "generation-bound directory/image/entry lookup",
                "no persistent hot cache and no skipped append validation",
            ],
            "permanent_gates": [
                "cross-check direct refill and phase 13 for all 588 current entries",
                "nested-call caller restoration with non-empty literals",
                "mutated descriptor, resolution, root ordinal and heap value all fail closed",
                "source gate forbids a second hand-written literal-resolution formula",
            ],
            "capacity_gate_before_product_link": {
                "bank0_text_headroom_bytes": 174,
                "ordinary_bank0_bss_headroom_bytes": 19,
                "fixed_bank0_headroom_bytes": 273,
                "e000_contingency_bytes": 386,
                "phase13_current_bytes": int(session["c2-decode-13"]["file_size"]),
                "phase13_current_headroom_bytes": 1792 - int(session["c2-decode-13"]["file_size"]),
                "resident_island_current_bytes": island_base + island_annex,
                "resident_island_headroom_bytes": 2048 - island_base - island_annex,
                "record_verifier_bytes_for_later_transaction_option": record_size,
                "rule": "any negative unapproved drift stops before a product link",
            },
            "successor_limit": (
                "After a green product-shaped capacity/placement probe, at most one separately "
                "authorized successor product link and the same receipt-less hardware presmoke."
            ),
            "hardware_measurements_required": [
                "boot-to-prompt and banner-completion frames",
                "two consecutive (+ 1 2) forms, product time separated from harness time",
                "nested compiled call that forces caller-buffer restoration",
                "C2D counts before and after repeated transient forms",
            ],
            "deferred_until_measured": (
                "Do not redesign the 27-call append transport in the same attempt. If the direct "
                "hot-refill repair leaves perceptible latency, its separately measured residual "
                "becomes a new review point rather than hidden scope growth."
            ),
        },
        "affected_claims": {
            "link29_structural_receipt": "remains valid structural evidence; hardware is still pending",
            "hardware_presmoke": "correctness first case passed, latency first red stopped the run",
            "promotion": "blocked",
            "c2_acceptance": "blocked",
            "performance": "not passed and no tolerance is inferred",
        },
        "claim_limit": (
            "Receipt-less hardware first-red diagnosis and exact static lower-bound accounting. "
            "It is not a performance acceptance, capacity authorization, product link, promotion "
            "or release claim. Dynamic phase-13 call counts are intentionally not claimed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build()
        expected = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        if args.action == "write":
            if OUTPUT.exists():
                os.chmod(OUTPUT, 0o644)
            OUTPUT.write_bytes(expected)
            os.chmod(OUTPUT, 0o444)
        else:
            require(OUTPUT.read_bytes() == expected, "diagnosis receipt drift")
        model = value["static_transport_accounting"][
            "minimum_anonymous_single_function_install"]
        print(f"c2-link29-latency-first-red: {args.action.upper()} "
              f"calls>={model['overlay_calls']} "
              f"cpu-byte-visits>={model['minimum_cpu_byte_visits_crc_plus_wipe']} "
              "dynamic-phase13=unclaimed promotion=blocked")
        return 0
    except (OSError, ValueError, KeyError, DiagnosisError) as error:
        print(f"c2-link29-latency-first-red: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
