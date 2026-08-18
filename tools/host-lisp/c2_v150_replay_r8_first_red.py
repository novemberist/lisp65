#!/usr/bin/env python3
"""Bind the consumed Link-97 r8 in-process verifier First Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.5.0-candidate-product-link97"
R8 = BUILD / "post-link-qualification-replay-r8"
PROFILE = R8 / "candidate-profile.json"
PRIOR_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r7-first-red.json")
AMBIENT = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-ambient-closure-receipt.json")
CONTENT = EVIDENCE / (
    "c2.3-v1.5.0-link97-nine-slice-content-map-rebind-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r8-first-red.json")
AMBIENT_TOOL = ROOT / "tools/host-lisp/c2_v150_qualification_ambient_closure.py"
CANDIDATE = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
ADAPTER = ROOT / "tools/host-lisp/c2_v150_replay_r8.py"
EXECUTION_HEAD = "3915c793"
FORMAT = "lisp65-c2.3-v150-link97-post-link-replay-r8-first-red-v1"
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
            f"r8 First-Red authority absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha_bytes(path.read_bytes())}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw), "sha256": sha_bytes(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"r8 First-Red JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"r8 First-Red JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def diagnostic() -> dict[str, Any]:
    source = r'''import json
import c2_v150_candidate_product as c
import c2_v150_qualification_ambient_closure as a
p = c.L95.CAN.PRODUCT
before = dict(p.PROFILE_RODATA_INPUT_SECTIONS)
value = json.load(open(a.RECEIPT)); value.pop("mutations_rejected")
a.validate(value, verify=True)
after = dict(p.PROFILE_RODATA_INPUT_SECTIONS)
error = None
try:
    c.configure(c.REPLAY_PREVIOUS_RED / "candidate-profile.json")
except Exception as caught:
    error = f"{type(caught).__name__}: {caught}"
print(json.dumps({"before": before, "after": after, "error": error}, sort_keys=True))'''
    environment = dict(__import__("os").environ)
    environment["PYTHONPATH"] = str(ROOT / "tools/host-lisp")
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def collect(*, run_diagnostic: bool) -> dict[str, Any]:
    prior = load(PRIOR_RED)
    frozen = prior["frozen_artifacts_after_stop"]
    for role, row in frozen.items():
        require(bind(ROOT / row["path"]) == row,
                f"frozen Link-97 artifact drift: {role}")
    files = sorted(path.relative_to(R8).as_posix()
                   for path in R8.rglob("*") if path.is_file())
    require(files == ["candidate-profile.json"],
            "r8 stopped-state output boundary drift")
    observed = diagnostic() if run_diagnostic else {
        "before": {
            ".rodata.eval_v2_workbench_service": 32,
            ".rodata.vm_callprim": 164,
            ".rodata.vm_native_call": 146,
        },
        "after": {
            ".rodata.eval_v2_workbench_service": 32,
            ".rodata.vm_callprim": 168,
            ".rodata.vm_native_call": 148,
        },
        "error": "ValueError: require-resolver profile selector order drift",
    }
    require(
        observed["before"][".rodata.vm_callprim"] == 164
        and observed["before"][".rodata.vm_native_call"] == 146
        and observed["after"][".rodata.vm_callprim"] == 168
        and observed["after"][".rodata.vm_native_call"] == 148
        and observed["error"]
            == "ValueError: require-resolver profile selector order drift",
        "r8 selector-contamination diagnostic drift")
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
            "ambient_closure_validated": True,
            "capacity_identity_validated": True,
            "content_map_rebind_validated": True,
            "candidate_configuration_started": True,
            "candidate_configuration_completed": False,
            "replacement_gate_started": False,
            "artifact_completion_started": False,
        },
        "mechanism": {
            "classification":
                "in-process-ambient-runtime-fixture-selector-state-contamination",
            "failure": observed["error"],
            "selector_state": observed,
            "execution_order": {
                "1_ambient_receipt_validation":
                    "runs runtime_gate in the replay process",
                "2_runtime_fixture_configuration": "164/146 -> 168/148",
                "3_candidate_configuration":
                    "rejects the second selector application before replacement",
            },
            "statement": (
                "The semantic content-map rebind passed. The ambient receipt "
                "then re-executed its artifact runtime fixture inside the "
                "replay process, mutating one-shot profile-selector globals. "
                "The real candidate configure correctly rejected that inherited "
                "state; no product qualification gate ran."),
        },
        "frozen_artifacts_after_stop": frozen,
        "execution_authority": {
            "authorization_commit": "37f12ed3",
            "execution_HEAD": EXECUTION_HEAD,
            "candidate_profile": bind(PROFILE),
            "prior_first_red": git_bind(EXECUTION_HEAD, PRIOR_RED),
            "ambient_closure": git_bind(EXECUTION_HEAD, AMBIENT),
            "content_map_rebind": git_bind(EXECUTION_HEAD, CONTENT),
            "ambient_tool": git_bind(EXECUTION_HEAD, AMBIENT_TOOL),
            "candidate_driver": git_bind(EXECUTION_HEAD, CANDIDATE),
            "r8_adapter": git_bind(EXECUTION_HEAD, ADAPTER),
            "recorder": bind(Path(__file__)),
        },
        "disposition": {
            "automatic_retry_authorized": False,
            "completion_or_media_authorized": False,
            "owner_question": (
                "Park, or authorize isolation of the ambient runtime fixture "
                "in a fresh process with a mutation against selector-state "
                "leakage, followed by separate authorization of any replay?"),
        },
        "claim_limit": (
            "One consumed r8 replay and one named verifier-side state leak. "
            "No candidate configuration, replacement gate, completion, "
            "product receipt, medium, device, Halt or release claim exists."),
    }


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting", {}).get(
            "artifact_only_replays_consumed") == 1
        and value.get("boundary", {}).get("replacement_gate_started") is False
        and value.get("boundary", {}).get("artifact_completion_started") is False
        and value.get("disposition", {}).get("automatic_retry_authorized")
            is False,
        "r8 First-Red claim drift")


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
            validate(candidate)
        except FirstRedError:
            rejected.append(name)
    require(rejected == list(cases), "r8 First-Red mutation survived")
    return rejected


def capture() -> int:
    value = collect(run_diagnostic=True); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 r8 First Red capture: PASS selector-state-leak")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(value == collect(run_diagnostic=False),
            "r8 First-Red authority drift")
    require(rejected == mutations(value), "r8 First-Red mutation drift")
    print("v1.5 Link-97 r8 First Red check: PASS selector-state-leak")
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
        print(f"v1.5 Link-97 r8 First Red: FIRST RED: {error}")
        raise SystemExit(2)
