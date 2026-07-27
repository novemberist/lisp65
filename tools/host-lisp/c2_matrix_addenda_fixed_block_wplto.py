#!/usr/bin/env python3
"""One WPLTO for the owner-approved Link-58 fixed-block relocation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_fixed_block_leaf_gate as FIXED_GATE  # noqa: E402
import c2_matrix_addenda_terminal_noreturn_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-fixed-block-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-fixed-block-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-text-capacity-first-red-"
    "receipt.json")
GEOMETRY_CORRECTION = EVIDENCE / (
    "c2.2-link58-fixed-block-geometry-correction-receipt.json")
CONTRACT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
KERNAL_CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY_CORRECTION.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    kernal = json.loads(KERNAL_CONTRACT.read_text(encoding="utf-8"))
    move = contract["capacity"]["fixed_block_relocation"]
    current = kernal["link58_fixed_block_rtov_fail_relocation_2026_07_23"]
    require(
        first["status"].startswith(
            "FIRST RED: E5 cold-front placement closes Session and E000")
        and first["walls"]["bank0_text"]["measured_headroom_bytes"] == 12
        and first["walls"]["bank0_text"]["deficit_bytes"] == 20
        and first["walls"]["fixed_hot_block"]["headroom_bytes"] == 33
        and geometry["status"] ==
            "corrected-before-successor-WPLTO-six-byte-noinit-and-aligned-floor"
        and geometry["correction"]["selected_tenant"]["symbol"] ==
            "rtov_fail"
        and geometry["correction"]["selected_tenant"][
            "projected_fixed_headroom_bytes"] == 4
        and move["status"] == "owner-approved-one-relocation"
        and move["candidate"] == "rtov_fail"
        and move["ordinary_text_credit_bytes"] == 21
        and move["projected_headroom_bytes"] == 4
        and current["capacity"]["fixed_code_bytes"] == 66
        and current["capacity"]["fixed_block_headroom_bytes"] == 4,
        "fixed-block relocation authority drift")
    mutations = FIXED_GATE.selftest()
    require(
        set(mutations) == {
            "wrong-address", "wrong-size", "wrong-section",
            "added-code-edge"},
        "fixed-block relocation mutation set drift")
    value["fixed_block_text_first_red"] = BASE.BASE.BASE.P.bind(FIRST_RED)
    value["fixed_block_geometry_correction"] = (
        BASE.BASE.BASE.P.bind(GEOMETRY_CORRECTION))
    value["fixed_block_relocation_contract"] = BASE.BASE.BASE.P.bind(CONTRACT)
    value["kernal_fixed_block_current_authority"] = (
        BASE.BASE.BASE.P.bind(KERNAL_CONTRACT))
    value["fixed_block_gate_mutations"] = mutations
    value["driver"] = BASE.BASE.BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "fixed-block WPLTO is one-shot")
    old = {
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
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.BASE_RECEIPT = old["base_receipt"]
        BASE.RECEIPT = old["receipt"]
        BASE.authority = old["authority"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    walls = value["walls"]
    capacity = value["capacity"]
    fixed_path = OUT / "fixed-block-rtov-fail-final.json"
    fixed = json.loads(fixed_path.read_text(encoding="utf-8"))
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] == 2
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536
        and fixed["status"] ==
            "passed-fixed-block-rtov-fail-identity-and-fixed-target"
        and fixed["fixed_code"] == {
            "address": 0xC218, "bytes": 69, "end_exclusive": 0xC25D}
        and fixed["leaf"]["address"] == 0xC245
        and fixed["leaf"]["bytes"] == 24
        and [row["target"] for row in
             fixed["leaf"]["outgoing_control_edges"]] ==
            ["rtov_wipe"]
        and fixed["hot_bss"]["address"] == 0xC25D
        and fixed["hot_bss"]["end_exclusive"] == 0xC34D
        and fixed["hot_bss"]["contract_end_exclusive"] == 0xC354
        and fixed["hot_bss"]["following_noinit"] == {
            "address": 0xC34D, "bytes": 6, "end_exclusive": 0xC353}
        and fixed["hot_bss"]["headroom_to_overlay_bytes"] == 2,
        "fixed-block WPLTO simultaneous close is red")
    value["format"] = (
        "lisp65-c2-link58-matrix-addenda-fixed-block-WPLTO-v1")
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-fixed-block-relocation-WPLTO-all-walls-and-gates-green")
    value["authority"] = authority()
    value["fixed_block_relocation"] = {
        "ordinary_text_before_headroom_bytes": 12,
        "ordinary_text_after_headroom_bytes":
            walls["bank0_text_headroom_bytes"],
        "required_text_noise_headroom_bytes": 32,
        "moved_symbol": fixed["leaf"],
        "fixed_code": fixed["fixed_code"],
        "hot_bss": fixed["hot_bss"],
        "runtime_overlay_vma": 0xC356,
    }
    value["fixed_block_gate"] = BASE.BASE.BASE.P.bind(fixed_path)
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = (
        "owner-authorized Link 58, then bundled C1 Freezer cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-fixed-block-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"island={walls['resident_island_headroom_bytes']} "
        f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-fixed-block-wplto: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
