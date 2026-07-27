#!/usr/bin/env python3
"""Third Class-A preflight replay with the current direct-entry receipt bound."""

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
            "build/c2.2/substitution/link52-phase-self-stamp-wplto-replay3")
        REPLAY.INTERNAL = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay3-internal-structural.json")
        REPLAY.BASE_RECEIPT = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay3-base-receipt.json")
        REPLAY.RECEIPT = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay3-receipt.json")
        REPLAY.PRELINK_RED = EVIDENCE / (
            "c2.2-link52-phase-self-stamp-wplto-replay2-receipt.json")
        return REPLAY.main()
    finally:
        (REPLAY.OUT, REPLAY.INTERNAL, REPLAY.BASE_RECEIPT,
         REPLAY.RECEIPT, REPLAY.PRELINK_RED) = old


if __name__ == "__main__":
    raise SystemExit(main())
