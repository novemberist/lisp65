#!/usr/bin/env python3
"""Bind the v1.6 defstruct patience-run First Red.

The priced floor expired without completion.  This gate preserves the narrow
claim, proves the stopped projection is byteidentical to the historical
180-second projection, and exposes the desk-pricing closure gap: the bound
counted 199,573 VM instructions but assigned no cost term to ordinary VM
instructions.  That gap is not asserted to be the product mechanism.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OWNER_COMMIT = "518196a3"
OLD_DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-pre-rollback-shadow-contact-device-receipt.json"
OLD_RESULT = EVIDENCE / "c2.3-v1.6-defstruct-pre-rollback-shadow-result-first-red-receipt.json"
DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-patience-contact-device-receipt.json"
PRICING = EVIDENCE / "c2.3-v1.6-defstruct-duration-pricing-receipt.json"
SESSION = ROOT / "config/c2-v16-defstruct-patience-session.json"
DRIVER = Path(__file__).resolve()
RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-patience-result-first-red-receipt.json"
FORMAT = "lisp65-c2.3-v1.6-defstruct-patience-result-first-red-v1"
RECORDED_ON = "2026-08-06"


class PatienceResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PatienceResultError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": digest(raw)}


def git_bind(commit: str, path: str) -> dict[str, Any]:
    resolved = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{resolved}:{path}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"commit": resolved, "path": path, "bytes": len(raw),
            "sha256": digest(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def captures(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {"diagnostic_record": value["diagnostic_record"]}
    for name, row in value["physical_bank0_captures"].items():
        result[f"bank0:{name}"] = row
    for name, row in value["backing_plane_oracles"].items():
        result[f"backing:{name}"] = row
    return result


def validate_binding(row: dict[str, Any]) -> None:
    path = ROOT / row["path"]
    require(path.is_file() and path.stat().st_size == row["bytes"]
            and digest(path.read_bytes()) == row["sha256"],
            f"capture binding drift: {row['path']}")


def derive() -> dict[str, Any]:
    old = load(OLD_DEVICE)
    old_result = load(OLD_RESULT)
    device = load(DEVICE)
    pricing = load(PRICING)
    session = load(SESSION)

    require(device["status"] ==
            "PATIENCE FLOOR EXPIRED WITH ACTIVE FORM; ONE STOPPED READ SET CAPTURED",
            "patience device status drift")
    quiet = device["quiet"]
    require(quiet["required_seconds"] == 780
            and quiet["elapsed_lower_bound_seconds"] >= 780
            and all(quiet[name] == 0 for name in (
                "monitor_accesses_before_floor", "screenshots_before_floor",
                "virtual_input_after_submit", "screen_polls_before_floor")),
            "zero-observation floor drift")
    require(device["first_observation"] == {
        "kind": "owner-physical-screen-only", "at_or_after_floor": True,
        "reported": "defstruct form still active; no result or prompt"},
        "owner postcondition drift")
    require(device["stop"]["count"] == 1
            and device["stop"]["already_stopped_before_reader"]
            and device["result"]["CPU_left_stopped"]
            and not device["result"]["completion_postcondition"]
            and not device["result"]["control_make_point_run"]
            and device["result"]["R_A_I_G"] is None,
            "one-stop/no-control boundary drift")

    require(device["pre_rollback_shadow"] == {
        "address": "0xc06b", "raw": "0x7f",
        "classification": "V5-FAIL-EDGE-UNREACHED", "forward_slot": None},
        "pre-rollback shadow drift")
    require(device["decoded_record"]["first-error.complete"]["state"] == "initial"
            and device["current"]["phase_owner"] == "0x00"
            and device["current"]["mem_oom"] == "0x00"
            and device["current"]["C2J_nonzero_bytes"] == 0,
            "clean stopped-state witnesses drift")
    require(device["mem_init"]["classification"] ==
            "INIT-BUILT-NO-FAILURE-REPRODUCED",
            "mem_init control drift")

    old_rows = captures(old)
    new_rows = captures(device)
    require(set(old_rows) == set(new_rows) and len(new_rows) == 14,
            "stopped projection inventory drift")
    comparison: list[dict[str, Any]] = []
    for name in sorted(new_rows):
        validate_binding(old_rows[name]); validate_binding(new_rows[name])
        identical = (old_rows[name]["bytes"], old_rows[name]["sha256"]) == (
            new_rows[name]["bytes"], new_rows[name]["sha256"])
        require(identical, f"180/780 stopped projection differs: {name}")
        comparison.append({"name": name, "bytes": new_rows[name]["bytes"],
                           "sha256": new_rows[name]["sha256"],
                           "byteidentical": True})

    inputs = pricing["bound_inputs"]
    calculation = pricing["calculation"]
    require(inputs["vm_instructions"] == 199573
            and calculation["operational_floor_seconds"] == 780
            and not any("instruction" in key for key in calculation),
            "pricing closure-gap premise drift")
    require(pricing["claim_limit"].startswith(
        "This is a conservative operational observation floor")
        and "not a measured defstruct completion time" in pricing["claim_limit"]
        and "mathematical worst case" in pricing["claim_limit"],
        "pricing claim limit drift")
    require(old_result["status"] ==
            "FIRST-RED-OBSERVATION-CROSSED-ACTIVE-DEFINITION",
            "historical 180-second authority drift")
    require(session["postconditions"]["incomplete"].startswith(
        "do not resume or retry; one commissioned stop"),
        "incomplete branch contract drift")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PATIENCE-FLOOR-NOT-COMPLETED; COST-MODEL-CLOSURE-FIRST-RED",
        "authorities": {"owner_commission": git_bind(OWNER_COMMIT, PLAN),
                        "session": bind(SESSION), "pricing": bind(PRICING),
                        "device": bind(DEVICE), "historical_180s_device": bind(OLD_DEVICE),
                        "historical_180s_result": bind(OLD_RESULT), "driver": bind(DRIVER)},
        "postcondition": {"priced_floor_seconds": 780,
                          "observed_elapsed_lower_bound_seconds":
                              quiet["elapsed_lower_bound_seconds"],
                          "form_completed": False, "live_prompt": False,
                          "make_point_control_run": False},
        "stopped_state": {"PC": device["stop"]["PC"],
                          "code_owner": device["stop"]["code_owner"]["selected_owner"],
                          "pre_rollback_shadow": "0x7f",
                          "v5_fail_edge_reached": False,
                          "first_error": "unreached", "phase_owner": "NONE",
                          "mem_oom": 0, "C2J": "CLEAR",
                          "mem_init": device["mem_init"]["classification"],
                          "CPU_left_stopped": True},
        "projection_comparison": {"captures": comparison,
                                  "byteidentical_count": len(comparison),
                                  "interpretation": (
                                      "The two post-stop projections are byteidentical. "
                                      "Because both are taken only after the commissioned "
                                      "monitor stop induced the known fail-closed hold, this "
                                      "does not prove the live operation made no progress.")},
        "pricing_closure": {"bound_vm_instructions": inputs["vm_instructions"],
                            "ordinary_VM_instruction_cost_term_present": False,
                            "classification":
                                "UNPRICED-PLAIN-VM-INSTRUCTION-TERM",
                            "claim": (
                                "The 780-second value remains a valid operational "
                                "observation floor, but it was not a completion upper "
                                "bound. The absent instruction-cost term is a desk-model "
                                "gap, not yet an attributed product mechanism.")},
        "decision": None,
        "next_question": (
            "Close the ordinary VM-instruction cost model or add an independent "
            "product-side completion/progress signal before any further timed contact."),
        "claim_limit": (
            "The form did not complete by the 780-second operational floor and "
            "was still active when the sole stop began after the recorded lower "
            "bound. This disproves completion within the commissioned patience "
            "window. It does not prove an infinite hang, a forward failure edge, "
            "a live-state plateau, or any R/A/I/G row."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT
            and value["status"] ==
                "PATIENCE-FLOOR-NOT-COMPLETED; COST-MODEL-CLOSURE-FIRST-RED",
            "result identity drift")
    require(value["postcondition"]["priced_floor_seconds"] == 780
            and value["postcondition"]["observed_elapsed_lower_bound_seconds"] >= 780
            and not value["postcondition"]["form_completed"]
            and not value["postcondition"]["make_point_control_run"],
            "postcondition claim drift")
    require(value["projection_comparison"]["byteidentical_count"] == 14
            and all(row["byteidentical"]
                    for row in value["projection_comparison"]["captures"]),
            "projection comparison drift")
    require(not value["stopped_state"]["v5_fail_edge_reached"]
            and value["stopped_state"]["first_error"] == "unreached"
            and value["stopped_state"]["C2J"] == "CLEAR"
            and value["decision"] is None,
            "narrow stopped-state result drift")
    require(value["pricing_closure"]["bound_vm_instructions"] == 199573
            and not value["pricing_closure"]["ordinary_VM_instruction_cost_term_present"]
            and "not yet an attributed product mechanism" in
                value["pricing_closure"]["claim"],
            "pricing closure claim drift")
    require("does not prove an infinite hang" in value["claim_limit"]
            and "live-state plateau" in value["claim_limit"],
            "claim limit widened")


def selftest() -> int:
    base = derive(); validate(base)
    mutations: list[tuple[str, list[Any], Any]] = [
        ("early-floor", ["postcondition", "priced_floor_seconds"], 779),
        ("short-elapsed", ["postcondition", "observed_elapsed_lower_bound_seconds"], 779),
        ("claim-complete", ["postcondition", "form_completed"], True),
        ("claim-control", ["postcondition", "make_point_control_run"], True),
        ("drop-capture", ["projection_comparison", "byteidentical_count"], 13),
        ("different-capture", ["projection_comparison", "captures", 0,
                               "byteidentical"], False),
        ("claim-v5", ["stopped_state", "v5_fail_edge_reached"], True),
        ("claim-error", ["stopped_state", "first_error"], "reached"),
        ("dirty-c2j", ["stopped_state", "C2J"], "ACTIVE"),
        ("select-row", ["decision"], "A"),
        ("drop-count", ["pricing_closure", "bound_vm_instructions"], 0),
        ("invent-instruction-price", ["pricing_closure",
                                      "ordinary_VM_instruction_cost_term_present"], True),
        ("attribute-product", ["pricing_closure", "claim"],
                              "This is the product mechanism."),
        ("claim-infinite", ["claim_limit"], "The product hangs forever."),
    ]
    rejected = 0
    for _, path, replacement in mutations:
        value = deepcopy(base); cursor: Any = value
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: validate(value)
        except PatienceResultError: rejected += 1
        else: raise PatienceResultError(f"mutation survived: {path}")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        value = {"status": "PASS", "mutations_rejected": selftest()}
    else:
        value = derive(); validate(value)
        if args.action == "write": write_json(RECEIPT, value)
        else: require(load(RECEIPT) == value, "result receipt differs from derivation")
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PatienceResultError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-v16-defstruct-patience-result: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
