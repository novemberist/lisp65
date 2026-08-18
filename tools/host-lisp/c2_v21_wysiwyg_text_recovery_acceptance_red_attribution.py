#!/usr/bin/env python3
"""Attribute the Link-116 artifact-continuation Acceptance-tail First Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_wysiwyg_text_recovery_artifact_replay as REPLAY  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.1-wysiwyg-text-recovery-acceptance-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
STATUS = "ATTRIBUTED: GREEN ACCEPTANCE OUTPUT; HISTORICAL 413-BYTE TAIL PIN"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def derive() -> dict[str, Any]:
    scope = load(REPLAY.SCOPE_RESULT)
    acceptance = load(REPLAY.ACCEPTANCE_RESULT)
    current = REPLAY.frozen_artifacts()
    comparison = acceptance["VMA_golden"]
    capacity = comparison["mapped_far_service_capacity"]
    far = acceptance["far_payload"]
    tuple_far = acceptance["linked_MAP_tuple"]["far_service"]
    require(scope["status"] == "PASS" and acceptance["status"] == "PASS"
            and comparison["dependent_fixed_vmas"] == 101
            and comparison["dependent_free_derived_vmas"] == 2
            and capacity["candidate_headroom_bytes"] == 251
            and far["candidate_derived_bytes"] == 1248
            and far["candidate_headroom_bytes"] == 251
            and far["arena_capacity_bytes"] == 1499
            and tuple_far["candidate_derived_bytes"] == 1248
            and tuple_far["candidate_headroom_bytes"] == 251
            and tuple_far["arena_capacity_bytes"] == 1499,
            "persisted Acceptance result is not candidate-green")
    headroom = REPLAY.FULL_SPAN.freight_headroom_gate(acceptance)
    require(headroom["candidate"] == {
                "end_exclusive": 32146, "bytes": 1248,
                "headroom_bytes": 251},
            "candidate-derived outer tail is not green")
    old_source = Path(
        REPLAY.PHASE9_RESUME.PREV.__file__).read_text(encoding="utf-8")
    require('"candidate_headroom_bytes") == 413' in old_source,
            "historical 413-byte Acceptance-tail pin absent")
    return {
        "format": "lisp65-c2.3-v2.1-wysiwyg-link116-acceptance-red-v1",
        "recorded_on": "2026-08-17", "status": STATUS,
        "classification": {
            "product_failure": False, "scope_failure": False,
            "acceptance_body_failure": False,
            "post_acceptance_consumer_failure": True,
            "mechanism": (
                "The fresh Acceptance wrote a complete PASS result with the "
                "candidate-derived 1248/1499-byte service and 251-byte "
                "headroom. Its inherited outer wrapper then required the "
                "historical pre-growth headroom 413 and returned red."),
        },
        "attempt_accounting": {"scope_attempts": 1,
            "scope_completions": 1, "acceptance_attempts": 1,
            "acceptance_outputs_written": 1,
            "qualification_tail_completions": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "persisted_scope": {"status": scope["status"], "pid": scope["pid"],
                            "receipt": bind(REPLAY.SCOPE_RESULT)},
        "persisted_acceptance": {
            "status": acceptance["status"], "pid": acceptance["pid"],
            "receipt": bind(REPLAY.ACCEPTANCE_RESULT),
            "fixed_vmas": 101, "derived_vmas": 2,
            "far_service_bytes": 1248, "far_service_capacity_bytes": 1499,
            "candidate_headroom_bytes": 251},
        "historical_tail": {
            "pinned_headroom_bytes": 413,
            "candidate_headroom_bytes": 251,
            "error": "acceptance did not consume reviewed freight-boundary Golden"},
        "candidate_derived_tail": headroom,
        "frozen_artifacts_before": current,
        "frozen_artifacts_after": REPLAY.frozen_artifacts(),
        "authority": {"owner": REPLAY.authorization(),
            "resume_owner": REPLAY.resume_authorization(),
            "preflight": bind(REPLAY.PREFLIGHT),
            "Scope": bind(REPLAY.SCOPE_RESULT),
            "Acceptance": bind(REPLAY.ACCEPTANCE_RESULT),
            "replay_driver": bind(REPLAY.DRIVER), "checker": bind(DRIVER)},
        "disposition_boundary": {
            "resume_authorized": False,
            "narrowest_resume": (
                "read-only qualification-tail validation over the persisted "
                "green Scope and Acceptance; no fresh Scope or Acceptance"),
            "relink_allowed": False, "completion_allowed": False,
            "media_allowed": False},
        "claim_limit": (
            "Read-only attribution only; persisted Acceptance is not promoted."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["classification"]["product_failure"] is False
            and value["classification"]["scope_failure"] is False
            and value["classification"]["acceptance_body_failure"] is False
            and value["classification"][
                "post_acceptance_consumer_failure"] is True
            and value["attempt_accounting"]["scope_completions"] == 1
            and value["attempt_accounting"]["acceptance_attempts"] == 1
            and value["attempt_accounting"][
                "acceptance_outputs_written"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["persisted_acceptance"]["status"] == "PASS"
            and value["persisted_acceptance"][
                "candidate_headroom_bytes"] == 251
            and value["historical_tail"]["pinned_headroom_bytes"] == 413
            and value["frozen_artifacts_before"] ==
                value["frozen_artifacts_after"]
            and value["disposition_boundary"]["resume_authorized"] is False,
            "Acceptance-red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "blame-product": lambda x: x["classification"].update(
            product_failure=True),
        "blame-Acceptance-body": lambda x: x["classification"].update(
            acceptance_body_failure=True),
        "hide-Acceptance-attempt": lambda x: x["attempt_accounting"].update(
            acceptance_attempts=0),
        "hide-green-output": lambda x: x["persisted_acceptance"].update(
            status="RED"),
        "restore-413-as-candidate": lambda x: x["persisted_acceptance"].update(
            candidate_headroom_bytes=413),
        "hide-old-pin": lambda x: x["historical_tail"].update(
            pinned_headroom_bytes=251),
        "change-artifact": lambda x: x["frozen_artifacts_after"].pop("map"),
        "self-authorize-tail": lambda x: x["disposition_boundary"].update(
            resume_authorized=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Acceptance-red mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        require(not RECEIPT.exists(), "Acceptance-red attribution is one-shot")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(load(RECEIPT) == value,
                "Acceptance-red attribution receipt stale")
    print("WYSIWYG Link-116 Acceptance Red: ATTRIBUTED tail-pin=413 current=251")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"WYSIWYG Link-116 Acceptance Red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
