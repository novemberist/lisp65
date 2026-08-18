#!/usr/bin/env python3
"""Run replacement card II after the real multi-TU oracle repair."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_source_oracle_replacement_card as PREVIOUS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-source-oracle-replacement2-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-source-oracle-replacement2-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-source-oracle-replacement2-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-source-oracle-replacement2-card-final-red.json"
HISTORICAL_RED = PREVIOUS.FINAL_RED
AUTHORIZATION_COMMIT = "50bddcd6"
RECORDED_ON = "2026-08-13"
LINK = 104
DRIVER = Path(__file__).resolve()
WPLTO_RESULT = BUILD / "receipts/wplto-base-result.json"
PRODUCER_LOG = BUILD / "receipts/v20-producer.log"


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
        check=True, stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION_COMMIT}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require(
        "replacement card ii authorized" in text
        and "one owning translation unit" in text
        and "real multi-tu build" in text
        and "one replacement card" in text,
        "replacement-II authorization text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical_red() -> dict[str, Any]:
    value = load(HISTORICAL_RED)
    require(
        value.get("status")
            == "FINAL RED: source-oracle replacement returns to owner"
        and value.get("root_cause", {}).get("class")
            == "GENERATED-MULTI-TU-ORACLE-DEFINITION-COLLISION"
        and value.get("attempt_accounting", {}).get("wplto_runs") == 1
        and value["attempt_accounting"]["product_link_attempts"] == 1
        and value["root_cause"]["product_artifacts_created"] is False
        and value.get("retry_authorized") is False,
        "replacement-I terminal authority drift")
    return value


def configure_previous() -> None:
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
    PREVIOUS.configure_base()


def artifact_paths() -> dict[str, Path]:
    configure_previous()
    return PREVIOUS.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    return {name: bind(path) for name, path in artifact_paths().items()}


def integration_gate() -> dict[str, Any]:
    oracle = PREVIOUS.BASE.ORACLE
    value = load(oracle.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    oracle.validate(value)
    target = value["target_codegen"]
    owner = value["source_gate"]["symbol_ownership"]
    require(
        rejected == oracle.mutations(value) and len(rejected) == 15
        and owner == {"definitions": 2,
            "owner": "c2-stream-phase-02a.c", "phase_wrappers": 18,
            "shared_decoder_definitions": 0}
        and target["translation_units"] == 18
        and target["unique_table_owner"] == "c2-stream-phase-02a.c"
        and target["duplicate_definition_mutation"] == "rejected-by-real-link"
        and target["real_consumer_source_mutations_rejected"] == [
            "single-TU-stand-in", "omit-real-link"],
        "real multi-TU integration gate drift")
    return {"receipt": bind(oracle.RECEIPT), "mutations": len(rejected),
            "translation_units": 18, "table_owners": 1,
            "phase02a_bytes": target["phase02a_bytes"],
            "headroom_bytes": target["headroom_bytes"]}


def preflight_value() -> dict[str, Any]:
    historical_red()
    return {
        "format": "lisp65-c2.3-v20-source-oracle-replacement2-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one real-multi-TU replacement card armed",
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
        "host_gates": {"multi_TU_oracle": integration_gate(),
            "exclusive_build_owner": PREVIOUS.lifecycle_source_gate(),
            "exclusive_build_mutations": PREVIOUS.lifecycle_mutations()},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "VMA_golden": bind(PREVIOUS.BASE.BASE.INV.GOLDEN),
            "map_tuple_fix": bind(PREVIOUS.BASE.BASE.FIX.RECEIPT),
            "driver": bind(DRIVER)},
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "replacement-II preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["acceptance"].update(cards_authorized=2),
        "drop-full-map": lambda x: x["configuration"].update(full_map_ownership=False),
        "restore-old-MAP-A": lambda x: x["configuration"]["MAP_tuple"].update(A="0x80"),
        "undersize-timeout": lambda x: x["configuration"].update(oracle_timeout_frames=63),
        "two-table-owners": lambda x: x["host_gates"]["multi_TU_oracle"].update(table_owners=2),
        "single-TU": lambda x: x["host_gates"]["multi_TU_oracle"].update(translation_units=1),
        "detach-final-red": lambda x: x["authority"]["historical_final_red"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "replacement-II preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement-II preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 source-oracle replacement-II: PREFLIGHT PASS multi-TU=18 card=0")


def produce_child() -> int:
    configure_previous()
    PREVIOUS.producer_build_owner_gate(BUILD.exists())
    return PREVIOUS.produce_child()


def scope_child() -> int:
    configure_previous()
    return PREVIOUS.scope_child()


def acceptance_child() -> int:
    configure_previous()
    return PREVIOUS.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run([sys.executable, str(DRIVER), action], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh replacement-II child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "replacement-II preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement-II product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner_authorization": authorization(),
        "historical_final_red": bind(HISTORICAL_RED),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement-II acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"], acceptance["pid"]}) == 4,
            "replacement-II process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v20-source-oracle-replacement2-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: source-authoritative oracle replacement-II card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "oracle_host_gate": bind(PREVIOUS.BASE.ORACLE.RECEIPT),
            "driver": bind(DRIVER)},
        "multi_TU_oracle": integration_gate(),
        "exclusive_build_owner": PREVIOUS.lifecycle_source_gate(),
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "artifacts_before": before, "artifacts_after": after,
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "next": "regenerate current-world media, then D1",
        "claim_limit": "Replacement-II card and artifacts only; no media/device.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 source-oracle replacement-II: PASS card=1/1 WPLTO=1 link=1 VMA=103")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-source-oracle-replacement2-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: source-oracle replacement-II returns to owner",
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


def _owner_crcs(path: Path) -> dict[str, list[str]]:
    source = path.read_text(encoding="utf-8")
    blocks = source.split("c2_phase02a_shelf_crc16:", 1)
    require(len(blocks) == 2, "candidate Shelf table absent")
    shelf_text, c2d_text = blocks[1].split("c2_phase02a_c2d_crc16:", 1)
    values = lambda text: re.findall(r"\.short 0x([0-9a-f]{4})", text)
    shelf = values(shelf_text); c2d = values(c2d_text)
    require(len(shelf) == len(c2d) == 6, "candidate CRC table cardinality drift")
    return {"shelf": ["0x" + value for value in shelf],
            "c2d": ["0x" + value for value in c2d]}


def _delivery_crcs() -> dict[str, list[str]]:
    base = BUILD / "static-plane/narrow-static"
    shelf = (base / "product/product-shelf-v4-direct.bin").read_bytes()
    c2d = (base / "v6-semantics/initial.c2d-v6.bin").read_bytes()
    offset = struct.unpack_from("<H", c2d, 28)[0]
    crc = PREVIOUS.BASE.ORACLE.crc16
    return {
        "shelf": [f"0x{crc(shelf[32 + i * 32:64 + i * 32]):04x}"
                  for i in range(6)],
        "c2d": [f"0x{crc(c2d[offset + i * 32:offset + (i + 1) * 32]):04x}"
                for i in range(6)],
    }


def bind_final_red() -> None:
    configure_previous()
    value = load(FINAL_RED)
    artifacts = frozen_artifacts()
    require(
        value.get("status")
            == "FINAL RED: source-oracle replacement-II returns to owner"
        and value.get("retry_authorized") is False
        and value["attempt_accounting"]["wplto_runs"] == 1
        and value["attempt_accounting"]["product_link_attempts"] == 1
        and all(name in artifacts for name in ("elf", "prg", "map", "lto"))
        and "inherited noinit/alignment geometry drift" in
            value.get("error", {}).get("message", ""),
        "replacement-II Final Red cannot be mechanism-bound")
    elf = artifact_paths()["elf"]
    truth = PREVIOUS.BASE.ElfTruth.read(
        elf, llvm_readobj=PREVIOUS.BASE.READOBJ, include_section_data=True)
    noinit = truth.section(".noinit")
    stack = truth.section(".lisp65_c2_static_stack")
    hot = truth.section(".lisp65_c2_fixed_bank0_hot_bss")
    heap = truth.symbol("__heap_start")
    require((noinit.address, noinit.bytes) == (0xC34D, 0)
            and (stack.address, stack.bytes) == (0xC074, 6)
            and hot.address + hot.bytes == 0xC34D
            and heap.value == 0xC354,
            "owned full-map state evidence drift")
    comparison = PREVIOUS.BASE.BASE.INV.compare_elf(elf)
    tuple_gate = PREVIOUS.BASE.BASE.linked_tuple_gate(elf)
    far = PREVIOUS.BASE.far_payload_gate(elf)
    generated = _owner_crcs(artifact_paths()["generated_phase02a"])
    delivery = _delivery_crcs()
    require(generated["shelf"] == delivery["shelf"]
            and generated["c2d"] != delivery["c2d"],
            "candidate delivery-oracle world-drift evidence absent")
    result = load(WPLTO_RESULT)
    require(result["WPLTO"]["return_code"] == 2,
            "WPLTO terminal status drift")
    value["root_cause"] = {
        "class": "INHERITED-FIXED-LEAF-NOINIT-SNAPSHOT-CROSSES-FULL-MAP-OWNER",
        "phase": "post-link fixed-block leaf qualification",
        "mechanism": (
            "The historical fixed-leaf checker still requires the old six-byte "
            ".noinit resident at $C34D. Full-map ownership correctly has zero "
            "ordinary .noinit there and owns the six-byte static stack at $C074."),
        "actual_noinit": {"address": "0xc34d", "bytes": 0},
        "historical_expectation": {"address": "0xc34d", "bytes": 6},
        "owned_static_stack": {"address": "0xc074", "bytes": 6},
        "heap_start": "0xc354", "product_link_artifacts_created": True,
    }
    value["independent_read_only_acceptance"] = {
        "VMA_golden": {"allocatable_sections": comparison["allocatable_sections"],
            "fixed_boundary_symbols": comparison["fixed_boundary_symbols"],
            "comparison": comparison["comparison"],
            "capacity_measurements": comparison["capacity_measurements"]},
        "linked_MAP_tuple": tuple_gate, "far_payload": far,
        "artifact_completion": "not run",
        "delivered_CRC_operands": "not yet publish-last completed",
    }
    value["additional_precompletion_red"] = {
        "class": "CANDIDATE-ORACLE-INPUT-WORLD-DRIFT",
        "mechanism": (
            "The real producer generated C2D oracle CRCs from an inherited "
            "V6.OUT world instead of the candidate static plane. Shelf rows "
            "match; all six C2D rows differ."),
        "generated_tables": generated, "candidate_delivery": delivery,
        "candidate_would_be_delivery_authoritative": False,
    }
    value["artifacts"] = artifacts
    value["integration_evidence"] = {
        "WPLTO_result": bind(WPLTO_RESULT), "producer_log": bind(PRODUCER_LOG),
        "generated_owner": bind(artifact_paths()["generated_phase02a"]),
        "candidate_C2D": bind(
            BUILD / "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin")}
    value["authority"]["driver"] = bind(DRIVER)
    value["evidence_rebound_after_terminal_stop"] = True
    FINAL_RED.write_bytes(canonical(value))
    print("2.0 source-oracle replacement-II: FINAL RED BOUND fixed-leaf + world-drift")


def selftest() -> None:
    value = preflight_value(); validate_preflight(value)
    require(len(preflight_mutations(value)) == 7
            and value["host_gates"]["multi_TU_oracle"]["translation_units"] == 18,
            "replacement-II selftest drift")
    print("2.0 source-oracle replacement-II: SELFTEST PASS multi-TU=18 mutations=7")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "replacement-II Final Red drift")
        if value.get("evidence_rebound_after_terminal_stop"):
            require(
                value["root_cause"]["class"]
                    == "INHERITED-FIXED-LEAF-NOINIT-SNAPSHOT-CROSSES-FULL-MAP-OWNER"
                and value["root_cause"]["product_link_artifacts_created"] is True
                and value["additional_precompletion_red"]["class"]
                    == "CANDIDATE-ORACLE-INPUT-WORLD-DRIFT"
                and value["independent_read_only_acceptance"]["VMA_golden"]
                    ["allocatable_sections"] == 103
                and value["authority"]["driver"] == bind(DRIVER),
                "bound replacement-II mechanism drift")
        print("2.0 source-oracle replacement-II: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 source-oracle replacement-II: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value["status"]
            == "PASS: source-authoritative oracle replacement-II card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True
        and value["multi_TU_oracle"]["translation_units"] == 18
        and value["multi_TU_oracle"]["table_owners"] == 1
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and value["acceptance"]["source_authoritative_oracle"]["timeout_frames"] == 64
        and value["acceptance"]["far_payload"]["bytes"] == 874,
        "green replacement-II receipt drift")
    print("2.0 source-oracle replacement-II: CHECK PASS card=1/1 WPLTO=1 link=1")


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
                print(f"replacement-II Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 source-oracle replacement-II: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
