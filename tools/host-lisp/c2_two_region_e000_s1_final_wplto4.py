#!/usr/bin/env python3
"""Run the still-unconsumed Link-60 WPLTO after the driver-order correction."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_two_region_e000_s1_final_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "two-region-session-store-e000-s1-final-wplto4")
    BASE.INTERNAL = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-wplto4-internal.json")
    BASE.BASE_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-wplto4-base.json")
    BASE.RAW_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-wplto4-raw.json")
    BASE.REPLAY_OUT = ROOT / (
        "build/c2.2/substitution/"
        "two-region-session-store-e000-s1-final-qualification4")
    BASE.REPLAY_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-qualification4.json")
    BASE.BASE_RESULT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-wplto4-base-result.json")
    BASE.FORMAT_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-format-and-stage-gate4.json")
    BASE.COMPLETION_SOURCE_RECEIPT = ROOT / (
        "build/c2.2/two-region-session-store/"
        "e000-s1-final-write-completion-source-gate4.json")
    BASE.EMITTER_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-emitter-union-gate4.json")
    BASE.ISLAND_RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-preinstall-source-host-gate4.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-two-region-e000-s1-final-wplto4-receipt.json")
    BASE.PRODUCT = BASE.OUT / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.C2D = (
        BASE.OUT
        / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
    BASE.RUNNER_PATH = Path(__file__)
    return BASE.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BASE.FinalMapError, RuntimeError, OSError, ValueError, KeyError) as error:
        print(
            "c2-two-region-e000-s1-final-wplto4: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
