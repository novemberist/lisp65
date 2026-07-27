#!/usr/bin/env python3
"""Owner-preauthorized successor link after the E000 evacuation WPLTO."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_real_abi_direct_entry_contract as CURRENT  # noqa: E402
import c2_lite_v6_real_abi_e000_eviction_wplto as EVAC  # noqa: E402
import c2_lite_v6_rtov_crc_real_abi_successor_link as LINK  # noqa: E402


OUT = ROOT / (
    "build/c2.2/substitution/product-link-40-c2-lite-v6-real-abi-e000")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link40-c2-lite-v6-real-abi-e000-structural-receipt.json")
EVAC_RECEIPT = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "gate-replay2-receipt.json")
EVAC_RECEIPT_SHA = (
    "0f02f9439b94e7f5467f804d7d5b4d13f646fa1f0f63b11d8485386a178b05a7")
LINK39_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link39-c2-lite-v6-real-abi-replay-structural-receipt.json")
LINK39_FIRST_RED_SHA = (
    "25a780ef732ed9105999a2775cadf28413d5e3dc55d63691492578e827741cb1")


def main() -> int:
    LINK.require(not OUT.exists() and not RECEIPT.exists(),
                 "Link 40 is one-shot")
    LINK.require(LINK.sha(EVAC_RECEIPT) == EVAC_RECEIPT_SHA,
                 "E000 evacuation authority drift")
    LINK.require(LINK.sha(LINK39_FIRST_RED) == LINK39_FIRST_RED_SHA,
                 "Link-39 resident-capacity First Red drift")
    evacuation = json.loads(EVAC_RECEIPT.read_text(encoding="utf-8"))
    LINK.require(
        evacuation["status"] ==
            "passed-purpose-bound-e000-evacuation-gate-replay"
        and evacuation["capacity"]["walls"] == {
            "bank0_text_headroom_bytes": 59,
            "ordinary_bank0_bss_headroom_bytes": 86,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 170,
            "e000_headroom_bytes": 445,
        }
        and evacuation["relocation"]["symbol"] == "vm_arity_accepts"
        and evacuation["relocation"]["bytes"] == 56,
        "E000 evacuation is not the owner-preauthorized shape")

    old = {
        "out": LINK.OUT,
        "receipt": LINK.RECEIPT,
        "number": LINK.LINK_NUMBER,
        "prerequisites": LINK.prerequisites,
        "configure": LINK.BASE_LINK.configure_profile,
        "direct_value": LINK.LITE_DIRECT.value,
        "direct_receipt": LINK.LITE_DIRECT.RECEIPT,
        "single_link": LINK.P.single_link,
    }

    def prerequisites() -> dict[str, Any]:
        value = old["prerequisites"]()
        value["link39_resident_capacity_first_red"] = LINK.bind(
            LINK39_FIRST_RED)
        value["owner_preauthorized_e000_evacuation"] = LINK.bind(
            EVAC_RECEIPT)
        value["current_v6_direct_entry_authority"] = LINK.bind(
            CURRENT.RECEIPT)
        value["link40_driver"] = LINK.bind(Path(__file__))
        return value

    def configure() -> tuple[str, ...]:
        features = old["configure"]()
        LINK.require(EVAC.FEATURE not in features,
                     "E000 evacuation feature duplicated")
        return (*features, EVAC.FEATURE)

    def single_link(*args: Any, **kwargs: Any) -> Any:
        kwargs["direct_entry_receipt"] = CURRENT.RECEIPT
        kwargs["direct_entry_check_tool"] = (
            "c2_lite_v6_real_abi_direct_entry_contract.py")
        lines = tuple(kwargs.get("extra_contract_lines", ()))
        kwargs["extra_contract_lines"] = (*lines,
            "e000_evacuation_symbol=vm_arity_accepts",
            "e000_evacuation_bytes=56",
            "wplto_text_headroom_bytes=59",
            "wplto_e000_headroom_bytes=445",
            "e000_evacuation_authority_sha256=" + EVAC_RECEIPT_SHA)
        return old["single_link"](*args, **kwargs)

    try:
        LINK.OUT = OUT
        LINK.RECEIPT = RECEIPT
        LINK.LINK_NUMBER = 40
        LINK.prerequisites = prerequisites
        LINK.BASE_LINK.configure_profile = configure
        LINK.LITE_DIRECT.value = CURRENT.value
        LINK.LITE_DIRECT.RECEIPT = CURRENT.RECEIPT
        LINK.P.single_link = single_link
        value = LINK.build()
    finally:
        LINK.OUT = old["out"]
        LINK.RECEIPT = old["receipt"]
        LINK.LINK_NUMBER = old["number"]
        LINK.prerequisites = old["prerequisites"]
        LINK.BASE_LINK.configure_profile = old["configure"]
        LINK.LITE_DIRECT.value = old["direct_value"]
        LINK.LITE_DIRECT.RECEIPT = old["direct_receipt"]
        LINK.P.single_link = old["single_link"]
    print("c2-lite-v6-real-abi-e000-successor-link: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
