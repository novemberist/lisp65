#!/usr/bin/env python3
"""Scope the vm_callprim return hold to the private C2D-byte path."""

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


OUT = BASE.SESSION / "vmcall-scoped-return-hold-NONPROMOTABLE"
LEAF_PATCH = OUT / "leaf-successor-jump.bin"
COMMON_PATCH = OUT / "common-return-hook-jump.bin"
HOOK = OUT / "scoped-return-hook.bin"
STATE = OUT / "scoped-return-state.bin"
PRELOAD = OUT / "scoped-return-preload.bin"
DIAGNOSTIC_PRODUCT = OUT / "lisp65-Link71-vmcall-scoped-return-NONPROMOTABLE.prg"
CAPTURE = OUT / "capture-summary.json"
ARM = OUT / "arm-summary.json"
RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-vmcall-scoped-return-hold-nonpromotable-receipt.json")

LEAF_PATCH_ADDRESS = 0x7785
LEAF_BEFORE = bytes.fromhex("4c 52 6b")
LEAF_AFTER = bytes.fromhex("4c a0 17")
COMMON_PATCH_ADDRESS = 0x52BA
COMMON_BEFORE = bytes.fromhex("a0 0d 91")
COMMON_AFTER = bytes.fromhex("4c b4 17")
HOOK_ADDRESS = 0x17A0
STATE_ADDRESS = 0x17F0
HOLD_PC = 0x17BE

# $17a0: private leaf result marker, then jump to the unchanged common epilogue.
# $17b4: preserve unrelated CALLPRIM returns; hold only after marker 0x67.
HOOK_BYTES = bytes.fromhex(
    "8d f0 17"       # sta $17f0
    "8e f1 17"       # stx $17f1
    "a9 67"          # lda #$67
    "8d f2 17"       # sta $17f2
    "ad f0 17"       # lda $17f0
    "ae f1 17"       # ldx $17f1
    "4c 52 6b"       # jmp $6b52
    "48"             # pha
    "ad f2 17"       # lda $17f2
    "c9 67"          # cmp #$67
    "d0 04"          # bne $17c0
    "68"             # pla
    "ea"             # nop; raster IRQs keep the episode latch healthy
    "80 fe"          # bra $17be
    "68"             # pla
    "a0 0d"          # ldy #$0d
    "91 02"          # sta (__rc0),y
    "4c be 52"       # jmp $52be
)
STATE_BYTES = bytes((0, 0, 0))

STATIC_RANGES = (
    ("zero-page", 0x00000000, 160),
    ("vm-buffer-state", 0x0000B9A0, 96),
    ("vm-code-and-reader-state", 0x0000BFA0, 80),
    ("c2d-header", 0x00050000, 48),
    ("diagnostic-hook", HOOK_ADDRESS, len(HOOK_BYTES)),
    ("diagnostic-state", STATE_ADDRESS, len(STATE_BYTES)),
)


class HoldError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldError(message)


def product_bytes(address: int, expected: bytes) -> int:
    product = BASE.PRODUCT.read_bytes()
    require(int.from_bytes(product[:2], "little") == BASE.LOAD_ADDRESS,
            "Link-71 PRG load address drift")
    offset = 2 + address - BASE.LOAD_ADDRESS
    require(product[offset:offset + len(expected)] == expected,
            f"Link-71 bytes drift at 0x{address:04x}")
    return offset


def prepare() -> dict[str, Any]:
    leaf_offset = product_bytes(LEAF_PATCH_ADDRESS, LEAF_BEFORE)
    common_offset = product_bytes(COMMON_PATCH_ADDRESS, COMMON_BEFORE)
    require(BASE.sha(BASE.PRODUCT) == BASE.EXPECTED_PRODUCT_SHA256,
            "Link-71 product authority drift")
    OUT.mkdir(parents=True, exist_ok=True)
    LEAF_PATCH.write_bytes(LEAF_AFTER)
    COMMON_PATCH.write_bytes(COMMON_AFTER)
    HOOK.write_bytes(HOOK_BYTES)
    STATE.write_bytes(STATE_BYTES)
    preload = bytearray(STATE_ADDRESS + len(STATE_BYTES) - HOOK_ADDRESS)
    preload[:len(HOOK_BYTES)] = HOOK_BYTES
    preload[STATE_ADDRESS - HOOK_ADDRESS:] = STATE_BYTES
    PRELOAD.write_bytes(preload)
    diagnostic_product = bytearray(BASE.PRODUCT.read_bytes())
    diagnostic_product[
        leaf_offset:leaf_offset + len(LEAF_AFTER)] = LEAF_AFTER
    diagnostic_product[
        common_offset:common_offset + len(COMMON_AFTER)] = COMMON_AFTER
    DIAGNOSTIC_PRODUCT.write_bytes(diagnostic_product)
    value = {
        "format": "lisp65-c2.2-Link71-vmcall-scoped-return-hold-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-scoped-return-capture",
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
        "patches": [
            {
                "address": f"0x{LEAF_PATCH_ADDRESS:04x}",
                "PRG_file_offset": leaf_offset,
                "before": LEAF_BEFORE.hex(),
                "after": LEAF_AFTER.hex(),
                "artifact": BASE.bind(LEAF_PATCH, LEAF_PATCH_ADDRESS),
            },
            {
                "address": f"0x{COMMON_PATCH_ADDRESS:04x}",
                "PRG_file_offset": common_offset,
                "before": COMMON_BEFORE.hex(),
                "after": COMMON_AFTER.hex(),
                "artifact": BASE.bind(COMMON_PATCH, COMMON_PATCH_ADDRESS),
            },
        ],
        "injected_diagnostic": {
            "hook": BASE.bind(HOOK, HOOK_ADDRESS),
            "state": BASE.bind(STATE, STATE_ADDRESS),
            "single_prestart_preload": BASE.bind(PRELOAD, HOOK_ADDRESS),
            "diagnostic_product": BASE.bind(
                DIAGNOSTIC_PRODUCT, BASE.LOAD_ADDRESS),
            "free_span": "0x17a0..0x17ff before resident island 0x1800",
            "product_file_bytes_delta": 0,
            "deployed_product_bytes_delta": 0,
            "changed_product_bytes": sum(
                left != right
                for left, right in zip(
                    BASE.PRODUCT.read_bytes(),
                    DIAGNOSTIC_PRODUCT.read_bytes(),
                )
            ),
        },
        "scope_proof": {
            "leaf_path": (
                "only the successor of JSR vm_c2d_byte sets marker 0x67"
            ),
            "common_path": (
                "marker zero preserves every unrelated CALLPRIM return by "
                "executing the replaced LDY/STA pair and jumping to 0x52be"
            ),
            "target_path": (
                "marker 0x67 holds after the unchanged common vm_callprim "
                "epilogue has returned to vm_run_inner"
            ),
            "broad_hook_first_red": (
                "the predecessor attempt patched the common site directly "
                "and was correctly discarded after an unrelated REPL "
                "CALLPRIM reached it first"
            ),
        },
        "capture_protocol": {
            "rule": (
                "the target wait is IRQ-friendly NOP/BRA because A/X are "
                "already saved in memory; deploy ends at a fresh REPL with "
                "no armed JTAG episode, the commissioned form is entered "
                "once on the physical keyboard, followed by one t1, no t0, "
                "and three monitor-only snapshots"
            ),
            "hold_PC": f"0x{HOLD_PC:04x}",
        },
        "prior_first_reds": [
            {
                "class": "common-site-scope",
                "answer": (
                    "an unrelated REPL CALLPRIM reached the unqualified "
                    "common hook first"
                ),
            },
            {
                "class": "SEI-monitor-interaction",
                "answer": (
                    "the scoped SEI loop plus subsequent monitor entry "
                    "tripped the product's correct source-less-IRQ guard"
                ),
            },
            {
                "class": "verified-input-multi-episode",
                "answer": (
                    "verified input used separate type, screenshot and "
                    "RETURN JTAG episodes before the form could execute; "
                    "the diagnostic now submits both text and RETURN in one "
                    "keyboard-virtualisation command"
                ),
            },
            {
                "class": "virtual-input-single-episode",
                "answer": (
                    "even one unverified -T keyboard episode reached the "
                    "product's second-sourceless-IRQ fail-closed path before "
                    "the scoped marker was set; virtual input is therefore "
                    "excluded from this diagnostic"
                ),
            },
            {
                "class": "runtime-monitor-arm",
                "answer": (
                    "even a single late monitor arm reached the correct "
                    "second-sourceless-IRQ fail-closed path before the "
                    "physical form; the successor uses a size-identical "
                    "prepatched diagnostic PRG and no post-start JTAG"
                ),
            },
        ],
        "claim_limit": (
            "One nonpromotable Prim-ID-67-scoped vm_callprim return capture."
        ),
    }
    BASE.write(RECEIPT, value)
    return {
        "status": "ready",
        "hook_bytes": len(HOOK_BYTES),
        "hold_PC": f"0x{HOLD_PC:04x}",
    }


def verify() -> dict[str, Any]:
    product_bytes(LEAF_PATCH_ADDRESS, LEAF_BEFORE)
    product_bytes(COMMON_PATCH_ADDRESS, COMMON_BEFORE)
    receipt = BASE.load(RECEIPT)
    require(LEAF_PATCH.read_bytes() == LEAF_AFTER, "leaf patch drift")
    require(COMMON_PATCH.read_bytes() == COMMON_AFTER, "common patch drift")
    require(HOOK.read_bytes() == HOOK_BYTES, "hook drift")
    require(STATE.read_bytes() == STATE_BYTES, "state drift")
    preload = bytearray(STATE_ADDRESS + len(STATE_BYTES) - HOOK_ADDRESS)
    preload[:len(HOOK_BYTES)] = HOOK_BYTES
    preload[STATE_ADDRESS - HOOK_ADDRESS:] = STATE_BYTES
    require(PRELOAD.read_bytes() == preload, "single preload drift")
    diagnostic_product = bytearray(BASE.PRODUCT.read_bytes())
    diagnostic_product[
        2 + LEAF_PATCH_ADDRESS - BASE.LOAD_ADDRESS:
        2 + LEAF_PATCH_ADDRESS - BASE.LOAD_ADDRESS + len(LEAF_AFTER)
    ] = LEAF_AFTER
    diagnostic_product[
        2 + COMMON_PATCH_ADDRESS - BASE.LOAD_ADDRESS:
        2 + COMMON_PATCH_ADDRESS - BASE.LOAD_ADDRESS + len(COMMON_AFTER)
    ] = COMMON_AFTER
    require(
        DIAGNOSTIC_PRODUCT.read_bytes() == diagnostic_product,
        "prepatched diagnostic product drift",
    )
    require(receipt["authority"]["product"]["sha256"]
            == BASE.sha(BASE.PRODUCT), "receipt product binding drift")
    return {"status": "verified", "hold_PC": f"0x{HOLD_PC:04x}"}


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


def write_block(fd: int, address: int, value: bytes) -> None:
    for offset in range(0, len(value), 16):
        chunk = value[offset:offset + 16]
        command(
            fd,
            (
                f"s{address + offset:08x} "
                + " ".join(f"{byte:02x}" for byte in chunk)
            ).encode(),
            0.05,
        )


def arm() -> dict[str, Any]:
    verify()
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    resumed = False
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c271scopedarm\r")
        command(fd, b"t1", 0.05)
        require(
            read_block(fd, LEAF_PATCH_ADDRESS, len(LEAF_BEFORE))
            == LEAF_BEFORE,
            "live leaf successor is not the unpatched Link-71 authority",
        )
        require(
            read_block(fd, COMMON_PATCH_ADDRESS, len(COMMON_BEFORE))
            == COMMON_BEFORE,
            "live common return is not the unpatched Link-71 authority",
        )
        for address, value in (
            (STATE_ADDRESS, STATE_BYTES),
            (HOOK_ADDRESS, HOOK_BYTES),
            (LEAF_PATCH_ADDRESS, LEAF_AFTER),
            (COMMON_PATCH_ADDRESS, COMMON_AFTER),
        ):
            write_block(fd, address, value)
            require(
                read_block(fd, address, len(value)) == value,
                f"late diagnostic write/readback mismatch at 0x{address:04x}",
            )
        command(fd, b"t0", 0.05)
        resumed = True
    finally:
        os.close(fd)
    require(resumed, "diagnostic was not resumed")
    value = {
        "format": "lisp65-Link71-vmcall-scoped-return-arm-v1",
        "device": SERIAL.DEVICE,
        "armed_in_one_monitor_episode": True,
        "resumed": True,
        "leaf_patch": BASE.bind(LEAF_PATCH, LEAF_PATCH_ADDRESS),
        "common_patch": BASE.bind(COMMON_PATCH, COMMON_PATCH_ADDRESS),
        "hook": BASE.bind(HOOK, HOOK_ADDRESS),
        "state": BASE.bind(STATE, STATE_ADDRESS),
    }
    BASE.write(ARM, value)
    receipt = BASE.load(RECEIPT)
    receipt["status"] = "armed-awaiting-physical-form"
    receipt["arm"] = BASE.bind(ARM)
    BASE.write(RECEIPT, receipt)
    return value


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "scoped-return capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c271scoped\r")
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
    diagnostic_state = raw_values["diagnostic-state"][0]
    summary = {
        "PC": registers["PC"],
        "A": registers["A"],
        "X": registers["X"],
        "Z": registers["Z"],
        "vm_status": zp[0x5F],
        "vm_run_frame": f"0x{frame_address:04x}",
        "saved_leaf_AX": diagnostic_state[:2].hex(),
        "scope_marker": f"0x{diagnostic_state[2]:02x}",
        "vm_buf_bank": vm_state[0x38],
        "vmr_window": vm_state[0x45] | (vm_state[0x46] << 8),
        "vmr_window_length": vm_state[0x47] | (vm_state[0x48] << 8),
        "expected_result_observed": (
            registers["A"] == "0x87"
            and registers["X"] == "0x00"
            and registers["Z"] == "0x00"
            and zp[0x5F] == 0
            and diagnostic_state == bytes((0x87, 0x00, 0x67))
        ),
    }
    value = {
        "format": "lisp65-Link71-vmcall-scoped-return-capture-v1",
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
    receipt["status"] = "completed-nonpromotable-scoped-return-capture"
    receipt["capture"] = BASE.bind(CAPTURE)
    receipt["answer"] = summary
    BASE.write(RECEIPT, receipt)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "arm", "capture"))
    action = parser.parse_args().action
    value = (
        prepare() if action == "prepare"
        else verify() if action == "verify"
        else arm() if action == "arm"
        else capture()
    )
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HoldError, BASE.HoldError, SERIAL.HoldError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-vmcall-scoped-return-hold: FIRST RED: "
              + str(error))
        raise SystemExit(2)
