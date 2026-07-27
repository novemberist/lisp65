#!/usr/bin/env python3
"""Bind the rejected direct-pending-cell E5 WPLTO without another link."""

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
    "link58-matrix-addenda-existing-detail-seam-wplto-replay")
CURRENT_MAP = CURRENT / "resident-island-seed.prg.map"
CURRENT_LTO = CURRENT / "resident-island-seed.prg.lto.o"
ATTEMPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-existing-detail-seam-wplto-replay-receipt.json")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-existing-detail-seam-wplto-replay-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-direct-pending-first-red-receipt.json")


def main() -> int:
    D.require(not RECEIPT.exists(), "direct-pending First Red is one-shot")
    rows = D.map_rows(CURRENT_MAP)
    symbols = D.symbols(CURRENT_LTO)
    text = rows[".text"]
    gap = rows[".lisp65_c2_kernal_window.reopen_gap0"]
    state = rows[".lisp65_c2_kernal_window.session_emitter_state"]
    text_headroom = 0xB4A3 - text["address"] - text["bytes"]
    overlap = max(0, gap["address"] + gap["bytes"] - state["address"])
    phase = symbols["c2_append_reserve_transient_bounds_phase"]
    session = 65438 + (((phase + 255) // 256) * 256 - 1024)
    D.require(
        text_headroom == 33 and gap["address"] == 0xFCA5
        and overlap == 3 and phase == 1268 and session == 65694,
        "direct-pending attribution drift",
    )
    value = {
        "format": "lisp65-c2.2-matrix-addenda-direct-pending-first-red-v1",
        "recorded_on": "2026-07-23",
        "status":
            "FIRST RED: direct terminal-cell access bloats cold E5 slice",
        "promotable": False,
        "authority": {
            "attempt_receipt": D.bind(ATTEMPT),
            "internal_receipt": D.bind(INTERNAL),
            "map": D.bind(CURRENT_MAP),
            "LTO_object": D.bind(CURRENT_LTO),
            "driver": D.bind(Path(__file__)),
        },
        "walls": {
            "bank0_text": {"headroom_bytes": 33, "required_bytes": 32,
                           "verdict": "green"},
            "E000": {"headroom_bytes": 51, "required_bytes": 54,
                     "deficit_bytes": 3, "overlap_bytes": overlap,
                     "verdict": "red"},
            "session_family": {"bytes": session, "limit_bytes": 65536,
                               "deficit_bytes": session - 65536,
                               "verdict": "red"},
        },
        "attribution": {
            "cold_phase_bytes": phase,
            "cold_phase_baseline_bytes": 977,
            "cold_phase_delta_bytes": phase - 977,
            "cause":
                "overlay directly addressed terminal pending_code/pending_symbol",
            "correction":
                "use existing append.error plus obj-result VM detail seam",
        },
        "execution_accounting": {
            "whole_program_LTO_attempts": 1,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "rollback_line": "Link 57 remains untouched",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-direct-pending-first-red: "
        "TEXT=33/32 E000=51/54 SESSION=65694/65536")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D.DiagnosisError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-direct-pending-first-red: FAIL: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
