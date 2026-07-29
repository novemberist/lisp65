#!/usr/bin/env python3
"""Prepare/bind/close the fresh v1.2.2 nine-case G5 hardware run."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v121_g5_hardware as G5  # noqa: E402


G5.BASE = ROOT / "build/c2.2/v1.2.2-acceptance/r5"
G5.RUNBOOK = G5.BASE / "g5-runbook.json"
G5.PREFLIGHT = G5.BASE / "r5-preflight-receipt.json"
G5.SESSION = G5.BASE / "hardware-session-01"
G5.EVIDENCE = G5.SESSION / "g5"
G5.DEPLOYMENT = G5.SESSION / "deployment.json"
G5.TRANSPORT = G5.SESSION / "media-transport-hardware-receipt.json"
G5.G5_RECEIPT = G5.SESSION / "g5-hardware-receipt.json"
G5.HARNESS_FIRST_RED = G5.SESSION / "harness-first-red.json"
G5.RESTAGE_ROUTE = G5.SESSION / "restage-route-observation.json"
G5.FORMAT = "lisp65-c2-lite-v1.2.2-G5-hardware-session-v1"
G5.TRANSPORT_FORMAT = (
    "lisp65-c2-lite-v1.2.2-media-transport-hardware-receipt-v1")
G5.REMOTE_MEDIA = "L65V122.D81"


if __name__ == "__main__":
    raise SystemExit(G5.main())
