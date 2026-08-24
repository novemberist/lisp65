#!/usr/bin/env python3
"""Run the broadened identity-scoped owner-registry replacement card."""

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

import c2_v160_input_fidelity_owner_scope_conversion as CONVERSION  # noqa: E402
import c2_v160_input_fidelity_owner_scope_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-owner-scope-family-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-owner-scope-family-preflight"
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-owner-scope-family-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-owner-scope-family-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-owner-scope-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "0b1d2bbf"
FORMAT = "lisp65-c2-v160-input-fidelity-owner-scope-family-card-v1"
STATUS = "PASS: INPUT-FIDELITY OWNER-SCOPE FAMILY REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY OWNER-SCOPE FAMILY GREEN"


class FamilyCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FamilyCardError(message)


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
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("self-disposition 2/3", "broaden once",
                  "every writer", "global selected set remains global",
                  "exactly one replacement card"):
        require(token in text, f"owner-scope family authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] == "FINAL RED: INPUT-FIDELITY OWNER SCOPE STOPS"
            and value["retry_authorized"] is False
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "cards_authorized": 1,
                "cards_consumed": 1, "device_contacts": 0,
                "media_builds": 0, "product_link_attempts": 1}
            and value["self_disposition"]["sequence_after_reset"] == 1
            and "source-owner companion escaped trigger" in
                value["error"]["message"],
            "owner-scope family predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.STATUS = STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.SELF_DISPOSITION_SEQUENCE = 2
    PREV.configure_module()


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "owner-scope family replacement is one-shot")
    conversion = CONVERSION.run_probe()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value["format"] = FORMAT + "-preflight"; value["status"] = STATUS
    value["owner_scope_family_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["identity_scoped_writer_family"] = conversion
    value["self_disposition"] = {"sequence_after_reset": 2,
        "budget": 3, "cards_authorized": 1, "cards_consumed": 0}
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity owner scope family: PREFLIGHT PASS card=0/1 "
          "writers=5 mutation=red")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == STATUS
            and value["identity_scoped_writer_family"] == CONVERSION.run_probe()
            and len(value["identity_scoped_writer_family"]["writer_family"]) == 5,
            "persisted owner-scope family preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["owner_scope_family_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["identity_scoped_writer_family"] = value[
        "identity_scoped_writer_family"]
    receipt["self_disposition"] = {"sequence_after_reset": 2,
        "budget": 3, "cards_authorized": 1, "cards_consumed": 1}
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity owner scope family: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY OWNER-SCOPE FAMILY STOPS"
    value["owner_scope_family_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["identity_scoped_writer_family"] = CONVERSION.run_probe()
    value["self_disposition"] = {"sequence_after_reset": 2,
        "budget": 3, "cards_authorized": 1, "cards_consumed": 1}
    value["retry_authorized"] = False
    value["next"] = "classify under standing delegation; no silent retry"
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 input fidelity owner scope family: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 input fidelity owner scope family: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity owner scope family: CHECK ARMED")
    else:
        print("v1.6 input fidelity owner scope family: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "card":
        card()
    elif action == "check":
        check()
    elif action == "_full_probe":
        configure_module(); PREV.PREV.full_consumer_probe_child(mutant=False)
    elif action == "_full_probe_mutant":
        configure_module(); PREV.PREV.full_consumer_probe_child(mutant=True)
    elif action == "_default_probe":
        configure_module(); PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module()
        print(json.dumps(
            PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(),
            sort_keys=True))
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
                print(f"owner-scope family Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 input fidelity owner scope family: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
