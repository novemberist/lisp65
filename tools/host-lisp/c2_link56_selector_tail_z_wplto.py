#!/usr/bin/env python3
"""One product-shaped WPLTO for the Link-55 selector tail-Z repair."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_link55_append_suffix_fusion_wplto as BASE  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link56-selector-tail-z-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link56-selector-tail-z-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link56-selector-tail-z-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link56-selector-tail-z-wplto-receipt.json")
HARDWARE = EVIDENCE / (
    "c2.2-product-link55-append-suffix-defun-crash-hardware-first-red.json")
CATALOG = EVIDENCE / (
    "c2.2-product-link55-defun-crash-static-suspect-catalog.json")


def authority() -> dict[str, Any]:
    base = BASE.GEOMETRY.authority()
    expected = {
        HARDWARE:
            "bb7c1e826cb666d8dc5274cc967ef6444eb45e28990e8481095e7ebc31244595",
        CATALOG:
            "6e4aa32c45b834c7997b5b92d38ba9704cccddf4be846ae9c0700086ea9fb2a2",
    }
    for path, digest in expected.items():
        P.require(path.is_file() and P.sha(path) == digest,
                  f"selector tail-Z authority drift: {path}")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    P.require(
        catalog["status"] == "convicted-selector-tail-violates-C-entry-Z0"
        and catalog["suspect_1_selector"]["verdict"] == "convicted"
        and catalog["suspect_2_fused_entry_geometry"]["verdict"] ==
            "exonerated"
        and catalog["suspect_3_plan_bytes"]["verdict"] == "exonerated"
        and catalog["execution_accounting"] == {
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0},
        "selector tail-Z catalog is incomplete")
    return {
        **base,
        "link55_hardware_first_red": P.bind(HARDWARE),
        "static_suspect_catalog": P.bind(CATALOG),
        "journal_prepare_contract": P.bind(BASE.FUSION.CONTRACT),
        "journal_prepare_source_gate": P.bind(
            ROOT / "tools/host-lisp/c2_journal_prepare_coresident_gate.py"),
        "journal_prepare_cutpoint_fixture": P.bind(BASE.FUSION.FIXTURE),
        "corrected_assembler_selector": P.bind(
            ROOT / "src/c2_journal_prepare_select.s"),
        "ELF_derived_assembler_ABI_gate": P.bind(
            ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    P.require(not OUT.exists() and not RECEIPT.exists(),
              "selector tail-Z WPLTO is one-shot")
    authority()
    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    source = BASE.FUSION.source_gate(
        OUT / "tail-z-journal-prepare-cutpoints")
    linked = BASE.FUSION.linked_gate(
        elf, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    abi = ABI.audit_elf(elf)
    leaf = abi["journal_prepare_selector"]
    walls = value["walls"]
    capacity = value["capacity"]
    P.require(
        source["fixture"]["marker_domain_cases"] == 512
        and source["fixture"]["marker_domain_accepted"] == 3
        and source["fixture"]["marker_domain_rejected"] == 509
        and source["checks"]["tail_C_ABI_Z0"]
        and linked["functions"]["c2_append_journal_prepare_phase"]["bytes"]
            == 58
        and linked["bytes"] == 1768
        and linked["packed_bytes"] == 1792
        and linked["headroom_bytes"] == 24
        and leaf["status"] ==
            "passed-real-context-ABI-two-total-tail-edges-Z0"
        and len(leaf["tail_C_entry_Z"]) == 2
        and all(row["operand"] in ("#$0", "#$00")
                for row in leaf["tail_C_entry_Z"].values())
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and walls == {
            "bank0_text_headroom_bytes": 48,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58},
        "selector tail-Z WPLTO qualification red")
    value["format"] = "lisp65-c2-link56-selector-tail-z-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-selector-tail-Z0-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["selector_tail_Z_repair"] = {
        "source_gate": source,
        "linked_fusion_gate": linked,
        "assembler_ABI_gate": leaf,
        "product_delta_bytes": {
            "selector": 4,
            "fused_slice": 4,
            "packed_session_family": 0,
            "resident_text": 0,
            "resident_window": 0,
            "bss": 0,
        },
        "fixed_edges": sorted(leaf["tail_C_entry_Z"]),
    }
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = (
        "Class-C successor product link; hardware remains off until the "
        "linked candidate is fully qualified")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link56-selector-tail-z-wplto: PASS "
        f"selector={leaf['bytes']} fusion={linked['bytes']} "
        f"session={capacity['session_family_bytes']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (P.ProbeError, BASE.FUSION.GateError, ABI.GateError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-link56-selector-tail-z-wplto: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
