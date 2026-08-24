#!/usr/bin/env python3
"""Run the one authorized IRQ-identity replacement hybrid card."""

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

import c2_v160_input_service_hybrid_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-replacement-preflight"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-irq-profile-probe-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-irq-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-irq-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "607a49de"
FORMAT = "lisp65-c2-v160-input-service-hybrid-irq-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID IRQ-IDENTITY REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 ADAPTIVE INPUT-SERVICE HYBRID HOST GREEN"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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
    for token in ("self-disposition 1/3", "exactly one replacement card",
                  "no product change", "owning section plus the unique entry label",
                  "zero-size symbol-body proxy"):
        require(token in text, f"replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: V1.6 ADAPTIVE INPUT-SERVICE HYBRID STOPS"
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["error"]["message"] ==
                "final IRQ does not carry the same-size capture call"
            and value["retry_authorized"] is False,
            "hybrid IRQ replacement predecessor drift")
    return value


def configure_module() -> None:
    BASE.BUILD = BUILD; BASE.PREFLIGHT = PREFLIGHT
    BASE.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    BASE.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    BASE.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    BASE.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    BASE.RECEIPT = RECEIPT; BASE.FINAL_RED = FINAL_RED
    BASE.DRIVER = DRIVER; BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS; BASE.FINAL_STATUS = FINAL_STATUS
    BASE.configure_module()


def preflight() -> None:
    predecessor(); auth = authority()
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, REAL_PROBE_BUILD, REAL_PROBE_PREFLIGHT,
        HYBRID_PROBE_BUILD, HYBRID_PROBE_PREFLIGHT, RECEIPT, FINAL_RED)),
        "IRQ-identity replacement is one-shot")
    configure_module(); BASE.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value["format"] = FORMAT + "-preflight"; value["status"] = PREFLIGHT_STATUS
    value["replacement_authority"] = auth
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["irq_identity_rule"] = {
        "authority": "owning-section-plus-unique-entry-and-call",
        "zero_size_symbol_proxy_rejected": True,
        "product_change": False}
    path.write_bytes(canonical(value))
    print("v1.6 hybrid IRQ identity replacement: PREFLIGHT PASS card=0/1")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["irq_identity_rule"]["zero_size_symbol_proxy_rejected"],
            "persisted IRQ replacement preflight drift")
    BASE.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["replacement_authority"] = auth
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["irq_identity_rule"] = value["irq_identity_rule"]
    receipt["next"] = "independent review, then owner device acceptance items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid IRQ identity replacement: CARD PASS card=1/1 review=required")


def record_red(error: Exception) -> None:
    configure_module(); BASE.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: V1.6 HYBRID IRQ-IDENTITY REPLACEMENT STOPS"
    value["replacement_authority"] = authority()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False
    value["next"] = "classify under standing self-disposition rules; no silent retry"
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_real_consumer_probe", "_membership_probe", "_hybrid_profile_probe",
        "_finalize_red", "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        print("v1.6 hybrid IRQ replacement:",
              "CHECK PASS" if RECEIPT.exists() else
              "CHECK FINAL RED" if FINAL_RED.exists() else
              "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists()
              else "CHECK LOCKED")
    elif action == "_hybrid_profile_probe":
        configure_module(); BASE.hybrid_profile_probe_child()
    elif action == "_real_consumer_probe":
        configure_module(); BASE.TOP.real_consumer_probe_child()
    elif action == "_membership_probe":
        configure_module(); BASE.TOP.PREV.membership_probe_child()
    elif action == "_full_probe":
        configure_module(); BASE.TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(mutant=False)
    elif action == "_full_probe_mutant":
        configure_module(); BASE.TOP.PREV.PREV.PREV.PREV.full_consumer_probe_child(mutant=True)
    elif action == "_default_probe":
        configure_module(); BASE.TOP.PREV.PREV.PREV.PREV.PREV.default_probe_child()
    elif action == "_owner_graph":
        configure_module()
        print(json.dumps(BASE.TOP.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.PREV.graph_gate(), sort_keys=True))
    else:
        configure_module(); BASE.TOP.child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"IRQ replacement Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 hybrid IRQ identity replacement: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
