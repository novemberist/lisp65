#!/usr/bin/env python3
"""Verify and decode the transport-proof v1.6 D2 RAM entry witness."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v126_editor_stall_device as MONITOR  # noqa: E402


class RAMEntryWitnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RAMEntryWitnessError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def bound_bytes(row: dict[str, Any], label: str) -> bytes:
    path = ROOT / row["path"]
    require(path.is_file() and not path.is_symlink(), f"{label} absent: {path}")
    payload = path.read_bytes()
    require(len(payload) == row["bytes"] and sha256(path) == row["sha256"],
            f"{label} binding drift")
    return payload


def prg_slice(payload: bytes, address: int, size: int) -> bytes:
    require(len(payload) >= 2, "diagnostic PRG truncated")
    load_address = int.from_bytes(payload[:2], "little")
    require(load_address == 0x2001, "diagnostic PRG load address drift")
    offset = 2 + address - load_address
    require(2 <= offset and offset + size <= len(payload),
            "diagnostic PRG witness range absent")
    return payload[offset:offset + size]


def validate_bootstrap_contract(witness: dict[str, Any]) -> None:
    require(witness["RAM_mapping_activation_address"] == 0x2024,
            "RAM-mapping activation address drift")
    require(witness["RAM_mapping_activation_bytes"] == "a22f8600a23e8601",
            "complete $00/$01 RAM-mapping pair absent")
    mapping_end = (witness["RAM_mapping_activation_address"]
                   + len(bytes.fromhex(witness["RAM_mapping_activation_bytes"])))
    require(witness["RAM_mapping_active_before_entry_call"]
            and witness["hook"] >= mapping_end,
            "entry call precedes complete $00/$01 RAM mapping")


def verify(deployment_path: Path) -> dict[str, Any]:
    deployment = load(deployment_path)
    witness = deployment["entry_witness"]
    require(witness == {
        "method": "RAM-store-at-_start",
        "hook": 0x202C,
        "routine": 0xC03F,
        "stamp_address": 0xC07A,
        "stamp_offset": 59,
        "stamp_initial": 0x6B,
        "stamp_value": 0x44,
        "routine_bytes": "a2448e30d08e7ac060",
        "displaced_bytes_replayed": "a2448e30d0",
        "RAM_mapping_activation_address": 0x2024,
        "RAM_mapping_activation_bytes": "a22f8600a23e8601",
        "RAM_mapping_active_before_entry_call": True,
        "readback_bytes": 1,
        "record_fully_reset_before_defstruct": True,
    }, "deployment RAM entry witness contract drift")
    validate_bootstrap_contract(witness)
    diagnostic = bound_bytes(deployment["diagnostic"]["prg"], "diagnostic PRG")
    control = bound_bytes(deployment["control"]["prg"], "control PRG")
    mapping = bytes.fromhex(witness["RAM_mapping_activation_bytes"])
    require(prg_slice(control, witness["RAM_mapping_activation_address"],
                      len(mapping)) == mapping,
            "control _start RAM-mapping authority drift")
    require(prg_slice(diagnostic, witness["RAM_mapping_activation_address"],
                      len(mapping)) == mapping,
            "diagnostic entry hook runs before RAM mapping")
    require(prg_slice(control, witness["hook"], 5) == bytes.fromhex("a2448e30d0"),
            "control _start displaced-byte authority drift")
    require(prg_slice(diagnostic, witness["hook"], 5) == bytes.fromhex("203fc0eaea"),
            "diagnostic _start RAM-witness hook drift")
    require(prg_slice(diagnostic, witness["routine"], 9) ==
            bytes.fromhex(witness["routine_bytes"]),
            "diagnostic RAM entry routine drift")
    require(prg_slice(diagnostic, witness["stamp_address"], 1) == b"\x6b",
            "boot-image entry stamp initial value drift")
    reset = bound_bytes(deployment["record"]["reset"], "record reset")
    require(len(reset) == 65 and reset[witness["stamp_offset"]] == 0x6B,
            "canonical measured-form record reset drift")
    require(reset[:9] != bytes.fromhex(witness["routine_bytes"]),
            "bootstrap routine survived in measured-form reset")
    return witness


def classify(*, return_submitted: bool, method: str, observed: bytes,
             expected: int, full_reset_before_defstruct: bool) -> dict[str, Any]:
    require(return_submitted, "virtual RETURN was not submitted")
    require(method == "RAM-store-at-_start",
            "entry proof relies on a live monitor breakpoint across launch")
    require(len(observed) == 1, "entry stamp readback must be exactly one byte")
    require(expected != 0, "entry stamp expectation is zero")
    require(observed[0] == expected,
            f"RAM entry stamp did not fire: got=0x{observed[0]:02x} expected=0x{expected:02x}")
    require(full_reset_before_defstruct,
            "entry bootstrap record is not fully reset before defstruct")
    return {
        "return_submitted": True,
        "entry_stamp_fired": True,
        "method": method,
        "observed": f"0x{observed[0]:02x}",
        "expected": f"0x{expected:02x}",
        "transport_proof": "RAM store executed on the diagnostic _start path",
        "live_monitor_breakpoint_required": False,
        "record_fully_reset_before_defstruct": True,
    }


def selftest(deployment_path: Path) -> dict[str, Any]:
    witness = verify(deployment_path)
    passed = classify(return_submitted=True, method=witness["method"],
                      observed=bytes((witness["stamp_value"],)),
                      expected=witness["stamp_value"],
                      full_reset_before_defstruct=True)
    cases = {
        "missing-return": dict(return_submitted=False, method=witness["method"],
                               observed=b"\x44", expected=0x44,
                               full_reset_before_defstruct=True),
        "live-monitor-breakpoint-across-launch": dict(
            return_submitted=True,
            method="live-monitor-breakpoint-across-launch",
            observed=b"\x44", expected=0x44,
            full_reset_before_defstruct=True),
        "zero-stamp": dict(return_submitted=True, method=witness["method"],
                           observed=b"\x00", expected=0x44,
                           full_reset_before_defstruct=True),
        "record-sentinel-not-entry": dict(
            return_submitted=True, method=witness["method"],
            observed=b"\x6b", expected=0x44,
            full_reset_before_defstruct=True),
        "ambiguous-read-width": dict(return_submitted=True, method=witness["method"],
                                     observed=b"\x44\x44", expected=0x44,
                                     full_reset_before_defstruct=True),
        "partial-reset-before-defstruct": dict(
            return_submitted=True, method=witness["method"],
            observed=b"\x44", expected=0x44,
            full_reset_before_defstruct=False),
    }
    rejected: dict[str, str] = {}
    for name, arguments in cases.items():
        try:
            classify(**arguments)
        except RAMEntryWitnessError as error:
            rejected[name] = str(error)
        else:
            raise RAMEntryWitnessError(f"RAM-entry mutation survived: {name}")
    for name, path, replacement in (
        ("half-mapped-entry-hook", "hook", 0x2028),
        ("truncate-mapping-pair", "RAM_mapping_activation_bytes", "a22f8600"),
    ):
        trial = deepcopy(witness)
        trial[path] = replacement
        try:
            validate_bootstrap_contract(trial)
        except RAMEntryWitnessError as error:
            rejected[name] = str(error)
        else:
            raise RAMEntryWitnessError(f"RAM-entry mutation survived: {name}")
    require(len(rejected) == 8, "RAM-entry mutation count drift")
    return {"entry_witness": witness, "synthetic_fired_stamp": passed,
            "mutations_rejected": rejected}


def decode(deployment_path: Path, input_path: Path, output_path: Path) -> int:
    witness = verify(deployment_path)
    require(input_path.is_file() and not input_path.is_symlink(),
            f"entry readback absent: {input_path}")
    observed = input_path.read_bytes()
    stamp = classify(return_submitted=True, method=witness["method"],
                     observed=observed, expected=witness["stamp_value"],
                     full_reset_before_defstruct=
                     witness["record_fully_reset_before_defstruct"])
    result = {
        "format": "lisp65-c2.3-v1.6-D2-RAM-entry-witness-v1",
        "status": "passed-entry-RAM-stamp-before-measured-forms",
        "entry_witness": witness,
        "stamp": stamp,
        "readback_sha256": hashlib.sha256(observed).hexdigest(),
        "product_bytes_changed": 0,
        "diagnostic_bytes": "bound non-promotable Phase-C identity",
    }
    write_json(output_path, result)
    print("D2 RAM ENTRY WITNESS PASS return=1 entry=$202c stamp=$c07a:$44")
    return 0


def submit_return(deployment_path: Path, device_path: str,
                  output_path: Path) -> int:
    witness = verify(deployment_path)
    fd = os.open(device_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c216ramentry\r")
        # Synchronisation enters the monitor. Resume once, then use the same
        # raw matrix transport whose RETURN arrival Stage 1 already proved.
        MONITOR.monitor_command(fd, b"t0", 0.03)
        commands = MONITOR.virtual_matrix_press(fd, "~M")
        time.sleep(0.1)
    finally:
        os.close(fd)
    require(len(commands) > 0, "virtual RETURN transport emitted no command")
    result = {
        "format": "lisp65-c2.3-v1.6-D2-virtual-RETURN-submit-v1",
        "status": "submitted-one-virtual-RETURN-without-monitor-breakpoint",
        "entry_witness_method": witness["method"],
        "matrix_commands": commands,
        "virtual_RETURNs": 1,
        "monitor_breakpoints_armed": 0,
    }
    write_json(output_path, result)
    print("D2 VIRTUAL RETURN SUBMIT PASS return=1 breakpoint=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "submit", "decode"))
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--device", default="/dev/ttyUSB1")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        result = selftest(args.deployment)
        print("D2 RAM ENTRY WITNESS SELFTEST PASS "
              f"mutations={len(result['mutations_rejected'])} entry-stamp=1 "
              "complete-map=1")
        return 0
    if args.action == "submit":
        require(args.output is not None, "submit requires --output")
        return submit_return(args.deployment, args.device, args.output)
    require(args.input is not None and args.output is not None,
            "decode requires --input and --output")
    return decode(args.deployment, args.input, args.output)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RAMEntryWitnessError as error:
        print(f"D2 RAM ENTRY WITNESS FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
