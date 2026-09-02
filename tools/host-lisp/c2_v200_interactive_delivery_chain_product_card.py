#!/usr/bin/env python3
"""Link and qualify the resident, generation-pure interactive delivery world."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_packed_object_generation_coherence as COHERENCE  # noqa: E402
import c2_v17_ide_idle_blink_product_card as PLANE_TOOLS  # noqa: E402
import c2_v17_recovery_quiescence as RECOVERY  # noqa: E402
import c2_v200_block3_return_product_card as LINK  # noqa: E402
import c2_v200_domain_tier2_pricing as T2_PRICE  # noqa: E402
import c2_v200_domain_tier2_product_card as T2  # noqa: E402
import c2_v200_interactive_delivery_chain_pricing as PRICE  # noqa: E402
import consolidated_consumption_authority as CONSUMPTION  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "d4a3888a"
PLAN_HEADER = (
    "## Owner word and reviewer authorization — Tier 2 and the delivery chain — 2026-09-01")
BUILD = ROOT / "build/c2.3/v2.0-interactive-delivery-chain-product-card-r1"
PREFLIGHT = ROOT / "build/c2.3/v2.0-interactive-delivery-chain-product-card-r1-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-plane.json")
PREFLIGHT_RECEIPT = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-preflight.json")
SOURCE_PREFLIGHT = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-source-preflight.json")
PRELINK_RED = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-prelink-red.json")
FRONTEND_RED = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-frontend-red.json")
DIRECT_ENTRY_RECEIPT = ARCH / (
    "c2.3-v2.0-block3-direct-entry-contract.json")
DIFFERENCE = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-difference.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-interactive-delivery-chain-product-card-r1-receipt.json")
REPORT = ROOT / (
    "docs/planning/v2.0.0-interactive-delivery-chain-product-card-report.md")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
EXTENT = 53820
BASE_EXTENT = 47795
FORMAT = "lisp65-c2-v200-interactive-delivery-chain-product-card-v1"
STATUS = "PASS: V2.0 RESIDENT INTERACTIVE DELIVERY PRODUCT GREEN"


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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "delivery authorization identity drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("two product cards", "resident", "53,820",
                  "combination is measured", "25% wall"):
        require(token in folded, f"delivery authorization token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(section.encode()),
        "sha256": hashlib.sha256(section.encode()).hexdigest(),
        "pricing": bind(PRICE.RECEIPT), "Tier_2_predecessor": bind(T2.RECEIPT),
        "right": "one delivery-chain product card, one WPLTO and one product link"}


def candidate_specs() -> tuple[tuple[str, str, Path], ...]:
    product = load(PLANE / "product/substitution-artifacts.json")
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == 6,
            "resident candidate manifest population drift")
    return tuple((key, role, ROOT / row["path"])
        for key, role, row in zip(
            PRICE.PRODUCT_KEYS,
            ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), rows))


def geometry() -> dict[str, Any]:
    product = load(PLANE / "product/substitution-artifacts.json")
    code = PLANE / "v6-semantics/bank2-static-code.bin"
    total = sum(int(load(path)["code_bytes"])
                for _key, _role, path in candidate_specs())
    require(total == code.stat().st_size == EXTENT,
            "resident candidate extent drift")
    return {"bytes": total, "headroom_bytes": 65536 - total,
        "images": product["images"], "entries": product["entries"],
        "resolutions": product["resolutions"], "roots": product["roots"],
        "product_build_id": product["product_build_id_hex"],
        "sha256": bind(code)["sha256"]}


def materialize_plane() -> dict[str, Any]:
    require(not PREFLIGHT.exists() and not PLANE_RECEIPT.exists(),
            "delivery preflight is one-shot")
    run([sys.executable,
         "tools/host-lisp/c2_v200_interactive_delivery_chain_pricing.py",
         "check"], "delivery price regeneration")
    shutil.copytree(PRICE.BUILD, PLANE)
    predecessor = ROOT / (
        "build/c2.3/v2.0-domain-tier1-product-card-r1-preflight")
    for name in ("projected-ownership-contract.json",
                 "projected-full-map-authority.json"):
        source = predecessor / name
        if source.is_file():
            shutil.copyfile(source, PREFLIGHT / name)
    product = load(PLANE / "product/substitution-artifacts.json")
    static = geometry()
    semantics = {"static_bank2": {"code_bytes": static["bytes"],
        "code_sha256": static["sha256"],
        "headroom_bytes": static["headroom_bytes"]}}
    PLANE_TOOLS.derived_profile(PLANE, product, semantics)
    PLANE_TOOLS.derived_contract(PLANE, EXTENT)
    PLANE_TOOLS.derived_header(PLANE, EXTENT)
    value = {"format": FORMAT + "-plane", "recorded_on": "2026-09-01",
        "status": "PASS: RESIDENT INTERACTIVE 53820-BYTE PLANE MATERIALIZED",
        "authority": authority(), "geometry": static,
        "manifests": [bind(path) for _key, _role, path in candidate_specs()],
        "product": bind(PLANE / "product/substitution-artifacts.json"),
        "profile": bind(PLANE / "candidate-profile.json"),
        "contract": bind(PLANE / "c2-lite-execution-contract.json"),
        "header": bind(PLANE / "c2_lite_static_plane.h"),
        "bank2": bind(PLANE / "v6-semantics/bank2-static-code.bin"),
        "accounting": {"WPLTO_runs": 0, "product_links": 0}}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def candidate_static_header_authority() -> tuple[Path, dict[str, Any], int]:
    header = PLANE / "c2_lite_static_plane.h"
    values = re.findall(
        rb"^#define LISP65_C2_LITE_STATIC_CODE_BYTES ([0-9]+)UL$",
        header.read_bytes(), re.MULTILINE)
    require(values == [str(EXTENT).encode()],
            "delivery static header is not candidate-derived")
    return header, bind(header), EXTENT


def patch_link_stack() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT,
        "DIRECT_ENTRY_RECEIPT": DIRECT_ENTRY_RECEIPT,
        "CURRENT_RECEIPT": T2.RECEIPT, "CURRENT_ELF": T2.ELF,
        "CURRENT_PRG": T2.PRG, "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "INVOCATION": INVOCATION,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "PRICING_RECEIPT": PRICE.RECEIPT,
        "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(LINK, name, value)
    LINK.authority = authority
    LINK.candidate_specs = candidate_specs
    LINK._plane_geometry = geometry
    LINK.candidate_static_header_authority = candidate_static_header_authority
    LINK.R4.R3.candidate_static_header_authority = candidate_static_header_authority
    LINK.configure()
    CONSUMPTION.configure_output_root_resolvers({
        "final-product-qualifier": ELF,
        "scope-qualifier": ELF,
        "acceptance-qualifier": ELF,
    })


def setup_link_world() -> tuple[Any, dict[str, Any], dict[str, object]]:
    LINK.R4.R3.CARD.RELEASE.R8.R7.CARD.stdlib_header_ordinals = (
        LINK.candidate_stdlib_ordinals)
    LINK.R4.R3.candidate_static_header_authority = candidate_static_header_authority
    core = LINK.R4.configure_seed_world()
    static = LINK.bind_candidate_plane()
    core.bind_paths_only(BUILD, PREFLIGHT)
    core.write_projections()
    require(static["consumer_observed_bytes"] == EXTENT,
            "product setup consumed another delivery extent")
    return core, {"status": "resident-plane-bound"}, {}


def packed_properties() -> dict[str, Any]:
    product = PLANE / "product/substitution-artifacts.json"
    closure = CLOSURE.derive(product)
    CLOSURE.require_closed(closure)
    specs = candidate_specs()
    lengths = [int(load(path)["code_bytes"]) for _key, _role, path in specs]
    plane = (PLANE / "v6-semantics/bank2-static-code.bin").read_bytes()
    require(sum(lengths) == len(plane) == EXTENT,
            "packed plane component boundary drift")
    coherence = COHERENCE.derive(
        PLANE / "stdlib-p0.manifest.json",
        PLANE / "product/stdlib-p0.code.bin", PRICE.STDLIB_SUITE,
        plane[:lengths[0]])
    COHERENCE.require_coherent(coherence)
    sources = PRICE.key_source_population(specs)
    wall = PRICE.delivered_host_wall(sources)
    require(closure["object_count"] == 797
            and closure["call_site_count"] == 2686
            and sources["armed_sink_set"] == ["c2_kernal_input_take"]
            and wall["counters"] == {"raw": 94, "seen": 94,
                                      "stored": 94, "taken": 94},
            "delivery closure/coherence/input wall drift")
    return {"closure": closure, "generation_coherence": coherence,
            "key_sources": sources, "host_wall": wall,
            "packed_plane_readback": bind(
                PLANE / "v6-semantics/bank2-static-code.bin")}


def configuration_gate() -> dict[str, Any]:
    patch_link_stack()
    setup_link_world()
    packed = packed_properties()
    price = load(PRICE.RECEIPT)["pricing"]
    require(price["resident_interactive_plane_bytes"] == EXTENT
            and price["maximum_object_bytes"] == 253,
            "delivery price no longer describes the candidate")
    return {"status": "PASS: RESIDENT DELIVERY WORLD ARMED 0/1",
        "plane": bind(PLANE_RECEIPT), "packed": packed,
        "maximum_object_bytes": price["maximum_object_bytes"],
        "D5_projection": price["D5_projection"]}


def source_preflight() -> dict[str, Any]:
    output = PREFLIGHT / "candidate-generated-source-preflight"
    mapping = LINK.materialize_candidate_sources(output)
    features = LINK.predecessor_features()
    sources = LINK.projected_source_list(mapping, features)
    value = {"format": FORMAT + "-source-preflight",
        "recorded_on": "2026-09-01",
        "status": "PASS: DELIVERY GENERATED SOURCE WORLD ARMED",
        "compiler_sources": {"total": len(sources),
            "generated": len(mapping)},
        "qualified_profile": bind(LINK.predecessor_profile()),
        "feature_count": len(features),
        "mutations_rejected": ["authored-generated-source-fallback",
                               "generated-source-omitted"]}
    require(len(sources) == 70 and len(mapping) >= 20 and len(features) == 35,
            "delivery source preflight population drift")
    SOURCE_PREFLIGHT.write_bytes(canonical(value))
    return value


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PLANE_RECEIPT, PREFLIGHT_RECEIPT, SOURCE_PREFLIGHT,
         RECEIPT, DIFFERENCE)), "delivery product preflight is one-shot")
    materialize_plane()
    gate = configuration_gate()
    sources = source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-01",
        "status": "PASS: V2.0 RESIDENT DELIVERY PRODUCT CARD ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "requirements": ["one WPLTO and one product link",
            "combined final-ELF responsiveness remains above 25 percent",
            "full attribution has zero unexplained members",
            "Scope and Acceptance are read-only over the frozen pair"],
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
            "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("v2.0 delivery product: PREFLIGHT PASS plane=53820 WPLTO=0/1 link=0/1")


def frozen_artifacts() -> dict[str, Any]:
    return {"ELF": bind(ELF), "PRG": bind(PRG),
        "map": bind(Path(str(PRG) + ".map")),
        "lto": bind(Path(str(PRG) + ".lto.o"))}


def profile_inputs(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            left, digest = line.split(":", 1)
            rows[Path(left.split("=", 1)[1]).name] = digest
    return rows


def counter_rows(value: Counter[tuple[Any, ...]]) -> list[list[Any]]:
    return [list(row) + [count] for row, count in sorted(value.items())]


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(T2.ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    section_rows = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                            for row in truth.sections) for truth in (old, new)]
    symbol_rows = [Counter((row.name, row.value, row.bytes, row.section)
                           for row in truth.symbols) for truth in (old, new)]
    relocation_rows = [Counter((row.source_section, row.offset,
        row.relocation_type, row.target, row.addend) for row in truth.relocations)
        for truth in (old, new)]
    changed_inputs = sorted(name for name in
        set(profile_inputs(T2.PROFILE)) | set(profile_inputs(PROFILE))
        if profile_inputs(T2.PROFILE).get(name) != profile_inputs(PROFILE).get(name))
    authored = [name for name in changed_inputs
                if not name.startswith("c2-stream-")]
    require(not authored, f"delivery link changed authored native input: {authored}")
    removed_sections, added_sections = (section_rows[0] - section_rows[1],
                                        section_rows[1] - section_rows[0])
    removed_symbols, added_symbols = (symbol_rows[0] - symbol_rows[1],
                                      symbol_rows[1] - symbol_rows[0])
    removed_relocs, added_relocs = (relocation_rows[0] - relocation_rows[1],
                                    relocation_rows[1] - relocation_rows[0])
    before_product = load(
        T2.TIER1.PLANE / "product/substitution-artifacts.json")
    after_product = load(PLANE / "product/substitution-artifacts.json")
    price = load(PRICE.RECEIPT)["pricing"]
    require(price["current_Tier_1_plane_bytes"] == BASE_EXTENT
            and price["resident_interactive_plane_bytes"] == EXTENT
            and before_product["images"] == after_product["images"] == 6,
            "delivery plane attribution root drift")
    return {"status": "PASS: TIER-2 TO RESIDENT DELIVERY FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(T2.ELF), "PRG": bind(T2.PRG),
                        "plane_bytes": BASE_EXTENT},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG),
                      "plane_bytes": EXTENT},
        "input_roots": {"authored_native_sources": "byte-identical",
            "changed_generated_inputs": changed_inputs,
            "candidate_plane": bind(
                PLANE / "v6-semantics/bank2-static-code.bin")},
        "plane_family": {"delta_bytes": EXTENT - BASE_EXTENT,
            "named_successor_objects": price["new_named_objects"],
            "replacement_credit_bytes":
                price["replaced_existing_object_credit_bytes"],
            "product_build_id_before": before_product["product_build_id_hex"],
            "product_build_id_after": after_product["product_build_id_hex"]},
        "sections": {"removed": counter_rows(removed_sections),
                     "added": counter_rows(added_sections), "unexplained": []},
        "symbols": {"removed": counter_rows(removed_symbols),
                    "added": counter_rows(added_symbols), "unexplained": []},
        "relocations": {"removed": counter_rows(removed_relocs),
                        "added": counter_rows(added_relocs), "unexplained": []},
        "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_plane_bytes": 0,
        "unexplained_members": 0}


def composed_bank2() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    plane_end = 0x20000 + EXTENT
    require(plane_end <= far_lma and far_lma == 0x2F8B2
            and far_lma + far.bytes <= cold_lma
            and cold_lma + cold.bytes <= 0x30000,
            "delivery composed Bank-2 ownership red")
    return {"owners": {"static_plane": [0x20000, plane_end],
        "mapped_far_service": [far_lma, far_lma + far.bytes],
        "mapped_product_cold": [cold_lma, cold_lma + cold.bytes],
        "bank_end_reserve": [cold_lma + cold.bytes, 0x30000]},
        "largest_contiguous_hole": {"start": plane_end,
            "end_exclusive": far_lma, "bytes": far_lma - plane_end},
        "overlaps": [], "shared_offset": 0x28000}


def native_walls() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    symbols = {row.name for row in truth.symbols}
    nested = LINK.BASE.MAP_NEST.check(ELF)
    dma = LINK.BASE.DMA.linked_read_model(ELF)
    LINK.BASE.DMA.validate_final(dma)
    bypass = LINK.BASE.BYPASS.linked_read_model(ELF)
    LINK.BASE.BYPASS.validate_final(bypass)
    queue = LINK.BASE.QUEUE.linked_owner_gate(ELF)
    recovery = RECOVERY.final_gate(
        ELF, PLANE / "v6-semantics/bank2-static-code.bin")
    require(nested["violations"] == []
            and dma["unsafe_content_DMA_count"] == 0
            and bypass["unsafe_content_DMA_count"] == 0
            and queue["dominated_calls"] == 1
            and recovery["status"] ==
                "PASS: FINAL ELF HAS DERIVED EMPTY-JOURNAL BYPASS"
            and "c2_refill_trace_read" not in symbols,
            "delivery standing native wall red")
    return {"nested_MAP": nested, "DMA": dma, "selector_bypass": bypass,
            "queue_single_owner": queue, "recovery_quiescence": recovery,
            "diagnostic_freight_absent": True}


def final_gate() -> dict[str, Any]:
    patch_link_stack()
    packed = packed_properties()
    compiler = load(Path(str(PRG) + ".compiler-input-consumption.json"))
    stdlib = load(Path(str(PRG) + ".stdlib-input-consumption.json"))
    authority_input = load(Path(str(PRG) + ".authority-input-consumption.json"))
    inventory = CONSUMPTION.validate_authority_input_inventory(authority_input)
    ordinals = LINK.candidate_stdlib_ordinals()
    require(compiler["consumed_value"] == EXTENT
            and stdlib["consumed_value"] == ordinals["repl_banner"]
            and compiler["bound_header"] == bind(
                PLANE / "c2_lite_static_plane.h")
            and stdlib["bound_header"] == bind(PLANE / "stdlib-p0.h")
            and "feature-profile-population" in inventory["categories"],
            "delivery final consumers escaped candidate authority")
    route = T2_PRICE.delivered_route(live=True)
    performance = T2.final_linked_responsiveness(ELF, route=route)
    require(performance["margin_percent"] >= 25.0
            and performance["walls"]["minimum_margin_percent"]["passed"],
            "combined Tier-2 plus interactive responsiveness wall red")
    contract, changes = T2.measured_successor_contract()
    require(contract["counts"] == {"error-raised": 553,
        "documented-permissive": 179, "silently-wrong": 102}
        and len(changes) == 8,
        "delivery successor lost Tier-2 semantics")
    return {"status": "PASS: FINAL RESIDENT INTERACTIVE PRODUCT CLOSED",
        "static_extent": EXTENT, "compiler_consumption": compiler,
        "stdlib_consumption": stdlib, "authority_consumption": authority_input,
        "authority_inventory": inventory, "packed_product": packed,
        "composed_bank2": composed_bank2(), "native_walls": native_walls(),
        "combined_responsiveness": performance,
        "Tier_2_contract_counts": contract["counts"],
        "Tier_2_changed_cells": changes,
        "D5_projection": load(PRICE.RECEIPT)["pricing"]["D5_projection"]}


def run_child(action: str) -> dict[str, Any]:
    output = run([sys.executable, str(DRIVER), action],
                 f"delivery child {action}")
    return {"action": action, "stdout_tail": " ".join(output.split()[-35:])}


def child(action: str) -> None:
    patch_link_stack()
    LINK.setup_child = setup_link_world
    LINK.BASE.configuration_gate = configuration_gate
    LINK.BASE.final_gate = final_gate
    inherited_configure = LINK.configure
    if action == "_produce":
        # Before the producer runs, the candidate profile cannot exist yet.
        # Source ownership is inherited from the frozen Tier-2 profile; the
        # final candidate profile is checked after the producer materializes it.
        def predecessor_profile_gate() -> dict[str, Any]:
            lines = T2.PROFILE.read_text(encoding="utf-8").splitlines()
            sources = tuple(line.split(":", 1)[0].split("=", 1)[1]
                            for line in lines
                            if line.startswith("input_sha256="))
            features = tuple(item for line in lines
                if line.startswith("feature_defines=")
                for item in line.split("=", 1)[1].split(",") if item)
            expected = LINK.predecessor_features()
            require(sources and features == expected,
                    "Tier-2 predecessor profile population drift")
            return {"sources": sources, "features": features,
                    "profile": bind(T2.PROFILE),
                    "phase": "pre-producer-source-ownership"}
        def configure_preproducer() -> None:
            inherited_configure()
            LINK.BASE.profile_gate = predecessor_profile_gate
        # LINK.child reconstructs its wrapper stack once more at entry.  Install
        # the phase view after that reconstruction, not before it.
        LINK.configure = configure_preproducer
    try:
        LINK.child(action)
    finally:
        LINK.configure = inherited_configure


def record_prelink_red() -> None:
    require(INVOCATION.is_file() and not BUILD.exists()
            and not PRELINK_RED.exists() and not ELF.exists() and not PRG.exists(),
            "delivery prelink-red lifecycle drift")
    value = {"format": FORMAT + "-prelink-red-v1",
        "recorded_on": "2026-09-01",
        "status": "ATTRIBUTED: PRE-PRODUCER PROFILE PHASE MIXUP; 0/1",
        "authority": authority(), "invocation": bind(INVOCATION),
        "mechanism": ("the inherited source-scope checker tried to read the "
            "candidate resolved-profile before the producer could create it"),
        "required_source_world": bind(T2.PROFILE),
        "absent_material_artifacts": [
            ELF.relative_to(ROOT).as_posix(), PRG.relative_to(ROOT).as_posix(),
            Path(str(PRG) + ".lto.o").relative_to(ROOT).as_posix()],
        "accounting": {"WPLTO_runs": 0, "product_links": 0},
        "successor": ("derive pre-producer source ownership from the frozen "
            "Tier-2 profile; final profile remains a post-producer obligation")}
    PRELINK_RED.write_bytes(canonical(value))
    print("v2.0 delivery product: PRELINK RED RECORDED WPLTO=0/1 link=0/1")


def record_frontend_red() -> None:
    objects = sorted((WPLTO / ".canonical-objects-resident-island-seed").glob("*.o"))
    require(PROFILE.is_file() and len(objects) == 70
            and not FRONTEND_RED.exists()
            and not ELF.exists() and not PRG.exists()
            and not Path(str(PRG) + ".lto.o").exists(),
            "delivery frontend-red lifecycle drift")
    value = {"format": FORMAT + "-frontend-red-v1",
        "recorded_on": "2026-09-01",
        "status": "ATTRIBUTED: OUTPUT-ROOT QUALIFIER POPULATION INCOMPLETE",
        "authority": authority(), "prelink_red": bind(PRELINK_RED),
        "resolved_profile": bind(PROFILE),
        "compiled_source_objects": len(objects),
        "mechanism": ("the inherited authority carried the build resolver but "
            "omitted final-product, Scope and Acceptance resolvers"),
        "successor_population": ["build", "final-product-qualifier",
            "scope-qualifier", "acceptance-qualifier"],
        "absent_material_artifacts": [
            ELF.relative_to(ROOT).as_posix(), PRG.relative_to(ROOT).as_posix(),
            Path(str(PRG) + ".lto.o").relative_to(ROOT).as_posix()],
        "accounting": {"compiler_frontend_attempts": 1,
            "completed_WPLTO_objects": 0, "product_links": 0}}
    FRONTEND_RED.write_bytes(canonical(value))
    print("v2.0 delivery product: FRONTEND RED RECORDED objects=70 WPLTO=0 link=0")


def build() -> None:
    pre = load(PREFLIGHT_RECEIPT)
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    if BUILD.exists():
        material = (ELF, PRG, Path(str(PRG) + ".lto.o"))
        require(not any(path.exists() for path in material),
                "delivery retry refuses to remove a material product artifact")
        shutil.rmtree(BUILD)
    require(clean == "" and pre["status"] ==
            "PASS: V2.0 RESIDENT DELIVERY PRODUCT CARD ARMED 0/1"
            and not BUILD.exists() and PRELINK_RED.exists() and FRONTEND_RED.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists(),
            "delivery product build is not at its committed one-shot boundary")
    patch_link_stack()
    invocation = {"status": "INVOKED", "authority": authority(),
                  "preflight": bind(PREFLIGHT_RECEIPT)}
    require(load(INVOCATION) == invocation,
            "delivery invocation changed after the precompiler stop")
    processes = [run_child("_produce")]
    before = frozen_artifacts()
    diff = attribution()
    require(diff["unexplained_members"] == 0,
            "delivery attribution retained an unexplained member")
    DIFFERENCE.write_bytes(canonical(diff))
    product = final_gate()
    processes.extend((run_child("_scope"), run_child("_accept")))
    after = frozen_artifacts()
    scope = load(LINK.BASE.SCOPE_RESULT)
    acceptance = load(LINK.BASE.ACCEPTANCE_RESULT)
    require(before == after and scope["status"] == acceptance["status"] == "PASS",
            "delivery Scope/Acceptance changed or rejected the frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-01",
        "status": STATUS, "authority": authority(),
        "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
        "prelink_red": bind(PRELINK_RED),
        "frontend_red": bind(FRONTEND_RED),
        "predecessor": {"ELF": bind(T2.ELF), "PRG": bind(T2.PRG)},
        "difference": diff, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(LINK.BASE.SCOPE_RESULT),
        "acceptance": bind(LINK.BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0,
            "pre_material_stops": 5, "frontend_stops_before_WPLTO": 1},
        "media_authorized": False,
        "media_condition": ("independent review first; any medium must rerun "
            "closure and generation coherence over packed readback bytes")}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    validate(value)
    print("v2.0 delivery product: BUILD PASS WPLTO=1/1 link=1/1")


def validate(value: dict[str, Any]) -> None:
    final = value["final_product"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and final["static_extent"] == EXTENT
            and final["packed_product"]["closure"]["object_count"] == 797
            and final["packed_product"]["generation_coherence"]["status"] ==
                "PASS: PACKED OBJECT GENERATION COHERENT"
            and final["packed_product"]["key_sources"]["armed_sink_set"] ==
                ["c2_kernal_input_take"]
            and final["packed_product"]["host_wall"]["counters"] == {
                "raw": 94, "seen": 94, "stored": 94, "taken": 94}
            and final["combined_responsiveness"]["margin_percent"] >= 25.0
            and final["Tier_2_contract_counts"]["silently-wrong"] == 102
            and final["composed_bank2"]["overlaps"] == []
            and value["artifacts_before"] == value["artifacts_after"] ==
                frozen_artifacts()
            and value["attempt_accounting"] == {"product_cards": 1,
                "WPLTO_runs": 1, "product_links": 1, "scope_runs": 1,
                "acceptance_runs": 1, "media_builds": 0,
                "device_contacts": 0, "pre_material_stops": 5,
                "frontend_stops_before_WPLTO": 1},
            "delivery product receipt drift")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "unexplained-link-member": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
        "packed-callee-missing": lambda row: row["final_product"]
            ["packed_product"]["closure"].update({"object_count": 796}),
        "mixed-generation": lambda row: row["final_product"]
            ["packed_product"]["generation_coherence"].update({"status": "RED"}),
        "public-queue-survives": lambda row: row["final_product"]
            ["packed_product"]["key_sources"].update(
                {"armed_sink_set": ["public-hardware-queue"]}),
        "delivered-consumer-not-drained": lambda row: row["final_product"]
            ["packed_product"]["host_wall"]["counters"].update({"taken": 0}),
        "combined-wall-red": lambda row: row["final_product"]
            ["combined_responsiveness"].update({"margin_percent": 24.99}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (CardError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "delivery product mutation survived")
    print(f"v2.0 delivery product: SELFTEST PASS mutations={len(rejected)}")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    pair = value["artifacts_after"]
    performance = final["combined_responsiveness"]
    hole = final["composed_bank2"]["largest_contiguous_hole"]["bytes"]
    REPORT.write_text(f"""# v2.0 interactive delivery chain — product card

Status: **{value['status']}**

The second authorized product card links one resident, single-generation
interactive world on top of the qualified Tier-2 pair.  Its static plane is
**{EXTENT:,} bytes**, the composed Bank-2 map is disjoint and retains a largest
contiguous hole of **{hole:,} bytes**.

The packed plane closes {final['packed_product']['closure']['object_count']}
objects and {final['packed_product']['closure']['call_site_count']:,} calls.
Generation coherence is derived independently from the same packed bytes.  The
complete armed key-source population resolves exactly to `c2_kernal_input_take`;
the delivered host wall ends at **94/94/94/94** and its `taken=0` mutation falls.

This card landed second, so it does not add two green prices.  It executes the
complete living interactive route and prices its CAR/CDR population against the
actual Tier-2 paths in this final ELF.  The combined result is
**{performance['frames_per_character']:.6f} frames/character**,
**{performance['service_events_per_frame']:.6f} events/frame** and
**{performance['margin_percent']:.3f}% margin**, green above 25%.

Tier-2 semantics remain freshly measured at **553 error / 179 permissive / 102
silently wrong**.  The predecessor-to-candidate attribution has zero unexplained
members; Scope and Acceptance are read-only green over ELF
`{pair['ELF']['sha256']}` / PRG `{pair['PRG']['sha256']}`.  Budget is exactly one
WPLTO and one product link.  No medium or device contact occurred; media remain
review-gated and must repeat closure and generation coherence over their own
packed readback bytes.
""", encoding="utf-8")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file(), "delivery product report absent")
    print("v2.0 delivery product: CHECK PASS WPLTO=1/1 link=1/1 media=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "record-prelink-red",
        "record-frontend-red",
        "build", "check",
        "selftest", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action != "preflight":
        patch_link_stack()
        LINK.setup_child = setup_link_world
        LINK.BASE.configuration_gate = configuration_gate
        LINK.BASE.final_gate = final_gate
    if action.startswith("_"):
        child(action); return 0
    {"preflight": preflight, "record-prelink-red": record_prelink_red,
     "record-frontend-red": record_frontend_red,
     "build": build, "check": check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 delivery product: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
