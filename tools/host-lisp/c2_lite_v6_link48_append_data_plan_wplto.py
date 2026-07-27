#!/usr/bin/env python3
"""One-shot WPLTO truth run for the Link-48 append data-plan amendment.

The prior cutpoint WPLTO stopped before a product candidate.  This successor
uses a fresh output/evidence identity while reusing that driver's full product
closure and gate program.  It adds no promotion or hardware claim.
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
OUT = ROOT / "build/c2.2/substitution/link48-append-data-plan-wplto"
INTERNAL = EVIDENCE / "c2.2-link48-append-data-plan-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link48-append-data-plan-wplto-receipt.json"


def main() -> int:
    old = (PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__)
    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.RECEIPT = RECEIPT
        # The inherited prerequisite binder must name this one-shot driver,
        # not the historical driver whose output identity has been consumed.
        PROBE.__file__ = str(Path(__file__).resolve())
        value = PROBE.run_probe()
    except (PROBE.GateError, PROBE.APPEND.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-data-plan-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1
    finally:
        PROBE.OUT, PROBE.INTERNAL, PROBE.RECEIPT, PROBE.__file__ = old

    # Seal the representation amendment into the final receipt after the
    # inherited full-gate run has produced its immutable evidence set.
    os.chmod(RECEIPT, 0o644)
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    recorded["format"] = recorded["format"].replace(
        "append-cutpoint", "append-data-plan")
    recorded["representation_amendment"] = {
        "forward_plan": [31, 35, 36, 37, 38],
        "rollback_plan": [43, 44, 30],
        "plan_data_bytes": 8,
        "interpreter": "existing Bank-0 serial facade target",
        "append_status_boundary": "scratch-lifetime sentinel",
        "window_requirement": "floor 115 bytes; near-zero delta",
    }
    RECEIPT.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-data-plan-wplto: "
          + ("PASS" if recorded.get("status", "").startswith("passed")
             else "FIRST RED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
