#!/usr/bin/env python3
"""One fresh WPLTO for E5's existing terminal seam with true MOS control flow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_terminal_detail_seam_wplto as BASE  # noqa: E402
import c2_matrix_e5_nesting_depth as E5  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-cold-front-terminal-noreturn-wplto-replay2")
INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-base.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay2-receipt.json")
AGGREGATE_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-"
    "aggregate-first-red-receipt.json")
ORDERING_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-noreturn-wplto-receipt.json")
ORDERING_RED_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-noreturn-wplto-internal.json")
EARLY_ORDERING_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-noreturn-wplto2-receipt.json")
EARLY_ORDERING_RED_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-noreturn-wplto2-internal.json")
CHECKER_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-receipt.json")
CHECKER_RED_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-internal.json")
SISTER_CHECKER_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay-receipt.json")
SISTER_CHECKER_RED_INTERNAL = EVIDENCE / (
    "c2.2-link58-matrix-addenda-cold-front-terminal-noreturn-"
    "wplto-replay-internal.json")
ORIGINAL_AUTHORITY = BASE.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def authority() -> dict[str, Any]:
    value = ORIGINAL_AUTHORITY()
    red = json.loads(AGGREGATE_RED.read_text(encoding="utf-8"))
    ordering_red = json.loads(ORDERING_RED.read_text(encoding="utf-8"))
    ordering_internal = json.loads(
        ORDERING_RED_INTERNAL.read_text(encoding="utf-8"))
    early_ordering_red = json.loads(
        EARLY_ORDERING_RED.read_text(encoding="utf-8"))
    early_ordering_internal = json.loads(
        EARLY_ORDERING_RED_INTERNAL.read_text(encoding="utf-8"))
    checker_red = json.loads(CHECKER_RED.read_text(encoding="utf-8"))
    checker_internal = json.loads(
        CHECKER_RED_INTERNAL.read_text(encoding="utf-8"))
    sister_checker_red = json.loads(
        SISTER_CHECKER_RED.read_text(encoding="utf-8"))
    sister_checker_internal = json.loads(
        SISTER_CHECKER_RED_INTERNAL.read_text(encoding="utf-8"))
    e5 = json.loads(E5.RECEIPT.read_text(encoding="utf-8"))
    require(
        red["status"].startswith(
            "FIRST RED: terminal abort was modeled as returning")
        and red["session_family"]["overflow_bytes"] == 158
        and red["changed_slices"][0]["name"] ==
            "c2-append-reserve-transient-bounds"
        and red["changed_slices"][0]["delta_bytes"] == 294
        and red["changed_slices"][0]["quantum_delta_bytes"] == 256
        and red["changed_slices"][1]["name"] == "error-text-renderer"
        and red["changed_slices"][1]["quantum_delta_bytes"] == 0
        and e5["status"] ==
            "passed-product-shaped-host-awaiting-real-eval-hardware"
        and len(e5["mutations"]) == 14
        and ordering_red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and ordering_internal["execution_accounting"][
            "product_closure_links"] == 1
        and "runtime_overlay_bank.py" in
            ordering_internal["diagnostic"]["message"]
        and "first-class-buffer-alloc" in
            ordering_internal["diagnostic"]["message"]
        and early_ordering_red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and early_ordering_internal["execution_accounting"][
            "product_closure_links"] == 1
        and "first-class-buffer-alloc" in
            early_ordering_internal["diagnostic"]["message"]
        and checker_red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and checker_internal["diagnostic"]["message"] ==
            "install did not retire typed BADOPCODE detail status-only"
        and checker_internal["execution_accounting"][
            "product_closure_links"] == 0,
        "terminal-control-flow WPLTO first checker authority drift")
    require(
        sister_checker_red["status"] ==
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO"
        and sister_checker_internal["diagnostic"]["message"] ==
            "retired BADOPCODE sister seam drift"
        and sister_checker_internal["execution_accounting"][
            "product_closure_links"] == 0,
        "terminal-control-flow WPLTO authority drift")
    value["terminal_return_model_first_red"] = BASE.BASE.P.bind(AGGREGATE_RED)
    value["terminal_noreturn_E5_fixture"] = BASE.BASE.P.bind(E5.RECEIPT)
    value["terminal_noreturn_ordering_first_red"] = (
        BASE.BASE.P.bind(ORDERING_RED))
    value["terminal_noreturn_ordering_diagnosis"] = (
        BASE.BASE.P.bind(ORDERING_RED_INTERNAL))
    value["terminal_noreturn_early_ordering_first_red"] = (
        BASE.BASE.P.bind(EARLY_ORDERING_RED))
    value["terminal_noreturn_early_ordering_diagnosis"] = (
        BASE.BASE.P.bind(EARLY_ORDERING_RED_INTERNAL))
    value["class_A_cold_front_checker_first_red"] = (
        BASE.BASE.P.bind(CHECKER_RED))
    value["class_A_cold_front_checker_diagnosis"] = (
        BASE.BASE.P.bind(CHECKER_RED_INTERNAL))
    value["class_A_cold_front_sister_checker_first_red"] = (
        BASE.BASE.P.bind(SISTER_CHECKER_RED))
    value["class_A_cold_front_sister_checker_diagnosis"] = (
        BASE.BASE.P.bind(SISTER_CHECKER_RED_INTERNAL))
    value["terminal_control_flow_correction"] = {
        "MOS": (
            "existing active REPL abort landing is non-returning at the "
            "depth-five callsite"),
        "host": "fixture retains its deliberate status-return path",
        "new_helpers": 0,
        "new_state_bytes": 0,
        "new_error_seams": 0,
        "target":
            "remove the fictitious +294-byte call-live expansion and its "
            "single 256-byte session-family quantum",
        "ordering_correction":
            "perform the depth refusal immediately after the authenticated "
            "depth read, before any other front or Attic value becomes live",
        "cold_phase_correction":
            "move the terminal refusal into the already non-leaf fronts "
            "phase immediately after c2_transient_fronts; both reservation "
            "phases return to their pre-E5 leaf form",
    }
    value["driver"] = BASE.BASE.P.bind(Path(__file__))
    return value


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
        "terminal-noreturn WPLTO is one-shot")
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
    walls = value["walls"]
    capacity = value["capacity"]
    require(
        walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] <= 65536,
        "terminal-noreturn simultaneous close is red")
    value["format"] = (
        "lisp65-c2-link58-matrix-addenda-terminal-noreturn-WPLTO-v1")
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-E5-existing-terminal-seam-WPLTO-all-walls-green")
    value["authority"] = authority()
    value["terminal_control_flow"] = (
        authority()["terminal_control_flow_correction"])
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["next_gate"] = (
        "authorized successor product link, then bundled C1 Freezer cutpoints")
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-matrix-addenda-terminal-noreturn-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-matrix-addenda-terminal-noreturn-wplto: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
