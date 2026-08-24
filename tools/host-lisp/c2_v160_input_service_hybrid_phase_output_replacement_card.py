#!/usr/bin/env python3
"""Run the phase-owned ABI-output replacement hybrid card."""

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
import c2_v160_input_service_hybrid_longjmp_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-preflight"
QUALIFICATION = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-qualification"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-phase-output-projected-profile-probe-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-phase-output-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-phase-output-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-longjmp-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-input-service-hybrid-abi-output-eacces-attribution.json"
PREDECESSOR_PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-input-service-hybrid-longjmp-preflight/preflight.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "bcc4c6ca"
FORMAT = "lisp65-c2-v160-input-service-hybrid-phase-output-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID PHASE-OWNED ABI OUTPUT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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
    for token in ("branch one applies", "self-dispositional with the reset budget",
                  "qualification-owned writable space", "sealed root falls",
                  "outside its owning phase's space"):
        require(token in text, f"phase-output replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    attribution = load(ATTRIBUTION)
    require(red["status"] == "FINAL RED: V1.6 HYBRID SEMANTIC-LONGJMP CARD STOPS"
            and red["retry_authorized"] is False
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1,
            "phase-output predecessor Final Red drift")
    require(attribution["status"] ==
                "ATTRIBUTED: ABI REPORT WRITE TARGET WAS ALREADY SEALED"
            and attribution["decision"]["classification"] == "known-family"
            and attribution["decision"]["self_disposition_budget_reset"] is True
            and attribution["decision"]["product_finding"] is False,
            "accepted EACCES attribution drift")
    return {"Final_Red": red, "attribution": attribution}


def validate_phase_output(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    phase = QUALIFICATION.resolve()
    frozen = (BUILD / "wplto").resolve()
    require(resolved.is_relative_to(phase),
            "qualification report outside phase-owned output root")
    require(not resolved.is_relative_to(frozen),
            "qualification report targets sealed producer root")
    require(resolved == (phase / "c2-asm-leaf-abi.json"),
            "qualification ABI report identity drift")
    return {"status": "passed-phase-owned-output-path",
            "phase_root": phase.relative_to(ROOT).as_posix(),
            "report": resolved.relative_to(ROOT).as_posix(),
            "producer_frozen_root": frozen.relative_to(ROOT).as_posix()}


def phase_output_selftest() -> dict[str, str]:
    rejected: dict[str, str] = {}
    trials = {
        "sealed-producer-root": BUILD / "wplto/c2-asm-leaf-abi.json",
        "outside-owning-phase": BUILD / "c2-asm-leaf-abi.json",
    }
    for name, path in trials.items():
        try:
            validate_phase_output(path)
        except CardError:
            rejected[name] = "rejected-pre-card"
        else:
            raise CardError(f"phase-output mutation survived: {name}")
    require(validate_phase_output(ABI_REPORT)["status"] ==
            "passed-phase-owned-output-path", "real phase-output path rejected")
    return rejected


def project_preflight(value: dict[str, Any]) -> dict[str, Any]:
    """Project only candidate identity fields; sealed proofs stay semantic."""
    old_build = "build/c2.3/v1.6-input-service-hybrid-longjmp-card"
    old_preflight = "build/c2.3/v1.6-input-service-hybrid-longjmp-preflight"
    old_status = "PASS: V1.6 HYBRID SEMANTIC-LONGJMP CARD ARMED 0/1"
    replacements = {
        old_build: BUILD.relative_to(ROOT).as_posix(),
        old_preflight: PREFLIGHT.relative_to(ROOT).as_posix(),
        old_status: PREFLIGHT_STATUS,
    }

    def visit(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: visit(child) for key, child in item.items()}
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, str):
            for old, new in replacements.items():
                item = item.replace(old, new)
        return item

    projected = visit(value)
    require(projected["full_real_caller_phase_owner"]["producer_root"] ==
                BUILD.relative_to(ROOT).as_posix()
            and projected["full_real_caller_phase_owner"]["setup_scope"] ==
                PREFLIGHT.relative_to(ROOT).as_posix()
            and projected["no_argument_real_consumer"]["producer_root"] ==
                BUILD.relative_to(ROOT).as_posix()
            and projected["transitive_output_owner_rebind"]["replacement_build"] ==
                BUILD.relative_to(ROOT).as_posix(),
            "candidate preflight path projection incomplete")
    return projected


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    PREV.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    PREV.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    PREV.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    REOPEN.QUALIFICATION_ROOT = QUALIFICATION
    current = PREV.configure_module
    if not getattr(current, "_v160_phase_owned_abi_output", False):
        def configured() -> None:
            current()

        configured._v160_phase_owned_abi_output = True  # type: ignore[attr-defined]
        PREV.configure_module = configured
    PREV.configure_module()
    require(REOPEN.ABI_REPORT == ABI_REPORT,
            "real consumer did not receive phase-owned ABI report path")


def preflight() -> None:
    predecessor(); auth = authority()
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, QUALIFICATION, REAL_PROBE_BUILD,
        REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD, HYBRID_PROBE_PREFLIGHT,
        RECEIPT, FINAL_RED)), "phase-output replacement is one-shot")
    output_gate = validate_phase_output(ABI_REPORT)
    mutations = phase_output_selftest()
    inherited = load(PREDECESSOR_PREFLIGHT)
    require(inherited["status"] ==
                "PASS: V1.6 HYBRID SEMANTIC-LONGJMP CARD ARMED 0/1"
            and inherited["attempt_accounting"] == {"cards_consumed": 0,
                "WPLTO_runs": 0, "product_links": 0,
                "media_builds": 0, "device_contacts": 0},
            "inherited hybrid preflight drift")
    value = project_preflight(inherited)
    PREFLIGHT.mkdir(parents=True)
    path = PREFLIGHT / "preflight.json"
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "phase_output_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "EACCES_attribution": bind(ATTRIBUTION),
        "phase_owned_ABI_output": output_gate,
        "phase_output_mutations_rejected": mutations,
        "inherited_hybrid_preflight": bind(PREDECESSOR_PREFLIGHT),
        "candidate_preflight_projection": {
            "status": "passed-candidate-path-and-vocabulary-projection",
            "source_world": "hybrid-semantic-longjmp-preflight",
            "projected_fields": ["producer roots", "setup scopes",
                                 "transitive owner roots", "status vocabulary"]},
        "phase_output_self_disposition": {
            "budget": 3, "sequence_after_reset": 1,
            "cards_authorized": 1, "cards_consumed": 0},
        "product_change": False})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid phase-owned output: PREFLIGHT PASS card=0/1 mutations=2")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["phase_owned_ABI_output"] == validate_phase_output(ABI_REPORT)
            and len(value["phase_output_mutations_rejected"]) == 2,
            "persisted phase-output preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    require(ABI_REPORT.is_file() and ABI_REPORT.parent == QUALIFICATION
            and not (BUILD / "wplto/c2-asm-leaf-abi.json").exists(),
            "real qualification consumer violated phase-output ownership")
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "phase_output_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "EACCES_attribution": bind(ATTRIBUTION),
        "phase_owned_ABI_output": {**validate_phase_output(ABI_REPORT),
                                    "artifact": bind(ABI_REPORT)},
        "phase_output_mutations_rejected":
            value["phase_output_mutations_rejected"],
        "phase_output_self_disposition": {
            "budget": 3, "sequence_after_reset": 1,
            "cards_authorized": 1, "cards_consumed": 1},
        "product_change": False,
        "next": "independent review, then owner device acceptance items 1 and 2"})
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid phase-owned output: CARD PASS card=1/1 review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value.update({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 HYBRID PHASE-OUTPUT REPLACEMENT STOPS",
        "phase_output_authority": authority(),
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "EACCES_attribution": bind(ATTRIBUTION),
        "retry_authorized": False,
        "next": "classify under standing self-disposition rules; no silent retry"})
    FINAL_RED.write_bytes(canonical(value))


def route(action: str) -> None:
    configure_module(); PREV.route(action)


def main() -> int:
    choices = ("preflight", "card", "check", "_real_consumer_probe",
        "_membership_probe", "_hybrid_profile_probe", "_finalize_red", "_dry",
        "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices)
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        print("v1.6 hybrid phase-owned output:",
              "CHECK PASS" if RECEIPT.exists() else
              "CHECK FINAL RED" if FINAL_RED.exists() else
              "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists()
              else "CHECK LOCKED")
    else: route(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"phase-output Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 hybrid phase-owned output: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
