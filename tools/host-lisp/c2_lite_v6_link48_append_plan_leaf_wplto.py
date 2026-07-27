#!/usr/bin/env python3
"""One-shot WPLTO truth run for the Link-48 assembler plan walker.

The consumed C data-plan attempt proved the eight plan bytes and every
cutpoint but stopped on its 441-byte generic interpreter.  This successor
keeps those semantics, substitutes one non-LTO Bank-0 leaf, and leaves detail
policy at the append-specific E000 status boundary.  It creates no promotable
product and runs no hardware.
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
OUT = ROOT / "build/c2.2/substitution/link48-append-plan-leaf-wplto"
INTERNAL = EVIDENCE / "c2.2-link48-append-plan-leaf-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link48-append-plan-leaf-wplto-receipt.json"


def main() -> int:
    old = (PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__)
    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.RECEIPT = RECEIPT
        # The inherited prerequisite binder must name this unconsumed driver,
        # never either historical one-shot identity.
        PROBE.__file__ = str(Path(__file__).resolve())
        value = PROBE.run_probe()
    except (PROBE.GateError, PROBE.APPEND.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-plan-leaf-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1
    finally:
        PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__ = old

    os.chmod(RECEIPT, 0o644)
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    recorded["format"] = recorded["format"].replace(
        "append-cutpoint", "append-plan-assembler-leaf")
    recorded["representation_amendment"] = {
        "forward_plan": [31, 35, 36, 37, 38],
        "rollback_plan": [43, 44, 30],
        "plan_data_bytes": 8,
        "walker": {
            **PROBE.bind(ROOT / "src/c2_append_plan_walk.s"),
            "placement": "Bank-0 generic-target text corridor",
            "non_lto": True,
            "policy": "plan selection and serial walk only",
        },
        "append_status_boundary": {
            "symbol": "c2_append_overlay_call",
            "policy": "first inner failure wins in two exclusive scratch bytes",
        },
        "generic_family_target": "one slot only; no plan or detail policy",
        "window_requirement": "contractual floor 115 bytes",
        "retry_policy": "one WPLTO truth run; no optimization retry",
    }
    recorded["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    if recorded.get("status", "").startswith("passed"):
        recorded["next_gate"] = (
            "separate Class-C authorization for successor product link")
    RECEIPT.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-plan-leaf-wplto: "
          + ("PASS" if recorded.get("status", "").startswith("passed")
             else "FIRST RED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
