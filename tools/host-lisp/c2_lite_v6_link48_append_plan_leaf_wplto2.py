#!/usr/bin/env python3
"""Authorized WPLTO after the Link-45 inherited-gate Class-A stop.

The predecessor identity consumed no compiler or product-closure link.  This
fresh one-shot identity binds that stop, the corrected gate, and the 109-byte
assembler walker before running the single authorized WPLTO truth build.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_cutpoint_wplto as PROBE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link48-append-plan-leaf-wplto2"
INTERNAL = EVIDENCE / "c2.2-link48-append-plan-leaf-wplto2-internal.json"
RECEIPT = EVIDENCE / "c2.2-link48-append-plan-leaf-wplto2-receipt.json"
CLASS_A_STOP = EVIDENCE / "c2.2-link48-append-plan-leaf-wplto-receipt.json"
LINK45_GATE = ROOT / "tools/host-lisp/c2_lite_v6_link45_bcode_ordinal_wplto.py"


def main() -> int:
    old = (PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__)
    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.RECEIPT = RECEIPT
        PROBE.__file__ = str(Path(__file__).resolve())
        PROBE.run_probe()
    except (PROBE.GateError, PROBE.APPEND.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-plan-leaf-wplto2: FAIL: " + str(error),
              file=sys.stderr)
        return 1
    finally:
        PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__ = old

    os.chmod(RECEIPT, 0o644)
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    closure_links = int(internal.get("execution_accounting", {}).get(
        "product_closure_links", 0))
    recorded["format"] = recorded["format"].replace(
        "append-cutpoint", "append-plan-assembler-leaf")
    recorded["class_A_predecessor"] = {
        **PROBE.bind(CLASS_A_STOP),
        "classification": "inherited Link-45 gate; zero closure links",
        "corrected_gate": PROBE.bind(LINK45_GATE),
    }
    recorded["representation_amendment"] = {
        "forward_plan": [31, 35, 36, 37, 38],
        "rollback_plan": [43, 44, 30],
        "plan_data_bytes": 8,
        "walker": {
            **PROBE.bind(ROOT / "src/c2_append_plan_walk.s"),
            "linked_source_bytes": 109,
            "placement": "Bank-0 generic-target text corridor",
            "non_lto": True,
            "policy": "plan selection and serial walk only",
        },
        "append_status_boundary": "c2_append_overlay_call",
        "generic_family_target": "one slot only; no plan or detail policy",
        "window_floor_bytes": 115,
        "retry_policy": "single authorized WPLTO truth run",
    }
    recorded["execution_accounting"] = {
        "whole_program_lto_closure_links": closure_links,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    if recorded.get("status", "").startswith("passed"):
        recorded["next_gate"] = "authorized successor product link"
    RECEIPT.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-plan-leaf-wplto2: "
          + ("PASS" if recorded.get("status", "").startswith("passed")
             else "FIRST RED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
