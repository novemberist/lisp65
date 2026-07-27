#!/usr/bin/env python3
"""Facade-16 WPLTO after the zero-link Class-A authority-gate stop."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_hybrid_facade16_wplto as FACADE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link48-append-final-hybrid-facade16-wplto2")
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto2-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-wplto2-receipt.json")


def main() -> int:
    old = (FACADE.OUT, FACADE.INTERNAL, FACADE.RECEIPT, FACADE.__file__)
    try:
        FACADE.OUT = OUT
        FACADE.INTERNAL = INTERNAL
        FACADE.RECEIPT = RECEIPT
        FACADE.__file__ = str(Path(__file__).resolve())
        return FACADE.main()
    finally:
        FACADE.OUT, FACADE.INTERNAL, FACADE.RECEIPT, FACADE.__file__ = old


if __name__ == "__main__":
    raise SystemExit(main())
