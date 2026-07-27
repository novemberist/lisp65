#!/usr/bin/env python3
"""Build and evaluate the zero-growth Link-44 OP_CLOSURE hold diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
from typing import Any

import c2_lite_v6_link44_vm_run_dir_latch_hw as CYCLE1
import c2_product_hw_presmoke as HW


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / "build/c2.2/substitution/product-link-44-c2-lite-v6-bank2-target-stage-replay"
BASE_PRODUCT = BASE / "lisp65-c2-substitution-linked.prg"
BASE_SHA = "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926"
BASE_RECEIPT = EVIDENCE / "c2.2-product-link44-c2-lite-v6-bank2-target-stage-replay-structural-receipt.json"
FEASIBILITY = EVIDENCE / "c2.2-link44-op-closure-postlink-patch-feasibility-receipt.json"
FEASIBILITY_SHA = "2130ba26be03b1a60745eb63ff8f9c643707ae1efc534f2582701c08d7d2e0e2"
CYCLE1_CORRECTION = EVIDENCE / "c2.2-link44-vm-run-dir-latch-hardware-cycle1-interpretation-correction.json"
CYCLE1_CORRECTION_SHA = "c5649f1566a277328a59a52a1d0e056fe9458c0e11ae3ef36f26be4c9a7bf76b"
SHELF = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"

OUT = ROOT / "build/c2.2/substitution/link44-op-closure-hold-cycle2"
PRODUCT = OUT / "lisp65-link44-op-closure-hold-cycle2-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-patch-manifest.json"
PATCH_RECEIPT = EVIDENCE / "c2.2-link44-op-closure-hold-cycle2-patch-receipt.json"
HW_OUT = ROOT / "build/c2.2/hardware-link44-op-closure-hold-cycle2"
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / "c2.2-link44-op-closure-hold-hardware-cycle2-receipt.json"

LOAD_ADDRESS = 0x2001
INSTRUCTION_ADDRESS = 0x8755
INSTRUCTION_FILE_OFFSET = 0x6756
BEFORE = bytes.fromhex("a2064c346a")
AFTER = bytes.fromhex("a2064c5587")
CHANGED_FILE_OFFSETS = (0x6759, 0x675A)
TEST_FORM = "(list(peek 255 132)(peek 255 131)(peek 255 132))"
ZP_START, ZP_END = 0x0016, 0x001C
VM_START, VM_END = 0xBFD9, 0xC023
OP_CLOSURE = 0x3F


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise GateError(f"missing {label}: {path}: {exc}") from exc
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"{label} is not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid {label}: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root is not an object")
    return value


def source_paths() -> dict[str, Path]:
    return {
        "product": BASE_PRODUCT,
        "elf": BASE / "lisp65-c2-substitution-linked.prg.elf",
        "map": BASE / "lisp65-c2-substitution-linked.prg.map",
        "window": BASE / "c2-product-kernal-window.bin",
        "boot_family": BASE / "runtime-overlays-boot-final.bin",
        "session_family": BASE / "runtime-overlays-session-final.bin",
        "shelf": SHELF,
        "c2d": BASE / "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin",
        "bank2_static": BASE / "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin",
        "contract": BASE / "resolved-profile.txt",
        "stage_header": BASE / "stage-config.h",
    }


def prerequisites() -> dict[str, Any]:
    paths = source_paths()
    for name, path in paths.items():
        regular(path, f"Link-44 {name}")
    require(sha(BASE_PRODUCT) == BASE_SHA, "Link-44 product authority drift")
    require(sha(FEASIBILITY) == FEASIBILITY_SHA,
            "post-link feasibility authority drift")
    require(sha(CYCLE1_CORRECTION) == CYCLE1_CORRECTION_SHA,
            "Class-B cycle-1 correction authority drift")
    feasibility = load_json(FEASIBILITY, "post-link feasibility receipt")
    require(feasibility.get("status") ==
            "passed-zero-growth-postlink-hold-patch-feasibility-hardware-not-run",
            "post-link feasibility is not green")
    require(feasibility.get("promotable") is False,
            "post-link feasibility lost its nonpromotable boundary")
    correction = load_json(CYCLE1_CORRECTION, "cycle-1 correction")
    require(correction.get("status") ==
            "corrected-site1-silent-no-lookup-identity",
            "Class-B cycle 1 does not authorize the second site")
    base = load_json(BASE_RECEIPT, "Link-44 structural receipt")
    require(base.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-44 structural authority is not green")
    require(base.get("product_identity", {}).get("product", {}).get("sha256") == BASE_SHA,
            "Link-44 receipt product binding drift")
    return {
        "link44_product": bind(BASE_PRODUCT),
        "link44_elf": bind(paths["elf"]),
        "link44_map": bind(paths["map"]),
        "link44_structural_receipt": bind(BASE_RECEIPT),
        "postlink_feasibility": bind(FEASIBILITY),
        "cycle1_interpretation_correction": bind(CYCLE1_CORRECTION),
    }


def patch_bytes(source: bytes) -> bytes:
    require(len(source) == 41542, "Link-44 product size drift")
    require(int.from_bytes(source[:2], "little") == LOAD_ADDRESS,
            "Link-44 PRG load address drift")
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 5] == BEFORE,
            "Link-44 OP_CLOSURE negative edge drift")
    result = bytearray(source)
    result[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 5] = AFTER
    return bytes(result)


def exact_patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(len(candidate) == len(source), "post-link patch changed file size")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == list(CHANGED_FILE_OFFSETS),
            f"post-link patch changed unexpected bytes: {changed}")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 5] == AFTER,
            "post-link patch does not encode the exact self-loop")
    mutations: dict[str, bytearray] = {}
    mutations["wrong-low-target-byte"] = bytearray(candidate)
    mutations["wrong-low-target-byte"][CHANGED_FILE_OFFSETS[0]] ^= 1
    mutations["wrong-high-target-byte"] = bytearray(candidate)
    mutations["wrong-high-target-byte"][CHANGED_FILE_OFFSETS[1]] ^= 1
    mutations["only-one-operand-changed"] = bytearray(candidate)
    mutations["only-one-operand-changed"][CHANGED_FILE_OFFSETS[1]] = source[CHANGED_FILE_OFFSETS[1]]
    mutations["opcode-changed"] = bytearray(candidate)
    mutations["opcode-changed"][INSTRUCTION_FILE_OFFSET + 2] = 0x20
    mutations["extra-neighbour-byte"] = bytearray(candidate)
    mutations["extra-neighbour-byte"][INSTRUCTION_FILE_OFFSET + 5] ^= 1
    rejected: dict[str, str] = {}
    for name, mutated in mutations.items():
        try:
            exact_patch_gate_no_mutations(source, bytes(mutated))
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"post-link mutation accepted: {name}")
    return {
        "status": "passed-exact-two-operand-byte-self-loop-patch",
        "instruction_address": "0x8755",
        "instruction_file_offset": "0x6756",
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "changed_file_offsets": ["0x6759", "0x675a"],
        "changed_cpu_addresses": ["0x8758", "0x8759"],
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
    }


def exact_patch_gate_no_mutations(source: bytes, candidate: bytes) -> None:
    require(len(candidate) == len(source), "size mutation")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == list(CHANGED_FILE_OFFSETS), "diff-domain mutation")
    require(candidate[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 5] == AFTER,
            "instruction mutation")


def classify_obj(raw: int) -> dict[str, Any]:
    if raw == 0:
        return {"domain": "NIL", "valid_op_closure_target": False}
    if raw & 1:
        signed = raw >> 1
        if signed & 0x4000:
            signed -= 0x8000
        return {"domain": "fixnum", "value": signed,
                "valid_op_closure_target": False}
    if 0xC000 <= raw <= 0xDFFE:
        ordinal = (raw >> 1) - 0x6000
        row: dict[str, Any] = {
            "domain": "BCODE", "directory_ordinal": ordinal,
            "handle_region": "persistent-low" if ordinal < 2048 else "transient-high",
            "valid_op_closure_target": True,
        }
        if ordinal >= 2048:
            row["normalized_transient_ordinal"] = ordinal - 2048
        return row
    if 0xE000 <= raw <= 0xFFFE:
        return {"domain": "SYMI", "symbol_index": (raw >> 1) - 0x7000,
                "valid_op_closure_target": False}
    return {"domain": "heap-pointer", "address": f"0x{raw:04x}",
            "valid_op_closure_target": True,
            "cell_type_required_for_final_interpretation": True}


def reconstruct(zp: bytes, vm: bytes) -> dict[str, Any]:
    require(len(zp) == ZP_END - ZP_START, "ZP capture length drift")
    require(len(vm) == VM_END - VM_START, "VM capture length drift")

    def get(address: int) -> int:
        if ZP_START <= address < ZP_END:
            return zp[address - ZP_START]
        if VM_START <= address < VM_END:
            return vm[address - VM_START]
        raise GateError(f"reconstruction address outside captures: 0x{address:04x}")

    def get16(address: int) -> int:
        return get(address) | (get(address + 1) << 8)

    cursor = get16(0x0016)
    require(VM_START <= cursor and cursor + 2 < VM_END,
            f"frozen bytecode cursor outside captured VM state: 0x{cursor:04x}")
    require(get(cursor) == OP_CLOSURE,
            f"frozen cursor does not point at OP_CLOSURE: 0x{get(cursor):02x}")
    literal_index = get(cursor + 1)
    upvalue_count = get(cursor + 2)
    literal_table = get16(0xC014)
    target_address = literal_table + 2 * literal_index
    require(VM_START <= literal_table < VM_END,
            f"literal table outside captured VM buffer: 0x{literal_table:04x}")
    require(VM_START <= target_address and target_address + 1 < VM_END,
            f"literal target outside captured VM buffer: 0x{target_address:04x}")
    raw = get16(target_address)
    return {
        "status": "reconstructed-op-closure-dir-find-target",
        "bytecode_cursor": f"0x{cursor:04x}",
        "opcode": f"0x{OP_CLOSURE:02x}",
        "literal_index": literal_index,
        "upvalue_count": upvalue_count,
        "literal_table": f"0x{literal_table:04x}",
        "literal_address": f"0x{target_address:04x}",
        "raw_target_obj": f"0x{raw:04x}",
        "target": classify_obj(raw),
    }


def reconstruction_selftest() -> dict[str, str]:
    zp = bytearray(ZP_END - ZP_START)
    vm = bytearray(VM_END - VM_START)
    cursor = 0xBFE0
    table = 0xBFF0
    zp[0:2] = struct.pack("<H", cursor)
    vm[cursor - VM_START:cursor - VM_START + 3] = bytes((OP_CLOSURE, 2, 1))
    vm[0xC014 - VM_START:0xC016 - VM_START] = struct.pack("<H", table)
    vm[table + 4 - VM_START:table + 6 - VM_START] = struct.pack("<H", 0xD000)
    result = reconstruct(bytes(zp), bytes(vm))
    require(result["target"]["handle_region"] == "transient-high"
            and result["target"]["normalized_transient_ordinal"] == 0,
            "synthetic transient-handle reconstruction drift")
    rejected: dict[str, str] = {}
    cases = {
        "wrong-opcode": (bytes(zp), bytes(bytearray(vm[:cursor - VM_START])
                                    + bytes((0x00,)) + vm[cursor - VM_START + 1:])),
        "cursor-outside-capture": (struct.pack("<H", 0x8000) + bytes(4), bytes(vm)),
    }
    for name, pair in cases.items():
        try:
            reconstruct(*pair)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"reconstruction mutation accepted: {name}")
    return {"valid-transient": "passed", **rejected}


def build() -> dict[str, Any]:
    require(not OUT.exists() and not PATCH_RECEIPT.exists(),
            "Class-B cycle-2 patch identity already exists")
    authority = prerequisites()
    source = regular(BASE_PRODUCT, "Link-44 product")
    candidate = patch_bytes(source)
    gate = exact_patch_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    require(sha(PRODUCT) != BASE_SHA, "diagnostic identity equals Link 44")
    manifest = {
        "format": "lisp65-c2-lite-v6-link44-op-closure-hold-patch-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-nonpromotable-zero-growth-class-b-cycle2-patch",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3,
                       "question": "OP_CLOSURE dir_find target identity"},
        "authority": authority,
        "diagnostic_identity": bind(PRODUCT),
        "patch_gate": gate,
        "capture_contract": {
            "count": 3,
            "spacing": ["hold+0ms", "hold+250ms", "hold+1000ms"],
            "ranges": ["0x0016:0x001c", "0xbfd9:0xc023"],
            "required": "all range pairs byteidentical before reconstruction",
        },
        "capacity_effect": {
            "product_file_bytes": 0, "bank0_text_bytes": 0,
            "ordinary_bank0_bss_bytes": 0, "fixed_hot_block_bytes": 0,
            "resident_island_bytes": 0, "e000_bytes": 0,
            "runtime_overlay_bytes": 0,
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0, "hardware_runs": 0,
            "diagnostic_byte_patches": 1, "changed_bytes": 2,
            "promotable_product_links": 0,
        },
        "claim_limit": (
            "A unique, permanently nonpromotable two-byte diagnostic identity. "
            "No product, capacity, latency, acceptance or promotion claim."),
        "next_gate": "one announced Class-B cycle-2 hardware run",
    }
    write_json(MANIFEST, manifest)
    receipt = {**manifest, "patch_manifest": bind(MANIFEST),
               "reconstruction_selftest": reconstruction_selftest()}
    write_json(PATCH_RECEIPT, receipt)
    for path in (PRODUCT, MANIFEST, PATCH_RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return receipt


def check() -> dict[str, Any]:
    prerequisites()
    receipt = load_json(PATCH_RECEIPT, "cycle-2 patch receipt")
    require(receipt.get("status") ==
            "passed-nonpromotable-zero-growth-class-b-cycle2-patch"
            and receipt.get("promotable") is False,
            "cycle-2 patch boundary drift")
    require(bind(PRODUCT) == receipt.get("diagnostic_identity"),
            "cycle-2 diagnostic identity drift")
    exact_patch_gate(regular(BASE_PRODUCT), regular(PRODUCT))
    require(all(value == 0 for value in receipt["capacity_effect"].values()),
            "cycle-2 patch has nonzero capacity effect")
    reconstruction_selftest()
    return receipt


def prepare_hardware() -> dict[str, Any]:
    patch = check()
    require(not HW_OUT.exists() and not HARDWARE_RECEIPT.exists(),
            "cycle-2 hardware deployment or result already exists")
    paths = source_paths()
    HW_OUT.mkdir(parents=True)
    stage, chain = CYCLE1.build_stage(paths, HW_OUT)
    preloads = [
        bind(paths["c2d"], HW.C2D_STAGE),
        bind(stage, HW.BOOT_OVERLAY_STAGE),
        bind(paths["session_family"], HW.SESSION_FAMILY_STAGE),
        bind(paths["shelf"], HW.SHELF_STAGE),
        bind(paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        bind(paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    deployment = {
        "format": "lisp65-c2-lite-v6-op-closure-hold-hardware-deployment-v1",
        "status": "ready-nonpromotable-class-b-cycle2-hardware-not-run",
        "promotable": False,
        "delegation": {"class": "B", "cycle": "2-of-3"},
        "product": bind(PRODUCT, LOAD_ADDRESS),
        "preloads": preloads,
        "boot_chain": chain,
        "input_contract": {"exact_form_count": 1, "forms": [TEST_FORM],
                           "additional_forms_forbidden": True},
        "capture_contract": patch["capture_contract"],
        "authority": {"patch_receipt": bind(PATCH_RECEIPT),
                      "link44_elf": bind(paths["elf"]),
                      "link44_map": bind(paths["map"])},
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
        "execution_accounting": {"compiler_runs": 0, "linker_runs": 0,
                                 "hardware_runs": 0,
                                 "class_b_cycles_consumed": 1},
        "claim_limit": (
            "One nonpromotable Class-B cycle-2 hardware diagnosis only; no "
            "product, acceptance, latency or promotion claim."),
    }
    require(all(deployment["span_checks"].values()), "deployment span overlap")
    write_json(DEPLOYMENT, deployment)
    for path in HW_OUT.iterdir():
        if path.is_file():
            os.chmod(path, 0o444)
    return deployment


def verify_hardware() -> dict[str, Any]:
    check()
    deployment = load_json(DEPLOYMENT, "cycle-2 hardware deployment")
    require(deployment.get("status") ==
            "ready-nonpromotable-class-b-cycle2-hardware-not-run"
            and deployment.get("promotable") is False,
            "cycle-2 hardware deployment boundary drift")
    require(bind(PRODUCT, LOAD_ADDRESS) == deployment.get("product"),
            "deployed diagnostic identity drift")
    paths = source_paths()
    expected = [
        (paths["c2d"], HW.C2D_STAGE),
        (HW_OUT / "boot-overlay.stage.bin", HW.BOOT_OVERLAY_STAGE),
        (paths["session_family"], HW.SESSION_FAMILY_STAGE),
        (paths["shelf"], HW.SHELF_STAGE),
        (paths["boot_family"], HW.BOOT_FAMILY_STAGE),
        (paths["window"], HW.KERNAL_WINDOW_STAGE),
    ]
    rows = deployment.get("preloads", [])
    require(len(rows) == len(expected), "cycle-2 preload count drift")
    for row, (path, address) in zip(rows, expected):
        require(row == bind(path, address), f"cycle-2 preload drift: {path.name}")
    require(all(deployment.get("span_checks", {}).values()), "span gate drift")
    require(not HARDWARE_RECEIPT.exists(), "Class-B cycle 2 already consumed")
    return deployment


def static_entry_name(ordinal: int) -> dict[str, Any] | None:
    return CYCLE1.static_entry_name(ordinal) if ordinal < 588 else None


def evaluate_hardware() -> dict[str, Any]:
    deployment = verify_hardware()
    timing = load_json(HW_OUT / "capture-timing.json", "capture timing")
    require(timing.get("reference") == "form-return-submitted"
            and len(timing.get("captures", [])) == 3,
            "capture timing contract drift")
    zp_paths = [HW_OUT / f"capture-{index}-zp-0016-001b.bin"
                for index in range(1, 4)]
    vm_paths = [HW_OUT / f"capture-{index}-vm-bfd9-c022.bin"
                for index in range(1, 4)]
    zp = [regular(path, "ZP capture") for path in zp_paths]
    vm = [regular(path, "VM capture") for path in vm_paths]
    zp_stable = all(item == zp[0] for item in zp[1:])
    vm_stable = all(item == vm[0] for item in vm[1:])
    if not zp_stable or not vm_stable:
        zp_drift = [
            {"address": f"0x{ZP_START + offset:04x}",
             "values": [f"0x{capture[offset]:02x}" for capture in zp]}
            for offset in range(len(zp[0]))
            if len({capture[offset] for capture in zp}) != 1
        ]
        vm_drift = [
            {"address": f"0x{VM_START + offset:04x}",
             "values": [f"0x{capture[offset]:02x}" for capture in vm]}
            for offset in range(len(vm[0]))
            if len({capture[offset] for capture in vm}) != 1
        ]
        captures = []
        for index, (zp_path, vm_path, when) in enumerate(
                zip(zp_paths, vm_paths, timing["captures"]), start=1):
            captures.append({
                "capture": index,
                "elapsed_after_form_return_ms": when["elapsed_after_form_return_ms"],
                "zp": {**bind(zp_path), "hex": zp[index - 1].hex()},
                "vm": bind(vm_path),
            })
        receipt = {
            "format": "lisp65-c2-lite-v6-link44-op-closure-hold-hardware-cycle2-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: Class-B cycle 2 capture-stability contract failed",
            "promotable": False,
            "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3,
                           "consumed": 2},
            "authorization": bind(PATCH_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "diagnostic_identity": bind(PRODUCT),
            "input": {"forms_submitted": 1, "form": TEST_FORM,
                      "additional_forms_submitted": 0},
            "first_red": {
                "gate": "three time-separated raw capture pairs must be byteidentical",
                "zp_byteidentical": zp_stable,
                "vm_byteidentical": vm_stable,
                "zp_drift": zp_drift,
                "vm_drift": vm_drift,
                "capture1_equals_capture3_zp": zp[0] == zp[2],
                "capture1_equals_capture2_vm": vm[0] == vm[1],
                "capture1_equals_capture3_vm": vm[0] == vm[2],
                "interpretation": (
                    "Only $0016/$0017 changed, from $cfce to $0101 and back; "
                    "the remaining four ZP bytes and all 74 VM bytes stayed exact. "
                    "The commissioned cursor provenance is therefore not stable "
                    "under real JTAG/IRQ observation and reconstruction is forbidden."),
            },
            "capture_timing": bind(HW_OUT / "capture-timing.json"),
            "captures": captures,
            "budgets": {
                "class_b_diagnostic_cycles": "2/3 consumed",
                "line1_product_first_reds": "2/3 unchanged",
                "completed_latency_measurements": "0/2 unchanged",
            },
            "execution_accounting": {
                "compiler_runs": 0, "linker_runs": 0,
                "diagnostic_byte_patches": 1, "changed_bytes": 2,
                "hardware_runs": 1, "read_only_post_stop_captures": 6,
                "remaining_class_b_cycles": 1,
            },
            "claim_limit": (
                "This is a nonpromotable diagnostic First Red. The failing "
                "lookup identity is not claimed or reconstructed."),
            "next_action": (
                "Review the falsified cursor-provenance model before any Class-B "
                "cycle 3; no autonomous retry."),
            "device_state": "intentionally held in the $8755 self-loop; safe to power off",
            "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        }
        write_json(HARDWARE_RECEIPT, receipt)
        for path in HW_OUT.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o444)
        os.chmod(HW_OUT, 0o555)
        os.chmod(HARDWARE_RECEIPT, 0o444)
        return receipt
    decoded = reconstruct(zp[0], vm[0])
    target = decoded["target"]
    if target.get("domain") == "BCODE" and target.get("directory_ordinal", 9999) < 588:
        target["static_entry"] = static_entry_name(target["directory_ordinal"])
    screen_paths = [HW_OUT / "before-expression.png",
                    HW_OUT / "before-expression.ansi.txt",
                    HW_OUT / "before-expression.txt"]
    for path in screen_paths:
        regular(path, "pre-expression screen evidence")
    captures = []
    for index, (zp_path, vm_path, when) in enumerate(
            zip(zp_paths, vm_paths, timing["captures"]), start=1):
        captures.append({
            "capture": index,
            "elapsed_after_form_return_ms": when["elapsed_after_form_return_ms"],
            "zp": bind(zp_path), "vm": bind(vm_path),
        })
    receipt = {
        "format": "lisp65-c2-lite-v6-link44-op-closure-hold-hardware-cycle2-v1",
        "recorded_on": "2026-07-22",
        "status": "captured-op-closure-failing-dir-find-target",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3,
                       "consumed": 2},
        "authorization": bind(PATCH_RECEIPT),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT),
        "input": {"forms_submitted": 1, "form": TEST_FORM,
                  "additional_forms_submitted": 0},
        "capture_stability": {
            "count": 3, "zp_byteidentical": True, "vm_byteidentical": True,
            "timing": bind(HW_OUT / "capture-timing.json"),
            "captures": captures,
        },
        "reconstruction": decoded,
        "budgets": {
            "class_b_diagnostic_cycles": "2/3 consumed",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_byte_patches": 1, "changed_bytes": 2,
            "hardware_runs": 1, "read_only_post_stop_captures": 6,
            "remaining_class_b_cycles": 1,
        },
        "claim_limit": (
            "The raw OP_CLOSURE target at the single negative dir_find edge is "
            "identified. This nonpromotable run proves no product fix, latency, "
            "acceptance or promotion."),
        "disposition": (
            "The diagnostic identity remains isolated under its Class-B path, "
            "read-only and permanently excluded from candidate/archive mixing."),
        "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
    }
    write_json(HARDWARE_RECEIPT, receipt)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "build", "check", "prepare-hardware",
        "verify-hardware", "evaluate-hardware"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            prerequisites()
            exact_patch_gate(regular(BASE_PRODUCT), patch_bytes(regular(BASE_PRODUCT)))
            reconstruction_selftest()
            print("c2-link44-op-closure-hold: SELFTEST PASS patch_mutations=5")
            return 0
        if args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        elif args.action == "prepare-hardware":
            value = prepare_hardware()
        elif args.action == "verify-hardware":
            value = verify_hardware()
        else:
            value = evaluate_hardware()
        print("c2-link44-op-closure-hold: " + str(value["status"]))
        return 0
    except Exception as exc:
        print("c2-link44-op-closure-hold: FAIL " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
