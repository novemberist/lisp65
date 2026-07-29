#!/usr/bin/env python3
"""Capture vm_callprim's result before vm_run_inner processes it."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_c2d_byte_return_hold as BASE  # noqa: E402
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402


OUT = BASE.SESSION / "vmcall-return-hold-NONPROMOTABLE"
PATCH = OUT / "vmcall-return-hold.bin"
CAPTURE = OUT / "capture-summary.json"
RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-vmcall-return-hold-nonpromotable-receipt.json")

PATCH_ADDRESS = 0x52BA
BEFORE = bytes.fromhex("a0 0d 91")
AFTER = bytes.fromhex("78 80 fe")
HOLD_PC = 0x52BB

STATIC_RANGES = (
    ("zero-page", 0x00000000, 160),
    ("vm-buffer-state", 0x0000B9A0, 96),
    ("vm-code-and-reader-state", 0x0000BFA0, 80),
    ("c2d-header", 0x00050000, 48),
)


class HoldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldError(message)


def product_span() -> tuple[int, bytes]:
    product = BASE.PRODUCT.read_bytes()
    require(int.from_bytes(product[:2], "little") == BASE.LOAD_ADDRESS,
            "Link-71 PRG load address drift")
    offset = 2 + PATCH_ADDRESS - BASE.LOAD_ADDRESS
    require(product[offset:offset + len(BEFORE)] == BEFORE,
            "Link-71 vm_run_inner successor bytes drift")
    return offset, product


def prepare() -> dict[str, Any]:
    require(not RECEIPT.exists(), "vmcall-return receipt already exists")
    deployment = BASE.load(BASE.SESSION_DEPLOYMENT)
    offset, _product = product_span()
    require(BASE.sha(BASE.PRODUCT) == BASE.EXPECTED_PRODUCT_SHA256,
            "Link-71 product authority drift")
    OUT.mkdir(parents=True, exist_ok=True)
    PATCH.write_bytes(AFTER)
    value = {
        "format": "lisp65-c2.2-Link71-vmcall-return-hold-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-vmcall-return-capture",
        "promotable": False,
        "authority": {
            "product": BASE.bind(BASE.PRODUCT, BASE.LOAD_ADDRESS),
            "ELF": BASE.bind(BASE.ELF),
            "session_deployment": BASE.bind(BASE.SESSION_DEPLOYMENT),
            "driver": BASE.bind(Path(__file__).resolve()),
        },
        "test": {
            "form": "(%require-c2d-byte (cons 0 0))",
            "expected_vm_callprim_result_AX": "0x0087",
        },
        "patch": {
            "runtime_address": f"0x{PATCH_ADDRESS:04x}",
            "PRG_file_offset": offset,
            "before": BEFORE.hex(),
            "after": AFTER.hex(),
            "artifact": BASE.bind(PATCH, PATCH_ADDRESS),
            "product_file_bytes_delta": 0,
            "deployed_product_bytes_delta": 0,
            "late_RAM_bytes_changed": len(AFTER),
        },
        "ELF_truth": {
            "call": "0x52b7 JSR 0x6aa0 vm_callprim",
            "patched_successor": "0x52ba LDY #0x0d; STA (__rc0),Y",
            "hold_PC": f"0x{HOLD_PC:04x}",
        },
        "capture_protocol": {
            "rule": (
                "one t1, no t0; three monitor-only reads of registers, VM "
                "state, code buffer and the dynamic vm_run_inner frame"
            ),
            "snapshots": 3,
        },
        "outcomes": {
            "AX_0087_status_00": (
                "the complete CALLPRIM dispatch and epilogue returned "
                "correctly; attribution advances into BUF_ENSURE_MINE"
            ),
            "other": (
                "the CALLPRIM epilogue or its ABI restoration is overruled"
            ),
        },
        "claim_limit": (
            "One nonpromotable Link-71 vm_callprim return-edge capture."
        ),
        "session_authority": {
            "product_sha256": deployment["product"]["sha256"],
            "media_sha256": deployment["media"]["sha256"],
        },
    }
    BASE.write(RECEIPT, value)
    return {"status": "ready", "patch_address": f"0x{PATCH_ADDRESS:04x}"}


def verify() -> dict[str, Any]:
    offset, product = product_span()
    receipt = BASE.load(RECEIPT)
    require(PATCH.read_bytes() == AFTER, "vmcall-return patch drift")
    require(product[offset:offset + len(BEFORE)] == BEFORE,
            "source product was modified")
    require(receipt["authority"]["product"]["sha256"]
            == BASE.sha(BASE.PRODUCT), "receipt product binding drift")
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
    require(not CAPTURE.exists(), "vmcall-return capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c271vmret\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        raw_values: dict[str, list[bytes]] = {
            name: [] for name, _address, _size in STATIC_RANGES}
        raw_values["vm-run-frame"] = []
        snapshots: list[dict[str, Any]] = []
        frame_address: int | None = None
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            directory = OUT / f"capture-{index}"
            directory.mkdir(parents=True, exist_ok=False)
            row: dict[str, Any] = {"index": index}
            for name, address, size in STATIC_RANGES:
                value = read_block(fd, address, size)
                path = directory / f"{name}.bin"
                path.write_bytes(value)
                raw_values[name].append(value)
                row[name] = BASE.bind(path, address)
            zp = raw_values["zero-page"][-1]
            current_frame = zp[0x02] | (zp[0x03] << 8)
            if frame_address is None:
                frame_address = current_frame
            require(current_frame == frame_address,
                    "vm_run_inner frame pointer moved while frozen")
            frame = read_block(fd, frame_address, 64)
            frame_path = directory / "vm-run-frame.bin"
            frame_path.write_bytes(frame)
            raw_values["vm-run-frame"].append(frame)
            row["vm-run-frame"] = BASE.bind(frame_path, frame_address)
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
    vm_state = raw_values["vm-code-and-reader-state"][0]
    summary = {
        "PC": registers["PC"],
        "A": registers["A"],
        "X": registers["X"],
        "Z": registers["Z"],
        "vm_status": zp[0x5F],
        "vm_run_frame": f"0x{frame_address:04x}",
        "vm_buf_bank": vm_state[0x38],
        "vmr_window": (
            vm_state[0x45] | (vm_state[0x46] << 8)
        ),
        "vmr_window_length": (
            vm_state[0x47] | (vm_state[0x48] << 8)
        ),
        "expected_result_observed": (
            registers["A"] == "0x87"
            and registers["X"] == "0x00"
            and registers["Z"] == "0x00"
            and zp[0x5F] == 0
        ),
    }
    value = {
        "format": "lisp65-Link71-vmcall-return-capture-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": SERIAL.DEVICE,
        "CPU_left_stopped": True,
        "registers": registers,
        "snapshots": snapshots,
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": BASE.sha_bytes(values[0]),
            }
            for name, values in raw_values.items()
        },
        "summary": summary,
    }
    BASE.write(CAPTURE, value)
    receipt = BASE.load(RECEIPT)
    receipt["status"] = "completed-nonpromotable-vmcall-return-capture"
    receipt["capture"] = BASE.bind(CAPTURE)
    receipt["answer"] = summary
    BASE.write(RECEIPT, receipt)
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
    except (HoldError, BASE.HoldError, SERIAL.HoldError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-vmcall-return-hold: FIRST RED: "
              + str(error))
        raise SystemExit(2)
