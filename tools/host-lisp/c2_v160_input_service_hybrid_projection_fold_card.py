#!/usr/bin/env python3
"""Run the self-dispositional v1.6 hybrid projection-fold successor card."""

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
import c2_v160_input_service_hybrid_final_world_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-preflight"
QUALIFICATION = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-qualification"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-profile-probe-preflight"
FOLD_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-consumer-probe-r2"
FOLD_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-consumer-preflight-r2"
FOLD_MUTANT_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-mutant-probe-r2"
FOLD_MUTANT_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-projection-fold-mutant-preflight-r2"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-projection-fold-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-input-service-hybrid-final-world-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-hybrid-deep-projection-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "27208cbf"
FORMAT = "lisp65-c2-v160-input-service-hybrid-projection-fold-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID PROJECTION FOLD ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 HYBRID FINAL WORLD GREEN THROUGH PROJECTION FOLD"


class CardError(RuntimeError): pass
class ConsumerReached(BaseException): pass


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
    for token in ("branch one applies", "feature projection is a fold",
                  "per-feature early return falls", "final-world guard"):
        require(token in text, f"projection-fold authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED); attribution = load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: V1.6 HYBRID FINAL-WORLD SUCCESSOR STOPS"
            and red["classification"]["real_compiler_consumption_still_absent"]
                is True and red["retry_authorized"] is False,
            "projection-fold predecessor Red drift")
    require(attribution["status"] ==
                "ATTRIBUTED: CAPTURE EARLY RETURN SKIPPED HYBRID PROJECTION"
            and attribution["decision"]["classification"] == "known-family"
            and attribution["exact_projection_writer"]["function"] ==
                "c2_product_substitution_link.input_capture_compile_profile",
            "accepted deep-projection attribution drift")
    return {"Final_Red": red, "attribution": attribution}


def install_paths() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.QUALIFICATION = QUALIFICATION; PREV.ABI_REPORT = ABI_REPORT
    PREV.REAL_PROBE_BUILD = REAL_PROBE_BUILD
    PREV.REAL_PROBE_PREFLIGHT = REAL_PROBE_PREFLIGHT
    PREV.HYBRID_PROBE_BUILD = HYBRID_PROBE_BUILD
    PREV.HYBRID_PROBE_PREFLIGHT = HYBRID_PROBE_PREFLIGHT
    PREV.ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS; PREV.FINAL_STATUS = FINAL_STATUS


def configure_module() -> None:
    install_paths(); PREV.configure_module()


def fold_probe_child(*, mutant: bool) -> None:
    configure_module()
    build = FOLD_MUTANT_BUILD if mutant else FOLD_BUILD
    preflight = FOLD_MUTANT_PREFLIGHT if mutant else FOLD_PREFLIGHT
    core, _activation = REOPEN.configure_stack(build, preflight)
    static = core.install_static(build)
    core.bind_paths_only(build, preflight); core.write_projections()
    original_link = PRODUCT.single_link
    original_project = PRODUCT.input_capture_compile_profile
    captured: dict[str, Any] = {}

    if mutant:
        def early_return(definitions: tuple[str, ...]) -> tuple[str, ...]:
            if (PRODUCT.INPUT_CAPTURE_ENABLED
                    and PRODUCT.INPUT_CAPTURE_FEATURE not in definitions):
                return (*definitions, PRODUCT.INPUT_CAPTURE_FEATURE)
            return original_project(definitions)
        PRODUCT.input_capture_compile_profile = early_return

    def stop(_out: Path, *, probe_definitions: tuple[str, ...] = (),
             **_kwargs: Any) -> None:
        incoming = tuple(probe_definitions)
        projected = PRODUCT.input_capture_compile_profile(incoming)
        selected = {Path(path).resolve() for path in PRODUCT.source_list(projected)}
        captured.update({"incoming_definitions": list(incoming),
            "projected_definitions": list(projected),
            "capture_consumed": PRODUCT.INPUT_CAPTURE_FEATURE in projected,
            "hybrid_consumed": PRODUCT.INPUT_HYBRID_FEATURE in projected,
            "consumer_source_consumed":
                PRODUCT.INPUT_HYBRID_SOURCE.resolve() in selected,
            "static_consumer_observed_bytes": static["consumer_observed_bytes"]})
        require(captured["capture_consumed"] and captured["hybrid_consumed"]
                and captured["consumer_source_consumed"],
                "feature projection returned before folding every active owner")
        raise ConsumerReached()

    PRODUCT.single_link = stop
    try:
        core.PRODUCT.BASE.produce_child()
    except ConsumerReached:
        print(json.dumps({"status": "passed-real-single-link-feature-fold",
                          **captured}, sort_keys=True))
    finally:
        PRODUCT.single_link = original_link
        PRODUCT.input_capture_compile_profile = original_project


def run_fold_gate() -> dict[str, Any]:
    good = subprocess.run([sys.executable, str(DRIVER), "_fold_probe"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(good.returncode == 0, f"real-consumer fold probe red: {good.stderr}")
    value = json.loads(good.stdout)
    require(value["status"] == "passed-real-single-link-feature-fold"
            and value["capture_consumed"] and value["hybrid_consumed"]
            and value["consumer_source_consumed"],
            "real-consumer fold probe receipt drift")
    mutant = subprocess.run([sys.executable, str(DRIVER), "_fold_probe_mutant"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(mutant.returncode != 0
            and "returned before folding every active owner" in mutant.stderr,
            "per-feature early-return mutation survived pre-card")
    return {**value, "early_return_mutation_rejected": True,
            "real_consumer": "single_link -> input_capture_compile_profile -> source_list"}


def preflight() -> None:
    predecessor(); auth = authority(); install_paths()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, QUALIFICATION,
        REAL_PROBE_BUILD, REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD,
        HYBRID_PROBE_PREFLIGHT, FOLD_BUILD, FOLD_PREFLIGHT,
        FOLD_MUTANT_BUILD, FOLD_MUTANT_PREFLIGHT, RECEIPT, FINAL_RED)),
        "projection-fold successor is one-shot")
    fold = run_fold_gate()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "projection_fold_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "deep_projection_attribution": bind(ATTRIBUTION),
        "real_single_link_feature_fold": fold,
        "projection_fold_self_disposition": {"branch": 1,
            "known_family": "bound-not-consumed",
            "cards_authorized": 1, "cards_consumed": 0},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid projection fold: PREFLIGHT PASS card=0/1 "
          "consumer=capture+hybrid mutation=red")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["real_single_link_feature_fold"]["capture_consumed"] is True
            and value["real_single_link_feature_fold"]["hybrid_consumed"] is True
            and value["real_single_link_feature_fold"][
                "consumer_source_consumed"] is True
            and value["real_single_link_feature_fold"][
                "early_return_mutation_rejected"] is True
            and value["projection_fold_self_disposition"] == {
                "branch": 1, "known_family": "bound-not-consumed",
                "cards_authorized": 1, "cards_consumed": 0},
            "persisted projection-fold preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt.update({"format": FORMAT, "status": FINAL_STATUS,
        "projection_fold_authority": auth,
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "deep_projection_attribution": bind(ATTRIBUTION),
        "real_single_link_feature_fold": value["real_single_link_feature_fold"],
        "projection_fold_self_disposition": {"branch": 1,
            "known_family": "bound-not-consumed",
            "cards_authorized": 1, "cards_consumed": 1},
        "media_authorized": False, "device_contacts": 0,
        "next": "independent final-world review; media/device closed"})
    PREV.validate_final_claims(receipt)
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid projection fold: CARD PASS card=1/1 "
          "final-world=green review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 HYBRID PROJECTION-FOLD SUCCESSOR STOPS",
            "projection_fold_authority": authority(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "deep_projection_attribution": bind(ATTRIBUTION),
            "retry_authorized": False, "media_authorized": False,
            "device_contacts": 0, "next": "classify under standing rules"})
        if str(error) == "persisted owner-scope preflight drift":
            value["attempt_accounting"] = {"cards_authorized": 1,
                "cards_consumed": 1, "WPLTO_runs": 0,
                "product_link_attempts": 0, "media_builds": 0,
                "device_contacts": 0}
            value["classification"] = {
                "mechanism_fully_attributed": True,
                "family": "additive-projection-not-substitution",
                "product_work_started": False,
                "fold_gate_passed": True,
                "inherited_owner_scope_contract_substituted": True}
            value["persisted_contract_drift"] = {
                "expected_field": "self_disposition",
                "expected_value": {"sequence_after_reset": 2, "budget": 3,
                    "cards_authorized": 1, "cards_consumed": 0},
                "observed_value": {"branch": 1,
                    "known_family": "bound-not-consumed",
                    "cards_authorized": 1, "cards_consumed": 0},
                "status_matches": True,
                "identity_scoped_owner_registry_matches": True,
                "exact_consumer":
                    "c2_v160_input_fidelity_owner_scope_replacement_card.card"}
            value["next"] = (
                "known-family self-dispositional replacement; preserve the "
                "inherited field and add projection-fold accounting separately")
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe",
        "_membership_probe", "_hybrid_profile_probe", "_finalize_red", "_dry",
        "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid projection fold:",
        "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists()
        else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists() else "CHECK LOCKED")
    elif action == "_fold_probe": fold_probe_child(mutant=False)
    elif action == "_fold_probe_mutant": fold_probe_child(mutant=True)
    else:
        configure_module(); PREV.main()
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"projection-fold Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 hybrid projection fold: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
