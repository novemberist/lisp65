#!/usr/bin/env python3
"""Run the candidate-object-derived replacement active-frame card."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-active-frame-liveness-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-active-frame-liveness-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-active-frame-liveness-replacement-process"
RECEIPT = ARCH / "c2.3-v1.6-active-frame-liveness-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-active-frame-liveness-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-active-frame-liveness-card-final-red.json"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-active-frame-liveness-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS REPLACEMENT FINAL WORLD GREEN"


def predecessor() -> dict[str, Any]:
    red = CARD.BASE.load(PREDECESSOR_RED)
    CARD.require(red["status"] == "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS"
        and red["error"]["message"] == "input-fidelity implementation receipt drift"
        and red["artifacts"] == {}
        and red["final_world_claims"] is None
        and not (ROOT / "build/c2.3/v1.6-active-frame-liveness-card").exists(),
        "active-frame replacement predecessor drift")
    return {"Final_Red": red,
        "classification": "candidate object replaced sealed 25-byte helper witness",
        "actual_product_attempt": {"WPLTO_runs": 0, "product_links": 0}}


def configure_module() -> None:
    CARD.configure_for_paths(BUILD, PREFLIGHT,
        tag="active-frame-liveness-replacement")


def install() -> None:
    CARD.BUILD = BUILD
    CARD.PREFLIGHT = PREFLIGHT
    CARD.PROCESS = PROCESS
    CARD.NORMAL_BUILD = PROCESS / "normal-build"
    CARD.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    CARD.MUTANT_BUILD = PROCESS / "mutant-build"
    CARD.MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
    CARD.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    CARD.RECEIPT = RECEIPT
    CARD.FINAL_RED = FINAL_RED
    CARD.PREDECESSOR = PREDECESSOR_RED
    CARD.DRIVER = DRIVER
    CARD.FORMAT = FORMAT
    CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    CARD.FINAL_STATUS = FINAL_STATUS
    CARD.predecessor = predecessor
    CARD.configure_module = configure_module
    CARD.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    result = CARD.main()
    if action == "card" and RECEIPT.is_file():
        value = CARD.BASE.load(RECEIPT)
        value["replacement_predecessor_Final_Red"] = CARD.BASE.bind(PREDECESSOR_RED)
        value["actual_predecessor_product_attempt"] = {
            "WPLTO_runs": 0, "product_links": 0}
        RECEIPT.write_bytes(CARD.canonical(value))
        CARD.check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                CARD.record_red(error)
            except Exception as receipt_error:
                print(f"active-frame replacement Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 active-frame replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
