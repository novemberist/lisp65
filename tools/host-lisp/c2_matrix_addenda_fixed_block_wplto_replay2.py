#!/usr/bin/env python3
"""Unconsumed WPLTO run with the real 28-byte fixed-block tenant."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_fixed_block_wplto_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto-replay2")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-replay2-receipt.json")
GEOMETRY_RED = EVIDENCE / (
    "c2.2-link58-fixed-block-mod-adjust-geometry-first-red-receipt.json")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    red = json.loads(GEOMETRY_RED.read_text(encoding="utf-8"))
    require(
        red["status"].startswith(
            "FIRST RED: 30-byte mod-adjust tenant exposed")
        and red["candidate"]["real_executable_capacity_bytes"] == 28
        and red["candidate"]["overflow_bytes"] == 2
        and red["disposition"]["selected_replacement"] == "rtov_read"
        and red["execution_accounting"][
            "completed_product_closure_links"] == 0,
        "fixed-block geometry First Red authority drift")
    value["fixed_block_first_candidate_geometry_red"] = (
        BASE.BASE.BASE.BASE.BASE.P.bind(GEOMETRY_RED))
    value["replacement"] = {
        "symbol": "rtov_read",
        "bytes": 28,
        "fixed_control_target": "c2_facade_vm_code_load",
        "ordinary_text_projected_headroom_bytes": 40,
        "fixed_block_projected_headroom_bytes": 0,
        "inherited_noinit_bytes": 5,
    }
    value["driver"] = BASE.BASE.BASE.BASE.BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "fixed-block replacement WPLTO is one-shot")
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
            "c2-matrix-addenda-fixed-block-wplto-replay2: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
