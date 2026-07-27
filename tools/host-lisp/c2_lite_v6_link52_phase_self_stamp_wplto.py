#!/usr/bin/env python3
"""One product-shaped WPLTO for the approved phase self-stamp redesign."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link52_install_phase_wplto as PROBE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link52-phase-self-stamp-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-base-receipt.json")
RECEIPT = EVIDENCE / "c2.2-link52-phase-self-stamp-wplto-receipt.json"
FIRST_RED = EVIDENCE / "c2.2-link52-install-phase-wplto-receipt.json"


def main() -> int:
    original = {
        "out": PROBE.OUT,
        "internal": PROBE.INTERNAL,
        "base_receipt": PROBE.BASE_RECEIPT,
        "receipt": PROBE.RECEIPT,
        "authority": PROBE.authority,
    }

    def authority():
        value = original["authority"]()
        value["driver"] = PROBE.bind(Path(__file__))
        value["superseded_resident_three_phase_first_red"] = PROBE.bind(FIRST_RED)
        return value

    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.BASE_RECEIPT = BASE_RECEIPT
        PROBE.RECEIPT = RECEIPT
        PROBE.authority = authority
        return PROBE.main()
    finally:
        PROBE.OUT = original["out"]
        PROBE.INTERNAL = original["internal"]
        PROBE.BASE_RECEIPT = original["base_receipt"]
        PROBE.RECEIPT = original["receipt"]
        PROBE.authority = original["authority"]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PROBE.ProbeError, OSError, ValueError, KeyError) as error:
        print("c2-lite-v6-link52-phase-self-stamp-wplto: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
