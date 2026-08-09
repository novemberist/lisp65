#!/usr/bin/env python3
"""Build and gate the diagnostic-only v1.6 mem_init before/after witness.

The product and the ROMC-safe diagnostic authority remain immutable.  This
tool derives one non-promotable sibling by routing the Workbench overlay entry
through a pre-init snapshot and the first post-mem_init allocator call through
a post-init snapshot.  Both snapshots are written by target code into the
owner-free Bank-0 interval and are intended for one mapping-aware physical
read after the authorized quiet launch.
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
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


OWNER_COMMIT = "9db66c1d"
PREPARATION_RECORDED_ON = "2026-08-05"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
BASE = ROOT / "build/c2.3/v1.6-defstruct-bootstrap-romc-repair"
BASE_ELF = BASE / "artifacts/diagnostic-link82-romc-safe.elf"
BASE_PRG = BASE / "artifacts/diagnostic-link82-romc-safe.prg"
BASE_DEPLOY = BASE / "deployment.json"
BASE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
CALLER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-gc-address-caller-attribution-receipt.json")
OWNERSHIP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
SOURCE_EVAL = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src/eval.c"
SOURCE_MEM = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src/mem.c"
BASE_BOOT_RAW = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/artifacts/boot-overlay.raw.bin")
BASE_BOOTSTAGE = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/artifacts/bootstage.bin")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
OUT = ROOT / "build/c2.3/v1.6-defstruct-mem-init-before-after"
ART = OUT / "artifacts"
DIAG_ELF = ART / "diagnostic-mem-init-before-after.elf"
DIAG_PRG = ART / "diagnostic-mem-init-before-after.prg"
BOOT_RAW = ART / "boot-overlay-mem-init-before-after.bin"
BOOTSTAGE = ART / "bootstage-mem-init-before-after.bin"
WITNESS_RESET_FILE = ART / "mem-init-witness-reset.bin"
RESET_DOMAIN_FILE = ART / "c2d-v6-reset-domain.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mem-init-before-after-preparation-receipt.json")
DRIVER = Path(__file__).resolve()
CONTACT_DRIVER = ROOT / "tools/host-lisp/c2_v16_mem_init_before_after_contact.py"
RUNNER = ROOT / "scripts/c2-v16-defstruct-mem-init-before-after-hw.sh"

PRG_LOAD = 0x2001
OVERLAY_START = 0xC356
OVERLAY_ENTRY = 0xC85A
EVAL_INIT = 0xC3FD
POST_INIT_CALL = 0xC4C5
INTERN = 0x2DFF
STATE = 0xC03F
PRE_ROUTINE = 0xC048
POST_ROUTINE = 0xC04E
COMMON_ROUTINE = 0xC052
WITNESS = 0xB582
WITNESS_BYTES = 10
BEFORE_TAG = 0xA1
AFTER_TAG = 0xA6
BEFORE_RESET = 0xD1
AFTER_RESET = 0xD2
FREELIST = 0x3D
ALLOC_HIGH = 0x39
SECOND_RECORD = 0x600
RESET_DOMAIN_BYTES = 50816
RESET_PREFIX_BYTES = 33840
C2J_OFFSET = 50752
C2J_BYTES = 64


class WitnessError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WitnessError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    try:
        label = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str], label: str) -> bytes:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    require(result.returncode == 0,
            f"{label} failed:\n{result.stdout.decode(errors='replace')}")
    return result.stdout


def git_blob(commit: str, path: str) -> tuple[bytes, dict[str, Any]]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"],
               "resolve commission").decode().strip()
    raw = run(["git", "show", f"{full}:{path}"], "read commission")
    return raw, {"path": f"git:{full}:{path}", "bytes": len(raw),
                 "sha256": digest(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def crc16(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = (((value << 1) ^ 0x1021) & 0xFFFF
                     if value & 0x8000 else (value << 1) & 0xFFFF)
    return value


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_slice(raw: bytes, address: int, count: int) -> bytes:
    require(int.from_bytes(raw[:2], "little") == PRG_LOAD, "PRG load drift")
    at = 2 + address - PRG_LOAD
    require(2 <= at and at + count <= len(raw), "PRG range absent")
    return raw[at:at + count]


def prg_patch(raw: bytearray, address: int, before: bytes, after: bytes) -> None:
    require(len(before) == len(after), "fixed-size PRG patch required")
    at = 2 + address - PRG_LOAD
    require(raw[at:at + len(before)] == before,
            f"PRG authority drift at ${address:04X}")
    raw[at:at + len(after)] = after


def wrapper() -> bytes:
    # Two entries share one body.  X=0 selects the before record and X=5 the
    # after record.  Raw bytes are written first; the tag is the commit byte.
    pre = b"\xda\x48\xa2\x00\x80\x04"       # PHX; PHA; LDX #0; BRA common
    post = b"\xda\x48\xa2\x05"             # PHX; PHA; LDX #5
    common = bytearray()
    for source, target in (
        (FREELIST, WITNESS + 1), (FREELIST + 1, WITNESS + 2),
        (ALLOC_HIGH, WITNESS + 3), (ALLOC_HIGH + 1, WITNESS + 4),
    ):
        common += bytes((0xA5, source, 0x9D)) + u16(target)
    common += b"\x8a\x18\x69" + bytes((BEFORE_TAG,))
    common += b"\x9d" + u16(WITNESS)
    common += b"\xe0\x00\xf0\x05"
    common += b"\x68\xfa\x4c" + u16(INTERN)
    common += b"\x68\xfa\x4c" + u16(EVAL_INIT)
    payload = pre + post + bytes(common)
    require(len(payload) == 51 and PRE_ROUTINE + len(pre) == POST_ROUTINE
            and POST_ROUTINE + len(post) == COMMON_ROUTINE,
            f"wrapper geometry drift: {len(payload)}")
    return payload


def witness_reset() -> bytes:
    return bytes((BEFORE_RESET, 0xCC, 0xCC, 0xCC, 0xCC,
                  AFTER_RESET, 0xCC, 0xCC, 0xCC, 0xCC))


def patch_section_address(path: Path, section_name: str, address: int) -> None:
    data = bytearray(path.read_bytes())
    require(data[:6] == b"\x7fELF\x01\x01", "ELF32 little-endian required")
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    str_header = shoff + shstrndx * shentsize
    str_offset, str_size = struct.unpack_from("<II", data, str_header + 16)
    strings = data[str_offset:str_offset + str_size]
    found = False
    for index in range(shnum):
        header = shoff + index * shentsize
        name_offset = struct.unpack_from("<I", data, header)[0]
        end = strings.find(0, name_offset)
        name = bytes(strings[name_offset:end]).decode("ascii")
        if name == section_name:
            struct.pack_into("<I", data, header + 12, address)
            found = True
    require(found, f"ELF section absent: {section_name}")
    path.chmod(path.stat().st_mode | 0o200)
    path.write_bytes(data)


def patch_overlay(raw: bytes) -> bytes:
    result = bytearray(raw)
    entry_at = OVERLAY_ENTRY - OVERLAY_START
    post_at = POST_INIT_CALL - OVERLAY_START
    require(result[entry_at:entry_at + 3] == b"\x4c" + u16(EVAL_INIT),
            "overlay entry authority drift")
    require(result[post_at:post_at + 3] == b"\x20" + u16(INTERN),
            "post-mem_init first allocator edge drift")
    result[entry_at:entry_at + 3] = b"\x4c" + u16(PRE_ROUTINE)
    result[post_at:post_at + 3] = b"\x20" + u16(POST_ROUTINE)
    return bytes(result)


def patch_bootstage(raw: bytes, overlay: bytes) -> bytes:
    require(raw[SECOND_RECORD:SECOND_RECORD + 4] == b"L65O",
            "second boot record absent")
    magic, version, header_bytes, build_id, start, entry, size, old_crc = \
        struct.unpack_from("<4sBBIHHHH", raw, SECOND_RECORD)
    require((magic, version, header_bytes, start, entry, size) ==
            (b"L65O", 1, 18, OVERLAY_START, OVERLAY_ENTRY, len(overlay)),
            "second boot descriptor geometry drift")
    old_overlay = raw[SECOND_RECORD + header_bytes:
                      SECOND_RECORD + header_bytes + size]
    require(old_overlay == BASE_BOOT_RAW.read_bytes()
            and crc16(old_overlay) == old_crc,
            "base boot payload/CRC drift")
    descriptor = struct.pack("<4sBBIHHHH", magic, version, header_bytes,
                             build_id, start, entry, size, crc16(overlay))
    result = raw[:SECOND_RECORD] + descriptor + overlay
    require(len(result) == len(raw) and result[:SECOND_RECORD] == raw[:SECOND_RECORD],
            "bootstage fixed-extent/first-record drift")
    return result


def patch_elf(overlay: bytes, routine: bytes, reset: bytes) -> None:
    truth = ElfTruth.read(BASE_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    base_overlay = bytearray(truth.section_bytes(".lisp65_workbench_overlay"))
    require(bytes(base_overlay) == BASE_BOOT_RAW.read_bytes(),
            "ELF/boot-overlay source divergence")
    base_overlay[:] = overlay
    state_name = ".lisp65_v16_defstruct_diagnostic_state"
    state = bytearray(truth.section_bytes(state_name))
    require(truth.section(state_name).address == STATE and len(state) == 65,
            "diagnostic state geometry drift")
    require(state[9:9 + len(routine)] == BASE_PRG.read_bytes()[
        2 + PRE_ROUTINE - PRG_LOAD:2 + PRE_ROUTINE - PRG_LOAD + len(routine)],
        "ELF/PRG state authority drift")
    state[PRE_ROUTINE - STATE:PRE_ROUTINE - STATE + len(routine)] = routine
    section_overlay = ART / "section-workbench-overlay.bin"
    section_state = ART / "section-diagnostic-state.bin"
    section_witness = ART / "section-mem-init-witness.bin"
    section_overlay.write_bytes(bytes(base_overlay))
    section_state.write_bytes(bytes(state))
    section_witness.write_bytes(reset)
    args = [str(OBJCOPY),
            f"--update-section=.lisp65_workbench_overlay={section_overlay}",
            f"--update-section={state_name}={section_state}",
            f"--add-section=.lisp65_v16_mem_init_witness={section_witness}",
            "--set-section-flags=.lisp65_v16_mem_init_witness=alloc,load,data",
            f"--add-symbol=lisp65_v16_mem_init_before_capture=0x{PRE_ROUTINE:x},global,function",
            f"--add-symbol=lisp65_v16_mem_init_after_capture=0x{POST_ROUTINE:x},global,function",
            f"--add-symbol=lisp65_v16_mem_init_witness=0x{WITNESS:x},global,object",
            str(BASE_ELF), str(DIAG_ELF)]
    run(args, "derive mem_init witness ELF")
    patch_section_address(DIAG_ELF, ".lisp65_v16_mem_init_witness", WITNESS)


def simulate(code: bytes, start: int, a: int, x: int,
             freelist: int, alloc_high: int) -> dict[str, Any]:
    memory = {FREELIST: freelist & 0xFF, FREELIST + 1: freelist >> 8,
              ALLOC_HIGH: alloc_high & 0xFF, ALLOC_HIGH + 1: alloc_high >> 8}
    for offset, value in enumerate(witness_reset()):
        memory[WITNESS + offset] = value
    pc, carry = start, False
    stack: list[int] = []
    steps = 0
    while True:
        steps += 1
        require(steps < 48, "wrapper model did not terminate")
        op = code[pc - PRE_ROUTINE]
        if op == 0xDA: stack.append(x); pc += 1
        elif op == 0x48: stack.append(a); pc += 1
        elif op == 0xA2: x = code[pc - PRE_ROUTINE + 1]; pc += 2
        elif op == 0x80:
            delta = code[pc - PRE_ROUTINE + 1]
            pc += 2 + (delta if delta < 0x80 else delta - 0x100)
        elif op == 0xA5: a = memory[code[pc - PRE_ROUTINE + 1]]; pc += 2
        elif op == 0x9D:
            target = int.from_bytes(code[pc - PRE_ROUTINE + 1:
                                         pc - PRE_ROUTINE + 3], "little") + x
            memory[target] = a; pc += 3
        elif op == 0x8A: a = x; pc += 1
        elif op == 0x18: carry = False; pc += 1
        elif op == 0x69:
            total = a + code[pc - PRE_ROUTINE + 1] + int(carry)
            a, carry, pc = total & 0xFF, total > 0xFF, pc + 2
        elif op == 0xE0:
            zero = x == code[pc - PRE_ROUTINE + 1]; pc += 2
        elif op == 0xF0:
            delta = code[pc - PRE_ROUTINE + 1]
            pc += 2 + (delta if zero else 0)
        elif op == 0x68: a = stack.pop(); pc += 1
        elif op == 0xFA: x = stack.pop(); pc += 1
        elif op == 0x4C:
            target = int.from_bytes(code[pc - PRE_ROUTINE + 1:
                                         pc - PRE_ROUTINE + 3], "little")
            return {"target": target, "A": a, "X": x, "steps": steps,
                    "witness": bytes(memory[WITNESS + i]
                                     for i in range(WITNESS_BYTES))}
        else:
            raise WitnessError(f"wrapper model opcode ${op:02X} at ${pc:04X}")


def build_artifacts() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    ART.mkdir(parents=True)
    routine, reset = wrapper(), witness_reset()
    base_prg = BASE_PRG.read_bytes()
    result = bytearray(base_prg)
    require(prg_slice(base_prg, WITNESS, WITNESS_BYTES) == b"\x00" * WITNESS_BYTES,
            "owner-free witness interval is not zero")
    prg_patch(result, WITNESS, b"\x00" * WITNESS_BYTES, reset)
    before_state = prg_slice(base_prg, PRE_ROUTINE, len(routine))
    prg_patch(result, PRE_ROUTINE, before_state, routine)
    DIAG_PRG.write_bytes(bytes(result))
    WITNESS_RESET_FILE.write_bytes(reset)
    overlay = patch_overlay(BASE_BOOT_RAW.read_bytes())
    BOOT_RAW.write_bytes(overlay)
    BOOTSTAGE.write_bytes(patch_bootstage(BASE_BOOTSTAGE.read_bytes(), overlay))
    patch_elf(overlay, routine, reset)

    base_deploy = load(BASE_DEPLOY)
    base_c2d = [row for row in base_deploy["diagnostic"]["preloads"]
                if row["role"] == "c2d-v6-code-plane"]
    require(len(base_c2d) == 1 and base_c2d[0]["bytes"] == RESET_PREFIX_BYTES,
            "one exact Link-82 C2D prefix required")
    prefix = (ROOT / base_c2d[0]["path"]).read_bytes()
    require(len(prefix) == RESET_PREFIX_BYTES
            and digest(prefix) == base_c2d[0]["sha256"],
            "Link-82 C2D prefix binding drift")
    reset_domain = prefix + bytes(RESET_DOMAIN_BYTES - RESET_PREFIX_BYTES)
    RESET_DOMAIN_FILE.write_bytes(reset_domain)
    deployment = deepcopy(base_deploy)
    deployment["format"] = "lisp65-c2.3-v1.6-mem-init-before-after-deployment-v1"
    deployment["status"] = "HOST-GREEN-NON-PROMOTABLE-MEM-INIT-WITNESS"
    deployment["diagnostic"]["prg"] = bind(DIAG_PRG)
    deployment["diagnostic"]["elf"] = bind(DIAG_ELF)
    rows = deployment["diagnostic"]["preloads"]
    c2d = [row for row in rows if row["role"] == "c2d-v6-code-plane"]
    require(len(c2d) == 1, "one C2D preload required")
    c2d[0].update(bind(RESET_DOMAIN_FILE))
    c2d[0]["address"] = "0x00050000"
    c2d[0]["role"] = "c2d-v6-reset-domain"
    boot = [row for row in rows if row["role"] == "c2-two-record-boot-stage"]
    require(len(boot) == 1, "one boot-stage preload required")
    boot[0].update(bind(BOOTSTAGE)); boot[0]["address"] = "0x00058500"
    boot[0]["role"] = "c2-two-record-boot-stage"
    deployment["mem_init_witness"] = {
        "address": f"0x{WITNESS:04x}", "bytes": WITNESS_BYTES,
        "reset": bind(WITNESS_RESET_FILE),
        "before": {"tag": "0xa1", "freelist": [1, 3], "alloc_high": [3, 5]},
        "after": {"tag": "0xa6", "freelist": [6, 8], "alloc_high": [8, 10]},
        "pre_routine": f"0x{PRE_ROUTINE:04x}",
        "post_routine": f"0x{POST_ROUTINE:04x}",
        "measured_forms": 0, "promotable": False,
        "reset_domain": {
            **bind(RESET_DOMAIN_FILE),
            "address": "0x00050000",
            "prefix_bytes": RESET_PREFIX_BYTES,
            "prefix_sha256": digest(prefix),
            "suffix_nonzero_bytes": 0,
            "C2J": [C2J_OFFSET, C2J_OFFSET + C2J_BYTES],
            "C2J_nonzero_bytes": 0,
        },
    }
    write_json(DEPLOY, deployment)
    write_json(RECEIPT, expected())


def exact() -> tuple[dict[str, Any], dict[str, Any]]:
    commission, commission_binding = git_blob(OWNER_COMMIT, PLAN)
    require(b"mem_init before/after witness authorized" in commission
            and b"one contact" in commission, "owner authorization drift")
    base_receipt, caller, ownership = (load(BASE_RECEIPT), load(CALLER_RECEIPT),
                                       load(OWNERSHIP_RECEIPT))
    require(caller["facts"]["linked_caller_partition"]
            ["unique_legal_edge_under_captured_state"]["symbol"] == "alloc+0x59",
            "caller authority drift")
    gap = ownership["facts"]["durable_witness"]["containing_gap"]
    require(gap == {"start": "0xb582", "end_exclusive": "0xb5c4", "bytes": 66}
            and ownership["facts"]["durable_witness"]
                ["disjoint_from_all_post_ownership_owners"],
            "owner-free interval authority drift")
    require(base_receipt["facts"]["scope"]["product_candidate_bytes_changed"] == 0,
            "base diagnostic scope drift")
    for path in (DIAG_ELF, DIAG_PRG, BOOT_RAW, BOOTSTAGE,
                 WITNESS_RESET_FILE, RESET_DOMAIN_FILE, DEPLOY):
        require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")

    base_deploy = load(BASE_DEPLOY)
    base_c2d = [row for row in base_deploy["diagnostic"]["preloads"]
                if row["role"] == "c2d-v6-code-plane"]
    require(len(base_c2d) == 1 and base_c2d[0]["bytes"] == RESET_PREFIX_BYTES,
            "base C2D prefix geometry drift")
    prefix = (ROOT / base_c2d[0]["path"]).read_bytes()
    reset_domain = RESET_DOMAIN_FILE.read_bytes()
    require(len(reset_domain) == RESET_DOMAIN_BYTES
            and reset_domain[:RESET_PREFIX_BYTES] == prefix
            and not any(reset_domain[RESET_PREFIX_BYTES:])
            and not any(reset_domain[C2J_OFFSET:C2J_OFFSET + C2J_BYTES]),
            "identity-matched complete reset-domain drift")
    deployment = load(DEPLOY)
    c2d = [row for row in deployment["diagnostic"]["preloads"]
           if row["role"] == "c2d-v6-reset-domain"]
    require(len(c2d) == 1 and c2d[0] == {
        **bind(RESET_DOMAIN_FILE), "address": "0x00050000",
        "role": "c2d-v6-reset-domain"},
        "deployed reset-domain row drift")
    reset_binding = deployment["mem_init_witness"]["reset_domain"]
    require(reset_binding == {
        **bind(RESET_DOMAIN_FILE), "address": "0x00050000",
        "prefix_bytes": RESET_PREFIX_BYTES, "prefix_sha256": digest(prefix),
        "suffix_nonzero_bytes": 0,
        "C2J": [C2J_OFFSET, C2J_OFFSET + C2J_BYTES],
        "C2J_nonzero_bytes": 0},
        "reset-domain deployment authority drift")

    routine, reset = wrapper(), witness_reset()
    truth = ElfTruth.read(DIAG_ELF, llvm_readobj=READOBJ, include_section_data=True)
    base_truth = ElfTruth.read(BASE_ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(truth.section_bytes(".lisp65_workbench_overlay") == BOOT_RAW.read_bytes(),
            "diagnostic ELF/boot overlay drift")
    require(truth.section_bytes(".lisp65_v16_defstruct_diagnostic_state")
            [PRE_ROUTINE - STATE:PRE_ROUTINE - STATE + len(routine)] == routine,
            "ELF wrapper bytes drift")
    witness_section = truth.section(".lisp65_v16_mem_init_witness")
    require((witness_section.address, witness_section.bytes) == (WITNESS, WITNESS_BYTES)
            and truth.section_bytes(witness_section.name) == reset,
            "ELF witness placement drift")
    require(prg_slice(DIAG_PRG.read_bytes(), WITNESS, WITNESS_BYTES) == reset
            and prg_slice(DIAG_PRG.read_bytes(), PRE_ROUTINE, len(routine)) == routine,
            "PRG witness/wrapper drift")
    base_overlay = base_truth.section_bytes(".lisp65_workbench_overlay")
    overlay = truth.section_bytes(".lisp65_workbench_overlay")
    changed = [i for i, pair in enumerate(zip(base_overlay, overlay, strict=True))
               if pair[0] != pair[1]]
    require(changed == [POST_INIT_CALL - OVERLAY_START + 1,
                        POST_INIT_CALL - OVERLAY_START + 2,
                        OVERLAY_ENTRY - OVERLAY_START + 1,
                        OVERLAY_ENTRY - OVERLAY_START + 2],
            f"overlay delta drift: {changed}")
    # Third entry byte stays $C3 in both JMP targets; it is intentionally not
    # counted as a changed byte even though the complete instruction is bound.
    require(overlay[OVERLAY_ENTRY - OVERLAY_START:
                    OVERLAY_ENTRY - OVERLAY_START + 3] == b"\x4c" + u16(PRE_ROUTINE)
            and overlay[POST_INIT_CALL - OVERLAY_START:
                        POST_INIT_CALL - OVERLAY_START + 3] == b"\x20" + u16(POST_ROUTINE),
            "overlay route drift")
    require(BOOTSTAGE.read_bytes()[:SECOND_RECORD] ==
            BASE_BOOTSTAGE.read_bytes()[:SECOND_RECORD],
            "bootstage first record drift")

    pre = simulate(routine, PRE_ROUTINE, 0x73, 0x4A, 0x1234, 0x5678)
    post = simulate(routine, POST_ROUTINE, 0x39, 0xB9, 0x0C00, 0x0000)
    require(pre == {"target": EVAL_INIT, "A": 0x73, "X": 0x4A, "steps": 21,
                    "witness": bytes.fromhex("a134127856d2cccccccc")}
            and post == {"target": INTERN, "A": 0x39, "X": 0xB9, "steps": 20,
                         "witness": bytes.fromhex("d1cccccccca6000c0000")},
            f"wrapper execution drift: pre={pre} post={post}")

    eval_source = SOURCE_EVAL.read_text(encoding="utf-8")
    mem_source = SOURCE_MEM.read_text(encoding="utf-8")
    require("WORKBENCH_BOOTFN void eval_init(void) {\n    obj t;\n    mem_init();" in eval_source
            and "for (i = MAX_CELLS - 1; i >= HEAP_CELLS; i--)" in mem_source,
            "source mem_init/eval_init order drift")
    require(base_overlay[POST_INIT_CALL - OVERLAY_START:
                         POST_INIT_CALL - OVERLAY_START + 3] == b"\x20" + u16(INTERN)
            and base_overlay[0xC4BD - OVERLAY_START:0xC4C5 - OVERLAY_START] ==
                bytes.fromhex("a25d8604a2b98605"),
            "first post-mem_init allocator setup drift")

    facts = {
        "placement": {
            "owner_free_interval": ["0xb582", "0xb5c4"],
            "witness": ["0xb582", "0xb58c"],
            "shared_wrapper": ["0xc048", "0xc07b"],
            "wrapper_inside_nonpromotable_record": True,
            "all_ranges_disjoint": True,
        },
        "routes": {
            "before": {"hook": "0xc85a", "entry": "0xc048",
                       "tail": "0xc3fd", "tag": "0xa1"},
            "after": {"hook": "0xc4c5", "entry": "0xc04e",
                      "tail": "0x2dff", "tag": "0xa6"},
            "post_hook_is_first_allocator_after_inlined_mem_init": True,
            "raw_before_tag": True, "A_X_preserved": True,
        },
        "execution": {
            "before_model": {**pre, "witness": pre["witness"].hex()},
            "after_model": {**post, "witness": post["witness"].hex()},
            "bootstage_first_record_byteidentical": True,
            "patched_second_record_CRC_valid": True,
            "base_product_and_ROMC_repair_immutable": True,
        },
        "reset_domain": {
            "bytes": RESET_DOMAIN_BYTES,
            "identity_prefix": [0, RESET_PREFIX_BYTES],
            "identity_prefix_sha256": digest(prefix),
            "zero_suffix": [RESET_PREFIX_BYTES, RESET_DOMAIN_BYTES],
            "suffix_nonzero_bytes": 0,
            "C2J": [C2J_OFFSET, C2J_OFFSET + C2J_BYTES],
            "C2J_nonzero_bytes": 0,
            "standing_gate": "c2-reset-domain-completeness-check",
            "prefix_only_restaging_rejected": True,
        },
        "decision_table": {
            "after_built_then_live_empty": "LATER-TARGET-STATE-DESTRUCTION",
            "before_empty_after_reached_empty": "MEM-INIT-DID-NOT-BUILD-FREELIST",
            "before_reached_after_absent": "MEM-INIT-IN-FLIGHT-OR-STALLED-NO-OVERCLAIM",
            "after_built_live_nonempty": "INIT-BUILT-NO-FAILURE-REPRODUCED",
            "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        },
        "scope": {"diagnostic_promotable": False, "product_bytes": 0,
                  "product_links": 0, "WPLTO_runs": 0, "hardware_contacts": 0,
                  "measured_forms": 0, "R_A_I_G": None,
                  "contact_authorized_by_owner": True,
                  "contact_consumed": False},
    }
    audit(facts)
    authorities = {
        "owner_authorization": commission_binding, "base_receipt": bind(BASE_RECEIPT),
        "caller_attribution": bind(CALLER_RECEIPT), "ownership": bind(OWNERSHIP_RECEIPT),
        "base_ELF": bind(BASE_ELF), "base_PRG": bind(BASE_PRG),
        "base_boot_overlay": bind(BASE_BOOT_RAW), "base_bootstage": bind(BASE_BOOTSTAGE),
        "source_eval": bind(SOURCE_EVAL), "source_mem": bind(SOURCE_MEM),
        "driver": bind(DRIVER), "contact_driver": bind(CONTACT_DRIVER),
        "runner": bind(RUNNER), "diagnostic_ELF": bind(DIAG_ELF),
        "diagnostic_PRG": bind(DIAG_PRG), "diagnostic_boot_overlay": bind(BOOT_RAW),
        "diagnostic_bootstage": bind(BOOTSTAGE), "deployment": bind(DEPLOY),
        "reset_domain": bind(RESET_DOMAIN_FILE),
        "standing_reset_domain_gate": bind(ROOT / (
            "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
            "c2.3-v1.3-link85-full-reset-domain-host-receipt.json")),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    require(facts["placement"] == {
        "owner_free_interval": ["0xb582", "0xb5c4"],
        "witness": ["0xb582", "0xb58c"],
        "shared_wrapper": ["0xc048", "0xc07b"],
        "wrapper_inside_nonpromotable_record": True,
        "all_ranges_disjoint": True}, "placement claim drift")
    routes = facts["routes"]
    require(routes["before"] == {"hook": "0xc85a", "entry": "0xc048",
                                  "tail": "0xc3fd", "tag": "0xa1"}
            and routes["after"] == {"hook": "0xc4c5", "entry": "0xc04e",
                                    "tail": "0x2dff", "tag": "0xa6"}
            and routes["post_hook_is_first_allocator_after_inlined_mem_init"]
            and routes["raw_before_tag"] and routes["A_X_preserved"],
            "route semantics drift")
    execution = facts["execution"]
    require(execution["before_model"]["target"] == EVAL_INIT
            and execution["after_model"]["target"] == INTERN
            and execution["before_model"]["A"] == 0x73
            and execution["before_model"]["X"] == 0x4A
            and execution["after_model"]["A"] == 0x39
            and execution["after_model"]["X"] == 0xB9
            and execution["before_model"]["witness"] == "a134127856d2cccccccc"
            and execution["after_model"]["witness"] == "d1cccccccca6000c0000"
            and execution["bootstage_first_record_byteidentical"]
            and execution["patched_second_record_CRC_valid"]
            and execution["base_product_and_ROMC_repair_immutable"],
            "execution/identity claim drift")
    require(facts["decision_table"] == {
        "after_built_then_live_empty": "LATER-TARGET-STATE-DESTRUCTION",
        "before_empty_after_reached_empty": "MEM-INIT-DID-NOT-BUILD-FREELIST",
        "before_reached_after_absent": "MEM-INIT-IN-FLIGHT-OR-STALLED-NO-OVERCLAIM",
        "after_built_live_nonempty": "INIT-BUILT-NO-FAILURE-REPRODUCED",
        "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"},
        "decision table drift")
    require(facts["reset_domain"] == {
        "bytes": RESET_DOMAIN_BYTES,
        "identity_prefix": [0, RESET_PREFIX_BYTES],
        "identity_prefix_sha256": digest((ROOT / load(BASE_DEPLOY)["diagnostic"]
            ["preloads"][0]["path"]).read_bytes()),
        "zero_suffix": [RESET_PREFIX_BYTES, RESET_DOMAIN_BYTES],
        "suffix_nonzero_bytes": 0,
        "C2J": [C2J_OFFSET, C2J_OFFSET + C2J_BYTES],
        "C2J_nonzero_bytes": 0,
        "standing_gate": "c2-reset-domain-completeness-check",
        "prefix_only_restaging_rejected": True},
        "reset-domain claim drift")
    require(facts["scope"] == {
        "diagnostic_promotable": False, "product_bytes": 0, "product_links": 0,
        "WPLTO_runs": 0, "hardware_contacts": 0, "measured_forms": 0,
        "R_A_I_G": None, "contact_authorized_by_owner": True,
        "contact_consumed": False}, "scope drift")


def expected() -> dict[str, Any]:
    facts, authorities = exact()
    return {
        "format": "lisp65-c2.3-v1.6-mem-init-before-after-preparation-v1",
        "recorded_on": PREPARATION_RECORDED_ON,
        "status": "HOST-GREEN NON-PROMOTABLE BEFORE-AFTER WITNESS; CONTACT READY",
        "authorities": authorities, "facts": facts,
        "execution_witnesses": 8,
        "rejected_mutations": [
            "move-witness-outside-owner-free-gap", "overlap-wrapper-and-witness",
            "route-before-after-eval-init", "route-after-before-mem-init-end",
            "write-tag-before-raw", "clobber-A", "clobber-X",
            "change-post-tail", "change-before-tail", "change-boot-first-record",
            "accept-bad-second-record-CRC", "mutate-base-product",
            "claim-missing-after-is-empty-after", "claim-nonreproduction-is-destruction",
            "claim-R-A-I-G", "claim-contact-consumed",
            "prefix-only-reset-domain", "nonzero-reset-domain-suffix",
            "nonclear-C2J", "allow-partial-restaging"],
        "claim_limit": (
            "Diagnostic-only host preparation for one owner-authorized physical "
            "launch contact. It adds two tagged allocator snapshots and no measured "
            "form. No product byte, product link, R/A/I/G result or device result is claimed."),
    }


def selftest() -> dict[str, Any]:
    facts, _ = exact()
    mutations: list[tuple[list[Any], Any]] = [
        (["placement", "witness", 0], "0xb581"),
        (["placement", "all_ranges_disjoint"], False),
        (["routes", "before", "tail"], "0xc400"),
        (["routes", "after", "hook"], "0xc4b4"),
        (["routes", "raw_before_tag"], False),
        (["routes", "A_X_preserved"], False),
        (["execution", "after_model", "X"], 0),
        (["routes", "after", "tail"], "0x2e00"),
        (["routes", "before", "tail"], "0xc3fe"),
        (["execution", "bootstage_first_record_byteidentical"], False),
        (["execution", "patched_second_record_CRC_valid"], False),
        (["execution", "base_product_and_ROMC_repair_immutable"], False),
        (["decision_table", "before_reached_after_absent"],
         "MEM-INIT-DID-NOT-BUILD-FREELIST"),
        (["decision_table", "after_built_live_nonempty"],
         "LATER-TARGET-STATE-DESTRUCTION"),
        (["scope", "R_A_I_G"], "R"),
        (["scope", "contact_consumed"], True),
        (["reset_domain", "bytes"], RESET_PREFIX_BYTES),
        (["reset_domain", "suffix_nonzero_bytes"], 1),
        (["reset_domain", "C2J_nonzero_bytes"], C2J_BYTES),
        (["reset_domain", "prefix_only_restaging_rejected"], False),
    ]
    rejected = 0
    for path, replacement in mutations:
        trial = deepcopy(facts)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except WitnessError:
            rejected += 1
        else:
            raise WitnessError(f"mutation survived: {path}")
    require(rejected == len(mutations), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": rejected,
            "execution_witnesses": 8}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.command == "build":
            build_artifacts()
            print("MEM_INIT BEFORE/AFTER BUILD PASS witness=B582-B58B "
                  "pre=C048 post=C04E contact=ready")
            return 0
        if args.command == "selftest":
            result = selftest()
            print("MEM_INIT BEFORE/AFTER SELFTEST PASS "
                  f"mutations={result['mutations']} witnesses={result['execution_witnesses']}")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(expected()),
                "mem_init before/after receipt drift; run build deliberately")
        print("MEM_INIT BEFORE/AFTER PASS witness=B582-B58B "
              "pre=C048 post=C04E contact=ready")
        return 0
    except (WitnessError, KeyError, ValueError, TypeError) as exc:
        print(f"MEM_INIT BEFORE/AFTER FIRST RED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
