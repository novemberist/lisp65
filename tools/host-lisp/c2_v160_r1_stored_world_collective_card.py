#!/usr/bin/env python3
"""Run the one authorized collective R1 stored-world conversion card."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_abort_driver_relocation_witness_conversion_card as PREV  # noqa: E402
import c2_v160_r1_stored_world_conversions as CONVERT  # noqa: E402
import c2_v160_r1_stored_world_sweep as SWEEP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-r1-stored-world-collective-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-r1-stored-world-collective-preflight"
RECEIPT = ARCH / "c2.3-v1.6-r1-stored-world-collective-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-r1-stored-world-collective-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-witness-conversion-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b6e6feba"
STATUS = "PASS: V1.6 R1 STORED-WORLD COLLECTIVE CARD GREEN"
FORMAT = "lisp65-c2-v160-r1-stored-world-collective-card-v1"
ORIGINAL_CONFIGURE = PREV.configure_module


class CollectiveCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CollectiveCardError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: R1 WITNESS-CONVERSION RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["linked_R1_counterproof"][
                "post_capture_free_bytes"] == 195,
            "collective-card frozen predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.PREDECESSOR_RED = PREDECESSOR_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.STATUS = STATUS
    PREV.FORMAT = FORMAT
    PREV.predecessor = predecessor
    ORIGINAL_CONFIGURE()
    CONVERT.install()


def arm() -> dict[str, Any]:
    sweep = load(SWEEP.RECEIPT)
    SWEEP.validate(sweep)
    conversions = CONVERT.preflight()
    require(sweep["collective_card_checklist"] == conversions["inventory_ids"]
            and len(conversions["mutations_rejected"]) == 8,
            "collective card does not close the complete sweep inventory")
    return {"status": "PASS: collective conversion checklist complete 8/8",
            "sweep": PREV.CORE.bind(SWEEP.RECEIPT),
            "inventory_ids": conversions["inventory_ids"],
            "conversion_functions": conversions["conversion_functions"],
            "mutations_rejected": conversions["mutations_rejected"]}


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["stored_world_collective_authority"] = (
        PREV.CORE.GATE.git_authority())
    value["witness_conversion_R1_Final_Red"] = PREV.CORE.bind(PREDECESSOR_RED)
    value["stored_world_collective"] = arm()
    value["next"] = ("independent review before input-fidelity reopen"
                     if green else
                     "owner disposition required; no retry or downstream work")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "collective card is one-shot")
    arm()
    PREV.configure_module = configure_module
    configure_module()
    PREV.preflight()
    append_chain(PREFLIGHT / "preflight.json", green=False)
    print("v1.6 R1 stored-world collective: PREFLIGHT PASS card=0/1 rows=8")


def card() -> None:
    predecessor()
    PREV.configure_module = configure_module
    configure_module()
    PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 stored-world collective: CARD PASS card=1/1 rows=8")


def child(action: str) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: R1 STORED-WORLD COLLECTIVE RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 R1 stored-world collective: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 R1 stored-world collective: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 stored-world collective: CHECK ARMED")
    else:
        print("v1.6 R1 stored-world collective: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_dry", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    else: child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"collective receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 R1 stored-world collective: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
