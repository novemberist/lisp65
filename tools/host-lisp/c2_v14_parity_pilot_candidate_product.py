#!/usr/bin/env python3
"""Build/check the v1.4 synchronous parity pilot as Link 89."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_candidate_product as PREV  # noqa: E402
import c2_m65_hw_gate as M65  # noqa: E402


RELEASE = "v1.4.0"
LINK = 89
BUILD = ROOT / "build/c2.3/v1.4.0-candidate-product-link89-r1"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD = EVIDENCE / "c2.3-v1.4-parity-pilot-wplto-receipt.json"
FLEET = ROOT / "build/post-promotion/v14/sample-fleet-host/fleet-receipt.json"
EXPECTED_STATIC = 47298
EXPECTED_ENTRIES = 788
EXPECTED_RESOLUTIONS = 3034
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710
EXPECTED_PRODUCT_ID = "0xac5f997a"
EXPECTED_BANK2_SHA = (
    "eb45f07ed2edc179812c585399aef5ee9ceb0dbdd02f1126e086e357156f4c30"
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
             "--selftest"], "v1.4 predecessor banner gate"),
        "input_wait": PREV.run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "v1.4 input/wait gate"),
        "boot_inheritance": PREV.run(
            [sys.executable, "tools/host-lisp/c2_ship_boot_inheritance_gate.py"],
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
    PREV.require(
        card["status"]
            == "passed-v1.4-parity-pilot-one-product-shaped-WPLTO"
        and card["wplto_probes_consumed"] == 1
        and card["resident_delta_bytes"] == 0
        and card["native_primitive_delta"] == 0
        and card["inherited_native_geometry"] == {
            "noinit_address": "0xc34d", "noinit_bytes": 6,
            "overlay_floor": "0xc354", "status": "restored-exactly",
        }
        and m65["status"] == "passed"
        and m65["artifact"]["code_bytes"] == 1784
        and m65["artifact"]["cases_executed_per_lane"] == 12
        and m65["artifact"]["lanes"] == 2
        and m65["mutations"]["count"] == 9
        and profile["product_build_id"] == EXPECTED_PRODUCT_ID
        and profile["bank2_static_code"]["sha256"] == EXPECTED_BANK2_SHA
        and fleet["sample_count"] == fleet["host_executions"] == 5
        and fleet["media_members_verified"] == 45,
        "Link-89 parity-pilot freight authority drift",
    )
    return {
        "mode": "v1.4-synchronous-parity-pilot-successor",
        "summaries": summaries,
        "m65_hw": PREV.bind(M65.RECEIPT),
        "accepted_native_geometry": PREV.bind(CARD),
        "ship_fleet": PREV.bind(FLEET),
        "tick_hook_disposition": PREV.bind(
            ROOT / "docs/planning/c2.3-v1.4-tick-hook-scheduler-design.md"),
    }


def build_manifest(wplto: dict[str, Any], completion: dict[str, Any]) -> dict[str, Any]:
    value = BASE_BUILD_MANIFEST(wplto, completion)
    plane = value["static_plane"]
    plane.update({
        "status": "passed-v1.4-parity-pilot-single-emitter-static-plane",
        "m65_hw_contract": PREV.bind(M65.CONTRACT),
        "m65_hw_execution": PREV.bind(M65.RECEIPT),
        "ship_fleet": PREV.bind(FLEET),
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
    value["status"] = "passed-v1.4-synchronous-parity-pilot-feature-gates"
    path.write_bytes(PREV.CAN.json_bytes(value))


def main() -> int:
    configure_successor()
    PREV.freight_gates = freight_gates
    PREV.augment_feature_receipt = augment_feature_receipt
    result = PREV.main()
    if result == 0 and len(sys.argv) > 1 and sys.argv[1] == "build":
        print(
            "c2-v1.4.0-link89-candidate-product: FREIGHT PASS "
            "m65=15 cases=24 mutations=9 ship=5 "
            "bank2=47298 resident=+0")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PREV.CandidateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-v1.4.0-link89-candidate-product: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
