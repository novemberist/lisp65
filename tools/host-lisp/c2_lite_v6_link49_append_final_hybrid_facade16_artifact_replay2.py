#!/usr/bin/env python3
"""Link-49 artifact replay after the authority-source Class-A stop."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link49_append_final_hybrid_facade16_artifact_replay as BASE  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-49-c2-lite-v6-append-final-hybrid-facade16-"
    "artifact-replay2")
RECEIPT = BASE.EVIDENCE / (
    "c2.2-product-link49-c2-lite-v6-append-final-hybrid-facade16-"
    "artifact-replay2-structural-receipt.json")


def main() -> int:
    old = BASE.OUT, BASE.RECEIPT, BASE.__file__
    try:
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.__file__ = str(Path(__file__).resolve())
        return BASE.main()
    finally:
        BASE.OUT, BASE.RECEIPT, BASE.__file__ = old


if __name__ == "__main__":
    raise SystemExit(main())
