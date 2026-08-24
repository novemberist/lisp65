#!/usr/bin/env python3
"""Run the real-consumer phase-output successor hybrid card."""

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

import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_input_service_hybrid_phase_output_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-preflight"
QUALIFICATION = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-qualification"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-consumption-profile-probe-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-phase-output-consumption-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-phase-output-consumption-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-phase-output-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "cf35c79c"
FORMAT = "lisp65-c2-v160-input-service-hybrid-phase-output-consumption-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID PHASE-OUTPUT REAL CONSUMER ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN"


class CardError(RuntimeError): pass


def require(value: bool, message: str) -> None:
    if not value: raise CardError(message)


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


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("self-disposition 2/3", "exactly one successor card",
                  "deepest reopen configurator", "real-consumer preflight",
                  "mutating the input back to the wplto root"):
        require(token in text, f"real-consumer successor authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: V1.6 HYBRID PHASE-OUTPUT REPLACEMENT STOPS"
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["retry_authorized"] is False
            and "wplto/c2-asm-leaf-abi.json" in value["error"]["message"],
            "phase-output real-consumer predecessor drift")
    return value


def install_paths() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.QUALIFICATION = QUALIFICATION; PREV.ABI_REPORT = ABI_REPORT
    PREV.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    PREV.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    PREV.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    PREV.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS


def configure_module(*, mutant: bool = False) -> None:
    install_paths()
    if mutant:
        PREV.QUALIFICATION = BUILD / "wplto"
        PREV.ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
    PREV.configure_module()


def real_consumer_gate(*, mutant: bool = False) -> dict[str, Any]:
    configure_module(mutant=mutant)
    expected = ABI_REPORT
    require(REOPEN.ABI_REPORT == expected,
            "deepest reopen configurator did not consume phase-owned ABI root")
    require(REOPEN.abi_report_path(BUILD) == expected,
            "derived ABI report path differs from real consumer")
    return {"status": "passed-real-configurator-consumes-phase-output",
        "qualification_root": QUALIFICATION.relative_to(ROOT).as_posix(),
        "report": expected.relative_to(ROOT).as_posix(),
        "real_consumer": "c2_v160_input_fidelity_reopen_replacement_card.configure_module"}


def preflight() -> None:
    predecessor(); auth = authority(); install_paths()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, QUALIFICATION,
        REAL_PROBE_BUILD, REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD,
        HYBRID_PROBE_PREFLIGHT, RECEIPT, FINAL_RED)),
        "phase-output real-consumer successor is one-shot")
    real = real_consumer_gate()
    rejected = False
    try: real_consumer_gate(mutant=True)
    except CardError: rejected = True
    require(rejected, "WPLTO-root real-consumer mutation survived pre-card")
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "real_consumer_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "phase_output_real_consumer": real,
        "WPLTO_root_mutation_rejected": True,
        "phase_output_self_disposition": {"budget": 3,
            "sequence_after_reset": 2, "cards_authorized": 1,
            "cards_consumed": 0}, "product_change": False})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid phase-output consumption: PREFLIGHT PASS card=0/1 real-consumer=green")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["phase_output_real_consumer"] == real_consumer_gate()
            and value["WPLTO_root_mutation_rejected"] is True,
            "persisted phase-output real-consumer preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    require(ABI_REPORT.is_file()
            and not (BUILD / "wplto/c2-asm-leaf-abi.json").exists(),
            "completed real consumer violated phase-output ownership")
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "real_consumer_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "phase_output_real_consumer": {**real_consumer_gate(),
                                       "artifact": bind(ABI_REPORT)},
        "WPLTO_root_mutation_rejected": True,
        "phase_output_self_disposition": {"budget": 3,
            "sequence_after_reset": 2, "cards_authorized": 1,
            "cards_consumed": 1}, "product_change": False,
        "next": "independent review, then owner device acceptance items 1 and 2"})
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid phase-output consumption: CARD PASS card=1/1 review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 HYBRID PHASE-OUTPUT CONSUMPTION STOPS",
            "real_consumer_authority": authority(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "retry_authorized": False,
            "next": "classify under standing self-disposition rules; no silent retry"})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_real_consumer_probe",
        "_membership_probe", "_hybrid_profile_probe", "_finalize_red", "_dry",
        "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid phase-output consumption:",
        "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists()
        else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists() else "CHECK LOCKED")
    else: configure_module(); PREV.route(action)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"phase-output consumption Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 hybrid phase-output consumption: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
