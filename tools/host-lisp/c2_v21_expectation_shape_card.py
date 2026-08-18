#!/usr/bin/env python3
"""Run the sole card behind the candidate expectation-shape sweep."""

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

import c2_v21_expectation_shape_sweep as SWEEP  # noqa: E402
import c2_lite_canonical_product as CAN  # noqa: E402
import c2_v21_workbench_capacity_card as PREV  # noqa: E402
import c2_v21_workbench_capacity_card_red_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-expectation-shape-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-expectation-shape-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-expectation-shape-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-expectation-shape-card-final-red.json"
PREDECESSOR = PREV.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "c54a062d"
RECORDED_ON = "2026-08-14"
LINK = 107


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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
    for token in ("counted expectation to a", "expected-set shape",
                  "any expectation enumerating or counting", "one card"):
        require(token in text, f"expectation-shape card authority absent: {token}")
    return authority


def predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    require(
        red.get("status") ==
            "FINAL RED: sole Workbench capacity card returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("status") ==
            "ATTRIBUTED FINAL RED: Real-ABI expected inventory omits current ELF caller"
        and attribution["new_final_red"]["actual_callsite_count"] == 10
        and attribution["new_final_red"]["expected_callsite_count"] == 9
        and attribution["new_final_red"]["added_current_ELF_owners"] == {
            "c2_phase02a_record_read": 1}
        and attribution["card_disposition"]["retry_authorized"] is False,
        "expectation-shape predecessor authority drift")
    return red, attribution


def sweep_authority() -> dict[str, Any]:
    value = load(SWEEP.RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    SWEEP.validate(value, verify=True)
    require(rejected == SWEEP.receipt_mutations(value)
            and value["sweep"]["pinned_candidate_shape_count"] == 0
            and value["disposition"]["cards_consumed"] == 0,
            "expectation-shape sweep authority drift")
    return {"receipt": bind(SWEEP.RECEIPT), "result": value["sweep"],
            "classifier_cases": value["classifier_cases"],
            "receipt_mutations_rejected": rejected}


def configure() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PREV.INVOCATION = INVOCATION
    PREV.PRODUCER_RESULT = PRODUCER_RESULT
    PREV.SCOPE_RESULT = SCOPE_RESULT
    PREV.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PREV.RECEIPT = BUILD / "unused-workbench-capacity-card-receipt.json"
    PREV.FINAL_RED = BUILD / "unused-workbench-capacity-card-final-red.json"
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.authorization = authorization
    PREV.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return PREV.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    result["real_abi_report"] = bind(ABI_REPORT)
    return result


def candidate_classification() -> dict[str, Any]:
    report = load(ABI_REPORT)
    require(
        report.get("status") == "passed-all-assembler-leaf-abi-contracts",
        "candidate real-ABI report is not green")
    callers = report["rtov_crc_mem_callers"]
    classification = CAN.classify_rtov_crc_callers(callers)
    require(
        classification["all_callers_classified"] is True
        and classification["candidate_derived_callsite_count"] ==
            callers["callsite_count"],
        "candidate real-ABI caller classification drift")
    return {
        "status": report["status"],
        "callsite_count": callers["callsite_count"],
        "classified_callsite_count":
            classification["candidate_derived_callsite_count"],
        "all_callers_classified": classification["all_callers_classified"],
        "classification_rule": classification["rule"],
        "owners": sorted(row["owner"] for row in callers["callers"]),
        "report": bind(ABI_REPORT),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    sweep = sweep_authority()
    return {
        "format": "lisp65-c2.3-v21-expectation-shape-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: caller classification and shape sweep green; card armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"expectation_shape_sweep": sweep,
            "capacity_domain": PREV.domain_authority(),
            "MAP_tuple_fixture_rebind": PREV.map_rebind_authority(),
            "actual_ownership_consumer":
                PREV.PREV.BASE.real_consumer_preflight()},
        "placement_inherited_green": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": 63, "image_growth_bytes": 0,
            "workbench_headroom_bytes": 879},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "expectation-shape card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "hide-pinned-shape": lambda x: x["host_gates"]
            ["expectation_shape_sweep"]["result"].update(
                pinned_candidate_shape_count=1),
        "pin-one-accepted-count": lambda x: x["host_gates"]
            ["expectation_shape_sweep"]["classifier_cases"].update(
                accepted_candidate_counts=[10]),
        "erase-capacity-headroom": lambda x: x["placement_inherited_green"]
            .update(workbench_headroom_bytes=0),
        "allow-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "expectation-shape card preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "expectation-shape preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 expectation-shape card: PREFLIGHT PASS pinned=0 card=0/1")


def produce_child() -> int:
    configure()
    return PREV.produce_child()


def scope_child() -> int:
    configure()
    return PREV.scope_child()


def acceptance_child() -> int:
    configure()
    return PREV.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh expectation-shape child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "expectation-shape preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "expectation-shape replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION),
        "sweep": bind(SWEEP.RECEIPT), "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "expectation-shape acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "expectation-shape process isolation drift")
    linked = producer["v21_text_recovery"]
    PREV.PREV.BASE.validate_linked(linked)
    candidate = producer["candidate_completion_identity"]
    abi = candidate_classification()
    require(candidate["address"] == 0xB98C
            and producer["candidate_completion_mutations"] ==
                ["reject-historical-0xb98a"]
            and producer["v21_text_recovery_mutations"] ==
                PREV.PREV.BASE.linked_mutations(linked)
            and acceptance.get("status") == "PASS"
            and abi["all_callers_classified"] is True
            and abi["classified_callsite_count"] == abi["callsite_count"],
            "linked candidate or classified ABI result drift")
    receipt = {
        "format": "lisp65-c2.3-v21-expectation-shape-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole expectation-shape replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "sweep": bind(SWEEP.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_result": linked, "completion_identity": candidate,
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
    print("2.1 expectation-shape card: PASS card=1/1 callers="
          f"{abi['callsite_count']} classified=all reserve=24")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-expectation-shape-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: sole expectation-shape card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(),
            "predecessor": bind(PREDECESSOR), "sweep": bind(SWEEP.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "expectation-shape Final Red drift")
        print("2.1 expectation-shape card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "expectation-shape preflight receipt drift")
        print("2.1 expectation-shape card: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") ==
            "PASS: sole expectation-shape replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["classification"]["all_callers_classified"] is True
        and value["classification"]["classified_callsite_count"] ==
            value["classification"]["callsite_count"]
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"],
        "expectation-shape green receipt drift")
    PREV.PREV.BASE.validate_linked(value["linked_result"])
    print("2.1 expectation-shape card: CHECK PASS card=1/1 classified=all")


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
                print(f"expectation-shape Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 expectation-shape card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
