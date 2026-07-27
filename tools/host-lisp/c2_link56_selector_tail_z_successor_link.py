#!/usr/bin/env python3
"""Build successor Link 56 with the journal-selector C-entry Z repair."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_fusion_successor_link as BASE  # noqa: E402


L = BASE.L
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 56
OUT = ROOT / (
    "build/c2.2/substitution/product-link-56-selector-tail-z")
RECEIPT = EVIDENCE / (
    "c2.2-product-link56-selector-tail-z-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link56-selector-tail-z-artifact-replay-receipt.json")
WPLTO_SHA = (
    "8725def24984518d4404776dc393e601f01b1d752b4028866556c82bc26d58e9")
WPLTO_AUTHORITY = WPLTO
WPLTO_AUTHORITY_SHA = WPLTO_SHA
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/link56-selector-tail-z-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-55-c2-lite-v6-append-suffix-fusion-attempt2/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "968990d2fd2904cd1d97aa16e870c3c369f3fa27d787f2894dd9db08dbd3297d")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link55-c2-lite-v6-append-suffix-fusion-"
    "final-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "c6e2bcd8284e22289aae7ccc7471cd4622da703a3e0ebbb1b660e6fb29216c8d")
HARDWARE = EVIDENCE / (
    "c2.2-product-link55-append-suffix-defun-crash-hardware-first-red.json")
HARDWARE_SHA = (
    "bb7c1e826cb666d8dc5274cc967ef6444eb45e28990e8481095e7ebc31244595")
CATALOG = EVIDENCE / (
    "c2.2-product-link55-defun-crash-static-suspect-catalog.json")
CATALOG_SHA = (
    "6e4aa32c45b834c7997b5b92d38ba9704cccddf4be846ae9c0700086ea9fb2a2")


class Link56Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link56Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            HARDWARE: HARDWARE_SHA,
            CATALOG: CATALOG_SHA,
            }.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-56 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = qualified["fresh_read_only_replay"]
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-selector-tail-Z0-WPLTO-all-walls-green"
        and not qualified["promotable"]
        and qualified["execution_accounting"]["compiler_runs"] == 0
        and qualified["execution_accounting"]["linker_runs"] == 0
        and replay["walls"] == {
            "bank0_text_headroom_bytes": 40,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58}
        and replay["capacity"]["session_catalog_records"] == 48
        and replay["capacity"]["session_family_bytes"] == 65438
        and replay["capacity"]["session_family_headroom_bytes"] == 98
        and replay["journal_prepare_co_residence_linked"]["bytes"] == 1768
        and replay["journal_prepare_co_residence_linked"][
            "packed_recovered_bytes"] == 256
        and replay["assembler_leaf_abi"]["journal_prepare_selector"][
            "status"] ==
            "passed-real-context-ABI-two-total-tail-edges-Z0"
        and baseline["product_identity"]["product"]["sha256"] == BASELINE_SHA
        and hardware["status"] ==
            "first-red-uncontrolled-hardware-crash-during-defun"
        and catalog["status"] ==
            "convicted-selector-tail-violates-C-entry-Z0",
        "Link-56 selector tail-Z authority is incomplete")
    BASE.profile_features()
    return qualified


def main() -> int:
    validate_authority()
    product = OUT / "lisp65-c2-substitution-linked.prg"
    replay_only = OUT.exists() or RECEIPT.exists()
    if replay_only:
        require(OUT.is_dir() and RECEIPT.is_file() and product.is_file()
                and L.sha(product) ==
                    "723579250e692112d4208ae56c0eede15f422858b3f99cc9cd2af1639599d93d",
                "Link-56 receipt-only completion input drift")
        existing = json.loads(RECEIPT.read_text(encoding="utf-8"))
        require(
            existing["link_number"] == LINK_NUMBER
            and existing["status"] ==
                "passed-append-suffix-and-one-quantum-fusion-product-identity-hardware-not-run",
            "Link-56 receipt-only completion is not the known adapter Red")
    else:
        names = (
            "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
            "WPLTO_AUTHORITY", "WPLTO_AUTHORITY_SHA", "WPLTO_SOURCE",
            "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA",
            "BASELINE_RECEIPT", "BASELINE_RECEIPT_SHA", "HARDWARE",
            "HARDWARE_SHA", "validate_authority",
        )
        old = {name: getattr(BASE, name) for name in names}
        try:
            BASE.LINK_NUMBER = LINK_NUMBER
            BASE.OUT = OUT
            BASE.RECEIPT = RECEIPT
            BASE.WPLTO = WPLTO
            BASE.WPLTO_SHA = WPLTO_SHA
            BASE.WPLTO_AUTHORITY = WPLTO_AUTHORITY
            BASE.WPLTO_AUTHORITY_SHA = WPLTO_AUTHORITY_SHA
            BASE.WPLTO_SOURCE = WPLTO_SOURCE
            BASE.WPLTO_PROFILE = WPLTO_PROFILE
            BASE.BASELINE = BASELINE
            BASE.BASELINE_SHA = BASELINE_SHA
            BASE.BASELINE_RECEIPT = BASELINE_RECEIPT
            BASE.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
            BASE.HARDWARE = HARDWARE
            BASE.HARDWARE_SHA = HARDWARE_SHA
            BASE.validate_authority = validate_authority
            result = BASE.main()
        finally:
            for name, value in old.items():
                setattr(BASE, name, value)
        if result != 0:
            return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    linked = receipt["fresh_replacement_gates"]["phase06a_cutpoint"]
    walls = receipt["fresh_replacement_gates"]["walls"]
    capacity = receipt["fresh_replacement_gates"]["capacity"]
    fusion = linked["journal_prepare_co_residence"]
    leaf = linked["assembler_leaf_abi"]["journal_prepare_selector"]
    elf = Path(str(product) + ".elf")
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and leaf["status"] ==
            "passed-real-context-ABI-two-total-tail-edges-Z0"
        and all(row["operand"] in ("#$0", "#$00")
                for row in leaf["tail_C_entry_Z"].values())
        and fusion["bytes"] == 1768
        and fusion["packed_bytes"] == 1792
        and capacity["session_family_bytes"] == 65438
        and capacity["session_family_headroom_bytes"] == 98
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54,
        "Link-56 final selector-tail-Z qualification red")
    receipt["format"] = "lisp65-c2-lite-v6-link56-selector-tail-z-v1"
    receipt["status"] = (
        "passed-selector-tail-Z0-product-identity-hardware-not-run")
    receipt["authority"]["link55_hardware_first_red"] = L.bind(HARDWARE)
    receipt["authority"]["static_suspect_catalog"] = L.bind(CATALOG)
    receipt["authority"]["selector_tail_Z_WPLTO_replay"] = L.bind(WPLTO)
    receipt["authority"]["link55_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["selector_tail_Z_repair"] = {
        "linked_leaf": leaf,
        "fused_slice": fusion,
        "marker_domain_cases": 512,
        "marker_domain_fail_closed": 509,
        "product_delta": {
            "selector_bytes": 4,
            "packed_session_family_bytes": 0,
            "resident_bytes": 0,
        },
    }
    receipt["class_A_receipt_completion"] = {
        "performed": replay_only,
        "reason": (
            "the first adapter read walls/capacity one level below their "
            "actual receipt location"),
        "compiler_runs": 0 if replay_only else None,
        "linker_runs": 0 if replay_only else None,
        "product_bytes_changed": 0,
    }
    receipt["product_identity"] = {
        "product": L.bind(product),
        "elf": L.bind(elf),
        "map": L.bind(Path(str(product) + ".map")),
        "predecessor_sha256": BASELINE_SHA,
        "new_identity": True,
    }
    receipt["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2",
    }
    receipt["next_gate"] = (
        "Hardware presmoke from line 1 after explicit device restart")
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link56-selector-tail-z: COMPLETE "
        f"product={L.sha(product)} selector={leaf['bytes']} "
        f"fusion={fusion['bytes']} session={capacity['session_family_bytes']} "
        f"text={walls['bank0_text_headroom_bytes']} "
        f"e000={walls['e000_headroom_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link56Error, BASE.Link55Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link56-selector-tail-z: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
