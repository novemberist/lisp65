#!/usr/bin/env python3
"""Facade-16 artifact replay after the size-less-vector Class-A stop."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_hybrid_facade16_artifact_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link48-append-final-hybrid-facade16-artifact-replay2")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-"
    "artifact-replay2-receipt.json")


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
