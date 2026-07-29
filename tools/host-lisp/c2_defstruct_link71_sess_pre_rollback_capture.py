#!/usr/bin/env python3
"""Capture the SESS-bound DEFSTRUCT failure with one non-resuming halt."""

from __future__ import annotations

import argparse
import hashlib
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


SESSION = ROOT / (
    "build/post-promotion/"
    "link71-defstruct-session-record-identity-hardware-replay-v3")
SESSION_DEPLOYMENT = SESSION / "deployment.json"
OUT = SESSION / "defstruct-only-pre-rollback-safe-NONPROMOTABLE"
PATCH = OUT / "pre-rollback-hold.bin"
RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-SESS-defstruct-pre-rollback-safe-capture-"
    "nonpromotable-receipt.json")
CAPTURE = OUT / "capture-summary.json"

WINDOW = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "final/c2-product-kernal-window.bin")
WINDOW_BASE = 0xE000
PATCH_ADDRESS = 0xE9BC
BEFORE = bytes.fromhex("20 e3 e9")
AFTER = bytes.fromhex("78 80 fe")
HOLD_PC = 0xE9BD
EXPECTED_PRODUCT_SHA256 = (
    "969047cb8116bb77510a0b75454053b765f74aedc482de287f3837db9a8a972e")
EXPECTED_MEDIA_SHA256 = (
    "f77997a9045f6642fc1ae1cd8f197790de5ad526f92e4518ff00451b12cd7b7c")

RANGES = (
    ("zero-page", 0x00000000, 160),
    ("resident-state-low", 0x0000B9A0, 96),
    ("resident-state-high", 0x0000BFA0, 96),
    ("software-stack-window", 0x0000C000, 1024),
    ("phase-scratch", 0x0000C0C6, 304),
    ("kernal-window-state", 0x0000FF80, 16),
    ("c2d-header", 0x00050000, 48),
    ("c2j", 0x0005C640, 64),
)


class CaptureError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CaptureError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object expected: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_bytes() -> bytes:
    image = WINDOW.read_bytes()
    require(len(image) == 8192, "Link-71 window size drift")
    offset = PATCH_ADDRESS - WINDOW_BASE
    value = image[offset:offset + len(BEFORE)]
    require(value == BEFORE, "Link-71 rollback call bytes drift")
    return value


def prepare() -> dict[str, Any]:
    require(SESSION_DEPLOYMENT.exists(), "v3 session deployment absent")
    require(not RECEIPT.exists(), "safe-capture receipt already exists")
    deployment = load(SESSION_DEPLOYMENT)
    require(
        deployment["product"]["sha256"] == EXPECTED_PRODUCT_SHA256,
        "Link-71 product authority drift",
    )
    require(
        deployment["media"]["sha256"] == EXPECTED_MEDIA_SHA256
        and deployment["remote_media"] == "L71SES3.D81",
        "canonical SESS medium authority drift",
    )
    source_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(AFTER)
    value = {
        "format": "lisp65-c2.2-Link71-SESS-pre-rollback-safe-capture-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-single-halt-capture",
        "promotable": False,
        "authority": {
            "session_deployment": bind(SESSION_DEPLOYMENT),
            "product": deployment["product"],
            "media": deployment["media"],
            "window": bind(WINDOW, 0x087FE000),
            "driver": bind(Path(__file__).resolve()),
        },
        "test": {
            "precondition": (
                "PLACE is loaded first through (%disk-load-lib 39 1), "
                "which must return t"
            ),
            "form": "(require (quote defstruct))",
            "hold": (
                "replace the common c2_append_begin rollback call with "
                "SEI/BRA-self and stop before rollback mutates provenance"
            ),
        },
        "patch": {
            "runtime_address": f"0x{PATCH_ADDRESS:04x}",
            "before": BEFORE.hex(),
            "after": AFTER.hex(),
            "artifact": bind(PATCH, PATCH_ADDRESS),
            "product_bytes_delta": 0,
        },
        "capture_protocol": {
            "rule": (
                "issue t1 exactly once, never issue t0, and read registers "
                "plus every memory witness through the already-stopped "
                "serial monitor"
            ),
            "reason": (
                "repeated halt/resume while the diagnostic SEI loop is "
                "active can synthesize two consecutive source-less IRQs "
                "and correctly trip c2_kernal_fail_closed"
            ),
            "snapshots": 3,
            "ranges": [
                {"name": name, "address": f"0x{address:08x}", "bytes": size}
                for name, address, size in RANGES
            ],
        },
        "claim_limit": (
            "One nonpromotable SESS-bound DEFSTRUCT primary-failure capture; "
            "no product, require, defstruct, or release qualification."
        ),
    }
    write(RECEIPT, value)
    return {
        "status": "ready",
        "patch_address": f"0x{PATCH_ADDRESS:04x}",
        "patch_sha256": sha(PATCH),
    }


def verify() -> dict[str, Any]:
    source_bytes()
    receipt = load(RECEIPT)
    deployment = load(SESSION_DEPLOYMENT)
    require(PATCH.read_bytes() == AFTER, "safe-capture patch drift")
    require(
        receipt["authority"]["session_deployment"]["sha256"]
        == sha(SESSION_DEPLOYMENT),
        "receipt/deployment binding drift",
    )
    require(
        deployment["product"]["sha256"] == EXPECTED_PRODUCT_SHA256
        and deployment["media"]["sha256"] == EXPECTED_MEDIA_SHA256,
        "v3 deployment authority drift",
    )
    return {
        "status": "verified",
        "source_bytes": BEFORE.hex(),
        "hold_bytes": AFTER.hex(),
    }


def command(fd: int, value: bytes, wait: float = 0.02) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.25)


def read_registers(fd: int) -> dict[str, Any]:
    raw = command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw,
    )
    require(match is not None, "register row absent")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    row = {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width) in enumerate(zip(names, widths), 1)
    }
    row["raw_hex"] = raw.hex()
    require(int(match.group(1), 16) == HOLD_PC, (
        f"unexpected stopped PC 0x{int(match.group(1), 16):04x}; "
        "capture refused before any resume"))
    return row


def read_block(fd: int, address: int, size: int) -> bytes:
    value = bytearray()
    for offset in range(0, size, 16):
        current = address + offset
        raw = command(fd, f"m{current:08x}".encode())
        match = re.search(
            fr":{current:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
        require(match is not None, (
            f"memory row absent at 0x{current:08x}: {raw!r}"))
        value.extend(bytes.fromhex(match.group(1).decode()))
    return bytes(value[:size])


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "safe capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c271sess-safe\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        snapshots: list[dict[str, Any]] = []
        raw_values: dict[str, list[bytes]] = {
            name: [] for name, _address, _size in RANGES}
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            directory = OUT / f"capture-{index}"
            directory.mkdir(parents=True, exist_ok=False)
            row: dict[str, Any] = {
                "index": index,
                "captured_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            for name, address, size in RANGES:
                value = read_block(fd, address, size)
                path = directory / f"{name}.bin"
                path.write_bytes(value)
                raw_values[name].append(value)
                row[name] = bind(path, address)
            snapshots.append(row)
        # Deliberately do not issue t0.  The CPU remains stopped and cannot
        # synthesize a source-less return IRQ during evidence collection.
    finally:
        os.close(fd)
    require(
        all(values[0] == values[1] == values[2]
            for values in raw_values.values()),
        "a frozen witness changed between monitor-only reads",
    )
    phase = raw_values["phase-scratch"][0]
    value = {
        "format": "lisp65-Link71-SESS-defstruct-pre-rollback-capture-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": SERIAL.DEVICE,
        "CPU_left_stopped": True,
        "registers": registers,
        "snapshots": snapshots,
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            }
            for name, values in raw_values.items()
        },
        "summary": {
            "PC": registers["PC"],
            "vm_status": raw_values["zero-page"][0][0x5F],
            "phase_owner": raw_values["zero-page"][0][0x89],
            "READY": raw_values["zero-page"][0][0x8C],
            "phase_trace": phase[296:304].hex(),
            "c2j_nonzero_bytes": sum(
                byte != 0 for byte in raw_values["c2j"][0]),
        },
    }
    write(CAPTURE, value)
    receipt = load(RECEIPT)
    receipt["status"] = "completed-nonpromotable-safe-primary-capture"
    receipt["capture"] = bind(CAPTURE)
    receipt["answer"] = value["summary"]
    write(RECEIPT, receipt)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "capture"))
    action = parser.parse_args().action
    value = (
        prepare() if action == "prepare"
        else verify() if action == "verify"
        else capture()
    )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, SERIAL.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-SESS-safe-capture: FIRST RED: " + str(error))
        raise SystemExit(2)
