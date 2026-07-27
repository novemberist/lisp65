#!/usr/bin/env python3
"""Build Link 53 with first-error-wins cold install provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link52_phase_self_stamp_successor_link as BASE  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 53
OUT = ROOT / (
    "build/c2.2/substitution/product-link-53-c2-lite-v6-first-fault-stamp")
RECEIPT = EVIDENCE / (
    "c2.2-product-link53-c2-lite-v6-first-fault-stamp-structural-receipt.json")
WPLTO = EVIDENCE / "c2.2-link53-first-fault-stamp-wplto-receipt.json"
WPLTO_SHA = (
    "0998eb36b316cb0f72bf8d0bc502ba1d4de3af235953b49dafa3babf8ed1acaa")
WPLTO_AUTHORITY = EVIDENCE / (
    "c2.2-link53-first-fault-stamp-wplto-internal-structural.json")
WPLTO_AUTHORITY_SHA = (
    "4f03cee87ba517c4cd505017569705c64e05e78f06a7f6e2f45e815aacd6d055")
WPLTO_SOURCE = ROOT / "build/c2.2/substitution/link53-first-fault-stamp-wplto"
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-52-c2-lite-v6-phase-self-stamp/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "183fb17392eb5c50c30a43cf4ad43cd188731b35dd0218b75b91bbe28725879c")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link52-c2-lite-v6-phase-self-stamp-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "ab77fcce6b380c2f5a988b9837fa6c9fdda8bc0f98bb08e8410ff243147710fe")
HARDWARE = EVIDENCE / (
    "c2.2-product-link52-phase-self-stamp-hardware-first-red.json")
HARDWARE_SHA = (
    "a2b6e6549d2aae5d6d246d80a790d16744d6b409d15c24a1ff23ce62d6504148")
MODE = "link53-c2-lite-v6-first-error-stamp-wins"
SOURCE_BASELINE = "product-link52-phase-self-stamp"
SOURCE_GATE_STATUS = "passed-first-error-stamp-wins-contract"
LINKED_GATE_STATUS = "passed-linked-first-error-stamped-install-provenance"
FINAL_FORMAT = "lisp65-c2-lite-v6-link53-first-fault-stamp-v1"
FINAL_STATUS = "passed-first-error-stamp-product-identity-hardware-not-run"
NEXT_GATE = (
    "Hardware double run: latency presmoke; if BADOPCODE recurs, "
    "capture first_error_session_slot plus trace_flags.")
DRIVER_LABEL = "c2-lite-v6-link53-first-fault-stamp"


class Link53Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link53Error(message)


def validate_authority() -> dict[str, Any]:
    expected = {
        WPLTO: WPLTO_SHA,
        WPLTO_AUTHORITY: WPLTO_AUTHORITY_SHA,
        BASELINE: BASELINE_SHA,
        BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
        HARDWARE: HARDWARE_SHA,
        BASE.PHASE.CONTRACT:
            "e5b274775db560a39c778709aea775f6fef86fbb041c5813fc6ad0b011bf4497",
    }
    for path, digest in expected.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-53 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    structural = json.loads(WPLTO_AUTHORITY.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-first-error-wins-WPLTO-all-walls-green"
        and not qualified["promotable"]
        and qualified["walls"] == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and qualified["capacity"]["session_family_bytes"] == 65438
        and qualified["source_gate"]["status"] ==
            "passed-first-error-stamp-wins-contract"
        and qualified["linked_gate"]["status"] ==
            "passed-linked-first-error-stamped-install-provenance"
        and structural["product_identity"]["product"]["sha256"] ==
            qualified["identity"]["product"]["sha256"],
        "Link-53 first-fault WPLTO authority incomplete")
    qualified = dict(qualified)
    qualified["frozen_identity"] = qualified["identity"]
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 53 is one-shot")
    validate_authority()
    names = (
        "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
        "WPLTO_AUTHORITY", "WPLTO_AUTHORITY_SHA", "WPLTO_SOURCE",
        "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA", "BASELINE_RECEIPT",
        "BASELINE_RECEIPT_SHA", "HARDWARE", "HARDWARE_SHA",
        "validate_authority", "MODE", "SOURCE_BASELINE",
        "SOURCE_GATE_STATUS", "LINKED_GATE_STATUS", "FINAL_FORMAT",
        "FINAL_STATUS", "NEXT_GATE", "DRIVER_LABEL",
    )
    old = {name: getattr(BASE, name) for name in names}
    replacement = {
        "LINK_NUMBER": LINK_NUMBER,
        "OUT": OUT,
        "RECEIPT": RECEIPT,
        "WPLTO": WPLTO,
        "WPLTO_SHA": WPLTO_SHA,
        "WPLTO_AUTHORITY": WPLTO_AUTHORITY,
        "WPLTO_AUTHORITY_SHA": WPLTO_AUTHORITY_SHA,
        "WPLTO_SOURCE": WPLTO_SOURCE,
        "WPLTO_PROFILE": WPLTO_PROFILE,
        "BASELINE": BASELINE,
        "BASELINE_SHA": BASELINE_SHA,
        "BASELINE_RECEIPT": BASELINE_RECEIPT,
        "BASELINE_RECEIPT_SHA": BASELINE_RECEIPT_SHA,
        "HARDWARE": HARDWARE,
        "HARDWARE_SHA": HARDWARE_SHA,
        "validate_authority": validate_authority,
        "MODE": MODE,
        "SOURCE_BASELINE": SOURCE_BASELINE,
        "SOURCE_GATE_STATUS": SOURCE_GATE_STATUS,
        "LINKED_GATE_STATUS": LINKED_GATE_STATUS,
        "FINAL_FORMAT": FINAL_FORMAT,
        "FINAL_STATUS": FINAL_STATUS,
        "NEXT_GATE": NEXT_GATE,
        "DRIVER_LABEL": DRIVER_LABEL,
    }
    try:
        for name, value in replacement.items():
            setattr(BASE, name, value)
        result = BASE.main()
    finally:
        for name, value in old.items():
            setattr(BASE, name, value)
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    phase = gates["install_phase_self_stamp"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536
        and phase["status"] ==
            "passed-linked-first-error-stamped-install-provenance"
        and phase["new_state_objects"] == 0,
        "Link-53 final product qualification red")
    authority = receipt["authority"]
    authority.pop("link51_rollback_product", None)
    authority.pop("link51_badopcode_hardware_capture", None)
    authority["link52_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    authority["link52_cleanup_tombstone_hardware_first_red"] = L.bind(HARDWARE)
    receipt["install_phase_provenance"]["semantics"] = (
        "first-error-slot-wins; cleanup cannot overwrite primary")
    receipt["install_phase_provenance"]["trace_flags"] = {
        "inner_vm_entered_bit": 1, "primary_locked_bit": 128}
    receipt["counters"] = {
        "class_b_diagnostic_cycles": "3/3 closed",
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link53-first-fault-stamp: COMPLETE "
          f"product={L.sha(product)} text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link53Error, BASE.Link52Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link53-first-fault-stamp: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
