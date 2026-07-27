#!/usr/bin/env python3
"""Product-shaped WPLTO for the cold append source-domain barrier."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_domain_wplto as BASE  # noqa: E402


P = BASE.P
SUFFIX = BASE.SUFFIX
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link55-append-suffix-cold-guard-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link55-append-suffix-cold-guard-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-cold-guard-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link55-append-suffix-cold-guard-wplto-receipt.json")
LINK54_PRODUCT = BASE.LINK54_PRODUCT
LINK54_RECEIPT = BASE.LINK54_RECEIPT
LINK54_HARDWARE = BASE.LINK54_HARDWARE
CONTRACT_PROBE = BASE.CONTRACT_PROBE
FIRST_RED = EVIDENCE / (
    "c2.2-link55-append-suffix-domain-wplto-first-red.json")


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
        FIRST_RED:
            "9510a3f57439a7b73c5b3c72e4ee3bdb51101ad040d507560deb13ef1e205f41",
        SUFFIX.CONTRACT:
            "f2a0412f6a2039c26d9d9438479b2d49b88dbeda014de80025a6cf7e30f3dee8",
    }
    for path, digest in expected.items():
        P.require(path.is_file() and P.sha(path) == digest,
                  f"Link-55 cold-guard authority SHA drift: {path}")
    baseline = json.loads(LINK54_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
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
        and first_red["status"] ==
            "first-red-source-domain-guard-expands-resident-window-by-406-bytes"
        and first_red["first_red"]["exact_attribution"] == {
            "c2_resident_delta_bytes": 406,
            "c2_stream_shelf_read_delta_bytes": 406,
            "other_c2_resident_delta_bytes": 0,
        }, "cold-guard baseline or first-red authority incomplete")
    return {
        "link54_rollback_product": {**P.bind(LINK54_PRODUCT),
                                    "status": "untouched"},
        "link54_structural_authority": P.bind(LINK54_RECEIPT),
        "link54_phase06a_hardware_first_red": P.bind(LINK54_HARDWARE),
        "append_suffix_contract_probe": P.bind(CONTRACT_PROBE),
        "resident_guard_WPLTO_first_red": P.bind(FIRST_RED),
        "cold_append_read_domain_contract": P.bind(SUFFIX.CONTRACT),
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    P.require(not OUT.exists() and not RECEIPT.exists(),
              "Link-55 cold-guard WPLTO is one-shot")
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
    walls = value["walls"]
    capacity = value["capacity"]
    source = value["append_suffix_read_domain_source_gate"]
    linked = value["append_suffix_read_domain_linked_gate"]
    P.require(
        source["status"] ==
            "passed-four-phase-suffix-and-source-domain-contract"
        and len(source["negative_mutations"]) == 13
        and linked["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and linked["source_read"]["bytes"] == 209
        and linked["source_read"]["section"] ==
            ".lisp65_c2_kernal_window.c2_resident"
        and linked["cold_guard"]["section"] == ".lisp65_rt_c2d_04"
        and linked["cold_guard"]["phase04_call_edges"] == 1
        and linked["new_state_objects"] == 0
        and walls["e000_headroom_bytes"] == 58
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536,
        "Link-55 cold append source-domain WPLTO qualification red")
    value["format"] = (
        "lisp65-c2-link55-append-suffix-cold-guard-wplto-v1")
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-cold-append-source-domain-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["cold_barrier_placement"] = {
        "seal_producer": linked["seal_producer"],
        "guard": linked["cold_guard"],
        "publication_restore": linked["publication_restore"],
        "resident_source_read": linked["source_read"],
        "resident_window_delta_bytes": 0,
        "new_state_bytes": 0,
        "session_family_headroom_bytes":
            65536 - capacity["session_family_bytes"],
    }
    value["next_gate"] = "authorized product Link 55; hardware not yet run"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-append-suffix-cold-guard-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"guard={linked['cold_guard']['bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (P.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-append-suffix-cold-guard-wplto: FIRST RED: "
              + str(error), file=sys.stderr)
        raise SystemExit(2)
