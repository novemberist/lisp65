#!/usr/bin/env python3
"""Build the authorized current-carrier defstruct diagnostic sister.

The immutable Link-92-r5 product is the control.  This tool derives one
non-promotable sibling without compiling or linking product code.  It combines
the accepted 65-byte R/A/I/G stopped-state record with the target-owned
VM-progress sampler, retargeted to owner-free ordinary RAM.  The G4 KERNAL
window CRC expectation is recomputed from the resulting bytes.
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
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_defstruct_phase_c as PHASE_C  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
AUTHORIZATION_COMMIT = "3b24db25b1cfb70f1a869d80c26230bc4c3b5d0c"
MEDIA_REPAIR_AUTHORIZATION_COMMIT = "6e4d184da9eeb1226b864d4ab91ca7338b99b50a"
PLAN_PATH = "docs/planning/post-v1.4.0-direction-plan.md"
P2_RECEIPT = EVIDENCE / "c2.3-post-v1.4-defstruct-completion-edge-receipt.json"
PHASE_B = EVIDENCE / "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json"
LINK92_RECEIPT = EVIDENCE / "c2.3-v1.12-link92-r5-artifact-completion-replay-receipt.json"
V17 = EVIDENCE / "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json"
V18 = EVIDENCE / "c2.3-v1.8-full-map-phase-a-closure-receipt.json"

BASE = ROOT / "build/c2.3/v1.4.0-candidate-product-link92-r5/final"
CONTROL_PRG = BASE / "lisp65-c2-substitution-linked.prg"
CONTROL_ELF = BASE / "lisp65-c2-substitution-linked.prg.elf"
CONTROL_WINDOW = BASE / "c2-product-kernal-window.bin"
CONTROL_D81 = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5/shared-system/"
    "lisp65-product.d81")
LIBRARY_D81 = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5-split/"
    "defstruct-acceptance/lisp65-library.d81")
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
RUNNER = ROOT / "scripts/c2-defstruct-terminal-ingress-hw.sh"
CONFIG = ROOT / "config/c2-defstruct-terminal-ingress-session.json"

OUT = ROOT / "build/c2.3/defstruct-terminal-ingress-sister-link92"
ART = OUT / "artifacts"
CONTROL_COPY_PRG = ART / "control-link92-r5.prg"
CONTROL_COPY_ELF = ART / "control-link92-r5.elf"
CONTROL_COPY_WINDOW = ART / "control-link92-r5-window.bin"
CONTROL_COPY_D81 = ART / "control-link92-r5-product.d81"
DIAG_PRG = ART / "diagnostic-terminal-ingress.prg"
DIAG_ELF = ART / "diagnostic-terminal-ingress.elf"
DIAG_WINDOW = ART / "diagnostic-terminal-ingress-window.bin"
DIAG_DESCRIPTOR = ART / "diagnostic-boot.id"
DIAG_STAGER = ART / "diagnostic-autoboot.c65"
DIAG_STAGER_MAP = ART / "diagnostic-autoboot.c65.map"
DIAG_STAGER_BUILD = ART / "diagnostic-stager-build"
DIAG_D81 = OUT / "diagnostic-terminal-ingress-product.d81"
RECORD_RESET = ART / "record-reset.bin"
RECORD_ARM = ART / "record-arm.bin"
PROGRESS_RESET = ART / "progress-state-and-ring-reset.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = EVIDENCE / "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json"

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-terminal-ingress-sister-v1"
RECORDED_ON = "2026-08-09"
PRG_LOAD = 0x2001
WINDOW_BASE = 0xE000
WINDOW_BYTES = 8192

# The Link-92 geometry closes these gaps from both sides.  They are not
# budgets: every byte below is owned by this one non-promotable identity.
CODE0 = 0xB3B0
CODE0_LIMIT = 0xB4A3
PROGRESS = 0xB582
PROGRESS_LIMIT = 0xB5C4
CODE1 = 0xBFF7
RECORD = 0xC03F
RECORD_LIMIT = 0xC080

PRODUCER = PROGRESS
PRODUCER_BYTES = 42
STATE = PRODUCER + PRODUCER_BYTES
STATE_BYTES = 8
COUNTER = STATE
OWNER = STATE + 4
ARM = STATE + 6
SLOTS = STATE + STATE_BYTES
SLOT_BYTES = 8
SLOT_COUNT = 2
SLOTS_BYTES = SLOT_BYTES * SLOT_COUNT

VM_HOOK = 0x467D
POLL = 0xBFEA
OWNER_OFF = 0xB9B2
ABORT_CALL = 0x2DDE
IRQ_SAMPLE_CALL = 0xE053
SAMPLER = 0xFEE1
SAMPLER_LIMIT = 0xFF40
FRAME_LO = 0xFF83
FRAME_HI = 0xFF84
BREAK_SAMPLE = 0xD613
COMMIT = 0xA5
SAMPLE_HIGH_STRIDE = 8
SAMPLE_FRAMES = SAMPLE_HIGH_STRIDE * 256
FRAME_HZ_MILLI = 51966

CRC_HIGH = 0xB4F4
CRC_LOW = 0xB4FA

SECTION_CODE0 = ".lisp65_post_v14_defstruct_code0"
SECTION_PROGRESS = ".lisp65_post_v14_defstruct_progress"
SECTION_CODE1 = ".lisp65_post_v14_defstruct_code1"
SECTION_RECORD = ".lisp65_post_v14_defstruct_record"

STATE_RESET = bytes((0, 0, 0, 0, 0xD2, 0xD3, COMMIT, 0xD4))
SLOT_RESET = bytes((0xD0, 0xD1, 0xD2, 0xD3,
                    0xD4, 0xD5, 0xD6, 0x00)) * SLOT_COUNT


class SisterError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SisterError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")
    return result.stdout


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"],
               "resolve authorization").strip()
    raw = subprocess.run(["git", "show", f"{full}:{path}"], cwd=ROOT,
                         stdout=subprocess.PIPE, check=True).stdout
    return {"authority": "git-blob", "commit": full, "path": path,
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
            value = (((value << 1) ^ 0x1021) & 0xFFFF
                     if value & 0x8000 else (value << 1) & 0xFFFF)
    return value


def replace(raw: bytearray, offset: int, before: bytes, after: bytes,
            label: str) -> None:
    require(len(before) == len(after), f"fixed-size patch required: {label}")
    require(raw[offset:offset + len(before)] == before,
            f"patch authority drift: {label}")
    raw[offset:offset + len(after)] = after


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
            source_after = self.origin + offset + 1
            delta = self.labels[label] - source_after
            require(-128 <= delta <= 127, f"branch out of range: {label}")
            self.raw[offset] = delta & 0xFF
        return bytes(self.raw)


def producer_bytes() -> bytes:
    """Atomic VM-dispatch counter plus owner snapshot."""
    a = Asm(PRODUCER)
    a.emit(0x08, 0x78, 0x48)             # PHP; SEI; PHA
    a.absolute(0xAD, OWNER_OFF); a.absolute(0x8D, OWNER)
    a.absolute(0xAD, OWNER_OFF + 1); a.absolute(0x8D, OWNER + 1)
    a.absolute(0xEE, COUNTER); a.branch(0xD0, "done")
    a.absolute(0xEE, COUNTER + 1); a.branch(0xD0, "done")
    a.absolute(0xEE, COUNTER + 2); a.branch(0xD0, "done")
    a.absolute(0xEE, COUNTER + 3)
    a.label("done")
    a.emit(0x68, 0x28)                   # PLA; PLP
    a.absolute(0xAE, POLL)               # displaced LDX; owns final N/Z
    a.emit(0x60)
    code = a.finish()
    require(len(code) == 39, f"producer size drift: {len(code)}")
    return code + b"\xea" * (PRODUCER_BYTES - len(code))


def sampler_bytes() -> bytes:
    """Owned raster IRQ snapshot into two ordinary-RAM commit-last slots."""
    a = Asm(SAMPLER)
    a.absolute(0xAD, ARM); a.emit(0xC9, COMMIT); a.branch(0xD0, "done")
    a.absolute(0xAD, FRAME_LO); a.branch(0xD0, "done")
    a.absolute(0xAD, FRAME_HI); a.emit(0x29, SAMPLE_HIGH_STRIDE - 1)
    a.branch(0xD0, "done")
    a.absolute(0xAD, FRAME_HI); a.emit(0x29, SLOT_BYTES); a.emit(0xAA)
    a.absolute(0x9E, SLOTS + 7)           # commit=0 before payload
    for index in range(4):
        a.absolute(0xAD, COUNTER + index); a.absolute(0x9D, SLOTS + index)
    for index in range(2):
        a.absolute(0xAD, OWNER + index); a.absolute(0x9D, SLOTS + 4 + index)
    a.absolute(0xAD, FRAME_HI); a.absolute(0x9D, SLOTS + 6)
    a.emit(0xA9, COMMIT); a.absolute(0x9D, SLOTS + 7)
    a.label("done")
    a.absolute(0xAD, BREAK_SAMPLE)        # displaced owned-IRQ load
    a.emit(0x60)
    code = a.finish()
    require(len(code) <= SAMPLER_LIMIT - SAMPLER,
            f"sampler does not fit retired abort head: {len(code)}")
    return code + b"\xea" * (SAMPLER_LIMIT - SAMPLER - len(code))


def record_patch(phase_b: dict[str, Any]) -> dict[str, Any]:
    config = {"addresses": {
        "code0": CODE0, "code0_limit": CODE0_LIMIT,
        "code1": CODE1, "code1_limit": RECORD,
        "record": RECORD, "record_limit": RECORD_LIMIT,
        "refill_hook": 0x47C5, "first_error_hook": 0x8EB7,
        "fail_closed_hook": 0xE08B, "entry_hook": 0x202C,
        "entry_routine": RECORD, "entry_stamp_offset": 59,
        "entry_stamp_value": 0x44,
    }}
    return PHASE_C.build_patch(config, phase_b)


def exact_ranges(before: bytes, after: bytes, *, base: int) -> list[dict[str, Any]]:
    require(len(before) == len(after), "identity comparison requires equal size")
    changed = [i for i, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    rows: list[dict[str, Any]] = []
    if not changed:
        return rows
    start = prior = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != prior + 1:
            rows.append({"start": f"0x{base + start:04x}",
                         "bytes": prior - start + 1,
                         "before": before[start:prior + 1].hex(),
                         "after": after[start:prior + 1].hex()})
            start = current
        prior = current
    return rows


def allocated_gap(truth: ElfTruth, start: int, end: int) -> dict[str, Any]:
    overlaps = [row.name for row in truth.sections
                if row.bytes and "SHF_ALLOC" in row.flags
                and row.address < end and row.address + row.bytes > start]
    require(not overlaps, f"diagnostic owner-free interval occupied: {overlaps}")
    prior = max((row for row in truth.sections if row.bytes
                 and "SHF_ALLOC" in row.flags
                 and row.address + row.bytes <= start),
                key=lambda row: row.address + row.bytes)
    after = min((row for row in truth.sections if row.bytes
                 and "SHF_ALLOC" in row.flags and row.address >= end),
                key=lambda row: row.address)
    require(prior.address + prior.bytes == start and after.address == end,
            f"owner-free interval boundaries drift: {start:04x}-{end:04x}")
    return {"start": f"0x{start:04x}", "end_exclusive": f"0x{end:04x}",
            "bytes": end - start, "prior_owner": prior.name,
            "next_owner": after.name, "active_overlaps": 0}


def session_contract(value: dict[str, Any]) -> None:
    require(value.get("format")
            == "lisp65-c2.3-post-v1.4-defstruct-terminal-ingress-session-v1"
            and value.get("status") == "owner-authorized-host-preparation-not-run"
            and value.get("authorization_commit") == AUTHORIZATION_COMMIT,
            "bundled session contract identity drift")
    require(value.get("order") == [
        "Link93-trace-acceptance",
        "Link92-defstruct-terminal-ingress-sister",
        "standing-trailing-peeks",
    ], "bundled session dependency order drift")
    row = value["defstruct"]
    require(row == {
        "product_medium": DIAG_D81.relative_to(ROOT).as_posix(),
        "library_medium": LIBRARY_D81.relative_to(ROOT).as_posix(),
        "forms": ["(require (quote defstruct))", "(defstruct point x y)"],
        "quiet_floor_seconds": 180,
        "physical_owner_keyboard_only": True,
        "monitor_accesses_during_active_form": 0,
        "screen_polls_during_active_form": 0,
        "post_form_stops": 1,
        "read_set": [
            "register-tuple-and-mapping",
            "65-byte-R/A/I/G-record-three-stable-copies",
            "VM-progress-producer-state-and-two-ring-slots",
            "C2D-reset-domain", "Bank-2-source", "physical-KERNAL-window",
        ],
    }, "bundled defstruct session row drift")
    require("No Link-93 hardware" in value.get("claim_limit", "")
            and "v1.5 scope" in value["claim_limit"],
            "bundled session claim limit broadened")


def apply_prg(base: bytes, patch: dict[str, Any], producer: bytes,
              sampler: bytes) -> tuple[bytes, bytes, int]:
    require(int.from_bytes(base[:2], "little") == PRG_LOAD,
            "Link-92 PRG load address drift")
    result = bytearray(base)
    for start, payload, label in (
        (CODE0, patch["code0"], "R/A/I/G code0"),
        (PROGRESS, producer + STATE_RESET + SLOT_RESET, "progress arena"),
        (CODE1, patch["code1"], "R/A/I/G code1"),
        (RECORD, patch["record_boot"], "R/A/I/G record"),
    ):
        offset = prg_offset(start)
        require(set(result[offset:offset + len(payload)]) <= {0},
                f"diagnostic arena is not owner-free zero space: {label}")
        result[offset:offset + len(payload)] = payload
    for row in patch["patches"]:
        if row["carrier"] != "resident-prg":
            continue
        replace(result, prg_offset(row["address"]), bytes.fromhex(row["before"]),
                bytes.fromhex(row["after"]), row["name"])
    replace(result, prg_offset(VM_HOOK), b"\xae" + u16(POLL),
            b"\x20" + u16(PRODUCER), "VM progress producer hook")
    replace(result, prg_offset(ABORT_CALL), b"\x20" + u16(SAMPLER),
            b"\xea\xea\xea", "retire abort-driver edge in diagnostic")

    window = bytearray(CONTROL_WINDOW.read_bytes())
    fail = next(row for row in patch["patches"]
                if row["name"] == "fail-closed-record-hook")
    replace(window, fail["address"] - WINDOW_BASE,
            bytes.fromhex(fail["before"]), bytes.fromhex(fail["after"]),
            fail["name"])
    replace(window, IRQ_SAMPLE_CALL - WINDOW_BASE, b"\xad" + u16(BREAK_SAMPLE),
            b"\x20" + u16(SAMPLER), "owned raster sampler call")
    replace(window, SAMPLER - WINDOW_BASE,
            bytes(window[SAMPLER - WINDOW_BASE:SAMPLER_LIMIT - WINDOW_BASE]),
            sampler, "target-owned sampler")
    new_crc = crc16(bytes(window))
    old_crc = crc16(CONTROL_WINDOW.read_bytes())
    require(result[prg_offset(CRC_HIGH)] == old_crc >> 8
            and result[prg_offset(CRC_LOW)] == old_crc & 0xFF,
            "Link-92 completed PRG/G4 authority drift")
    result[prg_offset(CRC_HIGH)] = new_crc >> 8
    result[prg_offset(CRC_LOW)] = new_crc & 0xFF
    return bytes(result), bytes(window), new_crc


def add_section_args(paths: dict[str, Path], addresses: dict[str, int]) -> list[str]:
    args: list[str] = []
    for name in (SECTION_CODE0, SECTION_PROGRESS, SECTION_CODE1, SECTION_RECORD):
        args += [f"--add-section={name}={paths[name]}"]
        flags = "alloc,load,readonly,code" if name != SECTION_RECORD else "alloc,load,data"
        args += [f"--set-section-flags={name}={flags}"]
    return args


def patch_elf(patch: dict[str, Any], progress: bytes, sampler: bytes,
              new_crc: int) -> None:
    truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    updates: dict[str, bytes] = {}
    text_name = ".text"
    text = bytearray(truth.section_bytes(text_name)); text_base = truth.section(text_name).address
    for row in patch["patches"]:
        if row["carrier"] == "resident-prg":
            replace(text, row["address"] - text_base, bytes.fromhex(row["before"]),
                    bytes.fromhex(row["after"]), f"ELF {row['name']}")
    replace(text, VM_HOOK - text_base, b"\xae" + u16(POLL),
            b"\x20" + u16(PRODUCER), "ELF VM progress producer hook")
    replace(text, ABORT_CALL - text_base, b"\x20" + u16(SAMPLER),
            b"\xea\xea\xea", "ELF retire abort-driver edge")
    updates[text_name] = bytes(text)

    irq_name = ".lisp65_c2_kernal_window.irq_handler"
    irq = bytearray(truth.section_bytes(irq_name)); irq_base = truth.section(irq_name).address
    replace(irq, IRQ_SAMPLE_CALL - irq_base, b"\xad" + u16(BREAK_SAMPLE),
            b"\x20" + u16(SAMPLER), "ELF owned raster sampler call")
    updates[irq_name] = bytes(irq)

    fail_name = ".lisp65_c2_kernal_window.map_switch_and_guards"
    fail_section = bytearray(truth.section_bytes(fail_name))
    fail_base = truth.section(fail_name).address
    fail = next(row for row in patch["patches"]
                if row["name"] == "fail-closed-record-hook")
    replace(fail_section, fail["address"] - fail_base,
            bytes.fromhex(fail["before"]), bytes.fromhex(fail["after"]),
            "ELF fail-closed record hook")
    updates[fail_name] = bytes(fail_section)

    reopen = ".lisp65_c2_kernal_window.reopen_gap1"
    reopen_data = bytearray(truth.section_bytes(reopen)); reopen_base = truth.section(reopen).address
    replace(reopen_data, SAMPLER - reopen_base,
            bytes(reopen_data[SAMPLER - reopen_base:SAMPLER_LIMIT - reopen_base]),
            sampler, "ELF target-owned sampler")
    updates[reopen] = bytes(reopen_data)

    handoff = ".lisp65_c2_kernal_handoff"
    handoff_data = bytearray(truth.section_bytes(handoff)); handoff_base = truth.section(handoff).address
    # The completed PRG contains the finalized 9F16 operands; the preserved
    # final ELF is the pre-completion A55A authority.  The sibling ELF must
    # describe the actual sibling PRG, so both operands are deliberately
    # replaced from that recorded ELF state.
    replace(handoff_data, CRC_HIGH - handoff_base, bytes((0xA5,)),
            bytes((new_crc >> 8,)), "ELF G4 CRC high")
    replace(handoff_data, CRC_LOW - handoff_base, bytes((0x5A,)),
            bytes((new_crc & 0xFF,)), "ELF G4 CRC low")
    updates[handoff] = bytes(handoff_data)

    ART.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for index, (name, payload) in enumerate({
        **updates,
        SECTION_CODE0: patch["code0"],
        SECTION_PROGRESS: progress,
        SECTION_CODE1: patch["code1"],
        SECTION_RECORD: patch["record_boot"],
    }.items()):
        path = ART / f"elf-section-{index}.bin"
        path.write_bytes(payload); paths[name] = path
    args = [str(OBJCOPY)]
    for name in updates:
        args += [f"--update-section={name}={paths[name]}"]
    args += add_section_args(paths, {
        SECTION_CODE0: CODE0, SECTION_PROGRESS: PROGRESS,
        SECTION_CODE1: CODE1, SECTION_RECORD: RECORD})
    symbols = {
        "lisp65_post_v14_defstruct_fail_capture": CODE0,
        "lisp65_post_v14_defstruct_progress_producer": PRODUCER,
        "lisp65_post_v14_defstruct_progress_state": STATE,
        "lisp65_post_v14_defstruct_progress_slots": SLOTS,
        "lisp65_post_v14_defstruct_refill_continue": CODE1,
        "lisp65_post_v14_defstruct_record": RECORD,
        "lisp65_post_v14_defstruct_sampler": SAMPLER,
    }
    for name, address in symbols.items():
        flags = "global,object" if name.endswith(("state", "slots", "record")) \
            else "global,function"
        args += [f"--add-symbol={name}=0x{address:x},{flags}"]
    args += [str(CONTROL_ELF), str(DIAG_ELF)]
    run(args, "derive diagnostic sister ELF")
    PHASE_C.patch_elf_section_addresses(DIAG_ELF, {
        SECTION_CODE0: CODE0, SECTION_PROGRESS: PROGRESS,
        SECTION_CODE1: CODE1, SECTION_RECORD: RECORD})


def medium_roles(image: Path, directory: Path) -> dict[str, dict[str, Any]]:
    names = ["autoboot.c65", "boot.id", "code.bin", "c2d.bin",
             "bootstage.bin", "session.bin", "shelf.bin", "boot.bin",
             "region1.bin", "window.bin", "lisp65.prg", "profile",
             "ide", "idex", "m65d"]
    directory.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict[str, Any]] = {}
    for name in names:
        output = directory / name.replace(".", "-")
        if output.exists():
            output.unlink()
        run(["c1541", "-attach", str(image), "-read", name, str(output)],
            f"extract {name} from {image.name}")
        rows[name] = bind(output)
    return rows


def role_paths(rows: dict[str, dict[str, Any]]) -> dict[str, Path]:
    return {name: ROOT / row["path"] for name, row in rows.items()}


def descriptor_rows(
    descriptor: bytes, payloads: dict[str, Path],
) -> tuple[list[dict[str, Any]], int, int]:
    require(
        len(descriptor) == MEDIA.DESCRIPTOR_BYTES
        and descriptor[:4] == b"L65B"
        and tuple(descriptor[4:8]) == (
            2, MEDIA.HEADER_BYTES, MEDIA.RECORDS, MEDIA.RESTAGE_LIMIT),
        "donor media descriptor envelope drift",
    )
    rows: list[dict[str, Any]] = []
    for index in range(MEDIA.RECORDS):
        start = MEDIA.HEADER_BYTES + index * MEDIA.RECORD_BYTES
        record = descriptor[start:start + MEDIA.RECORD_BYTES]
        role, flags, name_length, reserved = record[:4]
        destination = struct.unpack_from("<I", record, 4)[0]
        name = record[16:16 + name_length].decode("ascii").lower()
        require(
            reserved == 0 and role == index + 1 and name in payloads,
            f"donor descriptor layout drift at role {index + 1}",
        )
        path = payloads[name]
        require(path.is_file() and not path.is_symlink(),
                f"packed role absent: {name}")
        raw = path.read_bytes()
        rows.append({
            "role_id": role,
            "flags": flags,
            "name": name,
            "destination": destination,
            "bytes": len(raw),
            "crc32": MEDIA.crc32(raw),
            "path": path,
        })
    return (
        rows,
        struct.unpack_from("<I", descriptor, 8)[0],
        struct.unpack_from("<I", descriptor, 12)[0],
    )


def target_descriptor_check(
    descriptor: bytes, rows: list[dict[str, Any]],
    *, descriptor_build_id: int, stager_build_id: int,
) -> None:
    require(stager_build_id == descriptor_build_id,
            "cold stager and BOOT.ID bind different product worlds")
    try:
        MEDIA.parse_descriptor(descriptor, descriptor_build_id, rows)
    except MEDIA.MediaError as error:
        raise SisterError(str(error)) from error


def media_contract_mutations(
    donor_descriptor: bytes, donor_build_id: int,
    diagnostic_descriptor: bytes, diagnostic_build_id: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rejected: list[str] = []
    cases = {
        "payload-replaced-contract-inherited": (
            donor_descriptor, donor_build_id, donor_build_id),
        "descriptor-regenerated-stager-inherited": (
            diagnostic_descriptor, diagnostic_build_id, donor_build_id),
    }
    for name, (descriptor, descriptor_id, stager_id) in cases.items():
        try:
            target_descriptor_check(
                descriptor, rows, descriptor_build_id=descriptor_id,
                stager_build_id=stager_id)
        except SisterError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "derived-media contract mutation survived: "
            + ", ".join(sorted(set(cases) - set(rejected))))
    return {"mutations_rejected": len(rejected), "cases": sorted(rejected)}


def build_medium() -> dict[str, Any]:
    control = medium_roles(CONTROL_D81, OUT / "readback-control")
    control_paths = role_paths(control)
    donor_descriptor = control_paths["boot.id"].read_bytes()
    donor_rows, donor_build_id, profile_build_id = descriptor_rows(
        donor_descriptor, control_paths)
    target_descriptor_check(
        donor_descriptor, donor_rows,
        descriptor_build_id=donor_build_id, stager_build_id=donor_build_id)

    payloads = dict(control_paths)
    payloads["lisp65.prg"] = DIAG_PRG
    payloads["window.bin"] = DIAG_WINDOW
    rows, inherited_build_id, inherited_profile_id = descriptor_rows(
        donor_descriptor, payloads)
    require(inherited_build_id == donor_build_id
            and inherited_profile_id == profile_build_id,
            "donor media identity changed while deriving payload rows")
    donor_by_name = {row["name"]: row for row in donor_rows}
    stale_contract = [{
        "name": row["name"],
        "descriptor_crc32": f"0x{donor_by_name[row['name']]['crc32']:08x}",
        "packed_crc32": f"0x{row['crc32']:08x}",
    } for row in rows if row["crc32"] != donor_by_name[row["name"]]["crc32"]]
    require([row["name"] for row in stale_contract]
            == ["window.bin", "lisp65.prg"],
            "historical stale-contract First Red is not reproduced")
    descriptor, build_id = MEDIA.make_descriptor(rows, profile_build_id)
    DIAG_DESCRIPTOR.write_bytes(descriptor)
    target_descriptor_check(
        descriptor, rows, descriptor_build_id=build_id,
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
        "replace diagnostic D81 roles")
    diagnostic = medium_roles(DIAG_D81, OUT / "readback-diagnostic")
    for name in control:
        if name == "lisp65.prg":
            require(diagnostic[name]["sha256"] == sha(DIAG_PRG),
                    "diagnostic PRG role readback drift")
        elif name == "window.bin":
            require(diagnostic[name]["sha256"] == sha(DIAG_WINDOW),
                    "diagnostic window role readback drift")
        elif name == "boot.id":
            require(diagnostic[name]["sha256"] == sha(DIAG_DESCRIPTOR),
                    "diagnostic descriptor role readback drift")
        elif name == "autoboot.c65":
            require(diagnostic[name]["sha256"] == sha(DIAG_STAGER),
                    "diagnostic stager role readback drift")
        else:
            require(diagnostic[name]["sha256"] == control[name]["sha256"],
                    f"unrelated D81 role changed: {name}")
    readback_paths = role_paths(diagnostic)
    readback_descriptor = readback_paths["boot.id"].read_bytes()
    readback_rows, readback_build_id, readback_profile_id = descriptor_rows(
        readback_descriptor, readback_paths)
    require(readback_profile_id == profile_build_id,
            "diagnostic profile identity changed")
    target_descriptor_check(
        readback_descriptor, readback_rows,
        descriptor_build_id=readback_build_id, stager_build_id=build_id)
    contract_mutations = media_contract_mutations(
        donor_descriptor, donor_build_id, descriptor, build_id, rows)
    return {
        "control_roles": control,
        "diagnostic_roles": diagnostic,
        "shared_roles": 11,
        "replaced_payload_roles": ["lisp65.prg", "window.bin"],
        "regenerated_contract_roles": ["autoboot.c65", "boot.id"],
        "contract": {
            "status": "passed-target-equivalent-packed-role-descriptor-check",
            "donor_build_id": f"0x{donor_build_id:08x}",
            "diagnostic_build_id": f"0x{build_id:08x}",
            "profile_build_id": f"0x{profile_build_id:08x}",
            "descriptor": bind(DIAG_DESCRIPTOR),
            "stager": bind(DIAG_STAGER),
            "stager_map": bind(DIAG_STAGER_MAP),
            "stager_gate": stager_gate,
            "packed_roles_checked": len(readback_rows),
            "contract_members_regenerated_after_payload_change": True,
            "historical_first_red": {
                "classification": "payload-replaced-contract-inherited",
                "cold_stager_first_rejected_role": 8,
                "stale_records": stale_contract,
            },
            "mutations": contract_mutations,
        },
    }


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


def derive(*, write_artifacts: bool) -> dict[str, Any]:
    authorization = git_bind(AUTHORIZATION_COMMIT, PLAN_PATH)
    media_repair_authorization = git_bind(
        MEDIA_REPAIR_AUTHORIZATION_COMMIT, PLAN_PATH)
    require("The specified defstruct diagnostic sister is authorized" in
            subprocess.run(["git", "show", f"{AUTHORIZATION_COMMIT}:{PLAN_PATH}"],
                           cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout.decode(),
            "diagnostic sister authorization text absent")
    contract = load(CONFIG); session_contract(contract)
    p2 = load(P2_RECEIPT); phase_b = load(PHASE_B); link92 = load(LINK92_RECEIPT)
    require(p2["decision"]["named_terminal_ingress_candidate"]
            == "second source-less IRQ episode"
            and p2["future_device_row"]["name"]
            == "current-carrier terminal-ingress ring",
            "P2 terminal-ingress authority drift")
    require(phase_b["status"]
            == "passed-complete-Link82-defstruct-fail-closed-R-A-I-G-partition",
            "R/A/I/G record authority drift")
    require(link92["status"].startswith("passed"), "Link-92 authority not green")

    base_truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    gaps = [allocated_gap(base_truth, start, end) for start, end in (
        (CODE0, CODE0_LIMIT), (PROGRESS, PROGRESS_LIMIT),
        (CODE1, RECORD_LIMIT))]
    patch = record_patch(phase_b)
    producer = producer_bytes(); sampler = sampler_bytes()
    progress = producer + STATE_RESET + SLOT_RESET
    require(len(progress) == PROGRESS_LIMIT - PROGRESS,
            "progress arena does not exactly close owner-free interval")
    diag_prg, diag_window, new_crc = apply_prg(
        CONTROL_PRG.read_bytes(), patch, producer, sampler)
    old_crc = crc16(CONTROL_WINDOW.read_bytes())
    require(old_crc == 0x9F16, f"Link-92 window CRC drift: {old_crc:04x}")

    if write_artifacts:
        ART.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONTROL_PRG, CONTROL_COPY_PRG)
        shutil.copyfile(CONTROL_ELF, CONTROL_COPY_ELF)
        shutil.copyfile(CONTROL_WINDOW, CONTROL_COPY_WINDOW)
        shutil.copyfile(CONTROL_D81, CONTROL_COPY_D81)
        DIAG_PRG.write_bytes(diag_prg); DIAG_WINDOW.write_bytes(diag_window)
        RECORD_RESET.write_bytes(patch["record_reset"])
        RECORD_ARM.write_bytes(patch["record_arm"])
        PROGRESS_RESET.write_bytes(STATE_RESET + SLOT_RESET)
        patch_elf(patch, progress, sampler, new_crc)
        media = build_medium()
    else:
        require(DIAG_PRG.read_bytes() == diag_prg
                and DIAG_WINDOW.read_bytes() == diag_window,
                "diagnostic sister bytes no longer reproduce")
        require(RECORD_RESET.read_bytes() == patch["record_reset"]
                and RECORD_ARM.read_bytes() == patch["record_arm"]
                and PROGRESS_RESET.read_bytes() == STATE_RESET + SLOT_RESET,
                "diagnostic reset bytes no longer reproduce")
        # Re-extracting is intentional: the checker proves the packed medium,
        # not merely the producer's cached receipt.
        media = build_medium()

    require(bind(CONTROL_COPY_PRG)["sha256"] == sha(CONTROL_PRG)
            and bind(CONTROL_COPY_ELF)["sha256"] == sha(CONTROL_ELF)
            and bind(CONTROL_COPY_WINDOW)["sha256"] == sha(CONTROL_WINDOW)
            and bind(CONTROL_COPY_D81)["sha256"] == sha(CONTROL_D81),
            "control copy is not byteidentical")

    truth = ElfTruth.read(DIAG_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    for name, address in ((SECTION_CODE0, CODE0),
                          (SECTION_PROGRESS, PROGRESS),
                          (SECTION_CODE1, CODE1),
                          (SECTION_RECORD, RECORD)):
        require(truth.section(name).address == address,
                f"diagnostic section VMA drift: {name}")
    sampler_edges = executable_edges(truth, SAMPLER)
    require(sampler_edges == [{
        "section": ".lisp65_c2_kernal_window.irq_handler",
        "pc": "0xe053", "opcode": "JSR"}],
        f"sampler edge closure drift: {sampler_edges}")
    producer_edges = executable_edges(truth, PRODUCER)
    require(producer_edges == [{"section": ".text", "pc": "0x467d",
                                "opcode": "JSR"}],
            f"producer edge closure drift: {producer_edges}")

    entry = patch["entry_witness"]
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN-NON-PROMOTABLE-SISTER; BUNDLED-SESSION-READY",
        "authorities": {
            "owner_authorization": authorization,
            "media_contract_repair_authorization": media_repair_authorization,
            "P2_completion_edge": bind(P2_RECEIPT),
            "R_A_I_G_partition": bind(PHASE_B),
            "Link92_control": bind(LINK92_RECEIPT),
            "state_inventory_v17": bind(V17),
            "full_map_inventory_v18": bind(V18),
            "session_contract": bind(CONFIG),
            "session_runner": bind(RUNNER),
            "driver": bind(DRIVER),
        },
        "identity": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0, "hardware_runs": 0,
            "control_PRG": bind(CONTROL_COPY_PRG),
            "control_ELF": bind(CONTROL_COPY_ELF),
            "control_window": bind(CONTROL_COPY_WINDOW),
            "control_medium": bind(CONTROL_COPY_D81),
            "diagnostic_PRG": bind(DIAG_PRG),
            "diagnostic_ELF": bind(DIAG_ELF),
            "diagnostic_window": bind(DIAG_WINDOW),
            "diagnostic_medium": bind(DIAG_D81),
            "library_medium": bind(LIBRARY_D81),
            "enumerated_PRG_delta": exact_ranges(
                CONTROL_PRG.read_bytes(), diag_prg, base=PRG_LOAD - 2),
            "enumerated_window_delta": exact_ranges(
                CONTROL_WINDOW.read_bytes(), diag_window, base=WINDOW_BASE),
            "unrelated_medium_roles_byteidentical": media["shared_roles"],
            "replaced_payload_roles": media["replaced_payload_roles"],
            "regenerated_contract_roles": media["regenerated_contract_roles"],
            "media_contract": media["contract"],
        },
        "placement": {
            "owner_free_intervals": gaps,
            "record": ["0xc03f", "0xc080"],
            "progress_producer_state_and_slots": ["0xb582", "0xb5c4"],
            "G4_validated_region": ["0xe000", "0x10000"],
            "witness_slots_outside_G4_region": True,
            "record_outside_overlay_and_validated_regions": True,
            "simultaneously_live_and_disjoint": True,
        },
        "G4": {
            "control_window_crc16": f"0x{old_crc:04X}",
            "diagnostic_window_crc16": f"0x{new_crc:04X}",
            "PRG_expectation_operands": ["0xb4f4", "0xb4fa"],
            "expectation_recomputed_from_diagnostic_window": True,
            "control_ELF_precompletion_operands": "A55A",
            "control_PRG_completed_operands": f"{old_crc:04X}",
        },
        "instrument": {
            "record_bytes": 65,
            "record_fields": len(phase_b["facts"]["record"]["fields"]),
            "record_reset": bind(RECORD_RESET), "record_arm": bind(RECORD_ARM),
            "raw_before_tag": True,
            "last_two_refill_views": True,
            "independent_refill_oracle": "source bytes, never completion metadata",
            "terminal_ingress": {
                "tag": "irq.source-less-entry-2",
                "raw_tagged_values": ["episode-latch", "D019", "D01A"],
                "interrupted_return_PC_tagged": True,
            },
            "entry_witness": {
                "address": f"0x{RECORD + entry['stamp_offset']:04x}",
                "value": f"0x{entry['stamp_value']:02x}",
                "read_before_measured_record_reset": True,
            },
            "progress": {
                "producer": ["0xb582", "0xb5ac"],
                "state": ["0xb5ac", "0xb5b4"],
                "slots": ["0xb5b4", "0xb5c4"],
                "slot_count": SLOT_COUNT, "slot_bytes": SLOT_BYTES,
                "sample_period_frames": SAMPLE_FRAMES,
                "sample_period_seconds": f"{SAMPLE_FRAMES * 1000 / FRAME_HZ_MILLI:.6f}",
                "writer": "owned-raster-IRQ-commit-last",
                "monitor_or_CPU_stop_operations": 0,
                "source_less_or_fail_closed_inbound_edges": 0,
                "abort_driver_edge_retired": True,
                "abort_path_result_rule": "instrument-first-red; no R/A/I/G claim",
                "reset": bind(PROGRESS_RESET),
            },
        },
        "decision_table": {
            "R": "independent refill byte oracle fails before terminal ingress",
            "A": "append checkpoint/phase/C2J names forward failure",
            "I": "refills and A/G planes clean; tagged second source-less episode is first failing plane",
            "G": "first-error/VM/GC plane names failure before terminal ingress",
            "progress": "two committed slots distinguish live dispatch from a native/terminal plateau",
            "instrument_red": "missing tags/slots, abort-cleanup entry, or identity mismatch; no product claim",
        },
        "session": {
            "authorized": True, "execution_order": ["Link93-trace", "defstruct", "trailing-peeks"],
            "owner_physical_input_only": True,
            "monitor_access_during_active_form": 0,
            "screen_polling_during_active_form": 0,
            "stops_after_active_form": 1,
            "defstruct_quiet_floor_seconds": 180,
            "result_receipt_exists": False,
        },
        "claim_limit": (
            "Host-green non-promotable current-carrier sibling and packed media. "
            "No product fix, release, defstruct mechanism, trace hardware result, "
            "R/A/I/G selection or v1.5 scope is claimed before the authorized session."),
    }
    return value


def validate(value: dict[str, Any], *, reproduce: bool) -> None:
    require(value.get("format") == FORMAT
            and value.get("status")
            == "HOST-GREEN-NON-PROMOTABLE-SISTER; BUNDLED-SESSION-READY",
            "diagnostic sister status drift")
    identity = value["identity"]
    require(identity["promotable"] is False
            and identity["product_candidate_bytes_changed"] == 0
            and identity["product_links"] == 0
            and identity["WPLTO_runs"] == 0
            and identity["hardware_runs"] == 0
            and identity["unrelated_medium_roles_byteidentical"] == 11
            and identity["replaced_payload_roles"]
            == ["lisp65.prg", "window.bin"]
            and identity["regenerated_contract_roles"]
            == ["autoboot.c65", "boot.id"],
            "diagnostic identity boundary drift")
    require(identity["control_PRG"]["bytes"] == CONTROL_PRG.stat().st_size
            and identity["control_PRG"]["sha256"] == sha(CONTROL_PRG)
            and identity["control_ELF"]["sha256"] == sha(CONTROL_ELF)
            and identity["control_window"]["sha256"] == sha(CONTROL_WINDOW)
            and identity["control_medium"]["sha256"] == sha(CONTROL_D81),
            "control byteidentity drift")
    require(value["authorities"]["session_contract"] == bind(CONFIG)
            and value["authorities"]["session_runner"] == bind(RUNNER)
            and value["authorities"]["driver"] == bind(DRIVER),
            "diagnostic sister implementation binding drift")
    session_contract(load(CONFIG))
    require([(row["start"], row["bytes"])
             for row in identity["enumerated_PRG_delta"]] == [
        ("0x202c", 5), ("0x2dde", 3), ("0x467d", 3),
        ("0x47c5", 10), ("0x8eb7", 5), ("0xb3b0", 243),
        ("0xb4f4", 1), ("0xb4fa", 1), ("0xb582", 42),
        ("0xb5b0", 11), ("0xb5bc", 7), ("0xbff7", 71),
        ("0xc03f", 65),
    ] and [(row["start"], row["bytes"])
           for row in identity["enumerated_window_delta"]] == [
        ("0xe053", 3), ("0xe08b", 14), ("0xfee1", 95),
    ], "enumerated diagnostic delta closure drift")
    placement = value["placement"]
    require(placement["record"] == ["0xc03f", "0xc080"]
            and placement["progress_producer_state_and_slots"] == ["0xb582", "0xb5c4"]
            and placement["G4_validated_region"] == ["0xe000", "0x10000"]
            and placement["witness_slots_outside_G4_region"] is True
            and placement["record_outside_overlay_and_validated_regions"] is True
            and placement["simultaneously_live_and_disjoint"] is True
            and all(row["active_overlaps"] == 0
                    for row in placement["owner_free_intervals"]),
            "witness placement/ownership drift")
    require(value["G4"]["control_window_crc16"] == "0x9F16"
            and value["G4"]["diagnostic_window_crc16"]
            == f"0x{crc16(DIAG_WINDOW.read_bytes()):04X}"
            and value["G4"]["diagnostic_window_crc16"] != "0x9F16"
            and value["G4"]["expectation_recomputed_from_diagnostic_window"] is True,
            "G4 independent recomputation drift")
    media_contract = identity["media_contract"]
    require(
        media_contract["status"]
        == "passed-target-equivalent-packed-role-descriptor-check"
        and media_contract["donor_build_id"] != media_contract["diagnostic_build_id"]
        and media_contract["descriptor"] == bind(DIAG_DESCRIPTOR)
        and media_contract["stager"] == bind(DIAG_STAGER)
        and media_contract["stager_map"] == bind(DIAG_STAGER_MAP)
        and media_contract["diagnostic_build_id"]
        == f"0x{struct.unpack_from('<I', DIAG_DESCRIPTOR.read_bytes(), 8)[0]:08x}"
        and media_contract["profile_build_id"]
        == f"0x{struct.unpack_from('<I', DIAG_DESCRIPTOR.read_bytes(), 12)[0]:08x}"
        and media_contract["stager_gate"]["status"].startswith("passed-strict-build")
        and media_contract["packed_roles_checked"] == 13
        and media_contract["contract_members_regenerated_after_payload_change"] is True
        and media_contract["historical_first_red"] == {
            "classification": "payload-replaced-contract-inherited",
            "cold_stager_first_rejected_role": 8,
            "stale_records": [
                {"name": "window.bin", "descriptor_crc32": "0xd4bf510b",
                 "packed_crc32": "0x17d1df2b"},
                {"name": "lisp65.prg", "descriptor_crc32": "0x35ce3466",
                 "packed_crc32": "0x0604daec"},
            ],
        }
        and media_contract["mutations"] == {
            "mutations_rejected": 2,
            "cases": [
                "descriptor-regenerated-stager-inherited",
                "payload-replaced-contract-inherited",
            ],
        },
        "target-equivalent derived-media contract drift",
    )
    instrument = value["instrument"]
    require(instrument["record_bytes"] == 65
            and instrument["record_fields"] == 29
            and instrument["raw_before_tag"] is True
            and instrument["last_two_refill_views"] is True
            and instrument["terminal_ingress"] == {
                "tag": "irq.source-less-entry-2",
                "raw_tagged_values": ["episode-latch", "D019", "D01A"],
                "interrupted_return_PC_tagged": True,
            }, "R/A/I/G record contract drift")
    progress = instrument["progress"]
    require(progress["slots"] == ["0xb5b4", "0xb5c4"]
            and progress["slot_count"] == 2 and progress["slot_bytes"] == 8
            and progress["writer"] == "owned-raster-IRQ-commit-last"
            and progress["monitor_or_CPU_stop_operations"] == 0
            and progress["source_less_or_fail_closed_inbound_edges"] == 0
            and progress["abort_driver_edge_retired"] is True,
            "target-owned progress ring drift")
    require(value["session"] == {
        "authorized": True,
        "execution_order": ["Link93-trace", "defstruct", "trailing-peeks"],
        "owner_physical_input_only": True,
        "monitor_access_during_active_form": 0,
        "screen_polling_during_active_form": 0,
        "stops_after_active_form": 1,
        "defstruct_quiet_floor_seconds": 180,
        "result_receipt_exists": False,
    }, "bundled session boundary drift")
    require("No product fix" in value["claim_limit"]
            and "R/A/I/G selection" in value["claim_limit"],
            "diagnostic claim limit broadened")
    if reproduce:
        require(value == derive(write_artifacts=False),
                "diagnostic sister receipt no longer reproduces")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "promote-sister": lambda x: x["identity"].update(promotable=True),
        "claim-product-link": lambda x: x["identity"].update(product_links=1),
        "claim-hardware": lambda x: x["identity"].update(hardware_runs=1),
        "alter-control": lambda x: x["identity"]["control_PRG"].update(sha256="00" * 32),
        "change-third-medium-role": lambda x: x["identity"].update(
            unrelated_medium_roles_byteidentical=10),
        "inherit-payload-contract": lambda x: x["identity"]["media_contract"].update(
            contract_members_regenerated_after_payload_change=False),
        "drop-packed-role": lambda x: x["identity"]["media_contract"].update(
            packed_roles_checked=12),
        "move-slots-into-G4": lambda x: x["placement"].update(
            progress_producer_state_and_slots=["0xff40", "0xff50"]),
        "deny-slot-exclusion": lambda x: x["placement"].update(
            witness_slots_outside_G4_region=False),
        "claim-overlap": lambda x: x["placement"]["owner_free_intervals"][1].update(
            active_overlaps=1),
        "drop-simultaneous-fit": lambda x: x["placement"].update(
            simultaneously_live_and_disjoint=False),
        "reuse-old-G4": lambda x: x["G4"].update(
            diagnostic_window_crc16="0x9F16"),
        "metadata-as-G4-oracle": lambda x: x["G4"].update(
            expectation_recomputed_from_diagnostic_window=False),
        "drop-raw-before-tag": lambda x: x["instrument"].update(raw_before_tag=False),
        "drop-second-fill": lambda x: x["instrument"].update(last_two_refill_views=False),
        "untag-IRQ-return-PC": lambda x: x["instrument"]["terminal_ingress"].update(
            interrupted_return_PC_tagged=False),
        "drop-episode-raw": lambda x: x["instrument"]["terminal_ingress"][
            "raw_tagged_values"].pop(),
        "one-ring-slot": lambda x: x["instrument"]["progress"].update(slot_count=1),
        "non-owned-sampler": lambda x: x["instrument"]["progress"].update(
            writer="monitor-sampler"),
        "sampler-stops-CPU": lambda x: x["instrument"]["progress"].update(
            monitor_or_CPU_stop_operations=1),
        "source-less-sampler-edge": lambda x: x["instrument"]["progress"].update(
            source_less_or_fail_closed_inbound_edges=1),
        "keep-abort-edge": lambda x: x["instrument"]["progress"].update(
            abort_driver_edge_retired=False),
        "virtual-input": lambda x: x["session"].update(owner_physical_input_only=False),
        "monitor-active": lambda x: x["session"].update(
            monitor_access_during_active_form=1),
        "poll-active": lambda x: x["session"].update(
            screen_polling_during_active_form=1),
        "two-stops": lambda x: x["session"].update(stops_after_active_form=2),
        "forge-result": lambda x: x["session"].update(result_receipt_exists=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); mutate(trial)
        try:
            validate(trial, reproduce=False)
        except SisterError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "diagnostic sister mutation survived: "
            + ", ".join(sorted(set(cases) - set(rejected))))
    return rejected


def gate_wiring() -> None:
    source = GATES.read_text(encoding="utf-8")
    require(all(token in source for token in (
        "c2-defstruct-terminal-ingress-selftest:",
        "c2_defstruct_terminal_ingress_sister.py selftest",
        "c2-defstruct-terminal-ingress-check:",
        "c2_defstruct_terminal_ingress_sister.py check",
        "check-source: c2-defstruct-terminal-ingress-selftest",
    )), "diagnostic sister gate wiring absent")


def runner_audit() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    require("dry-run|stage|confirm-library|arm-after-require|wait-defstruct|capture" in source
            and "OWNER-PHYSICAL-INPUT-ONLY" in source,
            "diagnostic runner action/input surface drift")
    active = source.split("# ACTIVE-DEFSTRUCT-BEGIN", 1)[1].split(
        "# ACTIVE-DEFSTRUCT-END", 1)[0]
    require("sleep \"$quiet\"" in active
            and not any(token in active for token in (
                "run_m65", "screen ", "readback", "monitor", "--memsave")),
            "monitor or screen access leaked into active defstruct window")
    capture = source.split("if [ \"$ACTION\" = capture ]; then", 1)[1]
    require(capture.count("stop_once") == 1
            and "record-1.bin" in capture and "progress.bin" in capture
            and "c2d-reset-domain.bin" in capture
            and "bank2-source.bin" in capture,
            "one-stop/full-read capture contract drift")
    require("entry-witness.bin" in source
            and "record_reset=$(jq -r '.record.reset.path'" in source
            and "progress_reset=$(jq -r '.progress.reset.path'" in source
            and '"$record_reset@0x0000c03f"' in source
            and '"$progress_reset@0x0000b5ac"' in source
            and "sleep 1" in source,
            "pre-form reset/rearm choreography drift")


def write_deployment(value: dict[str, Any]) -> None:
    deployment = {
        "format": "lisp65-c2.3-post-v1.4-defstruct-terminal-ingress-deployment-v1",
        "status": "host-green-session-authorized-not-run",
        "product_medium": value["identity"]["diagnostic_medium"],
        "library_medium": value["identity"]["library_medium"],
        "record": {"address": "0x0000c03f", "bytes": 65,
                   "reset": value["instrument"]["record_reset"],
                   "arm": value["instrument"]["record_arm"]},
        "progress": {"address": "0x0000b5ac", "bytes": 24,
                     "reset": value["instrument"]["progress"]["reset"]},
        "entry_witness": value["instrument"]["entry_witness"],
        "forms": {"require": "(require (quote defstruct))",
                  "defstruct": "(defstruct point x y)"},
        "quiet_floor_seconds": value["session"]["defstruct_quiet_floor_seconds"],
        "readback": {"record": [0xC03F, 65], "progress": [0xB582, 66],
                     "bank2_source": [0x20000, 0x10000],
                     "c2d_reset_domain": [0x50000, 50816],
                     "window_physical": [0x087FE000, 8192]},
        "decision_table": value["decision_table"],
        "result_receipt_exists": False,
    }
    write_json(DEPLOY, deployment)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive(write_artifacts=True)
        validate(value, reproduce=False)
        write_deployment(value)
        RECEIPT.write_bytes(canonical(value))
        print(f"defstruct terminal-ingress sister: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    gate_wiring(); runner_audit()
    value = load(RECEIPT)
    validate(value, reproduce=(action == "check"))
    rejected = mutations(value)
    if action == "check":
        require(load(DEPLOY)["status"] == "host-green-session-authorized-not-run",
                "diagnostic deployment status drift")
        print("defstruct terminal-ingress sister: PASS host-green session-ready")
    else:
        print(f"defstruct terminal-ingress sister selftest: PASS mutations={len(rejected)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SisterError, MEDIA.MediaError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"defstruct terminal-ingress sister: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
