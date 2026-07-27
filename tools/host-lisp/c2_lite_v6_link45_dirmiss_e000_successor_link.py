#!/usr/bin/env python3
"""Build the authorized VM_DIRMISS-detail plus E000-evacuation successor.

This is product Link 45.  It starts from the untouched Link-44 rollback
identity, consumes the qualified artifact-only WPLTO authority, runs every
prelink, generic, C2-lite and placement gate freshly, and creates no hardware
claim.  The moved object is exactly vm_byte_args in the existing C2-resident
window section; no facade vector is added.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link44_dirmiss_detail_wplto as DETAIL  # noqa: E402
import c2_lite_v6_link44_dirmiss_e000_eviction_wplto as EVAC  # noqa: E402
import c2_lite_v6_link44_dirmiss_e000_eviction_artifact_replay as REPLAY_GATE  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


LINK_NUMBER = 45
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-45-c2-lite-v6-dirmiss-detail-e000-evacuation")
RECEIPT = LINK44.LINK.EVIDENCE / (
    "c2.2-product-link45-c2-lite-v6-dirmiss-detail-e000-evacuation-"
    "structural-receipt.json")
BASELINE = DETAIL.BASE_PRODUCT
BASELINE_SHA = DETAIL.BASE_PRODUCT_SHA
BASELINE_RECEIPT = DETAIL.BASE_RECEIPT
BASELINE_RECEIPT_SHA = DETAIL.BASE_RECEIPT_SHA
WPLTO = LINK44.LINK.EVIDENCE / (
    "c2.2-link44-dirmiss-detail-e000-eviction-"
    "artifact-replay2-receipt.json")
WPLTO_SHA = (
    "7fa57c13e17e377a6a4f94a8851528612238ca884b307c20562c6e893cb59f7e")
HARDWARE_FIRST_RED = DETAIL.FIRST_RED
DETAIL_CONTRACT_SHA = (
    "17b50b2cd151f485025d33149ab2cd94c10479aaf1259005427797385d08c9e2")
EVAC_CONTRACT_SHA = (
    "3e599f198b6658042ad9185e9c2373c506199dac01a88321bdbda144cd6168f4")


def prerequisites() -> dict[str, Any]:
    L = LINK44.LINK
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            WPLTO: WPLTO_SHA,
            HARDWARE_FIRST_RED: DETAIL.FIRST_RED_SHA,
            DETAIL.CONTRACT: DETAIL_CONTRACT_SHA,
            EVAC.CONTRACT: EVAC_CONTRACT_SHA}.items():
        L.require(path.is_file() and L.sha(path) == digest,
                  f"Link-45 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text())
    qualified = json.loads(WPLTO.read_text())
    first_red = json.loads(HARDWARE_FIRST_RED.read_text())
    evacuation = json.loads(EVAC.CONTRACT.read_text())
    L.require(
        baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and baseline["link_number"] == 44
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA,
        "Link-44 rollback identity is not authoritative")
    L.require(
        qualified["status"] ==
            "passed-complete-dirmiss-detail-E000-evacuation-WPLTO-artifact-replay"
        and qualified["scope"]["compiler_runs"] == 0
        and qualified["scope"]["linker_runs"] == 0
        and qualified["capacity"]["walls"]["bank0_text_headroom_bytes"] >= 32
        and qualified["capacity"]["walls"]["e000_headroom_bytes"] == 256
        and qualified["capacity"]["window_inventory"]["floor_bytes"] == 115
        and qualified["linked_eviction"]["new_vector"] is False
        and qualified["linked_detail"]["linked_reference_count"] == 4,
        "qualified status/detail E000 WPLTO authority is not fully green")
    L.require(
        first_red["budgets"]["line_1_product_first_reds"]["after"] == "2/3"
        and first_red["budgets"]["completed_latency_measurements"]["after"]
            == "0/2",
        "dynamic top-level hardware budget authority drift")
    L.require(
        evacuation["status"] == "class-c-approved-window-evacuation"
        and evacuation["authority"]["required_bank0_relief_bytes"] == 86
        and evacuation["authority"]["e000_floor_bytes"] == 115
        and evacuation["candidate"]["symbol"] == "vm_byte_args"
        and not evacuation["candidate"]["new_facade_vector"],
        "Class-C E000 evacuation authority absent")
    return {
        "link44_rollback_product": {**L.bind(BASELINE),
                                    "status": "untouched"},
        "link44_structural_authority": L.bind(BASELINE_RECEIPT),
        "qualified_detail_e000_wplto": L.bind(WPLTO),
        "dynamic_top_level_hardware_first_red": L.bind(HARDWARE_FIRST_RED),
        "detail_contract": L.bind(DETAIL.CONTRACT),
        "evacuation_contract": L.bind(EVAC.CONTRACT),
        "canonical_product_profile": PROFILE.check(),
        "driver": L.bind(Path(__file__)),
    }


def main() -> int:
    L = LINK44.LINK
    L.require(not OUT.exists() and not RECEIPT.exists(),
              "Link 45 is one-shot")
    old = {
        "out": LINK44.OUT, "receipt": LINK44.RECEIPT,
        "number": LINK44.LINK_NUMBER, "baseline": LINK44.BASELINE,
        "baseline_sha": LINK44.BASELINE_SHA,
        "baseline_receipt": LINK44.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK44.BASELINE_RECEIPT_SHA,
        "wplto": LINK44.WPLTO, "wplto_sha": LINK44.WPLTO_SHA,
        "hardware_first_red": LINK44.HARDWARE_FIRST_RED,
        "prerequisites": LINK44.prerequisites,
        "prelink": LINK44.BASE_LINK.fresh_prelink_gates,
        "replacement": LINK44.BASE_LINK.replacement_gates,
        "single_link": LINK44.P.single_link,
    }

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["vm_dirmiss_detail_source"] = DETAIL.source_gate(
            DETAIL.VM.read_text(), DETAIL.VM_H.read_text(),
            DETAIL.EVAL.read_text(), DETAIL.COMPILE.read_text(),
            DETAIL.INTERRUPT.read_text(), DETAIL.ERROR_OVERLAY.read_text(),
            mutations=True)
        value["vm_dirmiss_detail_semantics"] = DETAIL.semantic_fixture()
        value["vm_byte_args_e000_source"] = EVAC.contract_gate(
            DETAIL.VM.read_text(), mutations=True)
        value["e000_candidate_selection"] = EVAC.premove_candidate_gate()
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        truth = ElfTruth.read(
            elf, llvm_readobj=LINK44.P.TOOLCHAIN / "llvm-readobj")
        detail = REPLAY_GATE.detail_gate(truth)
        eviction = EVAC.linked_eviction_gate(elf)
        walls = value["walls"]
        L.require(detail["status"].startswith("passed-")
                  and detail["linked_reference_count"] == 4
                  and eviction["status"].startswith("passed-")
                  and eviction["bytes"] >= 86
                  and not eviction["new_vector"],
                  "fresh Link-45 detail/eviction linked gate red")
        L.require(walls["bank0_text_headroom_bytes"] >= 32
                  and walls["e000_headroom_bytes"] >= 115,
                  f"fresh Link-45 standing reserve/floor red: {walls}")
        value["vm_dirmiss_detail"] = detail
        value["vm_byte_args_e000_eviction"] = eviction
        value["standing_text_reserve_required_bytes"] = 32
        value["e000_floor_required_bytes"] = 115
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",
                                              "line1_first_red_budget=",
                                              "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link45-c2-lite-v6-dirmiss-detail-e000-evacuation",
            "source_baseline=link44-bank2-target-stage-replay",
            "promotable=no-hardware-not-run",
            "vm_dirmiss_detail=one-seam-six-source-status-plus-obj-result",
            "e000_eviction_symbol=vm_byte_args",
            "e000_eviction_new_vector=no",
            "standing_bank0_text_reserve_bytes=32",
            "final_e000_floor_bytes=115",
            "class_b_budget=3-of-3-exhausted",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = RECEIPT
        LINK44.LINK_NUMBER = LINK_NUMBER
        LINK44.BASELINE = BASELINE
        LINK44.BASELINE_SHA = BASELINE_SHA
        LINK44.BASELINE_RECEIPT = BASELINE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        LINK44.WPLTO = WPLTO
        LINK44.WPLTO_SHA = WPLTO_SHA
        LINK44.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        LINK44.prerequisites = prerequisites
        LINK44.BASE_LINK.fresh_prelink_gates = prelink
        LINK44.BASE_LINK.replacement_gates = replacement
        LINK44.P.single_link = single_link
        result = LINK44.main()
    finally:
        LINK44.OUT = old["out"]
        LINK44.RECEIPT = old["receipt"]
        LINK44.LINK_NUMBER = old["number"]
        LINK44.BASELINE = old["baseline"]
        LINK44.BASELINE_SHA = old["baseline_sha"]
        LINK44.BASELINE_RECEIPT = old["baseline_receipt"]
        LINK44.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        LINK44.WPLTO = old["wplto"]
        LINK44.WPLTO_SHA = old["wplto_sha"]
        LINK44.HARDWARE_FIRST_RED = old["hardware_first_red"]
        LINK44.prerequisites = old["prerequisites"]
        LINK44.BASE_LINK.fresh_prelink_gates = old["prelink"]
        LINK44.BASE_LINK.replacement_gates = old["replacement"]
        LINK44.P.single_link = old["single_link"]

    if result == 0:
        receipt = json.loads(RECEIPT.read_text())
        gates = receipt["fresh_replacement_gates"]
        walls = gates["walls"]
        L.require(receipt["link_number"] == LINK_NUMBER
                  and gates["vm_dirmiss_detail"]["status"].startswith("passed-")
                  and gates["vm_byte_args_e000_eviction"]["status"].startswith("passed-")
                  and walls["bank0_text_headroom_bytes"] >= 32
                  and walls["e000_headroom_bytes"] >= 115,
                  "Link-45 post-receipt qualification red")
        print("c2-lite-v6-link45-dirmiss-e000-successor: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} hardware=not-run")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
