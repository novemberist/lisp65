#!/usr/bin/env python3
"""Build the owner-authorized MAP CPU-read + progress-ring sibling.

The probe runs once from the low-RAM CRT handoff, before ``main``.  It maps a
small Bank-5 span and a small Attic span onto CPU block 2, compares each span
64 times with bytes taken from the delivered media roles, and restores the
ordinary low map, low megabyte register and llvm-mos Z=0 ABI before tail-
jumping to the displaced ``main`` call.  The already reviewed progress ring
continues independently during LOADING LIBRARIES.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
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
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v16_defstruct_phase_c as PHASE_C  # noqa: E402
import c2_v20_loading_libraries_progress_ring as RING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
MAP_CONTRACT = ROOT / "config/c2-mapped-far-map-contract-v2.json"
CPU_RECEIPT = ARCH / "c2.3-v2.0-cpu-transport-reconciliation-receipt.json"
RING_RECEIPT = ARCH / "c2.3-v2.0-loading-libraries-progress-ring-receipt.json"
USER_GUIDE = ROOT / (
    "build/upstream-verification/mega65-user-guide/"
    "appendix-45gs02-registers.tex")
CORE = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"

OUT = ROOT / "build/c2.3/v2.0-loading-libraries-progress-map"
ART = OUT / "artifacts"
PROBE_PRG = ART / "diagnostic-loading-libraries-progress-map.prg"
PROBE_ELF = ART / "diagnostic-loading-libraries-progress-map.elf"
PROBE_CODE = ART / "map-cpu-transport-probe.bin"
PROBE_D81 = OUT / "lisp65-loading-libraries-progress-map.d81"
PROBE_DESCRIPTOR = OUT / "boot.id"
PROBE_STAGER = OUT / "autoboot.c65"
PROBE_STAGER_MAP = OUT / "autoboot.c65.map"
PROBE_STAGER_BUILD = OUT / "stager-build"
DEPLOY = OUT / "deployment.json"
SESSION = ROOT / "config/c2-v20-loading-libraries-progress-map-session.json"
RUNNER = ROOT / "scripts/c2-v20-loading-libraries-progress-map-hw.sh"
RECEIPT = ARCH / "c2.3-v2.0-map-cpu-transport-probe-receipt.json"

AUTHORIZATION = "27f4177d"
FORMAT = "lisp65-c2.3-v2.0-map-cpu-transport-probe-v1"
RECORDED_ON = "2026-08-14"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

PRG_LOAD = 0x2001
HOOK = 0x2047
DISPLACED_MAIN = 0xA423
PROBE = 0xB324
PROBE_LIMIT = 0xB3B0
CPU_WINDOW = 0x4000
STATUS_BANK5 = 0xB5C2
STATUS_ATTIC = 0xB5C3
STATUS_RESET = 0xD7
STATUS_RUNNING_OR_MISMATCH = 0xE1
STATUS_PASS = 0xA5
REPEATS = 64
SIGNATURE_BYTES = 4
SECTION = ".lisp65_v20_map_cpu_transport_probe"

BANK5_PHYSICAL = 0x00050000
ATTIC_PHYSICAL = 0x08100000
BANK5_MAP_A = 0xC0
BANK5_MAP_X = 0x44
ATTIC_MB = 0x81
ATTIC_MAP_A = 0xC0
ATTIC_MAP_X = 0x4F


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


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
        temporary = Path(handle.name)
        handle.write(payload)
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
    require("progress-ring contact" in text
            and "map-based cpu-transport probe row" in text
            and "bank-5 span and an attic span" in text
            and "same session if ready" in text,
            "MAP/ring contact authorization drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


class Asm:
    def __init__(self, origin: int):
        self.origin = origin
        self.raw = bytearray()
        self.labels: dict[str, int] = {}
        self.branches: list[tuple[int, str]] = []
        self.absolutes: list[tuple[int, str]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.raw)

    def emit(self, *values: int) -> None:
        self.raw.extend(value & 0xFF for value in values)

    def absolute(self, opcode: int, address: int) -> None:
        self.emit(opcode, address, address >> 8)

    def absolute_label(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0, 0)
        self.absolutes.append((len(self.raw) - 2, label))

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.pc

    def branch(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.branches.append((len(self.raw) - 1, label))

    def finish(self) -> bytes:
        for offset, label in self.branches:
            require(label in self.labels, f"branch label absent: {label}")
            after = self.origin + offset + 1
            delta = self.labels[label] - after
            require(-128 <= delta <= 127, f"branch out of range: {label}")
            self.raw[offset] = delta & 0xFF
        for offset, label in self.absolutes:
            require(label in self.labels, f"absolute label absent: {label}")
            address = self.labels[label]
            self.raw[offset] = address & 0xFF
            self.raw[offset + 1] = address >> 8
        return bytes(self.raw)


def build_probe(bank5_signature: bytes, attic_signature: bytes) -> tuple[bytes, dict[str, Any]]:
    require(len(bank5_signature) == len(attic_signature) == SIGNATURE_BYTES,
            "signature extent drift")
    a = Asm(PROBE)

    def map_call(map_a: int, map_x: int) -> None:
        a.emit(0xA9, map_a, 0xA2, map_x)
        a.absolute_label(0x20, "map_helper")

    def compare(name: str, status: int, table: str) -> None:
        a.emit(0xA9, STATUS_RUNNING_OR_MISMATCH)
        a.absolute(0x8D, status)
        a.emit(0xA0, REPEATS)
        a.label(f"{name}_outer")
        a.emit(0xA2, 0x00)
        a.label(f"{name}_inner")
        a.absolute(0xBD, CPU_WINDOW)       # LDA $4000,X
        a.absolute_label(0xDD, table)      # CMP table,X
        a.branch(0xD0, f"{name}_done")
        a.emit(0xE8, 0xE0, SIGNATURE_BYTES)
        a.branch(0xD0, f"{name}_inner")
        a.emit(0x88)
        a.branch(0xD0, f"{name}_outer")
        a.emit(0xA9, STATUS_PASS)
        a.absolute(0x8D, status)
        a.label(f"{name}_done")

    # Primary MAP guidance: first disable low mapping, then set the megabyte,
    # then establish the ordinary 20-bit offset.  Block 7 remains mapped so
    # the E000 KERNAL window and IRQ closure retain their existing identity.
    map_call(0x00, 0x00)                   # low map off
    map_call(0x00, 0x0F)                   # low MB = $00
    map_call(BANK5_MAP_A, BANK5_MAP_X)      # $4000 -> $00050000
    compare("bank5", STATUS_BANK5, "bank5_table")

    map_call(0x00, 0x00)                   # low map off before MB transition
    map_call(ATTIC_MB, 0x0F)               # low MB = $81
    map_call(ATTIC_MAP_A, ATTIC_MAP_X)      # $4000 -> $08100000
    compare("attic", STATUS_ATTIC, "attic_table")

    map_call(0x00, 0x00)                   # leave low map disabled
    map_call(0x00, 0x0F)                   # restore low MB = $00
    a.emit(0x4C, DISPLACED_MAIN, DISPLACED_MAIN >> 8)

    a.label("map_helper")
    a.emit(0xA0, 0x00,                     # LDY #$00: high offset
           0xA3, 0x80,                     # LDZ #$80: preserve block 7
           0x5C,                           # MAP
           0xEA,                           # EOM
           0xA3, 0x00,                     # restore llvm-mos Z=0
           0x60)                           # RTS
    a.label("bank5_table")
    a.raw.extend(bank5_signature)
    a.label("attic_table")
    a.raw.extend(attic_signature)
    code = a.finish()
    require(len(code) <= PROBE_LIMIT - PROBE,
            f"MAP CPU probe exceeds ordinary-text headroom: {len(code)}")
    image = code + bytes(PROBE_LIMIT - PROBE - len(code))
    return image, {"used_bytes": len(code),
                   "headroom_bytes": PROBE_LIMIT - PROBE - len(code),
                   "labels": {key: f"0x{value:04x}"
                              for key, value in sorted(a.labels.items())},
                   "bank5_signature": bank5_signature.hex(),
                   "attic_signature": attic_signature.hex()}


def resolve(address: int, map_low: int, offset_low: int, mb_low: int) -> int:
    block = (address >> 13) & 3
    if address < 0x8000 and map_low & (1 << block):
        high = (offset_low + (address >> 8)) & 0xFFF
        return (mb_low << 20) | (high << 8) | (address & 0xFF)
    return address


def execute_probe(image: bytes, bank5: bytes, attic: bytes) -> dict[str, Any]:
    """Independent executable model for the exact emitted opcode stream."""
    memory = bytearray(65536)
    memory[PROBE:PROBE_LIMIT] = image
    memory[STATUS_BANK5] = STATUS_RESET
    memory[STATUS_ATTIC] = STATUS_RESET
    physical: dict[int, int] = {}
    for index, byte in enumerate(bank5):
        physical[BANK5_PHYSICAL + index] = byte
    for index, byte in enumerate(attic):
        physical[ATTIC_PHYSICAL + index] = byte
    pc = PROBE
    a = x = y = z = 0
    zero = False
    call_stack: list[int] = []
    map_low = 0
    offset_low = 0
    mb_low = 0
    map_high = 8
    mapped_reads = {"bank5": 0, "attic": 0, "other": 0}
    map_tuples: list[list[int]] = []
    eom_count = 0

    def read(address: int) -> int:
        target = resolve(address, map_low, offset_low, mb_low)
        if target >= 0x10000:
            if BANK5_PHYSICAL <= target < BANK5_PHYSICAL + len(bank5):
                mapped_reads["bank5"] += 1
            elif ATTIC_PHYSICAL <= target < ATTIC_PHYSICAL + len(attic):
                mapped_reads["attic"] += 1
            else:
                mapped_reads["other"] += 1
            return physical.get(target, 0xFF)
        return memory[target]

    for _ in range(10000):
        op = memory[pc]
        pc += 1
        if op in (0xA9, 0xA2, 0xA0, 0xA3, 0xE0):
            value = memory[pc]
            pc += 1
            if op == 0xA9:
                a = value; zero = a == 0
            elif op == 0xA2:
                x = value; zero = x == 0
            elif op == 0xA0:
                y = value; zero = y == 0
            elif op == 0xA3:
                z = value; zero = z == 0
            else:
                zero = x == value
        elif op in (0x8D, 0xBD, 0xDD, 0x20, 0x4C):
            address = memory[pc] | memory[pc + 1] << 8
            pc += 2
            if op == 0x8D:
                memory[address] = a
            elif op == 0xBD:
                a = read((address + x) & 0xFFFF); zero = a == 0
            elif op == 0xDD:
                zero = a == read((address + x) & 0xFFFF)
            elif op == 0x20:
                call_stack.append(pc); pc = address
            else:
                if address == DISPLACED_MAIN:
                    break
                pc = address
        elif op == 0xD0:
            delta = memory[pc]
            pc += 1
            if not zero:
                pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif op == 0xE8:
            x = (x + 1) & 0xFF; zero = x == 0
        elif op == 0x88:
            y = (y - 1) & 0xFF; zero = y == 0
        elif op == 0x5C:
            map_tuples.append([a, x, y, z])
            if x == 0x0F:
                mb_low = a
            else:
                offset_low = ((x & 0x0F) << 8) | a
                map_low = x >> 4
            if z != 0x0F:
                map_high = z >> 4
        elif op == 0xEA:
            eom_count += 1
        elif op == 0x60:
            require(call_stack, "probe model RTS without JSR")
            pc = call_stack.pop()
        else:
            raise ProbeError(f"unmodeled probe opcode 0x{op:02x} at 0x{pc-1:04x}")
    else:
        raise ProbeError("probe model did not reach displaced main")

    require(memory[STATUS_BANK5] == memory[STATUS_ATTIC] == STATUS_PASS,
            "MAP CPU probe did not pass both delivery-bound signatures")
    require(mapped_reads == {"bank5": REPEATS * SIGNATURE_BYTES,
                             "attic": REPEATS * SIGNATURE_BYTES,
                             "other": 0},
            f"MAP CPU probe read coverage drift: {mapped_reads}")
    require(map_low == 0 and map_high == 8 and mb_low == 0 and z == 0,
            "MAP CPU probe did not restore mapping/MB/Z state")
    require(eom_count == len(map_tuples) == 8,
            "MAP/EOM pairing or sequence count drift")
    return {"status_bank5": f"0x{memory[STATUS_BANK5]:02x}",
            "status_attic": f"0x{memory[STATUS_ATTIC]:02x}",
            "mapped_reads": mapped_reads, "map_calls": len(map_tuples),
            "EOMs": eom_count, "final_map_low": map_low,
            "final_map_high": map_high, "final_MB_low": mb_low,
            "final_Z": z, "tuples": [[f"0x{item:02x}" for item in row]
                                      for row in map_tuples]}


def mutate_executable(image: bytes, bank5: bytes, attic: bytes,
                      layout: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, bytearray] = {}
    labels = {key: int(value, 0) - PROBE for key, value in layout["labels"].items()}

    wrong_mb = bytearray(image)
    needle = bytes((0xA9, ATTIC_MB, 0xA2, 0x0F))
    at = wrong_mb.index(needle); wrong_mb[at + 1] = 0x80
    cases["attic-megabyte-transposed"] = wrong_mb

    wrong_bank5 = bytearray(image)
    needle = bytes((0xA9, BANK5_MAP_A, 0xA2, BANK5_MAP_X))
    at = wrong_bank5.index(needle); wrong_bank5[at + 1] = 0xB0
    cases["bank5-offset-drift"] = wrong_bank5

    wrong_block = bytearray(image)
    needle = bytes((0xA9, ATTIC_MAP_A, 0xA2, ATTIC_MAP_X))
    at = wrong_block.index(needle); wrong_block[at + 3] = 0x2F
    cases["attic-wrong-CPU-block"] = wrong_block

    corrupt_b5 = bytearray(image)
    corrupt_b5[labels["bank5_table"]] ^= 0x80
    cases["bank5-oracle-not-delivery-bound"] = corrupt_b5

    corrupt_attic = bytearray(image)
    corrupt_attic[labels["attic_table"]] ^= 0x80
    cases["attic-oracle-not-delivery-bound"] = corrupt_attic

    no_restore_mb = bytearray(image)
    restore = bytes((0xA9, 0x00, 0xA2, 0x0F))
    at = no_restore_mb.rindex(restore); no_restore_mb[at + 1] = 0x81
    cases["leave-attic-megabyte-live"] = no_restore_mb

    no_eom = bytearray(image)
    at = no_eom.index(bytes((0x5C, 0xEA))) + 1
    no_eom[at] = 0x00
    cases["MAP-without-EOM"] = no_eom

    no_z_restore = bytearray(image)
    helper = labels["map_helper"]
    marker = bytes((0xA3, 0x00, 0x60))
    at = no_z_restore.index(marker, helper)
    no_z_restore[at + 1] = 0x80
    cases["leave-Z-nonzero"] = no_z_restore

    rejected: dict[str, str] = {}
    for name, candidate in cases.items():
        try:
            execute_probe(bytes(candidate), bank5, attic)
        except ProbeError as error:
            rejected[name] = str(error)
        else:
            raise ProbeError(f"MAP CPU executable mutation survived: {name}")
    require(len(rejected) == 8, "MAP CPU executable mutation count drift")
    return rejected


def patch_elf(base_truth: ElfTruth, text: bytes, probe: bytes) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    text_path = ART / "text.bin"
    text_path.write_bytes(text)
    PROBE_CODE.write_bytes(probe)
    run([str(OBJCOPY), f"--update-section=.text={text_path}",
         f"--add-section={SECTION}={PROBE_CODE}",
         f"--set-section-flags={SECTION}=alloc,load,code",
         f"--add-symbol=lisp65_v20_map_cpu_probe=0x{PROBE:x},global,function",
         f"--add-symbol=lisp65_v20_map_cpu_bank5_status=0x{STATUS_BANK5:x},global,object",
         f"--add-symbol=lisp65_v20_map_cpu_attic_status=0x{STATUS_ATTIC:x},global,object",
         str(RING.DIAG_ELF), str(PROBE_ELF)], "derive MAP CPU probe ELF")
    PHASE_C.patch_elf_section_addresses(PROBE_ELF, {SECTION: PROBE})
    truth = ElfTruth.read(PROBE_ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(truth.section_bytes(SECTION) == probe
            and truth.section(SECTION).address == PROBE,
            "MAP CPU probe ELF section identity drift")
    require(base_truth.section(".text").address == 0x2023,
            "base text identity drift")


def build_medium() -> dict[str, Any]:
    control = SISTER.medium_roles(RING.DIAG_D81, OUT / "readback-control")
    paths = SISTER.role_paths(control)
    donor = paths["boot.id"].read_bytes()
    donor_rows, donor_id, profile_id = SISTER.descriptor_rows(donor, paths)
    SISTER.target_descriptor_check(donor, donor_rows,
                                   descriptor_build_id=donor_id,
                                   stager_build_id=donor_id)
    payloads = dict(paths); payloads["lisp65.prg"] = PROBE_PRG
    rows, inherited_id, inherited_profile = SISTER.descriptor_rows(donor, payloads)
    require(inherited_id == donor_id and inherited_profile == profile_id,
            "progress-ring donor world drift")
    descriptor, build_id = MEDIA.make_descriptor(rows, profile_id)
    PROBE_DESCRIPTOR.write_bytes(descriptor)
    SISTER.target_descriptor_check(descriptor, rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    stager_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=PROBE_STAGER_BUILD,
        stager=PROBE_STAGER, stager_map=PROBE_STAGER_MAP)
    shutil.copyfile(RING.DIAG_D81, PROBE_D81)
    run(["c1541", "-attach", str(PROBE_D81),
         "-delete", "lisp65.prg", "-write", str(PROBE_PRG), "lisp65.prg",
         "-delete", "boot.id", "-write", str(PROBE_DESCRIPTOR), "boot.id",
         "-delete", "autoboot.c65", "-write", str(PROBE_STAGER), "autoboot.c65"],
        "replace MAP CPU probe D81 roles")
    readback = SISTER.medium_roles(PROBE_D81, OUT / "readback-diagnostic")
    for name, row in control.items():
        expected = {"lisp65.prg": PROBE_PRG, "boot.id": PROBE_DESCRIPTOR,
                    "autoboot.c65": PROBE_STAGER}.get(name)
        if expected is None:
            require(readback[name]["sha256"] == row["sha256"],
                    f"unrelated bundled role changed: {name}")
        else:
            require(readback[name]["sha256"] == digest(expected.read_bytes()),
                    f"bundled role readback drift: {name}")
    rb_paths = SISTER.role_paths(readback)
    rb_rows, rb_id, rb_profile = SISTER.descriptor_rows(
        rb_paths["boot.id"].read_bytes(), rb_paths)
    require(rb_id == build_id and rb_profile == profile_id,
            "bundled diagnostic readback world drift")
    SISTER.target_descriptor_check(rb_paths["boot.id"].read_bytes(), rb_rows,
                                   descriptor_build_id=rb_id,
                                   stager_build_id=build_id)
    require(rb_paths["c2d.bin"].read_bytes()[:SIGNATURE_BYTES]
            == bytes.fromhex("43324400")
            and rb_paths["shelf.bin"].read_bytes()[:SIGNATURE_BYTES]
            == bytes.fromhex("4c363553"),
            "delivered probe source signatures drift")
    return {"control_roles": control, "diagnostic_roles": readback,
            "shared_roles": 12, "replaced_payload_roles": ["lisp65.prg"],
            "regenerated_contract_roles": ["autoboot.c65", "boot.id"],
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}",
            "stager_gate": stager_gate, "readback": "byteidentical"}


def primary_semantics() -> dict[str, Any]:
    guide = USER_GUIDE.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    contract = load(MAP_CONTRACT)
    require("Using the MAP instruction to access >1MB" in guide
            and "LDX #$0f" in guide
            and "reg_mb_low <= reg_a" in core
            and "temp_address(27 downto 20) := reg_mb_low" in core
            and contract["map_semantics"]["formula"].startswith("offset20"),
            "primary MAP/megabyte semantics absent")
    return {"user_guide": bind(USER_GUIDE), "core": bind(CORE),
            "existing_decode_contract": bind(MAP_CONTRACT),
            "lower_MB_rule": "X=$0F makes A the low-half megabyte byte",
            "lower_map_rule": "X[7:4] selects 8-KB blocks; X[3:0]:A is offset20>>8",
            "resolved_bank5": "MB=$00, offset=$4C000, CPU block 2: $4000->$00050000",
            "resolved_attic": "MB=$81, offset=$FC000, CPU block 2: $4000->$08100000"}


def build_all() -> dict[str, Any]:
    RING.check()
    cpu = load(CPU_RECEIPT); ring = load(RING_RECEIPT)
    require(cpu["library_load_sources"]["reads_in_proven_CPU_domain"] == 0
            and ring["accounting"]["contact_authorized"] is False,
            "pre-contact CPU/ring authority drift")
    media_paths = SISTER.role_paths(ring["media"]["diagnostic_roles"])
    bank5 = media_paths["c2d.bin"].read_bytes()
    attic = media_paths["shelf.bin"].read_bytes()
    bank5_signature = bank5[:SIGNATURE_BYTES]
    attic_signature = attic[:SIGNATURE_BYTES]
    require(bank5_signature == bytes.fromhex("43324400")
            and attic_signature == bytes.fromhex("4c363553"),
            "delivery-bound source signature drift")
    probe, layout = build_probe(bank5_signature, attic_signature)
    execution = execute_probe(probe, bank5, attic)
    executable_mutations = mutate_executable(probe, bank5, attic, layout)

    base_prg = bytearray(RING.DIAG_PRG.read_bytes())
    require(base_prg[:2] == bytes((PRG_LOAD & 0xFF, PRG_LOAD >> 8)),
            "ring PRG load address drift")
    hook_at = prg_offset(HOOK)
    require(base_prg[hook_at:hook_at + 3] == bytes((0x20, 0x23, 0xA4)),
            "displaced main call drift")
    gap_at = prg_offset(PROBE)
    require(base_prg[gap_at:gap_at + (PROBE_LIMIT - PROBE)]
            == bytes(PROBE_LIMIT - PROBE),
            "ordinary-text diagnostic headroom is not zero/free")
    base_prg[hook_at:hook_at + 3] = bytes((0x20, PROBE & 0xFF, PROBE >> 8))
    base_prg[gap_at:gap_at + len(probe)] = probe
    require(base_prg[prg_offset(STATUS_BANK5)] == STATUS_RESET
            and base_prg[prg_offset(STATUS_ATTIC)] == STATUS_RESET,
            "ring reset does not arm MAP result sentinels")
    ART.mkdir(parents=True, exist_ok=True)
    PROBE_PRG.write_bytes(base_prg)

    base_truth = ElfTruth.read(RING.DIAG_ELF, llvm_readobj=READOBJ,
                               include_section_data=True)
    text = bytearray(base_truth.section_bytes(".text"))
    text_base = base_truth.section(".text").address
    require(text[HOOK - text_base:HOOK - text_base + 3]
            == bytes((0x20, 0x23, 0xA4)), "ring ELF main call drift")
    text[HOOK - text_base:HOOK - text_base + 3] = bytes((0x20, PROBE & 0xFF,
                                                         PROBE >> 8))
    patch_elf(base_truth, bytes(text), probe)
    medium = build_medium()

    deployment = {
        "status": "HOST-GREEN; BUNDLED-CONTACT-AUTHORIZED",
        "product_D81": bind(PROBE_D81),
        "library_D81": bind(RING.LIBRARY_D81),
        "diagnostic_PRG": bind(PROBE_PRG), "diagnostic_ELF": bind(PROBE_ELF),
        "probe_status": {"bank5": "0xB5C2", "attic": "0xB5C3",
                         "reset": "0xD7", "mismatch": "0xE1", "pass": "0xA5"},
        "contact": {"authorized": True, "owner_keyboard": False,
                    "quiet_seconds": 180, "external_active_observations": 0,
                    "final_stop_transitions": 1,
                    "raw_first_ranges": ["0x0000B582:66", "0x0000FF83:2"]},
    }
    write_json(DEPLOY, deployment)
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; MAP-BANK5-ATTIC-PROBE-ARMED; BUNDLED-CONTACT-AUTHORIZED",
        "authority": git_authority(),
        "inputs": {"CPU_reconciliation": bind(CPU_RECEIPT),
                   "progress_ring": bind(RING_RECEIPT),
                   "ring_PRG": bind(RING.DIAG_PRG),
                   "ring_ELF": bind(RING.DIAG_ELF),
                   "ring_D81": bind(RING.DIAG_D81)},
        "primary_MAP_semantics": primary_semantics(),
        "identity": {"promotable": False, "product_links": 0,
                     "WPLTO_runs": 0, "product_candidate_bytes_changed": 0,
                     "enumerated_successor_delta": ["CRT main-call hook",
                                                    "0xB324..0xB3AF probe carrier",
                                                    "lisp65.prg", "boot.id",
                                                    "autoboot.c65"]},
        "probe": {"entry": "0xB324", "limit": "0xB3B0",
                  "hook": "0x2047 JSR $B324 replaces JSR $A423",
                  "continuation": "JMP $A423 with original JSR return frame intact",
                  "CPU_window": "0x4000..0x5fff (block 2 only)",
                  "signatures": {"bank5": bank5_signature.hex(),
                                 "attic": attic_signature.hex(),
                                 "bytes_each": SIGNATURE_BYTES,
                                 "repetitions": REPEATS,
                                 "CPU_reads_each": REPEATS * SIGNATURE_BYTES},
                  "status": {"bank5": "0xB5C2", "attic": "0xB5C3",
                             "reset": "0xD7", "running_or_mismatch": "0xE1",
                             "pass_commit": "0xA5"},
                  "layout": layout, "execution": execution,
                  "restoration": "low map disabled; low MB=$00; high block7 retained; Z=$00"},
        "progress_ring": {"unchanged": True, "slots": "0xB58E..0xB5C1",
                          "probe_status_is_disjoint": True,
                          "sample_every_frames": 2048, "slots_count": 4},
        "media": {**medium, "diagnostic_D81": bind(PROBE_D81),
                  "library_D81": bind(RING.LIBRARY_D81)},
        "deployment": bind(DEPLOY), "session": bind(SESSION), "runner": bind(RUNNER),
        "contact": {"authorized": True, "class": "B", "owner_keyboard": False,
                    "active_observations": 0, "quiet_seconds": 180,
                    "final_stop_transitions": 1, "D1_D5_open": False},
        "decision_table": {
            "A5_A5": "MAP CPU reads are target-green for both Bank 5 and Attic",
            "E1_A5": "Bank-5 MAP CPU read refuted; Attic target-green",
            "A5_E1": "Bank-5 target-green; Attic MAP CPU read refuted",
            "E1_E1": "MAP CPU successor refuted for both tested domains",
            "other": "instrument/setup red; no transport claim"},
        "mutations": {"executable": {"count": 8,
                                      "rejected": executable_mutations},
                      "receipt": None, "total": 0},
        "claim_limit": "Non-promotable target characterization plus the already commissioned progress ring. A passing four-byte span repeated 64 times proves this MAP transport form on the tested Bank-5 and Attic source bases; it does not yet replace product DMA readers or open D1-D5.",
    }
    receipt["mutations"]["receipt"] = mutation_gate(receipt)
    receipt["mutations"]["total"] = 8 + receipt["mutations"]["receipt"]["count"]
    write_json(RECEIPT, receipt)
    return receipt


def audit(value: dict[str, Any]) -> None:
    require(value["status"].endswith("BUNDLED-CONTACT-AUTHORIZED"),
            "MAP CPU probe status drift")
    probe = value["probe"]
    require(probe["entry"] == "0xB324" and probe["limit"] == "0xB3B0"
            and probe["CPU_window"].startswith("0x4000")
            and probe["signatures"] == {
                "bank5": "43324400", "attic": "4c363553",
                "bytes_each": 4, "repetitions": 64, "CPU_reads_each": 256}
            and probe["status"] == {
                "bank5": "0xB5C2", "attic": "0xB5C3", "reset": "0xD7",
                "running_or_mismatch": "0xE1", "pass_commit": "0xA5"}
            and probe["execution"]["mapped_reads"] == {
                "bank5": 256, "attic": 256, "other": 0}
            and probe["execution"]["map_calls"] == probe["execution"]["EOMs"] == 8
            and probe["execution"]["final_map_low"] == 0
            and probe["execution"]["final_map_high"] == 8
            and probe["execution"]["final_MB_low"] == 0
            and probe["execution"]["final_Z"] == 0,
            "MAP CPU probe execution/restoration drift")
    require(value["progress_ring"] == {
        "unchanged": True, "slots": "0xB58E..0xB5C1",
        "probe_status_is_disjoint": True, "sample_every_frames": 2048,
        "slots_count": 4}, "bundled progress-ring contract drift")
    require(value["media"]["shared_roles"] == 12
            and value["media"]["readback"] == "byteidentical",
            "bundled media closure drift")
    require(value["contact"] == {
        "authorized": True, "class": "B", "owner_keyboard": False,
        "active_observations": 0, "quiet_seconds": 180,
        "final_stop_transitions": 1, "D1_D5_open": False},
        "contact choreography drift")


def mutation_gate(base: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "move-probe-carrier": (["probe", "entry"], "0xC000"),
        "widen-CPU-window": (["probe", "CPU_window"], "0x2000..0x7fff"),
        "weaken-bank5-signature": (["probe", "signatures", "bank5"], "43"),
        "weaken-attic-signature": (["probe", "signatures", "attic"], "4c"),
        "reduce-repetitions": (["probe", "signatures", "repetitions"], 1),
        "drop-bank5-read": (["probe", "execution", "mapped_reads", "bank5"], 255),
        "drop-attic-read": (["probe", "execution", "mapped_reads", "attic"], 255),
        "leave-low-map": (["probe", "execution", "final_map_low"], 4),
        "leave-attic-MB": (["probe", "execution", "final_MB_low"], 0x81),
        "leave-Z": (["probe", "execution", "final_Z"], 0x80),
        "overlap-ring": (["progress_ring", "probe_status_is_disjoint"], False),
        "skip-media-readback": (["media", "readback"], "unchecked"),
        "observe-active-phase": (["contact", "active_observations"], 1),
        "add-stop": (["contact", "final_stop_transitions"], 2),
        "open-D1-D5": (["contact", "D1_D5_open"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ProbeError as error:
            rejected[name] = str(error)
        else:
            raise ProbeError(f"MAP CPU receipt mutation survived: {name}")
    require(len(rejected) == 15, "MAP CPU receipt mutation count drift")
    return {"count": len(rejected), "rejected": rejected}


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value["deployment"] == bind(DEPLOY)
            and value["session"] == bind(SESSION)
            and value["runner"] == bind(RUNNER)
            and value["media"]["diagnostic_D81"] == bind(PROBE_D81)
            and value["media"]["library_D81"] == bind(RING.LIBRARY_D81),
            "MAP CPU persisted artifact drift")
    probe = PROBE_CODE.read_bytes()
    roles = SISTER.role_paths(value["media"]["diagnostic_roles"])
    executable = mutate_executable(
        probe, roles["c2d.bin"].read_bytes(), roles["shelf.bin"].read_bytes(),
        value["probe"]["layout"])
    require(value["mutations"]["executable"] == {"count": 8,
                                                   "rejected": executable}
            and mutation_gate({key: deepcopy(item) for key, item in value.items()
                               if key != "mutations"})
                == value["mutations"]["receipt"]
            and value["mutations"]["total"] == 23,
            "MAP CPU persisted mutation drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = build_all() if args.action == "build" else check()
        print("C2 V2.0 MAP CPU TRANSPORT PROBE PASS "
              f"action={args.action} reads=256+256 mutations="
              f"{value['mutations']['total']} contact=authorized")
        return 0
    except (OSError, KeyError, ValueError, ProbeError,
            subprocess.CalledProcessError) as error:
        print(f"C2 V2.0 MAP CPU TRANSPORT PROBE FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
