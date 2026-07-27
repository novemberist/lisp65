#!/usr/bin/env python3
"""Prepare and evaluate the final Class-B Link-44 OP_CLOSURE diagnosis."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

import c2_lite_v6_link44_op_closure_cycle3_feasibility as FEAS
import c2_lite_v6_link44_op_closure_hold_hw as CYCLE2
import c2_lite_v6_link44_vm_run_dir_latch_hw as CYCLE1
import c2_product_hw_presmoke as HW


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FEASIBILITY = EVIDENCE / (
    "c2.2-link44-op-closure-cycle3-stable-descriptor-feasibility-receipt.json")
FEASIBILITY_SHA = "b503949a495514ca3ecd694dd2705f8eef6cb9e506204a9f5325050bf31e77ba"
OUT = ROOT / "build/c2.2/hardware-link44-op-closure-stable-descriptor-cycle3"
DEPLOYMENT = OUT / "deployment.json"
CAPTURE_PLAN = OUT / "descriptor-capture-plan.json"
NAME_PLAN = OUT / "name-capture-plan.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link44-op-closure-stable-descriptor-hardware-cycle3-receipt.json")
TEST_FORM = "(list(peek 255 132)(peek 255 131)(peek 255 132))"


class DiagnosticError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise DiagnosticError(f"missing {label}: {path}: {exc}") from exc
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"{label} must be regular and symlink-free: {path}")
    return path.read_bytes()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": digest(data),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"invalid {label}: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root is not an object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prerequisite_gate() -> tuple[dict[str, Any], dict[str, Path]]:
    require(digest(regular(FEASIBILITY)) == FEASIBILITY_SHA,
            "cycle-3 feasibility authority drift")
    feasibility = load_json(FEASIBILITY, "cycle-3 feasibility receipt")
    require(feasibility.get("status") ==
            "passed-final-cycle-stable-descriptor-feasibility-hardware-not-run",
            "cycle-3 feasibility is not green")
    require(feasibility.get("promotable") is False,
            "cycle-3 feasibility lost its nonpromotable boundary")
    CYCLE2.check()
    paths = CYCLE2.source_paths()
    for name, path in paths.items():
        regular(path, f"Link-44 {name}")
    return feasibility, paths


def prepare() -> dict[str, Any]:
    feasibility, paths = prerequisite_gate()
    require(not OUT.exists() and not HARDWARE_RECEIPT.exists(),
            "cycle-3 deployment or result already exists")
    OUT.mkdir(parents=True)
    stage, chain = CYCLE1.build_stage(paths, OUT)
    preloads = [
        bind(paths["c2d"], HW.C2D_STAGE),
        bind(stage, HW.BOOT_OVERLAY_STAGE),
        bind(paths["session_family"], HW.SESSION_FAMILY_STAGE),
        bind(paths["shelf"], HW.SHELF_STAGE),
        bind(paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        bind(paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    deployment = {
        "format": "lisp65-c2-lite-v6-op-closure-cycle3-hardware-deployment-v1",
        "recorded_on": "2026-07-22",
        "status": "ready-final-nonpromotable-class-b-cycle3-hardware-not-run",
        "promotable": False,
        "delegation": {"class": "B", "cycle": "3-of-3", "consumed": 2},
        "product": bind(CYCLE2.PRODUCT, CYCLE2.LOAD_ADDRESS),
        "deployment_identity": {
            "rule": "diagnostic product SHA plus this capture-contract manifest SHA",
            "product_bytes_reused_from_cycle2": True,
            "reason": (
                "The exact hold edge is unchanged; duplicating byteidentical product "
                "bytes would create a false identity. The capture contract is new."),
        },
        "preloads": preloads,
        "boot_chain": chain,
        "input_contract": {
            "exact_form_count": 1,
            "forms": [TEST_FORM],
            "additional_forms_forbidden": True,
        },
        "capture_contract": feasibility["prospective_capture_contract"],
        "authority": {
            "cycle3_feasibility": bind(FEASIBILITY),
            "cycle2_immutable_hold_product": bind(CYCLE2.PRODUCT),
            "link44_elf": bind(paths["elf"]),
            "link44_map": bind(paths["map"]),
        },
        "span_checks": {
            "c2d_before_boot_stage":
                HW.C2D_STAGE + paths["c2d"].stat().st_size <= HW.BOOT_OVERLAY_STAGE,
            "session_before_shelf":
                HW.SESSION_FAMILY_STAGE + paths["session_family"].stat().st_size <= HW.SHELF_STAGE,
            "shelf_before_boot":
                HW.SHELF_STAGE + paths["shelf"].stat().st_size <= HW.BOOT_FAMILY_STAGE,
            "window_ends_at_attic_limit":
                HW.KERNAL_WINDOW_STAGE + paths["window"].stat().st_size == 0x08800000,
        },
        "capacity_effect": {
            "product_file_bytes": 0, "bank0_text_bytes": 0,
            "ordinary_bank0_bss_bytes": 0, "fixed_hot_block_bytes": 0,
            "resident_island_bytes": 0, "e000_bytes": 0,
            "runtime_overlay_bytes": 0,
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "promotable_product_links": 0, "new_patch_operations": 0,
            "hardware_runs": 0, "class_b_cycles_consumed": 2,
        },
        "claim_limit": (
            "One final nonpromotable Class-B diagnosis only; no product, capacity, "
            "latency, acceptance or promotion claim."),
    }
    require(all(deployment["span_checks"].values()), "deployment span overlap")
    write_json(DEPLOYMENT, deployment)
    for path in OUT.iterdir():
        if path.is_file():
            os.chmod(path, 0o444)
    verify()
    return deployment


def verify() -> dict[str, Any]:
    _, paths = prerequisite_gate()
    deployment = load_json(DEPLOYMENT, "cycle-3 deployment")
    require(deployment.get("status") ==
            "ready-final-nonpromotable-class-b-cycle3-hardware-not-run"
            and deployment.get("promotable") is False,
            "cycle-3 deployment boundary drift")
    require(deployment.get("product") == bind(CYCLE2.PRODUCT,
                                               CYCLE2.LOAD_ADDRESS),
            "cycle-3 deployed diagnostic identity drift")
    expected = [
        (paths["c2d"], HW.C2D_STAGE),
        (OUT / "boot-overlay.stage.bin", HW.BOOT_OVERLAY_STAGE),
        (paths["session_family"], HW.SESSION_FAMILY_STAGE),
        (paths["shelf"], HW.SHELF_STAGE),
        (paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        (paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    rows = deployment.get("preloads", [])
    require(len(rows) == len(expected), "cycle-3 preload count drift")
    for row, (path, address) in zip(rows, expected):
        require(row == bind(path, address), f"cycle-3 preload drift: {path.name}")
    require(all(deployment.get("span_checks", {}).values()), "span gate drift")
    require(all(value == 0 for value in
                deployment.get("capacity_effect", {}).values()),
            "cycle-3 deployment has a capacity debit")
    require(not HARDWARE_RECEIPT.exists(), "Class-B cycle 3 already consumed")
    return deployment


def descriptor_paths() -> list[Path]:
    return [OUT / f"capture-{index}-dma-list-ba00-ba0b.bin"
            for index in range(1, 4)]


def nameoff_paths() -> list[Path]:
    return [OUT / f"capture-{index}-nameoff.bin" for index in range(1, 4)]


def name_paths() -> list[Path]:
    return [OUT / f"capture-{index}-symbol-name-window.bin"
            for index in range(1, 4)]


def capture_plan() -> dict[str, Any]:
    verify()
    require(not CAPTURE_PLAN.exists(), "descriptor capture plan already exists")
    captures = [regular(path, "DMA descriptor capture")
                for path in descriptor_paths()]
    plan: dict[str, Any] = {
        "format": "lisp65-c2-link44-cycle3-descriptor-capture-plan-v1",
        "descriptor_captures": [bind(path) for path in descriptor_paths()],
        "byteidentical": all(item == captures[0] for item in captures[1:]),
    }
    try:
        require(plan["byteidentical"],
                "three DMA descriptor captures are not byteidentical")
        decoded = FEAS.descriptor_identity(captures[0])
        start = int(decoded["nameoff_physical_address"], 16)
        plan.update({
            "status": "passed-stable-descriptor-ready-for-nameoff-capture",
            "descriptor_hex": captures[0].hex(),
            "decoded_identity": decoded,
            "nameoff_capture": {
                "start": f"0x{start:08x}",
                "end_exclusive": f"0x{start + 2:08x}",
                "bytes": 2,
            },
        })
    except (DiagnosticError, FEAS.GateError) as exc:
        plan.update({"status": "FIRST RED: descriptor stability/provenance failed",
                     "error": str(exc)})
    write_json(CAPTURE_PLAN, plan)
    os.chmod(CAPTURE_PLAN, 0o444)
    return plan


def name_plan() -> dict[str, Any]:
    require(not NAME_PLAN.exists(), "name capture plan already exists")
    descriptor = load_json(CAPTURE_PLAN, "descriptor capture plan")
    require(descriptor.get("status") ==
            "passed-stable-descriptor-ready-for-nameoff-capture",
            "stable descriptor is absent")
    captures = [regular(path, "nameoff capture") for path in nameoff_paths()]
    plan: dict[str, Any] = {
        "format": "lisp65-c2-link44-cycle3-name-capture-plan-v1",
        "nameoff_captures": [bind(path) for path in nameoff_paths()],
        "byteidentical": all(item == captures[0] for item in captures[1:]),
    }
    try:
        require(all(len(item) == 2 for item in captures),
                "nameoff capture length drift")
        require(plan["byteidentical"],
                "three nameoff captures are not byteidentical")
        offset = int.from_bytes(captures[0], "little")
        require(0 <= offset < FEAS.NAMEPOOL_BYTES,
                "symbol name offset is outside the canonical namepool")
        start = 0x00050000 + FEAS.SYMPOOL_EXT_OFF + offset
        count = min(FEAS.SYMBOL_NAME_BYTES, FEAS.NAMEPOOL_BYTES - offset)
        require(count > 0, "symbol name capture window is empty")
        plan.update({
            "status": "passed-stable-nameoff-ready-for-name-capture",
            "nameoff": offset,
            "nameoff_hex": captures[0].hex(),
            "name_capture": {
                "start": f"0x{start:08x}",
                "end_exclusive": f"0x{start + count:08x}",
                "bytes": count,
            },
        })
    except DiagnosticError as exc:
        plan.update({"status": "FIRST RED: nameoff stability/provenance failed",
                     "error": str(exc)})
    write_json(NAME_PLAN, plan)
    os.chmod(NAME_PLAN, 0o444)
    return plan


def _write_hardware_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    write_json(HARDWARE_RECEIPT, receipt)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return receipt


def evaluate() -> dict[str, Any]:
    deployment = verify()
    timing = load_json(OUT / "capture-timing.json", "capture timing")
    require(timing.get("reference") == "form-return-submitted",
            "cycle-3 capture timing reference drift")
    descriptor = load_json(CAPTURE_PLAN, "descriptor capture plan")
    base: dict[str, Any] = {
        "recorded_on": "2026-07-22",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 3,
                       "cycle_cap": 3, "consumed": 3},
        "authorization": bind(FEASIBILITY),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(CYCLE2.PRODUCT),
        "input": {"forms_submitted": 1, "form": TEST_FORM,
                  "additional_forms_submitted": 0},
        "capture_timing": bind(OUT / "capture-timing.json"),
        "budgets": {
            "class_b_diagnostic_cycles": "3/3 consumed; no fourth cycle",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_byte_patches": 0,
            "changed_bytes_relative_to_cycle2_hold": 0,
            "hardware_runs": 1,
            "remaining_class_b_cycles": 0,
        },
        "link44_rollback": {**bind(CYCLE2.BASE_PRODUCT), "status": "untouched"},
        "device_state": "intentionally held in the $8755 self-loop; safe to power off",
    }
    if descriptor.get("status") != \
            "passed-stable-descriptor-ready-for-nameoff-capture":
        return _write_hardware_receipt({
            **base,
            "format": "lisp65-c2-link44-op-closure-cycle3-first-red-v1",
            "status": "FIRST RED: final Class-B descriptor capture failed",
            "descriptor_capture_plan": bind(CAPTURE_PLAN),
            "claim_limit": "No lookup identity is claimed; no fourth Class-B cycle exists.",
            "next_action": "Class-C review for permanent product diagnosticability",
        })
    nameoff = load_json(NAME_PLAN, "name capture plan")
    if nameoff.get("status") != "passed-stable-nameoff-ready-for-name-capture":
        return _write_hardware_receipt({
            **base,
            "format": "lisp65-c2-link44-op-closure-cycle3-partial-v1",
            "status": "captured-raw-lookup-identity-name-enrichment-first-red",
            "descriptor_capture_plan": bind(CAPTURE_PLAN),
            "raw_lookup_identity": descriptor["decoded_identity"],
            "name_capture_plan": bind(NAME_PLAN),
            "claim_limit": (
                "The raw SYMI and symbol index are exact; a symbolic name is not "
                "claimed. No fourth Class-B cycle exists."),
            "next_action": "Class-C review using the exact raw lookup identity",
        })
    names = [regular(path, "symbol name capture") for path in name_paths()]
    require(all(len(item) == int(nameoff["name_capture"]["bytes"])
                for item in names), "symbol name capture length drift")
    stable = all(item == names[0] for item in names[1:])
    if not stable:
        return _write_hardware_receipt({
            **base,
            "format": "lisp65-c2-link44-op-closure-cycle3-partial-v1",
            "status": "captured-raw-lookup-identity-name-window-first-red",
            "descriptor_capture_plan": bind(CAPTURE_PLAN),
            "raw_lookup_identity": descriptor["decoded_identity"],
            "name_capture_plan": bind(NAME_PLAN),
            "name_captures": [bind(path) for path in name_paths()],
            "claim_limit": (
                "The raw SYMI and symbol index are exact; a symbolic name is not "
                "claimed because its captures drifted. No fourth Class-B cycle exists."),
            "next_action": "Class-C review using the exact raw lookup identity",
        })
    nul = names[0].find(b"\0")
    require(nul > 0, "captured symbol name lacks a nonempty NUL-terminated prefix")
    raw_name = names[0][:nul]
    try:
        symbol_name = raw_name.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DiagnosticError("captured symbol name is not ASCII") from exc
    require(all(0x20 <= value <= 0x7E for value in raw_name),
            "captured symbol name is not printable")
    require(re.fullmatch(r"_L[0-9]+", symbol_name) is not None,
            "OP_CLOSURE lookup is not the compiler's canonical helper name")
    decoded = descriptor["decoded_identity"]
    receipt = {
        **base,
        "format": "lisp65-c2-link44-op-closure-cycle3-hardware-v1",
        "status": "captured-final-class-b-op-closure-lookup-identity",
        "descriptor_capture": {
            "plan": bind(CAPTURE_PLAN),
            "captures": [bind(path) for path in descriptor_paths()],
            "byteidentical": True,
            "decoded": decoded,
        },
        "symbol_name_capture": {
            "plan": bind(NAME_PLAN),
            "nameoff_captures": [bind(path) for path in nameoff_paths()],
            "name_window_captures": [bind(path) for path in name_paths()],
            "byteidentical": True,
            "nameoff": nameoff["nameoff"],
            "symbol_name": symbol_name,
        },
        "lookup_identity": {
            "raw_target_obj": decoded["raw_target_obj"],
            "domain": "SYMI",
            "symbol_index": decoded["symbol_index"],
            "symbol_name": symbol_name,
            "failed_operation": "OP_CLOSURE dir_find",
        },
        "claim_limit": (
            "The exact lookup identity at the one negative OP_CLOSURE dir_find edge "
            "is established. This nonpromotable run proves no product fix, latency, "
            "acceptance or promotion."),
        "next_action": (
            "Class-C analysis of why this compiler-generated helper lacks a callable "
            "directory binding; no fourth Class-B cycle is authorized."),
    }
    return _write_hardware_receipt(receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "prepare", "verify", "capture-plan", "name-plan", "evaluate"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare()
        elif args.action == "verify":
            result = verify()
        elif args.action == "capture-plan":
            result = capture_plan()
        elif args.action == "name-plan":
            result = name_plan()
        else:
            result = evaluate()
        print("c2-link44-op-closure-cycle3-hw: " + str(result["status"]))
        return 0
    except Exception as exc:
        print("c2-link44-op-closure-cycle3-hw: FAIL " + str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
