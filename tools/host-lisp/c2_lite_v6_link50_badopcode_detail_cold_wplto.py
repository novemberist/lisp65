#!/usr/bin/env python3
"""One authorized WPLTO for the cold-branch BADOPCODE detail cut."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link50_badopcode_detail_wplto as W  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FIRST_RED = EVIDENCE / (
    "c2.2-link50-badopcode-detail-wplto2-capacity-first-red-analysis.json")
OUT = ROOT / "build/c2.2/substitution/link50-badopcode-detail-cold-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link50-badopcode-detail-cold-wplto-internal-structural.json")
RECEIPT = EVIDENCE / (
    "c2.2-link50-badopcode-detail-cold-wplto-receipt.json")
FIRST_RED_SHA = (
    "33308bccb484255b127ca679d69a6954ea491fdb0e7b72715fc8e8dd081acb22")


def main() -> int:
    W.require(FIRST_RED.is_file() and W.sha(FIRST_RED) == FIRST_RED_SHA,
              "hot-path WPLTO first-red analysis drift")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    contract = json.loads(W.CONTRACT.read_text(encoding="utf-8"))
    approved = contract["decision"]["approved_scope"]
    W.require(first_red["status"].startswith("FIRST RED:")
              and first_red["object_attribution_bytes"][0] == {
                  "symbol": "vm_run_inner", "before": 7934,
                  "after": 8447, "delta": 513,
                  "temperature": "hot VM dispatch"}
              and "cold_branch_detail_setup_with_cursor_only_common_done"
                  in approved
              and "one_successor_nonpromotable_product_shaped_wplto_probe"
                  in approved,
              "cold-branch successor WPLTO lacks exact Class-C authority")
    old = {"out": W.OUT, "internal": W.INTERNAL, "receipt": W.RECEIPT,
           "authority": W.authority}

    def authority() -> dict[str, Any]:
        value = old["authority"]()
        value["hot_path_capacity_first_red"] = W.bind(FIRST_RED)
        value["cold_branch_wplto_driver"] = W.bind(Path(__file__))
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
        print("c2-lite-v6-link50-badopcode-detail-cold-wplto: FAIL: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
