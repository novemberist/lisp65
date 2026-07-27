#!/usr/bin/env python3
"""One product-shaped WPLTO for first-error-wins install provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link52_install_phase_wplto as PROBE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = ROOT / "build/c2.2/substitution/link53-first-fault-stamp-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link53-first-fault-stamp-wplto-internal-structural.json")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-link53-first-fault-stamp-wplto-base-receipt.json")
RECEIPT = EVIDENCE / "c2.2-link53-first-fault-stamp-wplto-receipt.json"
LINK52_PRODUCT = ROOT / (
    "build/c2.2/substitution/product-link-52-c2-lite-v6-phase-self-stamp/"
    "lisp65-c2-substitution-linked.prg")
LINK52_RECEIPT = EVIDENCE / (
    "c2.2-product-link52-c2-lite-v6-phase-self-stamp-structural-receipt.json")
LINK52_HARDWARE = EVIDENCE / (
    "c2.2-product-link52-phase-self-stamp-hardware-first-red.json")


def authority() -> dict[str, Any]:
    expected = {
        LINK52_PRODUCT:
            "183fb17392eb5c50c30a43cf4ad43cd188731b35dd0218b75b91bbe28725879c",
        LINK52_RECEIPT:
            "ab77fcce6b380c2f5a988b9837fa6c9fdda8bc0f98bb08e8410ff243147710fe",
        LINK52_HARDWARE:
            "a2b6e6549d2aae5d6d246d80a790d16744d6b409d15c24a1ff23ce62d6504148",
    }
    for path, digest in expected.items():
        PROBE.require(path.is_file() and PROBE.sha(path) == digest,
                      f"Link-53 first-fault authority SHA drift: {path}")
    baseline = json.loads(LINK52_RECEIPT.read_text(encoding="utf-8"))
    hardware = json.loads(LINK52_HARDWARE.read_text(encoding="utf-8"))
    gates = baseline["fresh_replacement_gates"]
    PROBE.require(
        baseline["status"] ==
            "passed-new-phase-self-stamp-product-identity-hardware-not-run"
        and gates["walls"] == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and gates["capacity"]["session_family_bytes"] == 65438
        and hardware["status"] ==
            "first-red-before-inner-vm-after-successful-definition",
        "Link-52 capacity or hardware First Red authority incomplete")
    return {
        "link52_rollback_product": {**PROBE.bind(LINK52_PRODUCT),
                                    "status": "untouched"},
        "link52_structural_authority": PROBE.bind(LINK52_RECEIPT),
        "link52_cleanup_tombstone_hardware_first_red":
            PROBE.bind(LINK52_HARDWARE),
        "approved_first_fault_contract": PROBE.bind(PROBE.CONTRACT),
        "driver": PROBE.bind(Path(__file__)),
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
    walls = value["walls"]
    capacity = value["capacity"]
    PROBE.require(
        value["source_gate"]["status"] ==
            "passed-first-error-stamp-wins-contract"
        and value["linked_gate"]["status"] ==
            "passed-linked-first-error-stamped-install-provenance"
        and len(value["source_gate"]["negative_mutations"]) == 15
        and value["source_gate"]["fixture"]["cases_passed"] == 13
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_family_bytes"] <= 65536,
        "Link-53 first-fault WPLTO qualification red")
    value["format"] = "lisp65-c2-link53-first-fault-stamp-wplto-v1"
    value["recorded_on"] = "2026-07-23"
    value["status"] = "passed-first-error-wins-WPLTO-all-walls-green"
    value["authority"] = authority()
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
    value["first_error_precedence"] = {
        "storage_bytes": 0,
        "resident_stores_added": 0,
        "local_cleanup_lock": "rollback_unpublish-before-own-stamp",
        "nonlocal_cleanup_lock": "abort_control-before-own-stamp",
        "inner_transition": "sets-inner-and-lock-in-existing-store",
    }
    value["next_gate"] = "authorized Link-53 product link"
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link53-first-fault-stamp-wplto: PASS "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PROBE.ProbeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link53-first-fault-stamp-wplto: FAIL: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
