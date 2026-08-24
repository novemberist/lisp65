#!/usr/bin/env python3
"""Run the additive-contract replacement for the hybrid projection-fold card."""

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

import c2_v160_input_fidelity_owner_scope_replacement_card as OWNER  # noqa: E402
import c2_v160_input_service_hybrid_projection_fold_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-card-r3"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-preflight-r3"
QUALIFICATION = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-qualification-r3"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-real-probe-build-r3"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-real-probe-preflight-r3"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-profile-probe-build-r3"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-profile-probe-preflight-r3"
FOLD_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-consumer-probe-r3"
FOLD_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-consumer-preflight-r3"
FOLD_MUTANT_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-mutant-probe-r3"
FOLD_MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-mutant-preflight-r3"
CONTRACT_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-real-consumer-r3"
CONTRACT_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-real-consumer-preflight-r3"
CONTRACT_MUTANT_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-mutant-consumer-r3"
CONTRACT_MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-contract-mutant-consumer-preflight-r3"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-contract-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-contract-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-card-final-red.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "6b210e93"
FORMAT = "lisp65-c2-v160-input-service-hybrid-projection-fold-contract-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID PROJECTION FOLD CONTRACT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 HYBRID FINAL WORLD GREEN THROUGH ADDITIVE FOLD CONTRACT"


class CardError(RuntimeError): pass
class InheritedContractReached(BaseException): pass


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
    for token in ("self-disposition 1/3", "additive projection, never substitution",
                  "projection_fold_self_disposition", "exactly one replacement card"):
        require(token in text, f"additive-contract authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    require(red["status"] ==
                "FINAL RED: V1.6 HYBRID PROJECTION-FOLD SUCCESSOR STOPS"
            and red["classification"]["family"] ==
                "additive-projection-not-substitution"
            and red["classification"]["mechanism_fully_attributed"] is True
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_link_attempts"] == 0
            and red["retry_authorized"] is False,
            "projection-fold contract predecessor drift")
    return red


def install_paths() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.QUALIFICATION = QUALIFICATION; PREV.ABI_REPORT = ABI_REPORT
    PREV.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    PREV.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    PREV.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    PREV.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    PREV.FOLD_BUILD = FOLD_BUILD; PREV.FOLD_PREFLIGHT = FOLD_PREFLIGHT
    PREV.FOLD_MUTANT_BUILD = FOLD_MUTANT_BUILD
    PREV.FOLD_MUTANT_PREFLIGHT = FOLD_MUTANT_PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS


def configure_module() -> None:
    install_paths(); PREV.configure_module()


def contract_probe_child(*, mutant: bool) -> None:
    build = CONTRACT_MUTANT_BUILD if mutant else CONTRACT_BUILD
    preflight = CONTRACT_MUTANT_PREFLIGHT if mutant else CONTRACT_PREFLIGHT
    preflight.mkdir(parents=True)
    value = load(PREFLIGHT / "preflight.json")
    expected_sequence = value["self_disposition"]["sequence_after_reset"]
    if mutant:
        value["self_disposition"] = value["projection_fold_self_disposition"]
    (preflight / "preflight.json").write_bytes(canonical(value))

    OWNER.BUILD = build; OWNER.PREFLIGHT = preflight
    OWNER.RECEIPT = preflight / "forbidden-receipt.json"
    OWNER.FINAL_RED = preflight / "forbidden-final-red.json"
    OWNER.STATUS = value["status"]
    OWNER.SELF_DISPOSITION_SEQUENCE = expected_sequence
    original = OWNER.PREV.card

    def reached() -> None:
        raise InheritedContractReached()

    OWNER.PREV.card = reached
    try:
        OWNER.card()
    except InheritedContractReached:
        require(not mutant, "substituted inherited contract reached product work")
        print(json.dumps({"status": "passed-real-inherited-card-consumer",
            "preserved_field": "self_disposition",
            "additive_field": "projection_fold_self_disposition",
            "real_consumer":
                "c2_v160_input_fidelity_owner_scope_replacement_card.card"},
            sort_keys=True))
    finally:
        OWNER.PREV.card = original


def run_contract_gate() -> dict[str, Any]:
    good = subprocess.run([sys.executable, str(DRIVER), "_contract_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(good.returncode == 0, f"inherited-contract probe red: {good.stderr}")
    value = json.loads(good.stdout)
    require(value["status"] == "passed-real-inherited-card-consumer",
            "inherited-contract probe receipt drift")
    mutant = subprocess.run([sys.executable, str(DRIVER),
        "_contract_probe_mutant"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(mutant.returncode != 0
            and "persisted owner-scope preflight drift" in mutant.stderr,
            "substituted inherited-contract mutation survived pre-card")
    return {**value, "substitution_mutation_rejected": True}


def preflight() -> None:
    predecessor(); auth = authority(); install_paths()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, QUALIFICATION,
        REAL_PROBE_BUILD, REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD,
        HYBRID_PROBE_PREFLIGHT, FOLD_BUILD, FOLD_PREFLIGHT,
        FOLD_MUTANT_BUILD, FOLD_MUTANT_PREFLIGHT, CONTRACT_BUILD,
        CONTRACT_PREFLIGHT, CONTRACT_MUTANT_BUILD, CONTRACT_MUTANT_PREFLIGHT,
        RECEIPT, FINAL_RED)), "additive-contract replacement is one-shot")
    configure_module(); PREV.preflight()
    contract = run_contract_gate()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "additive_contract_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_inherited_contract_consumer": contract,
        "contract_self_disposition": {"sequence": 1, "budget": 3,
            "cards_authorized": 1, "cards_consumed": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid fold contract: PREFLIGHT PASS card=0/1 "
          "inherited=preserved mutation=red")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["real_inherited_contract_consumer"]
                ["substitution_mutation_rejected"] is True
            and value["contract_self_disposition"] == {"sequence": 1,
                "budget": 3, "cards_authorized": 1, "cards_consumed": 0},
            "persisted additive-contract preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "additive_contract_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "real_inherited_contract_consumer":
            value["real_inherited_contract_consumer"],
        "contract_self_disposition": {"sequence": 1, "budget": 3,
            "cards_authorized": 1, "cards_consumed": 1},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent final-world review; media/device closed"})
    PREV.PREV.validate_final_claims(receipt)
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid fold contract: CARD PASS card=1/1 "
          "final-world=green review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 HYBRID FOLD CONTRACT REPLACEMENT STOPS",
            "additive_contract_authority": authority(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0, "next": "return with full chain"})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_contract_probe",
        "_contract_probe_mutant", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe",
        "_membership_probe", "_hybrid_profile_probe", "_finalize_red", "_dry",
        "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid fold contract:",
        "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists()
        else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists()
        else "CHECK LOCKED")
    elif action == "_contract_probe": contract_probe_child(mutant=False)
    elif action == "_contract_probe_mutant": contract_probe_child(mutant=True)
    else:
        configure_module(); PREV.main()
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"fold-contract Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 hybrid fold contract: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
