#!/usr/bin/env python3
"""One WPLTO for the approved E5-cold/B3-D3-common-store package."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_wplto as BASE  # noqa: E402
import c2_matrix_addenda_wplto_first_red as RED  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-placement-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-capacity-first-red-receipt.json")
CONTRACT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
ORIGINAL_AUTHORITY = BASE.authority
TEXT_NOISE_HEADROOM = 32
E000_FLOOR = 54


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(
        first["status"] == "FIRST RED: two bound resident walls exceeded"
        and first["walls"]["bank0_text"]["deficit_bytes"] == 26
        and first["walls"]["E000"]["deficit_bytes"] == 12
        and contract["capacity"]["bank0_text_noise_floor_bytes"] == 32
        and contract["capacity"]["E000_final_floor_bytes"] == 54
        and contract["E5"]["producer"] ==
            "cold fronts phase immediately after authenticated "
            "transient-front discovery"
        and contract["B3_D3"]["one_truth"] ==
            "physical RUN/STOP and ordinary queue events share one "
            "tuple-store tail",
        "cold-placement authority drift",
    )
    value["capacity_first_red"] = P.bind(FIRST_RED)
    value["cold_placement_contract"] = P.bind(CONTRACT)
    value["cold_placement_driver"] = P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "matrix-addenda cold-placement WPLTO is one-shot",
    )
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
        auth = authority()
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
    current_map = OUT / "resident-island-seed.prg.map"
    historical_map_available = RED.CURRENT_MAP.is_file()
    before_map = RED.CURRENT_MAP if historical_map_available else current_map
    before = RED.map_rows(before_map)
    after = RED.map_rows(current_map)
    gap = after[".lisp65_c2_kernal_window.reopen_gap0"]
    state = after[".lisp65_c2_kernal_window.session_emitter_state"]
    resident = after[".lisp65_c2_kernal_window.c2_resident"]
    resident_end = resident["address"] + resident["bytes"]
    gap_end = gap["address"] + gap["bytes"]
    overlap = max(0, gap_end - state["address"])
    structure_path = OUT / "product-substitution-link.json"
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    require(
        value["status"].startswith("passed")
        and walls["bank0_text_headroom_bytes"] >= TEXT_NOISE_HEADROOM
        and walls["e000_headroom_bytes"] >= E000_FLOOR
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536
        and structure["actual_e000_future_margin_bytes"] ==
            walls["e000_headroom_bytes"]
        and gap["address"] == resident_end
        and gap["bytes"] > 0
        and state["address"] == 0xFD22
        and state["bytes"] == 0
        and overlap == 0,
        "cold-placement simultaneous WPLTO close is red",
    )
    old_text = 6
    old_e000 = 42
    value["format"] = (
        "lisp65-c2-link58-matrix-addenda-cold-placement-wplto-v1")
    value["status"] = (
        "passed-E5-cold-B3-D3-common-store-WPLTO-all-walls-green")
    value["authority"] = auth
    value["cold_placement"] = {
        "E5": {
            "producer":
                "cold reserve phase enters the existing terminal detail seam "
                "with code 63/Fixnum 5 before mutation",
            "consumer":
                "existing abort landing and numeric renderer",
            "resident_special_case_bytes": 0,
        },
        "B3_D3": {
            "tuple_store": "one common .Lstore_event tail",
            "queue_and_IRQ_sources": 2,
            "structural_recovery_required_bytes": 2,
        },
        "measured_recovery_from_first_red": {
            "bank0_text_bytes":
                walls["bank0_text_headroom_bytes"] - old_text,
            "E000_bytes": walls["e000_headroom_bytes"] - old_e000,
        },
        "reopen_gap0_geometry": {
            "start": gap["address"],
            "end_exclusive": gap_end,
            "bytes": gap["bytes"],
            "session_emitter_state_start": state["address"],
            "gap_to_state_headroom_bytes": state["address"] - gap_end,
            "overlap_bytes": overlap,
        },
        "map_delta": {
            "baseline": (
                P.bind(before_map) if historical_map_available else {
                    **P.bind(current_map),
                    "classification":
                        "current-source-clean-build-no-private-baseline",
                }),
            "E000_resident_bytes":
                after[".lisp65_c2_kernal_window.c2_resident"]["bytes"]
                - before[".lisp65_c2_kernal_window.c2_resident"]["bytes"],
            "ordinary_text_bytes":
                after[".text"]["bytes"] - before[".text"]["bytes"],
        },
    }
    value["hard_completion"] = {
        "bank0_text_headroom_bytes": walls["bank0_text_headroom_bytes"],
        "required_text_noise_headroom_bytes": TEXT_NOISE_HEADROOM,
        "e000_headroom_bytes": walls["e000_headroom_bytes"],
        "required_e000_floor_bytes": E000_FLOOR,
        "ordinary_bank0_bss_headroom_bytes":
            walls["ordinary_bank0_bss_headroom_bytes"],
        "fixed_hot_block_headroom_bytes":
            walls["fixed_hot_block_headroom_bytes"],
        "resident_island_headroom_bytes":
            walls["resident_island_headroom_bytes"],
        "session_family_bytes": capacity["session_family_bytes"],
        "session_family_headroom_bytes":
            capacity["session_family_headroom_bytes"],
    }
    value["product_substitution_structure"] = P.bind(structure_path)
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = (
        "Authorized successor product link, then bundled "
        "C1/B3/C3/D3/E5 hardware cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-cold-placement-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"bss={walls['ordinary_bank0_bss_headroom_bytes']} "
        f"fixed={walls['fixed_hot_block_headroom_bytes']} "
        f"island={walls['resident_island_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        f"overlap={overlap}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-cold-placement-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
