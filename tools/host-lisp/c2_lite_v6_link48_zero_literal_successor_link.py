#!/usr/bin/env python3
"""Build product Link 48 with valid zero-literal C2D-v6 execution."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link47_l65e_transient_successor_link as BASE  # noqa: E402
import c2_lite_v6_link47_zero_literal_wplto as PROBE  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


LINK_NUMBER = 48
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-48-c2-lite-v6-zero-literal-execution")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-product-link48-c2-lite-v6-zero-literal-execution-"
    "structural-receipt.json")
WPLTO = PROBE.RECEIPT
WPLTO_SHA = (
    "d8cdd3f3df1aad0483c78b81075be740006490c4e840039ff327cf71bb8b667f")
HYBRID_CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"


def current_e000_floor() -> int:
    """Return the active floor from its authority, never from link history."""
    contract = json.loads(HYBRID_CONTRACT.read_text(encoding="utf-8"))
    floor = int(contract["e000_geometry"]["active_floor_bytes"])
    gate_floor = int(contract["one_wplto_exit"]["e000_headroom_min_bytes"])
    L = BASE.LINK44.LINK
    L.require(floor == gate_floor,
              "hybrid E000 contract carries two different active floors")
    return floor


def prerequisites() -> dict[str, Any]:
    L = BASE.LINK44.LINK
    e000_floor = current_e000_floor()
    for path, digest in {
            PROBE.BASE_PRODUCT: PROBE.BASE_PRODUCT_SHA,
            PROBE.BASE_RECEIPT: PROBE.BASE_RECEIPT_SHA,
            PROBE.HARDWARE_FIRST_RED: PROBE.HARDWARE_FIRST_RED_SHA,
            WPLTO: WPLTO_SHA}.items():
        L.require(path.is_file() and L.sha(path) == digest,
                  f"Link-48 authority drift: {path}")
    baseline = json.loads(PROBE.BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(
        PROBE.HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    zero = qualified["zero_literal_execution"]
    L.require(
        baseline["link_number"] == 47
        and baseline["product_identity"]["product"]["sha256"] ==
            PROBE.BASE_PRODUCT_SHA,
        "Link-47 rollback line is not authoritative")
    L.require(
        first_red["status"] ==
            "first-red-valid-zero-literal-c2d-entry-rejected-by-runtime-reader"
        and first_red["accounting"]["line1_boot"] == "passed"
        and first_red["accounting"]
            ["line1_product_first_red_budget_before_run"] == "2/3"
        and first_red["accounting"]["completed_latency_measurements"] ==
            "0/2",
        "Link-47 zero-literal hardware First Red or counters drift")
    L.require(
        qualified["status"] ==
            "passed-product-shaped-WPLTO-no-hardware-no-product-candidate"
        and not qualified["promotable"]
        and zero["source"]["generated_sources"]["status"] ==
            "passed-generated-zero-literal-reader"
        and zero["linked"]["status"] ==
            "passed-linked-vm-run-dir-zero-literal-chain"
        and qualified["walls"]["e000_headroom_bytes"] >= e000_floor
        and qualified["capacity"]["session_family_bytes"] == 65438,
        "green zero-literal WPLTO authority is incomplete")
    return {
        "link47_rollback_product": {
            **L.bind(PROBE.BASE_PRODUCT), "status": "untouched"},
        "link47_structural_authority": L.bind(PROBE.BASE_RECEIPT),
        "link47_zero_literal_hardware_first_red": L.bind(
            PROBE.HARDWARE_FIRST_RED),
        "qualified_zero_literal_wplto": L.bind(WPLTO),
        "canonical_product_profile": BASE.PROFILE.check(),
        "driver": L.bind(Path(__file__)),
    }


def main() -> int:
    L = BASE.LINK44.LINK
    L.require(not OUT.exists() and not RECEIPT.exists(),
              "Link 48 is one-shot")
    old = {
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "number": BASE.LINK_NUMBER,
        "wplto": BASE.WPLTO_REPLAY,
        "wplto_sha": BASE.WPLTO_REPLAY_SHA,
        "prerequisites": BASE.prerequisites,
        "base_product": BASE.PROBE.BASE_PRODUCT,
        "base_product_sha": BASE.PROBE.BASE_PRODUCT_SHA,
        "base_receipt": BASE.PROBE.BASE_RECEIPT,
        "base_receipt_sha": BASE.PROBE.BASE_RECEIPT_SHA,
        "hardware_first_red": BASE.PROBE.HARDWARE_FIRST_RED,
        "hardware_first_red_sha": BASE.PROBE.HARDWARE_FIRST_RED_SHA,
        "transient_source": BASE.TRANSIENT.source_gate,
        "transient_linked": BASE.TRANSIENT.linked_gate,
        "single_link": BASE.LINK44.P.single_link,
    }

    def transient_source(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = old["transient_source"](*args, **kwargs)
        value["zero_literal_execution"] = ZERO.source_gate(
            generated_runtime=kwargs.get("generated_runtime"))
        return value

    def transient_linked(elf: Path) -> dict[str, Any]:
        value = old["transient_linked"](elf)
        c2d = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
        value["zero_literal_execution"] = ZERO.linked_gate(elf, c2d)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(
            line for line in kwargs.get("extra_contract_lines", ())
            if not line.startswith(("mode=", "source_baseline=",
                                    "promotable=",
                                    "line1_first_red_budget=",
                                    "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link48-c2-lite-v6-zero-literal-execution",
            "source_baseline=product-link47-l65e-transient-callability",
            "promotable=no-hardware-not-run",
            "zero_literal_wplto_authority_sha256=" + WPLTO_SHA,
            "c2d_v6_literal_count=zero-is-valid-count-not-validity-marker",
            "zero_literal_fixture=ordinal489-lcc-consp-code-length38",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.WPLTO_REPLAY = WPLTO
        BASE.WPLTO_REPLAY_SHA = WPLTO_SHA
        BASE.prerequisites = prerequisites
        BASE.PROBE.BASE_PRODUCT = PROBE.BASE_PRODUCT
        BASE.PROBE.BASE_PRODUCT_SHA = PROBE.BASE_PRODUCT_SHA
        BASE.PROBE.BASE_RECEIPT = PROBE.BASE_RECEIPT
        BASE.PROBE.BASE_RECEIPT_SHA = PROBE.BASE_RECEIPT_SHA
        BASE.PROBE.HARDWARE_FIRST_RED = PROBE.HARDWARE_FIRST_RED
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = PROBE.HARDWARE_FIRST_RED_SHA
        BASE.TRANSIENT.source_gate = transient_source
        BASE.TRANSIENT.linked_gate = transient_linked
        BASE.LINK44.P.single_link = single_link
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.LINK_NUMBER = old["number"]
        BASE.WPLTO_REPLAY = old["wplto"]
        BASE.WPLTO_REPLAY_SHA = old["wplto_sha"]
        BASE.prerequisites = old["prerequisites"]
        BASE.PROBE.BASE_PRODUCT = old["base_product"]
        BASE.PROBE.BASE_PRODUCT_SHA = old["base_product_sha"]
        BASE.PROBE.BASE_RECEIPT = old["base_receipt"]
        BASE.PROBE.BASE_RECEIPT_SHA = old["base_receipt_sha"]
        BASE.PROBE.HARDWARE_FIRST_RED = old["hardware_first_red"]
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = old["hardware_first_red_sha"]
        BASE.TRANSIENT.source_gate = old["transient_source"]
        BASE.TRANSIENT.linked_gate = old["transient_linked"]
        BASE.LINK44.P.single_link = old["single_link"]

    if result == 0:
        e000_floor = current_e000_floor()
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        gates = receipt["fresh_replacement_gates"]
        zero = gates["transient_execution_lookup"]
        walls = gates["walls"]
        L.require(
            receipt["link_number"] == LINK_NUMBER
            and receipt["product_identity"]["product"]["sha256"] !=
                PROBE.BASE_PRODUCT_SHA
            and zero["source"]["zero_literal_execution"]
                ["generated_sources"]["status"] ==
                    "passed-generated-zero-literal-reader"
            and zero["linked"]["zero_literal_execution"]["status"] ==
                "passed-linked-vm-run-dir-zero-literal-chain"
            and walls["e000_headroom_bytes"] >= e000_floor,
            "Link-48 post-receipt qualification red")
        print("c2-lite-v6-link48-zero-literal-successor: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              f"text={walls['bank0_text_headroom_bytes']} "
              f"e000={walls['e000_headroom_bytes']} "
              f"session={gates['capacity']['session_family_bytes']} "
              "hardware=not-run")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
