#!/usr/bin/env python3
"""Build the non-promotable Link-106 LOADING LIBRARIES progress sibling.

Successful logical Shelf/C2D reads increment one 32-bit target counter.  The
owned raster IRQ snapshots that counter plus the decoder phase/cursors into
four commit-last Bank-0 slots.  Nothing outside the target observes the
machine while the measured phase is active; a later contact, if separately
authorized, needs one final stop and one raw-first readback only.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
import c2_v16_defstruct_phase_c as PHASE_C  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
CPU_RECEIPT = ARCH / "c2.3-v2.0-cpu-transport-reconciliation-receipt.json"
GRANULARITY = ARCH / "c2.3-v2.0-convergence-granularity-review-receipt.json"
OWNERSHIP = ARCH / "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json"
MEDIA_RECEIPT = ARCH / "c2.3-v2.0-phase02b-header-consumption-completion-media-receipt.json"
CONTROL_ELF = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-replacement-card/"
                      "final/lisp65-c2-substitution-linked.prg.elf")
CONTROL_PRG = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-replacement-card/"
                      "final/lisp65-c2-substitution-linked.prg")
CONTROL_D81 = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-media/"
                      "shared-system/lisp65-product.d81")
LIBRARY_D81 = ROOT / ("build/c2.3/v2.0-phase02b-header-consumption-media-base/"
                      "library/lisp65-library.d81")
KERNAL_SOURCE = ROOT / "src/c2_kernal_window.s"
SESSION = ROOT / "config/c2-v20-loading-libraries-progress-session.json"
RUNNER = ROOT / "scripts/c2-v20-loading-libraries-progress-hw.sh"

OUT = ROOT / "build/c2.3/v2.0-loading-libraries-progress"
ART = OUT / "artifacts"
DIAG_PRG = ART / "diagnostic-loading-libraries-progress.prg"
DIAG_ELF = ART / "diagnostic-loading-libraries-progress.elf"
DIAG_WINDOW = ART / "diagnostic-loading-libraries-progress-window.bin"
DIAG_STATE = ART / "loading-libraries-progress-state-reset.bin"
DIAG_D81 = OUT / "lisp65-loading-libraries-progress.d81"
DIAG_DESCRIPTOR = OUT / "boot.id"
DIAG_STAGER = OUT / "autoboot.c65"
DIAG_STAGER_MAP = OUT / "autoboot.c65.map"
DIAG_STAGER_BUILD = OUT / "stager-build"
DEPLOY = OUT / "deployment.json"
RECEIPT = ARCH / "c2.3-v2.0-loading-libraries-progress-ring-receipt.json"

AUTHORIZATION = "db20fc5b"
FORMAT = "lisp65-c2.3-v2.0-loading-libraries-progress-ring-v1"
RECORDED_ON = "2026-08-14"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

PRG_LOAD = 0x2001
WINDOW_BASE = 0xE000
WINDOW_BYTES = 8192
ABORT_CALL = 0x2DDE
VM_C2D_CALL = 0x77C0
VM_C2D_SAFE_NIL = 0xFEDA
C2D_RETURN = 0xE32A
SHELF_RETURN = 0xE851
IRQ_SAMPLE_CALL = 0xE053
BREAK_SAMPLE = 0xD613
PRODUCER_C2D = 0xFE88
PRODUCER_SHELF = 0xFE8F
PRODUCER_LIMIT = 0xFEE1
SAMPLER = 0xFEE1
SAMPLER_LIMIT = 0xFF67
FRAME_LO = 0xFF83
FRAME_HI = 0xFF84
STATE = 0xB582
COUNTER = STATE
PHASE = STATE + 4
IMAGE = STATE + 5
ENTRY = STATE + 6
DESCRIPTOR = STATE + 8
TRANSPORT = STATE + 10
ARM = STATE + 11
SLOTS = STATE + 12
SLOT_BYTES = 13
SLOT_COUNT = 4
STATE_LIMIT = 0xB5C4
RUNTIME = 0xC084
RUNTIME_IMAGE = RUNTIME + 26
RUNTIME_ENTRY = RUNTIME + 28
RUNTIME_DESCRIPTOR = RUNTIME + 30
RUNTIME_PHASE = RUNTIME + 42
CRC_HIGH = 0xB4F4
CRC_LOW = 0xB4FA
COMMIT = 0xA5
ARM_VALUE = 0xA5
SAMPLE_HIGH_STRIDE = 8
SAMPLE_FRAMES = SAMPLE_HIGH_STRIDE * 256
FRAME_HZ_MILLI = 51966
SECTION_STATE = ".lisp65_v20_loading_libraries_progress_state"


class RingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name); handle.write(payload)
    temporary.replace(path)


def run(argv: list[str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    require("build the specified progress ring" in text
            and "target-side" in text and "no contact before the ring exists" in text,
            "progress-ring authorization drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def crc16(raw: bytes) -> int:
    value = 0xFFFF
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ 0x1021) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def replace(raw: bytearray, offset: int, before: bytes, after: bytes,
            label: str) -> None:
    require(len(before) == len(after), f"fixed-size patch required: {label}")
    require(raw[offset:offset + len(before)] == before,
            f"patch authority drift: {label}")
    raw[offset:offset + len(after)] = after


def with_nz(p: int, value: int) -> int:
    p = (p | 2) if value == 0 else (p & ~2)
    return (p | 0x80) if value & 0x80 else (p & ~0x80)


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

    def abs(self, opcode: int, address: int) -> None:
        self.emit(opcode, address & 0xFF, address >> 8)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.pc

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0); self.fixups.append((len(self.raw) - 1, label))

    def finish(self) -> bytes:
        for offset, label in self.fixups:
            require(label in self.labels, f"missing label: {label}")
            after = self.origin + offset + 1
            delta = self.labels[label] - after
            require(-128 <= delta <= 127, f"branch out of range: {label}")
            self.raw[offset] = delta & 0xFF
        return bytes(self.raw)


def producer_bytes(control: bytes) -> tuple[bytes, dict[str, int]]:
    """Two logical-read entries and one interrupt-atomic common commit."""
    a = Asm(PRODUCER_C2D)
    a.emit(0xAA)                            # TAX: preserve bool result/NZ shape
    a.branch(0xF0, "return")
    a.emit(0xA9, 0x00)                     # transport 0 = C2D / Bank 5
    a.branch(0x80, "common")
    require(a.pc == PRODUCER_SHELF, "Shelf producer entry drift")
    a.abs(0xAD, 0x0010)                    # displaced LDA c2 shelf result
    a.emit(0xAA)
    a.branch(0xF0, "return")
    a.emit(0xA9, 0x01)                     # transport 1 = Shelf / Attic
    a.branch(0x80, "common")
    a.label("return")
    a.emit(0x8A, 0x60)                     # TXA; RTS
    a.label("common")
    a.emit(0x08, 0x78)                     # PHP; SEI
    a.abs(0x8D, TRANSPORT)
    for source, destination in (
        (RUNTIME_PHASE, PHASE), (RUNTIME_IMAGE, IMAGE),
        (RUNTIME_ENTRY, ENTRY), (RUNTIME_ENTRY + 1, ENTRY + 1),
        (RUNTIME_DESCRIPTOR, DESCRIPTOR),
        (RUNTIME_DESCRIPTOR + 1, DESCRIPTOR + 1)):
        a.abs(0xAD, source); a.abs(0x8D, destination)
    a.abs(0xEE, COUNTER); a.branch(0xD0, "committed")
    a.abs(0xEE, COUNTER + 1); a.branch(0xD0, "committed")
    a.abs(0xEE, COUNTER + 2); a.branch(0xD0, "committed")
    a.abs(0xEE, COUNTER + 3)
    a.label("committed")
    a.emit(0x28, 0x8A, 0x60)               # PLP; TXA; RTS (final NZ matches bool)
    code = a.finish()
    require(len(code) <= VM_C2D_SAFE_NIL - PRODUCER_C2D,
            f"producer overlaps preserved NIL tail: {len(code)} bytes")
    tail = control[VM_C2D_SAFE_NIL - PRODUCER_C2D:PRODUCER_LIMIT - PRODUCER_C2D]
    require(tail == bytes.fromhex("a900a200a30060"), "vm_c2d NIL tail drift")
    image = code + bytes((0xEA,)) * (VM_C2D_SAFE_NIL - PRODUCER_C2D - len(code)) + tail
    require(len(image) == PRODUCER_LIMIT - PRODUCER_C2D,
            "producer carrier geometry drift")
    return image, {"c2d": PRODUCER_C2D, "shelf": PRODUCER_SHELF,
                   "common": a.labels["common"], "bytes": len(code)}


def sampler_bytes() -> tuple[bytes, dict[str, int]]:
    """Sample every 2048 owned raster frames; invalidate then commit last."""
    a = Asm(SAMPLER)
    a.abs(0xAD, ARM); a.emit(0xC9, ARM_VALUE); a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_LO); a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_HI); a.emit(0x29, SAMPLE_HIGH_STRIDE - 1)
    a.branch(0xD0, "done")
    a.abs(0xAD, FRAME_HI); a.emit(0x29, 0x18)
    a.emit(0xA2, 0); a.emit(0xC9, 0); a.branch(0xF0, "selected")
    a.emit(0xA2, SLOT_BYTES); a.emit(0xC9, 0x08); a.branch(0xF0, "selected")
    a.emit(0xA2, SLOT_BYTES * 2); a.emit(0xC9, 0x10); a.branch(0xF0, "selected")
    a.emit(0xA2, SLOT_BYTES * 3)
    a.label("selected")
    a.abs(0x9E, SLOTS + SLOT_BYTES - 1)     # commit = 0 before payload
    a.emit(0xA0, 0)
    a.label("copy")
    a.abs(0xB9, COUNTER); a.abs(0x9D, SLOTS)
    a.emit(0xE8, 0xC8, 0xC0, 11); a.branch(0xD0, "copy")
    a.abs(0xAD, FRAME_HI); a.abs(0x9D, SLOTS); a.emit(0xE8)
    a.emit(0xA9, COMMIT); a.abs(0x9D, SLOTS)  # commit last
    a.label("done")
    a.abs(0xAD, BREAK_SAMPLE); a.emit(0x60)  # replay displaced IRQ load
    code = a.finish()
    require(len(code) <= SAMPLER_LIMIT - SAMPLER,
            f"sampler carrier overflow: {len(code)} bytes")
    image = code + bytes((0xEA,)) * (SAMPLER_LIMIT - SAMPLER - len(code))
    return image, {"bytes": len(code), "selected": a.labels["selected"],
                   "copy": a.labels["copy"], "done": a.labels["done"]}


def state_reset() -> bytes:
    header = bytes((0, 0, 0, 0, 0xD0, 0xD1, 0xD2, 0xD3,
                    0xD4, 0xD5, 0xD6, ARM_VALUE))
    slot = bytes((0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE,
                  0xDF, 0xE0, 0xE1, 0xE2, 0xE3, 0x00))
    raw = header + slot * SLOT_COUNT + bytes((0xD7, 0xD7))
    require(len(raw) == STATE_LIMIT - STATE, "progress state geometry drift")
    return raw


def patched_images() -> dict[str, Any]:
    control_prg = bytearray(CONTROL_PRG.read_bytes())
    require(control_prg[:2] == u16(PRG_LOAD), "control PRG load address drift")
    truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                         include_section_data=True)
    control_roles = SISTER.medium_roles(CONTROL_D81, OUT / "readback-control")
    paths = SISTER.role_paths(control_roles)
    window = bytearray(paths["window.bin"].read_bytes())
    require(len(window) == WINDOW_BYTES, "control KERNAL window extent drift")
    require(paths["lisp65.prg"].read_bytes() == bytes(control_prg),
            "packed PRG is not Link-106 final PRG")
    original_gap = bytes(window[PRODUCER_C2D - WINDOW_BASE:PRODUCER_LIMIT - WINDOW_BASE])
    producer, producer_layout = producer_bytes(original_gap)
    sampler, sampler_layout = sampler_bytes()

    replace(window, C2D_RETURN - WINDOW_BASE, bytes.fromhex("aa8a60"),
            b"\x4c" + u16(PRODUCER_C2D), "C2D logical-success producer")
    replace(window, SHELF_RETURN - WINDOW_BASE, bytes.fromhex("a51060"),
            b"\x4c" + u16(PRODUCER_SHELF), "Shelf logical-success producer")
    replace(window, IRQ_SAMPLE_CALL - WINDOW_BASE, b"\xad" + u16(BREAK_SAMPLE),
            b"\x20" + u16(SAMPLER), "owned raster self-sampler")
    replace(window, PRODUCER_C2D - WINDOW_BASE, original_gap, producer,
            "producer carrier")
    abort = bytes(window[SAMPLER - WINDOW_BASE:SAMPLER_LIMIT - WINDOW_BASE])
    replace(window, SAMPLER - WINDOW_BASE, abort, sampler, "sampler carrier")
    new_crc = crc16(bytes(window))

    replace(control_prg, prg_offset(ABORT_CALL), b"\x20" + u16(SAMPLER),
            b"\xea\xea\xea", "retire abort-driver call")
    replace(control_prg, prg_offset(VM_C2D_CALL), b"\x20" + u16(PRODUCER_C2D),
            b"\x20" + u16(VM_C2D_SAFE_NIL), "retire overwritten vm_c2d_byte")
    reset = state_reset()
    replace(control_prg, prg_offset(STATE), bytes(STATE_LIMIT - STATE), reset,
            "owner-free progress state")
    old_crc = (control_prg[prg_offset(CRC_HIGH)] << 8
               | control_prg[prg_offset(CRC_LOW)])
    control_prg[prg_offset(CRC_HIGH)] = new_crc >> 8
    control_prg[prg_offset(CRC_LOW)] = new_crc & 0xFF
    require(old_crc == crc16(paths["window.bin"].read_bytes()),
            "packed control G4 CRC operand drift")

    ART.mkdir(parents=True, exist_ok=True)
    DIAG_PRG.write_bytes(control_prg)
    DIAG_WINDOW.write_bytes(window)
    DIAG_STATE.write_bytes(reset)
    patch_elf(truth, bytes(window), reset, new_crc, producer, sampler)
    return {"control_roles": control_roles, "control_paths": paths,
            "producer": producer_layout, "sampler": sampler_layout,
            "old_crc16": f"0x{old_crc:04x}", "new_crc16": f"0x{new_crc:04x}",
            "producer_hex": producer.hex(), "sampler_hex": sampler.hex(),
            "reset_hex": reset.hex()}


def patch_elf(truth: ElfTruth, window: bytes, reset: bytes, new_crc: int,
              producer: bytes, sampler: bytes) -> None:
    updates: dict[str, bytes] = {}
    text_name = ".text"
    text = bytearray(truth.section_bytes(text_name)); base = truth.section(text_name).address
    replace(text, ABORT_CALL - base, b"\x20" + u16(SAMPLER), b"\xea\xea\xea",
            "ELF retire abort-driver call")
    replace(text, VM_C2D_CALL - base, b"\x20" + u16(PRODUCER_C2D),
            b"\x20" + u16(VM_C2D_SAFE_NIL), "ELF retire vm_c2d_byte")
    updates[text_name] = bytes(text)

    c2_name = ".lisp65_c2_kernal_window.c2_resident"
    c2 = bytearray(truth.section_bytes(c2_name)); base = truth.section(c2_name).address
    replace(c2, C2D_RETURN - base, bytes.fromhex("aa8a60"),
            b"\x4c" + u16(PRODUCER_C2D), "ELF C2D producer")
    replace(c2, SHELF_RETURN - base, bytes.fromhex("a51060"),
            b"\x4c" + u16(PRODUCER_SHELF), "ELF Shelf producer")
    updates[c2_name] = bytes(c2)

    irq_name = ".lisp65_c2_kernal_window.irq_handler"
    irq = bytearray(truth.section_bytes(irq_name)); base = truth.section(irq_name).address
    replace(irq, IRQ_SAMPLE_CALL - base, b"\xad" + u16(BREAK_SAMPLE),
            b"\x20" + u16(SAMPLER), "ELF raster sampler")
    updates[irq_name] = bytes(irq)

    gap_name = ".lisp65_c2_kernal_window.reopen_gap1"
    gap = bytearray(truth.section_bytes(gap_name)); base = truth.section(gap_name).address
    require(base == PRODUCER_C2D and len(gap) >= SAMPLER_LIMIT - PRODUCER_C2D,
            "ELF reopen-gap carrier drift")
    gap[:PRODUCER_LIMIT - PRODUCER_C2D] = producer
    gap[SAMPLER - base:SAMPLER_LIMIT - base] = sampler
    updates[gap_name] = bytes(gap)

    handoff_name = ".lisp65_c2_kernal_handoff"
    handoff = bytearray(truth.section_bytes(handoff_name)); base = truth.section(handoff_name).address
    require(handoff[CRC_HIGH - base] == 0xA5 and handoff[CRC_LOW - base] == 0x5A,
            "pre-completion ELF G4 operands drift")
    handoff[CRC_HIGH - base] = new_crc >> 8
    handoff[CRC_LOW - base] = new_crc & 0xFF
    updates[handoff_name] = bytes(handoff)

    section_files: dict[str, Path] = {}
    for index, (name, raw) in enumerate(updates.items()):
        path = ART / f"elf-update-{index}.bin"; path.write_bytes(raw)
        section_files[name] = path
    argv = [str(OBJCOPY)]
    for name, path in section_files.items():
        argv.append(f"--update-section={name}={path}")
    argv.extend([f"--add-section={SECTION_STATE}={DIAG_STATE}",
                 f"--set-section-flags={SECTION_STATE}=alloc,load,data",
                 f"--add-symbol=lisp65_v20_loading_progress_counter=0x{COUNTER:x},global,object",
                 f"--add-symbol=lisp65_v20_loading_progress_slots=0x{SLOTS:x},global,object",
                 f"--add-symbol=lisp65_v20_loading_progress_c2d=0x{PRODUCER_C2D:x},global,function",
                 f"--add-symbol=lisp65_v20_loading_progress_shelf=0x{PRODUCER_SHELF:x},global,function",
                 f"--add-symbol=lisp65_v20_loading_progress_sampler=0x{SAMPLER:x},global,function",
                 str(CONTROL_ELF), str(DIAG_ELF)])
    run(argv, "derive loading-progress ELF")
    PHASE_C.patch_elf_section_addresses(DIAG_ELF, {SECTION_STATE: STATE})


def build_medium(layout: dict[str, Any]) -> dict[str, Any]:
    control = layout["control_roles"]
    paths = dict(layout["control_paths"])
    donor = paths["boot.id"].read_bytes()
    donor_rows, donor_id, profile_id = SISTER.descriptor_rows(donor, paths)
    SISTER.target_descriptor_check(donor, donor_rows,
                                   descriptor_build_id=donor_id,
                                   stager_build_id=donor_id)
    payloads = dict(paths); payloads["lisp65.prg"] = DIAG_PRG
    payloads["window.bin"] = DIAG_WINDOW
    rows, inherited_id, inherited_profile = SISTER.descriptor_rows(donor, payloads)
    require(inherited_id == donor_id and inherited_profile == profile_id,
            "donor world drift while deriving diagnostic rows")
    descriptor, build_id = MEDIA.make_descriptor(rows, profile_id)
    DIAG_DESCRIPTOR.write_bytes(descriptor)
    SISTER.target_descriptor_check(descriptor, rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    stager_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=DIAG_STAGER_BUILD,
        stager=DIAG_STAGER, stager_map=DIAG_STAGER_MAP)
    shutil.copyfile(CONTROL_D81, DIAG_D81)
    run(["c1541", "-attach", str(DIAG_D81),
         "-delete", "lisp65.prg", "-write", str(DIAG_PRG), "lisp65.prg",
         "-delete", "window.bin", "-write", str(DIAG_WINDOW), "window.bin",
         "-delete", "boot.id", "-write", str(DIAG_DESCRIPTOR), "boot.id",
         "-delete", "autoboot.c65", "-write", str(DIAG_STAGER), "autoboot.c65"],
        "replace progress-sibling D81 roles")
    readback = SISTER.medium_roles(DIAG_D81, OUT / "readback-diagnostic")
    for name, row in control.items():
        expected = ({"lisp65.prg": DIAG_PRG, "window.bin": DIAG_WINDOW,
                     "boot.id": DIAG_DESCRIPTOR,
                     "autoboot.c65": DIAG_STAGER}.get(name))
        if expected is None:
            require(readback[name]["sha256"] == row["sha256"],
                    f"unrelated diagnostic role changed: {name}")
        else:
            require(readback[name]["sha256"] == digest(expected.read_bytes()),
                    f"diagnostic role readback drift: {name}")
    rb_paths = SISTER.role_paths(readback)
    rb_rows, rb_id, rb_profile = SISTER.descriptor_rows(
        rb_paths["boot.id"].read_bytes(), rb_paths)
    require(rb_id == build_id and rb_profile == profile_id,
            "diagnostic readback world drift")
    SISTER.target_descriptor_check(rb_paths["boot.id"].read_bytes(), rb_rows,
                                   descriptor_build_id=rb_id,
                                   stager_build_id=build_id)
    return {"control_roles": control, "diagnostic_roles": readback,
            "shared_roles": 11,
            "replaced_payload_roles": ["lisp65.prg", "window.bin"],
            "regenerated_contract_roles": ["autoboot.c65", "boot.id"],
            "build_id": f"0x{build_id:08x}", "profile_id": f"0x{profile_id:08x}",
            "stager_gate": stager_gate, "readback": "byteidentical"}


def executable_edges(truth: ElfTruth, target: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in truth.sections:
        if "SHF_EXECINSTR" not in section.flags or section.bytes < 3:
            continue
        raw = truth.section_bytes(section.name)
        for index in range(len(raw) - 2):
            if raw[index] in (0x20, 0x4C) \
                    and int.from_bytes(raw[index + 1:index + 3], "little") == target:
                rows.append({"section": section.name,
                             "pc": f"0x{section.address + index:04x}",
                             "opcode": "JSR" if raw[index] == 0x20 else "JMP"})
    return rows


def irq_contract() -> dict[str, Any]:
    source = KERNAL_SOURCE.read_text(encoding="utf-8")
    owned = source.split("c2_kernal_irq_handler:", 1)[1].split(".Lsource_less:", 1)[0]
    sourceless = source.split(".Lsource_less:", 1)[1].split(
        ".section .lisp65_c2_kernal_window.nmi", 1)[0]
    require("lda $d019" in owned and "and #$01" in owned
            and "beq .Lsource_less" in owned and "sta $d019" in owned
            and "inc C2K_FRAME_LO" in owned
            and "jmp c2_kernal_fail_closed" in sourceless,
            "owned/source-less IRQ partition drift")
    return {"sampler_after": ["D019&1", "D019 acknowledge", "frame increment"],
            "source_less_branch_precedes_sampler": True,
            "source_less_edges_to_sampler": 0}


def session_contract() -> dict[str, Any]:
    value = load(SESSION)
    require(value["status"] == "host-prepared-contact-not-authorized"
            and value["active_interval"] == {
                "begins": "cold boot before STAGING MEDIA",
                "ends": "separately authorized final stop",
                "host_monitor_entries": 0, "host_CPU_stops": 0,
                "screenshots": 0, "FTP_accesses": 0,
                "sampler": "owned target raster IRQ only"}
            and value["future_readback"]["stop_transitions"] == 1
            and value["future_readback"]["raw_first"] is True
            and value["future_readback"]["physical_ranges"]
                == ["0x0000B582:66", "0x0000FF83:2"]
            and value["authorization"] == {
                "contact_authorized": False, "D1_D5_open": False,
                "dry_run_only": True}, "progress session choreography drift")
    runner = RUNNER.read_text(encoding="utf-8")
    require("only dry-run is available" in runner
            and "CONTACT-NOT-AUTHORIZED" in runner
            and not any(token in runner for token in (
                "mega65_ftp", "m65 ", "m65\"", "-t1", "--memsave", "sleep ")),
            "dry-run-only runner acquired a device action")
    return {"active_interval_external_actions": 0,
            "final_stop_transitions_after_future_authorization": 1,
            "raw_first_ranges": value["future_readback"]["physical_ranges"],
            "contact_authorized": False}


def producer_model(code: bytes, entry: int, result: int,
                   before: int, transport: int) -> dict[str, Any]:
    """Independent 6502 subset model for the emitted producer bytes."""
    memory = bytearray(65536)
    memory[PRODUCER_C2D:PRODUCER_C2D + len(code)] = code
    memory[COUNTER:COUNTER + 4] = before.to_bytes(4, "little")
    memory[PHASE:ARM + 1] = bytes((0xD0,)) * (ARM + 1 - PHASE)
    memory[RUNTIME_PHASE] = 0x0B; memory[RUNTIME_IMAGE] = 0x05
    memory[RUNTIME_ENTRY:RUNTIME_ENTRY + 2] = (0x0234).to_bytes(2, "little")
    memory[RUNTIME_DESCRIPTOR:RUNTIME_DESCRIPTOR + 2] = (0x0789).to_bytes(2, "little")
    memory[0x10] = result
    pc = entry; a = result; x = 0xCC; p = 0x20; sp = 0xFD
    interruptible: set[tuple[int, bytes]] = set()
    for _ in range(100):
        if not (p & 0x04):
            interruptible.add((int.from_bytes(memory[COUNTER:COUNTER + 4], "little"),
                               bytes(memory[PHASE:TRANSPORT + 1])))
        op = memory[pc]; pc += 1
        if op in (0xAD, 0x8D, 0xEE):
            address = memory[pc] | memory[pc + 1] << 8; pc += 2
            if op == 0xAD:
                a = memory[address]
                p = with_nz(p, a)
            elif op == 0x8D:
                memory[address] = a
            else:
                memory[address] = (memory[address] + 1) & 0xFF
                p = with_nz(p, memory[address])
        elif op == 0xA9:
            a = memory[pc]; pc += 1; p = with_nz(p, a)
        elif op in (0xF0, 0xD0, 0x80):
            delta = memory[pc]; pc += 1
            take = op == 0x80 or (op == 0xF0 and p & 2) or (op == 0xD0 and not p & 2)
            if take: pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif op == 0xAA:
            x = a; p = with_nz(p, x)
        elif op == 0x8A:
            a = x; p = with_nz(p, a)
        elif op == 0x08:
            memory[0x100 + sp] = p; sp = (sp - 1) & 0xFF
        elif op == 0x78:
            p |= 0x04
        elif op == 0x28:
            sp = (sp + 1) & 0xFF; p = memory[0x100 + sp]
        elif op == 0xEA:
            pass
        elif op == 0x60:
            break
        else:
            raise RingError(f"unmodeled producer opcode 0x{op:02x} at 0x{pc-1:04x}")
    else:
        raise RingError("producer model did not return")
    after = before if result == 0 else (before + 1) & 0xFFFFFFFF
    require(int.from_bytes(memory[COUNTER:COUNTER + 4], "little") == after
            and a == result and x == result and sp == 0xFD and not (p & 0x04),
            "producer execution result/register contract drift")
    if result:
        expected_tuple = bytes((0x0B, 0x05, 0x34, 0x02, 0x89, 0x07, transport))
        require(bytes(memory[PHASE:TRANSPORT + 1]) == expected_tuple,
                "producer phase/ordinal tuple drift")
        old_tuple = bytes((0xD0,)) * 7
        observed = sorted((count, state.hex())
                          for count, state in interruptible)
        require(interruptible <= {(before, old_tuple), (after, expected_tuple)},
                f"IRQ can see torn producer state: {observed}")
    else:
        require(bytes(memory[PHASE:TRANSPORT + 1]) == bytes((0xD0,)) * 7,
                "failed read changed progress tuple")
    return {"entry": f"0x{entry:04x}", "result": result,
            "before": before, "after": after,
            "interruptible_states": len(interruptible),
            "torn_interruptible_states": 0}


def producer_vectors(code: bytes) -> list[dict[str, Any]]:
    rows = [producer_model(code, PRODUCER_C2D, result, before, 0)
            for result in (0, 1)
            for before in (0, 0xFF, 0xFFFF, 0xFFFFFF, 0xFFFFFFFF)]
    rows += [producer_model(code, PRODUCER_SHELF, result, before, 1)
             for result in (0, 1)
             for before in (0, 0xFFFFFFFF)]
    require(len(rows) == 14, "producer execution vector count drift")
    return rows


def sampler_model(code: bytes, frame_lo: int, frame_hi: int,
                  counter: int) -> dict[str, Any]:
    """Execute the emitted sampler and check its real commit-last layout."""
    memory = bytearray(65536)
    memory[SAMPLER:SAMPLER + len(code)] = code
    memory[COUNTER:COUNTER + 4] = counter.to_bytes(4, "little")
    memory[PHASE:TRANSPORT + 1] = bytes((7, 3, 0x34, 0x02, 0x89, 0x07, 1))
    memory[ARM] = ARM_VALUE; memory[FRAME_LO] = frame_lo; memory[FRAME_HI] = frame_hi
    memory[BREAK_SAMPLE] = 0x80
    memory[SLOTS:SLOTS + SLOT_BYTES * SLOT_COUNT] = bytes((0xD7,)) * (SLOT_BYTES * SLOT_COUNT)
    pc = SAMPLER; a = 0; x = 0; y = 0; p = 0x20
    writes: list[int] = []
    for _ in range(300):
        op = memory[pc]; pc += 1
        if op in (0xAD, 0xB9, 0x9D, 0x9E):
            address = memory[pc] | memory[pc + 1] << 8; pc += 2
            if op == 0xAD:
                a = memory[address]; p = with_nz(p, a)
            elif op == 0xB9:
                a = memory[(address + y) & 0xFFFF]
                p = with_nz(p, a)
            elif op == 0x9D:
                target = (address + x) & 0xFFFF; memory[target] = a; writes.append(target)
            else:
                target = (address + x) & 0xFFFF; memory[target] = 0; writes.append(target)
        elif op in (0xA9, 0xA0, 0xA2, 0x29, 0xC0, 0xC9):
            value = memory[pc]; pc += 1
            if op == 0xA9: a = value; p = with_nz(p, a)
            elif op == 0xA0: y = value; p = with_nz(p, y)
            elif op == 0xA2: x = value; p = with_nz(p, x)
            elif op == 0x29: a &= value; p = with_nz(p, a)
            elif op == 0xC0: p = (p | 2) if y == value else (p & ~2)
            else: p = (p | 2) if a == value else (p & ~2)
        elif op in (0xF0, 0xD0):
            delta = memory[pc]; pc += 1
            take = (op == 0xF0 and p & 2) or (op == 0xD0 and not p & 2)
            if take: pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif op == 0xE8:
            x = (x + 1) & 0xFF; p = with_nz(p, x)
        elif op == 0xC8:
            y = (y + 1) & 0xFF; p = with_nz(p, y)
        elif op == 0xEA:
            pass
        elif op == 0x60:
            break
        else:
            raise RingError(f"unmodeled sampler opcode 0x{op:02x} at 0x{pc-1:04x}")
    else:
        raise RingError("sampler model did not return")
    sampled = frame_lo == 0 and frame_hi & 7 == 0
    if sampled:
        index = (frame_hi >> 3) & 3; start = SLOTS + index * SLOT_BYTES
        expected = (counter.to_bytes(4, "little")
                    + bytes((7, 3, 0x34, 0x02, 0x89, 0x07, 1, frame_hi, COMMIT)))
        require(bytes(memory[start:start + SLOT_BYTES]) == expected
                and writes[0] == start + SLOT_BYTES - 1
                and writes[-1] == start + SLOT_BYTES - 1,
                "sampler commit-last execution drift")
    else:
        require(not writes, "non-sample frame changed ring")
    require(a == 0x80 and p & 0x80, "displaced IRQ LDA/N flag not replayed")
    return {"frame_lo": frame_lo, "frame_hi": frame_hi,
            "sampled": sampled, "writes": len(writes)}


def sampler_vectors(code: bytes) -> list[dict[str, Any]]:
    rows = [sampler_model(code, 0, frame, 0x12345678)
            for frame in (0, 8, 16, 24)]
    rows += [sampler_model(code, 1, 8, 7), sampler_model(code, 0, 9, 7)]
    require([row["sampled"] for row in rows] == [True] * 4 + [False, False],
            "sampler execution vector drift")
    return rows


def slot(counter: int, phase: int, image: int, entry: int,
         descriptor: int, transport: int, frame_hi: int,
         commit: int = COMMIT) -> bytes:
    return (counter.to_bytes(4, "little") + bytes((phase, image))
            + entry.to_bytes(2, "little") + descriptor.to_bytes(2, "little")
            + bytes((transport, frame_hi, commit)))


def accepted_slots(raw: bytes, final_frame_hi: int) -> list[dict[str, int]]:
    require(len(raw) == SLOT_BYTES * SLOT_COUNT, "ring read width drift")
    rows: list[dict[str, int]] = []
    for offset in range(0, len(raw), SLOT_BYTES):
        item = raw[offset:offset + SLOT_BYTES]
        if item[12] != COMMIT:
            continue
        require(item[11] & (SAMPLE_HIGH_STRIDE - 1) == 0,
                "committed slot has impossible sample frame")
        rows.append({"offset": offset,
                     "counter": int.from_bytes(item[0:4], "little"),
                     "phase": item[4], "image": item[5],
                     "entry_or_publication": int.from_bytes(item[6:8], "little"),
                     "descriptor_ordinal": int.from_bytes(item[8:10], "little"),
                     "transport": item[10], "frame_hi": item[11],
                     "age": (final_frame_hi - item[11]) & 0xFF})
    rows.sort(key=lambda row: row["age"])
    require(len(rows) >= 2 and rows[1]["age"] - rows[0]["age"] == 8,
            "reader lacks two consecutive committed slots")
    return rows


def reader_vectors() -> list[dict[str, Any]]:
    raw = (slot(100, 3, 0, 10, 20, 1, 0xF8)
           + slot(200, 4, 1, 11, 21, 1, 0x00)
           + slot(300, 5, 2, 12, 22, 0, 0x08)
           + slot(400, 6, 3, 13, 23, 0, 0x10))
    newest = accepted_slots(raw, 0x12)[:2]
    require([row["counter"] for row in newest] == [400, 300],
            "latest ring-pair selection drift")
    torn = bytearray(raw); torn[3 * SLOT_BYTES + 12] = 0
    fallback = accepted_slots(bytes(torn), 0x12)[:2]
    require([row["counter"] for row in fallback] == [300, 200],
            "commit-last torn-slot fallback drift")
    return [{"name": "latest-consecutive-pair", "rows": newest},
            {"name": "torn-newest-falls-back", "rows": fallback}]


def executable_mutations(producer: bytes, sampler: bytes) -> dict[str, str]:
    rejected: dict[str, str] = {}

    no_sei = bytearray(producer)
    common = no_sei.index(bytes((0x08, 0x78, 0x8D)))
    no_sei[common + 1] = 0xEA
    try:
        producer_model(bytes(no_sei), PRODUCER_C2D, 1, 0xFF, 0)
    except RingError as error:
        rejected["producer-state-write-with-IRQ-enabled"] = str(error)
    else:
        raise RingError("producer SEI mutation survived")

    no_commit_clear = bytearray(sampler)
    marker = b"\x9e" + u16(SLOTS + SLOT_BYTES - 1)
    at = no_commit_clear.index(marker)
    no_commit_clear[at:at + 3] = b"\xea\xea\xea"
    if marker not in no_commit_clear:
        rejected["sampler-does-not-invalidate-before-payload"] = "commit invalidation absent"
    else:
        raise RingError("sampler invalidation mutation survived")

    no_displaced_load = bytearray(sampler)
    tail = b"\xad" + u16(BREAK_SAMPLE) + b"\x60"
    at = no_displaced_load.index(tail)
    no_displaced_load[at:at + 3] = b"\xa9\x00\xea"
    try:
        sampler_model(bytes(no_displaced_load), 0, 8, 1)
    except RingError as error:
        rejected["sampler-drops-displaced-IRQ-load"] = str(error)
    else:
        raise RingError("displaced IRQ-load mutation survived")

    torn = bytearray(slot(1, 1, 1, 1, 1, 1, 0, 0)
                     + slot(2, 2, 2, 2, 2, 1, 8)
                     + bytes(SLOT_BYTES * 2))
    try:
        accepted_slots(bytes(torn), 9)
    except RingError as error:
        rejected["reader-accepts-torn-uncommitted-slot"] = str(error)
    else:
        raise RingError("torn ring mutation survived")

    narrow_wrap = (0xFFFFFFFF + 1) & 0xFFFF
    if narrow_wrap == 0:
        rejected["16-bit-counter-ABA"] = "16-bit counter wrapped inside one busy phase"
    else:
        raise RingError("16-bit ABA mutation did not reproduce")

    source_less = bytearray(DIAG_WINDOW.read_bytes())
    source_less[0xE06D - WINDOW_BASE:0xE070 - WINDOW_BASE] = b"\x20" + u16(SAMPLER)
    edges = []
    for index in range(len(source_less) - 2):
        if source_less[index] in (0x20, 0x4C) \
                and int.from_bytes(source_less[index + 1:index + 3], "little") == SAMPLER:
            edges.append(WINDOW_BASE + index)
    if edges != [IRQ_SAMPLE_CALL]:
        rejected["sampler-reachable-from-source-less-guard"] = str([hex(x) for x in edges])
    else:
        raise RingError("source-less sampler edge mutation survived")

    require(len(rejected) == 6, "executable progress mutation count drift")
    return rejected


def build_all() -> dict[str, Any]:
    cpu = load(CPU_RECEIPT); granularity = load(GRANULARITY)
    ownership = load(OWNERSHIP); media_receipt = load(MEDIA_RECEIPT)
    require(cpu["status"].endswith("RING-STILL-REQUIRED")
            and cpu["library_load_sources"]["reads_in_proven_CPU_domain"] == 0,
            "CPU reconciliation authority absent")
    require(granularity["progress_ring_commission"]["built"] is False
            and granularity["progress_ring_commission"]["contact_authorized"] is False,
            "granularity predecessor boundary drift")
    gap = ownership["facts"]["durable_witness"]["containing_gap"]
    require(gap == {"start": "0xb582", "end_exclusive": "0xb5c4", "bytes": 66}
            and ownership["facts"]["durable_witness"]
                ["disjoint_from_all_post_ownership_owners"] is True,
            "owner-free Bank-0 slot authority drift")
    require(media_receipt["media"]["product_D81"] == bind(CONTROL_D81)
            and media_receipt["media"]["library_D81"] == bind(LIBRARY_D81),
            "Link-106 same-world media authority drift")
    choreography = session_contract()

    layout = patched_images()
    medium = build_medium(layout)
    truth = ElfTruth.read(DIAG_ELF, llvm_readobj=READOBJ, include_section_data=True)
    edges = {"c2d": executable_edges(truth, PRODUCER_C2D),
             "shelf": executable_edges(truth, PRODUCER_SHELF),
             "sampler": executable_edges(truth, SAMPLER)}
    require(edges["c2d"] == [{"section": ".lisp65_c2_kernal_window.c2_resident",
                              "pc": "0xe32a", "opcode": "JMP"}]
            and edges["shelf"] == [{"section": ".lisp65_c2_kernal_window.c2_resident",
                                    "pc": "0xe851", "opcode": "JMP"}]
            and edges["sampler"] == [{"section": ".lisp65_c2_kernal_window.irq_handler",
                                      "pc": "0xe053", "opcode": "JSR"}]
            and truth.section_bytes(".text")[ABORT_CALL - truth.section(".text").address:
                                                   ABORT_CALL - truth.section(".text").address + 3]
                == b"\xea\xea\xea",
            "diagnostic executable-edge closure drift")

    deployment = {
        "status": "HOST-GREEN; NON-PROMOTABLE; CONTACT-NOT-AUTHORIZED",
        "product_D81": bind(DIAG_D81), "library_D81": bind(LIBRARY_D81),
        "diagnostic_PRG": bind(DIAG_PRG), "diagnostic_ELF": bind(DIAG_ELF),
        "diagnostic_window": bind(DIAG_WINDOW),
        "state": {"physical_range": "0x0000B582..0x0000B5C3",
                  "counter": "0xB582..0xB585", "arm": "0xB58D",
                  "slots": "0xB58E..0xB5C1", "slot_bytes": SLOT_BYTES,
                  "slot_count": SLOT_COUNT},
        "future_contact": {"authorized": False,
                           "runner_action_available": "dry-run-only",
                           "active_phase_external_observations": 0,
                           "final_stop_transitions": 1,
                           "readback": "physical Bank-0 0x0000B582:66 and 0x0000FF83:2 raw-first"},
    }
    write_json(DEPLOY, deployment)
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; TARGET-SELF-SAMPLING-RING-ARMED; CONTACT-NOT-AUTHORIZED",
        "authority": git_authority(),
        "inputs": {"CPU_reconciliation": bind(CPU_RECEIPT),
                   "granularity_review": bind(GRANULARITY),
                   "owner_free_inventory": bind(OWNERSHIP),
                   "Link106_media": bind(MEDIA_RECEIPT),
                   "control_ELF": bind(CONTROL_ELF),
                   "control_PRG": bind(CONTROL_PRG),
                   "control_D81": bind(CONTROL_D81)},
        "identity": {"promotable": False, "product_candidate_bytes_changed": 0,
                     "product_links": 0, "WPLTO_runs": 0,
                     "hardware_contacts": 0,
                     "enumerated_delta_roles": ["lisp65.prg", "window.bin",
                                                "boot.id", "autoboot.c65"],
                     "control_bytes_outside_delta_byteidentical": True},
        "placement": {"owner_free_state": ["0xb582", "0xb5c4"],
                      "active_owner_overlaps": 0,
                      "outside_ownership_validated_regions": True,
                      "producer_carrier": ["0xfe88", "0xfee1"],
                      "sampler_carrier": ["0xfee1", "0xff67"],
                      "retired_edges": {"vm_c2d_byte": "0x77c0->0xfeda safe NIL",
                                        "abort_driver": "0x2dde NOP"}},
        "producer": {"granularity": "one increment per successful logical c2_stream_shelf_read/c2_stream_c2d_read",
                     "expected_full_boot_reads": 346298,
                     "counter": {"address": "0xb582", "bits": 32,
                                 "endianness": "little"},
                     "location_tuple": {"phase": "c2_runtime+42",
                                        "image": "low byte of image_cursor",
                                        "entry_or_publication": "entry_cursor",
                                        "descriptor_ordinal": "resolution_cursor",
                                        "transport": {"0": "C2D Bank-5", "1": "Shelf Attic"}},
                     "atomicity": "PHP; SEI before every state write; PLP only after tuple+counter commit",
                     "vectors": producer_vectors(bytes.fromhex(layout["producer_hex"])),
                     "edges": edges},
        "sampler": {"producer": "owned raster IRQ after VIC-raster proof/ack/frame increment",
                    "sample_every_frames": SAMPLE_FRAMES,
                    "sample_period_seconds": round(SAMPLE_FRAMES / (FRAME_HZ_MILLI / 1000), 6),
                    "no_ABA": {"counter_modulus": 4294967296,
                               "absolute_maximum_dispatches_per_sample_gap": 1576415349,
                               "maximum_is_below_modulus": True,
                               "frame_high_modulus_frames": 65536,
                               "ring_is_continuously_overwritten": True,
                               "reader_uses_final_FF83_FF84_and_two_consecutive_commits": True},
                    "slots": {"start": "0xb58e", "count": 4,
                              "bytes_each": 13, "end_exclusive": "0xb5c2"},
                    "commit_last": True, "invalidates_before_payload": True,
                    "displaced_IRQ_instruction_replayed": "LDA $D613",
                    "IRQ_partition": irq_contract(),
                    "execution_vectors": sampler_vectors(bytes.fromhex(layout["sampler_hex"])),
                    "reader_vectors": reader_vectors()},
        "media": {**medium, "diagnostic_D81": bind(DIAG_D81),
                  "library_D81": bind(LIBRARY_D81)},
        "deployment": bind(DEPLOY), "session_contract": bind(SESSION),
        "runner": bind(RUNNER),
        "choreography": choreography,
        "decision_table": {
            "growing_slots": "LIVE; derive measured logical-read rate and completion estimate",
            "fixed_slots": "NO LOGICAL READ PROGRESS; phase/ordinals name the loop or stall neighborhood",
            "READY": "D1 boot healthy; close the performance question before D2-D5",
            "invalid_or_torn": "INSTRUMENT RED; no product claim"},
        "accounting": {"product_bytes_changed": 0, "hardware_runs": 0,
                       "contact_authorized": False, "D1_D5_open": False},
        "claim_limit": "Host-green, non-promotable diagnostic sibling only. The ring measures successful logical read progress; it does not relax convergence, estimate a device rate before capture, claim a hang, authorize contact, or open D1-D5.",
    }
    audit(receipt)
    receipt["mutations"] = {
        "receipt": mutation_gate(receipt),
        "executable": {"count": 6, "rejected": executable_mutations(
            bytes.fromhex(layout["producer_hex"]),
            bytes.fromhex(layout["sampler_hex"]))},
        "total": 24,
    }
    write_json(RECEIPT, receipt)
    return receipt


def audit(value: dict[str, Any]) -> None:
    require(value["status"]
            == "HOST-GREEN; TARGET-SELF-SAMPLING-RING-ARMED; CONTACT-NOT-AUTHORIZED",
            "ring status drift")
    identity = value["identity"]
    require(identity["promotable"] is False
            and identity["product_candidate_bytes_changed"] == 0
            and identity["hardware_contacts"] == 0,
            "non-promotable identity drift")
    placement = value["placement"]
    require(placement["owner_free_state"] == ["0xb582", "0xb5c4"]
            and placement["active_owner_overlaps"] == 0
            and placement["outside_ownership_validated_regions"] is True,
            "owned state placement drift")
    producer = value["producer"]
    require(producer["expected_full_boot_reads"] == 346298
            and producer["counter"] == {"address": "0xb582", "bits": 32,
                                        "endianness": "little"}
            and producer["atomicity"].startswith("PHP; SEI")
            and all(row["torn_interruptible_states"] == 0
                    for row in producer["vectors"]),
            "producer semantics drift")
    sampler = value["sampler"]
    require(sampler["sample_every_frames"] == 2048
            and sampler["slots"] == {"start": "0xb58e", "count": 4,
                                     "bytes_each": 13,
                                     "end_exclusive": "0xb5c2"}
            and sampler["commit_last"] is True
            and sampler["invalidates_before_payload"] is True
            and sampler["no_ABA"] == {
                "counter_modulus": 4294967296,
                "absolute_maximum_dispatches_per_sample_gap": 1576415349,
                "maximum_is_below_modulus": True,
                "frame_high_modulus_frames": 65536,
                "ring_is_continuously_overwritten": True,
                "reader_uses_final_FF83_FF84_and_two_consecutive_commits": True}
            and sampler["IRQ_partition"]["source_less_edges_to_sampler"] == 0,
            "self-sampler semantics drift")
    require(len(sampler["execution_vectors"]) == 6
            and [row["sampled"] for row in sampler["execution_vectors"]]
                == [True, True, True, True, False, False]
            and len(sampler["reader_vectors"]) == 2,
            "self-sampler executable-vector drift")
    require(value["media"]["shared_roles"] == 11
            and value["media"]["readback"] == "byteidentical",
            "diagnostic media closure drift")
    require(value["accounting"] == {"product_bytes_changed": 0,
                                    "hardware_runs": 0,
                                    "contact_authorized": False,
                                    "D1_D5_open": False},
            "contact/accounting boundary drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "promote-diagnostic": (["identity", "promotable"], True),
        "claim-product-byte": (["identity", "product_candidate_bytes_changed"], 1),
        "move-state-under-owner": (["placement", "owner_free_state"], ["0xc000", "0xc042"]),
        "admit-owner-overlap": (["placement", "active_owner_overlaps"], 1),
        "enter-validated-region": (["placement", "outside_ownership_validated_regions"], False),
        "narrow-counter": (["producer", "counter", "bits"], 16),
        "count-probe-jobs": (["producer", "expected_full_boot_reads"], 2361562),
        "permit-torn-producer": (["producer", "vectors", 0, "torn_interruptible_states"], 1),
        "sample-every-frame": (["sampler", "sample_every_frames"], 1),
        "drop-slot": (["sampler", "slots", "count"], 3),
        "widen-slot": (["sampler", "slots", "bytes_each"], 14),
        "commit-first": (["sampler", "commit_last"], False),
        "skip-invalidation": (["sampler", "invalidates_before_payload"], False),
        "sample-source-less": (["sampler", "IRQ_partition", "source_less_edges_to_sampler"], 1),
        "alter-shared-media": (["media", "shared_roles"], 10),
        "skip-readback": (["media", "readback"], "unchecked"),
        "authorize-contact": (["accounting", "contact_authorized"], True),
        "open-D1-D5": (["accounting", "D1_D5_open"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except RingError as error: rejected[name] = str(error)
        else: raise RingError(f"ring mutation survived: {name}")
    require(len(rejected) == 18, "ring mutation count drift")
    return {"count": len(rejected), "rejected": rejected}


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value["deployment"] == bind(DEPLOY)
            and value["session_contract"] == bind(SESSION)
            and value["runner"] == bind(RUNNER)
            and value["media"]["diagnostic_D81"] == bind(DIAG_D81)
            and value["media"]["library_D81"] == bind(LIBRARY_D81),
            "persisted ring artifact drift")
    window = DIAG_WINDOW.read_bytes()
    producer = window[PRODUCER_C2D - WINDOW_BASE:PRODUCER_LIMIT - WINDOW_BASE]
    sampler = window[SAMPLER - WINDOW_BASE:SAMPLER_LIMIT - WINDOW_BASE]
    require(mutation_gate({k: deepcopy(v) for k, v in value.items()
                           if k != "mutations"})["count"] == 18
            and value["mutations"]["executable"] == {
                "count": 6, "rejected": executable_mutations(producer, sampler)}
            and value["mutations"]["total"] == 24,
            "persisted ring mutations drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = build_all() if args.action == "build" else check()
        print("C2 V2.0 LOADING LIBRARIES PROGRESS RING PASS "
              f"action={args.action} slots=4 mutations={value['mutations']['total']} contact=no")
        return 0
    except (OSError, KeyError, ValueError, RingError,
            subprocess.CalledProcessError) as error:
        print(f"C2 V2.0 LOADING LIBRARIES PROGRESS RING FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
