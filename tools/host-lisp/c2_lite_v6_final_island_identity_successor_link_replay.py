#!/usr/bin/env python3
"""Class-A authority replay of the unconsumed Link-42 program."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_final_island_identity_successor_link as DRIVER  # noqa: E402


FIRST_RED = DRIVER.RECEIPT
FIRST_RED_SHA = (
    "4b68eb531c03d645c887d126d9e2f4df087dab80d0d702091048a904e35a33a8")
DIAGNOSIS = DRIVER.LINK.EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-"
    "prelink-authority-diagnosis.json")
DRIVER.OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-42-c2-lite-v6-final-island-identity-replay")
DRIVER.RECEIPT = DRIVER.LINK.EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-"
    "replay-structural-receipt.json")


def record_diagnosis() -> dict[str, Any]:
    DRIVER.LINK.require(FIRST_RED.is_file() and
                        DRIVER.LINK.sha(FIRST_RED) == FIRST_RED_SHA,
                        "Link-42 prelink First Red drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    contract = json.loads(DRIVER.CONTRACT.read_text(encoding="utf-8"))
    DRIVER.LINK.require(
        first["status"] == "FIRST RED: C2-lite real-ABI Link 42 stopped"
        and first["diagnostic"]["message"] ==
            "co-resident source contract red: ['class_c_authority']"
        and first["execution_accounting"]["product_closure_links"] == 0
        and contract["status"] ==
            "class-c-approved-final-island-carrier-single-runtime-identity",
        "Link-42 authority-only diagnosis is not exact")
    value = {
        "format": "lisp65-c2-lite-link42-prelink-authority-disposition-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-class-a-current-contract-status-rebind-"
                  "link-unconsumed",
        "class": "A",
        "first_red": DRIVER.LINK.bind(FIRST_RED),
        "diagnosis": {
            "failed_check": "co-resident source contract class_c_authority",
            "current_status": contract["status"],
            "correction": "Recognize the owner-approved final-carrier "
                          "status; every capacity and layout assertion stays "
                          "unchanged.",
        },
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0},
        "authorization_effect": "The one Link-42 product-link authorization "
                                "remains unconsumed.",
    }
    DRIVER.LINK.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)
    return value


def main() -> int:
    DRIVER.LINK.require(not DRIVER.OUT.exists()
                        and not DRIVER.RECEIPT.exists()
                        and not DIAGNOSIS.exists(),
                        "Link-42 authority replay state is not one-shot")
    record_diagnosis()
    old_prerequisites = DRIVER.prerequisites

    def prerequisites() -> dict[str, Any]:
        value = old_prerequisites()
        value["class_a_prelink_authority_disposition"] = (
            DRIVER.LINK.bind(DIAGNOSIS))
        value["replay_driver"] = DRIVER.LINK.bind(Path(__file__))
        return value

    try:
        DRIVER.prerequisites = prerequisites
        return DRIVER.main()
    finally:
        DRIVER.prerequisites = old_prerequisites


if __name__ == "__main__":
    raise SystemExit(main())
