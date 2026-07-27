#!/usr/bin/env python3
"""Class-A replay after teaching the inherited preflight the current pin."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_fixed_block_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay-receipt.json")
PREFLIGHT_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-receipt.json")
PREFLIGHT_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-internal.json")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    red = json.loads(PREFLIGHT_RED.read_text(encoding="utf-8"))
    internal = json.loads(PREFLIGHT_INTERNAL.read_text(encoding="utf-8"))
    require(
        red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["status"] ==
            "FIRST RED: C2-lite real-ABI Link 50 stopped"
        and internal["diagnostic"]["message"] ==
            "Link-33 fixed hot-block configuration drift"
        and internal["execution_accounting"]["product_closure_links"] == 0,
        "fixed-block preflight First Red drift")
    value["class_A_fixed_pin_preflight_first_red"] = (
        BASE.BASE.BASE.BASE.P.bind(PREFLIGHT_RED))
    value["class_A_fixed_pin_preflight_diagnosis"] = (
        BASE.BASE.BASE.BASE.P.bind(PREFLIGHT_INTERNAL))
    value["class_A_fixed_pin_correction"] = {
        "old_private_expectation_bytes": 33,
        "canonical_current_expectation_bytes": 3,
        "source":
            "config/c2-kernal-unmap-contract.json current Link-58 object",
        "product_bytes": 0,
        "closure_links_before_replay": 0,
    }
    value["driver"] = BASE.BASE.BASE.BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "fixed-block WPLTO replay is one-shot")
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
        return BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-fixed-block-wplto-replay: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
