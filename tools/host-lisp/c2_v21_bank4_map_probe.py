#!/usr/bin/env python3
"""Build and bind the owner-authorized exact Bank-4 MAP probe.

This is a non-promotable pre-main sibling of the qualified Link-113 product.
The cold stager still delivers the complete product to physical Bank 4.  The
diagnostic replaces only the beginning of ``main`` after the product has been
copied to Bank 0.  It maps the delivery-known bytes at physical ``$00046A00``
to CPU ``$4A00``, performs 64 four-byte CPU reads, restores MAP state and
commits one result byte before entering an inert loop.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_defstruct_terminal_ingress_sister as SISTER  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v150_stager_liveness_successor as LIVE  # noqa: E402
import c2_v16_corrected_view_contact as VIEW  # noqa: E402
import c2_v21_facade_padding_linker_producer_rebind_20260817 as PAD  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
DESK = ARCH / "c2.3-v2.1-bank4-map-attribution-receipt.json"
BASE = ROOT / "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final"
BASE_PRG = BASE / "lisp65-c2-substitution-linked.prg"
BASE_ELF = BASE / "lisp65-c2-substitution-linked.prg.elf"
DONOR = ROOT / "build/c2.3/v2.1-configurator-parity-media/shared-system/lisp65-product.d81"
DONOR_MANIFEST = ROOT / (
    "build/c2.3/v2.1-configurator-parity-media/shared-system/"
    "candidate-manifest.json")
OUT = ROOT / "build/c2.3/v2.1-bank4-map-probe"
ART = OUT / "artifacts"
PROBE_PRG = ART / "b4sig.prg"
PROBE_ELF = ART / "b4sig.elf"
PROBE_CODE = ART / "b4sig.bin"
PROBE_D81 = OUT / "b4map.d81"
DESCRIPTOR = OUT / "boot.id"
STAGER = OUT / "autoboot.c65"
STAGER_MAP = OUT / "autoboot.c65.map"
STAGER_BUILD = OUT / "stager-build"
DEPLOY = OUT / "deployment.json"
SESSION = ROOT / "config/c2-v21-bank4-map-probe-session.json"
RUNNER = ROOT / "scripts/c2-v21-bank4-map-probe-hw.sh"
RECEIPT = ARCH / "c2.3-v2.1-bank4-map-probe-receipt.json"
DEVICE_RECEIPT = ARCH / "c2.3-v2.1-bank4-map-probe-device-receipt.json"
CONTACT = OUT / "contact"
CAPTURE = CONTACT / "raw-capture.json"
RESULT = CONTACT / "result.json"

AUTHORIZATION = "7c1c5657"
FORMAT = "lisp65-c2.3-v2.1-bank4-map-probe-v1"
RECORDED_ON = "2026-08-17"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

PRG_LOAD = 0x2001
ENTRY = 0xA4C6
SOURCE_PHYSICAL = 0x00046A00
CPU_POINTER = 0x4A00
MAP_A = 0x20
MAP_X = 0x44
EXPECTED = bytes.fromhex("188505a4")
REPEATS = 64
STATUS_RESET = 0xD7
STATUS_FAIL = 0xE1
STATUS_PASS = 0xA5


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


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")
    return result.stdout


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(["git", "rev-parse", f"{commit}^{{commit}}"],
                          cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          check=True).stdout.strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         stdout=subprocess.PIPE, check=True).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def authority() -> dict[str, Any]:
    row = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(["git", "show", f"{row['commit']}:{row['path']}"],
                         cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("bank-4 probe authorized", "18 85 05 a4",
                  "64 repetitions", "$a5", "$e1", "fresh media"):
        require(token in text, f"Bank-4 probe authority token absent: {token}")
    return row


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

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label: {name}")
        self.labels[name] = self.pc

    def absolute(self, opcode: int, address: int) -> None:
        self.emit(opcode, address, address >> 8)

    def absolute_label(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0, 0)
        self.absolutes.append((len(self.raw) - 2, label))

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


def probe_bytes() -> tuple[bytes, dict[str, int]]:
    a = Asm(ENTRY)

    def map_call(map_a: int, map_x: int) -> None:
        a.emit(0xA9, map_a, 0xA2, map_x)
        a.absolute_label(0x20, "map_helper")

    # The status remains RESET until the map has been restored.  ``outcome``
    # is private scratch; ``status`` is the sole commit-last decision byte.
    a.emit(0xA9, STATUS_RESET)
    a.absolute_label(0x8D, "status")
    for index in range(4):
        a.emit(0xA9, 0x00)
        a.absolute_label(0x8D, f"raw{index}")

    map_call(0x00, 0x00)       # no inherited low mapping
    map_call(0x00, 0x0F)       # low megabyte = $00
    map_call(MAP_A, MAP_X)      # block 2: $4A00 -> physical $00046A00

    a.emit(0xA0, REPEATS)
    a.label("outer")
    a.emit(0xA2, 0x00)
    a.label("inner")
    a.absolute(0xBD, CPU_POINTER)          # LDA $4A00,X
    a.absolute_label(0x9D, "raw0")        # STA raw0,X (raw-first)
    a.absolute_label(0xDD, "expected")    # CMP expected,X
    a.branch(0xD0, "mismatch")
    a.emit(0xE8, 0xE0, len(EXPECTED))
    a.branch(0xD0, "inner")
    a.emit(0x88)
    a.branch(0xD0, "outer")
    a.emit(0xA9, STATUS_PASS)
    a.branch(0x80, "save_outcome")
    a.label("mismatch")
    a.emit(0xA9, STATUS_FAIL)
    a.label("save_outcome")
    a.absolute_label(0x8D, "outcome")

    map_call(0x00, 0x00)       # low map disabled
    map_call(0x00, 0x0F)       # low megabyte restored
    a.absolute_label(0xAD, "outcome")
    a.absolute_label(0x8D, "status")      # commit-last
    a.label("hold")
    a.branch(0x80, "hold")

    a.label("map_helper")
    a.emit(0xA0, 0x00,         # high offset = $000
           0xA3, 0x80,         # retain identity map for high block 7
           0x5C, 0xEA,         # MAP; EOM
           0xA3, 0x00, 0x60)   # llvm-mos Z=0; RTS
    a.label("expected")
    a.raw.extend(EXPECTED)
    for index in range(4):
        a.label(f"raw{index}")
        a.emit(0x00)
    a.label("outcome"); a.emit(STATUS_RESET)
    a.label("status"); a.emit(STATUS_RESET)
    raw = a.finish()
    require(len(raw) <= 0x100, f"Bank-4 probe prefix too large: {len(raw)}")
    return raw, a.labels


def resolve(address: int, map_low: int, offset_low: int, mb_low: int) -> int:
    block = (address >> 13) & 3
    if address < 0x8000 and map_low & (1 << block):
        high = (offset_low + (address >> 8)) & 0xFFF
        return (mb_low << 20) | (high << 8) | (address & 0xFF)
    return address


def execute_probe(image: bytes, labels: dict[str, int], source: bytes) -> dict[str, Any]:
    memory = bytearray(65536)
    memory[ENTRY:ENTRY + len(image)] = image
    physical = {SOURCE_PHYSICAL + i: byte for i, byte in enumerate(source)}
    pc = ENTRY
    a = x = y = z = 0
    zero = False
    calls: list[int] = []
    map_low = offset_low = mb_low = 0
    map_high = 8
    reads = 0
    tuples: list[list[int]] = []
    eoms = 0

    def read(address: int) -> int:
        nonlocal reads
        target = resolve(address, map_low, offset_low, mb_low)
        if SOURCE_PHYSICAL <= target < SOURCE_PHYSICAL + len(source):
            reads += 1
        return physical.get(target, memory[target] if target < 65536 else 0xFF)

    for _ in range(20000):
        if pc == labels["hold"] and memory[labels["status"]] in (
                STATUS_PASS, STATUS_FAIL):
            break
        op = memory[pc]; pc += 1
        if op in (0xA9, 0xA2, 0xA0, 0xA3, 0xE0):
            value = memory[pc]; pc += 1
            if op == 0xA9: a = value; zero = a == 0
            elif op == 0xA2: x = value; zero = x == 0
            elif op == 0xA0: y = value; zero = y == 0
            elif op == 0xA3: z = value; zero = z == 0
            else: zero = x == value
        elif op in (0x8D, 0x9D, 0xAD, 0xBD, 0xDD, 0x20):
            address = memory[pc] | memory[pc + 1] << 8; pc += 2
            if op == 0x8D: memory[address] = a
            elif op == 0x9D: memory[(address + x) & 0xFFFF] = a
            elif op == 0xAD: a = memory[address]; zero = a == 0
            elif op == 0xBD: a = read((address + x) & 0xFFFF); zero = a == 0
            elif op == 0xDD: zero = a == memory[(address + x) & 0xFFFF]
            else: calls.append(pc); pc = address
        elif op in (0xD0, 0x80):
            delta = memory[pc]; pc += 1
            if op == 0x80 or not zero:
                pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif op == 0xE8: x = (x + 1) & 0xFF; zero = x == 0
        elif op == 0x88: y = (y - 1) & 0xFF; zero = y == 0
        elif op == 0x5C:
            tuples.append([a, x, y, z])
            if x == 0x0F: mb_low = a
            else: offset_low = ((x & 0x0F) << 8) | a; map_low = x >> 4
            if z != 0x0F: map_high = z >> 4
        elif op == 0xEA: eoms += 1
        elif op == 0x60:
            require(calls, "probe model RTS without JSR")
            pc = calls.pop()
        else:
            raise ProbeError(f"unmodeled opcode ${op:02x} at ${pc - 1:04x}")
    else:
        raise ProbeError("probe model did not reach committed hold")

    status = memory[labels["status"]]
    require(status == STATUS_PASS, f"probe model status ${status:02x}")
    require(reads == REPEATS * len(EXPECTED), f"raw read coverage drift: {reads}")
    require(bytes(memory[labels["raw0"]:labels["raw0"] + 4]) == EXPECTED,
            "raw-first terminal sample drift")
    require(map_low == 0 and map_high == 8 and mb_low == 0 and z == 0,
            "probe did not restore MAPL/MB/Z")
    require(len(tuples) == eoms == 5, "MAP/EOM pairing drift")
    require(tuples[2] == [MAP_A, MAP_X, 0, 0x80], "exact Bank-4 tuple drift")
    return {"status": f"0x{status:02x}", "raw_reads": reads,
            "terminal_raw": EXPECTED.hex(), "map_calls": len(tuples),
            "EOMs": eoms, "final_MAPL": "0x0000",
            "final_MAPH": "0x8000", "final_low_MB": "0x00", "final_Z": 0,
            "tuples": [[f"0x{v:02x}" for v in row] for row in tuples]}


def executable_mutations(image: bytes, labels: dict[str, int]) -> dict[str, str]:
    cases: dict[str, bytearray] = {}
    def offset(label: str) -> int: return labels[label] - ENTRY

    wrong_a = bytearray(image)
    at = wrong_a.index(bytes((0xA9, MAP_A, 0xA2, MAP_X)))
    wrong_a[at + 1] = 0x10; cases["wrong-map-offset"] = wrong_a
    wrong_x = bytearray(image); wrong_x[at + 3] = 0x24
    cases["wrong-map-block"] = wrong_x
    wrong_pointer = bytearray(image)
    atp = wrong_pointer.index(bytes((0xBD, CPU_POINTER & 0xFF,
                                     CPU_POINTER >> 8)))
    wrong_pointer[atp + 2] = 0x49; cases["wrong-cpu-pointer"] = wrong_pointer
    short = bytearray(image)
    atr = short.index(bytes((0xA0, REPEATS))); short[atr + 1] = REPEATS - 1
    cases["short-read-count"] = short
    wrong_oracle = bytearray(image); wrong_oracle[offset("expected")] ^= 0x80
    cases["oracle-not-delivery-bound"] = wrong_oracle
    live_map = bytearray(image)
    restore = bytes((0xA9, 0x00, 0xA2, 0x00)); atm = live_map.rindex(restore)
    live_map[atm + 3] = 0x40; cases["leave-low-map-live"] = live_map
    live_z = bytearray(image)
    atz = live_z.index(bytes((0xA3, 0x00, 0x60)), offset("map_helper"))
    live_z[atz + 1] = 0x80; cases["leave-z-nonzero"] = live_z

    rejected: dict[str, str] = {}
    for name, candidate in cases.items():
        try:
            execute_probe(bytes(candidate), labels, EXPECTED)
        except ProbeError as error:
            rejected[name] = str(error)
        else:
            raise ProbeError(f"Bank-4 executable mutation survived: {name}")
    require(len(rejected) == 7, "Bank-4 executable mutation count drift")
    return rejected


def patch_product(image: bytes, labels: dict[str, int]) -> dict[str, Any]:
    ART.mkdir(parents=True, exist_ok=True)
    truth = ElfTruth.read(BASE_ELF, llvm_readobj=READOBJ, include_section_data=True)
    main = truth.symbol("main")
    require(main.value == ENTRY and main.bytes >= len(image), "main carrier drift")
    text = bytearray(truth.section_bytes(".text"))
    text_base = truth.section(".text").address
    at = ENTRY - text_base
    before = bytes(text[at:at + len(image)])
    text[at:at + len(image)] = image
    text_path = ART / "text.bin"; text_path.write_bytes(text)
    PROBE_CODE.write_bytes(image)
    command = [str(OBJCOPY), f"--update-section=.text={text_path}"]
    for name in ("hold", "raw0", "status"):
        flags = "global,object" if name != "hold" else "global,function"
        command.append(
            f"--add-symbol=lisp65_v21_bank4_probe_{name}=0x{labels[name]:x},{flags}")
    command += [str(BASE_ELF), str(PROBE_ELF)]
    run(command, "derive Bank-4 probe ELF")
    derived = ElfTruth.read(PROBE_ELF, llvm_readobj=READOBJ,
                            include_section_data=True)
    require(derived.section_bytes(".text")[at:at + len(image)] == image,
            "diagnostic ELF probe bytes drift")

    prg = bytearray(BASE_PRG.read_bytes())
    require(int.from_bytes(prg[:2], "little") == PRG_LOAD,
            "candidate PRG load address drift")
    po = prg_offset(ENTRY)
    require(bytes(prg[po:po + len(image)]) == before,
            "ELF/PRG main carrier identity drift")
    prg[po:po + len(image)] = image
    PROBE_PRG.write_bytes(prg)
    require(PROBE_PRG.read_bytes()[0x6A00:0x6A04] == EXPECTED,
            "stager-delivered Bank-4 source truth drift")
    return {"carrier": "main-prefix", "entry": f"0x{ENTRY:04x}",
            "bytes": len(image), "main_bytes": main.bytes,
            "before_sha256": digest(before), "after_sha256": digest(image),
            "source_file_offset": "0x6a00",
            "source_physical": f"0x{SOURCE_PHYSICAL:08x}"}


def packed_medium_gate(path: Path, control: dict[str, dict[str, Any]]) -> dict[str, Any]:
    roles = SISTER.medium_roles(path, OUT / "readback-packed-gate")
    paths = SISTER.role_paths(roles)
    rows, build_id, profile_id = SISTER.descriptor_rows(
        paths["boot.id"].read_bytes(), paths)
    SISTER.target_descriptor_check(paths["boot.id"].read_bytes(), rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    require(paths["lisp65.prg"].read_bytes() == PROBE_PRG.read_bytes()
            and paths["autoboot.c65"].read_bytes() == STAGER.read_bytes()
            and paths["boot.id"].read_bytes() == DESCRIPTOR.read_bytes(),
            "packed diagnostic contract role drift")
    changed = {"lisp65.prg", "autoboot.c65", "boot.id"}
    require(all(roles[name]["sha256"] == control[name]["sha256"]
                for name in roles if name not in changed),
            "unrelated donor role changed")
    require(paths["lisp65.prg"].read_bytes()[0x6A00:0x6A04] == EXPECTED,
            "packed Bank-4 signature differs from delivery truth")
    return {"result": "passed-15-role-readback-and-current-descriptor",
            "roles": len(roles), "descriptor_rows": len(rows),
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}",
            "unchanged_roles": len(roles) - len(changed),
            "source_signature": EXPECTED.hex()}


def build_medium() -> dict[str, Any]:
    control = SISTER.medium_roles(DONOR, OUT / "readback-donor")
    paths = SISTER.role_paths(control)
    donor = paths["boot.id"].read_bytes()
    donor_rows, donor_id, profile_id = SISTER.descriptor_rows(donor, paths)
    SISTER.target_descriptor_check(donor, donor_rows,
                                   descriptor_build_id=donor_id,
                                   stager_build_id=donor_id)
    payloads = dict(paths); payloads["lisp65.prg"] = PROBE_PRG
    rows, inherited, inherited_profile = SISTER.descriptor_rows(donor, payloads)
    require(inherited == donor_id and inherited_profile == profile_id,
            "donor descriptor identity drift")
    descriptor, build_id = MEDIA.make_descriptor(rows, profile_id)
    DESCRIPTOR.write_bytes(descriptor)
    SISTER.target_descriptor_check(descriptor, rows,
                                   descriptor_build_id=build_id,
                                   stager_build_id=build_id)
    stager_gate = MEDIA.compile_stager(
        build_id, rows, build_dir=STAGER_BUILD, stager=STAGER,
        stager_map=STAGER_MAP, compile_defines=(LIVE.OPT_IN,))
    shutil.copyfile(DONOR, PROBE_D81)
    run(["c1541", "-attach", str(PROBE_D81),
         "-delete", "lisp65.prg", "-write", str(PROBE_PRG), "lisp65.prg",
         "-delete", "boot.id", "-write", str(DESCRIPTOR), "boot.id",
         "-delete", "autoboot.c65", "-write", str(STAGER), "autoboot.c65"],
        "replace Bank-4 diagnostic D81 roles")
    gates: dict[str, Callable[[Path], dict[str, Any]]] = {
        "autoboot.c65.elf": LIVE.delivered_liveness_gate,
        "b4map.d81": lambda path: packed_medium_gate(path, control),
    }
    closure = MEDIA.close_packed_artifacts(
        {"autoboot.c65.elf": Path(str(STAGER) + ".elf"),
         "b4map.d81": PROBE_D81}, gates)
    require(closure["complete"] is True
            and closure["registered"] == closure["executed"] ==
                ["autoboot.c65.elf", "b4map.d81"],
            "Bank-4 packed artifact closure incomplete")
    return {"donor": bind(DONOR), "donor_roles": len(control),
            "build_id": f"0x{build_id:08x}",
            "profile_id": f"0x{profile_id:08x}",
            "changed_payload_roles": ["lisp65.prg"],
            "regenerated_contract_roles": ["autoboot.c65", "boot.id"],
            "stager_gate": stager_gate, "packed_artifact_closure": closure,
            "product_D81": bind(PROBE_D81)}


def audit(value: dict[str, Any]) -> None:
    probe = value["probe"]
    contact = value["contact"]
    require(value.get("format") == FORMAT
            and value.get("status") ==
                "HOST-GREEN; BANK4-MAP-PROBE-CONTACT-AUTHORIZED"
            and probe["source"] == {"physical": "0x00046a00",
                                     "bytes": "188505a4"}
            and probe["tuple"] == {"A": "0x20", "X": "0x44",
                                     "MAPL": "0x4420",
                                     "CPU_pointer": "0x4a00"}
            and probe["repetitions"] == 64 and probe["raw_reads"] == 256
            and probe["execution"]["status"] == "0xa5"
            and probe["execution"]["final_MAPL"] == "0x0000"
            and probe["execution"]["final_MAPH"] == "0x8000"
            and probe["execution"]["final_Z"] == 0,
            "Bank-4 probe contract drift")
    closure = value["media"]["packed_artifact_closure"]
    require(closure["complete"] is True
            and closure["registered"] == closure["executed"] ==
                ["autoboot.c65.elf", "b4map.d81"],
            "Bank-4 packed closure drift")
    require(contact == {"authorized": True, "fresh_medium": True,
                        "owner_keyboard": False,
                        "automated_access_after_mount_before_stop": 0,
                        "stop_transitions": 1, "resumes": 0,
                        "D3_D5_open": False},
            "Bank-4 contact discipline drift")


def receipt_mutations(value: dict[str, Any]) -> dict[str, str]:
    cases = {
        "change-source-truth": (["probe", "source", "bytes"], "18850500"),
        "reduce-repetitions": (["probe", "repetitions"], 63),
        "reduce-raw-reads": (["probe", "raw_reads"], 255),
        "omit-packed-gate":
            (["media", "packed_artifact_closure", "complete"], False),
        "observe-after-mount":
            (["contact", "automated_access_after_mount_before_stop"], 1),
        "open-D3-D5": (["contact", "D3_D5_open"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(value); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except ProbeError as error: rejected[name] = str(error)
        else: raise ProbeError(f"Bank-4 receipt mutation survived: {name}")
    require(len(rejected) == 6, "Bank-4 receipt mutation count drift")
    return rejected


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Bank-4 probe build is one-shot")
    authority_row = authority()
    desk = load(DESK)
    require(desk["status"] ==
            "DESK-DECODE-CORRECT; BANK4-TARGET-PROBE-REQUIRED"
            and desk["closing_probe"]["authorization_state"] ==
                "SPECIFIED-NOT-AUTHORIZED-NOT-RUN"
            and desk["closing_probe"]["exact_row"]["expected"] ==
                EXPECTED.hex(),
            "Bank-4 desk boundary drift")
    PAD.check()
    OUT.mkdir(parents=True)
    image, labels = probe_bytes()
    execution = execute_probe(image, labels, EXPECTED)
    mutations = executable_mutations(image, labels)
    carrier = patch_product(image, labels)
    media = build_medium()
    deployment = {"format": FORMAT + "-deployment",
        "status": "READY", "product_medium": bind(PROBE_D81),
        "remote_name": "b4map.d81", "quiet_seconds": 75,
        "status_address": f"0x{labels['status']:08x}",
        "record_address": f"0x{labels['raw0']:08x}",
        "hold_address": f"0x{labels['hold']:04x}",
        "source_address": f"0x{SOURCE_PHYSICAL:08x}"}
    write_json(DEPLOY, deployment)
    value = {"format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; BANK4-MAP-PROBE-CONTACT-AUTHORIZED",
        "authority": {"owner": authority_row, "desk": bind(DESK),
                      "facade_padding_rebind": bind(PAD.RECEIPT)},
        "inputs": {"base_PRG": bind(BASE_PRG), "base_ELF": bind(BASE_ELF),
                   "donor_D81": bind(DONOR),
                   "donor_manifest": bind(DONOR_MANIFEST)},
        "identity": {"promotable": False, "product_links": 0,
                     "WPLTO_runs": 0, "product_candidate_bytes_changed": 0,
                     "diagnostic_delta": carrier},
        "probe": {"source": {"physical": "0x00046a00",
                                "bytes": EXPECTED.hex()},
                  "tuple": {"A": "0x20", "X": "0x44",
                            "MAPL": "0x4420", "CPU_pointer": "0x4a00"},
                  "repetitions": REPEATS,
                  "bytes_per_repetition": len(EXPECTED),
                  "raw_reads": REPEATS * len(EXPECTED),
                  "entry": f"0x{ENTRY:04x}",
                  "labels": {name: f"0x{address:04x}"
                             for name, address in sorted(labels.items())},
                  "status": {"reset": "0xd7", "mismatch": "0xe1",
                             "pass": "0xa5", "commit_last": True},
                  "execution": execution},
        "media": media, "deployment": bind(DEPLOY),
        "session": bind(SESSION), "runner": bind(RUNNER),
        "contact": {"authorized": True, "fresh_medium": True,
                    "owner_keyboard": False,
                    "automated_access_after_mount_before_stop": 0,
                    "stop_transitions": 1, "resumes": 0,
                    "D3_D5_open": False},
        "decision_table": {"0xa5":
            "intrinsic Bank-4 MAP property refuted; reader/caller path convicted",
            "0xe1": "exact Bank-4 MAP form refuted on target",
            "other": "setup red; no mechanism claim"},
        "mutations": {"executable": {"count": len(mutations),
                                       "rejected": mutations}},
        "claim_limit": "One non-promotable Bank-4 hardware characterization row. No product fix, D3-D5 opening, release or resume claim."}
    value["mutations"]["receipt"] = {"count": 6,
                                      "rejected": receipt_mutations(value)}
    value["mutations"]["total"] = 13
    audit(value)
    write_json(RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    require(value["deployment"] == bind(DEPLOY)
            and value["session"] == bind(SESSION)
            and value["runner"] == bind(RUNNER)
            and value["media"]["product_D81"] == bind(PROBE_D81),
            "Bank-4 persisted artifact drift")
    image, labels = probe_bytes()
    require(PROBE_CODE.read_bytes() == image
            and execute_probe(image, labels, EXPECTED) ==
                value["probe"]["execution"]
            and executable_mutations(image, labels) ==
                value["mutations"]["executable"]["rejected"]
            and receipt_mutations({k: deepcopy(v) for k, v in value.items()
                                   if k != "mutations"}) ==
                value["mutations"]["receipt"]["rejected"],
            "Bank-4 persisted execution/mutation drift")
    PAD.check()
    return value


def append_raw(path: Path, label: str, command: str, raw: bytes) -> None:
    row = canonical({"label": label, "command": command, "raw_hex": raw.hex()})
    with path.open("ab") as handle:
        handle.write(row); handle.flush(); os.fsync(handle.fileno())


def monitor_row(fd: int, address: int, raw_log: Path) -> bytes:
    command = f"m{address:08x}"
    raw = VIEW.command(fd, command.encode(), 0.05)
    append_raw(raw_log, f"physical-0x{address:08x}", command, raw)
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None, f"physical row absent at ${address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())


def capture() -> dict[str, Any]:
    prepared = check(); deployment = load(DEPLOY)
    device = os.environ.get("DEVICE", "/dev/ttyUSB1")
    require(Path(device).is_char_device(), f"serial device absent: {device}")
    require(not CAPTURE.exists() and not RESULT.exists(),
            "Bank-4 contact already captured")
    CONTACT.mkdir(parents=True, exist_ok=True)
    raw_log = CONTACT / "monitor-raw.ndjson"; raw_log.write_bytes(b"")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        stopped = VIEW.command(fd, b"t1", 0.08)
        append_raw(raw_log, "sole-final-stop", "t1", stopped)
        reg_raw = VIEW.command(fd, b"r", 0.05)
        append_raw(raw_log, "register-tuple", "r", reg_raw)
        registers = VIEW.parse_registers(reg_raw)
        status_address = int(deployment["status_address"], 0)
        record_address = int(deployment["record_address"], 0)
        record = monitor_row(fd, record_address, raw_log)
        source = monitor_row(fd, SOURCE_PHYSICAL, raw_log)
    finally:
        os.close(fd)
    value = {"format": FORMAT + "-raw", "captured_on": RECORDED_ON,
        "authority": {"probe": bind(RECEIPT), "medium": bind(PROBE_D81)},
        "device": device, "discipline": {
            "fresh_medium": True, "automated_accesses_after_mount_before_stop": 0,
            "stops": 1, "resumes": 0, "tuple_before_data": True,
            "raw_persisted_before_interpretation": True,
            "CPU_left_stopped": True, "D3_D5_executed": False},
        "tuple": registers, "status_address": f"0x{status_address:08x}",
        "record_address": f"0x{record_address:08x}",
        "record_row_hex": record.hex(), "source_row_hex": source.hex(),
        "raw_log": bind(raw_log),
        "claim_limit": "Raw-first stopped-state capture only; record owns classification."}
    write_json(CAPTURE, value)
    return value


def record() -> dict[str, Any]:
    prepared = check(); raw = load(CAPTURE); deployment = load(DEPLOY)
    labels = {name: int(address, 0)
              for name, address in prepared["probe"]["labels"].items()}
    record_address = int(raw["record_address"], 0)
    record_row = bytes.fromhex(raw["record_row_hex"])
    source = bytes.fromhex(raw["source_row_hex"])
    at = labels["raw0"] - record_address
    status_at = labels["status"] - record_address
    require(0 <= at <= 12 and 0 <= status_at < 16,
            "captured record row does not cover probe state")
    terminal = record_row[at:at + 4]
    status = record_row[status_at]
    require(source[:4] == EXPECTED, "physical Bank-4 delivery truth drift")
    meanings = {STATUS_PASS:
        "INTRINSIC-BANK4-PROPERTY-REFUTED; READER-CALLER-PATH-CONVICTED",
        STATUS_FAIL: "EXACT-BANK4-MAP-FORM-TARGET-REFUTED"}
    decision = meanings.get(status, "SETUP-RED; NO-MECHANISM-CLAIM")
    if status == STATUS_PASS:
        require(terminal == EXPECTED, "passing status lacks terminal raw match")
    pc = int(raw["tuple"]["PC"], 0)
    hold = int(deployment["hold_address"], 0)
    require(pc in {hold, hold + 2}, f"stopped PC outside committed hold: ${pc:04x}")
    require(raw["tuple"].get("MAPL") == "0x0000"
            and raw["tuple"].get("MAPH") == "0x8000",
            "target MAP state was not restored")
    value = {"format": FORMAT + "-device-v1", "recorded_on": RECORDED_ON,
        "status": decision, "authority": {"owner": authority(),
            "host_probe": bind(RECEIPT), "raw_capture": bind(CAPTURE)},
        "discipline": {"fresh_medium": True,
            "automated_accesses_after_mount_before_stop": 0,
            "stops": 1, "resumes": 0, "CPU_left_stopped": True,
            "D3_D5_open": False},
        "target": {"status": f"0x{status:02x}",
            "terminal_raw": terminal.hex(), "physical_source": source[:4].hex(),
            "repetitions": REPEATS, "raw_reads": REPEATS * len(EXPECTED),
            "tuple": raw["tuple"], "hold_PC": f"0x{pc:04x}"},
        "decision": decision,
        "claim_limit": "The exact authorized Bank-4 MAP row only. CPU remains stopped; no product fix or D3-D5 execution."}
    write_json(RESULT, value); write_json(DEVICE_RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest",
                                           "capture", "record"))
    action = parser.parse_args().action
    if action == "build": value = build()
    elif action in ("check", "selftest"): value = check()
    elif action == "capture": value = capture()
    else: value = record()
    if action in ("build", "check", "selftest"):
        print("Bank-4 MAP probe: PASS "
              f"action={action} reads=256 mutations={value['mutations']['total']} "
              "contact=authorized")
    else:
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, ProbeError,
            subprocess.CalledProcessError) as error:
        print(f"Bank-4 MAP probe: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
