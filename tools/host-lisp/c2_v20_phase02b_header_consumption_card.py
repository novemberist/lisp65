#!/usr/bin/env python3
"""Build the one authorized Link-106 candidate with a consumed header.

The predecessor bound the correct candidate static-plane header but the real
compiler selected the historical workspace header.  This card force-includes
the exact bound candidate path in every real compile and requires a second,
build-local compile-time assertion immediately after it.  Only then does the
ordinary producer and VMA-golden acceptance chain run.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_phase02b_extent_attribution as ATTR  # noqa: E402
import c2_v20_source_oracle_replacement3_card as PREVIOUS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v2.0-link105-phase02b-extent-attribution-receipt.json")
CANDIDATE_HEADER = ROOT / (
    "build/c2.3/v2.0-ownership-recharter-inputs/c2_lite_static_plane.h")
HISTORICAL_HEADER = ROOT / "src/c2_lite_static_plane.h"
BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-card-receipt.json")
FINAL_RED = EVIDENCE / (
    "c2.3-v2.0-phase02b-header-consumption-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION_COMMIT = "b21fbc49"
AUTHORIZATION_BYTES = 63079
AUTHORIZATION_SHA256 = (
    "dec9b4dfec0c26ed67743d866358c195fe05630005d89e53dd808c4f4d745f30")
HEADER_SHA256 = "f58bc7a13282e468489945363306918e84d7fcc17c8fa064bd300fa223fb0e37"
ATTRIBUTION_SHA256 = "a24c53aa7abe96d154eed49e7376ae898d1ee9cf965d314545fb52c846d47608"
LINK = 106
RECORDED_ON = "2026-08-13"


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    require(len(raw) == AUTHORIZATION_BYTES and hashlib.sha256(raw).hexdigest()
            == AUTHORIZATION_SHA256, "header-consumption authorization drift")
    for token in (
            b"Header-consumption fix authorized",
            b"bound \xe2\x89\xa0 consumed by the real compiler",
            b"compiler reads a header",
            b"other than the bound candidate one fails loudly",
            b"One product card",
            b"completion, media regeneration, the D1 repeat"):
        require(token in raw, f"authorization token absent: {token!r}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure_chain() -> None:
    PREVIOUS.BUILD = BUILD
    PREVIOUS.PREFLIGHT = PREFLIGHT
    PREVIOUS.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    PREVIOUS.INVOCATION = INVOCATION
    PREVIOUS.PRODUCER_RESULT = PRODUCER_RESULT
    PREVIOUS.SCOPE_RESULT = SCOPE_RESULT
    PREVIOUS.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    PREVIOUS.RECEIPT = RECEIPT
    PREVIOUS.FINAL_RED = FINAL_RED
    PREVIOUS.LINK = LINK
    PREVIOUS.DRIVER = DRIVER
    PREVIOUS.configure_chain()


def artifact_paths() -> dict[str, Path]:
    configure_chain()
    return PREVIOUS.BASE_CARD.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    return result


def attribution_authority() -> dict[str, Any]:
    binding = bind(ATTRIBUTION)
    require(binding["sha256"] == ATTRIBUTION_SHA256,
            "phase02b extent attribution identity drift")
    value = load(ATTRIBUTION)
    require(
        value.get("status") == (
            "PHASE02B-CONTRACT-SHORT-BY-104; "
            "AUTHORITATIVE-CODE-PLANE=46043")
        and value["authoritative_extent"]["value_bytes"] == 46043
        and value["linked_contract_attribution"]["observed_target_contract_bytes"]
            == 45939
        and value["far_payload_correlation"]["correlated"] is False
        and len(value["mutations_rejected"]) == 8,
        "phase02b attribution authority drift")
    return binding


def header_binding(path: Path = CANDIDATE_HEADER) -> dict[str, Any]:
    value = bind(path)
    require(path == CANDIDATE_HEADER and value["sha256"] == HEADER_SHA256,
            "compiler-consumed path is not the bound candidate header")
    return value


def configure_consumption() -> dict[str, Any]:
    binding = header_binding()
    PRODUCT.configure_compiler_consumed_static_header(
        CANDIDATE_HEADER, binding, 46043)
    return binding


def consumption_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (Path(PRODUCT.__file__).read_text(encoding="utf-8")
              if source_override is None else source_override)
    configure_call = "def configure_compiler_consumed_static_header("
    flag_call = "consumed_flags, consumed_report = compiler_consumed_static_header_flags("
    actual_extension = "    compile_flags.extend(consumed_flags)\n"
    receipt_write = 'target) + ".compiler-input-consumption.json")'
    require(source.count(configure_call) == source.count(flag_call) == 1
            and source.count(actual_extension) == source.count(receipt_write) == 1
            and source.index(flag_call) < source.index(actual_extension)
            and source.index(actual_extension) < source.index("for header in headers:")
            and source.index(actual_extension) < source.index(
                "run_link_with_exact_orphan_wrapper(out, target, command)")
            and source.index(receipt_write) > source.index(
                "run_link_with_exact_orphan_wrapper(out, target, command)"),
            "bound header is not wired into the real compiler consumer")
    return {
        "status": "PASS: exact bound candidate header reaches real compiler flags",
        "bound_header": header_binding(),
        "expected_static_code_bytes": 46043,
        "real_consumer": "c2_product_substitution_link.compile_link",
        "post_success_receipt": True,
    }


def consumption_source_mutations() -> list[str]:
    source = Path(PRODUCT.__file__).read_text(encoding="utf-8")
    extension = "    compile_flags.extend(consumed_flags)\n"
    cases = {
        "bound-but-not-consumed": source.replace(extension, "", 1),
        "consume-after-ordinary-headers": source.replace(
            extension, "", 1).replace(
                "    for directory in EXTRA_INCLUDE_DIRS:\n",
                extension + "    for directory in EXTRA_INCLUDE_DIRS:\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            consumption_source_gate(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "consumed-vs-bound source mutation survived")
    return rejected


def consumption_model_mutations() -> list[str]:
    cases: dict[str, Callable[[], None]] = {
        "historical-header-path": lambda: header_binding(HISTORICAL_HEADER),
        "candidate-binding-SHA-drift": lambda: (
            PRODUCT.configure_compiler_consumed_static_header(
                CANDIDATE_HEADER,
                {**bind(CANDIDATE_HEADER), "sha256": "0" * 64}, 46043)),
    }
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except (CardError, RuntimeError):
            rejected.append(name)
    require(rejected == list(cases), "consumed-header model mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v20-phase02b-header-consumption-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one real-consumer header-fix card armed",
        "attempt_accounting": {"cards_consumed": 0, "wplto_runs": 0,
                               "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "cards_authorized": 1,
                          "candidate_static_code_bytes": 46043,
                          "full_map_ownership": True,
                          "phase02a_reopened": False},
        "host_gates": {
            "single_owner_attribution": attribution_authority(),
            "inherited_single_owner_mutations": 8,
            "real_consumer": consumption_source_gate(),
            "real_consumer_mutations": consumption_source_mutations(),
            "path_identity_mutations": consumption_model_mutations(),
            "total_extent_and_consumption_mutations": 12,
        },
        "authority": {
            "owner_authorization": authorization(),
            "predecessor_card": bind(PREVIOUS.RECEIPT),
            "candidate_header": header_binding(),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "Host preflight only; no WPLTO, link, completion, media or device."),
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "header-consumption preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "accept-bound-only": lambda x: x["host_gates"]["real_consumer"].update(
            real_consumer="configuration-only"),
        "drop-104-attribution": lambda x: x["host_gates"].update(
            inherited_single_owner_mutations=0),
        "reopen-phase02a": lambda x: x["configuration"].update(
            phase02a_reopened=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "header-consumption preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "header-consumption preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 phase02b header consumption: PREFLIGHT PASS card=0")


def consumption_receipts() -> dict[str, dict[str, Any]]:
    paths = {
        "seed": BUILD / (
            "wplto/resident-island-seed.prg.compiler-input-consumption.json"),
        "final": BUILD / (
            "wplto/lisp65-c2-substitution-linked.prg."
            "compiler-input-consumption.json"),
    }
    result: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        value = load(path)
        require(
            value.get("status") == "passed-bound-candidate-header-consumed"
            and value.get("bound_header") == header_binding()
            and value.get("consumed_value") == 46043
            and value.get("historical_same_basename_accepted") is False
            and value.get("actual_force_include_flags") == [
                "-include", CANDIDATE_HEADER.relative_to(ROOT).as_posix(),
                "-include", value["compile_time_assertion"]["path"]],
            f"real compiler consumption receipt red: {name}")
        result[name] = {"binding": bind(path), "result": value}
    return result


def produce_child() -> int:
    configure_chain()
    configure_consumption()
    result = PREVIOUS.produce_child()
    consumption_receipts()
    return result


def scope_child() -> int:
    configure_chain()
    return PREVIOUS.scope_child()


def acceptance_child() -> int:
    configure_chain()
    return PREVIOUS.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh header-consumption child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "header-consumption preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "header-consumption product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK,
        "owner_authorization": authorization(),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    consumption = consumption_receipts()
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "acceptance changed Link-106 artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "header-consumption card process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v20-phase02b-header-consumption-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: candidate header consumed by real Link-106 compiler",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_links": 1, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner_authorization": authorization(),
            "attribution": attribution_authority(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "compiler_input_consumption": consumption,
        "mutations": {"single_owner_inherited": 8,
            "consumed_vs_bound": consumption_source_mutations(),
            "path_identity": consumption_model_mutations(), "total": 12},
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
            "One product card and linked artifacts only; completion, media "
            "and device have not run."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 phase02b header consumption: PASS card=1/1 "
          "consumed=46043 VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-phase02b-header-consumption-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: header-consumption card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner_authorization": authorization(),
            "attribution": attribution_authority(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
    }))


def selftest() -> None:
    value = preflight_value(); validate_preflight(value)
    require(len(preflight_mutations(value)) == 4
            and len(consumption_source_mutations()) == 2
            and len(consumption_model_mutations()) == 2,
            "header-consumption selftest drift")
    print("2.0 phase02b header consumption: SELFTEST PASS "
          "single-owner=8 consumed=4 card=one")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "header-consumption Final Red drift")
        print("2.0 phase02b header consumption: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 phase02b header consumption: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value.get("status")
            == "PASS: candidate header consumed by real Link-106 compiler"
        and value.get("attempt_accounting")["cards_consumed"] == 1
        and value.get("compiler_input_consumption") == consumption_receipts()
        and value.get("artifacts_before") == frozen_artifacts()
        and value.get("artifacts_after") == value["artifacts_before"]
        and value.get("process_isolation", {}).get("all_distinct") is True
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103,
        "green header-consumption card receipt drift")
    print("2.0 phase02b header consumption: CHECK PASS card=1/1")


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
                print(f"header-consumption Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 phase02b header consumption: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
