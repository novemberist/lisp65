#!/usr/bin/env python3
"""Run the real-consumer input-capture membership replacement card."""

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_input_fidelity_membership_consumption as MEMBERSHIP  # noqa: E402
import c2_v160_input_fidelity_membership_consumption_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-card")
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-preflight")
PROBE_BUILD = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-probe-build")
PROBE_PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-input-fidelity-membership-real-consumer-probe-preflight")
RECEIPT = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-real-consumer-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-real-consumer-card-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-membership-consumption-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d00e36cc"
FORMAT = "lisp65-c2-v160-input-fidelity-membership-real-consumer-card-v1"
PREFLIGHT_STATUS = (
    "PASS: INPUT-FIDELITY MEMBERSHIP REAL-CONSUMER REPLACEMENT ARMED 0/1")
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY MEMBERSHIP REAL-CONSUMER GREEN"


class CardError(RuntimeError):
    pass


class ProjectionReached(BaseException):
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
    for token in ("self-disposition 1/3", "exactly one replacement card",
                  "inside the real single_link() consumer",
                  "consumption closure", "zero-size witness"):
        require(token in text, f"real-consumer authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY MEMBERSHIP CONSUMPTION STOPS"
            and value["attempt_accounting"] == {"WPLTO_runs": 0,
                "cards_authorized": 1, "cards_consumed": 1,
                "device_contacts": 0, "media_builds": 0,
                "product_link_attempts": 0}
            and value["classification"]["class"] ==
                "real-consumer-profile-projection-missed"
            and value["classification"]["product_freight_reached"] is False
            and value["self_disposition"]["sequence_after_attribution"] == 1
            and value["retry_authorized"] is False,
            "real-consumer replacement predecessor drift")
    return value


def configure_module(*, probe: bool = False) -> None:
    PREV.BUILD = PROBE_BUILD if probe else BUILD
    PREV.PREFLIGHT = PROBE_PREFLIGHT if probe else PREFLIGHT
    PREV.PROBE_BUILD = (PROBE_BUILD / "direct-profile") if probe else (
        PREFLIGHT / "direct-profile")
    PREV.PROBE_PREFLIGHT = (PROBE_PREFLIGHT / "direct-profile") if probe else (
        PREFLIGHT / "direct-profile")
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()


def real_consumer_probe_child() -> None:
    require(not PROBE_BUILD.exists() and not PROBE_PREFLIGHT.exists(),
            "real-consumer membership probe is one-shot")
    # Root absence belongs to the pre-configuration phase.  The configured
    # probe consumer owns and may create these roots afterwards.
    configure_module(probe=True)
    original = PRODUCT.input_capture_compile_profile
    captured: dict[str, Any] = {}

    def observe(definitions: tuple[str, ...]) -> tuple[str, ...]:
        consumed = original(definitions)
        captured.update({"incoming_definitions": list(definitions),
                         "consumed_definitions": list(consumed),
                         "projection": MEMBERSHIP.validate_projection(
                             PRODUCT, consumed)})
        raise ProjectionReached()

    PRODUCT.input_capture_compile_profile = observe
    try:
        PREV.child("_produce")
    except ProjectionReached:
        require(captured.get("projection", {}).get("status") == MEMBERSHIP.STATUS,
                "real single-link caller did not reach membership projection")
        print(json.dumps(captured, sort_keys=True))
    finally:
        PRODUCT.input_capture_compile_profile = original


def run_real_consumer_probe() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER),
        "_real_consumer_probe"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"real single-link membership probe red: {result.stderr}")
    value = json.loads(result.stdout)
    feature = PRODUCT.INPUT_CAPTURE_FEATURE
    require(value["consumed_definitions"].count(feature) == 1
            and value["projection"]["status"] == MEMBERSHIP.STATUS,
            "real single-link membership projection receipt drift")
    return value


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "real-consumer replacement is one-shot")
    real = run_real_consumer_probe()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value["format"] = FORMAT + "-preflight"
    value["status"] = PREFLIGHT_STATUS
    value["real_consumer_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["real_single_link_membership"] = real
    value["attempt_accounting"] = {"cards_consumed": 0,
        "WPLTO_runs": 0, "product_links": 0,
        "media_builds": 0, "device_contacts": 0}
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity membership real consumer: PREFLIGHT PASS "
          "card=0/1 real-single-link=green mutations=4")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["real_single_link_membership"]["projection"]["status"] ==
                MEMBERSHIP.STATUS,
            "persisted real-consumer membership preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["real_consumer_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["real_single_link_membership"] = value[
        "real_single_link_membership"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity membership real consumer: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists(): return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY REAL-CONSUMER MEMBERSHIP STOPS"
    value["real_consumer_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False
    value["next"] = "classify under standing delegation; no silent retry"
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 membership real consumer: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 membership real consumer: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 membership real consumer: CHECK ARMED")
    else: print("v1.6 membership real consumer: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_real_consumer_probe", "_membership_probe", "_finalize_red",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "_default_probe", "_full_probe",
        "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_real_consumer_probe": real_consumer_probe_child()
    elif action == "_membership_probe":
        configure_module(probe=True); PREV.membership_probe_child()
    elif action == "_full_probe":
        configure_module(); PREV.PREV.PREV.PREV.full_consumer_probe_child(
            mutant=False)
    elif action == "_full_probe_mutant":
        configure_module(); PREV.PREV.PREV.PREV.full_consumer_probe_child(
            mutant=True)
    elif action == "_default_probe":
        configure_module(); PREV.PREV.PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module()
        print(json.dumps(
            PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(),
            sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"real-consumer Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 membership real consumer: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
