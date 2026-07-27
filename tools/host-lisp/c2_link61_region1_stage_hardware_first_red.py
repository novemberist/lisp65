#!/usr/bin/env python3
"""Bind the Link-61 Region-1 staging hardware First Red.

The upload readback proves the v4 Region-1 payload arrived at Bank 5.  The
post-boot capture proves the boot shelf subsequently reused that same range,
so Session-family verification correctly rejected the overwritten bytes.
This script is read-only apart from its evidence receipt.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link61-cutpoints3-4-NONPROMOTABLE")
PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-61-v4-final-frame-seal/"
    "lisp65-c2-substitution-linked.prg")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link61-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
REGION1 = CARRIER / (
    "runtime-overlays-session-c1-freezer-link61-region1.bin")
UPLOAD = RUN / (
    "deploy-readback-runtime-overlays-session-c1-freezer-link61-region1.bin")
SESSION = CARRIER / (
    "runtime-overlays-session-c1-freezer-link61-stage-bound.bin")
SHELF = ROOT / (
    "build/c2.2/substitution/published-nullary-call-bytecode-artifacts/"
    "product/product-shelf-v4-direct.bin")
BANK0 = RUN / "boot-bank0.bin"
BANK3 = RUN / "boot-bank3.bin"
BANK5 = RUN / "boot-bank5.bin"
SCREEN = RUN / "boot-screen.png"
SCREEN_TEXT = RUN / "boot-screen.txt"
DEPLOYMENT = RUN / "deployment.json"
CARRIER_RECEIPT = EVIDENCE / (
    "c2.2-link61-c1-freezer-carrier-nonpromotable-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link61-v4-frame-seal-structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link61-region1-stage-hardware-first-red.json")

REGION1_OFFSET = 0xBD00
RTOV_FAULT = 0xBFDB
RTOV_FAMILY = 0xBFDC
C2_READY = 0x008C


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing First-Red artifact: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def crc(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def main() -> int:
    require(not RECEIPT.exists(), "Region-1 First-Red receipt is one-shot")
    for path in (
            PRODUCT, REGION1, UPLOAD, SESSION, SHELF, BANK0, BANK3, BANK5,
            SCREEN, SCREEN_TEXT, DEPLOYMENT, CARRIER_RECEIPT, LINK_RECEIPT):
        require(path.is_file(), f"First-Red authority absent: {path}")
    product_sha = sha(PRODUCT)
    region1 = REGION1.read_bytes()
    upload = UPLOAD.read_bytes()
    session = SESSION.read_bytes()
    shelf = SHELF.read_bytes()
    bank0 = BANK0.read_bytes()
    bank3 = BANK3.read_bytes()
    bank5 = BANK5.read_bytes()
    live_region1 = bank5[
        REGION1_OFFSET:REGION1_OFFSET + len(region1)]
    differences = [
        index for index, pair in enumerate(zip(live_region1, region1))
        if pair[0] != pair[1]
    ]
    require(
        product_sha
        == "c4dc74a7729778ad79a1990bf88a25d7803040740bf626c15b08dc2a85607b9b"
        and upload == region1
        and bank3[:len(session)] == session
        and live_region1 == shelf[:len(region1)]
        and live_region1 != region1
        and len(differences) == 1908
        and crc(region1) == 0x66C6
        and crc(live_region1) == 0xA942
        and crc(session) == 0x4E98
        and bank0[RTOV_FAULT] == 23
        and bank0[RTOV_FAMILY] == 0
        and bank0[C2_READY] == 0
        and "E3e" in SCREEN_TEXT.read_text(encoding="utf-8"),
        "Link-61 Region-1 First-Red diagnosis does not reproduce")

    receipt = {
        "format":
            "lisp65-c2.2-Link61-v4-region1-stage-hardware-first-red-v1",
        "recorded_on": "2026-07-24",
        "status":
            "FIRST RED: Session Region-1 source overwritten before stage proof",
        "promotable": False,
        "authority": {
            "Link61_product": bind(PRODUCT),
            "Link61_structural_receipt": bind(LINK_RECEIPT),
            "nonpromotable_C1_carrier_receipt": bind(CARRIER_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "driver": bind(Path(__file__)),
        },
        "hardware": {
            "device_runs": 1,
            "C1_cutpoints_reached": 0,
            "latency_attempts_consumed": 0,
            "screen": "E3e runtime family staging failed; redeploy",
            "rtov_fault_address": "0xbfdb",
            "rtov_fault": 23,
            "rtov_fault_name": "VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE",
            "rtov_family": 0,
            "c2_ready": 0,
        },
        "proof": {
            "region1_address": "0x0005bd00",
            "region1_bytes": len(region1),
            "upload_readback": {
                "expected_sha256": sha(REGION1),
                "readback_sha256": sha(UPLOAD),
                "byteidentical": True,
                "crc16": "0x66c6",
            },
            "session_main_after_stage": {
                "bytes": len(session),
                "crc16": "0x4e98",
                "byteidentical": True,
            },
            "region1_at_failure": {
                "sha256": hashlib.sha256(live_region1).hexdigest(),
                "crc16": "0xa942",
                "different_bytes": len(differences),
                "byteidentical_to_boot_shelf_prefix": True,
            },
            "ordering": [
                "JTAG upload placed Region-1 byte-identically at Bank 5",
                "boot shelf staging reused Bank 5 0xbd00 for its L65S prefix",
                "Session main staged byte-identically into Bank 3",
                "Region-1 target CRC rejected the overwritten Bank-5 bytes",
                "publication remained fail-closed",
            ],
        },
        "captures": {
            "uploaded_region1_readback": bind(UPLOAD),
            "post_failure_bank0": bind(BANK0),
            "post_failure_bank3": bind(BANK3),
            "post_failure_bank5": bind(BANK5),
            "screen": bind(SCREEN),
            "screen_text": bind(SCREEN_TEXT),
        },
        "classification": {
            "carrier_specific": False,
            "reason": (
                "The diagnostic Region-1 image is byte-identical to the "
                "Link-61 product Region-1 image; the conflicting lifetime "
                "and address are shared by both."),
            "product_question": (
                "Region 1 needs a durable source and a post-shelf stage into "
                "Bank 5 before Session-family target verification."),
        },
        "claim_limit": (
            "Hardware First Red before C1. No Cutpoint, matrix, promotion, "
            "acceptance-chain, or release claim."),
        "next_gate": (
            "Class-C review of post-shelf Region-1 staging, followed by a "
            "fresh product-shaped WPLTO probe and successor link."),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link61-region1-stage-hardware-first-red: PASS "
        "upload=66c6 live=a942 shelf-prefix=yes main=4e98 "
        "fault=23 family=0 READY=0 cutpoints=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-link61-region1-stage-hardware-first-red: FAIL " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
