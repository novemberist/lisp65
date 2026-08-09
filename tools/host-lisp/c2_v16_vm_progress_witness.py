#!/usr/bin/env python3
"""Build and gate the non-promotable v1.6 VM progress identity.

The ordinary Link-82 dispatch begins with ``LDX vm_run_inner.poll_``.  This
identity redirects exactly that three-byte instruction through a low-RAM
helper which increments a 32-bit counter, snapshots the current C2 directory
ordinal, replays the displaced load and returns.  The helper and state occupy
the owner-free gap between the resident-island annex and the BASIC header, so
their reads cannot be redirected to ROM and rollback cannot reach them.
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
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_v16_defstruct_phase_c as PHASE_C  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-pre-rollback-shadow/deployment.json"
BASE_RECEIPT = EVIDENCE / (
    "c2.3-v1.6-defstruct-pre-rollback-shadow-preparation-receipt.json")
VM_COST = EVIDENCE / "c2.3-v1.6-defstruct-vm-cost-closure-receipt.json"
OWNERSHIP = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-guard-attribution-receipt.json")
V17 = EVIDENCE / "c2.3-v1.7-state-ownership-phase-a-inventory-receipt.json"
V18 = EVIDENCE / "c2.3-v1.8-full-map-phase-a-closure-receipt.json"
VM_SOURCE = ROOT / "src/vm.c"
PRODUCT_HEADER = ROOT / "src/c2_product_runtime.h"
PLAN_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
OWNER_COMMIT = "b8820ecadb875b0b581c9df9fd621c45c99bf75e"
DRIVER = Path(__file__).resolve()
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

OUT = ROOT / "build/c2.3/v1.6-defstruct-vm-progress"
ART = OUT / "artifacts"
PROGRESS_PRG = ART / "diagnostic-vm-progress.prg"
PROGRESS_ELF = ART / "diagnostic-vm-progress.elf"
HELPER_BIN = ART / "vm-progress-helper.bin"
STATE_BIN = ART / "vm-progress-state-reset.bin"
PRELOAD_BIN = ART / "vm-progress-lowram-preload.bin"
DEPLOY = OUT / "deployment.json"
RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-vm-progress-preparation-receipt.json"

FORMAT = "lisp65-c2.3-v1.6-defstruct-vm-progress-preparation-v1"
RECORDED_ON = "2026-08-06"
PRG_LOAD = 0x2001
HELPER = 0x1FCE
HELPER_BYTES = 42
STATE = HELPER + HELPER_BYTES
STATE_BYTES = 8
GAP_END = 0x2001
HOOK = 0x467D
POLL = 0xBFEA
OWNER_OFF = 0xB9B2
ROLLBACK_START = 0xE9E5
ROLLBACK_END = 0xEA02
SECTION_HELPER = ".lisp65_v16_defstruct_vm_progress_helper"
SECTION_STATE = ".lisp65_v16_defstruct_vm_progress_state"
STATE_RESET = bytes((0, 0, 0, 0, 0xD2, 0xD3, 0x20, 0xA5))


class ProgressError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProgressError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
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
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name); handle.write(raw)
    temporary.replace(path)


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"commit": full, "path": path, "bytes": len(raw),
            "sha256": digest(raw)}


def u16(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def prg_offset(address: int) -> int:
    return 2 + address - PRG_LOAD


def helper_bytes() -> bytes:
    counter = STATE
    owner = STATE + 4
    sequence = STATE + 6
    code = bytearray(b"\x48")              # preserve caller A
    code += b"\xee" + u16(sequence)       # sequence odd: write in progress
    code += b"\xad" + u16(OWNER_OFF)      # current C2 directory ordinal low
    code += b"\x8d" + u16(owner)
    code += b"\xad" + u16(OWNER_OFF + 1)  # current C2 directory ordinal high
    code += b"\x8d" + u16(owner + 1)
    code += b"\xee" + u16(counter)        # 32-bit little-endian increment
    code += b"\xd0\x0d"
    code += b"\xee" + u16(counter + 1)
    code += b"\xd0\x08"
    code += b"\xee" + u16(counter + 2)
    code += b"\xd0\x03"
    code += b"\xee" + u16(counter + 3)
    code += b"\xee" + u16(sequence)       # sequence even: atomic snapshot
    code += b"\x68"                       # restore caller A
    code += b"\xae" + u16(POLL)           # displaced LDX poll_; restores N/Z
    code += b"\x60"
    require(len(code) == HELPER_BYTES, f"progress helper size drift: {len(code)}")
    return bytes(code)


def run(argv: list[str], label: str) -> None:
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, check=False)
    require(result.returncode == 0, f"{label} failed:\n{result.stdout}")


def patch_elf(base_elf: Path, helper: bytes, state: bytes) -> None:
    truth = ElfTruth.read(base_elf, llvm_readobj=READOBJ, include_section_data=True)
    text = truth.section(".text")
    text_data = bytearray(truth.section_bytes(".text"))
    at = HOOK - text.address
    require(text_data[at:at + 3] == b"\xae" + u16(POLL),
            "base VM dispatch hook bytes drift")
    text_data[at:at + 3] = b"\x20" + u16(HELPER)
    ART.mkdir(parents=True, exist_ok=True)
    text_file = ART / "section-text.bin"; text_file.write_bytes(text_data)
    args = [str(OBJCOPY), f"--update-section=.text={text_file}",
            f"--add-section={SECTION_HELPER}={HELPER_BIN}",
            f"--set-section-flags={SECTION_HELPER}=alloc,load,readonly,code",
            f"--add-section={SECTION_STATE}={STATE_BIN}",
            f"--set-section-flags={SECTION_STATE}=alloc,load,data",
            f"--add-symbol=lisp65_v16_vm_progress_helper=0x{HELPER:x},global,function",
            f"--add-symbol=lisp65_v16_vm_progress_state=0x{STATE:x},global,object",
            str(base_elf), str(PROGRESS_ELF)]
    run(args, "derive VM-progress ELF")
    PHASE_C.patch_elf_section_addresses(PROGRESS_ELF, {
        SECTION_HELPER: HELPER, SECTION_STATE: STATE})


def allocated_gap(truth: ElfTruth) -> dict[str, Any]:
    allocated = [row for row in truth.sections
                 if row.bytes and "SHF_ALLOC" in row.flags]
    overlaps = [row.name for row in allocated
                if row.address < GAP_END and row.address + row.bytes > HELPER]
    require(not overlaps, f"progress low-RAM gap has active owners: {overlaps}")
    before = max((row for row in allocated if row.address + row.bytes <= HELPER),
                 key=lambda row: row.address + row.bytes)
    after = min((row for row in allocated if row.address >= GAP_END),
                key=lambda row: row.address)
    require(before.name == ".lisp65_resident_island_annex"
            and before.address + before.bytes == HELPER
            and after.name == ".basic_header" and after.address == GAP_END,
            "low-RAM owner-free gap boundary drift")
    return {"start": "0x1fce", "end_exclusive": "0x2001", "bytes": 51,
            "preceding_owner_end": before.name,
            "following_owner_start": after.name,
            "active_owner_overlaps": 0}


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


def execute_helper(raw: bytes, counter: int, owner: int,
                   sequence: int) -> dict[str, int]:
    """Execute the emitted helper in an independent tiny 6502 model."""
    require(0 <= counter <= 0xFFFFFFFF and 0 <= owner <= 0xFFFF,
            "execution-vector input outside encoded width")
    memory = bytearray(65536)
    memory[HELPER:HELPER + len(raw)] = raw
    memory[STATE:STATE + STATE_BYTES] = STATE_RESET
    memory[STATE:STATE + 4] = counter.to_bytes(4, "little")
    memory[STATE + 6] = sequence
    memory[OWNER_OFF:OWNER_OFF + 2] = owner.to_bytes(2, "little")
    memory[POLL] = 0x6C
    pc = HELPER; accumulator = 0x5A; x = 0; zero = False; stack = 0xFD
    for _step in range(64):
        opcode = memory[pc]; pc += 1
        if opcode in (0xEE, 0xAD, 0x8D, 0xAE):
            address = memory[pc] | memory[pc + 1] << 8; pc += 2
            if opcode == 0xEE:
                memory[address] = (memory[address] + 1) & 0xFF
                zero = memory[address] == 0
            elif opcode == 0xAD:
                accumulator = memory[address]; zero = accumulator == 0
            elif opcode == 0x8D:
                memory[address] = accumulator
            else:
                x = memory[address]; zero = x == 0
        elif opcode == 0x48:
            memory[0x100 + stack] = accumulator
            stack = (stack - 1) & 0xFF
        elif opcode == 0x68:
            stack = (stack + 1) & 0xFF
            accumulator = memory[0x100 + stack]
            zero = accumulator == 0
        elif opcode == 0xD0:
            delta = memory[pc]; pc += 1
            if not zero:
                pc = (pc + (delta if delta < 0x80 else delta - 0x100)) & 0xFFFF
        elif opcode == 0x60:
            break
        else:
            raise ProgressError(f"unmodeled helper opcode 0x{opcode:02x}")
    else:
        raise ProgressError("helper execution did not return")
    return {
        "counter": int.from_bytes(memory[STATE:STATE + 4], "little"),
        "owner": int.from_bytes(memory[STATE + 4:STATE + 6], "little"),
        "sequence": memory[STATE + 6], "arm": memory[STATE + 7],
        "returned_A": accumulator, "returned_X": x,
        "returned_zero": int(zero), "returned_stack": stack,
        "instructions_executed_at_most": 64,
    }


def helper_execution_vectors(raw: bytes) -> list[dict[str, Any]]:
    """Execute no-carry, every carry edge, and full wrap on every gate run."""
    vectors: list[dict[str, Any]] = []
    for before in (0, 1, 0xFE, 0xFF, 0xFFFF, 0xFFFFFF, 0xFFFFFFFF):
        after = execute_helper(raw, before, 0x02D5, 0x20)
        require(after == {
            "counter": (before + 1) & 0xFFFFFFFF, "owner": 0x02D5,
            "sequence": 0x22, "arm": 0xA5, "returned_A": 0x5A,
            "returned_X": 0x6C, "returned_zero": 0,
            "returned_stack": 0xFD,
            "instructions_executed_at_most": 64,
        }, f"helper execution-vector mismatch at 0x{before:08x}")
        vectors.append({"before": before, "after": after["counter"],
                        "owner_ordinal": "0x02d5",
                        "sequence_before": "0x20",
                        "sequence_after": f"0x{after['sequence']:02x}",
                        "A_before": "0x5a", "A_after": "0x5a",
                        "X_after": "0x6c", "Z_after": 0,
                        "stack_before": "0xfd", "stack_after": "0xfd"})
    require([row["after"] for row in vectors]
            == [1, 2, 0xFF, 0x100, 0x10000, 0x1000000, 0],
            "32-bit counter carry witness drift")
    return vectors


def build() -> dict[str, Any]:
    base_deploy = load(BASE_DEPLOY)
    base_receipt = load(BASE_RECEIPT)
    cost = load(VM_COST)
    ownership = load(OWNERSHIP)
    v17 = load(V17); v18 = load(V18)
    require(base_deploy["status"] == "HOST-GREEN-NON-PROMOTABLE-SHADOW-ARMED"
            and base_deploy["promotable"] is False,
            "pre-rollback shadow deployment drift")
    require(base_receipt["status"] ==
            "HOST-GREEN; RECONTACT QUESTION RETURNED TO OWNER",
            "pre-rollback shadow preparation drift")
    require(cost["status"] == "VM-COST-TERM-CLOSED; NO-COMPLETION-UPPER-BOUND"
            and cost["decision"]["required_next_instrument"] ==
            "independent product-side progress witness",
            "VM-cost closure prerequisite drift")
    require(ownership["facts"]["owner_free_rule"].startswith(
        "A diagnostic witness slot is owner-free only"),
        "owner-free/validated-region rule drift")
    require(v17["execution_witness"]["input_sections_enumerated"] == 72
            and v18["execution_witness"][
                "lto_allocatable_chain_inputs_enumerated"] == 80,
            "state/full-map inventory authority drift")
    vm_source = VM_SOURCE.read_text(encoding="utf-8")
    header = PRODUCT_HEADER.read_text(encoding="utf-8")
    require("{ static uint8_t poll_; if (++poll_ == 0) lisp_poll(); }" in vm_source
            and "static uint16_t vm_buf_off" in vm_source
            and "#define LISP65_C2_CODE_BANK_TAG 0xfeu" in header,
            "VM dispatch/C2 directory-ordinal source contract drift")

    base_prg_path = ROOT / base_deploy["diagnostic"]["prg"]["path"]
    base_elf_path = ROOT / base_deploy["diagnostic"]["elf"]["path"]
    require(bind(base_prg_path)["sha256"] ==
            base_deploy["diagnostic"]["prg"]["sha256"]
            and bind(base_elf_path)["sha256"] ==
            base_deploy["diagnostic"]["elf"]["sha256"],
            "base shadow artifact binding drift")
    base_prg = base_prg_path.read_bytes()
    require(int.from_bytes(base_prg[:2], "little") == PRG_LOAD,
            "base PRG load address drift")
    helper = helper_bytes(); state = STATE_RESET
    require(HELPER + len(helper) == STATE
            and STATE + len(state) <= GAP_END,
            "helper/state placement exceeds low-RAM gap")
    base_truth = ElfTruth.read(base_elf_path, llvm_readobj=READOBJ,
                               include_section_data=True)
    gap = allocated_gap(base_truth)
    require(base_truth.symbol("__heap_start").value == 0xC354
            and base_truth.symbol("__stack").value == 0xD000,
            "heap/stack ownership boundary drift")

    progress = bytearray(base_prg)
    at = prg_offset(HOOK)
    require(progress[at:at + 3] == b"\xae" + u16(POLL),
            "PRG dispatch-hook authority drift")
    progress[at:at + 3] = b"\x20" + u16(HELPER)
    ART.mkdir(parents=True, exist_ok=True)
    HELPER_BIN.write_bytes(helper); STATE_BIN.write_bytes(state)
    PRELOAD_BIN.write_bytes(helper + state); PROGRESS_PRG.write_bytes(progress)
    patch_elf(base_elf_path, helper, state)

    truth = ElfTruth.read(PROGRESS_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    require(truth.section(SECTION_HELPER).address == HELPER
            and truth.section_bytes(SECTION_HELPER) == helper
            and truth.section(SECTION_STATE).address == STATE
            and truth.section_bytes(SECTION_STATE) == state,
            "progress ELF low-RAM sections drift")
    edges = executable_edges(truth, HELPER)
    require(edges == [{"section": ".text", "pc": "0x467d", "opcode": "JSR"}],
            f"progress helper inbound-edge closure drift: {edges}")
    rollback = base_prg[prg_offset(ROLLBACK_START):prg_offset(ROLLBACK_END)]
    target = u16(HELPER)
    require(not any(rollback[i] in (0x20, 0x4C)
                    and rollback[i + 1:i + 3] == target
                    for i in range(len(rollback) - 2)),
            "rollback reaches progress helper")

    # Independent executable witnesses cover no carry and every carry edge.
    vectors = helper_execution_vectors(helper)

    deploy = deepcopy(base_deploy)
    deploy["format"] = "lisp65-c2.3-v1.6-vm-progress-deployment-v1"
    deploy["status"] = "HOST-GREEN-NON-PROMOTABLE-VM-PROGRESS-ARMED"
    deploy["diagnostic"]["prg"] = bind(PROGRESS_PRG)
    deploy["diagnostic"]["elf"] = bind(PROGRESS_ELF)
    deploy["diagnostic"]["preloads"].append({
        **bind(PRELOAD_BIN), "address": "0x00001fce",
        "role": "diagnostic-vm-progress-lowram"})
    deploy["vm_progress"] = {
        "helper": {"start": "0x1fce", "end_exclusive": "0x1ff8",
                   "bytes": HELPER_BYTES},
        "state": {"start": "0x1ff8", "end_exclusive": "0x2000",
                  "bytes": STATE_BYTES,
                  "layout": ["counter_u32_le", "owner_ordinal_u16_le",
                             "sequence", "arm"]},
        "dispatch_hook": "0x467d", "replaced": "LDX $BFEA",
        "replayed_before_return": True,
        "counter_granularity": "every VM dispatch",
        "sample_rule": "arm=A5 and equal even sequence before/after payload",
        "recontact_authorized": False,
    }
    write_json(DEPLOY, deploy)

    # Product/control authorities remain immutable.
    control_prg = ROOT / base_deploy["control"]["prg"]["path"]
    control_elf = ROOT / base_deploy["control"]["elf"]["path"]
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; PROGRESS-WITNESS-ARMED; CONTACT-NOT-AUTHORIZED",
        "authorities": {
            "owner_commission": git_bind(OWNER_COMMIT, PLAN_PATH),
            "base_shadow_deployment": bind(BASE_DEPLOY),
            "base_shadow_preparation": bind(BASE_RECEIPT),
            "VM_cost_closure": bind(VM_COST),
            "owner_free_rule": bind(OWNERSHIP),
            "state_inventory": bind(V17), "full_map_inventory": bind(V18),
            "VM_source": bind(VM_SOURCE), "C2_runtime_header": bind(PRODUCT_HEADER),
            "driver": bind(DRIVER),
        },
        "identity": {
            "promotable": False, "product_candidate_bytes_changed": 0,
            "product_links": 0, "WPLTO_runs": 0, "hardware_contacts": 0,
            "control_PRG": bind(control_prg), "control_ELF": bind(control_elf),
            "base_shadow_PRG": bind(base_prg_path),
            "base_shadow_ELF": bind(base_elf_path),
            "progress_PRG": bind(PROGRESS_PRG),
            "progress_ELF": bind(PROGRESS_ELF),
            "PRG_delta": [{"start": "0x467d", "bytes": 3,
                           "before": "aeeabf", "after": "20ce1f"}],
            "extra_lowram_preload": bind(PRELOAD_BIN),
            "other_preloads_byteidentical": True,
        },
        "placement": {
            "base_owner_free_gap": gap,
            "helper": {"start": "0x1fce", "end_exclusive": "0x1ff8",
                       "bytes": HELPER_BYTES, "always_RAM_below_ROM_windows": True},
            "state": {"start": "0x1ff8", "end_exclusive": "0x2000",
                      "bytes": STATE_BYTES, "always_RAM_below_ROM_windows": True},
            "spare_tail_bytes": GAP_END - (STATE + STATE_BYTES),
            "outside_ownership_validated_regions": True,
            "rollback_edges_to_helper": 0,
            "only_inbound_edge": edges[0],
        },
        "witness": {
            "hook": "vm_run_inner loop-head LDX poll_ at $467D",
            "counter": {"address": "0x1ff8", "bits": 32,
                        "endianness": "little", "granularity": "every VM dispatch",
                        "read_modify_write_under_ROM": False},
            "owner_ordinal": {"address": "0x1ffc", "bits": 16,
                              "source": "vm_buf_off ($B9B2/$B9B3)",
                              "C2_bank_tag": "0xfe",
                              "meaning": "current C2 directory ordinal"},
            "sequence": {"address": "0x1ffe", "initial": "0x20",
                         "odd_while_writing": True, "even_when_committed": True},
            "arm": {"address": "0x1fff", "value": "0xa5",
                    "staging_readback_required": True},
            "atomic_sample_rule": (
                "read sequence, payload, sequence; accept only equal even sequence "
                "and arm 0xA5"),
            "two_sample_decision": {
                "counter_grows": "LIVE-VM-DISPATCH-PROGRESS",
                "counter_equal": (
                    "NO-VM-DISPATCH-PROGRESS-IN-INTERVAL; owner ordinal and sampled "
                    "PC name the last VM owner / non-VM loop boundary"),
                "counter_decreases": "INVALID-SAMPLE-OR-WRAP; no claim",
            },
            "wrap_safety": {
                "counter_modulus": 4294967296,
                "target_cpu_hz": 40000000,
                "absolute_one_cycle_lower_bound_wrap_seconds": "107.3741824",
                "maximum_two_sample_horizon_seconds": 60,
                "wrap_possible_inside_authorized_horizon": False,
            },
            "helper_hex": helper.hex(),
            "reset_hex": state.hex(),
            "execution_vectors": vectors,
            "displaced_LDX_replayed": True,
            "register_stack_contract": {
                "caller_A_preserved": True,
                "hardware_stack_balanced": True,
                "return_NZ_from_displaced_LDX": True,
            },
            "rate_claim": (
                "instrumented diagnostic dispatch rate only; helper overhead is "
                "not silently promoted to the uninstrumented product rate"),
            "sample_transport_contract": {
                "status": "NOT-YET-BOUND",
                "noninterference_proof_present": False,
                "contact_authorized": False,
                "required_property": (
                    "two time-separated samples must not enter the monitor, stop "
                    "the CPU or trigger the source-less fail-closed path; otherwise "
                    "sample one can manufacture a frozen sample two; each atomic "
                    "read must also exclude an 8-bit seqlock ABA across 128 commits "
                    "or use an equivalent self-snapshot"),
            },
        },
        "deployment": bind(DEPLOY),
        "accounting": {"product_bytes_changed": 0, "product_links": 0,
                       "hardware_runs": 0, "recontact_authorized": False},
        "claim_limit": (
            "Host preparation of one non-promotable progress identity only. The "
            "counter establishes VM-dispatch progress, not completion or semantic "
            "correctness. An equal counter establishes no dispatch progress during "
            "the sampled interval; it is interpreted with the owner ordinal and CPU "
            "PC, not alone as an infinite-loop proof. No product byte, link, device "
            "contact, R/A/I/G result or recontact authorization is claimed."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT
            and value["status"] ==
            "HOST-GREEN; PROGRESS-WITNESS-ARMED; CONTACT-NOT-AUTHORIZED",
            "progress identity status drift")
    require(value["identity"]["promotable"] is False
            and value["identity"]["product_candidate_bytes_changed"] == 0
            and value["identity"]["product_links"] == 0
            and value["identity"]["WPLTO_runs"] == 0
            and value["identity"]["hardware_contacts"] == 0,
            "diagnostic identity boundary drift")
    placement = value["placement"]
    require(placement["base_owner_free_gap"]["active_owner_overlaps"] == 0
            and placement["helper"] == {
                "start": "0x1fce", "end_exclusive": "0x1ff8", "bytes": 42,
                "always_RAM_below_ROM_windows": True}
            and placement["state"] == {
                "start": "0x1ff8", "end_exclusive": "0x2000", "bytes": 8,
                "always_RAM_below_ROM_windows": True}
            and placement["spare_tail_bytes"] == 1
            and placement["outside_ownership_validated_regions"] is True
            and placement["rollback_edges_to_helper"] == 0
            and placement["only_inbound_edge"] == {
                "section": ".text", "pc": "0x467d", "opcode": "JSR"},
            "progress placement/route drift")
    witness = value["witness"]
    require(witness["counter"] == {
        "address": "0x1ff8", "bits": 32, "endianness": "little",
        "granularity": "every VM dispatch", "read_modify_write_under_ROM": False}
        and witness["owner_ordinal"] == {
            "address": "0x1ffc", "bits": 16,
            "source": "vm_buf_off ($B9B2/$B9B3)",
            "C2_bank_tag": "0xfe",
            "meaning": "current C2 directory ordinal"}
        and witness["sequence"] == {
            "address": "0x1ffe", "initial": "0x20",
            "odd_while_writing": True, "even_when_committed": True}
        and witness["arm"] == {"address": "0x1fff", "value": "0xa5",
                               "staging_readback_required": True}
        and witness["wrap_safety"]["maximum_two_sample_horizon_seconds"] == 60
        and witness["wrap_safety"]["wrap_possible_inside_authorized_horizon"] is False
        and witness["displaced_LDX_replayed"] is True
        and witness["register_stack_contract"] == {
            "caller_A_preserved": True,
            "hardware_stack_balanced": True,
            "return_NZ_from_displaced_LDX": True}
        and witness["rate_claim"].startswith(
            "instrumented diagnostic dispatch rate only")
        and witness["sample_transport_contract"] == {
            "status": "NOT-YET-BOUND",
            "noninterference_proof_present": False,
            "contact_authorized": False,
            "required_property": (
                "two time-separated samples must not enter the monitor, stop "
                "the CPU or trigger the source-less fail-closed path; otherwise "
                "sample one can manufacture a frozen sample two; each atomic "
                "read must also exclude an 8-bit seqlock ABA across 128 commits "
                "or use an equivalent self-snapshot")}
        and len(witness["execution_vectors"]) == 7,
        "progress witness semantics drift")
    require(value["accounting"] == {
        "product_bytes_changed": 0, "product_links": 0,
        "hardware_runs": 0, "recontact_authorized": False},
        "progress accounting drift")


def set_path(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for key in path[:-1]: cursor = cursor[key]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = load(RECEIPT)
    audit(base)
    cases: list[tuple[list[Any], Any]] = [
        (["status"], "CONTACT-AUTHORIZED"),
        (["identity", "promotable"], True),
        (["identity", "product_candidate_bytes_changed"], 1),
        (["identity", "product_links"], 1),
        (["identity", "hardware_contacts"], 1),
        (["placement", "base_owner_free_gap", "active_owner_overlaps"], 1),
        (["placement", "helper", "always_RAM_below_ROM_windows"], False),
        (["placement", "state", "always_RAM_below_ROM_windows"], False),
        (["placement", "outside_ownership_validated_regions"], False),
        (["placement", "rollback_edges_to_helper"], 1),
        (["placement", "only_inbound_edge", "pc"], "0xe9e5"),
        (["witness", "counter", "bits"], 16),
        (["witness", "counter", "granularity"], "every 256 dispatches"),
        (["witness", "counter", "read_modify_write_under_ROM"], True),
        (["witness", "owner_ordinal", "address"], "0x1ffa"),
        (["witness", "owner_ordinal", "C2_bank_tag"], "0x05"),
        (["witness", "sequence", "address"], "0x1ffc"),
        (["witness", "sequence", "odd_while_writing"], False),
        (["witness", "arm", "staging_readback_required"], False),
        (["witness", "wrap_safety", "maximum_two_sample_horizon_seconds"], 120),
        (["witness", "wrap_safety", "wrap_possible_inside_authorized_horizon"], True),
        (["witness", "displaced_LDX_replayed"], False),
        (["witness", "register_stack_contract", "caller_A_preserved"], False),
        (["witness", "register_stack_contract", "hardware_stack_balanced"], False),
        (["witness", "register_stack_contract", "return_NZ_from_displaced_LDX"], False),
        (["witness", "rate_claim"], "uninstrumented product rate"),
        (["witness", "sample_transport_contract", "noninterference_proof_present"], True),
        (["witness", "sample_transport_contract", "contact_authorized"], True),
        (["witness", "execution_vectors"], []),
        (["accounting", "recontact_authorized"], True),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base); set_path(trial, path, replacement)
        try: audit(trial)
        except ProgressError as error: rejected[f"mutation-{index:02d}"] = str(error)
        else: raise ProgressError(f"progress mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "vectors": len(base["witness"]["execution_vectors"]),
            "rejected": rejected}


def check() -> dict[str, Any]:
    value = load(RECEIPT); audit(value)
    for key in ("progress_PRG", "progress_ELF", "extra_lowram_preload"):
        row = value["identity"][key]
        require(bind(ROOT / row["path"]) == row, f"progress artifact drift: {key}")
    require(bind(DEPLOY) == value["deployment"], "progress deployment drift")
    helper = HELPER_BIN.read_bytes(); state = STATE_BIN.read_bytes()
    require(helper == helper_bytes() and state == STATE_RESET
            and PRELOAD_BIN.read_bytes() == helper + state,
            "progress helper/state artifact drift")
    require(helper_execution_vectors(helper) ==
            value["witness"]["execution_vectors"],
            "progress execution-vector receipt drift")
    return {"status": "PASS", "mutations": 30,
            "helper_bytes": len(helper), "state_bytes": len(state),
            "recontact_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "write":
        if OUT.exists(): shutil.rmtree(OUT)
        value = build(); write_json(RECEIPT, value)
        result = {"status": "WRITTEN", "helper_bytes": HELPER_BYTES,
                  "state_bytes": STATE_BYTES}
    elif args.action == "selftest": result = selftest()
    else: result = check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (ProgressError, OSError, ValueError, KeyError, IndexError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT VM PROGRESS FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
