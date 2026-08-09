#!/usr/bin/env python3
"""Close the missing ordinary-VM term in the defstruct patience price.

This is deliberately a pricing closure, not a completion-time oracle.  The
exact Phase-A instruction count is combined with the historical target VM
dispatch constant.  A second, independent lane scales the measured first and
idempotent require wall times by their exact instruction counts; that lane is
kept separate because it already contains window, refill and native work.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, getcontext
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
OLD_PRICE = ARCH / "c2.3-v1.6-defstruct-duration-pricing-receipt.json"
PATIENCE = ARCH / "c2.3-v1.6-defstruct-patience-result-first-red-receipt.json"
VM_AUTHORITY = EVIDENCE / (
    "post-release/v125-editor-input-latency-host-accounting-receipt.json")
REQUIRE_AUTHORITY = ARCH / (
    "c2.2-phase-m1-require-latency-measurement-receipt.json")
RECEIPT = ARCH / "c2.3-v1.6-defstruct-vm-cost-closure-receipt.json"
PLAN_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OWNER_COMMIT = "b8820ecadb875b0b581c9df9fd621c45c99bf75e"
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v1.6-defstruct-vm-cost-closure-v1"
RECORDED_ON = "2026-08-06"
getcontext().prec = 40


class CostError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CostError(message)


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


def decimal_text(value: Decimal, places: int = 9) -> str:
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def derive() -> dict[str, Any]:
    old = load(OLD_PRICE)
    patience = load(PATIENCE)
    vm = load(VM_AUTHORITY)
    req = load(REQUIRE_AUTHORITY)

    counts = old["bound_inputs"]
    instructions = counts["vm_instructions"]
    require(instructions == 199573, "exact defstruct VM instruction count drift")
    require(old["calculation"]["window_budget_frames"] == 26113
            and old["calculation"]["append_budget_frames"] == 882
            and old["calculation"]["operational_floor_seconds"] == 780,
            "prior patience price drift")
    require(patience["pricing_closure"] == {
        "bound_vm_instructions": 199573,
        "claim": (
            "The 780-second value remains a valid operational observation floor, "
            "but it was not a completion upper bound. The absent instruction-cost "
            "term is a desk-model gap, not yet an attributed product mechanism."),
        "classification": "UNPRICED-PLAIN-VM-INSTRUCTION-TERM",
        "ordinary_VM_instruction_cost_term_present": False,
    }, "patience First-Red pricing premise drift")
    require(patience["postcondition"]["observed_elapsed_lower_bound_seconds"] == 995
            and patience["postcondition"]["form_completed"] is False,
            "patience observation premise drift")

    constants = vm["bound_constants"]
    cycles_per_instruction = constants["historical_cycles_per_vm_instruction"]
    cpu_hz = constants["target_cpu_hz"]
    require(cycles_per_instruction == 1100 and cpu_hz == 40000000,
            "historical VM dispatch constants drift")
    projection_claim = vm["measurements"][
        "coalesced_ten_keys_per_render"]["bounded_time_projection"]
    require(projection_claim["historical_vm_instruction_microseconds"] == 27.5
            and "projection, not a target timing measurement"
            in projection_claim["claim_limit"],
            "historical VM projection claim boundary drift")

    hz = Decimal(str(counts["frame_hz"]))
    instruction_seconds = (Decimal(instructions) * Decimal(cycles_per_instruction)
                           / Decimal(cpu_hz))
    instruction_frames_exact = instruction_seconds * hz
    instruction_frames = math.ceil(instruction_frames_exact)
    base_frames = (old["calculation"]["window_budget_frames"]
                   + old["calculation"]["append_budget_frames"]
                   + instruction_frames)
    margin_frames = math.ceil(base_frames / 2)
    total_frames = base_frames + margin_frames
    total_seconds = Decimal(total_frames) / hz
    operational_floor = math.ceil(total_seconds)

    target = req["hardware_wall_truth"][
        "current_valid_full_reset_product_bound_media"]
    first = req["host_measurement"]["first_require"]
    repeat = req["host_measurement"]["idempotent_repeat"]
    require(target["first_require_seconds"] == 12
            and target["idempotent_repeat_seconds"] == 9
            and first["vm_instructions"] == 136765
            and repeat["vm_instructions"] == 134788,
            "require target/host instruction authority drift")
    first_amortized = Decimal(12) / Decimal(first["vm_instructions"])
    repeat_amortized = Decimal(9) / Decimal(repeat["vm_instructions"])
    first_scaled = first_amortized * Decimal(instructions)
    repeat_scaled = repeat_amortized * Decimal(instructions)
    observed = patience["postcondition"]["observed_elapsed_lower_bound_seconds"]

    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "VM-COST-TERM-CLOSED; NO-COMPLETION-UPPER-BOUND",
        "authorities": {
            "owner_commission": git_bind(OWNER_COMMIT, PLAN_PATH),
            "prior_duration_price": bind(OLD_PRICE),
            "patience_First_Red": bind(PATIENCE),
            "historical_VM_projection": bind(VM_AUTHORITY),
            "require_target_wall_and_host_counts": bind(REQUIRE_AUTHORITY),
            "driver": bind(DRIVER),
        },
        "exact_workload": {
            "vm_instructions": instructions,
            "initial_windows": counts["initial_windows"],
            "refills": counts["refills"],
            "persistent_appends": counts["persistent_appends"],
        },
        "ordinary_VM_cost_term": {
            "historical_cycles_per_instruction": cycles_per_instruction,
            "target_cpu_hz": cpu_hz,
            "microseconds_per_instruction": "27.500000000",
            "instruction_seconds": decimal_text(instruction_seconds),
            "instruction_frames_exact": decimal_text(instruction_frames_exact),
            "instruction_frames_charged_ceil": instruction_frames,
            "authority_kind": "historical target projection",
            "not_claimed": "current target timing measurement",
        },
        "completed_structural_price_lane": {
            "window_frames": old["calculation"]["window_budget_frames"],
            "append_frames": old["calculation"]["append_budget_frames"],
            "ordinary_VM_frames": instruction_frames,
            "base_frames": base_frames,
            "margin_rule": "50 percent, rounded upward in frames",
            "margin_frames": margin_frames,
            "total_frames": total_frames,
            "exact_seconds": decimal_text(total_seconds),
            "operational_floor_seconds": operational_floor,
            "operational_floor_minutes": decimal_text(
                Decimal(operational_floor) / Decimal(60), 6),
            "hours_scale": operational_floor >= 3600,
        },
        "independent_whole_wall_amortization": {
            "rule": (
                "independent cross-check only; never additive with the structural "
                "lane because measured require wall time already includes dispatch, "
                "window, refill and native work"),
            "first_require": {
                "seconds": 12, "vm_instructions": first["vm_instructions"],
                "microseconds_per_instruction_amortized": decimal_text(
                    first_amortized * Decimal(1000000)),
                "scaled_defstruct_seconds": decimal_text(first_scaled),
            },
            "idempotent_repeat": {
                "seconds": 9, "vm_instructions": repeat["vm_instructions"],
                "microseconds_per_instruction_amortized": decimal_text(
                    repeat_amortized * Decimal(1000000)),
                "scaled_defstruct_seconds": decimal_text(repeat_scaled),
            },
        },
        "decision": {
            "observed_incomplete_after_at_least_seconds": observed,
            "completed_price_floor_seconds": operational_floor,
            "observed_beyond_completed_price_floor_seconds": observed - operational_floor,
            "hours_scale_product_finding": False,
            "price_explains_patience_red": False,
            "longer_patience_contact_authorized_by_price": False,
            "required_next_instrument": "independent product-side progress witness",
            "reason": (
                "The missing ordinary VM term adds only about 5.49 seconds before "
                "margin. The completed price remains minutes-scale and is not a "
                "mathematical completion bound; the 995-second non-completion must "
                "be separated into live progress versus a loop by an independent "
                "witness, not by another guessed wait."),
        },
        "accounting": {"product_bytes_changed": 0, "product_links": 0,
                       "hardware_runs": 0},
        "claim_limit": (
            "This closes the named ordinary-VM pricing omission. It does not turn "
            "historical projection constants or require-wide amortization into a "
            "current per-op target measurement; it does not model target GC/native "
            "tails, prove a completion upper bound, prove life or a loop, authorize "
            "a longer wait, change product bytes, or consume hardware."),
    }
    return value


def audit(value: dict[str, Any]) -> None:
    require(value == derive(), "VM-cost closure receipt differs from derivation")


def set_path(value: dict[str, Any], path: list[str], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[list[str], Any]] = [
        (["status"], "COMPLETION-BOUND-PROVED"),
        (["exact_workload", "vm_instructions"], 199572),
        (["ordinary_VM_cost_term", "historical_cycles_per_instruction"], 1099),
        (["ordinary_VM_cost_term", "instruction_frames_charged_ceil"], 0),
        (["ordinary_VM_cost_term", "authority_kind"], "current measurement"),
        (["completed_structural_price_lane", "ordinary_VM_frames"], 0),
        (["completed_structural_price_lane", "margin_frames"], 0),
        (["completed_structural_price_lane", "hours_scale"], True),
        (["independent_whole_wall_amortization", "rule"], "additive"),
        (["independent_whole_wall_amortization", "first_require",
          "vm_instructions"], 1),
        (["decision", "hours_scale_product_finding"], True),
        (["decision", "price_explains_patience_red"], True),
        (["decision", "longer_patience_contact_authorized_by_price"], True),
        (["decision", "required_next_instrument"], "another timed wait"),
        (["accounting", "product_bytes_changed"], 1),
        (["accounting", "hardware_runs"], 1),
        (["claim_limit"], "defstruct completes within the priced floor"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base); set_path(trial, path, replacement)
        try:
            audit(trial)
        except CostError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise CostError(f"VM-cost mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "floor_seconds": base["completed_structural_price_lane"][
                "operational_floor_seconds"], "rejected": rejected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        value = derive()
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        result = {"status": "WRITTEN", "floor_seconds":
                  value["completed_structural_price_lane"][
                      "operational_floor_seconds"]}
    elif args.action == "selftest":
        result = selftest()
    else:
        audit(load(RECEIPT))
        result = {"status": "PASS", "mutations": 17,
                  "floor_seconds": derive()["completed_structural_price_lane"][
                      "operational_floor_seconds"]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CostError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT VM COST CLOSURE FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
