#!/usr/bin/env python3
"""Instantiate and run the qualified zero-byte Link-51 BADOPCODE hold."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any

from c2_badopcode_hold_shelf_gate import qualify
import c2_lite_v6_link50_badopcode_hold as historical_hold


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / (
    "build/c2.2/substitution/product-link-51-c2-lite-v6-canonical-t")
BASE_PRODUCT = BASE / "lisp65-c2-substitution-linked.prg"
BASE_ELF = Path(str(BASE_PRODUCT) + ".elf")
BASE_DEPLOYMENT = ROOT / (
    "build/c2.2/hardware-presmoke-link51-canonical-t/deployment.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link51-badopcode-hold-shelf-NONPROMOTABLE")
PRODUCT = OUT / "lisp65-link51-badopcode-hold-shelf-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-patch-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link51-badopcode-hold-shelf-patch-receipt.json")
HW_OUT = ROOT / "build/c2.2/hardware-link51-badopcode-hold-shelf"
DEPLOYMENT = HW_OUT / "deployment.json"
LAUNCH = HW_OUT / "launch.json"
CAPTURE = HW_OUT / "capture-timing.json"
CAPTURE_CORRECTION = HW_OUT / "capture-interpretation-correction.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link51-badopcode-hold-shelf-hardware-receipt.json")
COMPARISON_RECEIPT = EVIDENCE / (
    "c2.2-link51-badopcode-hold-shelf-link50-comparison.json")
HISTORICAL_CORRECTION = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-hold-cycle1-"
    "interpretation-correction.json")
HISTORICAL_HW = ROOT / "build/c2.2/hardware-link50-badopcode-hold-cycle1"
TOOLS = ROOT / "tools/m65tools"
DEVICE = Path("/dev/ttyUSB1")
BEFORE = bytes.fromhex("8617")
AFTER = bytes.fromhex("80fe")


class RunError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RunError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"not a regular symlink-free file: {path}")
    return path.read_bytes()


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(regular(path).decode("utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def patch_gate(source: bytes, candidate: bytes,
               offset: int) -> dict[str, Any]:
    require(len(source) == len(candidate), "patch changed PRG length")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == [offset, offset + 1],
            f"patch diff domain drift: {changed}")
    require(source[offset:offset + 2] == BEFORE,
            "qualified source bytes drift")
    require(candidate[offset:offset + 2] == AFTER,
            "diagnostic self-loop bytes drift")
    rejected: dict[str, str] = {}
    trials: dict[str, bytearray] = {}
    trials["wrong-opcode"] = bytearray(candidate)
    trials["wrong-opcode"][offset] = 0xea
    trials["wrong-relative-target"] = bytearray(candidate)
    trials["wrong-relative-target"][offset + 1] = 0xfc
    trials["only-opcode-changed"] = bytearray(candidate)
    trials["only-opcode-changed"][offset + 1] = BEFORE[1]
    trials["only-operand-changed"] = bytearray(candidate)
    trials["only-operand-changed"][offset] = BEFORE[0]
    trials["extra-neighbour-byte"] = bytearray(candidate)
    trials["extra-neighbour-byte"][offset + 2] ^= 1
    for name, trial in trials.items():
        try:
            patch_gate_shallow(source, bytes(trial), offset)
        except RunError:
            rejected[name] = "rejected"
        else:
            raise RunError(f"patch mutation accepted: {name}")
    return {
        "status": "passed-exact-two-byte-self-loop",
        "changed_file_offsets": [hex(offset), hex(offset + 1)],
        "changed_bytes": 2,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
    }


def patch_gate_shallow(source: bytes, candidate: bytes, offset: int) -> None:
    require(len(source) == len(candidate), "patch changed PRG length")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == [offset, offset + 1], "patch diff domain drift")
    require(candidate[offset:offset + 2] == AFTER, "self-loop bytes drift")


def build() -> dict[str, Any]:
    require(not OUT.exists() and not PATCH_RECEIPT.exists()
            and not HW_OUT.exists(), "Link-51 hold identity already exists")
    qualification = qualify(BASE_PRODUCT, BASE_ELF)
    offset = int(qualification["patch"]["instruction_file_offset"], 16)
    source = regular(BASE_PRODUCT)
    candidate = bytearray(source)
    candidate[offset:offset + 2] = AFTER
    gate = patch_gate(source, bytes(candidate), offset)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    deployment_base = load_json(BASE_DEPLOYMENT)
    manifest = {
        "format": "lisp65-c2-link51-badopcode-hold-shelf-patch-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-nonpromotable-link51-badopcode-hold",
        "promotable": False,
        "trigger": "Link 51 latency-line-2 VM_BADOPCODE recurrence",
        "authority": {
            "base_product": bind(BASE_PRODUCT),
            "base_elf": bind(BASE_ELF),
            "shelf_qualification": qualification,
        },
        "diagnostic_identity": bind(PRODUCT),
        "patch": {**qualification["patch"], **gate},
        "capacity_effect": {
            "bank0_text_bytes": 0,
            "ordinary_bank0_bss_bytes": 0,
            "fixed_hot_block_bytes": 0,
            "resident_island_bytes": 0,
            "e000_bytes": 0,
            "session_family_bytes": 0,
            "runtime_slice_bytes": 0,
            "file_bytes": 0,
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "changed_bytes": 2,
            "hardware_runs": 0,
            "completed_latency_measurements": 0,
        },
        "claim_limit": (
            "SHA-bound fixed-length diagnostic derivative only; never "
            "promotable and never latency or acceptance evidence."),
    }
    write_json(MANIFEST, manifest)
    write_json(PATCH_RECEIPT, {**manifest, "manifest": bind(MANIFEST)})
    HW_OUT.mkdir(parents=True)
    deployment = {
        **deployment_base,
        "format": "lisp65-c2-link51-badopcode-hold-deployment-v1",
        "status": "ready-nonpromotable-badopcode-hold",
        "promotable": False,
        "product": {**bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "base_product": bind(BASE_PRODUCT),
            "authorization_receipt": bind(PATCH_RECEIPT),
            "patch_manifest": bind(MANIFEST),
        },
        "manual_sequence": [
            "wait for banner and REPL",
            "evaluate (defun %c2h()(quote t)); expect %c2h",
            "evaluate the cold measurement form exactly once",
            "on recurrence the machine holds before status clear",
            "enter nothing further before read-only captures",
        ],
    }
    write_json(DEPLOYMENT, deployment)
    for path in (PRODUCT, MANIFEST, PATCH_RECEIPT, DEPLOYMENT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return {"patch_receipt": bind(PATCH_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "diagnostic_identity": bind(PRODUCT),
            "patch": manifest["patch"]}


def verify() -> dict[str, Any]:
    qualification = qualify(BASE_PRODUCT, BASE_ELF)
    receipt = load_json(PATCH_RECEIPT)
    deployment = load_json(DEPLOYMENT)
    require(receipt.get("status") ==
            "passed-nonpromotable-link51-badopcode-hold"
            and receipt.get("promotable") is False,
            "diagnostic receipt status drift")
    require(deployment.get("status") ==
            "ready-nonpromotable-badopcode-hold"
            and deployment.get("promotable") is False,
            "diagnostic deployment status drift")
    require(receipt["authority"]["base_product"] == bind(BASE_PRODUCT)
            and receipt["authority"]["base_elf"] == bind(BASE_ELF),
            "Link-51 authority drift")
    require(deployment["product"]["sha256"] ==
            receipt["diagnostic_identity"]["sha256"],
            "diagnostic identity drift")
    offset = int(qualification["patch"]["instruction_file_offset"], 16)
    patch_gate(regular(BASE_PRODUCT), regular(PRODUCT), offset)
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(bind(path)["sha256"] == row["sha256"]
                and bind(path)["bytes"] == row["bytes"],
                f"preload drift: {path}")
    return deployment


def run_m65(*arguments: str, timeout_seconds: int = 90) -> None:
    command = [str(TOOLS / "m65"), "-l", str(DEVICE), *arguments]
    subprocess.run(command, cwd=ROOT, check=True, timeout=timeout_seconds)


def require_hardware() -> None:
    require((TOOLS / "m65").is_file()
            and os.access(TOOLS / "m65", os.X_OK), "m65 tool absent")
    require(DEVICE.exists() and stat.S_ISCHR(DEVICE.stat().st_mode),
            f"JTAG device absent: {DEVICE}")


def deploy() -> dict[str, Any]:
    value = verify()
    require_hardware()
    require(not LAUNCH.exists(), "diagnostic identity already launched")
    run_m65("-F", "-H", "-1", str(PRODUCT))
    readbacks = []
    for row in value["preloads"]:
        path = ROOT / row["path"]
        address = int(row["address"], 16)
        end = address + row["bytes"]
        readback = HW_OUT / f"readback-{path.name}"
        run_m65("-H", "-@", f"{path}@0x{address:08x}")
        run_m65("--memsave",
                f"0x{address:08x}:0x{end:08x}={readback}")
        require(regular(readback) == regular(path),
                f"preload readback mismatch: {path}")
        readbacks.append(bind(readback, address))
    run_m65("-r", "-1", str(PRODUCT))
    result = {
        "format": "lisp65-c2-link51-badopcode-hold-launch-v1",
        "status": "launched-nonpromotable-badopcode-hold",
        "monotonic_ns": time.monotonic_ns(),
        "deployment": bind(DEPLOYMENT),
        "diagnostic_identity": bind(PRODUCT, 0x2001),
        "preload_readbacks": readbacks,
        "operator_next": value["manual_sequence"],
    }
    write_json(LAUNCH, result)
    os.chmod(LAUNCH, 0o444)
    return result


def capture() -> dict[str, Any]:
    verify()
    require_hardware()
    launch = load_json(LAUNCH)
    require(launch.get("status") ==
            "launched-nonpromotable-badopcode-hold",
            "diagnostic identity was not launched")
    require(not CAPTURE.exists(), "diagnostic capture already exists")
    start = time.monotonic_ns()
    observations = []
    for index in range(1, 4):
        path = HW_OUT / f"held-bank0-{index}.bin"
        run_m65("--memsave", f"0x00000000:0x00010000={path}")
        observations.append({
            "capture": index,
            "elapsed_ms": (time.monotonic_ns() - start) // 1_000_000,
            **bind(path, 0),
        })
        if index != 3:
            time.sleep(0.5)
    banks = {}
    for bank in (2, 3, 5):
        path = HW_OUT / f"held-bank{bank}.bin"
        start_address = bank << 16
        run_m65("--memsave",
                f"0x{start_address:08x}:0x{start_address + 65536:08x}={path}")
        banks[str(bank)] = bind(path, start_address)
    bank0 = [regular(HW_OUT / f"held-bank0-{index}.bin")
             for index in range(1, 4)]
    stable = bank0[0] == bank0[1] == bank0[2]
    result = {
        "format": "lisp65-c2-link51-badopcode-hold-captures-v1",
        "status": ("captured-stable-read-only-hold" if stable
                   else "first-red-bank0-not-stable"),
        "reference": "first JTAG read command start",
        "bank0_captures": observations,
        "bank0_byteidentical": stable,
        "banks": banks,
    }
    write_json(CAPTURE, result)
    os.chmod(CAPTURE, 0o444)
    return result


def evaluate() -> dict[str, Any]:
    deployment = verify()
    timing = load_json(CAPTURE)
    require(timing.get("status") in (
        "captured-stable-read-only-hold", "first-red-bank0-not-stable"),
        "held capture status is not recognized")
    qualification = qualify(BASE_PRODUCT, BASE_ELF)
    symbols = qualification["capture_symbols"]
    banks0 = [regular(HW_OUT / f"held-bank0-{index}.bin")
              for index in range(1, 4)]
    bank0 = banks0[0]
    bank2 = regular(HW_OUT / "held-bank2.bin")
    bank3 = regular(HW_OUT / "held-bank3.bin")
    bank5 = regular(HW_OUT / "held-bank5.bin")
    status_at = int(symbols["vm_status"]["address"], 16)
    require(all(row[status_at] == 2 for row in banks0),
            "machine is not stably held on VM_BADOPCODE")
    fields = {}
    for name, row in symbols.items():
        at = int(row["address"], 16)
        size = row["bytes"] or 1
        values = [capture[at:at + size] for capture in banks0]
        require(values[0] == values[1] == values[2],
                f"held VM field changed across captures: {name}")
        fields[name] = {
            "address": row["address"],
            "bytes": size,
            "hex": values[0].hex(),
        }
    changed_addresses = sorted({
        at for left, right in zip(banks0, banks0[1:])
        for at, pair in enumerate(zip(left, right)) if pair[0] != pair[1]
    })
    contract_ranges = [
        (int(row["address"], 16),
         int(row["address"], 16) + (row["bytes"] or 1))
        for row in symbols.values()
    ]
    require(not any(start <= at < end for at in changed_addresses
                    for start, end in contract_ranges),
            "a contract capture byte changed across reads")
    owner = historical_hold.active_owner_analysis(bank0, bank2, bank5)
    require(owner["active_owner_cache_exact"],
            "held active-owner cache differs from Bank-2 truth")
    correction = {
        "format": "lisp65-c2-link51-badopcode-hold-capture-correction-v1",
        "status": "passed-contract-state-stable-whole-bank-rule-retired",
        "historical_capture": bind(CAPTURE),
        "incorrect_rule": "all 65536 Bank-0 bytes must be byteidentical",
        "correct_rule": (
            "vm_status, vm_codebuf, vm_buf_off and all qualified VM window "
            "state must be byteidentical; unrelated hardware registers may "
            "advance while the CPU self-loops"),
        "changed_addresses": [hex(at) for at in changed_addresses],
        "qualified_fields_stable": sorted(symbols),
        "hardware_runs_added": 0,
        "product_bytes_changed": 0,
    }
    if not CAPTURE_CORRECTION.exists():
        write_json(CAPTURE_CORRECTION, correction)
        os.chmod(CAPTURE_CORRECTION, 0o444)
    else:
        require(load_json(CAPTURE_CORRECTION) == correction,
                "capture interpretation correction drift")
    value = {
        "format": "lisp65-c2-link51-badopcode-hold-hardware-v1",
        "recorded_on": "2026-07-22",
        "status": "captured-intermittent-badopcode-before-status-clear",
        "promotable": False,
        "diagnostic_identity": bind(PRODUCT),
        "authorization": bind(PATCH_RECEIPT),
        "deployment": bind(DEPLOYMENT),
        "capture": bind(CAPTURE),
        "capture_interpretation": bind(CAPTURE_CORRECTION),
        "held_vm_status": bank0[status_at],
        "held_vm_fields": fields,
        "held_active_owner": owner,
        "classification": (
            "active-owner-window-byteidentical-vm-execution-state"),
        "answer": (
            "The recurrence again holds with Bank-2 object and the active "
            "ordinal-171/lcc-run cache window byteidentical. Refill is "
            "exonerated; the intermittent BADOPCODE remains in logical "
            "cursor, dispatch, operand-stack or nested-service state."),
        "captured_planes": {
            "bank2": bind(HW_OUT / "held-bank2.bin", 0x00020000),
            "bank3": bind(HW_OUT / "held-bank3.bin", 0x00030000),
            "bank5": bind(HW_OUT / "held-bank5.bin", 0x00050000),
        },
        "captured_plane_prefixes": {
            "bank2": bank2[:64].hex(),
            "bank3": bank3[:64].hex(),
            "bank5": bank5[:64].hex(),
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "changed_bytes": 2,
            "hardware_runs": 1,
            "completed_latency_measurements": 0,
        },
        "claim_limit": (
            "Nonpromotable read-only diagnostic capture only; no latency, "
            "promotion or acceptance claim."),
        "rollback_line": {**bind(BASE_PRODUCT), "status": "untouched"},
        "preloads": deployment["preloads"],
    }
    write_json(HARDWARE_RECEIPT, value)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return value


def compare() -> dict[str, Any]:
    current = load_json(HARDWARE_RECEIPT)
    historical = load_json(HISTORICAL_CORRECTION)
    require(current.get("status") ==
            "captured-intermittent-badopcode-before-status-clear",
            "current hardware receipt status drift")
    require(historical.get("status") ==
            "corrected-active-owner-refill-exonerated",
            "historical correction status drift")
    now0 = regular(HW_OUT / "held-bank0-1.bin")
    old0 = regular(HISTORICAL_HW / "held-bank0-1.bin")
    now2 = regular(HW_OUT / "held-bank2.bin")
    old2 = regular(HISTORICAL_HW / "held-bank2.bin")
    now5 = regular(HW_OUT / "held-bank5.bin")
    old5 = regular(HISTORICAL_HW / "held-bank5.bin")
    qualification = qualify(BASE_PRODUCT, BASE_ELF)
    symbols = qualification["capture_symbols"]
    exact_fields = {}
    for name in ("vm_buf_off", "vm_codebuf", "vm_buf_bank", "vmr_hdrlen",
                 "vmr_littab", "vmr_code", "vmr_poff", "vmr_plen",
                 "vmr_pwmax", "vmr_win", "vmr_winlen", "vmr_streaming"):
        row = symbols[name]
        at = int(row["address"], 16)
        size = row["bytes"] or 1
        exact_fields[name] = now0[at:at + size] == old0[at:at + size]
    require(all(exact_fields.values()),
            "Link-51 held VM fingerprint differs from Link 50")
    now_owner = historical_hold.active_owner_analysis(now0, now2, now5)
    old_owner = historical_hold.active_owner_analysis(old0, old2, old5)
    require(now_owner == old_owner and now_owner["active_owner_cache_exact"],
            "held active-owner analysis differs across links")
    now_dynamic = historical_hold.entry(now5, 588)
    old_dynamic = historical_hold.entry(old5, 588)
    require(now_dynamic == old_dynamic,
            "published dynamic entry differs across held runs")
    now_code = now2[now_dynamic["code_offset"]:
                    now_dynamic["code_offset"] + now_dynamic["code_length"]]
    old_code = old2[old_dynamic["code_offset"]:
                    old_dynamic["code_offset"] + old_dynamic["code_length"]]
    require(now_code == old_code == historical_hold.EXPECTED_CODE,
            "published dynamic code differs across held runs")
    value = {
        "format": "lisp65-c2-link51-badopcode-link50-comparison-v1",
        "recorded_on": "2026-07-22",
        "status": "same-post-refill-badopcode-fingerprint-reproduced",
        "current_hardware": bind(HARDWARE_RECEIPT),
        "historical_interpretation": bind(HISTORICAL_CORRECTION),
        "exact_vm_fields": exact_fields,
        "active_owner": now_owner,
        "dynamic_entry_588": now_dynamic,
        "dynamic_code_hex": now_code.hex(),
        "c2d_counts": {
            "image_count": int.from_bytes(now5[12:14], "little"),
            "entry_count": int.from_bytes(now5[16:18], "little"),
            "resolution_count": int.from_bytes(now5[20:22], "little"),
        },
        "conclusion": (
            "Link 51 reproduces Link 50's byte-exact post-refill state: "
            "dynamic Entry 588 is published and exact, and restored "
            "ordinal 171/lcc-run owns an exact final streamed window. The "
            "outer hold cannot distinguish logical cursor, dispatch, "
            "operand-stack or nested-service origin after unwind."),
        "stop_rule": (
            "Do not infer a product fix or repeat this outer hold. A next "
            "step must provide a proved live inner execution witness or be "
            "an explicit product-scope decision."),
        "execution_accounting": {
            "hardware_runs_added": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_bytes_changed": 0,
            "completed_latency_measurements": 0,
        },
    }
    require(not COMPARISON_RECEIPT.exists(),
            "Link-51/Link-50 comparison already exists")
    write_json(COMPARISON_RECEIPT, value)
    os.chmod(COMPARISON_RECEIPT, 0o444)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "verify", "deploy",
                                         "capture", "evaluate", "compare"))
    args = parser.parse_args()
    try:
        value = globals()[args.mode]()
    except (RunError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        print(f"c2-link51-badopcode-hold: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
