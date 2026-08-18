#!/usr/bin/env python3
"""Run the one replacement card behind real post-link schema conformance."""

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

import c2_v21_guard_invariant_card as BASE  # noqa: E402
import c2_v21_guard_invariant_card_red_attribution as ATTR  # noqa: E402
import c2_v21_postlink_schema_contract as SCHEMA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-postlink-schema-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-postlink-schema-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-postlink-schema-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-postlink-schema-replacement-card-final-red.json"
PREDECESSOR = BASE.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "fb760d1c"
RECORDED_ON = "2026-08-14"
LINK = 107


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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
    for token in ("consumer speaks `control_flow_ownership`",
                  "every real post-link consumer schema",
                  "actual producer output", "one replacement card"):
        require(token in text, f"schema replacement authorization absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(
        red.get("status") == "FINAL RED: guard-invariant card returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("root_cause", {}).get("class") ==
            "POSTLINK-CONSUMER-SCHEMA-VOCABULARY-DRIFT",
        "schema replacement predecessor drift")
    return {"final_red": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION)}


def schema_authority() -> dict[str, Any]:
    value = load(SCHEMA.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    SCHEMA.validate(value, verify=True)
    require(rejected == {"contract": SCHEMA.contract_mutations(),
                         "receipt": SCHEMA.receipt_mutations(value)},
            "real post-link schema authority drift")
    gate = value["contract_gate"]
    return {"receipt": bind(SCHEMA.RECEIPT),
        "wrapper_count": gate["typed_path_wrappers"]["wrapper_count"],
        "schema_consumer_count": len(gate["schema_consumers"]),
        "real_consumer_execution_count": gate["real_consumer_executions"][
            "consumer_count"],
        "unknown_key_count": gate["schema_unknown_key_count"],
        "actual_producer_output": gate["real_consumer_executions"][
            "actual_producer_output"],
        "mutations_rejected": rejected}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-guard-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-guard-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    result["real_abi_report"] = bind(ABI_REPORT)
    return result


def preflight_value() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v21-postlink-schema-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: real post-link schemas green before replacement card",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"postlink_contract": schema_authority()},
        "authority": {"authorization": authorization(), **predecessor(),
                      "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "schema replacement preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "hide-schema-consumer": lambda x: x["host_gates"][
            "postlink_contract"].update(schema_consumer_count=3),
        "accept-unknown-key": lambda x: x["host_gates"][
            "postlink_contract"].update(unknown_key_count=1),
        "replace-actual-with-synthetic": lambda x: x["host_gates"][
            "postlink_contract"].update(actual_producer_output=False),
        "skip-real-consumer": lambda x: x["host_gates"][
            "postlink_contract"].update(real_consumer_execution_count=2),
        "spend-card-in-preflight": lambda x: x["attempt_accounting"].update(
            replacement_cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "schema replacement mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "schema replacement preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 schema replacement: PREFLIGHT PASS schemas=4 card=0/1")


def produce_child() -> int:
    configure()
    return BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh schema replacement child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "schema replacement preflight receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "schema replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        **predecessor(), "postlink_contract": bind(SCHEMA.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "schema replacement acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "schema replacement process isolation drift")
    transport = producer["v21_linked_transport"]
    local = producer["v21_text_recovery"]
    completion = producer["candidate_completion_identity"]
    require(
        transport["reader"]["address"] == "0x2277"
        and transport["reader"]["end_exclusive"] == "0x231d"
        and local["ownership"]["violations"] == []
        and local["status"] ==
            "PASS: local non-entries and emitted identities linked"
        and completion["status"] ==
            "PASS: publish-last consumed candidate identity"
        and acceptance.get("status") == "PASS",
        "schema replacement linked result drift")
    receipt = {
        "format": "lisp65-c2.3-v21-postlink-schema-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: post-link schema replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(), **predecessor(),
            "postlink_contract": bind(SCHEMA.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "postlink_contract": schema_authority(),
        "transport": transport, "local_return": local,
        "completion_identity": completion,
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "schema_contract": schema_authority()["mutations_rejected"]},
        "next": "completion and complete same-world media closure, then D1",
        "claim_limit": "One product card; completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 schema replacement: PASS card=1/1 schemas=4 ownership=0")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-postlink-schema-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: post-link schema replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(), **predecessor(),
            "postlink_contract": bind(SCHEMA.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Replacement card consumed; no completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "schema replacement Final Red drift")
        print("2.1 schema replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "schema replacement armed receipt drift")
        print("2.1 schema replacement: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") == "PASS: post-link schema replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["local_return"]["ownership"]["violations"] == []
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True,
        "schema replacement green receipt drift")
    print("2.1 schema replacement: CHECK PASS card=1/1 ownership=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "card", "check", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"schema replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 schema replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
