#!/usr/bin/env python3
"""Class-A harness replay, then the still-unspent final-Island WPLTO."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_final_island_identity_wplto as BASE  # noqa: E402

BASE.OUT = ROOT / "build/c2-lite/v6-final-island-identity-wplto-replay"
BASE.RECEIPT = BASE.EVIDENCE / (
    "c2.2-c2-lite-v6-final-island-identity-wplto-replay-receipt.json")

if __name__ == "__main__":
    raise SystemExit(BASE.main())
