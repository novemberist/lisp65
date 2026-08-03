#!/usr/bin/env python3
"""Run the one owner-authorized v1.3 explicit non-LTO screen card."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_fixed_block_leaf_gate as FIXED  # noqa: E402
import c2_v13_ship_freight_wplto as JOINT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


CAN = JOINT.CAN
BASE = JOINT.BASE
V = JOINT.V
PRODUCT = JOINT.PRODUCT
EVIDENCE = JOINT.EVIDENCE
BUILD = ROOT / "build/ship-builder/v13/screen-nonlto-wplto"
RECEIPT = EVIDENCE / "c2.3-v1.3-screen-nonlto-wplto-receipt.json"
PROFILE_RECEIPT = JOINT.PROFILE_RECEIPT
PROFILE = JOINT.PROFILE
INPUT_RECEIPT = JOINT.INPUT_RECEIPT
FIRST_RED_INLINE = EVIDENCE / "c2.3-v1.3-backspace-inline-wplto-first-red.json"
FIRST_RED_OUTLINED = EVIDENCE / "c2.3-v1.3-ship-joint-wplto-first-red.json"
OWNER_REVIEW = ROOT / "docs/planning/1.3-ship-builder-extended-halt1-review.md"
SCREEN = ROOT / "src/screen.c"
LEAF_SOURCE = ROOT / "src/screen_backspace_nonlto.s"
PRODUCT_LINK = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
SHIP_BUILDER = ROOT / "tools/host-lisp/ship_builder.py"
FLEET_RECEIPT = ROOT / "build/ship-builder/v1-fleet-final/fleet-receipt.json"
DRIVER = Path(__file__).resolve()
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"


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


def bind(path: Path) -> dict[str, Any]:
    return CAN.bind(path)


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip().splitlines()[-1]


def main() -> int:
    try:
        require(
            PROFILE_RECEIPT.is_file() and FIRST_RED_INLINE.is_file()
            and FIRST_RED_OUTLINED.is_file() and not BUILD.exists()
            and not RECEIPT.exists(),
            "explicit non-LTO screen WPLTO is one-shot after both source-shape First Reds",
        )
        input_summary = run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "input/wait/non-LTO gate")
        screen_summary = run(["make", "screen-smoke"], "screen smoke")
        fleet_summary = run(
            ["make", "ship-builder-sample-fleet-check"], "Ship fleet")
        input_receipt = load(INPUT_RECEIPT)
        require(
            len(input_receipt["mutations_rejected"]) == 17
            and input_receipt["target_leaf"]["bytes"] == 105
            and input_receipt["target_leaf"]["status"]
                == "passed-named-sized-native-leaf",
            "non-LTO DEL host/object gate drift",
        )
        fleet = load(FLEET_RECEIPT)
        require(
            fleet["sample_count"] == 4
            and fleet["host_executions"] == 4
            and fleet["media_members_verified"] == 36,
            "four-sample Ship fleet drift",
        )

        preflight = load(PROFILE_RECEIPT)
        profile = load(PROFILE)
        require(
            preflight["status"] == "passed-v1.3-joint-linker-free-profile"
            and profile["bank2_static_code"]["bytes"] == JOINT.EXPECTED_STATIC
            and profile["bank2_static_code"]["sha256"]
                == preflight["geometry"]["bank2_sha256"],
            "joint linker-free profile authority drift",
        )

        JOINT.RECEIPT = RECEIPT
        JOINT.DRIVER = DRIVER
        paths = JOINT.configure(BUILD)
        static = BASE.PROBE.REQ.build_static_plane()
        plane = BASE.PROBE.REQ.F1W.static_gate()
        header_binding = PRODUCT.bind_generated_stdlib_header(paths)
        product_path = paths["static_product"] / "substitution-artifacts.json"
        product = load(product_path)
        require(
            static["semantics"]["code_bytes"] == JOINT.EXPECTED_STATIC
            and plane["static_code_bytes"] == JOINT.EXPECTED_STATIC
            and product["entries"] == JOINT.EXPECTED_ENTRIES
            and product["resolutions"] == JOINT.EXPECTED_RESOLUTIONS
            and product["roots"] == JOINT.EXPECTED_ROOTS
            and product["product_build_id_hex"] == profile["product_build_id"],
            "non-LTO card static-plane identity drift",
        )
        V.EXPECTED_PRODUCT_ID = profile["product_build_id"]
        V.EXPECTED_BANK2_SHA = profile["bank2_static_code"]["sha256"]

        # Sole target-link invocation authorized for the explicit-boundary card.
        linked = CAN.run_wplto()
        replacement = linked["historical_checker_boundary"][
            "current_replacement_gates"]
        walls = replacement["walls"]
        capacity = replacement["capacity"]
        require(
            walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_headroom_bytes"] >= 0,
            "non-LTO screen card crossed a closed product wall",
        )

        elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
        require(elf.is_file(), "non-LTO screen linked ELF absent")
        FIXED.configure_link60_geometry()
        fixed = FIXED.audit_elf(elf, require_hot_bss=True)
        truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
        require(
            fixed["hot_bss"]["following_noinit"]["bytes"] == 6
            and fixed["hot_bss"]["contract_end_exclusive"] == 0xC354,
            "explicit boundary did not restore .noinit=6/overlay=$C354",
        )
        leaf = truth.symbol("scr_backspace")
        caller = truth.symbol("scr_putc")
        calls = [
            row for row in truth.relocations
            if row.source_section_index == caller.section_index
            and caller.value <= row.offset < caller.value + caller.bytes
            and row.target == "scr_backspace" and row.addend == 0
            and row.relocation_type == "R_MOS_ADDR16"
        ]
        state_targets = {
            "lisp65_screen_base", "lisp65_screen_cols", "lisp65_screen_row",
            "lisp65_screen_col", "lisp65_screen_cursor_on",
        }
        leaf_relocations = [
            row for row in truth.relocations
            if row.source_section_index == leaf.section_index
            and leaf.value <= row.offset < leaf.value + leaf.bytes
        ]
        require(
            leaf.symbol_type == "Function"
            and leaf.section == ".text.scr_backspace"
            and leaf.bytes == 105
            and len(calls) == 1
            and state_targets <= {row.target for row in leaf_relocations},
            "linked non-LTO DEL identity/call/dataflow drift",
        )

        value = {
            "format": "lisp65-c2.3-v1.3-screen-nonlto-WPLTO-v1",
            "recorded_on": "2026-08-01",
            "status": "passed-one-explicit-screen-nonlto-boundary-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "wplto_probes_consumed": 1,
            "host_gate_summaries": {
                "input_wait_nonlto": input_summary,
                "screen_smoke": screen_summary,
                "ship_fleet": fleet_summary,
            },
            "correction": {
                "implementation": "one separately assembled zero-argument target leaf",
                "leaf": {
                    "name": leaf.name,
                    "section": leaf.section,
                    "address": leaf.value,
                    "bytes": leaf.bytes,
                    "state_targets": sorted(state_targets),
                },
                "scr_putc_call_relocations": len(calls),
                "compiler_static_stack_noinit_bytes": 6,
                "overlay_min_start": "$C354",
                "padding_bytes": 0,
                "workbench_and_ship_identity": "scr_backspace",
            },
            "static_geometry": preflight["geometry"],
            "target_stdlib_header": header_binding,
            "fixed_block_geometry": fixed,
            "walls": walls,
            "capacity": capacity,
            "wplto": linked,
            "authority": {
                "owner_review": bind(OWNER_REVIEW),
                "outlined_first_red": bind(FIRST_RED_OUTLINED),
                "inline_first_red": bind(FIRST_RED_INLINE),
                "profile_preflight": bind(PROFILE_RECEIPT),
                "input_wait_receipt": bind(INPUT_RECEIPT),
                "ship_fleet_receipt": bind(FLEET_RECEIPT),
                "screen_driver": bind(SCREEN),
                "nonlto_leaf": bind(LEAF_SOURCE),
                "product_link_driver": bind(PRODUCT_LINK),
                "ship_builder": bind(SHIP_BUILDER),
                "profile": bind(PROFILE),
                "static_product": bind(product_path),
                "linked_ELF": bind(elf),
                "driver": bind(DRIVER),
            },
            "next_gate": "Extended v1.3 Halt #1 before the successor product link.",
            "claim_limit": (
                "One non-promotable explicit-boundary WPLTO; no successor "
                "product identity, hardware, acceptance or release claim."),
        }
        RECEIPT.write_bytes(CAN.json_bytes(value))
        print(
            "c2-v13-screen-nonlto-wplto: PASS "
            f"leaf={leaf.bytes} noinit=6 overlay=C354 "
            f"text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']} links=0")
        return 0
    except (CardError, KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"c2-v13-screen-nonlto-wplto: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
