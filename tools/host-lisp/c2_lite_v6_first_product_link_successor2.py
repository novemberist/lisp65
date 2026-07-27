#!/usr/bin/env python3
"""Second Class-A successor for the still-unconsumed C2-lite product link."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_direct_entry_contract as DIRECT  # noqa: E402
import c2_lite_v6_direct_entry_contract as LITE_DIRECT  # noqa: E402
import c2_lite_v6_first_product_link as LINK  # noqa: E402
import c2_lite_v6_first_product_link_successor as S1  # noqa: E402


FIRST_RED = S1.RECEIPT
OUT = ROOT / "build/c2.2/substitution/product-link-37-c2-lite-v6-successor2"
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-successor2-structural-receipt.json")
DIAGNOSIS = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-direct-entry-harness-diagnosis.json")


def generated_direct_entry_gate() -> dict[str, Any]:
    generated = OUT / "generated-product-sources"
    old = (DIRECT.BUILD, DIRECT.TARGET_CORE, DIRECT.PHASE_08,
           DIRECT.PHASE_12, DIRECT.TARGET_DEFINES)
    try:
        DIRECT.BUILD = OUT / "generated-direct-entry-gate"
        DIRECT.TARGET_CORE = generated / "c2-stream-v2-decoder.c"
        DIRECT.PHASE_08 = generated / "c2-stream-v2-phase-08.c"
        DIRECT.PHASE_12 = generated / "c2-stream-v2-phase-12.c"
        DIRECT.TARGET_DEFINES = ("C2D_V6_ROOT_SURROGATE",)
        value = DIRECT.collect()
    finally:
        (DIRECT.BUILD, DIRECT.TARGET_CORE, DIRECT.PHASE_08,
         DIRECT.PHASE_12, DIRECT.TARGET_DEFINES) = old
    parity = value["cross_parity"]
    LINK.require(parity["direct_entry_references"] == 637
                 and parity["fixnum_decodable_published_values"] == 0
                 and parity["target_phase12_negative_classes"] == 4,
                 "generated C2-lite direct-entry closure red")
    return {
        "status": "passed-generated-product-sources-637-of-637",
        "cross_parity": parity,
        "single_truth": value["single_truth"],
        "target_execution": value["target_execution"],
        "bindings": value["bindings"],
    }


def record_diagnosis() -> None:
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    LINK.require(first["status"] ==
                 "FIRST RED: first C2-lite product link stopped"
                 and "c2_hot_refill_direct_entry_contract.py" in
                    first["diagnostic"]["message"]
                 and first["execution_accounting"]["product_closure_links"] == 0,
                 "historical direct-entry First Red drift")
    current = LITE_DIRECT.value()
    value = {
        "format": "lisp65-c2-lite-v6-direct-entry-harness-disposition-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-class-a-direct-entry-rebind-product-link-unconsumed",
        "class": "A",
        "first_red": LINK.bind(FIRST_RED),
        "diagnosis": {
            "historical_receipt": LINK.bind(LINK.BASE.DIRECT.RECEIPT),
            "fresh_canonical_sha256": LINK.sha_bytes(current)
                if hasattr(LINK, "sha_bytes") else "recorded-by-new-receipt",
            "semantic_result": {
                "references": current["cross_parity"]["direct_entry_references"],
                "fixnum_decodable": current["cross_parity"]
                    ["fixnum_decodable_published_values"],
                "negative_classes": current["cross_parity"]
                    ["target_phase12_negative_classes"],
            },
            "disposition": (
                "Preserve the historical receipt; bind a new C2-lite current-"
                "source receipt and rerun parity against generated phase 8/12 "
                "after the product link."),
        },
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "product_links": 0, "hardware_runs": 0},
    }
    LINK.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)


def main() -> int:
    LINK.require(FIRST_RED.is_file() and LITE_DIRECT.RECEIPT.is_file()
                 and not OUT.exists() and not RECEIPT.exists()
                 and not DIAGNOSIS.exists(),
                 "C2-lite Link-37 successor2 state is not one-shot")
    record_diagnosis()
    old_out, old_receipt = LINK.OUT, LINK.RECEIPT
    old_check = LINK.BASE.PRE.check
    old_prerequisites = LINK.prerequisites
    old_single_link = LINK.P.single_link
    old_product_gates = LINK.c2_lite_product_gates

    def prerequisites() -> dict[str, Any]:
        result = old_prerequisites()
        result["class_a_v5_prelink_disposition"] = LINK.bind(S1.DIAGNOSIS)
        result["class_a_direct_entry_disposition"] = LINK.bind(DIAGNOSIS)
        result["c2_lite_direct_entry_receipt"] = LINK.bind(LITE_DIRECT.RECEIPT)
        result["successor2_driver"] = LINK.bind(Path(__file__))
        return result

    def single_link(out: Path, **kwargs: Any) -> None:
        kwargs["direct_entry_receipt"] = LITE_DIRECT.RECEIPT
        kwargs["direct_entry_check_tool"] = (
            "c2_lite_v6_direct_entry_contract.py")
        old_single_link(out, **kwargs)

    def product_gates(product: Path, elf: Path,
                      host: dict[str, Any]) -> dict[str, Any]:
        result = old_product_gates(product, elf, host)
        result["generated_direct_entry"] = generated_direct_entry_gate()
        return result

    try:
        LINK.OUT, LINK.RECEIPT = OUT, RECEIPT
        LINK.BASE.PRE.check = S1.current_b2_gate
        LINK.prerequisites = prerequisites
        LINK.P.single_link = single_link
        LINK.c2_lite_product_gates = product_gates
        value = LINK.build()
    finally:
        LINK.OUT, LINK.RECEIPT = old_out, old_receipt
        LINK.BASE.PRE.check = old_check
        LINK.prerequisites = old_prerequisites
        LINK.P.single_link = old_single_link
        LINK.c2_lite_product_gates = old_product_gates
    print("c2-lite-v6-first-product-link-successor2: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
