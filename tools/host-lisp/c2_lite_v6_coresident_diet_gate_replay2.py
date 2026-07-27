#!/usr/bin/env python3
"""Second Class-A replay: product-emission gate now reads ELF truth."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_coresident_diet_gate_replay as REPLAY  # noqa: E402


REPLAY.OUT = ROOT / "build/c2-lite/v6-coresident-diet-successor-gate-replay2"
REPLAY.RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-gate-replay2-receipt.json")
REPLAY.PATH_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-successor-gate-replay-receipt.json")


if __name__ == "__main__":
    raise SystemExit(REPLAY.main())
