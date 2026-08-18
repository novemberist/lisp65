#!/usr/bin/env python3
"""Run the one card behind the linked CPU-reader guard correction."""

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

import c2_v21_cpu_transport_card as CPU  # noqa: E402
import c2_v21_guard_invariant as GUARD  # noqa: E402
import c2_v21_postlink_wrapper_contract as WRAPPERS  # noqa: E402
import c2_v21_wrapper_contract_replacement_card as BASE  # noqa: E402
import c2_v21_wrapper_contract_replacement_red_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-guard-invariant-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-guard-invariant-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-guard-invariant-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-guard-invariant-card-final-red.json"
PREDECESSOR = BASE.FINAL_RED
ATTRIBUTION = ATTR.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "32ce1bc8"
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
    for token in ("reader span must not overlap", "$2277", "$5000",
                  "one card"):
        require(token in text, f"guard card authorization absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(
        red.get("status") ==
            "FINAL RED: wrapper-contract replacement returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("root_cause", {}).get("class") ==
            "LINKED-GUARD-PINS-READER-TO-WRONG-ADDRESS-DOMAIN"
        and attribution.get("card_disposition", {}).get("retry_authorized") is False,
        "guard card predecessor authority drift")
    return {"final_red": bind(PREDECESSOR), "attribution": bind(ATTRIBUTION)}


def guard_authority() -> dict[str, Any]:
    value = load(GUARD.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    GUARD.validate(value, verify=True)
    require(rejected == GUARD.mutations(value),
            "guard-invariant mutation authority drift")
    return {"receipt": bind(GUARD.RECEIPT),
            "positive": value["controls"]["positive_accepted"],
            "negative_rejected": value["controls"]["negative_rejected"],
            "real_ELF_reader": value["real_ELF_gate"]["reader"]}


def wrapper_authority() -> dict[str, Any]:
    gate = WRAPPERS.gate()
    rejected = WRAPPERS.mutations()
    require(gate["wrapper_count"] == 3 and gate["WPLTO_runs"] == 0
            and len(rejected) == 7,
            "live post-link wrapper conformance drift")
    return {"live_gate": gate, "mutations_rejected": rejected}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-wrapper-replacement-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-wrapper-replacement-final-red.json"
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
        "format": "lisp65-c2.3-v21-guard-invariant-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: real guard invariant green before one card",
        "configuration": {"link": LINK, "cards_authorized": 1},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "host_gates": {"guard_invariant": guard_authority(),
                       "postlink_wrappers": wrapper_authority()},
        "authority": {"authorization": authorization(), **predecessor(),
                      "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "guard card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "reject-0x2277": lambda x: x["host_gates"]["guard_invariant"].update(
            positive=None),
        "accept-0x5000": lambda x: x["host_gates"]["guard_invariant"].update(
            negative_rejected=[]),
        "hide-wrapper": lambda x: x["host_gates"]["postlink_wrappers"]
            ["live_gate"].update(wrapper_count=2),
        "spend-card-in-preflight": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "guard card preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "guard-invariant preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 guard card: PREFLIGHT PASS reader=2277 card=0/1")


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
            f"fresh guard-invariant child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "guard card preflight receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "guard-invariant card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "authorization": authorization(),
        **predecessor(), "guard_invariant": bind(GUARD.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "guard card acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "guard card process isolation drift")
    gate = producer["v21_linked_transport"]
    require(
        gate["reader"]["address"] == "0x2277"
        and gate["reader"]["end_exclusive"] == "0x231d"
        and producer["v21_linked_mutations"] == CPU.linked_mutations(gate)
        and "reader-inside-window" in producer["v21_linked_mutations"]
        and acceptance.get("status") == "PASS",
        "guard card linked result drift")
    receipt = {
        "format": "lisp65-c2.3-v21-guard-invariant-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: guard-invariant product card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"authorization": authorization(), **predecessor(),
            "guard_invariant": bind(GUARD.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "transport": gate,
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "linked": producer["v21_linked_mutations"]},
        "next": "completion and complete same-world media closure, then D1",
        "claim_limit": "One product card; completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 guard card: PASS card=1/1 reader=2277 window=4000..5fff")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-guard-invariant-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: guard-invariant card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"authorization": authorization(), **predecessor(),
            "guard_invariant": bind(GUARD.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Card consumed; no completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "guard card Final Red drift")
        print("2.1 guard card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "guard card armed receipt drift")
        print("2.1 guard card: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") == "PASS: guard-invariant product card green"
        and value["attempt_accounting"]["cards_consumed"] == 1
        and value["transport"]["reader"]["address"] == "0x2277"
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True,
        "guard card green receipt drift")
    print("2.1 guard card: CHECK PASS card=1/1 reader=2277")


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
                print(f"guard card Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 guard card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
