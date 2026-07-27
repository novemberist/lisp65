#!/usr/bin/env python3
"""One authorized WPLTO for the final one-quantum Session fusion."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_final_consolidation_gate as CONS  # noqa: E402
import c2_journal_prepare_coresident_gate as FUSION  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as PROFILE  # noqa: E402
import c2_lite_v6_link55_append_suffix_domain_wplto as BASE  # noqa: E402
import c2_lite_v6_link55_append_suffix_geometry_wplto as GEOMETRY  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/link55-append-suffix-fusion-asm-leaf-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link55-append-suffix-geometry-wplto-first-red.json")
PREFLIGHT_RED = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-wplto-receipt.json")
FUSION_FIRST_RED = EVIDENCE / (
    "c2.2-link55-journal-prepare-fusion-wplto-first-red.json")


def authority() -> dict[str, Any]:
    base = GEOMETRY.authority()
    expected = {
        FIRST_RED:
            "055d3d46cf3accdbd874733132a5e7aed665d9c339f31f9e87c5a045d17e3a2e",
        PREFLIGHT_RED:
            "3eb54375ffc5a6d5197e33eced2199d6f09131c02e2ef9c29129f1c1ff49c31a",
        FUSION_FIRST_RED:
            "7892a8ff32dd89bdc676035906c98a053ec223fe2f87d108760aa51f201ae18d",
        FUSION.CONTRACT:
            "958204a5a833e7a756f350e74350ec5210da6c8e7f1528c8c10ee2d30ca7559c",
        ROOT / "tools/host-lisp/c2_append_final_consolidation_gate.py":
            "a44b63e3fe1fd91b32c98ab3eb7d35bf5d1303b5c60dd2a37777074d6f491dfc",
        ROOT / "tools/host-lisp/c2_journal_prepare_coresident_gate.py":
            "ef8a4f6a251aad1e17cb95c8f31bfc70e2bb3801d4ec92f6e70cc11513ffb9d3",
        FUSION.FIXTURE:
            "3b2d12484f66bf7dcf1623c14ac5b52d3753d9e69b596dae1b5a3e32d0517d7a",
        ROOT / "src/c2_journal_prepare_select.s":
            "3d3317cf6f50783bba6f40584d436f4ec3030d6544e546638f851b08aaafc956",
        ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py":
            "8416ff075e168f585d413c421e41cdf98edbbe61ffdfaef5a2e5b6db9ebc2724",
    }
    for path, digest in expected.items():
        P.require(path.is_file() and P.sha(path) == digest,
                  f"Link-55 fusion authority SHA drift: {path}")
    red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    P.require(
        red["status"] ==
            "first-red-phase04-pack-quantum-leaves-session-family-158-bytes-over-capacity"
        and red["first_red"]["required_recovery_bytes"] == 158
        and red["first_red"]["available_proven_mechanism"] ==
            "one co-residence fusion that removes one 256-byte quantum would restore 98 bytes of Session-family reserve",
        "Link-55 one-quantum First Red authority drift")
    return {
        **base,
        "one_quantum_WPLTO_first_red": P.bind(FIRST_RED),
        "class_A_preflight_first_red": P.bind(PREFLIGHT_RED),
        "measured_C_selector_first_red": P.bind(FUSION_FIRST_RED),
        "corrected_final_consolidation_gate": P.bind(
            ROOT / "tools/host-lisp/c2_append_final_consolidation_gate.py"),
        "journal_prepare_contract": P.bind(FUSION.CONTRACT),
        "journal_prepare_source_gate": P.bind(
            ROOT / "tools/host-lisp/c2_journal_prepare_coresident_gate.py"),
        "journal_prepare_cutpoint_fixture": P.bind(FUSION.FIXTURE),
        "journal_prepare_assembler_selector": P.bind(
            ROOT / "src/c2_journal_prepare_select.s"),
        "ELF_derived_assembler_ABI_gate": P.bind(
            ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    P.require(not OUT.exists() and not RECEIPT.exists(),
              "Link-55 one-quantum fusion WPLTO is one-shot")
    authority()
    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
        "configure": CONS.configure_publish_clear,
        "features": PROFILE.resolved_features,
    }

    def configure_complete_profile() -> None:
        old["configure"]()
        FUSION.configure()

    def resolved_features() -> tuple[str, ...]:
        features = old["features"]()
        P.require(FUSION.FEATURE not in features,
                  "journal/prepare feature duplicated")
        return (*features, FUSION.FEATURE)

    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        CONS.configure_publish_clear = configure_complete_profile
        PROFILE.resolved_features = resolved_features
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
        CONS.configure_publish_clear = old["configure"]
        PROFILE.resolved_features = old["features"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    source = FUSION.source_gate(OUT / "journal-prepare-cutpoints")
    linked = FUSION.linked_gate(
        elf, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    walls = value["walls"]
    capacity = value["capacity"]
    P.require(
        source["status"] ==
            "passed-one-record-journal-prepare-source-contract"
        and source["fixture"]["negative_mutations"] == 6
        and linked["status"] ==
            "passed-linked-one-record-journal-prepare-cutpoint"
        and linked["functions"]["c2_append_journal_prepare_phase"]["bytes"]
            <= 82
        and linked["bytes"] <= 1792
        and linked["packed_recovered_bytes"] >= 256
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] == 58
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0,
        "Link-55 one-quantum fusion qualification red")
    value["format"] = "lisp65-c2-link55-append-suffix-fusion-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = "passed-one-quantum-fusion-WPLTO-all-walls-green"
    value["authority"] = authority()
    value["journal_prepare_co_residence"] = {
        "source": source,
        "linked": linked,
        "partner_selection": {
            "logical_order": ["rollback_prepare", "journal_write"],
            "pre_fusion_bytes": [888, 891],
            "pre_fusion_sum_bytes": 1779,
            "slice_cap_bytes": 1792,
            "packed_before_bytes": 2048,
            "packed_after_bytes": linked["packed_bytes"],
        },
        "catalog_records_before": 49,
        "catalog_records_after": 48,
        "new_state_bytes": 0,
        "new_pointers": 0,
    }
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = "authorized product Link 55, then hardware double-run"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-append-suffix-fusion-wplto: PASS "
          f"slice={linked['bytes']} packed={linked['packed_bytes']} "
          f"session={capacity['session_family_bytes']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (P.ProbeError, FUSION.GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-append-suffix-fusion-wplto: FIRST RED: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
