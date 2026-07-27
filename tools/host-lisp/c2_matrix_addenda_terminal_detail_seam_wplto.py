#!/usr/bin/env python3
"""One WPLTO for E5 on the existing terminal status-plus-detail seam."""

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
    "link58-matrix-addenda-terminal-detail-seam-wplto")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-receipt.json")
VM_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-replay2-internal.json")
VM_STDERR = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-vm-detail-seam-wplto-replay2/"
    "resident-island-seed.prg.link.stderr.txt")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    red = json.loads(VM_RED.read_text(encoding="utf-8"))
    stderr = VM_STDERR.read_text(encoding="utf-8")
    require(
        red["diagnostic"]["message"] ==
            "link command failed before orphan-wrapper acceptance: exit=1"
        and red["execution_accounting"]["product_closure_links"] == 0
        and "ordinary rodata predecessor/VMA/LMA relation drift" in stderr
        and ".text range is [0x2023, 0xB4E0]" in stderr
        and ".lisp65_c2_kernal_handoff range is [0xB4A3, 0xB5C3]"
            in stderr,
        "VM-status translation First Red drift",
    )
    value["VM_status_translation_first_red"] = BASE.P.bind(VM_RED)
    value["VM_status_translation_link_diagnostic"] = BASE.P.bind(VM_STDERR)
    value["approved_miniature_escape"] = {
        "first_red":
            "resident text ended at 0xB4E0 above the 0xB4A3 handoff",
        "replacement":
            "cold transient reserve calls the existing terminal "
            "lisp_abort_detail seam before mutation",
        "removed":
            "E5-specific VM status, mapping, evaluator branch and safe-boundary "
            "translation",
        "new_state_bytes": 0,
        "floor_or_anchor_changes": 0,
    }
    value["driver"] = BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "terminal-detail-seam WPLTO is one-shot",
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
        "lisp65-c2-link58-matrix-addenda-terminal-detail-seam-WPLTO-v1")
    value["status"] = (
        "passed-E5-terminal-detail-seam-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["E5_terminal_detail_seam"] = {
        "producer": "cold transient-reserve phase before mutation",
        "values": ["LISP65_ERR_C2_NESTING_DEPTH=63", "Fixnum 5"],
        "consumer": "existing lisp_abort_symbol plus numeric renderer",
        "abort_landing": "one existing C2J/transaction cleanup landing",
        "new_helpers": 0,
        "new_state_bytes": 0,
    }
    value["next_gate"] = (
        "authorized successor product link, then bundled C1 Freezer cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print("c2-matrix-addenda-terminal-detail-seam-wplto: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-terminal-detail-seam-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
