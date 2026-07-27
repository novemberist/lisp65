#!/usr/bin/env python3
"""Build the authorized Bank-2 target-stage successor as product Link 44."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_phase02b_artifact_replay as REPLAY  # noqa: E402
import c2_lite_v6_bank2_target_stage_phase02b_wplto as PROBE  # noqa: E402
import c2_lite_v6_export_symbol_domain_successor_link as LINK43  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402


B = PROBE.B
LINK = LINK43.LINK
BASE_LINK = LINK43.BASE_LINK
P = LINK43.P
RF = LINK43.LINK42.RF
LINK_NUMBER = 44
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-44-c2-lite-v6-bank2-target-stage")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-bank2-target-stage-"
    "structural-receipt.json")
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-43-c2-lite-v6-export-symbol-domain/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "9bbfb17707fe6e57bfd93c49db13f920fa48d0654227c19150aec4a34f1be43b")
BASELINE_RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-export-symbol-domain-"
    "structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "6cad468649ac5af85876be5e14b66e28fa4f5d6e32d64c25a6389a7934e04ae4")
WPLTO = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-bank2-target-stage-phase02b-"
    "artifact-replay-receipt.json")
WPLTO_SHA = (
    "8ef2e990d8cfe56d4772f09a5e4137f9825c6f4c1a97ab0008dbf33b362ae1a0")
HARDWARE_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-bank2-stage-hardware-first-red.json")
HARDWARE_FIRST_RED_SHA = (
    "835f743667d3db99f14bc1396bc47aab2943adf5c2ad7b89138206fd12e1ea17")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            WPLTO: WPLTO_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        LINK.require(path.is_file() and LINK.sha(path) == digest,
                     f"Link-44 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    profile = PROFILE.check()
    LINK.require(
        baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and baseline["link_number"] == 43
        and baseline["product_identity"]["product"]["sha256"] ==
            BASELINE_SHA,
        "Link-43 rollback identity is not authoritative")
    LINK.require(
        qualified["status"] ==
            "passed-complete-bank2-target-stage-phase02b-WPLTO"
        and qualified["source_contract"]["status"] ==
            "passed-phase02b-target-close-source-contract"
        and qualified["bound_source_mutations"]["count"] == 10
        and qualified["target_dataflow_gate"]["status"] ==
            "passed-real-target-dataflow-and-bounded-cold-slice"
        and qualified["target_dataflow_gate"]["phase"]["bytes"] == 1379
        and qualified["workbench_scratch_negative_fixture"]
            ["workbench_scratch_passing_records"] == 0
        and not qualified["workbench_scratch_negative_fixture"]
            ["ready_if_workbench_scratch_remains"]
        and qualified["aggregate_recovery"]["session_family_bytes"] == 65438
        and qualified["aggregate_recovery"]
            ["session_family_headroom_bytes"] == 98
        and qualified["product_shaped_wplto"]["fresh_gates"]["status"] ==
            "passed-artifact-only-complete-gate-replay",
        "Bank-2 phase-02b WPLTO authority is not fully green")
    LINK.require(
        first_red["status"] == "first-red-product-semantic-review-required"
        and first_red["budgets"]["line1_product_first_reds_consumed"] ==
            "2/3"
        and first_red["budgets"]["latency_measurements_consumed"] == "0/2",
        "Link-43 Bank-2 hardware First Red is not authoritative")
    authorization = contract["bank2_target_stage_successor_authorization"]
    LINK.require(
        contract["status"] ==
            "class-c-approved-symmetric-bank2-target-stage-wplto-"
            "successor-link-and-line1-presmoke"
        and authorization["product_first_red_budget"] ==
            "2/3 consumed; 1 remains"
        and authorization["latency_measurement_attempts"] == "0/2 consumed"
        and authorization["product_link_rule"].startswith(
            "One successor link is authorized"),
        "Bank-2 target-stage successor Class-C authority absent")
    return {
        "link43_rollback_product": LINK.bind(BASELINE),
        "link43_structural_authority": LINK.bind(BASELINE_RECEIPT),
        "bank2_phase02b_green_wplto": LINK.bind(WPLTO),
        "link43_bank2_hardware_first_red": LINK.bind(HARDWARE_FIRST_RED),
        "canonical_product_profile": profile,
        "c2_lite_contract": LINK.bind(CONTRACT),
        "c2_lite_addendum": LINK.bind(ADDENDUM),
        "driver": LINK.bind(Path(__file__)),
    }


def main() -> int:
    LINK.require(not OUT.exists() and not RECEIPT.exists(),
                 "Link 44 is one-shot")
    old = {
        "out": LINK43.OUT, "receipt": LINK43.RECEIPT,
        "number": LINK43.LINK_NUMBER, "baseline": LINK43.BASELINE,
        "baseline_sha": LINK43.BASELINE_SHA,
        "baseline_receipt": LINK43.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK43.BASELINE_RECEIPT_SHA,
        "wplto": LINK43.WPLTO, "wplto_sha": LINK43.WPLTO_SHA,
        "hardware_first_red": LINK43.HARDWARE_FIRST_RED,
        "prerequisites": LINK43.prerequisites,
        "rf_configure": RF.configure_roots_fronts,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "replacement": BASE_LINK.replacement_gates,
        "single_link": P.single_link,
    }

    def configure_roots_fronts_and_bank2() -> None:
        old["rf_configure"]()
        B.configure_bank2_stage()

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        gate_out = OUT / "fresh-c2-lite-prelink-gates/bank2-target-stage"
        previous_out = B.OUT
        try:
            B.OUT = gate_out
            source = PROBE.source_gate(test_mutations=True)
        finally:
            B.OUT = previous_out
        LINK.require(len(source["mutations_rejected"]) == 10,
                     "fresh Bank-2 source mutation matrix red")
        value["bank2_target_stage_source"] = source
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        shaped = {"artifacts": {"measurement_elf": LINK.bind(elf)}}
        target = B.elf_gate(shaped)
        workbench = B.target_fixture(REPLAY.fixture_product())
        LINK.require(target["phase"]["bytes"] <= B.CAP
                     and workbench["workbench_scratch_passing_records"] == 0
                     and not workbench["ready_if_workbench_scratch_remains"],
                     "linked Bank-2 target-dataflow or Workbench fixture red")
        value["bank2_target_dataflow"] = target
        value["bank2_workbench_scratch_negative"] = workbench
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(
            line for line in kwargs.get("extra_contract_lines", ())
            if not line.startswith((
                "mode=", "source_baseline=",
                "export_symbol_domain_wplto_authority_sha256=",
                "final_island_wplto_authority_sha256=",
                "line1_first_red_budget=",
                "latency_measurement_attempts=")))
        profile_rows = [line.split("=", 1)[1] for line in lines
                        if line.startswith("feature_defines=")]
        LINK.require(len(profile_rows) == 1,
                     "Link-44 entry has no unique feature profile")
        profile_features = tuple(profile_rows[0].split(","))
        PROFILE.compare_link_entry(profile_features)
        kwargs["extra_contract_lines"] = (
            "mode=link44-c2-lite-v6-bank2-target-stage",
            "source_baseline=link43-c2-lite-v6-export-symbol-domain",
            "bank2_target_stage=phase02b-coordinate-close-phase03-auth-"
                "phase03b-copy-and-target-crc",
            "bank2_target_stage_wplto_authority_sha256=" + WPLTO_SHA,
            "canonical_product_profile_sha256=" + PROFILE.sha(PROFILE.PROFILE),
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK43.OUT = OUT
        LINK43.RECEIPT = RECEIPT
        LINK43.LINK_NUMBER = LINK_NUMBER
        LINK43.BASELINE = BASELINE
        LINK43.BASELINE_SHA = BASELINE_SHA
        LINK43.BASELINE_RECEIPT = BASELINE_RECEIPT
        LINK43.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        LINK43.WPLTO = WPLTO
        LINK43.WPLTO_SHA = WPLTO_SHA
        LINK43.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        LINK43.prerequisites = prerequisites
        RF.configure_roots_fronts = configure_roots_fronts_and_bank2
        BASE_LINK.fresh_prelink_gates = prelink
        BASE_LINK.replacement_gates = replacement
        P.single_link = single_link
        result = LINK43.main()
    finally:
        LINK43.OUT = old["out"]
        LINK43.RECEIPT = old["receipt"]
        LINK43.LINK_NUMBER = old["number"]
        LINK43.BASELINE = old["baseline"]
        LINK43.BASELINE_SHA = old["baseline_sha"]
        LINK43.BASELINE_RECEIPT = old["baseline_receipt"]
        LINK43.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        LINK43.WPLTO = old["wplto"]
        LINK43.WPLTO_SHA = old["wplto_sha"]
        LINK43.HARDWARE_FIRST_RED = old["hardware_first_red"]
        LINK43.prerequisites = old["prerequisites"]
        RF.configure_roots_fronts = old["rf_configure"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        BASE_LINK.replacement_gates = old["replacement"]
        P.single_link = old["single_link"]
    if result == 0:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        LINK.require(receipt["link_number"] == LINK_NUMBER,
                     "Link-44 receipt number drift")
        print("c2-lite-v6-bank2-target-stage-successor-link: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              "budget=2/3 latency=0/2")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
