#!/usr/bin/env python3
"""Run the one owner-authorized v1.3 forced-inline DEL correction card."""

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
BUILD = ROOT / "build/ship-builder/v13/backspace-inline-wplto"
RECEIPT = EVIDENCE / "c2.3-v1.3-backspace-inline-wplto-receipt.json"
FIRST_RED = EVIDENCE / "c2.3-v1.3-ship-joint-wplto-first-red.json"
PROFILE_RECEIPT = JOINT.PROFILE_RECEIPT
PROFILE = JOINT.PROFILE
INPUT_RECEIPT = JOINT.INPUT_RECEIPT
SCREEN = ROOT / "src/screen.c"
SCREEN_SMOKE = ROOT / "scripts/screen-smoke-main.c"
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
            PROFILE_RECEIPT.is_file() and FIRST_RED.is_file()
            and not BUILD.exists() and not RECEIPT.exists(),
            "forced-inline correction WPLTO is one-shot after the joint First Red",
        )
        screen = SCREEN.read_text(encoding="utf-8")
        require(
            screen.count("SCR_ALWAYS_INLINE void scr_backspace_inline(void)") == 1
            and screen.count("scr_backspace_inline();") == 2
            and "__attribute__((always_inline))" in screen,
            "canonical forced-inline destructive-DEL source shape drift",
        )
        gates = JOINT.host_gates()
        gates["screen_smoke"] = run(["make", "screen-smoke"], "screen smoke")
        input_receipt = load(INPUT_RECEIPT)
        require(
            len(input_receipt["mutations_rejected"]) == 14
            and "screen-del-outlined" in input_receipt["mutations_rejected"]
            and "screen-public-del-diverged" in input_receipt["mutations_rejected"],
            "forced-inline DEL mutation family did not execute",
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

        # Select a fresh output tree and receipt without changing any of the
        # static-plane identities established by the linker-free profile.
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
            "correction-card static-plane identity drift",
        )
        V.EXPECTED_PRODUCT_ID = profile["product_build_id"]
        V.EXPECTED_BANK2_SHA = profile["bank2_static_code"]["sha256"]

        # The sole target-link invocation authorized for this correction card.
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
            "forced-inline correction crossed a closed product wall",
        )

        elf = paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf"
        require(elf.is_file(), "forced-inline correction linked ELF absent")
        FIXED.configure_link60_geometry()
        fixed = FIXED.audit_elf(elf, require_hot_bss=True)
        truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
        require(
            fixed["hot_bss"]["following_noinit"]["bytes"] == 6
            and fixed["hot_bss"]["contract_end_exclusive"] == 0xC354,
            "forced-inline correction did not restore .noinit=6/overlay=$C354",
        )
        require(
            not truth.symbols_by_name.get("scr_backspace_inline"),
            "canonical destructive-DEL helper survived as an outlined ELF symbol",
        )
        screen_symbols = {
            name: [
                {"address": row.value, "bytes": row.bytes, "section": row.section}
                for row in truth.symbols_by_name.get(name, [])
            ]
            for name in ("scr_putc", "scr_backspace", "scr_backspace_inline")
        }

        first_red = load(FIRST_RED)
        old_walls = load(JOINT.PREDECESSOR)["walls"]
        wall_delta = {
            key: walls[key] - old_walls[key]
            for key in (
                "bank0_text_headroom_bytes", "e000_headroom_bytes",
                "fixed_hot_block_headroom_bytes",
                "ordinary_bank0_bss_headroom_bytes",
                "resident_island_headroom_bytes",
            )
        }
        value = {
            "format": "lisp65-c2.3-v1.3-backspace-inline-WPLTO-v1",
            "recorded_on": "2026-08-01",
            "status": "passed-one-forced-inline-destructive-DEL-correction-WPLTO",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "wplto_probes_consumed": 1,
            "correction": {
                "implementation": "one canonical always_inline destructive-DEL body",
                "callers": ["scr_putc/write-char", "public scr_backspace"],
                "padding_bytes": 0,
                "outlined_helper_symbols": 0,
                "compiler_static_stack_noinit_bytes": 6,
                "overlay_min_start": "$C354",
                "screen_symbols": screen_symbols,
            },
            "host_gate_summaries": gates,
            "static_geometry": preflight["geometry"],
            "target_stdlib_header": header_binding,
            "fixed_block_geometry": fixed,
            "walls": walls,
            "wall_headroom_delta_from_link83": wall_delta,
            "capacity": capacity,
            "wplto": linked,
            "authority": {
                "owner_first_red": bind(FIRST_RED),
                "profile_preflight": bind(PROFILE_RECEIPT),
                "input_wait_receipt": bind(INPUT_RECEIPT),
                "input_wait_contract": bind(JOINT.INPUT.CONTRACT),
                "screen_driver": bind(SCREEN),
                "screen_smoke": bind(SCREEN_SMOKE),
                "profile": bind(PROFILE),
                "static_product": bind(product_path),
                "linked_ELF": bind(elf),
                "driver": bind(DRIVER),
            },
            "first_red_closed": {
                "prior_diagnostic": first_red["linker_diagnostic"],
                "mechanism": first_red["attribution"]["mechanism"],
                "closure": "forced inline; exact inherited geometry restored without padding",
            },
            "next_gate": "Extended v1.3 freight Halt #1 before a successor product link.",
            "claim_limit": (
                "One non-promotable correction WPLTO; no successor product "
                "identity, hardware, acceptance or release claim."),
        }
        RECEIPT.write_bytes(CAN.json_bytes(value))
        print(
            "c2-v13-backspace-inline-wplto: PASS "
            f"noinit=6 overlay=C354 text={walls['bank0_text_headroom_bytes']} "
            f"e000={walls['e000_headroom_bytes']} "
            f"session={capacity['session_family_headroom_bytes']} links=0")
        return 0
    except (CardError, KeyError, OSError, ValueError) as error:
        print(f"c2-v13-backspace-inline-wplto: FIRST RED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
