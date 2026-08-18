#!/usr/bin/env python3
"""Promote persisted Link-116 Scope/Acceptance through a read-only tail."""

from __future__ import annotations

import argparse
import ast
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

import c2_v21_wysiwyg_text_recovery_acceptance_red_attribution as RED  # noqa: E402
import c2_v21_wysiwyg_text_recovery_artifact_replay as REPLAY  # noqa: E402


PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "2b92214f"
RECORDED_ON = "2026-08-17"


class TailError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise TailError(message)


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
    for token in ("read-only qualification tail authorized",
                  "candidate-derived reserve",
                  "arena-minus-emission rule",
                  "persisted green scope and acceptance",
                  "no repeated scope/acceptance", "no wplto",
                  "relink or card"):
        require(token in text, f"qualification-tail authority absent: {token}")
    return value


def derive_headroom(acceptance: dict[str, Any]) -> dict[str, Any]:
    capacity = acceptance["VMA_golden"]["mapped_far_service_capacity"]
    start = capacity["start"]
    end = capacity["end_exclusive"]
    candidate_end = capacity["candidate_max_end_exclusive"]
    arena_bytes = end - start
    candidate_bytes = candidate_end - start
    headroom = end - candidate_end
    far = acceptance["far_payload"]
    tuple_far = acceptance["linked_MAP_tuple"]["far_service"]
    require(acceptance["status"] == "PASS"
            and 0 <= candidate_bytes <= arena_bytes
            and capacity["candidate_headroom_bytes"] == headroom
            and far["candidate_derived_bytes"] == candidate_bytes
            and far["arena_capacity_bytes"] == arena_bytes
            and far["candidate_headroom_bytes"] == headroom
            and tuple_far["candidate_derived_bytes"] == candidate_bytes
            and tuple_far["arena_capacity_bytes"] == arena_bytes
            and tuple_far["candidate_headroom_bytes"] == headroom,
            "qualification tail is not arena minus emitted candidate")
    return {"status": "PASS: headroom derived from candidate extents",
            "authority": "arena-contract-minus-emitted-candidate",
            "arena": {"start": start, "end_exclusive": end,
                      "capacity_bytes": arena_bytes},
            "candidate": {"end_exclusive": candidate_end,
                          "bytes": candidate_bytes,
                          "headroom_bytes": headroom},
            "historical_headroom_expectations": 0}


def validate_headroom(value: dict[str, Any], acceptance: dict[str, Any]) -> None:
    require(value == derive_headroom(acceptance)
            and value["candidate"]["headroom_bytes"] == 251
            and value["historical_headroom_expectations"] == 0,
            "candidate-derived qualification-tail result drift")


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") \
        if source_override is None else source_override
    tree = ast.parse(source)
    node = next(row for row in tree.body
                if isinstance(row, ast.FunctionDef)
                and row.name == "derive_headroom")
    body = ast.unparse(node)
    require("headroom = end - candidate_end" in body
            and "candidate_bytes = candidate_end - start" in body
            and "== 413" not in body,
            "qualification tail pins historical headroom")
    return {"status": "PASS: tail born candidate-derived",
            "historical_headroom_pins": 0}


def mutations(value: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-413-headroom": lambda x: x["candidate"].update(
            headroom_bytes=413),
        "shrink-arena": lambda x: x["arena"].update(capacity_bytes=1498),
        "grow-candidate": lambda x: x["candidate"].update(bytes=1249),
        "restore-historical-expectation": lambda x: x.update(
            historical_headroom_expectations=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_headroom(trial, acceptance)
        except TailError:
            rejected.append(name)
    require(rejected == list(cases), "qualification-tail mutation survived")
    return rejected


def run() -> None:
    require(not REPLAY.RECEIPT.exists(), "qualification tail is one-shot")
    red = load(RED.RECEIPT)
    scope = load(REPLAY.SCOPE_RESULT)
    acceptance = load(REPLAY.ACCEPTANCE_RESULT)
    producer = load(REPLAY.PRODUCER_RESULT)
    before = REPLAY.frozen_artifacts()
    require(red["status"] == RED.STATUS
            and red["disposition_boundary"]["resume_authorized"] is False
            and scope["status"] == "PASS" and acceptance["status"] == "PASS",
            "qualification-tail predecessor drift")
    headroom = derive_headroom(acceptance)
    validate_headroom(headroom, acceptance)
    rejected = mutations(headroom, acceptance)
    source = source_gate()
    after = REPLAY.frozen_artifacts()
    require(after == before, "qualification tail changed frozen Link-116 bytes")
    comparison = acceptance["VMA_golden"]
    require(comparison["dependent_fixed_vmas"] == 101
            and comparison["dependent_free_derived_vmas"] == 2
            and producer["v21_text_recovery"]["ordinary"] == {
                "reserve_bytes": 11, "text_end_exclusive": "0xb3a5"}
            and producer["linked_WYSIWYG_semantics"]["compiler_evidence"][
                "instruction_selection_constraint"] is None,
            "persisted qualification inputs are not green")
    value = {
        "format": "lisp65-c2.3-v2.1-wysiwyg-link116-artifact-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-116 artifact-only Scope/Acceptance",
        "authority": {"owner": REPLAY.authorization(),
            "scope_acceptance_resume_owner": REPLAY.resume_authorization(),
            "qualification_tail_owner": authorization(),
            "Acceptance_First_Red": bind(RED.RECEIPT),
            "preflight": bind(REPLAY.PREFLIGHT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "qualification_tails_run": 1,
            "scope_attempts_total": 2, "scope_completions": 1,
            "acceptance_attempts": 1, "acceptance_outputs_written": 1,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": producer, "scope": scope,
        "acceptance": acceptance, "qualification_tail": headroom,
        "process_isolation": {"qualification_tail": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": len({os.getpid(), scope["pid"],
                                 acceptance["pid"]}) == 3},
        "mutations_rejected": {"qualification_tail": rejected,
                               "source_birth": source},
        "next": "Completion and same-world media closure, then D2",
        "claim_limit": (
            "Scope/Acceptance promoted read-only; Completion/media/device zero."),
    }
    require(value["process_isolation"]["all_distinct"] is True,
            "qualification-tail process is not distinct")
    REPLAY.RECEIPT.write_bytes(canonical(value))
    print("WYSIWYG Link-116 tail: PASS headroom=251 Scope/Acceptance=reused")


def check() -> None:
    value = load(REPLAY.RECEIPT)
    frozen = REPLAY.frozen_artifacts()
    require(value["status"] == "PASS: Link-116 artifact-only Scope/Acceptance"
            and value["qualification_tail"]["candidate"][
                "headroom_bytes"] == 251
            and value["execution_accounting"]["qualification_tails_run"] == 1
            and value["execution_accounting"]["WPLTO_runs"] == 0
            and value["frozen_artifacts_before"] == frozen
            and value["frozen_artifacts_after"] == frozen,
            "qualification-tail receipt drift")
    print("WYSIWYG Link-116 tail: CHECK PASS headroom=251")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check"))
    {"run": run, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TailError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"WYSIWYG Link-116 tail: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
