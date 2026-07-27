#!/usr/bin/env python3
"""Bind the corrected nonpromotable attribution identity for deployment."""

from __future__ import annotations

from pathlib import Path

import c2_top_level_frame_attribution_deployment as BASE


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    BASE.INTERNAL = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-internal.json")
    BASE.REPLAY = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-artifact-replay2-receipt.json")
    BASE.OUT = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-deployment2-authority.json")
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
