#!/usr/bin/env python3
"""One product-shaped WPLTO for the append suffix/read-domain repair."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link54_phase06a_cutpoint_wplto as BASE  # noqa: E402
import c2_append_suffix_read_domain_gate as SUFFIX  # noqa: E402


P = BASE.PROBE.PROBE
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link55-append-suffix-domain-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link55-append-suffix-domain-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-domain-wplto-base-receipt.json")
RECEIPT = EVIDENCE / "c2.2-link55-append-suffix-domain-wplto-receipt.json"
LINK54_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-54-c2-lite-v6-phase06a-cutpoint/"
    "lisp65-c2-substitution-linked.prg")
LINK54_RECEIPT = EVIDENCE / (
    "c2.2-product-link54-c2-lite-v6-phase06a-cutpoint-structural-receipt.json")
LINK54_HARDWARE = EVIDENCE / (
    "c2.2-product-link54-phase06a-cutpoint-hardware-first-red.json")
CONTRACT_PROBE = EVIDENCE / (
    "c2.2-link54-phase06a-suffix-contract-probe-receipt.json")


def authority() -> dict[str, Any]:
    expected = {
        LINK54_PRODUCT:
            "4cfc797f4ac4fac6cc4fea363ea684ea0dc8c7b395372ebc8bbfe2072fedef07",
        LINK54_RECEIPT:
            "1d57762c36832d70f91299e6cc7ea44b72a5634301075983ffd3441ae3a08b34",
        LINK54_HARDWARE:
            "08cb5b0a3a258a47614bb01f60ca71ace2c20101f3b1442c9bc137765fe64ad8",
        CONTRACT_PROBE:
            "8ab10e9a0b858f162900d6d527dfd902fcca7f0e97a6115e4151546af88d607a",
        SUFFIX.CONTRACT:
            "f20282928acd4226e62dd29be04e8c6230f606758562108b9ac48bf7df976add",
    }
    for path, digest in expected.items():
        P.require(path.is_file() and P.sha(path) == digest,
                  f"Link-55 suffix-domain authority SHA drift: {path}")
    baseline = json.loads(LINK54_RECEIPT.read_text(encoding="utf-8"))
    hardware = json.loads(LINK54_HARDWARE.read_text(encoding="utf-8"))
    probe = json.loads(CONTRACT_PROBE.read_text(encoding="utf-8"))
    gates = baseline["fresh_replacement_gates"]
    P.require(
        baseline["status"] ==
            "passed-phase06a-five-cutpoint-product-identity-hardware-not-run"
        and gates["walls"] == {
            "bank0_text_headroom_bytes": 48,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and gates["capacity"]["session_family_bytes"] == 65438
        and hardware["status"] ==
            "first-red-locked-at-phase06a-image-record-read-before-inner-vm"
        and probe["status"] ==
            "passed-contract-classification-before-product-fix",
        "Link-54 suffix-domain baseline authority incomplete")
    return {
        "link54_rollback_product": {**P.bind(LINK54_PRODUCT),
                                    "status": "untouched"},
        "link54_structural_authority": P.bind(LINK54_RECEIPT),
        "link54_phase06a_hardware_first_red": P.bind(LINK54_HARDWARE),
        "append_suffix_contract_probe": P.bind(CONTRACT_PROBE),
        "append_suffix_read_domain_contract": P.bind(SUFFIX.CONTRACT),
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    P.require(not OUT.exists() and not RECEIPT.exists(),
              "Link-55 suffix-domain WPLTO is one-shot")
    authority()
    original = {
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
        BASE.OUT = original["out"]
        BASE.INTERNAL = original["internal"]
        BASE.BASE_RECEIPT = original["base_receipt"]
        BASE.RECEIPT = original["receipt"]
        BASE.authority = original["authority"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    source = SUFFIX.source_gate(mutations=True)
    linked = SUFFIX.linked_gate(
        elf, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    walls = value["walls"]
    capacity = value["capacity"]
    P.require(
        source["status"] ==
            "passed-four-phase-suffix-and-source-domain-contract"
        and len(source["negative_mutations"]) == 13
        and source["fixture"]["cases_passed"] == 11
        and linked["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and linked["new_state_objects"] == 0
        and all(row["bytes"] <= 1792
                for row in linked["phases"].values())
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536,
        "Link-55 append suffix/read-domain WPLTO qualification red")
    value["format"] = "lisp65-c2-link55-append-suffix-domain-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-append-suffix-source-domain-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["append_suffix_read_domain_source_gate"] = source
    value["append_suffix_read_domain_linked_gate"] = linked
    value["baseline_delta"] = {
        "bank0_text_bytes": 48 - walls["bank0_text_headroom_bytes"],
        "ordinary_bss_bytes": 213 -
            walls["ordinary_bank0_bss_headroom_bytes"],
        "fixed_hot_block_bytes": 33 -
            walls["fixed_hot_block_headroom_bytes"],
        "resident_island_bytes": 5 -
            walls["resident_island_headroom_bytes"],
        "e000_bytes": 58 - walls["e000_headroom_bytes"],
        "session_family_bytes": capacity["session_family_bytes"] - 65438,
    }
    value["product_fix"] = {
        "suffix_phases": ["06a", "06b", "07", "08"],
        "lower_bound": "c2_stream_context.image_first",
        "boot_full_stage_preserved": True,
        "post_ready_computed_source_policy": (
            "active append plus session tag plus authenticated private span"),
        "static_shelf_prefix_after_ready": "rejected-before-DMA",
        "new_state_bytes": 0,
    }
    value["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2",
    }
    value["next_gate"] = "separate Class-C authorization for product Link 55"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-append-suffix-domain-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"source_read={linked['source_read']['bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (P.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-append-suffix-domain-wplto: FIRST RED: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
