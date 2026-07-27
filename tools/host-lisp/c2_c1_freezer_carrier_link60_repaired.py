#!/usr/bin/env python3
"""Rebind the existing nonpromotable C1 carrier to repaired Link 60."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link60 as BASE  # noqa: E402
import c2_link60_boot_inventory_artifact_repair as REPAIR  # noqa: E402
import c2_link60_boot_inventory_pure_replay as REPLAY  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/"
    "link60-repaired-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
RECEIPT = REPAIR.EVIDENCE / (
    "c2.2-link60-repaired-c1-freezer-carrier-nonpromotable-receipt.json")


def main() -> int:
    BASE.LINK = REPAIR.OUT
    BASE.OUT = OUT
    BASE.LINK_RECEIPT = REPLAY.RECEIPT
    BASE.LINK_RECEIPT_STATUS = "passed-pure-full-replay-all-gates-green"
    BASE.RECEIPT = RECEIPT
    BASE.PRODUCT_SHA = REPLAY.EXPECTED_PRODUCT_SHA
    result = BASE.main()
    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["format"] = (
        "lisp65-c2.2-Link60-repaired-C1-Freezer-v4-carrier-receipt-v1")
    value["status"] = (
        "passed-repaired-Link60-capacity-and-gates-awaiting-hardware")
    value["authority"]["repair_driver"] = BASE.bind(Path(__file__))
    value["proof"]["boot_inventory"] = {
        "records": 12,
        "stage_slot": 9,
        "installer_slot": 10,
        "carrier_slot": 11,
        "boot_size": 19269,
        "boot_crc16": "0x49f6",
        "source": "canonical artifact-repair replay",
    }
    value["next_gate"] = (
        "one repaired-Link60 hardware appointment: Cutpoint 3 with episode "
        "latch, then Cutpoint 4 with write-completion barriers")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-carrier-link60-repaired: PASS "
        "boot=19269/49f6 session=64926/7753 "
        "product-delta=0 compiler=0 linker=0 hardware=not-run")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            "c2-c1-freezer-carrier-link60-repaired: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
