#!/usr/bin/env python3
"""Second Class-A artifact replay after admitting llvm-size as read-only."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_real_abi_e000_eviction_gate_replay as REPLAY  # noqa: E402


REPLAY.OUT = ROOT / (
    "build/c2-lite/v6-link39-real-abi-e000-evacuation-gate-replay2")
REPLAY.RECEIPT = REPLAY.EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "gate-replay2-receipt.json")
REPLAY.DIAGNOSIS = REPLAY.EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "read-only-tool-harness-diagnosis.json")


if __name__ == "__main__":
    raise SystemExit(REPLAY.main())
