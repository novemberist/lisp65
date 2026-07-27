#!/usr/bin/env python3
"""One authorized C2-lite v6 co-resident aggregate-diet WPLTO probe.

The probe attributes the 4,230-byte Session payload growth, fuses two
strictly adjacent append pairs, runs both fusion cutpoint matrices, and then
performs at most one product-shaped Whole-Program-LTO measurement.  It never
creates a product link and never runs hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_cold_eviction_probe as COLD  # noqa: E402
import c2_lite_v6_cold_plan_emitter_probe as PLAN  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_lite_v6_semantic_split_probe as SPLIT  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-coresident-diet-wplto-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-wplto-probe-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
SEMANTIC_FIXTURE = ROOT / "scripts/c2-lite-v6-semantic-split-cutpoints-main.c"
FUSION_FIXTURE = ROOT / "scripts/c2-lite-v6-coresident-cutpoints-main.c"
BASELINE_ELF = ROOT / (
    "build/c2-lite/v6-cold-eviction-wplto-probe/full-product-wplto/"
    "c2-lite-v6-full-seed.prg.elf")
BASELINE_MANIFEST = ROOT / (
    "build/c2-lite/v6-cold-eviction-wplto-probe/full-product-wplto/"
    "runtime-overlays-session-c2-lite.json")
PRESPLIT_MAP = ROOT / (
    "build/c2-lite/v6-cold-plan-emitter-wplto-probe/full-product-wplto/"
    "c2-lite-v6-full-seed.prg.map")
SEMANTIC_ELF = ROOT / (
    "build/c2-lite/v6-semantic-splits-wplto-probe-class-a-replay/"
    "full-product-wplto/c2-lite-v6-full-seed.prg.elf")
SEMANTIC_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-semantic-splits-wplto-class-a-replay-receipt.json")
PLACEMENT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-coresident-diet-wplto-probe-receipt.json")
CAP = 1792
PUBLISH_QUANTUM_CEILING = 1024
BANK_BYTES = 65536
PACK_QUANTUM = 256
E000_FLOOR = 115


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def align(value: int) -> int:
    return (value + PACK_QUANTUM - 1) & ~(PACK_QUANTUM - 1)


def packed_bytes(sizes: list[int]) -> int:
    cursor = align(32 + len(sizes) * 32)
    for size in sizes:
        cursor = align(cursor) + size
    return cursor


def fuse_pair(rows: list[tuple[str, str]], left: str, right: str,
              fused: tuple[str, str]) -> None:
    names = [name for name, _entry in rows]
    require(names.count(left) == 1 and names.count(right) == 1,
            f"fusion anchors absent: {left}, {right}")
    at = names.index(left)
    require(at + 1 < len(rows) and rows[at + 1][0] == right,
            f"fusion anchors are not adjacent: {left}, {right}")
    rows[at:at + 2] = [fused]


def configure_coresident_diet() -> None:
    SPLIT.configure_semantic_splits()
    append = list(PRODUCT.C2_APPEND_SLICES)
    fuse_pair(append, "crc", "metadata",
              ("crc_metadata", "c2_append_crc_metadata_phase"))
    fuse_pair(append, "publish_names", "publish_cells",
              ("publish_exports", "c2_append_publish_exports_phase"))
    PRODUCT.configure_append_slices(append)
    require(len(PRODUCT.C2_DECODER_SLICES) == 19
            and len(PRODUCT.C2_APPEND_SLICES) == 24
            and PRODUCT.SESSION_EMITTER_SLOT_BASE == 15
            and PRODUCT.SESSION_APPEND_SLOT_BASE == 23
            and PRODUCT.SESSION_SERVICE_SLOT_BASE == 47
            and len(PRODUCT.SESSION_SLICE_SPECS) == 51
            and PRODUCT.UNIQUE_SLICE_COUNT == 58,
            "co-resident runtime-family ABI drift")


def map_section_sizes(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    pattern = re.compile(
        r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        r"(\.lisp65_rt_\S+)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and not match.group(2).startswith(".rela"):
            result[match.group(2)] = int(match.group(1), 16)
    return result


def payload_attribution_gate() -> dict[str, Any]:
    baseline = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    baseline_truth = ElfTruth.read(
        BASELINE_ELF, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    split_truth = ElfTruth.read(
        SEMANTIC_ELF, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    presplit = map_section_sizes(PRESPLIT_MAP)
    groups = {
        "decoder_05": {
            "baseline": (".lisp65_rt_c2d_05",),
            "presplit": (".lisp65_rt_c2d_05",),
            "split": (".lisp65_rt_c2d_05a", ".lisp65_rt_c2d_05b")},
        "reserve_transient": {
            "baseline": (".lisp65_rt_c2append_reserve_transient",),
            "presplit": (".lisp65_rt_c2append_reserve_transient",),
            "split": (".lisp65_rt_c2append_reserve_transient_bounds",
                      ".lisp65_rt_c2append_reserve_transient_code")},
        "reserve_persistent": {
            "baseline": (".lisp65_rt_c2append_reserve_persistent",),
            "presplit": (".lisp65_rt_c2append_reserve_persistent",),
            "split": (".lisp65_rt_c2append_reserve_persistent_bounds",
                      ".lisp65_rt_c2append_reserve_persistent_code")},
        "stage": {
            "baseline": (".lisp65_rt_c2append_stage",),
            "presplit": (".lisp65_rt_c2append_stage",),
            "split": (".lisp65_rt_c2append_stage_copy",
                      ".lisp65_rt_c2append_stage_plane")},
        "publish_plan": {
            "baseline": (".lisp65_rt_c2append_publish_plan",),
            "presplit": (".lisp65_rt_c2append_publish_plan",),
            "split": (".lisp65_rt_c2append_publish_plan_scan",
                      ".lisp65_rt_c2append_publish_plan_resolve")},
    }
    rows: dict[str, Any] = {}
    for name, sections in groups.items():
        base = sum(baseline_truth.section(section).bytes
                   for section in sections["baseline"])
        pre = sum(presplit[section] for section in sections["presplit"])
        split = sum(split_truth.section(section).bytes
                    for section in sections["split"])
        rows[name] = {
            "baseline_bytes": base, "pre_split_bytes": pre,
            "semantic_split_bytes": split,
            "contract_growth_bytes": pre - base,
            "split_growth_bytes": split - pre,
            "total_growth_bytes": split - base,
            "successor_sections": list(sections["split"]),
        }
    baseline_raw = sum(row["file_size"] for row in baseline["slices"])
    # Reconstruct the failed 53-record profile from the exact, SHA-bound pack
    # invocation captured by First Red.  Parsing the frozen argv avoids
    # mutating the live profile before the sole authorized WPLTO run.
    semantic_receipt = json.loads(SEMANTIC_RECEIPT.read_text(encoding="utf-8"))
    split_sections = re.findall(
        r"'--slice', '[^']*?:(\.[^:']+):", semantic_receipt["failure"])
    split_sizes = [split_truth.section(section).bytes
                   for section in split_sections]
    split_group_growth = sum(row["total_growth_bytes"] for row in rows.values())
    split_raw = sum(split_sizes)
    split_pack = packed_bytes(split_sizes)
    raw_growth = split_raw - baseline_raw
    other = raw_growth - split_group_growth
    require(baseline["storage"]["size"] == 61854
            and len(baseline["slices"]) == 48
            and baseline_raw == 53627
            and len(split_sections) == 53 and split_raw == 57857
            and split_pack == 66206 and raw_growth == 4230
            and split_group_growth == 4698 and other == -468,
            "payload attribution authority drift")
    model = {
        "semantic_split_catalog_records": 53,
        "semantic_split_raw_payload_bytes": split_raw,
        "semantic_split_pack_bytes": split_pack,
        "semantic_split_packaging_bytes": split_pack - split_raw,
        "overflow_bytes": 670,
        "after_two_catalog_removals_bytes": 65694,
        "after_publish_quantum_crossing_bytes": 65438,
        "modeled_headroom_bytes": 98,
    }
    require(model["semantic_split_pack_bytes"] - BANK_BYTES == 670
            and model["after_two_catalog_removals_bytes"] - PACK_QUANTUM
                == model["after_publish_quantum_crossing_bytes"]
            and BANK_BYTES - model["after_publish_quantum_crossing_bytes"] == 98,
            "co-resident pack model arithmetic red")
    return {
        "status": "passed",
        "authorities": {"last_green_manifest": bind(BASELINE_MANIFEST),
                        "last_green_elf": bind(BASELINE_ELF),
                        "pre_split_map": bind(PRESPLIT_MAP),
                        "semantic_split_elf": bind(SEMANTIC_ELF),
                        "semantic_first_red": bind(SEMANTIC_RECEIPT)},
        "object_groups": rows,
        "raw_payload": {
            "baseline_bytes": baseline_raw,
            "semantic_split_bytes": split_raw,
            "growth_bytes": raw_growth,
            "five_groups_growth_bytes": split_group_growth,
            "all_other_slices_net_bytes": other,
        },
        "semantic_split_pack_reconstruction": {
            "catalog_records": len(split_sections),
            "sections": split_sections,
            "raw_payload_bytes": split_raw,
            "packed_bytes": split_pack,
            "packaging_bytes": split_pack - split_raw,
        },
        "packaging_model": model,
    }


def source_contract_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    crc = V6.c_function_definition(runtime, "c2_append_crc_metadata_phase")
    publish = V6.c_function_definition(runtime, "c2_append_publish_exports_phase")
    facade16 = contract.get("append_plan_facade16_successor_geometry", {})
    facade16_authority = (
        contract["status"] ==
            "owner-authorized: append-plan facade vector 16 and full "
            "three-byte successor repin"
        and facade16.get("status") ==
            "owner-authorized-pending-fresh-WPLTO"
        and facade16.get("facade", {}).get("append_plan_vector", {}).get(
            "address") == "0xb5f1"
        and facade16.get("following_chain", {}).get(
            "runtime_overlay_verifier_bindings") == "0xb949")
    hybrid_authority = (
        (contract["status"] in (
            "class-c-hybrid-numeric-early-errors-selected-one-wplto-authorized",
            "class-c-append-plan-abi-fix-wplto-link-defun-hardware-authorized")
         or facade16_authority)
        and contract["decision"]["bank0_scope_cut_selection"] ==
            "numeric-early-errors"
        and contract["decision"]
            ["bank0_scope_cut_attributed_text_bytes"] == 81
        and contract["scope"]["product_shaped_probes_authorized"] == 1
        and contract["scope"]["product_links_authorized"] in (0, 1))
    checks = {
        "class_c_authority": hybrid_authority or contract["status"] in (
            "class-c-approved-coresident-aggregate-diet-wplto-probe-authorized",
            "class-c-approved-first-product-link-authorized",
            "class-c-approved-bank3-stage-wplto-probe-authorized",
            "class-c-approved-final-island-carrier-single-runtime-identity",
            "class-c-approved-export-symbol-domain-wplto-probe",
            "class-c-approved-export-symbol-domain-successor-link-and-line1-presmoke",
            "class-c-approved-symmetric-bank2-target-stage-wplto-"
            "successor-link-and-line1-presmoke"),
        "caps_unchanged": contract["coresident_aggregate_diet"]
            ["runtime_slice_cap_bytes"] == CAP
            and contract["coresident_aggregate_diet"]
                ["pack_quantum_bytes"] == PACK_QUANTUM
            and contract["coresident_aggregate_diet"]
                ["bank_layout_change_authorized"] is False,
        "crc_precedes_metadata": crc.index("c2_stage_crc")
            < crc.index("for (i = 0; i < sizeof w->meta"),
        "publication_has_two_ordered_halves": publish.count(
            "for (i = 0; i < count; ++i)") == 2
            and publish.index("C2AW_PLAN_MARK(w) = C2_EXPORT_PUBLISH_MARK")
                < publish.index("c2_journal_count = 0")
                < publish.index("set_sym_function"),
        "fused_entries_do_not_call_overlays": "c2_overlay_call" not in crc
            and "c2_overlay_call" not in publish,
        "crc_helper_section_follows_fusion":
            '#ifdef LISP65_C2_LITE_V6_CORESIDENT_DIET\n'
            'C2_APPEND_SECTION("crc_metadata")' in runtime
            and 'C2_APPEND_SECTION("crc")\n#endif\n'
                'static uint32_t c2_stage_crc' in runtime,
        "serial_driver_uses_one_publication_entry":
            "c2_overlay_call(LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT, &c2aw)"
                in runtime,
        "slot_abi_complete": all(token in header for token in (
            "LISP65_C2_APPEND_CRC_METADATA_SLOT 24u",
            "LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT 43u",
            "LISP65_C2_APPEND_ABORT_CONTROL_SLOT 46u")),
        "no_format_or_bank_change": "C2_APPEND_SECTION(\"crc_metadata\")"
            in runtime and "C2_APPEND_SECTION(\"publish_exports\")" in runtime,
    }
    require(all(checks.values()), "co-resident source contract red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "product_handoff_added_bytes": 0,
            "product_handoff_added_pointers": 0}


def compile_fixture(source: Path, stem: str, expected: str) -> dict[str, Any]:
    binary = OUT / stem
    command = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-fsanitize=address,undefined", str(source), "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run([str(binary)], cwd=ROOT, check=True,
                         capture_output=True, text=True)
    require(run.stdout.strip() == expected, f"{stem} output drift")
    stdout = OUT / f"{stem}.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    return {"status": "passed", "source": bind(source),
            "binary": bind(binary), "stdout": bind(stdout),
            "asan": "passed", "ubsan": "passed"}


def cutpoint_gates() -> dict[str, Any]:
    semantic = compile_fixture(
        SEMANTIC_FIXTURE, "semantic-split-cutpoints",
        "c2-lite-v6-semantic-split-cutpoints: PASS chains=5 negatives=15 "
        "handoff-bytes=0 handoff-pointers=0")
    fusion = compile_fixture(
        FUSION_FIXTURE, "coresident-cutpoints",
        "c2-lite-v6-coresident-cutpoints: PASS fusions=2 halves=4 "
        "negatives=8 added-state-bytes=0 added-pointers=0")
    fusion.update({"fusions": 2, "internal_halves": 4,
                   "negative_mutations": 8,
                   "product_handoff_added_bytes": 0,
                   "product_handoff_added_pointers": 0})
    return {"status": "passed", "semantic_splits": semantic,
            "co_resident_fusions": fusion}


def shared_semantics_gate() -> dict[str, Any]:
    original = PLAN.OUT
    PLAN.OUT = OUT / "shared-semantics"
    try:
        publication = PLAN.publication_model_gate()
        host, emitter = PLAN.shared_entry_emitter_gate()
    finally:
        PLAN.OUT = original
    protocol = COLD.publication_protocol_gate()
    return {"status": "passed", "publication": publication,
            "entry_emitter": emitter, "host_v6": host,
            "maximum_plan_protocol": protocol}


def run_one_wplto() -> tuple[dict[str, Any], Path, Path]:
    original_configure = BASE.configure
    original_features = BASE.FEATURES
    original_out = V6.OUT

    def configure() -> None:
        original_configure()
        configure_coresident_diet()

    BASE.configure = configure
    BASE.FEATURES = (*original_features,
                     "LISP65_C2_PHASE11_SPLIT",
                     "LISP65_C2_LITE_COLD_EVICTION",
                     "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
                     "LISP65_C2_LITE_V6_CORESIDENT_DIET")
    V6.OUT = OUT
    try:
        result = V6.full_product_wplto()
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
        V6.OUT = original_out
    target = OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    require(target.is_file() and elf.is_file(), "green WPLTO artifacts absent")
    return result, target, elf


def capacity_gate(wplto: dict[str, Any], elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    fused = {
        "crc_metadata": truth.section(
            ".lisp65_rt_c2append_crc_metadata").bytes,
        "publish_exports": truth.section(
            ".lisp65_rt_c2append_publish_exports").bytes,
    }
    require(0 < fused["crc_metadata"] <= CAP,
            "crc+metadata fusion exceeds slice cap")
    require(0 < fused["publish_exports"] <= PUBLISH_QUANTUM_CEILING,
            "publication fusion did not cross the required 1024-byte quantum")
    retired = (
        ".lisp65_rt_c2append_crc", ".lisp65_rt_c2append_metadata",
        ".lisp65_rt_c2append_publish_names",
        ".lisp65_rt_c2append_publish_cells")
    survived = {name: name in truth.sections_by_name for name in retired}
    require(not any(survived.values()), "fusion predecessor survived: "
            + str(survived))
    sections = [spec.split(":")[2] for spec in PRODUCT.SESSION_SLICE_SPECS]
    sizes = [truth.section(section).bytes for section in sections]
    modeled = packed_bytes(sizes)
    session = wplto["successor_bank3_pack"]["session"]
    configured_runtime_sections = {
        spec.split(":")[2] for spec in
        PRODUCT.BOOT_SLICE_SPECS + PRODUCT.SESSION_SLICE_SPECS
    }
    require(len(sections) == 51
            and wplto["runtime_slices"]["count"]
                == len(configured_runtime_sections)
            and modeled == session["bytes"] <= BANK_BYTES
            and session["headroom_bytes"] == BANK_BYTES - modeled,
            "co-resident aggregate pack accounting red")
    return {
        "status": "passed", "slice_cap_bytes": CAP,
        "pack_quantum_bytes": PACK_QUANTUM,
        "fused_section_bytes": fused,
        "fused_section_headroom": {
            "crc_metadata_to_cap": CAP - fused["crc_metadata"],
            "publish_exports_to_quantum_ceiling":
                PUBLISH_QUANTUM_CEILING - fused["publish_exports"],
        },
        "retired_sections_present": survived,
        "session_catalog_records_before": 53,
        "session_catalog_records_after": len(sections),
        "configured_unique_runtime_slice_sections":
            len(configured_runtime_sections),
        "removed_catalog_records": 2,
        "session_raw_payload_bytes": sum(sizes),
        "session_family_bytes": modeled,
        "session_family_headroom_bytes": BANK_BYTES - modeled,
    }


def semantic_product_gate(wplto: dict[str, Any], target: Path,
                          elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    facade16 = contract.get("append_plan_facade16_successor_geometry", {})
    append_final_authority = (
        contract.get("status") ==
            "owner-authorized: append-plan facade vector 16 and full "
            "three-byte successor repin"
        and contract.get("decision", {}).get("e000_active_floor_bytes") == 54
        and facade16.get("status") ==
            "owner-authorized-pending-fresh-WPLTO")
    publication_section = (
        ".lisp65_rt_c2append_publish_clear" if append_final_authority
        else ".lisp65_rt_c2append_publish_exports")
    active_e000_floor = (54 if append_final_authority else E000_FLOOR)
    forbidden = ("c2_stream_product_child_value", "c2_entry_records",
                 "c2_source_read")
    cold = {name: len(truth.symbols_by_name.get(name, [])) for name in forbidden}
    require(not any(cold.values()), "cold tenant survived: " + str(cold))
    generated = target.parent / "generated-product-sources/c2_product_runtime.c"
    source = generated.read_text(encoding="utf-8")
    crc = V6.c_function_definition(source, "c2_append_crc_metadata_phase")
    publish = V6.c_function_definition(source, "c2_append_publish_exports_phase")
    hot = V6.c_function_definition(source, "c2_product_entry_read")
    retired_phase_symbols = (
        "c2_append_crc_phase", "c2_append_metadata_phase",
        "c2_append_publish_names_phase", "c2_append_publish_cells_phase")
    checks = {
        "only_fused_crc_metadata_emitted":
            not truth.symbols_by_name.get("c2_append_crc_phase")
            and not truth.symbols_by_name.get("c2_append_metadata_phase")
            and truth.symbol("c2_append_crc_metadata_phase").section
                == ".lisp65_rt_c2append_crc_metadata",
        "only_fused_publication_emitted":
            not truth.symbols_by_name.get("c2_append_publish_names_phase")
            and not truth.symbols_by_name.get("c2_append_publish_cells_phase")
            and truth.symbol("c2_append_publish_exports_phase").section
                == publication_section
            and (not append_final_authority
                 or ".lisp65_rt_c2append_publish_exports"
                    not in truth.sections_by_name),
        "fused_entries_are_source_free_where_required":
            "c2_stream_shelf_read" not in publish
            and "c2_source_read" not in publish,
        "fused_entries_do_not_call_overlays":
            "c2_overlay_call" not in crc and "c2_overlay_call" not in publish,
        "hot_entry_source_and_locator_free":
            "c2_stream_shelf_read" not in hot and "c2_source_read" not in hot
            and "+ 23" not in hot,
        "shared_entry_emitter_present":
            V6.c_function_definition(source, "c2_append_entries_phase").count(
                "c2d_v6_emit_entry_row") == 1,
        "restored_e000_floor": wplto["walls"]["e000_headroom_bytes"]
            >= active_e000_floor,
    }
    require(all(checks.values()), "co-resident product semantic gate red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "authority_model": {
                "append_final": append_final_authority,
                "publication_section": publication_section,
                "e000_floor_bytes": active_e000_floor,
            },
            "retired_cold_symbols": cold,
            "retired_phase_symbols": {
                name: len(truth.symbols_by_name.get(name, []))
                for name in retired_phase_symbols},
            "generated_runtime": bind(generated)}


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def record_first_red(error: BaseException) -> None:
    evidence = []
    if OUT.exists():
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                evidence.append(bind(path))
    value = {
        "format": "lisp65-c2-lite-v6-coresident-diet-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: co-resident aggregate-diet contract or WPLTO",
        "failure": str(error),
        "scope": {"whole_program_lto_attempts": int(
            (OUT / "full-product-wplto").exists()),
            "product_links": 0, "hardware_runs": 0, "promotable": False},
        "evidence": evidence,
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review; no retry or product link",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "co-resident probe is one-shot and already exists")
    for path in (CONTRACT, ADDENDUM, BASELINE_ELF, BASELINE_MANIFEST,
                 PRESPLIT_MAP, SEMANTIC_ELF, SEMANTIC_RECEIPT,
                 PLACEMENT_FIRST_RED, SEMANTIC_FIXTURE, FUSION_FIXTURE):
        require(path.is_file(), f"probe authority absent: {path}")
    OUT.mkdir(parents=True)
    attribution = payload_attribution_gate()
    source = source_contract_gate()
    cutpoints = cutpoint_gates()
    semantics = shared_semantics_gate()
    write_json(OUT / "payload-attribution-and-pack-model.json", attribution)
    write_json(OUT / "source-contract-gate.json", source)
    write_json(OUT / "cutpoint-gates.json", cutpoints)
    write_json(OUT / "shared-semantics-gate.json", semantics)

    wplto, target, elf = run_one_wplto()
    structural = COLD.structural_gates(target, elf)
    capacity = capacity_gate(wplto, elf)
    semantic = semantic_product_gate(wplto, target, elf)
    root = ROOT_GATE.collect()
    require(root["status"] == "pass", "permanent root-surrogate gate red")
    value = {
        "format": "lisp65-c2-lite-v6-coresident-diet-wplto-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-co-resident-aggregate-diet-one-product-shaped-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"contract": bind(CONTRACT), "addendum": bind(ADDENDUM),
                      "semantic_first_red": bind(SEMANTIC_RECEIPT),
                      "placement_first_red": bind(PLACEMENT_FIRST_RED)},
        "payload_attribution": attribution,
        "source_contract": source,
        "cutpoint_fixtures": cutpoints,
        "shared_semantics": semantics,
        "whole_program_lto": wplto,
        "co_resident_capacity": capacity,
        "product_semantics": semantic,
        "permanent_root_surrogate_gate": root,
        "fresh_structural_gates": structural,
        "artifacts": {"measurement_prg": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
        "claim_limit": (
            "Two atomic co-resident slices and one nonpromotable product-shaped "
            "WPLTO. No product link, hardware, performance, promotion or "
            "acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    write_json(OUT / "coresident-diet-wplto-probe.json", value)
    value["probe_report"] = bind(OUT / "coresident-diet-wplto-probe.json")
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, RuntimeError) as error:
        if OUT.exists() and not RECEIPT.exists():
            record_first_red(error)
        print("c2-lite-v6-coresident-diet: FIRST RED " + str(error))
        return 2
    capacity = value["co_resident_capacity"]
    print("c2-lite-v6-coresident-diet: PASS "
          f"records={capacity['session_catalog_records_after']} "
          f"session={capacity['session_family_bytes']} "
          f"headroom={capacity['session_family_headroom_bytes']} "
          f"e000={value['whole_program_lto']['walls']['e000_headroom_bytes']} "
          "product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
