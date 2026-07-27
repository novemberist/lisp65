#!/usr/bin/env python3
"""One WPLTO for E5 over the existing VM status-plus-obj detail seam."""

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
    "build/c2.2/substitution/link58-matrix-addenda-vm-detail-seam-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-receipt.json")
HELPER_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-placement-wplto-first-red-receipt.json")
DIRECT_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-direct-pending-first-red-receipt.json")
ORIGINAL_AUTHORITY = BASE.authority


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    helper = json.loads(HELPER_RED.read_text(encoding="utf-8"))
    direct = json.loads(DIRECT_RED.read_text(encoding="utf-8"))
    BASE.require(
        helper["status"] ==
            "FIRST RED: cold placement closes text but not E000/session"
        and direct["status"] ==
            "FIRST RED: direct terminal-cell access bloats cold E5 slice"
        and direct["walls"]["E000"]["deficit_bytes"] == 3
        and direct["walls"]["session_family"]["deficit_bytes"] == 158,
        "VM-detail-seam authority drift",
    )
    value["generic_defer_helper_first_red"] = BASE.P.bind(HELPER_RED)
    value["direct_terminal_cell_first_red"] = BASE.P.bind(DIRECT_RED)
    value["VM_detail_seam"] = {
        "producer_status_cell": "c2_append_state.append.error",
        "producer_detail_cell": "c2_append_state.main_ordinal output",
        "terminal_status": "vm_status",
        "terminal_detail": "ordinary obj result",
        "consumer": "vm_check_status",
        "constants": [63, "Fixnum 5"],
        "new_helpers": 0,
        "new_state_bytes": 0,
    }
    value["driver"] = BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    BASE.require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "VM-detail-seam WPLTO is one-shot",
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
        "lisp65-c2-link58-matrix-addenda-vm-detail-seam-wplto-v1")
    value["status"] = "passed-E5-VM-detail-seam-WPLTO-all-walls-green"
    value["authority"] = authority()
    value["E5_VM_detail_seam"] = authority()["VM_detail_seam"]
    value["next_gate"] = (
        "Authorized successor product link, then bundled "
        "C1/B3/C3/D3/E5 hardware cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print("c2-matrix-addenda-vm-detail-seam-wplto: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-vm-detail-seam-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
