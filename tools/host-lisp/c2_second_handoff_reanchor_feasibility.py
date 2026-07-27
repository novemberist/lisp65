#!/usr/bin/env python3
"""Paper-only feasibility map for the owner-directed second C2 reanchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / (
    "build/c2.2/substitution/l65r-v3-crc-convergence-temperature-wplto/"
    "resident-island-seed.prg.map")
SOURCE = ROOT / "src/vm_runtime_overlay.c"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v3-crc-convergence-temperature-wplto-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-second-handoff-reanchor-feasibility-receipt.json")

TEXT_START = 0x2023
CURRENT_HANDOFF = 0xB4A3
FIXED_BANK0 = 0xC080
FIXED_CODE = 0xC218
OVERLAY_VMA = 0xC356
STANDING_RESERVE = 32

SECTIONS = (
    ("handoff", ".lisp65_c2_kernal_handoff"),
    ("facade", ".lisp65_c2_host_facade"),
    ("io_reveal", ".lisp65_c2_kernal_io_reveal"),
    ("map_switch", ".lisp65_c2_kernal_map_switch"),
    ("kernal_state", ".lisp65_c2_kernal_state"),
    ("rodata", ".rodata"),
    ("verifier_bindings", ".lisp65_runtime_overlay_verifier_bindings"),
    ("data", ".data"),
    ("bss", ".bss"),
)


class FeasibilityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FeasibilityError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hx(value: int) -> str:
    return f"0x{value:04x}"


def output_sections(text: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+1\s+"
        r"(\.[A-Za-z0-9_.-]+)\s*$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            result[match.group(3)] = (
                int(match.group(1), 16), int(match.group(2), 16))
    return result


def symbol_size(text: str, symbol: str) -> int:
    pattern = re.compile(
        rf"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+1\s+"
        rf"{re.escape(symbol)}\s*$", re.MULTILINE)
    matches = pattern.findall(text)
    require(len(matches) == 1, f"map does not define {symbol} exactly once")
    return int(matches[0], 16)


def layout(anchor: int, sizes: dict[str, int]) -> list[dict[str, Any]]:
    cursor = anchor
    rows = []
    for name, _section in SECTIONS:
        size = sizes[name]
        rows.append({
            "name": name,
            "start": hx(cursor),
            "end_exclusive": hx(cursor + size),
            "bytes": size,
        })
        cursor += size
    return rows


def report() -> dict[str, Any]:
    require(MAP.is_file() and SOURCE.is_file() and FIRST_RED.is_file(),
            "temperature First-Red authority is incomplete")
    map_text = MAP.read_text(encoding="utf-8")
    sections = output_sections(map_text)
    expected = {
        ".text": (0x2023, 0x9575),
        ".lisp65_c2_kernal_handoff": (0xB4A3, 0x121),
        ".lisp65_c2_host_facade": (0xB5C4, 0x2D),
        ".lisp65_c2_kernal_io_reveal": (0xB5F1, 0x0B),
        ".lisp65_c2_kernal_map_switch": (0xB5FC, 0x0A),
        ".lisp65_c2_kernal_state": (0xB606, 0x14),
        ".rodata": (0xB70F, 0x360),
        ".lisp65_runtime_overlay_verifier_bindings": (0xBA6F, 0x20),
        ".data": (0xBA8F, 0x2A),
        ".bss": (0xBAB9, 0x638),
        ".lisp65_c2_fixed_bank0": (0xC080, 0x198),
        ".lisp65_c2_fixed_bank0_code": (0xC218, 0x2D),
    }
    for name, geometry in expected.items():
        require(sections.get(name) == geometry,
                f"temperature map geometry drift for {name}: "
                f"{sections.get(name)} != {geometry}")

    cold_helper = symbol_size(map_text, "rtov_crc_byte")
    require(cold_helper == 38, "cold-helper attribution drift")
    sizes = {name: sections[section][1] for name, section in SECTIONS}
    projected_text_bytes = sections[".text"][1] - cold_helper
    projected_text_end = TEXT_START + projected_text_bytes
    required_anchor = projected_text_end + STANDING_RESERVE
    downstream_bytes = sum(sizes.values())
    maximum_anchor = FIXED_BANK0 - downstream_bytes
    required_shift = required_anchor - CURRENT_HANDOFF
    maximum_shift = maximum_anchor - CURRENT_HANDOFF
    shortfall = required_anchor - maximum_anchor

    require(required_anchor == 0xB592 and maximum_anchor == 0xB527,
            "second-reanchor arithmetic drift")
    require(shortfall == 107 and projected_text_end - maximum_anchor == 75,
            "second-reanchor shortfall drift")

    required_layout = layout(required_anchor, sizes)
    maximum_layout = layout(maximum_anchor, sizes)
    require(required_layout[-1]["end_exclusive"] == "0xc0eb",
            "required layout end drift")
    require(maximum_layout[-1]["end_exclusive"] == "0xc080",
            "maximum layout does not end at fixed Bank-0")

    active_pin_files = [
        "config/c2-handoff-reanchor-authorization.json",
        "config/c2-kernal-unmap-contract.json",
        "docs/planning/c2.2-kernal-unmap-contract.md",
        "docs/planning/c2.2-link33-coordinated-residency-plan.md",
        "tools/host-lisp/c2_crc_asm_leaf_successor_link.py",
        "tools/host-lisp/c2_crc_asm_leaf_wplto_probe.py",
        "tools/host-lisp/c2_crc_asm_leaf_wplto_replay.py",
        "tools/host-lisp/c2_crc_codegen_correction_wplto_probe.py",
        "tools/host-lisp/c2_handoff_reanchor_feasibility.py",
        "tools/host-lisp/c2_handoff_reanchor_wplto_probe.py",
        "tools/host-lisp/c2_link33_handoff_reanchor_product_link.py",
        "tools/host-lisp/c2_product_substitution_link.py",
    ]
    for relative in active_pin_files:
        require((ROOT / relative).is_file(), f"active pin file absent: {relative}")

    return {
        "format": "lisp65-c2-second-handoff-reanchor-feasibility-v1",
        "recorded_on": "2026-07-21",
        "status": "not-feasible-current-pocket",
        "claim_limit": (
            "Paper-only map arithmetic. No source cut, compiler, linker, "
            "product identity or hardware execution."),
        "authority": {
            "temperature_first_red": {
                "path": FIRST_RED.relative_to(ROOT).as_posix(),
                "sha256": sha(FIRST_RED),
            },
            "temperature_map": {
                "path": MAP.relative_to(ROOT).as_posix(),
                "sha256": sha(MAP),
            },
            "product_source": {
                "path": SOURCE.relative_to(ROOT).as_posix(),
                "sha256": sha(SOURCE),
            },
        },
        "favorable_assumptions": {
            "cold_helper_removed_from_resident_text_bytes": cold_helper,
            "island_split_resident_delta_bytes": 0,
            "all_other_section_sizes": "held at the measured temperature-map values",
            "standing_lto_noise_reserve_bytes": STANDING_RESERVE,
        },
        "text": {
            "measured_bytes": sections[".text"][1],
            "projected_after_cold_move_bytes": projected_text_bytes,
            "projected_end_exclusive": hx(projected_text_end),
            "required_handoff_with_reserve": hx(required_anchor),
        },
        "pocket": {
            "downstream_bytes_handoff_through_bss": downstream_bytes,
            "current_anchor": hx(CURRENT_HANDOFF),
            "maximum_anchor_without_moving_c080": hx(maximum_anchor),
            "required_shift_bytes": required_shift,
            "maximum_absorbable_shift_bytes": maximum_shift,
            "shortfall_with_32_byte_reserve": shortfall,
            "shortfall_even_with_zero_reserve": projected_text_end - maximum_anchor,
        },
        "required_layout": required_layout,
        "maximum_absorbable_layout": maximum_layout,
        "fixed_points": {
            "fixed_bank0": hx(FIXED_BANK0),
            "fixed_code": hx(FIXED_CODE),
            "runtime_overlay_vma": hx(OVERLAY_VMA),
            "movement": "forbidden and not modeled",
        },
        "repin_inventory_if_reauthorized_after_new_capacity_decision": {
            "active_files": active_pin_files,
            "active_file_count": len(active_pin_files),
            "facade_vectors": 15,
            "publish_last_domains": 3,
            "historical_receipts": "immutable; never repinned",
        },
        "decision": {
            "owner_precondition": "failed",
            "reason": (
                "The required 0xb592 anchor would end ordinary BSS at "
                "0xc0eb, 107 bytes inside the fixed 0xc080 block. Even "
                "discarding the 32-byte reserve leaves a 75-byte collision."),
            "source_cuts": "not authorized after failed feasibility precondition",
            "next_gate": "Class-C review with the 107-byte positional shortfall",
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes": 0,
            "hardware_runs": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    require(args.run, "paper probe requires explicit --run")
    require(not RECEIPT.exists(), "second-reanchor feasibility already recorded")
    value = report()
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
