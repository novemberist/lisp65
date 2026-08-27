#!/usr/bin/env python3
"""Class-A-corrected successor for the unconsumed first C2-lite link.

The first driver stopped before source projection and before every product
closure link because it invoked the historical C2D-v5 object-size pin.  That
pin describes the retired v5 residence layout, not a C2-lite invariant.  This
successor retains the permanent B2 semantic and current-source invariants and
then delegates the unchanged one-link product program to the original driver.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_first_product_link as LINK  # noqa: E402


FIRST_RED = LINK.RECEIPT
FIRST_RED_SHA = ""
OUT = ROOT / "build/c2.2/substitution/product-link-37-c2-lite-v6-successor"
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-successor-structural-receipt.json")
DIAGNOSIS = LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-v5-prelink-harness-diagnosis.json")


def current_b2_gate(out: Path) -> dict[str, Any]:
    """Keep B2 truth without treating a retired v5 layout as C2-lite ABI."""
    out.mkdir(parents=True, exist_ok=True)
    interrupt = LINK.BASE.PRE.INTERRUPT.read_text(encoding="utf-8")
    runtime = LINK.BASE.PRE.SOURCE.read_text(encoding="utf-8")
    repl = (ROOT / "src/repl.c").read_text(encoding="utf-8")
    jump = LINK.BASE.PRE.function_body(interrupt, "lisp_abort_jump")
    poll = LINK.BASE.PRE.function_body(interrupt, "lisp_poll")
    cleanup = LINK.BASE.PRE.function_body(runtime, "c2_product_abort_cleanup")
    recover = LINK.BASE.PRE.function_body(runtime, "c2_product_abort_recover")
    landing = LINK.BASE.PRE.function_body(repl, "repl")
    checks = {
        "one_central_cleanup_before_longjmp":
            jump.count("c2_product_abort_cleanup()") == 1
            and jump.find("c2_product_abort_cleanup()") < jump.find("longjmp("),
        "run_stop_uses_common_abort_surface":
            poll.count("lisp_abort_static(LISP65_ERR_STOPPED") >= 1,
        "cleanup_first_closes_overlay_transaction":
            "vm_runtime_overlay_abort_cleanup()" in cleanup,
        "cleanup_does_not_run_c2j_on_failing_stack":
            "c2_abort_driver" not in cleanup,
        "restored_landing_runs_single_c2j_driver":
            recover.count("c2_abort_driver") >= 1
            and landing.count("c2_product_abort_recover()") == 1
            and landing.find("if (setjmp(lisp_toplevel))")
                < landing.find("c2_product_abort_recover()")
                < landing.find("lisp65_error_render_pending()"),
    }
    LINK.require(all(checks.values()),
                 "current C2-lite B2 source gate red: "
                 + str([name for name, value in checks.items() if not value]))
    model = LINK.BASE.PRE.b2_model_gate()
    LINK.require(model["status"] == "passed" and model["cases"] == 18,
                 "current C2-lite B2 semantic matrix red")
    value = {
        "status": "passed-prelink-product-link-not-run",
        "scope": "C2-lite current-source B2 seam plus permanent semantic model",
        "retired_check": (
            "C2D-v5 EXPECTED_RUNTIME and EXPECTED_SIZES object-byte pins; "
            "those layout numbers are not C2-lite execution-contract fields"),
        "b2_source": {"status": "passed", "checks": checks},
        "b2_model": model,
        "product_links": 0,
    }
    LINK.write_json(out / "c2-lite-current-b2-prelink.json", value)
    return value


def record_diagnosis() -> None:
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    LINK.require(first["status"] ==
                 "FIRST RED: first C2-lite product link stopped"
                 and first["diagnostic"]["message"] ==
                 "resident/source-object size drift: "
                 ".lisp65_c2_kernal_window.c2_resident=6528"
                 and first["execution_accounting"]["product_closure_links"] == 0,
                 "historical prelink First Red drift")
    value = {
        "format": "lisp65-c2-lite-v6-v5-prelink-harness-disposition-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-class-a-harness-disposition-product-link-unconsumed",
        "class": "A",
        "first_red": LINK.bind(FIRST_RED),
        "diagnosis": {
            "historical_gate": "c2_nested_append_v5_prelink.check",
            "historical_contract": "C2D-v5 fixed source-object and phase sizes",
            "observed_stop": "resident c2 section 6528 B vs retired v5 pin 6518 B",
            "why_not_product_evidence": (
                "The stop preceded C2-lite generated-source projection and all "
                "product closure links; it measured the unprojected v5-shaped "
                "translation unit against a retired layout pin."),
            "retained_truth": (
                "The 18-case RUN/STOP/C2J model and current shared abort-source "
                "seam run freshly; actual slice capacity and overlay closure are "
                "proved on the linked v6 ELF."),
        },
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "product_links": 0, "hardware_runs": 0},
        "authorization_effect": (
            "The exactly-one first C2-lite product-link authorization remains "
            "unconsumed."),
    }
    LINK.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)


def main() -> int:
    LINK.require(FIRST_RED.is_file() and not OUT.exists()
                 and not RECEIPT.exists() and not DIAGNOSIS.exists(),
                 "C2-lite Link-37 successor state is not one-shot")
    record_diagnosis()
    old_out = LINK.OUT
    old_receipt = LINK.RECEIPT
    old_check = LINK.BASE.PRE.check
    old_prerequisites = LINK.prerequisites

    def prerequisites() -> dict[str, Any]:
        value = old_prerequisites()
        value["class_a_v5_prelink_disposition"] = LINK.bind(DIAGNOSIS)
        value["successor_driver"] = LINK.bind(Path(__file__))
        return value

    try:
        LINK.OUT = OUT
        LINK.RECEIPT = RECEIPT
        LINK.BASE.PRE.check = current_b2_gate
        LINK.prerequisites = prerequisites
        value = LINK.build()
    finally:
        LINK.OUT = old_out
        LINK.RECEIPT = old_receipt
        LINK.BASE.PRE.check = old_check
        LINK.prerequisites = old_prerequisites
    print("c2-lite-v6-first-product-link-successor: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
