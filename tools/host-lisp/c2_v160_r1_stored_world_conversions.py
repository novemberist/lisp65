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
FREIGHT_PLACEMENT_PROVERS: dict[str, Callable[[str, dict[str, Any],
    dict[str, Any], dict[str, Any]], dict[str, Any]]] = {}
ACCEPTANCE_ARTIFACT_ROOT: Callable[[], Path] | None = None


class ConversionError(RuntimeError):
    pass


def configure_freight_placement_prover(gate: str,
        prover: Callable[[str, dict[str, Any], dict[str, Any],
                          dict[str, Any]], dict[str, Any]]) -> None:
    existing = FREIGHT_PLACEMENT_PROVERS.get(gate)
    require(existing is None or existing is prover,
            f"freight placement prover configured twice: {gate}")
    FREIGHT_PLACEMENT_PROVERS[gate] = prover


def configure_acceptance_artifact_root(provider: Callable[[], Path]) -> None:
    global ACCEPTANCE_ARTIFACT_ROOT
    require(ACCEPTANCE_ARTIFACT_ROOT is None
            or ACCEPTANCE_ARTIFACT_ROOT is provider,
            "acceptance artifact root configured twice")
    ACCEPTANCE_ARTIFACT_ROOT = provider


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
            elif registry["placement_gate"] in FREIGHT_PLACEMENT_PROVERS:
                proof = FREIGHT_PLACEMENT_PROVERS[registry["placement_gate"]](
                    name, row, layout, registry)
            elif registry["placement_gate"] == "candidate-derived-after-ordinary-bss":
                proof = _after_ordinary_bss_proof(name, row, layout, registry)
            elif registry["placement_gate"] == \
                    "linker-visible-fixed-raw/split-bss":
                owners = registration["owners"]
                expected = owners.get(name)
                by_name = {item["name"]: item
                           for item in layout["allocatable_sections"]}
                input_owner = by_name.get(
                    ".lisp65_c2_input_raw_owner")
                def validate_fixed(candidate: dict[str, Any]) -> None:
                    require(expected is not None and input_owner is not None
                            and candidate["vma"] == expected["address"]
                            and candidate["bytes"] == expected["bytes"]
                            and (name != ".lisp65_c2_symbol_metadata_bss"
                                 or candidate["vma"] ==
                                    input_owner["vma"] + input_owner["bytes"]),
                            f"fixed-raw/split-BSS placement violated: {name}")
                validate_fixed(row)
                mutations = {
                    "owner-address-diverges": {**row, "vma": row["vma"] + 1},
                    "owner-extent-diverges": {**row, "bytes": row["bytes"] + 1},
                }
                rejected: list[str] = []
                for label, mutant in mutations.items():
                    try:
                        validate_fixed(mutant)
                    except ConversionError:
                        rejected.append(label)
                require(rejected == list(mutations),
                        f"fixed-raw/split-BSS mutation survived: {name}")
                relation = (
                    "symbol-metadata-starts-at-input-owner-end"
                    if name == ".lisp65_c2_symbol_metadata_bss" else
                    "section-equals-linker-visible-fixed-raw-owner")
                proof = {"gate": "linker-visible-fixed-raw/split-bss",
                    "relation": relation, "status": "passed",
                    "mutations_rejected": rejected}
            elif registry["placement_gate"] == (
                    "derived-before-far-service/shared-map-offset"):
                proof = _derived_before_far_service_proof(
                    name, row, layout, registry)
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
                    "candidate-predecessor-end", "mapped-arena-contract",
                    "composed-raw-owner/preheap-gap",
                    "derived-before-far-service/shared-map-offset",
                    "linker-visible-fixed-raw/split-bss",
                    "candidate-derived-after-ordinary-bss"}
                and ((row["placement_proof"].get("gate") ==
                      "candidate-derived-after-ordinary-bss"
                      and row["placement_proof"].get("relation") ==
                      "record-follows-final-bss-before-raw-input-floor"
                      and row["placement_proof"].get("mutations_rejected") ==
                      ["record-adjacency-broken", "record-size-broken", "record-floor-broken"]
                      and set(row["placement_proof"]) ==
                      {"gate", "relation", "status", "mutations_rejected"})
                     or (row["placement_proof"].get("gate") ==
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
                             "gate", "relation", "status"})
                     or (row["placement_proof"].get("gate") ==
                         "composed-raw-owner/preheap-gap"
                         and row["placement_proof"].get("relation") in {
                             "code-start-equals-derived-raw-owner-end",
                             "state-start-equals-hot-bss-end-before-heap"}
                         and set(row["placement_proof"]) == {
                             "gate", "relation", "status"})
                     or (row["placement_proof"].get("gate") ==
                         "derived-before-far-service/shared-map-offset"
                         and row["placement_proof"].get("relation") ==
                         ("section-ends-at-far-service-in-vma-and-lma-"
                          "under-shared-page-offset")
                         and row["placement_proof"].get(
                             "mutations_rejected") == [
                                 "broken-vma-lma-adjacency",
                                 "broken-shared-map-offset"]
                         and set(row["placement_proof"]) == {
                             "gate", "relation", "status",
                             "mutations_rejected"})
                     or (row["placement_proof"].get("gate") ==
                         "linker-visible-fixed-raw/split-bss"
                         and row["placement_proof"].get("relation") in {
                             "section-equals-linker-visible-fixed-raw-owner",
                             "symbol-metadata-starts-at-input-owner-end"}
                         and row["placement_proof"].get(
                             "mutations_rejected") == [
                                 "owner-address-diverges",
                                 "owner-extent-diverges"]
                         and set(row["placement_proof"]) == {
                             "gate", "relation", "status",
                             "mutations_rejected"})),
                f"additive freight row is an address snapshot: {row.get('name')}")


def _after_ordinary_bss_proof(name: str, row: dict[str, Any],
        layout: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    owners = {item["name"]: item for item in layout["allocatable_sections"]}
    record_bytes = registry["registration"].get("record_bytes")
    require(name == ".noinit.lisp65_f011_status" and
            type(record_bytes) is int and record_bytes > 0,
            "F011 record authority mismatch")
    bss, raw = owners[".bss"], owners[".lisp65_c2_input_raw_owner"]
    def relation(candidate: dict[str, Any], raw_start: int) -> None:
        require(candidate["bytes"] == registry["registration"]["record_bytes"]
                and candidate["vma"] == bss["vma"] + bss["bytes"]
                and candidate["vma"] + candidate["bytes"] + 5 <= raw_start,
                "F011 record is not a disjoint BSS successor")
    relation(row, raw["vma"])
    mutations = [
        ("record-adjacency-broken", {**row, "vma": row["vma"] + 1}, raw["vma"]),
        ("record-size-broken", {**row, "bytes": record_bytes - 1}, raw["vma"]),
        ("record-floor-broken", row, row["vma"] + row["bytes"] + 4),
    ]
    rejected = []
    for name, candidate, limit in mutations:
        try: relation(candidate, limit)
        except ConversionError: rejected.append(name)
    require(len(rejected) == len(mutations), "F011 placement mutation survived")
    return {"gate": "candidate-derived-after-ordinary-bss",
            "relation": "record-follows-final-bss-before-raw-input-floor",
            "status": "passed", "mutations_rejected": rejected}


def _derived_before_far_service_proof(name: str, row: dict[str, Any],
        layout: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Prove the F011 tenant's linker-derived placement semantically.

    The relation is taken exclusively from the final ELF layout.  Neither the
    owner's address nor the far-service address is an Acceptance constant.
    """
    registration = registry["registration"]
    by_name = {item["name"]: item for item in layout["allocatable_sections"]}
    far = by_name.get(".lisp65_c2_mapped_far_service")
    require(name == ".lisp65_c2_mapped_f011_cold"
            and registry["registry"] == "block-26-f011-cold-read"
            and registration.get("physical_placement", {}).get("kind") ==
                "derived-before-far-service-under-shared-map-offset"
            and far is not None,
            "derived-before-far-service prover bound another owner")

    def relation(candidate: dict[str, Any]) -> None:
        owner_offset = candidate["lma"] - candidate["vma"]
        far_offset = far["lma"] - far["vma"]
        require(candidate["bytes"] > 0
                and candidate["bytes"] <= registration["capacity_bytes"]
                and candidate["vma"] >= registration["cpu_floor"]
                and candidate["vma"] + candidate["bytes"] == far["vma"]
                and candidate["lma"] + candidate["bytes"] == far["lma"]
                and owner_offset == far_offset
                and owner_offset & 0xff == 0,
                f"derived-before-far-service placement violated: {name}")

    relation(row)
    mutations = {
        "broken-vma-lma-adjacency": {**row,
            "vma": row["vma"] - 1, "lma": row["lma"] - 1},
        "broken-shared-map-offset": {**row, "lma": row["lma"] + 0x100},
    }
    rejected: list[str] = []
    for label, mutant in mutations.items():
        try:
            relation(mutant)
        except ConversionError:
            rejected.append(label)
        else:
            raise ConversionError(
                f"derived-before-far-service mutation survived: {label}")
    require(rejected == list(mutations),
            "derived-before-far-service mutation closure drift")
    return {"gate": "derived-before-far-service/shared-map-offset",
        "relation": ("section-ends-at-far-service-in-vma-and-lma-under-"
                     "shared-page-offset"),
        "mutations_rejected": rejected, "status": "passed"}


def _additive_section_closure(layout: dict[str, Any], golden: dict[str, Any],
                              registered: set[str],
                              proof_rows: list[dict[str, Any]]) -> dict[str, Any]:
    golden_names = V4_GOLDEN.all_names(golden)
    candidate_names = {row["name"] for row in layout["allocatable_sections"]}
    require(not (golden_names & registered),
            "additive freight has double Golden authority")
    require(candidate_names == golden_names | registered,
            "candidate section authority differs: unregistered="
            + repr(sorted(candidate_names - (golden_names | registered)))
            + "; missing=" + repr(sorted((golden_names | registered) - candidate_names)))
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


def mapped_lma_successor_mutations(elf: Path, *, packed_prg: Path | None = None,
        allowed_flat_packed_sections: set[str] | None = None) -> list[str]:
    policy = PRODUCT.MAPPED_TENANT_LMA_POLICY
    if policy not in ("bank2-top", "map-page-top"):
        return []
    layout = LAYOUT.layout_from_elf(elf, packed_prg=packed_prg,
        allowed_flat_packed_sections=allowed_flat_packed_sections)
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


def acceptance_golden_gate(elf: Path, golden: Any = V5_GOLDEN,
                           packed_prg: Path | None = None
                           ) -> dict[str, Any]:
    require(golden is V5_GOLDEN,
            "live acceptance reintroduced a pre-v5 Golden")
    additive: dict[str, Any] | None = None
    registries = PRODUCT.active_card_freight_registries()
    if registries:
        authority = load(golden.GOLDEN)
        registries, registered = _active_freight_union()
        layout = LAYOUT.layout_from_elf(elf, packed_prg=packed_prg,
            allowed_flat_packed_sections=registered)
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
                mapped_lma_successor_mutations(elf, packed_prg=packed_prg,
                    allowed_flat_packed_sections=registered))
        successor = candidate_fixed_successors(layout, authority)
        additive["candidate_derived_fixed_successors"] = successor
        additive["candidate_derived_fixed_successor_mutations"] = (
            candidate_fixed_successor_mutations(layout, authority))
        # The sealed Golden remains byte-history.  Its comparison view is
        # normalized only for the independently proved candidate successors;
        # every other fixed member remains exact.
        golden_layout = deepcopy(base_layout)
        sections = {row["name"]: row
                    for row in golden_layout["allocatable_sections"]}
        golden_sections = {row["name"]: row
                           for row in authority["section_invariants"]}
        ordinary_arena = next(row for row in authority["capacity_arenas"]
                              if row["id"] == "ordinary-text")
        sections[".text"]["bytes"] = (
            ordinary_arena["end_exclusive"] - sections[".text"]["vma"])
        sections[".lisp65_c2_mapped_far_facade"]["vma"] = (
            golden_sections[".lisp65_c2_mapped_far_facade"]["vma"])
        for name in ("__bss_end", "__bss_size",
                     "__lisp65_resident_island_end"):
            golden_layout["boundary_symbols"][name] = (
                authority["fixed_boundary_symbols"][name])
        if "zero_page_BSS" in successor:
            golden_layout["boundary_symbols"]["__zp_bss_size"] = (
                authority["fixed_boundary_symbols"]["__zp_bss_size"])
        comparison = golden.compare_layout(golden_layout, authority,
            normalized_fixed_members={
                ".lisp65_resident_island_annex.vma"} | (
                    {".zp.vma"} if "zero_page_BSS" in successor else set()))
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


def candidate_fixed_successors(layout: dict[str, Any],
                               authority: dict[str, Any]) -> dict[str, Any]:
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    text = rows[".text"]
    facade = rows[".lisp65_c2_mapped_far_facade"]
    handoff = rows[".lisp65_c2_kernal_handoff"]
    bss = rows[".bss"]
    island = rows[".lisp65_resident_island"]
    annex = rows[".lisp65_resident_island_annex"]
    symbols = layout["boundary_symbols"]
    expected_facade = max(0xB3B0, text["vma"] + text["bytes"] + 32)
    bss_end = bss["vma"] + bss["bytes"]
    split_bss = ".lisp65_c2_symbol_metadata_bss" in rows
    if split_bss:
        input_owner = rows[".lisp65_c2_input_raw_owner"]
        metadata = rows[".lisp65_c2_symbol_metadata_bss"]
        logical_bss_end = metadata["vma"] + metadata["bytes"]
        require(bss_end <= input_owner["vma"]
                and input_owner["vma"] + input_owner["bytes"] ==
                    metadata["vma"]
                and symbols["__bss_start"] == bss["vma"]
                and symbols["__bss_end"] == logical_bss_end
                and symbols["__bss_size"] ==
                    logical_bss_end - bss["vma"]
                and 0xC000 - logical_bss_end >= 5,
                "candidate split-BSS successor is not owner-derived/margin-safe")
    else:
        logical_bss_end = bss_end
    island_end = island["vma"] + island["bytes"]
    annex_vma = (island_end + annex["alignment"] - 1) & ~(
        annex["alignment"] - 1)
    require(facade["vma"] == expected_facade
            and facade["vma"] + facade["bytes"] <= handoff["vma"],
            "candidate facade is not derived from final text/owner interval")
    if not split_bss:
        require(symbols["__bss_start"] == bss["vma"]
                and symbols["__bss_size"] == bss["bytes"]
                and symbols["__bss_end"] == bss_end
                and 0xC000 - bss_end >= 5,
                "candidate BSS successor is not extent-derived/margin-safe")
    require(symbols["__lisp65_resident_island_start"] == island["vma"]
            and symbols["__lisp65_resident_island_end"] == island_end
            and annex["vma"] == annex_vma
            and annex["vma"] + annex["bytes"] <= 0x2000,
            "candidate resident-island end is not extent-derived")
    result = {"status": "passed-candidate-derived-fixed-successors",
        "facade": {"vma": facade["vma"], "derived_vma": expected_facade,
            "text_reserve_bytes": facade["vma"]-text["vma"]-text["bytes"],
            "next_owner_reserve_bytes":
                handoff["vma"]-facade["vma"]-facade["bytes"]},
        "BSS": {"vma": bss["vma"], "bytes": bss["bytes"],
            "end": logical_bss_end,
            "margin_bytes": 0xC000-logical_bss_end,
            "layout": "split-around-linker-visible-raw-owner"
                if split_bss else "single-section"},
        "resident_island": {"vma": island["vma"], "bytes": island["bytes"],
            "end": island_end, "annex_vma": annex["vma"],
            "derived_annex_vma": annex_vma,
            "annex_alignment": annex["alignment"],
            "combined_margin_bytes": 0x2000-annex["vma"]-annex["bytes"]},
        "sealed_golden_unchanged": True,
        "normalized_fixed_members": [".text.capacity_end",
            ".lisp65_c2_mapped_far_facade.vma",
            "__bss_end", "__bss_size", "__lisp65_resident_island_end",
            ".lisp65_resident_island_annex.vma"]}
    if symbols["__zp_bss_size"] != authority["fixed_boundary_symbols"][
            "__zp_bss_size"]:
        result["zero_page_BSS"] = candidate_zp_bss_successor(layout)
        result["zero_page_BSS_mutations"] = candidate_zp_bss_mutations(layout)
        result["normalized_fixed_members"].extend(("__zp_bss_size", ".zp.vma"))
    return result


def candidate_zp_bss_successor(layout: dict[str, Any]) -> dict[str, Any]:
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    bss, following = rows[".zp.bss"], rows[".zp"]
    fixed = rows[".lisp65_c2_convergence_zp"]
    symbols = layout["boundary_symbols"]
    require(bss["bytes"] > 0
            and symbols["__zp_bss_start"] == bss["vma"]
            and symbols["__zp_bss_size"] == bss["bytes"]
            and bss["vma"] + bss["bytes"] == following["vma"]
            and following["bytes"] > 0
            and following["vma"] + following["bytes"] <= fixed["vma"],
            "candidate ZP BSS is not extent-derived/disjoint")
    return {"vma": bss["vma"], "bytes": bss["bytes"],
            "next_owner": following["name"], "next_vma": following["vma"],
            "next_bytes": following["bytes"],
            "reserve_bytes": fixed["vma"]-following["vma"]-following["bytes"]}


def candidate_zp_bss_mutations(layout: dict[str, Any]) -> list[str]:
    wrong = deepcopy(layout)
    wrong["boundary_symbols"]["__zp_bss_size"] += 1
    overlap = deepcopy(layout)
    rows = {row["name"]: row for row in overlap["allocatable_sections"]}
    size = rows[".zp"]["vma"] - rows[".zp.bss"]["vma"] + 1
    rows[".zp.bss"]["bytes"] = size
    overlap["boundary_symbols"]["__zp_bss_size"] = size
    rejected = []
    for label, trial in (("ZP-BSS-boundary-diverges", wrong),
                         ("ZP-BSS-overlaps-next-owner", overlap)):
        try:
            candidate_zp_bss_successor(trial)
        except ConversionError:
            rejected.append(label)
    require(len(rejected) == 2, "ZP-BSS successor mutation survived")
    return rejected


def candidate_fixed_successor_mutations(
        layout: dict[str, Any], authority: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "facade-unexplained-shift": lambda x: next(row for row in
            x["allocatable_sections"] if row["name"] ==
            ".lisp65_c2_mapped_far_facade").update(vma=0xB3DD),
        "BSS-end-diverges": lambda x: x["boundary_symbols"].update(
            __bss_end=x["boundary_symbols"]["__bss_end"] + 1),
        "BSS-margin-spent": lambda x: next(row for row in
            x["allocatable_sections"] if row["name"] == ".bss").update(
                bytes=1586),
        "resident-end-diverges": lambda x: x["boundary_symbols"].update(
            __lisp65_resident_island_end=
                x["boundary_symbols"]["__lisp65_resident_island_end"] + 1),
        "resident-annex-adjacency-diverges": lambda x: next(row for row in
            x["allocatable_sections"] if row["name"] ==
            ".lisp65_resident_island_annex").update(
                vma=next(row for row in x["allocatable_sections"]
                         if row["name"] ==
                         ".lisp65_resident_island_annex")["vma"] + 2),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(layout); mutate(trial)
        try:
            candidate_fixed_successors(trial, authority)
        except ConversionError:
            rejected.append(name)
    require(rejected == list(cases),
            "candidate fixed-successor acceptance mutation survived")
    return rejected


def qualification_resolver_population(source_override: str | None = None
                                      ) -> dict[str, Any]:
    """Derive candidate-world resolvers reachable from live Acceptance.

    This complements the historical seven literal pins and six inherited
    closures: qualification functions are discovered from their actual local
    call graph, not appended to another hand-maintained list.
    """
    source = DRIVER.read_text(encoding="utf-8") if source_override is None \
        else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    root = "acceptance_golden_gate"
    require(root in functions, "Acceptance qualification root absent")
    reachable: set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(sorted({call.func.id for call in ast.walk(functions[name])
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id in functions} - reachable))
    candidate_arguments = {"layout", "elf", "packed_prg", "authority", "golden"}
    resolvers = sorted(name for name in reachable
        if candidate_arguments & {arg.arg for arg in functions[name].args.args})
    require(root in resolvers and "_freight_proof_rows" in resolvers
            and "candidate_fixed_successors" in resolvers,
            "Acceptance candidate-resolver closure is incomplete")
    return {"root": root,
        "derivation": "transitive local call graph plus candidate-world arguments",
        "resolvers": [{"name": name,
            "world_policy": "candidate-derived-before-sealed-normalization"}
            for name in resolvers],
        "resolver_count_derived": len(resolvers)}


def validate_qualification_resolver_population(value: dict[str, Any],
        source_override: str | None = None) -> dict[str, Any]:
    derived = qualification_resolver_population(source_override)
    require(value == derived, "qualification resolver population is stale")
    return value


def qualification_resolver_population_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    current = qualification_resolver_population(source)
    cases: dict[str, tuple[dict[str, Any], str]] = {}
    omitted = deepcopy(current); omitted["resolvers"].pop()
    omitted["resolver_count_derived"] -= 1
    cases["reachable-qualification-resolver-omitted"] = (omitted, source)
    added_source = source.replace(
        "    require(golden is V5_GOLDEN,\n",
        "    _mutation_new_qualification_resolver(layout)\n"
        "    require(golden is V5_GOLDEN,\n", 1) + (
        "\n\ndef _mutation_new_qualification_resolver(layout: dict[str, Any])"
        " -> dict[str, Any]:\n    return layout\n")
    cases["new-qualification-resolver-uninventoried"] = (current, added_source)
    missing_root = source.replace("def acceptance_golden_gate(",
                                  "def mutation_acceptance_golden_gate(", 1)
    cases["qualification-root-removed"] = (current, missing_root)
    rejected = []
    for label, (value, candidate_source) in cases.items():
        try:
            validate_qualification_resolver_population(value, candidate_source)
        except ConversionError:
            rejected.append(label)
    require(rejected == list(cases),
            "qualification resolver population mutation survived")
    return rejected


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
    ORACLE.BASE.CRC.BUILD = (ORACLE.BUILD if ACCEPTANCE_ARTIFACT_ROOT is None
                             else ACCEPTANCE_ARTIFACT_ROOT())
    golden = acceptance_golden_gate(paths["elf"], packed_prg=paths["prg"])
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
    require("acceptance_golden_gate(paths['elf'], packed_prg=paths['prg'])" in body
            and "ORACLE.BASE.INV.compare_elf" not in body
            and "VMA_golden_authority" in body,
            "acceptance consumer is not permanently bound to v5")
    return {"status": "PASS: live acceptance consumes v5 additively",
            "consumer": "acceptance_child", "authority": V5_GOLDEN.__name__}


def acceptance_golden_source_mutation() -> str:
    source = DRIVER.read_text(encoding="utf-8").replace(
        "golden = acceptance_golden_gate(paths[\"elf\"], packed_prg=paths[\"prg\"])",
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
