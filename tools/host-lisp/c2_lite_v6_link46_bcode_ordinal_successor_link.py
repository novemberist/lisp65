#!/usr/bin/env python3
"""Build authorized product Link 46 with the BCODE ordinal renderer."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link45_bcode_ordinal_wplto as W  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402


LINK_NUMBER = 46
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-46-c2-lite-v6-bcode-ordinal-renderer")
RECEIPT = W.EVIDENCE / (
    "c2.2-product-link46-c2-lite-v6-bcode-ordinal-renderer-"
    "structural-receipt.json")
WPLTO_SHA = (
    "a00347d17d48c4eb937067c6f347fb8564f067b40f694486583cfe7a1646b257")


def prerequisites() -> dict[str, Any]:
    L = LINK44.LINK
    for path, digest in {
            W.BASE_PRODUCT: W.BASE_PRODUCT_SHA,
            W.BASE_RECEIPT: W.BASE_RECEIPT_SHA,
            W.HARDWARE_FIRST_RED: W.HARDWARE_FIRST_RED_SHA,
            W.RECEIPT: WPLTO_SHA}.items():
        L.require(path.is_file() and L.sha(path) == digest,
                  f"Link-46 authority drift: {path}")
    baseline = json.loads(W.BASE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(W.RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(W.HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    L.require(
        baseline["link_number"] == 45
        and baseline["product_identity"]["product"]["sha256"] ==
            W.BASE_PRODUCT_SHA,
        "Link-45 rollback line is not authoritative")
    L.require(
        qualified["status"] ==
            "passed-product-shaped-WPLTO-no-hardware-no-product-candidate"
        and qualified["linked_renderer"]["status"].startswith("passed-")
        and qualified["linked_renderer"]["slice"] == {
            "bytes": 1139, "cap_bytes": 1320, "headroom_bytes": 181}
        and qualified["capacity"]["session_family_bytes"] == 65438
        and qualified["capacity"]["session_family_headroom_bytes"] == 98,
        "green BCODE ordinal WPLTO authority is incomplete")
    L.require(first_red["counters"]["line1_product_first_reds"] == "2/3"
              and first_red["counters"]["completed_latency_measurements"] ==
                  "0/2",
              "Link-46 hardware counters drift")
    return {
        "link45_rollback_product": {**L.bind(W.BASE_PRODUCT),
                                    "status": "untouched"},
        "link45_structural_authority": L.bind(W.BASE_RECEIPT),
        "qualified_bcode_ordinal_wplto": L.bind(W.RECEIPT),
        "link45_non_symbol_hardware_first_red": L.bind(W.HARDWARE_FIRST_RED),
        "approved_contract": L.bind(W.CONTRACT),
        "canonical_product_profile": PROFILE.check(),
        "driver": L.bind(Path(__file__)),
    }


def main() -> int:
    L = LINK44.LINK
    L.require(not OUT.exists() and not RECEIPT.exists(),
              "Link 46 is one-shot")
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
        value["bcode_ordinal_renderer_source"] = W.source_gate(run_smoke=True)
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        renderer = W.linked_gate(elf)
        walls, capacity = value["walls"], value["capacity"]
        L.require(renderer["status"].startswith("passed-")
                  and renderer["slice"]["bytes"] <= 1320,
                  "fresh Link-46 BCODE renderer gate red")
        L.require(walls["ordinary_bank0_bss_headroom_bytes"] == 86
                  and walls["e000_headroom_bytes"] >= 115
                  and all(int(walls[name]) >= 0 for name in (
                      "bank0_text_headroom_bytes",
                      "fixed_hot_block_headroom_bytes",
                      "resident_island_headroom_bytes")),
                  f"fresh Link-46 product wall red: {walls}")
        L.require(capacity["session_family_bytes"] <= 65536
                  and capacity["session_family_headroom_bytes"] >= 0,
                  f"fresh Link-46 Session aggregate red: {capacity}")
        value["bcode_ordinal_renderer"] = renderer
        value["l65e_dedicated_cap_bytes"] = 1320
        value["final_e000_floor_bytes"] = 115
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",
                                              "line1_first_red_budget=",
                                              "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link46-c2-lite-v6-bcode-ordinal-renderer",
            "source_baseline=link45-dirmiss-detail-e000-evacuation",
            "promotable=no-hardware-not-run",
            "detail_union=NIL-SYMI-BCODE-existing-cell",
            "bcode_rendering=raw-12-bit-ordinal-three-lower-hex",
            "l65e_dedicated_cap_bytes=1320",
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
        LINK44.BASELINE = W.BASE_PRODUCT
        LINK44.BASELINE_SHA = W.BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = W.BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = W.BASE_RECEIPT_SHA
        LINK44.WPLTO = W.RECEIPT
        LINK44.WPLTO_SHA = WPLTO_SHA
        LINK44.HARDWARE_FIRST_RED = W.HARDWARE_FIRST_RED
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
        L.require(receipt["link_number"] == LINK_NUMBER
                  and gates["bcode_ordinal_renderer"]["status"].startswith(
                      "passed-")
                  and gates["bcode_ordinal_renderer"]["slice"]["bytes"] <=
                      1320
                  and walls["e000_headroom_bytes"] >= 115,
                  "Link-46 post-receipt qualification red")
        print("c2-lite-v6-link46-bcode-ordinal: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"l65e={gates['bcode_ordinal_renderer']['slice']['bytes']} "
              f"session={gates['capacity']['session_family_bytes']} "
              "hardware=not-run")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
