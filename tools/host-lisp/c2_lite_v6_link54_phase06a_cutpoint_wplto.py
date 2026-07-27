#!/usr/bin/env python3
"""One product-shaped WPLTO for the five phase-06a read cutpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link53_first_fault_stamp_wplto as PROBE  # noqa: E402
import c2_phase06a_cutpoint_gate as CUT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link54-phase06a-cutpoint-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link54-phase06a-cutpoint-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link54-phase06a-cutpoint-wplto-base-receipt.json")
RECEIPT = EVIDENCE / "c2.2-link54-phase06a-cutpoint-wplto-receipt.json"
LINK53_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-53-c2-lite-v6-first-fault-stamp/"
    "lisp65-c2-substitution-linked.prg")
LINK53_RECEIPT = EVIDENCE / (
    "c2.2-product-link53-c2-lite-v6-first-fault-stamp-structural-receipt.json")
LINK53_HARDWARE = EVIDENCE / (
    "c2.2-product-link53-first-fault-stamp-hardware-first-red.json")


def authority() -> dict[str, Any]:
    expected = {
        LINK53_PRODUCT:
            "c48913ec561864db00a9ba3c5239912b1d64f8fc9572ee15e0abbfd9779442ce",
        LINK53_RECEIPT:
            "3e5e007771d260e55723c8bbd7f7c3480bfd29b99dfeaab9c5547b46a1b4ea8e",
        LINK53_HARDWARE:
            "55bc7f61b7ee580d4b0029858210eecc07cd507035e3ca2de8e9ccac5e423b53",
        CUT.CONTRACT:
            "52262ba5ab009742fdd30505c39ce136e4f5d932e8d65f7cbff75b451830de4b",
    }
    for path, digest in expected.items():
        PROBE.PROBE.require(path.is_file() and PROBE.PROBE.sha(path) == digest,
                            f"Link-54 cutpoint authority SHA drift: {path}")
    baseline = json.loads(LINK53_RECEIPT.read_text(encoding="utf-8"))
    hardware = json.loads(LINK53_HARDWARE.read_text(encoding="utf-8"))
    gates = baseline["fresh_replacement_gates"]
    PROBE.PROBE.require(
        baseline["status"] ==
            "passed-first-error-stamp-product-identity-hardware-not-run"
        and gates["walls"] == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and gates["capacity"]["session_family_bytes"] == 65438
        and hardware["status"] ==
            "first-error-locked-at-session-slot-5-phase-06a-before-inner-vm",
        "Link-53 capacity or phase-06a hardware authority incomplete")
    return {
        "link53_rollback_product": {**PROBE.PROBE.bind(LINK53_PRODUCT),
                                    "status": "untouched"},
        "link53_structural_authority": PROBE.PROBE.bind(LINK53_RECEIPT),
        "link53_phase06a_hardware_first_red":
            PROBE.PROBE.bind(LINK53_HARDWARE),
        "approved_phase06a_cutpoint_contract": PROBE.PROBE.bind(CUT.CONTRACT),
        "driver": PROBE.PROBE.bind(Path(__file__)),
    }


def main() -> int:
    original = {
        "out": PROBE.OUT,
        "internal": PROBE.INTERNAL,
        "base_receipt": PROBE.BASE_RECEIPT,
        "receipt": PROBE.RECEIPT,
        "authority": PROBE.authority,
    }
    try:
        PROBE.OUT = OUT
        PROBE.INTERNAL = INTERNAL
        PROBE.BASE_RECEIPT = BASE_RECEIPT
        PROBE.RECEIPT = RECEIPT
        PROBE.authority = authority
        result = PROBE.main()
    finally:
        PROBE.OUT = original["out"]
        PROBE.INTERNAL = original["internal"]
        PROBE.BASE_RECEIPT = original["base_receipt"]
        PROBE.RECEIPT = original["receipt"]
        PROBE.authority = original["authority"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    source = CUT.source_gate(mutations=True)
    linked = CUT.linked_gate(elf, ROOT / "tools/llvm-mos/bin/llvm-readobj")
    walls = value["walls"]
    capacity = value["capacity"]
    PROBE.PROBE.require(
        source["status"] == "passed-phase06a-five-read-cutpoint-contract"
        and len(source["negative_mutations"]) == 13
        and source["fixture"]["cases_passed"] == 6
        and linked["status"] == "passed-linked-phase06a-cutpoint-carrier"
        and linked["new_state_objects"] == 0
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536,
        "Link-54 phase-06a cutpoint WPLTO qualification red")
    value["format"] = "lisp65-c2-link54-phase06a-cutpoint-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = "passed-phase06a-five-cutpoint-WPLTO-all-walls-green"
    value["authority"] = authority()
    value["phase06a_cutpoint_source_gate"] = source
    value["phase06a_cutpoint_linked_gate"] = linked
    value["baseline_delta"] = {
        "bank0_text_bytes": 40 - walls["bank0_text_headroom_bytes"],
        "ordinary_bss_bytes": 213 -
            walls["ordinary_bank0_bss_headroom_bytes"],
        "fixed_hot_block_bytes": 33 -
            walls["fixed_hot_block_headroom_bytes"],
        "resident_island_bytes": 5 -
            walls["resident_island_headroom_bytes"],
        "e000_bytes": 58 - walls["e000_headroom_bytes"],
        "session_family_bytes": capacity["session_family_bytes"] - 65438,
    }
    value["phase06a_cutpoint"] = {
        "carrier": "existing c2_stream_context.reserved byte",
        "new_state_bytes": 0,
        "hot_path_delta_bytes": 0,
        "values": [0x61, 0x62, 0x63, 0x64, 0x65],
        "success_handoff": 0x6a,
    }
    value["next_gate"] = "authorized Link-54 product link"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link54-phase06a-cutpoint-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"phase06a={linked['phase06a']['bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PROBE.PROBE.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link54-phase06a-cutpoint-wplto: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
