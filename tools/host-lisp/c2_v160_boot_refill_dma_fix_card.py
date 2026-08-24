#!/usr/bin/env python3
"""Build the authorized final-world MAP-CPU boot-refill repair."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_boot_refill_dma_closure as CLOSURE  # noqa: E402
import c2_v160_nested_map_swap_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-map-cpu-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-map-cpu-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-boot-refill-map-cpu-card-final-red.json"
ATTRIBUTION = CLOSURE.RECEIPT
PREDECESSOR = ARCH / "c2.3-v1.6-nested-map-swap-acceptance-union-resume.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "fe531f3b"
FORMAT = "lisp65-c2-v160-boot-refill-map-cpu-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOOT REFILL MAP-CPU ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOOT REFILL MAP-CPU FINAL WORLD GREEN"

HISTORICAL_MUTATION_REGISTRY = (
    "restore-exact-pass-through",
    "remove-MAP-CPU-edge",
    "instrument-bypasses-safety",
    "hide-recorded-unsafe-count",
)
SELECTOR_MUTATION_REGISTRY = (
    "restore-boot-selector-dependency",
    "add-unregistered-selector-caller",
    "divert-registered-caller",
)


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def candidate_mutation_registry(gate: dict[str, Any]) -> dict[str, Any]:
    """Derive the named mutation population from active candidate freight."""
    expected = list(HISTORICAL_MUTATION_REGISTRY)
    active_freight: list[dict[str, Any]] = []
    if "selector_totality" in gate:
        expected.extend(SELECTOR_MUTATION_REGISTRY)
        active_freight.append({
            "registry": "boot-refill-selector-totality",
            "activation": "selector_totality present in final-ELF gate",
            "members": list(SELECTOR_MUTATION_REGISTRY),
        })
    require(len(expected) == len(set(expected)),
            "boot-refill mutation registry contains duplicate identities")
    return {
        "authority": "candidate-derived active mutation registry union",
        "historical_members": list(HISTORICAL_MUTATION_REGISTRY),
        "active_freight_registries": active_freight,
        "expected": expected,
    }


def mutation_population(
        gate: dict[str, Any], observed: list[str]) -> dict[str, Any]:
    """Report both named worlds; counts are summaries, never predicates."""
    registry = candidate_mutation_registry(gate)
    expected = registry["expected"]
    require(len(observed) == len(set(observed)),
            "observed boot-refill mutation identities are not unique")
    expected_set = set(expected); observed_set = set(observed)
    return {**registry, "observed": list(observed),
        "missing": sorted(expected_set - observed_set),
        "unexpected": sorted(observed_set - expected_set),
        "expected_count": len(expected), "observed_count": len(observed)}


def validate_mutation_population(value: dict[str, Any]) -> None:
    expected = value.get("expected", []); observed = value.get("observed", [])
    require(value.get("authority") ==
                "candidate-derived active mutation registry union"
            and len(expected) == len(set(expected))
            and len(observed) == len(set(observed))
            and value.get("missing") == sorted(set(expected) - set(observed))
            and value.get("unexpected") == sorted(set(observed) - set(expected))
            and value.get("missing") == [] and value.get("unexpected") == []
            and value.get("expected_count") == len(expected)
            and value.get("observed_count") == len(observed),
            "boot-refill named mutation population differs: "
            + json.dumps(value, sort_keys=True))


def mutation_population_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "remove-required-named-mutation": lambda x: x["observed"].pop(),
        "add-unregistered-named-mutation": lambda x: x["observed"].append(
            "unexpected:synthetic"),
        "restore-historical-exact-list": lambda x: x.update(
            expected=list(HISTORICAL_MUTATION_REGISTRY), expected_count=4),
        "omit-observed-side-of-drift-report": lambda x: x.pop("observed"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_mutation_population(trial)
        except (RuntimeError, KeyError):
            rejected.append(name)
    require(rejected == list(cases),
            "boot-refill mutation-population mutation survived")
    return rejected


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("regression question first", "gate blind-spot attribution",
                  "the fix card", "same map-cpu transport",
                  "unconditional success return", "instrument neutrality"):
        require(token in text, f"boot-refill fix authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    attribution = load(ATTRIBUTION)
    prior = load(PREDECESSOR)
    require(attribution["status"] ==
                "PASS: SHIPPED V1.5 AND V1.6 RED SHARE UNCHECKED DMA REFILL"
            and attribution["regression_decision"]["shipped_product_affected"]
                is True
            and prior["status"] ==
                "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
            "boot-refill fix predecessor drift")
    red = CLOSURE.linked_read_model(CLOSURE.RED_ELF)
    try:
        CLOSURE.validate_final(red)
    except CLOSURE.ClosureError:
        red_rejected = True
    else:
        red_rejected = False
    require(red_rejected, "historical unchecked refill did not fail successor gate")
    return {"attribution": bind(ATTRIBUTION),
            "nested_MAP_final_world": bind(PREDECESSOR),
            "historical_pass_through_rejected": red_rejected}


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = PROCESS
    PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.install()


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "fix_authority": authority(), "predecessor": predecessor(),
        "source_gate": CLOSURE.source_gate(),
        "source_mutations_rejected": CLOSURE.source_mutations(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "boot-refill MAP-CPU card is one-shot")
    predecessor(); authority(); PREV.preflight(); append_preflight()
    print("v1.6 boot refill MAP-CPU: PREFLIGHT PASS card=0/1 "
          "historical-pass-through=rejected")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["boot_refill_DMA_closure"]
    population = mutation_population(gate, value["mutations_rejected"])
    validate_mutation_population(population)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["unsafe_content_DMA_count"] == 0
            and gate["product_entry"]["raw_read_edges"] == 0
            and gate["product_entry"]["MAP_CPU_edges"] >= 1
            and gate["instrument"]["neutral"] is True,
            "boot-refill MAP-CPU final receipt drift")
    value["boot_refill_DMA_mutation_population"] = population
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["source_gate"]["failure_propagated"] is True,
            "persisted boot-refill preflight drift")
    PREV.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = CLOSURE.linked_read_model(elf)
    CLOSURE.validate_final(gate)
    mutations = CLOSURE.final_mutations(gate)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "fix_authority": authority(), "predecessor": predecessor(),
        "source_gate": CLOSURE.source_gate(),
        "boot_refill_DMA_closure": gate,
        "mutations_rejected": mutations,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope and acceptance; no media before full final-world green"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 boot refill MAP-CPU: CARD PASS card=1/1 unsafe=0")


def record_red(error: Exception) -> None:
    value = {"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 BOOT REFILL MAP-CPU CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "fix_authority": authority(), "predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False, "media_authorized": False,
        "next": "exceptionless disposition with full chain"}
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 boot refill MAP-CPU: CHECK PASS"); return 0
    return PREV.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"boot-refill Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 boot refill MAP-CPU: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
