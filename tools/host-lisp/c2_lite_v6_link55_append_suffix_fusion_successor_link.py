#!/usr/bin/env python3
"""Build product Link 55 with suffix reads and one-record journal fusion."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_append_final_consolidation_gate as CONS  # noqa: E402
import c2_append_suffix_read_domain_gate as SUFFIX  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_journal_prepare_coresident_gate as FUSION  # noqa: E402
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as PROFILE  # noqa: E402
import c2_lite_v6_link54_phase06a_cutpoint_successor_link as BASE  # noqa: E402


L = BASE.L
P = BASE.BASE.BASE.P
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 55
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-55-c2-lite-v6-append-suffix-fusion-attempt2")
RECEIPT = EVIDENCE / (
    "c2.2-product-link55-c2-lite-v6-append-suffix-fusion-"
    "attempt2-structural-receipt.json")
PREFLIGHT_FIRST_RED = EVIDENCE / (
    "c2.2-product-link55-c2-lite-v6-append-suffix-fusion-"
    "structural-receipt.json")
PREFLIGHT_FIRST_RED_SHA = (
    "3788820fad2a5a292c7c2086a381be49e1fc7abf20c8bbee2a645b74c27ff0a4")
WPLTO = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-"
    "artifact-replay2-receipt.json")
WPLTO_SHA = (
    "2d0c8bf53596ac733fe379bb4f342c09f5ea0617c5dd6b2168c714ea2837cc6e")
WPLTO_AUTHORITY = EVIDENCE / (
    "c2.2-link55-append-suffix-fusion-asm-leaf-wplto-"
    "internal-structural.json")
WPLTO_AUTHORITY_SHA = (
    "55a28fa189a9906f1d8229287d6cfd01aa6075b81f08a7002995cd32dad41d08")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link55-append-suffix-fusion-asm-leaf-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-54-c2-lite-v6-phase06a-cutpoint/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "4cfc797f4ac4fac6cc4fea363ea684ea0dc8c7b395372ebc8bbfe2072fedef07")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link54-c2-lite-v6-phase06a-cutpoint-"
    "structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "1d57762c36832d70f91299e6cc7ea44b72a5634301075983ffd3441ae3a08b34")
HARDWARE = EVIDENCE / (
    "c2.2-product-link54-phase06a-cutpoint-hardware-first-red.json")
HARDWARE_SHA = (
    "08cb5b0a3a258a47614bb01f60ca71ace2c20101f3b1442c9bc137765fe64ad8")


class Link55Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link55Error(message)


def profile_features() -> tuple[str, ...]:
    rows = [
        line.split("=", 1)[1]
        for line in WPLTO_PROFILE.read_text(encoding="utf-8").splitlines()
        if line.startswith("feature_defines=")
    ]
    require(len(rows) == 1, "Link-55 WPLTO profile has no unique feature row")
    values = tuple(rows[0].split(","))
    require(values[-1] == FUSION.FEATURE and values.count(FUSION.FEATURE) == 1,
            "Link-55 fusion feature is not uniquely profile-bound")
    return values


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            WPLTO_AUTHORITY: WPLTO_AUTHORITY_SHA,
            PREFLIGHT_FIRST_RED: PREFLIGHT_FIRST_RED_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            HARDWARE: HARDWARE_SHA,
            FUSION.CONTRACT:
                "958204a5a833e7a756f350e74350ec5210da6c8e7f1528c8c10ee2d30ca7559c",
        ROOT / "tools/host-lisp/c2_journal_prepare_coresident_gate.py":
                "ef8a4f6a251aad1e17cb95c8f31bfc70e2bb3801d4ec92f6e70cc11513ffb9d3",
            ROOT / "tools/host-lisp/c2_append_suffix_read_domain_gate.py":
                "919417e77a676fa59ea6ef397a910084b9b084c12731352bc269ae67e8583747",
            ROOT / "src/c2_journal_prepare_select.s":
                "3d3317cf6f50783bba6f40584d436f4ec3030d6544e546638f851b08aaafc956",
            ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py":
                "8416ff075e168f585d413c421e41cdf98edbbe61ffdfaef5a2e5b6db9ebc2724",
            }.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-55 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = qualified["fresh_read_only_replay"]
    hardware = json.loads(HARDWARE.read_text(encoding="utf-8"))
    first_red = json.loads(PREFLIGHT_FIRST_RED.read_text(encoding="utf-8"))
    require(
        qualified["status"] ==
            "passed-one-quantum-WPLTO-all-walls-green"
        and not qualified["promotable"]
        and qualified["execution_accounting"]["compiler_runs"] == 0
        and qualified["execution_accounting"]["linker_runs"] == 0
        and replay["walls"] == {
            "bank0_text_headroom_bytes": 48,
            "ordinary_bank0_bss_headroom_bytes": 213,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 5,
            "e000_headroom_bytes": 58,
        }
        and replay["capacity"]["session_catalog_records"] == 48
        and replay["capacity"]["session_family_bytes"] == 65438
        and replay["journal_prepare_co_residence_linked"]["bytes"] == 1764
        and replay["journal_prepare_co_residence_linked"][
            "packed_recovered_bytes"] == 256
        and replay["append_suffix_read_domain_linked"]["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and hardware["status"] ==
            "first-red-locked-at-phase06a-image-record-read-before-inner-vm"
        and hardware["finding"]["cutpoint_value"] == "0x61",
        "Link-55 suffix/fusion authority is incomplete")
    require(
        first_red["diagnostic"]["type"] == "TypeError"
        and "combined_source() takes 0 positional arguments" in
            first_red["diagnostic"]["message"]
        and first_red["execution_accounting"]["product_closure_links"] == 0,
        "Link-55 prelink adapter First Red drift")
    profile_features()
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 55 is one-shot")
    validate_authority()
    names = (
        "LINK_NUMBER", "OUT", "RECEIPT", "WPLTO", "WPLTO_SHA",
        "WPLTO_AUTHORITY", "WPLTO_AUTHORITY_SHA", "WPLTO_SOURCE",
        "WPLTO_PROFILE", "BASELINE", "BASELINE_SHA", "BASELINE_RECEIPT",
        "BASELINE_RECEIPT_SHA", "HARDWARE", "HARDWARE_SHA",
        "validate_authority",
    )
    old = {name: getattr(BASE, name) for name in names}
    old_cut_source = BASE.CUT.source_gate
    old_cut_linked = BASE.CUT.linked_gate
    old_configure = CONS.configure_publish_clear
    old_features = PROFILE.resolved_features

    def configure_complete_profile() -> None:
        old_configure()
        FUSION.configure()

    def combined_source(parts: dict[str, str] | None = None,
                        *, mutations: bool = False) -> dict[str, Any]:
        value = old_cut_source(parts, mutations=mutations)
        value["append_suffix_read_domain"] = SUFFIX.source_gate(
            mutations=True)
        value["journal_prepare_co_residence"] = FUSION.source_gate(
            OUT / "fresh-c2-lite-prelink-gates/journal-prepare-cutpoints")
        return value

    def combined_linked(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
        value = old_cut_linked(elf, llvm_readobj)
        value["append_suffix_read_domain"] = SUFFIX.linked_gate(
            elf, llvm_readobj)
        value["journal_prepare_co_residence"] = FUSION.linked_gate(
            elf, llvm_readobj)
        value["assembler_leaf_abi"] = ABI.audit_elf(elf)
        return value

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
        BASE.CUT.source_gate = combined_source
        BASE.CUT.linked_gate = combined_linked
        CONS.configure_publish_clear = configure_complete_profile
        PROFILE.resolved_features = profile_features
        result = BASE.main()
    finally:
        for name, value in old.items():
            setattr(BASE, name, value)
        BASE.CUT.source_gate = old_cut_source
        BASE.CUT.linked_gate = old_cut_linked
        CONS.configure_publish_clear = old_configure
        PROFILE.resolved_features = old_features
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prelink = receipt["fresh_prelink_gates"]["phase06a_cutpoint_source"]
    linked = receipt["fresh_replacement_gates"]["phase06a_cutpoint"]
    walls = receipt["fresh_replacement_gates"]["walls"]
    capacity = receipt["fresh_replacement_gates"]["capacity"]
    suffix_source = prelink["append_suffix_read_domain"]
    fusion_source = prelink["journal_prepare_co_residence"]
    suffix = linked["append_suffix_read_domain"]
    fusion = linked["journal_prepare_co_residence"]
    leaf = linked["assembler_leaf_abi"]["journal_prepare_selector"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    require(
        receipt["link_number"] == LINK_NUMBER
        and L.sha(product) != BASELINE_SHA
        and suffix_source["status"] ==
            "passed-four-phase-suffix-and-source-domain-contract"
        and suffix["status"] ==
            "passed-linked-four-phase-suffix-domain-closure"
        and fusion_source["status"] ==
            "passed-one-record-journal-prepare-source-contract"
        and fusion["status"] ==
            "passed-linked-one-record-journal-prepare-cutpoint"
        and fusion["bytes"] <= 1792
        and fusion["packed_recovered_bytes"] == 256
        and leaf["status"] in {
            "passed-real-context-ABI-and-two-tail-edges",
            "passed-real-context-ABI-two-total-tail-edges-Z0"}
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["ordinary_bank0_bss_headroom_bytes"] == 213
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0
        and walls["e000_headroom_bytes"] >= 54
        and capacity["session_catalog_records"] == 48
        and capacity["session_family_bytes"] <= 65536
        and capacity["session_family_headroom_bytes"] >= 98,
        "Link-55 final product qualification red")
    receipt["format"] = (
        "lisp65-c2-lite-v6-link55-append-suffix-fusion-v1")
    receipt["status"] = (
        "passed-append-suffix-and-one-quantum-fusion-"
        "product-identity-hardware-not-run")
    receipt["authority"]["link54_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["authority"]["link54_suffix_hardware_first_red"] = L.bind(HARDWARE)
    receipt["authority"]["link55_prelink_adapter_first_red"] = L.bind(
        PREFLIGHT_FIRST_RED)
    receipt["authority"]["link55_WPLTO_artifact_replay"] = L.bind(WPLTO)
    receipt["append_suffix_and_fusion"] = {
        "suffix_source_gate": suffix_source,
        "suffix_linked_gate": suffix,
        "fusion_source_gate": fusion_source,
        "fusion_linked_gate": fusion,
        "assembler_leaf_ABI": leaf,
        "session_catalog_records": {
            "before": 49, "after": 48},
        "session_family_headroom_bytes": capacity[
            "session_family_headroom_bytes"],
    }
    receipt["product_identity"] = {
        "product": L.bind(product), "elf": L.bind(elf),
        "map": L.bind(map_path)}
    receipt["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2"}
    receipt["next_gate"] = (
        "Hardware double run: boot, defun/cold first call, immediate warm "
        "second call; then the remaining seven-row C2-lite presmoke.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link55-append-suffix-fusion: COMPLETE "
          f"product={L.sha(product)} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"fusion={fusion['bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link55Error, BASE.Link54Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link55-append-suffix-fusion: FIRST RED: " +
              str(error), file=sys.stderr)
        raise SystemExit(2)
