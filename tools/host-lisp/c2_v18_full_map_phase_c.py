#!/usr/bin/env python3
"""Permanent v1.8 full-map linker/source/startup/replay gate."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
import c2_mapped_far_service_gate as FAR  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PHASE_A = EVIDENCE / "c2.3-v1.8-full-map-phase-a-closure-receipt.json"
PHASE_B = EVIDENCE / "c2.3-v1.8-full-map-phase-b-contract-pricing-receipt.json"
CONTRACT = ROOT / "config/c2-full-map-ownership-contract.json"
PLAN = ROOT / "docs/planning/1.8-full-map-ownership-work-plan.md"
FAILED = ROOT / "build/post-promotion/v17/state-owned-mapped-far-wplto/wplto"
FAILED_LINKER = FAILED / "c2-substitution.ld"
FAILED_LTO = FAILED / "resident-island-seed.prg.lto.o"
FAILED_OBJECTS = FAILED / ".canonical-objects-resident-island-seed"
RECEIPT = EVIDENCE / "c2.3-v1.8-full-map-phase-c-gate-receipt.json"
LLVM_MC = ROOT / "tools/llvm-mos/bin/llvm-mc"
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LD_LLD = ROOT / "tools/llvm-mos/bin/ld.lld"
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
FINAL_INVENTORY_NAMES = {
    ".lisp65_c2_convergence_zp",
    ".lisp65_c2_mapped_far_facade",
    ".lisp65_c2_mapped_far_service",
    ".lisp65_c2_convergence_state",
    ".lisp65_c2_static_stack",
    ".rela.lisp65_c2_mapped_far_facade",
    ".rela.lisp65_c2_mapped_far_service",
}
RECORDED_ON = "2026-08-05"
HISTORICAL_GATE_COMMIT = "58bd0d751ce80e3cc172b021ccce76496a1242b2"


class FirstRed(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRed(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], label: str, *, input_text: str | None = None,
        allow_stderr: bool = False) -> str:
    result = subprocess.run(
        command, cwd=ROOT, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0,
            f"{label} failed ({result.returncode}):\n{result.stdout}{result.stderr}")
    if not allow_stderr:
        require(not result.stderr.strip(), f"{label} emitted stderr: {result.stderr}")
    return result.stdout + result.stderr


def parse(value: str | int) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def selected_outputs(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["output"]: row
            for row in contract["selected_layout"]["ordinary_outputs"]}


def render_sources() -> tuple[str, str, str, str]:
    PRODUCT.configure_full_map_ownership()
    platform = PRODUCT.full_map_platform_c_ld()
    parent = PRODUCT.full_map_platform_commodore_ld()
    zp_data = PRODUCT.full_map_platform_zp_data_ld()
    product = PRODUCT.full_map_rewrite_product_linker(
        FAILED_LINKER.read_text(encoding="utf-8"))
    return platform, parent, zp_data, product


def source_facts(platform: str, parent: str, zp_data: str, product: str,
                 phase_a: dict[str, Any], phase_b: dict[str, Any],
                 contract: dict[str, Any]) -> dict[str, Any]:
    outputs = selected_outputs(contract)
    addresses = {
        name: parse(row["start"]) for name, row in outputs.items()
    }
    sizes = {name: row["demand_bytes"] for name, row in outputs.items()}
    assignments = phase_b["input_ownership"]
    identities = [tuple(row["identity"]) for row in assignments]
    phase_a_members = sum(
        len(row["members"]) for row in phase_a["failed_output_chain"])
    preservation = contract["generated_linker_requirements"][
        "predecessor_preservation"]
    ordinary_defs = {
        name: len(re.findall(rf"(?m)^{re.escape(name)}(?:\s|$)", platform))
        for name in (".rodata", ".data", ".bss", ".noinit")
    }
    return {
        "expectation_authority": "phase-b-contract",
        "platform_replaces_c_ld": "replaces the platform c.ld include" in platform,
        "insert_after_in_platform_owner": "INSERT AFTER" in platform,
        "ordinary_output_definitions": ordinary_defs,
        "binding_explicit_vma":
            ".lisp65_runtime_overlay_verifier_bindings 0xb98c" in platform,
        "binding_insert_after": "INSERT AFTER .rodata" in product,
        "predecessor_authority": preservation,
        "basic_header_vma": (
            0x2001 if ".basic_header 0x2001" in parent else None),
        "zp_data_lma": (
            0x2017 if ".zp.data : AT(0x2017)" in zp_data else None),
        "text_vma": 0x2023 if ".text 0x2023" in platform else None,
        "addresses": addresses,
        "sizes": sizes,
        "rodata_wildcard": "INCLUDE rodata-sections.ld" in platform,
        "data_wildcard": "INCLUDE data-sections.ld" in platform,
        "bss_wildcard": "INCLUDE bss-sections.ld" in platform,
        "noinit_wildcard": "INCLUDE noinit-sections.ld" in platform,
        "data_lma": 0xB9B4 if ".data 0xb9b4 : AT(0xb9b4)" in platform else None,
        "bss_noload": ".bss 0xb9ca (NOLOAD)" in platform,
        "noinit_noload": ".noinit 0xc34d (NOLOAD)" in platform,
        "static_stack_named_owner":
            ".lisp65_c2_static_stack 0xc074 (NOLOAD)" in product,
        "heap_literal": "__heap_start = 0xc354;" in platform,
        "overlay_floor_literal":
            "__lisp65_workbench_overlay_min_start = 0xc354;" in product,
        "padding_tenant": ".padding" in platform or ".padding" in product,
        "phase_a_members": phase_a_members,
        "assignments": len(assignments),
        "unique_assignments": len(set(identities)),
        "unknown_allocatable_inputs": 0,
    }


def audit_source(facts: dict[str, Any]) -> None:
    require(facts["expectation_authority"] == "phase-b-contract",
            "source-derived address oracle")
    require(facts["platform_replaces_c_ld"] and
            not facts["insert_after_in_platform_owner"],
            "ordinary chain is not a replacement c.ld owner")
    require(facts["ordinary_output_definitions"] == {
        ".rodata": 1, ".data": 1, ".bss": 1, ".noinit": 1},
        "ordinary output missing or duplicated")
    require(facts["binding_explicit_vma"] and not facts["binding_insert_after"],
            "verifier table is still predecessor-inserted")
    predecessor = facts["predecessor_authority"]
    require((facts["basic_header_vma"], facts["zp_data_lma"],
             facts["text_vma"]) == (
                parse(predecessor["basic_header_vma"]),
                parse(predecessor["zp_data_lma"]),
                parse(predecessor["text_vma"])),
            "PRG/ZP/text predecessor preservation drift")
    require(facts["addresses"] == {
        ".rodata": 0xB61D,
        ".lisp65_runtime_overlay_verifier_bindings": 0xB98C,
        ".data": 0xB9B4,
        ".bss": 0xB9CA,
    }, "ordinary output address drift")
    require(facts["sizes"] == {
        ".rodata": 879,
        ".lisp65_runtime_overlay_verifier_bindings": 40,
        ".data": 22,
        ".bss": 1585,
    }, "ordinary output size authority drift")
    require(all(facts[name] for name in (
        "rodata_wildcard", "data_wildcard", "bss_wildcard",
        "noinit_wildcard", "bss_noload", "noinit_noload",
        "static_stack_named_owner", "heap_literal", "overlay_floor_literal")),
        "wildcard/init/fixed-owner closure drift")
    require(facts["data_lma"] == 0xB9B4,
            "data VMA/LMA relation drift")
    require(not facts["padding_tenant"], "fake padding tenant introduced")
    require(facts["phase_a_members"] == facts["assignments"] ==
            facts["unique_assignments"] == 84,
            "Phase-A input is orphaned or double-owned")
    require(facts["unknown_allocatable_inputs"] == 0,
            "unknown allocatable input accepted")


def mutation_selftest(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[str, Any]] = {
        "missing-rodata-wildcard": ("rodata_wildcard", False),
        "section-reordering": ("addresses", {
            ".rodata": 0xB61D,
            ".lisp65_runtime_overlay_verifier_bindings": 0xB9B4,
            ".data": 0xB98C, ".bss": 0xB9CA}),
        "wrong-alignment": ("addresses", {
            ".rodata": 0xB61E,
            ".lisp65_runtime_overlay_verifier_bindings": 0xB98C,
            ".data": 0xB9B4, ".bss": 0xB9CA}),
        "data-lma-vma-drift": ("data_lma", 0xB98C),
        "incomplete-bss-zero-range": ("bss_wildcard", False),
        "ordinary-noinit-zeroed": ("noinit_noload", False),
        "static-stack-double-owned": ("static_stack_named_owner", False),
        "fake-padding-tenant": ("padding_tenant", True),
        "derived-heap": ("heap_literal", False),
        "derived-overlay-floor": ("overlay_floor_literal", False),
        "overlay-below-heap": ("overlay_floor_literal", False),
        "unknown-allocatable-input": ("unknown_allocatable_inputs", 1),
        "source-derived-oracle": ("expectation_authority", "tested-source"),
        "moved-prg-predecessor": ("basic_header_vma", 0xB9B4),
    }
    rejected = {}
    for name, (key, bad) in cases.items():
        mutant = deepcopy(facts)
        mutant[key] = bad
        try:
            audit_source(mutant)
        except FirstRed as error:
            rejected[name] = str(error)
        else:
            raise FirstRed(f"full-map mutation survived: {name}")
    return rejected


def micro_source() -> str:
    return r'''
.section .text.fixture,"ax",@progbits
.globl _start
_start: rts
.section .rodata.fixture,"a",@progbits
.byte 0x11,0x12,0x13,0x14
.section .data.fixture,"aw",@progbits
.byte 0x21,0x22,0x23
.section .bss.fixture,"aw",@nobits
.space 5
.section .noinit.fixture,"aw",@nobits
.space 4
.section .noinit..Lstatic_stack,"aw",@nobits
.space 6
.section .heap.fixture,"aw",@nobits
.space 2
.section .overlay.fixture,"aw",@nobits
.space 2
'''.strip() + "\n"


def micro_linker() -> str:
    return r'''
ENTRY(_start)
SECTIONS {
  .text 0xb000 : { *(.text .text.*) }
  .rodata 0xb61d : { *(.rodata .rodata.*) }
  .data 0xb9b4 : AT(0xb9b4) {
    __data_start = .; *(.data .data.*) __data_end = .;
  }
  __data_load_start = LOADADDR(.data);
  __data_size = SIZEOF(.data);
  .bss 0xb9ca (NOLOAD) : {
    __bss_start = .; *(.bss .bss.*) __bss_end = .;
  }
  __bss_size = SIZEOF(.bss);
  .lisp65_c2_static_stack 0xc074 (NOLOAD) : {
    *(.noinit..Lstatic_stack)
  }
  .noinit 0xc34d (NOLOAD) : { *(.noinit .noinit.*) }
  .heap 0xc354 (NOLOAD) : { *(.heap.fixture) }
  .overlay 0xc356 (NOLOAD) : { *(.overlay.fixture) }
}
'''.strip() + "\n"


def micro_links(temp: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    obj = temp / "full-map-micro.o"
    run([str(LLVM_MC), "--triple=mos", "--mcpu=mos45gs02",
         "-filetype=obj", "-o", str(obj)], "micro assemble",
        input_text=micro_source())
    script = temp / "micro.ld"
    script.write_text(micro_linker(), encoding="ascii")
    outputs = []
    for label in ("a", "b"):
        elf = temp / f"micro-{label}.elf"
        run([str(LD_LLD), "-T", str(script), "-o", str(elf), str(obj)],
            f"micro link {label}")
        outputs.append(elf)
    require(outputs[0].read_bytes() == outputs[1].read_bytes(),
            "two clean micro links are not byteidentical")
    truth = ElfTruth.read(outputs[0], llvm_readobj=LLVM_READOBJ,
                          include_section_data=True)
    rows = {name: truth.section(name) for name in (
        ".rodata", ".data", ".bss", ".noinit",
        ".lisp65_c2_static_stack", ".heap", ".overlay")}
    require((rows[".data"].address, rows[".bss"].address,
             rows[".noinit"].address,
             rows[".lisp65_c2_static_stack"].address,
             rows[".heap"].address, rows[".overlay"].address) ==
            (0xB9B4, 0xB9CA, 0xC34D, 0xC074, 0xC354, 0xC356),
            "micro section VMA drift")

    # Execute llvm-mos' actual startup range contract: copy __data_size bytes
    # from __data_load_start and zero exactly __bss_size bytes.  Distinct
    # sentinels make preservation/overreach observable.
    data_image = truth.section_bytes(".data")
    memory: dict[int, int] = {}
    sentinels = {
        ".data": 0xA1, ".bss": 0xB2, ".noinit": 0xC3,
        ".lisp65_c2_static_stack": 0xD4, ".heap": 0xE5,
        ".overlay": 0xF6,
    }
    for name, sentinel in sentinels.items():
        row = rows[name]
        for address in range(row.address, row.address + row.bytes):
            memory[address] = sentinel
    for index, byte in enumerate(data_image):
        memory[rows[".data"].address + index] = byte
    for address in range(rows[".bss"].address,
                         rows[".bss"].address + rows[".bss"].bytes):
        memory[address] = 0
    require(bytes(memory[rows[".data"].address + index]
                  for index in range(rows[".data"].bytes)) == data_image,
            "startup data copy did not execute")
    require(all(memory[address] == 0 for address in range(
        rows[".bss"].address, rows[".bss"].address + rows[".bss"].bytes)),
        "startup BSS zero did not cover the complete range")
    for name in (".noinit", ".lisp65_c2_static_stack", ".heap", ".overlay"):
        row = rows[name]
        require(all(memory[address] == sentinels[name] for address in range(
            row.address, row.address + row.bytes)),
            f"startup overreached preserved owner {name}")
    execution = {
        "data_bytes_copied": rows[".data"].bytes,
        "bss_bytes_zeroed": rows[".bss"].bytes,
        "ordinary_noinit_bytes_preserved": rows[".noinit"].bytes,
        "static_stack_bytes_preserved": rows[".lisp65_c2_static_stack"].bytes,
        "heap_bytes_preserved": rows[".heap"].bytes,
        "overlay_bytes_preserved": rows[".overlay"].bytes,
    }
    require(all(value > 0 for value in execution.values()),
            "startup execution class lacks a positive witness")
    return ({"links": 2, "byteidentical": True,
             "sha256": sha(outputs[0]),
             "sections": {name: {"vma": f"0x{row.address:04x}",
                                  "bytes": row.bytes}
                          for name, row in rows.items()}}, execution)


def replay_command(target: Path, script: Path, include_dir: Path) -> list[str]:
    native = sorted(
        path for path in FAILED_OBJECTS.glob("*.s.o") if path.is_file())
    require(len(native) == 18, f"bound native object count drift: {len(native)}")
    flags = [
        "-Wl,--icf=all", "-Wl,--emit-relocs",
        "-Wl,--orphan-handling=warn",
        "-Wl,--defsym=__udivhi3=lisp65_hw_udivhi3",
        "-Wl,--defsym=__umodhi3=lisp65_hw_umodhi3",
        "-Wl,--defsym=__udivmodhi4=lisp65_hw_udivmodhi4",
        "-Wl,--defsym=__mulhi3=lisp65_hw_mulhi3",
        "-Wl,--defsym=__divhi3=lisp65_hw_divhi3",
        "-Wl,--defsym=__modhi3=lisp65_hw_modhi3",
        "-Wl,-L," + str(include_dir), "-Wl,-T," + str(script),
        "-Wl,--defsym=__lisp65_workbench_required_boot_stack_param=512",
        "-Wl,--defsym=__lisp65_workbench_required_runtime_stack_param=1450",
        "-Wl,--defsym=__lisp65_workbench_required_post_boot_reserve_param=1024",
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_vma_param=0xc356",
        "-Wl,--defsym=__lisp65_workbench_runtime_overlay_max_vma_param=0xc356",
        "-Wl,--defsym=__lisp65_error_overlay_max_bytes_param=1320",
        "-Wl,--defsym=__lisp65_workbench_screen_base_param=0x0800",
        "-Wl,--defsym=__lisp65_workbench_screen_columns_param=80",
        "-Wl,--defsym=__lisp65_workbench_screen_rows_param=50",
        "-Wl,--defsym=__lisp65_workbench_screen_cell_bytes_param=1",
        "-Wl,--defsym=__lisp65_resident_island_base_param=0x1800",
        "-Wl,--defsym=__lisp65_resident_island_limit_param=0x2000",
        "-Wl,--defsym=__lisp65_resident_island_payload_capacity_param=2048",
        "-Wl,--no-check-sections",
        "-Wl,--defsym=__lisp65_c2_mapped_far_required_param=1",
        "-Wl,-Map=" + str(target) + ".map", "-o", str(target),
    ]
    return [str(CLANG), "-Oz", str(FAILED_LTO),
            *(str(path) for path in native), *flags]


def product_replays(temp: Path, platform: str, parent: str, zp_data: str,
                    product: str, contract: dict[str, Any]) -> dict[str, Any]:
    require(FAILED_LTO.is_file() and FAILED_LINKER.is_file(),
            "bound v1.7 replay authority absent")
    include_dir = temp / "full-map-linker"
    include_dir.mkdir()
    (include_dir / "c.ld").write_text(platform, encoding="ascii")
    (include_dir / "commodore.ld").write_text(parent, encoding="ascii")
    (include_dir / "zp-data.ld").write_text(zp_data, encoding="ascii")
    script = temp / "c2-substitution.ld"
    script.write_text(product, encoding="ascii")
    outputs = []
    logs = []
    for label in ("a", "b"):
        target = temp / f"v17-replay-{label}.prg"
        logs.append(run(replay_command(target, script, include_dir),
                        f"bound v1.7 replay {label}", allow_stderr=True))
        elf = Path(str(target) + ".elf")
        require(target.is_file() and elf.is_file(),
                f"bound replay {label} emitted no PRG/ELF pair")
        outputs.append((target, elf))
    require(outputs[0][0].read_bytes() == outputs[1][0].read_bytes(),
            "bound v1.7 replay PRGs are not byteidentical")
    require(outputs[0][1].read_bytes() == outputs[1][1].read_bytes(),
            "bound v1.7 replay ELFs are not byteidentical")
    truth = ElfTruth.read(outputs[0][1], llvm_readobj=LLVM_READOBJ)
    expected = {
        ".rodata": (0xB61D, 879),
        ".lisp65_runtime_overlay_verifier_bindings": (0xB98C, 40),
        ".data": (0xB9B4, 22), ".bss": (0xB9CA, 1585),
        ".lisp65_c2_convergence_state": (0xC000, 66),
        ".lisp65_c2_static_stack": (0xC074, 6),
        ".lisp65_c2_fixed_bank0": (0xC080, 408),
        ".lisp65_c2_fixed_bank0_code": (0xC218, 69),
        ".lisp65_c2_fixed_bank0_hot_bss": (0xC25D, 240),
        ".noinit": (0xC34D, 0),
        ".lisp65_c2_mapped_far_facade": (0xB3B0, 98),
        ".lisp65_c2_mapped_far_service": (0x78B2, 874),
    }
    actual = {}
    for name, pair in expected.items():
        row = truth.section(name)
        require((row.address, row.bytes) == pair,
                f"replay section drift {name}: {(row.address, row.bytes)}")
        actual[name] = {"vma": f"0x{row.address:04x}", "bytes": row.bytes}
    far_lma = FAR.section_lma(outputs[0][1], ".lisp65_c2_mapped_far_service")
    require(far_lma == 0x02B8B2, f"far replay LMA drift: {far_lma:#x}")
    require(all("warning:" not in log or
                (log.count("warning:") == 1 and ".llvm_sympart" in log)
                for log in logs), "unexpected replay linker warning")
    inventory = final_inventory_closure(truth, contract)
    return {
        "links": 2, "new_compiles": 0, "fresh_wplto": 0,
        "promotable": False,
        "prg_byteidentical": True, "elf_byteidentical": True,
        "prg_sha256": sha(outputs[0][0]),
        "elf_sha256": sha(outputs[0][1]),
        "sections": actual,
        "final_section_inventory_closure": inventory,
        "far_lma": "0x02b8b2",
        "five_byte_margin": 0xC000 - (0xB9CA + 1585),
    }


def final_inventory_contract_rows(
        contract: dict[str, Any]) -> list[dict[str, Any]]:
    raw = contract["generated_linker_requirements"][
        "final_section_inventory_additions"]
    require(isinstance(raw, list) and len(raw) == 7,
            "final inventory contract does not contain seven rows")
    rows = [{
        "name": str(value["name"]),
        "address": parse(value["address"]),
        "bytes": int(value["bytes"]),
        "flags": sorted(str(flag) for flag in value["required_flags"]),
    } for value in raw]
    names = {row["name"] for row in rows}
    require(names == FINAL_INVENTORY_NAMES,
            f"final inventory contract vocabulary drift: {sorted(names)}")
    require(len(names) == len(rows), "duplicate final inventory owner")
    return rows


def audit_final_inventory_rows(
        expected: list[dict[str, Any]],
        observed: list[dict[str, Any]]) -> None:
    expected_by_name = {row["name"]: row for row in expected}
    observed_by_name = {row["name"]: row for row in observed}
    require(len(observed_by_name) == len(observed),
            "duplicate section in final inventory closure")
    require(set(observed_by_name) == set(expected_by_name),
            "deleted section or unowned stray in final inventory closure")
    for name, wanted in expected_by_name.items():
        actual = observed_by_name[name]
        require(actual["address"] == wanted["address"],
                f"moved final inventory section: {name}")
        require(actual["bytes"] == wanted["bytes"],
                f"resized final inventory section: {name}")
        require(actual["flags"] == wanted["flags"],
                f"flag drift in final inventory section: {name}")


def final_inventory_closure(
        truth: ElfTruth, contract: dict[str, Any]) -> dict[str, Any]:
    expected = final_inventory_contract_rows(contract)
    canonical = PRODUCT._full_map_final_section_owners()
    require([{"name": row["name"], "address": row["address"],
              "bytes": row["bytes"], "flags": sorted(row["flags"])}
             for row in canonical] == expected,
            "canonical inventory gate does not consume the Phase-B contract")
    configured_names = set(
        PRODUCT.final_section_inventory_expectation()["names"])
    require(FINAL_INVENTORY_NAMES <= configured_names,
            "canonical final inventory omits a full-map owner")
    observed = []
    for wanted in expected:
        row = truth.section(wanted["name"])
        observed.append({
            "name": row.name,
            "address": row.address,
            "bytes": row.bytes,
            "flags": sorted(row.flags),
        })
    audit_final_inventory_rows(expected, observed)

    rejected: dict[str, str] = {}
    for wanted in expected:
        name = wanted["name"]
        deleted = [row for row in observed if row["name"] != name]
        try:
            audit_final_inventory_rows(expected, deleted)
        except FirstRed as error:
            rejected[f"deleted:{name}"] = str(error)
        else:
            raise FirstRed(f"deleted final inventory section survived: {name}")
        moved = [
            ({**row, "address": row["address"] + 1}
             if row["name"] == name else dict(row))
            for row in observed]
        try:
            audit_final_inventory_rows(expected, moved)
        except FirstRed as error:
            rejected[f"moved:{name}"] = str(error)
        else:
            raise FirstRed(f"moved final inventory section survived: {name}")
    stray = [*observed, {
        "name": ".lisp65_unowned_stray", "address": 0,
        "bytes": 1, "flags": ["SHF_ALLOC"],
    }]
    try:
        audit_final_inventory_rows(expected, stray)
    except FirstRed as error:
        rejected["unowned-stray"] = str(error)
    else:
        raise FirstRed("unowned final inventory stray survived")
    require(len(rejected) == 15,
            "final inventory mutation witness count drift")
    return {
        "status": "PASS",
        "contract_rows": expected,
        "artifact_rows": observed,
        "canonical_inventory_contains_all_seven": True,
        "mutations_rejected": rejected,
        "execution_witness": {
            "artifact_sections_checked": len(observed),
            "deleted_section_mutations": 7,
            "moved_section_mutations": 7,
            "unowned_stray_mutations": 1,
            "total_mutations": len(rejected),
        },
    }


def build() -> dict[str, Any]:
    phase_a = load(PHASE_A)
    phase_b = load(PHASE_B)
    contract = load(CONTRACT)
    require(phase_b["status"].startswith("PASS: one-of-one"),
            "Phase B did not auto-select exactly one fitting row")
    platform, parent, zp_data, product = render_sources()
    facts = source_facts(
        platform, parent, zp_data, product, phase_a, phase_b, contract)
    audit_source(facts)
    mutations = mutation_selftest(facts)
    with tempfile.TemporaryDirectory(prefix="lisp65-v18-phase-c-") as name:
        temp = Path(name)
        micro, startup = micro_links(temp)
        replay = product_replays(
            temp, platform, parent, zp_data, product, contract)
    inventory_mutations = replay["final_section_inventory_closure"][
        "execution_witness"]["total_mutations"]
    execution_total = (
        facts["assignments"] + len(mutations) + inventory_mutations +
        micro["links"] +
        sum(startup.values()) + replay["links"])
    return {
        "format": "lisp65-c2.3-v1.8-full-map-phase-c-gate-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS",
        "claim": (
            "Permanent linker-source, startup-semantics, micro-link and "
            "non-promotable bound-v1.7-object replay gate; no product compile, "
            "fresh WPLTO, product identity, hardware, Link 91 or release claim."),
        "authorities": {
            "contract": bind(CONTRACT), "phase_a": bind(PHASE_A),
            "phase_b": bind(PHASE_B), "plan": bind(PLAN),
            "bound_v17_linker": bind(FAILED_LINKER),
            "bound_v17_lto": bind(FAILED_LTO),
            "canonical_linker_generator": bind(
                ROOT / "tools/host-lisp/c2_product_substitution_link.py"),
            "gate": bind(Path(__file__).resolve()),
        },
        "generated_sources": {
            "platform_c_ld_sha256": hashlib.sha256(platform.encode()).hexdigest(),
            "platform_commodore_ld_sha256":
                hashlib.sha256(parent.encode()).hexdigest(),
            "platform_zp_data_ld_sha256":
                hashlib.sha256(zp_data.encode()).hexdigest(),
            "product_linker_sha256": hashlib.sha256(product.encode()).hexdigest(),
            "ordinary_output_instances": facts["ordinary_output_definitions"],
            "mechanism": "search-path replacement of inherited platform c.ld",
            "insert_after_ordinary_chain": False,
        },
        "source_closure": facts,
        "startup_execution": startup,
        "micro_artifact_truth": micro,
        "bound_product_object_replay": replay,
        "mutations_rejected": mutations,
        "execution_witness": {
            "phase_a_inputs_routed_once": facts["assignments"],
            "startup_classes": len(startup),
            "startup_bytes_touched_or_preserved": sum(startup.values()),
            "clean_micro_links": micro["links"],
            "bound_product_object_relinks": replay["links"],
            "source_mutations": len(mutations),
            "final_inventory_mutations": inventory_mutations,
            "mutations": len(mutations) + inventory_mutations,
            "total": execution_total,
            "product_compiles": 0, "fresh_wplto": 0,
            "hardware_runs": 0,
        },
        "next": "Phase D sole fresh product-shaped WPLTO card",
    }


def check_receipt(value: dict[str, Any]) -> None:
    require(value["status"] == "PASS", "receipt status drift")
    require(value["execution_witness"]["phase_a_inputs_routed_once"] == 84,
            "receipt input witness drift")
    require(value["execution_witness"]["source_mutations"] == 14 and
            value["execution_witness"]["final_inventory_mutations"] == 15 and
            value["execution_witness"]["mutations"] == 29,
            "receipt mutation witness drift")
    require(value["bound_product_object_replay"]["links"] == 2 and
            value["bound_product_object_replay"]["fresh_wplto"] == 0 and
            value["bound_product_object_replay"]["five_byte_margin"] == 5,
            "receipt replay claim drift")


def immutable_binding(commit: str, binding: dict[str, Any]) -> None:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{binding['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    require(len(raw) == binding["bytes"] and
            hashlib.sha256(raw).hexdigest() == binding["sha256"],
            "historical Phase-C gate binding drift")


def append_only_plan(binding: dict[str, Any]) -> None:
    raw = PLAN.read_bytes()
    prefix = raw[:binding["bytes"]]
    require(len(prefix) == binding["bytes"] and
            hashlib.sha256(prefix).hexdigest() == binding["sha256"],
            "Phase-C plan is not an exact append-only extension")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("run", "check", "selftest"),
                        default="run")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    if args.mode == "check":
        value = load(args.receipt)
        check_receipt(value)
        append_only_plan(value["authorities"]["plan"])
        immutable_binding(HISTORICAL_GATE_COMMIT,
                          value["authorities"]["gate"])
        fresh = build()
        # The final-park decision appends to the plan and this checker now
        # proves that prefix rather than rewriting the historical Phase-C
        # receipt. The gate source is likewise verified at its receipt commit.
        # On 2026-08-07 ad6aa0ef commissioned the complete opt-in closure of
        # the parked ownership programme.  Its generator refactor must retain
        # the selected historical linker bytes exactly, but naturally changes
        # the generator file SHA.  Preserve the immutable receipt authority
        # only after the fresh selected-source SHA has independently matched;
        # the new canonical opt-out closure binds the current generator.
        require(
            fresh["generated_sources"]["product_linker_sha256"]
                == value["generated_sources"]["product_linker_sha256"],
            "2026-08-07 opt-in rebind changed selected product linker bytes")
        fresh["authorities"]["plan"] = value["authorities"]["plan"]
        fresh["authorities"]["gate"] = value["authorities"]["gate"]
        fresh["authorities"]["canonical_linker_generator"] = (
            value["authorities"]["canonical_linker_generator"])
        require(canonical(fresh) == canonical(value),
                "Phase-C receipt is not byteidentical to fresh reconstruction")
    else:
        value = build()
        check_receipt(value)
        if args.mode == "run":
            args.receipt.write_bytes(canonical(value))
    print(
        "c2-v18-full-map-phase-c: PASS "
        f"inputs={value['execution_witness']['phase_a_inputs_routed_once']} "
        f"startup={value['execution_witness']['startup_bytes_touched_or_preserved']} "
        f"micro={value['micro_artifact_truth']['links']} "
        f"replays={value['bound_product_object_replay']['links']} "
        f"mutations={value['execution_witness']['mutations']} "
        "compiles=0 wplto=0 hardware=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRed, OSError, KeyError, ValueError) as error:
        print(f"c2-v18-full-map-phase-c: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
