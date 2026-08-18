#!/usr/bin/env python3
"""Run the sole card behind the Workbench capacity-domain conversion."""

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

import c2_v20_map_tuple_fixture_scope_rebind_20260814 as MAP_REBIND  # noqa: E402
import c2_v21_pinned_constant_card as PREV  # noqa: E402
import c2_v21_workbench_capacity_domain as DOMAIN  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-workbench-capacity-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-workbench-capacity-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-workbench-capacity-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-workbench-capacity-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-pinned-constant-card-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b3f6adc2"
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
    for token in ("checker conversion approved", "named domain",
                  "one card", "map-tuple fixture red"):
        require(token in text, f"Workbench capacity card authorization absent: {token}")
    return authority


def predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    red = load(PREDECESSOR); attribution = load(ATTRIBUTION)
    require(
        red.get("status") == "FINAL RED: sole pinned-constant card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and attribution.get("status") ==
            "ATTRIBUTED FINAL RED: transitive F1 helper pins overlay-size ceiling"
        and attribution["new_final_red"]["actual_workbench_overlay_bytes"] == 1851
        and attribution["new_final_red"]["historical_ceiling_bytes"] == 1792
        and attribution["card_disposition"]["retry_authorized"] is False,
        "Workbench capacity predecessor authority drift",
    )
    return red, attribution


def domain_authority() -> dict[str, Any]:
    value = load(DOMAIN.RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    DOMAIN.validate(value, verify=True)
    require(rejected == DOMAIN.receipt_mutations(value)
            and value["disposition"]["cards_authorized"] == 1
            and value["disposition"]["cards_consumed"] == 0,
            "Workbench capacity-domain authority drift")
    return {"receipt": bind(DOMAIN.RECEIPT),
            "arena": value["conversion"]["arena"],
            "capacity_bytes": value["conversion"]["capacity_bytes"],
            "candidate_bytes": value["terminal_consumer_replay"]
                ["candidate_workbench_bytes"],
            "headroom_bytes": value["terminal_consumer_replay"]
                ["headroom_bytes"]}


def map_rebind_authority() -> dict[str, Any]:
    value = load(MAP_REBIND.RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    MAP_REBIND.validate(value, verify=True)
    require(rejected == MAP_REBIND.receipt_mutations(value)
            and value["current_gate"]["selected_successor_copies"] == 1,
            "MAP-tuple fixture rebind authority drift")
    return {"receipt": bind(MAP_REBIND.RECEIPT),
            "selected_owner": value["current_gate"]["selected_owner"],
            "unrelated_scope_count": value["change"]["unrelated_scope_count"]}


def configure() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PREV.INVOCATION = INVOCATION
    PREV.PRODUCER_RESULT = PRODUCER_RESULT
    PREV.SCOPE_RESULT = SCOPE_RESULT
    PREV.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PREV.RECEIPT = BUILD / "unused-pinned-card-receipt.json"
    PREV.FINAL_RED = BUILD / "unused-pinned-card-final-red.json"
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
    return result


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v21-workbench-capacity-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: correct-domain F1 consumer and MAP rebind green; card armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"capacity_domain": domain_authority(),
            "MAP_tuple_fixture_rebind": map_rebind_authority(),
            "pinned_constant_sweep": PREV.sweep_authority(),
            "BUILDING_HEAP_rebind": PREV.heap_rebind_authority(),
            "actual_ownership_consumer": PREV.BASE.real_consumer_preflight()},
        "placement_inherited_green": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": 63, "image_growth_bytes": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "Workbench capacity card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "cross-domain-capacity": lambda x: x["host_gates"]
            ["capacity_domain"].update(arena="runtime-overlay-slices"),
        "erase-headroom": lambda x: x["host_gates"]
            ["capacity_domain"].update(headroom_bytes=0),
        "restore-MAP-cardinality-pin": lambda x: x["host_gates"]
            ["MAP_tuple_fixture_rebind"].update(unrelated_scope_count=0),
        "lose-resident-reserve": lambda x: x["placement_inherited_green"].update(
            resident_reserve_bytes=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "Workbench card preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "Workbench capacity preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 Workbench capacity card: PREFLIGHT PASS arena=2730 "
          "headroom=879 card=0/1")


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
            f"fresh Workbench capacity child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "Workbench card preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "Workbench capacity replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION),
        "capacity_domain": bind(DOMAIN.RECEIPT),
        "MAP_tuple_rebind": bind(MAP_REBIND.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "Workbench capacity acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "Workbench capacity process isolation drift")
    linked = producer["v21_text_recovery"]
    PREV.BASE.validate_linked(linked)
    candidate = producer["candidate_completion_identity"]
    require(candidate["address"] == 0xB98C
            and producer["candidate_completion_mutations"] ==
                ["reject-historical-0xb98a"]
            and producer["v21_text_recovery_mutations"] ==
                PREV.BASE.linked_mutations(linked),
            "Workbench card linked identity/mutation drift")
    domain = domain_authority()
    receipt = {
        "format": "lisp65-c2.3-v21-workbench-capacity-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole Workbench capacity-domain replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION),
            "capacity_domain": bind(DOMAIN.RECEIPT),
            "MAP_tuple_rebind": bind(MAP_REBIND.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "capacity_acceptance": domain,
        "linked_result": linked,
        "completion_identity": candidate,
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
    print("2.1 Workbench capacity card: PASS card=1/1 arena=2730 "
          "headroom=879 reserve=24")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-workbench-capacity-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: sole Workbench capacity card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(),
            "predecessor": bind(PREDECESSOR),
            "capacity_domain": bind(DOMAIN.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "Workbench capacity Final Red drift")
        print("2.1 Workbench capacity card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "Workbench preflight receipt drift")
        print("2.1 Workbench capacity card: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") ==
                "PASS: sole Workbench capacity-domain replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["capacity_acceptance"] == domain_authority()
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"],
            "Workbench capacity green receipt drift")
    PREV.BASE.validate_linked(value["linked_result"])
    print("2.1 Workbench capacity card: CHECK PASS card=1/1 arena=2730")


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
                print(f"Workbench capacity Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 Workbench capacity card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
