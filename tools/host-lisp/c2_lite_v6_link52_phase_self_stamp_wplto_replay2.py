#!/usr/bin/env python3
"""Second Class-A replay after the append-plan carrier learned self-stamps."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link52_phase_self_stamp_wplto_replay as REPLAY  # noqa: E402

EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    old = (REPLAY.OUT, REPLAY.INTERNAL, REPLAY.BASE_RECEIPT,
           REPLAY.RECEIPT, REPLAY.PRELINK_RED)
    try:
        REPLAY.OUT = ROOT / (
            "build/c2.2/substitution/link52-phase-self-stamp-wplto-replay2")
        REPLAY.INTERNAL = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay2-internal-structural.json")
        REPLAY.BASE_RECEIPT = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay2-base-receipt.json")
        REPLAY.RECEIPT = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay2-receipt.json")
        REPLAY.PRELINK_RED = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay-receipt.json")
        return REPLAY.main()
    finally:
        (REPLAY.OUT, REPLAY.INTERNAL, REPLAY.BASE_RECEIPT,
         REPLAY.RECEIPT, REPLAY.PRELINK_RED) = old


if __name__ == "__main__":
    raise SystemExit(main())
