#!/usr/bin/env python3
"""Capture Link-71 failure-hold PCs while rejecting interrupt samples."""

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
import c2_defstruct_link71_slot39_failure_hold as H  # noqa: E402


def one(fd: int, index: int) -> dict[str, Any]:
    rejected: list[str] = []
    for attempt in range(1, 33):
        token = f"#c271{index:02x}{attempt:02x}\r".encode()
        H.monitor_sync(fd, token)
        H.slow_write(fd, b"t1\r")
        time.sleep(0.01)
        H.slow_write(fd, b"r\r")
        raw = H.serial_read(fd, 0.25)
        H.slow_write(fd, b"t0\r")
        H.serial_read(fd, 0.05)
        matches = re.findall(
            rb"\n,[0-9A-Fa-f]{4}([0-9A-Fa-f]{4})", raw)
        if not matches:
            rejected.append("no-PC")
            continue
        values = [int(value, 16) for value in matches]
        for value in values:
            candidates = (
                value,
                (value >> 8) | ((value & 0xff) << 8),
            )
            for pc in candidates:
                if pc in H.SITE_BY_PC:
                    return {
                        "index": index,
                        "attempt": attempt,
                        "captured_at_utc": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "PC": f"0x{pc:04x}",
                        "site": H.SITE_BY_PC[pc],
                        "raw_hex": raw.hex(),
                        "rejected_interrupt_or_monitor_samples": rejected,
                    }
        rejected.extend(f"0x{value:04x}" for value in values)
    raise H.HoldError(
        f"no failure-hold PC after 32 samples for capture {index}: "
        + ",".join(rejected))


def main() -> int:
    H.verify()
    H.require(not H.PC_CAPTURE.exists(), "Link-71 PC capture is one-shot")
    fd = os.open(
        H.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        H.configure_serial(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(one(fd, index))
    finally:
        os.close(fd)
    H.require(
        len({row["site"] for row in rows}) == 1,
        "PC moved between failure sites")
    value = {
        "format": "lisp65-Link71-slot39-failure-PC-captures-v2",
        "capture_intervals_seconds": [0, 1, 5],
        "device": H.DEVICE,
        "interrupt_samples_rejected": True,
        "driver": H.bind(Path(__file__).resolve()),
        "rows": rows,
    }
    H.write_json(H.PC_CAPTURE, value)
    print(
        "c2-defstruct-link71-slot39-PC: PASS "
        f"site={rows[0]['site']} PC={rows[0]['PC']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (H.HoldError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-defstruct-link71-slot39-PC: FIRST RED: " + str(error))
        raise SystemExit(2)
