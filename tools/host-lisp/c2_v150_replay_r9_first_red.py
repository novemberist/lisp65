#!/usr/bin/env python3
"""Bind the consumed Link-97 r9 post-link consumer First Red."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.5.0-candidate-product-link97"
R9 = BUILD / "post-link-qualification-replay-r9"
PROFILE = R9 / "candidate-profile.json"
INTERNAL = R9 / "wplto-internal.json"
PRIOR_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r8-first-red.json")
ISOLATION = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-process-isolation-receipt.json")
CONTENT = EVIDENCE / (
    "c2.3-v1.5.0-link97-nine-slice-content-map-rebind-receipt.json")
CAPACITY = EVIDENCE / (
    "c2.3-v1.5.0-link97-capacity-identity-inversion-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r9-first-red.json")
CANDIDATE = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
ADAPTER = ROOT / "tools/host-lisp/c2_v150_replay_r9.py"
CANONICAL = ROOT / "tools/host-lisp/c2_lite_canonical_product.py"
REPLACEMENT = ROOT / (
    "tools/host-lisp/c2_lite_v6_boot_crc_abi_successor_link.py")
EXECUTION_HEAD = "6d704c5e51176d1da3f33b810d508eca0ced01c0"
EXECUTION_LABEL = "6d704c5e"
RECORDER_HEAD = "cf7ada9576685d0a4bab78d00d154adfa00dfa42"
FORMAT = "lisp65-c2.3-v150-link97-post-link-replay-r9-first-red-v1"
STATUS = "FIRST RED; OWNER-DISPOSITION-REQUIRED; AUTHORIZED-REPLAY-CONSUMED"
REQUIRED_KEYS = {
    "bank2_workbench_scratch_negative",
    "roots_fronts_one_slice_two_entry",
    "final_island_single_runtime_identity",
}


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"r9 First-Red authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw), "sha256": sha_bytes(raw)}


def git_text(commit: str, path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout.decode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"r9 First-Red JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"r9 First-Red object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def consumer_keys(source: str) -> set[str]:
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name == "fresh_current_product_postlink_gate")
    return {
        node.slice.value for node in ast.walk(function)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "replacement"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    }


def frozen_artifacts() -> dict[str, Any]:
    frozen = load(PRIOR_RED)["frozen_artifacts_after_stop"]
    for role, row in frozen.items():
        require(bind(ROOT / row["path"]) == row,
                f"frozen Link-97 artifact drift: {role}")
    return frozen


def collect() -> dict[str, Any]:
    internal = load(INTERNAL)
    replacement = internal["fresh_replacement_gates"]
    produced = set(replacement)
    consumed = consumer_keys(git_text(EXECUTION_HEAD, CANONICAL))
    missing = sorted(consumed - produced)
    files = sorted(
        path.relative_to(R9).as_posix()
        for path in R9.rglob("*") if path.is_file())
    require(
        files == [
            "c2-asm-leaf-real-abi-callers.json",
            "c2-crc-asm-leaf-workbench-gate.json",
            "candidate-profile.json", "wplto-internal.json"]
        and internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and replacement["status"] == "passed"
        and set(missing) == REQUIRED_KEYS
        and internal["fresh_real_abi_gate"]["status"]
            == "passed-all-assembler-leaf-abi-contracts",
        "r9 post-link consumer boundary drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "attempt_accounting": {
            "artifact_only_replays_authorized": 1,
            "artifact_only_replays_consumed": 1,
            "WPLTO_runs": 0, "compiler_runs": 0, "linker_runs": 0,
            "artifact_completions": 0, "media_builds": 0,
            "hardware_runs": 0,
        },
        "boundary": {
            "replay_profile_written": True,
            "process_isolation_validated": True,
            "ambient_capacity_content_closures_validated": True,
            "candidate_configuration_completed": True,
            "replacement_gate_completed": True,
            "real_ABI_gate_completed": True,
            "replay_internal_written": True,
            "current_postlink_consumer_started": True,
            "current_postlink_consumer_completed": False,
            "linked_gate_started": False,
            "artifact_completion_started": False,
        },
        "mechanism": {
            "classification":
                "postlink-producer-consumer-replacement-vocabulary-gap",
            "failure": "KeyError: 'bank2_workbench_scratch_negative'",
            "replacement_status": replacement["status"],
            "produced_keys": sorted(produced),
            "consumer_required_keys": sorted(consumed),
            "missing_keys": missing,
            "statement": (
                "The isolated runtime fixture left the candidate process "
                "clean, and the current replacement and real-ABI stages "
                "completed. The next post-link consumer directly requires "
                "three successor proof fields that the artifact-only "
                "replacement producer did not emit. It stopped on the first "
                "missing key before the linked gate or completion. This is a "
                "qualification producer/consumer contract gap; whether each "
                "field is a renamed proof or absent qualification remains an "
                "owner-gated content-closure question, not a product claim."),
        },
        "stopped_output": {
            "files": files,
            "profile": bind(PROFILE),
            "internal": bind(INTERNAL),
        },
        "frozen_artifacts_after_stop": frozen_artifacts(),
        "execution_authority": {
            "authorization_commit": "5ebf8e93",
            "prepared_HEAD": EXECUTION_LABEL,
            "prior_first_red": git_bind(EXECUTION_HEAD, PRIOR_RED),
            "process_isolation": git_bind(EXECUTION_HEAD, ISOLATION),
            "content_map_rebind": git_bind(EXECUTION_HEAD, CONTENT),
            "capacity_identity": git_bind(EXECUTION_HEAD, CAPACITY),
            "candidate_driver": git_bind(EXECUTION_HEAD, CANDIDATE),
            "r9_adapter": git_bind(EXECUTION_HEAD, ADAPTER),
            "postlink_consumer": git_bind(EXECUTION_HEAD, CANONICAL),
            "replacement_producer": git_bind(EXECUTION_HEAD, REPLACEMENT),
            "recorder": git_bind(RECORDER_HEAD, Path(__file__)),
        },
        "disposition": {
            "automatic_retry_authorized": False,
            "completion_or_media_authorized": False,
            "owner_question": (
                "Park, or authorize an artifact-only semantic content map "
                "for the three missing successor proof fields, followed by "
                "separate authorization of any later replay?"),
        },
        "claim_limit": (
            "One consumed r9 replay and one named post-link qualification "
            "producer/consumer gap. Replacement and real-ABI gates are green; "
            "linked gate, completion, product receipt, medium, device, Halt "
            "and release remain unclaimed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting", {}).get(
            "artifact_only_replays_consumed") == 1
        and value.get("boundary", {}).get("replacement_gate_completed") is True
        and value.get("boundary", {}).get(
            "current_postlink_consumer_completed") is False
        and value.get("boundary", {}).get("linked_gate_started") is False
        and value.get("boundary", {}).get("artifact_completion_started") is False
        and set(value.get("mechanism", {}).get("missing_keys", []))
            == REQUIRED_KEYS
        and value.get("disposition", {}).get("automatic_retry_authorized")
            is False,
        "r9 First-Red claim drift")
    if verify:
        require(value == collect(), "r9 First-Red authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-retry": lambda x: x["disposition"].update(
            automatic_retry_authorized=True),
        "claim-postlink-complete": lambda x: x["boundary"].update(
            current_postlink_consumer_completed=True),
        "claim-linked-gate": lambda x: x["boundary"].update(
            linked_gate_started=True),
        "claim-completion": lambda x: x["boundary"].update(
            artifact_completion_started=True),
        "erase-missing-proof": lambda x: x["mechanism"]["missing_keys"].pop(),
        "erase-consumption": lambda x: x["attempt_accounting"].update(
            artifact_only_replays_consumed=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except FirstRedError:
            rejected.append(name)
    require(rejected == list(cases), "r9 First-Red mutation survived")
    return rejected


def capture() -> int:
    require(not RECEIPT.exists(), "r9 First-Red receipt already exists")
    value = collect(); validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 r9 First Red capture: PASS postlink-vocabulary-gap")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "r9 First-Red mutation drift")
    print("v1.5 Link-97 r9 First Red check: PASS postlink-vocabulary-gap")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "check"))
    return {"capture": capture, "check": check}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 r9 First Red: RED: {error}")
        raise SystemExit(2)
