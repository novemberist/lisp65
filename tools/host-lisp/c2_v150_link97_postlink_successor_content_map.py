#!/usr/bin/env python3
"""Map three retired post-link proof names to current artifact identities."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
import c2_postlink_successor_identity as IDENTITY  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.5.0-candidate-product-link97"
ARTIFACT_ROOT = BUILD / "wplto"
INTERNAL = BUILD / "post-link-qualification-replay-r9/wplto-internal.json"
PROFILE = BUILD / "post-link-qualification-replay-r9/candidate-profile.json"
FIRST_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r9-first-red.json")
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-three-postlink-successor-content-map-receipt.json")
CONSUMER = HOST / "c2_lite_canonical_product.py"
BANK2_SOURCE = HOST / "c2_lite_v6_bank2_target_stage_wplto.py"
ROOTS_SOURCE = HOST / "c2_lite_v6_roots_fronts_successor_link.py"
ISLAND_SOURCE = HOST / "c2_final_island_identity_gate.py"
FORMAT = "lisp65-c2.3-v150-link97-three-postlink-content-map-v1"
STATUS = "passed-three-vocabulary-successors-zero-qualification-gaps"
FIELD_MAP = {
    "bank2_workbench_scratch_negative": {
        "identity": "bank2-target-and-workbench-identity",
        "claims": [
            "all six current Bank-2 records bind shelf source to target CRC",
            "the current Workbench payload passes zero Bank-2 records",
            "READY cannot follow while Workbench scratch remains"],
        "schema_rows": [
            "bank3_stage_before_publish", "workbench_crc_end_to_end"],
    },
    "roots_fronts_one_slice_two_entry": {
        "identity": "roots-fronts-single-slice-entry-identity",
        "claims": [
            "roots/fronts duties share one bounded runtime slice",
            "all roots/fronts entry functions reside in that slice",
            "the current session manifest and region sizes carry the slice"],
        "schema_rows": ["capacity"],
    },
    "final_island_single_runtime_identity": {
        "identity": "final-island-carrier-identity",
        "claims": [
            "the final carrier record names the current Resident Island",
            "carrier payload, manifest and extracted ELF section are identical",
            "eleven fail-closed identity mutations are rejected"],
        "schema_rows": ["runtime_family"],
    },
}


class ContentMapError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContentMapError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"three-field content-map authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"three-field content-map JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def function(text: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(text)
    node = next((item for item in tree.body
                 if isinstance(item, ast.FunctionDef)
                 and item.name == name), None)
    require(node is not None, f"consumer function absent: {name}")
    return node


def consumer_source_gate(source: str | None = None) -> dict[str, Any]:
    text = CONSUMER.read_text(encoding="utf-8") if source is None else source
    node = function(text, "fresh_current_product_postlink_gate")
    calls = [ast.unparse(item.func) for item in ast.walk(node)
             if isinstance(item, ast.Call)]
    replacement_keys = {
        item.slice.value for item in ast.walk(node)
        if isinstance(item, ast.Subscript)
        and isinstance(item.value, ast.Name)
        and item.value.id == "replacement"
        and isinstance(item.slice, ast.Constant)
        and isinstance(item.slice.value, str)}
    strings = {item.value for item in ast.walk(node)
               if isinstance(item, ast.Constant)
               and isinstance(item.value, str)}
    require(
        calls.count("SUCCESSOR_IDENTITY.project") == 1
        and not (set(FIELD_MAP) & replacement_keys)
        and {row["identity"] for row in FIELD_MAP.values()} <= strings,
        "post-link consumer retains retired proof vocabulary")
    return {
        "status": "passed-current-semantic-identity-consumer",
        "project_calls": 1,
        "retired_direct_field_reads": 0,
        "current_identity_names": sorted(
            row["identity"] for row in FIELD_MAP.values()),
        "rule": (
            "The post-link consumer binds semantic identities from the "
            "supplied artifact world, never retired producer field names."),
    }


def consumer_source_mutations() -> list[str]:
    source = CONSUMER.read_text(encoding="utf-8")
    anchor = "successor_identity = SUCCESSOR_IDENTITY.project("
    require(anchor in source, "consumer mutation anchor absent")
    cases = {
        "drop-current-projection": source.replace(
            anchor, "successor_identity = dict(", 1),
        "restore-retired-bank2-field": source.replace(
            "walls = replacement[\"walls\"]",
            ("_retired = replacement[\"bank2_workbench_scratch_negative\"]\n"
             "    walls = replacement[\"walls\"]"), 1),
        "pin-retired-roots-field": source.replace(
            "walls = replacement[\"walls\"]",
            ("_retired = replacement[\"roots_fronts_one_slice_two_entry\"]\n"
             "    walls = replacement[\"walls\"]"), 1),
        "pin-retired-island-field": source.replace(
            "walls = replacement[\"walls\"]",
            ("_retired = replacement[\"final_island_single_runtime_identity\"]\n"
             "    walls = replacement[\"walls\"]"), 1),
    }
    rejected: list[str] = []
    for name, mutant in cases.items():
        try:
            consumer_source_gate(mutant)
        except (ContentMapError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "consumer schema mutation survived")
    return rejected


def frozen_artifacts() -> dict[str, Any]:
    frozen = load(FIRST_RED)["frozen_artifacts_after_stop"]
    for role, row in frozen.items():
        require(bind(ROOT / row["path"]) == row,
                f"frozen Link-97 artifact drift: {role}")
    return frozen


def collect() -> dict[str, Any]:
    internal = load(INTERNAL)
    replacement = internal["fresh_replacement_gates"]
    before = frozen_artifacts()
    projection = IDENTITY.project(replacement, ARTIFACT_ROOT)
    after = frozen_artifacts()
    require(before == after, "content map changed frozen Link-97 artifacts")
    entries: dict[str, Any] = {}
    for old, spec in FIELD_MAP.items():
        proof = projection["proofs"][spec["identity"]]
        require(proof["current_schema_rows"] == spec["schema_rows"],
                f"schema carrier drift: {old}")
        entries[old] = {
            "classification": "vocabulary-successor-content-present",
            "semantic_claims": spec["claims"],
            "current_identity": spec["identity"],
            "current_schema_rows": spec["schema_rows"],
            "proof": proof,
        }
    value = {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "scope": {
            "product_links": 0, "compiler_or_WPLTO_runs": 0,
            "artifact_completions": 0, "media_builds": 0,
            "hardware_runs": 0, "frozen_Link97_artifacts_modified": False,
        },
        "authorities": {
            "authorization_commit": "0a2bf127",
            "r9_first_red": bind(FIRST_RED),
            "r9_internal": bind(INTERNAL), "candidate_profile": bind(PROFILE),
            "identity_projector": bind(Path(IDENTITY.__file__).resolve()),
            "content_map_tool": bind(Path(__file__)),
            "postlink_consumer": bind(CONSUMER),
            "historical_claim_sources": {
                "bank2": bind(BANK2_SOURCE), "roots_fronts": bind(ROOTS_SOURCE),
                "final_island": bind(ISLAND_SOURCE)},
            "consumer_source_gate": consumer_source_gate(),
            "consumer_source_mutations_rejected":
                consumer_source_mutations(),
        },
        "content_map": entries,
        "decision": {
            "vocabulary_cases": 3, "qualification_gaps": 0,
            "mixed_result": False,
            "consumer_schema_updated": True,
            "replay_authorized": False,
        },
        "frozen_artifacts_before": before,
        "frozen_artifacts_after": after,
        "claim_limit": (
            "Desk-only semantic attribution and current-schema consumer "
            "adaptation for three retired post-link proof names. No replay, "
            "completion, medium, device, Halt or release claim."),
    }
    validate(value, verify=False)
    return value


def validate(value: dict[str, Any], *, verify: bool) -> None:
    decision = value.get("decision", {})
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and decision == {
            "vocabulary_cases": 3, "qualification_gaps": 0,
            "mixed_result": False, "consumer_schema_updated": True,
            "replay_authorized": False}
        and value.get("scope", {}).get(
            "frozen_Link97_artifacts_modified") is False
        and value.get("frozen_artifacts_before")
            == value.get("frozen_artifacts_after")
        and set(value.get("content_map", {})) == set(FIELD_MAP),
        "three-field content-map decision drift")
    for old, spec in FIELD_MAP.items():
        row = value["content_map"][old]
        require(
            row.get("classification")
                == "vocabulary-successor-content-present"
            and row.get("semantic_claims") == spec["claims"]
            and row.get("current_identity") == spec["identity"]
            and row.get("current_schema_rows") == spec["schema_rows"],
            f"three-field semantic identity drift: {old}")
    bank = value["content_map"]["bank2_workbench_scratch_negative"]["proof"]
    roots = value["content_map"]["roots_fronts_one_slice_two_entry"]["proof"]
    island = value["content_map"][
        "final_island_single_runtime_identity"]["proof"]
    require(
        bank.get("status")
            == "passed-current-bank2-records-and-workbench-negative"
        and bank.get("record_count") == 6
        and bank.get("workbench_scratch_passing_records") == 0
        and bank.get("ready_if_workbench_scratch_remains") is False
        and roots.get("status")
            == "passed-current-one-slice-multiple-entry-identity"
        and len(roots.get("entries", {})) == 3
        and roots.get("retired_split_sections_present") is False
        and island.get("status")
            == "passed-final-record-equals-final-island-single-truth"
        and island.get("mutation_cases") == 11
        and island.get("seed_runtime_comparisons") == 0
        and island["identity"]["section_sha256"]
            == island["carrier_manifest_section_sha256"],
        "three-field artifact proof drift")
    if verify:
        require(value == collect(), "three-field content-map authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-retired-bank2-name": lambda x: x["content_map"]
            ["bank2_workbench_scratch_negative"].update(
                current_identity="bank2_workbench_scratch_negative"),
        "restore-retired-roots-name": lambda x: x["content_map"]
            ["roots_fronts_one_slice_two_entry"].update(
                current_identity="roots_fronts_one_slice_two_entry"),
        "restore-retired-island-name": lambda x: x["content_map"]
            ["final_island_single_runtime_identity"].update(
                current_identity="final_island_single_runtime_identity"),
        "accept-workbench-record": lambda x: x["content_map"]
            ["bank2_workbench_scratch_negative"]["proof"].update(
                workbench_scratch_passing_records=1),
        "drop-roots-entry": lambda x: x["content_map"]
            ["roots_fronts_one_slice_two_entry"]["proof"]["entries"].popitem(),
        "dim-island-mutations": lambda x: x["content_map"]
            ["final_island_single_runtime_identity"]["proof"].update(
                mutation_cases=10),
        "claim-qualification-gap": lambda x: x["decision"].update(
            vocabulary_cases=2, qualification_gaps=1, mixed_result=True),
        "claim-replay": lambda x: x["decision"].update(replay_authorized=True),
        "claim-artifact-write": lambda x: x["scope"].update(
            frozen_Link97_artifacts_modified=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except (ContentMapError, KeyError):
            rejected.append(name)
    require(rejected == list(cases), "three-field content-map mutation survived")
    return rejected


def selftest() -> int:
    value = collect(); mutations(value); consumer_source_mutations()
    print("v1.5 Link-97 three-field content map selftest: PASS vocabulary=3 gaps=0")
    return 0


def capture() -> int:
    require(not RECEIPT.exists(), "three-field content-map receipt exists")
    value = collect(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Link-97 three-field content map: PASS vocabulary=3 gaps=0")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "three-field mutation set drift")
    print("v1.5 Link-97 three-field content map check: PASS vocabulary=3 gaps=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "capture", "check"))
    return {"selftest": selftest, "capture": capture,
            "check": check}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContentMapError, IDENTITY.SuccessorIdentityError, OSError,
            KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 three-field content map: RED: {error}")
        raise SystemExit(2)
