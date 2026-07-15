#!/usr/bin/env python3
"""Audit control references into the staged Workbench boot overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


NM_RE = re.compile(r"^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+(\S)\s+(.+?)\s*$")
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
DISASSEMBLY_RE = re.compile(r"^Disassembly of section (.+):$")
CONTROL_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(jsr|jmp)\s+\$([0-9a-fA-F]+)\b",
    re.IGNORECASE,
)
DIRECT_OPERAND_RE = re.compile(r"^\$([0-9a-fA-F]+)\b")
OVERLAY_START = "__lisp65_workbench_overlay_start"
OVERLAY_END = "__lisp65_workbench_overlay_end"
OVERLAY_ENTRY = "__lisp65_workbench_overlay_entry"
ENTRY = "vm_workbench_boot_overlay_entry"
INSTALLER = "vm_install_staged_boot_overlay"
BOOT_SECTION = ".lisp65_workbench_overlay"
BOOT_FUNCTIONS = (ENTRY, "eval_init", "defprim")
OPTIONAL_BOOT_SLICE_FUNCTIONS = {
    "vm_boot_stack_probe_begin": ".lisp65_rt_boot_02",
}
BOOT_SLICE_FUNCTION_SECTIONS = {
    "vm_boot_fastpath_phase_verify": ".lisp65_rt_boot_00",
    "vm_boot_fastpath_phase_patches": ".lisp65_rt_boot_01",
    "vm_boot_fastpath_phase_entries": ".lisp65_rt_boot_02",
    "gc_freeze_boot": ".lisp65_rt_boot_02",
}
BOOT_SLICE_LINKER_SECTIONS = {
    f"__lisp65_rt_boot_{index:02d}_{suffix}": f".lisp65_rt_boot_{index:02d}"
    for index in range(3)
    for suffix in ("start", "end", "entry")
}
SECTION_PINS = {
    OVERLAY_START: BOOT_SECTION,
    OVERLAY_END: BOOT_SECTION,
    OVERLAY_ENTRY: BOOT_SECTION,
    ENTRY: BOOT_SECTION,
    "eval_init": BOOT_SECTION,
    "defprim": BOOT_SECTION,
    INSTALLER: ".text",
    **BOOT_SLICE_FUNCTION_SECTIONS,
    **BOOT_SLICE_LINKER_SECTIONS,
}
REQUIRED_RESIDENT = (
    "vm_load_lib_ext",
    "md_read",
    "md_name",
    "md_idx",
    "md_lit_node",
    "vm_register_embedded",
    "vm_dir_align8",
    "eval_vm_bridge",
    "eval_vm_apply",
    "mem_init",
    "vm_init",
    "str_arena_freeze",
    "lisp_stack_low",
)
TOP_LEVEL_RESIDENT_CALLERS = ("io_disk_lib_staged", "io_disk_load_lib")
RUNTIME_CRC = "rtov_crc_mem"
RUNTIME_CATALOG_VERIFIER = "vm_runtime_overlay_catalog_verifier"
RUNTIME_CATALOG_SECTION = ".lisp65_rt_rtov_catalog"
REMOVED_TRANSIENT_CRC = "rtov_c_crc_mem"


class AuditError(RuntimeError):
    pass


def _run(command: list[str]) -> str:
    try:
        return subprocess.run(
            command, check=True, text=True, capture_output=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise AuditError(f"command failed: {' '.join(command)}: {detail.strip()}") from exc


def _parse_symbols(text: str) -> dict[str, dict[str, int | str]]:
    symbols: dict[str, dict[str, int | str]] = {}
    for line in text.splitlines():
        match = NM_RE.match(line)
        if not match:
            continue
        address, size, symbol_type, name = match.groups()
        if name in symbols:
            raise AuditError(f"duplicate ELF symbol: {name}")
        symbols[name] = {
            "address": int(address, 16),
            "size": int(size, 16),
            "type": symbol_type,
        }
    return symbols


def _parse_objdump_symbols(text: str) -> dict[str, dict[str, int | str]]:
    symbols: dict[str, dict[str, int | str]] = {}
    for line in text.splitlines():
        parts = line.split()
        if (len(parts) < 5 or not HEX_RE.fullmatch(parts[0])
                or not HEX_RE.fullmatch(parts[-2])):
            continue
        address, section, size, name = parts[0], parts[-3], parts[-2], parts[-1]
        flags = parts[2:-3]
        if name in symbols:
            raise AuditError(f"duplicate objdump ELF symbol: {name}")
        symbols[name] = {
            "address": int(address, 16),
            "size": int(size, 16),
            "type": "F" if "F" in flags else ("O" if "O" in flags else ""),
            "section": section,
        }
    return symbols


def _merge_symbols(
    nm_symbols: dict[str, dict[str, int | str]],
    objdump_symbols: dict[str, dict[str, int | str]],
) -> dict[str, dict[str, int | str]]:
    symbols = {name: dict(record) for name, record in nm_symbols.items()}
    for name, record in objdump_symbols.items():
        previous = symbols.get(name)
        if previous is not None and int(previous["address"]) != int(record["address"]):
            raise AuditError(f"nm/objdump address mismatch for {name}")
        symbols[name] = dict(record)
    return symbols


def _parse_controls(text: str) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    section: str | None = None
    for line in text.splitlines():
        section_match = DISASSEMBLY_RE.match(line.strip())
        if section_match:
            section = section_match.group(1)
            continue
        match = CONTROL_RE.match(line)
        if match:
            source, opcode, target = match.groups()
            controls.append(
                {
                    "source": int(source, 16),
                    "opcode": opcode.lower(),
                    "target": int(target, 16),
                    "section": section,
                }
            )
    return controls


def _parse_instructions(text: str) -> list[dict[str, Any]]:
    instructions: list[dict[str, Any]] = []
    section: str | None = None
    for line in text.splitlines():
        section_match = DISASSEMBLY_RE.match(line.strip())
        if section_match:
            section = section_match.group(1)
            continue
        if ":" not in line:
            continue
        address_text, body = line.split(":", 1)
        address_text = address_text.strip()
        if not HEX_RE.fullmatch(address_text):
            continue
        body = body.split(";", 1)[0].strip()
        if not body:
            continue
        parts = body.split(None, 1)
        instructions.append({
            "address": int(address_text, 16),
            "opcode": parts[0].lower(),
            "operand": parts[1].strip().lower() if len(parts) == 2 else "",
            "section": section,
        })
    return instructions


def _address(symbols: dict[str, dict[str, int | str]], name: str) -> int:
    try:
        return int(symbols[name]["address"])
    except KeyError as exc:
        raise AuditError(f"missing ELF symbol: {name}") from exc


def _contains(symbols: dict[str, dict[str, int | str]], name: str, address: int) -> bool:
    record = symbols.get(name)
    if record is None:
        return False
    start, size = int(record["address"]), int(record["size"])
    return size > 0 and start <= address < start + size


def _audit(
    symbols: dict[str, dict[str, int | str]],
    controls: list[dict[str, Any]],
    instructions: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    required = tuple(SECTION_PINS)
    missing = [name for name in required if name not in symbols]
    if missing:
        return ["missing ELF symbols: " + ", ".join(missing)], {}

    for name, expected_section in SECTION_PINS.items():
        actual_section = str(symbols[name].get("section", ""))
        if actual_section != expected_section:
            errors.append(
                f"symbol section mismatch: {name}={actual_section or '<none>'} "
                f"expected={expected_section}"
            )

    start = _address(symbols, OVERLAY_START)
    end = _address(symbols, OVERLAY_END)
    entry = _address(symbols, ENTRY)
    if not start < end:
        errors.append("overlay span is empty or reversed")
    if _address(symbols, OVERLAY_ENTRY) != entry:
        errors.append("exported overlay entry does not match transaction entry")

    for index in range(3):
        slice_start = f"__lisp65_rt_boot_{index:02d}_start"
        if _address(symbols, slice_start) != start:
            errors.append(
                f"runtime boot slice {index:02d} does not share boot VMA 0x{start:04x}"
            )
    for index, function in enumerate((
        "vm_boot_fastpath_phase_verify",
        "vm_boot_fastpath_phase_patches",
        "vm_boot_fastpath_phase_entries",
    )):
        exported = f"__lisp65_rt_boot_{index:02d}_entry"
        if _address(symbols, exported) != _address(symbols, function):
            errors.append(f"runtime boot entry mismatch: {exported} != {function}")

    actual_boot_functions = sorted(
        name for name, record in symbols.items()
        if str(record.get("section", "")) == BOOT_SECTION
        and str(record.get("type", "")).upper() == "F"
        and int(record["size"]) > 0
    )
    optional_boot_functions = [
        name for name in OPTIONAL_BOOT_SLICE_FUNCTIONS if name in symbols
    ]
    expected_boot_functions = sorted(BOOT_FUNCTIONS)
    if actual_boot_functions != expected_boot_functions:
        errors.append(
            "boot function set mismatch: actual=" + ",".join(actual_boot_functions)
            + " expected=" + ",".join(expected_boot_functions)
        )

    resident_present = [
        name for name in (*REQUIRED_RESIDENT, *TOP_LEVEL_RESIDENT_CALLERS)
        if name in symbols
    ]
    for name in resident_present:
        section = str(symbols[name].get("section", ""))
        if section != ".text":
            errors.append(f"required resident symbol is not in .text: {name}={section}")

    inbound = [
        ref for ref in controls
        if ref.get("section") == ".text" and start <= ref["target"] < end
    ]
    valid_inbound = [
        ref for ref in inbound
        if ref["opcode"] == "jsr"
        and ref["target"] == entry
        and _contains(symbols, INSTALLER, ref["source"])
    ]
    if len(inbound) != 1 or len(valid_inbound) != 1:
        errors.append(
            "expected exactly one resident JSR from installer to transaction entry; "
            f"found inbound={len(inbound)} valid={len(valid_inbound)}"
        )

    entry_calls = [
        ref for ref in controls
        if ref.get("section") == BOOT_SECTION
        and ref["opcode"] in ("jsr", "jmp")
        and ref["target"] == _address(symbols, "eval_init")
        and _contains(symbols, ENTRY, ref["source"])
    ]
    if len(entry_calls) != 1:
        errors.append(
            f"expected one direct {ENTRY} -> eval_init JSR|JMP; found {len(entry_calls)}"
        )

    probe_calls: list[dict[str, Any]] = []
    if optional_boot_functions:
        probe = optional_boot_functions[0]
        probe_section = OPTIONAL_BOOT_SLICE_FUNCTIONS[probe]
        if str(symbols[probe].get("section", "")) != probe_section:
            errors.append(
                f"optional boot symbol is not in {probe_section}: "
                f"{probe}={symbols[probe].get('section', '') or '<none>'}"
            )
        probe_calls = [
            ref for ref in controls
            if ref.get("section") == probe_section
            and ref["opcode"] in ("jsr", "jmp")
            and ref["target"] == _address(symbols, probe)
            and _contains(symbols, "vm_boot_fastpath_phase_entries", ref["source"])
        ]
        if len(probe_calls) != 1:
            errors.append(
                "expected one direct vm_boot_fastpath_phase_entries -> "
                f"{probe} JSR|JMP; "
                f"found {len(probe_calls)}"
            )
        freeze_calls = [
            ref for ref in controls
            if ref.get("section") == probe_section
            and ref["opcode"] == "jsr"
            and ref["target"] == _address(symbols, "gc_freeze_boot")
            and _contains(symbols, "vm_boot_fastpath_phase_entries", ref["source"])
        ]
        if len(freeze_calls) != 1:
            errors.append(
                "expected one direct vm_boot_fastpath_phase_entries -> "
                f"gc_freeze_boot JSR; found {len(freeze_calls)}"
            )
        elif len(probe_calls) == 1 and probe_calls[0]["source"] <= freeze_calls[0]["source"]:
            errors.append(f"{probe} must be called after gc_freeze_boot")

    defprim = _address(symbols, "defprim")
    defprim_calls = [
        ref for ref in controls
        if ref.get("section") == BOOT_SECTION
        and _contains(symbols, "eval_init", ref["source"])
        if ref["opcode"] == "jsr"
        and ref["target"] == defprim
    ]
    if not defprim_calls:
        errors.append("no eval_init control reference reaches overlay-local defprim")

    crc_required = (RUNTIME_CRC, RUNTIME_CATALOG_VERIFIER)
    crc_missing = [name for name in crc_required if name not in symbols]
    if crc_missing:
        errors.append("missing runtime CRC symbols: " + ", ".join(crc_missing))
        crc_calls: list[dict[str, Any]] = []
        crc_body: list[dict[str, Any]] = []
        crc_decrement_operands: list[int] = []
    else:
        if str(symbols[RUNTIME_CRC].get("section", "")) != ".text":
            errors.append(f"{RUNTIME_CRC} is not pinned resident")
        if str(symbols[RUNTIME_CATALOG_VERIFIER].get("section", "")) != \
                RUNTIME_CATALOG_SECTION:
            errors.append(f"{RUNTIME_CATALOG_VERIFIER} section is not pinned")
        crc_calls = [
            ref for ref in controls
            if ref.get("section") == RUNTIME_CATALOG_SECTION
            and ref["opcode"] == "jsr"
            and ref["target"] == _address(symbols, RUNTIME_CRC)
            and _contains(symbols, RUNTIME_CATALOG_VERIFIER, ref["source"])
        ]
        if len(crc_calls) != 1:
            errors.append(
                "expected one catalog-verifier JSR to resident rtov_crc_mem; "
                f"found {len(crc_calls)}"
            )
        crc_body = [
            instruction for instruction in instructions
            if _contains(symbols, RUNTIME_CRC, instruction["address"])
        ]
        if any(item["opcode"] == "dew" for item in crc_body):
            errors.append("resident rtov_crc_mem contains forbidden dew regression")
        crc_decrement_operands = sorted({
            int(match.group(1), 16)
            for item in crc_body if item["opcode"] == "dec"
            for match in [DIRECT_OPERAND_RE.match(str(item["operand"]))]
            if match
        })
        if len(crc_decrement_operands) < 2:
            errors.append(
                "resident rtov_crc_mem does not decrement both length bytes"
            )
        if not any(item["opcode"] == "inw" for item in crc_body):
            errors.append("resident rtov_crc_mem does not advance its data pointer")
    if REMOVED_TRANSIENT_CRC in symbols:
        errors.append(f"removed transient CRC helper returned: {REMOVED_TRANSIENT_CRC}")

    metrics = {
        "overlay_start": start,
        "overlay_end": end,
        "overlay_bytes": end - start,
        "overlay_entry": entry,
        "resident_overlay_control_refs": len(inbound),
        "valid_installer_entry_refs": len(valid_inbound),
        "entry_eval_refs": len(entry_calls),
        "entry_eval_opcode": entry_calls[0]["opcode"] if len(entry_calls) == 1 else None,
        "boot_phase_probe_refs": len(probe_calls),
        "defprim_call_refs": len(defprim_calls),
        "boot_functions": actual_boot_functions,
        "boot_slice_vma": start,
        "section_pins": len(SECTION_PINS),
        "resident_symbols_pinned": len(resident_present),
        "resident_symbols_absorbed": len(REQUIRED_RESIDENT) + len(TOP_LEVEL_RESIDENT_CALLERS) - len(resident_present),
        "static_reference_scope": "section-annotated-absolute-jsr-jmp",
        "runtime_crc_catalog_refs": len(crc_calls),
        "runtime_crc_instructions": len(crc_body),
        "runtime_crc_decrement_operands": crc_decrement_operands,
    }
    return errors, metrics


def _write_report(path: Path, errors: list[str], metrics: dict[str, Any]) -> None:
    value = {
        "schema": "lisp65-workbench-overlay-control-audit-v3",
        "status": "pass" if not errors else "fail",
        "metrics": metrics,
        "errors": errors,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _selftest() -> int:
    def symbol(
        address: int, size: int = 0, section: str = ".text", kind: str = "F"
    ) -> dict[str, int | str]:
        return {"address": address, "size": size, "type": kind, "section": section}

    symbols = {
        OVERLAY_START: symbol(0x9000, section=BOOT_SECTION, kind=""),
        OVERLAY_END: symbol(0x9800, section=BOOT_SECTION, kind=""),
        OVERLAY_ENTRY: symbol(0x9100, section=BOOT_SECTION),
        ENTRY: symbol(0x9100, 0x03, BOOT_SECTION),
        INSTALLER: symbol(0x7000, 0x100),
        "eval_init": symbol(0x9200, 0x80, BOOT_SECTION),
        "defprim": symbol(0x9300, 0x20, BOOT_SECTION),
        "vm_boot_fastpath_phase_verify": symbol(0x9000, 0x100, ".lisp65_rt_boot_00"),
        "vm_boot_fastpath_phase_patches": symbol(0x9000, 0x100, ".lisp65_rt_boot_01"),
        "gc_freeze_boot": symbol(0x9000, 0x20, ".lisp65_rt_boot_02"),
        "vm_boot_fastpath_phase_entries": symbol(0x9020, 0x100, ".lisp65_rt_boot_02"),
        RUNTIME_CRC: symbol(0x6800, 0x40),
        RUNTIME_CATALOG_VERIFIER: symbol(
            0x9400, 0x100, RUNTIME_CATALOG_SECTION
        ),
    }
    for index in range(3):
        section = f".lisp65_rt_boot_{index:02d}"
        symbols[f"__lisp65_rt_boot_{index:02d}_start"] = symbol(
            0x9000, section=section, kind=""
        )
        symbols[f"__lisp65_rt_boot_{index:02d}_end"] = symbol(
            0x9400, section=section, kind=""
        )
        entry_address = 0x9020 if index == 2 else 0x9000
        symbols[f"__lisp65_rt_boot_{index:02d}_entry"] = symbol(
            entry_address, section=section
        )
    for index, name in enumerate(REQUIRED_RESIDENT):
        symbols[name] = symbol(0x6000 + index * 0x20, 0x10)
    controls = [
        {"source": 0x7050, "opcode": "jsr", "target": 0x9100, "section": ".text"},
        {"source": 0x9100, "opcode": "jmp", "target": 0x9200, "section": BOOT_SECTION},
        {"source": 0x9230, "opcode": "jsr", "target": 0x9300, "section": BOOT_SECTION},
        {"source": 0x9005, "opcode": "jsr", "target": 0x9000,
         "section": ".lisp65_rt_boot_00"},
        {"source": 0x9450, "opcode": "jsr", "target": 0x6800,
         "section": RUNTIME_CATALOG_SECTION},
    ]
    instructions = [
        {"address": 0x6810, "opcode": "dec", "operand": "$8", "section": ".text"},
        {"address": 0x6814, "opcode": "dec", "operand": "$6", "section": ".text"},
        {"address": 0x6818, "opcode": "inw", "operand": "$4", "section": ".text"},
    ]

    parsed_symbols = _parse_objdump_symbols(
        "00009100 g     F .lisp65_workbench_overlay 00000003 " + ENTRY + "\n"
    )
    parsed_controls = _parse_controls(
        "Disassembly of section .text:\n  7050: jsr $9100\n"
        "Disassembly of section .lisp65_workbench_overlay:\n  9100: jmp $9200\n"
    )
    parsed_instructions = _parse_instructions(
        "Disassembly of section .text:\n  6810: dec $8 ; 0x8 <__rc6>\n"
    )
    if (parsed_symbols[ENTRY]["section"] != BOOT_SECTION or [
        item["section"] for item in parsed_controls
    ] != [".text", BOOT_SECTION] or parsed_instructions != [{
        "address": 0x6810,
        "opcode": "dec",
        "operand": "$8",
        "section": ".text",
    }]):
        print("workbench-overlay-control-audit selftest: FAIL section-parser")
        return 1

    cases = 1
    errors, _ = _audit(symbols, controls, instructions)
    if errors:
        print(f"workbench-overlay-control-audit selftest: FAIL valid={errors}")
        return 1
    cases += 1
    probe_symbols = {
        **symbols,
        "vm_boot_stack_probe_begin": symbol(0x9120, 0x10, ".lisp65_rt_boot_02"),
    }
    probe_controls = [
        *controls,
        {"source": 0x9025, "opcode": "jsr", "target": 0x9000,
         "section": ".lisp65_rt_boot_02"},
        {"source": 0x9030, "opcode": "jsr", "target": 0x9120,
         "section": ".lisp65_rt_boot_02"},
    ]
    errors, _ = _audit(probe_symbols, probe_controls, instructions)
    if errors:
        print(f"workbench-overlay-control-audit selftest: FAIL probe-valid={errors}")
        return 1
    mutations = [
        ("entry-alias", {**symbols, OVERLAY_ENTRY: symbol(0x9101, section=BOOT_SECTION)}, controls),
        ("entry-section", {**symbols, ENTRY: symbol(0x9100, 3, ".text")}, controls),
        ("extra-boot-function", {**symbols, "surprise": symbol(0x9400, 0x10, BOOT_SECTION)}, controls),
        ("missing-inbound", symbols, controls[1:]),
        ("extra-inbound", symbols, controls + [
            {"source": 0x7100, "opcode": "jsr", "target": 0x9200, "section": ".text"}
        ]),
        ("wrong-installer", symbols, [{**controls[0], "source": 0x7100}, *controls[1:]]),
        ("missing-entry-eval", symbols, [controls[0], *controls[2:]]),
        ("extra-entry-eval", symbols, controls + [{**controls[1], "source": 0x9101}]),
        ("missing-defprim", symbols, [controls[0], controls[1], controls[3]]),
        ("verify-section", {**symbols,
            "vm_boot_fastpath_phase_verify": symbol(0x9000, 0x100, ".lisp65_rt_boot_01")}, controls),
        ("freeze-section", {**symbols,
            "gc_freeze_boot": symbol(0x9000, 0x20, ".text")}, controls),
        ("slice-vma", {**symbols,
            "__lisp65_rt_boot_01_start": symbol(0x9010, section=".lisp65_rt_boot_01", kind="")}, controls),
        ("resident-section", {**symbols, "mem_init": symbol(0x6000, 0x10, BOOT_SECTION)}, controls),
        ("inbound-section", symbols, [{**controls[0], "section": ".lisp65_rt_boot_00"}, *controls[1:]]),
        ("probe-section", {**symbols,
            "vm_boot_stack_probe_begin": symbol(0x9120, 0x10, ".text")},
         probe_controls),
        ("probe-missing-call", probe_symbols, controls),
        ("probe-before-freeze", probe_symbols, [
            *controls,
            {"source": 0x9025, "opcode": "jsr", "target": 0x9000,
             "section": ".lisp65_rt_boot_02"},
            {"source": 0x9020, "opcode": "jsr", "target": 0x9120,
             "section": ".lisp65_rt_boot_02"},
        ]),
    ]
    for name, case_symbols, case_controls in mutations:
        cases += 1
        case_errors, _ = _audit(case_symbols, case_controls, instructions)
        if not case_errors:
            print(f"workbench-overlay-control-audit selftest: FAIL mutation={name}")
            return 1
    crc_mutations = [
        ("crc-call", symbols, controls[:-1], instructions),
        ("crc-section", {**symbols, RUNTIME_CRC: symbol(
            0x6800, 0x40, RUNTIME_CATALOG_SECTION)}, controls, instructions),
        ("crc-legacy", {**symbols, REMOVED_TRANSIENT_CRC: symbol(
            0x9480, 0x20, RUNTIME_CATALOG_SECTION)}, controls, instructions),
        ("crc-dew", symbols, controls, [
            {**instructions[0], "opcode": "dew", "operand": "$16"},
            *instructions[1:],
        ]),
        ("crc-one-decrement", symbols, controls, instructions[1:]),
        ("crc-no-pointer-progress", symbols, controls, instructions[:2]),
    ]
    for name, case_symbols, case_controls, case_instructions in crc_mutations:
        cases += 1
        case_errors, _ = _audit(case_symbols, case_controls, case_instructions)
        if not case_errors:
            print(f"workbench-overlay-control-audit selftest: FAIL mutation={name}")
            return 1
    print(f"workbench-overlay-control-audit selftest: PASS cases={cases}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--nm", type=Path)
    parser.add_argument("--objdump", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    missing = [name for name in ("elf", "nm", "objdump", "out") if getattr(args, name) is None]
    if missing:
        parser.error("required without --selftest: " + ", ".join("--" + name for name in missing))
    try:
        nm_symbols = _parse_symbols(
            _run([str(args.nm), "-n", "-S", "--defined-only", str(args.elf)])
        )
        objdump_symbols = _parse_objdump_symbols(
            _run([str(args.objdump), "-t", str(args.elf)])
        )
        symbols = _merge_symbols(nm_symbols, objdump_symbols)
        disassembly = _run([
            str(args.objdump), "-d", "--no-show-raw-insn", str(args.elf)
        ])
        controls = _parse_controls(disassembly)
        instructions = _parse_instructions(disassembly)
        errors, metrics = _audit(symbols, controls, instructions)
        _write_report(args.out, errors, metrics)
    except (AuditError, OSError, ValueError) as exc:
        print(f"workbench-overlay-control-audit: ERROR {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"workbench-overlay-control-audit: FAIL {error}", file=sys.stderr)
        return 1
    print(
        "workbench-overlay-control-audit: PASS "
        f"overlay={metrics['overlay_bytes']}B "
        f"resident_refs={metrics['resident_overlay_control_refs']} "
        f"entry_eval={metrics['entry_eval_opcode']} "
        f"section_pins={metrics['section_pins']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
