#!/usr/bin/env python3
"""Class-A replay of the unconsumed Link-39 product-link authorization."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_real_abi_direct_entry_contract as CURRENT  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_successor_link as LINK  # noqa: E402


FIRST_RED = LINK.RECEIPT
FIRST_RED_SHA = (
    "464cc1ce66aa9cf4a9dca27cb4f01da5d4883d71503908f3ae0ba0a5c8834f60")
CURRENT_RECEIPT_SHA = (
    "f50fe4721727b9fa5ab3d10457b3f067154d3c926f4159cbc271522881b8a0f9")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-39-c2-lite-v6-real-abi-replay")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link39-c2-lite-v6-real-abi-replay-structural-receipt.json")
DIAGNOSIS = LINK.EVIDENCE / (
    "c2.2-product-link39-c2-lite-v6-real-abi-prelink-"
    "authority-diagnosis.json")


def record_diagnosis() -> dict[str, Any]:
    LINK.require(LINK.sha(FIRST_RED) == FIRST_RED_SHA,
                 "Link-39 prelink First-Red receipt drift")
    LINK.require(LINK.sha(CURRENT.RECEIPT) == CURRENT_RECEIPT_SHA,
                 "current v6 direct-entry authority drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.RECEIPT.read_text(encoding="utf-8"))
    LINK.require(
        first["status"] == "FIRST RED: C2-lite real-ABI Link 39 stopped"
        and first["diagnostic"] == {
            "type": "RebindError",
            "message": (
                "unexpected direct-entry rebind surface: "
                "['target_contract_harness', 'target_decoder']"),
        }
        and first["execution_accounting"]["product_closure_links"] == 0,
        "unexpected Link-39 prelink First-Red class")
    LINK.require(
        current["status"] ==
            "passed-current-v6-root-surrogate-direct-entry-contract"
        and current["cross_parity"]["direct_entry_references"] == 637
        and current["cross_parity"]["fixnum_decodable_published_values"] == 0
        and current["cross_parity"]["target_phase12_negative_classes"] == 4,
        "current-v6 direct-entry authority is not green")
    value = {
        "format": "lisp65-c2-lite-v6-link39-prelink-authority-disposition-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-class-a-current-v6-direct-entry-rebind-link-unconsumed",
        "class": "A",
        "first_red": LINK.bind(FIRST_RED),
        "diagnosis": {
            "failed_check": "historical hot-refill rebind-surface inventory",
            "cause": (
                "The C2-lite wrapper called the older hot-refill receipt "
                "builder, whose allowed source delta predates the later v6 "
                "root-surrogate harness branch."),
            "correction": (
                "Use a current source authority that reruns all 637 references "
                "and four negative classes, while the generated product gate "
                "still checks the v6 phase-8/12 truth after the link."),
            "product_semantics_changed": False,
        },
        "current_direct_entry_authority": LINK.bind(CURRENT.RECEIPT),
        "scope": {
            "product_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "authorization_effect": (
            "The exactly-one Link-39 product-link authorization remains "
            "unconsumed."),
    }
    LINK.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)
    return value


def main() -> int:
    LINK.require(FIRST_RED.is_file() and CURRENT.RECEIPT.is_file()
                 and not OUT.exists() and not RECEIPT.exists()
                 and not DIAGNOSIS.exists(),
                 "Link-39 Class-A replay state is not one-shot")
    record_diagnosis()
    old_out, old_receipt = LINK.OUT, LINK.RECEIPT
    old_prerequisites = LINK.prerequisites
    old_value = LINK.LITE_DIRECT.value
    old_direct_receipt = LINK.LITE_DIRECT.RECEIPT
    old_single_link = LINK.P.single_link

    def prerequisites() -> dict[str, Any]:
        value = old_prerequisites()
        value["class_a_prelink_authority_disposition"] = LINK.bind(DIAGNOSIS)
        value["current_v6_direct_entry_authority"] = LINK.bind(
            CURRENT.RECEIPT)
        value["replay_driver"] = LINK.bind(Path(__file__))
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        kwargs["direct_entry_receipt"] = CURRENT.RECEIPT
        kwargs["direct_entry_check_tool"] = (
            "c2_lite_v6_real_abi_direct_entry_contract.py")
        return old_single_link(*args, **kwargs)

    try:
        LINK.OUT, LINK.RECEIPT = OUT, RECEIPT
        LINK.prerequisites = prerequisites
        LINK.LITE_DIRECT.value = CURRENT.value
        LINK.LITE_DIRECT.RECEIPT = CURRENT.RECEIPT
        LINK.P.single_link = single_link
        value = LINK.build()
    finally:
        LINK.OUT, LINK.RECEIPT = old_out, old_receipt
        LINK.prerequisites = old_prerequisites
        LINK.LITE_DIRECT.value = old_value
        LINK.LITE_DIRECT.RECEIPT = old_direct_receipt
        LINK.P.single_link = old_single_link
    print("c2-lite-v6-rtov-crc-real-abi-successor-link-replay: "
          + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
