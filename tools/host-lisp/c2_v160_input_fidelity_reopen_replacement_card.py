#!/usr/bin/env python3
"""Run the one owner-released inventory-aware reopen replacement card."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_input_fidelity_reopen_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-reopen-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-reopen-replacement-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-reopen-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-reopen-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-fidelity-reopen-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "26bbed2b"
FORMAT = "lisp65-c2-v160-input-fidelity-reopen-replacement-card-v1"
STATUS = "PASS: V1.6 INPUT-FIDELITY REOPEN REPLACEMENT GREEN"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("exactly one replacement reopen card",
                  "card-owned inventory registration",
                  "section without a registration",
                  "registration without its section", "exceptionless"):
        require(token in text, f"replacement authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY REOPEN RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["artifacts"] == {}
            and "input_capture_main" in value["error"]["message"]
            and "input_capture_helper" in value["error"]["message"],
            "reopen Final Red predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
    PREV.INVOCATION = PREFLIGHT / "card-invocation.json"
    PREV.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    PREV.PRODUCT_PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
    PREV.PRODUCER_RESULT = BUILD / "producer-result.json"
    PREV.SCOPE_RESULT = BUILD / "owner-scope-result.json"
    PREV.ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
    PREV.ABI_REPORT = PREV.abi_report_path(BUILD)
    PREV.HOST_REPORT = BUILD / "input-fidelity-reopen-host.json"
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.STATUS = STATUS


def registration_gate() -> dict[str, Any]:
    value = FIDELITY.inventory_registration_gate()
    require(value["status"] == "passed-two-world-card-owned-registration"
            and value["R1_world"]["names"] == []
            and len(value["capture_world"]["names"]) == 4
            and value["mutations_rejected"] == [
                "section-without-registration", "registration-without-section"],
            "replacement inventory registration gate drift")
    return value


def preflight() -> None:
    predecessor(); authorization(); registration = registration_gate()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "reopen replacement is one-shot")
    configure_module()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["replacement_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["card_owned_inventory_registration"] = registration
    value["status"] = "PASS: INPUT-FIDELITY REOPEN REPLACEMENT ARMED 0/1"
    value["format"] = FORMAT + "-preflight"
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity reopen replacement: PREFLIGHT PASS "
          "card=0/1 inventory=0-or-4 mutations=2")


def card() -> None:
    predecessor(); authorization()
    configure_module()
    persisted = load(PREFLIGHT / "preflight.json")
    require(persisted["status"] in {
                "PASS: INPUT-FIDELITY REOPEN REPLACEMENT ARMED 0/1",
                "PASS: INPUT-FIDELITY GRAPH-REBIND REPLACEMENT ARMED 0/1"}
            and persisted["card_owned_inventory_registration"] ==
                registration_gate(), "replacement persisted preflight drift")
    # The inherited lifecycle consumes exactly one new card under rebound
    # paths; all product, scope, acceptance and host gates remain unchanged.
    PREV.card()
    value = load(RECEIPT)
    value["format"] = FORMAT; value["status"] = STATUS
    value["replacement_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["card_owned_inventory_registration"] = registration_gate()
    value["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 input fidelity reopen replacement: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module()
    {"_dry": PREV.dry_child, "_produce": PREV.produce_child,
     "_scope": PREV.scope_child, "_accept": PREV.acceptance_child,
     "_r1_arm": lambda: print(json.dumps(PREV.R1_TOP.arm(), sort_keys=True))
     }[action]()


def record_red(error: Exception) -> None:
    configure_module()
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["format"] = FORMAT + "-final-red"
        value["status"] = (
            "FINAL RED: INPUT-FIDELITY REOPEN REPLACEMENT RETURNS TO OWNER")
        value["replacement_authority"] = authorization()
        value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
        value["retry_authorized"] = False
        value["owner_disposition_required"] = True
        FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 input fidelity reopen replacement: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 input fidelity reopen replacement: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity reopen replacement: CHECK ARMED")
    else:
        print("v1.6 input fidelity reopen replacement: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm"))
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
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
