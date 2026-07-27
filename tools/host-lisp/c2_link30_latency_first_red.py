#!/usr/bin/env python3
"""Bind and explain Link 30's receipt-less latency first red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "build/c2.2/substitution/product-link-30-hot-refill"
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link30-hot-refill"
LATENCY = PRESMOKE / "latency"
STRUCTURAL = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.2-product-link30-hot-refill-structural-receipt.json")
LINK29_DIAGNOSIS = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                    "c2.2-product-link29-latency-hardware-first-red-diagnosis.json")
OUTPUT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
          "c2.2-product-link30-hot-refill-hardware-first-red-diagnosis.json")
PRODUCT_SHA = "1eba43ca05b2d7996071ca2445d3501f8caa9aad999ca1a1c6de818f302d1d18"
PAIR = re.compile(r"\(\s*t\s+(\d+)\s+(\d+)\s*\)", re.IGNORECASE)


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


def measured(path: Path) -> tuple[str, int, int, int]:
    found = PAIR.findall(path.read_text(encoding="utf-8", errors="replace"))
    require(bool(found), f"missing measured result: {path}")
    start, end = (int(item) for item in found[-1])
    return f"(t {start} {end})", start, end, (end - start) & 0xff


def slices(path: Path) -> dict[str, dict[str, Any]]:
    rows = load(path).get("slices")
    require(isinstance(rows, list), "session overlay manifest lacks slices")
    result = {row["name"]: row for row in rows}
    require(len(result) == len(rows), "duplicate session overlay slice name")
    return result


def build() -> dict[str, Any]:
    structural = load(STRUCTURAL)
    link29 = load(LINK29_DIAGNOSIS)
    deployment = load(PRESMOKE / "deployment.json")
    result = load(LATENCY / "result.json")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    cold_path = LATENCY / "definition_first_call.txt"
    warm_path = LATENCY / "warm_second_call.txt"
    boot_path = LATENCY / "diagnostics/after-input-timeout.txt"
    cold_result, cold_start, cold_end, cold_frames = measured(cold_path)
    warm_result, warm_start, warm_end, warm_frames = measured(warm_path)

    require(structural.get("status") ==
            "passed-new-product-identity-hardware-not-run",
            "Link-30 structural status drift")
    require(structural.get("product_identity", {}).get("product", {}).get(
        "sha256") == PRODUCT_SHA, "Link-30 structural product drift")
    require(sha(product) == PRODUCT_SHA, "Link-30 product bytes drift")
    require(deployment.get("product", {}).get("sha256") == PRODUCT_SHA,
            "deployment product drift")
    require(result.get("status") == "first-red-receipt-less"
            and result.get("product_sha256") == PRODUCT_SHA,
            "presmoke result is not the bound first red")
    measurements = result.get("measurement", {})
    require(measurements.get("boot_to_repl", {}).get("frames") == 927,
            "boot regression-watch value drift")
    require(cold_result == "(t 33 164)" and cold_frames == 131,
            "cold first-call measurement drift")
    require(warm_result == "(t 119 250)" and warm_frames == 131,
            "warm second-call measurement drift")
    require(result.get("first_red") == [
        "definition-first-call", "warm-second-call"],
        "first-red classification drift")

    rows = slices(LINK / "runtime-overlays-session-final.json")
    emit = [
        "c2-emit-prepare", "c2-emit-name", "c2-emit-literal-append",
        "c2-emit-code", "c2-emit-final-meta", "c2-emit-final-crc",
    ]
    append_before_decode = [
        "c2-append-envelope", "c2-append-crc", "c2-append-metadata",
        "c2-append-capacity", "c2-append-stage", "c2-append-image",
        "c2-append-entries",
    ]
    decode = [f"c2-decode-{name}" for name in (
        "04", "05", "06a", "06b", "07", "08", "09", "10", "11", "12")]
    publish = [
        "c2-append-header", "c2-append-publish-names",
        "c2-append-publish-cells",
    ]
    rollback = ["c2-append-rollback"]
    schedule = emit + append_before_decode + decode + publish + rollback
    require(len(schedule) == 27 and all(name in rows for name in schedule),
            "transient append schedule drift")
    target_bytes = sum(int(rows[name]["file_size"]) for name in schedule)
    verifier_bytes = (int(rows["catalog-verifier"]["file_size"])
                      + int(rows["record-verifier"]["file_size"]))
    calls = len(schedule)
    directory_bytes = len(rows) * 32
    crc_input = calls * verifier_bytes + target_bytes + calls * (32 + directory_bytes)
    wiped = calls * verifier_bytes + target_bytes
    byte_visits = crc_input + 2 * wiped
    require((target_bytes, verifier_bytes, directory_bytes, crc_input,
             wiped, byte_visits) ==
            (32496, 2473, 1152, 131235, 99267, 329769),
            "Link-30 authenticated-transport arithmetic drift")

    runtime = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    require("#ifndef LISP65_C2_DIRECT_HOT_REFILL" in runtime
            and "c2_stream_product_materialize_entry(" in runtime,
            "direct hot-refill source seam drift")
    require(all(text in runtime for text in (
        "c2_session_emit_finalize(&length)",
        "c2_append_begin(length, &before, &main)",
        "result = vm_run_dir((int)main, 0, 0)",
        "c2_append_rollback(&before)",
    )), "transient session append/execute/rollback source path drift")

    return {
        "format": "lisp65-c2-product-link30-hot-refill-hardware-first-red-diagnosis-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-receipt-less-hardware-presmoke-stopped",
        "scope": {
            "candidate_product_sha256": PRODUCT_SHA,
            "structural_receipt": binding(STRUCTURAL),
            "deployment": binding(PRESMOKE / "deployment.json"),
            "presmoke_result": binding(LATENCY / "result.json"),
            "predecessor_latency_diagnosis": binding(LINK29_DIAGNOSIS),
            "new_product_links_after_first_red": 0,
            "product_source_changes_after_first_red": 0,
            "remaining_hardware_cases": "not-run",
        },
        "hardware_observation": {
            "boot_to_repl": {
                "result": "(3 159 3)",
                "upper_bound_frames": 927,
                "upper_bound_milliseconds": 18540,
                "limit_frames": 1500,
                "claim_limit": (
                    "The stable owned-counter read happened after prompt polling, "
                    "verified virtual typing and evaluation. It is an upper bound, "
                    "not an exact banner-to-prompt duration."
                ),
                "transcript": binding(boot_path),
            },
            "definition_first_call": {
                "setup": "(defun %c2h()(quote t))",
                "form": "(let((a(peek 215 250)))(let((r(eval(quote(%c2h)))))(list r a(peek 215 250))))",
                "result": cold_result,
                "start_frame": cold_start,
                "end_frame": cold_end,
                "elapsed_frames": cold_frames,
                "nominal_milliseconds": cold_frames * 20,
                "limit_frames": 16,
                "transcript": binding(cold_path),
            },
            "warm_second_call": {
                "form": "(let((a(peek 215 250)))(let((r(eval(quote(%c2h)))))(list r a(peek 215 250))))",
                "result": warm_result,
                "start_frame": warm_start,
                "end_frame": warm_end,
                "elapsed_frames": warm_frames,
                "nominal_milliseconds": warm_frames * 20,
                "limit_frames": 10,
                "transcript": binding(warm_path),
            },
            "correctness": "passed for both measured calls",
            "latency": "first red; both limits exceeded and no warm speedup",
        },
        "static_attribution": {
            "fixed_path": {
                "old_phase13_transport_per_literal_refill": "removed",
                "direct_shared_materializer": "present in the exact product closure",
                "measured_change_from_link29_manual_observation":
                    "approximately 5 seconds per form to 2.62 seconds per form",
            },
            "remaining_transient_append_path": {
                "authenticated_overlay_calls": calls,
                "target_payload_bytes": target_bytes,
                "verifier_payload_bytes_per_call": verifier_bytes,
                "catalog_directory_bytes_per_call": directory_bytes,
                "minimum_crc_input_bytes": crc_input,
                "minimum_wipe_bytes_each_for_memset_and_verify": wiped,
                "minimum_cpu_byte_visits_crc_plus_wipe": byte_visits,
                "schedule": schedule,
            },
        },
        "root_cause": {
            "primary": (
                "Every top-level eval still creates a transient C2I-v2 session image. "
                "Its emitter, append, suffix decode, publication and rollback traverse "
                "27 separately authenticated runtime-overlay slices. Each call reloads "
                "and revalidates the unchanged catalog and record verifiers, scans the "
                "unchanged 36-record directory, validates the target payload and wipes "
                "both verifier and target bytes. The immutable family proof is therefore "
                "recomputed 27 times per expression."
            ),
            "why_cold_equals_warm": (
                "The target function is defined once, but each measured eval of its call "
                "is itself newly compiled, appended, executed and rolled back. The direct "
                "hot materializer removes phase-13 authentication from VM refill; it does "
                "not amortize the transient session-append transaction that encloses every "
                "top-level form."
            ),
            "predecessor_hypothesis_resolution": (
                "Link 29 named the 27-call append path as a real secondary floor that could "
                "not be isolated while phase 13 also dominated the static banner. Link 30 "
                "removes phase 13 and measures that floor directly at 131 frames."
            ),
        },
        "bounded_next_probe": {
            "name": "generation-bound transaction authentication amortization",
            "goal": (
                "Validate the immutable session-family catalog once at the append transaction "
                "boundary, bind the resulting trust state to family plus generation, and retain "
                "per-record bounds plus per-payload CRC and wipe for every executed slice."
            ),
            "must_not_do": [
                "remove payload CRC or wipe checks",
                "trust across a family/generation change",
                "weaken the 1,792-byte slice cap",
                "claim the 15/16- or 10-frame target before hardware measurement",
            ],
            "required_gates": [
                "catalog, directory, build-id and generation mutation fail before any target executes",
                "record/payload mutation still fails at the target boundary",
                "abort, rollback and family switch invalidate transaction trust",
                "all capacity walls, especially 19-byte ordinary BSS and closed $e000, are reported",
                "one capacity/placement probe before any successor product link",
            ],
            "authorization": "not requested by this diagnosis; product work remains stopped",
        },
        "claim_limit": (
            "This immutable diagnosis binds one receipt-less Link-30 hardware first red and "
            "the exact static path that explains it. It is not hardware acceptance, promotion, "
            "capacity authorization or permission to implement the proposed follow-up."
        ),
    }


def main() -> int:
    try:
        value = build()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                          encoding="ascii")
        os.chmod(OUTPUT, 0o444)
        print(
            "c2-link30-latency-first-red: BOUND "
            "cold=131f warm=131f next=authorization-required"
        )
    except (OSError, UnicodeError, json.JSONDecodeError, DiagnosisError) as exc:
        print(f"c2-link30-latency-first-red: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
