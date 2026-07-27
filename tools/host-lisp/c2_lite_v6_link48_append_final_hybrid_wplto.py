#!/usr/bin/env python3
"""One owner-authorized WPLTO for the final Hybrid append geometry.

This consumes candidate 1 (numeric-only early C2 errors), the 54-byte E000
floor and the predecessor-bound reopen/session/profile geometry in one
product-shaped WPLTO.  It creates no promotable product and uses no hardware.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_consolidation_wplto as BASE  # noqa: E402
import c2_numeric_early_errors_gate as CUT  # noqa: E402


P = BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link48-append-final-hybrid-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-wplto-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-wplto-receipt.json")
CLASS_A_FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-wplto-internal.json")
ABI_FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-wplto-first-red-diagnosis.json")
ABI_FIRST_RED_CORRECTION = EVIDENCE / (
    "c2.2-link48-append-final-hybrid-wplto-first-red-diagnosis-"
    "correction.json")
CONTRACT = ROOT / "config/c2-append-final-hybrid-contract.json"
EXECUTION = ROOT / "config/c2-lite-execution-contract.json"
E000_FLOOR = 54
TEXT_NOISE_FLOOR = 32


class HybridError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HybridError(message)


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "final Hybrid WPLTO is one-shot")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    selection = contract["selection"]
    require(selection["selected_candidate"] == "numeric-early-errors"
            and selection["selected_attributed_text_bytes"] == 81
            and selection["product_source_changes_authorized"] == 1
            and execution["decision"]["bank0_scope_cut_selection"] ==
                "numeric-early-errors"
            and execution["decision"]
                ["bank0_scope_cut_attributed_text_bytes"] == 81
            and execution["scope"]["product_shaped_probes_authorized"] == 1,
            "owner-selected Hybrid scope cut is absent")

    old = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "receipt": BASE.RECEIPT,
        "file": BASE.__file__,
        "e000_floor": BASE.E000_FLOOR,
        "prerequisites": BASE.PROBE.prerequisites,
        "rf_configure": BASE.RF.configure_roots_fronts,
        "profile_features": BASE.PROFILE.feature_defines,
        "capacity": BASE.capacity_gate,
        "consolidation_source": BASE.CONS.source_gate,
    }
    selected_features = (*old["profile_features"](), CUT.FEATURE)

    def prerequisites() -> dict[str, Any]:
        value = old["prerequisites"]()
        preflight = ROOT / (
            "build/c2.2/substitution/"
            "link48-append-final-hybrid-preflight/final-wplto-early-errors")
        value["numeric_early_errors"] = {
            "source": CUT.source_gate(),
            "host": CUT.host_gate(preflight),
        }
        value["hybrid_authority"] = {
            "contract": CUT.bind(CONTRACT),
            "execution_contract": CUT.bind(EXECUTION),
            "selected_candidate": selection["selected_candidate"],
            "selected_attributed_text_bytes":
                selection["selected_attributed_text_bytes"],
            "authorized_whole_program_lto_runs": 1,
        }
        if CLASS_A_FIRST_RED.is_file() and CLASS_A_FIRST_RED != INTERNAL:
            value["class_a_authority_preflight_first_red"] = CUT.bind(
                CLASS_A_FIRST_RED)
        if ABI_FIRST_RED.is_file():
            value["append_plan_abi_first_red"] = CUT.bind(ABI_FIRST_RED)
        if ABI_FIRST_RED_CORRECTION.is_file():
            value["append_plan_abi_first_red_correction"] = CUT.bind(
                ABI_FIRST_RED_CORRECTION)
        return value

    def configure_hybrid_geometry() -> None:
        old["rf_configure"]()
        P.configure_c2_lite_hybrid_e000_geometry()
        require(P.E000_FINAL_FLOOR_BYTES == E000_FLOOR
                and P.SESSION_EMITTER_STATE_BYTES == 10
                and P.PROFILE_RODATA_BASE == 0xFD2C,
                "active Hybrid E000 geometry drift")

    def feature_defines() -> tuple[str, ...]:
        return selected_features

    def capacity_gate(shape: dict[str, Any], elf: Path) -> dict[str, Any]:
        value = old["capacity"](shape, elf)
        value["numeric_early_errors"] = CUT.linked_gate(elf)
        return value

    def consolidation_source() -> dict[str, Any]:
        value = old["consolidation_source"]()
        value["hard_completion_criteria"]["e000_headroom_bytes"] = ">=54"
        return value

    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.RECEIPT = RECEIPT
        BASE.__file__ = str(Path(__file__).resolve())
        BASE.E000_FLOOR = E000_FLOOR
        BASE.PROBE.prerequisites = prerequisites
        BASE.RF.configure_roots_fronts = configure_hybrid_geometry
        BASE.PROFILE.feature_defines = feature_defines
        BASE.capacity_gate = capacity_gate
        BASE.CONS.source_gate = consolidation_source
        result = BASE.main()
    except (HybridError, CUT.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-final-hybrid-wplto: FAIL: "
              + str(error), file=sys.stderr)
        return 1
    finally:
        BASE.OUT = old["out"]
        BASE.INTERNAL = old["internal"]
        BASE.RECEIPT = old["receipt"]
        BASE.__file__ = old["file"]
        BASE.E000_FLOOR = old["e000_floor"]
        BASE.PROBE.prerequisites = old["prerequisites"]
        BASE.RF.configure_roots_fronts = old["rf_configure"]
        BASE.PROFILE.feature_defines = old["profile_features"]
        BASE.capacity_gate = old["capacity"]
        BASE.CONS.source_gate = old["consolidation_source"]

    if result != 0:
        return result
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if not recorded.get("status", "").startswith("passed"):
        os.chmod(RECEIPT, 0o444)
        return 1
    os.chmod(RECEIPT, 0o644)
    receipt = recorded
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    early = capacity["numeric_early_errors"]
    structure_path = OUT / "product-substitution-link.json"
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    require(receipt["status"].startswith("passed")
            and walls["bank0_text_headroom_bytes"] >= TEXT_NOISE_FLOOR
            and walls["e000_headroom_bytes"] >= E000_FLOOR
            and capacity["session_family_bytes"] <= 65536
            and early["resident_sentences_present"] == 0
            and structure["actual_e000_future_margin_bytes"] ==
                walls["e000_headroom_bytes"]
            and P.E000_FINAL_FLOOR_BYTES == E000_FLOOR
            and P.SESSION_EMITTER_STATE_BYTES == 10
            and P.PROFILE_RODATA_BASE == 0xFD2C,
            "final Hybrid simultaneous WPLTO close is red")
    receipt["status"] = (
        "passed-owner-hybrid-numeric-early-errors-simultaneous-WPLTO")
    receipt["hybrid"] = {
        "selection": "numeric-early-errors",
        "selected_attributed_text_bytes": 81,
        "linked_numeric_early_errors": early,
        "product_substitution_structure": CUT.bind(structure_path),
        "e000_geometry": {
            "floor_bytes": E000_FLOOR,
            "reopen_gap0": {"start": 0xFCA2, "end": 0xFD22,
                            "bytes": 128},
            "session_emitter_state": {"start": 0xFD22,
                                      "end": 0xFD2C, "bytes": 10},
            "profile_rodata_base": 0xFD2C,
            "former_overlap_bytes": 0,
            "self_defense": (
                "Any future need below 54 bytes automatically triggers scope "
                "triage; no negotiation and no fourth floor event."),
        },
        "hard_completion": {
            "bank0_text_headroom_bytes":
                walls["bank0_text_headroom_bytes"],
            "required_text_noise_headroom_bytes": TEXT_NOISE_FLOOR,
            "e000_headroom_bytes": walls["e000_headroom_bytes"],
            "required_e000_floor_bytes": E000_FLOOR,
            "session_family_bytes": capacity["session_family_bytes"],
            "session_family_headroom_bytes":
                capacity["session_family_headroom_bytes"],
        },
        "execution_accounting": {
            "authorized_whole_program_lto_runs": 1,
            "whole_program_lto_runs_consumed": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
    }
    receipt["next_gate"] = (
        "Separate Class-C authorization for the successor product link; "
        "Link 48 remains untouched.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-final-hybrid-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"fixed={walls['fixed_hot_block_headroom_bytes']} "
          f"island={walls['resident_island_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
