#!/usr/bin/env python3
"""Bind the real .noinit overlap that rejected the first fixed-block tenant."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ATTEMPT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay-internal.json")
PUBLIC = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay-receipt.json")
STDERR = ATTEMPT / "resident-island-seed.prg.link.stderr.txt"
LTO = ATTEMPT / "resident-island-seed.prg.lto.o"
LINKER = ATTEMPT / "c2-substitution.ld"
RECEIPT = EVIDENCE / (
    "c2.2-link58-fixed-block-mod-adjust-geometry-first-red-receipt.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"first-red evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    require(not RECEIPT.exists(), "fixed-block geometry receipt is one-shot")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))
    stderr = STDERR.read_text(encoding="utf-8")
    require(
        public["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["status"] ==
            "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and internal["diagnostic"]["message"] ==
            "link command failed before orphan-wrapper acceptance: exit=1"
        and internal["execution_accounting"]["product_closure_links"] == 0
        and ".noinit range is [0xC353, 0xC358]" in stderr
        and ".lisp65_rt_buffer_alloc range is [0xC356, 0xC9F3]"
            in stderr
        and "resident/noinit state overlaps the fixed runtime-overlay VMA"
            in stderr,
        "fixed-block geometry First Red drift")
    value = {
        "format": "lisp65-c2-link58-fixed-block-geometry-first-red-v1",
        "recorded_on": "2026-07-23",
        "status":
            "FIRST RED: 30-byte mod-adjust tenant exposed six inherited "
            "noinit bytes plus overlay alignment and missed the floor by "
            "four bytes",
        "promotable": False,
        "candidate": {
            "symbol": "lisp65_mod_adjust_tagged",
            "bytes": 30,
            "nominal_pocket_bytes": 33,
            "previously_unpriced_noinit_bytes": 6,
            "real_executable_capacity_bytes": 26,
            "overlay_floor_deficit_bytes": 4,
        },
        "measured_geometry": {
            "fixed_code_end_exclusive": "0xc263",
            "hot_bss_end_exclusive": "0xc353",
            "noinit": {
                "start": "0xc353",
                "end_exclusive": "0xc358",
                "bytes": 6,
            },
            "aligned_overlay_floor": "0xc35a",
            "runtime_overlay_vma": "0xc356",
        },
        "disposition": {
            "candidate": "rejected-before-product-link",
            "replacement_rule":
                "same owner-authorized fixed-block placement, choose one "
                "20..26-byte fixed-target resident function",
            "selected_replacement": "rtov_fail",
            "selected_bytes": 21,
            "selected_fixed_target": "rtov_wipe",
            "floor_anchor_or_shaving_changes": 0,
        },
        "authority": {
            "public_first_red": bind(PUBLIC),
            "internal_diagnosis": bind(INTERNAL),
            "linker_stderr": bind(STDERR),
            "WPLTO_object": bind(LTO),
            "generated_linker_script": bind(LINKER),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "whole_program_link_attempts": 1,
            "completed_product_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "next_gate":
            "one unconsumed WPLTO truth run with the 21-byte replacement",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-fixed-block-mod-adjust-first-red: PASS bound floor-deficit=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
