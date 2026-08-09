#!/usr/bin/env python3
"""Price the observation-safe defstruct patience window.

The calculation is deliberately conservative. The Phase-A reconstruction
binds every initial code-window load and refill in the full require/defstruct
sequence. Existing target evidence does not authorize scaling the measured
two-byte DMA cost to a code-window job, so each window event receives one
whole calibrated target frame. Persistent appends are charged again at the
maximum frame count in the twelve-cycle physical definition curve. This
double-counting is intentional; the resulting operational ceiling receives a
further fifty-percent margin before any observation is permitted.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence"
ARCH = EVIDENCE / "architecture-blocks"
PHASE_A = ARCH / "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json"
APPEND_CURVE = EVIDENCE / "r5/c1-definition-call-session-curve-receipt.json"
DMA_COST = EVIDENCE / "post-release/v122-halt-b-preparation-receipt.json"
TIME_CAL = ARCH / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
REQUIRE_COST = ARCH / "c2.2-phase-m1-require-latency-measurement-receipt.json"
SHADOW_RESULT = ARCH / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-result-first-red-receipt.json")
SESSION = ROOT / "config/c2-v16-defstruct-patience-session.json"
RECEIPT = ARCH / "c2.3-v1.6-defstruct-duration-pricing-receipt.json"
DRIVER = Path(__file__).resolve()
OWNER_COMMIT = "518196a3"
PLAN_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"

FORMAT = "lisp65-c2.3-v1.6-defstruct-duration-pricing-v1"
RECORDED_ON = "2026-08-06"
WINDOW_FRAME_CEILING = 1
MARGIN_NUMERATOR = 1
MARGIN_DENOMINATOR = 2


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"commit": full, "path": path, "bytes": len(raw), "sha256": sha(raw)}


def collect_counts(phase_a: dict[str, Any]) -> dict[str, int]:
    require_only = phase_a["require_only_control"]["require"]
    sequence = phase_a["windowed_sequence"]
    forms = sequence["forms"]
    require(len(forms) == 11, "full sequence no longer has eleven forms")
    persistent = sum(row.get("kind") == "persistent-definition" for row in forms)
    initial = require_only["window_trace"]["initial_window_count"]
    refills = require_only["window_trace"]["refill_count"]
    instructions = require_only["steps"]
    expansion = sequence["expansion"]
    initial += expansion["window_trace"]["initial_window_count"]
    refills += expansion["window_trace"]["refill_count"]
    instructions += expansion["steps"]
    for row in forms:
        initial += row["compile_window_trace"]["initial_window_count"]
        refills += row["compile_window_trace"]["refill_count"]
        instructions += row["compiler_steps"]
        if row.get("evaluation_window_trace") is not None:
            initial += row["evaluation_window_trace"]["initial_window_count"]
            refills += row["evaluation_window_trace"]["refill_count"]
            instructions += row["evaluation_steps"]
    initial += sequence["constructor"]["window_trace"]["initial_window_count"]
    refills += sequence["constructor"]["window_trace"]["refill_count"]
    instructions += sequence["constructor"]["steps"]
    counts = {"forms": len(forms), "persistent_appends": persistent,
              "initial_windows": initial, "refills": refills,
              "vm_instructions": instructions}
    require(counts == {"forms": 11, "persistent_appends": 9,
                       "initial_windows": 12310, "refills": 13803,
                       "vm_instructions": 199573},
            "Phase-A sequence counts drift")
    return counts


def derive() -> dict[str, Any]:
    phase_a = load(PHASE_A)
    curve = load(APPEND_CURVE)
    dma = load(DMA_COST)
    time_cal = load(TIME_CAL)
    require_cost = load(REQUIRE_COST)
    shadow = load(SHADOW_RESULT)
    session = load(SESSION)
    counts = collect_counts(phase_a)

    append_frames = curve["analysis"]["maximum_frames"]
    require(append_frames == 98 and len(curve["samples"]) == 12,
            "physical append-cycle ceiling drift")
    measurement = dma["measurement"]
    require(measurement["direct_scope"] == "2-byte vm_dma symbol-value reads"
            and measurement["frames_per_1000_reads"] == 0
            and measurement["microseconds_per_read_upper_bound"] == 20,
            "two-byte DMA timing authority drift")
    hz = time_cal["M4_time"]["frames_per_second"]
    require(abs(hz - 51.96615805290813) < 1e-12,
            "target frame calibration drift")
    hardware = require_cost["hardware_wall_truth"][
        "current_valid_full_reset_product_bound_media"]
    require(hardware["first_require_seconds"] == 12,
            "physical require wall-time authority drift")
    require(shadow["status"] == "FIRST-RED-OBSERVATION-CROSSED-ACTIVE-DEFINITION"
            and shadow["pre_rollback_shadow"]["value"] == "0x7f"
            and not shadow["pre_rollback_shadow"]["v5_fail_edge_reached"],
            "shadow-result premise drift")

    require_windows = phase_a["require_only_control"]["require"]["window_trace"]
    require_events = (require_windows["initial_window_count"]
                      + require_windows["refill_count"])
    observed_require_frames = hardware["first_require_seconds"] * hz
    aggregate_frames_per_event = observed_require_frames / require_events
    conservatism_factor = WINDOW_FRAME_CEILING / aggregate_frames_per_event

    window_events = counts["initial_windows"] + counts["refills"]
    window_frames = window_events * WINDOW_FRAME_CEILING
    append_budget_frames = counts["persistent_appends"] * append_frames
    base_frames = window_frames + append_budget_frames
    margin_frames = math.ceil(base_frames * MARGIN_NUMERATOR / MARGIN_DENOMINATOR)
    total_frames = base_frames + margin_frames
    exact_seconds = total_frames / hz
    floor_seconds = math.ceil(exact_seconds)
    require(floor_seconds == 780, "operational patience floor drift")

    quiet = session["quiet_contract"]
    require(session["format"] == "lisp65-c2.3-v1.6-defstruct-patience-session-v1"
            and quiet["minimum_seconds_after_defstruct_submission"] == floor_seconds
            and all(quiet[name] == 0 for name in (
                "monitor_accesses", "screenshots", "virtual_input",
                "screen_polling", "jtag_reads"))
            and quiet["early_owner_visual_check"] is False
            and session["accounting"] == {
                "product_bytes_changed": 0, "product_links": 0,
                "device_contacts_authorized": 1, "contact_started": False},
            "patience-session zero-observation contract drift")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PRICED-780-SECOND-ZERO-OBSERVATION-FLOOR",
        "authorities": {
            "owner_commission": git_bind(OWNER_COMMIT, PLAN_PATH),
            "phase_A_counts": bind(PHASE_A),
            "physical_append_curve": bind(APPEND_CURVE),
            "two_byte_DMA_measurement": bind(DMA_COST),
            "target_time_calibration": bind(TIME_CAL),
            "physical_require_wall_time": bind(REQUIRE_COST),
            "shadow_result": bind(SHADOW_RESULT),
            "session_contract": bind(SESSION),
            "driver": bind(DRIVER),
        },
        "bound_inputs": {
            **counts,
            "frame_hz": hz,
            "append_cycle_ceiling_frames": append_frames,
            "append_cycle_samples": 12,
            "window_event_ceiling_frames": WINDOW_FRAME_CEILING,
            "window_event_rule": (
                "one complete calibrated target frame per initial load or refill; "
                "the two-byte DMA result is not bulk-scaled"),
            "two_byte_DMA_upper_bound_microseconds": 20,
            "two_byte_DMA_bulk_scaling_authorized": False,
        },
        "cross_checks": {
            "physical_require_seconds": 12,
            "physical_require_window_events": require_events,
            "physical_require_aggregate_frames_per_window_event": round(
                aggregate_frames_per_event, 12),
            "one_frame_window_budget_over_observed_aggregate": round(
                conservatism_factor, 6),
            "append_work_double_counted": True,
            "reason": (
                "the 98-frame definition-to-first-call ceiling already contains "
                "compile/window work; charging all window events as well is intentional"),
        },
        "calculation": {
            "window_events": window_events,
            "window_budget_frames": window_frames,
            "append_budget_frames": append_budget_frames,
            "base_frames": base_frames,
            "base_seconds": base_frames / hz,
            "safety_margin": "50 percent, rounded upward in frames",
            "margin_frames": margin_frames,
            "total_frames": total_frames,
            "exact_seconds": exact_seconds,
            "operational_floor_seconds": floor_seconds,
            "operational_floor_minutes": floor_seconds / 60,
            "historical_180_second_observation_below_floor": True,
        },
        "contact": {
            "authorized_by_owner_commission": True,
            "started": False,
            "zero_observation_seconds": floor_seconds,
            "first_observation": "single physical-screen postcondition look",
            "success_control": "(make-point 3 4) => (point 3 4)",
            "incomplete_action": "one stop and existing full read set; no resume or retry",
        },
        "accounting": {"product_bytes_changed": 0, "product_links": 0,
                       "hardware_runs": 0},
        "claim_limit": (
            "This is a conservative operational observation floor, not a measured "
            "defstruct completion time or a proof of a mathematical worst case. It "
            "does not scale the two-byte DMA result to code windows, claim completion, "
            "exonerate or condemn defstruct, change product bytes, or consume the one "
            "authorized patience contact."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive(), "duration-pricing receipt differs from derivation")


def set_path(value: dict[str, Any], path: list[str], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[list[str], Any]] = [
        (["status"], "PRICED-180-SECOND-FLOOR"),
        (["bound_inputs", "forms"], 10),
        (["bound_inputs", "persistent_appends"], 8),
        (["bound_inputs", "initial_windows"], 12309),
        (["bound_inputs", "refills"], 13802),
        (["bound_inputs", "append_cycle_ceiling_frames"], 97),
        (["bound_inputs", "window_event_ceiling_frames"], 0),
        (["bound_inputs", "two_byte_DMA_bulk_scaling_authorized"], True),
        (["calculation", "margin_frames"], 0),
        (["calculation", "operational_floor_seconds"], 779),
        (["calculation", "historical_180_second_observation_below_floor"], False),
        (["contact", "zero_observation_seconds"], 180),
        (["contact", "first_observation"], "screenshot poll"),
        (["contact", "started"], True),
        (["accounting", "hardware_runs"], 1),
        (["claim_limit"], "defstruct completes within 780 seconds"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base)
        set_path(trial, path, replacement)
        try:
            audit(trial)
        except PricingError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise PricingError(f"pricing mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "floor_seconds": base["calculation"]["operational_floor_seconds"],
            "rejected": rejected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        value = derive()
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        result = {"status": "WRITTEN", "floor_seconds": 780}
    elif args.action == "selftest":
        result = selftest()
    else:
        audit(load(RECEIPT))
        result = {"status": "PASS", "mutations": 16,
                  "floor_seconds": 780, "floor_minutes": 13}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT DURATION PRICING FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
