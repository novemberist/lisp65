#!/usr/bin/env python3
"""Replay the unconsumed VM-detail-seam WPLTO after its Class-A gate fix."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_vm_detail_seam_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-vm-detail-seam-wplto-replay")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-replay-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-replay-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-replay-receipt.json")
FIRST = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-receipt.json")
FIRST_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-vm-detail-seam-wplto-internal.json")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    internal = json.loads(FIRST_INTERNAL.read_text(encoding="utf-8"))
    require(
        first["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and internal["diagnostic"]["message"] ==
            "DIRMISS user-facing detail seam drift"
        and internal["execution_accounting"]["product_closure_links"] == 0,
        "VM-detail-seam Class-A First Red drift",
    )
    bind = BASE.BASE.P.bind
    value["class_A_closed_detail_union_first_red"] = bind(FIRST)
    value["class_A_closed_detail_union_diagnosis"] = bind(FIRST_INTERNAL)
    value["class_A_correction"] = {
        "old_model": "exactly one lisp_abort_detail consumer meant DIRMISS",
        "current_model":
            "two code-qualified closed-union consumers: DIRMISS BCODE and "
            "separately authorized E5 exact Fixnum 5",
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
        "prior_product_closure_links": 0,
    }
    value["replay_driver"] = bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "VM-detail-seam WPLTO replay is one-shot",
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
        "lisp65-c2-link58-matrix-addenda-vm-detail-seam-WPLTO-replay-v1")
    value["authority"] = authority()
    value["class_A_replay"] = authority()["class_A_correction"]
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print("c2-matrix-addenda-vm-detail-seam-wplto-replay: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-vm-detail-seam-wplto-replay: FIRST RED: "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
