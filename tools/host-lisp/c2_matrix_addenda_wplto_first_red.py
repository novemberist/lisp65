#!/usr/bin/env python3
"""Attribute the immutable matrix-addenda WPLTO capacity First Red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CURRENT = ROOT / (
    "build/c2.2/substitution/link58-matrix-addenda-wplto-replay3")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-wplto2")
CURRENT_MAP = CURRENT / "resident-island-seed.prg.map"
BASELINE_MAP = BASELINE / "resident-island-seed.prg.map"
CURRENT_LTO = CURRENT / "resident-island-seed.prg.lto.o"
BASELINE_LTO = BASELINE / "resident-island-seed.prg.lto.o"
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay3-receipt.json")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay3-internal-structural.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-capacity-first-red-receipt.json")
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"


class DiagnosisError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def map_rows(path: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        r"(\.[A-Za-z0-9_.$-]+)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(4) not in rows:
            rows[match.group(4)] = {
                "address": int(match.group(1), 16),
                "load_address": int(match.group(2), 16),
                "bytes": int(match.group(3), 16),
            }
    return rows


def symbols(path: Path) -> dict[str, int]:
    output = subprocess.run(
        [str(NM), "-S", "--size-sort", str(path)],
        cwd=ROOT, text=True, capture_output=True, check=True).stdout
    result: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            try:
                result[fields[3]] = int(fields[1], 16)
            except ValueError:
                pass
    return result


def main() -> int:
    require(not RECEIPT.exists(), "capacity First-Red receipt is one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"] ==
            "link command failed before orphan-wrapper acceptance: exit=1",
        "bound WPLTO First Red drift",
    )
    before = map_rows(BASELINE_MAP)
    after = map_rows(CURRENT_MAP)
    before_symbols = symbols(BASELINE_LTO)
    after_symbols = symbols(CURRENT_LTO)

    text_end = after[".text"]["address"] + after[".text"]["bytes"]
    text_headroom = 0xB4A3 - text_end
    window_headroom = 58 - (
        after[".lisp65_c2_kernal_window.c2_resident"]["bytes"]
        - before[".lisp65_c2_kernal_window.c2_resident"]["bytes"]
        + 6)
    require(
        before[".text"]["bytes"] == 0x945A
        and after[".text"]["bytes"] == 0x947A
        and text_headroom == 6
        and window_headroom == 42
        and after[".lisp65_c2_kernal_window.reopen_gap0"]["address"]
            == 0xFCAE
        and after[".lisp65_c2_kernal_window.session_emitter_state"]["address"]
            == 0xFD22,
        "map attribution drift",
    )
    symbol_delta = {
        name: after_symbols.get(name, 0) - before_symbols.get(name, 0)
        for name in (
            "main", "c2_product_install", "c2_append_begin",
            "c2_append_reserve_transient_bounds_phase", "l65e_table")
    }
    require(
        symbol_delta == {
            "main": 5,
            "c2_product_install": 27,
            "c2_append_begin": 10,
            "c2_append_reserve_transient_bounds_phase": 6,
            "l65e_table": 29,
        },
        "symbol attribution drift",
    )
    value = {
        "format": "lisp65-c2.2-matrix-addenda-WPLTO-first-red-v1",
        "recorded_on": "2026-07-23",
        "status": "FIRST RED: two bound resident walls exceeded",
        "promotable": False,
        "authority": {
            "attempt_receipt": bind(FIRST_RED),
            "internal_receipt": bind(INTERNAL),
            "baseline_map": bind(BASELINE_MAP),
            "current_map": bind(CURRENT_MAP),
            "baseline_LTO_object": bind(BASELINE_LTO),
            "current_LTO_object": bind(CURRENT_LTO),
            "driver": bind(Path(__file__)),
        },
        "walls": {
            "bank0_text": {
                "baseline_headroom_bytes": 38,
                "measured_headroom_bytes": text_headroom,
                "required_noise_headroom_bytes": 32,
                "deficit_bytes": 32 - text_headroom,
                "verdict": "red",
            },
            "E000": {
                "baseline_headroom_bytes": 58,
                "measured_headroom_bytes": window_headroom,
                "required_floor_bytes": 54,
                "deficit_bytes": 54 - window_headroom,
                "overlap": {
                    "reopen_gap0": "$fcae..$fd2d",
                    "session_emitter_state": "$fd22..$fd2b",
                    "bytes": 12,
                },
                "verdict": "red",
            },
            "ordinary_BSS": {"headroom_bytes": 213, "verdict": "green"},
            "fixed_hot_block": {"headroom_bytes": 33, "verdict": "green"},
            "resident_island": {"headroom_bytes": 5, "verdict": "green"},
            "session_family": {
                "bytes": 65438,
                "headroom_bytes": 98,
                "reason":
                    "E5 grew 971->977 and L65E 1143->1204; both remain "
                    "inside their existing 256-byte pack quanta",
                "verdict": "green",
            },
        },
        "attribution": {
            "ordinary_text_delta_bytes": 32,
            "ordinary_text": {
                "D3_main_selector": symbol_delta["main"],
                "E5_product_install": symbol_delta["c2_product_install"],
            },
            "E000_delta_bytes": 16,
            "E000": {
                "B3_D3_queue_irq_seam_net": 6,
                "E5_append_begin": symbol_delta["c2_append_begin"],
            },
            "pack_neutral": {
                "E5_transient_reserve_delta":
                    symbol_delta["c2_append_reserve_transient_bounds_phase"],
                "E5_L65E_table_delta": symbol_delta["l65e_table"],
                "L65E_total_delta_bytes": 61,
            },
        },
        "gates_before_capacity_red": {
            "B3_D3": "host green; hardware pending",
            "C3": "host owner matrix green; H1/H2/H3 pending",
            "E5": "host+MOS green; hardware depth-five pending",
        },
        "execution_accounting": {
            "prelink_class_A_replays": 3,
            "whole_program_LTO_attempts": 1,
            "successful_product_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "stop_rule": (
            "Class-C product-capacity question: stop before successor link "
            "and all C1/B3/C3/D3/E5 hardware cutpoints"),
        "rollback_line": "Link 57 remains untouched",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-wplto-first-red: "
        "TEXT=6/32 (-26) E000=42/54 (-12) "
        "BSS=213 FIXED=33 ISLAND=5 SESSION=98")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiagnosisError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(
            "c2-matrix-addenda-wplto-first-red: FAIL: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
