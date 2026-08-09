#!/usr/bin/env python3
"""Bind and capture the v1.6 physical-launch boundary without resuming it.

The hook-free physical fallback deliberately restored the canonical entry
bytes and diagnostic record.  Consequently $C07A is data, not an entry
witness, in that identity.  This tool makes that distinction fail closed and
captures the remaining stopped-state witnesses without resetting or resuming
the target.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402


PHYSICAL = ROOT / (
    "build/c2.3/v1.6-defstruct-d2-physical-fallback/"
    "diagnostic-link82-physical.prg")
PHYSICAL_DEPLOY = ROOT / (
    "build/c2.3/v1.6-defstruct-d2-physical-fallback/deployment.json")
PHYSICAL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-fallback-preparation-receipt.json")
PHASE_C_DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
PHASE_C_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
PRIOR_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-launch-no-repl-device-first-red-receipt.json")

CURRENT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-physical-owner-corrected/physical-after-launch.png")
CURRENT_TIMEOUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-physical-owner-corrected/physical-require-timeout.png")
FAIL_CLOSED = ROOT / "build/ship-builder/v1-device-session/run/quiet-define-point.png"
BLANK_INIT = ROOT / (
    "build/ship-builder/v13/link85-interactive-human-test/run/"
    "waiting-for-human.png")

OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-launch-boundary-appointment")
DESK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-desk-first-red-receipt.json")
CAPTURE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-stopped-state-receipt.json")

RECORD_ADDRESS = 0xC03F
RECORD_BYTES = 65
BOOT_SLOT = 0xC07A
BOOT_SLOT_OFFSET = BOOT_SLOT - RECORD_ADDRESS
PHASE_ADDRESS = 0xC0C6
PHASE_BYTES = 304
FIRST_ERROR_OFFSET = 302
C2J_ADDRESS = 0x05C640
C2J_BYTES = 64
ENTRY_HOOK = 0x202C
ENTRY_BYTES = bytes.fromhex("a2448e30d0")

RANGES = (
    ("record", RECORD_ADDRESS, RECORD_BYTES),
    ("phase-scratch", PHASE_ADDRESS, PHASE_BYTES),
    ("c2j", C2J_ADDRESS, C2J_BYTES),
)


class BoundaryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise BoundaryError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_bytes(path.read_bytes()),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object expected: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prg_bytes(path: Path, address: int, size: int) -> bytes:
    value = path.read_bytes()
    load_address = int.from_bytes(value[:2], "little")
    offset = 2 + address - load_address
    require(2 <= offset and offset + size <= len(value),
            f"PRG address outside payload: 0x{address:04x}")
    return value[offset:offset + size]


def image_facts(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGB")
    pixels = list(image.getdata())
    colors = Counter(pixels)
    corners = [image.getpixel(point) for point in (
        (0, 0), (image.width - 1, 0),
        (0, image.height - 1), (image.width - 1, image.height - 1))]
    return {
        "binding": bind(path),
        "width": image.width,
        "height": image.height,
        "distinct_colors": len(colors),
        "dominant": {"rgb": list(colors.most_common(1)[0][0]),
                     "pixels": colors.most_common(1)[0][1]},
        "corners": [list(value) for value in corners],
        "uniform": len(colors) == 1,
    }


def desk_facts() -> dict[str, Any]:
    physical = load(PHYSICAL_RECEIPT)
    phase = load(PHASE_C_DEPLOY)
    reset_path = ROOT / phase["record"]["reset"]["path"]
    reset = reset_path.read_bytes()
    require(len(reset) == RECORD_BYTES, "canonical record size drift")
    require(physical["facts"]["entry_hook_present"] is False
            and physical["facts"]["boot_record_is_canonical_reset"] is True,
            "hook-free physical fallback contract drift")
    entry = prg_bytes(PHYSICAL, ENTRY_HOOK, len(ENTRY_BYTES))
    record = prg_bytes(PHYSICAL, RECORD_ADDRESS, RECORD_BYTES)
    require(entry == ENTRY_BYTES, "physical fallback unexpectedly has entry hook")
    require(record == reset, "physical fallback record is not canonical reset")

    current = image_facts(CURRENT)
    timeout = image_facts(CURRENT_TIMEOUT)
    red = image_facts(FAIL_CLOSED)
    blank = image_facts(BLANK_INIT)
    blue = [0, 0, 240]
    red_rgb = [240, 0, 0]
    require(current["binding"]["sha256"] == timeout["binding"]["sha256"],
            "launch screen changed during timeout")
    require(all(value == blue for value in current["corners"]),
            "current screen is not blue-framed BASIC/init state")
    require(all(value == red_rgb for value in red["corners"]),
            "fail-closed reference no longer has red frame")
    require(blank["uniform"] and blank["dominant"]["rgb"] == blue,
            "blank-init reference no longer uniform blue")
    require(not current["uniform"] and current["distinct_colors"] > 1,
            "current screen unexpectedly equals blank-init class")

    return {
        "screen_classification": {
            "current": current,
            "timeout": timeout,
            "known_fail_closed": red,
            "known_blank_init": blank,
            "stable_over_minutes": True,
            "class": "BASIC-echo-before-visible-Workbench-init",
            "is_fail_closed_frame": False,
            "is_blank_init_screen": False,
            "is_visible_REPL": False,
        },
        "physical_identity": {
            "binding": bind(PHYSICAL),
            "entry_bytes_at_0x202c": entry.hex(),
            "entry_hook_present": False,
            "record_matches_canonical_reset": True,
            "record_binding": bind(reset_path, RECORD_ADDRESS),
            "C07A_reset_value": reset[BOOT_SLOT_OFFSET],
            "C07A_is_boot_witness": False,
            "record_is_armed": False,
        },
        "usable_stopped_state": {
            "PC": True,
            "phase_scratch_and_first_error": True,
            "C2J": True,
            "record_as_boot_progress": False,
        },
    }


def audit_desk(value: dict[str, Any]) -> None:
    screen = value["screen_classification"]
    identity = value["physical_identity"]
    usable = value["usable_stopped_state"]
    require(screen["stable_over_minutes"]
            and screen["class"] == "BASIC-echo-before-visible-Workbench-init"
            and not screen["is_fail_closed_frame"]
            and not screen["is_blank_init_screen"]
            and not screen["is_visible_REPL"],
            "desk screen classification drift")
    require(not identity["entry_hook_present"]
            and identity["record_matches_canonical_reset"]
            and not identity["C07A_is_boot_witness"]
            and not identity["record_is_armed"],
            "physical identity witness classification drift")
    require(usable == {
        "PC": True,
        "phase_scratch_and_first_error": True,
        "C2J": True,
        "record_as_boot_progress": False,
    }, "stopped-state claim boundary drift")


def desk() -> dict[str, Any]:
    facts = desk_facts()
    audit_desk(facts)
    rejected: dict[str, str] = {}
    mutations = {
        "claim-red-frame": ("screen_classification", "is_fail_closed_frame"),
        "claim-blank-init": ("screen_classification", "is_blank_init_screen"),
        "claim-visible-REPL": ("screen_classification", "is_visible_REPL"),
        "claim-entry-hook": ("physical_identity", "entry_hook_present"),
        "claim-C07A-witness": ("physical_identity", "C07A_is_boot_witness"),
        "claim-record-progress": ("usable_stopped_state", "record_as_boot_progress"),
    }
    for name, (group, key) in mutations.items():
        changed = json.loads(json.dumps(facts))
        changed[group][key] = True
        try:
            audit_desk(changed)
        except BoundaryError as error:
            rejected[name] = str(error)
        else:
            raise BoundaryError(f"desk mutation survived: {name}")
    require(len(rejected) == 6, "desk mutation count drift")
    receipt = {
        "format": "lisp65-c2.3-v1.6-D2-launch-boundary-desk-v1",
        "recorded_on": date.today().isoformat(),
        "status": (
            "DESK FIRST RED: hook-free physical identity has no C07A boot "
            "witness; stopped-state salvage remains read-only"),
        "authorities": {
            "physical_fallback": bind(PHYSICAL_RECEIPT),
            "physical_deployment": bind(PHYSICAL_DEPLOY),
            "phase_C_deployment": bind(PHASE_C_DEPLOY),
            "phase_C_receipt": bind(PHASE_C_RECEIPT),
            "prior_physical_First_Red": bind(PRIOR_RED),
            "driver": bind(Path(__file__).resolve()),
        },
        "facts": facts,
        "mutations_rejected": rejected,
        "execution_witnesses": 4,
        "claim_limit": (
            "Desk classification and physical-identity witness semantics only; "
            "no device read, boot boundary, product defect, measured form or "
            "R/A/I/G result is claimed."),
    }
    write(DESK_RECEIPT, receipt)
    return receipt


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
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})", raw)
    require(match is not None, "monitor register row absent")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    row = {name: f"0x{int(match.group(index), 16):0{width}x}"
           for index, (name, width) in enumerate(zip(names, widths), 1)}
    row["raw_hex"] = raw.hex()
    return row


def read_block(fd: int, address: int, size: int) -> bytes:
    value = bytearray()
    for offset in range(0, size, 16):
        current = address + offset
        raw = command(fd, f"m{current:08x}".encode())
        match = re.search(fr":{current:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
        require(match is not None,
                f"monitor memory row absent at 0x{current:08x}: {raw!r}")
        value.extend(bytes.fromhex(match.group(1).decode()))
    return bytes(value[:size])


def capture_frozen(device: str) -> dict[str, Any]:
    require(DESK_RECEIPT.exists(), "desk receipt absent")
    desk_value = load(DESK_RECEIPT)
    audit_desk(desk_value["facts"])
    require(not CAPTURE_RECEIPT.exists(), "stopped-state capture is one-shot")
    OUT.mkdir(parents=True, exist_ok=True)
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c2v16-launch-boundary\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        values: dict[str, bytes] = {}
        rows: dict[str, Any] = {}
        for name, address, size in RANGES:
            value = read_block(fd, address, size)
            path = OUT / f"frozen-{name}.bin"
            path.write_bytes(value)
            values[name] = value
            rows[name] = bind(path, address)
        # Intentionally no t0: keep the only frozen state intact for review.
    finally:
        os.close(fd)

    record = values["record"]
    phase = values["phase-scratch"]
    c2j = values["c2j"]
    reset = (ROOT / load(PHASE_C_DEPLOY)["record"]["reset"]["path"]).read_bytes()
    first_error = phase[FIRST_ERROR_OFFSET:FIRST_ERROR_OFFSET + 2]
    first_error_path = OUT / "frozen-first-error-state.bin"
    first_error_path.write_bytes(first_error)
    summary = {
        "PC": registers["PC"],
        "C07A_value": record[BOOT_SLOT_OFFSET],
        "C07A_is_boot_witness_in_this_identity": False,
        "record_matches_canonical_reset": record == reset,
        "record_non_reset_bytes": sum(a != b for a, b in zip(record, reset)),
        "first_error_state_hex": first_error.hex(),
        "C2J_nonzero_bytes": sum(value != 0 for value in c2j),
        "CPU_left_stopped": True,
    }
    receipt = {
        "format": "lisp65-c2.3-v1.6-D2-launch-boundary-stopped-state-v1",
        "recorded_on": date.today().isoformat(),
        "status": "CAPTURED-READ-ONLY; CONTROL ROW NOT YET RUN",
        "device": device,
        "authorities": {
            "desk": bind(DESK_RECEIPT),
            "driver": bind(Path(__file__).resolve()),
            "phase_C_deployment": bind(PHASE_C_DEPLOY),
        },
        "registers": registers,
        "captures": {
            **rows,
            "first-error-state": bind(first_error_path,
                                       PHASE_ADDRESS + FIRST_ERROR_OFFSET),
        },
        "summary": summary,
        "control_row": None,
        "claim_limit": (
            "One stopped, read-only salvage of the frozen hook-free diagnostic "
            "launch. C07A and the unarmed record are not boot-progress witnesses; "
            "no reset, resume, measured form, product defect or R/A/I/G result."),
    }
    write(CAPTURE_RECEIPT, receipt)
    return receipt


def check() -> dict[str, Any]:
    facts = desk_facts()
    audit_desk(facts)
    if DESK_RECEIPT.exists():
        receipt = load(DESK_RECEIPT)
        require(receipt["facts"] == facts, "desk receipt facts drift")
    return {
        "status": "PASS",
        "desk_class": facts["screen_classification"]["class"],
        "C07A_is_boot_witness": False,
        "stopped_state_capture_present": CAPTURE_RECEIPT.exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("desk", "check", "capture-frozen"))
    parser.add_argument("--device", default=SERIAL.DEVICE)
    args = parser.parse_args()
    if args.action == "desk":
        value = desk()
    elif args.action == "check":
        value = check()
    else:
        value = capture_frozen(args.device)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BoundaryError, SERIAL.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-launch-boundary: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
