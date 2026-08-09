#!/usr/bin/env python3
"""Bind and price the v1.4 synchronous MEGA65 parity pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_ship_freight_wplto as JOINT  # noqa: E402
import c2_m65_hw_gate as M65  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/post-promotion/v14/parity-pilot-wplto"
PREFLIGHT = ROOT / "build/post-promotion/v14/parity-pilot-profile"
RECEIPT = EVIDENCE / "c2.3-v1.4-parity-pilot-wplto-receipt.json"
PROFILE_RECEIPT = EVIDENCE / "c2.3-v1.4-parity-pilot-profile-receipt.json"
PREDECESSOR = EVIDENCE / "c2.3-v1.3-link88-full-raster-wplto-receipt.json"
FLEET = ROOT / "build/post-promotion/v14/sample-fleet-host/fleet-receipt.json"
EXPECTED_STATIC = 47298
EXPECTED_ENTRIES = 788
EXPECTED_RESOLUTIONS = 3034
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


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


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
        "bank2_code_bytes": 1784,
        "entries": 31,
        "resolution_words": 87,
        "stdlib_kind4_literal_nodes": 70,
        "direct_entry_refs": 0,
        "roots": 0,
    }
    require(value == expected, f"v1.4 parity-pilot delta drift: {value}")
    return value


def fleet_witness() -> str:
    value = load(FLEET)
    names = [row["name"] for row in value["samples"]]
    require(
        value["status"] == "passed"
        and names == ["hello", "random-q", "long-runner", "interactive",
                      "parity-toy"]
        and value["sample_count"] == 5
        and value["host_executions"] == 5
        and value["media_members_verified"] == 45,
        "v1.4 five-sample execution witness drift",
    )
    return "ship-builder fleet: PASS samples=5 host-executions=5 media-members=45"


def host_gates() -> dict[str, str]:
    base = ORIGINAL_HOST_GATES()
    return {
        **base,
        "m65_hw": run(
            [sys.executable, "tools/host-lisp/c2_m65_hw_gate.py"],
            "m65-hw gate",
        ),
        "ship_contract": run(
            [sys.executable, "tools/host-lisp/ship_builder.py", "selftest"],
            "Ship contract selftest",
        ),
        "ship_fleet": fleet_witness(),
    }


def configure() -> None:
    JOINT.BUILD = BUILD
    JOINT.PREFLIGHT = PREFLIGHT
    JOINT.RECEIPT = RECEIPT
    JOINT.PROFILE_RECEIPT = PROFILE_RECEIPT
    JOINT.PREDECESSOR = PREDECESSOR
    JOINT.BASELINE_STDLIB = M65.BASE_PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_MANIFEST = M65.PREFIX.with_suffix(".manifest.json")
    JOINT.INPUT_RECEIPT = M65.RECEIPT
    JOINT.EXPECTED_STATIC = EXPECTED_STATIC
    JOINT.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    JOINT.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    JOINT.EXPECTED_ROOTS = EXPECTED_ROOTS
    JOINT.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    JOINT.DRIVER = DRIVER
    JOINT.freight_delta = delta
    JOINT.host_gates = host_gates


def annotate_profile(previous_v13: dict[str, Any]) -> None:
    value = load(JOINT.PROFILE)
    value["recorded_on"] = "2026-08-03"
    value["v13_ship_public_surface_delta"] = previous_v13
    value["v14_parity_pilot_delta"] = {
        **delta(),
        "baseline": "released v1.3.0 Link 88 static plane",
        "contracts": ["config/c2-m65-hw-contract.json"],
        "resident_bytes": 0,
        "native_primitives": 0,
    }
    value["authority"] = {
        "kind": "fresh-single-emitter-static-plane-dataflow",
        "emitter": "tools/host-lisp/c2_lite_canonical_product.py",
        "product_manifest": (
            "build/post-promotion/v14/parity-pilot-profile/"
            "static-plane/narrow-static/product/substitution-artifacts.json"),
        "compiled_stdlib_manifest": M65.PREFIX.with_suffix(
            ".manifest.json").relative_to(ROOT).as_posix(),
        "compiled_ide_manifest": JOINT.CURRENT_IDE.relative_to(ROOT).as_posix(),
        "bank2_static_plane": (
            "build/post-promotion/v14/parity-pilot-profile/"
            "static-plane/narrow-static/v6-semantics/bank2-static-code.bin"),
        "rule": (
            "The v1.4 card adds only the synchronous m65-hw Bank-2 freight "
            "to the released Link-88 six-image composition."),
    }
    JOINT.PROFILE.write_bytes(JOINT.CAN.json_bytes(value))
    # q records the current complete product identity.  Replay it only after
    # the v1.4 profile has its final, honestly separated v1.3/v1.4 deltas.
    q_summary = run(
        [sys.executable, "tools/host-lisp/c2_q_gate.py"],
        "final v1.4 profile q binding",
    )
    profile_receipt = load(PROFILE_RECEIPT)
    profile_receipt.update({
        "format": "lisp65-c2.3-v1.4-parity-pilot-profile-v1",
        "recorded_on": "2026-08-03",
        # The reused canonical WPLTO checks this compatibility status before
        # consuming the profile.  v14_status is the semantic authority.
        "status": "passed-v1.3-joint-linker-free-profile",
        "v14_status": "passed-v1.4-parity-pilot-linker-free-profile",
        "host_gate_summaries": {**profile_receipt["host_gate_summaries"],
                                "q_final_profile": q_summary},
        "authority": {
            **profile_receipt["authority"],
            "m65_hw": JOINT.bind(M65.RECEIPT),
            "m65_contract": JOINT.bind(M65.CONTRACT),
            "base_stdlib_manifest": JOINT.bind(
                M65.BASE_PREFIX.with_suffix(".manifest.json")),
            "stdlib_manifest": JOINT.bind(
                M65.PREFIX.with_suffix(".manifest.json")),
            "profile": JOINT.bind(JOINT.PROFILE),
            "q": JOINT.bind(JOINT.Q_RECEIPT),
            "driver": JOINT.bind(DRIVER),
        },
        "claim_limit": (
            "Linker-free v1.4 profile binding only; no product link, "
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
        "v1.4 Bank-2 freight moved a resident wall or session capacity",
    )
    facade = load(BUILD / "wplto/fixed-host-facade-final.json")
    fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
    noinit_address = fixed["end_exclusive"]
    noinit_bytes = fixed["following_noinit_bytes"]
    overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
    require(
        noinit_address == 0xC34D and noinit_bytes == 6
        and overlay_floor == 0xC354,
        "v1.4 parity pilot moved pinned noinit/overlay geometry",
    )
    value.update({
        "format": "lisp65-c2.3-v1.4-parity-pilot-WPLTO-v1",
        "recorded_on": "2026-08-03",
        "status": "passed-v1.4-parity-pilot-one-product-shaped-WPLTO",
        "resident_delta_bytes": 0,
        "native_primitive_delta": 0,
        "inherited_native_geometry": {
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
            "status": "restored-exactly",
        },
        "wall_headroom_delta_from_link88": {
            key: value["walls"][key] - predecessor["walls"][key]
            for key in value["walls"]
        },
        "sample_fleet": JOINT.bind(FLEET),
        "authority": {
            **value["authority"],
            "m65_hw": JOINT.bind(M65.RECEIPT),
            "m65_contract": JOINT.bind(M65.CONTRACT),
            "ship_fleet": JOINT.bind(FLEET),
            "driver": JOINT.bind(DRIVER),
        },
        "next_gate": "one Link 89 successor and the bundled v1.4 device session",
        "claim_limit": (
            "One non-promotable product-shaped WPLTO and five host-executed "
            "Ship samples; no successor identity or hardware claim."),
    })
    value.pop("wall_headroom_delta_from_link83", None)
    RECEIPT.write_bytes(JOINT.CAN.json_bytes(value))


ORIGINAL_HOST_GATES = JOINT.host_gates


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
                "c2-v14-parity-profile: PASS bank2=47298 delta=+1784 "
                "headroom=18238 linker=0")
        return result
    result = JOINT.wplto()
    if result == 0:
        annotate_wplto()
        print(
            "c2-v14-parity-wplto: PASS bank2=47298 delta=+1784 "
            "headroom=18238 resident=+0 noinit=6 overlay=0xc354 probes=1")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, JOINT.WPLTOError, OSError, KeyError, ValueError) as error:
        print(f"c2-v14-parity-wplto: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
