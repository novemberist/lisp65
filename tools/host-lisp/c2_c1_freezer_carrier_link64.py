#!/usr/bin/env python3
"""Rebind the nonpromotable C1 carrier to immutable Link 64."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link60 as BASE  # noqa: E402
import c2_c1_freezer_cutpoint_build_link64 as DONOR  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / (
    "build/c2.2/substitution/"
    "product-link-64-nonlto-stateless-completion-length")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
RECEIPT = EVIDENCE / (
    "c2.2-link64-c1-freezer-carrier-nonpromotable-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link64-nonlto-stateless-completion-length-"
    "structural-receipt.json")
PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")
LINK_RECEIPT_STATUS = (
    "passed-link64-nonlto-stateless-completion-length-product-"
    "identity-hardware-not-run")


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
        "lisp65-c2.2-Link64-C1-Freezer-v4-carrier-receipt-v1")
    value["status"] = (
        "passed-Link64-capacity-and-gates-awaiting-hardware")
    value["authority"]["link64_rebind_driver"] = BASE.bind(Path(__file__))
    value["proof"]["boot_inventory"] = {
        "records": 12,
        "stage_slot": 9,
        "installer_slot": 10,
        "carrier_slot": 11,
        "boot_size": boot["size"],
        "boot_crc16": f"0x{int(boot['crc16']):04x}",
        "source": "Link64 pure full replay",
    }
    value["proof"]["post_shelf_region1"] = {
        "durable_source": "0x08300000",
        "runtime_target": "Bank5:0xbd00",
        "publication_rule":
            "Phase03 shelf consumption -> copy -> target CRC -> VERIFIED",
    }
    value["proof"]["completion_retry_length"] = {
        "authority":
            "27-byte non-LTO leaf derives 48/64 from completion mode",
        "rematerializations": 3,
        "direct_callsites": 4,
        "scratch_clobber_mutation": "rejected",
        "source": "Link64 linked ELF gate",
    }
    value["next_gate"] = (
        "one Link64 hardware appointment: Cutpoint 3 with episode latch, "
        "then Cutpoint 4 with write-completion barriers")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-c1-freezer-carrier-link64: PASS "
        f"boot={boot['size']}/{int(boot['crc16']):04x} "
        f"session={session['size']}/{int(session['crc16']):04x} "
        "product-delta=0 compiler=0 linker=0 hardware=not-run")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            "c2-c1-freezer-carrier-link64: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
