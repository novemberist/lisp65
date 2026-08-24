#!/usr/bin/env python3
"""Run the owner-authorized R1 replacement with candidate witness identity."""

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

import c2_v160_abort_driver_relocation_card as CORE  # noqa: E402
import c2_v160_abort_driver_relocation_equate_owner_card as PREV  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-witness-conversion-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-abort-driver-relocation-witness-conversion-preflight")
RECEIPT = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-witness-conversion-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-witness-conversion-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-equate-owner-card-final-red.json")
ATTRIBUTION = ARCH / "c2.3-v1.6-zero-literal-witness-attribution-receipt.json"
PREDECESSOR_C2D = ROOT / (
    "build/c2.3/v1.6-abort-driver-relocation-equate-owner-card/wplto/"
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "92ec0fc1"
STATUS = "PASS: V1.6 R1 WITNESS-CONVERSION CARD GREEN"
FORMAT = "lisp65-c2-v160-abort-driver-relocation-witness-conversion-card-v1"


class WitnessConversionCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise WitnessConversionCardError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    attribution = load(ATTRIBUTION)
    require(value["status"] ==
                "FINAL RED: R1 EQUATE-OWNER CARD RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and set(value["artifacts"]) == {"ELF", "PRG"}
            and attribution["decision"]["classification"] ==
                "cross-inventory stored-world witness"
            and attribution["decision"]["genuine_zero_literal_regression"]
                is False,
            "R1 witness-conversion predecessor/attribution drift")
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


def witness_preflight() -> dict[str, Any]:
    value = ZERO.linked_inventory_selftest(
        FIDELITY.CANDIDATE_STATIC_PRODUCT,
        FIDELITY.CANDIDATE_STATIC_ROOT,
        PREDECESSOR_C2D)
    require(value["derived_ordinal"] == 658
            and value["expected_row_hex"] == value["observed_row_hex"]
                == "0500b49626007c090100"
            and value["mutations_rejected"] == [
                "restore-stored-ordinal-609",
                "foreign-row-at-derived-ordinal"],
            "R1 witness-conversion preflight drift")
    return value


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["witness_conversion_authority"] = CORE.GATE.git_authority()
    value["equate_owner_R1_Final_Red"] = CORE.bind(PREDECESSOR_RED)
    value["zero_literal_attribution"] = CORE.bind(ATTRIBUTION)
    value["witness_conversion"] = witness_preflight()
    value["next"] = (
        "independent review before input-fidelity reopen"
        if green else
        "owner disposition required; no retry, Completion, media, or device")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor()
    configure_module()
    PREV.preflight()
    append_chain(PREFLIGHT / "preflight.json", green=False)
    print("v1.6 R1 witness conversion: PREFLIGHT PASS card=0/1 ordinal=658")


def card() -> None:
    predecessor()
    configure_module()
    PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 witness conversion: CARD PASS card=1/1")


def child(action: str) -> None:
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module()
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: R1 WITNESS-CONVERSION RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 R1 witness conversion: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 R1 witness conversion: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 witness conversion: CHECK ARMED")
    else:
        print("v1.6 R1 witness conversion: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
                                           "_dry", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "card":
        card()
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print("R1 witness-conversion receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 R1 witness conversion: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
