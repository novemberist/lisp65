#!/usr/bin/env python3
"""Replay Link-112 qualification after the additive projection repair."""

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

import c2_asm_leaf_abi_gate as ABI  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_full_span_convergence_card as CARD  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_resume as PHASE9_RESUME  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402
import c2_v21_terminal_screen_map_authority_rebind as MAP_REBIND  # noqa: E402
import c2_v21_text_recovery_replacement_card as COMPLETION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
CARD_FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
MANIFEST = BUILD / "wplto/runtime-overlays-session-final.json"
REPLAY = BUILD / "artifact-only-replay"
PREFLIGHT = REPLAY / "preflight.json"
PRODUCER_RESULT = REPLAY / "producer-tail-result.json"
SCOPE_RESULT = REPLAY / "owner-scope-result.json"
ACCEPTANCE_RESULT = REPLAY / "artifact-acceptance.json"
ABI_REPORT = REPLAY / "c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-full-span-projection-artifact-replay-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-full-span-projection-artifact-replay-final-red.json")
RESUME_RED = ARCH / (
    "c2.3-v2.1-full-span-projection-artifact-replay-resume-red.json")
ACCEPTANCE_RED = ARCH / (
    "c2.3-v2.1-full-span-projection-artifact-replay-acceptance-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "fa46b234"
RESUME_AUTHORIZATION = "993372a7"
ACCEPTANCE_AUTHORIZATION = "ab3b3d53"
TAIL_AUTHORIZATION = "957295ef"
RECORDED_ON = "2026-08-16"
ORIGINAL_PHASE9_INSTALL = PHASE9_RESUME.install_successors


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("full projection **additively**",
                  "artifact-only qualification replay",
                  "no wplto", "no relink", "no card"):
        require(token in text, f"projection replay authority absent: {token}")
    return value


def resume_authorization() -> dict[str, Any]:
    value = git_binding(RESUME_AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("scope expectation derives from the complete",
                  "successor identities included", "old-name pin",
                  "resume-safe continuation from the scope step",
                  "no wplto", "no relink", "no card"):
        require(token in text, f"scope resume authority absent: {token}")
    return value


def acceptance_authorization() -> dict[str, Any]:
    value = git_binding(ACCEPTANCE_AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("entry derives from the elf symbol",
                  "store is located semantically", "unique-occurrence rule",
                  "resume continues **directly at acceptance**",
                  "no repeated scope", "no wplto", "link or card"):
        require(token in text, f"Acceptance resume authority absent: {token}")
    return value


def tail_authorization() -> dict[str, Any]:
    value = git_binding(TAIL_AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("headroom derives from the arena contract",
                  "413 becomes mutation-red",
                  "only the outer qualification tail",
                  "existing green acceptance receipt",
                  "no repeated scope or acceptance",
                  "no wplto, link or card"):
        require(token in text, f"qualification-tail authority absent: {token}")
    return value


def final_red() -> dict[str, Any]:
    value = load(CARD_FINAL_RED)
    require(
        value.get("status") == "FINAL RED: full-span card returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting") == {
            "WPLTO_runs": 1, "cards_authorized": 1, "cards_consumed": 1,
            "completion_runs": 0, "device_contacts": 0, "media_builds": 0,
            "product_link_attempts": 1},
        "Link-112 Final Red authority drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = final_red()["artifacts"]
    current = {name: bind(ROOT / row["path"]) for name, row in expected.items()}
    require(current == expected, "frozen Link-112 artifact SHA drift")
    return current


def _function_text(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next((row for row in tree.body
                 if isinstance(row, ast.FunctionDef) and row.name == name), None)
    require(node is not None, f"function absent: {name}")
    return ast.unparse(node)


def projection_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (Path(CARD.__file__).read_text(encoding="utf-8")
              if source_override is None else source_override)
    configured = _function_text(source, "configure_full_span_source")
    required = (
        "ORIGINAL_CONFIGURE_FIX_SOURCE()",
        "component = CONFIG.configure(PRODUCT)",
        "projection = PRODUCT.source_owner_scope_gate",
        "projection['components'] = {'full_span_convergence': component}",
        "return projection",
    )
    require(
        all(token in configured for token in required)
        and configured.index("component = CONFIG.configure(PRODUCT)")
            < configured.index("projection = PRODUCT.source_owner_scope_gate")
            < configured.index(
                "projection['components'] = {'full_span_convergence': component}")
            < configured.index("return projection"),
        "full-span wrapper substitutes or fails to add its component report")
    return {"status": "PASS: complete projection plus additive component report",
            "identity_fields_replaced": 0, "component_reports_added": 1}


def projection_source_mutations() -> list[str]:
    source = Path(CARD.__file__).read_text(encoding="utf-8")
    cases = {
        "restore-component-substitution": source.replace(
            "    return projection\n", "    return component\n", 1),
        "drop-additive-component": source.replace(
            "    projection[\"components\"] = "
            "{\"full_span_convergence\": component}\n", "", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            projection_source_gate(candidate)
        except (ReplayError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "projection-return mutation survived")
    return rejected


def successor_scope_gate(
        projection_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bind the historical Scope selftest to the current owner identity."""
    configured = (CARD.configure_full_span_source()
                  if projection_override is None else projection_override)
    complete = {row["name"]: row for row in configured.get("scopes", [])}
    require(set(complete) == {"mapped-far-content-convergence",
                              "map-cpu-library-read"}
            and all(row.get("selected") is True for row in complete.values()),
            "complete candidate source-owner projection is not selected")
    result = CARD.PRODUCT.source_owner_scope_selftest()
    selected = {row["name"]: row for row in result["selected"]["scopes"]}
    candidate = complete["mapped-far-content-convergence"]
    corrected = selected["mapped-far-content-convergence"]
    require(
        corrected["selected"] is True
        and corrected["defines"] == candidate["defines"]
        and corrected["sources"] == candidate["sources"]
        and result["mutations_rejected"] == 3,
        "successor-aware Scope identity differs from candidate projection")
    return {**result, "post_configuration_real_consumer": configured,
            "successor_identity": {"authority": "complete-candidate-projection",
                "name": candidate["name"], "defines": candidate["defines"],
                "sources": candidate["sources"]}}


def scope_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    configured = _function_text(source, "successor_scope_gate")
    require(
        "complete = {row['name']: row for row in configured.get('scopes', [])}"
            in configured
        and "candidate = complete['mapped-far-content-convergence']"
            in configured
        and "corrected['sources'] == candidate['sources']" in configured
        and "src/c2_mapped_far_convergence.s" not in configured,
        "Scope checker pins an old body name instead of candidate identity")
    return {"status": "PASS: Scope derives successor identity from candidate",
            "historical_body_name_pins": 0}


def scope_mutations() -> list[str]:
    trial = deepcopy(source_projection())
    row = next(item for item in trial["scopes"]
               if item["name"] == "mapped-far-content-convergence")
    row["sources"] = ["src/c2_mapped_far_convergence.s",
                      "src/optional/c2_mapped_far_service_v2.s"]
    rejected: list[str] = []
    try:
        successor_scope_gate(trial)
    except ReplayError:
        rejected.append("restore-old-body-name")
    require(rejected == ["restore-old-body-name"],
            "historical Scope body-name mutation survived")
    return rejected


def successor_linked_tuple_gate(elf: Path) -> dict[str, Any]:
    """Decode the emitted tuple and derive every internal service position."""
    tuple_gate = PHASE9_RESUME.TUPLE
    truth = ElfTruth.read(elf, llvm_readobj=tuple_gate.READOBJ,
                          include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    enter_section = truth.section(enter.section)
    enter_raw = truth.section_bytes(enter.section)
    body = enter_raw[enter.value - enter_section.address:
                     enter.value - enter_section.address + enter.bytes]
    expected = bytes.fromhex("48da5aa940a282a000a3805ceaa3007afa6860")
    decoded = tuple_gate.FIX.decode_low(0x40, 0x82)
    far = truth.section(tuple_gate.SECTION)
    far_raw = truth.section_bytes(far.name)
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    load_start = truth.symbol(
        "__lisp65_c2_mapped_far_service_load_start").value
    physical_entry = tuple_gate.FIX.map_low(service.value, decoded)
    emitted_physical_entry = load_start + service.value - far.address
    pattern = bytes.fromhex("a9048d00c0")
    stores = [index for index in range(len(far_raw) - len(pattern) + 1)
              if far_raw[index:index + len(pattern)] == pattern]
    candidate_end = far.address + far.bytes
    require(
        body == expected and enter.bytes == 19
        and service.section == far.name
        and physical_entry == emitted_physical_entry
        and tuple_gate.FIX.map_low(0x3185, decoded) == 0x3185
        and far.address == tuple_gate.ARENA_START and far.bytes > 0
        and candidate_end <= tuple_gate.ARENA_END
        and len(stores) == 1,
        "emitted candidate tuple, entry or unique descriptor store drift")
    store_offset = stores[0]
    return {
        "status": "passed-primary-semantics-candidate-derived-tuple",
        "symbol": "c2_mapped_far_enter", "VMA": f"0x{enter.value:04X}",
        "bytes": body.hex(),
        "tuple": {"A": "0x40", "X": "0x82", "Y": "0x00", "Z": "0x80"},
        "decode": decoded,
        "service_entry": {"symbol": service.name,
            "candidate_VMA": f"0x{service.value:04X}",
            "candidate_physical": f"0x{physical_entry:05X}",
            "derivation": "ELF-symbol-plus-decoded-MAP-tuple"},
        "service_entry_physical": f"0x{physical_entry:05X}",
        "block1_unchanged": True,
        "far_service": {"section": tuple_gate.SECTION, "start": far.address,
            "candidate_derived_bytes": far.bytes,
            "candidate_derived_end_exclusive": candidate_end,
            "arena_end_exclusive": tuple_gate.ARENA_END,
            "arena_capacity_bytes": tuple_gate.ARENA_END - tuple_gate.ARENA_START,
            "candidate_headroom_bytes": tuple_gate.ARENA_END - candidate_end,
            "size_source": "emitted-candidate-section-table",
            "fixed_size_expectation": False},
        "first_descriptor_store": {"physical_PC":
                f"0x{load_start + store_offset:08X}",
            "candidate_offset": f"0x{store_offset:02X}",
            "bytes": pattern.hex(), "effect": "STA $C000 <= $04",
            "occurrences": len(stores),
            "derivation": "unique-emitted-instruction-sequence"},
    }


def validate_successor_tuple(value: dict[str, Any], elf: Path) -> None:
    expected = successor_linked_tuple_gate(elf)
    if not (value == expected
            and value["tuple"] == {
                "A": "0x40", "X": "0x82", "Y": "0x00", "Z": "0x80"}
            and value["decode"]["mapped_low_half_blocks"] == [3]
            and value["decode"]["physical_offset"] == "0x24000"
            and value["far_service"]["fixed_size_expectation"] is False):
        # The inherited mutation runner catches the tuple gate's public error
        # type.  A replay-local error here would turn an expected rejected
        # mutant into a harness First Red.
        raise PHASE9_RESUME.TUPLE.TupleGateError(
            "successor-derived linked tuple evidence drift")


def acceptance_position_mutations() -> list[str]:
    value = successor_linked_tuple_gate(ELF)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-0x79dc-entry-pin": lambda x: x["service_entry"].update(
            candidate_VMA="0x79DC", candidate_physical="0x2B9DC"),
        "restore-0x32-store-pin": lambda x: x["first_descriptor_store"].update(
            candidate_offset="0x32", physical_PC="0x0002B8E4"),
        "accept-two-descriptor-stores": lambda x: x["first_descriptor_store"].update(
            occurrences=2),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_successor_tuple(trial, ELF)
        except PHASE9_RESUME.TUPLE.TupleGateError:
            rejected.append(name)
    require(rejected == list(cases), "Acceptance position mutation survived")
    return rejected


def acceptance_source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    configured = _function_text(source, "successor_linked_tuple_gate")
    require(
        "physical_entry = tuple_gate.FIX.map_low(service.value, decoded)"
            in configured
        and "emitted_physical_entry = load_start + service.value - far.address"
            in configured
        and "stores = [index for index in range" in configured
        and "len(stores) == 1" in configured
        and "service.value == 31196" not in configured
        and "far_raw[50:55]" not in configured,
        "Acceptance checker retains an internal entry/store position pin")
    return {"status": "PASS: entry and store derive from emitted candidate",
            "historical_position_pins": 0, "unique_store_required": True}


def freight_headroom_gate(
        acceptance_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Derive freight headroom from the arena and emitted candidate extents."""
    acceptance = (load(ACCEPTANCE_RESULT) if acceptance_override is None
                  else acceptance_override)
    capacity = acceptance.get("VMA_golden", {}).get(
        "mapped_far_service_capacity", {})
    far = acceptance.get("far_payload", {})
    start = capacity.get("start")
    end = capacity.get("end_exclusive")
    candidate_end = capacity.get("candidate_max_end_exclusive")
    require(all(isinstance(item, int) for item in (start, end, candidate_end)),
            "freight capacity lacks candidate-derived integer extents")
    arena_bytes = end - start
    candidate_bytes = candidate_end - start
    headroom = end - candidate_end
    require(
        acceptance.get("status") == "PASS"
        and 0 <= candidate_bytes <= arena_bytes
        and capacity.get("candidate_headroom_bytes") == headroom
        and far.get("arena_capacity_bytes") == arena_bytes
        and far.get("candidate_derived_bytes") == candidate_bytes
        and far.get("candidate_headroom_bytes") == headroom
        and far.get("candidate_derived_cpu_end_exclusive") == candidate_end,
        "freight headroom is not arena-minus-emitted-candidate")
    return {
        "status": "PASS: freight headroom derived from candidate extents",
        "authority": "arena-contract-minus-emitted-candidate",
        "arena": {"start": start, "end_exclusive": end,
                  "capacity_bytes": arena_bytes},
        "candidate": {"end_exclusive": candidate_end,
                      "bytes": candidate_bytes,
                      "headroom_bytes": headroom},
        "historical_headroom_expectations": 0,
    }


def freight_headroom_mutations() -> list[str]:
    acceptance = load(ACCEPTANCE_RESULT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-413-headroom": lambda x: x["VMA_golden"][
            "mapped_far_service_capacity"].update(
                candidate_headroom_bytes=413),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(acceptance); mutate(trial)
        try:
            freight_headroom_gate(trial)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "historical freight headroom survived")
    return rejected


def freight_headroom_source_gate(
        source_override: str | None = None) -> dict[str, Any]:
    source = (DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    gate = _function_text(source, "freight_headroom_gate")
    require(
        "headroom = end - candidate_end" in gate
        and "candidate_bytes = candidate_end - start" in gate
        and "== 413" not in gate,
        "outer freight wrapper retains a historical headroom pin")
    return {"status": "PASS: outer freight tail is candidate-derived",
            "historical_headroom_pins": 0}


def full_span_acceptance_child() -> int:
    """Run the existing Acceptance with candidate-derived full-span freight."""
    oracle = PHASE9_RESUME.ORACLE
    require(oracle.BUILD.is_dir() and not oracle.ACCEPTANCE_RESULT.exists(),
            "full-span acceptance child lifecycle drift")
    paths = oracle.artifact_paths()
    oracle.BASE.PRODUCT.configure_e000_reopening()
    oracle.BASE.PRODUCT.configure_full_map_ownership()
    oracle.BASE.PRODUCT.configure_low_resident_lma_reset()
    oracle.BASE.CRC.BUILD = oracle.BUILD
    comparison = oracle.BASE.INV.compare_elf(paths["elf"])
    linker = oracle.BASE.PRODUCT.low_resident_lma_reset_gate(
        paths["linker"].read_text(encoding="utf-8"))
    delivery = oracle.BASE.CRC.delivered_bytes_gate(paths["elf"], paths["prg"])
    oracle.BASE.CRC.validate_delivery(delivery, paths["elf"], paths["prg"])
    tuple_gate = successor_linked_tuple_gate(paths["elf"])
    far_payload = PHASE9_RESUME.TUPLE.far_payload_gate(paths["elf"])
    artifact = CARD.artifact_contract()
    value = {"status": "PASS", "pid": os.getpid(),
        "VMA_golden": comparison, "low_resident_LMA_reset": linker,
        "delivered_bytes": delivery,
        "delivery_mutations_rejected": oracle.BASE.CRC.delivery_mutations(
            delivery, paths["elf"], paths["prg"]),
        "linked_MAP_tuple": tuple_gate,
        "linked_MAP_mutations_rejected": PHASE9_RESUME.TUPLE.linked_mutations(
            tuple_gate, paths["elf"]),
        "far_payload": far_payload,
        "source_authoritative_oracle": oracle.linked_oracle_gate(paths["elf"])}
    require(
        comparison["allocatable_sections"] == 103
        and comparison["fixed_boundary_symbols"] == 25
        and comparison["freight_derived_boundary_symbols"] == 3
        and comparison["mapped_far_service_capacity"][
            "candidate_headroom_bytes"] == artifact["headroom_bytes"]
        and tuple_gate["far_service"]["candidate_derived_bytes"] ==
            artifact["exact_bytes"]
        and tuple_gate["far_service"]["candidate_headroom_bytes"] ==
            artifact["headroom_bytes"]
        and far_payload["candidate_derived_bytes"] == artifact["exact_bytes"]
        and tuple_gate["far_service"]["arena_capacity_bytes"] ==
            artifact["capacity_bytes"],
        "full-span Acceptance did not consume candidate-derived authorities")
    oracle.ACCEPTANCE_RESULT.write_bytes(canonical(value))
    return 0


def install_acceptance_successors() -> None:
    ORIGINAL_PHASE9_INSTALL()
    tuple_gate = PHASE9_RESUME.TUPLE
    tuple_gate.linked_tuple_gate = successor_linked_tuple_gate
    tuple_gate.validate_linked_tuple = validate_successor_tuple
    PHASE9_RESUME.MAP_CARD.linked_tuple_gate = successor_linked_tuple_gate
    PHASE9_RESUME.MAP_CARD.validate_linked_tuple = validate_successor_tuple
    PHASE9_RESUME.ORACLE.BASE.linked_tuple_gate = successor_linked_tuple_gate
    PHASE9_RESUME.ORACLE.acceptance_child = full_span_acceptance_child


def configure() -> dict[str, Any]:
    PHASE9_RESUME.install_successors = install_acceptance_successors
    install_acceptance_successors()
    CANDIDATE.placement_contract = MAP_REBIND.placement_contract
    CARD.PRODUCER_RESULT = PRODUCER_RESULT
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.ABI_REPORT = ABI_REPORT
    projection = CARD.configure()
    install_acceptance_successors()
    CARD.MAP_FIX.source_scope_gate = successor_scope_gate
    return projection


def source_projection() -> dict[str, Any]:
    value = configure()
    rows = {row["name"]: row for row in value.get("scopes", [])}
    component = value.get("components", {}).get("full_span_convergence", {})
    require(
        value.get("status") == "passed-define-and-source-owner-scope-closure"
        and set(rows) == {"mapped-far-content-convergence",
                          "map-cpu-library-read"}
        and all(row.get("selected") is True for row in rows.values())
        and rows["mapped-far-content-convergence"]["sources"] == [
            "src/optional/c2_mapped_far_convergence_full_span.s",
            "src/optional/c2_mapped_far_service_v2.s"]
        and rows["map-cpu-library-read"]["sources"] == [
            "src/optional/c2_map_cpu_read.s"]
        and component.get("candidate_body") ==
            "src/optional/c2_mapped_far_convergence_full_span.s"
        and component.get("single_body_owner") is True,
        "additive source-owner projection is incomplete")
    return value


def candidate_tail() -> dict[str, Any]:
    configure()
    report = ABI.audit_elf(ELF, out=ABI_REPORT, require_bank3_chain=True)
    derived = report["ELF_derived_C_called_inventory"]
    require(derived["status"] == ABI.ELF_DERIVED_C_CALLED_STATUS
            and derived["unclassified_C_called_functions"] == [],
            "frozen Link-112 ELF ABI closure red")
    section = COMPLETION.PRODUCT.section_table(ELF).get(
        COMPLETION.PRODUCT.VERIFIER_BINDING_SECTION)
    family_stage = bool(section and section["bytes"] == (
        COMPLETION.PRODUCT.VERIFIER_BINDING_BYTES
        + COMPLETION.PRODUCT.FAMILY_STAGE_BINDING_BYTES))
    require(family_stage, "candidate family-stage binding identity absent")
    COMPLETION.PRODUCT.FAMILY_STAGE_BINDINGS = family_stage
    local = CANDIDATE.linked_gate(ELF, MANIFEST)
    completion = COMPLETION.completion_gate(ELF)
    linked = CARD.linked_product()
    projection = source_projection()
    objects = BUILD / "wplto/.canonical-objects-resident-island-seed"
    CPU_objects = sorted(path.name for path in objects.iterdir()
                         if "c2_map_cpu_read" in path.name)
    full_span_objects = sorted(path.name for path in objects.iterdir()
                               if "convergence_full_span" in path.name)
    require(
        local["reader"]["bytes"] == 189
        and local["ownership"]["violations"] == []
        and linked["mapped_far"]["bytes"] == 1248
        and linked["mapped_far"]["headroom_bytes"] == 251
        and linked["terminal_screen_lease"]["post_phase_visible"] is False
        and completion["status"] ==
            "PASS: publish-last consumed candidate identity"
        and len(CPU_objects) == len(full_span_objects) == 1,
        "artifact-only Link-112 producer tail is red")
    return {
        "candidate_configuration": {"family_stage_bindings": family_stage},
        "ABI_vocabulary": {"status": derived["status"],
            "transitive_functions": derived["transitive_function_count"],
            "unclassified": derived["unclassified_C_called_functions"]},
        "local_return": local,
        "local_return_mutations": CANDIDATE.linked_mutations(local),
        "completion_identity": completion,
        "completion_mutations": ["reject-historical-0xb98a"],
        "linked_product": linked,
        "linked_mutations": CARD.linked_mutations(linked),
        "source_owner_projection": projection,
        "owner_objects": {"CPU_reader": CPU_objects,
                          "full_span": full_span_objects},
    }


def preflight_value() -> dict[str, Any]:
    frozen = frozen_artifacts()
    tail = candidate_tail()
    golden = GOLD.compare_elf(ELF)
    require(golden["dependent_fixed_vmas"] == 101
            and golden["dependent_free_derived_vmas"] == 2
            and golden["mapped_far_service_capacity"][
                "candidate_headroom_bytes"] == 251,
            "artifact-only Link-112 Golden preflight red")
    return {"format": "lisp65-c2.3-v2.1-full-span-projection-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: frozen Link-112 artifacts armed for qualification replay",
        "authority": {"owner": authorization(),
            "Final_Red": bind(CARD_FINAL_RED),
            "full_span_fix": bind(CARD.FIX.RECEIPT), "driver": bind(DRIVER)},
        "frozen_artifacts": frozen, "producer_tail": tail,
        "projection_source_gate": projection_source_gate(),
        "projection_source_mutations_rejected": projection_source_mutations(),
        "golden": {"fixed_vmas": 101, "derived_vmas": 2,
                   "mapped_far_headroom_bytes": 251},
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": "Post-link qualification only; frozen product bytes are read-only."}


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "full-span artifact-replay preflight drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("map"),
        "drop-CPU-owner": lambda x: x["producer_tail"][
            "source_owner_projection"]["scopes"].pop(),
        "restore-first-byte-body": lambda x: x["producer_tail"][
            "linked_product"]["mapped_far"].update(bytes=1086),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "full-span replay mutation survived")
    return rejected


def preflight() -> None:
    require(not PREFLIGHT.exists() and not PRODUCER_RESULT.exists()
            and not SCOPE_RESULT.exists() and not ACCEPTANCE_RESULT.exists()
            and not RECEIPT.exists(),
            "full-span projection artifact replay is one-shot")
    REPLAY.mkdir(parents=True, exist_ok=True)
    value = preflight_value(); value["mutations_rejected"] = mutations(value)
    PREFLIGHT.write_bytes(canonical(value))
    print("2.1 full-span projection replay: PREFLIGHT PASS frozen=9 replay=0/1")


def write_producer_tail() -> dict[str, Any]:
    original = load(BUILD / "producer-result.json")
    require(original.get("status") == "PASS"
            and "post_configuration_source_owner_gate" not in original,
            "Link-112 producer-tail input drift")
    for name, fact in frozen_artifacts().items():
        require(original["artifacts"].get(name) == fact,
                f"producer-tail frozen artifact drift: {name}")
    tail = candidate_tail()
    result = deepcopy(original)
    result["artifact_replay_pid"] = os.getpid()
    result["v21_text_recovery"] = tail["local_return"]
    result["v21_text_recovery_mutations"] = tail["local_return_mutations"]
    result["candidate_completion_identity"] = tail["completion_identity"]
    result["candidate_completion_mutations"] = tail["completion_mutations"]
    result["post_configuration_source_owner_gate"] = tail[
        "source_owner_projection"]
    result["CPU_reader_owner_objects"] = tail["owner_objects"]["CPU_reader"]
    PRODUCER_RESULT.write_bytes(canonical(result))
    return result


def scope_child() -> int:
    configure()
    return CARD.scope_child()


def acceptance_child() -> int:
    configure()
    return CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh full-span artifact-only {action} red:\n{result.stdout}")


def replay() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(rejected == mutations(expected), "replay mutation receipt drift")
    require(not PRODUCER_RESULT.exists() and not SCOPE_RESULT.exists()
            and not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "full-span artifact-replay output exists")
    before = frozen_artifacts()
    producer = write_producer_tail()
    run_child("_scope"); scope = load(SCOPE_RESULT)
    run_child("_accept"); acceptance = load(ACCEPTANCE_RESULT)
    after = frozen_artifacts()
    require(after == before, "artifact replay changed frozen Link-112 bytes")
    comparison = acceptance.get("VMA_golden", {})
    tail = candidate_tail()
    mapped = {row["name"]: row for row in producer[
        "post_configuration_source_owner_gate"]["scopes"]}
    require(
        len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
        and scope.get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and acceptance.get("far_payload", {}).get(
            "candidate_derived_bytes") == 1248
        and acceptance.get("far_payload", {}).get(
            "candidate_headroom_bytes") == 251
        and mapped["mapped-far-content-convergence"]["selected"] is True
        and mapped["map-cpu-library-read"]["selected"] is True
        and tail["linked_product"]["mapped_far"]["bytes"] == 1248,
        "artifact-only Link-112 Scope/Acceptance replay red")
    receipt = {"format": persisted["format"], "recorded_on": RECORDED_ON,
        "status": "PASS: Link-112 additive-projection artifact qualification",
        "authority": {"owner": authorization(),
            "Final_Red": bind(CARD_FINAL_RED),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": tail, "scope": scope, "acceptance": acceptance,
        "process_isolation": {"producer_tail": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "projection_source": projection_source_mutations(),
            "linked": tail["linked_mutations"]},
        "next": "Completion and same-world media closure, then D2 resume",
        "claim_limit": "Artifact qualification only; Completion/media/device remain zero."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 full-span projection replay: PASS WPLTO=0 link=0 card=0 bytes=1248")


def resume() -> None:
    resume_authorization(); scope_source_gate(); scope_mutations()
    red = load(FINAL_RED)
    require(
        red.get("status") ==
            "FIRST RED: Link-112 artifact qualification returns to owner"
        and red.get("retry_authorized") is False
        and red.get("execution_accounting", {}).get("scope_attempts") == 1,
        "Link-112 Scope First Red authority drift")
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    # The authorized Scope successor changes this replay driver only.  The
    # original preflight remains the authority for every product input.
    expected["authority"]["driver"] = persisted["authority"]["driver"]
    validate_preflight(persisted, expected)
    require(rejected == mutations(expected), "resume mutation receipt drift")
    require(PRODUCER_RESULT.exists() and not SCOPE_RESULT.exists()
            and not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "Link-112 Scope resume boundary drift")
    producer = load(PRODUCER_RESULT)
    require(producer.get("status") == "PASS"
            and producer.get("post_configuration_source_owner_gate", {}).get(
                "status") == "passed-define-and-source-owner-scope-closure",
            "persisted Link-112 producer tail is not green")
    before = frozen_artifacts()
    run_child("_scope"); scope = load(SCOPE_RESULT)
    run_child("_accept"); acceptance = load(ACCEPTANCE_RESULT)
    after = frozen_artifacts()
    require(after == before, "Scope resume changed frozen Link-112 bytes")
    comparison = acceptance.get("VMA_golden", {})
    tail = candidate_tail()
    mapped = {row["name"]: row for row in producer[
        "post_configuration_source_owner_gate"]["scopes"]}
    require(
        len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
        and scope.get("status") == "PASS"
        and scope.get("gate", {}).get("successor_identity", {}).get(
            "authority") == "complete-candidate-projection"
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and acceptance.get("far_payload", {}).get(
            "candidate_derived_bytes") == 1248
        and acceptance.get("far_payload", {}).get(
            "candidate_headroom_bytes") == 251
        and mapped["mapped-far-content-convergence"]["selected"] is True
        and mapped["map-cpu-library-read"]["selected"] is True
        and tail["linked_product"]["mapped_far"]["bytes"] == 1248,
        "resumed Link-112 Scope/Acceptance is red")
    receipt = {"format": persisted["format"], "recorded_on": RECORDED_ON,
        "status": "PASS: Link-112 successor-aware artifact qualification resumed",
        "authority": {"original_owner": authorization(),
            "resume_owner": resume_authorization(),
            "card_Final_Red": bind(CARD_FINAL_RED),
            "replay_First_Red": bind(FINAL_RED),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_resumes_authorized": 1,
            "scope_resumes_run": 1, "scope_attempts_total": 2,
            "acceptance_runs": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": tail, "scope": scope, "acceptance": acceptance,
        "process_isolation": {"resume_parent": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": {"preflight": rejected,
            "projection_source": projection_source_mutations(),
            "old_scope_body_name": scope_mutations(),
            "linked": tail["linked_mutations"]},
        "next": "Completion and same-world media closure, then D2 resume",
        "claim_limit": "Artifact qualification only; Completion/media/device remain zero."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 full-span projection replay: RESUME PASS scope=green "
          "acceptance=green WPLTO=0 link=0 card=0")


def acceptance_resume() -> None:
    acceptance_authorization(); acceptance_source_gate()
    acceptance_position_mutations()
    red = load(RESUME_RED)
    require(
        red.get("status") == "RESUME RED: Link-112 Acceptance returns to owner"
        and red.get("retry_authorized") is False
        and red.get("attribution", {}).get("load_entry", {}).get(
            "candidate") == "0x7a31"
        and red.get("attribution", {}).get("descriptor_store", {}).get(
            "candidate_offset") == "0x3a",
        "Link-112 Acceptance-position Red authority drift")
    require(PRODUCER_RESULT.exists() and SCOPE_RESULT.exists()
            and not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "Link-112 direct Acceptance resume boundary drift")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    require(producer.get("status") == "PASS" and scope.get("status") == "PASS"
            and scope.get("gate", {}).get("selected_owner") ==
                "mapped-far-content-convergence"
            and scope.get("gate", {}).get("historical_body_selected") is False
            and producer.get("post_configuration_source_owner_gate", {}).get(
                "components", {}).get("full_span_convergence", {}).get(
                    "candidate_body") ==
                "src/optional/c2_mapped_far_convergence_full_span.s",
            "persisted producer/Scope authority is not green")
    before = frozen_artifacts()
    run_child("_accept"); acceptance = load(ACCEPTANCE_RESULT)
    after = frozen_artifacts()
    require(after == before, "Acceptance resume changed frozen Link-112 bytes")
    comparison = acceptance.get("VMA_golden", {})
    tuple_gate = acceptance.get("linked_MAP_tuple", {})
    far = acceptance.get("far_payload", {})
    tail = candidate_tail()
    require(
        acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and comparison.get("mapped_far_service_capacity", {}).get(
            "candidate_headroom_bytes") == 251
        and tuple_gate.get("service_entry", {}).get("candidate_VMA") == "0x7A31"
        and tuple_gate.get("service_entry", {}).get(
            "candidate_physical") == "0x2BA31"
        and tuple_gate.get("first_descriptor_store", {}).get(
            "candidate_offset") == "0x3A"
        and tuple_gate.get("first_descriptor_store", {}).get(
            "occurrences") == 1
        and far.get("candidate_derived_bytes") == 1248
        and far.get("candidate_headroom_bytes") == 251
        and tail["linked_product"]["mapped_far"]["bytes"] == 1248,
        "direct Link-112 Acceptance resume is red")
    receipt = {"format": "lisp65-c2.3-v2.1-full-span-projection-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-112 emitted-position Acceptance resumed",
        "authority": {"original_owner": authorization(),
            "scope_resume_owner": resume_authorization(),
            "acceptance_resume_owner": acceptance_authorization(),
            "card_Final_Red": bind(CARD_FINAL_RED),
            "replay_First_Red": bind(FINAL_RED),
            "Acceptance_Red": bind(RESUME_RED), "preflight": bind(PREFLIGHT),
            "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_resumes_authorized": 1,
            "scope_resumes_run": 1, "scope_attempts_total": 2,
            "acceptance_resumes_authorized": 1,
            "acceptance_resumes_run": 1, "acceptance_attempts_total": 2,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "producer_tail": tail, "scope": scope, "acceptance": acceptance,
        "process_isolation": {"resume_parent": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": len({os.getpid(), scope["pid"],
                                  acceptance["pid"]}) == 3},
        "mutations_rejected": {"projection_source":
                projection_source_mutations(),
            "old_scope_body_name": scope_mutations(),
            "acceptance_positions": acceptance_position_mutations(),
            "linked": tail["linked_mutations"]},
        "next": "Completion and same-world media closure, then D2 resume",
        "claim_limit": "Artifact qualification only; Completion/media/device remain zero."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 full-span projection replay: ACCEPTANCE RESUME PASS "
          "WPLTO=0 link=0 card=0 bytes=1248")


def qualification_tail() -> None:
    """Resume only the outer tail over persisted green Acceptance evidence."""
    tail_authorization(); freight_headroom_source_gate()
    red = load(ACCEPTANCE_RED)
    require(
        red.get("status") ==
            "ACCEPTANCE RED: Link-112 freight wrapper returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red.get("attribution", {}).get("historical_headroom_bytes") == 413
        and red.get("attribution", {}).get("candidate_headroom_bytes") == 251
        and red.get("attribution", {}).get("inner_acceptance_reusable") is True,
        "Link-112 freight-tail Red authority drift")
    require(PRODUCER_RESULT.exists() and SCOPE_RESULT.exists()
            and ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "Link-112 outer qualification-tail boundary drift")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(
        producer.get("status") == "PASS"
        and scope.get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and red.get("inner_acceptance") == acceptance,
        "persisted Link-112 inner qualification evidence drift")
    before = frozen_artifacts()
    headroom = freight_headroom_gate(acceptance)
    rejected = freight_headroom_mutations()
    after = frozen_artifacts()
    require(
        before == after
        and headroom["candidate"] == {
            "end_exclusive": 32146, "bytes": 1248,
            "headroom_bytes": 251}
        and headroom["arena"] == {
            "start": 30898, "end_exclusive": 32397,
            "capacity_bytes": 1499},
        "outer freight qualification tail is red")
    receipt = {
        "format": "lisp65-c2.3-v2.1-full-span-projection-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-112 candidate-derived freight tail qualified",
        "authority": {"original_owner": authorization(),
            "scope_resume_owner": resume_authorization(),
            "acceptance_resume_owner": acceptance_authorization(),
            "qualification_tail_owner": tail_authorization(),
            "card_Final_Red": bind(CARD_FINAL_RED),
            "replay_First_Red": bind(FINAL_RED),
            "Acceptance_position_Red": bind(RESUME_RED),
            "freight_wrapper_Red": bind(ACCEPTANCE_RED),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_resumes_run": 1,
            "scope_attempts_total": 2,
            "acceptance_resumes_run": 1,
            "acceptance_attempts_total": 3,
            "qualification_tail_resumes_authorized": 1,
            "qualification_tail_resumes_run": 1,
            "scope_repeated_in_tail": 0,
            "acceptance_repeated_in_tail": 0,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": before,
        "frozen_artifacts_after": after,
        "persisted_producer_tail": bind(PRODUCER_RESULT),
        "persisted_scope": scope,
        "persisted_acceptance": acceptance,
        "freight_headroom": headroom,
        "mutations_rejected": {"historical_headroom": rejected},
        "next": "Completion and same-world media closure, then D2 resume",
        "claim_limit": "Outer qualification tail only; Scope and Acceptance were not repeated; Completion/media/device remain zero.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 full-span projection replay: QUALIFICATION TAIL PASS "
          "headroom=251 WPLTO=0 link=0 card=0")


def check() -> None:
    if RECEIPT.exists():
        value = load(RECEIPT); frozen = frozen_artifacts()
        require(
            value.get("status") ==
                "PASS: Link-112 candidate-derived freight tail qualified"
            and value.get("execution_accounting", {}).get("WPLTO_runs") == 0
            and value.get("execution_accounting", {}).get("product_links") == 0
            and value.get("execution_accounting", {}).get("cards_consumed") == 0
            and value.get("execution_accounting", {}).get(
                "scope_resumes_run") == 1
            and value.get("execution_accounting", {}).get(
                "acceptance_resumes_run") == 1
            and value.get("execution_accounting", {}).get(
                "qualification_tail_resumes_run") == 1
            and value.get("execution_accounting", {}).get(
                "scope_repeated_in_tail") == 0
            and value.get("execution_accounting", {}).get(
                "acceptance_repeated_in_tail") == 0
            and value.get("frozen_artifacts_before") == frozen
            and value.get("frozen_artifacts_after") == frozen
            and value.get("freight_headroom", {}).get("candidate", {}).get(
                "headroom_bytes") == 251
            and value.get("mutations_rejected", {}).get(
                "historical_headroom") == ["restore-413-headroom"],
            "full-span projection artifact-replay receipt drift")
        print("2.1 full-span projection replay: CHECK PASS artifacts=frozen")
        return
    if ACCEPTANCE_RED.exists():
        value = load(ACCEPTANCE_RED)
        require(
            value.get("status") ==
                "ACCEPTANCE RED: Link-112 freight wrapper returns to owner"
            and value.get("retry_authorized") is False
            and value.get("owner_disposition_required") is True
            and value.get("inner_acceptance", {}).get("status") == "PASS"
            and value.get("frozen_artifacts_before") == frozen_artifacts()
            and value.get("frozen_artifacts_after") == frozen_artifacts(),
            "full-span projection freight-wrapper red drift")
        print("2.1 full-span projection replay: CHECK ACCEPTANCE RED")
        return
    if RESUME_RED.exists():
        value = load(RESUME_RED)
        require(
            value.get("status") ==
                "RESUME RED: Link-112 Acceptance returns to owner"
            and value.get("retry_authorized") is False
            and value.get("owner_disposition_required") is True
            and value.get("frozen_artifacts_before") == frozen_artifacts()
            and value.get("frozen_artifacts_after") == frozen_artifacts()
            and value.get("execution_accounting", {}).get("scope_green") is True
            and value.get("execution_accounting", {}).get(
                "acceptance_attempts") == 1,
            "full-span projection Acceptance resume red drift")
        print("2.1 full-span projection replay: CHECK RESUME RED")
        return
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(
            value.get("status") ==
                "FIRST RED: Link-112 artifact qualification returns to owner"
            and value.get("retry_authorized") is False
            and value.get("owner_disposition_required") is True
            and value.get("frozen_artifacts_before") == frozen_artifacts()
            and value.get("frozen_artifacts_after") == frozen_artifacts(),
            "full-span projection artifact-replay Final Red drift")
        print("2.1 full-span projection replay: CHECK FINAL RED")
        return
    raise ReplayError("full-span projection artifact replay has no outcome")


def record_final_red(error: Exception) -> None:
    if not PREFLIGHT.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    frozen = frozen_artifacts()
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-full-span-projection-replay-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FIRST RED: Link-112 artifact qualification returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_attempts": 1,
            "acceptance_runs": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "frozen_artifacts_before": frozen, "frozen_artifacts_after": frozen,
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"owner": authorization(), "Final_Red": bind(CARD.FINAL_RED),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "claim_limit": "Scope stopped; Acceptance, Completion, media and device remain zero.",
    }))


def record_resume_red(error: Exception) -> None:
    if not SCOPE_RESULT.exists() or RECEIPT.exists() or RESUME_RED.exists():
        return
    scope = load(SCOPE_RESULT)
    frozen = frozen_artifacts()
    RESUME_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-full-span-projection-resume-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "RESUME RED: Link-112 Acceptance returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attribution": {
            "class": "HISTORICAL-INTERNAL-POSITION-PINS",
            "MAP_tuple": {"A": "0x40", "X": "0x82",
                          "status": "unchanged-and-correct"},
            "arena": {"candidate_bytes": 1248, "capacity_bytes": 1499,
                      "headroom_bytes": 251, "status": "within-contract"},
            "load_entry": {"historical": "0x79dc", "candidate": "0x7a31",
                           "candidate_physical": "0x0002ba31"},
            "descriptor_store": {"historical_offset": "0x32",
                                 "candidate_offset": "0x3a",
                                 "candidate_bytes": "a9048d00c0",
                                 "candidate_occurrences": 1}},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_resumes_authorized": 1,
            "scope_resumes_run": 1, "scope_attempts_total": 2,
            "scope_green": scope.get("status") == "PASS",
            "acceptance_attempts": 1, "acceptance_green": False,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "scope": scope, "frozen_artifacts_before": frozen,
        "frozen_artifacts_after": frozen,
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"original_owner": authorization(),
            "scope_resume_owner": resume_authorization(),
            "card_Final_Red": bind(CARD_FINAL_RED),
            "replay_First_Red": bind(FINAL_RED), "preflight": bind(PREFLIGHT),
            "driver": bind(DRIVER)},
        "claim_limit": "Scope is green; Acceptance, Completion, media and device remain zero.",
    }))


def record_acceptance_red(error: Exception) -> None:
    if not ACCEPTANCE_RESULT.exists() or RECEIPT.exists() \
            or ACCEPTANCE_RED.exists():
        return
    acceptance = load(ACCEPTANCE_RESULT)
    frozen = frozen_artifacts()
    capacity = acceptance.get("VMA_golden", {}).get(
        "mapped_far_service_capacity", {})
    require(acceptance.get("status") == "PASS"
            and capacity.get("candidate_headroom_bytes") == 251,
            "inner Acceptance is not reusable green evidence")
    ACCEPTANCE_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-full-span-freight-wrapper-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "ACCEPTANCE RED: Link-112 freight wrapper returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attribution": {"class": "HISTORICAL-FREIGHT-HEADROOM-PIN",
            "consumer": "c2_v21_phase9_abi_fix_artifact_replay."
                        "install_freight_acceptance",
            "historical_headroom_bytes": 413,
            "candidate_headroom_bytes": 251,
            "candidate_service_bytes": 1248,
            "arena_capacity_bytes": 1499,
            "inner_acceptance_reusable": True},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "scope_resumes_run": 1,
            "scope_green": True, "acceptance_attempts_total": 3,
            "inner_acceptance_green": True, "outer_acceptance_green": False,
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "inner_acceptance": acceptance,
        "frozen_artifacts_before": frozen, "frozen_artifacts_after": frozen,
        "retry_authorized": False, "owner_disposition_required": True,
        "authority": {"original_owner": authorization(),
            "scope_resume_owner": resume_authorization(),
            "acceptance_resume_owner": acceptance_authorization(),
            "card_Final_Red": bind(CARD_FINAL_RED),
            "replay_First_Red": bind(FINAL_RED),
            "Acceptance_position_Red": bind(RESUME_RED),
            "preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "claim_limit": "Inner Acceptance is green; outer qualification, Completion, media and device remain closed.",
    }))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "replay", "resume", "acceptance-resume",
        "qualification-tail", "check",
        "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "replay": replay, "resume": resume,
     "acceptance-resume": acceptance_resume,
     "qualification-tail": qualification_tail,
     "check": check,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "replay":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"2.1 full-span replay receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "resume":
            try:
                record_resume_red(error)
            except Exception as receipt_error:
                print(f"2.1 full-span resume receipt failure: {receipt_error}",
                      file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] == "acceptance-resume":
            try:
                record_acceptance_red(error)
            except Exception as receipt_error:
                print(f"2.1 full-span Acceptance receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 full-span projection replay: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
