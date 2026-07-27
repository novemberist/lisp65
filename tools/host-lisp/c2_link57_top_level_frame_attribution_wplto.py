#!/usr/bin/env python3
"""One nonpromotable WPLTO for top-level frame attribution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link57_l_full_keymap_current_product_wplto as CURRENT  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as PROFILE  # noqa: E402
import c2_top_level_frame_attribution_gate as ATTR  # noqa: E402


P = CURRENT.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link57-top-level-frame-attribution-wplto3")
INTERNAL = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto3-internal.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto3-base.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto3-first-red.json")
RECEIPT = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto3-receipt.json")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def main() -> int:
    require(
        not OUT.exists() and not INTERNAL.exists()
        and not BASE_RECEIPT.exists() and not FIRST_RED.exists()
        and not RECEIPT.exists(),
        "frame-attribution WPLTO is one-shot",
    )
    source = ATTR.validate(ATTR.source_bundle())
    source["mutations_rejected"] = ATTR.mutation_tests(ATTR.source_bundle())
    original_current = {
        "out": CURRENT.OUT,
        "internal": CURRENT.INTERNAL,
        "base_receipt": CURRENT.BASE_RECEIPT,
        "receipt": CURRENT.RECEIPT,
    }
    original_features = PROFILE.resolved_features

    def diagnostic_features() -> tuple[str, ...]:
        values = original_features()
        require("LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC" not in values,
                "diagnostic feature already present in product profile")
        return (*values, "LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC")

    try:
        CURRENT.OUT = OUT
        CURRENT.INTERNAL = INTERNAL
        CURRENT.BASE_RECEIPT = BASE_RECEIPT
        CURRENT.RECEIPT = FIRST_RED
        PROFILE.resolved_features = diagnostic_features
        result = CURRENT.main()
    finally:
        CURRENT.OUT = original_current["out"]
        CURRENT.INTERNAL = original_current["internal"]
        CURRENT.BASE_RECEIPT = original_current["base_receipt"]
        CURRENT.RECEIPT = original_current["receipt"]
        PROFILE.resolved_features = original_features

    # The inherited historical exact-size checker is expected to stop after
    # the one WPLTO.  That is a Class-A model mismatch, not authorization for
    # another compiler or linker run; qualification continues read-only.
    require(OUT.is_dir(), "frame-attribution WPLTO produced no artifact tree")
    require(result != 0 and FIRST_RED.is_file(),
            "inherited checker did not produce the expected read-only boundary")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-top-level-frame-attribution-wplto-boundary-v1",
        "recorded_on": "2026-07-23",
        "status":
            "WPLTO complete; inherited exact-wall checker red; read-only "
            "diagnostic qualification required",
        "promotable": False,
        "source_gate": source,
        "inherited_first_red": first,
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0
        },
        "next_gate":
            "Class-A read-only qualification of the immutable diagnostic ELF"
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProbeError,
        ATTR.GateError,
        CURRENT.WPLTOError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-link57-top-level-frame-attribution-WPLTO: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
