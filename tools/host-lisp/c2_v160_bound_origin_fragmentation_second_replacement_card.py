#!/usr/bin/env python3
"""Run the first-counter-derived fragmentation replacement successor."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_bound_origin_fragmentation_replacement_card as FRAG  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-process"
RECEIPT = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-second-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-second-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-replacement-card-final-red.json")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-bound-origin-fragmentation-second-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOUND-ORIGIN SECOND REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOUND-ORIGIN FINAL WORLD GREEN"


def predecessor() -> dict[str, Any]:
    red = FRAG.BOUND.CARD.BASE.load(PREDECESSOR_RED)
    row = red["counter_boundary_attribution"]
    FRAG.BOUND.CARD.require(red["status"] ==
            "FINAL RED: V1.6 BOUND-ORIGIN FRAGMENTATION REPLACEMENT STOPS"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and red["attempt_accounting"]["product_link_attempts"] == 1
        and red["attempt_accounting"]["media_builds"] == 0
        and row["candidate"]["ring_slots"] == 108
        and row["candidate"]["symbol_definition_count"] == 1
        and row["stored_member_value"] == 109
        and red["artifacts"]["ELF"]["sha256"] ==
            "62c844af56ba1913c5ee402e6d7e8623b0ae9b468018021806b5caadbc3ceb92",
        "second fragmentation replacement predecessor Red drift")
    return {"Final_Red": red,
            "conversion": "first candidate counter boundary minus ring base"}


def configure_module() -> None:
    FRAG.BOUND.CARD.configure_for_paths(BUILD, PREFLIGHT,
        tag="bound-origin-fragmentation-second-replacement")


def install() -> None:
    FRAG.BUILD = BUILD
    FRAG.PREFLIGHT = PREFLIGHT
    FRAG.PROCESS = PROCESS
    FRAG.RECEIPT = RECEIPT
    FRAG.FINAL_RED = FINAL_RED
    FRAG.PREDECESSOR_RED = PREDECESSOR_RED
    FRAG.DRIVER = DRIVER
    FRAG.FORMAT = FORMAT
    FRAG.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    FRAG.FINAL_STATUS = FINAL_STATUS
    FRAG.predecessor = predecessor
    FRAG.configure_module = configure_module
    FRAG.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    result = FRAG.main()
    if action == "card" and RECEIPT.is_file():
        value = FRAG.BOUND.CARD.BASE.load(RECEIPT)
        value["first_counter_predecessor_Final_Red"] = (
            FRAG.BOUND.CARD.BASE.bind(PREDECESSOR_RED))
        value["first_counter_conversion"] = predecessor()["conversion"]
        RECEIPT.write_bytes(FRAG.BOUND.CARD.canonical(value))
        FRAG.BOUND.check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                FRAG.BOUND.CARD.record_red(error)
            except Exception as receipt_error:
                print("second fragmentation replacement Final Red failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 second fragmentation replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
