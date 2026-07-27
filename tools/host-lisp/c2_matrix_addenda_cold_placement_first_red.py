#!/usr/bin/env python3
"""Bind the single cold-placement WPLTO First Red without another link."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_wplto_first_red as D  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CURRENT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-placement-wplto")
CURRENT_MAP = CURRENT / "resident-island-seed.prg.map"
CURRENT_LTO = CURRENT / "resident-island-seed.prg.lto.o"
OLD_MAP = D.CURRENT_MAP
OLD_LTO = D.CURRENT_LTO
PRIOR = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-capacity-first-red-receipt.json")
CONTRACT = ROOT / "config/c2-matrix-addenda-cold-placement-contract.json"
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-first-red-receipt.json")


def main() -> int:
    D.require(not RECEIPT.exists(), "cold-placement First Red is one-shot")
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    before = D.map_rows(OLD_MAP)
    after = D.map_rows(CURRENT_MAP)
    before_symbols = D.symbols(OLD_LTO)
    after_symbols = D.symbols(CURRENT_LTO)
    text_end = after[".text"]["address"] + after[".text"]["bytes"]
    text_headroom = 0xB4A3 - text_end
    gap = after[".lisp65_c2_kernal_window.reopen_gap0"]
    state = after[".lisp65_c2_kernal_window.session_emitter_state"]
    gap_end = gap["address"] + gap["bytes"]
    overlap = max(0, gap_end - state["address"])
    e000_headroom = 54 - (gap["address"] - 0xFCA2)
    phase_before = before_symbols["c2_append_reserve_transient_bounds_phase"]
    phase_after = after_symbols["c2_append_reserve_transient_bounds_phase"]
    phase_pack_before = ((phase_before + 255) // 256) * 256
    phase_pack_after = ((phase_after + 255) // 256) * 256
    session_before = prior["walls"]["session_family"]["bytes"]
    session_after = session_before + phase_pack_after - phase_pack_before
    symbol_delta = {
        name: after_symbols.get(name, 0) - before_symbols.get(name, 0)
        for name in (
            "c2_product_install",
            "c2_append_begin",
            "c2_append_reserve_transient_bounds_phase",
            "lisp65_error_raise_pending",
        )
    }
    D.require(
        prior["status"] == "FIRST RED: two bound resident walls exceeded"
        and text_headroom == 33
        and gap["address"] == 0xFCBA
        and gap["bytes"] == 128
        and state["address"] == 0xFD22
        and overlap == 24
        and e000_headroom == 30
        and before[".lisp65_c2_kernal_window.c2_resident"]["address"]
            - after[".lisp65_c2_kernal_window.c2_resident"]["address"] == 10
        and after[".lisp65_c2_kernal_window.c2_resident"]["bytes"]
            - before[".lisp65_c2_kernal_window.c2_resident"]["bytes"] == 22
        and symbol_delta == {
            "c2_product_install": -24,
            "c2_append_begin": 22,
            "c2_append_reserve_transient_bounds_phase": 308,
            "lisp65_error_raise_pending": 29,
        }
        and phase_pack_before == 1024
        and phase_pack_after == 1536
        and session_after == 65950,
        "cold-placement First-Red attribution drift",
    )
    value = {
        "format":
            "lisp65-c2.2-matrix-addenda-cold-placement-first-red-v1",
        "recorded_on": "2026-07-23",
        "status": "FIRST RED: cold placement closes text but not E000/session",
        "promotable": False,
        "authority": {
            "prior_capacity_first_red": D.bind(PRIOR),
            "cold_placement_contract": D.bind(CONTRACT),
            "current_map": D.bind(CURRENT_MAP),
            "current_LTO_object": D.bind(CURRENT_LTO),
            "prior_map": D.bind(OLD_MAP),
            "prior_LTO_object": D.bind(OLD_LTO),
            "driver": D.bind(Path(__file__)),
        },
        "walls": {
            "bank0_text": {
                "headroom_bytes": text_headroom,
                "required_noise_headroom_bytes": 32,
                "verdict": "green",
            },
            "E000": {
                "headroom_bytes": e000_headroom,
                "required_floor_bytes": 54,
                "deficit_bytes": 54 - e000_headroom,
                "reopen_gap0": "$fcba..$fd39",
                "session_emitter_state": "$fd22..$fd2b",
                "overlap_bytes": overlap,
                "verdict": "red",
            },
            "ordinary_BSS": {"headroom_bytes": 213, "verdict": "green"},
            "fixed_hot_block": {"headroom_bytes": 33, "verdict": "green"},
            "resident_island": {"headroom_bytes": 5, "verdict": "green"},
            "session_family": {
                "projected_bytes_from_measured_WPLTO_symbol_pack": session_after,
                "limit_bytes": 65536,
                "deficit_bytes": session_after - 65536,
                "verdict": "red",
            },
        },
        "attribution": {
            "B3_D3_common_store": {
                "E000_start_recovery_bytes": 10,
                "status": "structural recovery delivered",
            },
            "E5_safe_boundary": {
                "c2_product_install_text_delta_bytes":
                    symbol_delta["c2_product_install"],
                "c2_append_begin_E000_delta_bytes":
                    symbol_delta["c2_append_begin"],
                "lisp65_error_raise_pending_bytes":
                    symbol_delta["lisp65_error_raise_pending"],
            },
            "E5_cold_producer": {
                "transient_bounds_phase_before_bytes": phase_before,
                "transient_bounds_phase_after_bytes": phase_after,
                "delta_bytes":
                    symbol_delta["c2_append_reserve_transient_bounds_phase"],
                "pack_before_bytes": phase_pack_before,
                "pack_after_bytes": phase_pack_after,
                "session_aggregate_delta_bytes":
                    phase_pack_after - phase_pack_before,
            },
            "net": {
                "ordinary_text_headroom_change_bytes": text_headroom - 6,
                "E000_headroom_change_bytes": e000_headroom - 42,
            },
        },
        "execution_accounting": {
            "whole_program_LTO_attempts": 1,
            "successful_product_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "stop_rule": (
            "First Red: stop before the authorized successor product link "
            "and all bundled Freezer hardware cutpoints."),
        "rollback_line": "Link 57 remains untouched",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-cold-placement-first-red: "
        f"TEXT={text_headroom}/32 E000={e000_headroom}/54 "
        f"overlap={overlap} SESSION={session_after}/65536")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D.DiagnosisError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-cold-placement-first-red: FAIL: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
