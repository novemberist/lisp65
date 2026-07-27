#!/usr/bin/env python3
"""Unconsumed Link-57 attempt after the Class-A dominance-gate repair."""

from __future__ import annotations

import json
import os
from pathlib import Path

import c2_link57_keymap_nullary_successor_link as BASE


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FIRST_RED = EVIDENCE / (
    "c2.2-product-link57-keymap-nullary-fast-path-structural-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2")
RECEIPT = EVIDENCE / (
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json")


def main() -> int:
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    BASE.require(
        first["status"] == "FIRST RED: C2-lite real-ABI Link 57 stopped"
        and first["diagnostic"] == {
            "message": "mutation anchor absent: inner-transition-after-vm-call",
            "type": "GateError",
        }
        and first["execution_accounting"]["product_closure_links"] == 0,
        "Link-57 unconsumed Class-A boundary drift",
    )
    old_out, old_receipt = BASE.OUT, BASE.RECEIPT
    try:
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        result = BASE.main()
    finally:
        BASE.OUT, BASE.RECEIPT = old_out, old_receipt
    if result != 0:
        return result
    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["authority"]["class_A_prelink_first_red"] = BASE.L.bind(FIRST_RED)
    value["authority"]["corrected_first_fault_dominance_gate"] = BASE.L.bind(
        ROOT / "tools/host-lisp/c2_install_phase_discriminator_gate.py")
    value["class_A_prelink_replay"] = {
        "old_model":
            "the inner-VM install stamp had to be textually adjacent to "
            "vm_run_dir",
        "current_model":
            "the stamp must dominate vm_run_dir; the feature-gated frame "
            "stamp may intervene without changing product semantics",
        "first_attempt_product_closure_links": 0,
        "first_attempt_hardware_runs": 0,
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
