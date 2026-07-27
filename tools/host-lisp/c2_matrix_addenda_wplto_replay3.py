#!/usr/bin/env python3
"""Replay the unconsumed addenda WPLTO after the E5 renderer gate update."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link58-matrix-addenda-wplto-replay3"
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay3-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay3-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay3-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay2-receipt.json")
FIRST_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-replay2-internal-structural.json")
ORIGINAL_AUTHORITY = BASE.authority


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    internal = json.loads(FIRST_INTERNAL.read_text(encoding="utf-8"))
    BASE.P.require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"] ==
            "target renderer emit inventory drift"
        and internal["execution_accounting"]["product_closure_links"] == 0,
        "matrix-addenda E5 renderer First Red drift",
    )
    value["class_A_E5_renderer_checker_first_red"] = BASE.P.bind(FIRST_RED)
    value["class_A_E5_renderer_diagnosis"] = BASE.P.bind(FIRST_INTERNAL)
    value["correction"] = {
        "old_model": "pre-E5 six-JSR/one-JMP renderer inventory",
        "current_model":
            "approved depth-five suffix adds one JSR and one tail JMP; "
            "the E5 fixture proves exact code-63/Fixnum-5 qualification",
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
        "target_compiler_or_linker_runs_before_fix": 0,
    }
    value["replay_driver"] = BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    BASE.P.require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "matrix-addenda WPLTO replay3 is one-shot",
    )
    old = {
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
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
    if RECEIPT.exists():
        os.chmod(RECEIPT, 0o644)
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
        value["class_A_replay"] = {
            "cause": "pre-E5 renderer instruction inventory",
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "prior_target_compiler_or_linker_runs": 0,
        }
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(RECEIPT, 0o444)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-wplto-replay3: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
