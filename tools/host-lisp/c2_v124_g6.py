#!/usr/bin/env python3
"""Run fresh G6 on the exact v1.2.4 R6 package."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_g6 as G6  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.4-acceptance"
G6.R6_ROOT = BASE / "r6"
G6.SHIP = G6.R6_ROOT / "ship"
G6.MANIFEST = G6.SHIP / "manifest.json"
G6.R6_RECEIPT = G6.R6_ROOT / "r6-packaging-receipt.json"
G6.OUT = BASE / "g6/session-01"
G6.PLAN = G6.OUT / "g6-plan.json"
G6.REMOTE_PRODUCT = "L65V124R6.D81"
G6.REMOTE_WORK = "L65V124W.D81"
G6.SESSION_ID = "v1.2.4-G6-session-01"
G6.RECORDED_ON = date.today().isoformat()
G6.M65 = ROOT / "tools/m65tools/m65"
G6.FTP = ROOT / "tools/m65tools/mega65_ftp"


if __name__ == "__main__":
    G6.main()
