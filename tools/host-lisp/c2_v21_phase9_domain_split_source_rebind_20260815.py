#!/usr/bin/env python3
"""Loud source-closure successor for phase-9 domain split and emission truth."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_reopen_gap_attribution_rebind_phase9_abi_20260815 as PREV  # noqa: E402
import c2_v20_building_heap_device_source_unbind_phase9_20260815 as UNBIND  # noqa: E402
import c2_v21_phase9_relocation_emission as EMISSION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREVIOUS = PREV.RECEIPT
ABI_GATE = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
FAR_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-domain-split-source-rebind-20260815-receipt.json")
DRIVER = Path(__file__).resolve()


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


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


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "PASS: LOUD PHASE9 DOMAIN-SPLIT SOURCE-CLOSURE REBIND"
        and value["semantic_projection"] == {
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "historical_v20_source_is_live_predicate": False,
            "product_artifacts_changed": False,
            "replacement_cards_run": 0,
        }
        and set(value["gate_domains"]) == {
            "C_reachable_ASM_closure", "contractual_service_exits"}
        and value["gate_domains"]["contractual_service_exits"]
            ["exit_count"] == 8,
        "phase-9 domain-split source rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "merge-domains": lambda x: x["gate_domains"].pop(
            "contractual_service_exits"),
        "lose-exit": lambda x: x["gate_domains"]
            ["contractual_service_exits"].update(exit_count=7),
        "rewrite-history": lambda x: x["semantic_projection"].update(
            historical_receipts_changed=True),
        "restore-live-historical-source": lambda x: x["semantic_projection"].update(
            historical_v20_source_is_live_predicate=True),
        "spend-card": lambda x: x["semantic_projection"].update(
            replacement_cards_run=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "domain-split rebind mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS)
    PREV.audit(previous)
    unbind = load(UNBIND.RECEIPT)
    unbind_rejected = unbind.pop("mutations_rejected", None)
    UNBIND.validate(unbind)
    require(unbind_rejected == UNBIND.mutations(unbind),
            "v2.0 source-unbind authority drift")
    emission = load(EMISSION.RECEIPT)
    emission_rejected = emission.pop("mutations_rejected", None)
    EMISSION.validate(emission)
    require(emission_rejected == EMISSION.mutations(emission),
            "relocation-emission authority drift")
    value = {
        "format": "lisp65-c2.3-v21-phase9-domain-split-source-rebind-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: LOUD PHASE9 DOMAIN-SPLIT SOURCE-CLOSURE REBIND",
        "authority": {"previous_rebind": bind(PREVIOUS),
                      "owner_authorization": bind(PLAN),
                      "v20_source_unbind": bind(UNBIND.RECEIPT),
                      "relocation_emission": bind(EMISSION.RECEIPT),
                      "ABI_contract": bind(ABI_CONTRACT),
                      "ABI_gate": bind(ABI_GATE),
                      "far_source": bind(FAR_SOURCE),
                      "driver": bind(DRIVER)},
        "gate_domains": {
            "C_reachable_ASM_closure": {
                "membership_authority": "linked-ELF-relocation-closure",
                "obligation": "every actual closure member checked"},
            "contractual_service_exits": {
                "membership_authority": "mapped-far public-service contract",
                "exit_count": 8,
                "obligation": "every exit preserves __rc16..__rc31"},
        },
        "semantic_projection": {
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "historical_v20_source_is_live_predicate": False,
            "product_artifacts_changed": False,
            "replacement_cards_run": 0,
        },
        "claim_limit": (
            "Loud source-closure successor only; no WPLTO, link, media or "
            "device contact."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def build() -> None:
    require(not RECEIPT.exists(), "domain-split rebind receipt already exists")
    RECEIPT.write_bytes(canonical(derive()))
    print("phase-9 domain-split source rebind: PASS domains=2 exits=8")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    expected = derive(); expected.pop("mutations_rejected", None)
    require(value == expected and rejected == mutations(value),
            "domain-split source rebind authority drift")
    print("phase-9 domain-split source rebind check: PASS domains=2")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]) == 5,
            "domain-split source rebind mutation count drift")
    print("phase-9 domain-split source rebind selftest: PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    {"build": build, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"phase-9 domain-split source rebind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
