#!/usr/bin/env python3
"""Loud Link-109 source-closure successor for the phase-9 ABI repair."""

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

import c2_v21_reopen_gap_attribution_rebind_map_mask_d1_20260815 as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PREVIOUS = PREV.RECEIPT
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-phase9-abi-rebind-"
    "20260815-receipt.json")
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
FAR_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
READER_SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
ABI_GATE = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
SERVICE_GATE = ROOT / "tools/host-lisp/c2_mapped_far_service_gate.py"
EQUIVALENCE_GATE = ROOT / "tools/host-lisp/c2_mapped_far_asm_equivalence.py"
MAP_REBIND = ARCH / (
    "c2.3-v2.1-map-mask-fix-phase9-abi-rebind-receipt.json")


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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    previous = load(PREVIOUS)
    PREV.audit(previous)
    historical = PREV.PREV.PREV.PREV.PREV.OLD
    current = historical.current_attribution()
    projection = historical.PREV.PREV.OLD.semantic_projection(current)
    require(projection == previous["semantic_projection"],
            "reopen-gap semantic result changed during phase-9 ABI rebind")
    old_count = previous["source_scan"]["current_tracked_files"]
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(new_count > old_count,
            "phase-9 ABI source closure did not grow beyond Link 109")
    value = {
        "format": "lisp65-c2.3-v2.1-reopen-gap-phase9-abi-rebind-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: LOUD LINK109 PHASE9-ABI SOURCE-CLOSURE REBIND",
        "authority": {
            "previous_rebind": bind(PREVIOUS),
            "owner_authorization": bind(PLAN),
        },
        "inputs": {
            "ABI_contract": bind(ABI_CONTRACT),
            "mapped_far_source": bind(FAR_SOURCE),
            "CPU_reader_source": bind(READER_SOURCE),
            "transitive_ABI_gate": bind(ABI_GATE),
            "mapped_far_service_gate": bind(SERVICE_GATE),
            "assembly_equivalence_gate": bind(EQUIVALENCE_GATE),
            "MAP_semantic_rebind": bind(MAP_REBIND),
        },
        "source_scan": {
            "previous_tracked_files": old_count,
            "current_tracked_files": new_count,
        },
        "semantic_projection": projection,
        "result": {
            "semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False,
            "link109_remains_historical": True,
            "successor_card_runs": 0,
            "device_contacts_by_rebind": 0,
        },
        "claim_limit": (
            "Loud source-closure successor only; no WPLTO, product link, "
            "media, D1 or release claim."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "PASS: LOUD LINK109 PHASE9-ABI SOURCE-CLOSURE REBIND"
        and value.get("result") == {
            "semantic_conclusion": "byteidentical",
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "historical_receipts_changed": False,
            "product_artifacts_changed": False,
            "link109_remains_historical": True,
            "successor_card_runs": 0,
            "device_contacts_by_rebind": 0,
        }
        and value["source_scan"]["current_tracked_files"]
            > value["source_scan"]["previous_tracked_files"]
        and len(value.get("inputs", {})) == 7,
        "Link-109 phase-9 ABI rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipts_changed=True),
        "change-gap0": lambda x: x["result"].update(gap0="fixed"),
        "drop-ABI-contract": lambda x: x["inputs"].pop("ABI_contract"),
        "inherit-product-artifact": lambda x: x["result"].update(
            product_artifacts_changed=True),
        "spend-card": lambda x: x["result"].update(successor_card_runs=1),
        "invent-device-contact": lambda x: x["result"].update(
            device_contacts_by_rebind=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        mutate(trial)
        try:
            audit(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "phase-9 ABI rebind mutation survived")
    return rejected


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "phase-9 ABI rebind receipt exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive(), "phase-9 ABI source-closure rebind stale")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = record() if action == "record" else (
        check() if action == "check" else derive())
    print("Link-109 phase-9 ABI source rebind: PASS "
          f"{value['source_scan']['previous_tracked_files']}->"
          f"{value['source_scan']['current_tracked_files']} mutations=6")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"LINK109 PHASE9 ABI SOURCE REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
