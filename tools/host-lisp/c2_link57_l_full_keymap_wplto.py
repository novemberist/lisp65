#!/usr/bin/env python3
"""One product-shaped WPLTO for the canonical L-full keymap consumer.

This is a qualification link only.  It emits no promotable product identity
and performs no hardware action.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l_full_keymap_end_to_end_gate as KEYGATE  # noqa: E402
import c2_link56_selector_tail_z_wplto as BASE  # noqa: E402


P = BASE.P
BASE_AUTHORITY = BASE.authority
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link57-l-full-keymap-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link57-l-full-keymap-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-wplto-base-receipt.json")
HARNESS_FIRST_RED = EVIDENCE / (
    "c2.2-link57-l-full-keymap-wplto-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link57-l-full-keymap-wplto-replay-receipt.json")
LINK56 = ROOT / (
    "build/c2.2/substitution/product-link-56-selector-tail-z/"
    "lisp65-c2-substitution-linked.prg")
LINK56_RECEIPT = EVIDENCE / (
    "c2.2-product-link56-selector-tail-z-structural-receipt.json")
LATENCY = ROOT / (
    "build/c2.2/hardware-presmoke-link56-selector-tail-z/latency/result.json")


class WPLTOError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WPLTOError(message)


def write_receipt(value: dict[str, Any]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)


def authority() -> dict[str, Any]:
    base = BASE_AUTHORITY()
    expected = {
        LINK56:
            "723579250e692112d4208ae56c0eede15f422858b3f99cc9cd2af1639599d93d",
        LINK56_RECEIPT:
            "81b45bb16c4b4d5861aafd1dd44e1b76a98111818eba4e62e472163c1b485d7b",
        LATENCY:
            "800b96bfee2066749e9895dd56a3ca74f32bdcb26d43c3c65e97f7725c042939",
    }
    for path, digest in expected.items():
        require(path.is_file() and P.sha(path) == digest,
                f"L-full WPLTO authority drift: {path}")
    latency = json.loads(LATENCY.read_text(encoding="utf-8"))
    harness_red = json.loads(HARNESS_FIRST_RED.read_text(encoding="utf-8"))
    require(
        latency["status"] == "first-red-receipt-less"
        and latency["measurement"]["boot_to_repl"]["frames"] == 941
        and latency["measurement"]["definition_first_call"]["frames"] == 60
        and latency["measurement"]["warm_second_call"]["frames"] == 61,
        "Link-56 latency authority is incomplete",
    )
    require(
        harness_red["status"] ==
            "HARNESS FIRST RED: L-full keymap WPLTO not started"
        and harness_red["error"] == "maximum recursion depth exceeded"
        and harness_red["execution_accounting"] == {
            "hardware_runs": 0,
            "promotable_product_links": 0,
            "whole_program_lto_closure_links": 0,
        }
        and harness_red["internal_receipt"] is None
        and harness_red["base_receipt"] is None
        and not OUT.exists(),
        "Class-A wrapper First Red did not stop before WPLTO",
    )
    return {
        **base,
        "link56_product_baseline": {
            **P.bind(LINK56), "status": "untouched"},
        "link56_structural_authority": P.bind(LINK56_RECEIPT),
        "link56_latency_attempt_1_of_2": P.bind(LATENCY),
        "class_A_wrapper_first_red": P.bind(HARNESS_FIRST_RED),
        "canonical_keymap_contract": P.bind(KEYGATE.CONTRACT),
        "keymap_cross_check": P.bind(KEYGATE.CROSS_CHECK),
        "generated_product_consumer": P.bind(KEYGATE.GENERATED),
        "queue_to_action_gate": P.bind(Path(KEYGATE.__file__)),
        "kernal_unmap_contract": P.bind(
            ROOT / "config/c2-kernal-unmap-contract.json"),
        "driver": P.bind(Path(__file__)),
    }


def main() -> int:
    require(not OUT.exists() and not INTERNAL.exists()
            and not BASE_RECEIPT.exists() and not RECEIPT.exists(),
            "L-full keymap WPLTO is one-shot")
    auth = authority()
    source_gate = KEYGATE.validate(KEYGATE.source_bundle(), run_oracle=True)
    source_gate["mutations_rejected"] = KEYGATE.mutation_tests(
        KEYGATE.source_bundle())
    original = {
        "out": BASE.OUT,
        "internal": BASE.INTERNAL,
        "base_receipt": BASE.BASE_RECEIPT,
        "receipt": BASE.RECEIPT,
        "authority": BASE.authority,
    }
    try:
        BASE.OUT = OUT
        BASE.INTERNAL = INTERNAL
        BASE.BASE_RECEIPT = BASE_RECEIPT
        BASE.RECEIPT = RECEIPT
        BASE.authority = authority
        result = BASE.main()
    except Exception as error:
        result = 2
        detail = str(error)
    else:
        detail = None
    finally:
        BASE.OUT = original["out"]
        BASE.INTERNAL = original["internal"]
        BASE.BASE_RECEIPT = original["base_receipt"]
        BASE.RECEIPT = original["receipt"]
        BASE.authority = original["authority"]

    if result != 0:
        if detail is None:
            detail = "Link-50 final product qualification red"
        if RECEIPT.exists():
            os.chmod(RECEIPT, 0o644)
        write_receipt({
            "format": "lisp65-c2-link57-l-full-keymap-wplto-first-red-v1",
            "recorded_on": "2026-07-23",
            "status": (
                "FIRST RED: historical Link-50 checker stopped "
                "L-full keymap WPLTO"),
            "promotable": False,
            "authority": auth,
            "queue_to_action_gate": source_gate,
            "error": detail,
            "internal_receipt": P.bind(INTERNAL)
                if INTERNAL.is_file() else None,
            "base_receipt": P.bind(BASE_RECEIPT)
                if BASE_RECEIPT.is_file() else None,
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0,
                "hardware_runs": 0,
            },
            "latency_accounting": {
                "completed_measurements": "1/2",
                "this_probe_consumed_measurements": 0,
            },
            "next_gate": "stop; return measured First Red to Class-C review",
        })
        return 2

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    walls = value["walls"]
    capacity = value["capacity"]
    require(
        source_gate["status"] ==
            "passed-queue-tuple-to-compiled-product-action"
        and source_gate["mutations_rejected"] == 10
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] <= 65536,
        "L-full keymap WPLTO crossed a bound wall",
    )
    value["format"] = "lisp65-c2-link57-l-full-keymap-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = (
        "passed-L-full-keymap-end-to-end-WPLTO-all-walls-green")
    value["promotable"] = False
    value["authority"] = authority()
    value["queue_to_action_gate"] = source_gate
    value["execution_accounting"] = {
        "whole_program_lto_closure_links": 1,
        "promotable_product_links": 0,
        "hardware_runs": 0,
    }
    value["latency_accounting"] = {
        "completed_measurements": "1/2",
        "this_probe_consumed_measurements": 0,
    }
    value["next_gate"] = (
        "separate Class-C authorization for the successor product link")
    write_receipt(value)
    print(
        "c2-link57-l-full-keymap-wplto: PASS "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} "
        f"session={capacity['session_family_bytes']} "
        "keymap=2/2 mutations=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        WPLTOError,
        KEYGATE.GateError,
        KEYGATE.KEYMAP.KeymapError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print("c2-link57-l-full-keymap-wplto: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
