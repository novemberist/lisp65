#!/usr/bin/env python3
"""Bind the v1.3 Bank-2 Lisp read-line card without a new native seam."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_ship_freight_wplto as JOINT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/ship-builder/v13/bank2-read-line-product-shaped-wplto"
PREFLIGHT = ROOT / "build/ship-builder/v13/bank2-read-line-profile-preflight"
RECEIPT = EVIDENCE / "c2.3-v1.3-bank2-read-line-wplto-receipt.json"
PROFILE_RECEIPT = EVIDENCE / "c2.3-v1.3-bank2-read-line-profile-receipt.json"
EXPECTED_STATIC = 45514
EXPECTED_ENTRIES = 757
EXPECTED_RESOLUTIONS = 2947
EXPECTED_ROOTS = 350
EXPECTED_DIRECT_REFS = 710


def freight_delta() -> dict[str, int]:
    old = JOINT.load(JOINT.BASELINE_STDLIB)
    new = JOINT.load(JOINT.INPUT_MANIFEST)
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
        "bank2_code_bytes": 451,
        "entries": 7,
        "resolution_words": 16,
        "stdlib_kind4_literal_nodes": 14,
        "direct_entry_refs": 0,
        "roots": 0,
    }
    JOINT.require(value == expected, f"Bank-2 read-line delta drift: {value}")
    return value


def configure() -> None:
    JOINT.BUILD = BUILD
    JOINT.PREFLIGHT = PREFLIGHT
    JOINT.RECEIPT = RECEIPT
    JOINT.PROFILE_RECEIPT = PROFILE_RECEIPT
    JOINT.EXPECTED_STATIC = EXPECTED_STATIC
    JOINT.EXPECTED_ENTRIES = EXPECTED_ENTRIES
    JOINT.EXPECTED_RESOLUTIONS = EXPECTED_RESOLUTIONS
    JOINT.EXPECTED_ROOTS = EXPECTED_ROOTS
    JOINT.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    JOINT.DRIVER = Path(__file__).resolve()
    JOINT.freight_delta = freight_delta


def annotate(path: Path, phase: str) -> None:
    value: dict[str, Any] = JOINT.load(path)
    value["authority"]["driver"] = JOINT.bind(Path(__file__).resolve())
    value["bank2_read_line_disposition"] = {
        "phase": phase,
        "native_screen_driver_delta_bytes": 0,
        "native_del_leaf_linked": False,
        "lisp_allocation_max_cells_per_key": 4,
        "reason": (
            "read-line owns its last-row viewport entirely in Bank-2 Lisp; "
            "the pre-freight C screen driver is restored and the historical "
            "105-byte leaf remains unlinked shelf evidence"
        ),
    }
    if phase == "wplto":
        facade = JOINT.load(
            BUILD / "wplto/fixed-host-facade-final.json")
        fixed = facade["fixed_state_contract"]["bank0_hot_bss"]
        noinit_bytes = fixed["following_noinit_bytes"]
        noinit_address = fixed["end_exclusive"]
        overlay_floor = (noinit_address + noinit_bytes + 1) & ~1
        JOINT.require(
            noinit_address == 0xC34D
            and noinit_bytes == 6
            and overlay_floor == 0xC354,
            "Bank-2 read-line did not restore inherited noinit/overlay geometry",
        )
        value["inherited_native_geometry"] = {
            "noinit_address": f"0x{noinit_address:04x}",
            "noinit_bytes": noinit_bytes,
            "overlay_floor": f"0x{overlay_floor:04x}",
            "fixed_host_facade": JOINT.bind(
                BUILD / "wplto/fixed-host-facade-final.json"),
            "status": "restored-exactly",
        }
    value["next_gate"] = (
        "Link 84 successor and the already commissioned quiet closing session"
        if phase == "wplto" else "one ordinary product-shaped WPLTO"
    )
    path.write_bytes(JOINT.CAN.json_bytes(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("profile", "wplto"))
    args = parser.parse_args()
    configure()
    result = JOINT.profile() if args.phase == "profile" else JOINT.wplto()
    if result == 0:
        annotate(PROFILE_RECEIPT if args.phase == "profile" else RECEIPT, args.phase)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
