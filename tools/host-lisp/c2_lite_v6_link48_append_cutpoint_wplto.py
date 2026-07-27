#!/usr/bin/env python3
"""Product-shaped WPLTO for Link-48 append plans and BADOPCODE detail.

The probe starts from immutable product Link 48.  It replaces the two phase
range assumptions with named plans, binds the exact 119-byte zero-literal
fixture to those plans, and qualifies the two-byte first-failure detail seam.
It creates no promotable product and runs no hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_phase_plan_gate as APPEND  # noqa: E402
import c2_lite_v6_link47_l65e_transient_successor_link as BASE  # noqa: E402
import c2_zero_literal_execution_gate as ZERO  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-48-c2-lite-v6-zero-literal-execution")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link48-c2-lite-v6-zero-literal-execution-"
    "structural-receipt.json")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")
ROLLBACK_FIRST_RED = EVIDENCE / (
    "c2.2-product-link48-append-rollback-order-first-red.json")
OUT = ROOT / "build/c2.2/substitution/link48-append-cutpoint-wplto"
INTERNAL = EVIDENCE / "c2.2-link48-append-cutpoint-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link48-append-cutpoint-wplto-receipt.json"

BASE_PRODUCT_SHA = (
    "1b7f7309a415d113a0d8718805e8c860ff3583b82ee2037dfae9dac5f7f5eae6")
BASE_RECEIPT_SHA = (
    "867bd59ff9c669e98b4969062eeb0dfd39b0fb633f21dd3e19f067fedb3c7f25")
HARDWARE_FIRST_RED_SHA = (
    "f9f17db39694c973968581ac657c1d70fda95c4dd63fc5a81f89b0088864b3a6")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-48 append authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    require(baseline["link_number"] == 48
            and baseline["product_identity"]["product"]["sha256"] ==
                BASE_PRODUCT_SHA,
            "Link-48 rollback product is not authoritative")
    require(first_red["status"] ==
                "first-red-product-semantics-review-required"
            and first_red["accounting"]["line_1_status"] == "passed"
            and first_red["accounting"]["line_1_product_first_red_budget"] ==
                "2/3 unchanged"
            and first_red["accounting"]["completed_latency_measurements"] ==
                "0/2 unchanged",
            "Link-48 append hardware First Red or counters drift")
    return {
        "link48_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link48_structural_authority": bind(BASE_RECEIPT),
        "link48_append_hardware_first_red": bind(HARDWARE_FIRST_RED),
        "historical_rollback_first_red": bind(ROLLBACK_FIRST_RED),
        "append_cutpoint_contract": bind(APPEND.CONTRACT),
        "append_cutpoint_gate": bind(Path(APPEND.__file__)),
        "canonical_product_profile": BASE.PROFILE.check(),
        "driver": bind(Path(__file__)),
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "Link-48 append-cutpoint WPLTO is one-shot")
    old = {
        "out": BASE.OUT, "receipt": BASE.RECEIPT,
        "number": BASE.LINK_NUMBER,
        "wplto": BASE.WPLTO_REPLAY,
        "wplto_sha": BASE.WPLTO_REPLAY_SHA,
        "prerequisites": BASE.prerequisites,
        "base_product": BASE.PROBE.BASE_PRODUCT,
        "base_product_sha": BASE.PROBE.BASE_PRODUCT_SHA,
        "base_receipt": BASE.PROBE.BASE_RECEIPT,
        "base_receipt_sha": BASE.PROBE.BASE_RECEIPT_SHA,
        "hardware_first_red": BASE.PROBE.HARDWARE_FIRST_RED,
        "hardware_first_red_sha": BASE.PROBE.HARDWARE_FIRST_RED_SHA,
        "transient_source": BASE.TRANSIENT.source_gate,
        "transient_linked": BASE.TRANSIENT.linked_gate,
        "single_link": BASE.LINK44.P.single_link,
    }

    def transient_source(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = old["transient_source"](*args, **kwargs)
        value["zero_literal_execution"] = ZERO.source_gate(
            generated_runtime=kwargs.get("generated_runtime"))
        value["append_phase_plan"] = APPEND.source_gate()
        return value

    def transient_linked(elf: Path) -> dict[str, Any]:
        value = old["transient_linked"](elf)
        c2d = OUT / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin"
        value["zero_literal_execution"] = ZERO.linked_gate(elf, c2d)
        value["append_phase_plan"] = APPEND.linked_gate(elf)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(
            line for line in kwargs.get("extra_contract_lines", ())
            if not line.startswith(("mode=", "source_baseline=",
                                    "promotable=",
                                    "line1_first_red_budget=",
                                    "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link48-append-phase-plan-cutpoint-wplto",
            "source_baseline=product-link48-zero-literal-execution",
            "promotable=no-capacity-placement-probe-only",
            "forward_phase_plan=31,35,36,37,38",
            "rollback_phase_plan=43,44,30",
            "badopcode_detail=two-existing-scratch-bytes-first-failure-wins",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.OUT = OUT
        BASE.RECEIPT = INTERNAL
        BASE.LINK_NUMBER = 48
        BASE.WPLTO_REPLAY = BASE_RECEIPT
        BASE.WPLTO_REPLAY_SHA = BASE_RECEIPT_SHA
        BASE.prerequisites = prerequisites
        BASE.PROBE.BASE_PRODUCT = BASE_PRODUCT
        BASE.PROBE.BASE_PRODUCT_SHA = BASE_PRODUCT_SHA
        BASE.PROBE.BASE_RECEIPT = BASE_RECEIPT
        BASE.PROBE.BASE_RECEIPT_SHA = BASE_RECEIPT_SHA
        BASE.PROBE.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = HARDWARE_FIRST_RED_SHA
        BASE.TRANSIENT.source_gate = transient_source
        BASE.TRANSIENT.linked_gate = transient_linked
        BASE.LINK44.P.single_link = single_link
        result = BASE.main()
    finally:
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.LINK_NUMBER = old["number"]
        BASE.WPLTO_REPLAY = old["wplto"]
        BASE.WPLTO_REPLAY_SHA = old["wplto_sha"]
        BASE.prerequisites = old["prerequisites"]
        BASE.PROBE.BASE_PRODUCT = old["base_product"]
        BASE.PROBE.BASE_PRODUCT_SHA = old["base_product_sha"]
        BASE.PROBE.BASE_RECEIPT = old["base_receipt"]
        BASE.PROBE.BASE_RECEIPT_SHA = old["base_receipt_sha"]
        BASE.PROBE.HARDWARE_FIRST_RED = old["hardware_first_red"]
        BASE.PROBE.HARDWARE_FIRST_RED_SHA = old["hardware_first_red_sha"]
        BASE.TRANSIENT.source_gate = old["transient_source"]
        BASE.TRANSIENT.linked_gate = old["transient_linked"]
        BASE.LINK44.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-link48-append-cutpoint-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: append-cutpoint WPLTO stopped",
            "promotable": False,
            "internal_receipt": bind(INTERNAL),
            "link48_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0, "hardware_runs": 0},
            "next_gate": "stop; return measured First Red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return value

    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    gates = internal["fresh_replacement_gates"]
    lookup = gates["transient_execution_lookup"]
    append_source = lookup["source"]["append_phase_plan"]
    append_linked = lookup["linked"]["append_phase_plan"]
    zero_source = lookup["source"]["zero_literal_execution"]
    zero_linked = lookup["linked"]["zero_literal_execution"]
    walls, capacity = gates["walls"], gates["capacity"]
    require(
        append_source["status"] == "passed-append-cutpoint-contract"
        and append_linked["status"] ==
            "passed-linked-cutpoint-citizenship"
        and zero_source["generated_sources"]["status"] ==
            "passed-generated-zero-literal-reader"
        and zero_linked["status"] ==
            "passed-linked-vm-run-dir-zero-literal-chain"
        and walls["e000_headroom_bytes"] >=
            BASE.LINK44.P.E000_FINAL_FLOOR_BYTES
        and all(int(walls[name]) >= 0 for name in (
            "bank0_text_headroom_bytes",
            "ordinary_bank0_bss_headroom_bytes",
            "fixed_hot_block_headroom_bytes",
            "resident_island_headroom_bytes"))
        and capacity["session_family_bytes"] <= 65536,
        "append-cutpoint WPLTO did not complete fully green")
    product = ROOT / internal["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-link48-append-cutpoint-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
        "promotable": False,
        "claim_limit": (
            "Source/mutation fixtures, exact 119-byte oracle, final ELF and "
            "WPLTO placement only; no hardware result inherited."),
        "authority": prerequisites(),
        "append_phase_plan": {"source": append_source,
                              "linked": append_linked},
        "zero_literal_execution": {"source": zero_source,
                                   "linked": zero_linked},
        "walls": walls,
        "capacity": capacity,
        "product_shaped_identity": {**bind(product), "nonpromotable": True},
        "internal_structural_receipt": bind(INTERNAL),
        "link48_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0, "hardware_runs": 0},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "authorized successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link48-append-cutpoint-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"fixed={walls['fixed_hot_block_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} "
          "promotable=no hardware=not-run")
    return value


def main() -> int:
    try:
        run_probe()
        return 0
    except (GateError, APPEND.GateError, OSError, RuntimeError,
            ValueError) as error:
        print("c2-lite-v6-link48-append-cutpoint-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
