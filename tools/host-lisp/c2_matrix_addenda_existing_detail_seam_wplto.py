#!/usr/bin/env python3
"""One WPLTO after E5 reuses the existing terminal detail seam."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_cold_placement_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-existing-detail-seam-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-existing-detail-seam-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-existing-detail-seam-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-existing-detail-seam-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-first-red-receipt.json")
ORIGINAL_AUTHORITY = BASE.authority


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    BASE.require(
        first["status"] ==
            "FIRST RED: cold placement closes text but not E000/session"
        and first["walls"]["bank0_text"]["headroom_bytes"] == 33
        and first["walls"]["E000"]["deficit_bytes"] == 24
        and first["walls"]["session_family"]["deficit_bytes"] == 414,
        "existing-detail-seam First-Red authority drift",
    )
    value["cold_status_helper_first_red"] = BASE.P.bind(FIRST_RED)
    value["existing_detail_seam_amendment"] = {
        "status_cells": ["pending_code", "pending_symbol"],
        "constant_values": [63, "Fixnum 5"],
        "abort_landing": "lisp_abort_jump",
        "new_helpers": 0,
        "new_state_bytes": 0,
    }
    value["amended_driver"] = BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    BASE.require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "existing-detail-seam WPLTO is one-shot",
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
    value["format"] = (
        "lisp65-c2-link58-matrix-addenda-existing-detail-seam-wplto-v1")
    value["status"] = (
        "passed-E5-existing-detail-seam-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["E5_existing_detail_seam"] = {
        "producer": "two direct constant stores before mutation",
        "code": 63,
        "detail": "Fixnum 5",
        "terminal_cells": ["pending_code", "pending_symbol"],
        "safe_boundary": "existing lisp_abort_jump",
        "retired_helpers": [
            "lisp65_error_defer",
            "lisp65_error_raise_pending",
        ],
        "new_state_bytes": 0,
    }
    value["next_gate"] = (
        "Authorized successor product link, then bundled "
        "C1/B3/C3/D3/E5 hardware cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print("c2-matrix-addenda-existing-detail-seam-wplto: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-existing-detail-seam-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
