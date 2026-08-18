#!/usr/bin/env python3
"""Run the one replacement card behind post-link contract conformance."""

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

import c2_v21_expectation_shape_card as BASE  # noqa: E402
import c2_v21_expectation_shape_card_red_attribution as ATTR  # noqa: E402
import c2_v21_postlink_wrapper_contract as CONTRACT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-wrapper-contract-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-wrapper-contract-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-wrapper-contract-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-wrapper-contract-replacement-card-final-red.json"
PREDECESSOR = BASE.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "34e92a14"
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
    for token in ("all three wrappers normalize", "conformance preflight",
                  "a card is a product experiment", "one replacement card"):
        require(token in text, f"wrapper replacement authorization absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(
        red.get("status") ==
            "FINAL RED: sole expectation-shape card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("attempt_accounting", {}).get("WPLTO_runs") == 1
        and attribution.get("root_cause", {}).get("class") ==
            "ARTIFACT-ROLE-VOCABULARY-CASE-MISMATCH"
        and attribution.get("card_disposition", {}).get("retry_authorized") is False,
        "wrapper replacement predecessor authority drift")
    return {"final_red": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION)}


def contract_authority() -> dict[str, Any]:
    value = load(CONTRACT.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    CONTRACT.validate(value, verify=True)
    require(rejected == {"contract": CONTRACT.mutations(),
                         "receipt": CONTRACT.receipt_mutations(value)}
            and value["contract_gate"]["wrapper_count"] == 3
            and value["execution_accounting"]["WPLTO_runs"] == 0,
            "post-link wrapper conformance authority drift")
    return {"receipt": bind(CONTRACT.RECEIPT),
            "producer_roles": value["contract_gate"]["producer_roles"],
            "wrapper_count": value["contract_gate"]["wrapper_count"],
            "contract_mutations_rejected": rejected["contract"]}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-expectation-shape-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-expectation-shape-final-red.json"
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
        "format": "lisp65-c2.3-v21-wrapper-contract-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: wrapper plumbing green before replacement card",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"wrapper_contract": contract_authority(),
            "expectation_shape_sweep": BASE.sweep_authority(),
            "actual_ownership_consumer": BASE.PREV.PREV.BASE.real_consumer_preflight()},
        "authority": {"authorization": authorization(), **predecessor(),
                      "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "wrapper replacement preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "hide-wrapper": lambda x: x["host_gates"]["wrapper_contract"].update(
            wrapper_count=2),
        "accept-uppercase-role": lambda x: x["host_gates"]["wrapper_contract"]
            ["producer_roles"].__setitem__(0, "ELF"),
        "spend-card-in-preflight": lambda x: x["attempt_accounting"].update(
            replacement_cards_consumed=1),
        "run-WPLTO-in-preflight": lambda x: x["attempt_accounting"].update(
            WPLTO_runs=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "wrapper replacement mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "wrapper replacement preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 wrapper replacement: PREFLIGHT PASS wrappers=3 card=0/1")


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
            f"fresh wrapper replacement child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "wrapper replacement preflight receipt drift")
    require(not BUILD.exists() and INVOCATION.parent == PREFLIGHT
            and not INVOCATION.exists() and not RECEIPT.exists()
            and not FINAL_RED.exists(), "wrapper replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        **predecessor(), "wrapper_contract": bind(CONTRACT.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "wrapper replacement acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "wrapper replacement process isolation drift")
    linked = producer["v21_text_recovery"]
    BASE.PREV.PREV.BASE.validate_linked(linked)
    completion = producer["candidate_completion_identity"]
    abi = BASE.candidate_classification()
    require(completion["address"] == 0xB98C
            and producer["candidate_completion_mutations"] ==
                ["reject-historical-0xb98a"]
            and producer["v21_text_recovery_mutations"] ==
                BASE.PREV.PREV.BASE.linked_mutations(linked)
            and acceptance.get("status") == "PASS"
            and abi["all_callers_classified"] is True
            and abi["classified_callsite_count"] == abi["callsite_count"] == 10,
            "wrapper replacement linked result drift")
    receipt = {
        "format": "lisp65-c2.3-v21-wrapper-contract-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: wrapper-contract replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(), **predecessor(),
            "wrapper_contract": bind(CONTRACT.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "wrapper_contract": contract_authority(),
        "linked_result": linked, "completion_identity": completion,
        "classification": abi,
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "linked": producer["v21_text_recovery_mutations"],
            "completion": producer["candidate_completion_mutations"]},
        "next": "completion and same-world media closure, then D1",
        "claim_limit": "One card; completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 wrapper replacement: PASS card=1/1 wrappers=3 callers=10")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-wrapper-contract-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: wrapper-contract replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(), **predecessor(),
            "wrapper_contract": bind(CONTRACT.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Replacement card consumed; no completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "wrapper replacement Final Red drift")
        print("2.1 wrapper replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "wrapper replacement armed receipt drift")
        print("2.1 wrapper replacement: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") ==
            "PASS: wrapper-contract replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["wrapper_contract"]["wrapper_count"] == 3
            and value["classification"]["all_callers_classified"] is True
            and value["classification"]["callsite_count"] == 10
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"],
            "wrapper replacement green receipt drift")
    BASE.PREV.PREV.BASE.validate_linked(value["linked_result"])
    print("2.1 wrapper replacement: CHECK PASS card=1/1 wrappers=3")


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
                print(f"wrapper replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 wrapper replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
