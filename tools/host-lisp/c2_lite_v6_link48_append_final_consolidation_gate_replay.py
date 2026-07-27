#!/usr/bin/env python3
"""Resume the authorized consolidation after a zero-link preflight red.

The predecessor identity stopped in the historical roots/fronts source gate
before a compiler or linker ran.  This identity preserves that First Red and
consumes the still-unused, exactly-one WPLTO authorization.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link48_append_final_consolidation_wplto as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link48-append-final-consolidation-wplto-gate-replay")
INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-gate-replay-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-gate-replay-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-receipt.json")
FIRST_RED_INTERNAL = EVIDENCE / (
    "c2.2-link48-append-final-consolidation-wplto-internal.json")


def main() -> int:
    BASE.require(FIRST_RED.is_file() and FIRST_RED_INTERNAL.is_file(),
                 "zero-link preflight First Red is absent")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    first_red_internal = json.loads(
        FIRST_RED_INTERNAL.read_text(encoding="utf-8"))
    BASE.require(
        first_red["status"].startswith("FIRST RED")
        and first_red_internal["execution_accounting"]
            ["product_closure_links"] == 0
        and first_red_internal["diagnostic"]["message"] ==
            "roots/fronts source contract red: "
            "['marker_reuses_dead_source_byte']",
        "preflight red was not the qualified zero-link checker-model stop")
    BASE.require(not OUT.exists() and not INTERNAL.exists()
                 and not RECEIPT.exists(),
                 "final consolidation gate replay is one-shot")

    old = BASE.OUT, BASE.INTERNAL, BASE.RECEIPT, BASE.__file__
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.RECEIPT = RECEIPT
        BASE.__file__ = str(Path(__file__).resolve())
        result = BASE.main()
    finally:
        BASE.OUT, BASE.INTERNAL, BASE.RECEIPT, BASE.__file__ = old

    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o644)
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
        value["zero_link_preflight_model_first_red"] = {
            "receipt": BASE.PROBE.bind(FIRST_RED),
            "internal": BASE.PROBE.bind(FIRST_RED_INTERNAL),
            "product_closure_links": 0,
            "disposition": (
                "historical exact-spelling gate now accepts the exact shared "
                "record[23] authority; product source and capacity unchanged"),
        }
        value["execution_accounting_correction"] = {
            "preflight_product_closure_links": 0,
            "this_identity_is_the_only_actual_wplto": True,
        }
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BASE.PROBE.GateError, BASE.PROBE.APPEND.GateError,
            BASE.CONS.GateError, BASE.PROFILE.ProfileError,
            OSError, RuntimeError, ValueError, KeyError) as error:
        print("c2-lite-v6-link48-append-final-consolidation-gate-replay: "
              "FAIL: " + str(error), file=sys.stderr)
        raise SystemExit(1)
