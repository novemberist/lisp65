#!/usr/bin/env python3
"""Bind the consumed Link-97 r7 artifact-replay First Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.5.0-candidate-product-link97"
REPLAY = BUILD / "post-link-qualification-replay-r7"
PROFILE = REPLAY / "candidate-profile.json"
CONTENT_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-nine-slice-content-map-receipt.json")
AMBIENT_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-ambient-closure-receipt.json")
CAPACITY_RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-capacity-identity-inversion-receipt.json")
PRIOR_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r6-first-red.json")
REPLACEMENT = ROOT / (
    "tools/host-lisp/c2_lite_v6_boot_crc_abi_successor_link.py")
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r7-first-red.json")
EXECUTION_HEAD = "93303a02fbec1f40bd1e9c220bd665cabdc9c9b1"
FORMAT = "lisp65-c2.3-v150-link97-post-link-replay-r7-first-red-v1"
STATUS = "FIRST RED; OWNER-DISPOSITION-REQUIRED; AUTHORIZED-REPLAY-CONSUMED"


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"First-Red authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_bytes(path.read_bytes()),
    }


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw), "sha256": sha_bytes(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"First-Red JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"First-Red JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def frozen_artifacts() -> dict[str, Any]:
    prior = load(PRIOR_RED)["frozen_artifacts_after_stop"]
    for role, row in prior.items():
        path = ROOT / row["path"]
        require(bind(path) == row, f"frozen Link-97 artifact drift: {role}")
    return prior


def collect() -> dict[str, Any]:
    content = load(CONTENT_RECEIPT)
    ambient = load(AMBIENT_RECEIPT)
    capacity = load(CAPACITY_RECEIPT)
    recorded_source = content["authorities"]["replacement_gate"]
    execution_source = git_bind(EXECUTION_HEAD, REPLACEMENT)
    files = sorted(
        path.relative_to(REPLAY).as_posix()
        for path in REPLAY.rglob("*") if path.is_file())
    require(
        files == ["candidate-profile.json"]
        and content.get("status")
            == "passed-nine-vocabulary-successors-zero-freight-gaps"
        and ambient.get("status")
            == "PASSED-REPLACEMENT-INVERSION-AND-ONE-TIME-AMBIENT-SWEEP"
        and ambient.get("source_gate", {}).get("ambient_input_count") == 0
        and capacity.get("status")
            == "passed-Link-97-current-contract-capacity-inversion"
        and recorded_source["path"] == execution_source["path"]
        and recorded_source["sha256"] != execution_source["sha256"],
        "r7 content-map First-Red boundary drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-11",
        "status": STATUS,
        "attempt_accounting": {
            "artifact_only_replays_authorized": 1,
            "artifact_only_replays_consumed": 1,
            "WPLTO_runs": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "artifact_completions": 0,
            "media_builds": 0,
            "hardware_runs": 0,
        },
        "boundary": {
            "replay_profile_written": True,
            "ambient_closure_validated": True,
            "capacity_identity_validated": True,
            "content_map_validation_started": True,
            "content_map_validation_completed": False,
            "replacement_gate_started": False,
            "real_ABI_gate_started": False,
            "replay_internal_written": False,
            "artifact_completion_started": False,
        },
        "mechanism": {
            "classification":
                "pre-replacement-stale-content-map-source-authority",
            "failure": "content-map authority drift",
            "recorded_replacement_source": recorded_source,
            "execution_replacement_source": execution_source,
            "statement": (
                "The r7 replay validated the new ambient and capacity "
                "closures, then the pre-existing nine-slice content-map "
                "receipt rejected the replacement-gate source changed by "
                "the authorized inversion. No semantic content-map row, "
                "replacement gate or artifact completion was reached."),
        },
        "frozen_artifacts_after_stop": frozen_artifacts(),
        "execution_authority": {
            "authorization_commit": "f1560759",
            "prepared_HEAD": EXECUTION_HEAD,
            "candidate_profile": bind(PROFILE),
            "ambient_closure": bind(AMBIENT_RECEIPT),
            "capacity_identity": bind(CAPACITY_RECEIPT),
            "content_map": bind(CONTENT_RECEIPT),
            "recorder": bind(Path(__file__)),
        },
        "disposition": {
            "automatic_retry_authorized": False,
            "completion_or_media_authorized": False,
            "owner_question": (
                "Park, or explicitly authorize a semantic-preserving "
                "content-map source-authority rebind and separately "
                "authorize any later artifact-only replay?"),
        },
        "claim_limit": (
            "One consumed r7 artifact-only replay. The artifact-bound "
            "ambient and capacity closures are green; content-map authority "
            "validation is red. No replacement-gate, completion, product "
            "receipt, medium, device, Halt or release claim exists."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting", {}).get(
            "artifact_only_replays_consumed") == 1
        and value.get("boundary", {}).get("replacement_gate_started") is False
        and value.get("boundary", {}).get("artifact_completion_started") is False
        and value.get("disposition", {}).get("automatic_retry_authorized")
            is False,
        "r7 First-Red claim drift")
    if verify:
        require(value == collect(), "r7 First-Red authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-retry": lambda x: x["disposition"].update(
            automatic_retry_authorized=True),
        "claim-replacement": lambda x: x["boundary"].update(
            replacement_gate_started=True),
        "claim-completion": lambda x: x["boundary"].update(
            artifact_completion_started=True),
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
    require(rejected == list(cases), "r7 First-Red mutation survived")
    return rejected


def capture() -> int:
    value = collect(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 r7 First Red capture: PASS pre-replacement no-retry")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "r7 First-Red mutation drift")
    print("v1.5 Link-97 r7 First Red check: PASS pre-replacement no-retry")
    return 0


def selftest() -> int:
    value = collect(); mutations(value)
    print("v1.5 Link-97 r7 First Red selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "check", "selftest"))
    return {"capture": capture, "check": check,
            "selftest": selftest}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, OSError, KeyError, ValueError,
            subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 r7 First Red: FIRST RED: {error}")
        raise SystemExit(2)
