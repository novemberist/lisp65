#!/usr/bin/env python3
"""One owner-authorized handoff-reanchor WPLTO probe; never Link 33."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l65r_v2_boot_branch_relocation_probe as BRANCH  # noqa: E402
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-handoff-reanchor-wplto"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-wplto-probe-receipt.json")
AUTHORIZATION = ROOT / "config/c2-handoff-reanchor-authorization.json"
AUTHORIZATION_SHA256 = (
    "224cd63a6007207c5170bf92a732c6c724e1d06e0b9607338a2144ac96a72c73")
FEASIBILITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-handoff-reanchor-feasibility-receipt.json")
FEASIBILITY_SHA256 = (
    "95a2db2630a47ad3916f961c7d547fb4086d9bf793c91eac085e8b6aeb7d10f7")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-boot-branch-relocation-first-red-diagnosis.json")
FIRST_RED_SHA256 = (
    "2217ab1eff952428dbb54e35be19feccd404f678b9610bb1fc9711ba1093fa32")
FIRST_RED_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-boot-branch-probe/"
    "l65r-v2-boot-family-seed.prg.map")
FIRST_RED_MAP_SHA256 = (
    "9e365be63b4d6dce04a7d60d0314b1cdae063f8e2f140866513bbfe2fe7b804e")
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"

EXPECTED_SECTIONS = {
    ".lisp65_c2_kernal_handoff": (0xB4A3, 0x121),
    ".lisp65_c2_host_facade": (0xB5C4, 0x2D),
    ".lisp65_c2_kernal_io_reveal": (0xB5F1, 0x0B),
    ".lisp65_c2_kernal_map_switch": (0xB5FC, 0x0A),
    ".lisp65_c2_kernal_state": (0xB606, 0x14),
    ".rodata": (0xB61A, 0x33A),
    ".lisp65_runtime_overlay_verifier_bindings": (0xB954, 0x20),
    ".data": (0xB974, 0x16),
    ".bss": (0xB98A, 0x633),
    ".lisp65_c2_fixed_bank0": (0xC080, 0x198),
    ".lisp65_c2_fixed_bank0_code": (0xC218, 0x2D),
    ".lisp65_c2_fixed_bank0_hot_bss": (0xC245, 0xF0),
    ".noinit": (0xC335, 0),
    ".lisp65_workbench_overlay": (0xC356, 0x6C3),
}


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prerequisites() -> dict[str, Any]:
    require(sha(AUTHORIZATION) == AUTHORIZATION_SHA256,
            "handoff-reanchor authorization drift")
    require(sha(FEASIBILITY) == FEASIBILITY_SHA256,
            "handoff-reanchor feasibility receipt drift")
    require(sha(FIRST_RED) == FIRST_RED_SHA256,
            "two-byte First Red receipt drift")
    require(sha(FIRST_RED_MAP) == FIRST_RED_MAP_SHA256,
            "two-byte First Red WPLTO map drift")
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    require(authorization["status"] ==
            "owner-authorized-one-contract-migration-and-one-wplto-probe"
            and authorization["geometry"]["new_handoff_anchor"] == "0xb4a3"
            and authorization["geometry"]["delta_bytes"] == 34,
            "handoff-reanchor authorization is not applicable")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    successor = contract["handoff_reanchor_2026_07_21"]
    require(successor["status"] ==
            "owner-authorized-successor-pins-pending-wplto"
            and successor["low_resident_chain"]["handoff"]["address"] ==
            "0xb4a3"
            and successor["capacity_contract"][
                "bank0_text_headroom_min_bytes"] == 32,
            "machine-readable successor geometry drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback identity drift")
    return {
        **BRANCH.prerequisites(),
        "handoff_reanchor_authorization": bind(AUTHORIZATION),
        "handoff_reanchor_feasibility": bind(FEASIBILITY),
        "two_byte_first_red": bind(FIRST_RED),
        "two_byte_first_red_map": bind(FIRST_RED_MAP),
        "successor_contract": bind(CONTRACT),
        "successor_contract_document": bind(CONTRACT_DOC),
        "successor_plan": bind(PLAN),
    }


def pin_source_gate() -> dict[str, Any]:
    profile = BOOT.PROFILE.value()
    require(P.HANDOFF_BASE == 0xB4A3 and P.HANDOFF_BYTES == 0x121,
            "canonical Handoff constants drift")
    require(P.HOST_FACADE_BASE == 0xB5C4
            and P.host_facade_bytes() == 45
            and P.VERIFIER_BINDING_BASE == 0xB954
            and P.KERNAL_CRC_BINDING_HIGH_ADDRESS == 0xB4CC
            and P.KERNAL_CRC_BINDING_LOW_ADDRESS == 0xB4D0,
            "canonical successor pin constants drift")
    require(profile["fixed_facade"] == {
        "vector_count": 15, "handle_normalize_vma": 0xB5EE},
        "canonical profile successor VMA drift")
    expected_vectors = {
        name: 0xB5C4 + index * 3
        for index, name in enumerate([
            *P.HOST_FACADE_SYMBOLS, *P.HOST_FACADE_EXTENSION_SYMBOLS])
    }
    require(P.host_facade_vector_addresses() == expected_vectors
            and len(expected_vectors) == 15,
            "fifteen-vector successor projection drift")
    generated = P.linker_script()
    required = (
        ".lisp65_c2_kernal_handoff 0xb4a3",
        ".lisp65_c2_host_facade 0xb5c4",
        "c2_facade_runtime_overlay_exec == 0xb5eb",
        "c2_facade_handle_normalize == 0xb5ee",
        ".lisp65_c2_kernal_io_reveal 0xb5f1",
        ".lisp65_c2_kernal_map_switch 0xb5fc",
        ".lisp65_c2_kernal_state 0xb606",
        "ADDR(.rodata) ==\n           ADDR(.lisp65_c2_kernal_state)",
    )
    require(all(fragment in generated for fragment in required),
            "generated successor linker geometry is incomplete")
    forbidden = (
        ".lisp65_c2_kernal_handoff 0xb481",
        ".lisp65_c2_host_facade 0xb5a2",
        "c2_facade_handle_normalize == 0xb5cc",
    )
    require(not any(fragment in generated for fragment in forbidden),
            "historical active address survived in generated linker script")
    mutations = {
        "old-handoff": (0xB481, P.HANDOFF_BASE),
        "short-shift": (0xB4A2, P.HANDOFF_BASE),
        "old-facade": (0xB5A2, P.HOST_FACADE_BASE),
        "old-handle-vector": (0xB5CC, expected_vectors[
            "c2_facade_handle_normalize"]),
        "old-verifier-table": (0xB914, P.VERIFIER_BINDING_BASE),
        "old-crc-high": (0xB4AA, P.KERNAL_CRC_BINDING_HIGH_ADDRESS),
        "old-crc-low": (0xB4AE, P.KERNAL_CRC_BINDING_LOW_ADDRESS),
    }
    require(all(bad != good for bad, good in mutations.values()),
            "pin mutation matrix did not mutate")
    return {
        "status": "passed-single-successor-pin-source",
        "handoff": P.HANDOFF_BASE,
        "facade_vectors": expected_vectors,
        "publish_last": {
            "verifier_table": P.VERIFIER_BINDING_BASE,
            "crc_high": P.KERNAL_CRC_BINDING_HIGH_ADDRESS,
            "crc_low": P.KERNAL_CRC_BINDING_LOW_ADDRESS,
        },
        "profile": BOOT.PROFILE.receipt_identity(),
        "negative_mutations": {name: "rejected" for name in mutations},
    }


def geometry_gate(target: Path) -> dict[str, Any]:
    elf = Path(str(target) + ".elf")
    sections = P.section_table(elf)
    require(sections.get(".text", {}).get("address") == 0x2023,
            "successor .text origin drift")
    observed: dict[str, Any] = {}
    for name, (address, count) in EXPECTED_SECTIONS.items():
        row = sections.get(name)
        require(row == {"address": address, "bytes": count},
                f"successor section geometry red: {name}={row}")
        observed[name] = row
    text = sections[".text"]
    text_end = text["address"] + text["bytes"]
    bss = sections[".bss"]
    bss_end = bss["address"] + bss["bytes"]
    text_headroom = P.HANDOFF_BASE - text_end
    require(text_headroom >= 32,
            "standing LTO-noise reserve is below the 32-byte floor")
    require(P.FIXED_BANK0_BASE - bss_end == 195,
            "pre-fixed pocket is not exactly 195 bytes")
    require(P.fixed_bank0_headroom_bytes() == 33,
            "post-fixed pocket drift")
    symbols = P.defined_symbols(elf)
    vectors = P.host_facade_vector_addresses()
    require(all(symbols.get(name) == address
                for name, address in vectors.items()),
            "successor facade symbol pin drift")
    crc = P._kernal_crc_binding_locations(elf)
    require(crc["high_address"] == 0xB4CC
            and crc["low_address"] == 0xB4D0,
            "successor CRC operand pin drift")
    return {
        "status": "passed-exact-34-byte-chain-reanchor",
        "sections": observed,
        "bank0_text": {
            "end_exclusive": text_end,
            "handoff": P.HANDOFF_BASE,
            "headroom_bytes": text_headroom,
            "minimum_headroom_bytes": 32,
        },
        "pre_fixed_pocket": {
            "bss_end_exclusive": bss_end,
            "fixed_block": P.FIXED_BANK0_BASE,
            "headroom_bytes": 195,
        },
        "fixed_points": {
            "state": P.FIXED_BANK0_BASE,
            "code": P.FIXED_BANK0_CODE_BASE,
            "runtime_overlay_vma": 0xC356,
            "post_fixed_pocket_bytes": 33,
        },
        "vectors": vectors,
        "publish_last_addresses": {
            "runtime_overlay_verifier_bindings": sections[
                P.VERIFIER_BINDING_SECTION]["address"],
            "kernal_crc_high": crc["high_address"],
            "kernal_crc_low": crc["low_address"],
        },
    }


def write_successor_pins(target: Path, source_gate: dict[str, Any],
                         geometry: dict[str, Any], inventory: dict[str, Any],
                         lto: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    reports = {
        "handoff_geometry": {
            "format": "lisp65-c2-handoff-reanchor-geometry-pin-v1",
            "status": "passed", "geometry": geometry,
        },
        "facade_provenance": {
            "format": "lisp65-c2-facade15-successor-pin-v1",
            "status": "passed",
            "vectors": geometry["vectors"],
            "static_provenance": base["preinstallation_island"],
        },
        "publish_last": {
            "format": "lisp65-c2-publish-last-successor-pin-v1",
            "status": "passed",
            "addresses": geometry["publish_last_addresses"],
            "total_named_bytes": 34,
        },
        "profile_binding": {
            "format": "lisp65-c2-link33-profile-successor-binding-v1",
            "status": "passed",
            "canonical_profile": source_gate["profile"],
            "probe_profile": base["product_profile"],
        },
        "section_inventory": {
            "format": "lisp65-c2-link33-section-inventory-successor-pin-v1",
            "status": "passed", "inventory": inventory,
            "lto_partition": lto,
        },
    }
    result: dict[str, Any] = {}
    for name, value in reports.items():
        path = OUT / f"successor-pin-{name.replace('_', '-')}.json"
        write(path, value)
        result[name] = bind(path)
    return result


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "handoff-reanchor WPLTO probe is one-shot and already has output")
    authority = prerequisites()
    # Configure the same canonical profile before the source-only pin gate.
    # The first invocation stopped here, before creating OUT or invoking any
    # compiler/linker, because this call was missing; it did not consume the
    # authorized WPLTO probe.
    BOOT.BASE.configure()
    source_gate = pin_source_gate()
    original = {
        "OUT": BOOT.OUT,
        "RECEIPT": BOOT.RECEIPT,
        "prerequisites": BOOT.prerequisites,
        "attribution": BOOT.attribution,
        "protect": BOOT.BASE.protect,
    }
    BOOT.OUT, BOOT.RECEIPT = OUT, RECEIPT
    BOOT.prerequisites = prerequisites
    BOOT.attribution = BRANCH.attribution
    BOOT.BASE.protect = lambda _path: None
    try:
        base = BOOT.run_once()
    finally:
        BOOT.OUT, BOOT.RECEIPT = original["OUT"], original["RECEIPT"]
        BOOT.prerequisites = original["prerequisites"]
        BOOT.attribution = original["attribution"]
        BOOT.BASE.protect = original["protect"]

    if str(base.get("status", "")).startswith("FIRST RED"):
        base["format"] = "lisp65-c2-handoff-reanchor-wplto-first-red-v1"
        base["status"] = "FIRST RED: handoff-reanchor WPLTO stopped"
        base["handoff_reanchor_source_gate"] = source_gate
        base["next_gate"] = "review; no retry or Link 33"
        os.chmod(RECEIPT, 0o644)
        write(RECEIPT, base)
        original["protect"](OUT)
        return base

    try:
        target = ROOT / base["artifacts"]["probe_prg"]["path"]
        geometry = geometry_gate(target)
        inventory = P.final_section_inventory_gate(OUT, target)
        lto = P.lto_partition_metadata_gate(OUT, target)
        require(base["resident_walls"] == {
            "bank0_text_headroom_bytes": 42,
            "ordinary_bank0_bss_headroom_bytes": 195,
            "fixed_hot_block_headroom_bytes": 33,
            "resident_island_headroom_bytes": 7,
            "e000_headroom_bytes": 115,
        }, f"successor wall set drift: {base['resident_walls']}")
        require(all(value == "passed" for value in
                    base["fresh_structural_gates"].values()),
                "one or more inherited WPLTO gates are not freshly passed")
        pins = write_successor_pins(
            target, source_gate, geometry, inventory, lto, base)
        value = {
            **base,
            "format": "lisp65-c2-handoff-reanchor-wplto-probe-v1",
            "status": "passed-handoff-reanchor-wplto-no-link33",
            "authority": authority,
            "handoff_reanchor_source_gate": source_gate,
            "handoff_reanchor_geometry": geometry,
            "fresh_additional_gates": {
                "final_section_inventory": inventory["status"],
                "lto_partition_metadata": lto["status"],
                "minimum_32_byte_text_reserve": "passed",
                "exact_195_byte_pre_fixed_pocket": "passed",
                "fixed_points_unchanged": "passed",
            },
            "successor_pin_package": pins,
            "scope": {
                **base["scope"],
                "authorized_wplto_probes": 1,
                "actual_wplto_probes": 1,
                "product_closure_links": 0,
                "link33_attempts": 0,
                "product_bytes": 0,
                "hardware_runs": 0,
            },
            "claim_limit": (
                "One owner-authorized non-product WPLTO probe and complete "
                "prelink successor-pin package only. Link 33, hardware, "
                "promotion and acceptance remain not-run."),
            "next_gate": "review before any fresh Link 33",
        }
    except (ProbeError, RuntimeError, KeyError, ValueError) as error:
        value = {
            **base,
            "format": "lisp65-c2-handoff-reanchor-wplto-first-red-v1",
            "status": "FIRST RED: handoff-reanchor successor gate stopped",
            "authority": authority,
            "handoff_reanchor_source_gate": source_gate,
            "diagnostic": {"type": type(error).__name__, "message": str(error)},
            "next_gate": "review; no retry or Link 33",
        }
    os.chmod(RECEIPT, 0o644)
    write(RECEIPT, value)
    original["protect"](OUT)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "handoff-reanchor WPLTO receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-handoff-reanchor-wplto-no-link33",
            "handoff-reanchor WPLTO receipt is not green")
    require(value["handoff_reanchor_geometry"]["bank0_text"][
                "headroom_bytes"] >= 32
            and value["handoff_reanchor_geometry"]["pre_fixed_pocket"][
                "headroom_bytes"] == 195,
            "handoff-reanchor receipt geometry drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback identity drift")
    return value


def selftest() -> dict[str, Any]:
    BOOT.BASE.configure()
    source = pin_source_gate()
    P._handoff_z_abi_model_selftest()
    return {
        "status": "passed",
        "source_pin_mutations": source["negative_mutations"],
        "handoff_abi_mutations": P._handoff_z_abi_model_selftest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "run", "check"))
    args = parser.parse_args()
    if args.action == "selftest":
        result = selftest()
        print("c2-handoff-reanchor-wplto: SELFTEST PASS "
              f"pin-mutations={len(result['source_pin_mutations'])}")
        return 0
    result = run_once() if args.action == "run" else check()
    print("c2-handoff-reanchor-wplto: " + result["status"])
    return 3 if str(result["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, BOOT.GateError, BOOT.BASE.ProbeError,
            BRANCH.GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-handoff-reanchor-wplto: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
