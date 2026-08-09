#!/usr/bin/env python3
"""Bind every hand-written C2 assembler leaf to its actual llvm-mos ABI.

Assembler removes code-generation uncertainty, but it also removes C's type
checking at the call boundary.  This gate therefore treats the complete current
leaf sources as one inventory and enumerates every final-ELF edge into the
CRC leaf as well as the assembler-to-C pointer/length seam.  Relocations
provide edge provenance; disassembly proves the actual register operations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

import c2_crc_codegen_gate as DISASM
import c2_stz_z_dominance_gate as STZ
from elf_truth import ElfTruth, ElfTruthError, Relocation


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
ABI_POLICIES = {
    "c2_kernal_event_poll": {
        "source": ROOT / "src/c2_kernal_window.s",
        "section_token":
            ".section .lisp65_c2_kernal_window.typed_queue_driver",
        "linked": "required",
        "abi": (
            "C->ASM: lisp65_key_event pointer __rc2/__rc3; "
            "boolean result A; Z=0 at every return"),
    },
    "c2_append_journal_prepare_phase": {
        "source": ROOT / "src/c2_journal_prepare_select.s",
        "section_token":
            ".section\t.lisp65_rt_c2append_journal_prepare",
        "linked": "journal-prepare-co-residence-required",
        "abi": (
            "runtime-overlay->ASM: c2_append_state pointer __rc2/__rc3; "
            "result A; ASM tail-jumps to exactly one C body with pointer "
            "unchanged"),
    },
    "c2_append_plan_walk": {
        "source": ROOT / "src/c2_append_plan_walk.s",
        "section_token": ".section\t.lisp65_resident_island",
        "linked": "required-when-C-called",
        "abi": (
            "C->ASM: canonical plan pointer __rc2/__rc3; "
            "context __rc4/__rc5; "
            "result A; ASM->C c2_overlay_call: slot A; "
            "context __rc2/__rc3"),
    },
    "rtov_crc_mem": {
        "source": ROOT / "src/rtov_crc_mem.s",
        "section_token": ".section\t.text.rtov_crc_mem",
        "linked": "required",
        "abi": "C->ASM: pointer __rc2/__rc3; length A/X; result A/X; Z=0",
    },
    "c2_completion_mode_length": {
        "source": ROOT / "src/c2_completion_mode_length.s",
        "section_token": ".section\t.lisp65_rt_c2append_header",
        "linked": "required",
        "abi": (
            "C->ASM: completion mode A; length result A; "
            "PUBLISH=48, ACTIVE/ROLLBACK/CLEAR=64, unknown=0; Z=0"),
    },
    "rtov_dma_submit_wait": {
        "source": ROOT / "src/rtov_dma_completion.s",
        "section_token": ".section\t.text.rtov_dma_submit_wait",
        "linked": "profile-optional",
        "abi": "C->ASM: no arguments; no result; interrupt state restored",
    },
    "vm_boot_overlay_chain_commit": {
        "source": ROOT / "src/c2_boot_chain_commit.s",
        "section_token": ".section .text.vm_boot_overlay_chain_commit",
        "linked": "bank3-chain-required",
        "abi": (
            "ASM->C ov_crc16: pointer __rc2/__rc3; length A/X; "
            "result A/X"),
    },
    "vm_bank3_boot_stage_entry": {
        "source": ROOT / "src/c2_lite_bank3_stage_entry.s",
        "section_token": ".section .lisp65_boot_bank3_stage",
        "linked": "bank3-chain-required",
        "abi": "resident->ASM and ASM->C: no arguments; status in A",
    },
    "lisp65_error_overlay_entry": {
        "source": ROOT / "src/l65e_bcode_ordinal.s",
        "section_token": ".section\t.lisp65_rt_l65e",
        "linked": "required",
        "abi": (
            "runtime-overlay dispatcher->ASM: context pointer "
            "__rc2/__rc3; status A"),
    },
    "l65e_emit_bcode_ordinal": {
        "source": ROOT / "src/l65e_bcode_ordinal.s",
        "section_token": ".section\t.lisp65_rt_l65e",
        "linked": "required",
        "abi": "ASM->ASM: validated BCODE A/X; output through emit; void",
    },
    "lisp65_f011_mount_token_op": {
        "source": ROOT / "src/f011_guarded_write.s",
        "section_token": ".section\t.text.lisp65_f011_mount_token_op",
        "linked": "required-when-C-called",
        "abi": "C->ASM: mode A; boolean result A",
    },
    "lisp65_f011_scratch_buffer": {
        "source": ROOT / "src/f011_guarded_write.s",
        "section_token": ".section\t.text.lisp65_f011_scratch_buffer",
        "linked": "required-when-C-called",
        "abi": "C->ASM: offset A/X; write mode __rc2; boolean result A",
    },
    "lisp65_mod_adjust_tagged": {
        "source": ROOT / "src/mega65_math.s",
        "section_token": ".section\t.text.mega65_math_mod_adjust",
        "linked": "required-when-C-called",
        "abi": "C->ASM: tagged remainder A/X; tagged divisor __rc2/__rc3; result A/X",
    },
    "lisp65_ash_tagged": {
        "source": ROOT / "src/lisp65_ash_tagged.s",
        "section_token": ".section\t.lisp65_resident_island",
        "linked": "required-when-C-called",
        "abi": (
            "C->ASM: tagged value A/X; tagged count __rc2/__rc3; "
            "tagged result A/X; VM_TYPEERROR/NIL on invalid count or "
            "left-shift overflow; Z=0"),
    },
    "vm_c2d_byte": {
        "source": ROOT / "src/vm_c2d_byte.s",
        "section_token":
            ".section\t.lisp65_c2_kernal_window.reopen_gap1",
        "linked": "required-when-C-called",
        "abi": (
            "C->ASM: validated obj argument pointer __rc2/__rc3; "
            "obj result A/X; ASM->C c2_stream_c2d_read: offset A/X, "
            "destination __rc2/__rc3, length __rc4/__rc5; Z=0"),
    },
    "vm_code_load_converged": {
        "source": ROOT / "src/c2_mapped_far_service.s",
        "section_token":
            ".section .lisp65_c2_mapped_far_facade.entries",
        "linked": "required-when-C-called",
        "abi": (
            "C->ASM mapped-far facade: bank A; offset X/__rc2; "
            "length __rc3/__rc4; destination __rc6/__rc7; result A; "
            "facade preserves arguments across MAP, calls the owned far "
            "body, restores the caller map and returns with Z=0"),
    },
    "c2_physical_read_converged": {
        "source": ROOT / "src/c2_mapped_far_service.s",
        "section_token":
            ".section .lisp65_c2_mapped_far_facade.entries",
        "linked": "required-when-C-called",
        "abi": (
            "C->ASM mapped-far facade: physical source A/X/__rc2/__rc3; "
            "destination __rc4/__rc5; length __rc6/__rc7; result A; "
            "facade preserves arguments across MAP, calls the owned far "
            "body, restores the caller map and returns with Z=0"),
    },
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def _source_contract(name: str, text: str, row: dict[str, Any]) -> dict[str, Any]:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    section = " ".join(str(row["section_token"]).split())
    require(any(line.startswith(section) for line in lines)
            and f".globl {name}" in lines
            and f".type {name},@function" in lines
            and any(line.startswith(f".size {name},") for line in lines),
            f"assembler leaf lost named/sized ELF citizenship: {name}")
    return {"source": row["source"].relative_to(ROOT).as_posix(),
            "linked_policy": row["linked"], "abi": row["abi"]}


def _declared_asm_functions(
        texts: dict[Path, str] | None = None) -> dict[str, dict[str, Any]]:
    """Derive the possible leaf set from assembler declarations, never a list.

    The source declaration establishes assembler provenance.  The final ELF
    below decides which declarations exist and which have C callers.  A new
    ``.type ...,@function`` declaration therefore enters the checked universe
    without a gate edit.
    """
    supplied = texts or {
        path: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src").glob("*.s"))
    }
    result: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"^\s*\.type\s+([^,\s]+)\s*,\s*[@%]function\s*$", re.MULTILINE)
    for path, text in supplied.items():
        for match in pattern.finditer(text):
            name = match.group(1)
            # Fixed facade vectors and hardware interrupt entries are
            # intentionally size-less contract intervals, checked by their
            # dedicated gates.  This ABI gate's leaf universe is the regular
            # named+sized STT_FUNC population.
            if not re.search(r"^\s*\.size\s+" + re.escape(name) + r"\s*,",
                             text, re.MULTILINE):
                continue
            require(name not in result,
                    f"assembler function declaration is not unique: {name}")
            result[name] = {"source": path, "text": text}
    require(result, "no assembler function declarations discovered")
    return result


def source_inventory(texts: dict[Path, str] | None = None) -> dict[str, Any]:
    declarations = _declared_asm_functions(texts)
    result: dict[str, Any] = {}
    for name, declaration in declarations.items():
        row = ABI_POLICIES.get(name)
        source = declaration["source"]
        text = declaration["text"]
        lines = [" ".join(line.split()) for line in text.splitlines()]
        require(f".globl {name}" in lines
                and any(line.startswith(f".size {name},") for line in lines),
                f"assembler function lost named/sized ELF citizenship: {name}")
        result[name] = {
            "source": source.relative_to(ROOT).as_posix(),
            "policy": (row["abi"] if row else "derived-if-C-called"),
        }
        if row is not None:
            _source_contract(name, text, row)
    return result


def _body(rows: list[dict[str, Any]], symbol: Any) -> list[dict[str, Any]]:
    return [row for row in rows
            if row["section"] == symbol.section
            and symbol.value <= int(row["address"])
            < symbol.value + symbol.bytes]


def _relocations(truth: ElfTruth, symbol: Any) -> list[Relocation]:
    return [row for row in truth.relocations
            if row.source_section_index == symbol.section_index
            and symbol.value <= row.offset < symbol.value + symbol.bytes]


def _row_at_operand(rows: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    matches = [row for row in rows if int(row["address"]) == offset - 1]
    require(len(matches) == 1,
            f"operand relocation lacks one instruction owner: 0x{offset:x}")
    return matches[0]


def _one(rows: list[Relocation], *, target: str, relocation_type: str,
         offset: int) -> Relocation:
    matches = [row for row in rows if row.target == target
               and row.relocation_type == relocation_type
               and row.offset == offset]
    require(len(matches) == 1,
            f"ABI relocation mismatch: target={target} type={relocation_type} "
            f"offset=0x{offset:x} count={len(matches)}")
    return matches[0]


def _validate_crc_model(model: list[dict[str, str]]) -> None:
    expected = [
        {"opcode": "lda", "target": "pointer", "part": "lo"},
        {"opcode": "sta", "target": "__rc2", "part": "zp"},
        {"opcode": "lda", "target": "pointer", "part": "hi"},
        {"opcode": "sta", "target": "__rc3", "part": "zp"},
        {"opcode": "lda", "target": "length", "part": "lo"},
        {"opcode": "ldx", "target": "length", "part": "hi"},
        {"opcode": "jsr", "target": "ov_crc16", "part": "call"},
    ]
    require(model == expected,
            "ov_crc16 ABI dataflow is not pointer->__rc2/__rc3, "
            "length->A/X")


def _crc_call_gate(truth: ElfTruth, rows: list[dict[str, Any]]) \
        -> dict[str, Any]:
    owner = truth.symbol("vm_boot_overlay_chain_commit")
    body = _body(rows, owner)
    relocs = _relocations(truth, owner)
    calls = [row for row in relocs if row.target == "ov_crc16"
             and row.relocation_type == "R_MOS_ADDR16"]
    require(len(calls) == 1, "commit leaf must call ov_crc16 exactly once")
    call = calls[0]
    base = call.offset
    specs = (
        (base - 12, "__lisp65_workbench_overlay_start",
         "R_MOS_ADDR16_LO", "lda", "pointer", "lo"),
        (base - 10, "__rc2", "R_MOS_ADDR8", "sta", "__rc2", "zp"),
        (base - 8, "__lisp65_workbench_overlay_start",
         "R_MOS_ADDR16_HI", "lda", "pointer", "hi"),
        (base - 6, "__rc3", "R_MOS_ADDR8", "sta", "__rc3", "zp"),
        (base - 4, "__lisp65_workbench_overlay_len",
         "R_MOS_ADDR16_LO", "lda", "length", "lo"),
        (base - 2, "__lisp65_workbench_overlay_len",
         "R_MOS_ADDR16_HI", "ldx", "length", "hi"),
    )
    model: list[dict[str, str]] = []
    bindings: list[dict[str, Any]] = []
    for offset, target, kind, opcode, role, part in specs:
        relocation = _one(relocs, target=target, relocation_type=kind,
                          offset=offset)
        instruction = _row_at_operand(body, offset)
        require(instruction["opcode"] == opcode,
                f"ABI register operation drift at 0x{offset - 1:x}: "
                f"{instruction['opcode']} != {opcode}")
        model.append({"opcode": opcode, "target": role, "part": part})
        bindings.append({"instruction_address": offset - 1,
                         "opcode": opcode, "relocation_offset": offset,
                         "relocation_type": kind, "target": target,
                         "resolved_value": truth.symbol(target).value
                         + relocation.addend})
    call_row = _row_at_operand(body, call.offset)
    require(call_row["opcode"] == "jsr", "ov_crc16 edge is not JSR")
    model.append({"opcode": "jsr", "target": "ov_crc16", "part": "call"})
    _validate_crc_model(model)
    return {
        "status": "passed-pointer-rc2-rc3-length-a-x",
        "owner": {"section": owner.section, "address": owner.value,
                  "bytes": owner.bytes},
        "callee": "ov_crc16",
        "bindings": bindings,
        "call": {"instruction_address": call.offset - 1,
                 "relocation_offset": call.offset},
        "workbench": {
            "vma": truth.symbol("__lisp65_workbench_overlay_start").value,
            "bytes": truth.symbol("__lisp65_workbench_overlay_len").value},
    }


def _instruction_writer(row: dict[str, Any], register: str) -> bool:
    opcode = str(row["opcode"])
    if register == "A":
        return opcode in ("lda", "pla", "txa", "tya", "tza")
    if register == "X":
        return opcode in ("ldx", "plx", "tax")
    if register == "Y":
        return opcode in ("ldy", "ply", "tay")
    raise GateError(f"unknown ABI register: {register}")


def _crc_caller_model(model: dict[str, str]) -> None:
    require(model == {
        "pointer_low": "__rc2",
        "pointer_high": "__rc3",
        "length_low": "A",
        "length_high": "X",
        "edge": "JSR rtov_crc_mem",
    }, "rtov_crc_mem caller is not pointer->__rc2/__rc3, length->A/X")


def _append_plan_caller_model(model: dict[str, str]) -> None:
    require(model == {
        "plan_low": "__rc2", "plan_high": "__rc3",
        "plan_source": "canonical-linked-array",
        "context_low": "__rc4",
        "context_high": "__rc5",
        "edge": "DIRECT c2_facade_append_plan_walk",
    }, "c2 facade caller is not plan->__rc2/__rc3, "
       "context->__rc4/__rc5")


def _owner(truth: ElfTruth, relocation: Relocation) -> Any:
    address = relocation.offset - 1
    matches = [symbol for symbol in truth.symbols
               if symbol.section_index == relocation.source_section_index
               and symbol.bytes > 0
               and symbol.value <= address < symbol.value + symbol.bytes]
    require(matches, f"CRC callsite lacks a sized owner: 0x{address:x}")
    matches.sort(key=lambda symbol: symbol.bytes)
    require(len(matches) == 1 or matches[0].bytes < matches[1].bytes,
            f"CRC callsite owner is ambiguous: 0x{address:x}")
    return matches[0]


def _last_writer(window: list[dict[str, Any]], register: str) \
        -> dict[str, Any]:
    matches = [row for row in window if _instruction_writer(row, register)]
    require(matches, f"CRC callsite lacks a {register} length writer")
    return matches[-1]


def _crc_caller_inventory(truth: ElfTruth,
                          rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_rows = [row for row in truth.relocations
                   if row.target == "rtov_crc_mem"]
    require(target_rows, "final ELF has no rtov_crc_mem callers")
    result: list[dict[str, Any]] = []
    rc2 = truth.symbol("__rc2").value
    rc3 = truth.symbol("__rc3").value
    for relocation in sorted(
            target_rows,
            key=lambda row: (row.source_section_index, row.offset)):
        require(relocation.relocation_type == "R_MOS_ADDR16",
                "rtov_crc_mem has a non-direct relocation edge")
        owner = _owner(truth, relocation)
        body = _body(rows, owner)
        call = _row_at_operand(body, relocation.offset)
        require(call["opcode"] == "jsr",
                f"rtov_crc_mem edge is not JSR: 0x{relocation.offset - 1:x}")
        call_index = body.index(call)
        # Argument setup must occur after the preceding call or unconditional
        # control transfer.  This keeps the proof local to the real call edge
        # without assuming one compiler spelling for loads and transfers.
        start = 0
        for index, row in enumerate(body[:call_index]):
            if row["opcode"] in ("jsr", "jmp", "rts", "bra"):
                start = index + 1
        window = body[start:call_index]
        require(window, "rtov_crc_mem callsite has no local ABI setup")
        pointer_rows: dict[str, dict[str, Any]] = {}
        for name, address in (("__rc2", rc2), ("__rc3", rc3)):
            operand = f"${address:x}"
            matches = [row for row in window
                       if row["opcode"] in ("sta", "stx", "sty")
                       and row["operand"] == operand]
            require(matches,
                    f"CRC callsite lacks a local {name} pointer writer: "
                    f"0x{relocation.offset - 1:x}")
            pointer_rows[name] = matches[-1]
        a_writer = _last_writer(window, "A")
        x_writer = _last_writer(window, "X")
        model = {
            "pointer_low": "__rc2", "pointer_high": "__rc3",
            "length_low": "A", "length_high": "X",
            "edge": "JSR rtov_crc_mem",
        }
        _crc_caller_model(model)
        result.append({
            "owner": owner.name,
            "owner_section": owner.section,
            "call_address": relocation.offset - 1,
            "relocation_offset": relocation.offset,
            "pointer_low_writer": pointer_rows["__rc2"],
            "pointer_high_writer": pointer_rows["__rc3"],
            "length_low_writer": a_writer,
            "length_high_writer": x_writer,
            "model": model,
        })
    return {
        "status": "passed-complete-final-elf-caller-inventory",
        "callsite_count": len(result),
        "direct_jsr_count": len(result),
        "non_jsr_or_unowned_count": 0,
        "callers": result,
        "invariant": (
            "Every final-ELF relocation to rtov_crc_mem is owned, is a direct "
            "JSR, and locally establishes pointer in __rc2/__rc3 plus length "
            "in A/X. No caller class is inferred from the Leaf comment."),
    }


def _append_plan_caller_inventory(
        truth: ElfTruth, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prove the C/facade/ASM/C plan-walker ABI from the final ELF."""
    target_rows = [row for row in truth.relocations
                   if row.target == "c2_facade_append_plan_walk"]
    require(target_rows,
            "final ELF has no c2_facade_append_plan_walk callers")
    rc2 = truth.symbol("__rc2").value
    rc3 = truth.symbol("__rc3").value
    rc4 = truth.symbol("__rc4").value
    rc5 = truth.symbol("__rc5").value
    callers: list[dict[str, Any]] = []
    plan_names: set[str] = set()
    for relocation in sorted(
            target_rows,
            key=lambda row: (row.source_section_index, row.offset)):
        require(relocation.relocation_type == "R_MOS_ADDR16",
                "c2_facade_append_plan_walk has a non-direct relocation edge")
        owner = _owner(truth, relocation)
        body = _body(rows, owner)
        call = _row_at_operand(body, relocation.offset)
        require(call["opcode"] in ("jsr", "jmp")
                and (call["opcode"] != "jmp" or call is body[-1]),
                "append-plan facade edge is neither JSR nor terminal JMP")
        call_index = body.index(call)
        start = 0
        for index, row in enumerate(body[:call_index]):
            if row["opcode"] in ("jsr", "jmp", "rts", "bra"):
                start = index + 1
        window = body[start:call_index]
        require(window, "plan-walker callsite has no local ABI setup")
        context_writers: dict[str, dict[str, Any]] = {}
        for name, address in (("__rc4", rc4), ("__rc5", rc5)):
            matches = [row for row in window
                       if row["opcode"] in ("sta", "stx", "sty")
                       and row["operand"] == f"${address:x}"]
            require(matches,
                    f"plan-walker callsite lacks local {name} writer: "
                    f"0x{relocation.offset - 1:x}")
            context_writers[name] = matches[-1]
        call_window_addresses = {int(row["address"]) for row in window}
        plan_relocs = [row for row in truth.relocations
                       if row.source_section_index == relocation.source_section_index
                       and row.offset - 1 in call_window_addresses
                       and row.target in (
                           "lisp65_c2_append_stage_plan",
                           "lisp65_c2_append_persistent_publish_plan",
                           "lisp65_c2_append_rollback_plan")]
        require(len(plan_relocs) == 2
                and len({row.target for row in plan_relocs}) == 1,
                "plan-walker caller does not bind one canonical plan pointer")
        plan_name = plan_relocs[0].target
        plan_names.add(plan_name)
        low = [row for row in plan_relocs
               if row.relocation_type == "R_MOS_ADDR16_LO"]
        high = [row for row in plan_relocs
                if row.relocation_type == "R_MOS_ADDR16_HI"]
        require(len(low) == 1 and len(high) == 1,
                "canonical plan pointer lacks structured LO/HI relocations")
        low_writer = _row_at_operand(body, low[0].offset)
        high_writer = _row_at_operand(body, high[0].offset)
        register_abi = {
            "lda": ("A", "sta"),
            "ldx": ("X", "stx"),
            "ldy": ("Y", "sty"),
        }
        plan_stores: list[dict[str, Any]] = []
        for loader, expected_address, label in (
                (low_writer, rc2, "__rc2"),
                (high_writer, rc3, "__rc3")):
            binding = register_abi.get(str(loader["opcode"]))
            require(binding is not None,
                    f"canonical plan {label} relocation is not a register load")
            register, store_opcode = binding
            loader_index = body.index(loader)
            stores = []
            for row in body[loader_index + 1:call_index]:
                if (row["opcode"] == store_opcode
                        and row["operand"] == f"${expected_address:x}"):
                    stores.append(row)
                    break
                if (_instruction_writer(row, register)
                        or row["opcode"] in ("jsr", "jmp", "rts", "bra")):
                    break
            require(stores,
                    f"canonical plan pointer does not reach {label}")
            plan_stores.append(stores[0])
        model = {
            "plan_low": "__rc2", "plan_high": "__rc3",
            "plan_source": "canonical-linked-array", "context_low": "__rc4",
            "context_high": "__rc5",
            "edge": "DIRECT c2_facade_append_plan_walk",
        }
        _append_plan_caller_model(model)
        callers.append({
            "owner": owner.name, "owner_section": owner.section,
            "call_address": relocation.offset - 1, "plan": plan_name,
            "edge_opcode": call["opcode"],
            "context_low_writer": context_writers["__rc4"],
            "context_high_writer": context_writers["__rc5"],
            "plan_low_loader": low_writer,
            "plan_high_loader": high_writer,
            "plan_low_writer": plan_stores[0],
            "plan_high_writer": plan_stores[1],
            "model": model,
        })
    require(plan_names == {
                "lisp65_c2_append_stage_plan",
                "lisp65_c2_append_persistent_publish_plan",
                "lisp65_c2_append_rollback_plan"},
            f"final callers do not cover all named plans: {sorted(plan_names)}")

    facade = truth.symbol("c2_facade_append_plan_walk")
    require(facade.section == ".lisp65_c2_host_facade"
            and facade.value == 0xB5F1,
            "append-plan facade is not the pinned sixteenth vector")
    facade_edges = [row for row in truth.relocations
                    if row.target == "c2_append_plan_walk"]
    require(len(facade_edges) == 1
            and facade_edges[0].source_section_index == facade.section_index
            and facade_edges[0].relocation_type == "R_MOS_ADDR16",
            "append-plan facade is not the sole direct edge to the Leaf")
    facade_rows = [row for row in rows
                   if row["section"] == facade.section
                   and int(row["address"]) == facade_edges[0].offset - 1]
    require(len(facade_rows) == 1 and facade_rows[0]["opcode"] == "jmp",
            "append-plan facade edge is not a direct JMP")

    leaf = truth.symbol("c2_append_plan_walk")
    body = _body(rows, leaf)
    require([(row["opcode"], row["operand"]) for row in body[:8]] == [
        ("ldy", f"${rc4:x}"), ("sty", f"${truth.symbol('__rc6').value:x}"),
        ("ldy", f"${rc5:x}"), ("sty", f"${truth.symbol('__rc7').value:x}"),
        ("ldy", f"${rc2:x}"), ("sty", f"${rc4:x}"),
        ("ldy", f"${rc3:x}"), ("sty", f"${rc5:x}"),
    ], "plan walker does not consume plan __rc2/__rc3 and context "
       "__rc4/__rc5 first")
    outgoing = [row for row in _relocations(truth, leaf)
                if row.target == "c2_overlay_call"]
    require(len(outgoing) == 1
            and outgoing[0].relocation_type == "R_MOS_ADDR16",
            "plan walker lacks one direct append-boundary edge")
    out_call = _row_at_operand(body, outgoing[0].offset)
    require(out_call["opcode"] == "jsr",
            "plan walker append-boundary edge is not JSR")
    out_index = body.index(out_call)
    out_window = body[max(0, out_index - 16):out_index]
    for address, name in ((rc2, "__rc2"), (rc3, "__rc3")):
        require(any(row["opcode"] in ("sta", "stx", "sty")
                    and row["operand"] == f"${address:x}"
                    for row in out_window),
                f"plan walker does not restore context into {name}")
    require(_last_writer(out_window, "A")["opcode"] == "lda",
            "plan walker does not place the actual slot in A")
    return {
        "status": "passed-complete-C-facade-ASM-C-plan-walker-ABI",
        "callsite_count": len(callers),
        "plans": sorted(plan_names),
        "callers": callers,
        "facade": {
            "symbol": facade.name,
            "address": facade.value,
            "section": facade.section,
            "edge_opcode": facade_rows[0]["opcode"],
            "target": leaf.name,
        },
        "outgoing": {
            "callee": "c2_overlay_call",
            "call_address": outgoing[0].offset - 1,
            "context": "restored __rc2/__rc3",
            "slot": "A",
        },
    }


def _validate_policy_coverage(discovered: set[str],
                              policies: set[str]) -> None:
    unknown = sorted(discovered - policies)
    require(not unknown,
            "assembler function with C caller lacks an ABI policy: "
            + ", ".join(unknown))


def _c_called_asm_inventory(truth: ElfTruth) -> dict[str, Any]:
    """Derive every assembler STT_FUNC surface reached from non-ASM code.

    Direct references come from structured ELF relocations.  Runtime-overlay
    entries are indirect, so their ELF contract entry marker at the exact same
    (section, VMA) makes that surface visible without naming the leaf here.
    ABI policies describe how to check a discovered surface; they never define
    which surfaces exist.
    """
    declarations = _declared_asm_functions()
    linked: dict[str, Any] = {}
    for name in declarations:
        matches = truth.symbols_by_name.get(name, [])
        if len(matches) == 1 and matches[0].section not in (
                "Absolute", "Undefined") and matches[0].bytes > 0:
            linked[name] = matches[0]
    direct: dict[str, list[dict[str, Any]]] = {}
    unowned: list[dict[str, Any]] = []
    for relocation in truth.relocations:
        if relocation.target not in linked:
            continue
        try:
            owner = _owner(truth, relocation)
        except GateError:
            unowned.append({"target": relocation.target,
                            "source_section": relocation.source_section,
                            "offset": relocation.offset,
                            "relocation_type": relocation.relocation_type})
            continue
        if owner.name in linked:
            continue
        direct.setdefault(relocation.target, []).append({
            "owner": owner.name, "owner_section": owner.section,
            "relocation_offset": relocation.offset,
            "relocation_type": relocation.relocation_type,
        })
    indirect: dict[str, list[str]] = {}
    for name, symbol in linked.items():
        markers = sorted(row.name for row in truth.symbols
                         if row.name.startswith("__lisp65_rt_")
                         and row.name.endswith("_entry")
                         and row.section_index == symbol.section_index
                         and row.value == symbol.value)
        if markers:
            indirect[name] = markers
    discovered = set(direct) | set(indirect)
    _validate_policy_coverage(discovered, set(ABI_POLICIES))
    return {
        "status": "passed-ELF-derived-C-called-assembler-universe",
        "assembler_function_declarations": len(declarations),
        "linked_sized_assembler_functions": len(linked),
        "C_called_function_count": len(discovered),
        "C_called_functions": sorted(discovered),
        "direct_relocation_edges": direct,
        "indirect_runtime_overlay_entries": indirect,
        "non_function_data_or_vector_references": unowned,
        "unclassified_C_called_functions": [],
    }


def _validate_l65e_entry_model(model: dict[str, str]) -> None:
    require(model == {
        "entry_pointer_low": "read-__rc2",
        "entry_pointer_high": "read-__rc3",
        "dispatcher_pointer_low": "write-__rc2",
        "dispatcher_pointer_high": "write-__rc3",
        "dispatcher_target_low": "write-__rc18",
        "dispatcher_target_high": "write-__rc19",
        "edge": "JSR-__call_indir",
    }, "L65E runtime-overlay entry ABI dataflow drift")


def _l65e_entry_abi_gate(truth: ElfTruth,
                          rows: list[dict[str, Any]]) -> dict[str, Any]:
    entry = truth.symbol("lisp65_error_overlay_entry")
    body = _body(rows, entry)
    rc = {name: truth.symbol(name).value for name in
          ("__rc2", "__rc3", "__rc18", "__rc19")}
    require([(row["opcode"], row["operand"]) for row in body[:2]] ==
            [("lda", f"${rc['__rc2']:x}"),
             ("ora", f"${rc['__rc3']:x}")],
            "L65E entry does not consume context from __rc2/__rc3")
    require(not any(row["opcode"] in ("sta", "stx", "sty", "stz")
                    and row["operand"] in
                    (f"${rc['__rc2']:x}", f"${rc['__rc3']:x}")
                    for row in body[:2]),
            "L65E entry overwrites a context byte before reading it")

    dispatcher = truth.symbol("vm_runtime_overlay_exec_family")
    dispatcher_body = _body(rows, dispatcher)
    calls = sorted((row for row in _relocations(truth, dispatcher)
                    if row.target == "__call_indir"
                    and row.relocation_type == "R_MOS_ADDR16"),
                   key=lambda row: row.offset)
    require(calls, "runtime-overlay dispatcher has no final indirect edge")
    callsites: list[dict[str, Any]] = []
    # The same dispatcher has a per-record execution edge and the final
    # runtime-entry edge.  LTO may keep both.  Neither is a heuristic
    # exception: every final indirect edge must establish the identical
    # target/context ABI, so an added edge enters the proof automatically.
    for call in calls:
        call_address = call.offset - 1
        call_rows = [row for row in dispatcher_body
                     if int(row["address"]) == call_address]
        require(len(call_rows) == 1 and call_rows[0]["opcode"] == "jsr",
                "runtime-overlay final entry edge is not JSR __call_indir")
        call_index = dispatcher_body.index(call_rows[0])
        window = dispatcher_body[max(0, call_index - 16):call_index]
        writers: dict[str, dict[str, Any]] = {}
        for name in ("__rc2", "__rc3", "__rc18", "__rc19"):
            matches = [row for row in window
                       if row["opcode"] in ("sta", "stx", "sty")
                       and row["operand"] == f"${rc[name]:x}"]
            require(matches,
                    f"runtime-overlay edge lacks {name} writer at "
                    f"0x{call_address:x}")
            writers[name] = matches[-1]
        require(int(writers["__rc18"]["address"])
                < int(writers["__rc2"]["address"])
                and int(writers["__rc19"]["address"])
                < int(writers["__rc3"]["address"]) < call_address,
                "runtime-overlay target/context setup order drift")
        callsites.append({"call_address": call_address,
                          "writers": writers})
    model = {
        "entry_pointer_low": "read-__rc2",
        "entry_pointer_high": "read-__rc3",
        "dispatcher_pointer_low": "write-__rc2",
        "dispatcher_pointer_high": "write-__rc3",
        "dispatcher_target_low": "write-__rc18",
        "dispatcher_target_high": "write-__rc19",
        "edge": "JSR-__call_indir",
    }
    _validate_l65e_entry_model(model)
    return {
        "status": "passed-real-dispatcher-context-rc2-rc3-to-ASM-entry",
        "model": model,
        "entry": {"section": entry.section, "address": entry.value,
                  "bytes": entry.bytes,
                  "first_instructions": body[:2]},
        "dispatcher": {"owner": dispatcher.name,
                       "indirect_call_count": len(callsites),
                       "callsites": callsites},
    }


def _validate_journal_tail_z_model(
        model: dict[str, str]) -> None:
    require(set(model) == {
                "c2_append_journal_write_phase",
                "c2_append_rollback_prepare_phase"}
            and all(value in ("ldz-#$0", "ldz-#$00")
                    for value in model.values()),
            "journal-prepare selector tail ABI does not establish Z=0")


def _journal_prepare_selector_abi_gate(
        truth: ElfTruth, rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches = truth.symbols_by_name.get(
        "c2_append_journal_prepare_phase", [])
    if not matches:
        return {"status": "not-required-by-profile"}
    require(len(matches) == 1,
            "journal-prepare selector is not one ELF function")
    leaf = matches[0]
    body = _body(rows, leaf)
    rc2 = truth.symbol("__rc2").value
    rc3 = truth.symbol("__rc3").value
    require(any(row["opcode"] == "lda" and row["operand"] == f"${rc2:x}"
                for row in body)
            and any(row["opcode"] == "ora"
                    and row["operand"] == f"${rc3:x}" for row in body),
            "journal-prepare selector does not consume context __rc2/__rc3")
    immediates = {(row["opcode"], row["operand"]) for row in body}
    require(("ldz", "#$2") in immediates
            and ("ldz", "#$d5") in immediates,
            "journal-prepare selector target-field offsets drift")
    relocs = _relocations(truth, leaf)
    targets = {
        "c2_append_journal_write_phase",
        "c2_append_rollback_prepare_phase",
    }
    edges = [row for row in relocs if row.target in targets]
    require(len(edges) == 2 and {row.target for row in edges} == targets,
            "journal-prepare selector lost its two body edges")
    edge_rows = [_row_at_operand(body, row.offset) for row in edges]
    require(all(row["opcode"] == "jmp" for row in edge_rows)
            and not any(row["opcode"] == "jsr" for row in body),
            "journal-prepare selector bodies are not tail edges")
    z_writers = {"ldz", "inz", "dez", "taz", "plz"}
    tail_z: dict[str, dict[str, Any]] = {}
    for relocation, edge_row in zip(edges, edge_rows):
        edge_index = body.index(edge_row)
        writer = next(
            (row for row in reversed(body[:edge_index])
             if row["opcode"] in z_writers), None)
        require(writer is not None
                and writer["opcode"] == "ldz"
                and writer["operand"] in ("#$0", "#$00"),
                "journal-prepare selector tail edge does not establish Z=0: "
                + relocation.target)
        tail_z[relocation.target] = {
            "writer_address": writer["address"],
            "opcode": writer["opcode"],
            "operand": writer["operand"],
            "edge_address": edge_row["address"],
        }
    _validate_journal_tail_z_model({
        target: f"{row['opcode']}-{row['operand']}"
        for target, row in tail_z.items()
    })
    require(0 < leaf.bytes <= 82,
            "journal-prepare selector exceeds its measured ABI budget")
    return {
        "status": "passed-real-context-ABI-two-total-tail-edges-Z0",
        "section": leaf.section,
        "address": leaf.value,
        "bytes": leaf.bytes,
        "context_registers": ["__rc2", "__rc3"],
        "target_offsets": {"main_ordinal": 2, "journal_result": 213},
        "tail_targets": sorted(targets),
        "tail_C_entry_Z": tail_z,
        "marker_totality": {
            "main_ordinal_classes": 2,
            "marker_values_per_class": 256,
            "cases": 512,
            "accepted": 3,
            "fail_closed": 509,
        },
    }


def _linked_inventory(truth: ElfTruth, rows: list[dict[str, Any]], *,
                      require_bank3_chain: bool) -> dict[str, Any]:
    declarations = _declared_asm_functions()
    result: dict[str, Any] = {}
    for name, declaration in declarations.items():
        matches = truth.symbols_by_name.get(name, [])
        if not matches:
            result[name] = {"status": "not-linked-by-c2-lite-profile",
                            "source": declaration["source"].relative_to(ROOT).as_posix()}
            continue
        require(len(matches) == 1, f"assembler leaf is not unique: {name}")
        symbol = matches[0]
        require(symbol.symbol_type == "Function" and symbol.bytes > 0
                and symbol.section not in ("Absolute", "Undefined"),
                f"assembler leaf is not a sized ELF function: {name}")
        body = _body(rows, symbol)
        require(body, f"assembler leaf has no linked body: {name}")
        result[name] = {"status": "passed-linked-elf-citizen",
                        "source": declaration["source"].relative_to(ROOT).as_posix(),
                        "section": symbol.section, "address": symbol.value,
                        "bytes": symbol.bytes,
                        "terminal_opcode": body[-1]["opcode"]}

    crc = truth.symbol("rtov_crc_mem")
    crc_body = _body(rows, crc)
    rc = {name: truth.symbol(name).value for name in
          ("__rc2", "__rc3", "__rc4", "__rc5")}
    require([(row["opcode"], row["operand"]) for row in crc_body[:6]] ==
            [("ldy", f"${rc['__rc2']:x}"),
             ("sty", f"${rc['__rc4']:x}"),
             ("ldy", f"${rc['__rc3']:x}"),
             ("sty", f"${rc['__rc5']:x}"),
             ("sta", f"${rc['__rc2']:x}"),
             ("stx", f"${rc['__rc3']:x}")],
            "rtov_crc_mem does not consume pointer __rc2/__rc3 and length A/X")
    dec = {row["operand"] for row in crc_body if row["opcode"] == "dec"}
    require({f"${rc['__rc2']:x}", f"${rc['__rc3']:x}"} <= dec,
            "rtov_crc_mem no longer consumes length __rc2/__rc3")

    if require_bank3_chain:
        stage = truth.symbol("vm_bank3_boot_stage_entry")
        targets = {row.target for row in _relocations(truth, stage)
                   if row.relocation_type == "R_MOS_ADDR16"}
        require({"c2_lite_stage_boot_family", "vm_bank3_boot_stage_fail",
                 "vm_boot_overlay_chain_prepare",
                 "vm_boot_overlay_chain_commit"} <= targets,
                "Bank-3 stage leaf call/tail ABI drift")
    return result


def audit_elf(elf: Path, *, out: Path | None = None,
              require_bank3_chain: bool = True) -> dict[str, Any]:
    sources = source_inventory()
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(elf)], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    rows = DISASM.disassembly_rows(completed.stdout)
    linked = _linked_inventory(truth, rows,
                               require_bank3_chain=require_bank3_chain)
    stz_dominance = STZ.audit(linked_inventory=linked)
    derived_callers = _c_called_asm_inventory(truth)
    crc_callers = _crc_caller_inventory(truth, rows)
    append_plan_callers = _append_plan_caller_inventory(truth, rows)
    crc_call = (_crc_call_gate(truth, rows) if require_bank3_chain else
                {"status": "not-required-by-profile"})
    l65e_entry = _l65e_entry_abi_gate(truth, rows)
    journal_prepare = _journal_prepare_selector_abi_gate(truth, rows)
    value = {
        "format": "lisp65-c2-assembler-leaf-abi-dataflow-v3",
        "elf": str(elf),
        "status": "passed-all-assembler-leaf-abi-contracts",
        "source_inventory": sources,
        "handwritten_STZ_Z_dominance": stz_dominance,
        "handwritten_STZ_and_Z_boundary_discipline": stz_dominance,
        "linked_inventory": linked,
        "ELF_derived_C_called_inventory": derived_callers,
        "rtov_crc_mem_callers": crc_callers,
        "c2_append_plan_walk_callers": append_plan_callers,
        "boot_commit_crc_call": crc_call,
        "l65e_runtime_overlay_entry": l65e_entry,
        "journal_prepare_selector": journal_prepare,
        "invariant": (
            "Assembler declarations establish provenance; the final ELF "
            "derives the complete linked C-called leaf set. Every discovered "
            "surface has an ABI policy or the build is red. CRC and the "
            "runtime-overlay L65E entry additionally prove their real caller "
            "register setup from structured relocations and dataflow. Every "
            "handwritten 45GS02 STZ is source-derived and must be dominated "
            "by a proven Z=0 state. Every regular handwritten return and "
            "ASM-to-external edge must likewise carry Z=0; interrupt entries "
            "outside the C-called leaf universe instead prove preservation "
            "of the interrupted Z value."),
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def selftest() -> dict[str, str]:
    texts = {path: path.read_text(encoding="utf-8")
             for path in sorted((ROOT / "src").glob("*.s"))}
    source_inventory(texts)
    rejected: dict[str, str] = {}
    stz = STZ.selftest()
    for name in stz["mutations"]:
        rejected[f"STZ-Z-dominance:{name}"] = "rejected"
    declarations = _declared_asm_functions(texts)
    for name, row in ABI_POLICIES.items():
        mutated = dict(texts)
        path = Path(str(row["source"]))
        lines = mutated[path].splitlines()
        size_index = next(index for index, line in enumerate(lines)
                          if " ".join(line.split()).startswith(
                              f".size {name},"))
        lines[size_index] = lines[size_index].replace(".size", ".nosize", 1)
        mutated[path] = "\n".join(lines)
        try:
            _source_contract(name, mutated[path], row)
        except GateError:
            rejected[f"{name}-unsized"] = "rejected"
        else:
            raise GateError(f"source citizenship mutation survived: {name}")

    _validate_policy_coverage(
        {"rtov_crc_mem", "lisp65_error_overlay_entry"},
        set(ABI_POLICIES))
    try:
        _validate_policy_coverage(
            {"rtov_crc_mem", "future_unregistered_C_leaf"},
            set(ABI_POLICIES))
    except GateError:
        rejected["ELF-derived-new-C-leaf-without-policy"] = "rejected"
    else:
        raise GateError("unregistered ELF-derived C leaf survived")

    l65e = {
        "entry_pointer_low": "read-__rc2",
        "entry_pointer_high": "read-__rc3",
        "dispatcher_pointer_low": "write-__rc2",
        "dispatcher_pointer_high": "write-__rc3",
        "dispatcher_target_low": "write-__rc18",
        "dispatcher_target_high": "write-__rc19",
        "edge": "JSR-__call_indir",
    }
    _validate_l65e_entry_model(l65e)
    for name, key, value in (
            ("l65e-overwrite-context-low", "entry_pointer_low",
             "write-__rc2"),
            ("l65e-overwrite-context-high", "entry_pointer_high",
             "write-__rc3")):
        trial = dict(l65e); trial[key] = value
        try:
            _validate_l65e_entry_model(trial)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"L65E ABI mutation survived: {name}")

    base = [
        {"opcode": "lda", "target": "pointer", "part": "lo"},
        {"opcode": "sta", "target": "__rc2", "part": "zp"},
        {"opcode": "lda", "target": "pointer", "part": "hi"},
        {"opcode": "sta", "target": "__rc3", "part": "zp"},
        {"opcode": "lda", "target": "length", "part": "lo"},
        {"opcode": "ldx", "target": "length", "part": "hi"},
        {"opcode": "jsr", "target": "ov_crc16", "part": "call"},
    ]
    _validate_crc_model(base)
    mutations = {
        "pointer-length-swap": {0: "length", 2: "length",
                                4: "pointer", 5: "pointer"},
        "pointer-low-plus-one": {0: "pointer+1"},
        "pointer-high-plus-one": {2: "pointer+1"},
        "length-low-plus-one": {4: "length+1"},
        "length-high-plus-one": {5: "length+1"},
        "pointer-low-wrong-zp": {1: "__rc3"},
    }
    for name, changes in mutations.items():
        trial = [dict(row) for row in base]
        for index, target in changes.items():
            trial[index]["target"] = target
        try:
            _validate_crc_model(trial)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"ABI mutation survived: {name}")
    caller = {
        "pointer_low": "__rc2", "pointer_high": "__rc3",
        "length_low": "A", "length_high": "X",
        "edge": "JSR rtov_crc_mem",
    }
    _crc_caller_model(caller)
    for name, changes in {
            "rtov-crc-pointer-length-swap": {
                "pointer_low": "A", "pointer_high": "X",
                "length_low": "__rc2", "length_high": "__rc3"},
            "rtov-crc-pointer-low-one-byte-drift": {
                "pointer_low": "__rc3"},
            "rtov-crc-length-high-one-byte-drift": {
                "length_high": "A"},
            "rtov-crc-non-jsr-edge": {"edge": "JMP rtov_crc_mem"},
            }.items():
        trial = dict(caller)
        trial.update(changes)
        try:
            _crc_caller_model(trial)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"CRC caller mutation survived: {name}")
    plan_caller = {
        "plan_low": "__rc2", "plan_high": "__rc3",
        "plan_source": "canonical-linked-array", "context_low": "__rc4",
        "context_high": "__rc5",
        "edge": "DIRECT c2_facade_append_plan_walk",
    }
    _append_plan_caller_model(plan_caller)
    for name, changes in {
            "append-plan-pointer-swapped": {
                "plan_low": "__rc3", "plan_high": "__rc2"},
            "append-plan-private-source": {"plan_source": "private-array"},
            "append-plan-context-low-drift": {"context_low": "__rc5"},
            "append-plan-context-high-drift": {"context_high": "__rc4"},
            "append-plan-indirect-edge": {
                "edge": "INDIRECT c2_facade_append_plan_walk"},
            }.items():
        trial = dict(plan_caller)
        trial.update(changes)
        try:
            _append_plan_caller_model(trial)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"append plan caller mutation survived: {name}")
    journal_tail_z = {
        "c2_append_journal_write_phase": "ldz-#$0",
        "c2_append_rollback_prepare_phase": "ldz-#$0",
    }
    _validate_journal_tail_z_model(journal_tail_z)
    for target in journal_tail_z:
        trial = dict(journal_tail_z)
        trial[target] = "ldz-#$d5"
        try:
            _validate_journal_tail_z_model(trial)
        except GateError:
            rejected[f"{target}-tail-Z-not-zero"] = "rejected"
        else:
            raise GateError(
                f"journal selector tail-Z mutation survived: {target}")
    require(len(rejected) == len(ABI_POLICIES) + 20 + stz["rejected"],
            "assembler ABI mutation count drift")
    return rejected


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-bank3-chain", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            result = selftest()
            print("c2-asm-leaf-abi-gate: SELFTEST PASS mutations="
                  + str(len(result)))
            return 0
        if args.elf is None:
            parser.error("--elf is required without --selftest")
        result = audit_elf(
            args.elf, out=args.out,
            require_bank3_chain=not args.no_bank3_chain)
        print("c2-asm-leaf-abi-gate: " + result["status"])
        return 0
    except (GateError, STZ.GateError, ElfTruthError, OSError,
            subprocess.CalledProcessError, ValueError) as error:
        print("c2-asm-leaf-abi-gate: FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
