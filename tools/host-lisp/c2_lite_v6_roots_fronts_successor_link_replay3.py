#!/usr/bin/env python3
"""Authorized Link-41 successor with the complete canonical profile."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_roots_fronts_successor_link as DRIVER  # noqa: E402


DRIVER.OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-41-c2-lite-v6-roots-fronts-coresident-replay3")
DRIVER.RECEIPT = DRIVER.LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "replay3-structural-receipt.json")


if __name__ == "__main__":
    raise SystemExit(DRIVER.main())
