#!/usr/bin/env python3
"""Replay the unconsumed current-product WPLTO after a Class-A gate fix."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link57_l_full_keymap_current_product_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-current-product-wplto2")
INTERNAL = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto2-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-current-product-wplto2-receipt.json")
FIRST_RED = BASE.RECEIPT
CORRECTED_GATE = ROOT / (
    "tools/host-lisp/"
    "c2_lite_v6_bank2_target_stage_phase02b_wplto.py")
BASE_AUTHORITY = BASE.authority


def authority() -> dict[str, Any]:
    value = BASE_AUTHORITY()
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    BASE.require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and first["internal_receipt"] is not None,
        "Class-A static-plane checker First Red drift",
    )
    value["class_A_static_plane_checker_first_red"] = BASE.P.bind(FIRST_RED)
    value["corrected_bank2_dataflow_gate"] = BASE.P.bind(CORRECTED_GATE)
    value["replay_driver"] = BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    BASE.require(not OUT.exists() and not INTERNAL.exists()
                 and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
                 "current-product WPLTO replay is one-shot")
    original = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        result = BASE.main()
    finally:
        BASE.OUT = original["out"]
        BASE.INTERNAL = original["internal"]
        BASE.BASE_RECEIPT = original["base_receipt"]
        BASE.RECEIPT = original["receipt"]
        BASE.authority = original["authority"]
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o644)
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
        value["class_A_replay"] = {
            "first_attempt_target_compiler_runs": 0,
            "first_attempt_target_linker_runs": 0,
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "correction": (
                "the phase-02b/03b gate now recognizes the structured "
                "canonical static-plane macro instead of historical 34403UL"),
        }
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        BASE.WPLTOError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-current-product-WPLTO-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
