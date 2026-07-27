#!/usr/bin/env python3
"""Build product Link 49 with the final append geometry and facade vector 16."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_phase_plan_gate as APPEND  # noqa: E402
import c2_lite_v6_link48_append_final_hybrid_facade16_artifact_replay as QUAL  # noqa: E402
import c2_lite_v6_link48_zero_literal_successor_link as BASE  # noqa: E402
import c2_numeric_early_errors_gate as NUMERIC  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


L = BASE.BASE.LINK44.LINK
LINK44 = BASE.BASE.LINK44
BASE_LINK = LINK44.BASE_LINK
P = LINK44.P
RF = LINK44.RF
PROFILE = BASE.BASE.PROFILE
CONS = QUAL.CONS
STAGE = QUAL.STAGE
ART = QUAL.ART
LINK_NUMBER = 49
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-49-c2-lite-v6-append-final-hybrid-facade16")
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-product-link49-c2-lite-v6-append-final-hybrid-facade16-"
    "structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-48-c2-lite-v6-zero-literal-execution/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "1b7f7309a415d113a0d8718805e8c860ff3583b82ee2037dfae9dac5f7f5eae6")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link48-c2-lite-v6-zero-literal-execution-"
    "structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "867bd59ff9c669e98b4969062eeb0dfd39b0fb633f21dd3e19f067fedb3c7f25")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")
HARDWARE_FIRST_RED_SHA = (
    "f9f17db39694c973968581ac657c1d70fda95c4dd63fc5a81f89b0088864b3a6")
WPLTO = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-facade16-artifact-replay3-receipt.json")
WPLTO_SHA = (
    "c88e15934cf7ae70e860cd07da0e2992f7426da409d08c62fcb7fa66420a1735")
WPLTO_PROFILE = QUAL.SOURCE / "resolved-profile.txt"
CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
VERIFIER_BASE = 0xB949
EXPECTED_FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
    "LISP65_C2_NESTED_APPEND_V5",
    "LISP65_C2_RESIDENCY_TRIAGE",
    "LISP65_C2_E000_REOPEN",
    "LISP65_C2_BSS_TRIAGE",
    "LISP65_RUNTIME_OVERLAY_FORMAT_V3",
    "LISP65_C2_PHASE11_SPLIT",
    "LISP65_C2_LITE_COLD_EVICTION",
    "LISP65_C2_LITE_V6_SEMANTIC_SPLITS",
    "LISP65_C2_LITE_V6_CORESIDENT_DIET",
    "LISP65_C2_LITE_BANK3_STAGING",
    "LISP65_C2_LITE_BANK2_STAGING",
    "LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT",
    "LISP65_C2_LITE_VM_ARITY_E000",
    "LISP65_C2_LITE_CHIP_RAM",
    "LISP65_C2_APPEND_PLAN_FACADE",
    "LISP65_C2_NUMERIC_EARLY_ERRORS",
    "LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT",
)


def resolved_features() -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            WPLTO_PROFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    L.require(len(rows) == 1, "WPLTO has no unique feature row")
    values = tuple(rows[0].split(","))
    L.require(values == EXPECTED_FEATURES,
              "frozen facade-16 WPLTO feature set drift")
    return values


def current_profile_authority() -> dict[str, Any]:
    features = resolved_features()
    return {
        "status": "passed-bound-complete-WPLTO-profile",
        "base_profile_object": L.bind(PROFILE.PROFILE),
        "resolved_profile": L.bind(WPLTO_PROFILE),
        "feature_defines": list(features),
        "base_feature_count": 19,
        "wrapper_features": list(features[19:]),
        "reconstruction": "forbidden; exact frozen feature row consumed",
    }


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA,
            WPLTO: WPLTO_SHA}.items():
        L.require(path.is_file() and L.sha(path) == digest,
                  f"Link-49 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = qualified["fresh_read_only_replay"]
    L.require(
        baseline["link_number"] == 48
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-48 rollback identity is not authoritative")
    L.require(
        first_red["status"] == "first-red-product-semantics-review-required"
        and first_red["accounting"]["line_1_status"] == "passed"
        and first_red["accounting"]["line_1_product_first_red_budget"] ==
            "2/3 unchanged"
        and first_red["accounting"]["completed_latency_measurements"] ==
            "0/2 unchanged",
        "Link-48 append hardware First Red or counters drift")
    L.require(
        qualified["status"] ==
            "passed-complete-facade16-WPLTO-artifact-replay"
        and not qualified["promotable"]
        and replay["walls"] == {
            "bank0_text_headroom_bytes": 37,
            "ordinary_bank0_bss_headroom_bytes": 218,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 54}
        and replay["capacity"]["session_family_bytes"] == 65438
        and replay["append_phase_plan"]["linked"]["walker"]
            ["facade"]["address"] == 0xB5F1
        and qualified["execution_accounting"]["compiler_runs"] == 0
        and qualified["execution_accounting"]["linker_runs"] == 0,
        "facade-16 WPLTO artifact authority is incomplete")
    return {
        "link48_rollback_product": {**L.bind(BASELINE),
                                    "status": "untouched"},
        "link48_structural_authority": L.bind(BASELINE_RECEIPT),
        "link48_append_hardware_first_red": L.bind(HARDWARE_FIRST_RED),
        "qualified_facade16_wplto_replay": L.bind(WPLTO),
        "complete_product_profile": current_profile_authority(),
        "append_final_hybrid_contract": L.bind(CONTRACT),
        "driver": L.bind(Path(__file__)),
    }


def main() -> int:
    L.require(not OUT.exists() and not RECEIPT.exists(),
              "Link 49 is one-shot")
    features = resolved_features()
    old = {
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "number": BASE.LINK_NUMBER,
        "wplto": BASE.WPLTO, "wplto_sha": BASE.WPLTO_SHA,
        "prerequisites": BASE.prerequisites,
        "base_product": BASE.PROBE.BASE_PRODUCT,
        "base_product_sha": BASE.PROBE.BASE_PRODUCT_SHA,
        "base_receipt": BASE.PROBE.BASE_RECEIPT,
        "base_receipt_sha": BASE.PROBE.BASE_RECEIPT_SHA,
        "hardware_first_red": BASE.PROBE.HARDWARE_FIRST_RED,
        "hardware_first_red_sha": BASE.PROBE.HARDWARE_FIRST_RED_SHA,
        "profile_features": PROFILE.feature_defines,
        "profile_legacy": PROFILE.check_legacy_configuration,
        "profile_compare": PROFILE.compare_link_entry,
        "rf_configure": RF.configure_roots_fronts,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "replacement": BASE_LINK.replacement_gates,
        "single_link": P.single_link,
        "base_link_verifier": BASE_LINK.VERIFIER_BASE,
        "stage_verifier": STAGE.VERIFIER_BASE,
        "art_verifier": ART.VERIFIER_BASE,
        "p_verifier": P.VERIFIER_BINDING_BASE,
        "e000_floor": P.E000_FINAL_FLOOR_BYTES,
        "profile_rodata": P.PROFILE_RODATA_BASE,
        "append_facade": P.APPEND_PLAN_FACADE,
        "facade_extensions": P.HOST_FACADE_EXTENSION_SYMBOLS,
        "append_slices": tuple(CONS.CONS.PRODUCT.C2_APPEND_SLICES),
    }

    def feature_defines() -> tuple[str, ...]:
        return features

    def check_legacy_configuration(_observed: Iterable[str]) -> dict[str, Any]:
        return {
            "status": "passed-superseded-by-complete-WPLTO-profile",
            "complete_profile_sha256": L.sha(WPLTO_PROFILE),
        }

    def compare_link_entry(observed: Iterable[str]) -> None:
        L.require(tuple(observed) == features,
                  "product-link entry differs from complete facade-16 WPLTO")

    def configure_current_geometry() -> None:
        old["rf_configure"]()
        CONS.CONS.configure_publish_clear()
        P.configure_c2_lite_hybrid_e000_geometry()
        P.configure_append_plan_facade()
        L.require(P.E000_FINAL_FLOOR_BYTES == 54
                  and P.host_facade_bytes() == 48
                  and P.host_facade_vector_addresses()[
                      "c2_facade_append_plan_walk"] == 0xB5F1,
                  "Link-49 current geometry configuration drift")

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        consolidation = CONS.CONS.source_gate()
        consolidation["hard_completion_criteria"][
            "e000_headroom_bytes"] = ">=54"
        value["append_final_consolidation_source"] = consolidation
        value["append_phase_plan_source"] = APPEND.source_gate()
        value["numeric_early_errors_source"] = NUMERIC.source_gate()
        value["numeric_early_errors_host"] = NUMERIC.host_gate(
            OUT / "fresh-c2-lite-prelink-gates/numeric-early-errors")
        value["complete_product_profile"] = current_profile_authority()
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        walls, family = BASE_LINK.walls_and_family(elf)
        shape = {"walls": walls,
                 "runtime_slices": family["runtime_slices"],
                 "successor_bank3_pack": family["successor_bank3_pack"]}
        capacity = CONS.capacity_gate(shape, elf)
        semantic = BASE_LINK.DIET.semantic_product_gate(shape, product, elf)
        roots_fronts = CONS.roots_fronts_gate(elf)
        append = APPEND.linked_gate(elf)
        numeric = NUMERIC.linked_gate(elf)
        truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
        expected = {
            ".lisp65_c2_host_facade": (0xB5C4, 48),
            ".lisp65_c2_kernal_io_reveal": (0xB5F4, 11),
            ".lisp65_c2_kernal_map_switch": (0xB5FF, 10),
            ".lisp65_c2_kernal_state": (0xB609, 20),
            ".rodata": (0xB61D, 812),
            ".lisp65_runtime_overlay_verifier_bindings": (0xB949, 40),
            ".data": (0xB971, 2),
            ".bss": (0xB973, 1587),
        }
        actual = {name: (truth.section(name).address,
                         truth.section(name).bytes) for name in expected}
        L.require(
            walls == {
                "bank0_text_headroom_bytes": 37,
                "ordinary_bank0_bss_headroom_bytes": 218,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 54}
            and capacity["session_family_bytes"] == 65438
            and capacity["session_family_headroom_bytes"] == 98
            and semantic["status"] == "passed"
            and roots_fronts["status"].startswith("passed")
            and append["walker"]["facade"]["address"] == 0xB5F1
            and append["walker"]["facade_routed_C_call_edges"] == 2
            and numeric["resident_sentences_present"] == 0
            and actual == expected,
            "fresh Link-49 facade geometry, capacity, or semantic gate red")
        value["walls"] = walls
        value["capacity"] = capacity
        value["product_semantics_current"] = semantic
        value["roots_fronts_current"] = roots_fronts
        value["append_phase_plan"] = append
        value["numeric_early_errors"] = numeric
        value["facade16_low_resident_chain"] = {
            name: {"address": row[0], "bytes": row[1]}
            for name, row in actual.items()}
        value["final_e000_floor_bytes"] = 54
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "final_e000_floor_bytes=",
                          "line1_first_red_budget=",
                          "latency_measurement_attempts=")))
        profile_rows = [line.split("=", 1)[1] for line in lines
                        if line.startswith("feature_defines=")]
        L.require(len(profile_rows) == 1
                  and tuple(profile_rows[0].split(",")) == features,
                  "Link-49 entry is not bound to the complete WPLTO profile")
        kwargs["extra_contract_lines"] = (
            "mode=link49-c2-lite-v6-append-final-hybrid-facade16",
            "source_baseline=product-link48-zero-literal-execution",
            "promotable=no-hardware-not-run",
            "facade16_vector=c2_facade_append_plan_walk@0xb5f1",
            "facade16_wplto_replay_sha256=" + WPLTO_SHA,
            "publish_last_table=0xb949+40",
            "final_e000_floor_bytes=54",
            "text_noise_floor_bytes=32",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.prerequisites = prerequisites
        BASE.PROBE.BASE_PRODUCT = BASELINE
        BASE.PROBE.BASE_PRODUCT_SHA = BASELINE_SHA
        BASE.PROBE.BASE_RECEIPT = BASELINE_RECEIPT
        BASE.PROBE.BASE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        BASE.PROBE.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = HARDWARE_FIRST_RED_SHA
        PROFILE.feature_defines = feature_defines
        PROFILE.check_legacy_configuration = check_legacy_configuration
        PROFILE.compare_link_entry = compare_link_entry
        RF.configure_roots_fronts = configure_current_geometry
        BASE_LINK.fresh_prelink_gates = prelink
        BASE_LINK.replacement_gates = replacement
        P.single_link = single_link
        BASE_LINK.VERIFIER_BASE = VERIFIER_BASE
        STAGE.VERIFIER_BASE = VERIFIER_BASE
        ART.VERIFIER_BASE = VERIFIER_BASE
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.LINK_NUMBER = old["number"]
        BASE.WPLTO = old["wplto"]
        BASE.WPLTO_SHA = old["wplto_sha"]
        BASE.prerequisites = old["prerequisites"]
        BASE.PROBE.BASE_PRODUCT = old["base_product"]
        BASE.PROBE.BASE_PRODUCT_SHA = old["base_product_sha"]
        BASE.PROBE.BASE_RECEIPT = old["base_receipt"]
        BASE.PROBE.BASE_RECEIPT_SHA = old["base_receipt_sha"]
        BASE.PROBE.HARDWARE_FIRST_RED = old["hardware_first_red"]
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = old["hardware_first_red_sha"]
        PROFILE.feature_defines = old["profile_features"]
        PROFILE.check_legacy_configuration = old["profile_legacy"]
        PROFILE.compare_link_entry = old["profile_compare"]
        RF.configure_roots_fronts = old["rf_configure"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        BASE_LINK.replacement_gates = old["replacement"]
        P.single_link = old["single_link"]
        BASE_LINK.VERIFIER_BASE = old["base_link_verifier"]
        STAGE.VERIFIER_BASE = old["stage_verifier"]
        ART.VERIFIER_BASE = old["art_verifier"]
        P.VERIFIER_BINDING_BASE = old["p_verifier"]
        P.E000_FINAL_FLOOR_BYTES = old["e000_floor"]
        P.PROFILE_RODATA_BASE = old["profile_rodata"]
        P.APPEND_PLAN_FACADE = old["append_facade"]
        P.HOST_FACADE_EXTENSION_SYMBOLS = old["facade_extensions"]
        CONS.CONS.PRODUCT.configure_append_slices(old["append_slices"])

    if result == 0:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        gates = receipt["fresh_replacement_gates"]
        walls = gates["walls"]
        L.require(
            receipt["link_number"] == LINK_NUMBER
            and receipt["product_identity"]["product"]["sha256"] !=
                BASELINE_SHA
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] == 54
            and gates["capacity"]["session_family_bytes"] == 65438
            and gates["append_phase_plan"]["walker"]
                ["facade_routed_C_call_edges"] == 2,
            "Link-49 post-receipt qualification red")
        print("c2-lite-v6-link49-append-final-facade16: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} "
              f"island={walls['resident_island_headroom_bytes']} "
              f"session={gates['capacity']['session_family_bytes']} "
              "hardware=not-run")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
