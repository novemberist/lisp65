#!/usr/bin/env python3
"""Replay the unconsumed closure after correcting replay cardinality only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_terminal_detail_seam_wplto_inventory_replay as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-inventory-replay2")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay2-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay2-receipt.json")
FIRST = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay-receipt.json")
FIRST_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay-internal.json")
ORIGINAL_AUTHORITY = BASE.authority
FIRST_OUT = BASE.OUT


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    internal = json.loads(FIRST_INTERNAL.read_text(encoding="utf-8"))
    report = json.loads((
        FIRST_OUT /
        "final-section-inventory-resident-island-seed.prg.json"
    ).read_text(encoding="utf-8"))
    require(
        internal["diagnostic"]["message"] ==
            "corrected immutable seed qualification is red"
        and internal["execution_accounting"]["product_closure_links"] == 0
        and report["status"] == "passed"
        and report["pin"]["profile_derivation"]["expected_names"] == 175,
        "inventory replay-cardinality First Red drift",
    )
    bind = BASE.BASE.BASE.P.bind
    value["class_A_replay_cardinality_first_red"] = bind(FIRST)
    value["class_A_replay_cardinality_diagnosis"] = bind(FIRST_INTERNAL)
    value["green_175_name_inventory"] = bind(
        FIRST_OUT / "final-section-inventory-resident-island-seed.prg.json")
    value["class_A_replay_cardinality_correction"] = {
        "old_value": 138,
        "current_value": 175,
        "source": "configured profile derivation in the green inventory report",
        "product_bytes_changed": 0,
        "capacity_effect_bytes": 0,
        "prior_product_closure_links": 0,
    }
    value["replay2_driver"] = bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "second inventory continuation is one-shot",
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
        "lisp65-c2-link58-matrix-addenda-terminal-detail-seam-"
        "WPLTO-inventory-replay2-v1")
    value["authority"] = authority()
    value["class_A_inventory_replay_cardinality"] = (
        authority()["class_A_replay_cardinality_correction"])
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-terminal-detail-seam-inventory-replay2: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-terminal-detail-seam-inventory-replay2: "
            "FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
