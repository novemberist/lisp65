#!/usr/bin/env python3
"""Run the one authorized final-world v1.6 hybrid successor card."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
import c2_v160_input_service_hybrid_final_world as FINAL  # noqa: E402
import c2_v160_input_service_hybrid_phase_output_consumption_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-preflight"
QUALIFICATION = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-qualification"
ABI_REPORT = QUALIFICATION / "c2-asm-leaf-abi.json"
REAL_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-real-probe-build"
REAL_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-real-probe-preflight"
HYBRID_PROBE_BUILD = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-profile-probe-build"
HYBRID_PROBE_PREFLIGHT = ROOT / "build/c2.3/v1.6-input-service-hybrid-final-world-profile-probe-preflight"
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-input-service-hybrid-final-world-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-service-hybrid-final-world-card-final-red.json"
ATTRIBUTION = ARCH / "c2.3-v1.6-hybrid-consumer-absence-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "e1437e51"
FORMAT = "lisp65-c2-v160-input-service-hybrid-final-world-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 HYBRID FINAL-WORLD SUCCESSOR ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 HYBRID CLAIMS GREEN ON FINAL LINKED WORLD"
CONSUMER_MAX_BYTES = 70


class CardError(RuntimeError):
    pass


class OrderReached(BaseException):
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
    for token in ("exactly one successor card", "before core.install()",
                  "every claim proves on the final world",
                  "no isolated-object or synthetic-profile proof",
                  "media and device stay closed"):
        require(token in text, f"final-world card authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(ATTRIBUTION)
    require(value["status"] ==
                "ATTRIBUTED: HYBRID CONSUMER WAS BOUND AFTER THE REAL COMPILER WORLD"
            and value["classification"]["family"] == "bound-not-consumed"
            and value["classification"]["accepted_product_reached_hybrid_consumer"]
                is False
            and value["classification"]["successor_authorized"] is False,
            "accepted hybrid-consumer attribution drift")
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


def configure_module(*, late_mutant: bool = False) -> None:
    install_paths(); PREV.configure_module()
    if late_mutant:
        return

    def configure_stack(build: Path = BUILD, preflight: Path = PREFLIGHT,
                        *, activate_capture: bool = True
                        ) -> tuple[Any, dict[str, Any]]:
        REOPEN.R1_TOP.configure_module()
        core = REOPEN.set_core_paths(build, preflight)
        activation: dict[str, Any] = {"capture": None, "hybrid": None}
        if activate_capture:
            activation["capture"] = PRODUCT.configure_input_capture()
            activation["hybrid"] = PRODUCT.configure_input_hybrid()
        core.install(build, preflight)
        return core, activation

    configure_stack._v160_input_hybrid = True  # type: ignore[attr-defined]
    configure_stack._v160_hybrid_before_install = True  # type: ignore[attr-defined]
    REOPEN.configure_stack = configure_stack


def order_probe_child(*, late_mutant: bool) -> None:
    configure_module(late_mutant=late_mutant)
    original_configure = REOPEN.R1_TOP.configure_module
    original_hybrid = PRODUCT.configure_input_hybrid

    if late_mutant:
        # Successor dispatchers may already have installed a normal outer
        # wrapper before routing this inherited probe.  Mutate the semantic
        # activation itself so that such ambient setup cannot mask the
        # intended configuration-after-install counterexample.
        def omit_hybrid() -> dict[str, Any]:
            return {"mutant": "hybrid-activation-omitted-until-after-install"}

        PRODUCT.configure_input_hybrid = omit_hybrid

    def observe(_build: Path, _preflight: Path) -> None:
        selected = {Path(path).resolve()
                    for path in PRODUCT.source_list(PRODUCT.CONVERGENCE_DEFINES)}
        require(PRODUCT.INPUT_CAPTURE_ENABLED and PRODUCT.INPUT_HYBRID_ENABLED
                and PRODUCT.INPUT_HYBRID_FEATURE in PRODUCT.CONVERGENCE_DEFINES
                and PRODUCT.INPUT_HYBRID_SOURCE.resolve() in selected,
                "hybrid activation reached core.install too late")
        raise OrderReached()

    def configure_and_observe() -> None:
        original_configure()
        REOPEN.core_module().install = observe

    REOPEN.R1_TOP.configure_module = configure_and_observe
    try:
        REOPEN.configure_stack(PREFLIGHT / "order-probe-build",
                               PREFLIGHT / "order-probe-preflight")
    except OrderReached:
        print(json.dumps({"status": "passed-hybrid-before-core-install",
            "capture_enabled": PRODUCT.INPUT_CAPTURE_ENABLED,
            "hybrid_enabled": PRODUCT.INPUT_HYBRID_ENABLED,
            "hybrid_feature": PRODUCT.INPUT_HYBRID_FEATURE,
            "hybrid_source": PRODUCT.INPUT_HYBRID_SOURCE.relative_to(ROOT).as_posix()},
            sort_keys=True))
    finally:
        REOPEN.R1_TOP.configure_module = original_configure
        PRODUCT.configure_input_hybrid = original_hybrid


def run_order_gate() -> dict[str, Any]:
    good = subprocess.run([sys.executable, str(DRIVER), "_order_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(good.returncode == 0,
            f"configuration-before-install probe red: {good.stderr}")
    value = json.loads(good.stdout)
    require(value["status"] == "passed-hybrid-before-core-install",
            "configuration-before-install probe receipt drift")
    late = subprocess.run([sys.executable, str(DRIVER), "_order_probe_mutant"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(late.returncode != 0
            and "hybrid activation reached core.install too late" in late.stderr,
            "late hybrid activation mutation survived pre-card")
    return {**value, "late_activation_mutation_rejected": True,
            "real_consumer": "REOPEN.configure_stack -> core.install"}


def validate_consumer_membership(member: dict[str, Any], *,
                                 stored_size: int | None = None) -> None:
    """Validate emitted membership against the facade capacity contract.

    The candidate owns its freight size.  The fixed contract owns only the
    maximum; ``stored_size`` exists solely to exercise the historical-pin
    mutation below.
    """
    section_bytes = member.get("section_bytes")
    symbol_bytes = member.get("symbol_bytes")
    require(member.get("section") == FINAL.SECTION
            and member.get("symbol") == FINAL.SYMBOL
            and isinstance(section_bytes, int)
            and isinstance(symbol_bytes, int)
            and section_bytes == symbol_bytes
            and 0 < section_bytes <= CONSUMER_MAX_BYTES,
            "final linked hybrid consumer membership red")
    if stored_size is not None:
        require(section_bytes == symbol_bytes == stored_size,
                "stored hybrid consumer-size pin differs from candidate")


def validate_final_claims(value: dict[str, Any], *,
                          stored_consumer_size: int | None = None) -> None:
    final = value.get("final_world_claims", {})
    member = final.get("membership", {})
    require(value.get("status") == FINAL_STATUS,
            "final-world card status drift")
    require(final.get("status") == "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
            and final.get("claim_source") == "final linked ELF only"
            and final.get("isolated_object_claims") == 0
            and final.get("synthetic_profile_claims") == 0,
            "claim authority escaped final linked world")
    validate_consumer_membership(member, stored_size=stored_consumer_size)
    require(final.get("normalization", {}).get("executions") == 512
            and final.get("normalization", {}).get("parity") is True
            and final.get("loss", {}).get("linked_events_drained") == 94
            and final.get("loss", {}).get("linked_dropped") == 0
            and final.get("responsiveness", {}).get("margin_percent", 0) >= 25.0,
            "final linked hybrid claim wall red")


def claim_mutations(value: dict[str, Any]) -> dict[str, str]:
    cases = {
        "linked-consumer-absent": lambda x: x["final_world_claims"]
            ["membership"].update(section_bytes=0),
        "isolated-object-substitution": lambda x: x["final_world_claims"].update(
            claim_source="isolated source object", isolated_object_claims=1),
        "synthetic-profile-substitution": lambda x: x["final_world_claims"].update(
            claim_source="synthetic profile", synthetic_profile_claims=1),
        "recorded-loss-not-enforced": lambda x: x["final_world_claims"]
            ["loss"].update(linked_dropped=1),
    }
    rejected: dict[str, str] = {}
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_final_claims(trial)
        except CardError as error:
            rejected[name] = str(error)
        else:
            raise CardError(f"final-world claim mutation survived: {name}")
    try:
        validate_final_claims(deepcopy(value), stored_consumer_size=67)
    except CardError as error:
        rejected["restore-stored-consumer-size-67"] = str(error)
    else:
        raise CardError("final-world claim mutation survived: "
                        "restore-stored-consumer-size-67")
    return rejected


def preflight() -> None:
    predecessor(); auth = authority(); install_paths()
    require(not any(path.exists() for path in (BUILD, PREFLIGHT, QUALIFICATION,
        REAL_PROBE_BUILD, REAL_PROBE_PREFLIGHT, HYBRID_PROBE_BUILD,
        HYBRID_PROBE_PREFLIGHT, RECEIPT, FINAL_RED)),
        "final-world hybrid successor is one-shot")
    order = run_order_gate()
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    legacy = {"isolated_object_gate": value.get("hybrid_host_gates"),
              "synthetic_profile_probe": value.get("real_hybrid_profile")}
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "final_world_authority": auth, "consumer_absence_attribution": bind(ATTRIBUTION),
        "configuration_before_install": order,
        "pre_card_diagnostics_non_claim": legacy,
        "claim_authority": "post-link final ELF only",
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))
    print("v1.6 hybrid final-world successor: PREFLIGHT PASS card=0/1 "
          "order=hybrid-before-install claims=post-link-only")


def card() -> None:
    predecessor(); auth = authority(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == PREFLIGHT_STATUS
            and value["configuration_before_install"] == run_order_gate()
            and value["claim_authority"] == "post-link final ELF only",
            "persisted final-world preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    final = FINAL.derive(ELF)
    receipt.pop("hybrid_host_gates", None)
    receipt.pop("real_hybrid_profile", None)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["final_world_authority"] = auth
    receipt["consumer_absence_attribution"] = bind(ATTRIBUTION)
    receipt["configuration_before_install"] = value[
        "configuration_before_install"]
    receipt["final_world_claims"] = final
    receipt["pre_card_diagnostics_non_claim"] = value[
        "pre_card_diagnostics_non_claim"]
    receipt["media_authorized"] = False; receipt["device_contacts"] = 0
    receipt["next"] = "independent final-world verification; media/device closed"
    receipt["final_world_claim_mutations_rejected"] = claim_mutations(receipt)
    validate_final_claims(receipt)
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 hybrid final-world successor: CARD PASS card=1/1 "
          "consumer=candidate-derived<=70 final-world-claims=4 review=required")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
    else:
        discarded = bind(RECEIPT) if RECEIPT.exists() else None
        artifacts: dict[str, Any] = {}
        for name, path in {
            "ELF": ELF,
            "PRG": BUILD / "wplto/lisp65-c2-substitution-linked.prg",
            "map": BUILD / "wplto/lisp65-c2-substitution-linked.map",
            "lto": BUILD / "wplto/resident-island-seed.prg.lto.o",
            "resolved_profile": BUILD / "wplto/resolved-profile.txt",
        }.items():
            if path.is_file() and not path.is_symlink():
                artifacts[name] = bind(path)
        value = {"attempt_accounting": {"cards_authorized": 1,
            "cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}, "artifacts": artifacts,
            "discarded_predecessor_green_receipt": discarded}
        if RECEIPT.exists():
            RECEIPT.unlink()
    value.update({"format": FORMAT + "-final-red",
        "recorded_on": "2026-08-20",
        "status": "FINAL RED: V1.6 HYBRID FINAL-WORLD SUCCESSOR STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "final_world_authority": authority(),
        "consumer_absence_attribution": bind(ATTRIBUTION),
        "configuration_before_install": load(PREFLIGHT / "preflight.json")
            ["configuration_before_install"],
        "final_world_observation": {
            "consumer_section_present": False,
            "resolved_profile_hybrid_feature_present": False,
            "canonical_consumer_object_present": False,
            "capture_object_present": True,
        },
        "classification": {
            "wrapper_order_repair_reached_preflight": True,
            "real_compiler_consumption_still_absent": True,
            "mechanism_fully_attributed": False,
            "product_claims_inherited": False,
        },
        "retry_authorized": False, "media_authorized": False,
        "device_contacts": 0,
        "next": "attribute the real compiler consumption boundary; no silent retry"})
    FINAL_RED.write_bytes(canonical(value))


def seal_observed_red() -> None:
    require(ELF.is_file() and RECEIPT.is_file() and not FINAL_RED.exists(),
            "observed post-link Red is not uniquely sealable")
    record_red(CardError(
        "section identity is not unique: "
        ".lisp65_c2_kernal_window.input_consumer (0)"))
    print("v1.6 hybrid final-world successor: FINAL RED SEALED "
          "card=1/1 WPLTO=1 link=1 media=0 device=0")


def route(action: str) -> None:
    configure_module(); PREV.main_route(action) if hasattr(PREV, "main_route") else PREV.main()


def main() -> int:
    choices = ("preflight", "card", "check", "_seal_red",
        "_order_probe", "_order_probe_mutant",
        "_real_consumer_probe", "_membership_probe", "_hybrid_profile_probe",
        "_finalize_red", "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": print("v1.6 hybrid final-world successor:",
        "CHECK PASS" if RECEIPT.exists() else "CHECK FINAL RED" if FINAL_RED.exists()
        else "CHECK ARMED" if (PREFLIGHT / "preflight.json").exists() else "CHECK LOCKED")
    elif action == "_seal_red": seal_observed_red()
    elif action == "_order_probe": order_probe_child(late_mutant=False)
    elif action == "_order_probe_mutant": order_probe_child(late_mutant=True)
    else:
        configure_module()
        # The predecessor's main parser reads sys.argv and dispatches every
        # inherited real-consumer action through the fully configured stack.
        PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"final-world Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 hybrid final-world successor: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
