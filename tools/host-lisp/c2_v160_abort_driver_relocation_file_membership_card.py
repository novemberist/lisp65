#!/usr/bin/env python3
"""Run the owner-authorized R1 card with a real source-membership boundary."""

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

import c2_v160_abort_driver_relocation_second_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-file-membership-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-abort-driver-relocation-file-membership-preflight"
RECEIPT = ARCH / "c2.3-v1.6-abort-driver-relocation-file-membership-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-file-membership-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-second-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "53f6ecef"
STATUS = "PASS: V1.6 R1 FILE-MEMBERSHIP CARD GREEN"
FORMAT = "lisp65-c2-v160-abort-driver-relocation-file-membership-card-v1"


class MembershipCardError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise MembershipCardError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: SECOND REPLACEMENT R1 RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["family_delegation_ended"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["artifacts"] == {},
            "second replacement R1 Final Red predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.PREDECESSOR_RED = PREDECESSOR_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.STATUS = STATUS; PREV.FORMAT = FORMAT
    PREV.predecessor = predecessor


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["file_membership_authority"] = PREV.PREV.BASE.GATE.git_authority()
    value["second_replacement_R1_Final_Red"] = PREV.PREV.BASE.bind(
        PREDECESSOR_RED)
    value["next"] = (
        "independent review; input-fidelity reopen remains separately gated"
        if green else
        "owner disposition required; no retry, Completion, media, or device")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); configure_module(); PREV.preflight()
    append_chain(PREFLIGHT / "preflight.json", green=False)
    print("v1.6 R1 file membership: PREFLIGHT PASS card=0/1 inputs=distinct")


def card() -> None:
    predecessor(); configure_module(); PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS; value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 file membership: CARD PASS card=1/1")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: R1 FILE-MEMBERSHIP CARD RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists(): print("v1.6 R1 file membership: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 R1 file membership: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 file membership: CHECK ARMED")
    else: print("v1.6 R1 file membership: CHECK LOCKED")


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
                print(f"R1 membership receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 R1 file membership: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
