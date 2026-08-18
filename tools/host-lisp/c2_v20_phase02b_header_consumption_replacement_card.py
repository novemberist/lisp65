#!/usr/bin/env python3
"""Run the one authorized replacement header-consumption card.

The first Link-106 card died before WPLTO because its wrapper called a
non-exported predecessor adapter name.  This replacement keeps every product
and acceptance authority unchanged, gives the card fresh one-shot domains,
and structurally permits only the exported ``configure_chain`` entry at both
wrapper boundaries.
"""

from __future__ import annotations

import argparse
import ast
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

import c2_v20_phase02b_header_consumption_card as CARD  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v2.0-phase02b-header-consumption-replacement-preflight")
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-replacement-card-receipt.json")
FINAL_RED = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-replacement-card-final-red.json")
HISTORICAL_RED = CARD.FINAL_RED
AUTHORIZATION_COMMIT = "480a9f5e"
AUTHORIZATION_BYTES = 63751
AUTHORIZATION_SHA256 = (
    "d64c8e330a86f653a661556b351c076deda3ec160e74d31fbe08d4746d21d51f")
RECORDED_ON = "2026-08-13"
LINK = 106
DRIVER = Path(__file__).resolve()


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES
            and hashlib.sha256(raw).hexdigest() == AUTHORIZATION_SHA256,
            "replacement authorization identity drift")
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "replacement card authorized", "artifact-free red",
            "public exported entry only",
            "mutation against any non-exported adapter call",
            "one replacement card",
            "green proceeds to completion, media, the d1 repeat and d2\u2013d5"):
        require(token in text, f"replacement authorization token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical_red() -> dict[str, Any]:
    value = load(HISTORICAL_RED)
    require(
        value.get("status")
            == "FINAL RED: header-consumption card stopped before WPLTO"
        and value.get("root_cause", {}).get("class")
            == "WRAPPER-ADAPTER-LAYER-NAME-ERROR"
        and value.get("artifact_count") == 0
        and value.get("attempt_accounting", {}).get("wplto_runs") == 0
        and value.get("attempt_accounting", {}).get("product_link_attempts") == 0
        and value.get("retry_authorized") is False,
        "artifact-free predecessor Final Red drift")
    return value


def configure_card() -> None:
    CARD.BUILD = BUILD
    CARD.PREFLIGHT = PREFLIGHT
    CARD.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    CARD.INVOCATION = INVOCATION
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.RECEIPT = RECEIPT
    CARD.FINAL_RED = FINAL_RED
    CARD.LINK = LINK
    CARD.DRIVER = DRIVER
    CARD.configure_chain()


def artifact_paths() -> dict[str, Path]:
    configure_card()
    return CARD.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def function_calls(source: str, function: str) -> list[str]:
    tree = ast.parse(source)
    node = next((item for item in tree.body
                 if isinstance(item, ast.FunctionDef) and item.name == function),
                None)
    require(node is not None, f"adapter function absent: {function}")
    return [ast.unparse(item.func) for item in ast.walk(node)
            if isinstance(item, ast.Call)]


def exported_adapter_gate(
        card_source_override: str | None = None,
        replacement_source_override: str | None = None) -> dict[str, Any]:
    card_source = (Path(CARD.__file__).read_text(encoding="utf-8")
                   if card_source_override is None else card_source_override)
    replacement_source = (DRIVER.read_text(encoding="utf-8")
                          if replacement_source_override is None
                          else replacement_source_override)
    card_calls = function_calls(card_source, "configure_chain")
    replacement_calls = function_calls(replacement_source, "configure_card")
    require(
        card_calls.count("PREVIOUS.configure_chain") == 1
        and not any(call.startswith("PREVIOUS.configure_")
                    and call != "PREVIOUS.configure_chain"
                    for call in card_calls)
        and replacement_calls.count("CARD.configure_chain") == 1
        and not any(call.startswith("CARD.configure_")
                    and call != "CARD.configure_chain"
                    for call in replacement_calls),
        "wrapper called a non-exported adapter entry")
    require(callable(getattr(CARD.PREVIOUS, "configure_chain", None)),
            "predecessor exported configure_chain entry absent")
    return {
        "status": "PASS: both wrappers call only exported chain entries",
        "header_consumption_wrapper": "PREVIOUS.configure_chain",
        "replacement_wrapper": "CARD.configure_chain",
        "non_exported_adapter_calls": 0,
    }


def exported_adapter_mutations() -> list[str]:
    card_source = Path(CARD.__file__).read_text(encoding="utf-8")
    replacement_source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "restore-non-exported-predecessor-adapter": (
            card_source.replace("PREVIOUS.configure_chain()",
                                "PREVIOUS.configure_previous()", 1),
            replacement_source),
        "replacement-calls-non-exported-card-adapter": (
            card_source,
            replacement_source.replace("CARD.configure_chain()",
                                       "CARD.configure_previous()", 1)),
    }
    rejected: list[str] = []
    for name, (candidate_card, candidate_replacement) in cases.items():
        try:
            exported_adapter_gate(candidate_card, candidate_replacement)
        except (ReplacementError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "non-exported adapter mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    historical_red()
    return {
        "format": (
            "lisp65-c2.3-v20-phase02b-header-consumption-replacement-"
            "preflight-v1"),
        "recorded_on": RECORDED_ON,
        "status": "PASS: one exported-adapter replacement card armed",
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "wplto_runs": 0, "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "cards_authorized": 1,
            "candidate_static_code_bytes": 46043,
            "full_map_ownership": True, "phase02a_reopened": False},
        "host_gates": {
            "single_owner_attribution": CARD.attribution_authority(),
            "inherited_single_owner_mutations": 8,
            "real_consumer": CARD.consumption_source_gate(),
            "real_consumer_mutations": CARD.consumption_source_mutations(),
            "path_identity_mutations": CARD.consumption_model_mutations(),
            "exported_adapter": exported_adapter_gate(),
            "exported_adapter_mutations": exported_adapter_mutations(),
            "total_extent_consumption_and_adapter_mutations": 14,
        },
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "candidate_header": CARD.header_binding(), "driver": bind(DRIVER)},
        "claim_limit": (
            "Host preflight only; no WPLTO, link, completion, media or device."),
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "replacement preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-replacements": lambda x: x["configuration"].update(
            cards_authorized=2),
        "accept-bound-only": lambda x: x["host_gates"]["real_consumer"].update(
            real_consumer="configuration-only"),
        "reopen-phase02a": lambda x: x["configuration"].update(
            phase02a_reopened=True),
        "detach-historical-red": lambda x: x["authority"][
            "historical_final_red"].update(sha256="0" * 64),
        "accept-private-adapter": lambda x: x["host_gates"][
            "exported_adapter"].update(non_exported_adapter_calls=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 phase02b header consumption replacement: "
          "PREFLIGHT PASS card=0 adapters=exported")


def consumption_receipts() -> dict[str, dict[str, Any]]:
    configure_card()
    return CARD.consumption_receipts()


def produce_child() -> int:
    configure_card()
    return CARD.produce_child()


def scope_child() -> int:
    configure_card()
    return CARD.scope_child()


def acceptance_child() -> int:
    configure_card()
    return CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh header-consumption replacement child {action} red:\n"
            f"{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "replacement preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK,
        "owner_authorization": authorization(),
        "historical_final_red": bind(HISTORICAL_RED),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    consumption = consumption_receipts()
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement acceptance changed Link-106 artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "replacement card process isolation drift")
    receipt = {
        "format": (
            "lisp65-c2.3-v20-phase02b-header-consumption-replacement-card-v1"),
        "recorded_on": RECORDED_ON,
        "status": "PASS: replacement Link-106 consumed candidate header",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "attribution": CARD.attribution_authority(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "adapter_contract": exported_adapter_gate(),
        "compiler_input_consumption": consumption,
        "mutations": {"single_owner_inherited": 8,
            "consumed_vs_bound": CARD.consumption_source_mutations(),
            "path_identity": CARD.consumption_model_mutations(),
            "exported_adapter": exported_adapter_mutations(), "total": 14},
        "candidate_oracle_inputs": producer["candidate_oracle_inputs"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "next": "completion and same-world media, then D1",
        "claim_limit": (
            "One replacement product card and linked artifacts only; "
            "completion, media and device have not run."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 phase02b header consumption replacement: PASS card=1/1 "
          "consumed=46043 VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": (
            "lisp65-c2.3-v20-phase02b-header-consumption-replacement-"
            "final-red-v1"),
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: header-consumption replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "wplto_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def selftest() -> None:
    value = preflight_value(); validate_preflight(value)
    require(len(preflight_mutations(value)) == 5
            and len(CARD.consumption_source_mutations()) == 2
            and len(CARD.consumption_model_mutations()) == 2
            and len(exported_adapter_mutations()) == 2,
            "header-consumption replacement selftest drift")
    print("2.0 phase02b header consumption replacement: SELFTEST PASS "
          "single-owner=8 consumed=4 adapters=2 card=one")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "replacement Final Red drift")
        print("2.0 phase02b header consumption replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 phase02b header consumption replacement: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value.get("status")
            == "PASS: replacement Link-106 consumed candidate header"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value.get("adapter_contract") == exported_adapter_gate()
        and value.get("compiler_input_consumption") == consumption_receipts()
        and value.get("artifacts_before") == frozen_artifacts()
        and value.get("artifacts_after") == value["artifacts_before"]
        and value.get("process_isolation", {}).get("all_distinct") is True
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103,
        "green header-consumption replacement receipt drift")
    print("2.0 phase02b header consumption replacement: "
          "CHECK PASS card=1/1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card",
                                           "check", "_produce", "_scope",
                                           "_accept"))
    action = parser.parse_args().action
    {"selftest": selftest, "preflight": preflight, "card": card,
     "check": check, "_produce": produce_child, "_scope": scope_child,
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
                print(f"replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 phase02b header consumption replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
