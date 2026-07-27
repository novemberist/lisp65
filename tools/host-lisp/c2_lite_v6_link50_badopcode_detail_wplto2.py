#!/usr/bin/env python3
"""Run the still-unconsumed BADOPCODE WPLTO after the bound prelink fix."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_detail_wplto as W  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CORRECTION = EVIDENCE / (
    "c2.2-link50-badopcode-detail-wplto-prelink-accounting-correction.json")
OUT = ROOT / "build/c2.2/substitution/link50-badopcode-detail-wplto2"
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-detail-wplto2-internal-structural.json")
RECEIPT = EVIDENCE / "c2.2-link50-badopcode-detail-wplto2-receipt.json"
CORRECTION_SHA = (
    "2dc7bbf8d043a3f7f903e1202b72101360f69b3cf02942ad73f59fa33e848875")


def main() -> int:
    W.require(CORRECTION.is_file() and W.sha(CORRECTION) == CORRECTION_SHA,
              "qualified prelink accounting correction drift")
    correction = json.loads(CORRECTION.read_text(encoding="utf-8"))
    W.require(correction["status"] ==
                  "corrected-prelink-first-red-WPLTO-unconsumed"
              and correction["corrected_execution_accounting"]
                  ["whole_program_lto_closure_links"] == 0
              and correction["corrected_execution_accounting"]
                  ["authorized_wplto_probe_consumed"] is False,
              "prelink correction does not authorize the unconsumed WPLTO")
    old = {"out": W.OUT, "internal": W.INTERNAL, "receipt": W.RECEIPT,
           "authority": W.authority}

    def authority() -> dict[str, Any]:
        value = old["authority"]()
        value["qualified_prelink_accounting_correction"] = W.bind(CORRECTION)
        value["qualified_wplto_driver"] = W.bind(Path(__file__))
        return value

    try:
        W.OUT = OUT
        W.INTERNAL = INTERNAL
        W.RECEIPT = RECEIPT
        W.authority = authority
        return W.main()
    finally:
        W.OUT = old["out"]
        W.INTERNAL = old["internal"]
        W.RECEIPT = old["receipt"]
        W.authority = old["authority"]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (W.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link50-badopcode-detail-wplto2: FAIL: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
