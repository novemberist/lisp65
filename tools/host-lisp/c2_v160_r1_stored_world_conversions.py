#!/usr/bin/env python3
"""Install the eight owner-authorized R1 stored-world conversions."""

from __future__ import annotations

import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_r1_stored_world_sweep as SWEEP  # noqa: E402
import c2_golden_layout_inversion as LAYOUT  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_CARD  # noqa: E402
import c2_v20_map_tuple_fix_replacement_card as MAP_REPLACEMENT  # noqa: E402
import c2_v20_source_authoritative_oracle_card as ORACLE  # noqa: E402
import c2_v21_cpu_transport_replacement_card as CPU_REPLACEMENT  # noqa: E402
import c2_v21_dependent_vma_replacement_card as DEPENDENT  # noqa: E402
import c2_v21_full_span_projection_artifact_replay as EMITTED  # noqa: E402
import c2_v21_phase9_candidate_derived_tuple_gate as PAYLOAD  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as V5_GOLDEN  # noqa: E402
import c2_v21_dependency_invariant_golden as V4_GOLDEN  # noqa: E402


DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-r1-stored-world-conversions-v1"
STATUS = "PASS: ALL EIGHT R1 STORED-WORLD CONVERSIONS INSTALLED"


class ConversionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConversionError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def candidate_rows() -> list[dict[str, Any]]:
    value = MAP_CARD.configure_fix_source()
    rows = value.get("scopes", [])
    require(isinstance(rows, list) and rows, "candidate source-owner registry absent")
    return rows


def classify_registry(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify every selected candidate row; never pin registry size/order."""
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row.get("name")
        require(isinstance(name, str) and name not in by_name,
                f"duplicate source-owner identity: {name}")
        require(isinstance(row.get("selected"), bool)
                and isinstance(row.get("defines"), list)
                and isinstance(row.get("sources"), list)
                and all(isinstance(item, str) for item in row["sources"]),
                f"malformed source-owner row: {name}")
        by_name[name] = row
    selected = {name: row for name, row in by_name.items() if row["selected"]}
    require("map-cpu-library-read" in selected
            and selected["map-cpu-library-read"]["sources"] ==
                ["src/optional/c2_map_cpu_read.s"],
            "candidate registry CPU owner is absent or malformed")
    require("mapped-far-content-convergence" in selected,
            "candidate registry convergence owner absent")
    return {"status": "passed-additive-candidate-registry-classification",
            "selected_identities": sorted(selected),
            "selected_count_derived": len(selected),
            "rows": rows,
            "message_contract": "reports actual selected identities"}


def dynamic_configuration_gate() -> dict[str, Any]:
    return classify_registry(candidate_rows())


def source_scope_gate() -> dict[str, Any]:
    configured = MAP_CARD.configure_fix_source()
    complete = {row["name"]: row for row in configured.get("scopes", [])}
    require("mapped-far-content-convergence" in complete,
            "candidate convergence identity absent")
    result = MAP_CARD.PRODUCT.source_owner_scope_selftest()
    selected = {row["name"]: row for row in result["selected"]["scopes"]}
    require("mapped-far-content-convergence" in selected,
            "scope selftest convergence identity absent")
    candidate = complete["mapped-far-content-convergence"]
    observed = selected["mapped-far-content-convergence"]
    require(observed["selected"] is True
            and observed["defines"] == candidate["defines"]
            and observed["sources"] == candidate["sources"]
            and result["mutations_rejected"] >= 3,
            "scope identity differs from candidate projection")
    return {**result, "post_configuration_real_consumer": configured,
            "successor_identity": {"authority": "candidate-projection",
                "name": candidate["name"], "defines": candidate["defines"],
                "sources": candidate["sources"]}}


def single_implementation_gate() -> dict[str, Any]:
    scope = source_scope_gate()
    inventory = MAP_CARD.real_asm_inventory_gate()
    rows = scope["post_configuration_real_consumer"]["scopes"]
    matches = [row for row in rows
               if row["name"] == "mapped-far-content-convergence"]
    require(len(matches) == 1 and matches[0]["selected"] is True
            and len(matches[0]["sources"]) == len(set(matches[0]["sources"]))
            and inventory["duplicate-successor-in-global-asm-domain"] ==
                "rejected",
            "candidate-named implementation ownership drift")
    return {"status": "PASS: candidate-named owner has unique bodies",
            "selected_owner": matches[0]["name"],
            "candidate_sources": matches[0]["sources"],
            "selected_registry_count_derived":
                sum(row["selected"] is True for row in rows),
            "real_global_inventory": inventory}


def linked_tuple_gate(elf: Path) -> dict[str, Any]:
    return EMITTED.successor_linked_tuple_gate(elf)


def far_payload_gate(elf: Path) -> dict[str, Any]:
    return PAYLOAD.far_payload_gate(elf)


def linked_oracle_gate(elf: Path) -> dict[str, Any]:
    shelf_path = ORACLE.BUILD / (
        "static-plane/narrow-static/product/product-shelf-v4-direct.bin")
    c2d_path = ORACLE.BUILD / (
        "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin")
    shelf = shelf_path.read_bytes(); c2d = c2d_path.read_bytes()
    shelf_records = shelf[7]
    c2d_records = struct.unpack_from("<H", c2d, 12)[0]
    images = struct.unpack_from("<H", c2d, 28)[0]
    require(shelf_records > 0 and shelf_records == c2d_records
            and 32 + shelf_records * 32 <= len(shelf)
            and images + c2d_records * 32 <= len(c2d),
            "candidate image-domain headers disagree")
    shelf_values = [ORACLE.crc16(shelf[32 + i * 32:64 + i * 32])
                    for i in range(shelf_records)]
    c2d_values = [ORACLE.crc16(c2d[images + i * 32:images + (i + 1) * 32])
                  for i in range(c2d_records)]
    needle = b"".join(struct.pack("<H", value)
                      for value in shelf_values + c2d_values)
    truth = ORACLE.ElfTruth.read(
        elf, llvm_readobj=ORACLE.READOBJ, include_section_data=True)
    section = truth.section(ORACLE.PHASE02A_SECTION)
    linked = truth.section_bytes(ORACLE.PHASE02A_SECTION)
    generated = ORACLE.artifact_paths()["generated_phase02a"]
    decoder = ORACLE.artifact_paths()["generated_decoder"]
    source = generated.read_text(encoding="utf-8")
    decoder_source = decoder.read_text(encoding="utf-8")
    require(section.bytes == len(linked) <= 1792 and linked.find(needle) >= 0
            and decoder_source.count(
                "#define C2_PHASE02A_DELIVERY_ORACLE 1") == 1
            and decoder_source.count(
                "#define C2_PHASE02A_TIMEOUT_FRAMES 64u") == 1
            and source.count("c2_phase02a_shelf_crc16:") == 1
            and source.count("c2_phase02a_c2d_crc16:") == 1
            and all(f".short 0x{value:04x}" in source
                    for value in shelf_values + c2d_values),
            "candidate-derived linked delivery oracle drift")
    return {"status": "passed-candidate-header-derived-CRC-oracle",
            "section": ORACLE.PHASE02A_SECTION,
            "VMA": f"0x{section.address:04x}", "bytes": section.bytes,
            "capacity": 1792, "reserve": 1792 - section.bytes,
            "records_per_image_derived": shelf_records,
            "shelf_crc16": [f"0x{x:04x}" for x in shelf_values],
            "c2d_crc16": [f"0x{x:04x}" for x in c2d_values],
            "oracle_offset": linked.find(needle), "timeout_frames": 64,
            "delivery_inputs": [ORACLE.bind(shelf_path), ORACLE.bind(c2d_path)],
            "generated_owner": ORACLE.bind(generated),
            "generated_decoder": ORACLE.bind(decoder)}


def golden_sets(comparison: dict[str, Any]) -> dict[str, Any]:
    require(comparison.get("comparison") in {
                "dependent-address-invariants-plus-derived-vmas-exact",
                "dependent-address-plus-freight-boundaries-exact"},
            "candidate Golden comparison identity drift")
    fixed = comparison.get("dependent_fixed_vmas")
    derived = comparison.get("dependent_free_derived_vmas")
    total = comparison.get("allocatable_sections")
    boundaries = comparison.get("fixed_boundary_symbols")
    require(all(isinstance(value, int) and value >= 0
                for value in (fixed, derived, total, boundaries))
            and fixed + derived == total,
            "candidate Golden partition/set identity drift")
    return {"allocatable_sections_derived": total,
            "dependent_fixed_vmas_derived": fixed,
            "dependent_free_derived_vmas_derived": derived,
            "fixed_boundary_symbols_derived": boundaries,
            "partition_complete": True}


def acceptance_result_path() -> Path:
    override = os.environ.get("LISP65_R1_ACCEPTANCE_RESULT")
    return Path(override) if override else ORACLE.ACCEPTANCE_RESULT


def _active_freight_union() -> tuple[list[dict[str, Any]], set[str]]:
    registries = PRODUCT.active_card_freight_registries()
    names = [name for row in registries for name in row["allocated"]]
    require(registries and len(names) == len(set(names)),
            "active card-registry union is empty or has double authority")
    return registries, set(names)


def _freight_proof_rows(layout: dict[str, Any],
                        registries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {name for registry in registries for name in registry["allocated"]}
    predecessors = {
        ".lisp65_c2_kernal_window.input_capture_main":
            ".lisp65_c2_kernal_window.reopen_gap0",
        ".lisp65_c2_kernal_window.input_capture_helper":
            ".lisp65_c2_kernal_window.reopen_gap1",
        ".lisp65_c2_kernal_window.input_consumer":
            ".lisp65_c2_kernal_window.input_capture_helper",
    }
    by_name = {row["name"]: row for row in layout["allocatable_sections"]}
    rows: list[dict[str, Any]] = []
    require(names <= set(by_name), "active card freight absent from candidate")
    for registry in registries:
        registration = registry["registration"]
        for name in sorted(registry["allocated"]):
            row = by_name[name]
            if registry["placement_gate"] == "candidate-predecessor-end":
                require(name in predecessors,
                        "additive freight predecessor authority absent")
                predecessor = by_name[predecessors[name]]
                require(row["bytes"] > 0 and
                        row["vma"] == predecessor["vma"] + predecessor["bytes"],
                        f"additive freight violates derived placement: {name}")
                proof = {"gate": "candidate-predecessor-end",
                    "predecessor": predecessors[name],
                    "relation": "section-vma-equals-predecessor-vma-plus-bytes",
                    "status": "passed"}
            else:
                placement = registration.get("physical_placement")
                require(isinstance(placement, dict),
                        "mapped additive freight placement authority absent")
                fixed = (placement.get("kind") == "fixed-contract"
                         and row["lma"] == placement.get("physical_start"))
                top = (placement.get("kind") == "bank2-top-derived"
                       and row["lma"] + row["bytes"] ==
                           placement.get("bank_end_exclusive"))
                by_name = {item["name"]: item
                           for item in layout["allocatable_sections"]}
                far = by_name.get(".lisp65_c2_mapped_far_service")
                page = (placement.get("kind") == "map-page-top-derived"
                        and far is not None
                        and row["lma"] - row["vma"] ==
                            far["lma"] - far["vma"]
                        and (row["lma"] - row["vma"]) & 0xff == 0
                        and row["lma"] + row["bytes"] <=
                            placement.get("bank_end_exclusive"))
                require(registry["placement_gate"] == "mapped-arena-contract"
                        and row["bytes"] > 0
                        and row["bytes"] <= registration["capacity_bytes"]
                        and row["vma"] == registration["cpu_start"]
                        and (fixed or top or page),
                        f"mapped additive freight violates arena contract: {name}")
                proof = {"gate": "mapped-arena-contract",
                    "relation": (
                        "candidate-section-shares-page-encodable-map-offset"
                        if page else
                        "candidate-section-ends-at-derived-bank-end"
                        if top else
                        "candidate-section-fits-fixed-mapped-arena"),
                    "status": "passed"}
            rows.append({"name": name,
                "membership_authority": registry["registry"],
                "placement_proof": proof})
    return rows


def _validate_freight_rows(rows: list[dict[str, Any]],
                           registered: set[str]) -> None:
    require({row.get("name") for row in rows} == registered,
            "additive freight proof closure differs from registration")
    forbidden = {"address", "vma", "lma", "start", "end", "value"}
    for row in rows:
        require(not (set(row) & forbidden)
                and set(row) == {"name", "membership_authority",
                                 "placement_proof"}
                and isinstance(row["membership_authority"], str)
                and row["membership_authority"]
                and isinstance(row["placement_proof"], dict)
                and not (set(row["placement_proof"]) & forbidden)
                and row["placement_proof"].get("status") == "passed"
                and row["placement_proof"].get("gate") in {
                    "candidate-predecessor-end", "mapped-arena-contract"}
                and ((row["placement_proof"].get("gate") ==
                      "candidate-predecessor-end"
                      and row["placement_proof"].get("relation") ==
                      "section-vma-equals-predecessor-vma-plus-bytes"
                      and isinstance(row["placement_proof"].get("predecessor"), str)
                      and set(row["placement_proof"]) == {
                          "gate", "predecessor", "relation", "status"})
                     or (row["placement_proof"].get("gate") ==
                         "mapped-arena-contract"
                         and row["placement_proof"].get("relation") in {
                             "candidate-section-ends-at-derived-bank-end",
                             "candidate-section-shares-page-encodable-map-offset",
                             "candidate-section-fits-fixed-mapped-arena"}
                         and set(row["placement_proof"]) == {
                             "gate", "relation", "status"})),
                f"additive freight row is an address snapshot: {row.get('name')}")


def _additive_section_closure(layout: dict[str, Any], golden: dict[str, Any],
                              registered: set[str],
                              proof_rows: list[dict[str, Any]]) -> dict[str, Any]:
    golden_names = V4_GOLDEN.all_names(golden)
    candidate_names = {row["name"] for row in layout["allocatable_sections"]}
    require(not (golden_names & registered),
            "additive freight has double Golden authority")
    require(candidate_names == golden_names | registered,
            "candidate section has neither Golden nor card-freight authority")
    _validate_freight_rows(proof_rows, registered)
    base = deepcopy(layout)
    base["allocatable_sections"] = [
        row for row in layout["allocatable_sections"]
        if row["name"] in golden_names]
    return {"base_layout": base, "golden_sections": len(golden_names),
            "candidate_sections": len(candidate_names),
            "registered_sections": sorted(registered),
            "freight_rows": proof_rows}


def _mapped_lma_successor(layout: dict[str, Any],
                          golden: dict[str, Any]
                          ) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Project an authorized derived mapped LMA without rewriting v5."""
    policy = PRODUCT.MAPPED_TENANT_LMA_POLICY
    if policy not in ("bank2-top", "map-page-top"):
        return layout, None
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    far_name = ".lisp65_c2_mapped_far_service"
    cold_name = ".lisp65_c2_mapped_product_cold"
    boundary = "__lisp65_c2_mapped_far_service_load_start"
    require(far_name in rows and cold_name in rows,
            "upper-anchor mapped tenant population incomplete")
    far, cold = rows[far_name], rows[cold_name]
    actual = layout["boundary_symbols"][boundary]
    if policy == "map-page-top":
        far_offset = far["lma"] - far["vma"]
        cold_offset = cold["lma"] - cold["vma"]
        highest_cpu_end = max(far["vma"] + far["bytes"],
                              cold["vma"] + cold["bytes"])
        require(actual == far["lma"] and far_offset == cold_offset
                and far_offset & 0xff == 0
                and highest_cpu_end + far_offset <= 0x00030000
                and highest_cpu_end + far_offset + 0x100 > 0x00030000,
                "candidate page-congruent LMA relation is not composed")
        relations = [
            "both-tenant-offsets-equal",
            "shared-offset-is-page-encodable",
            "next-page-offset-escapes-bank2"]
        authority = "candidate final-ELF LOADADDR plus map-page-top policy"
    else:
        require(actual == far["lma"]
                and far["lma"] + far["bytes"] == cold["lma"]
                and cold["lma"] + cold["bytes"] == 0x00030000,
                "candidate upper-anchor LMA relation is not composed")
        relations = [
            "far-load-start-equals-far-section-lma",
            "far-load-end-equals-product-cold-load-start",
            "product-cold-load-end-equals-bank2-end"]
        authority = "candidate final-ELF LOADADDR plus bank2-top policy"
    normalized = deepcopy(layout)
    normalized["boundary_symbols"][boundary] = (
        golden["fixed_boundary_symbols"][boundary])
    return normalized, {
        "status": "passed",
        "authority": authority,
        "boundary": boundary,
        "relations": relations,
        "golden_rewritten": False,
        "candidate_boundary_is_additive_successor": True,
    }


def mapped_lma_successor_mutations(elf: Path) -> list[str]:
    policy = PRODUCT.MAPPED_TENANT_LMA_POLICY
    if policy not in ("bank2-top", "map-page-top"):
        return []
    layout = LAYOUT.layout_from_elf(elf)
    golden = load(V5_GOLDEN.GOLDEN)
    rejected: list[str] = []
    boundary = "__lisp65_c2_mapped_far_service_load_start"
    far_name = ".lisp65_c2_mapped_far_service"
    cold_name = ".lisp65_c2_mapped_product_cold"
    mutants = {}
    stored = deepcopy(layout)
    by_name = {row["name"]: row for row in stored["allocatable_sections"]}
    by_name[far_name]["lma"] = 0x0002B8B2
    stored["boundary_symbols"][boundary] = 0x0002B8B2
    mutants["stored-far-LMA"] = stored
    broken = deepcopy(layout)
    by_name = {row["name"]: row for row in broken["allocatable_sections"]}
    by_name[cold_name]["lma"] += 1
    mutants[("broken-shared-map-offset" if policy == "map-page-top" else
             "broken-mapped-tenant-adjacency")] = broken
    if policy == "map-page-top":
        residue = deepcopy(layout)
        by_name = {row["name"]: row for row in
                   residue["allocatable_sections"]}
        by_name[far_name]["lma"] += 1
        by_name[cold_name]["lma"] += 1
        residue["boundary_symbols"][boundary] += 1
        mutants["non-page-congruent-shared-offset"] = residue
    for label, mutant in mutants.items():
        try:
            _mapped_lma_successor(mutant, golden)
        except ConversionError:
            rejected.append(label)
        else:
            raise ConversionError(
                f"mapped LMA successor mutation survived: {label}")
    return rejected


def additive_freight_mutations(elf: Path) -> list[str]:
    golden = load(V5_GOLDEN.GOLDEN)
    layout = LAYOUT.layout_from_elf(elf)
    registries, registered = _active_freight_union()
    rows = _freight_proof_rows(layout, registries)
    rejected: list[str] = []

    pinned_registries = deepcopy(registries)
    mapped_rows = [registry for registry in pinned_registries
                   if registry["placement_gate"] == "mapped-arena-contract"]
    if mapped_rows:
        mapped_rows[-1]["registration"]["physical_placement"] = {
            "kind": "fixed-contract", "physical_start": 0x0002BE8D,
            "authority": "stored predecessor world"}

    third = deepcopy(layout)
    mutant = deepcopy(third["allocatable_sections"][0])
    mutant["name"] = ".mutation.unregistered-third-category"
    third["allocatable_sections"].append(mutant)
    for label, action in (
            ("unregistered-third-category", lambda: _additive_section_closure(
                third, golden, registered, rows)),
            ("double-golden-and-card-authority", lambda: _additive_section_closure(
                layout, golden, registered | {next(iter(V4_GOLDEN.all_names(golden)))},
                rows)),
            ("address-snapshot-in-freight-row", lambda: _additive_section_closure(
                layout, golden, registered,
                [({**row, "address": 0xFD08}
                  if row["name"] == sorted(registered)[0] else row)
                 for row in rows])),
            ("omitted-active-registry", lambda: _additive_section_closure(
                layout, golden,
                registered - set(registries[-1]["allocated"]),
                [row for row in rows if row["name"] not in
                    set(registries[-1]["allocated"])])),
            ("stored-mapped-LMA", lambda: _freight_proof_rows(
                layout, pinned_registries))):
        try:
            action()
        except ConversionError:
            rejected.append(label)
        else:
            raise ConversionError(f"additive freight mutation survived: {label}")
    return rejected


def acceptance_golden_gate(elf: Path, golden: Any = V5_GOLDEN
                           ) -> dict[str, Any]:
    require(golden is V5_GOLDEN,
            "live acceptance reintroduced a pre-v5 Golden")
    additive: dict[str, Any] | None = None
    registries = PRODUCT.active_card_freight_registries()
    if registries:
        authority = load(golden.GOLDEN)
        layout = LAYOUT.layout_from_elf(elf)
        registries, registered = _active_freight_union()
        proof_rows = _freight_proof_rows(layout, registries)
        additive = _additive_section_closure(
            layout, authority, registered, proof_rows)
        base_layout = additive.pop("base_layout")
        comparison_layout, relocation = _mapped_lma_successor(
            layout, authority)
        # The additive section closure removes card freight before the Golden
        # comparison.  Carry the one reviewed boundary normalization into
        # that same base view while retaining every other candidate member.
        if relocation is not None:
            boundary = relocation["boundary"]
            base_layout["boundary_symbols"][boundary] = (
                comparison_layout["boundary_symbols"][boundary])
            additive["mapped_LMA_successor"] = relocation
            additive["mapped_LMA_mutations_rejected"] = (
                mapped_lma_successor_mutations(elf))
        comparison = golden.compare_layout(base_layout, authority)
        additive["placement_gate"] = {
            "gate": "active-card-registry-union",
            "status": "passed",
            "registries": [row["registry"] for row in registries],
            "proof_rows": proof_rows,
        }
    else:
        comparison = golden.compare_elf(elf)
    require(comparison.get("comparison") ==
                "dependent-address-plus-freight-boundaries-exact"
            and comparison.get("dependent_fixed_vmas") == 101
            and comparison.get("fixed_boundary_symbols") == 25,
            "live acceptance did not consume accepted v5")
    return {"comparison": comparison, "additive_card_freight": additive,
        "provenance": {
            "mode": "read-only-additive-successor-authority",
            "historical_dependent_vma_v4": DEPENDENT.review_authority(),
            "accepted_freight_boundary_v5": V5_GOLDEN.bind(V5_GOLDEN.RECEIPT)}}


def acceptance_golden_mutation(elf: Path) -> str:
    try:
        acceptance_golden_gate(elf, DEPENDENT.GOLD)
    except ConversionError as error:
        require(str(error) == "live acceptance reintroduced a pre-v5 Golden",
                "v4 reintroduction mutation failed for another reason")
        return "reintroduce-reviewed-v4-binding"
    raise ConversionError("v4 acceptance binding mutation survived")


def acceptance_child() -> int:
    result_path = acceptance_result_path()
    require(ORACLE.BUILD.is_dir() and not result_path.exists(),
            "acceptance child lifecycle drift")
    paths = ORACLE.artifact_paths()
    ORACLE.BASE.PRODUCT.configure_e000_reopening()
    ORACLE.BASE.PRODUCT.configure_full_map_ownership()
    ORACLE.BASE.PRODUCT.configure_low_resident_lma_reset()
    ORACLE.BASE.CRC.BUILD = ORACLE.BUILD
    golden = acceptance_golden_gate(paths["elf"])
    comparison = golden["comparison"]
    linker = ORACLE.BASE.PRODUCT.low_resident_lma_reset_gate(
        paths["linker"].read_text(encoding="utf-8"))
    delivery = ORACLE.BASE.CRC.delivered_bytes_gate(paths["elf"], paths["prg"])
    ORACLE.BASE.CRC.validate_delivery(delivery, paths["elf"], paths["prg"])
    tuple_value = linked_tuple_gate(paths["elf"])
    value = {"status": "PASS", "pid": os.getpid(),
        "VMA_golden": comparison,
        "VMA_golden_authority": golden["provenance"],
        "additive_card_freight": golden["additive_card_freight"],
        "VMA_golden_derived_shape": golden_sets(comparison),
        "low_resident_LMA_reset": linker, "delivered_bytes": delivery,
        "delivery_mutations_rejected": ORACLE.BASE.CRC.delivery_mutations(
            delivery, paths["elf"], paths["prg"]),
        "linked_MAP_tuple": tuple_value,
        "linked_MAP_mutations_rejected": EMITTED.acceptance_position_mutations(),
        "far_payload": far_payload_gate(paths["elf"]),
        "source_authoritative_oracle": linked_oracle_gate(paths["elf"])}
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(ORACLE.canonical(value))
    return 0


def dependent_acceptance_child() -> int:
    result = DEPENDENT.BASE.acceptance_child()
    result_path = acceptance_result_path()
    value = load(result_path)
    value["dependent_vma_authority"] = DEPENDENT.review_authority()
    value["freight_boundary_v5_authority"] = V5_GOLDEN.bind(
        V5_GOLDEN.RECEIPT)
    value["dependent_vma_derived_shape"] = golden_sets(value["VMA_golden"])
    result_path.write_bytes(DEPENDENT.canonical(value))
    return result


def install() -> None:
    CPU_REPLACEMENT.dynamic_configuration_gate = dynamic_configuration_gate
    MAP_CARD.source_scope_gate = source_scope_gate
    MAP_REPLACEMENT.single_implementation_gate = single_implementation_gate
    MAP_CARD.linked_tuple_gate = linked_tuple_gate
    ORACLE.BASE.linked_tuple_gate = linked_tuple_gate
    ORACLE.far_payload_gate = far_payload_gate
    ORACLE.linked_oracle_gate = linked_oracle_gate
    ORACLE.acceptance_child = acceptance_child
    DEPENDENT.acceptance_child = dependent_acceptance_child


def structural_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None \
        else source_override
    tree = ast.parse(source)
    functions = {row.name: ast.unparse(row) for row in tree.body
                 if isinstance(row, ast.FunctionDef)}
    require("== [('mapped-far-content-convergence'" not in
                functions["classify_registry"]
            and "src/c2_mapped_far_convergence.s" not in
                functions["source_scope_gate"]
            and "service.value == 31196" not in functions["linked_tuple_gate"]
            and "end - start == 874" not in functions["far_payload_gate"]
            and "range(6)" not in functions["linked_oracle_gate"]
            and "comparison['allocatable_sections'] == 103" not in
                functions["golden_sets"]
            and "comparison.get('dependent_fixed_vmas') == 101" not in
                functions["dependent_acceptance_child"],
            "stored-world form remains in collective converter")
    return {"status": STATUS, "inventory_ids": SWEEP.derive()[
                "collective_card_checklist"],
            "conversion_functions": {
                "post-producer.source-owner-exact-list":
                    "classify_registry",
                "scope.single-implementation-old-successor":
                    "single_implementation_gate",
                "scope.source-pair-old-successor": "source_scope_gate",
                "acceptance.map-tuple-snapshot": "linked_tuple_gate",
                "acceptance.far-payload-size": "far_payload_gate",
                "acceptance.oracle-image-count": "linked_oracle_gate",
                "acceptance.base-golden-cardinalities": "golden_sets",
                "acceptance.dependent-vma-cardinalities":
                    "dependent_acceptance_child"}}


def acceptance_golden_source_gate(source_override: str | None = None
                                  ) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None \
        else source_override
    tree = ast.parse(source)
    functions = {row.name: ast.unparse(row) for row in tree.body
                 if isinstance(row, ast.FunctionDef)}
    body = functions["acceptance_child"]
    require("acceptance_golden_gate(paths['elf'])" in body
            and "ORACLE.BASE.INV.compare_elf" not in body
            and "VMA_golden_authority" in body,
            "acceptance consumer is not permanently bound to v5")
    return {"status": "PASS: live acceptance consumes v5 additively",
            "consumer": "acceptance_child", "authority": V5_GOLDEN.__name__}


def acceptance_golden_source_mutation() -> str:
    source = DRIVER.read_text(encoding="utf-8").replace(
        "golden = acceptance_golden_gate(paths[\"elf\"])",
        "golden = ORACLE.BASE.INV.compare_elf(paths[\"elf\"])", 1)
    try:
        acceptance_golden_source_gate(source)
    except ConversionError:
        return "reintroduce-ambient-pre-v5-consumer"
    raise ConversionError("ambient Golden consumer mutation survived")


def validate_structural(value: dict[str, Any]) -> None:
    expected = structural_gate()
    require(value == expected
            and set(value["inventory_ids"]) ==
                set(value["conversion_functions"]),
            "collective inventory/checklist conversion incomplete")


def mutations() -> list[str]:
    value = structural_gate()
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-exact-registry": lambda x: x["conversion_functions"].update(
            {"post-producer.source-owner-exact-list": "stored-two-row-list"}),
        "restore-one-selected-owner": lambda x: x["conversion_functions"].update(
            {"scope.single-implementation-old-successor": "len-selected-equals-one"}),
        "restore-old-source-pair": lambda x: x["conversion_functions"].update(
            {"scope.source-pair-old-successor": "stored-source-pair"}),
        "restore-tuple-snapshot": lambda x: x["conversion_functions"].update(
            {"acceptance.map-tuple-snapshot": "stored-entry-size-offset"}),
        "restore-874-payload": lambda x: x["conversion_functions"].update(
            {"acceptance.far-payload-size": "stored-874"}),
        "restore-six-images": lambda x: x["conversion_functions"].update(
            {"acceptance.oracle-image-count": "stored-six"}),
        "restore-golden-counts": lambda x: x["conversion_functions"].update(
            {"acceptance.base-golden-cardinalities": "stored-103-27"}),
        "restore-vma-partition-counts": lambda x: x["conversion_functions"].update(
            {"acceptance.dependent-vma-cardinalities": "stored-103-101-2-27"}),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_structural(trial)
        except ConversionError:
            rejected.append(name)
    require(rejected == list(cases), "stored-world relapse mutation survived")
    return rejected


def preflight() -> dict[str, Any]:
    value = structural_gate()
    validate_structural(value)
    value["mutations_rejected"] = mutations()
    value["acceptance_golden_rebind"] = acceptance_golden_source_gate()
    value["acceptance_golden_rebind_mutation"] = (
        acceptance_golden_source_mutation())
    require(len(value["inventory_ids"]) == len(value["mutations_rejected"]) == 8,
            "collective card inventory/mutation cardinality drift")
    return value


if __name__ == "__main__":
    value = preflight()
    print(f"R1 stored-world conversions: PASS rows={len(value['inventory_ids'])} "
          f"mutations={len(value['mutations_rejected'])}")
