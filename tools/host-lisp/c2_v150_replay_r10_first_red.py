#!/usr/bin/env python3
"""Bind the consumed Link-97 r10 completion-adapter First Red."""

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
R10 = BUILD / "post-link-qualification-replay-r10"
PROFILE = R10 / "candidate-profile.json"
INTERNAL = R10 / "wplto-internal.json"
LINKED = R10 / "single-submit-linked-gates.json"
GUARD = EVIDENCE / "c2.3-v1.5.0-link97-terminal-guard-receipt.json"
PRIOR_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r9-first-red.json")
SCHEMA = EVIDENCE / (
    "c2.3-v1.5.0-link97-qualification-current-schema-rebind-receipt.json")
CONTENT = EVIDENCE / (
    "c2.3-v1.5.0-link97-three-postlink-successor-content-map-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r10-first-red.json")
ADAPTER = ROOT / "tools/host-lisp/c2_v150_replay_r10.py"
CANDIDATE = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
EXECUTION_HEAD = "e8abbecee06a6f73187b283bb1f8871ee35e1ae4"
RECORDER_HEAD = "b7ff9e8e06ca90d6695ec602bf7faeb218ea9a93"
AUTHORIZATION = "a2274c29"
FORMAT = "lisp65-c2.3-v150-link97-post-link-replay-r10-first-red-v1"
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
            f"r10 First-Red authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw), "sha256": sha_bytes(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"r10 First-Red JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"r10 First-Red object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def diagnostic() -> dict[str, Any]:
    source = r'''import json
import c2_v150_replay_r10 as r
p = r.CARD.PRODUCT
before = dict(p.PROFILE_RODATA_INPUT_SECTIONS)
p.configure_require_resolver_profile_geometry()
p.configure_defstruct_foundation_profile_geometry()
after_first = dict(p.PROFILE_RODATA_INPUT_SECTIONS)
error = None
try:
    p.configure_require_resolver_profile_geometry()
except Exception as caught:
    error = f"{type(caught).__name__}: {caught}"
print(json.dumps({"before": before, "after_first": after_first,
                  "error": error}, sort_keys=True))'''
    environment = dict(__import__("os").environ)
    environment["PYTHONPATH"] = str(ROOT / "tools/host-lisp")
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=ROOT, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def frozen_artifacts() -> dict[str, Any]:
    frozen = load(PRIOR_RED)["frozen_artifacts_after_stop"]
    for role, row in frozen.items():
        require(bind(ROOT / row["path"]) == row,
                f"frozen Link-97 artifact drift: {role}")
    return frozen


def collect() -> dict[str, Any]:
    files = sorted(path.relative_to(R10).as_posix()
                   for path in R10.rglob("*") if path.is_file())
    expected_files = [
        "c2-asm-leaf-real-abi-callers.json",
        "c2-crc-asm-leaf-workbench-gate.json",
        "candidate-profile.json",
        "single-submit-linked-gates.json",
        "wplto-internal.json",
    ]
    internal = load(INTERNAL)
    linked = load(LINKED)
    observed = diagnostic()
    require(
        files == expected_files
        and internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal["fresh_replacement_gates"]["status"] == "passed"
        and linked["status"]
            == "passed-single-submit-local-observation-and-complete-leaf-ABI"
        and observed == {
            "before": {
                ".rodata.eval_v2_workbench_service": 32,
                ".rodata.vm_callprim": 164,
                ".rodata.vm_native_call": 146,
            },
            "after_first": {
                ".rodata.eval_v2_workbench_service": 32,
                ".rodata.vm_callprim": 168,
                ".rodata.vm_native_call": 148,
            },
            "error": "ValueError: require-resolver profile selector order drift",
        }
        and not (BUILD / "final").exists()
        and not (BUILD / "canonical-product-manifest.json").exists()
        and not (EVIDENCE / "c2.3-v1.5.0-link97-product-card-receipt.json").exists()
        and not (EVIDENCE / (
            "c2.3-v1.5.0-link97-post-link-qualification-replay-receipt.json"
        )).exists(),
        "r10 completion-adapter stopped-state drift")
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
            "current_schema_closure_validated": True,
            "replacement_and_real_ABI_completed": True,
            "current_postlink_consumer_completed": True,
            "linked_gate_completed": True,
            "terminal_guard_recorded": True,
            "fresh_completion_process_started": True,
            "completion_profile_selected_once": True,
            "inherited_closer_configuration_started": True,
            "artifact_completion_started": False,
            "final_artifacts_written": False,
        },
        "mechanism": {
            "classification":
                "fresh-process-completion-adapter-double-profile-configuration",
            "failure": observed["error"],
            "selector_state": observed,
            "execution_order": {
                "1_adapter_complete":
                    "CARD.configure(REPLAY_PROFILE) selects 164/146 -> 168/148",
                "2_inherited_complete_action":
                    "L94.complete_action enters configure_card a second time",
                "3_one_shot_guard":
                    "require selector correctly rejects 168/148 as its predecessor",
            },
            "statement": (
                "The 3/3 current-schema post-link consumer, linked gate and "
                "terminal guard all completed. In the already fresh completion "
                "child, the r10 adapter selected the append-only product profile "
                "once and then called an inherited closer whose first operation "
                "selects that same profile again. The one-shot selector correctly "
                "rejected the second application before artifact completion. "
                "This is a completion-adapter lifecycle defect, not a product, "
                "geometry, freight, qualification-content or process-isolation red."
            ),
        },
        "stopped_output": {
            "files": files,
            "profile": bind(PROFILE),
            "internal": bind(INTERNAL),
            "linked_gate": bind(LINKED),
            "terminal_guard": bind(GUARD),
        },
        "diagnostic_hygiene": {
            "unbound_ephemeral_file_removed_during_first_reproduction":
                "receipts/write-completion-source-gate.json",
            "observed_bytes_before_removal": 4932,
            "sha_bound_before_removal": False,
            "claim_dependency": False,
            "frozen_product_or_authority_artifact_changed": False,
            "statement": (
                "The first desk reproduction entered the inherited configure "
                "path and removed its unbound, build-local completion-source "
                "gate while resetting that path. No SHA had been bound, so it "
                "is not reconstructed and no claim relies on it. Subsequent "
                "diagnostics exercise only the selector functions in a fresh "
                "process and do not touch the stopped output."
            ),
        },
        "frozen_artifacts_after_stop": frozen_artifacts(),
        "execution_authority": {
            "authorization_commit": AUTHORIZATION,
            "prepared_HEAD": EXECUTION_HEAD,
            "prior_first_red": git_bind(EXECUTION_HEAD, PRIOR_RED),
            "current_schema_closure": git_bind(EXECUTION_HEAD, SCHEMA),
            "three_field_content_map": git_bind(EXECUTION_HEAD, CONTENT),
            "candidate_driver": git_bind(EXECUTION_HEAD, CANDIDATE),
            "r10_adapter": git_bind(EXECUTION_HEAD, ADAPTER),
            "recorder": git_bind(RECORDER_HEAD, Path(__file__)),
        },
        "disposition": {
            "automatic_retry_authorized": False,
            "completion_or_media_authorized": False,
            "owner_question": (
                "Park, or authorize a completion-only adapter repair that lets "
                "the inherited closer own the single profile selection, followed "
                "by one resume over the frozen r10 qualification outputs?"
            ),
        },
        "claim_limit": (
            "One consumed r10 replay, green current-schema qualification through "
            "the linked gate and terminal guard, and one named completion-adapter "
            "double-configuration. No artifact completion, final product receipt, "
            "medium, device, Halt or release claim exists."
        ),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting", {}).get(
            "artifact_only_replays_consumed") == 1
        and value.get("boundary", {}).get(
            "current_postlink_consumer_completed") is True
        and value.get("boundary", {}).get("linked_gate_completed") is True
        and value.get("boundary", {}).get("artifact_completion_started") is False
        and value.get("boundary", {}).get("final_artifacts_written") is False
        and value.get("mechanism", {}).get("classification")
            == "fresh-process-completion-adapter-double-profile-configuration"
        and value.get("disposition", {}).get("automatic_retry_authorized")
            is False,
        "r10 First-Red claim drift")
    if verify:
        require(value == collect(), "r10 First-Red authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-retry": lambda x: x["disposition"].update(
            automatic_retry_authorized=True),
        "erase-postlink-green": lambda x: x["boundary"].update(
            current_postlink_consumer_completed=False),
        "erase-linked-green": lambda x: x["boundary"].update(
            linked_gate_completed=False),
        "claim-completion": lambda x: x["boundary"].update(
            artifact_completion_started=True),
        "claim-final": lambda x: x["boundary"].update(
            final_artifacts_written=True),
        "erase-consumption": lambda x: x["attempt_accounting"].update(
            artifact_only_replays_consumed=0),
        "misclassify-product": lambda x: x["mechanism"].update(
            classification="product-red"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except FirstRedError:
            rejected.append(name)
    require(rejected == list(cases), "r10 First-Red mutation survived")
    return rejected


def capture() -> int:
    require(not RECEIPT.exists(), "r10 First-Red receipt already exists")
    value = collect(); validate(value, verify=False)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 r10 First Red capture: PASS completion-double-config")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    successor = EVIDENCE / (
        "c2.3-v1.5.0-link97-post-link-qualification-replay-receipt.json")
    if successor.is_file():
        validate(value, verify=False)
        for row in value["stopped_output"].values():
            if isinstance(row, dict) and "path" in row:
                require(bind(ROOT / row["path"]) == row,
                        "r10 stopped authority changed after resume")
        frozen_artifacts()
    else:
        validate(value, verify=True)
    require(rejected == mutations(value), "r10 First-Red mutation drift")
    print("v1.5 Link-97 r10 First Red check: PASS completion-double-config")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "check"))
    return {"capture": capture, "check": check}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 r10 First Red: FAIL: {error}")
        raise SystemExit(2)
