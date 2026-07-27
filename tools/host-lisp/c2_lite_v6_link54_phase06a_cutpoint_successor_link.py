#!/usr/bin/env python3
"""Build Link 54 with five cold phase-06a read cutpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link53_first_fault_stamp_successor_link as BASE  # noqa: E402
import c2_phase06a_cutpoint_gate as CUT  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 54
OUT = ROOT / (
    "build/c2.2/substitution/product-link-54-c2-lite-v6-phase06a-cutpoint")
RECEIPT = EVIDENCE / (
    "c2.2-product-link54-c2-lite-v6-phase06a-cutpoint-structural-receipt.json")
WPLTO = EVIDENCE / "c2.2-link54-phase06a-cutpoint-wplto-receipt.json"
WPLTO_SHA = (
    "a09b143e8ee67c4386c66a455f6dd084eb87dc7777dd327e282fb40bafbfdeaa")
WPLTO_AUTHORITY = EVIDENCE / (
    "c2.2-link54-phase06a-cutpoint-wplto-internal-structural.json")
WPLTO_AUTHORITY_SHA = (
    "f4cf9dc7c3e77137dcef63f8d5dd5349eacb0300b36bf891f01a980e002ab9c1")
WPLTO_SOURCE = ROOT / "build/c2.2/substitution/link54-phase06a-cutpoint-wplto"
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-53-c2-lite-v6-first-fault-stamp/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "c48913ec561864db00a9ba3c5239912b1d64f8fc9572ee15e0abbfd9779442ce")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link53-c2-lite-v6-first-fault-stamp-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "3e5e007771d260e55723c8bbd7f7c3480bfd29b99dfeaab9c5547b46a1b4ea8e")
HARDWARE = EVIDENCE / (
    "c2.2-product-link53-first-fault-stamp-hardware-first-red.json")
HARDWARE_SHA = (
    "55bc7f61b7ee580d4b0029858210eecc07cd507035e3ca2de8e9ccac5e423b53")


class Link54Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link54Error(message)


def validate_authority() -> dict[str, Any]:
    expected = {
        WPLTO: WPLTO_SHA,
        WPLTO_AUTHORITY: WPLTO_AUTHORITY_SHA,
        BASELINE: BASELINE_SHA,
        BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
        HARDWARE: HARDWARE_SHA,
        CUT.CONTRACT:
            "52262ba5ab009742fdd30505c39ce136e4f5d932e8d65f7cbff75b451830de4b",
    }
    for path, digest in expected.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-54 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    structural = json.loads(WPLTO_AUTHORITY.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-phase06a-five-cutpoint-WPLTO-all-walls-green"
        and not qualified["promotable"]
        and qualified["walls"] == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and qualified["capacity"]["session_family_bytes"] == 65438
        and qualified["phase06a_cutpoint_source_gate"]["status"] ==
            "passed-phase06a-five-read-cutpoint-contract"
        and qualified["phase06a_cutpoint_linked_gate"]["status"] ==
            "passed-linked-phase06a-cutpoint-carrier"
        and structural["product_identity"]["product"]["sha256"] ==
            qualified["identity"]["product"]["sha256"],
        "Link-54 phase-06a cutpoint WPLTO authority incomplete")
    qualified = dict(qualified)
    qualified["frozen_identity"] = qualified["identity"]
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 54 is one-shot")
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
    hook_owner = BASE.BASE
    hook_names = (
        "EXTRA_SOURCE_GATE_KEY", "EXTRA_SOURCE_GATE",
        "EXTRA_LINKED_GATE_KEY", "EXTRA_LINKED_GATE",
        "EXTRA_CONTRACT_LINES",
    )
    old_hooks = {name: getattr(hook_owner, name) for name in hook_names}
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
        "MODE": "link54-c2-lite-v6-phase06a-five-cutpoints",
        "SOURCE_BASELINE": "product-link53-first-error-stamp",
        "SOURCE_GATE_STATUS": "passed-first-error-stamp-wins-contract",
        "LINKED_GATE_STATUS":
            "passed-linked-first-error-stamped-install-provenance",
        "FINAL_FORMAT": "lisp65-c2-lite-v6-link54-phase06a-cutpoint-v1",
        "FINAL_STATUS":
            "passed-phase06a-five-cutpoint-product-identity-hardware-not-run",
        "NEXT_GATE": (
            "Hardware double run: cold defun/call plus latency presmoke; "
            "on ERR_IO read the phase-06a reserved-byte cutpoint."),
        "DRIVER_LABEL": "c2-lite-v6-link54-phase06a-cutpoint",
    }
    try:
        for name, value in replacement.items():
            setattr(BASE, name, value)
        hook_owner.EXTRA_SOURCE_GATE_KEY = "phase06a_cutpoint_source"
        hook_owner.EXTRA_SOURCE_GATE = lambda: CUT.source_gate(mutations=True)
        hook_owner.EXTRA_LINKED_GATE_KEY = "phase06a_cutpoint"
        hook_owner.EXTRA_LINKED_GATE = CUT.linked_gate
        hook_owner.EXTRA_CONTRACT_LINES = (
            "phase06a_cutpoints=61,62,63,64,65",
            "phase06a_success_handoff=6a",
            "phase06a_cutpoint_state_delta=0",
        )
        result = BASE.main()
    finally:
        for name, value in old.items():
            setattr(BASE, name, value)
        for name, value in old_hooks.items():
            setattr(hook_owner, name, value)
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    gates = receipt["fresh_replacement_gates"]
    prelink = receipt["fresh_prelink_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    cutpoint = gates["phase06a_cutpoint"]
    source = prelink["phase06a_cutpoint_source"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and source["status"] == "passed-phase06a-five-read-cutpoint-contract"
        and len(source["negative_mutations"]) == 13
        and cutpoint["status"] == "passed-linked-phase06a-cutpoint-carrier"
        and cutpoint["new_state_objects"] == 0
        and cutpoint["phase06a"]["bytes"] <= 1792
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and capacity["session_family_bytes"] <= 65536,
        "Link-54 final product qualification red")
    authority = receipt["authority"]
    authority.pop("link52_rollback_product", None)
    authority.pop("link52_cleanup_tombstone_hardware_first_red", None)
    authority["link53_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    authority["link53_phase06a_hardware_first_red"] = L.bind(HARDWARE)
    authority["phase06a_cutpoint_wplto"] = L.bind(WPLTO)
    authority["phase06a_cutpoint_structural_truth"] = L.bind(WPLTO_AUTHORITY)
    receipt["phase06a_cutpoint"] = {
        "contract": L.bind(CUT.CONTRACT),
        "source_gate": source,
        "linked_gate": cutpoint,
        "new_state_bytes": 0,
        "hot_path_delta_bytes": 0,
        "hardware_readback": {
            "reserved_address": "derive from linked scratch plus append offset",
            "image_record": "0x61", "metadata_header": "0x62",
            "entry_record": "0x63", "code_header": "0x64",
            "literal_block": "0x65", "success": "0x6a",
        },
    }
    receipt["product_identity"] = {
        "product": L.bind(product), "elf": L.bind(elf),
        "map": L.bind(map_path)}
    receipt["counters"] = {
        "class_b_diagnostic_cycles": "3/3 closed for prior BADOPCODE",
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2"}
    receipt["next_gate"] = replacement["NEXT_GATE"]
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link54-phase06a-cutpoint: COMPLETE "
          f"product={L.sha(product)} text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"phase06a={cutpoint['phase06a']['bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link54Error, BASE.Link53Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link54-phase06a-cutpoint: FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
