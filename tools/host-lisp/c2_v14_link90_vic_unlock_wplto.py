#!/usr/bin/env python3
"""Fresh profile and one WPLTO for the v1.4 VIC-unlock edge fix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v14_parity_pilot_wplto as BASE  # noqa: E402


JOINT = BASE.JOINT
M65 = BASE.M65
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v14/link90-vic-unlock-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v14/link90-vic-unlock-profile"
RECEIPT = EVIDENCE / "c2.3-v1.4-link90-vic-unlock-wplto-receipt.json"
PROFILE_RECEIPT = EVIDENCE / (
    "c2.3-v1.4-link90-vic-unlock-profile-receipt.json")
PREDECESSOR = EVIDENCE / "c2.3-v1.4-parity-pilot-wplto-receipt.json"
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
DRIVER = Path(__file__).resolve()


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def delta() -> dict[str, int]:
    old = load(M65.BASE_PREFIX.with_suffix(".manifest.json"))
    new = load(M65.PREFIX.with_suffix(".manifest.json"))
    value = {
        "bank2_code_bytes": new["code_bytes"] - old["code_bytes"],
        "entries": len(new["entries"]) - len(old["entries"]),
        "resolution_words": (
            len(new["literal_patches"]) - len(old["literal_patches"])),
        "stdlib_kind4_literal_nodes": (
            sum(row["kind"] == 4 for row in new["literal_nodes"])
            - sum(row["kind"] == 4 for row in old["literal_nodes"])
        ),
        "direct_entry_refs": 0,
        "roots": 0,
    }
    expected = {
        "bank2_code_bytes": 1768,
        "entries": 30,
        "resolution_words": 84,
        "stdlib_kind4_literal_nodes": 68,
        "direct_entry_refs": 0,
        "roots": 0,
    }
    require(value == expected, f"Link-90 VIC-unlock delta drift: {value}")
    return value


def fleet_witness() -> str:
    fleet = load(FLEET)
    toy = load(FIXED_TOY)
    require(
        fleet["status"] == "passed"
        and fleet["sample_count"] == fleet["host_executions"] == 5
        and fleet["media_members_verified"] == 45,
        "released five-sample fleet witness drift",
    )
    require(
        toy["status"] == "passed"
        and toy["executions"] == 1
        and toy["verification"]["members_verified"] == 9
        and toy["image"]["sha256"]
            == "640d115e01d238413821ab9cf5b59056abf553e96e27cf0c64d8db75ef8a2bde"
        and "status=0 input=1" in toy["host_execution"]["output"],
        "fixed parity-toy execution witness drift",
    )
    return "ship-builder fleet: PASS samples=5 fixed-parity-toy=1 media-members=54"


def host_gates() -> dict[str, str]:
    base = BASE.ORIGINAL_HOST_GATES()
    return {
        **base,
        "m65_hw": BASE.run(
            [sys.executable, "tools/host-lisp/c2_m65_hw_gate.py"],
            "m65-hw gate",
        ),
        "ship_contract": BASE.run(
            [sys.executable, "tools/host-lisp/ship_builder.py", "selftest"],
            "Ship contract selftest",
        ),
        "ship_fleet": fleet_witness(),
    }


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.RECEIPT = RECEIPT
    BASE.PROFILE_RECEIPT = PROFILE_RECEIPT
    BASE.PREDECESSOR = PREDECESSOR
    BASE.FLEET = FLEET
    BASE.EXPECTED_STATIC = EXPECTED_STATIC
    BASE.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    BASE.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    BASE.EXPECTED_ROOTS = EXPECTED_ROOTS
    BASE.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    BASE.DRIVER = DRIVER
    BASE.delta = delta
    BASE.host_gates = host_gates
    BASE.configure()


def annotate_profile(previous_v13: dict[str, Any]) -> None:
    value = load(JOINT.PROFILE)
    value["recorded_on"] = "2026-08-03"
    value["v13_ship_public_surface_delta"] = previous_v13
    value["v14_parity_pilot_delta"] = {
        **delta(),
        "baseline": "released v1.3.0 Link 88 static plane",
        "contracts": ["config/c2-m65-hw-contract.json"],
        "correction": "private-inline VIC-IV unlock pair",
        "resident_bytes": 0,
        "native_primitives": 0,
    }
    value["authority"] = {
        "kind": "fresh-single-emitter-static-plane-dataflow",
        "emitter": "tools/host-lisp/c2_lite_canonical_product.py",
        "product_manifest": (
            "build/post-promotion/v14/link90-vic-unlock-profile/"
            "static-plane/narrow-static/product/substitution-artifacts.json"),
        "compiled_stdlib_manifest": M65.PREFIX.with_suffix(
            ".manifest.json").relative_to(ROOT).as_posix(),
        "compiled_ide_manifest": JOINT.CURRENT_IDE.relative_to(ROOT).as_posix(),
        "bank2_static_plane": (
            "build/post-promotion/v14/link90-vic-unlock-profile/"
            "static-plane/narrow-static/v6-semantics/bank2-static-code.bin"),
        "rule": (
            "The Link-90 profile retains the synchronous v1.4 surface and "
            "replaces the standalone VIC-unlock target edge with its "
            "private-inline form."),
    }
    JOINT.PROFILE.write_bytes(JOINT.CAN.json_bytes(value))
    q_summary = BASE.run(
        [sys.executable, "tools/host-lisp/c2_q_gate.py"],
        "final Link-90 profile q binding",
    )
    profile_receipt = load(PROFILE_RECEIPT)
    profile_receipt.update({
        "format": "lisp65-c2.3-v1.4-link90-vic-unlock-profile-v1",
        "recorded_on": "2026-08-03",
        "status": "passed-v1.3-joint-linker-free-profile",
        "v14_status": "passed-v1.4-link90-vic-unlock-linker-free-profile",
        "host_gate_summaries": {
            **profile_receipt["host_gate_summaries"],
            "q_final_profile": q_summary,
        },
        "authority": {
            **profile_receipt["authority"],
            "attribution": JOINT.bind(ATTRIBUTION),
            "m65_hw": JOINT.bind(M65.RECEIPT),
            "m65_contract": JOINT.bind(M65.CONTRACT),
            "base_stdlib_manifest": JOINT.bind(
                M65.BASE_PREFIX.with_suffix(".manifest.json")),
            "stdlib_manifest": JOINT.bind(
                M65.PREFIX.with_suffix(".manifest.json")),
            "fixed_parity_toy": JOINT.bind(FIXED_TOY),
            "profile": JOINT.bind(JOINT.PROFILE),
            "q": JOINT.bind(JOINT.Q_RECEIPT),
            "driver": JOINT.bind(DRIVER),
        },
        "claim_limit": (
            "Linker-free Link-90 correction profile only; no product link, "
            "hardware or release claim."),
    })
    PROFILE_RECEIPT.write_bytes(JOINT.CAN.json_bytes(profile_receipt))


def annotate_wplto() -> None:
    value = load(RECEIPT)
    predecessor = load(PREDECESSOR)
    require(
        value["static_geometry"]["bank2_static_code_bytes"] == EXPECTED_STATIC
        and value["static_geometry"]["entries"] == EXPECTED_ENTRIES
        and value["static_geometry"]["resolutions"] == EXPECTED_RESOLUTIONS
        and value["walls"] == predecessor["walls"]
        and value["capacity"] == predecessor["capacity"],
        "Link-90 fix moved a resident wall or session capacity",
    )
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(
        noinit_address == 0xC34D and noinit_bytes == 6
        and overlay_floor == 0xC354,
        "Link-90 fix moved pinned noinit/overlay geometry",
    )
    value.update({
        "format": "lisp65-c2.3-v1.4-link90-vic-unlock-WPLTO-v1",
        "recorded_on": "2026-08-03",
        "status": "passed-v1.4-link90-vic-unlock-one-product-shaped-WPLTO",
        "wplto_probes_consumed": 1,
        "resident_delta_bytes": 0,
        "native_primitive_delta": 0,
        "inherited_native_geometry": {
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
            "status": "restored-exactly",
        },
        "wall_headroom_delta_from_link89": {
            key: value["walls"][key] - predecessor["walls"][key]
            for key in value["walls"]
        },
        "authority": {
            **value["authority"],
            "attribution": JOINT.bind(ATTRIBUTION),
            "m65_hw": JOINT.bind(M65.RECEIPT),
            "m65_contract": JOINT.bind(M65.CONTRACT),
            "fixed_parity_toy": JOINT.bind(FIXED_TOY),
            "driver": JOINT.bind(DRIVER),
        },
        "next_gate": "one Link 90 and one autonomous parity-toy target boot",
        "claim_limit": (
            "One non-promotable correction WPLTO and a host-executed fixed "
            "Ship sample; no successor identity or fixed-target claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("profile", "wplto"))
    args = parser.parse_args()
    configure()
    if args.phase == "profile":
        previous = load(JOINT.PROFILE)["v13_ship_public_surface_delta"]
        result = JOINT.profile()
        if result == 0:
            annotate_profile(previous)
            print(
                "c2-v14-link90-vic-unlock-profile: PASS "
                "bank2=47282 delta=+1768 headroom=18254 linker=0")
        return result
    result = JOINT.wplto()
    if result == 0:
        annotate_wplto()
        print(
            "c2-v14-link90-vic-unlock-wplto: PASS bank2=47282 "
            "delta=+1768 headroom=18254 resident=+0 noinit=6 "
            "overlay=0xc354 probes=1")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, BASE.CardError, JOINT.WPLTOError,
            OSError, KeyError, ValueError) as error:
        print(f"c2-v14-link90-vic-unlock-wplto: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
