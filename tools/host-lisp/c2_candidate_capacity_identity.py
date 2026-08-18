#!/usr/bin/env python3
"""Qualify current C2 Session capacity from the supplied candidate world.

The gate deliberately has no predecessor layout vocabulary.  Its section set,
catalog cardinality, storage bounds and publication identity come from the
ELF-adjacent L65R manifests and the contracts named by the current tree.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EXECUTION_CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
APPEND_CONTRACT = ROOT / "config/c2-append-cutpoint-contract.json"
SERVICE_CONTRACT = ROOT / "config/c2-session-service-contract.json"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.3-v1.5.0-link97-capacity-identity-inversion-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r4-first-red.json")
LIVE_SHAPE_AUTHORITY = EVIDENCE / (
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r5-first-red.json")
LINK97_ELF = ROOT / (
    "build/c2.3/v1.5.0-candidate-product-link97/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
CANONICAL_SOURCE = ROOT / "tools/host-lisp/c2_lite_canonical_product.py"
REPLACEMENT_SOURCE = ROOT / (
    "tools/host-lisp/c2_lite_v6_boot_crc_abi_successor_link.py")
REPLAY_SOURCE = ROOT / "tools/host-lisp/c2_v150_candidate_product.py"
# The immutable capacity receipt was recorded at this source boundary.  Its
# current semantic surface is re-executed by capacity_integration_gate(); the
# unrelated post-link consumer may evolve without rewriting that history.
CANONICAL_CAPACITY_AUTHORITY_HEAD = (
    "6d704c5e51176d1da3f33b810d508eca0ced01c0")
CAPACITY_RECORDER_HEAD = "6d704c5e51176d1da3f33b810d508eca0ced01c0"


class CapacityIdentityError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CapacityIdentityError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"capacity identity input absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"capacity identity artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def candidate_contract_projection() -> dict[str, Any]:
    execution = load(EXECUTION_CONTRACT)
    append = load(APPEND_CONTRACT)
    service = load(SERVICE_CONTRACT)
    facade = execution.get("append_plan_facade16_successor_geometry", {})
    publication = append.get("publish_clear_co_residence", {})
    physical_slice = publication.get("physical_slice")
    logical_entries = publication.get("logical_entries")
    service_name = service.get("first_instance", {}).get("name")
    require(
        execution.get("status") ==
            "owner-authorized: append-plan facade vector 16 and full "
            "three-byte successor repin"
        and execution.get("decision", {}).get("e000_active_floor_bytes") == 54
        and facade.get("status") == "owner-authorized-pending-fresh-WPLTO"
        and append.get("schema") == "lisp65.c2.append-cutpoint-contract.v8"
        and isinstance(physical_slice, str) and physical_slice
        and isinstance(logical_entries, list) and logical_entries
        and all(isinstance(item, str) and item for item in logical_entries)
        and service.get("format") == "lisp65-c2-session-service-contract-v1"
        and isinstance(service_name, str) and service_name,
        "current candidate capacity contract identity is incomplete",
    )
    publication_section = f".lisp65_rt_c2append_{physical_slice}"
    logical_functions = [
        f"c2_append_{name}_phase" for name in logical_entries]
    publication_functions = [
        f"__lisp65_rt_c2append_{physical_slice}_entry",
        *logical_functions,
        f"c2_append_{physical_slice}_phase",
        f"c2tr_{physical_slice}_body",
    ]
    return {
        "status": "passed-current-candidate-contract-projection",
        "publication_section": publication_section,
        "publication_logical_entries": logical_entries,
        "publication_required_functions": publication_functions,
        "session_service_name": service_name,
        "runtime_slice_cap_bytes": int(
            execution["semantic_slice_splits"]["runtime_slice_cap_bytes"]),
        "authorities": {
            "execution": bind(EXECUTION_CONTRACT),
            "append": bind(APPEND_CONTRACT),
            "session_service": bind(SERVICE_CONTRACT),
        },
        "rule": (
            "Capacity expectations are derived from the bound contract and "
            "artifact identity of the candidate world, never prior-world "
            "section names or catalog constants."),
    }


def live_shape_fixture() -> dict[str, Any]:
    """Load the independently captured replacement-wall operand."""
    evidence = load(LIVE_SHAPE_AUTHORITY)
    mechanism = evidence.get("mechanism", {})
    live = mechanism.get("live_shape", {}).get("runtime_slices", {})
    session = mechanism.get("matched_operands", {})
    require(
        evidence.get("status")
            == "FIRST RED; OWNER-DISPOSITION-REQUIRED; "
               "AUTHORIZED-REPLAY-CONSUMED"
        and mechanism.get("classification")
            == "post-inversion-cross-family-cardinality-domain-mismatch"
        and all(isinstance(live.get(key), int) for key in (
            "count", "cap_bytes", "largest_bytes",
            "minimum_headroom_bytes"))
        and isinstance(session.get("session_path"), str)
        and isinstance(session.get("session_sha256"), str)
        and isinstance(session.get("session_bytes"), int)
        and isinstance(session.get("session_headroom_bytes"), int),
        "independently supplied live-shape fixture is incomplete",
    )
    return {
        "runtime_slices": deepcopy(live),
        "successor_bank3_pack": {
            "session": {
                "path": session["session_path"],
                "bytes": session["session_bytes"],
                "sha256": session["session_sha256"],
                "headroom_bytes": session["session_headroom_bytes"],
            },
        },
    }


def capacity_gate(shape: dict[str, Any], elf: Path) -> dict[str, Any]:
    """Validate capacity solely from the passed candidate artifact set."""
    root = elf.parent  # supplied candidate artifact set
    projection = candidate_contract_projection()
    boot_manifest_path = root / "runtime-overlays-boot-final.json"
    session_manifest_path = root / "runtime-overlays-session-final.json"
    session = load(session_manifest_path)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    rows = session["slices"]
    catalog = session["catalog"]
    policy = session["policy"]
    storage = session["storage"]
    overflow = session["overflow_storage"]
    sections = [row["section"] for row in rows]
    catalog_count = int(catalog["slice_count"])
    section_count = len(sections)
    slice_cap = int(policy["max_slice_bytes"])
    bank_capacity = int(storage["limit"]) - int(storage["address"])
    storage_path = root / storage["file"]
    overflow_path = root / overflow["file"]
    profile_path = root / session["abi"]["contract"]
    header_path = root / session["config_header"]["file"]
    publication_section = projection["publication_section"]
    publication_rows = [
        row for row in rows if row["section"] == publication_section]
    service_rows = [
        row for row in rows
        if row["name"] == projection["session_service_name"]]
    require(
        session.get("schema") == "lisp65-runtime-overlay-package-v2"
        and session.get("lifetime_family") == "session"
        and session.get("elf", {}).get("sha256") == bind(elf)["sha256"]
        and session.get("catalog", {}).get("version") == 4
        and catalog_count == section_count == len(set(sections))
        and catalog_count <= int(policy["max_slices"])
        and [int(row["id"]) for row in rows] == list(range(section_count))
        and slice_cap == projection["runtime_slice_cap_bytes"]
        and int(storage["size"]) == storage_path.stat().st_size
        and int(storage["size"]) <= bank_capacity
        and storage["sha256"] == bind(storage_path)["sha256"]
        and int(overflow["used"]) == overflow_path.stat().st_size
        and int(overflow["used"]) <= int(overflow["capacity"])
        and int(overflow["capacity"])
            == int(overflow["limit"]) - int(overflow["address"])
        and overflow["sha256"] == bind(overflow_path)["sha256"]
        and session["abi"]["sha256"] == bind(profile_path)["sha256"]
        and session["config_header"]["sha256"] == bind(header_path)["sha256"],
        "candidate Session manifest/contract capacity identity red",
    )

    section_evidence: list[dict[str, Any]] = []
    for row in rows:
        section = truth.section(row["section"])
        region = int(row["region_id"])
        limit = int(storage["size"] if region == 0 else overflow["used"])
        require(
            region in (0, 1)
            and section.bytes == int(row["file_size"])
                == int(row["memory_size"])
            and 0 < section.bytes <= slice_cap
            and int(row["file_offset"]) + section.bytes <= limit
            and int(row["vma"]) == int(policy["common_vma"]),
            f"candidate Session section identity red: {row['section']}",
        )
        section_evidence.append({
            "id": int(row["id"]),
            "name": row["name"],
            "section": row["section"],
            "bytes": section.bytes,
            "region_id": region,
            "sha256": row["sha256"],
        })

    publication_functions = projection["publication_required_functions"]
    require(
        len(publication_rows) == 1
        and len(service_rows) == 1
        and all(truth.symbol(name).section == publication_section
                for name in publication_functions),
        "candidate publication/service semantic content identity red",
    )
    main_end = max(
        int(row["file_offset"]) + int(row["file_size"])
        for row in rows if int(row["region_id"]) == 0)
    overflow_end = max(
        (int(row["file_offset"]) + int(row["file_size"])
         for row in rows if int(row["region_id"]) == 1), default=0)
    shape_session = shape["successor_bank3_pack"]["session"]
    expected_shape_session = {
        **bind(storage_path),
        "headroom_bytes": bank_capacity - int(storage["size"]),
    }
    require(
        main_end == int(storage["size"])
        and overflow_end == int(overflow["used"])
        and shape_session == expected_shape_session,
        "candidate capacity projection differs from passed replacement shape",
    )

    append_rows = [
        row for row in rows if row["name"].startswith("c2-append-")]
    rollback_rows = [
        row["name"] for row in append_rows
        if row["name"].startswith("c2-append-rollback-")]
    service_bytes = sum(int(row["file_size"]) for row in service_rows)
    return {
        "status": "passed",
        "identity_status": "passed-current-contract-derived-capacity",
        "contract_projection": projection,
        "artifact_root": elf.parent.relative_to(ROOT).as_posix(),
        "ELF": bind(elf),
        "manifests": {
            "boot": bind(boot_manifest_path),
            "session": bind(session_manifest_path),
        },
        "publication_section": publication_section,
        "publication_semantic_functions": publication_functions,
        "slice_cap_bytes": slice_cap,
        "session_catalog_records": catalog_count,
        "session_sections": sections,
        "section_evidence": section_evidence,
        "session_capacity_domain_records": catalog_count,
        "append_records": len(append_rows),
        "session_service_records": len(service_rows),
        "session_service_bytes": service_bytes,
        "session_family_bytes": int(storage["size"]),
        "session_family_headroom_bytes": bank_capacity - int(storage["size"]),
        "session_overflow_bytes": int(overflow["used"]),
        "session_overflow_headroom_bytes":
            int(overflow["capacity"]) - int(overflow["used"]),
        "region1_rollback_sequence": rollback_rows,
        "derivation_rule": projection["rule"],
    }


def capacity_source_gate(source: str | None = None) -> dict[str, Any]:
    text = Path(__file__).read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    function = next((node for node in tree.body
                     if isinstance(node, ast.FunctionDef)
                     and node.name == "capacity_gate"), None)
    require(function is not None, "candidate capacity gate absent")
    loaded = {node.id for node in ast.walk(function)
              if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    constants = {node.value for node in ast.walk(function)
                 if isinstance(node, ast.Constant)}
    expressions = {ast.unparse(node) for node in ast.walk(function)}
    require(
        "OUT" not in loaded
        and "elf.parent" in expressions
        and "PRODUCT" not in loaded and "DIET" not in loaded
        and "SESSION_SLICE_SPECS" not in constants
        and ".lisp65_rt_c2append_publish_exports" not in constants
        and 51 not in constants
        and "catalog['slice_count']" in expressions
        and "projection['publication_section']" in expressions
        and not any("shape['runtime_slices']" in item
                    for item in expressions),
        "capacity gate reads a prior-world or ambient expectation",
    )
    return {
        "status": "passed-candidate-artifact-and-contract-inputs-only",
        "artifact_root": "elf.parent",
        "historical_publication_literals": 0,
        "historical_catalog_cardinality_literals": 0,
        "module_global_OUT_reads": 0,
        "cross_domain_shape_cardinality_reads": 0,
        "rule": (
            "A capacity expectation is derived from the bound contract of "
            "the candidate world, never a prior world's constants."),
    }


def capacity_source_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    cases = {
        "restore-module-global-OUT": (
            "root = elf.parent  # supplied candidate artifact set",
            "root = OUT  # supplied candidate artifact set"),
        "pin-historical-publication-name": (
            "publication_section = projection[\"publication_section\"]",
            "publication_section = \".lisp65_rt_c2append_publish_exports\""),
        "pin-historical-session-cardinality": (
            "catalog_count = int(catalog[\"slice_count\"])",
            "catalog_count = 51"),
        "restore-cross-domain-runtime-cardinality": (
            "and overflow_end == int(overflow[\"used\"])",
            "and overflow_end == int(overflow[\"used\"])\n"
            "        and int(shape[\"runtime_slices\"][\"count\"]) "
            "== len(sections)"),
    }
    rejected: list[str] = []
    for name, (old, new) in cases.items():
        require(old in source, f"capacity source mutation anchor absent: {name}")
        mutant = source.replace(old, new, 1)
        try:
            capacity_source_gate(mutant)
        except CapacityIdentityError:
            rejected.append(name)
    require(rejected == list(cases), "capacity source mutation survived")
    return rejected


def live_shape_fixture_gate(source: str | None = None) -> dict[str, Any]:
    text = Path(__file__).read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    fixture = next((node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "live_shape_fixture"), None)
    collector = next((node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "collect"), None)
    require(fixture is not None and collector is not None,
            "independent live-shape fixture seam absent")
    fixture_expressions = {ast.unparse(node) for node in ast.walk(fixture)}
    collector_calls = {ast.unparse(node.func) for node in ast.walk(collector)
                       if isinstance(node, ast.Call)}
    collector_expressions = {ast.unparse(node) for node in ast.walk(collector)}
    require(
        "load(LIVE_SHAPE_AUTHORITY)" in fixture_expressions
        and "LINK97_ELF" not in fixture_expressions
        and "live_shape_fixture" in collector_calls
        and "shape = live_shape_fixture()" in collector_expressions
        and "artifact_shape" not in collector_calls,
        "live-shape fixture is self-derived or not independently supplied",
    )
    return {
        "status": "passed-independent-live-shape-fixture",
        "authority": bind(LIVE_SHAPE_AUTHORITY),
        "fixture_input": "bound-r5-stopped-state-live-shape",
        "candidate_artifact_reads": 0,
        "rule": (
            "A fixture must consume an independently supplied live shape; "
            "a shape derived by the fixture from the candidate under test "
            "is a tautology and is rejected."),
    }


def live_shape_fixture_mutations() -> list[str]:
    source = Path(__file__).read_text(encoding="utf-8")
    cases = {
        "self-derive-live-shape-from-candidate": (
            "def collect() -> dict[str, Any]:\n"
            "    shape = live_shape_fixture()",
            "def collect() -> dict[str, Any]:\n"
            "    shape = artifact_shape(LINK97_ELF)"),
        "derive-fixture-from-candidate-ELF": (
            "evidence = load(LIVE_SHAPE_AUTHORITY)",
            "evidence = artifact_shape(LINK97_ELF)"),
    }
    rejected: list[str] = []
    for name, (old, new) in cases.items():
        require(old in source, f"live-shape mutation anchor absent: {name}")
        mutant = source.replace(old, new, 1)
        try:
            live_shape_fixture_gate(mutant)
        except CapacityIdentityError:
            rejected.append(name)
    require(rejected == list(cases), "tautological live-shape fixture survived")
    return rejected


def capacity_integration_gate(
        canonical_source: str | None = None,
        replacement_source: str | None = None,
        replay_source: str | None = None) -> dict[str, Any]:
    texts = {
        "canonical": (CANONICAL_SOURCE.read_text(encoding="utf-8")
                      if canonical_source is None else canonical_source),
        "replacement": (REPLACEMENT_SOURCE.read_text(encoding="utf-8")
                        if replacement_source is None else replacement_source),
        "replay": (REPLAY_SOURCE.read_text(encoding="utf-8")
                   if replay_source is None else replay_source),
    }
    trees = {name: ast.parse(text) for name, text in texts.items()}
    canonical = next((node for node in trees["canonical"].body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "fresh_session_capacity_gate"), None)
    postlink = next((node for node in trees["canonical"].body
                     if isinstance(node, ast.FunctionDef)
                     and node.name == "fresh_current_product_postlink_gate"),
                    None)
    replacement = next((node for node in trees["replacement"].body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "replacement_gates"), None)
    replay = next((node for node in trees["replay"].body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "post_link_replay"), None)
    require(all(node is not None
                for node in (canonical, postlink, replacement, replay)),
            "capacity integration entrypoint absent")
    canonical_calls = {ast.unparse(node.func) for node in ast.walk(canonical)
                       if isinstance(node, ast.Call)}
    replacement_calls = {ast.unparse(node.func) for node in ast.walk(replacement)
                         if isinstance(node, ast.Call)}
    replay_calls = [node for node in ast.walk(replay)
                    if isinstance(node, ast.Call)
                    and ast.unparse(node.func) == "base.replacement_gates"]
    replay_keywords = ({item.arg: ast.unparse(item.value)
                        for item in replay_calls[0].keywords}
                       if len(replay_calls) == 1 else {})
    postlink_constants = {node.value for node in ast.walk(postlink)
                          if isinstance(node, ast.Constant)}
    postlink_expressions = {ast.unparse(node) for node in ast.walk(postlink)}
    require(
        "CAPACITY_IDENTITY.capacity_gate" in canonical_calls
        and "qualifier" in replacement_calls
        and replay_keywords.get("capacity_qualifier")
            == "can.fresh_session_capacity_gate",
        "candidate replay is not routed through the inverted capacity stage",
    )
    require(
        not ({51, 52, 1956, 2032, 64926, 65536} & postlink_constants)
        and "passed-current-v4-two-region-session-aggregate"
            not in postlink_constants
        and "session_manifest['catalog']['slice_count']"
            in postlink_expressions
        and "int(overflow['limit']) - int(overflow['address'])"
            in postlink_expressions
        and "capacity['identity_status']" in postlink_expressions,
        "post-link capacity consumer pins prior-world expectations",
    )
    return {
        "status": "passed-current-build-and-replay-route-one-inverted-stage",
        "canonical_delegate": "CAPACITY_IDENTITY.capacity_gate",
        "replacement_seam": "capacity_qualifier",
        "replay_qualifier": "can.fresh_session_capacity_gate",
        "postlink_consumer": "manifest-and-capacity-identity-derived",
        "historical_default_preserved_for_historical_callers": True,
    }


def capacity_integration_mutations() -> list[str]:
    canonical = CANONICAL_SOURCE.read_text(encoding="utf-8")
    replay = REPLAY_SOURCE.read_text(encoding="utf-8")
    canonical_anchor = "return CAPACITY_IDENTITY.capacity_gate(shape, elf)"
    replay_anchor = (
        "            capacity_qualifier=can.fresh_session_capacity_gate,\n")
    require(canonical_anchor in canonical and replay_anchor in replay,
            "capacity integration mutation anchor absent")
    replay_prefix, replay_separator, replay_suffix = replay.rpartition(
        replay_anchor)
    require(bool(replay_separator), "capacity replay route anchor absent")
    cases = {
        "restore-canonical-prior-world-stage": (
            canonical.replace(canonical_anchor,
                              "return LINK50.BASE.CONS.capacity_gate(shape, elf)",
                              1), None),
        "drop-replay-capacity-identity-route": (
            None, replay_prefix + replay_suffix),
    }
    rejected: list[str] = []
    for name, (canonical_mutant, replay_mutant) in cases.items():
        try:
            capacity_integration_gate(
                canonical_source=canonical_mutant,
                replay_source=replay_mutant)
        except CapacityIdentityError:
            rejected.append(name)
    require(rejected == list(cases), "capacity integration mutation survived")
    consumer_cases = {
        "pin-postlink-session-cardinality": (
            "expected_records = int(session_manifest[\"catalog\"][\"slice_count\"])",
            "expected_records = 51"),
        "pin-postlink-overflow-capacity": (
            "overflow_capacity = int(overflow[\"limit\"]) - int(overflow[\"address\"])",
            "overflow_capacity = 2032"),
        "pin-postlink-capacity-status": (
            "and capacity[\"status\"] == \"passed\"",
            "and capacity[\"status\"] == "
            "\"passed-current-v4-two-region-session-aggregate\""),
    }
    for name, (old, new) in consumer_cases.items():
        require(old in canonical,
                f"capacity consumer mutation anchor absent: {name}")
        try:
            capacity_integration_gate(
                canonical_source=canonical.replace(old, new, 1))
        except CapacityIdentityError:
            rejected.append(name)
    require(rejected == [*cases, *consumer_cases],
            "capacity consumer mutation survived")
    return rejected


def collect() -> dict[str, Any]:
    shape = live_shape_fixture()
    result = capacity_gate(shape, LINK97_ELF)
    return {
        "format": "lisp65-candidate-capacity-identity-inversion-v1",
        "recorded_on": "2026-08-11",
        "status": "passed-Link-97-current-contract-capacity-inversion",
        "capacity": result,
        "independent_live_shape": shape,
        "source_gate": capacity_source_gate(),
        "fixture_gate": live_shape_fixture_gate(),
        "integration_gate": capacity_integration_gate(),
        "authorities": {
            "tool": git_bind(CAPACITY_RECORDER_HEAD, Path(__file__)),
            "first_red": bind(FIRST_RED),
            "live_shape_first_red": bind(LIVE_SHAPE_AUTHORITY),
            "candidate_ELF": bind(LINK97_ELF),
            "canonical_product": git_bind(
                CANONICAL_CAPACITY_AUTHORITY_HEAD, CANONICAL_SOURCE),
            "replacement_gate": bind(REPLACEMENT_SOURCE),
            "replay_driver": bind(REPLAY_SOURCE),
        },
        "claim_limit": (
            "Host-only qualification of the frozen Link-97 capacity stage. "
            "No completion, compilation, link, media or hardware claim."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    capacity = value.get("capacity", {})
    projection = capacity.get("contract_projection", {})
    current_projection = candidate_contract_projection()
    current_shape = live_shape_fixture()
    require(
        value.get("format") == "lisp65-candidate-capacity-identity-inversion-v1"
        and value.get("status")
            == "passed-Link-97-current-contract-capacity-inversion"
        and capacity.get("status") == "passed"
        and capacity.get("identity_status")
            == "passed-current-contract-derived-capacity"
        and projection == current_projection
        and capacity.get("publication_section")
            == current_projection["publication_section"]
        and capacity.get("publication_semantic_functions")
            == current_projection["publication_required_functions"]
        and capacity.get("session_catalog_records")
            == len(capacity.get("session_sections", []))
            == len(set(capacity.get("session_sections", [])))
        and capacity.get("session_catalog_records")
            == len(capacity.get("section_evidence", []))
        and capacity.get("session_family_headroom_bytes", -1) >= 0
        and capacity.get("session_overflow_headroom_bytes", -1) >= 0
        and value.get("independent_live_shape") == current_shape
        and value.get("source_gate") == capacity_source_gate()
        and value.get("fixture_gate") == live_shape_fixture_gate()
        and value.get("integration_gate") == capacity_integration_gate(),
        "candidate capacity identity receipt drift",
    )
    if verify:
        require(value.get("capacity")
                == capacity_gate(current_shape, LINK97_ELF)
                and value.get("authorities") == {
                    "tool": git_bind(CAPACITY_RECORDER_HEAD, Path(__file__)),
                    "first_red": bind(FIRST_RED),
                    "live_shape_first_red": bind(LIVE_SHAPE_AUTHORITY),
                    "candidate_ELF": bind(LINK97_ELF),
                    "canonical_product": git_bind(
                        CANONICAL_CAPACITY_AUTHORITY_HEAD, CANONICAL_SOURCE),
                    "replacement_gate": bind(REPLACEMENT_SOURCE),
                    "replay_driver": bind(REPLAY_SOURCE),
                }, "candidate capacity artifact authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "receipt-pin-historical-publication-name": lambda x: x["capacity"].update(
            publication_section=".lisp65_rt_c2append_publish_exports"),
        "receipt-pin-historical-session-cardinality": lambda x: x["capacity"].update(
            session_catalog_records=51),
        "drop-current-session-section": lambda x: x["capacity"]
            ["session_sections"].pop(),
        "drop-publication-semantic-function": lambda x: x["capacity"]
            ["publication_semantic_functions"].pop(),
        "overflow-main-session-bank": lambda x: x["capacity"].update(
            session_family_headroom_bytes=-1),
        "overflow-session-region1": lambda x: x["capacity"].update(
            session_overflow_headroom_bytes=-1),
        "replace-contract-projection": lambda x: x["capacity"]
            ["contract_projection"].update(status="historical"),
        "confuse-live-shape-52-with-union-62": lambda x: x
            ["independent_live_shape"]["runtime_slices"].update(count=62),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate, verify=False)
        except CapacityIdentityError:
            rejected.append(name)
    require(rejected == list(cases), "capacity identity mutation survived")
    return [*capacity_source_mutations(), *live_shape_fixture_mutations(),
            *capacity_integration_mutations(), *rejected]


def selftest() -> int:
    capacity_source_gate()
    capacity_source_mutations()
    live_shape_fixture_gate()
    live_shape_fixture_mutations()
    capacity_integration_gate()
    capacity_integration_mutations()
    value = collect()
    mutations(value)
    print("candidate capacity identity selftest: PASS "
          f"session={value['capacity']['session_catalog_records']} "
          f"headroom={value['capacity']['session_family_headroom_bytes']}")
    return 0


def capture() -> int:
    value = collect()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("candidate capacity identity capture: PASS "
          f"session={value['capacity']['session_catalog_records']} "
          f"headroom={value['capacity']['session_family_headroom_bytes']}")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value),
            "capacity identity mutation receipt drift")
    print("candidate capacity identity check: PASS "
          f"session={value['capacity']['session_catalog_records']} "
          f"headroom={value['capacity']['session_family_headroom_bytes']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "check", "selftest"))
    args = parser.parse_args()
    return {"capture": capture, "check": check,
            "selftest": selftest}[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
