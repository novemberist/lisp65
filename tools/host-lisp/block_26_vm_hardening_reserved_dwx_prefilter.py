#!/usr/bin/env python3
"""Run Card 3's packed/GC wall over the reserved-BSS successor pair."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_vm_hardening_dwx_prefilter as BASE  # noqa: E402
import block_26_vm_hardening_reserved_product_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/2.6/card3-vm-hardening-dwx-r2"
MEDIA_BUILD = BUILD / "media"
WPLTO = MEDIA_BUILD / "inputs/wplto"
STATIC = MEDIA_BUILD / "inputs/static-plane"
TARGET = MEDIA_BUILD / "canonical-product"
SHARED = MEDIA_BUILD / "shared-system"
MEDIA_RECEIPT = BUILD / "prefilter-medium-receipt.json"
SESSION = BUILD / "unused-device-session.json"
PREFILTER_RECEIPT = ARCH / "block-2.6-card3-vm-hardening-dwx-r2.json"
REPORT = ROOT / "docs/planning/2.6-card3-vm-hardening-dwx-r2.md"
FORMAT = "lisp65-block-2.6-card3-vm-hardening-dwx-r2-v1"
STATUS = "PASS: CARD-3 RESERVED A3-A6 PACKED PREFILTER AND GC-CYCLE WALL GREEN"
MEDIA_FORMAT = "lisp65-block-2.6-card3-vm-hardening-dwx-medium-r2-v1"
MEDIA_STATUS = "PASS: CARD-3 RESERVED A3-A6 DWX PREFILTER MEDIUM READY"
SESSION_FORMAT = "lisp65-block-2.6-card3-vm-hardening-unused-device-session-r2-v1"


def patch() -> None:
    # The r2 wrapper retains the r1 card as CARD; expose the same compatibility
    # seam the generic DWX adapter expects without changing either card.
    CARD.CARD2 = CARD.CARD.CARD2
    BASE.CARD = CARD
    values = {
        "BUILD": BUILD, "MEDIA_BUILD": MEDIA_BUILD, "WPLTO": WPLTO,
        "STATIC": STATIC, "TARGET": TARGET, "SHARED": SHARED,
        "MEDIA_RECEIPT": MEDIA_RECEIPT, "SESSION": SESSION,
        "PREFILTER_RECEIPT": PREFILTER_RECEIPT, "REPORT": REPORT,
        "FORMAT": FORMAT, "STATUS": STATUS, "MEDIA_FORMAT": MEDIA_FORMAT,
        "MEDIA_STATUS": MEDIA_STATUS, "SESSION_FORMAT": SESSION_FORMAT,
    }
    for name, value in values.items():
        setattr(BASE, name, value)
    for cls in (BASE.ProductCard, BASE.Adapter):
        cls.BUILD = CARD.BUILD
        cls.WPLTO = CARD.WPLTO
        cls.PLANE = CARD.PLANE
        cls.PRG = CARD.PRG
        cls.ELF = CARD.ELF
        cls.RECEIPT = CARD.RECEIPT
        cls.STATUS = CARD.STATUS
    BASE.ProductCard.LINK = CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    BASE.Adapter.PRICING_RECEIPT = BASE.MediaPrice.RECEIPT
    BASE.Adapter.PRICE = BASE.MediaPrice


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    patch()
    {"write": BASE.write, "check": BASE.check,
     "selftest": BASE.selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Block 2.6 Card 3 reserved DWX: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
