#!/usr/bin/env python3
"""Build/check the v1.4 VIC-unlock successor as Link 90."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v14_parity_pilot_candidate_product as LINK89  # noqa: E402


PREV = LINK89.PREV
M65 = LINK89.M65
RELEASE = "v1.4.0"
LINK = 90
BUILD = ROOT / "build/c2.3/v1.4.0-candidate-product-link90-r1"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD = EVIDENCE / "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json"
ATTRIBUTION = EVIDENCE / (
    "c2.3-v1.4-link89-vic-unlock-tailcall-attribution.json")
FLEET = ROOT / "build/post-promotion/v14/sample-fleet-host/fleet-receipt.json"
FIXED_TOY = ROOT / (
    "build/post-promotion/v14/sample-fleet-host-link90/"
    "parity-toy.receipt.json")
EXPECTED_STATIC = 47282
EXPECTED_ENTRIES = 787
EXPECTED_RESOLUTIONS = 3031
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
EXPECTED_PRODUCT_ID = "0x293611ce"
EXPECTED_BANK2_SHA = (
    "f09a167b31e5a78dfd02195a3d49e5af0e26bb1b3343a14b986ca8f538edf846"
)
BASE_BUILD_MANIFEST = PREV.build_manifest


def configure_successor() -> None:
    PREV.RELEASE = RELEASE
    PREV.LINK = LINK
    PREV.BUILD = BUILD
    PREV.MANIFEST = MANIFEST
    PREV.DRIVER = DRIVER
    PREV.CARD = CARD
    PREV.STDLIB = M65.PREFIX.with_suffix(".manifest.json")
    PREV.EXPECTED_STATIC = EXPECTED_STATIC
    PREV.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    PREV.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    PREV.EXPECTED_ROOTS = EXPECTED_ROOTS
    PREV.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    PREV.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    PREV.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    PREV.PRODUCT.RELEASE = RELEASE
    PREV.PRODUCT.LINK = LINK
    PREV.PRODUCT.BUILD = BUILD
    PREV.PRODUCT.MANIFEST = MANIFEST
    PREV.PRODUCT.DRIVER = DRIVER
    PREV.PRODUCT.V.RANDOM_MANIFEST = PREV.STDLIB
    PREV.PRODUCT.V.EXPECTED_STATIC = EXPECTED_STATIC
    PREV.PRODUCT.V.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    PREV.PRODUCT.V.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    PREV.PRODUCT.V.EXPECTED_ROOTS = EXPECTED_ROOTS
    PREV.PRODUCT.V.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    PREV.PRODUCT.V.EXPECTED_PRODUCT_ID = EXPECTED_PRODUCT_ID
    PREV.PRODUCT.V.EXPECTED_BANK2_SHA = EXPECTED_BANK2_SHA
    PREV.PRODUCT.build_manifest = build_manifest


def freight_gates() -> dict[str, Any]:
    summaries = {
        "banner": PREV.run(
            [sys.executable, "tools/host-lisp/c2_repl_banner_version_gate.py",
             "--selftest"], "v1.4 successor banner gate"),
        "input_wait": PREV.run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "v1.4 input/wait gate"),
        "boot_inheritance": PREV.run(
            [sys.executable,
             "tools/host-lisp/c2_ship_boot_inheritance_gate.py"],
            "v1.4 Ship boot-inheritance gate"),
        "q": PREV.run(
            [sys.executable, "tools/host-lisp/c2_q_gate.py"],
            "v1.4 q gate"),
        "editor": PREV.run(
            [sys.executable,
             "tools/host-lisp/c2_v126_editor_allocation_gate.py", "check"],
            "v1.4 editor allocation gate"),
        "m65_hw": PREV.run(
            [sys.executable, "tools/host-lisp/c2_m65_hw_gate.py"],
            "v1.4 m65-hw gate"),
        "surface": PREV.run(
            [sys.executable,
             "tools/host-lisp/v11_surface_delivery_parity.py"],
            "v1.4 surface-delivery parity"),
        "ship_contract": PREV.run(
            [sys.executable, "tools/host-lisp/ship_builder.py", "selftest"],
            "v1.4 Ship contract selftest"),
    }
    card = PREV.load(CARD)
    m65 = PREV.load(M65.RECEIPT)
    profile = PREV.load(PREV.PROFILE)
    fleet = PREV.load(FLEET)
    toy = PREV.load(FIXED_TOY)
    attribution = PREV.load(ATTRIBUTION)
    PREV.require(
        card["status"]
            == "passed-v1.4-link90-vic-unlock-one-product-shaped-WPLTO"
        and card["wplto_probes_consumed"] == 1
        and card["resident_delta_bytes"] == 0
        and card["native_primitive_delta"] == 0
        and card["wall_headroom_delta_from_link89"] == {
            "bank0_text_headroom_bytes": 0,
            "e000_headroom_bytes": 0,
            "fixed_hot_block_headroom_bytes": 0,
            "ordinary_bank0_bss_headroom_bytes": 0,
            "resident_island_headroom_bytes": 0,
        }
        and m65["status"] == "passed"
        and m65["artifact"]["code_bytes"] == 1768
        and m65["artifact"]["objects"] == 30
        and m65["artifact"]["cases_executed_per_lane"] == 13
        and m65["artifact"]["lanes"] == 2
        and m65["mutations"]["count"] == 10
        and profile["product_build_id"] == EXPECTED_PRODUCT_ID
        and profile["bank2_static_code"]["sha256"] == EXPECTED_BANK2_SHA
        and fleet["sample_count"] == fleet["host_executions"] == 5
        and toy["status"] == "passed"
        and toy["executions"] == 1
        and toy["verification"]["members_verified"] == 9
        and attribution["status"]
            == "ATTRIBUTED AND HOST-FIXED; SUCCESSOR DEVICE PROOF REQUIRED",
        "Link-90 VIC-unlock freight authority drift",
    )
    return {
        "mode": "v1.4-vic-unlock-target-edge-successor",
        "summaries": summaries,
        "m65_hw": PREV.bind(M65.RECEIPT),
        "attribution": PREV.bind(ATTRIBUTION),
        "accepted_native_geometry": PREV.bind(CARD),
        "ship_fleet": PREV.bind(FLEET),
        "fixed_parity_toy": PREV.bind(FIXED_TOY),
        "tick_hook_disposition": PREV.bind(
            ROOT / "docs/planning/c2.3-v1.4-tick-hook-scheduler-design.md"),
    }


def build_manifest(wplto: dict[str, Any],
                   completion: dict[str, Any]) -> dict[str, Any]:
    value = BASE_BUILD_MANIFEST(wplto, completion)
    plane = value["static_plane"]
    plane.update({
        "status": "passed-v1.4-vic-unlock-single-emitter-static-plane",
        "m65_hw_contract": PREV.bind(M65.CONTRACT),
        "m65_hw_execution": PREV.bind(M65.RECEIPT),
        "attribution": PREV.bind(ATTRIBUTION),
        "ship_fleet": PREV.bind(FLEET),
        "fixed_parity_toy": PREV.bind(FIXED_TOY),
        "tick_hook_disposition": PREV.bind(
            ROOT / "docs/planning/c2.3-v1.4-tick-hook-scheduler-design.md"),
    })
    value["candidate"]["release"] = RELEASE
    value["candidate"]["source_driver"] = PREV.bind(DRIVER)
    MANIFEST.write_bytes(PREV.CAN.json_bytes(value))
    return value


def augment_feature_receipt(freight: dict[str, Any]) -> None:
    path = BUILD / "receipts" / f"{RELEASE}-feature-gates.json"
    value = PREV.load(path)
    value.update(freight)
    value["status"] = "passed-v1.4-vic-unlock-successor-feature-gates"
    path.write_bytes(PREV.CAN.json_bytes(value))


def main() -> int:
    configure_successor()
    PREV.freight_gates = freight_gates
    PREV.augment_feature_receipt = augment_feature_receipt
    result = PREV.main()
    if result == 0 and len(sys.argv) > 1 and sys.argv[1] == "build":
        print(
            "c2-v1.4.0-link90-candidate-product: FREIGHT PASS "
            "m65=15 cases=26 mutations=10 ship=5+1 "
            "bank2=47282 resident=+0")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PREV.CandidateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v1.4.0-link90-candidate-product: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
