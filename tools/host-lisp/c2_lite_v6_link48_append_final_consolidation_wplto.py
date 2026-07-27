#!/usr/bin/env python3
"""One authorized WPLTO truth run for the final append consolidation.

This is the hard-stop round approved after the fourth placement attempt.  It
does not move another tenant: it retires internal BADOPCODE diagnostic
scaffolding, fuses publish_exports with journal_clear, and deduplicates the
rollback-plan setup.  One product-shaped WPLTO must close text, E000 and the
Session aggregate together; no product link or hardware run is performed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_final_consolidation_gate as CONS  # noqa: E402
import c2_lite_v6_final_island_identity_successor_link as FINAL  # noqa: E402
import c2_lite_v6_link48_append_cutpoint_wplto as PROBE  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


P = FINAL.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link48-append-final-consolidation-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-receipt.json")
DESIGN = EVIDENCE / (
    "c2.2-link48-append-cold-cut-wplto-first-red-diagnosis.json")
TEXT_NOISE_FLOOR = 32
E000_FLOOR = 115
BANK_BYTES = 65536
CAP = 1792


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PROBE.GateError(message)


def capacity_gate(shape: dict[str, Any], elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    sections = [spec.split(":")[2] for spec in P.SESSION_SLICE_SPECS]
    sizes = [truth.section(section).bytes for section in sections]
    modeled = FINAL.BASE_LINK.DIET.packed_bytes(sizes)
    session = shape["successor_bank3_pack"]["session"]
    fused = truth.section(".lisp65_rt_c2append_publish_clear")
    journal_prepare = (
        ".lisp65_rt_c2append_journal_prepare" in truth.sections_by_name)
    expected_records = 48 if journal_prepare else 49
    expected_append_records = 21 if journal_prepare else 22
    expected_service_base = 44 if journal_prepare else 45
    retired = {name: name in truth.sections_by_name for name in (
        ".lisp65_rt_c2append_journal_clear",
        ".lisp65_rt_c2append_publish_exports")}
    require(len(sections) == expected_records
            and len(P.C2_APPEND_SLICES) == expected_append_records
            and P.SESSION_SERVICE_SLOT_BASE == expected_service_base
            and modeled == session["bytes"] <= BANK_BYTES
            and session["headroom_bytes"] == BANK_BYTES - modeled
            and 0 < fused.bytes <= CAP
            and not any(retired.values()),
            "final consolidation aggregate/profile gate red")
    return {
        "status": "passed-final-one-record-aggregate-consolidation",
        "slice_cap_bytes": CAP,
        "pack_quantum_bytes": 256,
        "publish_clear_bytes": fused.bytes,
        "publish_clear_headroom_bytes": CAP - fused.bytes,
        "retired_sections_present": retired,
        "session_catalog_records": len(sections),
        "journal_prepare_co_resident": journal_prepare,
        "session_family_bytes": modeled,
        "session_family_headroom_bytes": BANK_BYTES - modeled,
    }


def roots_fronts_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_rt_c2append_roots_fronts")
    symbols = {name: truth.symbol(name) for name in (
        "c2_append_roots_phase", "c2_append_fronts_phase",
        "c2_append_roots_fronts_phase")}
    require(0 < section.bytes <= CAP
            and all(symbol.section == section.name and symbol.bytes > 0
                    for symbol in symbols.values())
            and ".lisp65_rt_c2append_roots" not in truth.sections_by_name
            and ".lisp65_rt_c2append_fronts" not in truth.sections_by_name,
            "roots/fronts predecessor fusion regressed")
    return {
        "status": "passed-one-slice-two-entry-linked-product",
        "section": {"name": section.name, "address": section.address,
                    "bytes": section.bytes,
                    "headroom_bytes": CAP - section.bytes},
        "entries": {name: {"address": symbol.value, "bytes": symbol.bytes,
                           "section": symbol.section}
                    for name, symbol in symbols.items()},
    }


def main() -> int:
    old = {
        "out": PROBE.OUT,
        "internal": PROBE.INTERNAL,
        "receipt": PROBE.RECEIPT,
        "file": PROBE.__file__,
        "prerequisites": PROBE.prerequisites,
        "rf_configure": RF.configure_roots_fronts,
        "profile_features": PROFILE.feature_defines,
        "profile_compare": PROFILE.compare_link_entry,
        "capacity": FINAL.capacity_gate,
        "roots": FINAL.roots_fronts_product_gate,
    }
    expected_features = (*old["profile_features"](), CONS.FEATURE)

    def prerequisites() -> dict[str, Any]:
        value = old["prerequisites"]()
        value["final_consolidation_source"] = CONS.source_gate()
        value["class_c_first_red_diagnosis"] = PROBE.bind(DESIGN)
        value["probe_profile_delta"] = {
            "base_profile": PROFILE.check(),
            "added_feature": CONS.FEATURE,
            "feature_defines": list(expected_features),
        }
        return value

    def configure_roots_fronts_and_publish_clear() -> None:
        old["rf_configure"]()
        CONS.configure_publish_clear()

    def feature_defines() -> tuple[str, ...]:
        return expected_features

    def compare_link_entry(features: Any) -> None:
        if tuple(features) != expected_features:
            raise PROFILE.ProfileError(
                "product-link entry differs from final consolidation profile")

    try:
        require(not OUT.exists() and not INTERNAL.exists()
                and not RECEIPT.exists(),
                "final consolidation WPLTO is one-shot")
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.RECEIPT = RECEIPT
        PROBE.__file__ = str(Path(__file__).resolve())
        PROBE.prerequisites = prerequisites
        RF.configure_roots_fronts = configure_roots_fronts_and_publish_clear
        PROFILE.feature_defines = feature_defines
        PROFILE.compare_link_entry = compare_link_entry
        FINAL.capacity_gate = capacity_gate
        FINAL.roots_fronts_product_gate = roots_fronts_gate
        result = PROBE.run_probe()
    except (PROBE.GateError, PROBE.APPEND.GateError, CONS.GateError,
            PROFILE.ProfileError, OSError, RuntimeError, ValueError) as error:
        print("c2-lite-v6-link48-append-final-consolidation-wplto: FAIL: "
              + str(error), file=sys.stderr)
        return 1
    finally:
        PROBE.OUT = old["out"]
        PROBE.INTERNAL = old["internal"]
        PROBE.RECEIPT = old["receipt"]
        PROBE.__file__ = old["file"]
        PROBE.prerequisites = old["prerequisites"]
        RF.configure_roots_fronts = old["rf_configure"]
        PROFILE.feature_defines = old["profile_features"]
        PROFILE.compare_link_entry = old["profile_compare"]
        FINAL.capacity_gate = old["capacity"]
        FINAL.roots_fronts_product_gate = old["roots"]

    os.chmod(RECEIPT, 0o644)
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if not recorded.get("status", "").startswith("passed"):
        recorded["status"] = (
            "FIRST RED: final consolidation failed the simultaneous hard close")
        recorded["next_gate"] = (
            "No further consolidation or placement cycle; return the measured "
            "floor-or-scope decision to Alex after recovery.")
    else:
        internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
        gates = internal["fresh_replacement_gates"]
        walls, capacity = gates["walls"], gates["capacity"]
        hard_completion = {
            "bank0_text": {
                "headroom_bytes": walls["bank0_text_headroom_bytes"],
                "required_noise_headroom_bytes": TEXT_NOISE_FLOOR,
                "passed": walls["bank0_text_headroom_bytes"] >=
                    TEXT_NOISE_FLOOR,
            },
            "e000": {
                "headroom_bytes": walls["e000_headroom_bytes"],
                "floor_bytes": E000_FLOOR,
                "passed": walls["e000_headroom_bytes"] >= E000_FLOOR,
            },
            "session_aggregate": {
                "bytes": capacity["session_family_bytes"],
                "headroom_bytes": capacity["session_family_headroom_bytes"],
                "ceiling_bytes": BANK_BYTES,
                "passed": capacity["session_family_bytes"] <= BANK_BYTES,
            },
        }
        recorded["hard_completion"] = hard_completion
        if all(item["passed"] for item in hard_completion.values()):
            recorded["status"] = (
                "passed-final-consolidation-simultaneous-three-currency-close")
            recorded["next_gate"] = (
                "Separate Class-C authorization for the successor product "
                "link; Link 48 remains untouched.")
        else:
            recorded["status"] = (
                "FIRST RED: final consolidation missed the simultaneous "
                "three-currency hard close")
            recorded["next_gate"] = (
                "No further consolidation or placement cycle; return the "
                "measured floor-or-scope decision to Alex after recovery.")
    recorded["consolidation"] = {
        "kind": "content reduction, not tenant placement",
        "badopcode_detail": "retired; DIRMISS detail preserved",
        "physical_fusion": "publish_exports+journal_clear -> publish_clear",
        "rollback_setup": "one shared E000 seam",
        "product_links": 0,
        "hardware_runs": 0,
        "line1_first_red_budget": "2/3 unchanged",
        "latency_measurement_attempts": "0/2 unchanged",
    }
    RECEIPT.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-final-consolidation-wplto: "
          + ("PASS" if recorded["status"].startswith("passed")
             else "FIRST RED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
