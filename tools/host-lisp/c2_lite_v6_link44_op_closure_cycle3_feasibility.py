#!/usr/bin/env python3
"""Prove the final Class-B Link-44 OP_CLOSURE capture before hardware.

Cycle 2 falsified the assumption that compiler scratch at $16/$17 retained a
bytecode cursor.  This gate uses no compiler scratch.  It proves that the
named, sized c2_dma_list object at $BA00 is the last descriptor written on the
single negative OP_CLOSURE -> dir_find edge.  That descriptor identifies the
SYMFN_EXT entry and therefore the exact interned-symbol object passed to
dir_find.  The corresponding Bank-5 name offset/name bytes are optional
read-only enrichment and are also captured under the CPU hold.

This is paper/ELF work only: no compiler, linker, product patch, or hardware.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-44-c2-lite-v6-bank2-target-stage-replay")
PRODUCT = BASE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
LTO = Path(str(PRODUCT) + ".lto.o")
WINDOW = BASE / "c2-product-kernal-window.bin"
DIAGNOSTIC = ROOT / (
    "build/c2.2/substitution/link44-op-closure-hold-cycle2/"
    "lisp65-link44-op-closure-hold-cycle2-NONPROMOTABLE.prg")
CYCLE2_RECEIPT = EVIDENCE / (
    "c2.2-link44-op-closure-hold-hardware-cycle2-receipt.json")
CYCLE2_VM = ROOT / (
    "build/c2.2/hardware-link44-op-closure-hold-cycle2/"
    "capture-1-vm-bfd9-c022.bin")
PRIOR_FEASIBILITY = EVIDENCE / (
    "c2.2-link44-op-closure-postlink-patch-feasibility-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link44-op-closure-cycle3-stable-descriptor-feasibility-receipt.json")

READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PRODUCT_SHA = "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926"
DIAGNOSTIC_SHA = "b38df65558f1915c411823874e67d43668f7761cc7b789034bd42caaa5e4d48e"
CYCLE2_RECEIPT_SHA = "73fc8d3be49c99a053390e0d67b7977ce5d41b9265ad1c8e92468e57e3705ff5"

LOAD_ADDRESS = 0x2001
FAIL_EDGE = 0x8755
BEFORE = bytes.fromhex("a2064c346a")
AFTER = bytes.fromhex("a2064c5587")
PATCH_CPU_ADDRESSES = (0x8758, 0x8759)
PATCH_FILE_OFFSETS = tuple(2 + value - LOAD_ADDRESS
                           for value in PATCH_CPU_ADDRESSES)

DMA_LIST_ADDRESS = 0xBA00
DMA_LIST_BYTES = 12
DMA_WRITER_ADDRESS = 0xFF90
DMA_WRITER_BYTES = 68
SYMPOOL_EXT_BANK = 5
SYMPOOL_EXT_OFF = 0xC680
NAMEPOOL_BYTES = 10208
MAX_SYM = 752
SYMVAL_EXT_OFF = SYMPOOL_EXT_OFF + NAMEPOOL_BYTES
NAMEOFF_EXT_OFF = SYMVAL_EXT_OFF + MAX_SYM * 2
SYMFN_EXT_OFF = NAMEOFF_EXT_OFF + MAX_SYM * 2
SYMFN_EXT_END = SYMFN_EXT_OFF + MAX_SYM * 2
SYMI_BASE = 0x7000
SYMBOL_NAME_BYTES = 34


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"{label} must be regular and symlink-free: {path}")
    return path.read_bytes()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = regular(path)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": digest(data),
    }


def product_slice(product: bytes, address: int, count: int) -> bytes:
    offset = 2 + address - LOAD_ADDRESS
    require(0 <= offset <= len(product) - count,
            f"CPU address outside Link-44 PRG: 0x{address:04x}")
    return product[offset:offset + count]


def window_slice(window: bytes, address: int, count: int) -> bytes:
    offset = address - 0xE000
    require(0 <= offset <= len(window) - count,
            f"CPU address outside KERNAL window: 0x{address:04x}")
    return window[offset:offset + count]


def exact_hold_patch(product: bytes, diagnostic: bytes) -> dict[str, Any]:
    require(digest(product) == PRODUCT_SHA, "Link-44 product authority drift")
    require(digest(diagnostic) == DIAGNOSTIC_SHA,
            "cycle-2 hold identity drift")
    require(int.from_bytes(product[:2], "little") == LOAD_ADDRESS,
            "Link-44 load address drift")
    require(product_slice(product, FAIL_EDGE, len(BEFORE)) == BEFORE,
            "Link-44 negative dir_find edge drift")
    require(product_slice(diagnostic, FAIL_EDGE, len(AFTER)) == AFTER,
            "diagnostic hold edge drift")
    changed = [index for index, pair in enumerate(zip(product, diagnostic))
               if pair[0] != pair[1]]
    require(len(product) == len(diagnostic), "hold patch changed file size")
    require(changed == list(PATCH_FILE_OFFSETS),
            f"hold patch changed unexpected bytes: {changed}")

    mutants: dict[str, bytearray] = {
        "wrong-low-target-byte": bytearray(diagnostic),
        "wrong-high-target-byte": bytearray(diagnostic),
        "only-one-operand-changed": bytearray(diagnostic),
        "opcode-changed": bytearray(diagnostic),
        "extra-neighbour-byte": bytearray(diagnostic),
    }
    mutants["wrong-low-target-byte"][PATCH_FILE_OFFSETS[0]] ^= 1
    mutants["wrong-high-target-byte"][PATCH_FILE_OFFSETS[1]] ^= 1
    mutants["only-one-operand-changed"][PATCH_FILE_OFFSETS[1]] = BEFORE[4]
    mutants["opcode-changed"][PATCH_FILE_OFFSETS[0] - 1] = 0x20
    mutants["extra-neighbour-byte"][PATCH_FILE_OFFSETS[1] + 1] ^= 1
    rejected: dict[str, str] = {}
    for name, mutant in mutants.items():
        try:
            candidate = bytes(mutant)
            delta = [index for index, pair in enumerate(zip(product, candidate))
                     if pair[0] != pair[1]]
            require(delta == list(PATCH_FILE_OFFSETS), "diff-domain mutation")
            require(product_slice(candidate, FAIL_EDGE, len(AFTER)) == AFTER,
                    "hold-loop mutation")
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"hold-patch mutation passed: {name}")
    return {
        "status": "passed-existing-exact-two-byte-self-loop",
        "instruction_address": "0x8755",
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "changed_cpu_addresses": ["0x8758", "0x8759"],
        "changed_file_offsets": ["0x6759", "0x675a"],
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
        "cycle3_identity_rule": (
            "The immutable cycle-2 diagnostic product bytes are reused honestly; "
            "cycle 3 receives a distinct SHA-bound deployment/capture identity, "
            "not a duplicate file falsely presented as new product bytes."),
    }


def descriptor_identity(data: bytes) -> dict[str, Any]:
    require(len(data) == DMA_LIST_BYTES, "DMA descriptor length drift")
    source = data[3] | (data[4] << 8)
    target = data[6] | (data[7] << 8)
    length = data[1] | (data[2] << 8)
    require(data[0] == 0, "descriptor command is not copy")
    require(length == 2, "last symbol-function DMA length is not 2")
    require(data[5] == SYMPOOL_EXT_BANK,
            "last symbol-function DMA source bank is not Bank 5")
    require(SYMFN_EXT_OFF <= source < SYMFN_EXT_END,
            "descriptor source is outside SYMFN_EXT")
    require((source - SYMFN_EXT_OFF) % 2 == 0,
            "descriptor source is not a SYMFN_EXT cell boundary")
    require(data[8] == 0, "symbol-function DMA target is not Bank 0")
    require(data[9:12] == bytes(3), "descriptor reserved bytes are nonzero")
    index = (source - SYMFN_EXT_OFF) // 2
    require(index < MAX_SYM, "derived symbol index exceeds MAX_SYM")
    raw = ((SYMI_BASE + index) << 1) & 0xFFFF
    require(0xE000 <= raw <= 0xFFFE and raw % 2 == 0,
            "derived object is not an interned-symbol immediate")
    return {
        "command": "copy",
        "length": length,
        "source_bank": data[5],
        "source_offset": f"0x{source:04x}",
        "target_bank": data[8],
        "target_offset": f"0x{target:04x}",
        "symbol_index": index,
        "raw_target_obj": f"0x{raw:04x}",
        "raw_target_domain": "SYMI",
        "nameoff_physical_address": f"0x{0x00050000 + NAMEOFF_EXT_OFF + 2 * index:08x}",
        "namepool_physical_base": f"0x{0x00050000 + SYMPOOL_EXT_OFF:08x}",
    }


def descriptor_selftest() -> dict[str, Any]:
    source = SYMFN_EXT_OFF + 2 * 17
    valid = bytes((0, 2, 0, source & 0xFF, source >> 8, 5,
                   0x34, 0xC1, 0, 0, 0, 0))
    decoded = descriptor_identity(valid)
    require(decoded["symbol_index"] == 17
            and decoded["raw_target_obj"] == "0xe022",
            "descriptor positive fixture drift")
    mutants: dict[str, bytearray] = {
        "wrong-command": bytearray(valid),
        "wrong-length": bytearray(valid),
        "wrong-source-bank": bytearray(valid),
        "source-before-symfn": bytearray(valid),
        "odd-source": bytearray(valid),
        "nonzero-length-high-byte": bytearray(valid),
        "wrong-target-bank": bytearray(valid),
        "nonzero-reserved": bytearray(valid),
    }
    mutants["wrong-command"][0] = 1
    mutants["wrong-length"][1] = 3
    mutants["wrong-source-bank"][5] = 4
    mutants["source-before-symfn"][3:5] = (SYMFN_EXT_OFF - 2).to_bytes(2, "little")
    mutants["odd-source"][3] ^= 1
    mutants["nonzero-length-high-byte"][2] = 1
    mutants["wrong-target-bank"][8] = 1
    mutants["nonzero-reserved"][11] = 1
    rejected: dict[str, str] = {}
    for name, mutant in mutants.items():
        try:
            descriptor_identity(bytes(mutant))
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"descriptor mutation passed: {name}")
    return {
        "status": "passed-descriptor-decoder-domain-fixtures",
        "positive_fixture": decoded,
        "mutations_rejected": rejected,
    }


def exact_relocation(truth: ElfTruth, *, offset: int, target: str,
                     resolved: int) -> dict[str, Any]:
    rows = [row for row in truth.relocations
            if row.source_section == ".text" and row.offset == offset
            and row.relocation_type == "R_MOS_ADDR16"]
    require(len(rows) == 1, f"relocation identity drift at 0x{offset:04x}")
    row = rows[0]
    identity = truth.relocation_target_identity(row)
    require(row.target == target and identity["resolved_value"] == resolved,
            f"relocation target drift at 0x{offset:04x}")
    return {
        "operand_address": f"0x{offset:04x}",
        "target": target,
        "resolved_address": f"0x{resolved:04x}",
        "relocation_type": row.relocation_type,
    }


def _validate_provenance_model(model: dict[str, Any]) -> None:
    symbol = model["descriptor_symbol"]
    require(symbol == {
        "name": "c2_dma_list", "section": ".bss",
        "address": DMA_LIST_ADDRESS, "bytes": DMA_LIST_BYTES,
        "type": "Object"}, "c2_dma_list symbol provenance drift")
    writer = model["writer_symbol"]
    require(writer == {
        "name": "c2_facade_target_c2_dma",
        "section": ".lisp65_c2_kernal_window.reopen_gap2",
        "address": DMA_WRITER_ADDRESS, "bytes": DMA_WRITER_BYTES,
        "type": "Function"}, "DMA writer symbol provenance drift")
    refs = model["descriptor_references"]
    absolute = [row for row in refs if row["kind"] == "field"]
    split = [row for row in refs if row["kind"] == "list-pointer"]
    require(len(refs) == 14 and len(absolute) == 12 and len(split) == 2,
            "DMA descriptor relocation inventory count drift")
    require({row["addend"] for row in absolute} == set(range(12)),
            "DMA descriptor field relocation set drift")
    require({row["type"] for row in split} ==
            {"R_MOS_ADDR16_HI", "R_MOS_ADDR16_LO"},
            "DMA list-pointer relocation pair drift")
    require(all(row["source_section"] == writer["section"]
                and writer["address"] <= row["offset"] <
                writer["address"] + writer["bytes"] for row in refs),
            "DMA descriptor has a reference outside its one writer")
    call_chain = model["call_chain"]
    require([row["resolved_address"] for row in call_chain] ==
            ["0x8bfa", "0x6757", "0xb5c7"],
            "OP_CLOSURE descriptor call chain drift")


def provenance_selftest(model: dict[str, Any]) -> dict[str, str]:
    mutations: dict[str, dict[str, Any]] = {}
    mutations["wrong-symbol-address"] = deepcopy(model)
    mutations["wrong-symbol-address"]["descriptor_symbol"]["address"] += 1
    mutations["wrong-symbol-size"] = deepcopy(model)
    mutations["wrong-symbol-size"]["descriptor_symbol"]["bytes"] -= 1
    mutations["missing-field-relocation"] = deepcopy(model)
    mutations["missing-field-relocation"]["descriptor_references"].pop(0)
    mutations["foreign-writer-reference"] = deepcopy(model)
    mutations["foreign-writer-reference"]["descriptor_references"][0]["source_section"] = ".text"
    mutations["wrong-call-target"] = deepcopy(model)
    mutations["wrong-call-target"]["call_chain"][1]["resolved_address"] = "0x0000"
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        try:
            _validate_provenance_model(mutant)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"provenance mutation passed: {name}")
    return rejected


def elf_provenance(product: bytes, window: bytes) -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    descriptor = truth.symbol("c2_dma_list")
    writer = truth.symbol("c2_facade_target_c2_dma")
    sym_function = truth.symbol("sym_function")
    dir_find = truth.symbol("dir_find")
    vm_run_inner = truth.symbol("vm_run_inner")
    require((descriptor.section, descriptor.value, descriptor.bytes,
             descriptor.symbol_type) ==
            (".bss", DMA_LIST_ADDRESS, DMA_LIST_BYTES, "Object"),
            "c2_dma_list ELF identity drift")
    require((writer.section, writer.value, writer.bytes,
             writer.symbol_type) ==
            (".lisp65_c2_kernal_window.reopen_gap2", DMA_WRITER_ADDRESS,
             DMA_WRITER_BYTES, "Function"),
            "DMA writer ELF identity drift")
    require((sym_function.value, sym_function.bytes) == (0x6757, 108),
            "sym_function ELF identity drift")
    require((dir_find.value, dir_find.bytes) == (0x8BFA, 50),
            "dir_find ELF identity drift")
    require((vm_run_inner.value, vm_run_inner.bytes) == (0x6920, 7975),
            "vm_run_inner ELF identity drift")

    refs = [row for row in truth.relocations if row.target == "c2_dma_list"]
    ref_rows = []
    for row in refs:
        owner = truth.resolve_interval(section=row.source_section,
                                       address=row.offset)
        require(owner["name"] == "c2_facade_target_c2_dma",
                "c2_dma_list reference is outside the one sized writer")
        ref_rows.append({
            "kind": ("list-pointer" if row.relocation_type in
                     ("R_MOS_ADDR16_HI", "R_MOS_ADDR16_LO") else "field"),
            "source_section": row.source_section,
            "offset": row.offset,
            "type": row.relocation_type,
            "addend": row.addend,
        })
    model = {
        "descriptor_symbol": {
            "name": descriptor.name, "section": descriptor.section,
            "address": descriptor.value, "bytes": descriptor.bytes,
            "type": descriptor.symbol_type,
        },
        "writer_symbol": {
            "name": writer.name, "section": writer.section,
            "address": writer.value, "bytes": writer.bytes,
            "type": writer.symbol_type,
        },
        "descriptor_references": ref_rows,
        "call_chain": [
            exact_relocation(truth, offset=0x7764, target=".text",
                             resolved=0x8BFA),
            exact_relocation(truth, offset=0x8BFB, target=".text",
                             resolved=0x6757),
            exact_relocation(truth, offset=0x679E,
                             target="c2_facade_c2_dma", resolved=0xB5C7),
        ],
    }
    _validate_provenance_model(model)

    spans = {
        "symbolic-op-closure-dispatch": (
            0x7217,
            "b2048507a406b104aa30034c6177a5072901f0034c6177e0e090034c6177"),
        "negative-dir-find-edge": (
            0x7761, "a50720fa8ba00b91028aa01091028a10034c5587"),
        "dir-find": (
            0x8BFA,
            "205767a8a9ffe00010128604460484056605b008e0e0d007c0008005a2ff60e0e0a2ffb00c18a5056900a8a50469a0aa9860"),
        "symfn-offset-and-DMA-call": (
            0x676C,
            "204f6686040a2604186920850aa50469fa18a6028616a6038617a205a0028604a6028605a6038606640784086409aaa50a20c7b5"),
        "host-facade-vector": (0xB5C7, "4c90ff"),
    }
    for name, (address, expected_hex) in spans.items():
        expected = bytes.fromhex(expected_hex)
        actual = (window_slice(window, address, len(expected))
                  if address >= 0xE000 else
                  product_slice(product, address, len(expected)))
        require(actual == expected, f"linked dataflow span drift: {name}")
    target_body = bytes.fromhex(
        "860aa608a4098e01ba8c02ba9c00ba8d03baa60a8e04baa6048e05baa6058e06ba"
        "a6068e07baa6078e08ba9c09ba9c0aba9c0bbaa9008d02d7a9ba8d01d7a9008d00d760")
    require(window_slice(window, DMA_WRITER_ADDRESS, len(target_body)) == target_body,
            "linked DMA writer body drift")

    return {
        "status": "passed-structured-ELF-and-linked-dataflow-provenance",
        **model,
        "mutations_rejected": provenance_selftest(model),
        "last-writer_proof": {
            "sequence": [
                "OP_CLOSURE loads the symbolic literal and calls dir_find",
                "dir_find calls sym_function",
                "sym_function derives SYMFN_EXT_OFF + 2*symbol_index",
                "the host facade jumps to the sole c2_dma_list writer",
                "dir_find performs CPU-only domain checks after sym_function",
                "the negative edge reaches the $8755 hold before cleanup or wipe",
            ],
            "asynchronous_writer_exclusion": (
                "All fourteen structured references to the named descriptor are "
                "owned by c2_facade_target_c2_dma; IRQ/NMI sections have none. "
                "The hold loop contains only JMP $8755 and starts no further DMA."),
            "descriptor_lifetime": (
                "The producer writes all twelve bytes before starting DMA. DMA reads "
                "the descriptor but never writes it; after the call chain returns, the "
                "descriptor remains the last submitted job until another producer call."),
        },
    }


def old_frame_route_rejection() -> dict[str, Any]:
    data = regular(CYCLE2_VM, "cycle-2 stable VM frame")
    require(len(data) == 74, "cycle-2 VM frame length drift")
    require(data.count(bytes((0x3F,))) == 0,
            "cycle-2 VM frame unexpectedly acquired OP_CLOSURE")
    # Addresses C014..C021 lie 0x3b..0x48 bytes into the BFD9 capture.
    def word(address: int) -> int:
        offset = address - 0xBFD9
        return data[offset] | (data[offset + 1] << 8)
    require(word(0xC014) == 0xBFE0 and word(0xC016) == 0xBFEC,
            "cycle-2 VM frame pointer interpretation drift")
    require(word(0xC01A) == 52 and word(0xC020) == 37,
            "cycle-2 VM frame payload/window interpretation drift")
    return {
        "status": "rejected-as-insufficient-no-cursor-inference",
        "capture": bind(CYCLE2_VM),
        "bytecode_buffer_contains_op_closure_0x3f": False,
        "littab": "0xbfe0",
        "code": "0xbfec",
        "payload_bytes": 52,
        "resident_window_bytes": 37,
        "reason": (
            "The complete stable 74-byte frame contains no OP_CLOSURE opcode and "
            "does not encode the live PC. It cannot identify this lookup without "
            "reusing the falsified $16/$17 compiler-scratch assumption."),
    }


def main() -> int:
    try:
        require(not RECEIPT.exists(), "cycle-3 feasibility receipt already exists")
        product = regular(PRODUCT, "Link-44 product")
        diagnostic = regular(DIAGNOSTIC, "cycle-2 hold diagnostic")
        window = regular(WINDOW, "Link-44 KERNAL window")
        require(digest(CYCLE2_RECEIPT.read_bytes()) == CYCLE2_RECEIPT_SHA,
                "cycle-2 First Red receipt drift")
        cycle2 = json.loads(regular(CYCLE2_RECEIPT).decode("utf-8"))
        require(cycle2.get("status") ==
                "FIRST RED: Class-B cycle 2 capture-stability contract failed",
                "cycle-2 First Red status drift")
        require(SYMFN_EXT_END == 0x10000,
                "canonical Bank-5 symbol layout arithmetic drift")

        patch = exact_hold_patch(product, diagnostic)
        provenance = elf_provenance(product, window)
        decoder_test = descriptor_selftest()
        old_route = old_frame_route_rejection()
        authority_paths = {
            "link44_product": PRODUCT,
            "link44_elf": ELF,
            "link44_map": MAP,
            "link44_lto_object": LTO,
            "link44_kernal_window": WINDOW,
            "immutable_hold_diagnostic": DIAGNOSTIC,
            "cycle2_first_red": CYCLE2_RECEIPT,
            "prior_postlink_feasibility_historical": PRIOR_FEASIBILITY,
            "platform_dma_source": ROOT / "src/c2_platform_dma.c",
            "symbol_source": ROOT / "src/symbol.c",
            "symbol_contract": ROOT / "src/symbol.h",
            "object_encoding_contract": ROOT / "src/obj.h",
            "compiler_source": ROOT / "src/compile.c",
            "canonical_workbench_defines": ROOT / "config/workbench.mk",
        }
        receipt = {
            "format": "lisp65-c2-lite-v6-link44-op-closure-cycle3-feasibility-v1",
            "recorded_on": "2026-07-22",
            "status": "passed-final-cycle-stable-descriptor-feasibility-hardware-not-run",
            "promotable": False,
            "delegation": {
                "class": "B feasibility prerequisite",
                "cycle": "3-of-3 proposed, not consumed",
                "question": "exact negative OP_CLOSURE dir_find lookup identity",
            },
            "scope": {
                "compiler_runs": 0,
                "linker_runs": 0,
                "new_product_bytes": 0,
                "new_diagnostic_bytes": 0,
                "hardware_runs": 0,
            },
            "authority": {name: bind(path) for name, path in authority_paths.items()},
            "canonical_layout": {
                "symbol_pool": {"bank": 5, "offset": "0xc680", "bytes": 10208},
                "symbol_values_offset": "0xee60",
                "symbol_name_offsets": {"offset": "0xf440", "entries": 752,
                                        "entry_bytes": 2},
                "symbol_functions": {"offset": "0xfa20", "entries": 752,
                                     "entry_bytes": 2,
                                     "end_exclusive": "0x10000"},
                "object_formula": "raw_target_obj = ((0x7000 + symbol_index) << 1) & 0xffff",
            },
            "hold_patch": patch,
            "elf_and_liveness_proof": provenance,
            "descriptor_decoder": decoder_test,
            "rejected_frame_only_route": old_route,
            "prospective_capture_contract": {
                "holdpoint": {
                    "address": "0x8755",
                    "edge": "single negative dir_find result inside OP_CLOSURE",
                    "timing": "before common VM_DIRMISS cleanup, journal abort, or wipe",
                },
                "primary_cells": [{
                    "address_start": "0x0000ba00",
                    "address_end_exclusive": "0x0000ba0c",
                    "bytes": 12,
                    "meaning": "c2_dma_list, last submitted SYMFN_EXT read",
                    "stability_source": (
                        "ELF-named .bss Object, exactly one sized writer, complete "
                        "relocation inventory, frozen CPU edge after its last call"),
                }],
                "derived_read_only_enrichment": [
                    {
                        "cells": "Bank-5 nameoff[symbol_index], two bytes",
                        "stability_source": (
                            "symbol.c persistent intern table; written only while "
                            "interning, before the held OP_CLOSURE consumes the symbol"),
                    },
                    {
                        "cells": "Bank-5 namepool[nameoff], fixed 34-byte contract window",
                        "stability_source": (
                            "symbol.c append-only interned-name pool plus stopped CPU; "
                            "LISP65_SYMBOL_NAME_BUFFER is 34 including NUL"),
                    },
                ],
                "capture_count": 3,
                "spacing": ["hold+0ms", "hold+250ms", "hold+1000ms"],
                "required": (
                    "all three descriptor, nameoff and name-window captures are "
                    "byteidentical before any lookup identity is claimed"),
                "identity_output": ["raw SYMI object", "symbol index", "symbol name"],
            },
            "capacity_effect": {
                "product_file_bytes": 0,
                "bank0_text_bytes": 0,
                "ordinary_bank0_bss_bytes": 0,
                "fixed_hot_block_bytes": 0,
                "resident_island_bytes": 0,
                "e000_bytes": 0,
                "runtime_overlay_bytes": 0,
            },
            "budgets": {
                "class_b_diagnostic_cycles": "2/3 consumed; green feasibility permits final cycle 3",
                "line1_product_first_reds": "2/3 unchanged",
                "completed_latency_measurements": "0/2 unchanged",
            },
            "claim_boundary": (
                "This receipt proves the capture cells and their liveness before "
                "hardware. It does not identify the actual failing symbol, consume "
                "cycle 3, change product bytes, or make product, latency, acceptance "
                "or promotion claims."),
            "next_gate": (
                "prepare one distinct nonpromotable cycle-3 deployment identity; "
                "announce device need; execute exactly one form and one hardware run"),
        }
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        print("c2-link44-op-closure-cycle3-feasibility: PASS "
              "source=c2_dma_list cells=12 liveness=ELF mutations=18 hardware=not-run")
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError,
            GateError) as exc:
        print(f"c2-link44-op-closure-cycle3-feasibility: FAIL: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
