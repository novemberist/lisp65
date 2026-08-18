#!/usr/bin/env python3
"""Run the sole card behind the one-time pinned-constant sweep."""

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

import c2_v20_building_heap_attribution as HEAP  # noqa: E402
import c2_v21_local_return_identity_card as BASE  # noqa: E402
import c2_v21_pinned_constant_sweep as SWEEP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-pinned-constant-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-pinned-constant-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / "c2.3-v2.1-pinned-constant-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v2.1-local-return-identity-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-local-return-identity-card-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d615bcf4"
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
    for token in (
            "pinned-address sweep commissioned",
            "specific stage consumes the candidate address", "broaden-once",
            "stale building-heap source rebind", "one card"):
        require(token in text, f"pinned card authorization absent: {token}")
    return authority


def predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    red = load(PREDECESSOR); attribution = load(ATTRIBUTION)
    require(red.get("status") ==
                "FINAL RED: local-return-identity card returns to owner"
            and red.get("retry_authorized") is False
            and attribution.get("status") ==
                "ATTRIBUTED FINAL RED: legacy qualification stage pins verifier base"
            and attribution["new_final_red"]["implicit_expected_address"]
                == "0xb9cd"
            and attribution["new_final_red"]["candidate_address"] == "0xb98c"
            and attribution["card_disposition"]["retry_authorized"] is False,
            "pinned-address predecessor authority drift")
    return red, attribution


def sweep_authority() -> dict[str, Any]:
    value = load(SWEEP.RECEIPT)
    receipt_rejected = value.pop("receipt_mutations_rejected", None)
    SWEEP.validate(value, verify=True)
    require(receipt_rejected == SWEEP.receipt_mutations(value)
            and value["sweep"]["pinned_count"] == 0
            and value["sweep"]["expectation_count"] == 14,
            "pinned-constant sweep authority drift")
    return {"receipt": bind(SWEEP.RECEIPT), "result": value["sweep"],
            "receipt_mutations_rejected": receipt_rejected}


def heap_rebind_authority() -> dict[str, Any]:
    value = load(HEAP.LATEST_REBIND)
    require(value.get("format") ==
                "lisp65-c2.3-v20-building-heap-attribution-rebind-v2"
            and value.get("status") ==
                "PASS: second loud semantic-preserving current-source rebind"
            and value["change"]["semantic_claims_changed"] is False
            and value["change"]["historical_receipt_rewritten"] is False
            and value["claim_continuity"]["recontact_authorized"] is False,
            "BUILDING-HEAP second rebind authority drift")
    return {"receipt": bind(HEAP.LATEST_REBIND),
            "previous_rebind": value["authority"]["previous_rebind"],
            "semantic_claims_changed": False}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.RECEIPT = BUILD / "unused-local-return-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-local-return-final-red.json"
    BASE.PREDECESSOR = PREDECESSOR
    BASE.ATTRIBUTION = ATTRIBUTION
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.LINK = LINK
    BASE.authorization = authorization
    BASE.predecessor = predecessor
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v21-pinned-constant-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: constant sweep and source rebind green; card armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {"pinned_constant_sweep": sweep_authority(),
            "BUILDING_HEAP_rebind": heap_rebind_authority(),
            "local_identity_source": BASE.selector_source_gate(),
            "actual_ownership_consumer": BASE.real_consumer_preflight()},
        "placement_inherited_green": {"resident_reserve_bytes": 24,
            "cold_helper_bytes": 63, "image_growth_bytes": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "driver": bind(DRIVER)},
        "claim_limit": "Host preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "pinned-constant card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "hide-pinned-constant": lambda x: x["host_gates"]
            ["pinned_constant_sweep"]["result"].update(pinned_count=1),
        "detach-source-rebind": lambda x: x["host_gates"]
            ["BUILDING_HEAP_rebind"].update(semantic_claims_changed=True),
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
    require(rejected == list(cases), "pinned card preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "pinned-constant preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 pinned-constant card: PREFLIGHT PASS expectations=14 "
          "pinned=0 card=0/1")


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
            f"fresh pinned-constant child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "pinned card preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "pinned-constant replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        "predecessor": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION),
        "sweep": bind(SWEEP.RECEIPT), "heap_rebind": bind(HEAP.LATEST_REBIND),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "pinned-constant acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "pinned-constant process isolation drift")
    linked = producer["v21_text_recovery"]
    BASE.validate_linked(linked)
    candidate = producer["candidate_completion_identity"]
    require(candidate["address"] == 0xB98C
            and producer["candidate_completion_mutations"] ==
                ["reject-historical-0xb98a"]
            and producer["v21_text_recovery_mutations"] ==
                BASE.linked_mutations(linked),
            "linked candidate identity or mutation receipt drift")
    receipt = {
        "format": "lisp65-c2.3-v21-pinned-constant-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole pinned-constant replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"authorization": authorization(),
            "predecessor_final_red": bind(PREDECESSOR),
            "attribution": bind(ATTRIBUTION), "sweep": bind(SWEEP.RECEIPT),
            "BUILDING_HEAP_rebind": bind(HEAP.LATEST_REBIND),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_result": linked,
        "completion_identity": candidate,
        "qualification_constants": {"expectations": 14, "pinned": 0,
            "candidate_verifier_address": "0xb98c"},
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
        "claim_limit": "One card; media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 pinned-constant card: PASS card=1/1 address=b98c "
          "reserve=24 pinned=0")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-pinned-constant-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: sole pinned-constant card returns to owner",
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
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}}))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "pinned-constant Final Red drift")
        print("2.1 pinned-constant card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "pinned preflight receipt drift")
        print("2.1 pinned-constant card: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") ==
                "PASS: sole pinned-constant replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["qualification_constants"] == {
                "expectations": 14, "pinned": 0,
                "candidate_verifier_address": "0xb98c"}
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"],
            "pinned-constant green receipt drift")
    BASE.validate_linked(value["linked_result"])
    print("2.1 pinned-constant card: CHECK PASS card=1/1 pinned=0")


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
                print(f"pinned Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 pinned-constant card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
