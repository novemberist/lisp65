#!/usr/bin/env python3
"""Run C1 cutpoints 2..4 with the memory-driven hold carrier."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_hw_fixture as M  # noqa: E402


CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-memory-holds-link58-rebound-"
    "stage-bound-NONPROMOTABLE")
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link58-rebound-stage-bound.bin")
CARRIER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-memory-hold-carrier-"
    "nonpromotable-receipt.json")
CARRIER_STATUS = (
    "passed-capacity-and-gates-awaiting-separate-hardware-authorization")
OUT = ROOT / (
    "build/c2.2/"
    "c1-freezer-memory-hold-hardware-link58-attempt5-NONPROMOTABLE")
PRIOR_OUT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link58-attempt4-NONPROMOTABLE")
PRIOR_STATE = PRIOR_OUT / "hardware-state.json"
PRIOR_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-C1-Freezer-cutpoint2-continuation-"
    "hardware-first-red.json")
HARDWARE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-C1-Freezer-memory-hold-four-cutpoint-"
    "hardware-receipt.json")
CUTPOINT3_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-C1-Freezer-memory-hold-cutpoint3-continuation-"
    "hardware-first-red.json")


def configure() -> None:
    M.CARRIER = CARRIER
    M.CARRIER_BASENAME = CARRIER_BASENAME
    M.CARRIER_RECEIPT = CARRIER_RECEIPT
    M.CARRIER_RECEIPT_STATUS = CARRIER_STATUS
    M.DEPLOYMENT_STATUS = (
        "ready-nonpromotable-memory-hold-cutpoints-2-through-4")
    M.OUT = OUT
    M.HARDWARE_RECEIPT = HARDWARE_RECEIPT


def require_prior_cutpoint1() -> dict[str, Any]:
    M.require(PRIOR_STATE.is_file() and PRIOR_FIRST_RED.is_file(),
              "accepted cutpoint-1 hardware authority is absent")
    state = M.read_json(PRIOR_STATE)
    M.require(
        state["product_sha256"] == M.PRODUCT_SHA
        and len(state["cutpoints"]) >= 1
        and state["cutpoints"][0]["id"] == 1
        and state["cutpoints"][0]["status"] == "passed"
        and state["cutpoints"][0]["operator_call_output"] == "t",
        "accepted cutpoint-1 hardware authority drift")
    return deepcopy(state["cutpoints"][0])


def prepare(out: Path) -> None:
    require_prior_cutpoint1()
    M.prepare(out)
    deployment_path = out / "deployment.json"
    os.chmod(deployment_path, 0o644)
    deployment = M.read_json(deployment_path)
    deployment["format"] = (
        "lisp65-c2.2-C1-Freezer-memory-hold-hardware-fixture-v2")
    deployment["status"] = (
        "ready-nonpromotable-memory-hold-cutpoints-2-through-4")
    deployment["authority"]["accepted_cutpoint1_first_run"] = (
        M.bind(PRIOR_FIRST_RED))
    deployment["protocol"] = {
        "accepted_prior_cutpoints": [1],
        "current_device_appointment_cutpoints": [2, 3, 4],
        "return_from_Freezer_key": "F3",
        "hold_carrier": (
            "fresh load of 0x17e0 on every loop iteration; "
            "no register-resume assumption"),
    }
    deployment["execution_accounting"][
        "accepted_prior_product_device_runs"] = 1
    deployment["execution_accounting"][
        "current_device_appointment_runs"] = 0
    deployment_path.write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(deployment_path, 0o444)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture: PREPARE PASS "
        "accepted=1 pending=2,3,4 hardware=not-run")


def verify(out: Path) -> None:
    require_prior_cutpoint1()
    M.verify(out)
    deployment = M.read_json(out / "deployment.json")
    M.require(
        deployment["status"] ==
            "ready-nonpromotable-memory-hold-cutpoints-2-through-4"
        and deployment["protocol"]["accepted_prior_cutpoints"] == [1]
        and deployment["protocol"][
            "current_device_appointment_cutpoints"] == [2, 3, 4]
        and deployment["protocol"]["return_from_Freezer_key"] == "F3",
        "memory-hold hardware protocol drift")
    print(
        "c2-c1-freezer-memory-hold-hw-fixture: VERIFY PASS "
        "hardware=not-run next=separate-authorization")


def observe_boot(out: Path) -> None:
    prior = require_prior_cutpoint1()
    M.observe_boot(out)
    state = M.load_state(out)
    prior["evidence_origin"] = M.bind(PRIOR_FIRST_RED)
    state["format"] = (
        "lisp65-c2.2-C1-Freezer-memory-hold-hardware-state-v2")
    state["status"] = "passed-cutpoint-1-ready-for-cutpoint-2"
    state["device_runs"] = 2
    state["current_device_appointment_runs"] = 1
    state["next_cutpoint"] = 2
    state["cutpoints"] = [prior]
    M.save_state(out, state)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture: BOOT PASS "
        "accepted=1 next=cutpoint-2")


def confirm_output(out: Path, cutpoint: int, output: str) -> None:
    M.confirm_output(out, cutpoint, output)
    if cutpoint != 4:
        return
    os.chmod(HARDWARE_RECEIPT, 0o644)
    receipt = M.read_json(HARDWARE_RECEIPT)
    receipt["format"] = (
        "lisp65-c2.2-link58-C1-Freezer-memory-hold-"
        "hardware-receipt-v2")
    receipt["status"] = (
        "passed-C1-open-transaction-Freezer-four-cutpoint-"
        "two-appointment-fixture")
    receipt["authority"]["accepted_cutpoint1_first_run"] = (
        M.bind(PRIOR_FIRST_RED))
    receipt["hardware"]["device_runs"] = 2
    receipt["hardware"]["current_device_appointment_runs"] = 1
    receipt["hardware"]["current_device_appointment_cutpoints"] = [2, 3, 4]
    receipt["hardware"]["Freezer_return_key"] = "F3"
    receipt["execution_accounting"]["hardware_runs"] = 2
    receipt["execution_accounting"][
        "current_device_appointment_runs"] = 1
    receipt["verdict"]["hold_carrier"] = (
        "memory-driven at cutpoints 2 through 4")
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(HARDWARE_RECEIPT, 0o444)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture: COMPLETE "
        "accepted=1 measured=2,3,4 matrix=C1-pass")


def record_cutpoint3_first_red(
        out: Path, operator_observation: str) -> None:
    M.require(not CUTPOINT3_FIRST_RED_RECEIPT.exists(),
              "cutpoint-3 memory-hold First Red already exists")
    state = M.load_state(out)
    M.require(
        state["status"] == "passed-cutpoint-3-hold-awaiting-Freezer"
        and state["next_cutpoint"] == 3
        and len(state["cutpoints"]) == 3
        and state["cutpoints"][0]["status"] == "passed"
        and state["cutpoints"][1]["status"] == "passed"
        and state["cutpoints"][2]["id"] == 3,
        "hardware state is not the cutpoint-3 continuation First Red")
    root = out / "cutpoint-3"
    before = M.capture_paths(out, 3, "hold-before")
    after = M.capture_paths(out, 3, "hold-after")
    post = M.capture_paths(out, 3, "post")
    for captures in (before, after, post):
        M.require_captures(captures)
    for name in ("bank2", "bank3", "bank5"):
        M.require(
            before[name].read_bytes() == after[name].read_bytes(),
            f"cutpoint-3 thaw identity drifted in {name}")
    M.require(
        not M.e000_equal_except_contract(
            before["e000"].read_bytes(), after["e000"].read_bytes()),
        "cutpoint-3 thaw changed bound E000 bytes")
    before_journal = before["bank5"].read_bytes()[50752:50816]
    after_journal = after["bank5"].read_bytes()[50752:50816]
    post_journal = post["bank5"].read_bytes()[50752:50816]
    bank5_series = [
        root / f"first-red-bank5-t{index}.bin" for index in range(3)]
    control_series = [
        root / f"first-red-control-t{index}.bin" for index in range(3)]
    frame_series = [
        root / f"first-red-frame-t{index}.bin" for index in range(3)]
    for path in (*bank5_series, *control_series, *frame_series):
        M.require(path.is_file(), f"First Red capture absent: {path}")
    M.require(
        before_journal[:4] == b"C2J\0"
        and before_journal == after_journal == post_journal
        and post_journal != bytes(64)
        and len({path.read_bytes() for path in bank5_series}) == 1
        and bank5_series[0].read_bytes() == post["bank5"].read_bytes()
        and all(path.read_bytes() == bytes((0, 3))
                for path in control_series)
        and len({path.read_bytes() for path in frame_series}) == 1,
        "cutpoint-3 First Red lacks stable released-command witnesses")
    low_path = root / "first-red-bank0-t0.bin"
    screen_png = root / "first-red-screen.png"
    screen_ansi = root / "first-red-screen.ansi.txt"
    screen_text = root / "first-red-screen.txt"
    for path in (low_path, screen_png, screen_ansi, screen_text):
        M.require(path.is_file() and path.stat().st_size > 0,
                  f"cutpoint-3 First Red evidence absent: {path}")
    low = low_path.read_bytes()
    M.require(
        low[M.RTOV_FAULT] == 0
        and low[M.RTOV_FAMILY] == 2
        and low[M.C2_READY] == 1,
        "cutpoint-3 First Red lost the published product state")
    frame_value = int.from_bytes(frame_series[0].read_bytes(), "little")
    row = state["cutpoints"][2]
    row["status"] = "first-red-continuation-stalled-after-thaw"
    row["Freezer_operator_observation"] = operator_observation
    row["hold_after_thaw"] = M.bound_captures(after)
    row["post_release"] = M.bound_captures(post)
    row["checks"] = {
        "Bank2_thaw_identity": "byteidentical",
        "Bank3_thaw_identity": "byteidentical",
        "Bank5_C2D_export_C2J_thaw_identity": "byteidentical",
        "E000_thaw_identity": "byteidentical-except-FF83-FF84-FF86",
        "command_memory_after_release": [0, 3],
        "C2J_after_release": "unchanged-ACTIVE",
        "continuation_liveness": "failed",
        "frame_witness": f"stable-0x{frame_value:04x}",
    }
    state["status"] = (
        "first-red-cutpoint-3-memory-hold-continuation-stalled-after-thaw")
    state["next_cutpoint"] = None
    M.save_state(out, state)
    receipt = {
        "format": (
            "lisp65-c2.2-C1-Freezer-memory-hold-cutpoint3-"
            "continuation-first-red-v1"),
        "status": (
            "first-red-C1-header-before-exports-continuation-"
            "stalled-after-thaw"),
        "matrix_row": "C1",
        "matrix_status": "OPEN-first-red",
        "promotable": False,
        "product_identity": M.bind(M.paths()["product"]),
        "diagnostic_identity": {
            "carrier": M.bind(
                CARRIER / CARRIER_BASENAME),
            "resident_product_bytes_changed": 0,
            "hold_carrier": (
                "memory reload from 0x17e0 on every loop iteration"),
        },
        "authority": {
            "contract": M.bind(M.CONTRACT),
            "carrier": M.bind(CARRIER_RECEIPT),
            "deployment": M.bind(out / "deployment.json"),
            "accepted_cutpoint1": M.bind(PRIOR_FIRST_RED),
        },
        "hardware": {
            "accepted_cutpoints": [1, 2],
            "first_red_cutpoint": 3,
            "not_run_cutpoints": [4],
            "Freezer_return_key": "F3",
            "operator_observation": operator_observation,
            "command_reached_after_release": [0, 3],
            "vm_status": low[0x005B],
            "rtov_fault": low[M.RTOV_FAULT],
            "rtov_family": low[M.RTOV_FAMILY],
            "c2_ready": low[M.C2_READY],
            "C2J": {
                "state": "unchanged-ACTIVE",
                "bytes": 64,
                "sha256": M.hashlib.sha256(post_journal).hexdigest(),
            },
            "frame_witness": f"stable-0x{frame_value:04x}",
        },
        "captures": {
            "hold_before": M.bound_captures(before),
            "hold_after_thaw": M.bound_captures(after),
            "post_release": M.bound_captures(post),
            "postmortem_bank5": [M.bind(path) for path in bank5_series],
            "postmortem_controls": [
                M.bind(path) for path in control_series],
            "postmortem_frames": [M.bind(path) for path in frame_series],
            "postmortem_bank0": M.bind(low_path),
            "screen": {
                "png": M.bind(screen_png),
                "ansi": M.bind(screen_ansi),
                "text": M.bind(screen_text),
            },
        },
        "verdict": {
            "freeze_thaw_storage_identity": "passed",
            "register_carrier_assumption": "eliminated",
            "memory_command_release_observed": True,
            "continuation_liveness": "failed",
            "journal_cleanup": "not-reached-C2J-remained-ACTIVE",
            "cutpoint4": "not-run-first-red-discipline",
            "latency_attempts_consumed": 0,
        },
        "diagnosis_boundary": (
            "The memory-driven harness proves that command 0 was visible "
            "after a byte-identical thaw, yet execution did not reach C2J "
            "clear. C1 therefore remains open. The evidence does not yet "
            "assign cause between product continuation state and the "
            "platform Freezer resume frame."),
        "claim_limit": (
            "C1 hardware First Red only. No matrix closure, promotion, "
            "acceptance-chain result or release claim."),
        "next_gate": (
            "Class-C review of the cutpoint-3 continuation/resume state; "
            "no cutpoint-4 run or acceptance chain"),
    }
    CUTPOINT3_FIRST_RED_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(CUTPOINT3_FIRST_RED_RECEIPT, 0o444)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture: FIRST RED RECORDED "
        "cutpoint=3 command=0 reached=3 C2J=ACTIVE matrix-C1=OPEN")


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("prepare", "verify", "observe-boot", "observe-hold",
                 "observe-thaw", "confirm-output",
                 "record-cutpoint3-first-red"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--cutpoint", type=int, choices=(2, 3, 4))
    parser.add_argument("--freezer-output")
    parser.add_argument("--output")
    parser.add_argument("--operator-observation")
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        if args.mode == "prepare":
            prepare(out)
        elif args.mode == "verify":
            verify(out)
        elif args.mode == "observe-boot":
            observe_boot(out)
        elif args.mode == "observe-hold":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.observe_hold(out, args.cutpoint)
        elif args.mode == "observe-thaw":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(args.freezer_output is not None,
                      "--freezer-output is required")
            M.observe_thaw(out, args.cutpoint, args.freezer_output)
        elif args.mode == "record-cutpoint3-first-red":
            M.require(args.operator_observation is not None,
                      "--operator-observation is required")
            record_cutpoint3_first_red(
                out, args.operator_observation)
        else:
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(args.output is not None, "--output is required")
            confirm_output(out, args.cutpoint, args.output)
    except (
        M.FixtureError, M.HW.PreSmokeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-memory-hold-hw-fixture: FIRST RED: "
            + str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
