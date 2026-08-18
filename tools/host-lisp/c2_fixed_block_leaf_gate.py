#!/usr/bin/env python3
"""Pin the Link-58 fixed-block rtov_fail leaf to structured ELF truth."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from elf_truth import (
    ElfTruth, ElfTruthError, Relocation, Section, Symbol,
)


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
CODE_SECTION = ".lisp65_c2_fixed_bank0_code"
HOT_BSS_SECTION = ".lisp65_c2_fixed_bank0_hot_bss"
LEAF = "rtov_fail"
FIXED_TARGET = "rtov_wipe"
DATA_TARGET = "rtov_fault"
CODE_ADDRESS = 0xC218
CODE_BYTES = 66
LEAF_ADDRESS = 0xC245
LEAF_BYTES = 21
HOT_BSS_ADDRESS = 0xC25A
HOT_BSS_BYTES = 240
NOINIT_ADDRESS = 0xC34A
NOINIT_BYTES = 6
OWNED_STACK_SECTION = ".lisp65_c2_static_stack"
OWNED_STACK_ADDRESS = 0xC074
OWNED_STACK_BYTES = 6
OVERLAY_FLOOR = 0xC352
EXPECTED_DATA_EDGES = 0


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def configure_link60_geometry() -> None:
    """Select the owner-authorized Link-60 fixed-block successor pins."""
    global CODE_BYTES, LEAF_BYTES, HOT_BSS_ADDRESS
    global NOINIT_ADDRESS, OVERLAY_FLOOR, EXPECTED_DATA_EDGES
    CODE_BYTES = 69
    LEAF_BYTES = 24
    HOT_BSS_ADDRESS = 0xC25D
    NOINIT_ADDRESS = 0xC34D
    OVERLAY_FLOOR = 0xC354
    EXPECTED_DATA_EDGES = 3


def audit_truth(truth: ElfTruth, *, require_hot_bss: bool,
                full_map_ownership: bool = False) -> dict[str, Any]:
    code = truth.section(CODE_SECTION)
    leaf = truth.symbol(LEAF)
    require(
        (code.address, code.bytes) == (CODE_ADDRESS, CODE_BYTES),
        f"fixed-code geometry drift: {code}")
    require(
        leaf.symbol_type == "Function"
        and leaf.section == CODE_SECTION
        and leaf.value == LEAF_ADDRESS
        and leaf.bytes == LEAF_BYTES,
        f"fixed rtov_fail identity drift: {leaf}")

    outgoing = [
        row for row in truth.relocations
        if row.source_section_index == leaf.section_index
        and leaf.value <= row.offset < leaf.value + leaf.bytes
    ]
    address_rows = [
        row for row in outgoing if row.relocation_type == "R_MOS_ADDR16"]
    control_rows: list[Relocation] = []
    data_rows: list[Relocation] = []
    for row in address_rows:
        identity = truth.relocation_target_identity(row)
        target_section = truth.section(identity["section"])
        if "SHF_EXECINSTR" in target_section.flags:
            control_rows.append(row)
        else:
            data_rows.append(row)
    control_edges: list[dict[str, Any]] = []
    for row in control_rows:
        identity = truth.relocation_target_identity(row)
        interval = truth.resolve_interval(
            section=identity["section"],
            address=identity["resolved_value"])
        control_edges.append({
            "target": interval["name"],
            "section": identity["section"],
            "type": row.relocation_type,
            "offset": row.offset,
            "relocation_symbol": identity["symbol"],
            "addend": identity["addend"],
            "resolved_value": identity["resolved_value"],
        })
    require(
        len(control_edges) == 1
        and control_edges[0]["target"] == FIXED_TARGET,
        f"fixed rtov_fail has a non-fixed control target: {control_edges}")
    data_edges: list[dict[str, Any]] = []
    for row in data_rows:
        identity = truth.relocation_target_identity(row)
        candidates = [
            interval for interval in truth.sized_intervals(
                section=identity["section"], symbol_types=("Object",))
            if interval.start <= identity["resolved_value"] <
            interval.end_exclusive
        ]
        require(
            len(candidates) == 1,
            "fixed rtov_fail data target must resolve to one sized object: "
            f"identity={identity} candidates={candidates}")
        data_edges.append({
            "target": candidates[0].name,
            "section": identity["section"],
            "type": row.relocation_type,
            "offset": row.offset,
            "relocation_symbol": identity["symbol"],
            "addend": identity["addend"],
            "resolved_value": identity["resolved_value"],
        })
    require(
        len(data_edges) == EXPECTED_DATA_EDGES
        and all(row["target"] == DATA_TARGET for row in data_edges),
        f"fixed rtov_fail absolute data-edge drift: {data_edges}")

    hot_bss: dict[str, Any] | None = None
    if require_hot_bss:
        section = truth.section(HOT_BSS_SECTION)
        heap = truth.symbol("heap")
        require(
            (section.address, section.bytes) ==
                (HOT_BSS_ADDRESS, HOT_BSS_BYTES)
            and heap.section == HOT_BSS_SECTION
            and heap.value == HOT_BSS_ADDRESS
            and heap.bytes == HOT_BSS_BYTES,
            f"fixed hot-BSS geometry drift: section={section} heap={heap}")
        require(
            section.address + section.bytes == NOINIT_ADDRESS,
            "fixed hot-BSS end drift")
        noinit = truth.section(".noinit")
        noinit_end = noinit.address + noinit.bytes
        owned_stack: dict[str, Any] | None = None
        if full_map_ownership:
            stack = truth.section(OWNED_STACK_SECTION)
            require(
                (noinit.address, noinit.bytes) == (NOINIT_ADDRESS, 0)
                and noinit_end == NOINIT_ADDRESS
                and (stack.address, stack.bytes) ==
                    (OWNED_STACK_ADDRESS, OWNED_STACK_BYTES),
                "full-map state ownership drift: "
                f"noinit={noinit} static_stack={stack}")
            overlay_min = OVERLAY_FLOOR
            owned_stack = {
                "section": OWNED_STACK_SECTION,
                "address": stack.address,
                "bytes": stack.bytes,
                "end_exclusive": stack.address + stack.bytes,
            }
        else:
            overlay_min = (noinit_end + 2) & ~1
            require(
                (noinit.address, noinit.bytes) ==
                    (NOINIT_ADDRESS, NOINIT_BYTES)
                and noinit_end == NOINIT_ADDRESS + NOINIT_BYTES
                and overlay_min == OVERLAY_FLOOR,
                f"inherited noinit/alignment geometry drift: {noinit}")
        hot_bss = {
            "address": section.address,
            "bytes": section.bytes,
            "end_exclusive": section.address + section.bytes,
            "following_noinit": {
                "address": noinit.address,
                "bytes": noinit.bytes,
                "end_exclusive": noinit_end,
            },
            "owned_static_stack": owned_stack,
            "geometry_authority": (
                "full-map-state-ownership"
                if full_map_ownership else "historical-inherited-noinit"),
            "contract_end_exclusive": overlay_min,
            "headroom_to_overlay_bytes": 0xC356 - overlay_min,
        }

    return {
        "format": "lisp65-c2-fixed-block-rtov-fail-gate-v1",
        "status": "passed-fixed-block-rtov-fail-identity-and-fixed-target",
        "fixed_code": {
            "address": code.address,
            "bytes": code.bytes,
            "end_exclusive": code.address + code.bytes,
        },
        "leaf": {
            "name": leaf.name,
            "section": leaf.section,
            "address": leaf.value,
            "bytes": leaf.bytes,
            "outgoing_control_edges": control_edges,
            "outgoing_absolute_data_edges": data_edges,
        },
        "hot_bss": hot_bss,
    }


def audit_elf(elf: Path, *, out: Path | None = None,
              require_hot_bss: bool = True,
              full_map_ownership: bool = False) -> dict[str, Any]:
    value = audit_truth(
        ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj"),
        require_hot_bss=require_hot_bss,
        full_map_ownership=full_map_ownership)
    value["elf"] = str(elf)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return value


def _fixture() -> ElfTruth:
    sections = [
        Section(0, "", 0, 0, "SHT_NULL", (), 0),
        Section(1, CODE_SECTION, CODE_ADDRESS, CODE_BYTES, "SHT_PROGBITS",
                ("SHF_EXECINSTR",), 0),
        Section(2, HOT_BSS_SECTION, HOT_BSS_ADDRESS, HOT_BSS_BYTES,
                "SHT_NOBITS",
                ("SHF_WRITE",), 0),
        Section(3, ".text", 0x2000, 0x200, "SHT_PROGBITS",
                ("SHF_EXECINSTR",), 0),
        Section(4, ".noinit", NOINIT_ADDRESS, NOINIT_BYTES, "SHT_NOBITS",
                ("SHF_WRITE",), 0),
        Section(5, ".bss", 0xBF00, 0x100, "SHT_NOBITS",
                ("SHF_WRITE",), 0),
    ]
    symbols = [
        Symbol(0, "", 0, 0, "Local", "None", "Undefined", 0),
        Symbol(1, LEAF, LEAF_ADDRESS, LEAF_BYTES, "Local", "Function",
               CODE_SECTION, 1),
        Symbol(2, FIXED_TARGET, 0x2100, 70, "Local", "Function", ".text", 3),
        Symbol(3, ".text", 0x2000, 0, "Local", "Section", ".text", 3),
        Symbol(4, "heap", HOT_BSS_ADDRESS, HOT_BSS_BYTES, "Global", "Object",
               HOT_BSS_SECTION, 2),
        Symbol(5, "forbidden_call", 0x2180, 8, "Global", "Function",
               ".text", 3),
        Symbol(6, DATA_TARGET, 0xBFDB, 1, "Global", "Object", ".bss", 5),
    ]
    relocations = [
        Relocation(".rela.fixed", CODE_SECTION, 1, 0xC250,
                   "R_MOS_ADDR16", 3, ".text", 0x100),
    ]
    relocations.extend(
        Relocation(".rela.fixed", CODE_SECTION, 1, LEAF_ADDRESS + offset,
                   "R_MOS_ADDR16", 6, DATA_TARGET, 0)
        for offset in (3, 12, 19)[:EXPECTED_DATA_EDGES])
    return ElfTruth(
        sections=sections, symbols=symbols, relocations=relocations)


def _full_map_fixture() -> ElfTruth:
    fixture = _fixture()
    sections = list(fixture.sections)
    sections[4] = replace(
        sections[4], address=NOINIT_ADDRESS, bytes=0)
    sections.append(Section(
        len(sections), OWNED_STACK_SECTION, OWNED_STACK_ADDRESS,
        OWNED_STACK_BYTES, "SHT_NOBITS", ("SHF_WRITE",), 0))
    return ElfTruth(
        sections=sections, symbols=fixture.symbols,
        relocations=fixture.relocations)


def full_map_ownership_selftest() -> dict[str, str]:
    """Retire the inherited `.noinit` snapshot in the owned-map world."""
    fixture = _full_map_fixture()
    audit_truth(
        fixture, require_hot_bss=True, full_map_ownership=True)
    cases: dict[str, ElfTruth] = {}

    resurrected = list(fixture.sections)
    resurrected[4] = replace(resurrected[4], bytes=NOINIT_BYTES)
    cases["resurrect-historical-six-byte-noinit"] = ElfTruth(
        sections=resurrected, symbols=fixture.symbols,
        relocations=fixture.relocations)

    moved = list(fixture.sections)
    moved[-1] = replace(moved[-1], address=0xC34D)
    cases["move-owned-stack-to-historical-noinit"] = ElfTruth(
        sections=moved, symbols=fixture.symbols,
        relocations=fixture.relocations)

    dropped = list(fixture.sections[:-1])
    cases["drop-owned-static-stack"] = ElfTruth(
        sections=dropped, symbols=fixture.symbols,
        relocations=fixture.relocations)

    rejected: dict[str, str] = {}
    for name, candidate in cases.items():
        try:
            audit_truth(
                candidate, require_hot_bss=True,
                full_map_ownership=True)
        except (GateError, ElfTruthError):
            rejected[name] = "rejected"
        else:
            raise GateError(f"full-map ownership mutation survived: {name}")
    require(rejected == {name: "rejected" for name in cases},
            "full-map ownership mutation set drift")
    return rejected


def selftest() -> dict[str, str]:
    fixture = _fixture()
    audit_truth(fixture, require_hot_bss=True)
    mutations: dict[str, ElfTruth] = {}
    for label, replacement in (
            ("wrong-address", {"value": 0xC246}),
            ("wrong-size", {"bytes": LEAF_BYTES - 1}),
            ("wrong-section", {"section": ".text", "section_index": 3})):
        symbols = list(fixture.symbols)
        symbols[1] = replace(symbols[1], **replacement)
        mutations[label] = ElfTruth(
            sections=fixture.sections, symbols=symbols,
            relocations=fixture.relocations)
    mutations["added-code-edge"] = ElfTruth(
        sections=fixture.sections, symbols=fixture.symbols,
        relocations=fixture.relocations + [
            Relocation(".rela.fixed", CODE_SECTION, 1,
                       LEAF_ADDRESS + LEAF_BYTES - 2,
                       "R_MOS_ADDR16", 3, ".text", 0x180)])
    if EXPECTED_DATA_EDGES:
        symbols = list(fixture.symbols)
        symbols[6] = replace(symbols[6], name="wrong_data")
        mutations["wrong-data-edge"] = ElfTruth(
            sections=fixture.sections, symbols=symbols,
            relocations=fixture.relocations)
    rejected: dict[str, str] = {}
    for label, mutation in mutations.items():
        try:
            audit_truth(mutation, require_hot_bss=True)
        except (GateError, ElfTruthError):
            rejected[label] = "rejected"
        else:
            raise GateError(f"fixed-block mutation survived: {label}")
    require(
        len(rejected) == 4 + int(bool(EXPECTED_DATA_EDGES)),
        "fixed-block mutation count drift")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(), indent=2, sort_keys=True))
        return 0
    if args.elf is None:
        parser.error("--elf is required unless --selftest is used")
    value = audit_elf(args.elf, out=args.out)
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
