#!/usr/bin/env python3
"""Artifact-only producer-tail, Scope and Acceptance replay for Link 108."""

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

import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_local_return_identity_card as LOCAL  # noqa: E402
import c2_v21_product_loading_liveness_card as CARD  # noqa: E402
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
RECEIPT = ARCH / "c2.3-v2.1-product-loading-liveness-artifact-replay-receipt.json"
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "19b76794"
FORMAT = "lisp65-c2.3-v2.1-product-loading-liveness-artifact-replay-v1"


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
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("checker rebind and artifact-only replay approved",
                  "no wplto", "no link", "no card consumed",
                  "new checkers are born candidate-derived"):
        require(token in text, f"artifact-replay authority absent: {token}")
    return authority


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    require(
        value.get("status") == "FINAL RED: product-liveness card returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting") == {
            "WPLTO_runs": 1, "cards_authorized": 1, "cards_consumed": 1,
            "completion_runs": 0, "device_contacts": 0, "media_builds": 0,
            "product_link_attempts": 1},
        "product-liveness Final Red authority drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = final_red()["artifacts"]
    current = {name: bind(ROOT / row["path"]) for name, row in expected.items()}
    require(current == expected, "frozen Link-108 artifact SHA drift")
    return current


def configure() -> None:
    LOCAL.linked_gate = CANDIDATE.linked_gate
    LOCAL.linked_mutations = CANDIDATE.linked_mutations
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.configure()


def candidate_tail() -> dict[str, Any]:
    # Bind every historical consumer to the frozen Link-108 candidate before
    # asking it to interpret candidate sections or publish-last metadata.
    configure()
    section = COMPLETION.PRODUCT.section_table(ELF).get(
        COMPLETION.PRODUCT.VERIFIER_BINDING_SECTION)
    family_stage = bool(section and section["bytes"] == (
        COMPLETION.PRODUCT.VERIFIER_BINDING_BYTES
        + COMPLETION.PRODUCT.FAMILY_STAGE_BINDING_BYTES))
    require(family_stage,
            "candidate family-stage binding identity is absent")
    COMPLETION.PRODUCT.FAMILY_STAGE_BINDINGS = family_stage
    linked = CANDIDATE.linked_gate(ELF, MANIFEST)
    completion = COMPLETION.completion_gate(ELF)
    require(linked["reader"]["bytes"] == 188
            and linked["ordinary"]["reserve_bytes"] == 2
            and linked["ownership"]["violations"] == []
            and completion["status"] ==
                "PASS: publish-last consumed candidate identity",
            "artifact-only producer tail is not green")
    return {"candidate_configuration": {
                "family_stage_bindings": family_stage},
            "local_return": linked,
            "local_return_mutations": CANDIDATE.linked_mutations(linked),
            "completion_identity": completion,
            "completion_mutations": ["reject-historical-0xb98a"]}


def preflight_value() -> dict[str, Any]:
    before = frozen_artifacts()
    tail = candidate_tail()
    golden = GOLD.compare_elf(ELF)
    require(golden["dependent_fixed_vmas"] == 101
            and golden["dependent_free_derived_vmas"] == 2,
            "artifact-only preflight Golden red")
    return {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: artifact-only replay armed; frozen SHAs exact",
        "authority": {"owner": authorization(), "final_red": bind(FINAL_RED),
                      "checker": bind(CANDIDATE.DRIVER), "driver": bind(DRIVER)},
        "frozen_artifacts": before,
        "checker_birth": CANDIDATE.birth_gate(),
        "checker_birth_mutations": CANDIDATE.source_mutations(),
        "producer_tail": tail,
        "golden": {"fixed_vmas": 101, "derived_vmas": 2,
                   "ordinary_headroom_bytes": 2},
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": "Artifact-only preflight; no product artifact is written.",
    }


def validate_preflight(
        value: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    require(value == (preflight_value() if expected is None else expected),
            "artifact-only replay preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("map"),
        "restore-old-reader": lambda x: x["producer_tail"]["local_return"][
            "reader"].update(bytes=166),
        "skip-birth-gate": lambda x: x.update(checker_birth={}),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate, value)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "artifact-only preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not REPLAY.exists() and not RECEIPT.exists(),
            "artifact-only replay is one-shot")
    value = preflight_value()
    validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    REPLAY.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(value))
    print("2.1 liveness replay: PREFLIGHT PASS artifacts=frozen replay=0/1")


def write_producer_tail() -> dict[str, Any]:
    original = load(BUILD / "producer-result.json")
    require(original.get("status") == "PASS"
            and "v21_text_recovery" not in original
            and "candidate_completion_identity" not in original,
            "artifact-only replay producer-tail input drift")
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
            f"fresh artifact-only {action} red:\n{result.stdout}")


def replay() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "artifact-only preflight mutation receipt drift")
    require(not PRODUCER_RESULT.exists() and not SCOPE_RESULT.exists()
            and not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "artifact-only replay output already exists")
    before = frozen_artifacts()
    producer = write_producer_tail()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "artifact-only replay changed frozen artifacts")
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    comparison = acceptance.get("VMA_golden", {})
    require(
        len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
        and scope.get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and producer["v21_text_recovery"]["ownership"]["violations"] == [],
        "artifact-only Scope/Acceptance replay red")
    receipt = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: artifact-only producer-tail Scope Acceptance replay",
        "authority": {"owner": authorization(), "final_red": bind(FINAL_RED),
            "preflight": bind(PREFLIGHT), "checker": bind(CANDIDATE.DRIVER),
            "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": candidate_tail(),
        "scope": scope, "acceptance": acceptance,
        "process_isolation": {"producer_tail": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "checker_birth": CANDIDATE.source_mutations(),
            "linked": producer["v21_text_recovery_mutations"]},
        "next": "Completion and same-world media closure, then D1",
        "claim_limit": "Artifact qualification only; Completion/media/device remain zero.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 liveness replay: PASS WPLTO=0 link=0 card=0 fixed=101 derived=2")


def check() -> None:
    value = load(RECEIPT)
    before = frozen_artifacts()
    require(
        value.get("status") ==
            "PASS: artifact-only producer-tail Scope Acceptance replay"
        and value.get("execution_accounting") == {
            "artifact_replays_authorized": 1, "artifact_replays_run": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0}
        and value.get("frozen_artifacts_before") == before
        and value.get("frozen_artifacts_after") == before
        and value.get("process_isolation", {}).get("all_distinct") is True,
        "artifact-only replay receipt drift")
    print("2.1 liveness replay: CHECK PASS artifacts=frozen WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "replay", "check", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "replay": replay, "check": check,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, CANDIDATE.CandidateCheckerError) as error:
        print(f"2.1 liveness replay: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
