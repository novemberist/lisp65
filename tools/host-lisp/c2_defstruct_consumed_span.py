#!/usr/bin/env python3
"""Prepare and close the final defstruct consumed-span evidence row.

The terminal refill witness already identifies the only two payload spans on
the direct escape chain: ordinal 656 at payload PC 29 (three bytes), followed
by ordinal 696 at payload PC 10 (sixteen bytes).  The old witness retained
only their first opcode.  This non-promotable runtime delta keeps the existing
last-two identity ring and snapshots every byte of those two spans after the
refill and before dispatch.  A stopped-state replay then compares the bytes to
the captured C2D/Bank-2 source planes; completion metadata is never an oracle.

No product or medium byte is changed.  The patch is installed after ``require``
and before the measured ``defstruct`` form, in already enumerated diagnostic
arenas.  The first device preflight rejected the no-longer-matching historical
stopped state before any memory read; a deterministic reproduction is needed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORIZATION_COMMIT = "952ae756"
PLAN = "docs/planning/post-v1.4.0-direction-plan.md"
COVERAGE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-f018b-coverage-receipt.json")
SISTER = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json")
TERMINAL_DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-device-receipt.json")
PHASE_B = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
BASE = ROOT / "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts"
PRG = BASE / "diagnostic-terminal-ingress.prg"
ELF = BASE / "diagnostic-terminal-ingress.elf"
MEDIUM = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/"
    "diagnostic-terminal-ingress-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5-split/"
    "defstruct-acceptance/lisp65-library.d81")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RUNNER = ROOT / "scripts/c2-defstruct-consumed-span-hw.sh"

OUT = ROOT / "build/c2.3/defstruct-consumed-span-closing"
ART = OUT / "artifacts"
CODE0_PATCH = ART / "terminal-and-span-capture.bin"
CODE1_PATCH = ART / "refill-capture-call.bin"
DISPATCH_RESTORE = ART / "dispatch-restore.bin"
SPAN_RESET = ART / "consumed-span-reset.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-consumed-span-preparation-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-consumed-span-result-receipt.json")

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-consumed-span-preparation-v1"
RESULT_FORMAT = "lisp65-c2.3-post-v1.4-defstruct-consumed-span-result-v1"
RECORDED_ON = "2026-08-10"
PRG_LOAD = 0x2001

VM_DISPATCH_HOOK = 0x467D
CODE0 = 0xB3B0
CAPTURE = 0xB3C0
REFILL_HOOK = 0xB44A
CODE1_CALL = 0xC038
SPAN_RECORD = 0xB582
SPAN_RECORD_BYTES = 66
C2D_ENTRIES_OFFSET = 2096
C2D_ENTRY_BYTES = 10
C2_CODE_HEADER_SCALAR_BYTES = 7
VM_BUF_OFF = 0xB9B2
VM_BUF_BANK = 0xBFD8
VMR_CODE = 0xBFDD
VMR_WIN = 0xBFE5
VMR_WINLEN = 0xBFE7

PRIOR_SLOT = 0
LAST_SLOT = 16
TAG = 0
BANK = 1
OWNER = 2
WINDOW = 4
LENGTH = 6
ACTUAL = 8
PRIOR_ACTUAL_BYTES = 3
LAST_ACTUAL_BYTES = 16
PRIOR_SENTINEL = 0xD0
LAST_SENTINEL = 0xD1
PRIOR_COMMIT = 0xA1
LAST_COMMIT = 0xA2

EXPECTED_HISTORICAL_TUPLE = {
    "PC": "0xB42C", "SP": "0x018D", "X": "0x8D",
    "MAPH": "0x8000", "MAPL": "0x0000",
}
REJECTED_LIVE_TUPLE = {
    "PC": "0xE193", "SP": "0x01EE", "X": "0x00",
    "MAPH": "0xB300", "MAPL": "0xE300",
}
EXPECTED_FINAL_TUPLE = {
    "PC": "0xB3B9", "SP": "0x018D", "MAPH": "0x8000", "MAPL": "0x0000",
}
EXPECTED_RESULT_BINDINGS = {
    "registers": {
        "path": "build/c2.3/defstruct-consumed-span-closing/device/final-registers.json",
        "bytes": 785,
        "sha256": "f22c858a88067a7e35d0e0d4e80e33a8115485def676c2862c5875dc0dfae526",
    },
    "span_capture": {
        "path": "build/c2.3/defstruct-consumed-span-closing/device/consumed-spans.bin",
        "bytes": 66,
        "sha256": "050777c14264808733ad2cbbd8a81cc5bb9380338d5a0e23176815f0360d67cb",
    },
    "terminal_ring": {
        "path": "build/c2.3/defstruct-consumed-span-closing/device/terminal-ring.bin",
        "bytes": 65,
        "sha256": "27cd03c57dfa0c6cdafbe62b5c3e52e772d43de69e7dfead6e1586325591053e",
    },
    "Bank_2": {
        "path": "build/c2.3/defstruct-consumed-span-closing/device/bank2-source.bin",
        "bytes": 65536,
        "sha256": "c8036f2ef7713f7f06dfd7e471953c15d5d1b59f8d158b82e948d5e1377e141c",
    },
    "C2D": {
        "path": "build/c2.3/defstruct-consumed-span-closing/device/c2d-reset-domain.bin",
        "bytes": 50816,
        "sha256": "67de7e15bf2923c70d4f5292b06f5bb0b5d138c6cce35be8d6ab175251766f13",
    },
}


class SpanError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SpanError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(path, canonical(value))


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def u16_at(raw: bytes, at: int) -> int:
    require(0 <= at <= len(raw) - 2, "u16 outside artifact")
    return int.from_bytes(raw[at:at + 2], "little")


class Asm:
    def __init__(self, origin: int):
        self.origin = origin
        self.raw = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.raw)

    def emit(self, *values: int) -> None:
        self.raw.extend(values)

    def absolute(self, opcode: int, address: int) -> None:
        self.emit(opcode, address & 0xFF, address >> 8)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.pc

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.raw) - 1, label))

    def finish(self) -> bytes:
        for offset, label in self.fixups:
            require(label in self.labels, f"missing label: {label}")
            after = self.origin + offset + 1
            delta = self.labels[label] - after
            require(-128 <= delta <= 127, f"branch out of range: {label}")
            self.raw[offset] = delta & 0xFF
        return bytes(self.raw)


def source_spans() -> list[dict[str, Any]]:
    device = load(TERMINAL_DEVICE)
    capsules = device["backing_planes"]["source_capsules"]
    decoded = device["record"]["decoded"]
    require(len(capsules) == 2, "terminal source-capsule cardinality drift")
    rows = []
    for prefix, capsule in zip(("previous-fill", "last-fill"), capsules):
        entry = capsule["entry"]
        raw = bytes.fromhex(capsule["object_hex"])
        require(len(raw) == entry["code_length"]
                and digest(raw) == capsule["object_sha256"],
                f"{prefix} source object drift")
        cursor = decoded[f"{prefix}.cursor"]["value_le"]
        window = decoded[f"{prefix}.window-base"]["value_le"]
        owner_raw = bytes.fromhex(decoded[f"{prefix}.owner"]["value_hex"])
        owner = int.from_bytes(owner_raw[1:], "little")
        header = 7 + 2 * entry["literal_count"]
        payload = raw[header:]
        require(owner_raw[0] == 1 and owner == entry["ordinal"]
                and cursor == window and cursor < len(payload),
                f"{prefix} identity drift")
        consumed = payload[cursor:]
        rows.append({
            "name": prefix, "owner_bank": owner_raw[0], "owner_ordinal": owner,
            "window_base": window, "consumed_bytes": len(consumed),
            "source_hex": consumed.hex(), "source_sha256": digest(consumed),
            "object_sha256": capsule["object_sha256"],
            "image_slot": entry["image_slot"],
            "literal_count": entry["literal_count"],
            "code_offset": entry["code_offset"],
            "code_length": entry["code_length"],
            "resolution_base": entry["resolution_base"],
            "generation": entry["generation"],
            "object_header_bytes": header, "object_payload_bytes": len(payload),
        })
    require([(row["owner_ordinal"], row["window_base"],
              row["consumed_bytes"], row["source_hex"]) for row in rows] == [
        (656, 29, 3, "3e0204"),
        (696, 10, 16, "0c0d3538030101023e01040b38033305"),
    ], "closing consumed-span authority drift")
    return rows


def span_reset() -> bytes:
    rows = source_spans()
    raw = bytearray((0xCD,)) * SPAN_RECORD_BYTES
    for start, sentinel, row, size in (
        (PRIOR_SLOT, PRIOR_SENTINEL, rows[0], PRIOR_ACTUAL_BYTES),
        (LAST_SLOT, LAST_SENTINEL, rows[1], LAST_ACTUAL_BYTES),
    ):
        require(row["consumed_bytes"] == size, "slot/source geometry drift")
        raw[start + TAG] = sentinel
        raw[start + BANK] = row["owner_bank"]
        raw[start + OWNER:start + OWNER + 2] = u16(row["owner_ordinal"])
        raw[start + WINDOW:start + WINDOW + 2] = u16(row["window_base"])
        raw[start + LENGTH:start + LENGTH + 2] = u16(size)
        raw[start + ACTUAL:start + ACTUAL + size] = bytes((0xCC,)) * size
    return bytes(raw)


def capture_routine() -> bytes:
    """Return the post-refill/pre-dispatch snapshot routine at $B3C0."""
    a = Asm(CAPTURE)
    a.absolute(0xAD, VM_BUF_BANK); a.emit(0xC9, 1); a.branch(0xD0, "done")
    a.absolute(0xAD, VM_BUF_OFF + 1); a.emit(0xC9, 2); a.branch(0xD0, "done")
    a.absolute(0xAD, VM_BUF_OFF); a.emit(0xC9, 0x90); a.branch(0xF0, "prior")
    a.emit(0xC9, 0xB8); a.branch(0xD0, "done")

    for address, expected in ((VMR_WIN, 10), (VMR_WIN + 1, 0),
                              (VMR_WINLEN, 16), (VMR_WINLEN + 1, 0)):
        a.absolute(0xAD, address)
        if expected:
            a.emit(0xC9, expected)
        a.branch(0xD0, "done")
    a.absolute(0x9C, SPAN_RECORD + LAST_SLOT + TAG)
    a.absolute(0xAD, VMR_CODE); a.emit(0x85, 0x04)
    a.absolute(0xAD, VMR_CODE + 1); a.emit(0x85, 0x05)
    a.emit(0xA0, 0)
    a.label("last-loop")
    a.emit(0xB1, 0x04)
    a.absolute(0x99, SPAN_RECORD + LAST_SLOT + ACTUAL)
    a.emit(0xC8, 0xC0, LAST_ACTUAL_BYTES)
    a.branch(0xD0, "last-loop")
    a.emit(0xA9, LAST_COMMIT); a.absolute(0x8D, SPAN_RECORD + LAST_SLOT + TAG)
    a.emit(0x60)

    a.label("prior")
    for address, expected in ((VMR_WIN, 29), (VMR_WIN + 1, 0),
                              (VMR_WINLEN, 3), (VMR_WINLEN + 1, 0)):
        a.absolute(0xAD, address)
        if expected:
            a.emit(0xC9, expected)
        a.branch(0xD0, "done")
    a.absolute(0x9C, SPAN_RECORD + PRIOR_SLOT + TAG)
    a.absolute(0xAD, VMR_CODE); a.emit(0x85, 0x04)
    a.absolute(0xAD, VMR_CODE + 1); a.emit(0x85, 0x05)
    a.emit(0xA0, 0)
    a.label("prior-loop")
    a.emit(0xB1, 0x04)
    a.absolute(0x99, SPAN_RECORD + PRIOR_SLOT + ACTUAL)
    a.emit(0xC8, 0xC0, PRIOR_ACTUAL_BYTES)
    a.branch(0xD0, "prior-loop")
    a.emit(0xA9, PRIOR_COMMIT); a.absolute(0x8D, SPAN_RECORD + PRIOR_SLOT + TAG)
    a.label("done")
    a.emit(0x60)
    result = a.finish()
    require(len(result) <= REFILL_HOOK - CAPTURE,
            f"capture routine exceeds terminal arena: {len(result)}")
    return result


def code0_patch() -> bytes:
    raw = bytearray()
    raw.extend((0x78,))                         # SEI
    raw.extend((0x9C, 0x1A, 0xD0))             # STZ $D01A
    raw.extend((0xA9, 0x02, 0x8D, 0x20, 0xD0)) # red border
    raw.extend((0x4C, 0xB9, 0xB3))             # JMP $B3B9
    raw.extend((0xEA,) * (CAPTURE - CODE0 - len(raw)))
    raw.extend(capture_routine())
    raw.extend((0xEA,) * (REFILL_HOOK - CODE0 - len(raw)))
    require(len(raw) == REFILL_HOOK - CODE0, "code0 patch geometry drift")
    return bytes(raw)


def code1_patch() -> bytes:
    return bytes((0x20, CAPTURE & 0xFF, CAPTURE >> 8, 0x60))


def dispatch_restore() -> bytes:
    return bytes.fromhex("aeeabf")              # displaced LDX vm_run_inner.poll_


def validate_base() -> dict[str, Any]:
    sister = load(SISTER)
    require(sister["identity"]["diagnostic_PRG"] == bind(PRG)
            and sister["identity"]["diagnostic_ELF"] == bind(ELF)
            and sister["identity"]["diagnostic_medium"] == bind(MEDIUM)
            and sister["identity"]["library_medium"] == bind(LIBRARY),
            "diagnostic sister identity drift")
    prg = PRG.read_bytes()
    require(int.from_bytes(prg[:2], "little") == PRG_LOAD, "PRG load drift")
    require(prg[prg_offset(VM_DISPATCH_HOOK):prg_offset(VM_DISPATCH_HOOK) + 3]
            == bytes.fromhex("2082b5"), "dispatch producer hook drift")
    require(prg[prg_offset(CODE1_CALL):prg_offset(CODE1_CALL) + 4]
            == bytes.fromhex("60eaeaea"), "refill continuation tail drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(truth.symbol("vm_codebuf").value == 0xBFA0
            and truth.symbol("vm_codebuf").bytes == 56
            and truth.symbol("vmr_code").value == VMR_CODE
            and truth.symbol("vmr_win").value == VMR_WIN
            and truth.symbol("vmr_winlen").value == VMR_WINLEN,
            "linked VM window geometry drift")
    return {"sister": sister, "PRG": prg, "truth": truth}


def patch_rows() -> list[dict[str, Any]]:
    base = validate_base()["PRG"]
    rows = []
    for address, after, label in (
        (VM_DISPATCH_HOOK, dispatch_restore(), "retire-dispatch-progress-producer"),
        (CODE0, code0_patch(), "terminal-hold-and-consumed-span-capture"),
        (CODE1_CALL, code1_patch(), "post-refill-pre-dispatch-capture-call"),
        (SPAN_RECORD, span_reset(), "consumed-span-record-reset"),
    ):
        before = base[prg_offset(address):prg_offset(address) + len(after)]
        require(len(before) == len(after), f"patch outside PRG: {label}")
        rows.append({"name": label, "address": f"0x{address:04X}",
                     "bytes": len(after), "before": before.hex(),
                     "after": after.hex()})
    return rows


def runner_contract() -> dict[str, Any]:
    source = RUNNER.read_text(encoding="utf-8")
    capture = source.split('if [ "$ACTION" = capture ]; then', 1)[1]
    order = [capture.index(token) for token in (
        "stop_once",
        "TUPLE-BEFORE-MEMORY",
        'readback 0x0000b582 66',
        'readback 0x0000c03f 65',
        'readback 0x00020000 65536',
        'readback 0x00050000 50816',
        'python3 "$PY" result-record',
    )]
    require(order == sorted(order),
            "runner does not bind tuple before closing memory reads")
    require(capture.count("readback ") == 4
            and "run_m65 -r" not in capture
            and "screen " not in capture,
            "closing capture read/resume discipline drift")
    arm = source.split('if [ "$ACTION" = arm-after-require ]; then', 1)[1].split(
        'if [ "$ACTION" = capture ]; then', 1)[0]
    require(arm.index("PRE-FORM-MONITOR-BEGIN") <
            arm.index('run_m65 -r') < arm.index("PRE-FORM-MONITOR-END")
            and arm.count('run_m65 -r') == 1,
            "pre-form patch/resume corridor drift")
    return {
        "tuple_before_first_memory_read": True,
        "post_stop_memory_reads": 4,
        "post_stop_resume_reset_RUN": 0,
        "pre_form_resume_count": 1,
    }


def decode_span(raw: bytes, start: int, *, sentinel: int, commit: int,
                source: dict[str, Any]) -> dict[str, Any]:
    size = source["consumed_bytes"]
    require(len(raw) == SPAN_RECORD_BYTES, "span record geometry drift")
    metadata = {
        "owner_bank": raw[start + BANK],
        "owner_ordinal": u16_at(raw, start + OWNER),
        "window_base": u16_at(raw, start + WINDOW),
        "consumed_bytes": u16_at(raw, start + LENGTH),
    }
    expected_metadata = {key: source[key] for key in metadata}
    require(metadata == expected_metadata, f"{source['name']} metadata drift")
    tag = raw[start + TAG]
    state = "committed" if tag == commit else "initial" if tag == sentinel else "invalid"
    actual = raw[start + ACTUAL:start + ACTUAL + size]
    return {"name": source["name"], "state": state, "tag": tag,
            **metadata, "actual_hex": actual.hex(),
            "source_hex": source["source_hex"],
            "first_difference": next((index for index, pair in enumerate(
                zip(actual, bytes.fromhex(source["source_hex"]), strict=True))
                if pair[0] != pair[1]), None)}


def captured_source_spans(device: Path,
                          authorities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct the source oracle from the same stopped-state capture."""
    bank2 = (device / "bank2-source.bin").read_bytes()
    c2d = (device / "c2d-reset-domain.bin").read_bytes()
    require(len(bank2) == 65536 and len(c2d) == 50816,
            "captured source-plane geometry drift")
    rows: list[dict[str, Any]] = []
    for authority in authorities:
        at = C2D_ENTRIES_OFFSET + authority["owner_ordinal"] * C2D_ENTRY_BYTES
        entry = c2d[at:at + C2D_ENTRY_BYTES]
        require(len(entry) == C2D_ENTRY_BYTES,
                f"{authority['name']} C2D row outside captured plane")
        captured = {
            "image_slot": entry[0], "literal_count": entry[1],
            "code_offset": u16_at(entry, 2), "code_length": u16_at(entry, 4),
            "resolution_base": u16_at(entry, 6), "generation": u16_at(entry, 8),
        }
        expected = {key: authority[key] for key in captured}
        require(captured == expected,
                f"{authority['name']} captured C2D identity drift")
        obj = bank2[captured["code_offset"]:
                    captured["code_offset"] + captured["code_length"]]
        header = C2_CODE_HEADER_SCALAR_BYTES + 2 * captured["literal_count"]
        require(len(obj) == captured["code_length"]
                and digest(obj) == authority["object_sha256"]
                and header == authority["object_header_bytes"],
                f"{authority['name']} captured Bank-2 object drift")
        payload = obj[header:]
        start = authority["window_base"]
        end = start + authority["consumed_bytes"]
        require(end == len(payload),
                f"{authority['name']} consumed-span end drift")
        source = payload[start:end]
        require(source.hex() == authority["source_hex"]
                and digest(source) == authority["source_sha256"],
                f"{authority['name']} captured source truth drift")
        rows.append({**authority, "source_hex": source.hex(),
                     "source_sha256": digest(source),
                     "captured_C2D_entry_hex": entry.hex(),
                     "captured_object_hex": obj.hex(),
                     "captured_object_sha256": digest(obj)})
    return rows


def emulate_capture(*, owner: int, window: int, payload: bytes,
                    length: int | None = None) -> bytes:
    body = capture_routine()
    memory: dict[int, int] = {}
    reset = span_reset()
    memory.update({SPAN_RECORD + i: value for i, value in enumerate(reset)})
    memory[VM_BUF_BANK] = 1
    memory[VM_BUF_OFF] = owner & 0xFF
    memory[VM_BUF_OFF + 1] = owner >> 8
    memory[VMR_WIN] = window & 0xFF
    memory[VMR_WIN + 1] = window >> 8
    observed_length = len(payload) if length is None else length
    memory[VMR_WINLEN] = observed_length & 0xFF
    memory[VMR_WINLEN + 1] = observed_length >> 8
    pointer = 0x7000
    memory[VMR_CODE] = pointer & 0xFF
    memory[VMR_CODE + 1] = pointer >> 8
    memory.update({pointer + i: value for i, value in enumerate(payload)})
    pc = 0; a = y = 0; zero = False; steps = 0
    while True:
        steps += 1
        require(steps < 300, "capture emulator did not return")
        op = body[pc]
        if op == 0xAD:                    # LDA abs
            address = body[pc + 1] | body[pc + 2] << 8
            a = memory.get(address, 0); zero = a == 0; pc += 3
        elif op == 0xC9:                  # CMP #imm
            zero = a == body[pc + 1]; pc += 2
        elif op in (0xD0, 0xF0):          # BNE/BEQ
            take = (not zero) if op == 0xD0 else zero
            delta = body[pc + 1]; delta = delta - 256 if delta & 0x80 else delta
            pc = pc + 2 + (delta if take else 0)
        elif op == 0x9C:                  # STZ abs
            address = body[pc + 1] | body[pc + 2] << 8
            memory[address] = 0; pc += 3
        elif op == 0x85:                  # STA zp
            memory[body[pc + 1]] = a; pc += 2
        elif op == 0xA0:                  # LDY #imm
            y = body[pc + 1]; zero = y == 0; pc += 2
        elif op == 0xB1:                  # LDA (zp),Y
            zp = body[pc + 1]
            address = memory.get(zp, 0) | memory.get(zp + 1, 0) << 8
            a = memory.get((address + y) & 0xFFFF, 0); zero = a == 0; pc += 2
        elif op == 0x99:                  # STA abs,Y
            address = body[pc + 1] | body[pc + 2] << 8
            memory[(address + y) & 0xFFFF] = a; pc += 3
        elif op == 0xC8:                  # INY
            y = (y + 1) & 0xFF; zero = y == 0; pc += 1
        elif op == 0xC0:                  # CPY #imm
            zero = y == body[pc + 1]; pc += 2
        elif op == 0xA9:                  # LDA #imm
            a = body[pc + 1]; zero = a == 0; pc += 2
        elif op == 0x8D:                  # STA abs
            address = body[pc + 1] | body[pc + 2] << 8
            memory[address] = a; pc += 3
        elif op == 0x60:                  # RTS
            break
        else:
            raise SpanError(f"unexpected capture opcode ${op:02X} at +{pc}")
    return bytes(memory.get(SPAN_RECORD + i, 0) for i in range(SPAN_RECORD_BYTES))


def derive(*, write_artifacts: bool) -> dict[str, Any]:
    base = validate_base()
    coverage = load(COVERAGE)
    require(coverage["decision"]["F018B_membership_for_active_load"] == "REFUTED"
            and coverage["decision"]["F018B_membership_for_any_earlier_partial_tail"]
            == "UNPROVEN"
            and coverage["specified_final_evidence_row"]["authorized_by_this_result"]
            is False, "coverage authority drift")
    authorization = git_bind(AUTHORIZATION_COMMIT, PLAN)
    authorization_text = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{PLAN}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    require("Consumed-span row authorized" in authorization_text
            and "no further evidence row follows it" in authorization_text,
            "closing-row authorization text absent")
    spans = source_spans()
    patches = patch_rows()
    artifacts = {
        CODE0_PATCH: code0_patch(), CODE1_PATCH: code1_patch(),
        DISPATCH_RESTORE: dispatch_restore(), SPAN_RESET: span_reset(),
    }
    artifact_by_patch = {
        "retire-dispatch-progress-producer": DISPATCH_RESTORE,
        "terminal-hold-and-consumed-span-capture": CODE0_PATCH,
        "post-refill-pre-dispatch-capture-call": CODE1_PATCH,
        "consumed-span-record-reset": SPAN_RESET,
    }
    if write_artifacts:
        for path, raw in artifacts.items():
            write(path, raw)
    else:
        for path, raw in artifacts.items():
            require(path.read_bytes() == raw, f"artifact drift: {path.name}")

    # Execute the linked snapshot body independently for both authorized rows.
    prior = emulate_capture(owner=656, window=29,
                            payload=bytes.fromhex(spans[0]["source_hex"]))
    last = emulate_capture(owner=696, window=10,
                           payload=bytes.fromhex(spans[1]["source_hex"]))
    prior_row = decode_span(prior, PRIOR_SLOT, sentinel=PRIOR_SENTINEL,
                            commit=PRIOR_COMMIT, source=spans[0])
    last_row = decode_span(last, LAST_SLOT, sentinel=LAST_SENTINEL,
                           commit=LAST_COMMIT, source=spans[1])
    require(prior_row["state"] == last_row["state"] == "committed"
            and prior_row["first_difference"] is None
            and last_row["first_difference"] is None,
            "capture execution model failed")
    nonmatch = emulate_capture(owner=700, window=0, payload=b"\x00")
    require(nonmatch == span_reset(), "nonmatching refill mutated closing row")
    wrong_length = emulate_capture(owner=696, window=10,
                                   payload=bytes.fromhex(spans[1]["source_hex"]),
                                   length=15)
    require(wrong_length == span_reset(), "wrong-length refill committed")

    deployment = {
        "format": "lisp65-c2.3-post-v1.4-defstruct-consumed-span-deployment-v1",
        "status": "HOST-GREEN; ONE OWNER-PHYSICAL REPRODUCTION REQUIRED",
        "base_runner": "scripts/c2-defstruct-terminal-ingress-hw.sh",
        "device_output": (OUT / "device").relative_to(ROOT).as_posix(),
        "product_medium": bind(MEDIUM), "library_medium": bind(LIBRARY),
        "patches": [{"name": row["name"], "address": row["address"],
                     "artifact": bind(artifact_by_patch[row["name"]])}
                    for row in patches],
        "quiet_floor_seconds": 180,
        "forms": ["(require (quote defstruct))", "(defstruct point x y)"],
        "post_stop_reads": [
            {"address": "0x0000B582", "bytes": 66, "name": "consumed-spans"},
            {"address": "0x0000C03F", "bytes": 65, "name": "terminal-ring"},
            {"address": "0x00020000", "bytes": 65536, "name": "Bank-2-source"},
            {"address": "0x00050000", "bytes": 50816, "name": "C2D-reset-domain"},
        ],
        "tuple_before_any_memory_read": {
            "PC": "0xB3B9", "SP": "0x018D", "MAPH": "0x8000",
            "MAPL": "0x0000",
        },
    }
    if write_artifacts:
        write_json(DEPLOY, deployment)
    else:
        require(load(DEPLOY) == deployment, "deployment drift")

    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN-CLOSING-ROW; DEVICE-REPRODUCTION-REQUIRED",
        "authorities": {
            "owner_authorization": authorization, "coverage": bind(COVERAGE),
            "diagnostic_sister": bind(SISTER), "terminal_source_capsule": bind(TERMINAL_DEVICE),
            "phase_B_record": bind(PHASE_B), "diagnostic_PRG": bind(PRG),
            "diagnostic_ELF": bind(ELF), "diagnostic_medium": bind(MEDIUM),
            "library_medium": bind(LIBRARY), "runner": bind(RUNNER),
        },
        "existing_stopped_state_preflight": {
            "expected": EXPECTED_HISTORICAL_TUPLE,
            "observed": REJECTED_LIVE_TUPLE,
            "matched": False, "target_memory_reads_after_mismatch": 0,
            "claim": "none; deterministic reproduction required",
        },
        "identity": {
            "promotable": False, "product_bytes_changed": 0,
            "medium_bytes_changed": 0, "product_links": 0, "WPLTO_runs": 0,
            "runtime_patch_bytes": sum(row["bytes"] for row in patches),
            "runtime_patches": patches, "G4_window_bytes_changed": 0,
            "control_PRG_sha256": bind(PRG)["sha256"],
        },
        "spans": spans,
        "instrument": {
            "writer": "target-owned post-refill/pre-dispatch hook",
            "hook_PC": "0xC038", "capture_PC": "0xB3C0",
            "record_address": "0xB582", "record_bytes": SPAN_RECORD_BYTES,
            "commit_last": True, "completion_metadata_used_as_oracle": False,
            "source_oracle": "captured C2D entry plus captured Bank-2 object",
            "terminal_last_two_identity_ring_retained": True,
            "only_exact_owner-window-length_rows_commit": True,
            "execution_model": [prior_row, last_row],
            "wrong_length_commits": False, "unrelated_refill_mutates_record": False,
            "artifacts": {path.name: bind(path) for path in artifacts},
        },
        "contact": {
            "authorized": True, "contacts": 1,
            "physical_owner_input_only": True,
            "monitor_accesses_during_active_form": 0,
            "screen_polls_during_active_form": 0,
            "stops_after_active_form": 1,
            "tuple_and_static_SHA_before_any_memory_read": True,
            "RUN_resume_reset_after_final_stop": 0,
            "runner_contract": runner_contract(),
        },
        "decision_table": {
            "any_byte_difference": (
                "STALE-CONSUMED-SPAN-PROVEN; reopen F018B-family owner question"),
            "both_spans_byte_exact": (
                "STALENESS-REFUTED; local terminal-ingress corruption; "
                "structural stack/vector defense owner question"),
            "identity_or_tag_mismatch": "INSTRUMENT-RED; no product claim",
            "further_evidence_rows": 0,
        },
        "claim_limit": (
            "Host-green non-promotable closing-row preparation only. The rejected "
            "historical stopped state yielded no memory read. No staleness decision, "
            "fix, link, ownership recharter or v1.5 scope claim exists before the one "
            "authorized deterministic reproduction."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT
            and value["status"] ==
            "HOST-GREEN-CLOSING-ROW; DEVICE-REPRODUCTION-REQUIRED",
            "preparation identity drift")
    preflight = value["existing_stopped_state_preflight"]
    require(preflight["matched"] is False
            and preflight["target_memory_reads_after_mismatch"] == 0,
            "rejected-state read discipline drift")
    identity = value["identity"]
    require(identity["promotable"] is False
            and identity["product_bytes_changed"] == 0
            and identity["medium_bytes_changed"] == 0
            and identity["G4_window_bytes_changed"] == 0,
            "identity boundary drift")
    require([(row["owner_ordinal"], row["window_base"], row["consumed_bytes"])
             for row in value["spans"]] == [(656, 29, 3), (696, 10, 16)],
            "consumed-span set drift")
    instrument = value["instrument"]
    require(instrument["writer"] == "target-owned post-refill/pre-dispatch hook"
            and instrument["commit_last"] is True
            and instrument["completion_metadata_used_as_oracle"] is False
            and instrument["source_oracle"] ==
            "captured C2D entry plus captured Bank-2 object"
            and instrument["terminal_last_two_identity_ring_retained"] is True
            and instrument["only_exact_owner-window-length_rows_commit"] is True
            and instrument["wrong_length_commits"] is False
            and instrument["unrelated_refill_mutates_record"] is False,
            "instrument contract drift")
    contact = value["contact"]
    require(contact["authorized"] is True and contact["contacts"] == 1
            and contact["physical_owner_input_only"] is True
            and contact["monitor_accesses_during_active_form"] == 0
            and contact["screen_polls_during_active_form"] == 0
            and contact["stops_after_active_form"] == 1
            and contact["tuple_and_static_SHA_before_any_memory_read"] is True,
            "contact discipline drift")
    require(contact["runner_contract"] == {
        "tuple_before_first_memory_read": True,
        "post_stop_memory_reads": 4,
        "post_stop_resume_reset_RUN": 0,
        "pre_form_resume_count": 1,
    }, "runner contract drift")
    require(value["decision_table"]["further_evidence_rows"] == 0,
            "closing-row finality drift")


def audit(value: dict[str, Any]) -> None:
    validate(value)
    require(value == derive(write_artifacts=False),
            "preparation receipt differs from reconstruction")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive(write_artifacts=False)
    cases: list[tuple[str, list[Any], Any]] = [
        ("claim-existing-stop", ["existing_stopped_state_preflight", "matched"], True),
        ("read-after-tuple-mismatch", ["existing_stopped_state_preflight",
                                       "target_memory_reads_after_mismatch"], 1),
        ("promotable", ["identity", "promotable"], True),
        ("product-byte", ["identity", "product_bytes_changed"], 1),
        ("medium-byte", ["identity", "medium_bytes_changed"], 1),
        ("G4-window-byte", ["identity", "G4_window_bytes_changed"], 1),
        ("move-prior-owner", ["spans", 0, "owner_ordinal"], 655),
        ("move-prior-window", ["spans", 0, "window_base"], 28),
        ("short-prior", ["spans", 0, "consumed_bytes"], 2),
        ("move-last-owner", ["spans", 1, "owner_ordinal"], 697),
        ("move-last-window", ["spans", 1, "window_base"], 11),
        ("short-last", ["spans", 1, "consumed_bytes"], 15),
        ("host-writer", ["instrument", "writer"], "host post-stop writer"),
        ("commit-first", ["instrument", "commit_last"], False),
        ("completion-oracle", ["instrument", "completion_metadata_used_as_oracle"], True),
        ("tracked-source-only", ["instrument", "source_oracle"],
         "tracked historical capsule only"),
        ("drop-last-two-ring", ["instrument", "terminal_last_two_identity_ring_retained"], False),
        ("broad-filter", ["instrument", "only_exact_owner-window-length_rows_commit"], False),
        ("wrong-length-commit", ["instrument", "wrong_length_commits"], True),
        ("unrelated-write", ["instrument", "unrelated_refill_mutates_record"], True),
        ("virtual-input", ["contact", "physical_owner_input_only"], False),
        ("active-monitor", ["contact", "monitor_accesses_during_active_form"], 1),
        ("active-screen", ["contact", "screen_polls_during_active_form"], 1),
        ("two-stops", ["contact", "stops_after_active_form"], 2),
        ("memory-before-tuple", ["contact", "tuple_and_static_SHA_before_any_memory_read"], False),
        ("permit-next-row", ["decision_table", "further_evidence_rows"], 1),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate(trial)
            require(trial == derive(write_artifacts=False), "mutated receipt accepted")
        except SpanError:
            rejected.append(name)
        else:
            raise SpanError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected, "spans": 2, "further_evidence_rows": 0}


def result_from_capture() -> dict[str, Any]:
    preparation = load(RECEIPT)
    audit(preparation)
    device = OUT / "device"
    registers = load(device / "final-registers.json")
    expected_tuple = load(DEPLOY)["tuple_before_any_memory_read"]
    for name, expected in expected_tuple.items():
        require(registers[name].lower() == expected.lower(),
                f"final tuple mismatch: {name}")
    raw = (device / "consumed-spans.bin").read_bytes()
    sources = captured_source_spans(device, preparation["spans"])
    rows = [
        decode_span(raw, PRIOR_SLOT, sentinel=PRIOR_SENTINEL,
                    commit=PRIOR_COMMIT, source=sources[0]),
        decode_span(raw, LAST_SLOT, sentinel=LAST_SENTINEL,
                    commit=LAST_COMMIT, source=sources[1]),
    ]
    require(all(row["state"] == "committed" for row in rows),
            "one or more consumed spans did not commit")
    terminal = (device / "terminal-ring.bin").read_bytes()
    terminal_identity(terminal)
    bindings = {
        "registers": bind(device / "final-registers.json"),
        "span_capture": bind(device / "consumed-spans.bin"),
        "terminal_ring": bind(device / "terminal-ring.bin"),
        "Bank_2": bind(device / "bank2-source.bin"),
        "C2D": bind(device / "c2d-reset-domain.bin"),
    }
    require(bindings == EXPECTED_RESULT_BINDINGS,
            "closing device-artifact identity drift")
    stale = [row for row in rows if row["first_difference"] is not None]
    decision = ("STALE-CONSUMED-SPAN-PROVEN; F018B-FAMILY-QUESTION-REOPENED"
                if stale else
                "ALL-CONSUMED-SPANS-BYTE-EXACT; STALENESS-REFUTED; "
                "LOCAL-TERMINAL-INGRESS-CORRUPTION")
    return {
        "format": RESULT_FORMAT, "recorded_on": RECORDED_ON,
        "status": decision,
        "authorities": {"preparation": bind(RECEIPT), **bindings},
        "tuple": {name: registers[name] for name in expected_tuple},
        "raw_capture": {"span_record_hex": raw.hex(),
                        "terminal_ring_hex": terminal.hex()},
        "source_oracles": sources,
        "spans": rows, "stale_span_count": len(stale),
        "decision": {
            "classification": decision,
            "attribution_closed": True, "further_evidence_rows": 0,
            "owner_decision_required": True,
            "next": ("F018B-family recharter question" if stale else
                     "structural terminal-ingress stack/vector defense commission"),
        },
        "claim_limit": (
            "Closing evidence row. It decides only stale consumed-window bytes versus "
            "local terminal-ingress corruption and routes the fix choice to the owner."),
    }


def terminal_identity(terminal: bytes) -> tuple[int, int, int, int]:
    require(len(terminal) == 65, "terminal ring geometry drift")
    phase_b = load(PHASE_B)
    fields = phase_b["facts"]["record"]["fields"]
    by_name = {row["name"]: row for row in fields}

    def field_value(name: str) -> int:
        field = by_name[name]
        tag = terminal[field["tag_offset"]]
        require(tag == field["reached_tag"], f"terminal field not reached: {name}")
        at = field["value_offset"]
        return int.from_bytes(terminal[at:at + field["value_bytes"]], "little")

    result = (field_value("previous-fill.owner"),
              field_value("previous-fill.window-base"),
              field_value("last-fill.owner"),
              field_value("last-fill.window-base"))
    require(result == (0x029001, 29, 0x02B801, 10),
            "terminal last-two refill identity differs from snapshot filters")
    return result


def validate_result(value: dict[str, Any]) -> None:
    require(value["format"] == RESULT_FORMAT and value["recorded_on"] == RECORDED_ON,
            "closing result identity drift")
    preparation = load(RECEIPT)
    audit(preparation)
    require(value["authorities"]["preparation"] == bind(RECEIPT),
            "closing preparation binding drift")
    require({key: value["authorities"][key] for key in EXPECTED_RESULT_BINDINGS}
            == EXPECTED_RESULT_BINDINGS, "closing capture binding drift")
    require({key: value["tuple"][key].lower() for key in EXPECTED_FINAL_TUPLE}
            == {key: expected.lower() for key, expected in EXPECTED_FINAL_TUPLE.items()},
            "closing terminal tuple drift")
    span_raw = bytes.fromhex(value["raw_capture"]["span_record_hex"])
    terminal = bytes.fromhex(value["raw_capture"]["terminal_ring_hex"])
    require(digest(span_raw) == EXPECTED_RESULT_BINDINGS["span_capture"]["sha256"]
            and digest(terminal) == EXPECTED_RESULT_BINDINGS["terminal_ring"]["sha256"],
            "embedded closing capture drift")
    terminal_identity(terminal)
    sources = value["source_oracles"]
    require(len(sources) == len(preparation["spans"]) == 2,
            "closing source-oracle cardinality drift")
    for source, authority in zip(sources, preparation["spans"], strict=True):
        for key, expected in authority.items():
            require(source[key] == expected,
                    f"{authority['name']} source authority drift: {key}")
        entry = bytes.fromhex(source["captured_C2D_entry_hex"])
        obj = bytes.fromhex(source["captured_object_hex"])
        require(len(entry) == C2D_ENTRY_BYTES
                and entry[0] == source["image_slot"]
                and entry[1] == source["literal_count"]
                and u16_at(entry, 2) == source["code_offset"]
                and u16_at(entry, 4) == source["code_length"]
                and u16_at(entry, 6) == source["resolution_base"]
                and u16_at(entry, 8) == source["generation"],
                f"{source['name']} embedded C2D row drift")
        header = C2_CODE_HEADER_SCALAR_BYTES + 2 * source["literal_count"]
        payload = obj[header:]
        start = source["window_base"]
        end = start + source["consumed_bytes"]
        consumed = payload[start:end]
        require(len(obj) == source["code_length"]
                and digest(obj) == source["captured_object_sha256"]
                == source["object_sha256"]
                and end == len(payload)
                and consumed.hex() == source["source_hex"]
                and digest(consumed) == source["source_sha256"],
                f"{source['name']} embedded source oracle drift")
    rows = [
        decode_span(span_raw, PRIOR_SLOT, sentinel=PRIOR_SENTINEL,
                    commit=PRIOR_COMMIT, source=sources[0]),
        decode_span(span_raw, LAST_SLOT, sentinel=LAST_SENTINEL,
                    commit=LAST_COMMIT, source=sources[1]),
    ]
    require(value["spans"] == rows
            and all(row["state"] == "committed" for row in rows),
            "closing decoded span drift")
    stale = [row for row in rows if row["first_difference"] is not None]
    decision = ("STALE-CONSUMED-SPAN-PROVEN; F018B-FAMILY-QUESTION-REOPENED"
                if stale else
                "ALL-CONSUMED-SPANS-BYTE-EXACT; STALENESS-REFUTED; "
                "LOCAL-TERMINAL-INGRESS-CORRUPTION")
    require(value["status"] == decision
            and value["stale_span_count"] == len(stale)
            and value["decision"] == {
                "classification": decision,
                "attribution_closed": True,
                "further_evidence_rows": 0,
                "owner_decision_required": True,
                "next": ("F018B-family recharter question" if stale else
                         "structural terminal-ingress stack/vector defense commission"),
            }, "closing decision drift")


def result_selftest() -> dict[str, Any]:
    base = load(RESULT)
    validate_result(base)
    cases: list[tuple[str, list[Any], Any]] = [
        ("change-status", ["status"], "STALE-CONSUMED-SPAN-PROVEN"),
        ("move-PC", ["tuple", "PC"], "0xB3BA"),
        ("change-span-raw", ["raw_capture", "span_record_hex"], "00" * 66),
        ("change-ring-raw", ["raw_capture", "terminal_ring_hex"], "00" * 65),
        ("change-C2D-row", ["source_oracles", 0, "captured_C2D_entry_hex"],
         "00" * 10),
        ("change-source-object", ["source_oracles", 0, "captured_object_hex"],
         "00" * 45),
        ("change-source-byte", ["source_oracles", 1, "source_hex"], "00" * 16),
        ("change-actual", ["spans", 0, "actual_hex"], "000000"),
        ("change-tag", ["spans", 1, "tag"], LAST_SENTINEL),
        ("invent-stale", ["stale_span_count"], 1),
        ("open-attribution", ["decision", "attribution_closed"], False),
        ("permit-next-row", ["decision", "further_evidence_rows"], 1),
        ("drop-owner-decision", ["decision", "owner_decision_required"], False),
        ("reopen-F018B", ["decision", "next"], "F018B-family recharter question"),
        ("change-Bank2-binding", ["authorities", "Bank_2", "sha256"], "0" * 64),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate_result(trial)
        except (SpanError, ValueError, KeyError, IndexError):
            rejected.append(name)
        else:
            raise SpanError(f"result mutation survived: {name}")
    require(len(rejected) == len(cases), "result mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "classification": base["status"], "further_evidence_rows": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "derive", "record", "check", "selftest", "result-record", "result-check",
        "result-selftest"))
    args = parser.parse_args()
    if args.action == "derive":
        value = derive(write_artifacts=False)
    elif args.action == "record":
        value = derive(write_artifacts=True)
        write_json(RECEIPT, value)
    elif args.action == "check":
        audit(load(RECEIPT))
        value = {"status": "PASS", "mutations_rejected": 26,
                 "spans": 2, "further_evidence_rows": 0}
    elif args.action == "selftest":
        value = selftest()
    elif args.action == "result-record":
        value = result_from_capture()
        write_json(RESULT, value)
    elif args.action == "result-selftest":
        value = result_selftest()
    else:
        result = load(RESULT)
        validate_result(result)
        value = {"status": "PASS", "classification": result["status"],
                 "mutations_rejected": 15, "further_evidence_rows": 0}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SpanError, ElfTruthError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT CONSUMED SPAN: {error}", file=sys.stderr)
        raise SystemExit(1)
