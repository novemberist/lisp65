#!/usr/bin/env python3
"""Run the component-aware recovery-sanitization replacement card."""

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
import c2_v160_execution_boundary_backstop_card as CARD  # noqa: E402
import c2_v160_execution_boundary_recovery_sanitization_card as FIRST  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.6-recovery-sanitization-preflight-red-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "8fc42756"
FORMAT = "lisp65-c2-v160-recovery-sanitization-component-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 RECOVERY SANITIZATION COMPONENT REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RECOVERY SANITIZATION COMPONENT FINAL WORLD GREEN"


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("component-aware conversion", "additive-membership rule",
                  "unregistered component falls", "the product card run",
                  "18 ordinary-text and 11 far-service bytes"):
        CARD.require(token in text, f"component-replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = CARD.load(RED_ATTRIBUTION)
    CARD.require(red["status"] ==
        "ATTRIBUTED: ACTIVE-FRAME GATE PINS PRE-SPLIT OWNER SHAPE"
        and red["decision"]["class"] == "stored-world owner projection"
        and red["attempt_accounting"]["cards_consumed"] == 0
        and red["drift"]["observed_recovery_sanitization_world"] == {
            "active_frame_stack_access_counts": {
                "read_stack_return_high": 1, "read_stack_return_low": 1,
                "write_stack_return_high": 1, "write_stack_return_low": 1},
            "active_frame_walker_bytes": 41,
            "far_liveness_section_bytes": 84,
            "ordinary_recovery_entry_bytes": 9,
            "shared_saved_CSR_walker_bytes": 43},
        "component-replacement predecessor drift")
    return {**FIRST.predecessor(),
            "precard_Red_attribution": CARD.bind(RED_ATTRIBUTION)}


def install() -> None:
    CARD.BUILD = ROOT / "build/c2.3/v1.6-recovery-sanitization-component-replacement-card"
    CARD.PREFLIGHT = ROOT / "build/c2.3/v1.6-recovery-sanitization-component-replacement-preflight"
    CARD.PROCESS = ROOT / "build/c2.3/v1.6-recovery-sanitization-component-replacement-process"
    CARD.INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-recovery-sanitization-component-replacement-inherited-process"
    CARD.RECEIPT = ARCH / "c2.3-v1.6-recovery-sanitization-component-replacement-card-receipt.json"
    CARD.FINAL_RED = ARCH / "c2.3-v1.6-recovery-sanitization-component-replacement-card-final-red.json"
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
    CARD.require(components["mutations_rejected"] == [
        "single-component-equality", "unregistered-component",
        "duplicate-component-owner"],
        "component-aware mutation receipt drift")
    value.update({"component_conversion_authority": authority(),
        "precard_Red_attribution": CARD.bind(RED_ATTRIBUTION),
        "recovery_sanitization_pricing": price,
        "component_conversion": components})
    path.write_bytes(CARD.canonical(value))
    print("v1.6 recovery component replacement: PREFLIGHT PASS 41+43=84 card=0/1")


def check_receipt() -> dict[str, Any]:
    value = CARD.check_receipt()
    gate = value["execution_boundary_backstop"]
    active = value["active_frame_final_gate"]["enforcement"][
        "component_membership"]
    ACTIVE.validate_component_membership(active, full_section=False)
    CARD.require(value["status"] == FINAL_STATUS
        and gate["ordinary_free_bytes"] >= 18
        and gate["mapped_far_service"]["free_bytes"] >= 11
        and active["derived_component_bytes"] == 84
        and active["mutations_rejected"] == ["single-component-equality",
            "unregistered-component", "duplicate-component-owner"],
        "component-aware recovery final receipt drift")
    return value


def card() -> None:
    install()
    pre = CARD.load(CARD.PREFLIGHT / "preflight.json")
    CARD.require(pre["status"] == PREFLIGHT_STATUS
                 and pre["component_conversion"]["derived_component_bytes"] == 84,
                 "component-replacement persisted preflight drift")
    CARD.card()
    check_receipt()
    print("v1.6 recovery component replacement: CARD PASS final-world=green")


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 recovery component replacement: CHECK PASS"); return 0
    return CARD.PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: CARD.record_red(error)
            except Exception as receipt_error:
                print(f"component-replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 recovery component replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
