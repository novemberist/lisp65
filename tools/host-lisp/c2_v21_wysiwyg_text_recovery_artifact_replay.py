#!/usr/bin/env python3
"""Artifact-only Scope/Acceptance continuation for frozen Link 116."""

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

import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_full_span_projection_artifact_replay as FULL_SPAN  # noqa: E402
import c2_v21_map_mask_fix_card as MAP_CARD  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_resume as PHASE9_RESUME  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402
import c2_v21_text_recovery_replacement_card as COMPLETION  # noqa: E402
import c2_v21_wysiwyg_candidate_contract as PLACEMENT  # noqa: E402
import c2_v21_wysiwyg_linked_semantics as WYSIWYG  # noqa: E402
import c2_v21_wysiwyg_text_recovery_replacement_card as CARD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
MANIFEST = BUILD / "wplto/runtime-overlays-session-final.json"
REPLAY = BUILD / "artifact-only-scope-acceptance"
PREFLIGHT = REPLAY / "preflight.json"
PRODUCER_RESULT = REPLAY / "producer-tail-result.json"
SCOPE_RESULT = REPLAY / "owner-scope-result.json"
ACCEPTANCE_RESULT = REPLAY / "artifact-acceptance.json"
ABI_REPORT = REPLAY / "c2-asm-leaf-abi.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-artifact-replay-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "f60d6f98"
RESUME_AUTHORIZATION = "285fe24f"
RECORDED_ON = "2026-08-17"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().replace("*", "").split())
    for token in ("checker conversions approved",
                  "reserve candidate-derived",
                  "behavioral equivalence, never mnemonic identity",
                  "scope/acceptance only",
                  "frozen link-116 shas", "no relink"):
        require(token in text, f"Link-116 continuation authority absent: {token}")
    return value


def resume_authorization() -> dict[str, Any]:
    value = git_binding(RESUME_AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().replace("*", "").split())
    for token in ("driver-only preflight rebind",
                  "exactly one fresh scope/acceptance run",
                  "same frozen link-116 shas", "no wplto",
                  "no relink", "no card"):
        require(token in text, f"Link-116 resume authority absent: {token}")
    return value


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    require(value.get("status") ==
                "FINAL RED: Link-116 replacement returns to owner"
            and value.get("retry_authorized") is False
            and value.get("owner_disposition_required") is True
            and value.get("attempt_accounting") == {
                "WPLTO_runs": 1, "cards_authorized": 1,
                "cards_consumed": 1, "completion_runs": 0,
                "device_contacts": 0, "media_builds": 0,
                "product_link_attempts": 1},
            "Link-116 Final Red authority drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = final_red()["artifacts"]
    current = {name: bind(ROOT / row["path"])
               for name, row in expected.items()}
    require(current == expected, "frozen Link-116 artifact SHA drift")
    return current


def configure() -> None:
    # The lower card's configure routine assigns the candidate contract via
    # MAP_CARD.  Replace that producer, not just its current consumer, so the
    # same candidates are seen by Scope and Acceptance in their fresh processes.
    MAP_CARD.placement_contract = PLACEMENT.derive
    CANDIDATE.placement_contract = PLACEMENT.derive
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.ABI_REPORT = ABI_REPORT
    CARD.install()
    # Full-span source and Acceptance identities were already accepted for
    # this product lineage.  The Link-116 continuation must install those
    # successors, not fall back to the historical MAP-tuple vocabulary.
    PHASE9_RESUME.install_successors = FULL_SPAN.install_acceptance_successors
    FULL_SPAN.install_acceptance_successors()
    MAP_CARD.placement_contract = PLACEMENT.derive
    CANDIDATE.placement_contract = PLACEMENT.derive
    CARD.BASE.configure()
    FULL_SPAN.install_acceptance_successors()
    FULL_SPAN.CARD.MAP_FIX.source_scope_gate = FULL_SPAN.successor_scope_gate
    MAP_CARD.placement_contract = PLACEMENT.derive
    CANDIDATE.placement_contract = PLACEMENT.derive


def candidate_tail() -> dict[str, Any]:
    configure()
    report = ABI.audit_elf(ELF, out=ABI_REPORT, require_bank3_chain=True)
    derived = report["ELF_derived_C_called_inventory"]
    require(derived["status"] == ABI.ELF_DERIVED_C_CALLED_STATUS
            and derived["unclassified_C_called_functions"] == [],
            "frozen Link-116 ELF ABI closure red")
    section = COMPLETION.PRODUCT.section_table(ELF).get(
        COMPLETION.PRODUCT.VERIFIER_BINDING_SECTION)
    family_stage = bool(section and section["bytes"] == (
        COMPLETION.PRODUCT.VERIFIER_BINDING_BYTES
        + COMPLETION.PRODUCT.FAMILY_STAGE_BINDING_BYTES))
    require(family_stage, "candidate family-stage binding identity absent")
    COMPLETION.PRODUCT.FAMILY_STAGE_BINDINGS = family_stage
    local = CANDIDATE.linked_gate(ELF, MANIFEST)
    completion = COMPLETION.completion_gate(ELF)
    placement = PLACEMENT.derive(ELF)
    semantic = WYSIWYG.derive(ELF)
    original = load(BUILD / "producer-result.json")
    transport = original["v21_linked_transport"]
    require(local["reader"]["bytes"] == 189
            and local["ordinary"] == {
                "reserve_bytes": 11, "text_end_exclusive": "0xb3a5"}
            and local["ownership"]["violations"] == []
            and placement["ordinary_reserve_bytes"] == 11
            and semantic["behavior"]["semantic_mismatches"] == 0
            and semantic["compiler_evidence"][
                "instruction_selection_constraint"] is None
            and completion["status"] ==
                "PASS: publish-last consumed candidate identity"
            and transport["reader"]["bytes"] == 189,
            "artifact-only Link-116 producer tail is red")
    return {
        "candidate_configuration": {"family_stage_bindings": family_stage},
        "ABI_vocabulary": {"status": derived["status"],
            "transitive_functions": derived["transitive_function_count"],
            "unclassified": derived["unclassified_C_called_functions"]},
        "local_return": local,
        "local_return_mutations": CANDIDATE.linked_mutations(local),
        "completion_identity": completion,
        "completion_mutations": ["reject-historical-0xb98a"],
        "placement": placement,
        "placement_mutations": PLACEMENT.mutations(placement),
        "WYSIWYG_semantics": semantic,
        "WYSIWYG_semantic_mutations": WYSIWYG.mutations(semantic),
        "linked_transport": transport,
    }


def preflight_value() -> dict[str, Any]:
    frozen = frozen_artifacts()
    tail = candidate_tail()
    golden = GOLD.compare_elf(ELF)
    require(golden["dependent_fixed_vmas"] == 101
            and golden["dependent_free_derived_vmas"] == 2,
            "artifact-only Link-116 Golden preflight red")
    return {
        "format": "lisp65-c2.3-v2.1-wysiwyg-link116-artifact-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: frozen Link-116 armed for Scope/Acceptance",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
                      "placement_checker": bind(PLACEMENT.DRIVER),
                      "semantic_checker": bind(WYSIWYG.DRIVER),
                      "driver": bind(DRIVER)},
        "frozen_artifacts": frozen,
        "supporting_seed": bind(
            BUILD / "wplto/resident-island-seed.prg.lto.o"),
        "producer_tail": tail,
        "golden": {"fixed_vmas": 101, "derived_vmas": 2,
                   "ordinary_headroom_bytes": 11},
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Scope/Acceptance only; frozen Link-116 product bytes are read-only."),
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "Link-116 artifact replay preflight drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("map"),
        "restore-reserve-one": lambda x: x["producer_tail"]["placement"].update(
            ordinary_reserve_bytes=1),
        "restore-opcode-contract": lambda x: x["producer_tail"][
            "WYSIWYG_semantics"]["compiler_evidence"].update(
                instruction_selection_constraint="CMP/LDA"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_preflight(trial, value)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "Link-116 replay mutation survived")
    return rejected


def preflight() -> None:
    require(not PREFLIGHT.exists() and not PRODUCER_RESULT.exists()
            and not SCOPE_RESULT.exists() and not ACCEPTANCE_RESULT.exists()
            and not RECEIPT.exists(), "Link-116 artifact replay is one-shot")
    REPLAY.mkdir(parents=True, exist_ok=True)
    value = preflight_value()
    value["mutations_rejected"] = mutations(value)
    PREFLIGHT.write_bytes(canonical(value))
    print("WYSIWYG Link-116 replay: PREFLIGHT PASS frozen=9 reserve=11")


def rebind_preflight() -> None:
    resume_authorization()
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    require("driver_pre_scope_adapter" not in persisted["authority"],
            "Link-116 replay preflight already rebound")
    expected = preflight_value()
    prior_driver = persisted["authority"]["driver"]
    comparison = deepcopy(expected)
    comparison["authority"]["driver"] = prior_driver
    require(persisted == comparison and rejected == mutations(comparison),
            "driver-only rebind would move non-driver preflight authority")
    expected["authority"]["driver_pre_scope_adapter"] = prior_driver
    expected["mutations_rejected"] = mutations(preflight_value())
    PREFLIGHT.write_bytes(canonical(expected))
    print("WYSIWYG Link-116 replay: PREFLIGHT REBIND driver-only")


def write_producer_tail() -> dict[str, Any]:
    original = load(BUILD / "producer-result.json")
    require(original.get("status") == "PASS"
            and "v21_text_recovery" not in original
            and "candidate_completion_identity" not in original,
            "Link-116 producer-tail input drift")
    for name, fact in frozen_artifacts().items():
        require(original["artifacts"].get(name) == fact,
                f"producer-tail frozen artifact drift: {name}")
    tail = candidate_tail()
    result = deepcopy(original)
    result["artifact_replay_pid"] = os.getpid()
    result["v21_text_recovery"] = tail["local_return"]
    result["v21_text_recovery_mutations"] = tail["local_return_mutations"]
    result["candidate_completion_identity"] = tail["completion_identity"]
    result["candidate_completion_mutations"] = tail["completion_mutations"]
    result["linked_WYSIWYG_semantics"] = tail["WYSIWYG_semantics"]
    result["linked_WYSIWYG_semantic_mutations"] = tail[
        "WYSIWYG_semantic_mutations"]
    PRODUCER_RESULT.write_bytes(canonical(result))
    return result


def scope_child() -> int:
    configure()
    return CARD.BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return CARD.BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh Link-116 artifact-only {action} red:\n{result.stdout}")


def replay() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    prior_driver = persisted["authority"].pop(
        "driver_pre_scope_adapter", None)
    require(prior_driver is not None,
            "authorized driver-only preflight rebind absent")
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == mutations(expected), "replay mutation receipt drift")
    require(PRODUCER_RESULT.exists() and not SCOPE_RESULT.exists()
            and not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "Link-116 artifact replay output exists")
    before = frozen_artifacts()
    producer = load(PRODUCER_RESULT)
    require(producer.get("status") == "PASS"
            and producer.get("v21_text_recovery", {}).get(
                "ordinary") == {
                    "reserve_bytes": 11,
                    "text_end_exclusive": "0xb3a5"}
            and producer.get("linked_WYSIWYG_semantics", {}).get(
                "compiler_evidence", {}).get(
                    "instruction_selection_constraint") is None,
            "persisted Link-116 producer-tail is not resume-green")
    run_child("_scope")
    scope = load(SCOPE_RESULT)
    run_child("_accept")
    acceptance = load(ACCEPTANCE_RESULT)
    after = frozen_artifacts()
    require(after == before, "Scope/Acceptance changed frozen Link-116 bytes")
    comparison = acceptance.get("VMA_golden", {})
    tail = candidate_tail()
    require(len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
            and scope.get("status") == "PASS"
            and acceptance.get("status") == "PASS"
            and comparison.get("dependent_fixed_vmas") == 101
            and comparison.get("dependent_free_derived_vmas") == 2
            and producer["v21_text_recovery"]["ordinary"] == {
                "reserve_bytes": 11, "text_end_exclusive": "0xb3a5"}
            and producer["linked_WYSIWYG_semantics"]["compiler_evidence"][
                "instruction_selection_constraint"] is None
            and tail["WYSIWYG_semantics"]["behavior"][
                "semantic_mismatches"] == 0,
            "artifact-only Link-116 Scope/Acceptance replay red")
    receipt = {
        "format": persisted["format"], "recorded_on": RECORDED_ON,
        "status": "PASS: Link-116 artifact-only Scope/Acceptance",
        "authority": {"owner": authorization(),
                      "resume_owner": resume_authorization(),
                      "Final_Red": bind(FINAL_RED),
                      "preflight": bind(PREFLIGHT),
                      "driver_pre_scope_adapter": prior_driver,
                      "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": tail, "scope": scope, "acceptance": acceptance,
        "process_isolation": {"producer_tail": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "placement": tail["placement_mutations"],
            "WYSIWYG_semantics": tail["WYSIWYG_semantic_mutations"],
            "linked": tail["local_return_mutations"]},
        "next": "Completion and same-world media closure, then D2",
        "claim_limit": (
            "Artifact qualification only; Completion/media/device remain zero."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("WYSIWYG Link-116 replay: PASS WPLTO=0 link=0 card=0 reserve=11")


def check() -> None:
    value = load(RECEIPT)
    frozen = frozen_artifacts()
    require(value.get("status") ==
                "PASS: Link-116 artifact-only Scope/Acceptance"
            and value.get("execution_accounting", {}).get("WPLTO_runs") == 0
            and value.get("execution_accounting", {}).get("product_links") == 0
            and value.get("execution_accounting", {}).get("cards_consumed") == 0
            and value.get("frozen_artifacts_before") == frozen
            and value.get("frozen_artifacts_after") == frozen
            and value.get("process_isolation", {}).get("all_distinct") is True,
            "Link-116 artifact replay receipt drift")
    print("WYSIWYG Link-116 replay: CHECK PASS artifacts=frozen")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "rebind-preflight", "replay", "check",
        "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "rebind-preflight": rebind_preflight,
     "replay": replay, "check": check,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"WYSIWYG Link-116 replay: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
