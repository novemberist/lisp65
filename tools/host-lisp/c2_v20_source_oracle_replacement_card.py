#!/usr/bin/env python3
"""Run the one replacement card after the build-directory owner fix."""

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

import c2_v20_source_authoritative_oracle_card as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-source-oracle-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-source-oracle-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-source-oracle-replacement-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-source-oracle-replacement-card-final-red.json"
HISTORICAL_RED = BASE.FINAL_RED
AUTHORIZATION_COMMIT = "8cdaa6ec"
RECORDED_ON = "2026-08-13"
LINK = 103
DRIVER = Path(__file__).resolve()
WPLTO_RESULT = BUILD / "receipts/wplto-base-result.json"
PRODUCER_LOG = BUILD / "receipts/v20-producer.log"
GENERATED_DECODER = BUILD / "wplto/generated-product-sources/c2-stream-decoder.c"


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
        check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require(
        "replacement card authorized" in text
        and "build directory belongs to the producer alone" in text
        and "one creating party per exclusively-owned resource" in text
        and "one replacement card" in text,
        "replacement-card authorization text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical_red() -> dict[str, Any]:
    value = load(HISTORICAL_RED)
    require(
        value.get("status") == "FINAL RED: source-oracle card returns to owner"
        and value.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1,
            "device_contacts": 0, "media_builds": 0,
            "product_link_attempts": 0, "wplto_runs": 0}
        and value.get("retry_authorized") is False
        and "File exists" in value.get("error", {}).get("message", ""),
        "pre-product historical Final Red drift")
    return value


def configure_base() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.LINK = LINK
    BASE.DRIVER = DRIVER


def artifact_paths() -> dict[str, Path]:
    configure_base()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return {name: bind(path) for name, path in artifact_paths().items()}


def producer_build_owner_gate(build_exists: bool) -> dict[str, Any]:
    require(not build_exists,
            "exclusive producer build directory was pre-created")
    return {"resource": BUILD.relative_to(ROOT).as_posix(),
            "exclusive_creator": "producer-child",
            "parent_creates_resource": False}


def lifecycle_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") \
        if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    card_fn = functions.get("card")
    producer_fn = functions.get("produce_child")
    require(card_fn is not None and producer_fn is not None,
            "replacement card lifecycle absent")
    card_text = ast.unparse(card_fn)
    producer_text = ast.unparse(producer_fn)
    card_calls = [ast.unparse(node.func) for node in ast.walk(card_fn)
                  if isinstance(node, ast.Call)]
    producer_calls = [ast.unparse(node.func) for node in ast.walk(producer_fn)
                      if isinstance(node, ast.Call)]
    require(
        "BUILD.mkdir" not in card_text
        and card_calls.count("run_child") == 3
        and producer_calls.count("producer_build_owner_gate") == 1
        and producer_calls.count("BASE.BASE.PRODUCER.produce_candidate") == 1
        and "BUILD.mkdir" not in producer_text,
        "build-directory creation has more than one owner")
    return {"status": "PASS: producer exclusively owns build creation",
            "parent_mkdir_calls": card_calls.count("BUILD.mkdir"),
            "producer_entry_checks": 1,
            "actual_producer_calls": 1}


def lifecycle_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    anchor = '    run_child("_produce")\n'
    require(source.count(anchor) == 1, "replacement producer-call anchor drift")
    cases = {
        "parent-precreates-exclusive-build": source.replace(
            anchor, "    BUILD.mkdir(parents=True)\n" + anchor, 1),
        "drop-producer-owner-check": source.replace(
            "    producer_build_owner_gate(BUILD.exists())\n", "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            lifecycle_source_gate(candidate)
        except (ReplacementError, SyntaxError):
            rejected.append(name)
    try:
        producer_build_owner_gate(True)
    except ReplacementError:
        rejected.append("pre-existing-directory-runtime")
    require(rejected == [*cases, "pre-existing-directory-runtime"],
            "exclusive-build-owner mutation survived")
    return rejected


def preflight_value() -> dict[str, Any]:
    historical_red()
    return {
        "format": "lisp65-c2.3-v20-source-oracle-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one producer-owned-build replacement card armed",
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "wplto_runs": 0, "product_links": 0, "device_contacts": 0},
        "configuration": {"link": LINK, "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "MAP_tuple": {"A": "0x40", "X": "0x82"},
            "oracle_timeout_frames": 64, "new_staging_roles": 0},
        "acceptance": {"VMA_invariants": 103, "fixed_boundaries": 27,
            "candidate_derived_validation": True,
            "publish_last_CRC_operands": 2,
            "far_payload_extent_identity": True,
            "linked_delivery_oracle": True, "cards_authorized": 1},
        "host_gates": {"source_oracle": BASE.host_authority(),
            "exclusive_build_owner": lifecycle_source_gate(),
            "exclusive_build_mutations": lifecycle_mutations()},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "VMA_golden": bind(BASE.BASE.INV.GOLDEN),
            "map_tuple_fix": bind(BASE.BASE.FIX.RECEIPT), "driver": bind(DRIVER)},
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "replacement-card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["acceptance"].update(cards_authorized=2),
        "drop-full-map": lambda x: x["configuration"].update(full_map_ownership=False),
        "restore-old-MAP-X": lambda x: x["configuration"]["MAP_tuple"].update(X="0x24"),
        "undersize-timeout": lambda x: x["configuration"].update(oracle_timeout_frames=63),
        "detach-first-red": lambda x: x["authority"]["historical_final_red"].update(sha256="0" * 64),
        "claim-parent-owner": lambda x: x["host_gates"]["exclusive_build_owner"].update(parent_creates_resource=True),
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
    print("2.0 source-oracle replacement: PREFLIGHT PASS owner=producer card=0")


def produce_child() -> int:
    configure_base()
    producer_build_owner_gate(BUILD.exists())
    BASE.BASE.configure_fix_source()
    BASE.BASE.PRODUCER.LINK = LINK
    BASE.BASE.PRODUCER.BUILD = BUILD
    BASE.BASE.PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    BASE.BASE.PRODUCT.configure_full_map_ownership()
    BASE.BASE.PRODUCT.configure_low_resident_lma_reset()
    artifacts = BASE.BASE.PRODUCER.produce_candidate()
    expected = artifact_paths()
    require(all(artifacts[key] == expected[key]
                for key in ("elf", "prg", "map", "lto", "linker",
                            "resolved_profile")),
            "replacement producer artifact path drift")
    PRODUCER_RESULT.write_bytes(canonical({"status": "PASS", "pid": os.getpid(),
                                           "artifacts": frozen_artifacts()}))
    return 0


def scope_child() -> int:
    configure_base()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure_base()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh replacement child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "replacement preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner_authorization": authorization(),
        "historical_final_red": bind(HISTORICAL_RED),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "read-only replacement acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"], acceptance["pid"]}) == 4,
            "replacement process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v20-source-oracle-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: source-authoritative oracle replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "oracle_host_gate": bind(BASE.ORACLE.RECEIPT), "driver": bind(DRIVER)},
        "exclusive_build_owner": lifecycle_source_gate(),
        "exclusive_build_mutations_rejected": lifecycle_mutations(),
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "artifacts_before": before, "artifacts_after": after,
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "next": "regenerate current-world media, then D1",
        "claim_limit": "Replacement card and linked artifacts only; media/device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 source-oracle replacement: PASS card=1/1 WPLTO=1 link=1 VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-source-oracle-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: source-oracle replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "wplto_runs": 1 if PRODUCER_RESULT.exists() or artifacts else 0,
            "product_link_attempts": 1 if PRODUCER_RESULT.exists() or artifacts else 0,
            "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}}))


def bind_final_red() -> None:
    value = load(FINAL_RED)
    require(
        value.get("status")
            == "FINAL RED: source-oracle replacement returns to owner"
        and value.get("retry_authorized") is False
        and value.get("attempt_accounting", {}).get("wplto_runs") == 1
        and value["attempt_accounting"]["product_link_attempts"] == 1
        and not any(name in value.get("artifacts", {})
                    for name in ("elf", "prg", "map", "lto"))
        and "already defined" in value.get("error", {}).get("message", ""),
        "replacement Final Red cannot be mechanism-bound")
    result = load(WPLTO_RESULT)
    require(result["WPLTO"]["product_completed"] is False
            and result["WPLTO"]["return_code"] == 2,
            "WPLTO terminal result drift")
    wrappers = sorted(path for path in GENERATED_DECODER.parent.glob(
        "c2-stream-*.c") if path != GENERATED_DECODER
        and '#include "c2-stream-decoder.c"' in path.read_text(encoding="utf-8"))
    source = GENERATED_DECODER.read_text(encoding="utf-8")
    require(len(wrappers) >= 10
            and source.count("c2_phase02a_shelf_crc16:") == 1
            and source.count("c2_phase02a_c2d_crc16:") == 1,
            "generated multi-TU collision evidence drift")
    value["root_cause"] = {
        "class": "GENERATED-MULTI-TU-ORACLE-DEFINITION-COLLISION",
        "phase": "WPLTO seed-link compilation",
        "mechanism": (
            "The delivery-oracle tables were defined in the shared generated "
            "decoder included by every phase wrapper, so one translation unit "
            "defined both local assembler labels repeatedly."),
        "symbols": ["c2_phase02a_shelf_crc16",
                    "c2_phase02a_c2d_crc16"],
        "generated_decoder_includers": len(wrappers),
        "host_gate_blind_spot": (
            "The target-codegen host gate compiled one projected phase and "
            "did not execute the real multi-wrapper product consumer."),
        "product_artifacts_created": False,
    }
    value["integration_evidence"] = {
        "WPLTO_result": bind(WPLTO_RESULT), "producer_log": bind(PRODUCER_LOG),
        "generated_decoder": bind(GENERATED_DECODER),
        "sample_wrappers": [bind(path) for path in wrappers[:3]],
    }
    value["authority"]["driver"] = bind(DRIVER)
    value["evidence_rebound_after_terminal_stop"] = True
    FINAL_RED.write_bytes(canonical(value))
    print("2.0 source-oracle replacement: FINAL RED BOUND multi-TU collision")


def selftest() -> None:
    value = preflight_value(); validate_preflight(value)
    require(len(lifecycle_mutations()) == 3
            and len(preflight_mutations(value)) == 6,
            "replacement selftest mutation count drift")
    print("2.0 source-oracle replacement: SELFTEST PASS owner=producer mutations=9")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "replacement Final Red drift")
        if value.get("evidence_rebound_after_terminal_stop"):
            require(
                value.get("root_cause", {}).get("class")
                    == "GENERATED-MULTI-TU-ORACLE-DEFINITION-COLLISION"
                and value["root_cause"]["product_artifacts_created"] is False
                and value["attempt_accounting"]["wplto_runs"] == 1
                and value["attempt_accounting"]["product_link_attempts"] == 1
                and value["authority"]["driver"] == bind(DRIVER),
                "bound replacement Final Red mechanism drift")
        print("2.0 source-oracle replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 source-oracle replacement: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value["status"] == "PASS: source-authoritative oracle replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["attempt_accounting"]["wplto_runs"] == 1
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True
        and value["exclusive_build_owner"]["parent_mkdir_calls"] == 0
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and value["acceptance"]["source_authoritative_oracle"]["timeout_frames"] == 64
        and value["acceptance"]["far_payload"]["bytes"] == 874,
        "green source-oracle replacement receipt drift")
    print("2.0 source-oracle replacement: CHECK PASS card=1/1 WPLTO=1 link=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check",
                                           "bind-red", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"selftest": selftest, "preflight": preflight, "card": card,
     "bind-red": bind_final_red,
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
        print(f"2.0 source-oracle replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
