#!/usr/bin/env python3
"""Run the one authorized semantic-longjmp hybrid successor card."""

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

import c2_v160_input_service_hybrid_irq_identity_replacement_card as PREV  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-preflight"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-longjmp-profile-probe-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-longjmp-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-longjmp-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-irq-replacement-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "0e2d170d"
FORMAT = "lisp65-c2-v160-input-service-hybrid-longjmp-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID SEMANTIC-LONGJMP CARD ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN"

class CardError(RuntimeError): pass

def require(value: bool, message: str) -> None:
    if not value: raise CardError(message)

def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()

def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text()); require(isinstance(value, dict), "JSON object required")
    return value

def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}

def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("self-disposition 2/3", "exactly one successor card",
                  "no product change", "semantically equivalent",
                  "accumulator-only identity"):
        require(token in text, f"longjmp successor authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] == "FINAL RED: V1.6 HYBRID IRQ-IDENTITY REPLACEMENT STOPS"
            and value["error"]["message"] == "native longjmp capture disable absent from final ELF"
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["retry_authorized"] is False,
            "semantic-longjmp predecessor drift")
    return value

def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.REAL_PROBE_BUILD = REAL_PROBE_BUILD; PREV.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    PREV.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD; PREV.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED; PREV.DRIVER = DRIVER
    PREV.FORMAT = FORMAT; PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()

def preflight() -> None:
    predecessor(); auth = authority()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, REAL_PROBE_BUILD,
        REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD, HYBRID_PROBE_PREFLIGHT,
        RECEIPT, FINAL_RED)), "semantic-longjmp card is one-shot")
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "longjmp_authority": auth, "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "longjmp_identity": {"authority": "semantic-immediate-ff-store-to-ring-tail",
                              "accumulator_only_pin_rejected": True,
                              "product_change": False}})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid semantic-longjmp: PREFLIGHT PASS card=0/1")

def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["longjmp_identity"]["accumulator_only_pin_rejected"],
            "persisted semantic-longjmp preflight drift")
    PREV.card(); receipt = load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "longjmp_authority": auth, "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "longjmp_identity": value["longjmp_identity"],
        "next": "independent review, then owner device acceptance items 1 and 2"})
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid semantic-longjmp: CARD PASS card=1/1 review=required")

def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 HYBRID SEMANTIC-LONGJMP CARD STOPS",
            "longjmp_authority": authority(), "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "retry_authorized": False,
            "next": "self-disposition budget exhausted after this seam if red"})
        FINAL_RED.write_bytes(canonical(value))

def route(action: str) -> None:
    configure_module(); base = PREV.BASE
    if action == "_hybrid_profile_probe": base.hybrid_profile_probe_child()
    elif action == "_real_consumer_probe": base.TOP.real_consumer_probe_child()
    elif action == "_membership_probe": base.TOP.PREV.membership_probe_child()
    elif action == "_full_probe": base.TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(mutant=False)
    elif action == "_full_probe_mutant": base.TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(mutant=True)
    elif action == "_default_probe": base.TOP.PREV.PREV.PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph": print(json.dumps(base.TOP.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(), sort_keys=True))
    else: base.TOP.child(action)

def main() -> int:
    choices = ("preflight", "card", "check", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce", "_scope",
        "_accept", "_r1_arm", "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("action", choices=choices)
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid semantic-longjmp:", "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists() else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists() else "CHECK LOCKED")
    else: route(action)
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error: print(f"semantic-longjmp Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 hybrid semantic-longjmp: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
