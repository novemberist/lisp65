#!/usr/bin/env python3
"""Run the liveness-consumed second replacement active-frame card."""

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
BUILD = ROOT / "build/c2.3/v1.6-active-frame-liveness-second-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-active-frame-liveness-second-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-active-frame-liveness-second-replacement-process"
RECEIPT = ARCH / "c2.3-v1.6-active-frame-liveness-second-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-active-frame-liveness-second-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-active-frame-liveness-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-active-frame-liveness-second-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS SECOND REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ACTIVE-FRAME LIVENESS SECOND REPLACEMENT FINAL WORLD GREEN"


def predecessor() -> dict[str, Any]:
    red = CARD.BASE.load(PREDECESSOR_RED)
    elf = ROOT / ("build/c2.3/v1.6-active-frame-liveness-replacement-card/"
                  "wplto/lisp65-c2-substitution-linked.prg.elf")
    CARD.require(red["status"] == "FINAL RED: V1.6 ACTIVE-FRAME LIVENESS STOPS"
        and red["error"]["message"] ==
            "post-R1 successor exceeds the fixed E000 reserve floor"
        and elf.is_file(), "second active-frame replacement predecessor drift")
    truth = CARD.ACTIVE.ElfTruth.read(elf, llvm_readobj=CARD.ACTIVE.READOBJ,
                                      include_section_data=True)
    service = truth.section(CARD.ACTIVE.SERVICE)
    main = truth.section(".lisp65_c2_kernal_window.input_capture_main")
    helper = truth.section(".lisp65_c2_kernal_window.input_capture_helper")
    CARD.require(service.bytes == 1382 and main.bytes + helper.bytes == 65,
        "second replacement attribution world drift")
    return {"Final_Red": red, "attribution": {
        "stored_capture_bytes": 59, "candidate_capture_bytes": 65,
        "E000_free_bytes": 60, "E000_floor_bytes": 54,
        "bound_liveness_service_bytes": 80,
        "consumed_predecessor_far_service_bytes": service.bytes,
        "classes": ["derived-not-pinned freight",
                    "bound-not-consumed compiler source"]}}


def configure_module() -> None:
    CARD.configure_for_paths(BUILD, PREFLIGHT,
        tag="active-frame-liveness-second-replacement")


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
        value["second_replacement_predecessor_Final_Red"] = (
            CARD.BASE.bind(PREDECESSOR_RED))
        value["second_replacement_attribution"] = predecessor()["attribution"]
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
                print(f"active-frame second replacement Final Red failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 active-frame second replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
