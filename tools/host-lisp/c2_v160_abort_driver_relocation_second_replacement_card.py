#!/usr/bin/env python3
"""Run the final delegated second replacement R1 card."""

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

import c2_v160_abort_driver_relocation_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-second-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-abort-driver-relocation-second-replacement-preflight"
RECEIPT = ARCH / "c2.3-v1.6-abort-driver-relocation-second-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-second-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "a0c9ecb5"
STATUS = "PASS: V1.6 SECOND REPLACEMENT R1 GREEN"
FORMAT = "lisp65-c2-v160-abort-driver-relocation-second-replacement-card-v1"


class SecondReplacementError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise SecondReplacementError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] == "FINAL RED: REPLACEMENT R1 RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["artifacts"] == {}
            and set(value["intermediate_artifacts"]) == {"seed_ELF", "seed_PRG"},
            "replacement R1 Final Red predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.PREDECESSOR_RED = PREDECESSOR_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.STATUS = STATUS; PREV.FORMAT = FORMAT
    PREV.predecessor = predecessor


def append_chain(path: Path) -> None:
    value = load(path)
    value["second_replacement_authority"] = PREV.BASE.GATE.git_authority()
    value["replacement_R1_Final_Red"] = PREV.BASE.bind(PREDECESSOR_RED)
    value["delegation_end"] = (
        "A third R1-family Red returns to the owner; no further delegated card.")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); configure_module(); PREV.preflight()
    append_chain(PREFLIGHT / "preflight.json")
    print("v1.6 second replacement R1: PREFLIGHT PASS card=0/1 boundary=closed")


def card() -> None:
    predecessor(); configure_module(); PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS; value["format"] = FORMAT
    value["replacement_R1_Final_Red"] = PREV.BASE.bind(PREDECESSOR_RED)
    value["second_replacement_authority"] = PREV.BASE.GATE.git_authority()
    value["delegation_end"] = "R1 green; input-fidelity reopen requires review."
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 second replacement R1: CARD PASS card=1/1")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: SECOND REPLACEMENT R1 RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["replacement_R1_Final_Red"] = PREV.BASE.bind(PREDECESSOR_RED)
        value["second_replacement_authority"] = PREV.BASE.GATE.git_authority()
        value["family_delegation_ended"] = True
        FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 second replacement R1: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 second replacement R1: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 second replacement R1: CHECK ARMED")
    else: print("v1.6 second replacement R1: CHECK LOCKED")


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
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"second replacement R1 receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 second replacement R1: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
