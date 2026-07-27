#!/usr/bin/env python3
"""Class-B cycle 3: hold Link 50 at the defun emitter/append failure seam."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import c2_lite_v6_link50_badopcode_hold as c1
import c2_lite_v6_link50_badopcode_inner_hold as c2


ROOT = c1.ROOT
EVIDENCE = c1.EVIDENCE
BASE_PRODUCT = c1.BASE_PRODUCT
BASE_ELF = c1.BASE_ELF
BASE_DEPLOYMENT = c1.BASE_DEPLOYMENT
LOAD_ADDRESS = c1.LOAD_ADDRESS

CYCLE2_RECEIPT = c2.HARDWARE_RECEIPT
CYCLE2_RECEIPT_SHA = (
    "ff1c7b7739315ec4078ff8548bf25828b85897e5bb8af5766a176c475056b30c")

FEASIBILITY = EVIDENCE / (
    "c2.2-link50-defun-service-hold-cycle3-feasibility.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-defun-service-hold-cycle3-NONPROMOTABLE")
PRODUCT = OUT / "lisp65-link50-defun-service-hold-cycle3-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-service-hold-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link50-defun-service-hold-cycle3-patch-receipt.json")
HW_OUT = ROOT / "build/c2.2/hardware-link50-defun-service-hold-cycle3"
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link50-defun-service-hold-cycle3-hardware-receipt.json")

# The common emitter/append failure seam starts by ending the authenticated
# overlay transaction.  Replacing only that JSR with SEI; BRA * freezes all
# producer state before cleanup.  Transaction-begin and final-commit failures
# bypass this address, so an ordinary rendered error is itself the complement.
SITE_ADDRESS = 0x2742
BEFORE = bytes.fromhex("2041ff")
AFTER = bytes.fromhex("7880fe")
FILE_OFFSET = 2 + SITE_ADDRESS - LOAD_ADDRESS

C2E_ADDRESS = 0xFD22
C2E_BYTES = 10
C2_PHASE_OWNER = 0x0089
C2_PHASE_SCRATCH = 0xC0C6
C2_PHASE_SCRATCH_BYTES = 304


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def authority() -> dict[str, Any]:
    base = c2.verify_authority()
    require(c1.sha(CYCLE2_RECEIPT) == CYCLE2_RECEIPT_SHA,
            "cycle-2 no-hold authority drift")
    receipt = c1.load_json(CYCLE2_RECEIPT, "cycle-2 no-hold receipt")
    require(receipt.get("status") ==
            "answered-no-inner-hold-definition-failed-before-publication",
            "cycle-2 no-hold receipt is not authoritative")
    return {**base, "cycle2_no_inner_hold": c1.bind(CYCLE2_RECEIPT)}


def patch(source: bytes) -> bytes:
    require(c1.u16(source, 0) == LOAD_ADDRESS, "Link-50 load address drift")
    require(source[FILE_OFFSET:FILE_OFFSET + 3] == BEFORE,
            "Link-50 service failure seam drift")
    result = bytearray(source)
    result[FILE_OFFSET:FILE_OFFSET + 3] = AFTER
    return bytes(result)


def patch_gate_shallow(source: bytes, candidate: bytes) -> None:
    require(len(candidate) == len(source), "service hold changed file size")
    changed = [index for index, pair in enumerate(zip(source, candidate))
               if pair[0] != pair[1]]
    require(changed == list(range(FILE_OFFSET, FILE_OFFSET + 3)),
            "service hold diff domain drift")
    require(candidate[FILE_OFFSET:FILE_OFFSET + 3] == AFTER,
            "service hold instruction drift")


def patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    patch_gate_shallow(source, candidate)
    mutations: dict[str, bytes] = {}
    for index, name in enumerate(("sei", "bra", "backedge")):
        value = bytearray(candidate)
        value[FILE_OFFSET + index] ^= 1
        mutations[f"wrong-{name}"] = bytes(value)
    missing = bytearray(candidate)
    missing[FILE_OFFSET:FILE_OFFSET + 3] = BEFORE
    mutations["missing-hold"] = bytes(missing)
    extra = bytearray(candidate)
    extra[FILE_OFFSET + 3] ^= 1
    mutations["extra-neighbour-byte"] = bytes(extra)
    rejected: dict[str, str] = {}
    for name, value in mutations.items():
        try:
            patch_gate_shallow(source, value)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"service hold mutation accepted: {name}")
    return {
        "status": "passed-one-exact-sei-bra-service-hold",
        "instruction_address": f"0x{SITE_ADDRESS:04x}",
        "instruction_file_offset": f"0x{FILE_OFFSET:04x}",
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "changed_bytes": 3,
        "file_size_delta_bytes": 0,
        "mutations_rejected": rejected,
    }


def dataflow_gate() -> dict[str, Any]:
    nm = subprocess.check_output([
        str(ROOT / "tools/llvm-mos/bin/llvm-nm"), "-S", "--size-sort",
        str(BASE_ELF)], text=True)
    anchors = (
        "00002689 0000023a T c2_product_install",
        "0000fd22 0000000a b c2e",
        "0000c0c6 00000130 B lisp65_c2_phase_scratch",
    )
    require(all(anchor in nm for anchor in anchors),
            "service-hold ELF symbol geometry drift")
    dis = subprocess.check_output([
        str(ROOT / "tools/llvm-mos/bin/llvm-objdump"), "-d",
        "--start-address=0x26ee", "--stop-address=0x28c3",
        str(BASE_ELF)], text=True)
    groups = {
        "transaction_begin_bypasses_common": (
            "26f8: 20 9e fc", "26fb: aa", "26fc: f0 03",
            "26fe: 4c 45 27"),
        "reset_failure_enters_common": (
            "2701: 20 03 f9", "2704: aa", "2705: f0 03",
            "2707: 4c 42 27"),
        "add_failure_enters_common": (
            "2720: 20 32 f9", "2723: aa", "2724: d0 1c"),
        "finalize_failure_enters_common": (
            "2739: 20 2b fb", "273c: aa", "273d: d0 03",
            "2742: 20 41 ff"),
        "append_failure_enters_common": (
            "27aa: 20 bb e0", "27ad: aa", "27ae: d0 03",
            "27b0: 4c 42 27"),
        "persistent_commit_bypasses_common": (
            "27b3: 20 41 ff", "2884: aa", "2885: f0 03",
            "2887: 4c 45 27"),
    }
    for name, rows in groups.items():
        require(all(row in dis for row in rows),
                f"service failure dataflow drift: {name}")
    return {
        "status": "passed-exact-common-seam-and-bypass-partition",
        "c2_product_install": {"address": "0x2689", "bytes": 570},
        "common_hold": (
            "reset, add, finalize and append failures all reach 0x2742 "
            "before transaction cleanup"),
        "complement": (
            "transaction-begin and persistent transaction-end failures jump "
            "directly to 0x2745 and therefore render instead of holding"),
        "stable_witnesses": {
            "c2e": {
                "address": f"0x{C2E_ADDRESS:04x}", "bytes": C2E_BYTES,
                "fields": (
                    "code_cursor:u16, entry_count:u16, literal_count:u16, "
                    "string_bytes:u16, active:u8, failed:u8"),
            },
            "phase_owner": f"0x{C2_PHASE_OWNER:04x}",
            "phase_scratch": {
                "address": f"0x{C2_PHASE_SCRATCH:04x}",
                "bytes": C2_PHASE_SCRATCH_BYTES,
            },
            "stability": (
                "SEI executes before the self-loop; no cleanup, renderer or "
                "IRQ can modify these witnesses while JTAG reads them"),
        },
        "classification": {
            "hold_active_1": "emitter reset/add/finalize family; scratch retains work status",
            "hold_active_0_nonzero_counts": "finalize completed; c2_append_begin failed",
            "hold_zero_state": "emitter reset/acquire failed before initialization",
            "rendered_error_header_unchanged": "transaction begin failed",
            "rendered_error_header_advanced": "persistent transaction end failed after append",
        },
        "anchors": groups,
    }


def feasibility() -> dict[str, Any]:
    require(not FEASIBILITY.exists(), "cycle-3 feasibility already exists")
    source = c1.regular(BASE_PRODUCT)
    candidate = patch(source)
    value = {
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-feasibility-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-zero-growth-service-boundary-hold-feasibility-hardware-not-run",
        "promotable": False,
        "delegation": {
            "class": "B", "cycle": 3, "cycle_cap": 3,
            "question": "first failing persistent-definition service substep",
        },
        "authority": authority(),
        "elf_dataflow": dataflow_gate(),
        "prospective_patch": patch_gate(source, candidate),
        "capacity_effect": {name: 0 for name in (
            "bank0_text_bytes", "ordinary_bank0_bss_bytes",
            "fixed_hot_block_bytes", "resident_island_bytes", "e000_bytes",
            "session_family_bytes", "runtime_slice_bytes", "file_bytes")},
        "budgets": {
            "class_b_first-execution-diagnostic":
                "2/3 consumed; prospective hardware run consumes final cycle 3",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "Feasibility only: no diagnostic identity, hardware run, product "
            "link, product byte, capacity, latency or acceptance claim."),
        "next_gate": "one SHA-bound nonpromotable final-cycle identity",
    }
    c1.write_json(FEASIBILITY, value)
    os.chmod(FEASIBILITY, 0o444)
    return value


def verify_feasibility() -> dict[str, Any]:
    value = c1.load_json(FEASIBILITY, "cycle-3 feasibility")
    require(value.get("status") ==
            "passed-zero-growth-service-boundary-hold-feasibility-hardware-not-run",
            "cycle-3 feasibility is not green")
    authority()
    source = c1.regular(BASE_PRODUCT)
    patch_gate(source, patch(source))
    dataflow_gate()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not PATCH_RECEIPT.exists(),
            "cycle-3 diagnostic identity already exists")
    verify_feasibility()
    source = c1.regular(BASE_PRODUCT)
    candidate = patch(source)
    gate = patch_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    manifest = {
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-patch-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-nonpromotable-fixed-length-service-hold-cycle3",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 3, "cycle_cap": 3},
        "authority": authority(),
        "feasibility": c1.bind(FEASIBILITY),
        "diagnostic_identity": c1.bind(PRODUCT),
        "patch_gate": gate,
        "capture_contract": {
            "three_time_separated_full_bank0_captures": True,
            "bank2_and_c2d_captures": True,
            "c2e": "0xfd22..0xfd2b",
            "phase_owner": "0x0089",
            "phase_scratch": "0xc0c6..0xc1f5",
        },
        "capacity_effect": {name: 0 for name in (
            "bank0_text_bytes", "ordinary_bank0_bss_bytes",
            "fixed_hot_block_bytes", "resident_island_bytes", "e000_bytes",
            "session_family_bytes", "runtime_slice_bytes", "file_bytes")},
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "changed_bytes": 3, "hardware_runs": 0,
            "promotable_candidates": 0,
        },
        "claim_limit": (
            "Permanently nonpromotable fixed-size derivative of Link 50; no "
            "product, latency, promotion or acceptance claim."),
        "rollback_line": {**c1.bind(BASE_PRODUCT), "status": "untouched"},
        "next_gate": "one announced final Class-B cycle-3 hardware run",
    }
    c1.write_json(MANIFEST, manifest)
    receipt = {**manifest, "manifest": c1.bind(MANIFEST)}
    c1.write_json(PATCH_RECEIPT, receipt)
    for path in (PRODUCT, MANIFEST, PATCH_RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return receipt


def check() -> dict[str, Any]:
    verify_feasibility()
    receipt = c1.load_json(PATCH_RECEIPT, "cycle-3 patch receipt")
    require(receipt.get("status") ==
            "passed-nonpromotable-fixed-length-service-hold-cycle3"
            and receipt.get("promotable") is False,
            "cycle-3 patch receipt is not green/nonpromotable")
    patch_gate(c1.regular(BASE_PRODUCT), c1.regular(PRODUCT))
    require(c1.bind(PRODUCT) == receipt["diagnostic_identity"],
            "cycle-3 diagnostic identity drift")
    return receipt


def prepare_hardware() -> dict[str, Any]:
    check()
    require(not DEPLOYMENT.exists(), "cycle-3 deployment already exists")
    source = c1.load_json(BASE_DEPLOYMENT, "Link-50 deployment")
    value = {
        **source,
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-deployment-v1",
        "status": "ready-nonpromotable-class-b-final-cycle3",
        "product": {**c1.bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "base_link50_product": c1.bind(BASE_PRODUCT),
            "authorization_receipt": c1.bind(PATCH_RECEIPT),
        },
        "new_product_links": 0,
        "promotable": False,
        "manual_sequence": [
            "wait for banner and REPL",
            "evaluate (defun %c2h () 't) exactly once",
            "if the machine holds, enter nothing further and take JTAG captures",
            "if an error renders, enter nothing further; the bypass complement is the answer",
        ],
        "claim_limit": (
            "Final nonpromotable Class-B diagnostic cycle; never a product "
            "presmoke, latency attempt, promotion or acceptance run."),
    }
    HW_OUT.mkdir(parents=True)
    c1.write_json(DEPLOYMENT, value)
    return value


def verify_hardware() -> dict[str, Any]:
    check()
    value = c1.load_json(DEPLOYMENT, "cycle-3 deployment")
    require(value.get("status") == "ready-nonpromotable-class-b-final-cycle3"
            and value.get("promotable") is False
            and value.get("new_product_links") == 0,
            "cycle-3 deployment status drift")
    require(c1.bind(PRODUCT) == {key: value["product"][key]
                                 for key in ("path", "bytes", "sha256")},
            "cycle-3 deployment product drift")
    for row in value["preloads"]:
        path = ROOT / row["path"]
        require(c1.bind(path)["bytes"] == row["bytes"]
                and c1.sha(path) == row["sha256"],
                f"cycle-3 preload drift: {path}")
    return value


def deploy_hardware() -> dict[str, Any]:
    value = verify_hardware()
    c1.require_hardware_tools()
    require(not (HW_OUT / "launch.json").exists(),
            "cycle-3 hardware run already launched")
    c1.run_command(c1.m65("-F", "-H", "-1", str(PRODUCT)))
    readbacks: list[dict[str, Any]] = []
    for row in value["preloads"]:
        path = ROOT / row["path"]
        address = int(row["address"], 16)
        readback = HW_OUT / ("readback-" + path.name)
        c1.run_command(c1.m65("-H", "-@", f"{path}@0x{address:08x}"))
        c1.run_command(c1.m65(
            "--memsave", f"0x{address:08x}:0x{address + row['bytes']:08x}={readback}"))
        require(c1.regular(readback) == c1.regular(path),
                f"cycle-3 preload readback mismatch: {path}")
        readbacks.append(c1.bind(readback, address))
    c1.run_command(c1.m65("-r", "-1", str(PRODUCT)))
    launch = {
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-launch-v1",
        "status": "launched-nonpromotable-class-b-final-cycle3",
        "monotonic_ns": time.monotonic_ns(),
        "deployment": c1.bind(DEPLOYMENT),
        "diagnostic_identity": c1.bind(PRODUCT, LOAD_ADDRESS),
        "preload_readbacks": readbacks,
        "operator_next": value["manual_sequence"],
    }
    c1.write_json(HW_OUT / "launch.json", launch)
    return launch


def capture_hardware() -> dict[str, Any]:
    verify_hardware()
    c1.require_hardware_tools()
    launch = c1.load_json(HW_OUT / "launch.json", "cycle-3 launch")
    require(launch.get("status") ==
            "launched-nonpromotable-class-b-final-cycle3",
            "cycle-3 diagnostic was not launched")
    require(not (HW_OUT / "capture-timing.json").exists(),
            "cycle-3 captures already exist")
    start = time.monotonic_ns()
    observations: list[dict[str, Any]] = []
    for index in range(1, 4):
        path = HW_OUT / f"held-bank0-{index}.bin"
        c1.run_command(c1.m65("--memsave", f"0x00000000:0x00010000={path}"))
        observations.append({
            "capture": index,
            "elapsed_ms": (time.monotonic_ns() - start) // 1_000_000,
            **c1.bind(path, 0),
        })
        if index != 3:
            time.sleep(0.5)
    for bank in (2, 5):
        path = HW_OUT / f"held-bank{bank}.bin"
        address = bank << 16
        c1.run_command(c1.m65(
            "--memsave", f"0x{address:08x}:0x{address + 65536:08x}={path}"))
    value = {
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-captures-v1",
        "status": "captured-read-only-after-service-hold-attempt",
        "reference": "first-JTAG-read-command-start",
        "bank0_captures": observations,
        "bank2": c1.bind(HW_OUT / "held-bank2.bin", 0x00020000),
        "bank5": c1.bind(HW_OUT / "held-bank5.bin", 0x00050000),
    }
    c1.write_json(HW_OUT / "capture-timing.json", value)
    return value


def evaluate_success() -> dict[str, Any]:
    verify_hardware()
    require(not HARDWARE_RECEIPT.exists(), "cycle-3 hardware receipt already exists")
    timing = c1.load_json(HW_OUT / "capture-timing.json", "cycle-3 captures")
    paths0 = [HW_OUT / f"held-bank0-{index}.bin" for index in range(1, 4)]
    banks0 = [c1.regular(path) for path in paths0]
    bank2_path = HW_OUT / "held-bank2.bin"
    bank5_path = HW_OUT / "held-bank5.bin"
    screenshot = HW_OUT / "after-defun.png"
    ansi = HW_OUT / "after-defun.ansi.txt"
    bank2 = c1.regular(bank2_path)
    bank5 = c1.regular(bank5_path)
    require(all(len(value) == 65536 for value in [*banks0, bank2, bank5]),
            "cycle-3 capture geometry drift")
    require(c1.regular(screenshot)[:8] == b"\x89PNG\r\n\x1a\n"
            and len(c1.regular(ansi)) > 0,
            "cycle-3 visible success evidence drift")
    require(bank5[:5] == b"C2D\0\x06", "cycle-3 C2D-v6 magic drift")

    product_states = []
    owners = []
    for bank0 in banks0:
        state = {
            "vm_status": bank0[c1.VM_STATUS],
            "c2_ready": bank0[c1.C2_READY],
            "c2_journal_count": c1.u16(bank0, c1.C2_JOURNAL_COUNT),
            "phase_owner": bank0[C2_PHASE_OWNER],
            "c2e_hex": bank0[C2E_ADDRESS:C2E_ADDRESS + C2E_BYTES].hex(),
        }
        require(state == {
            "vm_status": 0,
            "c2_ready": 1,
            "c2_journal_count": 0,
            "phase_owner": 0,
            "c2e_hex": "49000100000006000000",
        }, f"cycle-3 post-defun state drift: {state}")
        owner = c1.active_owner_analysis(bank0, bank2, bank5)
        require(owner["bank_tag"] == 1 and owner["ordinal"] == 171
                and owner["object_name"] == "lcc-run"
                and owner["active_owner_cache_exact"] is True,
                "cycle-3 post-defun owner is not exact lcc-run ordinal 171")
        product_states.append(state)
        owners.append(owner)

    header = {
        "transient_watermark": c1.u16(bank5, 8),
        "generation": c1.u16(bank5, 10),
        "image_count": c1.u16(bank5, 12),
        "entry_count": c1.u16(bank5, 16),
        "resolution_count": c1.u16(bank5, 20),
        "root_count": c1.u16(bank5, 24),
    }
    require(header == {
        "transient_watermark": 4096,
        "generation": 1,
        "image_count": 7,
        "entry_count": 589,
        "resolution_count": 2264,
        "root_count": 283,
    }, f"cycle-3 published header drift: {header}")
    dynamic = c1.entry(bank5, 588)
    require(dynamic == {
        "ordinal": 588,
        "raw_hex": "060063860900d8080100",
        "image_slot": 6,
        "literal_count": 0,
        "code_offset": 34403,
        "code_length": 9,
        "resolution_base": 2264,
        "generation": 1,
    }, f"cycle-3 dynamic entry drift: {dynamic}")
    expected_code = bytes.fromhex("b50000020200002c05")
    require(bank2[34403:34412] == expected_code,
            "cycle-3 dynamic code bytes drift")

    changed = c2.varying_offsets(banks0)
    allowed = {0x0016, 0x0017, 0xFF83, 0xFF84} | set(range(0x0100, 0x0200))
    require(set(changed) <= allowed,
            "cycle-3 non-hold variance escaped IRQ/hardware-stack state")
    protected = {
        c1.VM_STATUS, c1.C2_READY,
        c1.C2_JOURNAL_COUNT, c1.C2_JOURNAL_COUNT + 1,
        C2_PHASE_OWNER,
        *range(C2E_ADDRESS, C2E_ADDRESS + C2E_BYTES),
    }
    require(not protected.intersection(changed),
            "cycle-3 non-hold variance touched a product witness")

    captures = [{
        "capture": index,
        "elapsed_ms": timing["bank0_captures"][index - 1]["elapsed_ms"],
        **c1.bind(path, 0),
        "product_state": product_states[index - 1],
        "active_owner": owners[index - 1],
    } for index, path in enumerate(paths0, start=1)]
    value = {
        "format": "lisp65-c2-link50-defun-service-hold-cycle3-hardware-v1",
        "recorded_on": "2026-07-22",
        "status": "answered-no-service-failure-definition-published",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 3, "cycle_cap": 3},
        "authorization": c1.bind(PATCH_RECEIPT),
        "deployment": c1.bind(DEPLOYMENT),
        "diagnostic_identity": c1.bind(PRODUCT),
        "operator_observation": {
            "input": "(defun %c2h () 't)",
            "rendered_result": "%c2h",
            "additional_forms_submitted": 0,
            "screenshot": c1.bind(screenshot),
            "ansi": c1.bind(ansi),
        },
        "answer": {
            "common_emitter_append_failure_seam_reached": False,
            "definition_published": True,
            "proof": (
                "The patched common seam would execute SEI and loop forever. "
                "Instead the REPL rendered %c2h; C2D advanced exactly to one "
                "new image and entry, Entry 588 and its nine Bank-2 bytes are "
                "exact, the transaction journal is empty and READY remains one."),
            "service_substeps": (
                "Transaction begin, emitter reset/add/finalize, append begin "
                "and persistent transaction end all succeeded in this run."),
            "cycle2_disposition": (
                "The cycle-2 defun-time BADOPCODE did not reproduce. It remains "
                "a bound hardware observation, but cannot honestly be assigned "
                "to a deterministic service substep from these runs."),
            "original_execution_question": (
                "The newly published %c2h was deliberately not called in this "
                "final diagnostic cycle, so the original first-call BADOPCODE "
                "remains a separate unresolved product question."),
        },
        "published_object": {
            "c2d_v6_header": header,
            "entry_588": dynamic,
            "bank2_code_hex": expected_code.hex(),
        },
        "captures": {
            "bank0_variance_offsets": [f"0x{offset:04x}" for offset in changed],
            "variance_class": (
                "normal IRQ/hardware-stack motion after a successful REPL return; "
                "all product witnesses are stable"),
            "bank0": captures,
            "bank2": c1.bind(bank2_path, 0x00020000),
            "bank5": c1.bind(bank5_path, 0x00050000),
            "timing": c1.bind(HW_OUT / "capture-timing.json"),
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "diagnostic_instruction_patches": 1,
            "changed_bytes": 3,
            "hardware_runs": 1,
            "read_only_post_defun_captures": 5,
            "remaining_autonomous_cycles": 0,
            "completed_latency_attempts": 0,
        },
        "budgets": {
            "class_b_first-execution-diagnostic": "3/3 consumed; exhausted",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "This nonpromotable final-cycle result proves one successful defun "
            "and excludes the instrumented service failure seam in that run. "
            "It does not prove first-call execution, latency, promotion or "
            "acceptance, and it authorizes no fourth diagnostic patch cycle."),
        "rollback_line": {**c1.bind(BASE_PRODUCT), "status": "untouched"},
        "disposition": (
            "Class-B budget exhausted. Any further diagnosis requires a new "
            "Class-C product/contract decision; the diagnostic identity remains "
            "isolated and permanently nonpromotable."),
    }
    c1.write_json(HARDWARE_RECEIPT, value)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "selftest", "feasibility", "build", "check", "prepare-hardware",
        "verify-hardware", "deploy-hardware", "capture-hardware",
        "evaluate-success"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            authority()
            source = c1.regular(BASE_PRODUCT)
            patch_gate(source, patch(source))
            dataflow_gate()
            print("c2-link50-defun-service-hold: SELFTEST PASS mutations=5")
            return 0
        if args.action == "feasibility":
            value = feasibility()
        elif args.action == "build":
            value = build()
        elif args.action == "check":
            value = check()
        elif args.action == "prepare-hardware":
            value = prepare_hardware()
        elif args.action == "verify-hardware":
            value = verify_hardware()
        elif args.action == "deploy-hardware":
            value = deploy_hardware()
        elif args.action == "evaluate-success":
            value = evaluate_success()
        else:
            value = capture_hardware()
        print("c2-link50-defun-service-hold: " + str(value["status"]))
        return 0
    except Exception as error:
        print("c2-link50-defun-service-hold: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
