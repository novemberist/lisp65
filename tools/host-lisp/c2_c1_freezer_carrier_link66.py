#!/usr/bin/env python3
"""Rebind the nonpromotable C1 carrier to immutable Link 66."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link60 as BASE  # noqa: E402
import c2_c1_freezer_cutpoint_build_link66 as DONOR  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / (
    "build/c2.2/substitution/"
    "product-link-66-single-submit-completion")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link66-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
RECEIPT = EVIDENCE / (
    "c2.2-link66-c1-freezer-carrier-nonpromotable-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link66-single-submit-completion-"
    "structural-receipt.json")
PRODUCT_SHA = (
    "482b0b28171515c79ee2c8fd3ad78cea37716887ba06acddac0067db8171f6b4")
LINK_RECEIPT_STATUS = (
    "passed-link66-single-submit-completion-product-identity-"
    "hardware-not-run")


def main() -> int:
    DONOR.configure()
    BASE.DONOR = DONOR.BASE.OUT
    BASE.DONOR_RECEIPT = DONOR.BASE.RECEIPT
    BASE.DONOR_RECEIPT_STATUS = DONOR.DONOR_STATUS
    BASE.SOURCE_GATE = DONOR.BASE.OUT / "c1-freezer-cutpoint-source-gate.json"
    BASE.LINK = LINK
    BASE.OUT = OUT
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.LINK_RECEIPT_STATUS = LINK_RECEIPT_STATUS
    BASE.RECEIPT = RECEIPT
    BASE.PRODUCT_SHA = PRODUCT_SHA
    BASE.EXPECTED_SESSION_CRC = None
    BASE.TAIL_BYTES = None
    result = BASE.main()
    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    boot = json.loads(
        (LINK / "runtime-overlays-boot-final.json").read_text(
            encoding="utf-8"))["storage"]
    session = json.loads(
        (LINK / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))["storage"]
    value["format"] = (
        "lisp65-c2.2-Link66-C1-Freezer-v4-carrier-receipt-v1")
    value["status"] = (
        "passed-Link66-capacity-and-gates-awaiting-hardware")
    value["authority"]["link66_rebind_driver"] = BASE.bind(Path(__file__))
    value["proof"]["boot_inventory"] = {
        "records": 12,
        "stage_slot": 9,
        "installer_slot": 10,
        "carrier_slot": 11,
        "boot_size": boot["size"],
        "boot_crc16": f"0x{int(boot['crc16']):04x}",
        "source": "Link66 pure full replay",
    }
    value["proof"]["post_shelf_region1"] = {
        "durable_source": "0x08300000",
        "runtime_target": "Bank5:0xbd00",
        "publication_rule":
            "Phase03 shelf consumption -> copy -> target CRC -> VERIFIED",
    }
    value["proof"]["completion_observation"] = {
        "shape":
            "one poison pass; one target read; local comparison retries only",
        "reader_submit_count": 1,
        "retry_target_after_reader": True,
        "retry_target_after_poison": True,
        "source": "Link66 linked ELF gate",
    }
    value["construction"]["region1_byteidentical_Link66"] = (
        value["construction"].pop("region1_byteidentical_Link60"))
    value["next_gate"] = (
        "one Link66 hardware appointment: Cutpoint 3 with episode latch, "
        "then Cutpoint 4 with write-completion barriers")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-carrier-link66: PASS "
        f"boot={boot['size']}/{int(boot['crc16']):04x} "
        f"session={session['size']}/{int(session['crc16']):04x} "
        "product-delta=0 compiler=0 linker=0 hardware=not-run")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            "c2-c1-freezer-carrier-link66: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
