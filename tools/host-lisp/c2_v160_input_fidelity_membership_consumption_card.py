#!/usr/bin/env python3
"""Run the one-source input-capture membership replacement card."""

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

import c2_lite_v6_rtov_crc_real_abi_successor_link as PRODUCER  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_input_fidelity_membership_consumption as MEMBERSHIP  # noqa: E402
import c2_v160_input_fidelity_owner_scope_family_replacement_card as PREV  # noqa: E402
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-membership-consumption-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-consumption-preflight")
PROBE_BUILD = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-consumption-probe-build")
PROBE_PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-consumption-probe-preflight")
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-consumption-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-consumption-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-owner-scope-family-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-input-fidelity-placement-escape-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "db9752ac"
FORMAT = "lisp65-c2-v160-input-fidelity-membership-consumption-card-v1"
PREFLIGHT_STATUS = (
    "PASS: INPUT-FIDELITY MEMBERSHIP-CONSUMPTION REPLACEMENT ARMED 0/1")
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY MEMBERSHIP-CONSUMPTION GREEN"


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


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one replacement card", "same single source",
                  "consumption closure", "zero-size witness",
                  "before any wplto"):
        require(token in text, f"membership-consumption authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red, attribution = load(PREDECESSOR_RED), load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: INPUT-FIDELITY OWNER-SCOPE FAMILY STOPS"
            and red["hard_stop"]["mechanism"] == "open"
            and red["hard_stop"]["successors_authorized"] == 0
            and red["attempt_accounting"]["cards_consumed"] == 1
            and attribution["status"] ==
                "ATTRIBUTED: CAPTURE LAYOUT ENABLED BUT OWNER SOURCE NOT CONSUMED"
            and attribution["decision"]["classification"] ==
                "bound-layout-with-unconsumed-source-owner"
            and attribution["decision"]["stored_pre_R1_addresses"] is False
            and attribution["decision"]["holes_shrank_or_require_repricing"]
                is False,
            "membership-consumption predecessor/attribution drift")
    return {"Final_Red": bind(PREDECESSOR_RED),
            "attribution": bind(ATTRIBUTION)}


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()
    current = REOPEN.configure_stack
    if not getattr(current, "_membership_consumption_projection", False):
        def configure_stack(build: Path = BUILD, preflight: Path = PREFLIGHT,
                            *, activate_capture: bool = True
                            ) -> tuple[Any, dict[str, Any]]:
            core, activation = current(
                build, preflight, activate_capture=activate_capture)
            if activate_capture:
                MEMBERSHIP.install_profile_projection(PRODUCT,
                                                       PRODUCER.BASE_LINK)
            return core, activation

        configure_stack._membership_consumption_projection = True  # type: ignore[attr-defined]
        REOPEN.configure_stack = configure_stack
    REOPEN.PREFLIGHT_STATUS_VOCABULARY.add(PREFLIGHT_STATUS)


def membership_probe_child() -> None:
    configure_module()
    require(not PROBE_BUILD.exists() and not PROBE_PREFLIGHT.exists(),
            "membership-consumption probe is one-shot")
    _core, activation = REOPEN.configure_stack(PROBE_BUILD, PROBE_PREFLIGHT)
    require(activation["feature"] == PRODUCT.INPUT_CAPTURE_FEATURE,
            "build configuration did not activate capture membership")
    features = tuple(PRODUCER.BASE_LINK.configure_profile())
    value = MEMBERSHIP.validate_projection(PRODUCT, features)
    print(json.dumps(value, sort_keys=True))


def run_membership_probe() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_membership_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"membership-consumption real-profile probe red: {result.stderr}")
    value = json.loads(result.stdout)
    require(value["status"] == MEMBERSHIP.STATUS
            and len(value["mutations_rejected"]) == 4,
            "membership-consumption probe receipt drift")
    return value


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "membership-consumption replacement is one-shot")
    gate = run_membership_probe()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value["format"] = FORMAT + "-preflight"
    value["status"] = PREFLIGHT_STATUS
    value["membership_consumption_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["placement_escape_attribution"] = bind(ATTRIBUTION)
    value["single_source_membership"] = gate
    value["attempt_accounting"] = {"cards_consumed": 0,
        "WPLTO_runs": 0, "product_links": 0,
        "media_builds": 0, "device_contacts": 0}
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity membership consumption: PREFLIGHT PASS "
          "card=0/1 closure=green zero-size-mutations=2")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["single_source_membership"]["status"] ==
                MEMBERSHIP.STATUS
            and len(value["single_source_membership"]["mutations_rejected"]) == 4,
            "persisted membership-consumption preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["membership_consumption_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["placement_escape_attribution"] = bind(ATTRIBUTION)
    receipt["single_source_membership"] = value["single_source_membership"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity membership consumption: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY MEMBERSHIP CONSUMPTION STOPS"
    value["membership_consumption_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["placement_escape_attribution"] = bind(ATTRIBUTION)
    value["retry_authorized"] = False
    value["next"] = "classify under standing delegation; no silent retry"
    FINAL_RED.write_bytes(canonical(value))


def finalize_red() -> None:
    value = load(FINAL_RED)
    message = value.get("error", {}).get("message", "")
    require("input-capture layout selection escaped build configuration"
                in message
            and value.get("artifacts") == {},
            "membership-consumption pre-WPLTO Red drift")
    value["attempt_accounting"] = {"WPLTO_runs": 0,
        "cards_authorized": 1, "cards_consumed": 1,
        "device_contacts": 0, "media_builds": 0,
        "product_link_attempts": 0}
    value["authority"]["driver"] = bind(DRIVER)
    value["classification"] = {
        "class": "real-consumer-profile-projection-missed",
        "known_family": "bound-is-not-consumed / real-consumer preflight",
        "product_freight_reached": False,
        "permanent_compile_link_closure_fired": True,
        "preflight_direct-adapter-was-not-real-caller": True,
    }
    value["self_disposition"] = {"sequence_after_attribution": 1,
        "budget": 3, "replacement_cards_authorized": 0,
        "replacement_cards_consumed": 0}
    value["self_disposition_budget_exhausted"] = False
    value["owner_disposition_required"] = False
    value["retry_authorized"] = False
    value["next"] = (
        "known-family self-disposition must be bound before one replacement")
    FINAL_RED.write_bytes(canonical(value))
    print("v1.6 input fidelity membership consumption: FINAL RED SEALED "
          "WPLTO=0 link=0 card=1/1")


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 input fidelity membership consumption: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 input fidelity membership consumption: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity membership consumption: CHECK ARMED")
    else:
        print("v1.6 input fidelity membership consumption: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_finalize_red",
        "_membership_probe", "_dry", "_produce", "_scope", "_accept",
        "_r1_arm", "_owner_graph", "_default_probe", "_full_probe",
        "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_finalize_red": finalize_red()
    elif action == "_membership_probe": membership_probe_child()
    elif action == "_full_probe":
        configure_module(); PREV.PREV.PREV.full_consumer_probe_child(mutant=False)
    elif action == "_full_probe_mutant":
        configure_module(); PREV.PREV.PREV.full_consumer_probe_child(mutant=True)
    elif action == "_default_probe":
        configure_module(); PREV.PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module()
        print(json.dumps(
            PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(),
            sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"membership-consumption Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 input fidelity membership consumption: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
