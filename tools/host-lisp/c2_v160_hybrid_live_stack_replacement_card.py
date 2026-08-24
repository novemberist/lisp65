#!/usr/bin/env python3
"""Run the one-shot replacement for the live-stack Hybrid conversion card."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-hybrid-live-stack-replacement-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v1.6-hybrid-live-stack-replacement-preflight-r1"
PROCESS = ROOT / "build/c2.3/v1.6-hybrid-live-stack-replacement-process-r1"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
RECEIPT = ARCH / "c2.3-v1.6-hybrid-live-stack-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-hybrid-live-stack-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-hybrid-live-stack-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ae63d726"
FORMAT = "lisp65-c2-v160-hybrid-live-stack-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID LIVE STACK REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 HYBRID LIVE STACK REPLACEMENT FINAL WORLD GREEN"


def predecessor() -> dict[str, Any]:
    red = BASE.load(PREDECESSOR_RED)
    BASE.require(
        red["status"] == "FINAL RED: V1.6 HYBRID LIVE STACK CONVERSION STOPS"
        and red["retry_authorized"] is False
        and red["classification"]["mechanism_fully_attributed"] is True
        and red["classification"]["real_compiler_consumption_still_absent"] is False
        and red["final_world_observation"]["consumer_section_present"] is True
        and red["final_geometry_attribution"]["post_hybrid_free_bytes"] == 69
        and red["final_geometry_attribution"]["surplus_over_floor_bytes"] == 15,
        "live-stack replacement predecessor drift")
    return {"Final_Red": red}


def configure_module() -> None:
    BASE.set_paths(BUILD, PREFLIGHT, tag="live-stack-replacement-r1")
    BASE.PREV.configure_module()


def install() -> None:
    BASE.BUILD = BUILD
    BASE.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PREFLIGHT = PREFLIGHT
    BASE.NORMAL_BUILD = NORMAL_BUILD
    BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD
    BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.PREDECESSOR_RED = PREDECESSOR_RED
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BASE.FINAL_STATUS = FINAL_STATUS
    BASE.predecessor = predecessor
    BASE.configure_module = configure_module


def main() -> int:
    install()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        configure_module()
        value = BASE.load(RECEIPT)
        BASE.require(value["status"] == FINAL_STATUS
                     and value["artifacts_before"] == value["artifacts_after"],
                     "live-stack replacement receipt/artifact drift")
        BASE.PREV.PREV.PREV.validate_final_claims(value)
        successor = value["R1_capture_successor"]
        BASE.require(successor["post_capture_free_bytes"] == 69
                     and successor["reserve_floor_bytes"] == 54
                     and successor["surplus_over_floor_bytes"] == 15
                     and successor["stored_capture_only_reserve_pin_rejected"]
                     is True,
                     "live-stack replacement derived reserve drift")
        witness = value["real_process_argv_witness"]
        BASE.require(witness["normal"]["compiler_process_count"] == 68
                     and witness["normal"]["all_hybrid"] is True
                     and witness["normal"]["consumer_source_process_present"]
                     is True
                     and witness["snapshot_mutation"]["compiler_process_count"]
                     == 67
                     and witness["snapshot_mutation"]["all_hybrid"] is False,
                     "live-stack replacement process witness drift")
        print("v1.6 hybrid live stack replacement: CHECK PASS "
              "processes=68/67 consumer=67 reserve=69/15 claims=512+94")
        return 0
    return BASE.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                BASE.record_red(error)
            except Exception as receipt_error:
                print(f"live-stack replacement Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 hybrid live stack replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
