#!/usr/bin/env python3
"""Run the phase-owner-bound v1.6 input-fidelity replacement card."""

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

import c2_v160_input_fidelity_live_path_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-phase-owner-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-phase-owner-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-phase-owner-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-phase-owner-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-live-path-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "44c6f7a8"
FORMAT = "lisp65-c2-v160-input-fidelity-phase-owner-card-v1"
STATUS = "PASS: INPUT-FIDELITY PHASE-OWNER REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY PHASE-OWNER REPLACEMENT GREEN"
PHASE = PREV.PREV.PREV
ORIGINAL_PHASE_SETUP = PHASE.phase_setup


class PhaseOwnerError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseOwnerError(message)


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
    for token in ("final autonomous replacement", "exactly one replacement card",
                  "phase module's owning slot", "complete child configuration chain",
                  "restoring the phase predecessor", "no fourth self-disposition"):
        require(token in text, f"phase-owner authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] == "FINAL RED: INPUT-FIDELITY LIVE PATH RETURNS TO REVIEW"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_link_attempts"] == 0
            and value["attribution"]["classification"] ==
                "full-child-configuration-restored-phase-owner-slot-after-direct-live-path-probe",
            "phase-owner predecessor drift")
    return value


def phase_owner_setup(build: Path | None = None,
                      preflight: Path | None = None) -> tuple[Any, dict[str, Any]]:
    return ORIGINAL_PHASE_SETUP(BUILD if build is None else build,
                                PREFLIGHT if preflight is None else preflight)


def configure_module(*, mutant: bool = False) -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()
    owner = ORIGINAL_PHASE_SETUP if mutant else phase_owner_setup
    PHASE.phase_setup = owner
    setup_adapter = PREV.PREV.PREV.PREV
    setup_adapter.setup_owned = owner
    reopen = PREV.PREV.PREV.PREV.PREV.PREV.PREV
    reopen.setup = owner
    reopen.PREFLIGHT_STATUS_VOCABULARY.add(STATUS)


def full_consumer_probe_child(*, mutant: bool) -> None:
    configure_module(mutant=mutant)
    reopen = PREV.PREV.PREV.PREV.PREV.PREV.PREV
    original = reopen.produce_child

    def stop_after_real_setup() -> None:
        reopen.setup()
        handoff = load(PREFLIGHT / "setup-ownership-boundary.json")
        print(json.dumps(handoff, sort_keys=True))

    reopen.produce_child = stop_after_real_setup
    try:
        PREV.child("_produce")
    finally:
        reopen.produce_child = original


def run_full_probe(*, mutant: bool = False) -> subprocess.CompletedProcess[str]:
    action = "_full_probe_mutant" if mutant else "_full_probe"
    return subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def full_consumer_gate(value: dict[str, Any]) -> dict[str, Any]:
    result = run_full_probe()
    require(result.returncode == 0,
            f"full real-caller phase-owner probe red: {result.stderr}")
    handoff = json.loads(result.stdout)
    require(handoff["producer_root"] == BUILD.relative_to(ROOT).as_posix()
            and handoff["setup_scope"] == PREFLIGHT.relative_to(ROOT).as_posix()
            and handoff["phase"] == "produce",
            "full real caller consumed non-candidate roots")
    mutant = run_full_probe(mutant=True)
    require(mutant.returncode != 0,
            "restored phase predecessor survived full real caller")
    return {"status": "PASS: FULL CHILD CONSUMES PHASE-OWNER CALLBACK",
        "consumer": "complete inherited _produce chain through parameterless setup",
        "producer_root": handoff["producer_root"],
        "setup_scope": handoff["setup_scope"],
        "phase_predecessor_mutation_rejected": True,
        "WPLTO_runs": 0, "product_links": 0,
        "outer_preflight_status": value["status"]}


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    PREV.PREV.PREV.PREV.PREV.PREV.PREV.validate_card_preflight(value)
    mutant = dict(value); mutant["status"] = "PASS: UNKNOWN PHASE OWNER 0/1"
    rejected = False
    try:
        PREV.PREV.PREV.PREV.PREV.PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown phase-owner status survived real consumer")
    return {"status": "PASS: REAL CONSUMER ACCEPTS PHASE-OWNER STATUS",
        "emitted_status": value["status"],
        "unknown_status_mutation_rejected": True}


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-owner replacement is one-shot")
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    full = full_consumer_gate(value)
    value["format"] = FORMAT + "-preflight"; value["status"] = STATUS
    value["phase_owner_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["full_real_caller_phase_owner"] = full
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity phase owner: PREFLIGHT PASS card=0/1 "
          "full-real-caller=green mutation=red")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == STATUS
            and value["full_real_caller_phase_owner"]["producer_root"] ==
                BUILD.relative_to(ROOT).as_posix()
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted phase-owner preflight drift")
    PREV.PREV.PREV.PREV.PREV.PREV.PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["phase_owner_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["full_real_caller_phase_owner"] = value[
        "full_real_caller_phase_owner"]
    receipt["phase_owned_guards"] = value["phase_owned_guards"]
    receipt["setup_ownership"] = value["setup_ownership"]
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["card_owned_inventory_registration"] = value[
        "card_owned_inventory_registration"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity phase owner: CARD PASS card=1/1 device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists(): return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY PHASE OWNER RETURNS TO REVIEW"
    value["phase_owner_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False; value["review_disposition_required"] = True
    value["self_disposition_budget_exhausted"] = True
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 input fidelity phase owner: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 input fidelity phase owner: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity phase owner: CHECK ARMED")
    else: print("v1.6 input fidelity phase owner: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_full_probe": full_consumer_probe_child(mutant=False)
    elif action == "_full_probe_mutant": full_consumer_probe_child(mutant=True)
    elif action == "_default_probe":
        configure_module(); PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module(); print(json.dumps(PREV.PREV.PREV.PREV.PREV.graph_gate(),
                                             sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"phase-owner Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity phase owner: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
