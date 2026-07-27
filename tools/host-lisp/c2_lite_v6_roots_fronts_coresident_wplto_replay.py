#!/usr/bin/env python3
"""Artifact-only qualification replay for the roots/fronts WPLTO.

The sole WPLTO completed and packed both families, then a harness looked for
the provisional KERNAL-window extraction one directory above its product
artifacts.  This replay extracts that read-only view from the frozen ELF and
runs the complete post-WPLTO gate set without compiling or linking anything.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as PROBE  # noqa: E402


P = PROBE.P
STAGE = PROBE.STAGE
DERIVED = PROBE.DERIVED
OUT = PROBE.OUT
FULL = OUT / "full-product-wplto"
TARGET = FULL / "c2-lite-v6-full-seed.prg"
ELF = Path(str(TARGET) + ".elf")
FIRST_RED = PROBE.RECEIPT
FIRST_RED_SHA = (
    "501d2d74662135b71a6f039571fd34db610a8d230b78a0daccf2a9686fce2e53")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-link40-roots-fronts-coresident-wplto-"
    "artifact-replay-receipt.json")
GATE_OUT = OUT / "artifact-replay-gates"


def reconstruct_wplto() -> dict[str, Any]:
    sections = P.section_table(ELF)
    text = sections[".text"]
    bss = sections[".bss"]
    walls = {
        "bank0_text_headroom_bytes":
            P.HANDOFF_BASE - text["address"] - text["bytes"],
        "ordinary_bank0_bss_headroom_bytes":
            P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"],
        "fixed_hot_block_headroom_bytes": P.fixed_bank0_headroom_bytes(),
        "resident_island_headroom_bytes": 2048 - sum(
            sections.get(name, {}).get("bytes", 0) for name in
            (".lisp65_resident_island", ".lisp65_resident_island_annex")),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - sum(
            sections[name]["bytes"] for name in P.KERNAL_SECTIONS),
    }
    PROBE.require(all(value >= 0 for key, value in walls.items()
                      if key != "e000_headroom_bytes")
                  and walls["e000_headroom_bytes"] >= 115,
                  f"artifact WPLTO wall red: {walls}")
    slice_sections = {spec.split(":")[2] for spec in
                      P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    sizes = {name: sections.get(name, {}).get("bytes", 0)
             for name in slice_sections}
    over = {name: size for name, size in sizes.items()
            if size <= 0 or size > PROBE.CAP}
    PROBE.require(not over, f"artifact WPLTO slice wall red: {over}")
    boot_image = FULL / "runtime-overlays-boot-c2-lite.bin"
    session_image = FULL / "runtime-overlays-session-c2-lite.bin"
    PROBE.require(boot_image.stat().st_size <= PROBE.BANK_BYTES
                  and session_image.stat().st_size ==
                      PROBE.EXPECTED_SESSION_BYTES,
                  "artifact family capacity red")
    return {
        "status": "reconstructed-from-sha-bound-WPLTO-artifacts",
        "product_links": 0, "promotable": False, "hardware_runs": 0,
        "target": PROBE.bind(TARGET), "elf": PROBE.bind(ELF),
        "map": PROBE.bind(Path(str(TARGET) + ".map")),
        "resolved_profile": PROBE.bind(FULL / "resolved-profile.txt"),
        "walls": walls,
        "runtime_slices": {"count": len(sizes), "cap_bytes": PROBE.CAP,
                           "largest_bytes": max(sizes.values()),
                           "minimum_headroom_bytes":
                               PROBE.CAP - max(sizes.values())},
        "successor_bank3_pack": {
            "boot": {**PROBE.bind(boot_image),
                     "headroom_bytes": PROBE.BANK_BYTES -
                         boot_image.stat().st_size},
            "session": {**PROBE.bind(session_image),
                        "headroom_bytes": PROBE.BANK_BYTES -
                            session_image.stat().st_size},
        },
    }


def replay_gates(wplto: dict[str, Any]) -> dict[str, Any]:
    # The failed harness omitted this artifact-only extraction.  It is a view
    # of the ELF, not a compiler/linker/product mutation.
    GATE_OUT.mkdir(exist_ok=True)
    window = P.extract_provisional_kernal_window(GATE_OUT, TARGET)
    stage_states = STAGE.state_machine_gate()
    stage_source = STAGE.source_contract_gate()

    truth = PROBE.ElfTruth.read(
        ELF, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    stage_symbols = {name: truth.symbol(name) for name in (
        "c2_lite_stage_boot_family_impl", "c2_lite_stage_boot_family",
        "vm_bank3_boot_stage_entry", "vm_boot_overlay_chain_prepare",
        "ov_bank_crc16", "vm_bank3_boot_stage_fail",
        "vm_boot_overlay_chain_commit", "c2_lite_stage_session_family_impl",
        "c2_lite_stage_session_family", "rtov_family_stage_bindings")}
    PROBE.require(all(symbol.bytes > 0 for name, symbol in stage_symbols.items()
                      if name != "rtov_family_stage_bindings")
                  and stage_symbols["rtov_family_stage_bindings"].section ==
                      P.VERIFIER_BINDING_SECTION,
                  "stage symbol inventory red")
    publish = json.loads(
        (FULL / "runtime-verifier-publish-last.json").read_text(
            encoding="utf-8"))
    PROBE.require(publish["status"] == "passed"
                  and publish["bytes"] == 40
                  and publish["changed_range_confined"],
                  "existing stage publish-last evidence red")

    old_abi_out = DERIVED.ABI_PROBE.OUT
    try:
        DERIVED.ABI_PROBE.OUT = GATE_OUT
        abi = ABI.audit_elf(
            ELF, out=GATE_OUT / "c2-asm-leaf-real-abi-callers-replay.json",
            require_bank3_chain=True)
        crc = DERIVED.ABI_PROBE.workbench_crc_gate(TARGET, ELF)
    finally:
        DERIVED.ABI_PROBE.OUT = old_abi_out
    facade = P.fixed_facade_gate(GATE_OUT, TARGET, "roots-fronts-replay")
    handoff = P.handoff_z_abi_gate(GATE_OUT, TARGET, "roots-fronts-replay")
    pre = P.pre_ownership_gate(GATE_OUT, TARGET, "roots-fronts-replay")
    profile = P.profile_data_reference_gate(
        GATE_OUT, TARGET, "roots-fronts-replay", pre)
    inventory = P.final_section_inventory_gate(GATE_OUT, TARGET)
    kernal = P.kernal_freedom_gate(GATE_OUT, TARGET)
    no_attic = DERIVED.LINK.no_runtime_attic_gate(
        ELF, FULL / "generated-product-sources")
    overlay = DERIVED.LINK.BASE.LINK33_BASE.final_overlay_closure(ELF)
    preinstall = DERIVED.LINK.BASE.ISLAND.static_elf_gate(ELF)
    PROBE.require(all(gate["status"] == "passed" for gate in
                      (facade, handoff, pre, profile, inventory, kernal))
                  and no_attic["status"].startswith("passed")
                  and overlay["status"] ==
                      "passed-final-elf-overlay-closure"
                  and preinstall["status"] ==
                      "passed-static-preinstallation-Island-gate",
                  "one or more artifact replay structure gates are red")
    return {
        "status": "passed-artifact-only-complete-gate-replay",
        "provisional_window": window,
        "stage_state_machine": stage_states,
        "stage_source_contract": stage_source,
        "stage_symbols": {name: {"section": symbol.section,
                                  "address": symbol.value,
                                  "bytes": symbol.bytes}
                          for name, symbol in stage_symbols.items()},
        "stage_publish_last": publish,
        "real_abi": abi, "six_vector_crc": crc,
        "fixed_facade": facade, "handoff": handoff,
        "pre_ownership": pre, "profile_data": profile,
        "section_inventory": inventory, "kernal_freedom": kernal,
        "no_runtime_attic": no_attic, "overlay_closure": overlay,
        "preinstallation_island": preinstall,
    }


def build() -> dict[str, Any]:
    PROBE.require(not RECEIPT.exists(), "artifact replay already exists")
    PROBE.require(FIRST_RED.is_file() and PROBE.sha(FIRST_RED) == FIRST_RED_SHA,
                  "roots/fronts WPLTO harness First Red drift")
    PROBE.require(TARGET.is_file() and ELF.is_file(),
                  "frozen WPLTO artifacts absent")
    # Restore the exact in-memory profile only for interpreting the frozen ELF.
    STAGE.apply_profile(STAGE.BASE.configure)
    PROBE.configure_roots_fronts()
    wplto = reconstruct_wplto()
    gates = replay_gates(wplto)
    product = {
        "status": "passed-one-product-shaped-roots-fronts-WPLTO-replay",
        "whole_program_lto": wplto,
        "capacity": {"walls": wplto["walls"], "e000_floor_bytes": 115,
                     "session_aggregate":
                         wplto["successor_bank3_pack"]["session"]},
        "fresh_gates": gates,
        "artifacts": {"measurement_product": PROBE.bind(TARGET),
                      "measurement_elf": PROBE.bind(ELF),
                      "measurement_map": PROBE.bind(
                          Path(str(TARGET) + ".map"))},
    }
    aggregate = PROBE.product_gate(product)
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    value = {
        "format": "lisp65-c2-lite-v6-roots-fronts-artifact-replay-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-roots-fronts-WPLTO-artifact-only-replay",
        "scope": {"whole_program_lto_probes": 0,
                  "replayed_prior_wplto_artifacts": 1,
                  "compiler_runs": 0, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"harness_first_red": PROBE.bind(FIRST_RED),
                      "driver": PROBE.bind(Path(__file__)),
                      "frozen_artifacts": first["evidence"]},
        "harness_correction": {
            "class": "Class A output-path model only",
            "old_missing_path": str(OUT / "c2-product-kernal-window.bin"),
            "source": PROBE.bind(ELF),
            "compiler_or_linker_runs": 0,
        },
        "source_contract": PROBE.source_gate(),
        "cutpoint_fixtures": {
            "status": "inherited-from-same-WPLTO-run-before-harness-stop",
            "fixture": PROBE.bind(PROBE.FIXTURE),
            "stdout": PROBE.bind(OUT /
                "roots-fronts-cutpoints.stdout.txt")},
        "product_shaped_wplto": product,
        "aggregate_recovery": aggregate,
        "rollback_line": {**PROBE.bind(DERIVED.BASE.LINK40_PRODUCT),
                          "status": "untouched"},
        "latency_attempts_consumed": "0/2",
        "next_gate": "Owner-authorized successor product link",
    }
    PROBE.write_json(OUT / "roots-fronts-artifact-replay-report.json", value)
    value["replay_report"] = PROBE.bind(
        OUT / "roots-fronts-artifact-replay-report.json")
    PROBE.write_json(RECEIPT, value)
    PROBE.protect()
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print("c2-lite-roots-fronts-replay: FIRST RED " + str(error))
        return 2
    cap = value["aggregate_recovery"]
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    print("c2-lite-roots-fronts-replay: PASS "
          f"slice={cap['slice']['bytes']}B session={cap['session_family_bytes']}B "
          f"headroom={cap['session_family_headroom_bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B compiler=0 link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
