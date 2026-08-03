#!/usr/bin/env python3
"""Bind the fresh-G5-tested v1.3.0 R5 set and package exact R6 bytes."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v121_r5_r6 as FLOW  # noqa: E402


BASE = ROOT / "build/c2.3/v1.3.0-acceptance"
FLOW.RELEASE = "v1.3.0"
FLOW.BASE = BASE
FLOW.R5_PREFLIGHT = BASE / "r5/r5-preflight-receipt.json"
FLOW.G5 = BASE / "r5/hardware-session-01/g5-hardware-receipt.json"
FLOW.R5_BIND_ROOT = BASE / "r5-tested"
FLOW.R5_BIND = FLOW.R5_BIND_ROOT / "r5-tested-set-receipt.json"
FLOW.R6_ROOT = BASE / "r6"
FLOW.R6_SHIP = FLOW.R6_ROOT / "ship"
FLOW.R6_RECEIPT = FLOW.R6_ROOT / "r6-packaging-receipt.json"


def configure() -> None:
    """Bind the generic packager to the v1.3 acceptance tree."""
    r6 = FLOW.R6
    r6.TOOL = Path(__file__).resolve()
    r6.OLD_R5 = FLOW.R5_PREFLIGHT
    r6.G5 = FLOW.G5
    r6.R5_OUT = FLOW.R5_BIND_ROOT
    r6.R5_PRODUCT = FLOW.R5_BIND_ROOT / "product"
    r6.R5_RECEIPT = FLOW.R5_BIND
    r6.R6_OUT = FLOW.R6_ROOT
    r6.R6_SHIP = FLOW.R6_SHIP
    r6.R6_RECEIPT = FLOW.R6_RECEIPT
    r6.CHAIN = ()
    r6.R5_ACCEPTED_STATUSES = {"passed-tested-R5-bind"}
    r6.R5_PROOF_NAME = "r5-preflight-receipt.json"
    r6.R5_PACKAGE_CLAIM = "passed-tested-R5-bind"
    r6.R5_DESCRIPTION = "fresh-G5-tested v1.3.0 R5 set"
    r6.R5_MAPPING = "all-19-tested-R5-roles-exactly-once"
    r6.R6_ID = "R6-from-v1.3.0-tested-R5"
    r6.R6_RECEIPT_ID = "R6-v1.3.0-tested-set"
    r6.RECORDED_ON = date.today().isoformat()


FLOW.configure = configure


if __name__ == "__main__":
    raise SystemExit(FLOW.main())
