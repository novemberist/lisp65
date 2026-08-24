#!/usr/bin/env python3
"""Run the semantic-v16core recovery-sanitization replacement card."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import c2_v160_active_frame_liveness_card as ACTIVE_CARD  # noqa: E402
import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402
import c2_v160_execution_boundary_recovery_sanitization_card as FIRST  # noqa: E402
import c2_v160_execution_boundary_recovery_sanitization_replacement_card as PREVIOUS  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
PREVIOUS_RED = ARCH / (
    "c2.3-v1.6-recovery-sanitization-component-replacement-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-pin-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "8362a4fd"
FORMAT = "lisp65-c2-v160-recovery-sanitization-library-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 RECOVERY SANITIZATION LIBRARY REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RECOVERY SANITIZATION SEMANTIC FINAL WORLD GREEN"


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("known-family self-disposition", "stored size proxy is false",
                  "exactly one replacement card", "semantic boundary fixture",
                  "reintroduced 248 equality"):
        CARD.require(token in text, f"library replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = CARD.load(PREVIOUS_RED); attribution = CARD.load(ATTRIBUTION)
    CARD.require(red["status"] == "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS"
        and red["error"]["message"] == "candidate v16core lost the empty-phase fix"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and attribution["status"] ==
            "ATTRIBUTED: V16CORE EMPTY-PHASE CHECKER PINS CODE SIZE"
        and attribution["decision"]["known_family"] is True
        and attribution["decision"]["product_defect"] is False,
        "library-replacement predecessor drift")
    return {**PREVIOUS.predecessor(), "component_card_Final_Red": CARD.bind(
        PREVIOUS_RED), "library_pin_attribution": CARD.bind(ATTRIBUTION)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-recovery-sanitization-library-replacement-card-final-red.json"
    CARD.DRIVER = DRIVER
    CARD.AUTHORIZATION = AUTHORIZATION
    CARD.FORMAT = FORMAT
    CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    CARD.FINAL_STATUS = FINAL_STATUS
    CARD.EXPECTED_LANDING_BYTES = 32
    CARD.authority = authority
    CARD.predecessor = predecessor
    CARD.install()


def preflight() -> None:
    install()
    price = FIRST.pricing()
    CARD.preflight()
    path = CARD.PREFLIGHT / "preflight.json"
    value = CARD.load(path)
    components = value["active_frame_preflight"]["assembled_price"][
        "component_membership"]
    ACTIVE.validate_component_membership(components, full_section=True)
    value.update({"library_replacement_authority": authority(),
        "component_card_Final_Red": CARD.bind(PREVIOUS_RED),
        "library_pin_attribution": CARD.bind(ATTRIBUTION),
        "recovery_sanitization_pricing": price,
        "component_conversion": components})
    path.write_bytes(CARD.canonical(value))
    print("v1.6 recovery library replacement: PREFLIGHT PASS semantic card=0/1")


def check_receipt() -> dict[str, Any]:
    value = CARD.check_receipt()
    gate = value["execution_boundary_backstop"]
    components = value["active_frame_final_gate"]["enforcement"][
        "component_membership"]
    library = value["candidate_v16core"]
    ACTIVE.validate_component_membership(components, full_section=False)
    ACTIVE_CARD.validate_empty_phase_claim(library["empty_phase_semantic_claim"])
    CARD.require(value["status"] == FINAL_STATUS
        and gate["ordinary_free_bytes"] >= 18
        and gate["mapped_far_service"]["free_bytes"] >= 11
        and components["derived_component_bytes"] == 84
        and library["encoded_bytes"] == library[
            "empty_phase_semantic_claim"]["encoded_bytes"]
        and library["mutations_rejected"] == ["restore-stored-248-size-pin",
            "unfixed-form-accepted", "emitted-object-not-consumed"],
        "semantic-library recovery final receipt drift")
    return value


def card() -> None:
    install()
    pre = CARD.load(CARD.PREFLIGHT / "preflight.json")
    CARD.require(pre["status"] == PREFLIGHT_STATUS
                 and pre["component_conversion"]["derived_component_bytes"] == 84,
                 "library-replacement persisted preflight drift")
    CARD.card()
    check_receipt()
    print("v1.6 recovery library replacement: CARD PASS final-world=green")


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 recovery library replacement: CHECK PASS"); return 0
    return CARD.PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: CARD.record_red(error)
            except Exception as receipt_error:
                print(f"library-replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 recovery library replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
