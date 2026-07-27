#!/usr/bin/env python3
"""One L65R-v2 boot-family evacuation WPLTO probe; no product Link 33."""

from __future__ import annotations

import argparse
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
import c2_l65r_v2_product_probe as BASE  # noqa: E402
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import elf_truth as ELF  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-boot-family-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-boot-family-capacity-probe-receipt.json")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-product-implementation-capacity-probe-receipt.json")
CONTRACT = ROOT / "config/c2-l65r-v2-boot-family-contract.json"
FIRST_RED_RECEIPT_SHA = (
    "76a15b6aa31e914a02eee603b5ff063ca9ded32c38a2d7dc3680431692bd6646")
FIRST_RED_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-product-probe/"
    "l65r-v2-island-seed.prg.map")
FIRST_RED_MAP_SHA = (
    "f70864c84265ce18e42e5eff9acfbbec6f60afb621ce5f2b3ccf42e319682c49")
PRE_V2_MAP = ROOT / (
    "build/c2.2/substitution/product-link-33-profile-inventory-final/"
    "resident-island-seed.prg.map")
PRE_V2_MAP_SHA = (
    "88e1eb02bfb06f0eb667678938ef2c7bda5d0d2c25dc5f41b4093bd59187d954")
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
FEATURES = PROFILE.feature_defines()
INSTALLER_SECTION = ".lisp65_rt_island_00"
INSTALLER_FUNCTIONS = {
    "vm_resident_island_install",
    "rtov_island_u16",
    "rtov_island_build_id",
    "rtov_island_source_crc",
}
RUNTIME_OVERLAY_VMA_MARKER = "__lisp65_workbench_runtime_overlay_vma"
RUNTIME_OVERLAY_VMA = 0xC356


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def _lifetime_errors(*, boot_names: set[str], session_names: set[str],
                     helper_sections: dict[str, str], source: str,
                     main_source: str) -> list[str]:
    errors: list[str] = []
    if "resident-island-installer" not in boot_names or \
            "resident-island-image" not in boot_names:
        errors.append("boot-installation-record-missing")
    if {"resident-island-installer", "resident-island-image"} & session_names:
        errors.append("installation-record-reachable-from-session-catalog")
    misplaced = sorted(name for name in INSTALLER_FUNCTIONS
                       if helper_sections.get(name) != INSTALLER_SECTION)
    if misplaced:
        errors.append("installer-helper-outside-single-boot-slice:" +
                      ",".join(misplaced))
    latch = (
        "family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT\n"
        "            && rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE")
    if latch not in source:
        errors.append("boot-family-reentry-latch-absent")
    install = main_source.find("vm_runtime_overlay_install_island()")
    session = main_source.find("c2_product_boot()")
    repl = main_source.find("repl()")
    if install < 0 or session < 0 or repl < 0 or not install < session < repl:
        errors.append("installer-not-strictly-before-session-and-repl")
    return errors


def lifetime_model_selftest() -> dict[str, str]:
    runtime = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    main = (ROOT / "src/main.c").read_text(encoding="utf-8")
    boot = {"resident-island-installer", "resident-island-image"}
    sections = {name: INSTALLER_SECTION for name in INSTALLER_FUNCTIONS}
    require(not _lifetime_errors(
        boot_names=boot, session_names=set(), helper_sections=sections,
        source=runtime, main_source=main),
        "valid boot lifetime model rejected")
    mutations = {
        "installer-in-session-catalog": dict(
            boot_names=boot,
            session_names={"resident-island-installer"},
            helper_sections=sections, source=runtime, main_source=main),
        "helper-in-third-section": dict(
            boot_names=boot, session_names=set(),
            helper_sections={**sections,
                             "rtov_island_source_crc": ".lisp65_rt_island_01"},
            source=runtime, main_source=main),
        "reentry-latch-removed": dict(
            boot_names=boot, session_names=set(), helper_sections=sections,
            source=runtime.replace(
                "family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT\n"
                "            && rtov_family != "
                "LISP65_RUNTIME_OVERLAY_FAMILY_INACTIVE",
                "family == LISP65_RUNTIME_OVERLAY_FAMILY_BOOT && 0"),
            main_source=main),
        "installer-after-session": dict(
            boot_names=boot, session_names=set(), helper_sections=sections,
            source=runtime,
            main_source=main.replace(
                "boot_overlay_result = (uint8_t)"
                "vm_runtime_overlay_install_island();",
                "/* moved after session */") +
                "\nvm_runtime_overlay_install_island();\n"),
    }
    result: dict[str, str] = {}
    for name, args in mutations.items():
        require(_lifetime_errors(**args),
                f"boot lifetime mutation accepted: {name}")
        result[name] = "rejected"
    return result


def _installer_relocation_provenance(
        records: list[dict[str, object]], *,
        section_names: set[str],
        symbol_sections: dict[str, set[str]],
        symbol_values: dict[str, int],
        registered_absolute_markers: dict[str, int] | None = None,
        installer_start: int,
        installer_end: int) -> tuple[
            list[dict[str, object]], list[dict[str, object]]]:
    """Classify installer ownership by ELF provenance, never by bare VMA."""
    installer_records: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    absolute_markers = registered_absolute_markers or {}
    for record in records:
        target = str(record["target"])
        if target in section_names:
            candidates = {target}
        else:
            candidates = set(symbol_sections.get(target, set()))
        value = symbol_values.get(target)
        numeric_overlap = (value is not None
                           and installer_start <= value < installer_end)
        if len(candidates) > 1 and (
                INSTALLER_SECTION in candidates or numeric_overlap):
            errors.append({
                "reason": "ambiguous-installer-target-provenance",
                "record": record,
                "candidate_sections": sorted(candidates),
            })
            continue
        if not candidates:
            if numeric_overlap:
                errors.append({
                    "reason": "unresolved-installer-vma-target",
                    "record": record,
                })
            continue
        target_section = next(iter(candidates))
        if target_section == "Absolute" and numeric_overlap:
            if absolute_markers.get(target) != value:
                errors.append({
                    "reason": "unregistered-absolute-overlay-marker",
                    "record": record,
                })
            continue
        if target_section != INSTALLER_SECTION:
            # Equal numeric addresses are expected in the fixed-overlay model.
            continue
        bound = {**record, "target_section": target_section}
        installer_records.append(bound)
        if str(record["source_section"]) != INSTALLER_SECTION:
            errors.append({
                "reason": "external-edge-into-installer",
                "record": bound,
            })
    return installer_records, errors


def lifetime_relocation_model_selftest() -> dict[str, str]:
    sections = {INSTALLER_SECTION, ".lisp65_workbench_overlay",
                ".lisp65_rt_buffer_alloc", ".text"}
    start = 0xC356
    end = 0xC84F

    def classify(records: list[dict[str, object]], *,
                 owners: dict[str, set[str]],
                 values: dict[str, int]) -> list[dict[str, object]]:
        _matched, errors = _installer_relocation_provenance(
            records, section_names=sections, symbol_sections=owners,
            symbol_values=values, registered_absolute_markers={},
            installer_start=start,
            installer_end=end)
        return errors

    base = {
        "source_section": ".text", "offset": 1,
        "type": "R_MOS_ADDR16", "addend": 0,
    }
    same_vma = [{**base, "target": "neighbor_at_c356"}]
    require(not classify(
        same_vma,
        owners={"neighbor_at_c356": {".lisp65_workbench_overlay"}},
        values={"neighbor_at_c356": start}),
        "section-qualified equal-VMA neighbor was rejected")

    external_symbol = [{**base, "target": "vm_resident_island_install"}]
    require(classify(
        external_symbol,
        owners={"vm_resident_island_install": {INSTALLER_SECTION}},
        values={"vm_resident_island_install": 0xC4C8}),
        "external installer-symbol edge was accepted")

    external_addend = [{**base, "target": INSTALLER_SECTION, "addend": 64}]
    require(classify(external_addend, owners={}, values={}),
            "external installer-section/addend edge was accepted")

    ambiguous = [{**base, "target": "ambiguous_at_c356"}]
    require(classify(
        ambiguous,
        owners={"ambiguous_at_c356": {
            INSTALLER_SECTION, ".lisp65_workbench_overlay"}},
        values={"ambiguous_at_c356": start}),
        "ambiguous installer target provenance was accepted")

    return {
        "same-vma-neighbor-section": "accepted",
        "external-installer-symbol": "rejected",
        "external-installer-section-addend": "rejected",
        "ambiguous-installer-provenance": "rejected",
    }


def lifetime_symbol_provenance_selftest() -> dict[str, str]:
    sections = {INSTALLER_SECTION, ".lisp65_workbench_overlay", ".text"}
    start = RUNTIME_OVERLAY_VMA
    end = 0xC84F
    base = {
        "source_section": ".text", "offset": 1,
        "type": "R_MOS_ADDR16", "addend": 0,
    }

    def errors(target: str, owners: set[str], *, value: int,
               markers: dict[str, int] | None = None) -> list[dict[str, object]]:
        _matched, result = _installer_relocation_provenance(
            [{**base, "target": target}], section_names=sections,
            symbol_sections={target: owners}, symbol_values={target: value},
            registered_absolute_markers=markers,
            installer_start=start, installer_end=end)
        return result

    require(not errors(
        "__lisp65_workbench_overlay_start",
        {".lisp65_workbench_overlay"}, value=start),
        "section-bound workbench marker rejected")
    require(not errors(
        RUNTIME_OVERLAY_VMA_MARKER, {"Absolute"}, value=start,
        markers={RUNTIME_OVERLAY_VMA_MARKER: start}),
        "registered Absolute runtime-overlay marker rejected")
    require(errors("unknown_at_c356", {"Absolute"}, value=start),
            "unknown Absolute overlay marker accepted")
    require(errors("installer_target", {INSTALLER_SECTION}, value=0xC4C8),
            "external installer target accepted")
    return {
        "structured-section-bound-workbench-marker": "accepted",
        "registered-absolute-runtime-vma-marker": "accepted",
        "unknown-absolute-at-same-vma": "rejected",
        "external-installer-target-after-parser": "rejected",
    }


def boot_lifetime_gate(elf: Path, boot_manifest: dict[str, Any],
                       session_manifest: dict[str, Any]) -> dict[str, Any]:
    truth = ELF.ElfTruth.read(
        elf, llvm_readobj=TOOLCHAIN / "llvm-readobj",
        absolute_markers={RUNTIME_OVERLAY_VMA_MARKER: RUNTIME_OVERLAY_VMA})
    helper_sections = {
        name: truth.symbol(name).section for name in INSTALLER_FUNCTIONS}
    boot_names = {str(row["name"]) for row in boot_manifest["slices"]}
    session_names = {str(row["name"]) for row in session_manifest["slices"]}
    runtime = (ROOT / "src/vm_runtime_overlay.c").read_text(encoding="utf-8")
    main = (ROOT / "src/main.c").read_text(encoding="utf-8")
    errors = _lifetime_errors(
        boot_names=boot_names, session_names=session_names,
        helper_sections=helper_sections, source=runtime, main_source=main)
    require(not errors, f"FIRST RED: boot installer lifetime {errors}")
    installer_geometry = truth.section(INSTALLER_SECTION)
    geometry = {"address": installer_geometry.address,
                "bytes": installer_geometry.bytes}
    require(0 < geometry["bytes"] <= 1792,
            f"FIRST RED: boot installer slice size {geometry['bytes']}")

    installer_start = geometry["address"]
    installer_end = installer_start + geometry["bytes"]
    relocation_records = [{
        "relocation_section": row.relocation_section,
        "source_section": row.source_section,
        "offset": row.offset,
        "type": row.relocation_type,
        "target": row.target,
        "addend": row.addend,
    } for row in truth.relocations]
    installer_relocations, relocation_errors = (
        _installer_relocation_provenance(
            relocation_records,
            section_names=set(truth.sections_by_name),
            symbol_sections=truth.section_symbol_sets(),
            symbol_values=truth.symbol_values(),
            registered_absolute_markers={
                RUNTIME_OVERLAY_VMA_MARKER: RUNTIME_OVERLAY_VMA},
            installer_start=installer_start,
            installer_end=installer_end))
    require(not relocation_errors,
            "FIRST RED: non-Boot relocation into installer "
            f"{relocation_errors}")
    installer_records = [row for row in boot_manifest["slices"]
                         if row["name"] == "resident-island-installer"]
    carrier_records = [row for row in boot_manifest["slices"]
                       if row["name"] == "resident-island-image"]
    require(len(installer_records) == len(carrier_records) == 1,
            "FIRST RED: installation story is not exactly two Boot records")
    require(installer_records[0]["section"] == INSTALLER_SECTION
            and carrier_records[0]["roles"] == ["boot", "data-only"],
            "FIRST RED: installation records escaped their contract")
    return {
        "status": "passed-single-boot-installer-lifetime-closure",
        "installer_section": geometry,
        "installer_functions": helper_sections,
        "boot_record_names": sorted(boot_names),
        "session_installation_records": [],
        "ownership_identity": "target-section-plus-symbol/addend-never-bare-vma",
        "elf_truth": {
            "source": "llvm-readobj-json",
            "sections": len(truth.sections),
            "symbols": len(truth.symbols),
            "overlapping_sections_at_runtime_vma": len(
                truth.sections_at_vma(RUNTIME_OVERLAY_VMA)),
            "registered_absolute_markers": {
                RUNTIME_OVERLAY_VMA_MARKER: RUNTIME_OVERLAY_VMA},
        },
        "retained_relocation_count": len(relocation_records),
        "installer_target_relocation_count": len(installer_relocations),
        "internal_installer_target_relocations": len(installer_relocations),
        "external_installer_target_relocations": 0,
        "outside_direct_edges": [],
        "one_way_family_latch": "inactive-to-boot-to-session-no-return",
        "negative_matrix": {
            **lifetime_model_selftest(),
            **lifetime_relocation_model_selftest(),
            **lifetime_symbol_provenance_selftest(),
        },
    }


def _text_function_sizes(path: Path) -> dict[str, int]:
    pattern = re.compile(
        r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
        r".*:\(\.text\.([^)]+)\)")
    result: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            result[match.group(2)] = result.get(match.group(2), 0) + int(
                match.group(1), 16)
    return result


def attribution(probe_map: Path) -> dict[str, Any]:
    require(sha(FIRST_RED_MAP) == FIRST_RED_MAP_SHA,
            "first-red map identity drift")
    require(sha(PRE_V2_MAP) == PRE_V2_MAP_SHA,
            "pre-v2 WPLTO map identity drift")
    before = _text_function_sizes(FIRST_RED_MAP)
    after = _text_function_sizes(probe_map)
    pre_v2 = _text_function_sizes(PRE_V2_MAP)
    named = ("vm_runtime_overlay_exec_family",
             "vm_runtime_overlay_install_island")
    return {
        "first_red_map": bind(FIRST_RED_MAP),
        "pre_v2_map": bind(PRE_V2_MAP),
        "functions": {
            name: {
                "pre_v2_bytes": pre_v2.get(name, 0),
                "first_red_bytes": before.get(name, 0),
                "boot_family_probe_bytes": after.get(name, 0),
                "reclaimed_from_first_red_bytes": (
                    before.get(name, 0) - after.get(name, 0)),
            } for name in named
        },
    }


def prerequisites() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-authorized-single-product-shaped-wplto-probe"
            and contract["placement"]["new_installation_sections"] == 0
            and contract["placement"]["session_reachability"] == "forbidden",
            "boot-family authorization contract drift")
    require(FIRST_RED_RECEIPT.is_file()
            and sha(FIRST_RED_RECEIPT) == FIRST_RED_RECEIPT_SHA,
            "L65R-v2 capacity first-red receipt drift")
    first = json.loads(FIRST_RED_RECEIPT.read_text(encoding="utf-8"))
    require(str(first.get("status", "")).startswith("FIRST RED")
            and first["scope"]["link33_attempts"] == 0,
            "predecessor is not the authorized first red")
    return {**BASE.prerequisites(), "boot_family_contract": bind(CONTRACT),
            "predecessor_first_red": bind(FIRST_RED_RECEIPT)}


def evidence_tree() -> list[dict[str, Any]]:
    return [bind(path) for path in sorted(OUT.rglob("*")) if path.is_file()]


def bind_first_red(error: BaseException, prereq: dict[str, Any]) -> dict[str, Any]:
    result = {
        "format": "lisp65-c2-l65r-v2-boot-family-capacity-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: sole boot-family WPLTO probe stopped",
        "diagnostic": {"type": type(error).__name__, "message": str(error)},
        "scope": {"link33_attempts": 0, "product_closure_links": 0,
                  "hardware_runs": 0, "retry_authorized": False},
        "prerequisites": prereq,
        "evidence": evidence_tree(),
        "rollback_line": {**bind(BASE.LINK32), "status": "untouched"},
        "next_gate": "review; no automatic retry or Link 33",
    }
    report = OUT / "l65r-v2-boot-family-capacity-first-red.json"
    write(report, json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = bind(report)
    write(RECEIPT, json.dumps(result, indent=2, sort_keys=True) + "\n")
    os.chmod(RECEIPT, 0o444)
    BASE.protect(OUT)
    return result


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "boot-family WPLTO probe is one-shot and already has output")
    BASE.configure()
    prereq = prerequisites()
    OUT.mkdir(parents=True)
    try:
        host = BASE.host_gate(OUT)
        artifacts_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
        artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
        P.write_v2_profile_report(OUT, artifacts)
        write(OUT / "c2-substitution.ld", P.linker_script())
        contract_lines = [
            "profile=" + P.PROFILE,
            "mode=l65r-v2-single-boot-installer-wplto-probe",
            "hardware_execution=prohibited",
            "product_link=not-run",
            "runtime_overlay_catalog_version=2",
            "runtime_overlay_decoder_versions=2-only",
            "boot_family_record_count=10",
            "boot_installer_slice_count=1",
            "resident_island_carrier_slot=9",
            "product_profile_object_sha256=" + PROFILE.sha256(),
            "c2_artifacts_sha256=" + sha(artifacts_path),
            "linker_sha256=" + sha(OUT / "c2-substitution.ld"),
        ]
        for source in P.source_list():
            path = Path(source)
            contract_lines.append(
                f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
        resolved = OUT / "resolved-profile.txt"
        write(resolved, "\n".join(contract_lines) + "\n")
        headers = BASE.build_headers(OUT, artifacts, resolved)
        seed = P.compile_link(
            OUT, "l65r-v2-boot-family-seed.prg", headers, artifacts,
            probe_definitions=FEATURES)
        island_header = OUT / "resident-island.h"
        P.tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
               "--nm", str(TOOLCHAIN / "llvm-nm"),
               "--objcopy", str(TOOLCHAIN / "llvm-objcopy"),
               "--abi-contract", str(resolved), "--header", str(island_header))
        final_headers = [headers[0], headers[1], island_header,
                         headers[3], headers[4]]
        probe = P.compile_link(
            OUT, "l65r-v2-boot-family-placement.prg", final_headers,
            artifacts, probe_definitions=FEATURES)
        elf = Path(str(probe) + ".elf")

        provisional = P.extract_provisional_kernal_window(OUT, probe)
        handoff = P.handoff_z_abi_gate(OUT, probe, "l65r-v2-boot-family")
        pre = P.pre_ownership_gate(OUT, probe, "l65r-v2-boot-family")
        data_refs = P.profile_data_reference_gate(
            OUT, probe, "l65r-v2-boot-family", pre)
        facade = P.fixed_facade_gate(OUT, probe, "l65r-v2-boot-family")
        boot_u = P.overlay_pack_family(OUT, probe, resolved, "boot", "unbound")
        session_u = P.overlay_pack_family(
            OUT, probe, resolved, "session", "unbound")
        binding = P.patch_verifier_binding_table(
            OUT, probe, boot_u[1], session_u[1])
        boot = P.overlay_pack_family(OUT, probe, resolved, "boot", "final")
        session = P.overlay_pack_family(OUT, probe, resolved, "session", "final")
        identity = P.runtime_family_identity_gate(
            OUT, boot_u, session_u, boot, session)
        write(OUT / "runtime-overlays-final.bin", session[0].read_bytes())
        P.closure_gate(OUT, probe)
        kernal = P.kernal_freedom_gate(OUT, probe)
        balance = P.substitution_balance(OUT, probe, kernal)
        preinstall = ISLAND.static_elf_gate(elf)
        boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
        session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
        lifetime = boot_lifetime_gate(elf, boot_manifest, session_manifest)

        sections = P.section_table(elf)
        text = sections[".text"]
        bss = sections[".bss"]
        walls = {
            "bank0_text_headroom_bytes": P.HANDOFF_BASE - text["address"] - text["bytes"],
            "ordinary_bank0_bss_headroom_bytes": (
                P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]),
            "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
            "resident_island_headroom_bytes": (
                2048 - sections[".lisp65_resident_island"]["bytes"] -
                sections[".lisp65_resident_island_annex"]["bytes"]),
            "e000_headroom_bytes": kernal["capacity"]["actual_future_margin_bytes"],
        }
        require(all(value >= 0 for value in walls.values()),
                f"FIRST RED: resident wall {walls}")
        require(walls["e000_headroom_bytes"] == 115,
                "FIRST RED: final E000 equation did not land at 115 bytes")
        installer = boot_manifest["slices"][8]
        carrier = boot_manifest["slices"][9]
        require(installer["name"] == "resident-island-installer"
                and carrier["name"] == "resident-island-image"
                and carrier["entry_offset"] == 0xffff
                and carrier["abi_version"] == 0
                and carrier["vma"] == 0x1800,
                "FIRST RED: two-record installation contract drift")
        require(installer["file_size"] <= 1792
                and carrier["file_size"] <= 1792,
                "FIRST RED: installer or carrier exceeds immutable cap")
        packer_mutations = BASE.packer_mutations(boot[0], boot[1])
        require(len(packer_mutations) == 10,
                "FIRST RED: packer mutation matrix incomplete")
        attr = attribution(Path(str(probe) + ".map"))
        result = {
            "format": "lisp65-c2-l65r-v2-boot-family-capacity-probe-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-boot-family-wplto-no-link33",
            "scope": {"whole_program_lto_probe_links": 2,
                      "product_closure_links": 0, "link33_attempts": 0,
                      "hardware_runs": 0},
            "prerequisites": prereq,
            "product_profile": PROFILE.receipt_identity(),
            "target_decoder": host,
            "boot_lifetime": lifetime,
            "preinstallation_island": preinstall,
            "records": {
                "installer": {"bytes": installer["file_size"],
                              "headroom_bytes": 1792 - installer["file_size"],
                              "section": installer["section"]},
                "carrier": {"bytes": carrier["file_size"],
                            "headroom_bytes": 1792 - carrier["file_size"],
                            "entry_offset": carrier["entry_offset"],
                            "destination": carrier["vma"],
                            "sha256": carrier["sha256"]},
            },
            "runtime_banks": {
                "boot": {"records": len(boot_manifest["slices"]),
                         "bytes": boot[0].stat().st_size,
                         "headroom_bytes": 65536 - boot[0].stat().st_size},
                "session": {"records": len(session_manifest["slices"]),
                            "bytes": session[0].stat().st_size,
                            "headroom_bytes": 65536 - session[0].stat().st_size},
            },
            "resident_walls": walls,
            "e000_equation": "531 - 416 - 6 = 115",
            "resident_attribution": attr,
            "packer_mutations": packer_mutations,
            "fresh_structural_gates": {
                "handoff": handoff["status"],
                "pre_ownership": pre["status"],
                "profile_data_references": data_refs["status"],
                "fixed_facade": facade["status"],
                "runtime_family_identity": identity["status"],
                "one_truth": "passed", "kernal_freedom": kernal["status"],
                # Extraction proves the 8-KiB shape.  Identity remains
                # deliberately provisional until the product publish-last
                # step, so it has a separate identity_status claim.
                "provisional_window": "passed",
                "verifier_publish_last": binding["status"],
            },
            "substitution_balance_probe": balance["status"],
            "artifacts": {"probe_prg": bind(probe), "probe_elf": bind(elf),
                          "boot_image": bind(boot[0]),
                          "boot_manifest": bind(boot[1]),
                          "session_image": bind(session[0]),
                          "session_manifest": bind(session[1]),
                          "resolved_profile": bind(resolved)},
            "claim_limit": (
                "Product-shaped WPLTO, pack, capacity, placement and static "
                "lifetime proof only; not Link 33, hardware or acceptance."),
            "next_gate": "fresh Link 33 with no inherited green",
        }
        report = OUT / "l65r-v2-boot-family-capacity-probe.json"
        write(report, json.dumps(result, indent=2, sort_keys=True) + "\n")
        result["report"] = bind(report)
        write(RECEIPT, json.dumps(result, indent=2, sort_keys=True) + "\n")
        os.chmod(RECEIPT, 0o444)
        BASE.protect(OUT)
        return result
    except (GateError, BASE.ProbeError, ISLAND.GateError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        if OUT.exists() and not RECEIPT.exists():
            return bind_first_red(error, prereq)
        raise


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "boot-family capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-boot-family-wplto-no-link33",
            "boot-family capacity receipt is not green")
    for row in value["artifacts"].values():
        path = ROOT / row["path"]
        require(path.is_file() and sha(path) == row["sha256"],
                f"boot-family artifact drift: {path}")
    require(sha(BASE.LINK32) == BASE.LINK32_SHA, "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        BASE.configure()
        mutations = {
            **lifetime_model_selftest(),
            **lifetime_relocation_model_selftest(),
            **lifetime_symbol_provenance_selftest(),
            **ELF.selftest(),
        }
        print("c2-l65r-v2-boot-family-probe: SELFTEST PASS mutations=" +
              str(len(mutations)))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-l65r-v2-boot-family-probe: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, BASE.ProbeError, ISLAND.GateError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print(f"c2-l65r-v2-boot-family-probe: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
