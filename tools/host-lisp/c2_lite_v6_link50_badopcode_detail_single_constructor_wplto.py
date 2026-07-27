#!/usr/bin/env python3
"""Final authorized WPLTO for the single joined BADOPCODE constructor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_detail_wplto as W  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
COLD_RED = EVIDENCE / (
    "c2.2-link50-badopcode-detail-cold-wplto-"
    "capacity-first-red-analysis.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-badopcode-detail-single-constructor-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-detail-single-constructor-wplto-"
    "internal-structural.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-detail-single-constructor-wplto-receipt.json")
COLD_RED_SHA = (
    "fe774adaf2cc887d3ad8ca9b446a5d3a834da60fb56de59820ff96271e148736")


def main() -> int:
    W.require(COLD_RED.is_file() and W.sha(COLD_RED) == COLD_RED_SHA,
              "cold-branch WPLTO first-red analysis drift")
    first_red = json.loads(COLD_RED.read_text(encoding="utf-8"))
    contract = json.loads(W.CONTRACT.read_text(encoding="utf-8"))
    approved = contract["decision"]["approved_scope"]
    W.require(first_red["status"].startswith("FIRST RED:")
              and first_red["object_attribution_bytes"][0]
                  ["cold_delta_from_baseline"] == 484
              and "single_joined_noinline_constructor_form" in approved
              and "one_final_nonpromotable_product_shaped_wplto_probe"
                  in approved,
              "single-constructor WPLTO lacks exact Class-C authority")
    old = {"out": W.OUT, "internal": W.INTERNAL, "receipt": W.RECEIPT,
           "authority": W.authority}

    def authority() -> dict[str, Any]:
        value = old["authority"]()
        value["cold_branch_capacity_first_red"] = W.bind(COLD_RED)
        value["single_constructor_wplto_driver"] = W.bind(Path(__file__))
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
        print("c2-lite-v6-link50-badopcode-detail-single-constructor-wplto: "
              "FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(2)
