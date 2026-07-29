#!/usr/bin/env python3
"""Capture the Link-71 %c2d-byte result before CALLPRIM consumes it."""

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


BASE = ROOT / "build/post-promotion/link71-defstruct-header-crc-domain"
PRODUCT = BASE / "final/lisp65-c2-substitution-linked.prg"
ELF = BASE / "final/lisp65-c2-substitution-linked.prg.elf"
SESSION = ROOT / (
    "build/post-promotion/"
    "link71-defstruct-session-record-identity-hardware-replay-v3")
SESSION_DEPLOYMENT = SESSION / "deployment.json"
OUT = SESSION / "c2d-byte-return-hold-NONPROMOTABLE"
PATCH = OUT / "c2d-byte-return-hold.bin"
CAPTURE = OUT / "capture-summary.json"
RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-c2d-byte-return-hold-nonpromotable-receipt.json")

LOAD_ADDRESS = 0x2001
PATCH_ADDRESS = 0x7785
BEFORE = bytes.fromhex("4c 52 6b")
AFTER = bytes.fromhex("78 80 fe")
HOLD_PC = 0x7786
EXPECTED_PRODUCT_SHA256 = (
    "969047cb8116bb77510a0b75454053b765f74aedc482de287f3837db9a8a972e")
EXPECTED_MEDIA_SHA256 = (
    "f77997a9045f6642fc1ae1cd8f197790de5ad526f92e4518ff00451b12cd7b7c")

STATIC_RANGES = (
    ("zero-page", 0x00000000, 160),
    ("resident-state-low", 0x0000B9A0, 96),
    ("software-stack-window", 0x0000C000, 1024),
    ("c2d-header", 0x00050000, 48),
)


class HoldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldError(message)


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


def product_span() -> tuple[int, bytes]:
    product = PRODUCT.read_bytes()
    require(int.from_bytes(product[:2], "little") == LOAD_ADDRESS,
            "Link-71 PRG load address drift")
    offset = 2 + PATCH_ADDRESS - LOAD_ADDRESS
    require(product[offset:offset + len(BEFORE)] == BEFORE,
            "Link-71 CALLPRIM successor bytes drift")
    return offset, product


def prepare() -> dict[str, Any]:
    require(not RECEIPT.exists(), "return-hold receipt already exists")
    deployment = load(SESSION_DEPLOYMENT)
    offset, _product = product_span()
    require(sha(PRODUCT) == EXPECTED_PRODUCT_SHA256,
            "Link-71 product authority drift")
    require(
        deployment["product"]["sha256"] == EXPECTED_PRODUCT_SHA256,
        "session product authority drift",
    )
    require(
        deployment["media"]["sha256"] == EXPECTED_MEDIA_SHA256,
        "session medium authority drift",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(AFTER)
    value = {
        "format": "lisp65-c2.2-Link71-c2d-byte-return-hold-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-return-edge-capture",
        "promotable": False,
        "authority": {
            "product": bind(PRODUCT, LOAD_ADDRESS),
            "ELF": bind(ELF),
            "session_deployment": bind(SESSION_DEPLOYMENT),
            "driver": bind(Path(__file__).resolve()),
        },
        "test": {
            "form": "(%require-c2d-byte (cons 0 0))",
            "expected_C2D_byte_0": "0x43",
            "expected_tagged_result_AX": "0x0087",
        },
        "patch": {
            "runtime_address": f"0x{PATCH_ADDRESS:04x}",
            "PRG_file_offset": offset,
            "before": BEFORE.hex(),
            "after": AFTER.hex(),
            "artifact": bind(PATCH, PATCH_ADDRESS),
            "product_file_bytes_delta": 0,
            "deployed_product_bytes_delta": 0,
            "late_RAM_bytes_changed": len(AFTER),
            "semantics": (
                "replace the common jump immediately after JSR "
                "vm_c2d_byte with SEI/BRA-self; A/X/Z and the restored "
                "CALLPRIM argument pointer remain live"
            ),
        },
        "ELF_truth": {
            "call": "0x7782 JSR 0xfe88 vm_c2d_byte",
            "patched_successor": "0x7785 JMP 0x6b52",
            "hold_PC": f"0x{HOLD_PC:04x}",
        },
        "capture_protocol": {
            "rule": (
                "issue t1 exactly once, never issue t0, then read registers "
                "and all witnesses from the already-stopped serial monitor"
            ),
            "snapshots": 3,
            "dynamic_witness": (
                "read eight bytes from the restored __rc2/__rc3 pointer "
                "found in the first zero-page snapshot"
            ),
        },
        "outcomes": {
            "AX_0087_Z_00_status_00": (
                "leaf and C2D reader returned correctly; the fault is after "
                "the CALLPRIM leaf-return edge"
            ),
            "other": (
                "the captured register, status, argument-buffer and C2D "
                "witnesses attribute the private primitive failure"
            ),
        },
        "claim_limit": (
            "One nonpromotable Link-71 private-C2D-byte return-edge capture; "
            "no product, require, defstruct or release qualification."
        ),
    }
    write(RECEIPT, value)
    return {
        "status": "ready",
        "patch_address": f"0x{PATCH_ADDRESS:04x}",
        "patch_sha256": sha(PATCH),
    }


def verify() -> dict[str, Any]:
    offset, product = product_span()
    deployment = load(SESSION_DEPLOYMENT)
    receipt = load(RECEIPT)
    require(PATCH.read_bytes() == AFTER, "return-hold patch drift")
    require(product[offset:offset + len(BEFORE)] == BEFORE,
            "source product was modified")
    require(
        deployment["product"]["sha256"] == EXPECTED_PRODUCT_SHA256
        and deployment["media"]["sha256"] == EXPECTED_MEDIA_SHA256,
        "session authority drift",
    )
    require(
        receipt["authority"]["product"]["sha256"] == sha(PRODUCT),
        "receipt product binding drift",
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
    require(not CAPTURE.exists(), "return-edge capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c271c2dret\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        snapshots: list[dict[str, Any]] = []
        raw_values: dict[str, list[bytes]] = {
            name: [] for name, _address, _size in STATIC_RANGES}
        raw_values["args"] = []
        args_address: int | None = None
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
            for name, address, size in STATIC_RANGES:
                value = read_block(fd, address, size)
                path = directory / f"{name}.bin"
                path.write_bytes(value)
                raw_values[name].append(value)
                row[name] = bind(path, address)
            zero_page = raw_values["zero-page"][-1]
            current_args = zero_page[0x04] | (zero_page[0x05] << 8)
            if args_address is None:
                args_address = current_args
            require(current_args == args_address,
                    "restored argument pointer moved while frozen")
            args = read_block(fd, args_address, 8)
            args_path = directory / "args.bin"
            args_path.write_bytes(args)
            raw_values["args"].append(args)
            row["args"] = bind(args_path, args_address)
            snapshots.append(row)
        # Deliberately never issue t0.
    finally:
        os.close(fd)
    require(
        all(values[0] == values[1] == values[2]
            for values in raw_values.values()),
        "a frozen witness changed between monitor-only reads",
    )
    zp = raw_values["zero-page"][0]
    c2d = raw_values["c2d-header"][0]
    args = raw_values["args"][0]
    summary = {
        "PC": registers["PC"],
        "A": registers["A"],
        "X": registers["X"],
        "Z": registers["Z"],
        "vm_status": zp[0x5F],
        "args_address": f"0x{args_address:04x}",
        "args_bytes": args.hex(),
        "C2D_byte_0": f"0x{c2d[0]:02x}",
        "expected_result_observed": (
            registers["A"] == "0x87"
            and registers["X"] == "0x00"
            and registers["Z"] == "0x00"
            and zp[0x5F] == 0
            and c2d[0] == 0x43
            and args[0] == 0x43
        ),
    }
    value = {
        "format": "lisp65-Link71-c2d-byte-return-capture-v1",
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
        "summary": summary,
    }
    write(CAPTURE, value)
    receipt = load(RECEIPT)
    receipt["status"] = "completed-nonpromotable-return-edge-capture"
    receipt["capture"] = bind(CAPTURE)
    receipt["answer"] = summary
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
    except (HoldError, SERIAL.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-c2d-byte-return-hold: FIRST RED: "
              + str(error))
        raise SystemExit(2)
