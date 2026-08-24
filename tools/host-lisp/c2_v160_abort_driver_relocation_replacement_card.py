#!/usr/bin/env python3
"""Run the one authorized replacement R1 card after reserve-pin disposal."""

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

import c2_v160_abort_driver_relocation_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-abort-driver-relocation-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-abort-driver-relocation-replacement-preflight"
RECEIPT = ARCH / "c2.3-v1.6-abort-driver-relocation-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-abort-driver-relocation-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "677b0fa7"
STATUS = "PASS: V1.6 REPLACEMENT R1 ABORT-DRIVER RELOCATION GREEN"
FORMAT = "lisp65-c2-v160-abort-driver-relocation-replacement-card-v1"


class ReplacementError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise ReplacementError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: R1 ABORT-DRIVER RELOCATION RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["artifacts"] == {},
            "R1 Final Red predecessor drift")
    return value


def configure() -> None:
    BASE.BUILD = BUILD; BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    BASE.INVOCATION = PREFLIGHT / "card-invocation.json"
    BASE.PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
    BASE.PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
    BASE.PRODUCER_RESULT = BUILD / "producer-result.json"
    BASE.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    BASE.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    BASE.ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
    BASE.R1_REPORT = BUILD / "abort-driver-relocation-host.json"
    BASE.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PRODUCT_PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    BASE.RECEIPT = RECEIPT; BASE.FINAL_RED = FINAL_RED
    BASE.DRIVER = DRIVER; BASE.AUTHORIZATION = AUTHORIZATION
    BASE.STATUS = STATUS; BASE.FORMAT = FORMAT
    BASE.GATE.AUTHORIZATION = AUTHORIZATION

    original_roots = BASE.roots
    original_install = BASE.install
    original_bind = BASE.bind_paths_only
    BASE.roots = lambda build=BUILD, preflight=PREFLIGHT: original_roots(
        build, preflight)
    BASE.install = lambda build=BUILD, preflight=PREFLIGHT: original_install(
        build, preflight)
    BASE.bind_paths_only = lambda build=BUILD, preflight=PREFLIGHT: original_bind(
        build, preflight)


def add_predecessor(path: Path) -> None:
    value = load(path)
    value["replacement_authority"] = BASE.GATE.git_authority()
    value["predecessor_Final_Red"] = BASE.bind(PREDECESSOR_RED)
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); configure(); BASE.preflight()
    add_predecessor(BASE.PREFLIGHT_RECEIPT)
    print("v1.6 replacement R1: PREFLIGHT PASS card=0/1 derived-reserve")


def card() -> None:
    predecessor(); configure(); BASE.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    value["predecessor_Final_Red"] = BASE.bind(PREDECESSOR_RED)
    value["replacement_authority"] = BASE.GATE.git_authority()
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 replacement R1: CARD PASS card=1/1")


def child(action: str) -> None:
    configure()
    {"_dry": BASE.dry_child, "_produce": BASE.produce_child,
     "_scope": BASE.scope_child, "_accept": BASE.acceptance_child}[action]()


def record_red(error: Exception) -> None:
    configure(); BASE.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: REPLACEMENT R1 RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["predecessor_Final_Red"] = BASE.bind(PREDECESSOR_RED)
        value["replacement_authority"] = BASE.GATE.git_authority()
        FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 replacement R1: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 replacement R1: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 replacement R1: CHECK ARMED")
    else: print("v1.6 replacement R1: CHECK LOCKED")


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
                print(f"replacement R1 receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 replacement R1: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
