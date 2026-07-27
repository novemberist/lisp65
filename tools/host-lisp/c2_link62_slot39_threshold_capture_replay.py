#!/usr/bin/env python3
"""Capture linked PCs and replay the completed Slot-39 hardware evidence."""

from __future__ import annotations

import argparse
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import termios
import time
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HW = ROOT / (
    "build/c2.2/hardware-link62-slot39-threshold-hold2-NONPROMOTABLE")
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold2-nonpromotable-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-carrier-seal-hardware-first-red.json")
ATTRIBUTION = EVIDENCE / (
    "c2.2-link62-slot39-completion-host-elf-attribution.json")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link62-slot39-threshold-hold2-NONPROMOTABLE/"
    "runtime-overlays-session-link62-slot39-threshold-hold2-NONPROMOTABLE.bin")
DONOR_ELF = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-hardware-receipt.json")
PARSER_FIRST_RED = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-receipt-parser-first-red.json")
PC_CAPTURE = HW / "pc-captures.json"

DEVICE = "/dev/ttyUSB1"
POLL_FIRST = 0xC6FF
POLL_LAST = 0xC94B
PRE_TIMEOUT_BODY_FIRST = 0xC7D6
PRE_TIMEOUT_BODY_LAST = 0xC8A1
TIMEOUT_SAMPLE_FIRST = 0xC8A2
THRESHOLD_BRANCH = 0xC8CA


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
        f"not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(regular(path) == data, f"generated evidence differs: {path}")
        return
    path.write_bytes(data)
    os.chmod(path, 0o444)


def serial_read(fd: int, seconds: float) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        timeout = min(0.02, max(0.0, deadline - time.monotonic()))
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            try:
                result.extend(os.read(fd, 8192))
            except BlockingIOError:
                pass
    return bytes(result)


def slow_write(fd: int, value: bytes) -> None:
    for byte in value:
        while True:
            try:
                if os.write(fd, bytes((byte,))):
                    break
            except BlockingIOError:
                time.sleep(0.001)


def configure(fd: int) -> None:
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = (
        attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
    ) | termios.CS8 | termios.CLOCAL | termios.CREAD
    attrs[3] = 0
    attrs[4] = termios.B2000000
    attrs[5] = termios.B2000000
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def sync(fd: int, token: bytes) -> None:
    slow_write(fd, b"\x15#\r")
    time.sleep(0.05)
    serial_read(fd, 0.2)
    slow_write(fd, token)
    response = serial_read(fd, 0.5)
    require(token in response, "serial monitor synchronisation failed")


def one_pc(fd: int, index: int) -> dict[str, Any]:
    token = f"#c8ca{index:04x}\r".encode()
    sync(fd, token)
    slow_write(fd, b"t1\r")
    time.sleep(0.02)
    slow_write(fd, b"r\r")
    raw = serial_read(fd, 0.5)
    slow_write(fd, b"t0\r")
    serial_read(fd, 0.1)
    match = re.search(rb"\n,[0-9A-Fa-f]{4}([0-9A-Fa-f]{4})", raw)
    require(match is not None, f"PC absent from register response {index}")
    pc = int(match.group(1), 16)
    return {
        "index": index,
        "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "PC": f"0x{pc:04x}",
        "raw_hex": raw.hex(),
        "inside_c2_completion_poll": POLL_FIRST <= pc <= POLL_LAST,
        "inside_pre_timeout_body":
            PRE_TIMEOUT_BODY_FIRST <= pc <= PRE_TIMEOUT_BODY_LAST,
        "at_threshold_branch": pc == THRESHOLD_BRANCH,
    }


def capture_pc() -> dict[str, Any]:
    require(not PC_CAPTURE.exists(), "PC capture is one-shot")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(one_pc(fd, index))
    finally:
        os.close(fd)
    value = {
        "format": "lisp65-Link62-slot39-threshold-PC-captures-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": DEVICE,
        "rows": rows,
        "capture_effect": (
            "monitor t1/r/t0 samples PC and resumes the already-running "
            "nonpromotable diagnostic identity"),
    }
    write_json(PC_CAPTURE, value)
    return value


def bytes_at(index: int, name: str) -> bytes:
    return regular(HW / f"capture-{index}/{name}.bin")


def bind_parser_first_red() -> dict[str, Any]:
    trace = (
        "re.PatternError: nothing to repeat at position 22; "
        r"legacy pattern used \\$? instead of \$?")
    value = {
        "format":
            "lisp65-c2.2-Link62-slot39-threshold-receipt-parser-first-red-v1",
        "recorded_on": "2026-07-24",
        "status": "first-red-receipt-parser-after-complete-hardware-capture",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "deployment": bind(HW / "deployment.json"),
            "threshold_PC_request_log": bind(HW / "threshold-pc.txt"),
            "capture_timing": bind(HW / "capture-times.json"),
        },
        "finding": {
            "error": trace,
            "hardware_capture_complete_before_error": True,
            "product_finding": False,
            "hardware_replay_required": False,
            "repair": (
                "pure replay against the immutable captures; the -B command "
                "only installed a breakpoint and was never a PC witness, so "
                "three direct monitor-register samples are bound separately"),
        },
        "claim_limit": "Class-A receipt-parser First Red only.",
    }
    write_json(PARSER_FIRST_RED, value)
    return value


def evaluate() -> dict[str, Any]:
    bind_parser_first_red()
    pc_capture = json.loads(regular(PC_CAPTURE))
    rows_pc = pc_capture["rows"]
    require(
        len(rows_pc) == 3
        and all(row["inside_c2_completion_poll"] for row in rows_pc)
        and not any(row["at_threshold_branch"] for row in rows_pc),
        "PC samples do not establish a no-hold poll state")

    timing = json.loads(regular(HW / "capture-times.json"))
    require(timing["interval_seconds"] == [0, 1, 5], "timing drift")
    rows: list[dict[str, Any]] = []
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "start-zp", "completion-record", "trace", "c2j")
    }
    for index in range(1, 4):
        start = bytes_at(index, "start-zp")
        record = bytes_at(index, "completion-record")
        trace = bytes_at(index, "trace")
        zp = bytes_at(index, "runtime-zp")
        frame = bytes_at(index, "frame")
        c2j = bytes_at(index, "c2j")
        require(
            (len(start), len(record), len(trace), len(zp), len(frame), len(c2j))
            == (8, 32, 8, 48, 5, 64),
            f"capture {index} geometry drift")
        for name, value in (
            ("start-zp", start), ("completion-record", record),
            ("trace", trace), ("c2j", c2j),
        ):
            stable[name].append(value)
        poll_start = start[7] | start[0] << 8
        current = int.from_bytes(frame[:2], "little")
        producer = int.from_bytes(record[25:27], "little")
        target = binascii.crc_hqx(c2j, 0xFFFF)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "poll_start": f"0x{poll_start:04x}",
            "current_frame": f"0x{current:04x}",
            "external_elapsed_frames": (current - poll_start) & 0xFFFF,
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{producer:04x}",
            "target_seal": f"0x{target:04x}",
            "seal_matches": producer == target,
            "target_format_CRC32":
                f"0x{zlib.crc32(c2j[:60]) & 0xffffffff:08x}",
            "target_format_CRC32_valid":
                int.from_bytes(c2j[60:64], "little")
                == zlib.crc32(c2j[:60]) & 0xffffffff,
            "slot_stamp": trace[4],
            "rtov_busy": zp[9],
            "rtov_loaded_len": int.from_bytes(zp[11:13], "little"),
        })
    for name, values in stable.items():
        require(
            values[0] == values[1] == values[2],
            f"time-separated {name} witnesses changed")
    require(
        [row["external_elapsed_frames"] for row in rows] == [233, 332, 578]
        and all(row["completion_mode"] == "0xa3" for row in rows)
        and all(row["producer_seal"] == "0x2801" for row in rows)
        and all(row["seal_matches"] for row in rows)
        and all(row["target_format_CRC32_valid"] for row in rows)
        and all(row["slot_stamp"] == 39 for row in rows)
        and all(row["rtov_busy"] == 1 for row in rows)
        and all(row["rtov_loaded_len"] == 1532 for row in rows),
        "captured threshold witnesses differ from the bound result")
    window = regular(HW / "runtime-slot39.bin")
    require(
        len(window) == 1526
        and window[THRESHOLD_BRANCH - EXPECTED_VMA:
                   THRESHOLD_BRANCH - EXPECTED_VMA + 2] == bytes.fromhex("b0fe"),
        "runtime Slot-39 threshold patch drift")

    value = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hardware-v2",
        "recorded_on": "2026-07-24",
        "status": "completed-no-threshold-hold-inner-attempt-does-not-return",
        "promotable": False,
        "authority": {
            "host_ELF_attribution": bind(ATTRIBUTION),
            "diagnostic_carrier_receipt": bind(PATCH_RECEIPT),
            "diagnostic_harness_First_Red": bind(FIRST_RED),
            "receipt_parser_First_Red": bind(PARSER_FIRST_RED),
            "carrier": bind(CARRIER, 0x08000000),
            "donor_ELF": bind(DONOR_ELF),
            "deployment": bind(HW / "deployment.json"),
            "PC_captures": bind(PC_CAPTURE),
            "capture_timing": bind(HW / "capture-times.json"),
            "evaluator": bind(Path(__file__)),
        },
        "time_separated_memory_captures": rows,
        "time_separated_PC_captures": rows_pc,
        "answers": {
            "threshold_hold_reached": False,
            "current_location": (
                "c2_completion_poll before its timeout sample/decision; "
                "the exact PC samples remain inside the pre-timeout body"),
            "poll_start": "0x05c8, stable in $17/$1e",
            "external_elapsed_frames": [233, 332, 578],
            "producer_seal": "0x2801",
            "target_seal": "0x2801",
            "seal_divergence": False,
            "completion_mode": "0xa3 (rollback re-entry)",
            "timeout_verdict": (
                "the 64-frame arithmetic is not reached while one completion "
                "attempt remains inside its poison/write/readback body; the "
                "current fail-closed bound is therefore per returned attempt, "
                "not a wall-clock bound"),
            "why_slot39_appeared_hung": (
                "a single inner completion attempt can outlive the 64-frame "
                "contract before control reaches $c8a2..$c8ca"),
        },
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            } for name, values in stable.items()
        },
        "execution_accounting": {
            "diagnostic_hardware_cycles": 2,
            "first_cycle": "carrier-seal harness First Red before test form",
            "second_cycle": "complete memory and PC capture",
            "product_links": 0,
            "compiler_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "diagnostic_lifecycle": {
            "identity": bind(CARRIER)["sha256"],
            "state": "discarded-after-capture",
            "eligible_for_promotion": False,
        },
        "next_decision_class": (
            "Class C: the completion contract needs a bounded inner-attempt "
            "mechanism or a timeout check inside the long body; no fix is "
            "implemented by this diagnostic."),
        "claim_limit": (
            "Diagnostic attribution only; no product fix, C1 closure, "
            "matrix-gate, acceptance-chain, promotion or release claim."),
    }
    write_json(RECEIPT, value)
    return value


EXPECTED_VMA = 0xC356


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture-pc", "evaluate"))
    args = parser.parse_args()
    value = capture_pc() if args.action == "capture-pc" else evaluate()
    print("c2-link62-slot39-threshold-capture: " + value["format"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link62-slot39-threshold-capture: FIRST RED: " + str(error))
        raise SystemExit(2)
