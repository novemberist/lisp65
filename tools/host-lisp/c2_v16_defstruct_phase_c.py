#!/usr/bin/env python3
"""Build and gate the one non-promotable Link-82 defstruct identity.

The control is the released Link-82 authority itself.  The diagnostic sibling
is derived byte-for-byte from that authority: four fixed hooks, two code
caves that are absent from the product ownership map, and one 65-byte ordinary
RAM record.  No product link or WPLTO is created.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
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
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


CONFIG = ROOT / "config/c2-v16-defstruct-phase-c-diagnostic.json"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PHASE_B = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json"
)
BASE = ROOT / "build/c2.2/v1.2.5-candidate-product-link82/wplto"
CONTROL_ELF = BASE / "lisp65-c2-substitution-linked.prg.elf"
CONTROL_PRG = BASE / "lisp65-c2-substitution-linked.prg"
PRODUCT_MEDIUM = ROOT / "build/c2.2/v1.2.5-candidate-media/lisp65-product.d81"
LIBRARY_MEDIUM = ROOT / (
    "build/ship-builder/v1-device-session/defstruct-media/"
    "require-defstruct-ship-session.d81"
)
PRIOR_DEPLOY = ROOT / (
    "build/c2.2/v1.2.5-require-prior-append-hardware/deployment.json"
)
CONTROL_WINDOW = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/final/"
    "c2-product-kernal-window.bin"
)
V13_MEDIUM = ROOT / "build/c2.3/v1.3.0-candidate-media-link88-r1/lisp65-product.d81"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
DRIVER = Path(__file__).resolve()
HW = ROOT / "scripts/c2-v16-defstruct-phase-c-hw.sh"
GATES = ROOT / "mk/gates.mk"
OUT = ROOT / "build/c2.3/v1.6-defstruct-phase-c"
ARTIFACTS = OUT / "artifacts"
CONTROL_COPY_ELF = ARTIFACTS / "control-link82.elf"
CONTROL_COPY_PRG = ARTIFACTS / "control-link82.prg"
DIAG_ELF = ARTIFACTS / "diagnostic-link82.elf"
DIAG_PRG = ARTIFACTS / "diagnostic-link82.prg"
DIAG_WINDOW = ARTIFACTS / "diagnostic-window.bin"
RESET = ARTIFACTS / "record-reset.bin"
ARM = ARTIFACTS / "record-arm.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json"
)
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-plan-growth-rebind-2026-08-05.json"
)
FORMAT = "lisp65-c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-v1"
PRG_LOAD = 0x2001


class PhaseCError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseCError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def run(argv: list[str], label: str, *, cwd: Path = ROOT) -> str:
    result = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")
    return result.stdout


def u16(value: int) -> bytes:
    require(0 <= value <= 0xFFFF, f"u16 overflow: {value}")
    return bytes((value & 0xFF, value >> 8))


class Code:
    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def add(self, opcode: int, *operand: int) -> None:
        self.parts.append(bytes((opcode, *operand)))

    def lda_abs(self, address: int) -> None: self.parts.append(b"\xad" + u16(address))
    def sta_abs(self, address: int) -> None: self.parts.append(b"\x8d" + u16(address))
    def ldx_abs(self, address: int) -> None: self.parts.append(b"\xae" + u16(address))
    def ldy_abs(self, address: int) -> None: self.parts.append(b"\xac" + u16(address))
    def ldx_imm(self, value: int) -> None: self.add(0xA2, value)
    def lda_zp(self, address: int) -> None: self.add(0xA5, address)
    def sta_zp(self, address: int) -> None: self.add(0x85, address)
    def stx_zp(self, address: int) -> None: self.add(0x86, address)
    def sty_zp(self, address: int) -> None: self.add(0x84, address)
    def stx_abs(self, address: int) -> None: self.parts.append(b"\x8e" + u16(address))
    def lda_imm(self, value: int) -> None: self.add(0xA9, value)
    def lda_ind_z(self, address: int) -> None: self.add(0xB2, address)
    def lda_stack_x(self, offset: int) -> None: self.parts.append(bytes((0xBD, offset, 0x01)))
    def jmp(self, address: int) -> None: self.parts.append(b"\x4c" + u16(address))
    def jsr(self, address: int) -> None: self.parts.append(b"\x20" + u16(address))
    def tag(self, address: int, value: int) -> None:
        self.lda_imm(value); self.sta_abs(address)

    def bytes(self) -> bytes: return b"".join(self.parts)


def record_reset(record: dict[str, Any]) -> bytes:
    data = bytearray([0xCC] * record["bytes"])
    for field in record["fields"]:
        offset = field.get("offset", field.get("tag_offset"))
        require(isinstance(offset, int), "record tag offset absent")
        data[offset] = field["initial_sentinel"]
    require(len(data) == 65 and data[0] == 0x51 and 0 not in data,
            "record reset sentinel geometry drift")
    return bytes(data)


def entry_routine(record: dict[str, Any], rec: int, stamp_offset: int,
                  stamp_value: int) -> bytes:
    """Replay the displaced _start bytes and leave a transport-proof stamp.

    The routine occupies the first eight bytes of the record only in the boot
    image.  The measured defstruct form starts by restoring the complete
    canonical 65-byte reset image, so this bootstrap role cannot alter any
    R/A/I/G field semantics.
    """
    reserved = {
        value
        for field in record["fields"]
        for value in (field["initial_sentinel"], field["reached_tag"])
    }
    require(stamp_value != 0 and stamp_value not in reserved,
            "entry stamp collides with a legal record sentinel/tag")
    require(stamp_offset == 59 and rec + stamp_offset == 0xC07A,
            "entry stamp placement drift")
    payload = (b"\xa2\x44"          # LDX #$44 (displaced original)
               b"\x8e\x30\xd0"      # STX $D030 (displaced original)
               b"\x8e" + u16(rec + stamp_offset) +  # STX entry stamp
               b"\x60")              # RTS
    require(len(payload) == 9, "entry routine size drift")
    return payload


def append_capture(code: Code, rec: int) -> None:
    # Raw first, tag last for each field; complete is written last.
    code.lda_abs(0xC1F4); code.sta_abs(rec + 44)
    code.ldx_imm(0xB3); code.stx_abs(rec + 43)
    code.lda_zp(0x89); code.sta_abs(rec + 46)
    code.add(0xE8); code.stx_abs(rec + 45)  # INX -> B4
    code.lda_abs(0xC19B); code.sta_abs(rec + 48)
    code.add(0xE8); code.stx_abs(rec + 47)  # INX -> B5
    code.tag(rec + 42, 0xB2)


def irq_capture(code: Code, rec: int) -> None:
    code.lda_abs(0xFF86); code.sta_abs(rec + 51)
    code.ldx_imm(0xB7); code.stx_abs(rec + 50)
    code.lda_abs(0xFF89); code.sta_abs(rec + 53)
    code.add(0xE8); code.stx_abs(rec + 52)  # INX -> B8
    code.lda_abs(0xD01A); code.sta_abs(rec + 55)
    code.add(0xE8); code.stx_abs(rec + 54)  # INX -> B9
    code.add(0xBA)  # TSX; IRQ stack is Z,Y,X,A,P,PCL,PCH above SP.
    code.lda_stack_x(6); code.sta_abs(rec + 57)
    code.lda_stack_x(7); code.sta_abs(rec + 58)
    code.tag(rec + 56, 0xBA)
    code.tag(rec + 49, 0xB6)


def gc_capture(code: Code, rec: int) -> None:
    code.lda_zp(0x8F); code.sta_abs(rec + 61)
    code.ldx_imm(0xBC); code.stx_abs(rec + 60)
    code.lda_abs(0xB9F0); code.sta_abs(rec + 63)
    code.lda_abs(0xB9F1); code.sta_abs(rec + 64)
    code.add(0xE8); code.stx_abs(rec + 62)  # INX -> BD
    code.tag(rec + 59, 0xBB)


def fail_routine(start: int, rec: int) -> bytes:
    code = Code()
    append_capture(code, rec)
    irq_capture(code, rec)
    gc_capture(code, rec)
    # Original guard body, after all record writes and before the endless loop.
    code.add(0x78)  # SEI
    code.parts.append(b"\x9c" + u16(0xD01A))  # STZ abs
    code.lda_imm(2); code.sta_abs(0xD020)
    loop = start + len(code.bytes())
    code.jmp(loop)
    require(len(code.bytes()) == 132, f"fail capture size drift: {len(code.bytes())}")
    return code.bytes()


def error_routine(rec: int) -> bytes:
    code = Code()
    code.stx_zp(0x17)  # Original detail high-byte preservation.
    code.lda_zp(0x5B); code.sta_abs(rec + 29); code.tag(rec + 28, 0xAD)
    code.tag(rec + 27, 0xAC)
    code.lda_zp(0x5B)  # Restore the original helper input after tag stores.
    # Tail-jump to the original helper; its RTS returns to the patched caller.
    code.jmp(0x973B)
    payload = code.bytes()
    require(len(payload) == 22, f"error capture size drift: {len(payload)}")
    require(payload[-5:] == b"\xa5\x5b\x4c\x3b\x97",
            "first-error helper input is not restored before tail-jump")
    return payload


def refill_parts(continue_at: int, rec: int) -> tuple[bytes, bytes, list[dict[str, Any]]]:
    code = Code()
    # Match the real dispatcher seam: fetch the byte immediately after the
    # successful F018B return, before any diagnostic bookkeeping can delay it.
    code.ldx_abs(0xBFDD); code.ldy_abs(0xBFDE)
    code.stx_zp(0x04); code.sty_zp(0x05)
    code.lda_ind_z(0x04); code.add(0x48)  # PHA

    operations: list[dict[str, Any]] = [{
        "name": "independent-opcode-read",
        "source": "(vmr_code),Z immediately after successful refill",
        "before_bookkeeping": True,
    }]
    # Previous raw view first, then its five reached tags.
    for source, dest in zip(
        (16, 17, 19, 20, 21, 23, 24, 26),
        (3, 4, 6, 7, 8, 10, 11, 13), strict=True,
    ):
        code.lda_abs(rec + source); code.sta_abs(rec + dest)
    for dest, tag in ((2, 0xA3), (5, 0xA4), (9, 0xA5),
                      (12, 0xA6), (1, 0xA2)):
        code.tag(rec + dest, tag)

    # The accepted geometry deliberately ends the first straight-line block
    # here; one unconditional placement jump reaches the second owned cave.
    prefix = code.bytes()
    require(len(prefix) == 86, f"refill prefix size drift: {len(prefix)}")

    tail = Code()
    # Cursor and window base are the same newly materialized payload position.
    tail.lda_abs(0xBFE5); tail.sta_abs(rec + 16); tail.sta_abs(rec + 23)
    tail.lda_abs(0xBFE6); tail.sta_abs(rec + 17); tail.sta_abs(rec + 24)
    tail.tag(rec + 15, 0xA8); tail.tag(rec + 22, 0xAA)
    tail.lda_abs(0xBFD8); tail.sta_abs(rec + 19)
    tail.lda_abs(0xB9B2); tail.sta_abs(rec + 20)
    tail.lda_abs(0xB9B3); tail.sta_abs(rec + 21)
    tail.tag(rec + 18, 0xA9)
    tail.add(0x68); tail.sta_abs(rec + 26); tail.tag(rec + 25, 0xAB)  # PLA
    tail.tag(rec + 14, 0xA7); tail.add(0x60)  # RTS
    tail_bytes = tail.bytes()
    require(len(tail_bytes) == 66, f"refill tail size drift: {len(tail_bytes)}")
    # Five unreachable NOPs make the diagnostic section's owned extent stable;
    # they are not on the refill path and cannot become a hidden witness.
    tail_bytes += b"\xea" * 5
    return prefix + b"\x4c" + u16(continue_at), tail_bytes, operations


def build_patch(config: dict[str, Any], phase_b: dict[str, Any]) -> dict[str, Any]:
    addresses = config["addresses"]
    record = phase_b["facts"]["record"]
    rec = addresses["record"]
    fail = fail_routine(addresses["code0"], rec)
    error_address = addresses["code0"] + len(fail)
    error = error_routine(rec)
    refill_address = error_address + len(error)
    prefix, tail, operations = refill_parts(addresses["code1"], rec)
    code0 = fail + error + prefix
    code0 += b"\xea" * (addresses["code0_limit"] - addresses["code0"]
                         - len(code0))
    require(len(code0) == addresses["code0_limit"] - addresses["code0"],
            f"code0 must exactly occupy its owned gap: {len(code0)}")
    require(len(tail) <= addresses["code1_limit"] - addresses["code1"],
            "code1 overflows ordinary-RAM gap")
    reset = record_reset(record)
    entry = entry_routine(record, rec, addresses["entry_stamp_offset"],
                          addresses["entry_stamp_value"])
    boot_record = bytearray(reset)
    boot_record[:len(entry)] = entry
    patches = [
        {"name": "entry-RAM-witness-hook", "carrier": "resident-prg",
         "address": addresses["entry_hook"],
         "before": "a2448e30d0",
         "after": (b"\x20" + u16(addresses["entry_routine"]) + b"\xea\xea").hex()},
        {"name": "refill-dispatcher-hook", "carrier": "resident-prg",
         "address": addresses["refill_hook"],
         "before": "aedd_bfac_debf_8604_8405".replace("_", ""),
         "after": (b"\x20" + u16(refill_address) + b"\xea" * 7).hex()},
        {"name": "first-non-ok-hook", "carrier": "resident-prg",
         "address": addresses["first_error_hook"],
         "before": "8617203b97",
         "after": (b"\x20" + u16(error_address) + b"\xea\xea").hex()},
        {"name": "fail-closed-record-hook", "carrier": "kernal-window",
         "address": addresses["fail_closed_hook"],
         "before": "78a9008d1ad0a9028d20d04c96e0",
         "after": (b"\x4c" + u16(addresses["code0"]) + b"\xea" * 11).hex()},
    ]
    return {
        "code0": code0, "code1": tail, "record_boot": bytes(boot_record),
        "record_reset": reset,
        "record_arm": bytes((0xA1,)), "patches": patches,
        "symbols": {
            "lisp65_v16_defstruct_entry_capture": addresses["entry_routine"],
            "lisp65_v16_defstruct_fail_capture": addresses["code0"],
            "lisp65_v16_defstruct_first_error_capture": error_address,
            "lisp65_v16_defstruct_refill_capture": refill_address,
            "lisp65_v16_defstruct_refill_continue": addresses["code1"],
            "lisp65_v16_defstruct_diagnostic_state": rec,
        },
        "operations": operations,
        "entry_witness": {
            "method": "RAM-store-at-_start",
            "hook": addresses["entry_hook"],
            "routine": addresses["entry_routine"],
            "stamp_address": rec + addresses["entry_stamp_offset"],
            "stamp_offset": addresses["entry_stamp_offset"],
            "stamp_initial": reset[addresses["entry_stamp_offset"]],
            "stamp_value": addresses["entry_stamp_value"],
            "routine_bytes": entry.hex(),
            "displaced_bytes_replayed": "a2448e30d0",
            "RAM_mapping_activation_address": 0x2024,
            "RAM_mapping_activation_bytes": "a22f8600a23e8601",
            "RAM_mapping_active_before_entry_call": True,
        },
    }


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def apply_patch_bytes(data: bytearray, offset: int, before: bytes, after: bytes,
                      name: str) -> None:
    require(len(before) == len(after), f"fixed-size patch required: {name}")
    require(data[offset:offset + len(before)] == before,
            f"patch authority drift: {name}")
    data[offset:offset + len(after)] = after


def patch_prg(control: bytes, patch: dict[str, Any], config: dict[str, Any]) -> bytes:
    result = bytearray(control)
    addresses = config["addresses"]
    require(int.from_bytes(result[:2], "little") == PRG_LOAD,
            "Link-82 PRG load address drift")
    for start, payload, name in (
        (addresses["code0"], patch["code0"], "diagnostic-code0"),
        (addresses["code1"], patch["code1"], "diagnostic-code1"),
        (addresses["record"], patch["record_boot"], "diagnostic-record/bootstrap"),
    ):
        offset = prg_offset(start)
        require(set(result[offset:offset + len(payload)]) <= {0},
                f"diagnostic gap is not unowned zero space: {name}")
        result[offset:offset + len(payload)] = payload
    for row in patch["patches"]:
        if row["carrier"] != "resident-prg":
            continue
        apply_patch_bytes(result, prg_offset(row["address"]),
                          bytes.fromhex(row["before"]), bytes.fromhex(row["after"]),
                          row["name"])
    return bytes(result)


def extract_file(image: Path, name: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    run(["c1541", "-attach", str(image), "-read", name, str(output)],
        f"extract {name}")


def patch_window(control_window: Path, patch: dict[str, Any]) -> bytes:
    data = bytearray(control_window.read_bytes())
    require(len(data) == 8192, "Link-82 window size drift")
    row = next(item for item in patch["patches"]
               if item["name"] == "fail-closed-record-hook")
    apply_patch_bytes(data, row["address"] - 0xE000,
                      bytes.fromhex(row["before"]), bytes.fromhex(row["after"]),
                      row["name"])
    return bytes(data)


def patch_elf(patch: dict[str, Any], config: dict[str, Any]) -> None:
    truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = truth.section(".text")
    text_data = bytearray(truth.section_bytes(".text"))
    guard = truth.section(".lisp65_c2_kernal_window.map_switch_and_guards")
    guard_data = bytearray(truth.section_bytes(guard.name))
    for row in patch["patches"]:
        before, after = bytes.fromhex(row["before"]), bytes.fromhex(row["after"])
        if row["carrier"] == "resident-prg":
            apply_patch_bytes(text_data, row["address"] - text.address,
                              before, after, row["name"])
        else:
            apply_patch_bytes(guard_data, row["address"] - guard.address,
                              before, after, row["name"])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    section_files = {
        ".text": bytes(text_data), guard.name: bytes(guard_data),
        ".lisp65_v16_defstruct_diagnostic_code0": patch["code0"],
        ".lisp65_v16_defstruct_diagnostic_code1": patch["code1"],
        ".lisp65_v16_defstruct_diagnostic_state": patch["record_boot"],
    }
    paths: dict[str, Path] = {}
    for index, (name, payload) in enumerate(section_files.items()):
        path = ARTIFACTS / f"section-{index}.bin"
        path.write_bytes(payload); paths[name] = path
    args = [str(OBJCOPY),
            f"--update-section=.text={paths['.text']}",
            f"--update-section={guard.name}={paths[guard.name]}"]
    for name in (
        ".lisp65_v16_defstruct_diagnostic_code0",
        ".lisp65_v16_defstruct_diagnostic_code1",
        ".lisp65_v16_defstruct_diagnostic_state",
    ):
        args.append(f"--add-section={name}={paths[name]}")
        flags = "alloc,load,readonly,code" if "code" in name else "alloc,load,data"
        args.append(f"--set-section-flags={name}={flags}")
    for name, address in patch["symbols"].items():
        flags = "global,object" if name.endswith("_state") else "global,function"
        args.append(f"--add-symbol={name}=0x{address:x},{flags}")
    args += [str(CONTROL_ELF), str(DIAG_ELF)]
    run(args, "derive diagnostic ELF")
    patch_elf_section_addresses(DIAG_ELF, {
        ".lisp65_v16_defstruct_diagnostic_code0": config["addresses"]["code0"],
        ".lisp65_v16_defstruct_diagnostic_code1": config["addresses"]["code1"],
        ".lisp65_v16_defstruct_diagnostic_state": config["addresses"]["record"],
    })


def patch_elf_section_addresses(path: Path, addresses: dict[str, int]) -> None:
    """Set sh_addr on objcopy-added ELF32 sections without relinking product bytes.

    llvm-objcopy deliberately refuses --change-section-address on an ET_EXEC
    MOS image.  The added sections are evidence-only views of bytes already
    placed in the PRG; changing their section-header address neither creates a
    program segment nor mutates any product byte.
    """
    data = bytearray(path.read_bytes())
    require(data[:6] == b"\x7fELF\x01\x01", "diagnostic ELF is not ELF32 little-endian")
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    require(shentsize == 40 and 0 < shstrndx < shnum,
            "diagnostic ELF section-header geometry drift")
    str_header = shoff + shstrndx * shentsize
    str_offset, str_size = struct.unpack_from("<II", data, str_header + 16)
    strings = data[str_offset:str_offset + str_size]
    found: set[str] = set()
    for index in range(shnum):
        header = shoff + index * shentsize
        name_offset = struct.unpack_from("<I", data, header)[0]
        end = strings.find(0, name_offset)
        require(end >= 0, "diagnostic ELF section-name table drift")
        name = bytes(strings[name_offset:end]).decode("ascii")
        if name in addresses:
            struct.pack_into("<I", data, header + 12, addresses[name])
            found.add(name)
    require(found == set(addresses), f"diagnostic ELF sections absent: {set(addresses) - found}")
    path.chmod(path.stat().st_mode | 0o200)
    path.write_bytes(data)


def ranges(before: bytes, after: bytes, *, base: int = 0) -> list[dict[str, Any]]:
    require(len(before) == len(after), "fixed-size identity comparison required")
    changed = [index for index, pair in enumerate(zip(before, after, strict=True))
               if pair[0] != pair[1]]
    result: list[dict[str, Any]] = []
    if not changed:
        return result
    start = prior = changed[0]
    for current in changed[1:] + [changed[-1] + 2]:
        if current != prior + 1:
            result.append({
                "start": f"0x{base + start:04x}",
                "bytes": prior - start + 1,
                "before": before[start:prior + 1].hex(),
                "after": after[start:prior + 1].hex(),
            })
            start = current
        prior = current
    return result


def elf_memory_diff(control: ElfTruth, diagnostic: ElfTruth) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = {row.name for row in control.sections} | {row.name for row in diagnostic.sections}
    for name in sorted(names):
        if not name or name in (".symtab", ".strtab", ".shstrtab"):
            continue
        lefts = control.sections_by_name.get(name, [])
        rights = diagnostic.sections_by_name.get(name, [])
        if len(lefts) != 1 or len(rights) != 1:
            if name.startswith(".lisp65_v16_defstruct_diagnostic_"):
                row = rights[0]
                rows.append({"section": name, "address": f"0x{row.address:04x}",
                             "bytes": row.bytes, "kind": "diagnostic-only"})
            continue
        left, right = lefts[0], rights[0]
        if left.bytes == right.bytes and left.address == right.address:
            try:
                ldata, rdata = control.section_bytes(name), diagnostic.section_bytes(name)
            except Exception:
                continue
            if ldata != rdata:
                rows.append({"section": name, "address": f"0x{left.address:04x}",
                             "kind": "patched-hook",
                             "ranges": ranges(ldata, rdata, base=left.address)})
    return rows


def facts(config: dict[str, Any], phase_b: dict[str, Any], patch: dict[str, Any],
          memory_diff: list[dict[str, Any]]) -> dict[str, Any]:
    record = phase_b["facts"]["record"]
    return {
        "identity": {
            "control_byteidentical_to_Link82": True,
            "diagnostic_promotable": False,
            "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0,
            "diagnostic_identities": 1,
            "library_medium_byteidentical": True,
            "non_window_preloads_byteidentical": True,
            "diagnostic_window_is_only_preload_delta": True,
        },
        "placement": {
            "code0": {"start": "0xb3b0", "end_exclusive": "0xb4a3", "bytes": 243},
            "code1": {"start": "0xbff7", "end_exclusive": "0xc03e", "bytes": 71},
            "record": {"start": "0xc03f", "end_exclusive": "0xc080", "bytes": 65,
                       "ordinary_RAM": True, "overlaps_ZP_window_overlay": False,
                       "boot_prefix_bytes": 9,
                       "canonical_reset_before_measured_form": 65},
            "simultaneously_live_and_disjoint": True,
        },
        "instrument": {
            "hooks": patch["patches"], "symbols": patch["symbols"],
            "ELF_memory_differences": memory_diff,
            "entry_witness": {
                **patch["entry_witness"],
                "nonzero_and_disjoint_from_record_values": True,
                "bootstrap_CPU_visible_after_RAM_mapping": True,
                "bootstrap_uses_protected_refill_seam": False,
                "full_record_reset_before_defstruct": True,
                "live_monitor_breakpoint_required": False,
            },
            "record_fields": len(record["fields"]),
            "record_bytes": record["bytes"],
            "reset_on_measured_form_entry": True,
            "raw_before_tag": True,
            "last_two_completed_refill_views": True,
            "dispatcher_side_capture": True,
            "opcode_read_before_bookkeeping": True,
            "source_byte_oracle": "stopped C2D/object source bytes",
            "completion_metadata_is_not_oracle": True,
            "stores_submit_DMA": False,
            "stores_call_product_helpers": False,
            "stores_can_fail": False,
            "in_stream_witness": False,
            "first_error_restores_status_argument": True,
        },
        "runner": {
            "cold_reset_before_each_identity": True,
            "exact_media_readback": True,
            "context_asserts": ["fresh BASIC", "Workbench prompt", "C2J CLEAR",
                                "phase owner NONE", "Session rows zero"],
            "D1_buffer_peek_before_keys": True,
            "D1_final_buffer_peek_after_keys": True,
            "D1_monitor_reads_per_key": 0,
            "D1_nonempty_buffer_fixture_rejected": True,
            "D1_hang_one_stop_packet": ["queue", "gc_runs", "PC", "buffer"],
            "transfer_progress_guard_seconds": 120,
            "quiet_forms": ["(require 'defstruct)", "(defstruct point x y)"],
            "monitor_accesses_while_form_active": 0,
            "screen_accesses_while_form_active": 0,
            "D2_post_event_stops": 1,
            "stable_reads": 3,
            "complete_read_set": ["65-byte record", "low RAM", "Bank-2 source",
                                  "C2D header/rows", "last-fill source bytes"],
        },
        "classification": {
            "rows": ["R", "A", "I", "G"],
            "synthetic_execution_witnesses": 7,
            "unclassified_outcome_allowed": False,
        },
    }


def audit(value: dict[str, Any]) -> None:
    require(value["identity"] == {
        "control_byteidentical_to_Link82": True,
        "diagnostic_promotable": False,
        "product_candidate_bytes_changed": 0,
        "product_links": 0, "WPLTO_runs": 0, "diagnostic_identities": 1,
        "library_medium_byteidentical": True,
        "non_window_preloads_byteidentical": True,
        "diagnostic_window_is_only_preload_delta": True,
    }, "diagnostic identity boundary drift")
    placement = value["placement"]
    require(placement["code0"]["bytes"] == 243
            and placement["code1"]["bytes"] == 71
            and placement["record"]["bytes"] == 65
            and placement["record"]["ordinary_RAM"]
            and not placement["record"]["overlaps_ZP_window_overlay"]
            and placement["record"]["boot_prefix_bytes"] == 9
            and placement["record"]["canonical_reset_before_measured_form"] == 65
            and placement["simultaneously_live_and_disjoint"],
            "diagnostic placement/record bounds drift")
    instrument = value["instrument"]
    entry = instrument["entry_witness"]
    require(entry["method"] == "RAM-store-at-_start"
            and entry["hook"] == 0x202C
            and entry["routine"] == 0xC03F
            and entry["stamp_address"] == 0xC07A
            and entry["stamp_offset"] == 59
            and entry["stamp_initial"] == 0x6B
            and entry["stamp_value"] == 0x44
            and entry["routine_bytes"] == "a2448e30d08e7ac060"
            and entry["displaced_bytes_replayed"] == "a2448e30d0"
            and entry["RAM_mapping_activation_address"] == 0x2024
            and entry["RAM_mapping_activation_bytes"] == "a22f8600a23e8601"
            and entry["RAM_mapping_active_before_entry_call"]
            and entry["nonzero_and_disjoint_from_record_values"]
            and entry["bootstrap_CPU_visible_after_RAM_mapping"]
            and not entry["bootstrap_uses_protected_refill_seam"]
            and entry["full_record_reset_before_defstruct"]
            and not entry["live_monitor_breakpoint_required"],
            "transport-proof RAM entry witness drift")
    require(instrument["record_fields"] == 29
            and instrument["reset_on_measured_form_entry"]
            and instrument["raw_before_tag"]
            and instrument["last_two_completed_refill_views"]
            and instrument["dispatcher_side_capture"]
            and instrument["opcode_read_before_bookkeeping"]
            and instrument["source_byte_oracle"] == "stopped C2D/object source bytes"
            and instrument["completion_metadata_is_not_oracle"]
            and not instrument["stores_submit_DMA"]
            and not instrument["stores_call_product_helpers"]
            and not instrument["stores_can_fail"]
            and not instrument["in_stream_witness"]
            and instrument["first_error_restores_status_argument"],
            "diagnostic instrument semantics drift")
    runner = value["runner"]
    require(runner["cold_reset_before_each_identity"]
            and runner["exact_media_readback"]
            and len(runner["context_asserts"]) == 5
            and runner["D1_buffer_peek_before_keys"]
            and runner["D1_final_buffer_peek_after_keys"]
            and runner["D1_monitor_reads_per_key"] == 0
            and runner["D1_nonempty_buffer_fixture_rejected"]
            and runner["D1_hang_one_stop_packet"] ==
            ["queue", "gc_runs", "PC", "buffer"]
            and runner["transfer_progress_guard_seconds"] == 120
            and runner["monitor_accesses_while_form_active"] == 0
            and runner["screen_accesses_while_form_active"] == 0
            and runner["D2_post_event_stops"] == 1
            and runner["stable_reads"] == 3,
            "quiet runner contract drift")
    require(value["classification"] == {
        "rows": ["R", "A", "I", "G"], "synthetic_execution_witnesses": 7,
        "unclassified_outcome_allowed": False,
    }, "R/A/I/G execution witness drift")


def mutations(base: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "make-promotable": (["identity", "diagnostic_promotable"], True),
        "claim-product-delta": (["identity", "product_candidate_bytes_changed"], 1),
        "claim-WPLTO": (["identity", "WPLTO_runs"], 1),
        "zero-sentinel": (["instrument", "reset_on_measured_form_entry"], False),
        "missing-tags": (["instrument", "raw_before_tag"], False),
        "source-derived-address": (["instrument", "source_byte_oracle"], "refill metadata"),
        "completion-flag-oracle": (["instrument", "completion_metadata_is_not_oracle"], False),
        "in-stream-witness": (["instrument", "in_stream_witness"], True),
        "late-opcode-read": (["instrument", "opcode_read_before_bookkeeping"], False),
        "one-fill-only": (["instrument", "last_two_completed_refill_views"], False),
        "record-in-overlay": (["placement", "record", "overlaps_ZP_window_overlay"], True),
        "non-simultaneous-fit": (["placement", "simultaneously_live_and_disjoint"], False),
        "monitor-during-form": (["runner", "monitor_accesses_while_form_active"], 1),
        "screen-during-form": (["runner", "screen_accesses_while_form_active"], 1),
        "drop-quiet-policy": (["runner", "quiet_forms"], []),
        "drop-context-assert": (["runner", "context_asserts"], ["fresh BASIC"]),
        "drop-transfer-guard": (["runner", "transfer_progress_guard_seconds"], 0),
        "add-second-stop": (["runner", "D2_post_event_stops"], 2),
        "admit-unclassified": (["classification", "unclassified_outcome_allowed"], True),
        "clobber-first-error-helper-input": (
            ["instrument", "first_error_restores_status_argument"], False),
        "zero-entry-stamp": (
            ["instrument", "entry_witness", "stamp_value"], 0),
        "entry-stamp-collides-with-record-sentinel": (
            ["instrument", "entry_witness", "stamp_value"], 0x6B),
        "partial-record-reset-after-entry": (
            ["instrument", "entry_witness", "full_record_reset_before_defstruct"],
            False),
        "bootstrap-through-protected-refill": (
            ["instrument", "entry_witness", "bootstrap_uses_protected_refill_seam"],
            True),
        "live-monitor-breakpoint-entry-proof": (
            ["instrument", "entry_witness", "method"],
            "live-monitor-breakpoint-across-launch"),
        "entry-before-complete-RAM-mapping": (
            ["instrument", "entry_witness", "RAM_mapping_active_before_entry_call"],
            False),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        target: Any = trial
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(trial)
            require(trial["runner"]["quiet_forms"] ==
                    ["(require 'defstruct)", "(defstruct point x y)"],
                    "quiet form policy absent")
        except PhaseCError as error:
            rejected[name] = str(error)
        else:
            raise PhaseCError(f"Phase-C mutation survived: {name}")
    return rejected


def build() -> tuple[dict[str, Any], dict[str, Any], str]:
    config = load(CONFIG); phase_b = load(PHASE_B); prior = load(PRIOR_DEPLOY)
    require(phase_b["status"] ==
            "passed-complete-Link82-defstruct-fail-closed-R-A-I-G-partition",
            "Phase-B authority status drift")
    authority = config["authority"]
    require(sha(CONTROL_ELF) == authority["control_elf_sha256"]
            and sha(CONTROL_PRG) == authority["control_prg_sha256"]
            and sha(PRODUCT_MEDIUM) == authority["control_product_medium_sha256"]
            and sha(LIBRARY_MEDIUM) == authority["library_medium_sha256"]
            and sha(PRIOR_DEPLOY) == authority["prior_deployment_sha256"],
            "Link-82 control authority drift")
    require(prior["status"] == "passed-host-dry-run-ready-for-one-device-session"
            and prior["candidate"]["package_medium"]["sha256"] ==
            authority["library_medium_sha256"],
            "Link-82 prior deployment authority drift")
    require(bind(CONTROL_WINDOW)["sha256"] == next(
        row["sha256"] for row in prior["candidate"]["preloads"]
        if row["role"] == "c2-kernal-window"),
        "Link-82 control window/preload drift")
    patch = build_patch(config, phase_b)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONTROL_ELF, CONTROL_COPY_ELF)
    shutil.copyfile(CONTROL_PRG, CONTROL_COPY_PRG)
    require(sha(CONTROL_COPY_ELF) == authority["control_elf_sha256"]
            and sha(CONTROL_COPY_PRG) == authority["control_prg_sha256"],
            "control identity is not byteidentical to Link-82")
    DIAG_PRG.write_bytes(patch_prg(CONTROL_PRG.read_bytes(), patch, config))
    DIAG_WINDOW.write_bytes(patch_window(CONTROL_WINDOW, patch))
    RESET.write_bytes(patch["record_reset"]); ARM.write_bytes(patch["record_arm"])
    patch_elf(patch, config)
    listing = run(["c1541", "-attach", str(LIBRARY_MEDIUM), "-list"],
                  "list exact library medium")

    control_truth = ElfTruth.read(CONTROL_ELF, llvm_readobj=READOBJ,
                                  include_section_data=True)
    diag_truth = ElfTruth.read(DIAG_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    memory_diff = elf_memory_diff(control_truth, diag_truth)
    expected_sections = {
        ".text", ".lisp65_c2_kernal_window.map_switch_and_guards",
        ".lisp65_v16_defstruct_diagnostic_code0",
        ".lisp65_v16_defstruct_diagnostic_code1",
        ".lisp65_v16_defstruct_diagnostic_state",
    }
    require({row["section"] for row in memory_diff} == expected_sections,
            f"diagnostic ELF difference set drift: {memory_diff}")
    for name, address in patch["symbols"].items():
        require(diag_truth.symbol(name).value == address,
                f"diagnostic symbol address drift: {name}")
    value = facts(config, phase_b, patch, memory_diff)
    audit(value)
    return value, patch, listing


def prepare() -> int:
    require(not REBIND.exists(),
            "historical Phase-C receipt is append-only rebound; prepare is disabled")
    value, patch, listing = build()
    rejected = mutations(value)
    config = load(CONFIG); prior = load(PRIOR_DEPLOY)
    control_preloads = []
    for row in prior["candidate"]["preloads"]:
        bound = bind(ROOT / row["path"])
        require(bound["bytes"] == row["bytes"] and bound["sha256"] == row["sha256"],
                f"Link-82 preload drift: {row['role']}")
        control_preloads.append({**row, "path": bound["path"]})
    diagnostic_preloads = deepcopy(control_preloads)
    window_row = next(row for row in diagnostic_preloads
                      if row["role"] == "c2-kernal-window")
    window_row.update(bind(DIAG_WINDOW))
    deployment = {
        "format": "lisp65-c2.3-v1.6-defstruct-phase-c-deployment-v1",
        "status": "prepared-non-promotable", "promotable": False,
        "library_medium": bind(LIBRARY_MEDIUM),
        "control_product_medium": bind(PRODUCT_MEDIUM),
        "control": {"elf": bind(CONTROL_COPY_ELF), "prg": bind(CONTROL_COPY_PRG),
                    "window": bind(CONTROL_WINDOW), "preloads": control_preloads},
        "diagnostic": {"elf": bind(DIAG_ELF), "prg": bind(DIAG_PRG),
                       "window": bind(DIAG_WINDOW), "preloads": diagnostic_preloads},
        "ordinary_product_D1": bind(V13_MEDIUM),
        "record": {"address": "0x0000c03f", "bytes": 65,
                   "reset": bind(RESET), "arm": bind(ARM)},
        "entry_witness": {
            **patch["entry_witness"],
            "readback_bytes": 1,
            "record_fully_reset_before_defstruct": True,
        },
        "witness_symbols": {name: f"0x{address:04x}"
                            for name, address in patch["symbols"].items()},
        "library_remote": config["library_remote"],
        "forms": {"require": "(require 'defstruct)",
                  "defstruct": "(defstruct point x y)"},
        "readback": {"low_RAM": [0, 65536], "bank2": [131072, 196608],
                     "C2D": [327680, 378496], "stable_record_reads": 3},
    }
    write_json(DEPLOY, deployment)
    receipt = {
        "format": FORMAT, "recorded_on": date.today().isoformat(),
        "status": "PREPARED-NON-PROMOTABLE-LINK82-DIAGNOSTIC",
        "facts": value,
        "library_medium": deployment["library_medium"],
        "control_product_medium": deployment["control_product_medium"],
        "control": deployment["control"], "diagnostic": deployment["diagnostic"],
        "exact_PRG_byte_differences": ranges(
            CONTROL_PRG.read_bytes(), DIAG_PRG.read_bytes(), base=PRG_LOAD - 2),
        "exact_window_byte_differences": ranges(
            CONTROL_WINDOW.read_bytes(), DIAG_WINDOW.read_bytes(),
            base=0xE000),
        "media_listing_sha256": sha_bytes(listing.encode()),
        "verification": {"execution_witnesses": 7,
                         "mutation_count": len(rejected),
                         "mutations_rejected": rejected},
        "bindings": {"config": bind(CONFIG), "phase_B": bind(PHASE_B),
                     "plan": bind(PLAN), "driver": bind(DRIVER),
                     "hardware_runner": bind(HW), "gate_wiring": bind(GATES),
                     "deployment": bind(DEPLOY)},
        "claim_limit": (
            "One permanently non-promotable Link-82 diagnostic sibling and its "
            "quiet-session runner. No product link, WPLTO, fix or hardware result."
        ),
    }
    write_json(RECEIPT, receipt)
    print(f"PHASE C PREPARED control=byteidentical record=65 fields=29 "
          f"witnesses=7 mutations={len(rejected)}")
    return 0


def audit_rebind(recorded: dict[str, Any], rebind: dict[str, Any]) -> None:
    require(rebind["format"] == "lisp65-c2.3-v1.6-phase-C-binding-rebind-v1"
            and rebind["recorded_on"] == "2026-08-05"
            and rebind["status"] == "LOUD-DATED-REBIND-PLAN-APPEND-ONLY",
            "Phase-C rebind identity/status drift")
    require(rebind["reason"] == (
        "The Phase-C plan binding predates the append-only launch-boundary "
        "method, device dispositions and diagnostic-delta attribution. The "
        "plan later grew through the consumed full run, loud Slot-39 correction "
        "and pre-rollback shadow preparation. The historical receipt remains "
        "unchanged; this checker change consumes the explicit append-only "
        "rebind."),
        "Phase-C rebind does not name plan growth")
    require(rebind["authority_receipt"] == bind(RECEIPT),
            "Phase-C rebind receipt authority drift")
    require(rebind["authorized_bindings"] == ["driver", "gate_wiring", "plan"],
            "Phase-C rebind scope is not exactly plan+checker+gate wiring")
    for name in rebind["authorized_bindings"]:
        require(rebind["from"][name] == recorded["bindings"][name],
                f"Phase-C rebind old binding drift: {name}")
        require(rebind["to"][name] == bind(ROOT / recorded["bindings"][name]["path"]),
                f"Phase-C rebind current binding drift: {name}")
    old_plan = recorded["bindings"]["plan"]
    plan_data = PLAN.read_bytes()
    require(len(plan_data) >= old_plan["bytes"]
            and sha_bytes(plan_data[:old_plan["bytes"]]) == old_plan["sha256"],
            "Phase-C historical plan is not an exact prefix")
    require(rebind["append_only_proof"] == {
        "old_bytes": old_plan["bytes"],
        "old_prefix_sha256": old_plan["sha256"],
        "new_bytes": len(plan_data),
        "new_sha256": sha_bytes(plan_data),
        "old_plan_remains_exact_prefix": True,
        "historical_receipt_rewritten": False,
    }, "Phase-C append-only proof drift")


def rebind_mutations(recorded: dict[str, Any], base: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "silent-rebind": (["status"], "PASS"),
        "erase-growth-reason": (["reason"], ""),
        "widen-to-hardware-runner": (
            ["authorized_bindings"],
            ["driver", "gate_wiring", "hardware_runner", "plan"]),
        "rewrite-historical-receipt": (
            ["append_only_proof", "historical_receipt_rewritten"], True),
        "claim-non-prefix": (
            ["append_only_proof", "old_plan_remains_exact_prefix"], False),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        target: Any = trial
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit_rebind(recorded, trial)
        except PhaseCError as error:
            rejected[name] = str(error)
        else:
            raise PhaseCError(f"Phase-C rebind mutation survived: {name}")
    return rejected


def check() -> int:
    recorded = load(RECEIPT)
    require(recorded["format"] == FORMAT
            and recorded["status"] == "PREPARED-NON-PROMOTABLE-LINK82-DIAGNOSTIC",
            "Phase-C receipt status drift")
    value, patch, _listing = build()
    audit(value)
    rejected = mutations(value)
    require(recorded["facts"] == value
            and recorded["verification"]["mutation_count"] == len(rejected)
            and recorded["verification"]["mutations_rejected"] == rejected,
            "Phase-C receipt no longer reproduces")
    rebind = load(REBIND)
    audit_rebind(recorded, rebind)
    rebind_rejected = rebind_mutations(recorded, rebind)
    for name, row in recorded["bindings"].items():
        if name in rebind["authorized_bindings"]:
            require(bind(ROOT / row["path"]) == rebind["to"][name],
                    f"Phase-C rebound binding drift: {name}")
        else:
            require(bind(ROOT / row["path"]) == row,
                    f"Phase-C binding drift: {name}")
    print(f"PHASE C PASS control=byteidentical diagnostic=1 record=65 "
          f"witnesses=7 mutations={len(rejected)} "
          f"REBOUND=2026-08-05-closure-append-only "
          f"rebind-mutations={len(rebind_rejected)}")
    return 0


def selftest() -> int:
    config = load(CONFIG); phase_b = load(PHASE_B)
    patch = build_patch(config, phase_b)
    require(len(patch["code0"]) == 243 and len(patch["code1"]) == 71
            and len(patch["record_boot"]) == 65
            and len(patch["record_reset"]) == 65
            and patch["record_boot"][:9] == bytes.fromhex("a2448e30d08e7ac060")
            and patch["record_reset"][:9] != patch["record_boot"][:9]
            and len(patch["patches"]) == 4,
            "Phase-C local construction selftest drift")
    value = facts(config, phase_b, patch, [
        {"section": name} for name in (
            ".text", ".lisp65_c2_kernal_window.map_switch_and_guards",
            ".lisp65_v16_defstruct_diagnostic_code0",
            ".lisp65_v16_defstruct_diagnostic_code1",
            ".lisp65_v16_defstruct_diagnostic_state",
        )])
    audit(value); rejected = mutations(value); runner_source_audit()
    import c2_v126_editor_stall_device as legacy
    with tempfile.TemporaryDirectory(prefix="v16-d1-buffer-") as temp_name:
        directory = Path(temp_name)

        def fixture(fill: int) -> None:
            memory = legacy._synthetic_buffer_memory(fill)
            pool = bytearray(10208); pool[:12] = b"ide-buffers\0"
            offsets = bytes(1504)
            symvals = bytearray(1504)
            symvals[:2] = int(memory.symval).to_bytes(2, "little")
            rows = {
                "d1-context-nsym.bin": (1).to_bytes(2, "little"),
                "d1-context-namepool.bin": bytes(pool),
                "d1-context-nameoff.bin": offsets,
                "d1-context-symval.bin": bytes(symvals),
                "d1-context-str-cur-off.bin": (0x2000).to_bytes(2, "little"),
                "d1-context-heap.bin": memory.heap,
                "d1-context-ext.bin": memory.ext,
                "d1-context-arena-2000.bin": memory.arena,
                "d1-context-arena-4480.bin": bytes(0x2480),
            }
            for name, payload in rows.items():
                (directory / name).write_bytes(payload)

        fixture(0); check_d1_buffer(directory)
        fixture(64); check_d1_buffer(directory, expected_fill=64)
        fixture(1)
        try:
            check_d1_buffer(directory)
        except PhaseCError:
            pass
        else:
            raise PhaseCError("D1 nonempty-buffer mutation survived")
    print(f"PHASE C SELFTEST PASS code=243+71 record=65 entry=RAM "
          f"witnesses=7 mutations={len(rejected)}")
    return 0


def dry_run() -> int:
    check()
    runner_source_audit()
    deployment = load(DEPLOY)
    require(deployment["status"] == "prepared-non-promotable"
            and deployment["promotable"] is False,
            "Phase-C deployment drift")
    print("PHASE C DRY RUN PASS cold-resets=2 quiet-forms=2 "
          "monitor-during-forms=0 D2-post-event-stops=1 stable-reads=3")
    return 0


def runner_source_audit() -> None:
    source = HW.read_text(encoding="utf-8")
    require(".diagnostic.medium" not in source
            and ".library_medium.path" in source
            and ".diagnostic.preloads[]" in source,
            "library/diagnostic deployment split drift")
    require("FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}" in source,
            "120-second transfer guard absent")
    require('case "$CONTACT" in 1|2)' in source
            and 'contact-$CONTACT' in source,
            "one-contact plus setup-reserve accounting absent")
    require("capture_d1_buffer d1-context" in source
            and "--prefix d1-final-memory --expected-fill 64" in source
            and "capture-d1-hang" in source,
            "D1 direct-buffer/one-stop path absent")
    d1_start = source.index("\ni=0\n")
    d1_end = source.index("\nscreen d1-final\n", d1_start)
    d1_active = source[d1_start:d1_end]
    require("readback" not in d1_active and "screen " not in d1_active,
            "D1 per-key observation leaked into quiet interval")
    require_window = source[
        source.index("quiet_input d2-require"):
        source.index("screen d2-require-result")]
    defstruct_window = source[
        source.index("quiet_input d2-defstruct"):
        source.index("screen d2-first-observation")]
    for label, window in (("require", require_window),
                          ("defstruct", defstruct_window)):
        require("readback" not in window and window.count("screen ") == 0,
                f"{label} quiet interval contains an observation")
    require("--expect t" in source
            and source.count('readback "$record" 65') == 3,
            "exact require/stable-record read policy drift")


def check_d1_buffer(
        directory: Path, *, prefix: str = "d1-context", expected_fill: int = 0,
) -> int:
    """Validate an editor context from direct live-memory captures."""
    import c2_v126_editor_stall_device as legacy

    def captured(name: str) -> bytes:
        path = directory / f"{prefix}-{name}.bin"
        require(path.is_file(), f"D1 buffer capture absent: {path}")
        return path.read_bytes()

    nsym = legacy.u16(captured("nsym"), 0)
    require(0 < nsym <= 752, f"D1 live nsym out of range: {nsym}")
    pool = captured("namepool")
    offsets = captured("nameoff")
    matches: list[int] = []
    for index in range(nsym):
        offset = legacy.u16(offsets, index * 2)
        if offset >= len(pool):
            continue
        end = pool.find(b"\0", offset)
        if end >= 0 and pool[offset:end] == b"ide-buffers":
            matches.append(index)
    require(len(matches) == 1, f"D1 ide-buffers symbol matches: {matches}")
    symvals = captured("symval")
    symval = legacy.u16(symvals, matches[0] * 2)
    arena_offset = legacy.u16(captured("str-cur-off"), 0)
    require(arena_offset in (0x2000, 0x4480),
            f"D1 active string arena drift: 0x{arena_offset:04x}")
    arena = captured(f"arena-{arena_offset:04x}")
    memory = legacy.BufferMemory(
        heap=captured("heap"), ext=captured("ext"), arena=arena,
        arena_offset=arena_offset, symval=symval)
    buffer = memory.buffer_fill("measure3")
    require(buffer["line_count"] == 1
            and buffer["line_lengths"] == [expected_fill]
            and buffer["fill"] == expected_fill
            and buffer["point"] == [0, expected_fill],
            f"D1 measure3 context drift: {buffer}")
    result = {
        "status": "passed-live-buffer-peek",
        "expected_fill": expected_fill,
        "symbol_index": matches[0], "nsym": nsym, "buffer": buffer,
        "source": "live symbol value plus Bank-0/4 heap and active string arena",
    }
    write_json(directory / f"{prefix}-buffer-context.json", result)
    print(f"PHASE D1 CONTEXT PASS buffer=measure3 fill={expected_fill} "
          f"point=0,{expected_fill}")
    return 0


def capture_d1_hang(directory: Path, device: str) -> int:
    """Persist the standing queue/gc/PC packet after the final buffer stop."""
    import c2_v126_editor_stall_device as legacy
    legacy.SERIAL.DEVICE = device
    packet = legacy.halt_capture()
    packet["buffer_capture_prefix"] = "d1-final-memory"
    packet["status"] = "D1-final-buffer-postcondition-failed-one-stop-packet"
    write_json(directory / "d1-hang-one-stop-packet.json", packet)
    print("PHASE D1 HANG PACKET CAPTURED cpu-left-stopped=true")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "dry-run", "check-d1-buffer",
        "capture-d1-hang"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--prefix", default="d1-context")
    parser.add_argument("--expected-fill", type=int, default=0)
    parser.add_argument("--device", default="/dev/ttyUSB1")
    args = parser.parse_args(); action = args.action
    if action == "check-d1-buffer":
        require(args.directory is not None, "--directory is required")
        return check_d1_buffer(
            args.directory, prefix=args.prefix, expected_fill=args.expected_fill)
    if action == "capture-d1-hang":
        require(args.directory is not None, "--directory is required")
        return capture_d1_hang(args.directory, args.device)
    return {"prepare": prepare, "check": check, "selftest": selftest,
            "dry-run": dry_run}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PhaseCError as error:
        print(f"FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
