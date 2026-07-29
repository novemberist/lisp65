#!/usr/bin/env python3
"""Qualify and link the Link-74 handwritten-ASM Z-boundary correction."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ASM_ABI  # noqa: E402
import c2_defstruct_vm_codebuf_owner_successor_link73 as PREV  # noqa: E402


BASE = PREV.BASE
LINK = 74
ROOT_BUILD = ROOT / "build/post-promotion/link74-asm-z-boundary"
PRELINK_FIRST_RED_BUILD = ROOT_BUILD / "product-shaped-probe"
PROBE_BUILD = ROOT_BUILD / "product-shaped-probe-class-a-replay"
LINK_BUILD = ROOT_BUILD
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRELINK_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link74-asm-z-boundary-prelink-checker-first-red.json")
AGGREGATE_MODEL_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link74-asm-z-boundary-aggregate-model-first-red.json")
POSTLINK_REPLAY_FIRST_RED_RECEIPT = EVIDENCE / (
    "c2.2-link74-asm-z-boundary-postlink-replay-first-red.json")
WPLTO_RECEIPT = EVIDENCE / (
    "c2.2-link74-asm-z-boundary-wplto-receipt.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link74-asm-z-boundary-structural-receipt.json")
PREDECESSOR = EVIDENCE / (
    "c2.2-product-link73-vm-codebuf-owner-structural-receipt.json")
BASELINE_MAP = (
    ROOT / "build/post-promotion/link73-vm-codebuf-owner/final/"
    "resident-island-seed.prg.map")
DRIVER = Path(__file__).resolve()


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure() -> None:
    BASE.LINK = LINK
    BASE.ROOT_BUILD = ROOT_BUILD
    BASE.PROBE_BUILD = PROBE_BUILD
    BASE.LINK_BUILD = LINK_BUILD
    BASE.WPLTO_RECEIPT = WPLTO_RECEIPT
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.LINK69 = PREDECESSOR
    BASE.EVIDENCE = EVIDENCE
    BASE.DRIVER = DRIVER
    BASE.fix_gates = fix_gates


def fix_gates() -> dict[str, Any]:
    """Replay every affected source gate without the Link-72 count model."""
    resolver = PREV.PREV.ORIGINAL_FIX_GATES()
    episode_source = Path(PREV.PREV.EPISODE.SOURCE).read_text(
        encoding="utf-8")
    episode = {
        "source": PREV.PREV.EPISODE.source_gate(episode_source),
        "semantics": PREV.PREV.EPISODE.semantic_gate(),
        "mutations": PREV.PREV.EPISODE.mutation_gate(episode_source),
    }
    service = {
        "source": BASE.SERVICE.source_gate(),
        "source_mutations_rejected": BASE.SERVICE.mutation_gate(),
        "host": BASE.SERVICE.host_fixtures(
            ROOT_BUILD / "service-owner-lifetime-host"),
    }
    z_discipline = ASM_ABI.STZ.audit()
    abi_mutations = ASM_ABI.selftest()
    require(
        len(abi_mutations) == 160
        and z_discipline["status"]
            == "passed-all-handwritten-STZ-sites-and-Z-boundaries"
        and z_discipline["assembly_entry_count"] == 59
        and z_discipline["assembly_exit_count"] == 87
        and z_discipline["site_count"] == 25
        and episode["mutations"]["rejected"]
            == episode["mutations"]["total"] == 13
        and service["source"]["status"]
            == "passed-contract-stub-stateless-and-busy-dominance"
        and {
            "vm-codebuf-bank-owner-not-invalidated",
            "vm-codebuf-object-owner-not-invalidated",
            "vm-codebuf-owner-invalidated-too-late",
        } <= set(service["source_mutations_rejected"]),
        "Link-74 resolver, Z-boundary, IRQ or service gate red")
    return {
        "resolver_and_header": resolver,
        "assembler_Z_boundary": z_discipline,
        "assembler_ABI_and_Z_mutations": {
            "status": "passed",
            "rejected": len(abi_mutations),
            "names": sorted(abi_mutations),
        },
        "IRQ_episode": episode,
        "session_service_owner_lifetime": service,
    }


def existing_probe_result() -> tuple[dict[str, Path], dict[str, Any]]:
    """Read the completed one-shot WPLTO without invoking a build driver."""
    paths = BASE.paths(PROBE_BUILD)
    internal = load(paths["receipts"] / "wplto-internal.json")
    replacement = internal["fresh_replacement_gates"]
    static = load(
        paths["receipts"] / "defstruct-static-plane-authority.json")
    require(
        internal["status"]
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal["execution_accounting"]["product_closure_links"] == 1
        and static["status"].startswith("passed-"),
        "completed Link-74 WPLTO authority absent")
    return paths, {
        "plane": {
            "static_code_bytes":
                static["c2d_v6"]["static_bank2"]["code_bytes"],
        },
        "walls": replacement["walls"],
        "capacity": replacement["capacity"],
        "wplto": {
            "status":
                "passed-current-product-WPLTO-bound-by-artifact-replay",
            "historical_checker_boundary":
                "non-authoritative legacy qualification remains red",
            "qualification": BASE.bind(
                paths["receipts"] / "wplto-qualification.json"),
            "linked_gates": BASE.bind(
                paths["receipts"] / "single-submit-linked-gates.json"),
            "internal": BASE.bind(
                paths["receipts"] / "wplto-internal.json"),
        },
    }


def probe_action() -> int:
    configure()
    require(
        not WPLTO_RECEIPT.exists(),
        "Link-74 WPLTO receipt already exists")
    first_red = load(PRELINK_FIRST_RED_RECEIPT)
    aggregate_first_red = load(AGGREGATE_MODEL_FIRST_RED_RECEIPT)
    predecessor = load(PREDECESSOR)
    require(
        first_red["execution_accounting"][
            "current_product_WPLTO_links"] == 0
        and first_red["classification"]
            == "class-A-stale-L65E-capacity-checker"
        and aggregate_first_red["execution_accounting"][
            "additional_WPLTO_links"] == 0
        and predecessor["status"].startswith("passed-Link73-")
        and predecessor["walls"]["session_family_headroom_bytes"] == 113,
        "Link-73 predecessor authority drift")
    gates = fix_gates()
    if PROBE_BUILD.exists():
        paths, result = existing_probe_result()
    else:
        paths, result = BASE.run_wplto(PROBE_BUILD)
    probe_map = paths["wplto"] / "resident-island-seed.prg.map"
    before_entry = PREV.PREV.symbol_bytes(
        BASELINE_MAP, "lisp65_error_overlay_entry")
    after_entry = PREV.PREV.symbol_bytes(
        probe_map, "lisp65_error_overlay_entry")
    before_emit = PREV.PREV.symbol_bytes(
        BASELINE_MAP, "l65e_emit_bcode_ordinal")
    after_emit = PREV.PREV.symbol_bytes(
        probe_map, "l65e_emit_bcode_ordinal")
    linked_gate_path = (
        paths["receipts"] / "c2-asm-ABI-and-Z-boundary-WPLTO.json")
    linked_gate = ASM_ABI.audit_elf(
        paths["wplto"] / "lisp65-c2-substitution-linked.prg.elf",
        out=linked_gate_path)
    l65m = linked_gate["linked_inventory"]["vm_l65m_batch_repeat"]
    l65e = linked_gate["linked_inventory"]["lisp65_error_overlay_entry"]
    require(
        before_entry == 333
        and after_entry == 339
        and after_entry - before_entry == 6
        and before_emit == after_emit == 68
        and l65e["bytes"] == 339
        and l65m["status"] == "not-linked-by-c2-lite-profile"
        and linked_gate["handwritten_STZ_and_Z_boundary_discipline"][
            "assembly_entry_count"] == 59
        and linked_gate["handwritten_STZ_and_Z_boundary_discipline"][
            "assembly_exit_count"] == 87
        and result["walls"]["bank0_text_headroom_bytes"]
            == predecessor["walls"]["bank0_text_headroom_bytes"] == 351
        and result["walls"]["resident_island_headroom_bytes"]
            == predecessor["walls"]["resident_island_headroom_bytes"] == 50
        and result["walls"]["e000_headroom_bytes"]
            == predecessor["walls"]["e000_headroom_bytes"] == 54
        and result["capacity"]["session_family_bytes"] == 65423
        and result["capacity"]["session_family_headroom_bytes"] == 113,
        "Link-74 WPLTO geometry, closure or linked Z discipline red")
    value = {
        "format": "lisp65-c2.2-link74-ASM-Z-boundary-WPLTO-v1",
        "recorded_on": "2026-07-28",
        "status": "passed-Link74-ASM-Z-boundary-product-shaped-WPLTO",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "prelink_checker_first_red": BASE.bind(PRELINK_FIRST_RED_RECEIPT),
        "aggregate_model_first_red": BASE.bind(
            AGGREGATE_MODEL_FIRST_RED_RECEIPT),
        "symbol_attribution": {
            "lisp65_error_overlay_entry": {
                "Link73_bytes": before_entry,
                "Link74_WPLTO_bytes": after_entry,
                "delta_bytes": after_entry - before_entry,
                "temperature": "cold-error-path",
                "packing_effect":
                    "same 256-byte Session quantum; aggregate delta zero",
            },
            "l65e_emit_bcode_ordinal": {
                "Link73_bytes": before_emit,
                "Link74_WPLTO_bytes": after_emit,
                "delta_bytes": after_emit - before_emit,
            },
            "vm_l65m_batch_repeat": {
                "source_delta_bytes": 2,
                "C2_lite_product_delta_bytes": 0,
                "closure": l65m["status"],
            },
        },
        "fix_gates": gates,
        "linked_ASM_ABI_and_Z_boundary": BASE.bind(linked_gate_path),
        "static_code_bytes": result["plane"]["static_code_bytes"],
        "walls": result["walls"],
        "capacity": result["capacity"],
        "wplto": result["wplto"],
        "authority": {
            "predecessor": BASE.bind(PREDECESSOR),
            "Z_boundary_contract": BASE.bind(
                ROOT / "docs/planning/c2-asm-z-boundary-sweep.md"),
            "ASM_ABI_gate": BASE.bind(
                ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
            "Z_semantics_gate": BASE.bind(
                ROOT / "tools/host-lisp/c2_stz_z_dominance_gate.py"),
            "linked_ELF": BASE.bind(
                paths["wplto"] /
                "lisp65-c2-substitution-linked.prg.elf"),
            "driver": BASE.bind(DRIVER),
        },
        "next_gate": "one authorized Link-74 successor product link",
        "claim_limit":
            "Product-shaped geometry and linked ASM/Z discipline only; "
            "no Link-74 product or hardware claim.",
    }
    write(WPLTO_RECEIPT, value)
    print(
        "c2-asm-z-boundary-link74: WPLTO PASS "
        f"l65e={after_entry} text="
        f"{result['walls']['bank0_text_headroom_bytes']} "
        f"island={result['walls']['resident_island_headroom_bytes']} "
        f"e000={result['walls']['e000_headroom_bytes']} "
        f"session={result['capacity']['session_family_headroom_bytes']}")
    return 0


def link_action() -> int:
    configure()
    require(WPLTO_RECEIPT.is_file(), "accepted Link-74 WPLTO absent")
    result = 0
    if not LINK_RECEIPT.exists():
        result = BASE.link_action()
    receipt = load(LINK_RECEIPT)
    # Run source-only gates before configuring the artifact checker.  The
    # checker deliberately retargets the mutable resolver modules at FINAL;
    # replaying source selectors after that retarget is a model-order error.
    final_fix_gates = fix_gates()
    manifest_path = ROOT_BUILD / "canonical-product-manifest.json"
    manifest = load(manifest_path)
    manifest["static_plane"]["status"] = (
        "passed-ASM-Z-boundary-successor-single-emitter-static-plane")
    write(manifest_path, manifest)
    BASE.configure(LINK_BUILD)
    checked = BASE.CAN.check()
    final_elf = (
        ROOT_BUILD / "final/lisp65-c2-substitution-linked.prg.elf")
    final_map = ROOT_BUILD / "final/resident-island-seed.prg.map"
    replay_path = ROOT_BUILD / (
        "receipts/c2-asm-ABI-and-Z-boundary-final-replay.json")
    replay = ASM_ABI.audit_elf(final_elf, out=replay_path)
    authority = load(WPLTO_RECEIPT)
    require(
        checked["identity"] == manifest["identity"]
        and PREV.PREV.symbol_bytes(
            final_map, "lisp65_error_overlay_entry") == 339
        and replay["linked_inventory"][
            "lisp65_error_overlay_entry"]["bytes"] == 339
        and replay["linked_inventory"][
            "vm_l65m_batch_repeat"]["status"]
            == "not-linked-by-c2-lite-profile"
        and replay["handwritten_STZ_and_Z_boundary_discipline"][
            "assembly_entry_count"] == 59
        and replay["handwritten_STZ_and_Z_boundary_discipline"][
            "assembly_exit_count"] == 87
        and receipt["walls"]["bank0_text_headroom_bytes"]
            == authority["walls"]["bank0_text_headroom_bytes"]
        and receipt["walls"]["resident_island_headroom_bytes"]
            == authority["walls"]["resident_island_headroom_bytes"]
        and receipt["walls"]["e000_headroom_bytes"]
            == authority["walls"]["e000_headroom_bytes"]
        and receipt["walls"]["session_family_headroom_bytes"]
            == authority["capacity"]["session_family_headroom_bytes"],
        "Link-74 final identity, map or ASM/Z replay red")
    receipt.update({
        "format": "lisp65-c2.2-product-link74-ASM-Z-boundary-successor-v1",
        "status":
            "passed-Link74-ASM-Z-boundary-successor-hardware-not-run",
        "predecessor": BASE.bind(PREDECESSOR),
        "manifest": BASE.bind(manifest_path),
        "fix_gates": final_fix_gates,
        "linked_ASM_ABI_and_Z_boundary": BASE.bind(replay_path),
        "postlink_replay_first_red": BASE.bind(
            POSTLINK_REPLAY_FIRST_RED_RECEIPT),
        "next_gate":
            "One named two-timepoint LIT(1) hardware discriminator: "
            "initial materialization versus post-service owner reload.",
        "claim_limit":
            "Link 74 structural completion only; hardware unclaimed.",
    })
    receipt["authority"]["driver"] = BASE.bind(DRIVER)
    write(LINK_RECEIPT, receipt)
    print(
        "c2-asm-z-boundary-link74: LINK PASS "
        f"product={receipt['product']['sha256']} "
        f"text={receipt['walls']['bank0_text_headroom_bytes']} "
        f"e000={receipt['walls']['e000_headroom_bytes']} "
        f"session={receipt['walls']['session_family_headroom_bytes']}")
    return result


def main() -> int:
    action = sys.argv[1:] or ["probe"]
    require(
        action in (["probe"], ["link"], ["_complete"]),
        "usage: c2_asm_z_boundary_successor_link74.py "
        "[probe|link|_complete]")
    if action == ["probe"]:
        return probe_action()
    if action == ["link"]:
        return link_action()
    configure()
    return BASE.complete_action()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        SuccessorError, PREV.SuccessorError, PREV.PREV.SuccessorError,
        BASE.SuccessorError, BASE.PROBE.ProbeError,
        BASE.CAN.CanonicalError, BASE.SERVICE.GateError,
        BASE.SERVICE.ElfTruthError, ASM_ABI.GateError,
        ASM_ABI.STZ.GateError, OSError, ValueError, KeyError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print(
            "c2-asm-z-boundary-link74: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
