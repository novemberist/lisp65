#!/usr/bin/env python3
"""Class-A prelink-authority replay of the unconsumed Link-38 program."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_boot_crc_abi_successor_link as LINK  # noqa: E402


FIRST_RED = LINK.RECEIPT
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-38-c2-lite-v6-boot-crc-abi-replay")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-replay-structural-receipt.json")
DIAGNOSIS = LINK.EVIDENCE / (
    "c2.2-product-link38-c2-lite-v6-boot-crc-abi-prelink-authority-diagnosis.json")


def record_diagnosis() -> dict[str, Any]:
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    LINK.require(first["status"] ==
                 "FIRST RED: C2-lite boot-CRC ABI successor link stopped"
                 and first["diagnostic"]["message"] ==
                    "co-resident source contract red: ['class_c_authority']"
                 and first["execution_accounting"]["product_closure_links"] == 0,
                 "prelink authority First Red drift")
    contract = json.loads(
        (ROOT / "config/c2-lite-execution-contract.json").read_text(
            encoding="utf-8"))
    LINK.require(contract["status"] ==
                 "class-c-approved-bank3-stage-wplto-probe-authorized"
                 and contract["coresident_aggregate_diet"]
                    ["runtime_slice_cap_bytes"] == LINK.CAP
                 and contract["coresident_aggregate_diet"]
                    ["bank_layout_change_authorized"] is False,
                 "current C2-lite authority content drift")
    value = {
        "format": "lisp65-c2-lite-link38-prelink-authority-disposition-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-class-a-current-contract-status-rebind-link-unconsumed",
        "class": "A",
        "first_red": LINK.bind(FIRST_RED),
        "diagnosis": {
            "failed_check": "co-resident source contract class_c_authority",
            "historical_allowed_statuses": [
                "class-c-approved-coresident-aggregate-diet-wplto-probe-authorized",
                "class-c-approved-first-product-link-authorized"],
            "current_status": contract["status"],
            "correction": (
                "Recognize the current Bank-3 stage Class-C contract status; "
                "all capacity, cap, pack-quantum and bank-layout assertions "
                "remain unchanged."),
        },
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0},
        "authorization_effect": (
            "The exactly-one Link-38 product-link authorization remains "
            "unconsumed."),
    }
    LINK.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)
    return value


def main() -> int:
    LINK.require(FIRST_RED.is_file() and not OUT.exists()
                 and not RECEIPT.exists() and not DIAGNOSIS.exists(),
                 "Link-38 authority replay state is not one-shot")
    record_diagnosis()
    old_out, old_receipt = LINK.OUT, LINK.RECEIPT
    old_prerequisites = LINK.prerequisites

    def prerequisites() -> dict[str, Any]:
        value = old_prerequisites()
        value["class_a_prelink_authority_disposition"] = LINK.bind(DIAGNOSIS)
        value["replay_driver"] = LINK.bind(Path(__file__))
        return value

    try:
        LINK.OUT, LINK.RECEIPT = OUT, RECEIPT
        LINK.prerequisites = prerequisites
        value = LINK.build()
    finally:
        LINK.OUT, LINK.RECEIPT = old_out, old_receipt
        LINK.prerequisites = old_prerequisites
    print("c2-lite-v6-boot-crc-abi-successor-link-replay: "
          + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
