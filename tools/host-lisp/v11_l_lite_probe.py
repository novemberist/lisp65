#!/usr/bin/env python3
"""Verify the bounded L-lite probe receipt without promoting its candidate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l-lite-probe-receipt.json"
)
COMPOSITION = ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
FOOTPRINT = ROOT / "build/products/workbench/overlay-stack-guard/footprint-audit.json"
RUNTIME = ROOT / "build/products/workbench/overlay-stack-guard/runtime-overlays-manifest.json"
SHELF = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin"


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.relative_to(ROOT)} is not an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_binding(row: dict[str, Any]) -> None:
    path = ROOT / str(row.get("path"))
    require(path.is_file(), f"missing bound file: {row.get('path')}")
    require(path.stat().st_size == row.get("bytes"), f"size drift: {row.get('path')}")
    require(sha256(path) == row.get("sha256"), f"SHA drift: {row.get('path')}")


def current_metrics(composition: dict[str, Any], footprint: dict[str, Any],
                    runtime: dict[str, Any]) -> dict[str, int]:
    slices = runtime.get("slices")
    require(isinstance(slices, list) and len(slices) == 44,
            "selected product must retain the 44-slice Wave-2 runtime bank")
    runtime_slices = [row for row in slices if "runtime" in row.get("roles", [])]
    max_runtime = max(int(row["file_size"]) for row in runtime_slices)
    installer = next(row for row in slices if row.get("id") == 37)
    boot_verify = next(row for row in slices if row.get("id") == 33)
    runtime_image = ROOT / (
        "build/products/workbench/overlay-stack-guard/"
        "lisp65-mvp-workbench.overlays.bin"
    )
    runtime_bytes = runtime_image.stat().st_size
    shelf_bytes = SHELF.stat().st_size
    return {
        "bank_post_boot_reserve_bytes": int(footprint["post_boot_reserve"]),
        "boot_fastpath_verify_slice_bytes": int(boot_verify["file_size"]),
        "codebuf_headroom": int(composition["codebuf"]["headroom"]),
        "directory_load_headroom": int(composition["directory"]["load_headroom"]),
        "directory_post_align_headroom": int(composition["directory"]["post_align_headroom"]),
        "ext_code_peak_headroom": int(composition["ext_code"]["worst_peak_headroom"]),
        "ext_code_post_headroom": int(composition["ext_code"]["post_headroom"]),
        "fixed_overlay_bytes": int(footprint["overlay_end"] - footprint["overlay_base"]),
        "fixed_overlay_headroom_bytes": 0,
        "installer_slice_bytes": int(installer["file_size"]),
        "installer_slice_headroom_bytes": 1792 - int(installer["file_size"]),
        "namepool_headroom_bytes": int(composition["namepool"]["headroom"]),
        "resident_island_bytes": 1668,
        "resident_island_reserve_bytes": 120,
        "runtime_overlay_bank_bytes": runtime_bytes,
        "runtime_overlay_bank_headroom_bytes": 65536 - runtime_bytes,
        "runtime_overlay_max_slice_bytes": max_runtime,
        "runtime_overlay_max_slice_headroom_bytes": 1792 - max_runtime,
        "shelf_bytes": shelf_bytes,
        "shelf_headroom_bytes": 65535 - shelf_bytes,
        "symbol_headroom": int(composition["symbols"]["headroom"]),
    }


def validate(receipt: dict[str, Any], *, verify_files: bool = True) -> None:
    require(receipt.get("format") == "lisp65-v11-l-lite-probe-receipt-v1",
            "receipt format drift")
    require(receipt.get("status") ==
            "core-probe-passed-color-rider-deferred-to-c2",
            "receipt status overclaims the deferred rider")
    rider = receipt.get("color_scroll_rider")
    require(isinstance(rider, dict)
            and rider.get("status") ==
                "final-fallback-to-c2-after-authorized-retry-hard-gate",
            "color-scroll fallback is not explicit")
    require(rider.get("resident_attempt", {}).get("result") ==
            "hard-gate-fail-fully-rolled-back",
            "resident attempt was not recorded as rejected")
    require(rider.get("runtime_overlay_attempt", {}).get("result") ==
            "hard-gate-fail-fully-rolled-back",
            "runtime-overlay attempt was not recorded as rejected")
    shaving = rider.get("shaving_attempt")
    require(isinstance(shaving, dict)
            and shaving.get("result") ==
                "failed-auto-fallback-to-c2-no-second-attempt",
            "authorized shaving fallback is not explicit")
    require(shaving.get("authorized_slice_ids") == [1, 6, 13, 14, 21, 30, 32, 33],
            "authorized shaving slice inventory drift")
    require(shaving.get("changes_rolled_back") is True,
            "failed shaving changes were not rolled back")
    require(shaving.get("behavior_parity") ==
            "not-applicable-no-shave-retained-after-hard-gate",
            "failed shaving attempt must not claim retained behavior parity")
    require(shaving.get("varied_relink_stability") ==
            "not-applicable-no-shave-retained-after-hard-gate",
            "failed shaving attempt must not claim retained relink stability")
    require(sum(int(row["packed_quantum_recovered"])
                for row in shaving.get("candidate_observations", [])) == 256,
            "failed shaving diagnostic arithmetic drift")
    retry = rider.get("authorized_retry")
    require(isinstance(retry, dict)
            and retry.get("result") ==
                "failed-final-fallback-to-c2-no-third-round",
            "authorized retry final fallback is not explicit")
    require(retry.get("observed_slice_32_candidate_bytes") == 957,
            "authorized retry slice-32 diagnostic drift")
    require(retry.get("changes_rolled_back") is True,
            "authorized retry changes were not rolled back")
    require(retry.get("product_link") == "not-run-after-first-red-hard-gate"
            and retry.get("riderless_define_negative") ==
                "not-run-after-first-red-hard-gate",
            "authorized retry overclaims post-gate work")
    require(retry.get("four_engine_parity") ==
            "not-applicable-no-shave-retained-after-first-red-hard-gate"
            and retry.get("varied_double_link_stability") ==
                "not-applicable-no-shave-retained-after-first-red-hard-gate",
            "authorized retry overclaims retained parity or stability")
    binding_gate = rider.get("binding_gate")
    require(isinstance(binding_gate, dict)
            and binding_gate.get("status") ==
                "passed-c2-deferred-gate-infrastructure"
            and binding_gate.get("selftest") == "pass-mutations-2",
            "C2-deferred rider binding gate is not closed")
    packaging = rider.get("post_fallback_gate_packaging")
    require(isinstance(packaging, dict)
            and packaging.get("classification") ==
                "fallback packaging, not a third product-integration attempt",
            "post-fallback gate packaging is not explicit")
    overlay_attempt = rider["runtime_overlay_attempt"]
    require(overlay_attempt.get("payload_alignment_bytes") == 256,
            "runtime-overlay alignment evidence drift")
    require(overlay_attempt.get("next_aligned_payload_offset") == 65536,
            "runtime-overlay overflow boundary drift")
    require(overlay_attempt.get("minimum_reclaim_for_one_allocation_quantum_bytes") == 192,
            "runtime-overlay minimum-reclaim evidence drift")
    require(receipt.get("gates", {}).get("hardware") == "not-run",
            "probe receipt must not claim hardware")
    known_issue = receipt.get("release_known_issue")
    require(isinstance(known_issue, dict)
            and known_issue.get("classification") ==
                "display-only-no-data-or-program-state-effect"
            and known_issue.get("cure") == "C2-runtime-layout-evolution"
            and known_issue.get("screen_clear_workaround") ==
                "rejected-scr-clear-does-not-reset-color-ram",
            "color-scroll Known Issue or rejected workaround drift")

    capacity = receipt.get("capacity")
    require(isinstance(capacity, dict), "capacity block missing")
    baseline = capacity.get("baseline_wave2")
    candidate = capacity.get("candidate_without_color_scroll")
    delta = capacity.get("delta")
    require(all(isinstance(value, dict) for value in (baseline, candidate, delta)),
            "capacity baseline/candidate/delta missing")
    require(set(baseline) == set(candidate) == set(delta), "capacity key drift")
    for key in baseline:
        require(candidate[key] - baseline[key] == delta[key],
                f"capacity arithmetic drift: {key}")

    if not verify_files:
        return
    bindings: list[dict[str, Any]] = []
    bindings.extend(receipt["candidate"]["artifacts"])
    truth = receipt["source_of_truth"]
    bindings.extend([truth["config"], truth["generator"]])
    bindings.extend(truth["generated_outputs"])
    bindings.append(receipt["baseline"]["receipt"])
    bindings.append(rider["isolated_mechanics"]["hardware_prg"])
    bindings.extend(binding_gate["bindings"])
    for row in bindings:
        verify_binding(row)

    measured = current_metrics(load(COMPOSITION), load(FOOTPRINT), load(RUNTIME))
    require(measured == candidate,
            f"live capacity drift: expected={candidate} measured={measured}")
    runtime = load(RUNTIME)
    last_slice = runtime["slices"][-1]
    recorded_last = overlay_attempt["existing_last_slice"]
    require({
        "id": int(last_slice["id"]),
        "file_offset": int(last_slice["file_offset"]),
        "file_size": int(last_slice["file_size"]),
        "end_offset": int(last_slice["file_offset"]) + int(last_slice["file_size"]),
    } == recorded_last, "runtime-overlay last-slice evidence drift")
    aligned_end = (recorded_last["end_offset"] + 255) & ~255
    require(aligned_end == overlay_attempt["next_aligned_payload_offset"],
            "runtime-overlay next-offset arithmetic drift")
    require(recorded_last["end_offset"] - (65536 - 256) ==
            overlay_attempt["minimum_reclaim_for_one_allocation_quantum_bytes"],
            "runtime-overlay reclaim-threshold arithmetic drift")


def check() -> None:
    validate(load(RECEIPT))
    print("v11-l-lite-probe: PASS core=passed color-scroll=deferred-to-c2 "
          "hardware=not-run")


def selftest() -> None:
    receipt = load(RECEIPT)
    validate(receipt)
    mutation = copy.deepcopy(receipt)
    mutation["capacity"]["delta"]["symbol_headroom"] += 1
    try:
        validate(mutation, verify_files=False)
    except ProbeError:
        pass
    else:
        raise ProbeError("capacity arithmetic mutation was accepted")
    mutation = copy.deepcopy(receipt)
    mutation["gates"]["hardware"] = "pass"
    try:
        validate(mutation, verify_files=False)
    except ProbeError:
        pass
    else:
        raise ProbeError("hardware overclaim mutation was accepted")
    print("v11-l-lite-probe: SELFTEST PASS mutations=2")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args(argv)
    try:
        selftest() if args.command == "selftest" else check()
    except (OSError, ValueError, KeyError, StopIteration, ProbeError) as exc:
        print(f"v11-l-lite-probe: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
