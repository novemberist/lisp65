#!/usr/bin/env python3
"""Class-A replay of Link 44 after qualifying the stale authority gate."""

from __future__ import annotations

import json
from pathlib import Path

import c2_lite_v6_bank2_target_stage_successor_link as LINK44


ROOT = LINK44.ROOT
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-44-c2-lite-v6-bank2-target-stage-replay")
RECEIPT = LINK44.LINK.EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-bank2-target-stage-replay-"
    "structural-receipt.json")
FIRST_RED = LINK44.LINK.EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-bank2-target-stage-"
    "structural-receipt.json")
FIRST_RED_SHA = (
    "20cdb81cb58b3803b91f4f289aecf21a04f73c17ca153199ff0dbe774a5039b8")


def main() -> int:
    old_out, old_receipt = LINK44.OUT, LINK44.RECEIPT
    old_prerequisites = LINK44.prerequisites

    def prerequisites() -> dict[str, object]:
        value = old_prerequisites()
        LINK44.LINK.require(
            FIRST_RED.is_file()
            and LINK44.LINK.sha(FIRST_RED) == FIRST_RED_SHA,
            "Link-44 stale-authority First Red drift")
        first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
        LINK44.LINK.require(
            first["status"] == "FIRST RED: C2-lite real-ABI Link 44 stopped"
            and first["diagnostic"]["message"] ==
                "co-resident source contract red: ['class_c_authority']"
            and first["execution_accounting"]["product_closure_links"] == 0,
            "Link-44 First Red is not the Class-A authority-only stop")
        value["stale_authority_gate_first_red"] = LINK44.LINK.bind(FIRST_RED)
        value["class_a_replay_driver"] = LINK44.LINK.bind(Path(__file__))
        return value

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = RECEIPT
        LINK44.prerequisites = prerequisites
        return LINK44.main()
    finally:
        LINK44.OUT = old_out
        LINK44.RECEIPT = old_receipt
        LINK44.prerequisites = old_prerequisites


if __name__ == "__main__":
    raise SystemExit(main())
