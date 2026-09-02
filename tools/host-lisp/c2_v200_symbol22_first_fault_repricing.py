#!/usr/bin/env python3
"""Re-price the v2.0 `$22` first-fault latch after raw-owner discovery.

This successor is host-only.  It assembles and executes one relocatable target
micro-object, but performs no WPLTO, product link, media build or device work.
"""

from __future__ import annotations

import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from cpu6502 import CPU  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v200_symbol22_first_fault_pricing as OLD  # noqa: E402
import c2_v200_symbol22_first_fault_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
REGISTER = ROOT / "docs/reference/gate-and-tool-register.md"
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-repricing-report.md"
RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-repricing-receipt.json"
OLD_PRICE = ARCH / "c2.3-v2.0-symbol22-first-fault-pricing-receipt.json"
OWNER_RED = ARCH / "c2.3-v2.0-symbol22-first-fault-product-card-r1-owner-red.json"
RELEASE_ELF = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
RELEASE_PRG = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg")
RELEASE_PROFILE = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/resolved-profile.txt")
SEED_ELF = ROOT / (
    "build/c2.3/v2.0-symbol22-first-fault-product-card-r1/wplto/"
    "resident-island-seed.prg.elf")
SEED_PROFILE = SEED_ELF.parent / "resolved-profile.txt"
FULL_MAP = ROOT / "config/c2-full-map-ownership-contract.json"
STATE_OWNERSHIP = ROOT / "config/c2-state-ownership-contract.json"
BUILD = ROOT / "build/phase0-symbol22-first-fault-repricing"
ASM = BUILD / "symbol22-first-fault-split-latch.s"
OBJ = BUILD / "symbol22-first-fault-split-latch.o"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
AUTHORIZATION = "8cc0161d3bdbbe5c9a1b41fc75dfb4464fe2d57b"
EVIDENCE_ERA = "af2377d1b4d1d19f1a2573981c3f573345213e3b"
AUTHORIZATION_HEADER = (
    "## Reviewer disposition — phase-0 double occupancy — 2026-08-31")
FORMAT = "lisp65-c2.3-v200-symbol22-first-fault-repricing-v1"
STATUS = "PASS: DISJOINT SPLIT LATCH PRICED; PRODUCT CARD REQUIRED"
CODE_SECTION = ".lisp65_symbol22_first_fault_latch"
STATE_SECTION = ".lisp65_symbol22_first_fault_state"
PAYLOAD_BYTES = 34
STATE_BYTES = 5
TAG = 0xA5
ERROR = 0x22


ASM_SOURCE = '''\
\t.section .lisp65_symbol22_first_fault_state,"aw",@progbits
\t.globl lisp65_symbol22_latch_state
\t.type lisp65_symbol22_latch_state,@object
lisp65_symbol22_latch_state:
\t.byte 0, 0, 0, 0, 0
\t.size lisp65_symbol22_latch_state, .-lisp65_symbol22_latch_state

\t.section .lisp65_symbol22_first_fault_latch,"ax",@progbits
\t.globl lisp65_symbol22_latch_capture
\t.globl c2_symbol22_repl_buf
\t.type lisp65_symbol22_latch_capture,@function
lisp65_symbol22_latch_capture:
\tlda lisp65_symbol22_latch_state
\tbne .Llatch_return
\ttsx
\tlda $0107,x
\tsta lisp65_symbol22_latch_state+1
\tlda $0108,x
\tsta lisp65_symbol22_latch_state+2
\tlda $16
\tsta lisp65_symbol22_latch_state+3
\tlda $17
\tsta lisp65_symbol22_latch_state+4
\tldy #0
.Llatch_copy:
\tlda ($16),y
\tsta c2_symbol22_repl_buf,y
\tbeq .Llatch_commit
\tiny
\tcpy #$22
\tbne .Llatch_copy
.Llatch_commit:
\tlda #$a5
\tsta lisp65_symbol22_latch_state
.Llatch_return:
\trts
\t.size lisp65_symbol22_latch_capture, .-lisp65_symbol22_latch_capture
'''


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def sealed_bind(commit: str, path: Path) -> dict[str, Any]:
    """Bind an immutable receipt input in the commit that sealed its claim."""
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw), "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    completed = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(completed.returncode == 0,
            f"{label} failed ({completed.returncode}):\n{completed.stdout}")
    return completed.stdout


def authorization() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(AUTHORIZATION_HEADER) == 1,
            "repricing authorization section drift")
    section = AUTHORIZATION_HEADER + text.split(AUTHORIZATION_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative,
            "section": AUTHORIZATION_HEADER, "bytes": len(payload),
            "sha256": sha(payload)}


def features(path: Path) -> list[str]:
    rows = dict(line.split("=", 1) for line in
                path.read_text(encoding="utf-8").splitlines() if "=" in line)
    return rows["feature_defines"].split(",")


def allocated_owners(truth: ElfTruth, start: int, end: int) -> list[str]:
    return [row.name for row in truth.sections if row.bytes > 0
        and "SHF_ALLOC" in set(row.flags)
        and max(start, row.address) < min(end, row.address + row.bytes)]


def predecessor_geometry() -> dict[str, Any]:
    release = ElfTruth.read(RELEASE_ELF, llvm_readobj=READOBJ)
    seed = ElfTruth.read(SEED_ELF, llvm_readobj=READOBJ)
    handoff = release.section(".lisp65_c2_kernal_handoff")
    host_facade = release.section(".lisp65_c2_host_facade")
    terminal_refs = CARD.raw_interval_references(RELEASE_ELF,
        handoff.address + handoff.bytes, host_facade.address,
        exclude_section="__no_candidate_section__")
    raw_targets = sorted({row["target"] for row in terminal_refs})
    raw_sections = sorted({row["source_section"] for row in terminal_refs})
    raw_start, raw_end = min(raw_targets), max(raw_targets) + 1
    code_start, code_end = raw_end, host_facade.address
    code_candidate_end = code_start + 48
    code_allocated = allocated_owners(release, code_start, code_candidate_end)
    code_raw = CARD.raw_interval_references(RELEASE_ELF, code_start,
        code_candidate_end, exclude_section="__no_candidate_section__")
    full = load(FULL_MAP)
    state_contract = load(STATE_OWNERSHIP)
    owners = full["fixed_simultaneous_live_ledger"]
    former = next(row for row in owners
                  if row["owner"] == "former-noinit-named-gap")
    alignment = next(row for row in owners
                     if row["owner"] == "heap-alignment-gap")
    fixed = release.section(".lisp65_c2_fixed_bank0_hot_bss")
    ordinary_bss = release.section(".bss")
    noinit = release.section(".noinit")
    overlay = release.symbol("__lisp65_workbench_runtime_overlay_vma_param")
    state_start = int(former["start"], 0)
    heap_start = int(alignment["end_exclusive"], 0)
    state_end = state_start + STATE_BYTES
    state_allocated = allocated_owners(release, state_start, state_end)
    state_raw = CARD.raw_interval_references(RELEASE_ELF, state_start,
        state_end, exclude_section="__no_candidate_section__")
    raw_prg = RELEASE_PRG.read_bytes()
    load_at = int.from_bytes(raw_prg[:2], "little")
    code_file = 2 + code_start - load_at
    code_gap = raw_prg[code_file:code_file + code_end - code_start]
    text = release.section(".text")
    mapped_facade = release.section(".lisp65_c2_mapped_far_facade")
    far = release.section(".lisp65_c2_mapped_far_service")
    cold = release.section(".lisp65_c2_mapped_product_cold")
    repl = release.symbol("repl.buf")
    release_features = features(RELEASE_PROFILE)
    seed_features = features(SEED_PROFILE)
    seed_ownership = CARD.composed_gap_ownership(SEED_ELF, SEED_PROFILE)
    mapped_physical = sorted(
        (int(row["physical_start"], 0),
         int(row["owner_physical_end_exclusive"], 0), row["owner"])
        for row in owners if "physical_start" in row)
    expected_terminal_sections = [
        ".lisp65_rt_c2append_header",
        ".lisp65_rt_c2append_publish_clear",
        ".lisp65_rt_c2append_publish_plan_resolve",
        ".lisp65_rt_c2append_publish_plan_scan",
    ]
    require((handoff.address + handoff.bytes, host_facade.address) ==
                (0xB582, 0xB5C4)
            and len(terminal_refs) == 64
            and raw_targets == list(range(0xB582, 0xB592))
            and raw_sections == expected_terminal_sections
            and (raw_start, raw_end, code_start, code_end) ==
                (0xB582, 0xB592, 0xB592, 0xB5C4)
            and not code_allocated and not code_raw
            and code_gap == bytes(50),
            "derived post-guard code interval is not owner-free")
    require((int(former["start"], 0), int(former["end_exclusive"], 0),
             int(alignment["start"], 0), heap_start) ==
                (0xC34D, 0xC353, 0xC353, 0xC354)
            and (fixed.address + fixed.bytes, noinit.address, noinit.bytes,
                 overlay.value) == (0xC34D, 0xC34D, 0, 0xC356)
            and not state_allocated and not state_raw
            and ordinary_bss.address + ordinary_bss.bytes < state_start
            and all(not (start <= state_start < end)
                    for start, end, _owner in mapped_physical)
            and state_contract["arena_skeleton"]["deliberate_bank0_gaps"][-1]
                == {"start": "0xc34d", "end_exclusive": "0xc354", "bytes": 7},
            "five-byte state interval is not named predecessor capacity")
    require(release_features.count(PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1
            and PRODUCT.SYMBOL22_LATCH_FEATURE not in release_features
            and seed_features.count(PRODUCT.TERMINAL_RETURN_GUARD_FEATURE) == 1
            and seed_features.count(PRODUCT.SYMBOL22_LATCH_FEATURE) == 1
            and PRODUCT.REFILL_WITNESS_FEATURE not in release_features
            and seed_ownership["logical_owners"] == [CARD.SECTION,
                "raw-fixed-address-terminal-return-guard"],
            "active/inactive claimant proof drift")
    return {
        "release": {"ELF": bind(RELEASE_ELF), "PRG": bind(RELEASE_PRG),
                    "profile": bind(RELEASE_PROFILE)},
        "code_interval": {"start": code_start, "end_exclusive": code_end,
            "bytes": code_end - code_start, "candidate_end": code_candidate_end,
            "candidate_bytes": 48, "residual_bytes": code_end-code_candidate_end,
            "allocated_claimants": code_allocated,
            "fixed_raw_claimants": code_raw,
            "packed_initial_hex": code_gap.hex()},
        "terminal_return_guard": {"active": True,
            "feature": PRODUCT.TERMINAL_RETURN_GUARD_FEATURE,
            "raw_interval": [raw_start, raw_end],
            "data_references": len(terminal_refs),
            "emitted_sections": raw_sections,
            "disjoint_from_candidate": raw_end == code_start},
        "state_interval": {"start": state_start, "end_exclusive": heap_start,
            "bytes": heap_start-state_start, "candidate_end": state_end,
            "candidate_bytes": STATE_BYTES,
            "residual_bytes": heap_start-state_end,
            "predecessor_capacity_owners": [former["owner"], alignment["owner"]],
            "allocated_claimants": state_allocated,
            "fixed_raw_claimants": state_raw,
            "initialization": "candidate packed PROGBITS zeros"},
        "boundaries": {"fixed_hot_end": fixed.address + fixed.bytes,
            "ordinary_bss_end": ordinary_bss.address + ordinary_bss.bytes,
            "ordinary_noinit": [noinit.address, noinit.address + noinit.bytes],
            "heap_boundary": heap_start, "runtime_overlay_start": overlay.value,
            "runtime_overlay_max_end": overlay.value + 0x700},
        "payload": {"owner": "repl.buf", "address": repl.value,
            "capacity_bytes": repl.bytes, "candidate_interval": [repl.value,
                repl.value + PAYLOAD_BYTES], "new_allocation_bytes": 0,
            "temporal_handoff": "fault capture until stopped read; no new input"},
        "ordinary_text_projection": {"predecessor_end": text.address+text.bytes,
            "fault_edge_delta_bytes": 3,
            "projected_facade_VMA": mapped_facade.address + 3,
            "facade_bytes": mapped_facade.bytes,
            "projected_next_owner_reserve_bytes":
                handoff.address - (mapped_facade.address + 3 + mapped_facade.bytes),
            "ordinary_text_floor_bytes": 32,
            "authority": "projection-only; final LTO must derive"},
        "mapped_alternatives": {
            "far_service": {"demand_bytes": far.bytes,
                "capacity_bytes": 1499, "free_bytes": 1499-far.bytes},
            "product_cold": {"demand_bytes": cold.bytes,
                "capacity_bytes": 371, "free_bytes": 371-cold.bytes,
                "VMA_end": cold.address+cold.bytes, "VMA_limit": 0x8000}},
        "claimant_classes": [
            {"class": "SHF_ALLOC sections", "candidate_conflicts": 0},
            {"class": "fixed raw data accessors", "candidate_conflicts": 0,
             "active_adjacent_owner": "terminal-return guard"},
            {"class": "zero-size and named-capacity contracts",
             "candidate_conflicts": 0,
             "successor_action": "five bytes of former-noinit gap become state owner"},
            {"class": "range writers/wipers", "candidate_conflicts": 0,
             "facts": [f"BSS wipe ends at {ordinary_bss.address + ordinary_bss.bytes:04X}",
                       f"runtime-overlay wipe begins at {overlay.value:04X}"]},
            {"class": "mapping-domain aliases", "candidate_conflicts": 0,
             "domain": "baseline physical Bank-0, VMA=LMA",
             "mapped_physical_intervals": [
                 {"start": start, "end_exclusive": end, "owner": owner}
                 for start, end, owner in mapped_physical]},
            {"class": "loader initialization", "candidate_conflicts": 0,
             "handoff": "candidate state is five emitted PROGBITS zero bytes"},
            {"class": "temporal scratch owner", "candidate_conflicts": 0,
             "owner": "repl.buf", "cutpoint": "before further input"},
        ],
        "inactive_claims_proven": {
            PRODUCT.SYMBOL22_LATCH_FEATURE: "absent in release; selected by successor",
            PRODUCT.REFILL_WITNESS_FEATURE: "absent in release and seed profiles",
            PRODUCT.TERMINAL_RETURN_GUARD_FEATURE: "ACTIVE, enumerated, retained",
        },
        "rejected_seed": {"ELF": bind(SEED_ELF), "profile": bind(SEED_PROFILE),
            "logical_owners": seed_ownership["logical_owners"]}}


def compile_candidate() -> tuple[dict[str, Any], ElfTruth]:
    BUILD.mkdir(parents=True, exist_ok=True)
    ASM.write_text(ASM_SOURCE, encoding="utf-8")
    run([str(CC), "-c", "-mcpu=mos45gs02", str(ASM), "-o", str(OBJ)],
        "split-latch target assembly")
    truth = ElfTruth.read(OBJ, llvm_readobj=READOBJ, include_section_data=True)
    code = truth.section(CODE_SECTION)
    state = truth.section(STATE_SECTION)
    helper = truth.symbol("lisp65_symbol22_latch_capture")
    state_symbol = truth.symbol("lisp65_symbol22_latch_state")
    relocations = [row for row in truth.relocations
                   if row.source_section == CODE_SECTION]
    targets = Counter(row.target for row in relocations)
    addends = {target: sorted(row.addend for row in relocations
                              if row.target == target) for target in targets}
    disasm = run([str(OBJDUMP), "-dr", str(OBJ)], "split-latch disassembly")
    require((code.bytes, state.bytes, helper.bytes, state_symbol.bytes) ==
                (48, 5, 48, 5)
            and targets == Counter({"lisp65_symbol22_latch_state": 6,
                                    "c2_symbol22_repl_buf": 1})
            and addends == {"lisp65_symbol22_latch_state": [0, 0, 1, 2, 3, 4],
                            "c2_symbol22_repl_buf": [0]}
            and "lisp_abort_code" not in disasm
            and "rts" in disasm and "cpy\t#$22" in disasm,
            "split-latch micro-object geometry or semantics drift")
    return ({"object": bind(OBJ), "code_section": CODE_SECTION,
        "code_bytes": code.bytes, "state_section": STATE_SECTION,
        "state_bytes": state.bytes, "total_materialized_bytes": code.bytes+state.bytes,
        "relocations": [{"offset": row.offset,
            "kind": row.relocation_type,
            "target": row.target, "addend": row.addend} for row in relocations],
        "relocation_targets": dict(targets),
        "failure_edge": {"helper_returns": True,
            "then_existing_abort": "lisp_abort_static($22)",
            "projected_text_delta_bytes": 3},
        "record": {"state": ["commit_tag", "caller_low", "caller_high",
            "name_pointer_low", "name_pointer_high"],
            "payload_bytes": PAYLOAD_BYTES, "NUL_stopped": True,
            "second_fault_preserves_first": True}}, truth)


def relocated_code(truth: ElfTruth, code_address: int, state_address: int,
                   payload_address: int) -> bytes:
    raw = bytearray(truth.section_bytes(CODE_SECTION))
    targets = {"lisp65_symbol22_latch_state": state_address,
               "c2_symbol22_repl_buf": payload_address}
    for row in truth.relocations:
        if row.source_section != CODE_SECTION:
            continue
        require(row.relocation_type == "R_MOS_ADDR16" and row.target in targets,
                f"unsupported micro relocation: {row}")
        value = targets[row.target] + row.addend
        raw[row.offset:row.offset+2] = value.to_bytes(2, "little")
    return bytes(raw)


def execute_positive_control(truth: ElfTruth, geometry: dict[str, Any]) -> dict[str, Any]:
    code_address = geometry["code_interval"]["start"]
    state_address = geometry["state_interval"]["start"]
    payload_address = geometry["payload"]["address"]
    code = relocated_code(truth, code_address, state_address, payload_address)

    def machine_for(name: bytes, caller: int, pointer: int) -> tuple[CPU, int]:
        machine = CPU()
        machine.mem[code_address:code_address+len(code)] = code
        machine.mem[state_address:state_address+STATE_BYTES] = bytes(STATE_BYTES)
        machine.mem[pointer:pointer+len(name)] = name
        machine.mem[0x16] = pointer & 0xFF
        machine.mem[0x17] = pointer >> 8
        machine.SP = 0xE0
        sentinel = 0x4000
        return_word = sentinel - 1
        machine.mem[0x01E1] = return_word & 0xFF
        machine.mem[0x01E2] = return_word >> 8
        machine.mem[0x01E7] = caller & 0xFF
        machine.mem[0x01E8] = caller >> 8
        machine.PC = code_address
        return machine, sentinel

    caller, pointer = 0x4567, 0x0600
    full_name = b"abcdefghijklmnopqrstuvwxyzabcdefgh"
    machine, sentinel = machine_for(full_name, caller, pointer)
    steps = 0
    while machine.PC != sentinel and steps < 1000:
        machine.step(); steps += 1
    state = bytes(machine.mem[state_address:state_address+STATE_BYTES])
    payload = bytes(machine.mem[payload_address:payload_address+PAYLOAD_BYTES])
    require(machine.PC == sentinel
            and state == bytes((TAG, 0x67, 0x45, 0x00, 0x06))
            and payload == full_name,
            "executed full-name positive control did not commit complete record")
    first = state + payload
    later = b"later\0"
    machine.mem[0x0700:0x0700+len(later)] = later
    machine.mem[0x16:0x18] = bytes((0x00, 0x07))
    machine.SP = 0xE0
    machine.mem[0x01E1] = (sentinel - 1) & 0xFF
    machine.mem[0x01E2] = (sentinel - 1) >> 8
    machine.PC = code_address
    second_steps = 0
    while machine.PC != sentinel and second_steps < 20:
        machine.step(); second_steps += 1
    second = (bytes(machine.mem[state_address:state_address+STATE_BYTES])
              + bytes(machine.mem[payload_address:payload_address+PAYLOAD_BYTES]))
    require(second == first, "second fault overwrote first-fault record")
    short_machine, short_sentinel = machine_for(b"abc\0poison", 0x1234, 0x0700)
    short_steps = 0
    while short_machine.PC != short_sentinel and short_steps < 1000:
        short_machine.step(); short_steps += 1
    short_payload = bytes(short_machine.mem[payload_address:
                                            payload_address+PAYLOAD_BYTES])
    require(short_payload[:4] == b"abc\0" and not any(short_payload[4:]),
            "executed NUL-stop positive control crossed terminator")
    return {"status": "PASS: RELOCATED TARGET MICRO EXECUTED",
        "code_address": code_address, "state_address": state_address,
        "payload_address": payload_address, "steps_to_return": steps,
        "record_hex": first.hex(), "full_34_bytes_preserved": True,
        "short_name_stops_at_NUL": True,
        "second_fault_preserves_first": True,
        "final_product_positive_control_still_required": True}


def alternatives(geometry: dict[str, Any]) -> list[dict[str, Any]]:
    mapped = geometry["mapped_alternatives"]
    return [
        {"name": "split ordinary Bank-0 code/state", "selected": True,
         "cost": {"code_bytes": 48, "packed_state_bytes": 5,
                  "new_BSS_bytes": 0, "projected_text_edge_bytes": 3},
         "loss": "none; caller, pointer and all 34 NUL-stopped bytes retained"},
        {"name": "co-located original handoff-gap latch", "selected": False,
         "cost": {"bytes": 57, "logical_owners": 2},
         "loss": "terminal-return guard would overwrite state and code"},
        {"name": "mapped Far-Service body", "selected": False,
         "cost": {"body_bytes": 48,
                  "available_bytes": mapped["far_service"]["free_bytes"],
                  "shortfall_bytes": 48-mapped["far_service"]["free_bytes"],
                  "additional": "MAP entry/exit and call stub"},
         "loss": "requires arena/transport work and a nesting proof at the fault edge"},
        {"name": "mapped Product-Cold body", "selected": False,
         "cost": {"body_bytes": 48,
                  "available_bytes": mapped["product_cold"]["free_bytes"],
                  "shortfall_bytes": 48-mapped["product_cold"]["free_bytes"]},
         "loss": "misses the $8000 VMA boundary by one byte before entry freight"},
        {"name": "Bank-2 payload carrier", "selected": False,
         "cost": {"new_payload_bytes": 34,
                  "writes_per_full_fault": 34,
                  "existing_payload_allocation_bytes": 0},
         "loss": "adds MAP-dependent stopped-read state and does not place the helper"},
        {"name": "state smaller than five bytes", "selected": False,
         "cost": {"minimum_bytes": 5},
         "loss": "loses atomic commit, caller or name pointer; inadmissible"},
        {"name": "put helper in ordinary .text", "selected": False,
         "cost": {"helper_plus_edge_bytes": 51,
                  "projected_next_owner_reserve_bytes": 50},
         "loss": "larger facade/LMA/relocation movement than the disjoint fixed-code gap"},
    ]


def validate(value: dict[str, Any]) -> None:
    geometry = value["geometry"]
    candidate = value["candidate"]
    control = value["positive_control"]
    selected = [row for row in value["alternatives"] if row["selected"]]
    require(value["status"] == STATUS and len(selected) == 1
            and selected[0]["name"] == "split ordinary Bank-0 code/state",
            "repricing did not select exactly one winner")
    require(geometry["terminal_return_guard"]["active"] is True
            and geometry["terminal_return_guard"]["disjoint_from_candidate"]
            and geometry["terminal_return_guard"]["data_references"] == 64,
            "active terminal guard was hidden or overlapped")
    require(geometry["code_interval"]["bytes"] == 50
            and geometry["code_interval"]["candidate_bytes"] == 48
            and geometry["code_interval"]["residual_bytes"] == 2
            and not geometry["code_interval"]["allocated_claimants"]
            and not geometry["code_interval"]["fixed_raw_claimants"],
            "code interval is not genuinely disjoint")
    require(geometry["state_interval"]["bytes"] == 7
            and geometry["state_interval"]["candidate_bytes"] == 5
            and geometry["state_interval"]["residual_bytes"] == 2
            and not geometry["state_interval"]["allocated_claimants"]
            and not geometry["state_interval"]["fixed_raw_claimants"],
            "state interval is not genuinely disjoint")
    require(len(geometry["claimant_classes"]) == 7
            and all(row["candidate_conflicts"] == 0
                    for row in geometry["claimant_classes"])
            and geometry["inactive_claims_proven"][
                PRODUCT.TERMINAL_RETURN_GUARD_FEATURE].startswith("ACTIVE"),
            "claimant population or inactivity proof was weakened")
    require((candidate["code_bytes"], candidate["state_bytes"],
             candidate["record"]["payload_bytes"]) == (48, 5, 34)
            and candidate["record"]["NUL_stopped"]
            and candidate["record"]["second_fault_preserves_first"],
            "discriminating record or exact freight was weakened")
    require(control["status"] == "PASS: RELOCATED TARGET MICRO EXECUTED"
            and control["full_34_bytes_preserved"]
            and control["short_name_stops_at_NUL"]
            and control["second_fault_preserves_first"],
            "host-positive control is not sharp")
    require(value["final_card_obligations"] == [
        "derive both intervals and every claimant class from the final candidate",
        "prove the packed five-byte state origin is zero",
        "execute the positive control on the final ELF",
        "prove state and repl.buf payload survive longjmp, cleanup and wipe",
        "prove the successful intern path is byte-identical",
        "prove the helper returns directly into the existing $22 abort edge",
        "rerun all standing composition, MAP and capacity walls",
    ], "final-card obligations drift")
    require(value["verification"] == {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0,
            "product_source_edits": 0},
            "host-only repricing crossed its authority")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "assume-terminal-guard-inactive": lambda x: x["geometry"][
            "terminal_return_guard"].update(active=False),
        "omit-fixed-raw-claimants": lambda x: x["geometry"][
            "terminal_return_guard"].update(data_references=0),
        "omit-range-writer-claimant-class": lambda x: x["geometry"][
            "claimant_classes"].pop(3),
        "code-overlaps-host-facade": lambda x: x["geometry"][
            "code_interval"].update(candidate_bytes=51),
        "state-crosses-heap-boundary": lambda x: x["geometry"][
            "state_interval"].update(candidate_bytes=8),
        "payload-only-33-bytes": lambda x: x["candidate"]["record"].update(
            payload_bytes=33),
        "state-only-four-bytes": lambda x: x["candidate"].update(state_bytes=4),
        "copy-ignores-NUL": lambda x: x["candidate"]["record"].update(
            NUL_stopped=False),
        "second-fault-overwrites": lambda x: x["positive_control"].update(
            second_fault_preserves_first=False),
        "mapped-shortfall-selected": lambda x: (
            x["alternatives"][0].update(selected=False),
            x["alternatives"][2].update(selected=True)),
        "final-positive-control-removed": lambda x: x[
            "final_card_obligations"].remove(
                "execute the positive control on the final ELF"),
        "survival-proof-removed": lambda x: x[
            "final_card_obligations"].remove(
                "prove state and repl.buf payload survive longjmp, cleanup and wipe"),
        "product-link-spent-during-price": lambda x: x["verification"].update(
            product_links=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "repricing mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    old = load(OLD_PRICE)
    red = load(OWNER_RED)
    require(old["status"] == OLD.STATUS
            and red["status"] == "SECOND RED: ACTIVE RAW OWNER OVERLAPS LATCH"
            and red["accounting"]["seed_WPLTO"] == 1
            and red["accounting"]["product_closure_links"] == 0,
            "repricing predecessor authority drift")
    geometry = predecessor_geometry()
    candidate, truth = compile_candidate()
    positive = execute_positive_control(truth, geometry)
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS,
        "authority": {"review_authorization": authorization(),
            "original_price": bind(OLD_PRICE), "owner_red": bind(OWNER_RED)},
        "inputs": {"driver": sealed_bind(EVIDENCE_ERA, Path(__file__).resolve()),
            "full_map_contract": bind(FULL_MAP),
            "state_ownership_contract": bind(STATE_OWNERSHIP),
            "gate_register": sealed_bind(EVIDENCE_ERA, REGISTER)},
        "geometry": geometry, "candidate": candidate,
        "positive_control": positive, "alternatives": alternatives(geometry),
        "selection": {"name": "split ordinary Bank-0 code/state",
            "code": "48 bytes at derived terminal-guard raw end",
            "state": "5 packed zero bytes after empty .noinit",
            "payload": "unchanged 34-byte NUL-stopped repl.buf alias",
            "reason": ("preserves every discriminating byte, adds no BSS/name/MAP "
                       "freight, and leaves two bytes in each destination interval")},
        "final_card_obligations": [
            "derive both intervals and every claimant class from the final candidate",
            "prove the packed five-byte state origin is zero",
            "execute the positive control on the final ELF",
            "prove state and repl.buf payload survive longjmp, cleanup and wipe",
            "prove the successful intern path is byte-identical",
            "prove the helper returns directly into the existing $22 abort edge",
            "rerun all standing composition, MAP and capacity walls",
        ],
        "budget": {"prior_seed_WPLTOs": 1,
            "prior_product_closure_links": 0,
            "new_WPLTOs_authorized": 0, "new_product_links_authorized": 0},
        "verification": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0,
            "product_source_edits": 0},
        "claim_limit": ("Host-only successor price. No product implementation, "
            "final-LTO identity, media, device, Comfort or Block-3 claim.")}
    validate(value)
    value["verification"]["mutations_rejected"] = mutations(value)
    return value


def report(value: dict[str, Any]) -> str:
    geometry = value["geometry"]
    candidate = value["candidate"]
    alternatives_rows = "\n".join(
        f"| {row['name']} | {'**yes**' if row['selected'] else 'no'} | "
        f"`{json.dumps(row['cost'], sort_keys=True)}` | {row['loss']} |"
        for row in value["alternatives"])
    return f'''# v2.0 Phase 0 — `$22` first-fault latch re-pricing

Status: **{value['status']}**

## One winner

Keep the active terminal-return guard and split the diagnostic freight across
two derived, baseline Bank-0 intervals:

- the guard's 64 final-byte data references end at `$B592`; the **48-byte**
  capture helper occupies `$B592..$B5C1`, leaving **2 bytes** before the host
  facade at `$B5C4`;
- the empty ordinary `.noinit` owner ends at `$C34D`; a **5-byte packed-zero**
  state occupies `$C34D..$C351`, leaving **2 bytes** before the heap boundary
  at `$C354`;
- the full **34-byte, NUL-stopped payload** remains in the zero-allocation
  `repl.buf` alias.  Caller, name pointer, atomic tag and payload are unchanged.

The helper now returns to the existing `$22` abort edge instead of carrying
its own abort tail.  That reduces it from 52 to 48 bytes while preserving the
record.  The failure-edge text projection is +3 bytes; the mapped facade still
derives from final text and is projected to retain **{geometry['ordinary_text_projection']['projected_next_owner_reserve_bytes']} bytes** before the handoff.  This is a price, not a final-LTO claim.

The relocated target micro-object executed both positive controls: a complete
34-byte name committed caller and pointer, an early NUL stopped the copy, and
a second fault preserved the first record.  The final product must execute the
same control again and prove both carriers survive `longjmp`, cleanup and wipe.

## Ownership enumeration

The round enumerates seven claimant classes: allocated ELF sections, fixed raw
data references, zero-size/named-capacity contracts, range writers and wipes,
mapping-domain aliases, loader initialization, and temporal scratch ownership.
The terminal guard is explicitly **active**, not inferred inactive.  The
refill witness is proven absent from both live profiles.  Both destination
intervals have zero allocated or raw-access conflicts before successor
ownership is applied.

## Alternatives

| Form | Selected | Cost | What it loses |
|---|---:|---|---|
{alternatives_rows}

The state cannot shrink below five bytes without losing atomic commit, caller
or name pointer.  Moving the payload to Bank 2 spends 34 new bytes and does not
place the helper.  Far-Service has 11 free bytes; Product-Cold has 47 and misses
the 48-byte helper by one byte before entry freight.  No discriminating content
was traded for placement.

## Permanent rule and next boundary

The gate register now states the rule bought by r1: **ownership includes fixed
raw accesses, not only ELF sections**.  A placement proves every claimant class
and proves inactivity rather than assuming it.  Thirteen mutations reject the
old false-green and every weakening of content, origin, positive control,
survival, capacity or budget.

This round used **0 WPLTO, 0 product links, 0 media builds and 0 device
contacts**.  The frozen r1 seed remains unqualified evidence and was not
resumed.  A new product-card/WPLTO/link budget remains an owner decision after
review of this target.
'''


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in {"record", "check", "selftest"},
            "usage: record|check|selftest")
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
        REPORT.write_text(report(value), encoding="utf-8")
    elif action == "check":
        require(load(RECEIPT) == value, "repricing receipt stale")
        require(REPORT.read_text(encoding="utf-8") == report(value),
                "repricing report stale")
    else:
        require(len(value["verification"]["mutations_rejected"]) == 13,
                "repricing mutation count drift")
    print("v2.0 symbol22 repricing: PASS code=48/50 state=5/7 payload=34 "
          "WPLTO=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 symbol22 repricing: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
