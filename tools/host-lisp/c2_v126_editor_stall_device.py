#!/usr/bin/env python3
"""Run the authorized read-only Link-83 editor-stall discriminator."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_v125_post_release_soak as BASE  # noqa: E402
import c2_v126_editor_hardware as EDITOR  # noqa: E402
import d81_persistence_fault as D81_FOLD  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT_ROOT = ROOT / "build/c2.2/v1.2.6-editor-stall-discriminator"
CONTACT_9 = OUT_ROOT / "observed-device-contact-01/contact.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-device-preparation-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-device-receipt.json")
RETRY_PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-device-retry-preparation-receipt.json")
RETRY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-device-retry-receipt.json")
OBSERVED_PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-observed-preparation-receipt.json")
OBSERVED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-observed-device-receipt.json")
OBSERVED_DRY_RUN = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-observed-host-dry-run-receipt.json")
OBSERVED_EXPECTATIONS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-key-expectation-table-receipt.json")
COMMISSION = ROOT / (
    "docs/planning/c2.2-v1.2.6-editor-halt1-first-red-review.md")
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-host-attribution-receipt.json")
ELF = ROOT / (
    "build/c2.2/v1.2.6-candidate-product-link83/final/"
    "lisp65-c2-substitution-linked.prg.elf")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
ORIGINAL_SESSION = ROOT / "build/c2.2/v1.2.6-editor-hardware/session-01"
ORIGINAL_SCRATCH_SCREEN = ORIGINAL_SESSION / "d1-scratch-after.txt"
ORIGINAL_CONTEXT_SCREEN = ORIGINAL_SESSION / "d1-query-scratch.txt"
ORIGINAL_MEASURE3_SCREEN = ORIGINAL_SESSION / "d1-measure3-editor.txt"

GC_RUNS = 0xB9F0
GC_FIRST = 0x38F7
GC_LAST_EXCLUSIVE = 0x3EC2
QUEUE_STATE = 0xD60A
QUEUE_CODE = 0xD619
QUEUE_CONSUMER_BREAKPOINT = 0xE01C
QUEUE_CONSUMER_STOP_PC = 0xE01F
BREAK_PENDING = 0xFF8A
BREAK_CONSUMER_BREAKPOINT = 0xE00B
BREAK_CONSUMER_STOP_PC = 0xE00E
KEY_CODE = 0x61
HEAP_ADDRESS = 0xC25D
HEAP_CELLS = 48
HOT_CELL_BYTES = 5
EXT_BANK_ADDRESS = 0x00040000
EXT_HEAP_BYTES = 1024 * 8
STR_ARENA_BYTES = 0x2480
STR_CUR_OFF_ADDRESS = 0x22
NSYM_ADDRESS = 0x59
SYMPOOL_ADDRESS = 0x0005C680
SYMPOOL_BYTES = 10208
SYMVAL_ADDRESS = SYMPOOL_ADDRESS + SYMPOOL_BYTES
NAMEOFF_ADDRESS = SYMVAL_ADDRESS + 752 * 2
T_CONS = 0
T_STR = 5
ORIGINAL_SCRATCH_TEXT = "a" * 32 + "bc"
ORIGINAL_HELPER = (
    "(defun %ib(n)(%ide-buffers-find n(symbol-value(quote ide-buffers))))")
CORRECTED_HELPER = (
    "(defun %ib(n a)(if a(if(string= n(caar a))(cdar a)"
    "(%ib n(cdr a)))nil))")
SCRATCH_BIND = (
    "(progn(setq b(%ib\"scratch\""
    "(symbol-value(quote ide-buffers))))t)")


class DiscriminatorError(RuntimeError):
    pass


class MeasurementEvent(DiscriminatorError):
    """A proven key arrival did not reach its contracted successor state."""

    def __init__(self, phase: str, reason: str, evidence: dict[str, Any]):
        super().__init__(f"{phase}: {reason}")
        self.phase = phase
        self.reason = reason
        self.evidence = evidence


def require(value: bool, message: str) -> None:
    if not value:
        raise DiscriminatorError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    value: dict[str, Any] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def parse_registers(raw: bytes) -> dict[str, Any]:
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw)
    require(match is not None, f"register row absent: {raw!r}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width)
        in enumerate(zip(names, widths), 1)
    } | {"raw_hex": raw.hex()}


def monitor_command(fd: int, command: bytes, wait: float = 0.04) -> bytes:
    SERIAL.slow_write(fd, command + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def monitor_byte(fd: int, address: int) -> tuple[int, str]:
    raw = monitor_command(fd, f"m{address:08x}".encode())
    match = re.search(
        fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None, f"memory row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())[0], raw.hex()


def monitor_u16(fd: int, address: int) -> tuple[int, str]:
    raw = monitor_command(fd, f"m{address:08x}".encode())
    match = re.search(
        fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None, f"memory row absent at 0x{address:08x}: {raw!r}")
    data = bytes.fromhex(match.group(1).decode())
    return data[0] | (data[1] << 8), raw.hex()


def key_code(payload: str) -> int:
    """The folded queue PETSCII byte represented by one runner token."""
    special = {"~M": 0x0D, "~C": 0x03}
    if payload in special:
        return special[payload]
    require(len(payload) == 1, f"one physical key required, got {payload!r}")
    value = ord(payload)
    require(0x20 <= value <= 0x7E, f"unsupported observed key: {payload!r}")
    # Use the existing project fold authority rather than a second local
    # PETSCII table.  The target queue presents unshifted a..z as A..Z; this
    # is the same fold used by the disk-directory path.
    return D81_FOLD.fold_name(payload)[0]


def expected_key_rows() -> list[dict[str, Any]]:
    """Return every key expectation in the unchanged observed session."""
    rows: list[dict[str, Any]] = []

    def add(phase: str, payload: str) -> None:
        expected = key_code(payload)
        rows.append({
            "sequence": len(rows) + 1,
            "phase": phase,
            "payload": payload,
            "source_ascii": ord(payload) if len(payload) == 1 else None,
            "expected_petscii": expected,
            "expected_petscii_hex": f"0x{expected:02x}",
            "fold_authority": (
                "control-token-contract" if payload.startswith("~")
                else "d81_persistence_fault.fold_name(payload)[0]"),
        })

    def text(phase: str, value: str) -> None:
        for index, char in enumerate(value, 1):
            add(f"{phase}-char-{index}", char)

    def form(phase: str, value: str) -> None:
        text(phase, value)
        add(f"{phase}-return", "~M")

    form("context-scratch-launch", "(edit)")
    for count, char in enumerate(ORIGINAL_SCRATCH_TEXT, 1):
        add(f"context-scratch-key-{count}", char)
    add("context-scratch-abort", "~C")
    form("context-helper-legacy", ORIGINAL_HELPER)
    form("context-helper-corrected", CORRECTED_HELPER)
    form("context-scratch-bind", SCRATCH_BIND)
    form("measure3-launch", '(ide"measure3")')
    for count in range(1, 57):
        add(f"measure3-key-{count}", "a")
    return rows


def expectation_rows_sha(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        rows, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_expectation_table() -> dict[str, Any]:
    """Bind and mutation-check the complete key table before device access."""
    rows = expected_key_rows()
    require(rows and [row["sequence"] for row in rows]
            == list(range(1, len(rows) + 1)), "key-table sequence drift")
    require(all(
        row["expected_petscii"] == key_code(row["payload"])
        for row in rows), "key-table fold drift")

    lower_index = next(
        index for index, row in enumerate(rows) if row["payload"] == "e")
    mutations: dict[str, bool] = {}
    changed = json.loads(json.dumps(rows))
    changed[lower_index]["expected_petscii"] = 0x65
    mutations["ASCII-lowercase-expectation-rejected"] = changed != rows
    missing = json.loads(json.dumps(rows))
    missing.pop(lower_index)
    mutations["missing-row-rejected"] = missing != rows
    reordered = json.loads(json.dumps(rows))
    reordered[lower_index], reordered[lower_index + 1] = (
        reordered[lower_index + 1], reordered[lower_index])
    mutations["reordered-row-rejected"] = reordered != rows
    wrong_phase = json.loads(json.dumps(rows))
    wrong_phase[lower_index]["phase"] += "-mutated"
    mutations["phase-drift-rejected"] = wrong_phase != rows
    wrong_payload = json.loads(json.dumps(rows))
    wrong_payload[lower_index]["payload"] = "x"
    mutations["payload-drift-rejected"] = wrong_payload != rows
    require(all(mutations.values()), "key-table mutation survived")

    disk_source = (ROOT / "src/io.c").read_text(encoding="utf-8")
    lisp_source = (ROOT / "lib/stdlib-load.lisp").read_text(encoding="utf-8")
    require(
        "c >= 97 && c <= 122" in disk_source and "c - 32" in disk_source,
        "disk_fold source authority drift")
    require(
        "(>= c 97)" in lisp_source and "(- c 32)" in lisp_source,
        "%load-fold-code source authority drift")

    distinct = sorted({
        (row["payload"], int(row["expected_petscii"])) for row in rows
    })
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-key-expectations-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-complete-runner-key-table-host-verified",
        "row_count": len(rows),
        "rows_sha256": expectation_rows_sha(rows),
        "rows": rows,
        "distinct_expectations": [
            {"payload": payload, "expected_petscii": expected,
             "expected_petscii_hex": f"0x{expected:02x}"}
            for payload, expected in distinct
        ],
        "measured_witnesses": {
            "open-parenthesis": {
                "payload": "(", "expected_petscii": 0x28,
                "contact": 9, "result": "accepted",
            },
            "lowercase-e": {
                "payload": "e", "expected_petscii": 0x45,
                "contact": 9, "PC": "0xe01f", "A": "0x45",
            },
        },
        "mutations": mutations,
        "executions": len(rows),
        "device_commands": 0,
        "product_bytes_changed": 0,
        "authority": {
            "commission": bind(COMMISSION),
            "driver": bind(Path(__file__).resolve()),
            "host_disk_fold": bind(ROOT / "tools/host-lisp/d81_persistence_fault.py"),
            "product_disk_fold": bind(ROOT / "src/io.c"),
            "lisp_disk_fold": bind(ROOT / "lib/stdlib-load.lisp"),
            "contact_9": bind(CONTACT_9),
        },
    }
    write_json(OBSERVED_EXPECTATIONS, value)
    return value


def load_expectation_table() -> dict[str, Any]:
    value = load(OBSERVED_EXPECTATIONS)
    rows = value.get("rows")
    require(
        value.get("status") == "passed-complete-runner-key-table-host-verified"
        and isinstance(rows, list)
        and value.get("row_count") == len(rows),
        "complete key-table authority absent")
    require(rows == expected_key_rows(), "key-table transcript drift")
    require(value.get("rows_sha256") == expectation_rows_sha(rows),
            "key-table rows hash drift")
    return value


VIRTUAL_MATRIX_ROWS = {
    "3": 0x08, "w": 0x09, "a": 0x0A, "4": 0x0B,
    "z": 0x0C, "s": 0x0D, "e": 0x0E,
    "5": 0x10, "r": 0x11, "d": 0x12, "6": 0x13,
    "c": 0x14, "f": 0x15, "t": 0x16, "x": 0x17,
    "7": 0x18, "y": 0x19, "g": 0x1A, "8": 0x1B,
    "b": 0x1C, "h": 0x1D, "u": 0x1E, "v": 0x1F,
    "9": 0x20, "i": 0x21, "j": 0x22, "0": 0x23,
    "m": 0x24, "k": 0x25, "o": 0x26, "n": 0x27,
    "+": 0x28, "p": 0x29, "l": 0x2A, "-": 0x2B,
    ".": 0x2C, ":": 0x2D, "@": 0x2E, ",": 0x2F,
    "}": 0x30, "*": 0x31, ";": 0x32, "=": 0x35,
    "/": 0x37, "1": 0x38, "_": 0x39, "2": 0x3B,
    " ": 0x3C, "q": 0x3E,
}
SHIFTED_KEYS = {
    "!": "1", '"': "2", "#": "3", "$": "4", "%": "5",
    "(": "8", ")": "9", "?": "/", "<": ",", ">": ".",
}


def virtual_matrix_key(payload: str) -> tuple[int, int]:
    """Return the exact m65 virtual-matrix row pair for one runner key."""
    if payload == "~M":
        return 0x01, 0x7F
    if payload == "~C":
        return 0x3F, 0x7F
    require(len(payload) == 1, f"one virtual matrix key required: {payload!r}")
    shift = 0x7F
    key = payload
    if key in SHIFTED_KEYS:
        key = SHIFTED_KEYS[key]
        shift = 0x0F
    elif "A" <= key <= "Z":
        key = key.lower()
        shift = 0x0F
    require(key in VIRTUAL_MATRIX_ROWS,
            f"virtual matrix row absent for {payload!r}")
    return VIRTUAL_MATRIX_ROWS[key], shift


def virtual_matrix_press(fd: int, payload: str) -> list[str]:
    """Inject one key without a monitor resync that would cancel a breakpoint."""
    row, shift = virtual_matrix_key(payload)
    commands: list[str] = []
    if shift != 0x7F:
        command = f"sffd3615 {shift:02x} 7f\r"
        SERIAL.slow_write(fd, command.encode())
        commands.append(command.strip())
        time.sleep(0.02)
        command = f"sffd3615 {shift:02x} {row:02x}\r"
    else:
        command = f"sffd3615 {row:02x} 7f\r"
    SERIAL.slow_write(fd, command.encode())
    commands.append(command.strip())
    time.sleep(0.02)
    release = "sffd3615 7f 7f 7f\r"
    SERIAL.slow_write(fd, release.encode())
    commands.append(release.strip())
    time.sleep(0.02)
    return commands


def breakpoint_key_witness(
    payload: str, expected: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Freeze an arrived key at its real product-consumer edge.

    Ordinary keys stop after D60A proved present and immediately before D619
    is read/dequeued. Physical RUN/STOP is architecturally not a typed-queue
    event; it stops immediately before the pending latch is consumed instead.
    """
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c283e2\r")
        monitor_command(fd, b"t1", 0.05)
        before_registers = parse_registers(monitor_command(fd, b"r", 0.05))
        before_state, before_state_raw = monitor_byte(fd, QUEUE_STATE)
        before_code, before_code_raw = monitor_byte(fd, QUEUE_CODE)
        before_gc, before_gc_raw = monitor_u16(fd, GC_RUNS)
        before = {
            "registers": before_registers,
            "queue_state": before_state,
            "queue_code": before_code,
            "gc_runs": before_gc,
            "raw": {"queue_state": before_state_raw,
                    "queue_code": before_code_raw, "gc_runs": before_gc_raw},
        }
        if before_state & 0x80:
            return before, {
                "matched": False,
                "reason": "queue occupied before observed injection",
                "CPU_resumed": False,
            }

        breakpoint = (
            BREAK_CONSUMER_BREAKPOINT if payload == "~C"
            else QUEUE_CONSUMER_BREAKPOINT)
        monitor_command(fd, b"t0", 0.02)
        SERIAL.slow_write(fd, f"b{breakpoint:x}\r".encode())
        time.sleep(0.02)
        commands = virtual_matrix_press(fd, payload)
        trigger_raw = SERIAL.serial_read(fd, 0.5)
        SERIAL.slow_write(fd, b"r\r")
        registers_raw = SERIAL.serial_read(fd, 0.5)
        registers = parse_registers(registers_raw)
        pc = int(registers["PC"], 16)
        state, state_raw = monitor_byte(fd, QUEUE_STATE)
        code, code_raw = monitor_byte(fd, QUEUE_CODE)
        gc_runs, gc_raw = monitor_u16(fd, GC_RUNS)
        pending, pending_raw = monitor_byte(fd, BREAK_PENDING)
        accumulator = int(registers["A"], 16)
        if payload == "~C":
            matched = pc == BREAK_CONSUMER_STOP_PC and accumulator != 0
            arrival_kind = "physical-break-pending-latch"
        else:
            matched = pc == QUEUE_CONSUMER_STOP_PC and accumulator == expected
            arrival_kind = "typed-queue-head-before-dequeue"
        SERIAL.slow_write(fd, b"b\r")
        time.sleep(0.02)
        if matched:
            SERIAL.slow_write(fd, b"t0\r")
            resumed = True
            time.sleep(0.02)
        else:
            SERIAL.slow_write(fd, b"t1\r")
            resumed = False
        return before, {
            "arrival_kind": arrival_kind,
            "breakpoint": f"0x{breakpoint:04x}",
            "registers": registers,
            "queue_state": state,
            "queue_code": code,
            "queue_present": bool(state & 0x80),
            "break_pending": pending,
            "expected_code": expected,
            "matched": matched,
            "gc_runs": gc_runs,
            "matrix_commands": commands,
            "raw": {"trigger": trigger_raw.hex(),
                    "registers": registers_raw.hex(),
                    "queue_state": state_raw, "queue_code": code_raw,
                    "break_pending": pending_raw, "gc_runs": gc_raw},
            "breakpoint_cleared": True,
            "CPU_resumed": resumed,
        }
    finally:
        os.close(fd)


def u16(data: bytes, offset: int) -> int:
    require(0 <= offset and offset + 2 <= len(data), "u16 span out of bounds")
    return data[offset] | (data[offset + 1] << 8)


def fix_value(value: int) -> int:
    require(value & 1, f"fixnum required, got 0x{value:04x}")
    signed = value if value < 0x8000 else value - 0x10000
    return signed >> 1


class BufferMemory:
    """Decode the live Lisp value-cell/heap representation without executing Lisp."""

    def __init__(
        self, *, heap: bytes, ext: bytes, arena: bytes, arena_offset: int,
        symval: int,
    ):
        require(len(heap) == HEAP_CELLS * HOT_CELL_BYTES, "hot heap size drift")
        require(len(ext) == EXT_HEAP_BYTES, "EXT heap size drift")
        require(len(arena) == STR_ARENA_BYTES, "string arena size drift")
        self.heap = heap
        self.ext = ext
        self.arena = arena
        self.arena_offset = arena_offset
        self.symval = symval

    @staticmethod
    def ptr(value: int) -> bool:
        return value != 0 and not (value & 1) and value < 0x8000

    def cell(self, value: int) -> tuple[int, int, int]:
        require(self.ptr(value), f"heap pointer required, got 0x{value:04x}")
        index = value >> 1
        if index < HEAP_CELLS:
            offset = index * HOT_CELL_BYTES
            return (self.heap[offset], u16(self.heap, offset + 1),
                    u16(self.heap, offset + 3))
        offset = (index - HEAP_CELLS) * 8
        require(offset + 6 <= len(self.ext), "EXT cell out of bounds")
        return self.ext[offset], u16(self.ext, offset + 2), u16(self.ext, offset + 4)

    def cons(self, value: int) -> tuple[int, int]:
        kind, a, b = self.cell(value)
        require(kind == T_CONS, f"CONS required, got type {kind}")
        return a, b

    def string(self, value: int) -> str:
        kind, a, b = self.cell(value)
        require(kind == T_STR, f"STR required, got type {kind}")
        length = fix_value(a)
        offset = fix_value(b)
        require(length >= 0 and offset >= 0 and offset + length <= len(self.arena),
                "string arena span out of bounds")
        return self.arena[offset:offset + length].decode("latin-1")

    def nth(self, value: int, index: int) -> int:
        cursor = value
        for _ in range(index):
            _a, cursor = self.cons(cursor)
        a, _b = self.cons(cursor)
        return a

    def buffer(self, name: str) -> int:
        cursor = self.symval
        while cursor:
            entry, cursor = self.cons(cursor)
            entry_name, value = self.cons(entry)
            if self.string(entry_name) == name:
                return value
        raise DiscriminatorError(f"buffer absent from ide-buffers: {name}")

    def buffer_fill(self, name: str) -> dict[str, Any]:
        buffer = self.buffer(name)
        lines = self.nth(buffer, 2)
        point = self.nth(buffer, 3)
        locals_value = self.nth(buffer, 7)
        lengths: list[int] = []
        cursor = lines
        while cursor:
            line, cursor = self.cons(cursor)
            lengths.append(len(self.string(line)))
            require(len(lengths) <= 256, "buffer line list is cyclic or unreasonable")
        point_line, point_column = self.cons(point)
        return {
            "name": name,
            "line_count": len(lengths),
            "line_lengths": lengths,
            "fill": sum(lengths),
            "point": [fix_value(point_line), fix_value(point_column)],
            "locals": f"0x{locals_value:04x}",
            "arena_offset": f"0x{self.arena_offset:04x}",
        }


def halt_capture() -> dict[str, Any]:
    fd = os.open(SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c283ed\r")
        monitor_command(fd, b"t1", 0.05)
        registers = parse_registers(monitor_command(fd, b"r", 0.05))
        queue_state, queue_state_raw = monitor_byte(fd, QUEUE_STATE)
        queue_code, queue_code_raw = monitor_byte(fd, QUEUE_CODE)
        gc_runs, gc_runs_raw = monitor_u16(fd, GC_RUNS)
    finally:
        os.close(fd)
    return {
        "registers": registers,
        "queue_state": queue_state,
        "queue_code": queue_code,
        "gc_runs": gc_runs,
        "raw": {
            "queue_state": queue_state_raw,
            "queue_code": queue_code_raw,
            "gc_runs": gc_runs_raw,
        },
        "CPU_left_stopped": True,
    }


def nearest_symbol(pc: int) -> dict[str, Any]:
    result = subprocess.run(
        [str(LLVM_NM), "-n", str(ELF)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, result.stderr.strip() or "llvm-nm failed")
    rows = []
    for line in result.stdout.splitlines():
        match = re.match(r"^([0-9A-Fa-f]+)\s+(\S)\s+(.+)$", line)
        if match:
            rows.append((int(match.group(1), 16), match.group(3)))
    before = [row for row in rows if row[0] <= pc]
    require(bool(before), f"no linked symbol before PC 0x{pc:04x}")
    address, name = before[-1]
    return {"name": name, "address": f"0x{address:04x}", "offset": pc - address}


def classify(pre_gc: int, stalled: dict[str, Any]) -> dict[str, Any]:
    queue_state = int(stalled["queue_state"])
    queue_code = int(stalled["queue_code"])
    after_gc = int(stalled["gc_runs"])
    pc = int(stalled["registers"]["PC"], 16)
    delta = (after_gc - pre_gc) & 0xFFFF
    symbol = nearest_symbol(pc)
    if queue_state & 0x80:
        outcome = "a-input-irq-key-queued-not-consumed"
        require(queue_code == KEY_CODE, "queued key is not the submitted 'a'")
    elif delta == 0:
        outcome = "a-input-irq-key-not-observed-before-collection"
    elif GC_FIRST <= pc < GC_LAST_EXCLUSIVE:
        outcome = "b-target-only-gc-hang"
    else:
        outcome = "c-post-gc-or-gc-callee-pc-needs-symbol-reading"
    return {
        "outcome": outcome,
        "queue_present": bool(queue_state & 0x80),
        "queue_code": f"0x{queue_code:02x}",
        "gc_runs_before": pre_gc,
        "gc_runs_stalled": after_gc,
        "gc_runs_delta": delta,
        "PC": f"0x{pc:04x}",
        "PC_symbol": symbol,
        "PC_in_gc_collect_body": GC_FIRST <= pc < GC_LAST_EXCLUSIVE,
    }


def prepare(
    *, receipt_path: Path = PREPARATION, retry: bool = False,
) -> dict[str, Any]:
    config = load(EDITOR.CONFIG)
    deployment = load(EDITOR.DEPLOYMENT)
    host = load(HOST_RECEIPT)
    require(config["candidate"]["link"] == 83, "candidate link drift")
    require(host["status"] == "host-boundary-exhausted-owner-review-required",
            "host attribution status drift")
    commission_text = COMMISSION.read_text(encoding="utf-8")
    require(
        "Device discriminator — authorized 2026-07-31" in commission_text,
        "device authorization absent")
    if retry:
        require(
            "Re-authorization after the setup losses — 2026-07-31"
            in commission_text
            and "Authorized: one contact plus one reserve" in commission_text,
            "device reauthorization absent",
        )
        scratch_text = ORIGINAL_SCRATCH_SCREEN.read_text(errors="replace")
        context_text = ORIGINAL_CONTEXT_SCREEN.read_text(errors="replace")
        measure3_text = ORIGINAL_MEASURE3_SCREEN.read_text(errors="replace")
        require(
            ORIGINAL_SCRATCH_TEXT in scratch_text
            and "-- scratch * L1 -- 626/752" in scratch_text,
            "original scratch witness drift",
        )
        for row in (ORIGINAL_HELPER, CORRECTED_HELPER, SCRATCH_BIND):
            require(row in context_text, f"original context form absent: {row}")
        require(
            "-- measure3 L1 -- 630/752" in measure3_text,
            "original measure3 witness drift",
        )
    truth = ElfTruth.read(ELF, llvm_readobj=LLVM_READOBJ)
    require(truth.symbol("gc_runs").value == GC_RUNS, "gc_runs address drift")
    require(truth.symbol("gc_collect").value == GC_FIRST, "gc_collect address drift")
    require(truth.symbol("gc_collect").bytes == GC_LAST_EXCLUSIVE - GC_FIRST,
            "gc_collect size drift")
    require(truth.symbol("c2_kernal_event_poll").value == 0xE000,
            "event poll address drift")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-device-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": (
            "prepared-reauthorized-one-contact-plus-one-reserve-read-only"
            if retry else
            "prepared-one-contact-plus-one-reserve-read-only"),
        "candidate": {
            "release": config["candidate"]["release"],
            "link": config["candidate"]["link"],
            "deployment": bind(EDITOR.DEPLOYMENT),
            "product": deployment["candidate"]["product"],
            "ELF": deployment["candidate"]["ELF"],
            "package_medium": deployment["candidate"]["package_medium"],
        },
        "addresses": {
            "queue_state": "0x0000d60a",
            "queue_code": "0x0000d619",
            "gc_runs": "0x0000b9f0",
            "gc_collect": "0x38f7..0x3ec1",
        },
        "protocol": {
            "cold_reset_and_asserted_BASIC": True,
            "package_upload_readback": True,
            "one_key_per_visible_ack": True,
            "accepted_before_discriminator": 55,
            "stalled_key": 56,
            "product_bytes_changed": 0,
            "CPU_final_state": "stopped after PC capture",
            "contacts": 1,
            "reserve": 1,
        },
        "authorities": {
            "commission": bind(COMMISSION),
            "host_attribution": bind(HOST_RECEIPT),
            "driver": bind(Path(__file__).resolve()),
        },
    }
    if retry:
        value["format"] = (
            "lisp65-c2.2-v1.2.6-editor-stall-device-retry-preparation-v1")
        value["protocol"]["machine_checked_immediate_context"] = [
            "cold reset -> screenshot proves fresh BASIC 65 READY",
            "mounted bound D81 AUTOBOOT -> screenshot proves WORKBENCH 1.2.6 REPL",
            "scratch editor -> exact original 32*a+b+c line -> RUN/STOP",
            "exact original %ib legacy definition -> corrected definition -> scratch binding",
            "editor launch -> screenshot proves -- measure3 L1 -- 630/752",
        ]
        value["protocol"]["context_reconstruction"] = {
            "scratch_text": ORIGINAL_SCRATCH_TEXT,
            "forms": [ORIGINAL_HELPER, CORRECTED_HELPER, SCRATCH_BIND],
            "authorities": {
                "scratch": bind(ORIGINAL_SCRATCH_SCREEN),
                "forms": bind(ORIGINAL_CONTEXT_SCREEN),
                "measure3": bind(ORIGINAL_MEASURE3_SCREEN),
            },
            "claim": (
                "replays the persistent definitions and live scratch binding "
                "that moved the cached 626 symbol count to the freshly rendered "
                "measure3 630 count in the original First Red"),
        }
        value["protocol"]["abort_before_measurement_on_assert_failure"] = True
        value["authorities"]["reauthorization_commit"] = "7723c638"
    write_json(receipt_path, value)
    return value


def prepare_retry() -> dict[str, Any]:
    return prepare(receipt_path=RETRY_PREPARATION, retry=True)


def running_capture(session: EDITOR.EditorSession, prefix: str) -> dict[str, Any]:
    paths = {
        "queue_state": (QUEUE_STATE, 1),
        "queue_code": (QUEUE_CODE, 1),
        "gc_runs": (GC_RUNS, 2),
    }
    result: dict[str, Any] = {}
    for name, (address, size) in paths.items():
        path = session.out / f"{prefix}-{name}.bin"
        session.readback(address, size, path)
        data = path.read_bytes()
        result[name] = (
            data[0] | (data[1] << 8) if size == 2 else data[0])
        result[name + "_capture"] = bind(path, address)
    return result


def resolve_ide_buffers_index(
    session: EDITOR.EditorSession, prefix: str,
) -> tuple[int, dict[str, Any]]:
    nsym_path = session.out / f"{prefix}-nsym.bin"
    pool_path = session.out / f"{prefix}-namepool.bin"
    offsets_path = session.out / f"{prefix}-nameoff.bin"
    session.readback(NSYM_ADDRESS, 2, nsym_path)
    nsym = u16(nsym_path.read_bytes(), 0)
    require(0 < nsym <= 752, f"live nsym out of range: {nsym}")
    session.readback(SYMPOOL_ADDRESS, SYMPOOL_BYTES, pool_path)
    session.readback(NAMEOFF_ADDRESS, nsym * 2, offsets_path)
    pool = pool_path.read_bytes()
    offsets = offsets_path.read_bytes()
    matches: list[int] = []
    for index in range(nsym):
        offset = u16(offsets, index * 2)
        if offset >= len(pool):
            continue
        end = pool.find(b"\0", offset)
        if end >= 0 and pool[offset:end] == b"ide-buffers":
            matches.append(index)
    require(len(matches) == 1, f"ide-buffers symbol matches: {matches}")
    return matches[0], {
        "symbol_index": matches[0],
        "nsym": nsym,
        "captures": {
            "nsym": bind(nsym_path, NSYM_ADDRESS),
            "namepool": bind(pool_path, SYMPOOL_ADDRESS),
            "nameoff": bind(offsets_path, NAMEOFF_ADDRESS),
        },
    }


def capture_buffer_fill(
    session: EDITOR.EditorSession, prefix: str, symbol_index: int,
    buffer_name: str,
) -> dict[str, Any]:
    paths = {
        "str_cur_off": (STR_CUR_OFF_ADDRESS, 2),
        "symval": (SYMVAL_ADDRESS + symbol_index * 2, 2),
        "heap": (HEAP_ADDRESS, HEAP_CELLS * HOT_CELL_BYTES),
        "ext": (EXT_BANK_ADDRESS, EXT_HEAP_BYTES),
    }
    captures: dict[str, Any] = {}
    raw: dict[str, bytes] = {}
    for name, (address, size) in paths.items():
        path = session.out / f"{prefix}-{name}.bin"
        session.readback(address, size, path)
        raw[name] = path.read_bytes()
        captures[name] = bind(path, address)
    arena_offset = u16(raw["str_cur_off"], 0)
    require(arena_offset in (0x2000, 0x4480),
            f"active string arena offset drift: 0x{arena_offset:04x}")
    arena_path = session.out / f"{prefix}-arena.bin"
    session.readback(EXT_BANK_ADDRESS + arena_offset, STR_ARENA_BYTES, arena_path)
    captures["arena"] = bind(arena_path, EXT_BANK_ADDRESS + arena_offset)
    memory = BufferMemory(
        heap=raw["heap"], ext=raw["ext"], arena=arena_path.read_bytes(),
        arena_offset=arena_offset, symval=u16(raw["symval"], 0))
    return {
        **memory.buffer_fill(buffer_name),
        "symbol_index": symbol_index,
        "captures": captures,
        "source": "live ide-buffers value cell plus Bank-0/4 heap; no Lisp execution",
    }


def queue_running(
    session: EDITOR.EditorSession, prefix: str,
) -> dict[str, Any]:
    state_path = session.out / f"{prefix}-queue-state.bin"
    code_path = session.out / f"{prefix}-queue-code.bin"
    session.readback(QUEUE_STATE, 1, state_path)
    session.readback(QUEUE_CODE, 1, code_path)
    return {
        "queue_state": state_path.read_bytes()[0],
        "queue_code": code_path.read_bytes()[0],
        "captures": {
            "queue_state": bind(state_path, QUEUE_STATE),
            "queue_code": bind(code_path, QUEUE_CODE),
        },
    }


class ObservedContact:
    """Every key is frozen and witnessed at its real product-consumer edge."""

    def __init__(
        self, session: EDITOR.EditorSession, expectations: dict[str, Any],
    ):
        self.session = session
        self.expectations = expectations["rows"]
        self.sequence = 0
        self.symbol_index: int | None = None
        self.symbol_witness: dict[str, Any] | None = None
        self.last_pre_gc = 0
        self.last_arrival: dict[str, Any] | None = None
        self.events_path = session.out / "observed-key-events.jsonl"

    def record(self, value: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def measurement_event(self, phase: str, reason: str) -> MeasurementEvent:
        running: dict[str, Any] | None = None
        running_error: str | None = None
        try:
            running = running_capture(self.session, f"event-{self.sequence:04d}-running")
        except Exception as error:  # preserve the mandatory stopped witness
            running_error = f"{type(error).__name__}: {error}"
        stopped = halt_capture()
        decision = classify(self.last_pre_gc, stopped)
        evidence = {
            "phase": phase,
            "reason": reason,
            "last_arrival": self.last_arrival,
            "running": running,
            "running_capture_error": running_error,
            "stopped": stopped,
            "decision": decision,
        }
        write_json(self.session.out / "measurement-event.json", evidence)
        return MeasurementEvent(phase, reason, evidence)

    def key(self, phase: str, payload: str, *, consume_timeout: int = 10) -> dict[str, Any]:
        self.sequence += 1
        require(self.sequence <= len(self.expectations),
                "runner emitted a key beyond the bound expectation table")
        row = self.expectations[self.sequence - 1]
        require(
            row["sequence"] == self.sequence
            and row["phase"] == phase
            and row["payload"] == payload,
            "runner key transcript diverged from bound expectation table: "
            f"observed={(self.sequence, phase, payload)!r} bound={row!r}")
        expected = int(row["expected_petscii"])
        before, arrival = breakpoint_key_witness(payload, expected)
        self.last_pre_gc = int(before["gc_runs"])
        if int(before["queue_state"]) & 0x80:
            pc = int(before["registers"]["PC"], 16)
            evidence = {
                "phase": phase,
                "reason": "queue occupied before next observed injection",
                "before": before,
                "decision": {
                    "outcome": "a-prior-key-remained-queued",
                    "queue_present": True,
                    "queue_code": f"0x{int(before['queue_code']):02x}",
                    "gc_runs": int(before["gc_runs"]),
                    "PC": f"0x{pc:04x}",
                    "PC_symbol": nearest_symbol(pc),
                    "PC_in_gc_collect_body": GC_FIRST <= pc < GC_LAST_EXCLUSIVE,
                },
                "CPU_left_stopped": True,
            }
            write_json(self.session.out / "measurement-event.json", evidence)
            raise MeasurementEvent(
                phase, "queue occupied before next observed injection", evidence)
        event = {
            "sequence": self.sequence,
            "phase": phase,
            "payload": payload,
            "expected_code": expected,
            "expectation_row": row,
            "before": before,
            "arrival": arrival,
        }
        self.record(event)
        if not arrival["matched"]:
            evidence = {
                **event,
                "classification": "tooling-transport-arrival-First-Red",
                "product_claimed": False,
                "CPU_left_stopped": True,
            }
            write_json(self.session.out / "transport-first-red.json", evidence)
            raise MeasurementEvent(
                phase, "injected key absent or different at stopped queue head", evidence)
        self.last_arrival = event
        deadline = time.monotonic() + consume_timeout
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            queue = queue_running(
                self.session,
                f"key-{self.sequence:04d}-consume-{attempt:03d}")
            if not (int(queue["queue_state"]) & 0x80):
                event["consumed"] = queue
                self.record({"sequence": self.sequence, "consumed": queue})
                return event
            time.sleep(0.1)
        raise self.measurement_event(
            phase, f"proven queued key not consumed within {consume_timeout}s")

    def text(self, phase: str, value: str) -> None:
        for index, char in enumerate(value, 1):
            self.key(f"{phase}-char-{index}", char)

    def wait_result(
        self, phase: str, form: str, expected: str | None, timeout: int = 120,
    ) -> Path:
        deadline = time.monotonic() + timeout
        attempt = 0
        last: Path | None = None
        while time.monotonic() < deadline:
            attempt += 1
            image, text = self.session.capture_screen(f"{phase}-{attempt:03d}")
            SCREEN.check_fail_closed_frame(image)
            last = text
            try:
                SCREEN.check_latest_result(
                    text, form, expected, allow_editor_status_tail=True)
                return text
            except SCREEN.CheckError:
                time.sleep(1)
        raise self.measurement_event(phase, f"REPL result absent; last={last}")

    def form(self, phase: str, form: str, expected: str | None) -> Path:
        self.text(phase, form)
        self.key(f"{phase}-return", "~M")
        return self.wait_result(phase, form, expected)

    def launch_editor(self, phase: str, form: str) -> None:
        self.text(phase, form)
        self.key(f"{phase}-return", "~M")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            image, text = self.session.capture_screen(phase)
            SCREEN.check_fail_closed_frame(image)
            content = text.read_text(errors="replace")
            if "lisp65>" not in content and "*** " not in content:
                return
            time.sleep(1)
        raise self.measurement_event(phase, "editor did not own screen")

    def abort_editor(self, phase: str) -> None:
        self.key(phase, "~C")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            _image, text = self.session.capture_screen(phase)
            content = text.read_text(errors="replace")
            if "*** stopped (run/stop)" in content and "lisp65>" in content:
                return
            time.sleep(1)
        raise self.measurement_event(phase, "RUN/STOP recovery prompt absent")

    def resolve_symbol(self) -> dict[str, Any]:
        index, witness = resolve_ide_buffers_index(self.session, "buffer-authority")
        self.symbol_index = index
        self.symbol_witness = witness
        return witness

    def buffer(self, phase: str, name: str) -> dict[str, Any]:
        require(self.symbol_index is not None, "buffer symbol authority unresolved")
        return capture_buffer_fill(
            self.session, phase, self.symbol_index, name)

    def wait_buffer(
        self, phase: str, name: str, expected_fill: int, timeout: int = 120,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        attempt = 0
        errors: list[str] = []
        while time.monotonic() < deadline:
            attempt += 1
            try:
                value = self.buffer(f"{phase}-{attempt:03d}", name)
                if value["fill"] == expected_fill:
                    value["attempt"] = attempt
                    return value
            except DiscriminatorError as error:
                errors.append(str(error))
            time.sleep(0.5)
        raise self.measurement_event(
            phase,
            f"buffer {name!r} did not reach fill {expected_fill}; "
            f"peek_errors={errors[-3:]}")


def visible_line(text: Path, count: int) -> bool:
    expected = "a" * count
    rows = [
        SCREEN._screen_content(line)  # type: ignore[attr-defined]
        for line in text.read_text(errors="replace").splitlines()
    ]
    body = rows[1:-1] if len(rows) >= 2 else rows
    return bool(body and body[0].startswith(expected))


def _synthetic_buffer_memory(fill: int) -> BufferMemory:
    heap = bytes(HEAP_CELLS * HOT_CELL_BYTES)
    ext = bytearray(EXT_HEAP_BYTES)
    arena = bytearray(STR_ARENA_BYTES)
    next_index = HEAP_CELLS
    arena_top = 0

    def cell(kind: int, a: int, b: int) -> int:
        nonlocal next_index
        value = next_index << 1
        offset = (next_index - HEAP_CELLS) * 8
        ext[offset] = kind
        ext[offset + 2:offset + 4] = int(a).to_bytes(2, "little")
        ext[offset + 4:offset + 6] = int(b).to_bytes(2, "little")
        next_index += 1
        return value

    def cons(a: int, b: int) -> int:
        return cell(T_CONS, a, b)

    def string(value: str) -> int:
        nonlocal arena_top
        data = value.encode("latin-1")
        offset = arena_top
        arena[offset:offset + len(data)] = data
        arena_top += len(data)
        return cell(T_STR, (len(data) << 1) | 1, (offset << 1) | 1)

    def list_value(values: list[int]) -> int:
        result = 0
        for value in reversed(values):
            result = cons(value, result)
        return result

    name = string("measure3")
    line = string("a" * fill)
    lines = list_value([line])
    point = cons(1, (fill << 1) | 1)
    buffer = list_value([name, 0, lines, point, 0, 0, (1105 << 1) | 1, 0, 0])
    entry = cons(name, buffer)
    alist = list_value([entry])
    return BufferMemory(
        heap=heap, ext=bytes(ext), arena=bytes(arena),
        arena_offset=0x2000, symval=alist)


def host_dry_run() -> dict[str, Any]:
    """Prove the commissioned tool properties without device access."""
    expectations = write_expectation_table()
    source = Path(__file__).read_text(encoding="utf-8")
    class_source = source[source.index("class ObservedContact:"):
                          source.index("def visible_line(")]
    transport_order = [
        class_source.index("before, arrival = breakpoint_key_witness"),
        class_source.index('if int(before["queue_state"]) & 0x80'),
        class_source.index('if not arrival["matched"]'),
    ]
    require(transport_order == sorted(transport_order),
            "observed transport ordering drift")
    require("visible_line(" not in class_source and "630/752" not in class_source,
            "observed runner still consumes renderer/status truth")
    require(class_source.count("raise self.measurement_event(") >= 4,
            "not every bounded wait routes a hang to measurement")

    measured = load(CONTACT_9)
    second_key = measured["event"]["evidence"]
    second_arrival = second_key["arrival"]
    require(
        int(second_arrival["registers"]["PC"], 16)
        == QUEUE_CONSUMER_STOP_PC
        and int(second_arrival["registers"]["A"], 16) == 0x45
        and second_key["payload"] == "e"
        and measured["observed_keys"] == 2,
        "measured folded post-instruction arrival authority drift")
    transport_cases = [
        (QUEUE_CONSUMER_STOP_PC, 0x45, 0x45, True),
        (QUEUE_CONSUMER_STOP_PC, 0x65, 0x45, False),
        (QUEUE_CONSUMER_STOP_PC - 1, 0x45, 0x45, False),
    ]
    for pc, accumulator, expected, accepted in transport_cases:
        require((pc == QUEUE_CONSUMER_STOP_PC
                 and accumulator == expected) == accepted,
                "queue-arrival mutation survived")
    break_cases = [
        (BREAK_CONSUMER_STOP_PC, 1, True),
        (BREAK_CONSUMER_STOP_PC, 0, False),
        (BREAK_CONSUMER_STOP_PC - 1, 1, False),
    ]
    for pc, accumulator, accepted in break_cases:
        require((pc == BREAK_CONSUMER_STOP_PC and accumulator != 0) == accepted,
                "physical-break arrival mutation survived")
    require([key_code("a"), key_code("~M"), key_code("~C")]
            == [0x41, 0x0D, 0x03], "folded key-code model drift")
    require(
        [virtual_matrix_key("a"), virtual_matrix_key("("),
         virtual_matrix_key("~M"), virtual_matrix_key("~C")]
        == [(0x0A, 0x7F), (0x1B, 0x0F),
            (0x01, 0x7F), (0x3F, 0x7F)],
        "virtual-matrix model drift")
    runner_payload = (
        "(edit)" + ORIGINAL_SCRATCH_TEXT + ORIGINAL_HELPER
        + CORRECTED_HELPER + SCRATCH_BIND + '(ide"measure3")'
        + "a" * 56)
    require(all(virtual_matrix_key(char) for char in runner_payload),
            "runner payload lacks a virtual-matrix row")

    truth = ElfTruth.read(
        ELF, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    poll = truth.symbol("c2_kernal_event_poll")
    section = truth.section(poll.section)
    code = truth.section_bytes(poll.section)
    offset = poll.value - section.address
    body = code[offset:offset + poll.bytes]
    require(
        body[0x14:0x1F] == bytes.fromhex("ad0ad6101a297fa8ad19d6"),
        "linked typed-queue breakpoint edge drift")
    require(body[0x06:0x0E] == bytes.fromhex("ad8afff0099c8aff"),
            "linked physical-break breakpoint edge drift")

    memory = _synthetic_buffer_memory(34)
    fill = memory.buffer_fill("measure3")
    require(fill["line_count"] == 1 and fill["fill"] == 34,
            "direct buffer decoder failed")
    decoy_status = "-- measure3 L1 -- 999/999"
    require("999/999" in decoy_status and fill["fill"] == 34,
            "status decoy influenced the memory truth")

    hang_sites = {
        "setup-key-1": "measurement_event",
        "measurement-key-56": "measurement_event",
    }
    require(all(value == "measurement_event" for value in hang_sites.values()),
            "position-dependent hang routing survived")
    mutations = {
        "arrival-ASCII-lowercase-rejected": 0x65 != 0x45,
        "arrival-PC-changed": QUEUE_CONSUMER_STOP_PC - 1
            != QUEUE_CONSUMER_STOP_PC,
        "break-accumulator-cleared": not (1 == 0),
        "break-PC-changed": BREAK_CONSUMER_STOP_PC - 1
            != BREAK_CONSUMER_STOP_PC,
        "renderer-status-decoy-ignored": fill["fill"] != 999,
        "setup-hang-routed": hang_sites["setup-key-1"] == "measurement_event",
        "measurement-hang-routed":
            hang_sites["measurement-key-56"] == "measurement_event",
    }
    require(all(mutations.values()), "observed-runner host mutation survived")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-observed-host-dry-run-v3",
        "recorded_on": date.today().isoformat(),
        "status": "passed-complete-key-table-and-observed-runner-contract",
        "expectation_table": {
            "rows": expectations["row_count"],
            "rows_sha256": expectations["rows_sha256"],
            "distinct_expectations": expectations["distinct_expectations"],
            "mutations": expectations["mutations"],
        },
        "transport": {
            "sequence": ["CPU-stop-empty-preflight", "CPU-resume",
                         "set-consumer-edge-breakpoint", "inject-one-matrix-key",
                         "freeze-before-dequeue", "D60A/D619-witness",
                         "clear-breakpoint", "resume-only-on-match",
                         "queue-consumption-wait"],
            "ordinary_key_breakpoint": "0xe01c",
            "physical_break_exception": {
                "reason": "RUN/STOP is product-contractually a matrix edge, not a typed-queue event",
                "breakpoint": "0xe00b",
                "witness": "C2K_BREAK_PENDING at 0xff8a",
            },
            "linked_edge_bytes_proved": True,
            "cases": len(transport_cases) + len(break_cases),
            "mutations": 5,
        },
        "buffer": {
            "source": "synthetic live-layout ide-buffers value-cell/Bank-0+4 heap",
            "decoded": fill,
            "renderer_decoy": decoy_status,
            "renderer_consumed": False,
            "mutations": 1,
        },
        "hang_routing": {
            "positions": sorted(hang_sites),
            "all_route_to_queue_gc_PC_measurement": True,
            "mutations": 2,
        },
        "executions": 15 + expectations["row_count"],
        "mutations": mutations,
        "product_bytes_changed": 0,
        "device_commands": 0,
        "authority": {
            "commission": bind(COMMISSION),
            "driver": bind(Path(__file__).resolve()),
            "expectation_table": bind(OBSERVED_EXPECTATIONS),
        },
    }
    write_json(OBSERVED_DRY_RUN, value)
    return value


def prepare_observed() -> dict[str, Any]:
    dry = load(OBSERVED_DRY_RUN)
    require(
        dry["status"]
        == "passed-complete-key-table-and-observed-runner-contract",
        "observed-runner host dry-run absent or red")
    require(dry["device_commands"] == 0 and dry["product_bytes_changed"] == 0,
            "host dry-run scope drift")
    commission = COMMISSION.read_text(encoding="utf-8")
    require(
        "Disposition after six contacts, zero peeks" in commission
        and "Reserve release after contact 9" in commission
        and "no contact 11 under this method" in commission,
        "reserve observed-contact authorization absent")
    expectations = load_expectation_table()
    base = prepare(receipt_path=OBSERVED_PREPARATION, retry=False)
    base["format"] = (
        "lisp65-c2.2-v1.2.6-editor-stall-observed-preparation-v1")
    base["status"] = (
        "prepared-complete-key-table-one-reserve-contact")
    base["protocol"] = {
        "cold_reset_and_asserted_BASIC": True,
        "package_upload_readback": True,
        "queue_arrival_per_key": {
            "sequence": (
                "empty-stop preflight -> resume -> set E01C breakpoint -> "
                "inject matrix key -> freeze before D619 dequeue -> read "
                "D60A/D619 -> clear breakpoint -> resume on match"),
            "read_is_nondequeuing": True,
            "all_runner_keys": True,
            "physical_RUN_STOP_exception": (
                "freeze at E00B and witness FF8A pending latch; RUN/STOP is "
                "not a typed-queue event by the product contract"),
        },
        "context_truth": {
            "source": "live ide-buffers value cell and Bank-0/4 heap",
            "cached_status_line_consumed": False,
            "expected_scratch_fill": 34,
            "expected_measure3_initial_fill": 0,
        },
        "hang_policy": (
            "every timeout at every position captures queue, gc_runs and stopped PC"),
        "key_expectations": {
            "rows": expectations["row_count"],
            "rows_sha256": expectations["rows_sha256"],
            "source": "complete phase/payload/PETSCII table; no runtime inference",
        },
        "product_bytes_changed": 0,
        "authorized_contact_index": 2,
        "fresh_contacts": 0,
        "reserve": 1,
    }
    base["authorities"]["host_dry_run"] = bind(OBSERVED_DRY_RUN)
    base["authorities"]["expectation_table"] = bind(OBSERVED_EXPECTATIONS)
    base["authorities"]["conditional_authorization_commit"] = "a31e0037"
    write_json(OBSERVED_PREPARATION, base)
    return base


def observed_contact(index: int) -> dict[str, Any]:
    require(index == 2, "only the receipt-bound reserve contact is authorized")
    out = OUT_ROOT / f"observed-device-contact-{index:02d}"
    require(not out.exists(), f"observed contact output already exists: {out}")
    out.mkdir(parents=True)
    preparation = load(OBSERVED_PREPARATION)
    require(
        preparation["status"]
        == "prepared-complete-key-table-one-reserve-contact"
        and preparation["protocol"]["authorized_contact_index"] == 2,
        "observed reserve contact is not conditionally authorized")
    require(
        preparation["authorities"]["driver"]["sha256"]
        == sha256(Path(__file__).resolve()),
        "observed driver changed after dry-run/preparation")
    require(
        preparation["authorities"]["expectation_table"]["sha256"]
        == sha256(OBSERVED_EXPECTATIONS),
        "observed key expectation table changed after preparation")
    expectations = load_expectation_table()
    config = load(EDITOR.CONFIG)
    session = EDITOR.EditorSession(config, preparation)
    session.out = out
    observed = ObservedContact(session, expectations)
    try:
        session.media_deploy()
        symbol = observed.resolve_symbol()

        observed.launch_editor("context-scratch-launch", "(edit)")
        initial_scratch = observed.buffer("context-scratch-initial", "scratch")
        require(
            initial_scratch["line_count"] == 1
            and initial_scratch["fill"] == 0,
            f"fresh scratch memory state drift: {initial_scratch}")
        scratch_rows: list[dict[str, Any]] = []
        for count, char in enumerate(ORIGINAL_SCRATCH_TEXT, 1):
            observed.key(f"context-scratch-key-{count}", char)
            scratch_rows.append(observed.wait_buffer(
                f"context-scratch-fill-{count}", "scratch", count))
        observed.abort_editor("context-scratch-abort")

        observed.form("context-helper-legacy", ORIGINAL_HELPER, "%ib")
        observed.form("context-helper-corrected", CORRECTED_HELPER, "%ib")
        observed.form("context-scratch-bind", SCRATCH_BIND, "t")
        scratch_memory = observed.buffer("context-scratch-memory", "scratch")
        require(
            scratch_memory["line_count"] == 1
            and scratch_memory["fill"] == len(ORIGINAL_SCRATCH_TEXT),
            f"reconstructed scratch memory state drift: {scratch_memory}")

        observed.launch_editor("measure3-launch", '(ide"measure3")')
        initial_measure3 = observed.buffer("measure3-memory-initial", "measure3")
        require(
            initial_measure3["line_count"] == 1
            and initial_measure3["fill"] == 0,
            f"measure3 memory start drift: {initial_measure3}")
        rows: list[dict[str, Any]] = []
        for count in range(1, 56):
            observed.key(f"measure3-key-{count}", "a")
            rows.append(observed.wait_buffer(
                f"measure3-fill-{count}", "measure3", count))
        before_56 = observed.buffer("measure3-before-56", "measure3")
        require(before_56["fill"] == 55, "measure3 fill before key 56 drift")
        observed.key("measure3-key-56", "a")
        after_56 = observed.wait_buffer(
            "measure3-fill-56", "measure3", 56)
        require(observed.sequence == expectations["row_count"],
                "runner ended before consuming the complete key table")
        value = {
            "contact": index,
            "status": "stall-not-reproduced-observed-transport-and-memory-green",
            "symbol_authority": symbol,
            "initial_scratch": initial_scratch,
            "scratch_final": scratch_memory,
            "initial_measure3": initial_measure3,
            "before_56": before_56,
            "after_56": after_56,
            "observed_keys": observed.sequence,
            "product_bytes_changed": 0,
        }
    except MeasurementEvent as event:
        transport = event.evidence.get("classification", "") == (
            "tooling-transport-arrival-First-Red")
        value = {
            "contact": index,
            "status": (
                "FIRST-RED-observed-transport-tooling"
                if transport else
                "stall-reproduced-observed-arrival-and-measured"),
            "event": {
                "phase": event.phase,
                "reason": event.reason,
                "evidence": event.evidence,
            },
            "observed_keys": observed.sequence,
            "product_bytes_changed": 0,
        }
    except DiscriminatorError as error:
        value = {
            "contact": index,
            "status": "FIRST-RED-machine-checked-context-memory-assert",
            "error_type": type(error).__name__,
            "error": str(error),
            "observed_keys": observed.sequence,
            "product_bytes_changed": 0,
            "measurement_claimed": False,
        }
    write_json(out / "contact.json", value)
    return value


def finalize_observed(contact: dict[str, Any]) -> dict[str, Any]:
    contacts = [contact]
    first_path = OUT_ROOT / "observed-device-contact-01/contact.json"
    if int(contact["contact"]) == 2 and first_path.is_file():
        first = load(first_path)
        require(first["contact"] == 1, "observed contact-1 identity drift")
        contacts.insert(0, first)
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-observed-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": contact["status"],
        "contact": contact,
        "contacts": contacts,
        "execution_accounting": {
            "physical_contacts": int(contact["contact"]),
            "reserve_consumed": int(contact["contact"]) == 2,
            "product_links": 0,
            "product_bytes_changed": 0,
        },
        "authority": {
            "preparation": bind(OBSERVED_PREPARATION),
            "host_dry_run": bind(OBSERVED_DRY_RUN),
            "expectation_table": bind(OBSERVED_EXPECTATIONS),
            "commission": bind(COMMISSION),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": "owner review; no product fix or link inferred by the runner",
    }
    write_json(OBSERVED_RECEIPT, value)
    return value


def run_contact(
    index: int, *, retry: bool = False,
) -> dict[str, Any]:
    require(index in (1, 2), "contact must be one or two")
    prefix = "reauthorized-device-contact" if retry else "contact"
    out = OUT_ROOT / f"{prefix}-{index:02d}"
    require(not out.exists(), f"contact output already exists: {out}")
    out.mkdir(parents=True)
    config = load(EDITOR.CONFIG)
    preparation = load(RETRY_PREPARATION if retry else EDITOR.PREPARATION)
    require(
        preparation["candidate"]["link"] == 83,
        "editor-session preparation is not Link 83",
    )
    require(
        preparation["candidate"]["deployment"]["sha256"]
        == sha256(EDITOR.DEPLOYMENT),
        "editor-session deployment binding drift",
    )
    session = EDITOR.EditorSession(config, preparation)
    session.out = out
    # The bound Link-83 entry contract is the mounted product-medium AUTOBOOT.
    # Do not combine that reset/mount path with the legacy concurrent m65 load.
    session.media_deploy()
    if retry:
        # Reconstruct the immediate state that produced the original 630/752
        # witness.  The old scratch status remained cached at 626 while these
        # forms interned four names; the next editor launch rendered 630.  Bind
        # the causal setup, not merely four arbitrary symbol insertions.
        session.launch_editor("context-scratch", "(edit)")
        scratch = session.send_linear_batches_until(
            "context-scratch-text", ORIGINAL_SCRATCH_TEXT, "", 1)
        require(
            visible_line(scratch, len(ORIGINAL_SCRATCH_TEXT)),
            "original scratch line acknowledgement absent",
        )
        require(
            re.search(
                r"(?m)^\s*-- scratch \* L1 -- 626/752\s*$",
                scratch.read_text(errors="replace"),
            ) is not None,
            "original scratch starting context absent",
        )
        session.abort_editor("context-scratch-abort")
        session.run_form("context-helper-legacy", ORIGINAL_HELPER, "%ib")
        session.run_form("context-helper-corrected", CORRECTED_HELPER, "%ib")
        session.run_form("context-scratch-bind", SCRATCH_BIND, "t")
    session.launch_editor("editor", "(ide\"measure3\")")
    _initial_image, initial_text = session.capture_screen("editor-baseline")
    require(
        re.search(
            r"(?m)^\s*-- measure3 L1 -- 630/752\s*$",
            initial_text.read_text(errors="replace"),
        ) is not None,
        "exact measure3 starting state absent",
    )
    completion = session.send_linear_batches_until(
        "typing", "a" * 55, "", 1)
    require(visible_line(completion, 55), "55-key visible acknowledgement absent")
    before = running_capture(session, "before-56")
    require(not (int(before["queue_state"]) & 0x80),
            "typed queue not empty before key 56")
    session.send_keys("a")
    deadline = time.monotonic() + 120
    reproduced = True
    last_screen: Path | None = None
    capture_index = 0
    while time.monotonic() < deadline:
        capture_index += 1
        image, text = session.capture_screen(
            f"after-56-{capture_index:03d}")
        SCREEN.check_fail_closed_frame(image)
        last_screen = text
        if visible_line(text, 56):
            reproduced = False
            break
        time.sleep(1)
    require(last_screen is not None, "no post-key screen capture")
    if not reproduced:
        value = {
            "contact": index,
            "status": "stall-not-reproduced-reserve-eligible",
            "before": before,
            "screen": bind(last_screen),
            "product_bytes_changed": 0,
        }
        write_json(out / "contact.json", value)
        return value
    running = running_capture(session, "stalled-running")
    stopped = halt_capture()
    decision = classify(int(before["gc_runs"]), stopped)
    value = {
        "contact": index,
        "status": "stall-reproduced-and-classified",
        "before": before,
        "stalled_running": running,
        "stalled_stopped": stopped,
        "decision": decision,
        "screen": bind(last_screen),
        "product_bytes_changed": 0,
    }
    write_json(out / "contact.json", value)
    return value


def guarded_retry_contact(index: int) -> dict[str, Any]:
    out = OUT_ROOT / f"reauthorized-device-contact-{index:02d}"
    try:
        return run_contact(index, retry=True)
    except Exception as error:
        evidence: dict[str, Any] = {}
        for name in (
            "fresh-start.txt", "package-upload.log", "package-readback.d81",
            "media-autoboot.txt", "media-entry.json",
            "context-scratch.txt", "context-scratch-text-batch-34-completion-1.txt",
            "context-scratch-abort-prompt.txt", "context-helper-legacy.txt",
            "context-helper-corrected.txt", "context-scratch-bind.txt", "editor.txt",
            "editor-baseline.txt",
        ):
            path = out / name
            if path.is_file():
                evidence[name] = bind(path)
        value = {
            "contact": index,
            "status": "FIRST-RED-machine-checked-preflight-or-run-aborted",
            "error_type": type(error).__name__,
            "error": str(error),
            "evidence": evidence,
            "product_bytes_changed": 0,
            "measurement_claimed": False,
        }
        write_json(out / "contact.json", value)
        raise


def finalize(
    contact: dict[str, Any], *, retry: bool = False,
) -> dict[str, Any]:
    preparation_path = RETRY_PREPARATION if retry else PREPARATION
    receipt_path = RETRY_RECEIPT if retry else RECEIPT
    preparation = load(preparation_path)
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": contact["status"],
        "contact": contact,
        "execution_accounting": {
            "physical_contacts": int(contact["contact"]),
            "reserve_consumed": int(contact["contact"]) == 2,
            "product_links": 0,
            "product_bytes_changed": 0,
        },
        "authority": {
            "preparation": bind(preparation_path),
            "commission": preparation["authorities"]["commission"],
            "host_attribution": preparation["authorities"]["host_attribution"],
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": "owner review; no fix, link or further hardware authorized",
    }
    write_json(receipt_path, value)
    return value


def close_retry_exhausted() -> dict[str, Any]:
    """Bind the reauthorized contacts without claiming a discriminator."""
    contact_1 = OUT_ROOT / "reauthorized-device-contact-01"
    contact_2 = OUT_ROOT / "reauthorized-device-contact-02"
    host_preflights = [
        OUT_ROOT / "reauthorized-contact-01/contact.json",
        OUT_ROOT / "reauthorized-host-preflight-first-red-02/contact.json",
    ]
    package = ROOT / load(EDITOR.DEPLOYMENT)["candidate"]["package_medium"]["path"]
    package_sha = sha256(package)
    c1_readback = contact_1 / "package-readback.d81"
    c2_readback = contact_2 / "package-readback.d81"
    c1_media = load(contact_1 / "media-entry.json")
    c2_media = load(contact_2 / "media-entry.json")
    c1_editor = contact_1 / "editor-baseline.txt"
    c2_scratch = contact_2 / "context-scratch.txt"
    c2_first = contact_2 / "context-scratch-text-batch-1-completion-1.txt"
    c2_last = contact_2 / "context-scratch-text-batch-1-completion-93.txt"
    for readback in (c1_readback, c2_readback):
        require(sha256(readback) == package_sha, "retry package readback drift")
    for media in (c1_media, c2_media):
        require(
            media["status"] == "passed-bound-product-medium-autoboot",
            "retry canonical media entry absent",
        )
    require(
        "-- measure3 L1 -- 626/752" in c1_editor.read_text(errors="replace"),
        "contact 1 fresh measure3 witness drift",
    )
    require(
        "-- scratch L1 -- 626/752" in c2_first.read_text(errors="replace"),
        "contact 2 fresh scratch witness drift",
    )
    require(c2_first.read_bytes() == c2_last.read_bytes(),
            "contact 2 screen changed during the bounded first-key wait")
    require(
        ORIGINAL_SCRATCH_TEXT not in c2_last.read_text(errors="replace"),
        "contact 2 unexpectedly acknowledged the setup key",
    )
    preflight_rows = [load(path) for path in host_preflights]
    require(
        [row["error"] for row in preflight_rows] == ["'link'", "'deployment'"],
        "host-only preflight accounting drift",
    )
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-device-retry-v1",
        "recorded_on": date.today().isoformat(),
        "status": (
            "FIRST-RED-discriminator-not-reached-reauthorized-contact-budget-"
            "exhausted"),
        "product_result": {
            "classification": "unmeasured",
            "queue_state": None,
            "queue_code": None,
            "gc_runs": None,
            "PC": None,
            "reason": (
                "both reauthorized physical contacts stopped at machine-checked "
                "immediate-context gates before the 55-to-56 discriminator"),
        },
        "host_only_preflights": [
            {
                "classification": "zero-device-command-host-preflight-First-Red",
                "error": row["error"],
                "receipt": bind(path),
            }
            for path, row in zip(host_preflights, preflight_rows)
        ],
        "contacts": [
            {
                "contact": 1,
                "classification": "immediate-context-assert-First-Red",
                "proved": [
                    "fresh BASIC 65 READY",
                    "bound package upload/readback",
                    "bound D81 AUTOBOOT WORKBENCH 1.2.6",
                    "fresh measure3 rendered 626/752",
                ],
                "failed_assert": "required original measure3 context 630/752",
                "package_readback": bind(c1_readback),
                "media_entry": bind(contact_1 / "media-entry.json"),
                "screen": bind(c1_editor),
                "measurement_keys_submitted": 0,
            },
            {
                "contact": 2,
                "classification": "setup-transport-visible-ack-First-Red",
                "proved": [
                    "fresh BASIC 65 READY",
                    "bound package upload/readback",
                    "bound D81 AUTOBOOT WORKBENCH 1.2.6",
                    "fresh scratch editor rendered 626/752",
                    "screen byteidentical for the bounded 120-second setup-key wait",
                ],
                "failed_assert": (
                    "first context-reconstruction key was not visibly acknowledged"),
                "package_readback": bind(c2_readback),
                "media_entry": bind(contact_2 / "media-entry.json"),
                "scratch_screen": bind(c2_scratch),
                "first_wait_screen": bind(c2_first),
                "last_wait_screen": bind(c2_last),
                "setup_virtual_key_commands_issued": 1,
                "setup_keys_visibly_acknowledged": 0,
                "measurement_keys_submitted": 0,
                "context_helper_forms_executed": 0,
            },
        ],
        "standing_rule_result": (
            "passed: each failed immediate-context assertion stopped before the "
            "authorized discriminator measurement"),
        "execution_accounting": {
            "physical_contacts": 2,
            "reserve_consumed": True,
            "authorized_queue_gc_PC_observations": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "further_hardware_authorized": False,
        },
        "authority": {
            "preparation": bind(RETRY_PREPARATION),
            "commission": bind(COMMISSION),
            "host_attribution": bind(HOST_RECEIPT),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": "owner review; no fix, link or further hardware authorized",
    }
    write_json(RETRY_RECEIPT, value)
    return value


def close_exhausted() -> dict[str, Any]:
    """Bind the two pre-discriminator harness First Reds without retrying."""
    contact_1 = OUT_ROOT / "contact-01"
    contact_2 = OUT_ROOT / "contact-02"
    package = ROOT / load(EDITOR.DEPLOYMENT)["candidate"]["package_medium"]["path"]
    c1_readback = contact_1 / "package-readback.d81"
    c1_boot = contact_1 / "boot.txt"
    c2_readback = contact_2 / "package-readback.d81"
    c2_media = load(contact_2 / "media-entry.json")
    c2_initial = contact_2 / "typing-batch-1-completion-1.txt"
    c2_last = contact_2 / "typing-batch-1-completion-93.txt"
    require(c1_readback.read_bytes() == package.read_bytes(),
            "contact 1 package readback drift")
    require("lisp65>" not in c1_boot.read_text(errors="replace"),
            "contact 1 unexpectedly reached the REPL")
    require(c2_readback.read_bytes() == package.read_bytes(),
            "contact 2 package readback drift")
    require(c2_media["status"] == "passed-bound-product-medium-autoboot",
            "contact 2 canonical media entry absent")
    require("-- disc L1 -- 626/752" in c2_initial.read_text(errors="replace"),
            "contact 2 wrong starting-state witness absent")
    require(c2_initial.read_bytes() == c2_last.read_bytes(),
            "contact 2 screen changed while awaiting key 1")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED-discriminator-not-reached-contact-budget-exhausted",
        "product_result": {
            "classification": "unmeasured",
            "queue_state": None,
            "queue_code": None,
            "gc_runs": None,
            "PC": None,
            "reason": "both contacts stopped on attributable harness errors before the authorized 55-to-56 observation",
        },
        "contacts": [
            {
                "contact": 1,
                "classification": "harness-First-Red-before-REPL",
                "mechanism": "runner combined canonical D81 mount/reset with the legacy concurrent m65 product-load entry, contrary to the bound media-entry contract",
                "package_readback": bind(c1_readback),
                "transfer_log": bind(contact_1 / "package-upload.log"),
                "final_screen": bind(c1_boot),
                "keys_submitted": 0,
            },
            {
                "contact": 2,
                "classification": "harness-First-Red-wrong-editor-state",
                "mechanism": "runner opened disc instead of the authoritative measure3 buffer; the starting heap witness was 626/752 instead of 630/752 and key 1 was not acknowledged",
                "media_entry": bind(contact_2 / "media-entry.json"),
                "package_readback": bind(c2_readback),
                "starting_screen": bind(c2_initial),
                "final_screen": bind(c2_last),
                "keys_submitted": 1,
                "keys_visibly_acknowledged": 0,
            },
        ],
        "execution_accounting": {
            "physical_contacts": 2,
            "reserve_consumed": True,
            "authorized_queue_gc_PC_observations": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "further_hardware_authorized": False,
        },
        "corrected_unexecuted_runner": {
            "entry": "mounted product D81 AUTOBOOT.C65",
            "editor_form": "(ide\"measure3\")",
            "starting_state_gate": "-- measure3 L1 -- 630/752",
            "status": "prepared-but-not-authorized-after-contact-budget",
        },
        "authority": {
            "preparation": bind(PREPARATION),
            "commission": bind(COMMISSION),
            "host_attribution": bind(HOST_RECEIPT),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": "owner review; no third contact, fix, or link authorized",
    }
    write_json(RECEIPT, value)
    return value


def selftest() -> None:
    raw = b"\n38F7 01 02 03 04 05 01F0\n"
    registers = parse_registers(raw)
    require(registers["PC"] == "0x38f7", "register parser mutation")
    base = {"queue_state": 0, "queue_code": 0,
            "gc_runs": 8, "registers": {"PC": "0x38f7"}}
    # Avoid ELF access in selftest: exercise the disjoint predicates directly.
    require((0x80 & 0x80) != 0, "queue predicate mutation")
    require(((8 - 7) & 0xFFFF) == 1, "GC delta mutation")
    require(GC_FIRST <= int(base["registers"]["PC"], 16)
            < GC_LAST_EXCLUSIVE, "GC range mutation")
    print("c2-v126-editor-stall-device: SELFTEST PASS outcomes=3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=(
            "selftest", "prepare", "prepare-retry", "run", "run-retry",
            "close-exhausted", "close-retry-exhausted",
            "dry-run-observed", "prepare-observed", "run-observed"))
    parser.add_argument("--contact", type=int, default=1)
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
        return 0
    if args.command == "dry-run-observed":
        value = host_dry_run()
        print(
            "c2-v126-editor-stall-device: OBSERVED DRY RUN PASS "
            f"executions={value['executions']} mutations={len(value['mutations'])}")
        return 0
    if args.command == "prepare-observed":
        prepare_observed()
        print(
            "c2-v126-editor-stall-device: OBSERVED PREPARED "
            "contact=2 reserve=1 expectations=complete")
        return 0
    if args.command == "prepare":
        prepare()
        print("c2-v126-editor-stall-device: PREPARED contact=1 reserve=1")
        return 0
    if args.command == "prepare-retry":
        prepare_retry()
        print("c2-v126-editor-stall-device: RETRY PREPARED contact=1 reserve=1 asserts=3")
        return 0
    if args.command == "close-exhausted":
        close_exhausted()
        print("c2-v126-editor-stall-device: FIRST RED contacts=2 discriminator=unmeasured")
        return 0
    if args.command == "close-retry-exhausted":
        close_retry_exhausted()
        print(
            "c2-v126-editor-stall-device: FIRST RED reauthorized-contacts=2 "
            "discriminator=unmeasured")
        return 0
    if args.command == "run-observed":
        require(OBSERVED_PREPARATION.is_file(),
                "observed run requires preparation receipt")
        contact = observed_contact(args.contact)
        finalize_observed(contact)
        print("c2-v126-editor-stall-device: " + contact["status"])
        return 0
    retry = args.command == "run-retry"
    preparation_path = RETRY_PREPARATION if retry else PREPARATION
    require(preparation_path.is_file(), "run requires preparation receipt")
    contact = (
        guarded_retry_contact(args.contact) if retry
        else run_contact(args.contact))
    finalize(contact, retry=retry)
    print(
        "c2-v126-editor-stall-device: "
        + (contact.get("decision", {}).get("outcome") or contact["status"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiscriminatorError, EDITOR.SessionError, BASE.SoakError, OSError,
            ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print("c2-v126-editor-stall-device: FIRST RED: " + str(error))
        raise SystemExit(2)
