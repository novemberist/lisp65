#!/usr/bin/env python3
"""Build authorized Link 42 with final-carrier runtime identity only."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_final_island_identity_gate as IDENTITY  # noqa: E402
import c2_lite_v6_family_slot_derived_identity_wplto as FAMILY  # noqa: E402
import c2_lite_v6_real_abi_direct_entry_contract as CURRENT_DIRECT  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
import c2_lite_v6_roots_fronts_successor_link as LINK41  # noqa: E402


LINK = LINK41.LINK
BASE_LINK = LINK41.BASE_LINK
P = LINK41.P
LINK_NUMBER = 42
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-42-c2-lite-v6-final-island-identity")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-"
    "structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-41-c2-lite-v6-roots-fronts-coresident-replay3/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "91a5e69d7308dfc31123ff2421fe8b3de56f4a18491a8b35b3378212327ec405")
BASELINE_RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-"
    "replay3-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "d4836a3aab7398f372e029c919016d9c4fd9a5ce57867a90e590d17b80ca6ab8")
WPLTO = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-final-island-identity-wplto-"
    "artifact-replay-receipt.json")
WPLTO_SHA = (
    "e03d28bd240fce10e216fff5012f2ba51c02d3adfa8e6a4bdce840cde75af842")
HARDWARE_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-island-seed-identity-"
    "hardware-first-red.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
EXPECTED_SESSION_BYTES = 65438
EXPECTED_SESSION_HEADROOM = 98


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            WPLTO: WPLTO_SHA}.items():
        LINK.require(path.is_file() and LINK.sha(path) == digest,
                     f"Link-42 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    profile = PROFILE.check()
    LINK.require(
        baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and baseline["link_number"] == 41
        and baseline["product_identity"]["product"]["sha256"] ==
            BASELINE_SHA,
        "Link-41 rollback identity is not authoritative")
    LINK.require(
        qualified["status"] ==
            "passed-final-island-carrier-single-runtime-identity-"
            "WPLTO-artifact-replay"
        and qualified["final_island_identity_gate"]["status"] ==
            "passed-final-record-equals-final-island-single-truth"
        and qualified["final_island_identity_gate"]["mutation_cases"] == 11
        and qualified["active_runtime_host_matrix"]["carrier_bytes"] == 5
        and qualified["active_runtime_host_matrix"]
            ["seed_length_compile_constant"] == 4
        and qualified["aggregate_recovery"]["session_family_bytes"] ==
            EXPECTED_SESSION_BYTES
        and qualified["aggregate_recovery"]
            ["session_family_headroom_bytes"] == EXPECTED_SESSION_HEADROOM
        and qualified["product_shaped_wplto"]["fresh_gates"]["status"] ==
            "passed-artifact-only-complete-gate-replay",
        "final-Island WPLTO authority is not fully green")
    LINK.require(
        contract["status"] ==
            "class-c-approved-final-island-carrier-single-runtime-identity"
        and contract["final_island_carrier_identity"]["latency_attempts_consumed"]
            == "0/2",
        "final-Island Class-C authorization absent")
    return {
        "link41_rollback_product": LINK.bind(BASELINE),
        "link41_structural_authority": LINK.bind(BASELINE_RECEIPT),
        "final_island_green_wplto": LINK.bind(WPLTO),
        "link41_final_island_hardware_first_red":
            LINK.bind(HARDWARE_FIRST_RED),
        "current_v6_direct_entry_authority":
            LINK.bind(CURRENT_DIRECT.RECEIPT),
        "canonical_roots_fronts_product_profile": profile,
        "c2_lite_contract": LINK.bind(CONTRACT),
        "c2_lite_addendum": LINK.bind(ADDENDUM),
        "driver": LINK.bind(Path(__file__)),
    }


def capacity_gate(shape: dict[str, Any], elf: Path) -> dict[str, Any]:
    return LINK41.capacity_gate(shape, elf)


def roots_fronts_product_gate(elf: Path) -> dict[str, Any]:
    old_out = LINK41.OUT
    try:
        LINK41.OUT = OUT
        return LINK41.roots_fronts_product_gate(elf)
    finally:
        LINK41.OUT = old_out


def main() -> int:
    LINK.require(not OUT.exists() and not RECEIPT.exists(),
                 "Link 42 is one-shot")
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
        return PROFILE.feature_defines()

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
                     "Link-42 fresh fusion/family prelink gate red")
        value["roots_fronts_cutpoints"] = cutpoints
        value["roots_fronts_source"] = source
        value["family_slot_host_matrix"] = family_host
        value["family_slot_source"] = family_source
        value["final_island_single_identity_source"] = (
            IDENTITY.source_gate())
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
        value["final_island_single_runtime_identity"] = IDENTITY.audit(
            elf,
            OUT / "runtime-overlays-boot-final.bin",
            OUT / "runtime-overlays-boot-final.json",
            OUT / "generated-product-sources/vm_runtime_overlay.c",
            OUT / "final-island-single-runtime-identity.json")
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
        PROFILE.compare_link_entry(tuple(profile_rows[0].split(",")))
        kwargs["extra_contract_lines"] = (
            "mode=link42-c2-lite-v6-final-island-identity",
            "source_baseline=link41-c2-lite-v6-roots-fronts-coresident",
            "roots_fronts_one_physical_record_two_entries=required",
            "final_island_runtime_identity=authenticated-final-carrier-record",
            "prerequisite_seed_runtime_identity=forbidden",
            "final_island_wplto_authority_sha256=" + WPLTO_SHA,
            "canonical_product_profile="
                + PROFILE.PROFILE.relative_to(ROOT).as_posix(),
            "canonical_product_profile_sha256="
                + PROFILE.sha(PROFILE.PROFILE),
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK.OUT = OUT
        LINK.RECEIPT = RECEIPT
        LINK.LINK_NUMBER = LINK_NUMBER
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
    print("c2-lite-v6-final-island-successor-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
