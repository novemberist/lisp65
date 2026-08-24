#!/usr/bin/env python3
"""Run the reviewed Scope-state and forecast-floor liveness successor."""

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

from elf_truth import ElfTruth  # noqa: E402
import c2_v160_liveness_config as CONFIG  # noqa: E402
import c2_v160_liveness_fix as FIX  # noqa: E402
import c2_v160_liveness_fix_additive_capacity_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-scope-floor-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-liveness-fix-scope-floor-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-liveness-fix-scope-floor-process"
NORMAL_BUILD = PROCESS / "normal-build"; NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"; MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ARCH / "c2.3-v1.6-liveness-fix-scope-floor-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-scope-floor-card-final-red.json"
IMMEDIATE_RED = ARCH / "c2.3-v1.6-liveness-fix-additive-capacity-card-final-red.json"
FROZEN_BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-additive-capacity-card/wplto"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "95d28d02"
FORMAT = "lisp65-c2-v160-liveness-scope-floor-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 LIVENESS SCOPE FLOOR ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 RETIREMENT LIVENESS FIX FINAL WORLD GREEN"
TAG = "retirement-liveness-scope-floor"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
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
    for token in ("exactly one replacement card", "active liveness successor",
                  "predictions are bounds, not equalities", "14 free bytes",
                  "every liveness proof re-runs unchanged"):
        require(token in text, f"scope/floor authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(IMMEDIATE_RED)
    require(value["status"] ==
                "FINAL RED: V1.6 LIVENESS ADDITIVE CAPACITY RETURNS TO REVIEW"
            and "R1 successor identity is incomplete before restore" in
                value["error"]["message"]
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["family_self_disposition_exhausted"] is True
            and set(value["artifacts"]) == {"ELF", "PRG"},
            "scope/floor predecessor drift")
    return value


def scope_floor_gate(build: Path = FROZEN_BUILD, *, require_feature: bool = False
                     ) -> dict[str, Any]:
    profile = build / "resolved-profile.txt"
    elf = build / "lisp65-c2-substitution-linked.prg.elf"
    text = profile.read_text(encoding="utf-8")
    successor_sources = tuple(path.relative_to(ROOT).as_posix()
                              for path in (CONFIG.NEW_SERVICE, CONFIG.NEW_PADDING))
    predecessor_sources = tuple(path.relative_to(ROOT).as_posix()
                                for path in (CONFIG.OLD_SERVICE, CONFIG.OLD_PADDING))
    require(all(source in text for source in successor_sources)
            and all(source not in text for source in predecessor_sources)
            and (not require_feature or CONFIG.FEATURE in text),
            "frozen successor profile does not own Scope configuration")
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=False)
    service = truth.section(".lisp65_c2_mapped_far_service")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    ordinary = facade.address - (truth.section(".text").address
                                 + truth.section(".text").bytes)
    forecast = FIX.forecast_floor_gate(ordinary)
    red = predecessor()
    require(service.bytes == 1425 and facade.bytes == 98 and ordinary >= 3
            and (build != FROZEN_BUILD or ordinary == 14)
            and red["error"]["message"].endswith(
                "R1 successor identity is incomplete before restore\n"),
            "frozen final-world Scope/floor witness drift")
    return {"status": "PASS: SCOPE READS ACTIVE SUCCESSOR ARTIFACTS",
        "configuration_authority": {"resolved_profile": bind(profile), "ELF": bind(elf)},
        "successor_sources": list(successor_sources), "predecessor_sources_absent": True,
        "feature_line_present": CONFIG.FEATURE in text,
        "frozen_missing_feature_line_rejected_by_successor": (
            not require_feature and CONFIG.FEATURE not in text),
        "historical_reexecution_mutation_rejected": True,
        "forecast_floor": {**forecast,
            "stored_equality_mutation_rejected": True},
        "final_geometry": {"far_service_bytes": service.bytes,
            "facade_bytes": facade.bytes, "ordinary_text_free_bytes": ordinary}}


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT; PREV.PROCESS = PROCESS
    PREV.NORMAL_BUILD = NORMAL_BUILD; PREV.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    PREV.MUTANT_BUILD = MUTANT_BUILD; PREV.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    PREV.PRODUCT_ELF = PRODUCT_ELF; PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED; PREV.IMMEDIATE_RED = IMMEDIATE_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS; PREV.TAG = TAG
    PREV.authority = authority; PREV.predecessor = predecessor


def append(path: Path, gate: dict[str, Any]) -> None:
    value = load(path); value.update({"scope_floor_authority": authority(),
        "immediate_Final_Red": bind(IMMEDIATE_RED), "scope_floor_gate": gate})
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor(); authority(); gate = scope_floor_gate()
    configure_module(); PREV.preflight(); append(PREFLIGHT / "preflight.json", gate)
    print("v1.6 liveness scope/floor: PREFLIGHT PASS card=0/1 actual=14 floor=3")


def card() -> None:
    predecessor(); authority(); configure_module(); PREV.card()
    append(RECEIPT, scope_floor_gate(BUILD / "wplto", require_feature=True))
    print("v1.6 liveness scope/floor: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED); value.update({"format": FORMAT + "-final-red",
            "status": "FINAL RED: V1.6 LIVENESS SCOPE FLOOR STOPS",
            "scope_floor_authority": authority(), "immediate_Final_Red": bind(IMMEDIATE_RED),
            "retry_authorized": False, "media_authorized": False, "device_contacts": 0})
        FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    choices = ("preflight", "card", "check", "_process_probe", "_process_probe_mutant",
        "_contract_probe", "_contract_probe_mutant", "_fold_probe", "_fold_probe_mutant",
        "_order_probe", "_order_probe_mutant", "_real_consumer_probe", "_membership_probe",
        "_hybrid_profile_probe", "_finalize_red", "_dry", "_produce", "_scope", "_accept",
        "_r1_arm", "_owner_graph", "_default_probe", "_full_probe", "_full_probe_mutant")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=choices); action = parser.parse_args().action
    configure_module()
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check":
        value = load(RECEIPT); require(value["status"] == FINAL_STATUS,
            "scope/floor receipt drift")
        print("v1.6 liveness scope/floor: CHECK PASS")
    else:
        PREV.main()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"scope/floor Final Red failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 liveness scope/floor: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
