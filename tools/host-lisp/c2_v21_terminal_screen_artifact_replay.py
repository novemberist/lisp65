#!/usr/bin/env python3
"""Artifact-only producer-tail, Scope and Acceptance replay for Link 111."""

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
import c2_v21_abi_vocabulary_pairing as ABI_PAIR  # noqa: E402
import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_resume as PHASE9_RESUME  # noqa: E402
import c2_v21_terminal_screen_map_authority_rebind as MAP_REBIND  # noqa: E402
import c2_v21_terminal_screen_lease_card as CARD  # noqa: E402
import c2_v21_text_recovery_replacement_card as COMPLETION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
MANIFEST = BUILD / "wplto/runtime-overlays-session-final.json"
REPLAY = BUILD / "artifact-only-replay"
PREFLIGHT = REPLAY / "preflight.json"
PRODUCER_RESULT = REPLAY / "producer-tail-result.json"
SCOPE_RESULT = REPLAY / "owner-scope-result.json"
ACCEPTANCE_RESULT = REPLAY / "artifact-acceptance.json"
ABI_REPORT = REPLAY / "c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-artifact-replay-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9180e59a"
RECORDED_ON = "2026-08-16"


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
    text = " ".join(raw.lower().split())
    for token in ("artifact-only qualification replay",
                  "producer/consumer pairing clause",
                  "authority rebinds loudly", "no wplto", "no relink",
                  "no card"):
        require(token in text, f"screen artifact-replay token absent: {token}")
    return value


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    require(
        value.get("status") ==
            "FINAL RED: terminal screen-lease card returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting") == {
            "WPLTO_runs": 1, "cards_authorized": 1, "cards_consumed": 1,
            "completion_runs": 0, "device_contacts": 0, "media_builds": 0,
            "product_link_attempts": 1},
        "terminal screen Final Red authority drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = final_red()["artifacts"]
    current = {name: bind(ROOT / row["path"]) for name, row in expected.items()}
    require(current == expected, "frozen Link-111 artifact SHA drift")
    return current


def configure() -> None:
    PHASE9_RESUME.install_successors()
    CANDIDATE.placement_contract = MAP_REBIND.placement_contract
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.ABI_REPORT = ABI_REPORT
    CARD.configure()


def candidate_tail() -> dict[str, Any]:
    configure()
    report = ABI.audit_elf(ELF, out=ABI_REPORT, require_bank3_chain=True)
    derived = report["ELF_derived_C_called_inventory"]
    require(derived["status"] == ABI.ELF_DERIVED_C_CALLED_STATUS
            and derived["unclassified_C_called_functions"] == [],
            "frozen ELF ABI vocabulary/closure red")
    section = COMPLETION.PRODUCT.section_table(ELF).get(
        COMPLETION.PRODUCT.VERIFIER_BINDING_SECTION)
    family_stage = bool(section and section["bytes"] == (
        COMPLETION.PRODUCT.VERIFIER_BINDING_BYTES
        + COMPLETION.PRODUCT.FAMILY_STAGE_BINDING_BYTES))
    require(family_stage, "candidate family-stage binding identity absent")
    COMPLETION.PRODUCT.FAMILY_STAGE_BINDINGS = family_stage
    local = CANDIDATE.linked_gate(ELF, MANIFEST)
    completion = COMPLETION.completion_gate(ELF)
    linked = CARD.linked_product()
    require(
        local["reader"]["bytes"] == 189
        and local["ordinary"]["reserve_bytes"] == 1
        and local["ownership"]["violations"] == []
        and linked["terminal_screen_lease"]["post_phase_visible"] is False
        and linked["MAP_tuple_gate"]["positive"]["MAPL"] == "0x4fc0"
        and completion["status"] ==
            "PASS: publish-last consumed candidate identity",
        "artifact-only Link-111 producer tail is red")
    return {"candidate_configuration": {
                "family_stage_bindings": family_stage},
            "ABI_vocabulary": {"status": derived["status"],
                "transitive_functions": derived["transitive_function_count"],
                "unclassified": derived["unclassified_C_called_functions"]},
            "local_return": local,
            "local_return_mutations": CANDIDATE.linked_mutations(local),
            "completion_identity": completion,
            "completion_mutations": ["reject-historical-0xb98a"],
            "linked_product": linked,
            "screen_mutations": CARD.linked_mutations(linked)}


def preflight_value() -> dict[str, Any]:
    frozen = frozen_artifacts()
    tail = candidate_tail()
    golden = GOLD.compare_elf(ELF)
    require(golden["dependent_fixed_vmas"] == 101
            and golden["dependent_free_derived_vmas"] == 2,
            "artifact-only Link-111 Golden preflight red")
    return {"format": "lisp65-c2.3-v2.1-terminal-screen-artifact-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-111 frozen artifacts armed for qualification replay",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "ABI_pairing": bind(ABI_PAIR.RECEIPT),
            "MAP_rebind": bind(MAP_REBIND.RECEIPT), "driver": bind(DRIVER)},
        "frozen_artifacts": frozen,
        "producer_tail": tail,
        "golden": {"fixed_vmas": 101, "derived_vmas": 2,
                   "ordinary_headroom_bytes": 1},
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": "Post-link qualification only; frozen product bytes are read-only."}


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "terminal screen artifact-replay preflight drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("map"),
        "restore-old-ABI-word": lambda x: x["producer_tail"][
            "ABI_vocabulary"].update(
                status="passed-ELF-derived-C-called-assembler-universe"),
        "restore-old-MAP-authority": lambda x: x["authority"].pop("MAP_rebind"),
        "restore-visible-zero": lambda x: x["producer_tail"]["linked_product"]
            ["terminal_screen_lease"].update(post_phase_visible=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "artifact-replay mutation survived")
    return rejected


def preflight() -> None:
    require(not PREFLIGHT.exists() and not PRODUCER_RESULT.exists()
            and not SCOPE_RESULT.exists() and not ACCEPTANCE_RESULT.exists()
            and not RECEIPT.exists(),
            "terminal screen artifact replay is one-shot")
    REPLAY.mkdir(parents=True, exist_ok=True)
    value = preflight_value(); value["mutations_rejected"] = mutations(value)
    PREFLIGHT.write_bytes(canonical(value))
    print("2.1 terminal screen replay: PREFLIGHT PASS frozen=9 replay=0/1")


def rebind_preflight() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    prior_driver = persisted["authority"]["driver"]
    comparison = deepcopy(expected)
    comparison["authority"]["driver"] = prior_driver
    require(persisted == comparison and rejected == mutations(comparison),
            "Acceptance-adapter rebind moved more than replay-driver authority")
    expected["authority"]["driver_pre_acceptance_adapter"] = prior_driver
    expected["mutations_rejected"] = mutations(preflight_value())
    PREFLIGHT.write_bytes(canonical(expected))
    print("2.1 terminal screen replay: PREFLIGHT REBIND acceptance-adapter-only")


def write_producer_tail() -> dict[str, Any]:
    original = load(BUILD / "producer-result.json")
    require(original.get("status") == "PASS"
            and "v21_text_recovery" not in original
            and "candidate_completion_identity" not in original,
            "terminal screen producer-tail input drift")
    tail = candidate_tail()
    result = deepcopy(original)
    result["artifact_replay_pid"] = os.getpid()
    result["v21_text_recovery"] = tail["local_return"]
    result["v21_text_recovery_mutations"] = tail["local_return_mutations"]
    result["candidate_completion_identity"] = tail["completion_identity"]
    result["candidate_completion_mutations"] = tail["completion_mutations"]
    PRODUCER_RESULT.write_bytes(canonical(result))
    return result


def scope_child() -> int:
    configure()
    return CARD.scope_child()


def acceptance_child() -> int:
    configure()
    return CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh terminal screen artifact-only {action} red:\n{result.stdout}")


def replay() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    persisted["authority"].pop("driver_pre_acceptance_adapter", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(rejected == mutations(expected), "replay mutation receipt drift")
    require(not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "terminal screen artifact-replay output exists")
    before = frozen_artifacts()
    if PRODUCER_RESULT.exists():
        producer = load(PRODUCER_RESULT)
        require(producer.get("status") == "PASS"
                and producer.get("v21_text_recovery", {}).get(
                    "ownership", {}).get("violations") == [],
                "persisted producer-tail is not green")
    else:
        producer = write_producer_tail()
    if SCOPE_RESULT.exists():
        scope = load(SCOPE_RESULT)
        require(scope.get("status") == "PASS", "persisted Scope is not green")
    else:
        run_child("_scope")
        scope = load(SCOPE_RESULT)
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "artifact replay changed frozen Link-111 bytes")
    acceptance = load(ACCEPTANCE_RESULT)
    comparison = acceptance.get("VMA_golden", {})
    tail = candidate_tail()
    require(
        len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
        and scope.get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and producer["v21_text_recovery"]["ownership"]["violations"] == []
        and tail["linked_product"]["terminal_screen_lease"][
            "post_phase_visible"] is False,
        "artifact-only Link-111 Scope/Acceptance replay red")
    receipt = {"format": persisted["format"], "recorded_on": RECORDED_ON,
        "status": "PASS: Link-111 artifact-only producer-tail Scope Acceptance",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "preflight": bind(PREFLIGHT), "ABI_pairing": bind(ABI_PAIR.RECEIPT),
            "MAP_rebind": bind(MAP_REBIND.RECEIPT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": tail, "scope": scope, "acceptance": acceptance,
        "process_isolation": {"producer_tail": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "ABI_pairing": load(ABI_PAIR.RECEIPT)["mutations_rejected"],
            "MAP_rebind": load(MAP_REBIND.RECEIPT)["mutations_rejected"],
            "linked": producer["v21_text_recovery_mutations"],
            "screen": tail["screen_mutations"]},
        "next": "Completion and same-world media closure, then clean owner-observed D1",
        "claim_limit": "Artifact qualification only; Completion/media/device remain zero."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 terminal screen replay: PASS WPLTO=0 link=0 card=0 fixed=101")


def check() -> None:
    value = load(RECEIPT); frozen = frozen_artifacts()
    require(
        value.get("status") ==
            "PASS: Link-111 artifact-only producer-tail Scope Acceptance"
        and value.get("execution_accounting", {}).get("WPLTO_runs") == 0
        and value.get("execution_accounting", {}).get("product_links") == 0
        and value.get("execution_accounting", {}).get("cards_consumed") == 0
        and value.get("frozen_artifacts_before") == frozen
        and value.get("frozen_artifacts_after") == frozen
        and value.get("process_isolation", {}).get("all_distinct") is True,
        "terminal screen artifact-replay receipt drift")
    print("2.1 terminal screen replay: CHECK PASS artifacts=frozen")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "rebind-preflight", "replay", "check", "_scope", "_accept"))
    {"preflight": preflight, "replay": replay, "check": check,
     "rebind-preflight": rebind_preflight,
     "_scope": scope_child, "_accept": acceptance_child}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 terminal screen replay: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
