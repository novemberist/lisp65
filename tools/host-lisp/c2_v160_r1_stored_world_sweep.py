#!/usr/bin/env python3
"""Inventory stored-world expectations on the frozen R1 post-link chain."""

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
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
FINAL_RED = ARCH / (
    "c2.3-v1.6-abort-driver-relocation-witness-conversion-card-final-red.json")
RECEIPT = ARCH / "c2.3-v1.6-r1-stored-world-sweep-receipt.json"
ELF = ROOT / (
    "build/c2.3/v1.6-abort-driver-relocation-witness-conversion-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "b6e6feba"
RECORDED_ON = "2026-08-19"
FORMAT = "lisp65-c2-v160-r1-stored-world-sweep-v1"
STATUS = "PASS: R1 POST-LINK STORED-WORLD INVENTORY COMPLETE"

# This is the actual delegation order reached by R1's fresh _scope/_accept
# children.  Modules without a leaf check only configure and delegate.
CHAIN = (
    "c2_v160_abort_driver_relocation_card",
    "c2_v21_wysiwyg_input_card",
    "c2_v21_probe_oracle_root_padding_replacement_card",
    "c2_v21_probe_oracle_root_card",
    "c2_v21_full_span_convergence_card",
    "c2_v21_phase9_abi_fix_replacement_card",
    "c2_v21_phase9_abi_fix_card",
    "c2_v21_map_mask_fix_card",
    "c2_v21_product_loading_liveness_card",
    "c2_v21_dependent_vma_replacement_card",
    "c2_v21_postlink_schema_replacement_card",
    "c2_v21_guard_invariant_card",
    "c2_v21_wrapper_contract_replacement_card",
    "c2_v21_expectation_shape_card",
    "c2_v21_workbench_capacity_card",
    "c2_v21_pinned_constant_card",
    "c2_v21_local_return_identity_card",
    "c2_v21_text_recovery_replacement_card",
    "c2_v21_text_recovery_card",
    "c2_v21_cpu_transport_shrink_card",
    "c2_v21_cpu_transport_replacement_card",
    "c2_v21_cpu_transport_card",
    "c2_v20_phase02b_header_consumption_replacement_card",
    "c2_v20_phase02b_header_consumption_card",
    "c2_v20_source_oracle_replacement3_card",
    "c2_v20_source_authoritative_oracle_card",
)

CPU_REPLACEMENT = HOST / "c2_v21_cpu_transport_replacement_card.py"
MAP_REPLACEMENT = HOST / "c2_v20_map_tuple_fix_replacement_card.py"
MAP_CARD = HOST / "c2_v20_map_tuple_fix_card.py"
ORACLE = HOST / "c2_v20_source_authoritative_oracle_card.py"
DEPENDENT = HOST / "c2_v21_dependent_vma_replacement_card.py"
R1 = HOST / "c2_v160_abort_driver_relocation.py"


class SweepError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SweepError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").replace("`", "").split())
    for token in ("host-only stored-world sweep", "entire post-link consumer",
                  "enumeration against red evidence only",
                  "one collective conversion card"):
        require(token in text, f"stored-world sweep authority absent: {token}")
    return value


def function(path: Path, name: str, source: str | None = None) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8") if source is None else source)
    rows = [node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique function absent: {path.name}:{name}")
    return rows[0]


def expressions(path: Path, name: str, source: str | None = None) -> set[str]:
    return {ast.unparse(row) for row in ast.walk(function(path, name, source))}


def chain_gate() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name in CHAIN:
        path = HOST / f"{name}.py"
        require(path.is_file(), f"post-link chain member absent: {name}")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {row.name for row in tree.body if isinstance(row, ast.FunctionDef)}
        expected = (["scope_child", "acceptance_child"]
                    if name != "c2_v21_cpu_transport_replacement_card"
                    else ["scope_child", "acceptance_child",
                          "dynamic_configuration_gate"])
        require(all(item in functions for item in expected),
                f"post-link entry missing: {name}")
        rows.append({"module": name, "entries": expected, "source": bind(path)})
    return {"status": "passed-explicit-post-link-delegation-closure",
            "module_count": len(rows), "modules": rows,
            "leaf_scope": "c2_v20_source_authoritative_oracle_card.scope_child",
            "leaf_acceptance":
                "c2_v20_source_authoritative_oracle_card.acceptance_child",
            "post_producer_tail":
                "c2_v21_cpu_transport_replacement_card.dynamic_configuration_gate"}


def source_gate(overrides: dict[str, str] | None = None) -> dict[str, Any]:
    sources = {path.name: path.read_text(encoding="utf-8") for path in
               (CPU_REPLACEMENT, MAP_REPLACEMENT, MAP_CARD, ORACLE, DEPENDENT)}
    if overrides:
        sources.update(overrides)
    cpu = expressions(CPU_REPLACEMENT, "dynamic_configuration_gate",
                      sources[CPU_REPLACEMENT.name])
    scope = expressions(MAP_REPLACEMENT, "single_implementation_gate",
                        sources[MAP_REPLACEMENT.name])
    scope_source = expressions(MAP_CARD, "source_scope_gate",
                               sources[MAP_CARD.name])
    tuple_gate = expressions(MAP_CARD, "linked_tuple_gate",
                             sources[MAP_CARD.name])
    oracle = expressions(ORACLE, "linked_oracle_gate", sources[ORACLE.name])
    far = expressions(ORACLE, "far_payload_gate", sources[ORACLE.name])
    accept = expressions(ORACLE, "acceptance_child", sources[ORACLE.name])
    dependent = expressions(DEPENDENT, "acceptance_child",
                            sources[DEPENDENT.name])
    require(
        "[(row['name'], row['selected']) for row in rows] == "
        "[('mapped-far-content-convergence', True), "
        "('map-cpu-library-read', True)]" in cpu
        and "rows[1]['sources'] == ['src/optional/c2_map_cpu_read.s']" in cpu,
        "first exact-list/cardinality site escaped the sweep")
    require(
        "len(selected) == 1" in scope
        and "selected[0]['sources'].count(" in "\n".join(scope)
        and "src/optional/c2_mapped_far_service_v2.s" in
            sources[MAP_REPLACEMENT.name],
        "scope implementation stored-world site escaped the sweep")
    require(
        "corrected['sources'] == ['src/c2_mapped_far_convergence.s', "
        "'src/optional/c2_mapped_far_service_v2.s']" in scope_source,
        "scope source-pair stored-world site escaped the sweep")
    require(
        "body == expected" in tuple_gate
        and "service.value == 31196" in tuple_gate
        and "(far.address, far.bytes) == (30898, 874)" in tuple_gate
        and "first_store == bytes.fromhex('a9048d00c0')" in tuple_gate,
        "MAP tuple stored-world identity site escaped the sweep")
    require("section.bytes == len(raw) == end - start == 874" in far,
            "far-payload stored size escaped the sweep")
    require("records == 6" in oracle
            and "struct.unpack_from('<H', c2d, 12)[0] == 6" in oracle,
            "oracle image-cardinality sites escaped the sweep")
    require("comparison['allocatable_sections'] == 103" in accept
            and "comparison['fixed_boundary_symbols'] == 27" in accept,
            "base Golden cardinalities escaped the sweep")
    for expression in (
            "comparison.get('allocatable_sections') == 103",
            "comparison.get('dependent_fixed_vmas') == 101",
            "comparison.get('dependent_free_derived_vmas') == 2",
            "comparison.get('fixed_boundary_symbols') == 27"):
        require(expression in dependent,
                f"dependent-VMA cardinality escaped the sweep: {expression}")
    return {"status": "passed-all-known-stored-world-sites-present",
            "site_count": 8}


def linked_facts() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    far = truth.section(".lisp65_c2_mapped_far_service")
    enter = truth.symbol("c2_mapped_far_enter")
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    raw = truth.section_bytes(far.name)
    store = bytes.fromhex("a9048d00c0")
    offsets = [at for at in range(len(raw)) if raw.startswith(store, at)]
    require(far.bytes == 1382 and service.value == 0x7A31
            and enter.bytes == 19 and offsets == [0x3A],
            "frozen R1 ELF identity drift")
    return {"ELF": bind(ELF), "far_service_bytes": far.bytes,
            "service_entry_vma": f"0x{service.value:04x}",
            "descriptor_store_offsets": offsets,
            "map_enter_bytes": enter.bytes}


def inventory() -> list[dict[str, Any]]:
    return [
        {"id": "post-producer.source-owner-exact-list", "stage": "produce-tail",
         "class": "exact registry cardinality and order",
         "stored": ["mapped-far-content-convergence", "map-cpu-library-read"],
         "candidate": ["mapped-far-content-convergence",
                       "map-cpu-library-read", "v160-input-capture"],
         "conversion": "identity-classify every candidate-derived row; no exact list",
         "message_fix": "report extra/missing identities, not 'CPU owner omitted'"},
        {"id": "scope.single-implementation-old-successor", "stage": "scope",
         "class": "exact selected count and stored source membership",
         "stored": {"selected_count": 1,
                    "source": "src/optional/c2_mapped_far_service_v2.s"},
         "candidate": {"selected_registry_count": 3,
                    "owner": "mapped-far-content-convergence",
                    "sources": [
                        "src/optional/c2_mapped_far_convergence_full_span.s",
                        "src/optional/c2_mapped_far_service_v2.s"]},
         "conversion": "resolve the named owner and all implementation members from the candidate projection"},
        {"id": "scope.source-pair-old-successor", "stage": "scope",
         "class": "stored ordered source pair",
         "stored": ["src/c2_mapped_far_convergence.s",
                    "src/optional/c2_mapped_far_service_v2.s"],
         "candidate": ["src/optional/c2_mapped_far_convergence_full_span.s",
                       "src/optional/c2_mapped_far_service_v2.s"],
         "conversion": "candidate-derived membership, order-insensitive unless consumed"},
        {"id": "acceptance.map-tuple-snapshot", "stage": "acceptance",
         "class": "stored emitted body/address/size/offset snapshot",
         "stored": {"service_entry_vma": "0x79dc", "far_service_bytes": 874,
                    "descriptor_store_offset": 0x32},
         "candidate": {"service_entry_vma": "0x7a31", "far_service_bytes": 1382,
                       "descriptor_store_offset": 0x3a},
         "conversion": "retain decoded A=$40/X=$82 hardware invariant; derive emitted identity"},
        {"id": "acceptance.far-payload-size", "stage": "acceptance",
         "class": "stored section extent", "stored": 874, "candidate": 1382,
         "conversion": "ELF section/LMA symbols plus fixed 1499-byte arena contract"},
        {"id": "acceptance.oracle-image-count", "stage": "acceptance",
         "class": "stored image cardinality", "stored": 6,
         "candidate": "derive from bound shelf/C2D headers and manifest inventory",
         "conversion": "cross-check candidate-derived domains, never literal six"},
        {"id": "acceptance.base-golden-cardinalities", "stage": "acceptance",
         "class": "stored result counts", "stored": {"sections": 103,
                    "boundaries": 27},
         "candidate": "derive counts from the bound Golden/result projection",
         "conversion": "validate set equality and report derived cardinality"},
        {"id": "acceptance.dependent-vma-cardinalities", "stage": "acceptance-tail",
         "class": "stored result partition counts", "stored": {"sections": 103,
                    "fixed": 101, "derived": 2, "boundaries": 27},
         "candidate": "derive partitions from reviewed Golden v4 projection",
         "conversion": "validate partition/set identities, not historical counts"},
    ]


def exclusions() -> list[dict[str, str]]:
    return [
        {"id": "map-tuple-A40-X82", "classification": "hardware semantic invariant"},
        {"id": "far-service-arena-1499", "classification": "capacity contract"},
        {"id": "phase02a-arena-1792", "classification": "capacity contract"},
        {"id": "phase02a-timeout-64", "classification": "priced timing contract"},
        {"id": "definition-count-equals-one", "classification":
            "uniqueness invariant; not whole-registry cardinality"},
    ]


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    require(red["status"] == "FINAL RED: R1 WITNESS-CONVERSION RETURNS TO OWNER"
            and red["retry_authorized"] is False
            and red["artifacts"]["ELF"] == bind(ELF),
            "frozen R1 Final Red authority drift")
    sites = inventory()
    return {"format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
            "claim_limit": "Read-only enumeration over frozen Red evidence; not qualification or acceptance.",
            "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
                "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
            "chain": chain_gate(), "source_gate": source_gate(),
            "linked_facts": linked_facts(), "inventory": sites,
            "inventory_count": len(sites), "reviewed_exclusions": exclusions(),
            "collective_card_checklist": [row["id"] for row in sites],
            "disposition": {"collective_cards_authorized": 1,
                "collective_cards_consumed": 0,
                "every_inventory_row_must_be_converted": True},
            "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
                "driver": bind(DRIVER)},
            "next": "one collective conversion card; any Red returns to owner"}


def validate(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "R1 stored-world sweep receipt drift")


def mutations() -> list[str]:
    base = {path.name: path.read_text(encoding="utf-8") for path in
            (CPU_REPLACEMENT, MAP_REPLACEMENT, MAP_CARD, ORACLE, DEPENDENT)}
    cases: dict[str, tuple[str, str, str]] = {
        "hide-exact-list": (CPU_REPLACEMENT.name,
            "[(row[\"name\"], row[\"selected\"]) for row in rows] == [\n"
            "            (\"mapped-far-content-convergence\", True),\n"
            "            (\"map-cpu-library-read\", True)]", "expected_rows"),
        "hide-old-far-size": (ORACLE.name, "end - start == 874", "end - start"),
        "hide-dependent-count": (DEPENDENT.name,
            "comparison.get(\"dependent_fixed_vmas\") == 101", "True"),
    }
    rejected: list[str] = []
    for name, (role, old, new) in cases.items():
        require(old in base[role], f"sweep mutation anchor absent: {name}")
        mutant = dict(base); mutant[role] = mutant[role].replace(old, new, 1)
        try:
            source_gate(mutant)
        except (SweepError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "stored-world sweep omission mutation survived")
    return rejected


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["inventory_count"] == 8
            and value["collective_card_checklist"] ==
                [row["id"] for row in value["inventory"]]
            and mutations() == ["hide-exact-list", "hide-old-far-size",
                                "hide-dependent-count"],
            "stored-world sweep completeness drift")
    print("v1.6 R1 stored-world sweep: PASS chain=26 inventory=8 mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("print", "check"))
    action = parser.parse_args().action
    if action == "print":
        print(canonical(derive()).decode(), end="")
    else:
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
