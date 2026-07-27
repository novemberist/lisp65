#!/usr/bin/env python3
"""Class-A replay after correcting one source-inventory string anchor."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_family_slot_identity_wplto as BASE  # noqa: E402


HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-link40-family-slot-identity-wplto-receipt.json")
HARNESS_FIRST_RED_SHA = (
    "55e2d61e87b60c40e95af3022ff1beffd7993e57f8e4ac300d470c2454dbc3a8")
BASE.OUT = ROOT / "build/c2-lite/v6-link40-family-slot-identity-wplto-replay"
BASE.RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-link40-family-slot-identity-wplto-replay-receipt.json")
_authority = BASE.authority


def authority():
    value = _authority()
    BASE.require(HARNESS_FIRST_RED.is_file() and
                 hashlib.sha256(HARNESS_FIRST_RED.read_bytes()).hexdigest() ==
                 HARNESS_FIRST_RED_SHA,
                 "family/slot inventory-harness First Red drift")
    value["inventory_harness_first_red"] = BASE.bind(HARNESS_FIRST_RED)
    value["inventory_harness_disposition"] = {
        "class": "A",
        "cause": "exact source anchor named the facade instead of the direct "
                 "explicit-family transport call",
        "product_bytes": 0,
        "compiler_or_product_links": 0,
        "hardware_runs": 0,
        "corrected_execution_accounting": {
            "whole_program_lto_probes": 0,
            "host_fixture_compiles": 5,
        },
    }
    value["replay_driver"] = BASE.bind(Path(__file__))
    return value


BASE.authority = authority


if __name__ == "__main__":
    raise SystemExit(BASE.main())
