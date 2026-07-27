#!/usr/bin/env python3
"""One product-shaped WPLTO for the approved C2.2 matrix addenda."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link57_l_full_keymap_current_product_wplto as BASE  # noqa: E402
import c2_matrix_b3_d3_break_delivery as B3D3  # noqa: E402
import c2_matrix_c3_handoff_freezer as C3  # noqa: E402
import c2_matrix_e5_nesting_depth as E5  # noqa: E402
import c2_published_nullary_call_product_artifacts as CURRENT  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link58-matrix-addenda-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-base-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-wplto-receipt.json")
ORIGINAL_AUTHORITY = BASE.authority
PRODUCT_IDENTITY = CURRENT.PRODUCT / "substitution-artifacts.json"
PRODUCT_ARTIFACTS = CURRENT.RECEIPT
SPECS = CURRENT.SPECS


def fixture_result(module: Any) -> dict[str, Any]:
    return json.loads(module.RECEIPT.read_text(encoding="utf-8"))


def authority() -> dict[str, Any]:
    base = ORIGINAL_AUTHORITY()
    b3d3 = fixture_result(B3D3)
    c3 = fixture_result(C3)
    e5 = fixture_result(E5)
    P.require(
        b3d3["status"] ==
            "passed-host-source-model-awaiting-hardware-queue-full"
        and len(b3d3["mutations"]) == 16
        and len(c3["owner_matrix"]) == 4
        and len(c3["mutations"]) == 6
        and len(e5["cases"]) == 5
        and len(e5["mutations"]) == 14,
        "approved matrix-addenda authority is incomplete",
    )
    return {
        **base,
        "approved_addenda_contract": P.bind(B3D3.ADDENDA),
        "approved_addenda_review": P.bind(B3D3.REVIEW),
        "B3_D3_fixture": {
            **P.bind(B3D3.RECEIPT), "result": b3d3["status"]},
        "C3_fixture": {
            **P.bind(C3.RECEIPT), "result": c3["status"]},
        "E5_fixture": {
            **P.bind(E5.RECEIPT), "result": e5["status"]},
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    P.require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "matrix-addenda WPLTO is one-shot",
    )
    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
        "product_identity": BASE.PRODUCT_IDENTITY,
        "product_artifacts": BASE.PRODUCT_ARTIFACTS,
        "bytecode": BASE.BYTECODE,
        "specs": BASE.SPECS,
    }
    try:
        BASE.PRODUCT_IDENTITY = PRODUCT_IDENTITY
        BASE.PRODUCT_ARTIFACTS = PRODUCT_ARTIFACTS
        BASE.BYTECODE = CURRENT.BASE
        BASE.SPECS = SPECS
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
        BASE.PRODUCT_IDENTITY = old["product_identity"]
        BASE.PRODUCT_ARTIFACTS = old["product_artifacts"]
        BASE.BYTECODE = old["bytecode"]
        BASE.SPECS = old["specs"]

    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    value["format"] = "lisp65-c2-link58-matrix-addenda-wplto-v1"
    value["status"] = "passed-matrix-addenda-WPLTO-all-walls-green"
    value["authority"] = auth
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = (
        "Class-C successor product link, then bundled C1/B3/C3/D3/E5 "
        "hardware cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(RECEIPT, 0o444)
    print("c2-matrix-addenda-wplto: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-wplto: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
