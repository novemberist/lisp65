#!/usr/bin/env python3
"""Assemble and gate the one Phase-F Class-C halt #2 package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2.2-phase-f-halt2.json"
NOTE = ROOT / "docs/planning/c2.2-phase-f-halt2-review.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
F1 = EVIDENCE / "c2.2-f1-published-value-call-wplto-receipt.json"
F2 = EVIDENCE / "c2.2-f2-bitops-wplto-receipt.json"
F3 = EVIDENCE / "c2.2-f3-state-error-first-red-receipt.json"
F4 = EVIDENCE / "c2.2-f4-s1-freight-session-preparation-receipt.json"
F5 = EVIDENCE / "c2.2-f5-while-catch-throw-design-probe-receipt.json"
PUBLIC = ROOT / "lib/dialect-v2/eval-runtime.lisp"
RECEIPT = EVIDENCE / "c2.2-phase-f-halt2-review-receipt.json"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def validate() -> dict[str, Any]:
    review = load(CONFIG)
    f1, f2, f3, f4, f5 = (load(path) for path in (F1, F2, F3, F4, F5))
    requested = review["requested_disposition"]

    require(
        review["format"] == "lisp65-c2.2-phase-f-halt2-review-v1"
        and review["status"] == "class-C-halt-2-owner-approved"
        and review["owner_decision"]["successor_link_count"] == 1
        and review["owner_decision"]["successor_link_freight"]
        == requested["one_successor_link"]
        and "while is local structured iteration"
        in review["owner_decision"]["taxonomy_note"]
        and requested["one_successor_link"] == [
            "F1-n-ary-published-value-direct-call", "F2-bitops"]
        and requested["park_without_product_bytes"]
        == ["F3-gc-room-error-trio"]
        and requested["paper_decision_only"]
        == ["F5-select-while-defer-catch-throw"],
        "halt #2 identity or requested disposition drift",
    )
    require(
        f1["status"] == "passed-F1-product-shaped-WPLTO-all-walls-green"
        and f1["source_gate"]["new_resident_state_bytes"] == 0
        and f1["execution_gate"]["fixture_count"] == 18
        and f1["source_gate"]["mutations_rejected"] == 10
        and f1["static_plane_gate"]["static_code_bytes"] == 34748
        and f1["static_plane_gate"]["entries"] == 596
        and f1["freight"]["resolutions_candidate"] == 2283
        and f1["freight"]["roots_candidate"] == 283,
        "F1 receipt drift",
    )
    require(
        f2["status"] == "passed-F1-plus-F2-product-shaped-WPLTO"
        and f2["F2"]["emission_gate"]["bank2_static_code_bytes"] == 34990
        and f2["F2"]["emission_gate"]["entries"] == 602
        and f2["F2"]["emission_gate"]["resolutions"] == 2299
        and f2["F2"]["emission_gate"]["roots"] == 283
        and f2["F2"]["execution_gate"]["positive_count"] == 28
        and f2["F2"]["execution_gate"]["negative_count"] == 8
        and f2["F2"]["source_gate"]["mutations_rejected"] == 16
        and review["F2"]["bank2_static_code_bytes_including_F1"] == 34990
        and review["F2"]["bank2_delta_from_release_bytes"] == 448,
        "F2 receipt drift",
    )
    walls = dict(f2["walls"])
    require(
        walls == {
            "bank0_text_headroom_bytes": 90,
            "e000_headroom_bytes": 151,
            "fixed_hot_block_headroom_bytes": 2,
            "ordinary_bank0_bss_headroom_bytes": 137,
            "resident_island_headroom_bytes": 69,
        }
        and f2["capacity"]["session_family_headroom_bytes"] == 610,
        "F2 wall or aggregate drift",
    )
    require(
        review["F2"]["walls"] == walls | {
            "session_family_headroom_bytes": 610
        },
        "halt #2 F2 wall transcription drift",
    )
    require(
        f3["status"] == "parked-at-hard-cold-slice-cap-before-product-link"
        and f3["capacity_attribution"]["section_bytes"] == 2552
        and f3["capacity_attribution"]["hard_cap_bytes"] == 1792
        and f3["capacity_attribution"]["over_cap_bytes"] == 760
        and f3["decision"]["followup_attempts"] == 0
        and f3["product_links"] == 0 and f3["hardware_runs"] == 0,
        "F3 First Red or parked disposition drift",
    )
    require(
        f4["status"]
        == "passed-S1-preparation-hardware-not-run-link-not-bound"
        and f4["session_gate"]["row_count"] == 12
        and len(f4["session_gate"]["claim_rows"]) == 3
        and len(f4["session_gate"]["regression_rows"]) == 6
        and f4["session_gate"]["mutations_rejected"] == 10
        and f4["F3"]["status"] == "parked-not-in-S1"
        and f4["hardware_runs"] == 0 and f4["product_links"] == 0,
        "F4 session preparation drift",
    )
    require(
        f5["status"] == "passed-owner-accepted-paper-decision"
        and f5["decision"]["selected"] == "while"
        and f5["decision"]["taxonomy"] == "one control-flow repair"
        and f5["decision"]["mutations_rejected"] == 10
        and f5["decision"]["new_product_bytes"] == 0
        and f5["hardware_runs"] == 0 and f5["product_links"] == 0,
        "F5 paper decision drift",
    )

    public = PUBLIC.read_text(encoding="utf-8")
    for forbidden in (
        "(defun gc ()", "(defun room ()", "(defun error (message)",
        "(%buffer-read 4 nil)", "(%buffer-read 5 nil)",
        "(%buffer-read 6 message)",
    ):
        require(forbidden not in public,
                f"parked F3 product surface is active: {forbidden}")

    return {
        "status": "passed-single-Class-C-halt-2-package",
        "recommended_link": ["F1", "F2"],
        "parked": ["F3"],
        "paper_only": ["F5"],
        "S1_rows": 12,
        "product_links_so_far": 0,
        "hardware_runs_so_far": 0,
        "walls": walls | {
            "session_family_headroom_bytes":
                f2["capacity"]["session_family_headroom_bytes"]
        },
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def main() -> int:
    try:
        result = validate()
        receipt = {
            "format": "lisp65-c2.2-phase-f-halt2-review-receipt-v1",
            "recorded_on": "2026-07-27",
            "status": "Class-C-halt-2-owner-approved",
            "promotable": False,
            "result": result,
            "claim_limit": load(CONFIG)["claim_limit"],
            "authority": {
                "review": bind(CONFIG),
                "note": bind(NOTE),
                "F1": bind(F1),
                "F2": bind(F2),
                "F3": bind(F3),
                "F4": bind(F4),
                "F5": bind(F5),
                "gate": bind(Path(__file__)),
            },
        }
        atomic_json(RECEIPT, receipt)
        print(
            "c2 Phase-F halt #2 gate: PASS "
            "link=F1+F2 parked=F3 paper=F5 S1-rows=12 "
            "links=0 hardware=0"
        )
        return 0
    except (GateError, KeyError, ValueError, OSError) as exc:
        print(f"c2 Phase-F halt #2 gate: FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
