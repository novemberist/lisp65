#!/usr/bin/env python3
"""Owner-authorized WPLTO after the append-plan Leaf ABI correction."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_hybrid_wplto as HYBRID  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link48-append-final-hybrid-abi-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-abi-wplto-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-abi-wplto-receipt.json")


def main() -> int:
    old = (HYBRID.OUT, HYBRID.INTERNAL, HYBRID.RECEIPT, HYBRID.__file__)
    try:
        HYBRID.OUT = OUT
        HYBRID.INTERNAL = INTERNAL
        HYBRID.RECEIPT = RECEIPT
        HYBRID.__file__ = str(Path(__file__).resolve())
        return HYBRID.main()
    finally:
        HYBRID.OUT, HYBRID.INTERNAL, HYBRID.RECEIPT, HYBRID.__file__ = old


if __name__ == "__main__":
    raise SystemExit(main())
