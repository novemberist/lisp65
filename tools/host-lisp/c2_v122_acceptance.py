#!/usr/bin/env python3
"""Materialize the v1.2.2 R5/G5 handoff only from sealed R4."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_acceptance as ACCEPTANCE  # noqa: E402


ACCEPTANCE.OUT = ROOT / "build/c2.2/v1.2.2-acceptance/r5"
ACCEPTANCE.PREFLIGHT = ACCEPTANCE.OUT / "r5-preflight-receipt.json"
ACCEPTANCE.RUNBOOK = ACCEPTANCE.OUT / "g5-runbook.json"


if __name__ == "__main__":
    raise SystemExit(ACCEPTANCE.main())
