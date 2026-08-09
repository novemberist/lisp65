#!/usr/bin/env python3
"""Prove that the corrected D2 launch crosses the Link-82 entry.

The device form is deliberately a monitor-side witness.  It changes no
product or diagnostic byte: a breakpoint is armed at the bound `_start`, one
virtual RETURN is submitted through the already-proved matrix transport, and
the post-instruction PC is read before the breakpoint is removed.  A mismatch
leaves the CPU stopped.
"""

from __future__ import annotations

import argparse
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


ENTRY_PC = 0x2023
ENTRY_OPCODE = 0x78  # SEI, one byte; MEGA65 breakpoints report post-instruction.
ENTRY_STOP_PC = 0x2024
FIRST_DIAGNOSTIC_DELTA = 0x47C5


class EntryWitnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EntryWitnessError(message)


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


def verify_entry_bytes(deployment: dict[str, Any]) -> dict[str, Any]:
    row = deployment["diagnostic"]["prg"]
    path = ROOT / row["path"]
    require(path.is_file(), f"diagnostic PRG absent: {path}")
    require(path.stat().st_size == row["bytes"] and sha256(path) == row["sha256"],
            "diagnostic PRG binding drift")
    payload = path.read_bytes()
    require(len(payload) >= 2, "diagnostic PRG is truncated")
    load_address = payload[0] | (payload[1] << 8)
    offset = 2 + ENTRY_PC - load_address
    require(load_address == 0x2001 and 2 <= offset < len(payload),
            "diagnostic PRG entry geometry drift")
    require(payload[offset] == ENTRY_OPCODE,
            f"entry opcode drift: 0x{payload[offset]:02x}")
    require(ENTRY_STOP_PC < FIRST_DIAGNOSTIC_DELTA,
            "entry witness is not before the first diagnostic delta")
    return {
        "load_address": f"0x{load_address:04x}",
        "entry_pc": f"0x{ENTRY_PC:04x}",
        "entry_opcode": f"0x{ENTRY_OPCODE:02x}",
        "post_instruction_pc": f"0x{ENTRY_STOP_PC:04x}",
        "first_diagnostic_delta": f"0x{FIRST_DIAGNOSTIC_DELTA:04x}",
        "prg_sha256": row["sha256"],
    }


LAUNCH_ORDER = [
    "CPU-resumed",
    "breakpoint-arm-written",
    "armed-state-observed",
    "virtual-RETURN-submitted",
    "post-entry-PC-observed",
]


def classify(*, return_submitted: bool, breakpoint: int,
             observed_pc: int, launch_order: list[str]) -> dict[str, Any]:
    require(return_submitted, "virtual RETURN was not submitted")
    require(breakpoint == ENTRY_PC, "entry breakpoint address drift")
    require(launch_order == LAUNCH_ORDER,
            "breakpoint was not observed armed before the launch edge")
    require(ENTRY_PC < FIRST_DIAGNOSTIC_DELTA,
            "entry breakpoint is not before diagnostic code")
    require(observed_pc == ENTRY_STOP_PC,
            f"entry breakpoint did not fire: PC=0x{observed_pc:04x}")
    return {
        "return_submitted": True,
        "entry_stamp_fired": True,
        "breakpoint": f"0x{breakpoint:04x}",
        "launch_order": launch_order,
        "armed_state_observed_before_launch": True,
        "observed_post_instruction_pc": f"0x{observed_pc:04x}",
        "ambiguity_closed": "entry observed before any immediate return",
    }


def selftest(deployment_path: Path) -> dict[str, Any]:
    entry = verify_entry_bytes(load(deployment_path))
    fired = classify(return_submitted=True, breakpoint=ENTRY_PC,
                     observed_pc=ENTRY_STOP_PC,
                     launch_order=LAUNCH_ORDER)
    rejected: dict[str, str] = {}
    cases = {
        "missing-return": dict(return_submitted=False, breakpoint=ENTRY_PC,
                               observed_pc=ENTRY_STOP_PC,
                               launch_order=LAUNCH_ORDER),
        "wrong-breakpoint": dict(return_submitted=True, breakpoint=0x2024,
                                 observed_pc=ENTRY_STOP_PC,
                                 launch_order=LAUNCH_ORDER),
        "non-entry": dict(return_submitted=True, breakpoint=ENTRY_PC,
                          observed_pc=0xA474,
                          launch_order=LAUNCH_ORDER),
        "immediate-return-without-entry-stamp": dict(
            return_submitted=True, breakpoint=ENTRY_PC, observed_pc=0xA65C,
            launch_order=LAUNCH_ORDER),
        "late-arm-after-launch": dict(
            return_submitted=True, breakpoint=ENTRY_PC,
            observed_pc=ENTRY_STOP_PC,
            launch_order=[
                "CPU-resumed",
                "virtual-RETURN-submitted",
                "breakpoint-arm-written",
                "armed-state-observed",
                "post-entry-PC-observed",
            ]),
    }
    for name, arguments in cases.items():
        try:
            classify(**arguments)
        except EntryWitnessError as error:
            rejected[name] = str(error)
        else:
            raise EntryWitnessError(f"entry-witness mutation survived: {name}")
    require(len(rejected) == 5, "entry-witness mutation count drift")
    return {"entry": entry, "synthetic_fired_stamp": fired,
            "mutations_rejected": rejected}


def device(deployment_path: Path, device_path: str, output: Path) -> int:
    deployment = load(deployment_path)
    entry = verify_entry_bytes(deployment)
    fd = os.open(device_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c216d2\r")
        MONITOR.monitor_command(fd, b"t1", 0.05)
        before_raw = MONITOR.monitor_command(fd, b"r", 0.05)
        before = MONITOR.parse_registers(before_raw)

        # Resume before arming: the MEGA65 monitor cancels a queued breakpoint
        # on either t0 or t1.  From the arm write through the RETURN launch
        # edge, no state-changing monitor command is permitted.
        MONITOR.monitor_command(fd, b"t0", 0.03)
        SERIAL.slow_write(fd, f"b{ENTRY_PC:x}\r".encode())
        time.sleep(0.05)
        arm_raw = SERIAL.serial_read(fd, 0.2)
        launch_order = LAUNCH_ORDER[:3]

        # The virtual matrix helper sends exactly one RETURN and performs no
        # monitor resync that could erase the armed breakpoint.
        commands = MONITOR.virtual_matrix_press(fd, "~M")
        launch_order.append("virtual-RETURN-submitted")
        time.sleep(1.0)

        # Read the breakpoint stop without t1: t1 itself cancels a queued BP.
        after_raw = MONITOR.monitor_command(fd, b"r", 0.05)
        after = MONITOR.parse_registers(after_raw)
        after_pc = int(after["PC"], 16)
        launch_order.append("post-entry-PC-observed")
        SERIAL.slow_write(fd, b"b\r")
        time.sleep(0.03)

        try:
            stamp = classify(return_submitted=len(commands) > 0,
                             breakpoint=ENTRY_PC, observed_pc=after_pc,
                             launch_order=launch_order)
        except EntryWitnessError:
            MONITOR.monitor_command(fd, b"t1", 0.03)
            raise
        MONITOR.monitor_command(fd, b"t0", 0.03)
        result = {
            "format": "lisp65-c2.3-v1.6-D2-entry-PC-witness-v1",
            "status": "passed-entry-before-first-diagnostic-delta",
            "entry_authority": entry,
            "before_registers": before,
            "after_registers": after,
            "arm_response_raw_hex": arm_raw.hex(),
            "matrix_commands": commands,
            "stamp": stamp,
            "breakpoint_cleared": True,
            "CPU_resumed_only_on_match": True,
            "product_or_diagnostic_bytes_changed": 0,
        }
        write_json(output, result)
        print("D2 ENTRY WITNESS PASS return=1 entry=0x2023 stop=0x2024")
        return 0
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "device"))
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--device", default="/dev/ttyUSB1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "selftest":
        result = selftest(args.deployment)
        print("D2 ENTRY WITNESS SELFTEST PASS "
              f"mutations={len(result['mutations_rejected'])} "
              "return=1 entry-stamp=1")
        return 0
    require(args.output is not None, "device action requires --output")
    return device(args.deployment, args.device, args.output)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EntryWitnessError as error:
        print(f"D2 ENTRY WITNESS FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
