#!/usr/bin/env python3
"""Build product Link 47 with the L65E ABI and callable transient high edge."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link45_bcode_ordinal_wplto as ORDINAL  # noqa: E402
import c2_lite_v6_link46_l65e_transient_wplto as PROBE  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
import c2_transient_execution_lookup_gate as TRANSIENT  # noqa: E402


LINK_NUMBER = 47
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-47-c2-lite-v6-l65e-transient-callability")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-product-link47-c2-lite-v6-l65e-transient-callability-"
    "structural-receipt.json")
WPLTO_REPLAY = PROBE.EVIDENCE / (
    "c2.2-link46-l65e-transient-wplto-artifact-replay-receipt.json")
WPLTO_REPLAY_SHA = (
    "efc190e25222bf92cbb77a8bd1b330ddf315865d32ecc81dff116915619cc5a1")
L65E_CONTRACT = ROOT / "config/c2-vm-badopcode-detail-contract.json"


def prerequisites() -> dict[str, Any]:
    L = LINK44.LINK
    for path, digest in {
            PROBE.BASE_PRODUCT: PROBE.BASE_PRODUCT_SHA,
            PROBE.BASE_RECEIPT: PROBE.BASE_RECEIPT_SHA,
            PROBE.HARDWARE_FIRST_RED: PROBE.HARDWARE_FIRST_RED_SHA,
            WPLTO_REPLAY: WPLTO_REPLAY_SHA}.items():
        L.require(path.is_file() and L.sha(path) == digest,
                  f"Link-47 authority drift: {path}")
    baseline = json.loads(PROBE.BASE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO_REPLAY.read_text(encoding="utf-8"))
    first_red = json.loads(
        PROBE.HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    L.require(
        baseline["link_number"] == 46
        and baseline["product_identity"]["product"]["sha256"] ==
            PROBE.BASE_PRODUCT_SHA,
        "Link-46 rollback line is not authoritative")
    L.require(
        qualified["status"] ==
            "passed-pure-artifact-replay-no-compiler-no-link-no-hardware"
        and qualified["walls"]["e000_headroom_bytes"] == 129
        and qualified["walls"]["bank0_text_headroom_bytes"] == 17
        and qualified["capacity"]["session_family_bytes"] == 65438
        and qualified["assembler_leaf_abi"]["status"] ==
            "passed-all-assembler-leaf-abi-contracts"
        and qualified["transient_execution_lookup"]["linked"]["status"] ==
            "passed-linked-one-normalizer-common-record-path",
        "green L65E/transient WPLTO replay authority is incomplete")
    L.require(
        first_red["accounting"]["line1_product_first_red_budget"] ==
            "unchanged-at-2/3"
        and first_red["accounting"]["completed_latency_measurements"] ==
            "0/2",
        "Link-47 hardware counters drift")
    return {
        "link46_rollback_product": {
            **L.bind(PROBE.BASE_PRODUCT), "status": "untouched"},
        "link46_structural_authority": L.bind(PROBE.BASE_RECEIPT),
        "qualified_l65e_transient_wplto_replay": L.bind(WPLTO_REPLAY),
        "link46_l65e_abi_hardware_first_red": L.bind(
            PROBE.HARDWARE_FIRST_RED),
        "canonical_product_profile": PROFILE.check(),
        "driver": L.bind(Path(__file__)),
    }


def main() -> int:
    L = LINK44.LINK
    L.require(not OUT.exists() and not RECEIPT.exists(),
              "Link 47 is one-shot")
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
        value["bcode_ordinal_renderer_source"] = \
            ORDINAL.source_gate(run_smoke=True)
        value["assembler_leaf_abi_source"] = {
            "status": "passed-ELF-derived-policy-and-mutation-preflight",
            "inventory": ABI.source_inventory(),
            "mutations_rejected": ABI.selftest(),
        }
        value["transient_execution_lookup_source"] = \
            TRANSIENT.source_gate()
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        renderer = ORDINAL.linked_gate(elf)
        abi_path = OUT / "c2-assembler-leaf-abi-derived-final.json"
        abi = ABI.audit_elf(elf, out=abi_path)
        generated = OUT / "generated-product-sources"
        transient_source = TRANSIENT.source_gate(
            generated_runtime=generated / "c2_product_runtime.c",
            generated_hot=generated / "c2_hot_literal.c")
        transient_linked = TRANSIENT.linked_gate(elf)
        walls, capacity = value["walls"], value["capacity"]
        expected = json.loads(L65E_CONTRACT.read_text(encoding="utf-8"))[
            "renderer"]["l65e_expected_shape"]
        L.require(renderer["slice"] == {
                    "bytes": expected["slice_bytes"],
                    "cap_bytes": expected["slice_cap_bytes"],
                    "headroom_bytes": (
                        expected["slice_cap_bytes"] -
                        expected["slice_bytes"])},
                  f"fresh Link-47 L65E shape red: {renderer['slice']}")
        L.require(abi["status"] == "passed-all-assembler-leaf-abi-contracts"
                  and abi["ELF_derived_C_called_inventory"]
                      ["unclassified_C_called_functions"] == [],
                  "fresh Link-47 ELF-derived assembler ABI gate red")
        L.require(transient_source["generated_sources"]["status"] ==
                      "passed-generated-source-domain-split"
                  and transient_linked["status"] ==
                      "passed-linked-one-normalizer-common-record-path",
                  "fresh Link-47 callable transient high-edge red")
        L.require(walls["e000_headroom_bytes"] >=
                      LINK44.P.E000_FINAL_FLOOR_BYTES
                  and all(int(walls[name]) >= 0 for name in (
                      "bank0_text_headroom_bytes",
                      "ordinary_bank0_bss_headroom_bytes",
                      "fixed_hot_block_headroom_bytes",
                      "resident_island_headroom_bytes")),
                  f"fresh Link-47 product wall red: {walls}")
        L.require(capacity["session_family_bytes"] <= 65536
                  and capacity["session_family_headroom_bytes"] >= 0,
                  f"fresh Link-47 Session aggregate red: {capacity}")
        value["bcode_ordinal_renderer"] = renderer
        value["assembler_leaf_abi_derived"] = abi
        value["assembler_leaf_abi_evidence"] = L.bind(abi_path)
        value["transient_execution_lookup"] = {
            "source": transient_source, "linked": transient_linked}
        value["final_e000_floor_bytes"] = \
            LINK44.P.E000_FINAL_FLOOR_BYTES
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",
                                              "line1_first_red_budget=",
                                              "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link47-c2-lite-v6-l65e-transient-callability",
            "source_baseline=link46-bcode-ordinal-renderer",
            "promotable=no-hardware-not-run",
            "l65e_entry_abi=context-in-rc2-rc3-no-entry-overwrite",
            "assembler_leaf_universe=ELF-derived-C-called",
            "transient_execution=logical4095-physical2047-high-domains",
            "final_e000_floor_bytes="
                + str(LINK44.P.E000_FINAL_FLOOR_BYTES),
            "class_b_budget=3-of-3-exhausted",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = RECEIPT
        LINK44.LINK_NUMBER = LINK_NUMBER
        LINK44.BASELINE = PROBE.BASE_PRODUCT
        LINK44.BASELINE_SHA = PROBE.BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = PROBE.BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = PROBE.BASE_RECEIPT_SHA
        LINK44.WPLTO = WPLTO_REPLAY
        LINK44.WPLTO_SHA = WPLTO_REPLAY_SHA
        LINK44.HARDWARE_FIRST_RED = PROBE.HARDWARE_FIRST_RED
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
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        gates = receipt["fresh_replacement_gates"]
        walls = gates["walls"]
        L.require(
            receipt["link_number"] == LINK_NUMBER
            and receipt["product_identity"]["product"]["sha256"] !=
                PROBE.BASE_PRODUCT_SHA
            and gates["assembler_leaf_abi_derived"]["status"] ==
                "passed-all-assembler-leaf-abi-contracts"
            and gates["transient_execution_lookup"]["linked"]["status"] ==
                "passed-linked-one-normalizer-common-record-path"
            and walls["e000_headroom_bytes"] >=
                LINK44.P.E000_FINAL_FLOOR_BYTES,
            "Link-47 post-receipt qualification red")
        print("c2-lite-v6-link47-l65e-transient-successor: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} "
              f"island={walls['resident_island_headroom_bytes']} "
              f"session={gates['capacity']['session_family_bytes']} "
              "hardware=not-run")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
