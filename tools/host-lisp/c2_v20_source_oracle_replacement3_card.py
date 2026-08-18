#!/usr/bin/env python3
"""Run the one owner-authorized candidate-world oracle replacement card."""

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

import c2_fixed_block_leaf_gate as FIXED  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_source_authoritative_oracle_card as BASE_CARD  # noqa: E402
import c2_v20_source_oracle_replacement_card as REPLACEMENT  # noqa: E402
import c2_v20_source_oracle_replacement2_card as PREVIOUS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-source-oracle-replacement3-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-source-oracle-replacement3-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-source-oracle-replacement3-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-source-oracle-replacement3-card-final-red.json"
HISTORICAL_RED = PREVIOUS.FINAL_RED
AUTHORIZATION_COMMIT = "ebec721a"
RECORDED_ON = "2026-08-13"
LINK = 105
DRIVER = Path(__file__).resolve()


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
        "both fixes, one card" in text
        and "historical `.noinit` checker retires loudly" in text
        and "oracle sourcing binds to the candidate world" in text
        and "exactly one new card" in text,
        "replacement-III authorization text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical_red() -> dict[str, Any]:
    value = load(HISTORICAL_RED)
    require(
        value.get("status")
            == "FINAL RED: source-oracle replacement-II returns to owner"
        and value.get("root_cause", {}).get("class")
            == "INHERITED-FIXED-LEAF-NOINIT-SNAPSHOT-CROSSES-FULL-MAP-OWNER"
        and value.get("additional_precompletion_red", {}).get("class")
            == "CANDIDATE-ORACLE-INPUT-WORLD-DRIFT"
        and value.get("retry_authorized") is False
        and value.get("attempt_accounting", {}).get("wplto_runs") == 1,
        "replacement-II terminal authority drift")
    return value


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
    PREVIOUS.configure_previous()


def artifact_paths() -> dict[str, Path]:
    configure_chain()
    return BASE_CARD.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    paths = artifact_paths()
    result = {name: bind(path) for name, path in paths.items()}
    seed = BUILD / "wplto/resident-island-seed.prg.lto.o"
    result["seed_lto"] = bind(seed)
    return result


def retirement_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (Path(PRODUCT.__file__).read_text(encoding="utf-8")
              if source_override is None else source_override)
    call = "        full_map_ownership=FULL_MAP_OWNERSHIP)\n"
    branch = "        if FULL_MAP_OWNERSHIP:\n"
    stack_row = (
        "            required_sections["
        "FIXED_BLOCK_LEAF.OWNED_STACK_SECTION] = (\n")
    require(source.count(call) == 1 and source.count(branch) >= 1
            and source.count(stack_row) == 1
            and "FIXED_BLOCK_LEAF.OWNED_STACK_BYTES" in source,
            "historical noinit checker remains on the full-map path")
    FIXED.configure_link60_geometry()
    rejected = FIXED.full_map_ownership_selftest()
    require("resurrect-historical-six-byte-noinit" in rejected,
            "historical noinit resurrection mutation absent")
    return {
        "status": "PASS: historical noinit snapshot retired in full-map world",
        "authority": "full-map-state-ownership",
        "ordinary_noinit": {"address": "0xc34d", "bytes": 0},
        "owned_static_stack": {"address": "0xc074", "bytes": 6},
        "mutations_rejected": sorted(rejected),
    }


def retirement_source_mutations() -> list[str]:
    source = Path(PRODUCT.__file__).read_text(encoding="utf-8")
    old = "        full_map_ownership=FULL_MAP_OWNERSHIP)\n"
    require(source.count(old) == 1, "full-map checker call anchor drift")
    cases = {
        "force-historical-noinit-checker": source.replace(
            old, "        full_map_ownership=False)\n", 1),
        "drop-owned-stack-section": source.replace(
            "FIXED_BLOCK_LEAF.OWNED_STACK_SECTION",
            "'.noinit'", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            retirement_source_gate(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "historical noinit source mutation survived")
    return rejected


def candidate_input_gate() -> dict[str, Any]:
    source = PRODUCER.candidate_oracle_source_gate()
    mutations = PRODUCER.candidate_oracle_source_mutations()
    require(mutations == ["historical-OUT-as-oracle",
                           "drop-candidate-input-binding",
                           "bind-after-real-consumer"],
            "candidate input mutation set drift")
    return {**source, "mutations_rejected": mutations}


def preflight_value() -> dict[str, Any]:
    historical_red()
    old_artifacts = historical_red()["artifacts"]
    require(old_artifacts
            and PREVIOUS.BUILD != BUILD,
            "tainted replacement-II artifact disposition drift")
    return {
        "format": "lisp65-c2.3-v20-source-oracle-replacement3-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one candidate-world replacement card armed",
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
        "host_gates": {
            "historical_noinit_retirement": retirement_source_gate(),
            "historical_noinit_mutations": retirement_source_mutations(),
            "candidate_oracle_inputs": candidate_input_gate(),
            "multi_TU_oracle": PREVIOUS.integration_gate(),
            "exclusive_build_owner": REPLACEMENT.lifecycle_source_gate(),
            "exclusive_build_mutations": REPLACEMENT.lifecycle_mutations(),
        },
        "artifact_disposition": {
            "replacement2": "discarded-never-replayed",
            "tainted_artifact_count": len(old_artifacts),
            "new_build_identity": BUILD.relative_to(ROOT).as_posix(),
        },
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "VMA_golden": bind(BASE_CARD.BASE.INV.GOLDEN),
            "map_tuple_fix": bind(BASE_CARD.BASE.FIX.RECEIPT),
            "driver": bind(DRIVER)},
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(value == preflight_value(), "replacement-III preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two": lambda x: x["acceptance"].update(cards_authorized=2),
        "resurrect-noinit": lambda x: x["host_gates"][
            "historical_noinit_retirement"]["ordinary_noinit"].update(bytes=6),
        "historical-oracle-input": lambda x: x["host_gates"][
            "candidate_oracle_inputs"].update(historical_OUT_reads=1),
        "replay-tainted-r2": lambda x: x["artifact_disposition"].update(
            replacement2="artifact-only-replay"),
        "drop-full-map": lambda x: x["configuration"].update(
            full_map_ownership=False),
        "detach-final-red": lambda x: x["authority"][
            "historical_final_red"].update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "replacement-III preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement-III preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 source-oracle replacement-III: PREFLIGHT PASS card=0")


def produce_child() -> int:
    configure_chain()
    REPLACEMENT.producer_build_owner_gate(BUILD.exists())
    BASE_CARD.BASE.configure_fix_source()
    BASE_CARD.BASE.PRODUCER.LINK = LINK
    BASE_CARD.BASE.PRODUCER.BUILD = BUILD
    BASE_CARD.BASE.PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    BASE_CARD.BASE.PRODUCT.configure_full_map_ownership()
    BASE_CARD.BASE.PRODUCT.configure_low_resident_lma_reset()
    artifacts = BASE_CARD.BASE.PRODUCER.produce_candidate()
    expected = artifact_paths()
    require(all(artifacts[key] == expected[key]
                for key in ("elf", "prg", "map", "linker",
                            "resolved_profile")),
            "replacement-III producer artifact path drift")
    oracle_receipt = BUILD / "receipts/candidate-oracle-input-closure.json"
    oracle_inputs = load(oracle_receipt)
    require(oracle_inputs == artifacts["candidate_oracle_inputs"]
            and oracle_inputs["historical_OUT_inputs"] == 0,
            "candidate oracle input closure drift after producer")
    PRODUCER_RESULT.write_bytes(canonical({
        "status": "PASS", "pid": os.getpid(),
        "artifacts": frozen_artifacts(),
        "candidate_oracle_inputs": bind(oracle_receipt)}))
    return 0


def scope_child() -> int:
    configure_chain()
    return BASE_CARD.scope_child()


def acceptance_child() -> int:
    configure_chain()
    return BASE_CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh replacement-III child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "replacement-III preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "replacement-III product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner_authorization": authorization(),
        "historical_final_red": bind(HISTORICAL_RED),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement-III acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "replacement-III process isolation drift")
    receipt = {
        "format": "lisp65-c2.3-v20-source-oracle-replacement3-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: candidate-world source-oracle replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "wplto_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "authority": {"owner_authorization": authorization(),
            "historical_final_red": bind(HISTORICAL_RED),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "artifact_disposition": value["artifact_disposition"],
        "candidate_oracle_inputs": producer["candidate_oracle_inputs"],
        "historical_noinit_retirement": retirement_source_gate(),
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "owner_scope": scope["gate"],
        "next": "regenerate current-world media, then D1",
        "claim_limit": "Card and linked artifacts only; media/device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 source-oracle replacement-III: PASS card=1/1 "
          "WPLTO=1 link=1 VMA=103 oracle=candidate")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-source-oracle-replacement3-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: source-oracle replacement-III returns to owner",
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
    require(len(preflight_mutations(value)) == 6
            and len(value["host_gates"]["historical_noinit_retirement"]
                    ["mutations_rejected"]) == 3
            and len(value["host_gates"]["candidate_oracle_inputs"]
                    ["mutations_rejected"]) == 3,
            "replacement-III selftest drift")
    print("2.0 source-oracle replacement-III: SELFTEST PASS "
          "noinit=retired oracle=candidate mutations=6")


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "replacement-III Final Red drift")
        print("2.0 source-oracle replacement-III: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 source-oracle replacement-III: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    verification = value.get("verification_rebind", {})
    require(
        value["status"]
            == "PASS: candidate-world source-oracle replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True
        and value["candidate_oracle_inputs"]["sha256"] == bind(
            BUILD / "receipts/candidate-oracle-input-closure.json")["sha256"]
        and value["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and value["acceptance"]["source_authoritative_oracle"][
            "timeout_frames"] == 64
        and verification.get("reason")
            == "post-card selftest no longer requires the candidate build to be absent"
        and verification.get("executed_driver") == value["authority"]["driver"]
        and verification.get("current_driver") == bind(DRIVER),
        "green replacement-III receipt drift")
    print("2.0 source-oracle replacement-III: CHECK PASS card=1/1")


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
                print(f"replacement-III Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 source-oracle replacement-III: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
