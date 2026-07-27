#!/usr/bin/env python3
"""Permanent source/profile gate for the final append consolidation.

The consolidation is intentionally not another placement attempt.  It
removes the fixture-complete BADOPCODE diagnostic scaffold, represents
publish_exports and journal_clear as two marker-selected operations in one
physical Session record, and retains one shared rollback-plan setup seam.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_phase_plan_gate as PLAN  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


FEATURE = "LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT"
CONTRACT = ROOT / "config/c2-append-cutpoint-contract.json"
CAP = 1792
BANK_BYTES = 65536
PACK_QUANTUM = 256


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def configure_publish_clear() -> None:
    rows = list(PRODUCT.C2_APPEND_SLICES)
    names = [name for name, _entry in rows]
    require(names.count("journal_clear") == 1
            and names.count("publish_exports") == 1,
            "publish/clear profile anchors absent")
    rows.pop(names.index("journal_clear"))
    names = [name for name, _entry in rows]
    at = names.index("publish_exports")
    rows[at] = ("publish_clear", "c2_append_publish_clear_phase")
    PRODUCT.configure_append_slices(rows)
    require(
        len(PRODUCT.C2_APPEND_SLICES) == 22
        and PRODUCT.SESSION_APPEND_SLOT_BASE == 23
        and PRODUCT.SESSION_SERVICE_SLOT_BASE == 45
        and len(PRODUCT.SESSION_SLICE_SPECS) == 49
        and PRODUCT.UNIQUE_SLICE_COUNT == 56,
        "publish/clear physical-profile ABI drift")


def profile_gate() -> dict[str, Any]:
    names = [name for name, _entry in PRODUCT.C2_APPEND_SLICES]
    require(names.count("publish_clear") == 1
            and "publish_exports" not in names
            and "journal_clear" not in names,
            "publish/clear profile still has two records")
    at = names.index("publish_clear")
    require(PRODUCT.C2_APPEND_SLICES[at] ==
            ("publish_clear", "c2_append_publish_clear_phase"),
            "fused record entry drift")
    specs = [spec for spec in PRODUCT.SESSION_SLICE_SPECS
             if "c2-append-publish-clear" in spec]
    journal_prepare = "journal_prepare" in names
    expected_slot = 40 if journal_prepare else 41
    require(len(specs) == 1
            and specs[0].startswith(
                f"{expected_slot}:c2-append-publish-clear:")
            and ":c2_append_publish_clear_phase" in specs[0],
            "fused public record projection/slot drift")
    return {
        "status": "passed-one-physical-record-profile",
        "append_records": len(PRODUCT.C2_APPEND_SLICES),
        "session_records": len(PRODUCT.SESSION_SLICE_SPECS),
        "session_service_slot_base": PRODUCT.SESSION_SERVICE_SLOT_BASE,
        "fused_record": specs[0],
        "retired_records": ["journal_clear", "publish_exports"],
    }


def source_gate() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] == "lisp65.c2.append-cutpoint-contract.v8"
            and contract["publish_clear_co_residence"]["slot"] == 40
            and contract["badopcode_detail_retirement"]["preserved"] == [
                "VM_BADOPCODE fail-closed status",
                "cold tagged install-phase provenance outside the append work structs",
                "DIRMISS symbolic name detail",
                "DIRMISS BCODE ordinal detail"],
            "final consolidation contract drift")
    plan = PLAN.source_gate()
    require(plan["phase_plan"]["forward_plan"] ==
                [30, 39, 33, 34, 35, 36]
            and plan["phase_plan"]["persistent_publish_plan"] ==
                [37, 38, 39, 40]
            and plan["phase_plan"]["rollback_plan"] ==
                [39, 41, 42, 43, 44, 45, 40, 39]
            and len(plan["co_resident_publish_clear"]
                    ["negative_mutations"]) == 6,
            "final consolidation source/mutation gate red")
    return {
        "status": "passed-final-append-consolidation-source-contract",
        "feature": FEATURE,
        "phase_plan": plan,
        "hard_completion_criteria": {
            "bank0_text_headroom_bytes": ">=32",
            "e000_headroom_bytes": ">=54",
            "session_family_bytes": f"<={BANK_BYTES}",
            "slice_cap_bytes": CAP,
            "pack_quantum_bytes": PACK_QUANTUM,
        },
    }


def main() -> int:
    result = source_gate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
