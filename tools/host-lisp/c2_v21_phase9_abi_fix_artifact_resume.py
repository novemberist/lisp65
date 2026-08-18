#!/usr/bin/env python3
"""Resume only Acceptance on the frozen phase-9 ABI candidate."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_map_tuple_fix_card as MAP_CARD  # noqa: E402
import c2_v20_source_authoritative_oracle_card as ORACLE  # noqa: E402
import c2_v21_dependent_vma_replacement_card as DEP  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_replay as PREV  # noqa: E402
import c2_v21_phase9_abi_fix_replacement_card as CARD  # noqa: E402
import c2_v21_phase9_candidate_derived_tuple_gate as TUPLE  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = CARD.BUILD
ELF = PREV.ELF
RESUME = BUILD / "candidate-derived-tuple-artifact-resume"
PREFLIGHT = RESUME / "preflight.json"
ACCEPTANCE_RESULT = RESUME / "artifact-acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-abi-fix-artifact-resume-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ded37acd"
RECORDED_ON = "2026-08-16"
FORMAT = "lisp65-c2.3-v2.1-phase9-ABI-artifact-acceptance-resume-v1"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("size derivation approved", "emitted candidate",
                  "fixed arena capacity", "acceptance continues",
                  "no wplto, no relink, no card consumed"):
        require(token in text, f"artifact-resume authority absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    value = load(PREV.REPLAY_FINAL_RED)
    require(value.get("status")
            == "FINAL RED: phase-9 artifact-only replay returns to owner"
            and value.get("retry_authorized") is False
            and value["attribution"]["classification"]
                == "verifier freight pin; no tuple-semantic drift",
            "artifact replay Final Red predecessor drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return PREV.frozen_artifacts()


def successor_oracle_acceptance() -> int:
    """Run the real lower Acceptance with v5 and the successor tuple gate."""
    require(ORACLE.BUILD.is_dir() and not ORACLE.ACCEPTANCE_RESULT.exists(),
            "successor acceptance child lifecycle drift")
    paths = ORACLE.artifact_paths()
    ORACLE.BASE.PRODUCT.configure_e000_reopening()
    ORACLE.BASE.PRODUCT.configure_full_map_ownership()
    ORACLE.BASE.PRODUCT.configure_low_resident_lma_reset()
    ORACLE.BASE.CRC.BUILD = ORACLE.BUILD
    comparison = ORACLE.BASE.INV.compare_elf(paths["elf"])
    linker = ORACLE.BASE.PRODUCT.low_resident_lma_reset_gate(
        paths["linker"].read_text(encoding="utf-8"))
    delivery = ORACLE.BASE.CRC.delivered_bytes_gate(paths["elf"], paths["prg"])
    ORACLE.BASE.CRC.validate_delivery(delivery, paths["elf"], paths["prg"])
    tuple_gate = ORACLE.BASE.linked_tuple_gate(paths["elf"])
    value = {"status": "PASS", "pid": os.getpid(),
        "VMA_golden": comparison, "low_resident_LMA_reset": linker,
        "delivered_bytes": delivery,
        "delivery_mutations_rejected": ORACLE.BASE.CRC.delivery_mutations(
            delivery, paths["elf"], paths["prg"]),
        "linked_MAP_tuple": tuple_gate,
        "linked_MAP_mutations_rejected": ORACLE.BASE.linked_mutations(
            tuple_gate, paths["elf"]),
        "far_payload": ORACLE.far_payload_gate(paths["elf"]),
        "source_authoritative_oracle": ORACLE.linked_oracle_gate(paths["elf"])}
    require(
        comparison["allocatable_sections"] == 103
        and comparison["fixed_boundary_symbols"] == 25
        and comparison["freight_derived_boundary_symbols"] == 3
        and comparison["mapped_far_service_capacity"][
            "candidate_headroom_bytes"] == 413
        and tuple_gate["far_service"]["candidate_derived_bytes"] == 1086
        and tuple_gate["far_service"]["arena_capacity_bytes"] == 1499,
        "successor Acceptance did not consume v5/derived tuple authorities")
    ORACLE.ACCEPTANCE_RESULT.write_bytes(canonical(value))
    return 0


def install_successors() -> None:
    PREV.install_freight_acceptance()
    DEP.GOLD = GOLD
    DEP.ACCEPTANCE_OWNER.INV = GOLD
    MAP_CARD.linked_tuple_gate = TUPLE.linked_tuple_gate
    MAP_CARD.validate_linked_tuple = TUPLE.validate_linked_tuple
    MAP_CARD.linked_mutations = TUPLE.linked_mutations
    ORACLE.far_payload_gate = TUPLE.far_payload_gate
    ORACLE.acceptance_child = successor_oracle_acceptance


def configure() -> None:
    install_successors()
    CARD.SCOPE_RESULT = PREV.SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.configure()
    DEP.GOLD = GOLD
    DEP.ACCEPTANCE_OWNER.INV = GOLD
    MAP_CARD.linked_tuple_gate = TUPLE.linked_tuple_gate
    MAP_CARD.validate_linked_tuple = TUPLE.validate_linked_tuple
    MAP_CARD.linked_mutations = TUPLE.linked_mutations
    ORACLE.far_payload_gate = TUPLE.far_payload_gate


def preflight_value() -> dict[str, Any]:
    predecessor()
    frozen = frozen_artifacts()
    scope = load(PREV.SCOPE_RESULT)
    tuple_receipt = load(TUPLE.RECEIPT)
    require(scope.get("status") == "PASS"
            and tuple_receipt.get("status")
                == "PASS: candidate-derived tuple gate ready for frozen replay"
            and tuple_receipt["tuple_gate"]["far_service"][
                "candidate_headroom_bytes"] == 413,
            "artifact-resume host authority red")
    return {"format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: frozen Acceptance resume armed",
        "authority": {"owner": authorization(),
            "predecessor_Final_Red": bind(PREV.REPLAY_FINAL_RED),
            "candidate_derived_tuple": bind(TUPLE.RECEIPT),
            "freight_boundary_review": bind(GOLD.RECEIPT),
            "persisted_green_scope": bind(PREV.SCOPE_RESULT),
            "driver": bind(DRIVER)},
        "frozen_artifacts": frozen,
        "execution_lock": {"acceptance_resumes_authorized": 1,
            "acceptance_resumes_run": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "scope_runs": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Acceptance only; product artifacts remain read-only."}


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "artifact Acceptance resume preflight drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "rerun-scope": lambda x: x["execution_lock"].update(scope_runs=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("elf"),
        "restore-old-tuple-authority": lambda x: x["authority"].pop(
            "candidate_derived_tuple")}
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except ResumeError:
            rejected.append(name)
    require(rejected == list(cases), "artifact resume mutation survived")
    return rejected


def preflight() -> None:
    require(not RESUME.exists() and not RECEIPT.exists(),
            "artifact Acceptance resume is one-shot")
    value = preflight_value(); value["mutations_rejected"] = mutations(value)
    RESUME.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(value))
    print("2.1 phase-9 artifact resume: PREFLIGHT PASS Acceptance=0/1 WPLTO=0")


def rebind_preflight() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    prior_driver = persisted["authority"]["driver"]
    prior_tuple = persisted["authority"]["candidate_derived_tuple"]
    comparison = deepcopy(expected)
    comparison["authority"]["driver"] = prior_driver
    comparison["authority"]["candidate_derived_tuple"] = prior_tuple
    require(persisted == comparison and rejected == mutations(comparison),
            "artifact resume rebind moved more than broadened gate authorities")
    expected["authority"]["pre_rebind"] = {
        "driver": prior_driver, "candidate_derived_tuple": prior_tuple}
    expected["mutations_rejected"] = mutations(preflight_value())
    PREFLIGHT.write_bytes(canonical(expected))
    print("2.1 phase-9 artifact resume: PREFLIGHT REBIND PASS consumers=2")


def acceptance_child() -> int:
    configure()
    return CARD.acceptance_child()


def run_acceptance() -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_accept"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh artifact Acceptance resume red:\n{result.stdout}")


def resume() -> None:
    persisted = load(PREFLIGHT); rejected = persisted.pop("mutations_rejected")
    lineage = persisted["authority"].pop("pre_rebind", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(isinstance(lineage, dict)
            and set(lineage) == {"driver", "candidate_derived_tuple"},
            "artifact resume broaden-once lineage absent")
    require(rejected == mutations(expected), "artifact resume mutation drift")
    require(not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "artifact Acceptance resume output exists")
    before = frozen_artifacts()
    run_acceptance()
    after = frozen_artifacts()
    require(after == before, "Acceptance resume changed frozen artifacts")
    acceptance = load(ACCEPTANCE_RESULT)
    comparison = acceptance["VMA_golden"]
    tuple_gate = acceptance["linked_MAP_tuple"]
    require(
        acceptance.get("status") == "PASS"
        and comparison["fixed_boundary_symbols"] == 25
        and comparison["freight_derived_boundary_symbols"] == 3
        and tuple_gate["far_service"]["candidate_derived_bytes"] == 1086
        and tuple_gate["far_service"]["arena_capacity_bytes"] == 1499
        and tuple_gate["far_service"]["candidate_headroom_bytes"] == 413,
        "resumed frozen Acceptance result drift")
    receipt = {"format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: frozen phase-9 Acceptance resumed and green",
        "authority": {"owner": authorization(), "preflight": bind(PREFLIGHT),
            "predecessor_Final_Red": bind(PREV.REPLAY_FINAL_RED),
            "candidate_derived_tuple": bind(TUPLE.RECEIPT),
            "golden_review": bind(GOLD.RECEIPT), "driver": bind(DRIVER)},
        "execution_accounting": {"acceptance_resumes_authorized": 1,
            "acceptance_resumes_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "scope_runs": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "persisted_scope": load(PREV.SCOPE_RESULT), "acceptance": acceptance,
        "process_isolation": {"parent": os.getpid(),
            "acceptance": acceptance["pid"], "distinct": True},
        "mutations_rejected": rejected,
        "next": "Completion, same-world media closure, owner-observed D1",
        "claim_limit": "Acceptance green; Completion/media/device have not run."}
    require(receipt["process_isolation"]["parent"]
            != receipt["process_isolation"]["acceptance"],
            "Acceptance did not run in a fresh process")
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 phase-9 artifact resume: PASS tuple=derived capacity=1086/1499")


def check() -> None:
    value = load(RECEIPT)
    require(value.get("status")
            == "PASS: frozen phase-9 Acceptance resumed and green"
            and value["execution_accounting"]["WPLTO_runs"] == 0
            and value["frozen_artifacts_after"] == frozen_artifacts()
            and value["acceptance"]["linked_MAP_tuple"]["far_service"][
                "candidate_headroom_bytes"] == 413,
            "artifact Acceptance resume receipt drift")
    print("2.1 phase-9 artifact resume: CHECK PASS WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "rebind-preflight", "resume", "check", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "rebind-preflight": rebind_preflight,
     "resume": resume, "check": check,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
