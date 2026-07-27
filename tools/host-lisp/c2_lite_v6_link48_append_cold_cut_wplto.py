#!/usr/bin/env python3
"""One authorized WPLTO truth run for the final append cold cut.

The predecessor WPLTO measured the correct phase plans but placed their
policy in resident code.  This one-shot identity keeps the proven plan bytes,
moves terminal status publication into the final append publication phase,
and places the sole serial walker in the resident Island.  It creates no
promotable product and runs no hardware.
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
OUT = ROOT / "build/c2.2/substitution/link48-append-cold-cut-wplto"
INTERNAL = EVIDENCE / "c2.2-link48-append-cold-cut-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link48-append-cold-cut-wplto-receipt.json"
DESIGN = EVIDENCE / (
    "c2.2-link48-append-temperature-residency-design-receipt.json")


def main() -> int:
    old = (PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__,
           PROBE.prerequisites)

    def prerequisites() -> dict[str, object]:
        value = old[4]()
        value["temperature_residency_design"] = PROBE.bind(DESIGN)
        return value

    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.RECEIPT = RECEIPT
        PROBE.__file__ = str(Path(__file__).resolve())
        PROBE.prerequisites = prerequisites
        PROBE.run_probe()
    except (PROBE.GateError, PROBE.APPEND.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-cold-cut-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1
    finally:
        (PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__,
         PROBE.prerequisites) = old

    os.chmod(RECEIPT, 0o644)
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    closure_links = int(internal.get("execution_accounting", {}).get(
        "product_closure_links", 0))
    recorded["format"] = recorded["format"].replace(
        "append-cutpoint", "append-cold-temperature-cut")
    recorded["temperature_cut"] = {
        "authority": PROBE.bind(DESIGN),
        "resident_minimum": [
            "generic Session family seam",
            "raw first-error transport in the existing append scratch",
            "one non-LTO Island plan walker",
        ],
        "cold_phase_owners": {
            "terminal_status_publication": "c2_append_publish_exports_phase",
            "rollback_before_publication": [43, 44, 30],
        },
        "walker": {
            **PROBE.bind(ROOT / "src/c2_append_plan_walk.s"),
            "isolated_object_bytes": 75,
            "placement": ".lisp65_resident_island",
            "selection": "canonical zero-terminated plan pointer",
        },
        "new_resident_cells": 0,
        "new_roots": 0,
        "required_e000_floor_bytes": 115,
        "retry_policy": "one WPLTO truth run; no retry or shaving",
    }
    recorded["execution_accounting"] = {
        "whole_program_lto_closure_links": closure_links,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    if recorded.get("status", "").startswith("passed"):
        recorded["next_gate"] = (
            "separate Class-C authorization for successor product link")
    else:
        recorded["next_gate"] = (
            "stop and return the measured genuine hot remainder to Class-C review")
    RECEIPT.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-cold-cut-wplto: "
          + ("PASS" if recorded.get("status", "").startswith("passed")
             else "FIRST RED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
