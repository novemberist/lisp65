#!/usr/bin/env python3
"""Build and bind the fresh, final-floor-aware C2 Link 33 product candidate."""

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
import c2_hot_refill_capacity_probe as HOT  # noqa: E402
import c2_hot_refill_direct_entry_contract as DIRECT  # noqa: E402
import c2_nested_append_v5_prelink as PRE  # noqa: E402
import c2_nested_append_v5_successor_link as LINK33_BASE  # noqa: E402
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/product-link-33-profile-inventory-final"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-profile-inventory-structural-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK32_PRG = LINK32 / "lisp65-c2-substitution-linked.prg"
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
SECTION_REPLAY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-facade15-section-replay-receipt.json")
SECTION_REPLAY_SHA = (
    "67422c4b3c01873e3bf398326bcbc47cb8e7b5a5ad58330409405ba0b24bfc40")
PROFILE_BINDING_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-product-profile-binding-replay-receipt.json")
PROFILE_BINDING_RECEIPT_SHA = (
    "2ac45ba1b02bc995693f8a8ee84034a233b4481f526db03c4a8a85258647d3c6")
INVENTORY_REPLAY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-profile-derived-section-inventory-replay-receipt.json")
INVENTORY_REPLAY_RECEIPT_SHA = (
    "d8e6d6f3784af87032b25eb6e8a548cee4c9cba6c6beb47b6d88b80aef2db130")
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
PREREQUISITES = {
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link32-preinstall-island-guard-structural-receipt.json":
        "5843fea325faf2c63afc9c675de556cf72a8bb911555de0f375c98edf58ee2ab",
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-prelink-receipt.json":
        "09c3f83f9a698bf1f6ac9a0e50d4c1540238e956f8a4c1eefc65c8b1b49fb3a0",
    DIRECT.RECEIPT:
        "492fea599840dddadfe00421eb3f88fa2c72ab678e5e160344a7ea83595e0973",
    SECTION_REPLAY_RECEIPT: SECTION_REPLAY_SHA,
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-bss-triage-structural-receipt.json":
        "43913289b06de8b86568793aabd93fb48ac9b52773257097ca70ef8fc55219ce",
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-profile-bound-structural-receipt.json":
        "7e128fcbe3caa248d78de9dcc7594c005829338a99cc61f60c2a7b0fb3e18715",
    INVENTORY_REPLAY_RECEIPT: INVENTORY_REPLAY_RECEIPT_SHA,
}
FEATURES = PROFILE.feature_defines()
CAP = 1792
ADDITIONAL_CONTRACT_LINES: tuple[str, ...] = ()


class LinkError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LinkError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def configure() -> None:
    PROFILE.configure(P)
    require(len(P.C2_APPEND_SLICES) == 21
            and len(P.SESSION_SLICE_SPECS) == 46
            and P.UNIQUE_SLICE_COUNT == 53,
            "Link-33 append ABI configuration drift")
    require(P.host_facade_bytes() == 45
            and P.host_facade_vector_addresses().get(
                "c2_facade_handle_normalize") == 0xB5EE,
            "Link-33 facade-15 configuration drift")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    current_fixed = contract[
        "link58_fixed_block_rtov_fail_relocation_2026_07_23"]
    require(
        current_fixed["status"] ==
            "owner-authorized-pending-fresh-WPLTO"
        and P.FIXED_BANK0_CODE_BYTES ==
            current_fixed["capacity"]["fixed_code_bytes"]
        and P.fixed_bank0_headroom_bytes() ==
            current_fixed["capacity"]["fixed_block_headroom_bytes"],
        "current fixed hot-block configuration drift")


def prerequisites() -> dict[str, Any]:
    for path, expected in PREREQUISITES.items():
        require(path.is_file() and sha(path) == expected,
                f"Link-33 prerequisite drift: {path}")
    require(sha(LINK32_PRG) == LINK32_SHA,
            "Link-32 rollback product identity drift")
    replay = json.loads(SECTION_REPLAY_RECEIPT.read_text(encoding="utf-8"))
    require(replay.get("status")
            == "passed-pure-section-index-gate-replay-no-link",
            "section-index replay is not green")
    require(PROFILE_BINDING_RECEIPT.is_file()
            and sha(PROFILE_BINDING_RECEIPT) == PROFILE_BINDING_RECEIPT_SHA,
            "profile-object binding replay absent")
    profile_binding = json.loads(
        PROFILE_BINDING_RECEIPT.read_text(encoding="utf-8"))
    require(profile_binding.get("status")
            == "passed-profile-object-binding-pure-replay-no-link"
            and profile_binding["product_profile_object"]["sha256"]
            == PROFILE.sha256()
            and profile_binding["historical_green_wplto_profile"]
                ["equivalent_to_profile_object_sha256"] == PROFILE.sha256(),
            "probe/link profile-object SHA parity is not green")
    inventory_replay = json.loads(
        INVENTORY_REPLAY_RECEIPT.read_text(encoding="utf-8"))
    require(inventory_replay.get("status")
            == "passed-profile-derived-inventory-pure-replay-no-link"
            and inventory_replay["canonical_profile_object"]["sha256"]
            == PROFILE.sha256()
            and inventory_replay["derivation"]["expected_link33_names"] == 167,
            "profile-derived inventory replay is not green")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    floor = contract["formal_reopening_2026_07_21"]["final_floor_rule"]
    require(floor.get("status")
            == "bound-after-green-st_shndx-provenance-replay"
            and floor.get("bytes") == P.E000_FINAL_FLOOR_BYTES == 115,
            "final E000 floor contract is not bound at 115 bytes")
    return {
        "receipts": {path.name: bind(path) for path in PREREQUISITES},
        "contract": bind(CONTRACT),
        "contract_document": bind(CONTRACT_DOC),
        "plan": bind(PLAN),
        "product_profile_object": PROFILE.receipt_identity(),
        "profile_binding_replay": bind(PROFILE_BINDING_RECEIPT),
        "profile_inventory_replay": bind(INVENTORY_REPLAY_RECEIPT),
        "link32_rollback": {"product": bind(LINK32_PRG), "status": "untouched"},
    }


def capacity(elf: Path, out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sections = P.section_table(elf)
    text = sections[".text"]
    bss = sections[".bss"]
    text_room = P.HANDOFF_BASE - text["address"] - text["bytes"]
    bss_room = P.FIXED_BANK0_BASE - bss["address"] - bss["bytes"]
    fixed_room = P.fixed_bank0_headroom_bytes()
    island_room = (2048 - sections[".lisp65_resident_island"]["bytes"]
                   - sections[".lisp65_resident_island_annex"]["bytes"])
    e000_room = P.KERNAL_WINDOW_BYTES - sum(
        sections[name]["bytes"] for name in P.KERNAL_SECTIONS)
    in_window_debit = sum(
        sections[name]["bytes"] for name in P.e000_reopening_section_names())
    formal_debit = P.e000_reopening_debit(sections)
    facade_debit = formal_debit - in_window_debit
    pre_package_room = e000_room + in_window_debit
    require(text_room >= 0 and bss_room >= 0 and fixed_room >= 0
            and island_room >= 0 and e000_room >= P.E000_FINAL_FLOOR_BYTES,
            "FIRST RED: Link-33 resident walls "
            f"text={text_room} bss={bss_room} fixed={fixed_room} "
            f"island={island_room} e000={e000_room}")
    require((pre_package_room, in_window_debit, facade_debit,
             formal_debit, e000_room) == (531, 416, 6, 422, 115),
            "FIRST RED: Link-33 final E000 equation drift "
            f"pre={pre_package_room} in_window={in_window_debit} "
            f"facade={facade_debit} total={formal_debit} final={e000_room}")
    slices = {spec.split(":")[2]: sections.get(
        spec.split(":")[2], {}).get("bytes", 0)
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    over = {name: size for name, size in slices.items()
            if size <= 0 or size > CAP}
    require(not over, f"FIRST RED: runtime slice cap: {over}")
    boot = json.loads((out / "runtime-overlays-boot-final.json").read_text())
    session = json.loads((out / "runtime-overlays-session-final.json").read_text())
    require(boot["storage"]["size"] <= 65536
            and session["storage"]["size"] <= 65536,
            "FIRST RED: runtime overlay bank overflow")
    return {
        "bank0_text_headroom_bytes": text_room,
        "ordinary_bank0_bss_headroom_bytes": bss_room,
        "fixed_hot_block_headroom_bytes": fixed_room,
        "resident_island_headroom_bytes": island_room,
        "e000": {
            "actual_headroom_bytes": e000_room,
            "final_floor_bytes": P.E000_FINAL_FLOOR_BYTES,
            "headroom_above_floor_bytes": e000_room - P.E000_FINAL_FLOOR_BYTES,
            "pre_package_headroom_bytes": pre_package_room,
            "in_window_debit_bytes": in_window_debit,
            "facade_debit_bytes_outside_window": facade_debit,
            "debit_bytes": formal_debit,
            "debit_cap_bytes": P.E000_REOPEN_DEBIT_CAP,
            "equations": ["531 - 416 = 115", "416 + 6 = 422"],
            "third_opening": "forbidden",
        },
        "runtime_slices": {
            "count": len(slices), "cap_bytes": CAP,
            "largest_bytes": max(slices.values()),
            "minimum_headroom_bytes": CAP - max(slices.values()),
        },
        "runtime_overlay_bank": {
            "boot_bytes": boot["storage"]["size"],
            "boot_headroom_bytes": 65536 - boot["storage"]["size"],
            "session_bytes": session["storage"]["size"],
            "session_headroom_bytes": 65536 - session["storage"]["size"],
        },
    }, sections


def evidence_tree(out: Path) -> dict[str, dict[str, Any]]:
    return {path.relative_to(out).as_posix(): bind(path)
            for path in sorted(out.rglob("*")) if path.is_file()}


def protect(out: Path) -> None:
    if out.is_dir():
        for path in out.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
        for path in sorted((p for p in out.rglob("*") if p.is_dir()),
                           key=lambda p: len(p.parts), reverse=True):
            os.chmod(path, 0o555)
        os.chmod(out, 0o555)


def bind_first_red(error: Exception, prereq: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2-product-link33-bss-triage-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: fresh Link 33 failed",
        "diagnostic": str(error),
        "link_number": 33,
        "execution_accounting": {
            "product_closure_links": int((OUT / "lisp65-c2-substitution-linked.prg").is_file()),
            "hardware_runs": 0,
        },
        "prerequisites": prereq,
        "evidence": evidence_tree(OUT) if OUT.is_dir() else {},
        "rollback_line": {"link32_sha256": LINK32_SHA, "status": "untouched"},
        "next_gate": "return to review; no retry or hardware presmoke",
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    protect(OUT)
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "fresh final-floor Link 33 is one-shot and already has output")
    configure()
    prereq = prerequisites()
    try:
        fresh = PRE.check(OUT / "fresh-v5-prelink-gates")
        require(fresh["status"] == "passed-prelink-product-link-not-run"
                and fresh["b2_model"]["cases"] == 18,
                "FIRST RED: fresh nested-append/B2 gates failed")
        P.single_link(
            OUT, probe_definitions=FEATURES,
            direct_entry_receipt=DIRECT.RECEIPT,
            direct_entry_check_tool="c2_hot_refill_direct_entry_contract.py",
            extra_contract_lines=(
                "mode=link33-bss-triage-final-floor-product",
                "feature_defines=" + ",".join(FEATURES),
                "product_profile_object="
                + PROFILE.PROFILE.relative_to(ROOT).as_posix(),
                "product_profile_object_sha256=" + PROFILE.sha256(),
                "append_abi=v5-high-edge-transient-c2j",
                "append_slice_count=" + str(len(P.C2_APPEND_SLICES)),
                "fixed_facade_vector_count=15",
                "final_e000_floor_bytes=115",
                "section_index_replay_sha256=" + SECTION_REPLAY_SHA,
                "profile_inventory_replay_sha256="
                + INVENTORY_REPLAY_RECEIPT_SHA,
                "green_inheritance=none",
            ) + ADDITIONAL_CONTRACT_LINES)
        product = OUT / "lisp65-c2-substitution-linked.prg"
        elf = Path(str(product) + ".elf")
        structure = json.loads((OUT / "product-substitution-link.json").read_text())
        total = json.loads((OUT / "total-publish-last-domain.json").read_text())
        require(structure["status"] == "passed"
                and structure["product_closure_link_count"] == 1,
                "FIRST RED: generic product closure is not green")
        require(total["status"] == "passed"
                and total["declared_domain_bytes"] == 34,
                "FIRST RED: 34-byte publish-last binding is not green")
        cap, sections = capacity(elf, OUT)
        closure = LINK33_BASE.final_overlay_closure(elf)
        preinstall = ISLAND.static_elf_gate(elf)
        direct = HOT.direct_path_gate(elf)
        require(preinstall["status"]
                == "passed-static-preinstallation-Island-gate",
                "FIRST RED: preinstallation-Island gate is not green")
        value = {
            "format": "lisp65-c2-product-link33-bss-triage-structural-v1",
            "recorded_on": "2026-07-21",
            "status": "passed-new-product-identity-hardware-not-run",
            "link_number": 33,
            "inheritance": "none; every structural and capacity gate ran freshly",
            "execution_accounting": {
                "fresh_nonproduct_target_compiles": 2,
                "resident_island_seed_links": 1,
                "product_closure_links": 1,
                "hardware_runs": 0,
            },
            "prerequisites": prereq,
            "profile_hash_parity": {
                "probe_receipt_sha256": PROFILE.sha256(),
                "link_driver_sha256": PROFILE.sha256(),
                "status": "passed-identical-canonical-object",
            },
            "product_identity": {
                "product": bind(product), "elf": bind(elf),
                "resolved_profile": bind(OUT / "resolved-profile.txt"),
            },
            "post_link_identity": {
                "declared_mutable_product_bytes": total["declared_domain_bytes"],
                "actual_changed_bytes": total["actual_changed_bytes"],
                "status": total["status"],
            },
            "nested_append_v5": {
                "feature_defines": list(FEATURES),
                "append_slice_count": len(P.C2_APPEND_SLICES),
                "session_slice_count": len(P.SESSION_SLICE_SPECS),
                "b2_run_stop_cases": fresh["b2_model"]["cases"],
                "final_overlay_closure": closure,
            },
            "preinstallation_Island": preinstall,
            "hot_refill": direct,
            "capacity": cap,
            "section_count": len(sections),
            "claim_limit": (
                "Fresh Link 33 product identity and complete structural/capacity "
                "closure only. Hardware, latency, nested-eval smoke, GC read "
                "cost, Freezer identity, promotion and acceptance are not run."),
            "next_gate": "owner-authorized hardware presmoke protocol",
        }
        report = OUT / "link33-bss-triage-final-structural.json"
        report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        receipt = {**value, "structural_report": bind(report),
                   "evidence_file_count": len(evidence_tree(OUT))}
        RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
        protect(OUT)
        return receipt
    except (LinkError, PRE.GateError, ISLAND.GateError, RuntimeError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return bind_first_red(error, prereq)


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "Link-33 receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if value.get("status") == "passed-new-product-identity-hardware-not-run":
        for row in value["product_identity"].values():
            path = ROOT / row["path"]
            require(path.is_file() and sha(path) == row["sha256"],
                    f"Link-33 product identity drift: {path}")
    require(sha(LINK32_PRG) == LINK32_SHA, "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        configure()
        generated = P.linker_script()
        require("C2 final E000 floor below 115 bytes" in generated
                and "c2_facade_handle_normalize == 0xb5ee" in generated,
                "final-floor/facade linker contract absent")
        require(PRE.b2_model_gate()["cases"] == 18,
                "B2 model selftest drift")
        ISLAND.facade_interval_model_selftest()
        print("c2-link33-bss-triage-final: SELFTEST PASS floor=115 facade=15")
        return 0
    value = check() if args.action == "check" else build()
    print("c2-link33-bss-triage-final: " + value["status"])
    return 0 if str(value["status"]).startswith("passed") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LinkError, PRE.GateError, ISLAND.GateError, OSError, ValueError,
            KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(f"c2-link33-bss-triage-final: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
