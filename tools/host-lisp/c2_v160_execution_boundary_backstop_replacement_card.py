#!/usr/bin/env python3
"""Fresh target for the unconsumed execution-boundary card authorization."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-precard-red.json"
ORIGINAL_PREDECESSOR = CARD.predecessor


def predecessor():
    value = ORIGINAL_PREDECESSOR()
    red = CARD.load(RED)
    CARD.require(red["status"] ==
        "PRE-CARD RED: EXECUTION-BOUNDARY IRQ TAIL IDENTITY"
        and red["attempt_accounting"]["cards_consumed"] == 0
        and red["original_authorization_unconsumed"] is True,
        "execution-boundary pre-card ABI disposition drift")
    return {**value, "precard_ABI_red": CARD.bind(RED)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-replacement-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-replacement-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY REPLACEMENT ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY REPLACEMENT FINAL WORLD GREEN"
    CARD.predecessor = predecessor
    CARD.install()


def main() -> int:
    install()
    return CARD.main()


if __name__ == "__main__":
    raise SystemExit(main())
