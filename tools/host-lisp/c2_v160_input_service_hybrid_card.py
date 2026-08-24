#!/usr/bin/env python3
"""Run the owner-released v1.6 adaptive input-service hybrid card."""

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
import c2_v160_input_fidelity_reopen_card as REOPEN  # noqa: E402
import c2_v160_input_fidelity_membership_real_consumer_replacement_card as TOP  # noqa: E402
import c2_v160_input_service_hybrid as HYBRID  # noqa: E402
import c2_v160_input_service_hybrid_capacity_world_attribution as CAPACITY  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-card-preflight"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-profile-probe-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d9f0fdda"
FORMAT = "lisp65-c2-v160-input-service-hybrid-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID ARMED 0/1"
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


def authorization() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("accepted: option 2", "%require-c2d-header-layout-p",
                  "33 slots / 601 name bytes", "first real slot of margin",
                  "no public-name change", "no max_sym price",
                  "released card proceeds"):
        require(token in text, f"hybrid card authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_module() -> None:
    TOP.BUILD = BUILD; TOP.PREFLIGHT = PREFLIGHT
    TOP.PROBE_BUILD = REAL_PROBE_BUILD
    TOP.PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    TOP.RECEIPT = RECEIPT; TOP.FINAL_RED = FINAL_RED
    TOP.DRIVER = DRIVER; TOP.FORMAT = FORMAT
    TOP.PREFLIGHT_STATUS = PREFLIGHT_STATUS; TOP.FINAL_STATUS = FINAL_STATUS
    TOP.configure_module()
    current = REOPEN.configure_stack
    if not getattr(current, "_v160_input_hybrid", False):
        def configure_stack(build: Path = BUILD, preflight: Path = PREFLIGHT,
                            *, activate_capture: bool = True
                            ) -> tuple[Any, dict[str, Any]]:
            core, activation = current(
                build, preflight, activate_capture=activate_capture)
            if activate_capture:
                activation = dict(activation)
                activation["hybrid"] = PRODUCT.configure_input_hybrid()
            return core, activation

        configure_stack._v160_input_hybrid = True  # type: ignore[attr-defined]
        REOPEN.configure_stack = configure_stack


def hybrid_profile_probe_child() -> None:
    configure_module()
    probe_build = HYBRID_PROBE_BUILD
    probe_preflight = HYBRID_PROBE_PREFLIGHT
    _core, activation = REOPEN.configure_stack(probe_build, probe_preflight)
    features = PRODUCT.input_capture_compile_profile(
        tuple(PRODUCT.CONVERGENCE_DEFINES))
    sources = PRODUCT.source_list(features)
    capture_path = PRODUCT.INPUT_CAPTURE_SOURCE.resolve()
    consumer_path = PRODUCT.INPUT_HYBRID_SOURCE.resolve()
    selected_paths = {Path(source).resolve() for source in sources}
    capture = capture_path.relative_to(ROOT).as_posix()
    consumer = consumer_path.relative_to(ROOT).as_posix()
    registration = PRODUCT.input_capture_inventory_registration(features)
    require(features.count(PRODUCT.INPUT_CAPTURE_FEATURE) == 1
            and features.count(PRODUCT.INPUT_HYBRID_FEATURE) == 1
            and capture_path in selected_paths and consumer_path in selected_paths
            and registration["hybrid_selected"] is True
            and len(registration["allocated"]) == 3,
            "real compiler profile did not consume hybrid build membership")
    value = {"status": "passed-real-profile-hybrid-consumption",
            "activation": activation, "features": list(features),
            "capture_source": capture, "consumer_source": consumer,
            "inventory": registration}
    print(json.dumps(value, sort_keys=True))


def run_hybrid_profile_probe() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER),
        "_hybrid_profile_probe"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"fresh-process hybrid profile probe red: {result.stderr}")
    value = json.loads(result.stdout)
    require(value["status"] == "passed-real-profile-hybrid-consumption",
            "fresh-process hybrid profile receipt drift")
    return value


def preflight() -> None:
    authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not REAL_PROBE_BUILD.exists()
            and not REAL_PROBE_PREFLIGHT.exists()
            and not HYBRID_PROBE_BUILD.exists()
            and not HYBRID_PROBE_PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "adaptive hybrid card is one-shot")
    hybrid = HYBRID.derive()
    capacity = CAPACITY.derive()
    require(capacity["capacity"]["with_optional_reclaim"] == {
                "symbol_slots": 33, "namepool_bytes": 601}
            and capacity["capacity"]["with_optional_reclaim_margin"] == {
                "symbol_slots": 1, "namepool_bytes": 217}
            and capacity["proven_optional_reclaim"]["functions_after"] == 387,
            "corrected live-world capacity contract drift")
    profile = run_hybrid_profile_probe()
    configure_module()
    TOP.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value["format"] = FORMAT + "-preflight"
    value["status"] = PREFLIGHT_STATUS
    value["hybrid_authority"] = authority
    value["hybrid_host_gates"] = hybrid
    value["corrected_capacity_world"] = capacity
    value["real_hybrid_profile"] = profile
    value["attempt_accounting"] = {"cards_consumed": 0, "WPLTO_runs": 0,
        "product_links": 0, "media_builds": 0, "device_contacts": 0}
    path.write_bytes(canonical(value))
    print("v1.6 adaptive input-service hybrid: PREFLIGHT PASS "
          "card=0/1 capacity=33/601 profile=consumed")


def card() -> None:
    authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["corrected_capacity_world"]["capacity"]
                ["with_optional_reclaim"]["symbol_slots"] == 33
            and value["real_hybrid_profile"]["status"] ==
                "passed-real-profile-hybrid-consumption",
            "persisted hybrid preflight drift")
    TOP.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["hybrid_authority"] = authority
    receipt["hybrid_host_gates"] = HYBRID.derive()
    receipt["corrected_capacity_world"] = value["corrected_capacity_world"]
    receipt["real_hybrid_profile"] = value["real_hybrid_profile"]
    receipt["next"] = "independent review, then owner device acceptance items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 adaptive input-service hybrid: CARD PASS card=1/1 "
          "review=required device=closed")


def child(action: str) -> None:
    configure_module(); TOP.child(action)


def record_red(error: Exception) -> None:
    configure_module(); TOP.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: V1.6 ADAPTIVE INPUT-SERVICE HYBRID STOPS"
    value["hybrid_authority"] = authorization()
    value["retry_authorized"] = False
    value["next"] = "classify under standing self-disposition rules; no silent retry"
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 adaptive input-service hybrid: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 adaptive input-service hybrid: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 adaptive input-service hybrid: CHECK ARMED")
    else:
        print("v1.6 adaptive input-service hybrid: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_real_consumer_probe", "_membership_probe", "_finalize_red",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "_default_probe", "_hybrid_profile_probe", "_full_probe",
        "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_real_consumer_probe":
        configure_module(); TOP.real_consumer_probe_child()
    elif action == "_hybrid_profile_probe":
        hybrid_profile_probe_child()
    elif action == "_membership_probe":
        configure_module(); TOP.PREV.membership_probe_child()
    elif action == "_full_probe":
        configure_module(); TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(
            mutant=False)
    elif action == "_full_probe_mutant":
        configure_module(); TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(
            mutant=True)
    elif action == "_default_probe":
        configure_module(); TOP.PREV.PREV.PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module()
        print(json.dumps(
            TOP.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(),
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
                print(f"hybrid Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 adaptive input-service hybrid: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
