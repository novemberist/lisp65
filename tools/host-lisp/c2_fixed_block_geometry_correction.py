#!/usr/bin/env python3
"""Bind the corrected six-byte noinit/alignment geometry from both First Reds."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OLD_RECEIPT = EVIDENCE / (
    "c2.2-link58-fixed-block-mod-adjust-geometry-first-red-receipt.json")
MOD_ATTEMPT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay")
READ_ATTEMPT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-final")
READ_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-final-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-fixed-block-geometry-correction-receipt.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"geometry authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    require(not RECEIPT.exists(), "geometry correction receipt is one-shot")
    old = json.loads(OLD_RECEIPT.read_text(encoding="utf-8"))
    mod_stderr = (MOD_ATTEMPT /
                  "resident-island-seed.prg.link.stderr.txt").read_text(
                      encoding="utf-8")
    read_stderr = (READ_ATTEMPT /
                   "resident-island-seed.prg.link.stderr.txt").read_text(
                       encoding="utf-8")
    read_map = (READ_ATTEMPT /
                "resident-island-seed.prg.map").read_text(encoding="utf-8")
    read_internal = json.loads(READ_INTERNAL.read_text(encoding="utf-8"))
    require(
        old["candidate"]["previously_unpriced_noinit_bytes"] == 5
        and ".noinit range is [0xC353, 0xC358]" in mod_stderr
        and ".noinit range is [0xC351, 0xC356]" in read_stderr
        and "    c351     c351        6     1 .noinit" in read_map
        and "__lisp65_workbench_overlay_min_start = "
            "ALIGN(__lisp65_workbench_noinit_end + 1, 2)" in read_map
        and read_internal["execution_accounting"][
            "product_closure_links"] == 0,
        "fixed-block correction source drift")
    value = {
        "format": "lisp65-c2-link58-fixed-block-geometry-correction-v1",
        "recorded_on": "2026-07-23",
        "status":
            "corrected-before-successor-WPLTO-six-byte-noinit-and-aligned-floor",
        "promotable": False,
        "correction": {
            "superseded_display_fields": {
                "noinit_bytes": 5,
                "executable_capacity_bytes": 28,
                "overflow_bytes": 2,
            },
            "linker_truth": {
                "noinit_bytes": 6,
                "overlay_floor_formula": "ALIGN(__noinit_end + 1, 2)",
                "mod_adjust_30_floor": "0xc35a",
                "mod_adjust_30_deficit_bytes": 4,
                "rtov_read_28_floor": "0xc358",
                "rtov_read_28_deficit_bytes": 2,
            },
            "selected_tenant": {
                "symbol": "rtov_fail",
                "bytes": 21,
                "fixed_control_target": "rtov_wipe",
                "projected_overlay_floor": "0xc352",
                "projected_fixed_headroom_bytes": 4,
                "projected_text_headroom_bytes": 33,
            },
        },
        "history_rule":
            "The immutable earlier receipt remains a record of its displayed "
            "interpretation; this SHA-bound correction is the current geometry "
            "authority and does not rewrite history.",
        "authority": {
            "superseded_receipt": bind(OLD_RECEIPT),
            "mod_adjust_linker_stderr": bind(
                MOD_ATTEMPT / "resident-island-seed.prg.link.stderr.txt"),
            "mod_adjust_linker_script": bind(
                MOD_ATTEMPT / "c2-substitution.ld"),
            "rtov_read_internal": bind(READ_INTERNAL),
            "rtov_read_linker_map": bind(
                READ_ATTEMPT / "resident-island-seed.prg.map"),
            "rtov_read_linker_stderr": bind(
                READ_ATTEMPT / "resident-island-seed.prg.link.stderr.txt"),
            "rtov_read_linker_script": bind(
                READ_ATTEMPT / "c2-substitution.ld"),
            "driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "new_compiler_runs": 0,
            "new_linker_runs": 0,
            "product_bytes": 0,
            "hardware_runs": 0,
        },
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-fixed-block-geometry-correction: PASS noinit=6 fixed=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
