#!/usr/bin/env python3
"""Capture a stable Link-71 Slot-40 self-loop PC over the serial monitor."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold as HOLD  # noqa: E402


OUT = HOLD.OUT
PC_CAPTURE = OUT / "pc-captures.json"
SITE_BY_PC = {
    vma: name for name, vma in HOLD.SITES
}


def one(fd: int, index: int) -> dict[str, Any]:
    rejected: list[str] = []
    for attempt in range(1, 33):
        token = f"#c272{index:02x}{attempt:02x}\r".encode()
        SERIAL.monitor_sync(fd, token)
        SERIAL.slow_write(fd, b"t1\r")
        time.sleep(0.01)
        SERIAL.slow_write(fd, b"r\r")
        raw = SERIAL.serial_read(fd, 0.25)
        SERIAL.slow_write(fd, b"t0\r")
        SERIAL.serial_read(fd, 0.05)
        matches = re.findall(
            rb"\n,[0-9A-Fa-f]{4}([0-9A-Fa-f]{4})", raw)
        if not matches:
            rejected.append("no-PC")
            continue
        values = [int(value, 16) for value in matches]
        for value in values:
            for pc in (value, (value >> 8) | ((value & 0xff) << 8)):
                # BRA $-2 alternates between the opcode address and the
                # following operand depending on the sampled cycle.
                for candidate in (pc, pc - 1):
                    if candidate in SITE_BY_PC:
                        return {
                            "index": index,
                            "attempt": attempt,
                            "captured_at_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "PC": f"0x{pc:04x}",
                            "hold_VMA": f"0x{candidate:04x}",
                            "site": SITE_BY_PC[candidate],
                            "raw_hex": raw.hex(),
                            "rejected_samples": rejected,
                        }
        rejected.extend(f"0x{value:04x}" for value in values)
    raise HOLD.HoldError(
        f"no Slot-40 hold PC after 32 samples for capture {index}: "
        + ",".join(rejected))


def main() -> int:
    HOLD.verify()
    HOLD.require(not PC_CAPTURE.exists(), "Slot-40 PC capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(one(fd, index))
    finally:
        os.close(fd)
    HOLD.require(
        len({row["site"] for row in rows}) == 1,
        "Slot-40 PC moved between failure sites")
    value = {
        "format": "lisp65-Link71-slot40-failure-PC-captures-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": SERIAL.DEVICE,
        "rows": rows,
    }
    HOLD.write_json(PC_CAPTURE, value)
    print(
        "c2-defstruct-Link71-Slot40-PC: PASS "
        f"site={rows[0]['site']} PC={rows[0]['PC']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot40-PC: FIRST RED: " + str(error))
        raise SystemExit(2)
