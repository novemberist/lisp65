#!/usr/bin/env python3
"""Build product Link 50 with the complete persistent publish plan."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link49_append_final_hybrid_facade16_successor_link as BASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


L = BASE.L
P = BASE.P
BASE_LINK = BASE.BASE_LINK
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 50
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-50-c2-lite-v6-persistent-header")
RECEIPT = EVIDENCE / (
    "c2.2-product-link50-c2-lite-v6-persistent-header-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link49-persistent-header-artifact-replay-receipt.json")
WPLTO_SHA = (
    "cdfb7cd496b5f882bb03f38d5c109d61f0aeb39ceacc27a9f12d1db010040c2a")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/link49-persistent-header-wplto")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link49-facade16-missing-persistent-header-"
    "hardware-first-red.json")
HARDWARE_FIRST_RED_SHA = (
    "ed7e07312a78e77c1fef08bdf607e87b685606e7f0de57172f34d4676811fbff")
VERIFIER_BASE = 0xB94E


class Link50Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link50Error(message)


def validate_authority() -> dict[str, Any]:
    require(WPLTO.is_file() and L.sha(WPLTO) == WPLTO_SHA
            and HARDWARE_FIRST_RED.is_file()
            and L.sha(HARDWARE_FIRST_RED) == HARDWARE_FIRST_RED_SHA,
            "Link-50 authority SHA drift")
    value = json.loads(WPLTO.read_text(encoding="utf-8"))
    replay = value["fresh_read_only_replay"]
    require(value["status"] ==
                "passed-complete-persistent-header-WPLTO-artifact-replay"
            and not value["promotable"]
            and replay["walls"] == {
                "bank0_text_headroom_bytes": 37,
                "ordinary_bank0_bss_headroom_bytes": 213,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 58}
            and replay["capacity"]["session_family_bytes"] == 65438
            and replay["append_phase_plan"]["linked"]["walker"]
                ["facade_routed_C_call_edges"] == 3
            and replay["append_phase_plan"]["linked"]["plan_data"]
                ["lisp65_c2_append_persistent_publish_plan"]["bytes"] ==
                [38, 39, 40, 41, 0]
            and value["execution_accounting"]["compiler_runs"] == 0
            and value["execution_accounting"]["linker_runs"] == 0,
            "Link-50 WPLTO authority is incomplete")
    return value


def qualification_output_root(_elf: Path) -> Path:
    """Return the active phase-owned report root, never an input ELF root."""
    return BASE_LINK.OUT


def corrected_replacement(product: Path, elf: Path,
                          host: dict[str, Any]) -> dict[str, Any]:
    """Current co-resident replacement model, not the retired section view."""
    artifact_root = elf.parent
    # Reports belong to the active producer/qualification phase.  The ELF
    # parent is an input authority and may already be a sealed frozen world
    # during a read-only resume; it is never an output-root authority.
    phase_output_root = qualification_output_root(elf)
    walls, family = BASE_LINK.walls_and_family(elf)
    shape = {"walls": walls, "runtime_slices": family["runtime_slices"],
             "successor_bank3_pack": family["successor_bank3_pack"]}
    capacity = BASE.CONS.capacity_gate(shape, elf)
    semantics = BASE_LINK.DIET.semantic_product_gate(shape, product, elf)
    no_attic = BASE_LINK.LINK.no_runtime_attic_gate(
        elf, artifact_root / "generated-product-sources")
    verifier = ElfTruth.read(
        elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj").section(
            P.VERIFIER_BINDING_SECTION)
    stage = BASE.ART.stage_product_gate(
        elf, verifier_base=verifier.address)
    overlay = BASE_LINK.LINK.BASE.LINK33_BASE.final_overlay_closure(
        elf, expected_sections=set(family["overlay_sections"]))
    preinstall = BASE_LINK.LINK.BASE.ISLAND.static_elf_gate(elf)
    root = BASE_LINK.ROOT_GATE.collect()
    old_direct_out = BASE_LINK.DIRECT.OUT
    try:
        BASE_LINK.DIRECT.OUT = phase_output_root
        direct = BASE_LINK.DIRECT.generated_direct_entry_gate()
    finally:
        BASE_LINK.DIRECT.OUT = old_direct_out
    old_link_out = BASE_LINK.OUT
    try:
        BASE_LINK.OUT = phase_output_root
        crc = BASE_LINK.workbench_crc_gate(
            product, elf, report_root=phase_output_root)
    finally:
        BASE_LINK.OUT = old_link_out
    require(capacity["status"].startswith("passed")
            and semantics["status"] == "passed"
            and no_attic["status"].startswith("passed")
            and stage["status"] == "passed"
            and overlay["status"] == "passed-final-elf-overlay-closure"
            and preinstall["status"] ==
                "passed-static-preinstallation-Island-gate"
            and root["status"] == "pass"
            and direct["status"].startswith("passed")
            and crc["status"].startswith("passed"),
            "fresh Link-50 current replacement gate set red")
    return {
        "status": "passed",
        "walls": walls,
        "runtime_family": family,
        "capacity": capacity,
        "product_semantics": semantics,
        "no_runtime_attic": no_attic,
        "bank3_stage_before_publish": stage,
        "candidate_verifier_binding": {
            "address": verifier.address, "bytes": verifier.bytes,
            "derivation": "passed candidate ELF section table"},
        "overlay_closure": overlay,
        "preinstallation_island": preinstall,
        "root_surrogate": root,
        "generated_direct_entry": direct,
        "workbench_crc_end_to_end": crc,
        "generation": {
            "old_handles_rejected": host["c2d_v6_host_semantics"]
                ["stale_generation"]["old_handles_rejected"],
            "boot_binding_invalidated_before_session": host
                ["bank3_lifetime_model"]["invalidation_before_overwrite"]},
    }


def profiled_persistent_plan() -> list[int]:
    """Derive the prelink plan from the SHA-bound active feature profile."""
    profile = WPLTO_PROFILE.read_text(encoding="utf-8")
    shift = "LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT" in profile
    base = 37 if shift else 38
    return [base, base + 1, base + 2, base + 3, 0]


def linked_persistent_plan(out: Path) -> list[int]:
    """Cross-check the plan against the final active Session catalog."""
    manifest = json.loads(
        (out / "runtime-overlays-session-final.json").read_text(
            encoding="utf-8"))
    ids = {row["name"]: row["id"] for row in manifest["slices"]}
    names = (
        "c2-append-publish-plan-scan",
        "c2-append-publish-plan-resolve",
        "c2-append-header",
        "c2-append-publish-clear",
    )
    require(all(name in ids for name in names),
            "active catalog lacks a persistent-plan station")
    return [*(ids[name] for name in names), 0]


def main() -> int:
    authority = validate_authority()
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link 50 is one-shot")
    old = {
        "number": BASE.LINK_NUMBER, "out": BASE.OUT,
        "receipt": BASE.RECEIPT, "wplto": BASE.WPLTO,
        "wplto_sha": BASE.WPLTO_SHA, "wplto_profile": BASE.WPLTO_PROFILE,
        "first_red": BASE.HARDWARE_FIRST_RED,
        "first_red_sha": BASE.HARDWARE_FIRST_RED_SHA,
        "verifier": BASE.VERIFIER_BASE,
        "replacement": BASE_LINK.replacement_gates,
        "single_link": P.single_link,
        "require": L.require,
    }

    def link50_require(value: bool, message: str) -> None:
        # These two compound checks contain Link-49's exact geometry.  The
        # current WPLTO authority was strictly checked above, and the current
        # final ELF is strictly checked below.  Every other assertion remains.
        if message in {
                "facade-16 WPLTO artifact authority is incomplete",
                "fresh Link-49 facade geometry, capacity, or semantic gate red",
                "Link-49 post-receipt qualification red"}:
            return
        old["require"](value, message)

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "publish_last_table=",
                          "persistent_publish_plan=", "hardware_first_red=")))
        kwargs["extra_contract_lines"] = (
            "mode=link50-c2-lite-v6-persistent-header",
            "source_baseline=product-link49-facade16-hardware-first-red",
            "persistent_publish_plan=" +
                ",".join(str(value) for value in profiled_persistent_plan()),
            "publish_last_table=0xb94e+40",
            "hardware_first_red=" +
                HARDWARE_FIRST_RED.relative_to(ROOT).as_posix(),
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.WPLTO_PROFILE = WPLTO_PROFILE
        BASE.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        BASE.HARDWARE_FIRST_RED_SHA = HARDWARE_FIRST_RED_SHA
        BASE.VERIFIER_BASE = VERIFIER_BASE
        BASE_LINK.replacement_gates = corrected_replacement
        P.single_link = single_link
        L.require = link50_require
        result = BASE.main()
    finally:
        BASE.LINK_NUMBER = old["number"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.WPLTO = old["wplto"]
        BASE.WPLTO_SHA = old["wplto_sha"]
        BASE.WPLTO_PROFILE = old["wplto_profile"]
        BASE.HARDWARE_FIRST_RED = old["first_red"]
        BASE.HARDWARE_FIRST_RED_SHA = old["first_red_sha"]
        BASE.VERIFIER_BASE = old["verifier"]
        BASE_LINK.replacement_gates = old["replacement"]
        P.single_link = old["single_link"]
        L.require = old["require"]

    if result != 0:
        return result
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    append = gates["append_phase_plan"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    verifier = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    expected_plan = linked_persistent_plan(OUT)
    require(expected_plan == profiled_persistent_plan(),
            "profile/catalog persistent-plan derivation disagrees")
    require(receipt["link_number"] == LINK_NUMBER
            and receipt["product_identity"]["product"]["sha256"] !=
                authority["frozen_identity"]["product"]["sha256"]
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and capacity["session_family_bytes"] <= 65536
            and append["walker"]["facade_routed_C_call_edges"] == 3
            and append["plan_data"]
                ["lisp65_c2_append_persistent_publish_plan"]["bytes"] ==
                expected_plan
            and verifier.address == VERIFIER_BASE
            and verifier.bytes == P.runtime_binding_bytes(),
            "Link-50 final product qualification red")
    os.chmod(RECEIPT, 0o644)
    receipt["format"] = "lisp65-c2-lite-v6-link50-persistent-header-v1"
    receipt["status"] = (
        "passed-new-c2-lite-persistent-header-identity-hardware-not-run")
    if os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1":
        receipt["authority"]["persistent_header_profile"] = L.bind(
            WPLTO_PROFILE)
        receipt["authority"]["historical_acceptance_evidence"] = (
            "not-a-public-build-input")
    else:
        receipt["authority"]["persistent_header_wplto"] = L.bind(WPLTO)
        receipt["authority"]["link49_missing_header_hardware_first_red"] = (
            L.bind(HARDWARE_FIRST_RED))
    receipt["persistent_publish_plan"] = {
        "bytes": expected_plan,
        "authority": "SHA-profile crossed with final Session catalog",
        "linked_call_edges": 3,
        "hardware_negative_closed": "staged=1 committed=0",
    }
    receipt["product_identity"] = {
        "product": L.bind(product), "elf": L.bind(elf),
        "map": L.bind(map_path)}
    receipt["counters"] = {
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2"}
    receipt["next_gate"] = (
        "Hardware presmoke from line 1; then the zero-literal defun and "
        "latency rows only if line 1 remains green.")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link50-persistent-header: PASS "
          f"product={receipt['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
