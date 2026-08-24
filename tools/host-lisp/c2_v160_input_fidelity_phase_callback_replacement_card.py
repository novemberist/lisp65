#!/usr/bin/env python3
"""Run the real-consumer-bound phase callback replacement card."""

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

import c2_v160_input_fidelity_phase_guard_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-phase-callback-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-phase-callback-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-phase-callback-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-phase-callback-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-phase-guard-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "3fa4a5d1"
FORMAT = "lisp65-c2-v160-input-fidelity-phase-callback-card-v1"
STATUS = "PASS: INPUT-FIDELITY PHASE-CALLBACK REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY PHASE-CALLBACK REPLACEMENT GREEN"


class PhaseCallbackError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseCallbackError(message)


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
    for token in ("at this seam", "exactly one replacement card",
                  "last configuration edge", "actual dry child",
                  "restoring the predecessor callback", "exceptionless"):
        require(token in text, f"phase-callback authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY PHASE GUARD RETURNS TO REVIEW"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_link_attempts"] == 0
            and value["attribution"]["classification"] ==
                "inherited-child-reconfiguration-replaced-phase-callback-before-real-consumer",
            "phase-callback predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()
    # The setup-owner adapter re-reads this module slot during every inherited
    # child configuration. Bind there, at the final edge its consumer uses.
    setup_adapter = PREV.PREV
    setup_adapter.setup_owned = PREV.phase_setup
    reopen = PREV.PREV.PREV.PREV.PREV
    reopen.setup = PREV.phase_setup
    reopen.PREFLIGHT_STATUS_VOCABULARY.add(STATUS)


def callback_consumer_gate(value: dict[str, Any]) -> dict[str, Any]:
    handoff_path = (PREFLIGHT / "real-producer-dry-preflight" /
                    "setup-ownership-boundary.json")
    handoff = load(handoff_path)

    def validate(candidate: dict[str, Any]) -> None:
        require(candidate.get("phase") == "produce"
                and candidate.get("producer_root_absent_at_handoff") is True,
                "real dry child did not consume phase_setup")

    validate(handoff)
    mutant = dict(handoff); mutant.pop("phase", None)
    rejected = False
    try:
        validate(mutant)
    except PhaseCallbackError:
        rejected = True
    require(rejected, "restored predecessor callback mutation survived")
    return {"status": "PASS: REAL DRY CHILD CONSUMED PHASE CALLBACK",
        "consumer": "inherited _dry child after final configure_module",
        "witness": bind(handoff_path), "consumed_phase": "produce",
        "predecessor_callback_mutation_rejected": True,
        "outer_preflight_status": value["status"]}


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    PREV.PREV.PREV.PREV.PREV.validate_card_preflight(value)
    mutant = dict(value); mutant["status"] = "PASS: UNKNOWN CALLBACK 0/1"
    rejected = False
    try:
        PREV.PREV.PREV.PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown phase-callback status survived real consumer")
    return {"status": "PASS: REAL CONSUMER ACCEPTS PHASE-CALLBACK STATUS",
        "emitted_status": value["status"],
        "unknown_status_mutation_rejected": True}


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-callback replacement is one-shot")
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    callback = callback_consumer_gate(value)
    value["format"] = FORMAT + "-preflight"; value["status"] = STATUS
    value["phase_callback_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["real_phase_callback_consumer"] = callback
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity phase callback: PREFLIGHT PASS card=0/1 "
          "real-child=phase_setup mutation=red")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == STATUS
            and value["real_phase_callback_consumer"]["consumed_phase"] ==
                "produce"
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted phase-callback preflight drift")
    PREV.PREV.PREV.PREV.PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["phase_callback_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["real_phase_callback_consumer"] = value[
        "real_phase_callback_consumer"]
    receipt["phase_owned_guards"] = value["phase_owned_guards"]
    receipt["setup_ownership"] = value["setup_ownership"]
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["card_owned_inventory_registration"] = value[
        "card_owned_inventory_registration"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity phase callback: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists(): return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY PHASE CALLBACK RETURNS TO REVIEW"
    value["phase_callback_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False; value["review_disposition_required"] = True
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 input fidelity phase callback: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 input fidelity phase callback: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity phase callback: CHECK ARMED")
    else: print("v1.6 input fidelity phase callback: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_owner_graph":
        configure_module(); print(json.dumps(PREV.PREV.PREV.graph_gate(), sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"phase-callback Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity phase callback: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
