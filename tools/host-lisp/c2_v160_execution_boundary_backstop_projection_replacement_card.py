#!/usr/bin/env python3
"""One replacement for the execution-boundary additive-projection red."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-replacement-card-final-red.json"
ORIGINAL_PREDECESSOR = CARD.predecessor


def predecessor():
    value = ORIGINAL_PREDECESSOR()
    red = CARD.load(RED)
    CARD.require(red["status"] ==
        "FINAL RED: EXECUTION-BOUNDARY PREFLIGHT PROJECTION SUBSTITUTED"
        and red["attempt_accounting"]["cards_consumed"] == 1
        and red["attempt_accounting"]["WPLTO_runs"] == 0,
        "execution-boundary projection-red disposition drift")
    return {**value, "additive_projection_red": CARD.bind(RED)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-projection-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-projection-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-projection-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-projection-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-projection-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-projection-replacement-card-final-red.json"
    CARD.DRIVER = Path(__file__).resolve()
    CARD.FORMAT = "lisp65-c2-v160-execution-boundary-backstop-projection-replacement-card-v1"
    CARD.PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY PROJECTION REPLACEMENT ARMED 0/1"
    CARD.FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY PROJECTION REPLACEMENT FINAL WORLD GREEN"
    CARD.predecessor = predecessor
    CARD.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        return CARD.main()
    except Exception as error:
        if action == "card":
            CARD.record_red(error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
