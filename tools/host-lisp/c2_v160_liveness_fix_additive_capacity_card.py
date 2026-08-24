#!/usr/bin/env python3
"""Run the additive successor to the liveness capacity card."""

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

import c2_v160_liveness_fix_capacity_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-additive-capacity-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-liveness-fix-additive-capacity-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-liveness-fix-additive-capacity-process"
NORMAL_BUILD = PROCESS / "normal-build"; NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"; MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-liveness-fix-additive-capacity-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-additive-capacity-card-final-red.json"
IMMEDIATE_RED = ARCH / "c2.3-v1.6-liveness-fix-capacity-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "cd01a8c0"
FORMAT = "lisp65-c2-v160-liveness-additive-capacity-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 LIVENESS ADDITIVE CAPACITY ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX FINAL WORLD GREEN"
TAG = "retirement-liveness-additive-capacity"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("self-disposition 3/3", "additive-projection-not-substitution",
                  "exactly one successor card", "zero wpltos", "any further red"):
        require(token in text, f"additive capacity authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(IMMEDIATE_RED)
    require(value["status"] == "FINAL RED: V1.6 LIVENESS CAPACITY REPLACEMENT STOPS"
            and value["error"]["message"] == "persisted owner-scope preflight drift"
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_link_attempts"] == 0
            and not value["artifacts"] and value["retry_authorized"] is False,
            "additive capacity predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT; PREV.PROCESS = PROCESS
    PREV.NORMAL_BUILD = NORMAL_BUILD; PREV.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    PREV.MUTANT_BUILD = MUTANT_BUILD; PREV.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    PREV.PRODUCT_ELF = PRODUCT_ELF; PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED; PREV.DRIVER = DRIVER
    PREV.IMMEDIATE_RED = IMMEDIATE_RED
    PREV.AUTHORIZATION = AUTHORIZATION; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.TAG = TAG; PREV.authority = authority; PREV.predecessor = predecessor


def append(path: Path) -> None:
    value = load(path)
    value.update({"additive_capacity_authority": authority(),
        "immediate_Final_Red": bind(IMMEDIATE_RED),
        "liveness_card_family": {"self_disposition": "3/3",
            "inherited_self_disposition_preserved": True,
            "next_red_returns_to_review": True}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); authority(); configure_module(); PREV.preflight()
    append(PREFLIGHT / "preflight.json")
    print("v1.6 liveness additive capacity: PREFLIGHT PASS card=0/1")


def card() -> None:
    predecessor(); authority(); configure_module(); PREV.card()
    append(RECEIPT)
    print("v1.6 liveness additive capacity: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 LIVENESS ADDITIVE CAPACITY RETURNS TO REVIEW",
            "additive_capacity_authority": authority(),
            "immediate_Final_Red": bind(IMMEDIATE_RED),
            "family_self_disposition_exhausted": True,
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe", "_process_probe_mutant",
        "_contract_probe", "_contract_probe_mutant", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce", "_scope", "_accept",
        "_r1_arm", "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    configure_module()
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        value = load(RECEIPT); require(value["status"] == FINAL_STATUS,
            "additive capacity receipt drift")
        print("v1.6 liveness additive capacity: CHECK PASS")
    else:
        PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"additive capacity Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 liveness additive capacity: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
