#!/usr/bin/env python3
"""Build the authorized Link 41 after roots/fronts aggregate recovery."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_family_slot_derived_identity_wplto as FAMILY  # noqa: E402
import c2_lite_v6_real_abi_direct_entry_contract as CURRENT_DIRECT  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_successor_link as LINK  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = LINK.P
BASE_LINK = LINK.BASE_LINK
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-41-c2-lite-v6-roots-fronts-coresident")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "a683a2e9b3be92b41bcc5ef0013f0e1c7ef379a63c26f4fe1883a21508bf44a0")
BASELINE_RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link40-c2-lite-v6-real-abi-e000-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "97811a742ba748105d5b3fcd93e42f95649e745249212f94713e888554ffbe58")
WPLTO = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-link40-roots-fronts-coresident-wplto-"
    "artifact-replay-receipt.json")
WPLTO_SHA = (
    "9c80b6a65a22854ec2478f0d53f3373a55b3cb3281ff126d34d7a0a8d0941add")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
PRELINK_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "structural-receipt.json")
PRELINK_FIRST_RED_SHA = (
    "f1d346766709edc8788360a0eb0335476a5eb27eef6c2aaa4824276c6d980468")
PRELINK_REPLAY_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "replay-structural-receipt.json")
PRELINK_REPLAY_FIRST_RED_SHA = (
    "6d168fba789a126f2163cefeeb00e0ec8d1971a2ac529171742dcc8195000617")
PROFILE_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-profile-first-red-"
    "diagnosis.json")
PROFILE_FIRST_RED_SHA = (
    "33942f30a848b51a9a8b3f87d5e291ceb9ca41c0e3217fb8033858f8583e0303")
EXPECTED_SESSION_BYTES = 65438
EXPECTED_SESSION_HEADROOM = 98


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            WPLTO: WPLTO_SHA,
            PRELINK_FIRST_RED: PRELINK_FIRST_RED_SHA,
            PRELINK_REPLAY_FIRST_RED: PRELINK_REPLAY_FIRST_RED_SHA,
            PROFILE_FIRST_RED: PROFILE_FIRST_RED_SHA}.items():
        LINK.require(path.is_file() and LINK.sha(path) == digest,
                     f"Link-41 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    profile = PROFILE.check()
    LINK.require(
        baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and baseline["link_number"] == 40
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-40 rollback identity is not authoritative")
    LINK.require(
        qualified["status"] ==
            "passed-roots-fronts-WPLTO-artifact-only-replay"
        and qualified["aggregate_recovery"]["session_family_bytes"] ==
            EXPECTED_SESSION_BYTES
        and qualified["aggregate_recovery"]["session_family_headroom_bytes"] ==
            EXPECTED_SESSION_HEADROOM
        and qualified["aggregate_recovery"]["slice"]["bytes"] == 1473
        and qualified["product_shaped_wplto"]["fresh_gates"]["status"] ==
            "passed-artifact-only-complete-gate-replay",
        "roots/fronts WPLTO authority is not fully green")
    LINK.require(
        contract["roots_fronts_aggregate_recovery"]["status"] ==
            "class-c-approved-and-wplto-passed"
        and contract["roots_fronts_aggregate_recovery"]
            ["session_family_headroom_bytes"] == EXPECTED_SESSION_HEADROOM,
        "roots/fronts contract binding is absent")
    return {
        "link40_rollback_product": LINK.bind(BASELINE),
        "link40_structural_authority": LINK.bind(BASELINE_RECEIPT),
        "roots_fronts_green_wplto": LINK.bind(WPLTO),
        "stale_direct_entry_authority_first_red":
            LINK.bind(PRELINK_FIRST_RED),
        "stale_direct_entry_check_tool_first_red":
            LINK.bind(PRELINK_REPLAY_FIRST_RED),
        "current_v6_direct_entry_authority":
            LINK.bind(CURRENT_DIRECT.RECEIPT),
        "profile_selection_first_red": LINK.bind(PROFILE_FIRST_RED),
        "canonical_roots_fronts_product_profile": profile,
        "c2_lite_contract": LINK.bind(CONTRACT),
        "c2_lite_addendum": LINK.bind(ADDENDUM),
        "driver": LINK.bind(Path(__file__)),
    }


def capacity_gate(shape: dict[str, Any], elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    sections = [spec.split(":")[2] for spec in P.SESSION_SLICE_SPECS]
    sizes = [truth.section(section).bytes for section in sections]
    modeled = BASE_LINK.DIET.packed_bytes(sizes)
    session = shape["successor_bank3_pack"]["session"]
    fused = truth.section(".lisp65_rt_c2append_roots_fronts")
    append_contract = json.loads(
        (ROOT / "config/c2-lite-execution-contract.json").read_text(
            encoding="utf-8"))
    facade16 = append_contract.get(
        "append_plan_facade16_successor_geometry", {})
    current_append_geometry = (
        append_contract.get("status") ==
            "owner-authorized: append-plan facade vector 16 and full "
            "three-byte successor repin"
        and append_contract.get("decision", {}).get(
            "e000_active_floor_bytes") == 54
        and facade16.get("status") ==
            "owner-authorized-pending-fresh-WPLTO")
    publication_section = (
        ".lisp65_rt_c2append_publish_clear" if current_append_geometry
        else ".lisp65_rt_c2append_publish_exports")
    publication = truth.section(publication_section)
    retired = {name: name in truth.sections_by_name for name in (
        ".lisp65_rt_c2append_crc", ".lisp65_rt_c2append_metadata",
        ".lisp65_rt_c2append_roots", ".lisp65_rt_c2append_fronts",
        ".lisp65_rt_c2append_publish_names",
        ".lisp65_rt_c2append_publish_cells")}
    if current_append_geometry:
        retired.update({name: name in truth.sections_by_name for name in (
            ".lisp65_rt_c2append_publish_exports",
            ".lisp65_rt_c2append_journal_clear")})
    configured = {spec.split(":")[2] for spec in
                  P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    expected_session_records = 49 if current_append_geometry else 50
    expected_append_records = 22 if current_append_geometry else 23
    LINK.require(len(sections) == expected_session_records
                 and len(P.C2_APPEND_SLICES) == expected_append_records
                 and modeled == session["bytes"] == EXPECTED_SESSION_BYTES
                 and session["headroom_bytes"] == EXPECTED_SESSION_HEADROOM
                 and shape["runtime_slices"]["count"] == len(configured)
                 and 0 < fused.bytes <= RF.CAP
                 and 0 < publication.bytes <= RF.CAP
                 and not any(retired.values()),
                 "Link-41 roots/fronts aggregate accounting red")
    return {
        "status": "passed",
        "slice_cap_bytes": RF.CAP,
        "pack_quantum_bytes": RF.PACK_QUANTUM,
        "fused_section_bytes": {
            "crc_metadata": truth.section(
                ".lisp65_rt_c2append_crc_metadata").bytes,
            "roots_fronts": fused.bytes,
            "publication": publication.bytes},
        "publication_section": publication_section,
        "current_append_geometry": current_append_geometry,
        "retired_sections_present": retired,
        "session_catalog_records_before": 51,
        "session_catalog_records_after": len(sections),
        "removed_catalog_records_total": (
            4 if current_append_geometry else 3),
        "session_raw_payload_bytes": sum(sizes),
        "session_family_bytes": modeled,
        "session_family_headroom_bytes": EXPECTED_SESSION_HEADROOM,
    }


def roots_fronts_product_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_rt_c2append_roots_fronts")
    symbols = {name: truth.symbol(name) for name in (
        "c2_append_roots_phase", "c2_append_fronts_phase",
        "c2_append_roots_fronts_phase")}
    LINK.require(0 < section.bytes <= RF.CAP
                 and all(symbol.section == section.name and symbol.bytes > 0
                         for symbol in symbols.values())
                 and ".lisp65_rt_c2append_roots" not in truth.sections_by_name
                 and ".lisp65_rt_c2append_fronts" not in
                     truth.sections_by_name,
                 "linked roots/fronts one-slice/two-entry gate red")
    session = OUT / "runtime-overlays-session-final.bin"
    LINK.require(session.stat().st_size == EXPECTED_SESSION_BYTES,
                 "linked roots/fronts Session family drift")
    return {
        "status": "passed-one-slice-two-entry-linked-product",
        "section": {"name": section.name, "address": section.address,
                    "bytes": section.bytes,
                    "headroom_bytes": RF.CAP - section.bytes},
        "entries": {name: {"address": symbol.value,
                           "bytes": symbol.bytes,
                           "section": symbol.section}
                    for name, symbol in symbols.items()},
        "session_family_bytes": session.stat().st_size,
        "session_family_headroom_bytes":
            RF.BANK_BYTES - session.stat().st_size,
    }


def main() -> int:
    LINK.require(not OUT.exists() and not RECEIPT.exists(),
                 "Link 41 is one-shot")
    old = {
        "out": LINK.OUT, "receipt": LINK.RECEIPT,
        "number": LINK.LINK_NUMBER, "baseline": LINK.BASELINE,
        "baseline_sha": LINK.BASELINE_SHA,
        "prerequisites": LINK.prerequisites,
        "configure": BASE_LINK.configure_profile,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "replacement": BASE_LINK.replacement_gates,
        "capacity": BASE_LINK.DIET.capacity_gate,
        "single_link": P.single_link,
        "direct_value": LINK.LITE_DIRECT.value,
        "direct_receipt": LINK.LITE_DIRECT.RECEIPT,
    }

    def configure() -> tuple[str, ...]:
        legacy = old["configure"]()
        RF.configure_roots_fronts()
        PROFILE.check_legacy_configuration((*legacy, RF.FEATURE))
        features = PROFILE.feature_defines()
        return features

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        rf_out = OUT / "fresh-c2-lite-prelink-gates/roots-fronts"
        family_out = OUT / "fresh-c2-lite-prelink-gates/family-slot"
        rf_out.mkdir(parents=True)
        family_out.mkdir(parents=True)
        old_rf_out, old_family_out = RF.OUT, FAMILY.OUT
        try:
            RF.OUT = rf_out
            cutpoints = RF.cutpoint_gate()
            source = RF.source_gate()
            FAMILY.OUT = family_out
            family_host = FAMILY.host_gate()
            family_source = FAMILY.source_gate(
                FAMILY.SOURCE.read_text(encoding="utf-8"))
        finally:
            RF.OUT, FAMILY.OUT = old_rf_out, old_family_out
        LINK.require(cutpoints["negative_cases"] == 6
                     and family_host["cartesian_cases"] == 8,
                     "Link-41 fresh fusion/family prelink gate red")
        value["roots_fronts_cutpoints"] = cutpoints
        value["roots_fronts_source"] = source
        value["family_slot_host_matrix"] = family_host
        value["family_slot_source"] = family_source
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        old_family_out = FAMILY.OUT
        try:
            FAMILY.OUT = OUT
            family = FAMILY.closure_gate(product, elf)
        finally:
            FAMILY.OUT = old_family_out
        value["derived_family_slot_closure"] = family
        value["roots_fronts_one_slice_two_entry"] = (
            roots_fronts_product_gate(elf))
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        kwargs["direct_entry_receipt"] = CURRENT_DIRECT.RECEIPT
        kwargs["direct_entry_check_tool"] = (
            "c2_lite_v6_real_abi_direct_entry_contract.py")
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=")))
        profile_rows = [line.split("=", 1)[1] for line in lines
                        if line.startswith("feature_defines=")]
        LINK.require(len(profile_rows) == 1,
                     "product-link entry has no unique feature profile")
        profile_features = tuple(profile_rows[0].split(","))
        PROFILE.compare_link_entry(profile_features)
        kwargs["extra_contract_lines"] = (
            "mode=link41-c2-lite-v6-roots-fronts-coresident",
            "source_baseline=link40-c2-lite-v6-real-abi-e000",
            "roots_fronts_one_physical_record_two_entries=required",
            "roots_fronts_wplto_authority_sha256=" + WPLTO_SHA,
            "canonical_product_profile="
                + PROFILE.PROFILE.relative_to(ROOT).as_posix(),
            "canonical_product_profile_sha256=" + PROFILE.sha(PROFILE.PROFILE),
            "canonical_wplto_profile_sha256="
                + PROFILE.value()["authority"]["green_wplto_profile"]
                    ["sha256"],
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK.OUT = OUT
        LINK.RECEIPT = RECEIPT
        LINK.LINK_NUMBER = 41
        LINK.BASELINE = BASELINE
        LINK.BASELINE_SHA = BASELINE_SHA
        LINK.prerequisites = prerequisites
        BASE_LINK.configure_profile = configure
        BASE_LINK.fresh_prelink_gates = prelink
        BASE_LINK.replacement_gates = replacement
        BASE_LINK.DIET.capacity_gate = capacity_gate
        P.single_link = single_link
        LINK.LITE_DIRECT.value = CURRENT_DIRECT.value
        LINK.LITE_DIRECT.RECEIPT = CURRENT_DIRECT.RECEIPT
        value = LINK.build()
    finally:
        LINK.OUT = old["out"]
        LINK.RECEIPT = old["receipt"]
        LINK.LINK_NUMBER = old["number"]
        LINK.BASELINE = old["baseline"]
        LINK.BASELINE_SHA = old["baseline_sha"]
        LINK.prerequisites = old["prerequisites"]
        BASE_LINK.configure_profile = old["configure"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        BASE_LINK.replacement_gates = old["replacement"]
        BASE_LINK.DIET.capacity_gate = old["capacity"]
        P.single_link = old["single_link"]
        LINK.LITE_DIRECT.value = old["direct_value"]
        LINK.LITE_DIRECT.RECEIPT = old["direct_receipt"]
    print("c2-lite-v6-roots-fronts-successor-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
