#!/usr/bin/env python3
"""Retry the nonpromotable attribution WPLTO after artifact-profile repair."""

from __future__ import annotations

from pathlib import Path

import c2_link57_top_level_frame_attribution_wplto as BASE


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    BASE.OUT = ROOT / (
        "build/c2.2/substitution/"
        "link57-top-level-frame-attribution-wplto4")
    BASE.INTERNAL = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-internal.json")
    BASE.BASE_RECEIPT = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-base.json")
    BASE.FIRST_RED = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-first-red.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-receipt.json")
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
