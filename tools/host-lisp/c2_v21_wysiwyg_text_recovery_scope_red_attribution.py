#!/usr/bin/env python3
"""Attribute the Link-116 artifact-continuation Scope First Red."""

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
    "c2.3-v2.1-wysiwyg-text-recovery-scope-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
STATUS = "ATTRIBUTED: LINK-116 SCOPE ADAPTER OMITTED ACCEPTED SUCCESSOR"


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
    preflight = load(REPLAY.PREFLIGHT)
    producer = load(REPLAY.PRODUCER_RESULT)
    current = REPLAY.frozen_artifacts()
    require(preflight["frozen_artifacts"] == current
            and not REPLAY.SCOPE_RESULT.exists()
            and not REPLAY.ACCEPTANCE_RESULT.exists()
            and not REPLAY.RECEIPT.exists(),
            "Scope First-Red lifecycle/frozen artifact drift")
    projection = producer["post_configuration_source_owner_gate"]
    rows = {row["name"]: row for row in projection["scopes"]}
    candidate = rows["mapped-far-content-convergence"]
    require(candidate["sources"] == [
                "src/optional/c2_mapped_far_convergence_full_span.s",
                "src/optional/c2_mapped_far_facade_padding.s",
                "src/optional/c2_mapped_far_service_v2.s"]
            and candidate["selected"] is True,
            "candidate source-owner projection is not complete")
    REPLAY.configure()
    successor = REPLAY.FULL_SPAN.successor_scope_gate(projection)
    identity = successor["successor_identity"]
    require(identity["sources"] == candidate["sources"]
            and identity["defines"] == candidate["defines"],
            "repaired Scope adapter does not consume candidate identity")
    historical = Path(
        REPLAY.FULL_SPAN.CARD.MAP_FIX.__file__).read_text(encoding="utf-8")
    require('"src/c2_mapped_far_convergence.s"' in historical
            and "corrected trampoline escaped source-owner scope" in historical,
            "historical MAP Scope pin not found")
    before_driver = preflight["authority"]["driver"]
    after_driver = bind(REPLAY.DRIVER)
    return {
        "format": "lisp65-c2.3-v2.1-wysiwyg-link116-scope-red-v1",
        "recorded_on": "2026-08-17", "status": STATUS,
        "classification": {
            "product_failure": False, "freight_failure": False,
            "checker_semantics_new": False, "adapter_failure": True,
            "mechanism": (
                "The new Link-116 replay installed the historical Phase-9 "
                "successors instead of the already-accepted full-span "
                "Scope/Acceptance successors. The historical Scope therefore "
                "compared the current projection with an old body name."),
        },
        "attempt_accounting": {"artifact_replays_authorized": 1,
            "scope_attempts": 1, "scope_completions": 0,
            "acceptance_attempts": 0, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "candidate_projection": candidate,
        "historical_consumer": {
            "expected_body": "src/c2_mapped_far_convergence.s",
            "error": "corrected trampoline escaped source-owner scope"},
        "repaired_adapter_preflight": {
            "accepted_successor":
                "c2_v21_full_span_projection_artifact_replay",
            "candidate_identity_consumed": identity,
            "desk_result": "PASS",
            "scope_or_acceptance_executed": False},
        "frozen_artifacts_before": current,
        "frozen_artifacts_after": REPLAY.frozen_artifacts(),
        "authority": {"owner": REPLAY.authorization(),
            "preflight": bind(REPLAY.PREFLIGHT),
            "producer_tail": bind(REPLAY.PRODUCER_RESULT),
            "driver_before_scope": before_driver,
            "driver_after_adapter_repair": after_driver,
            "checker": bind(DRIVER)},
        "disposition_boundary": {
            "resume_authorized": False,
            "narrowest_resume": (
                "loud driver-only preflight rebind, then one fresh Scope and "
                "Acceptance over the same frozen Link-116 SHAs"),
            "relink_allowed": False, "completion_allowed": False,
            "media_allowed": False},
        "claim_limit": (
            "Read-only attribution and adapter desk-preflight only; no retry."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["classification"] == {
                "product_failure": False, "freight_failure": False,
                "checker_semantics_new": False, "adapter_failure": True,
                "mechanism": value["classification"]["mechanism"]}
            and value["attempt_accounting"]["scope_attempts"] == 1
            and value["attempt_accounting"]["acceptance_attempts"] == 0
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_links"] == 0
            and value["frozen_artifacts_before"] ==
                value["frozen_artifacts_after"]
            and value["repaired_adapter_preflight"]["desk_result"] == "PASS"
            and value["disposition_boundary"]["resume_authorized"] is False
            and value["disposition_boundary"]["relink_allowed"] is False,
            "Scope-red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "blame-product": lambda x: x["classification"].update(
            product_failure=True),
        "blame-freight": lambda x: x["classification"].update(
            freight_failure=True),
        "claim-new-semantics": lambda x: x["classification"].update(
            checker_semantics_new=True),
        "hide-scope-attempt": lambda x: x["attempt_accounting"].update(
            scope_attempts=0),
        "invent-acceptance": lambda x: x["attempt_accounting"].update(
            acceptance_attempts=1),
        "invent-link": lambda x: x["attempt_accounting"].update(
            product_links=1),
        "change-artifact": lambda x: x["frozen_artifacts_after"].pop("map"),
        "self-authorize-resume": lambda x: x["disposition_boundary"].update(
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
    require(rejected == list(cases), "Scope-red attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        value["mutations_rejected"] = mutations(value)
        require(not RECEIPT.exists(), "Scope-red attribution is one-shot")
        RECEIPT.write_bytes(canonical(value))
    else:
        # Historical evidence witnesses the driver that actually produced the
        # Scope Red.  The authorized driver-only rebind must not turn the live
        # successor back into a predicate on that historical world.
        value = load(RECEIPT)
        rejected = value.pop("mutations_rejected", None)
        validate(value)
        require(rejected == mutations(value)
                and value["frozen_artifacts_after"] == REPLAY.frozen_artifacts(),
                "historical Scope-red receipt/frozen artifacts drift")
    print("WYSIWYG Link-116 Scope Red: ATTRIBUTED adapter=yes mutations=8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"WYSIWYG Link-116 Scope Red: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
