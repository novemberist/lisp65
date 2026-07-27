#!/usr/bin/env python3
"""Class-B cycle 2: hold Link 50 at the first inner VM failure edge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any

import c2_lite_v6_link50_badopcode_hold as c1


ROOT = c1.ROOT
EVIDENCE = c1.EVIDENCE
BASE_PRODUCT = c1.BASE_PRODUCT
BASE_ELF = c1.BASE_ELF
BASE_DEPLOYMENT = c1.BASE_DEPLOYMENT
LOAD_ADDRESS = c1.LOAD_ADDRESS

CORRECTION = c1.HARDWARE_INTERPRETATION_CORRECTION
CORRECTION_SHA = (
    "c0aaedca3cddae2658456c2448fc50d5b3d6eca9001f7e2424290de8ab49d391")

FEASIBILITY = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-inner-hold-cycle2-feasibility.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link50-first-call-badopcode-inner-hold-cycle2-NONPROMOTABLE")
PRODUCT = OUT / "lisp65-link50-badopcode-inner-hold-cycle2-NONPROMOTABLE.prg"
MANIFEST = OUT / "fixed-length-inner-hold-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-inner-hold-cycle2-patch-receipt.json")
HW_OUT = ROOT / "build/c2.2/hardware-link50-badopcode-inner-hold-cycle2"
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link50-first-call-badopcode-inner-hold-cycle2-hardware-receipt.json")

# Each original instruction is a three-byte absolute JMP into vm_run_inner's
# common unwind.  SEI; BRA -2 is also exactly three bytes.  The one-time SEI
# makes compiler scratch and the C software frame stable under the owned IRQ;
# the BRA then holds without touching product state or allocating a latch.
HOLD = bytes.fromhex("7880fe")
SITES: tuple[dict[str, Any], ...] = (
    {
        "name": "invalid-opcode-dispatch",
        "address": 0x6DCA,
        "before": bytes.fromhex("4cb76a"),
        "precondition": "opcode >= 0x42; vm_status is still VM_OK",
        "witness": "__rc20/__rc21 is the physical cursor immediately after the fetched opcode",
    },
    {
        "name": "post-handler-status",
        "address": 0x7066,
        "before": bytes.fromhex("4cbb6a"),
        "precondition": "LDX vm_status observed a nonzero handler status",
        "witness": "vm_status is nonzero; the live vm_run_inner frame has not unwound",
    },
    {
        "name": "callprim-propagation",
        "address": 0x781A,
        "before": bytes.fromhex("4c5d88"),
        "precondition": "LDX vm_status observed a nonzero vm_callprim result",
        "witness": "software-frame offsets +7/+8 retain CALLPRIM pcur; lcc-run final pcur is 62",
    },
)

LCC_RUN_PAYLOAD = bytes.fromhex(
    "0b3c00013a010b361d070b3406011e1c012b1d0d0b353439012b3d26023d230205"
    "0b361d070b3406021e1c012b1d0939010b35343d26020539012c3d260205")
LCC_RUN_FINAL_CALL = bytes.fromhex("3d260205")
LCC_RUN_FINAL_CALL_PC = 59
LCC_RUN_FINAL_PCUR = 62
VM_RUN_INNER_ADDRESS = 0x69AA
VM_RUN_INNER_SIZE = 0x1EFE
SOFTWARE_SP = 0x0002
PHYSICAL_IP = 0x0004
NEXT_IP = 0x0016
FRAME_PCUR = 7
FRAME_BYTES = 45


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def file_offset(address: int) -> int:
    return 2 + address - LOAD_ADDRESS


def verify_authority() -> dict[str, Any]:
    authority = c1.verify_authority()
    require(c1.sha(CORRECTION) == CORRECTION_SHA,
            "cycle-1 owner-aware correction drift")
    correction = c1.load_json(CORRECTION, "cycle-1 interpretation correction")
    require(correction.get("status") ==
            "corrected-active-owner-refill-exonerated",
            "cycle-1 correction is not authoritative")
    return {**authority, "cycle1_interpretation_correction": c1.bind(CORRECTION)}


def base_span(source: bytes, site: dict[str, Any]) -> bytes:
    at = file_offset(site["address"])
    require(at >= 2 and at + 3 <= len(source),
            f"patch site outside Link 50: {site['name']}")
    return source[at:at + 3]


def patched(source: bytes) -> bytes:
    require(c1.u16(source, 0) == LOAD_ADDRESS, "Link-50 load address drift")
    result = bytearray(source)
    for site in SITES:
        require(base_span(source, site) == site["before"],
                f"Link-50 inner edge drift: {site['name']}")
        at = file_offset(site["address"])
        result[at:at + 3] = HOLD
    return bytes(result)


def changed_offsets() -> list[int]:
    return [file_offset(site["address"]) + delta
            for site in SITES for delta in range(3)]


def exact_patch_gate_shallow(source: bytes, candidate: bytes) -> None:
    require(len(candidate) == len(source), "inner hold changed file size")
    actual = [index for index, (before, after) in
              enumerate(zip(source, candidate)) if before != after]
    require(actual == changed_offsets(), "inner hold diff domain drift")
    for site in SITES:
        at = file_offset(site["address"])
        require(candidate[at:at + 3] == HOLD,
                f"inner hold bytes drift: {site['name']}")


def exact_patch_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    exact_patch_gate_shallow(source, candidate)
    mutations: dict[str, bytes] = {}
    for index, site in enumerate(SITES):
        at = file_offset(site["address"])
        missing = bytearray(candidate)
        missing[at:at + 3] = site["before"]
        mutations[f"missing-{site['name']}"] = bytes(missing)
        no_sei = bytearray(candidate)
        no_sei[at] = 0xEA
        mutations[f"irq-open-{site['name']}"] = bytes(no_sei)
        wrong_loop = bytearray(candidate)
        wrong_loop[at + 2] = 0xFC
        mutations[f"wrong-loop-{site['name']}"] = bytes(wrong_loop)
    extra = bytearray(candidate)
    extra[file_offset(SITES[-1]["address"]) + 3] ^= 1
    mutations["extra-neighbour-byte"] = bytes(extra)
    rejected: dict[str, str] = {}
    for name, mutation in mutations.items():
        try:
            exact_patch_gate_shallow(source, mutation)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"inner hold mutation accepted: {name}")
    return {
        "status": "passed-three-exact-sei-bra-inner-holds",
        "hold_hex": HOLD.hex(),
        "hold_semantics": "SEI once, then BRA to itself; live frame and ZP stop changing",
        "changed_bytes": len(changed_offsets()),
        "file_size_delta_bytes": 0,
        "sites": [{
            "name": site["name"],
            "instruction_address": f"0x{site['address']:04x}",
            "instruction_file_offset": f"0x{file_offset(site['address']):04x}",
            "before_hex": site["before"].hex(),
            "after_hex": HOLD.hex(),
            "precondition": site["precondition"],
            "witness": site["witness"],
        } for site in SITES],
        "changed_file_offsets": [f"0x{value:04x}" for value in changed_offsets()],
        "mutations_rejected": rejected,
    }


def disassembly_truth() -> dict[str, Any]:
    nm = subprocess.check_output([
        str(ROOT / "tools/llvm-mos/bin/llvm-nm"), "-S", "--size-sort",
        str(BASE_ELF)], text=True)
    require("000069aa 00001efe t vm_run_inner" in nm,
            "vm_run_inner ELF interval drift")
    objdump = subprocess.check_output([
        str(ROOT / "tools/llvm-mos/bin/llvm-objdump"), "-d",
        "--start-address=0x69aa", "--stop-address=0x88a8",
        str(BASE_ELF)], text=True)
    anchors = {
        "invalid_dispatch": [
            "6dba: a6 04", "6dc2: e3 16", "6dc4: b2 04",
            "6dc6: c9 42", "6dca: 4c b7 6a"],
        "post_handler_status": [
            "705f: a6 5b", "7061: d0 03", "7066: 4c bb 6a"],
        "callprim_status": [
            "780d: 20 8f 8c", "7816: a6 5b", "7818: f0 03",
            "781a: 4c 5d 88"],
        "pcur_frame_reads": [
            "784d: a0 08", "784f: b1 02", "7859: a0 07", "785b: b1 02"],
    }
    for group, rows in anchors.items():
        require(all(row in objdump for row in rows),
                f"inner dataflow disassembly drift: {group}")
    require(LCC_RUN_PAYLOAD[LCC_RUN_FINAL_CALL_PC:] == LCC_RUN_FINAL_CALL,
            "lcc-run final CALLPRIM/RET bytes drift")
    return {
        "vm_run_inner": {
            "address": f"0x{VM_RUN_INNER_ADDRESS:04x}",
            "bytes": VM_RUN_INNER_SIZE,
            "section": ".text",
        },
        "invalid_dispatch_dataflow": (
            "$04/$05 is copied to $16/$17, INW advances $16/$17 once, "
            "then the opcode at ($04),Z is compared with 0x42; no write to "
            "$04/$05 or $16/$17 occurs before the patched edge."),
        "post_handler_dataflow": (
            "LDX vm_status immediately dominates the nonzero branch and the "
            "patched edge; the vm_run_inner frame has not entered unwind."),
        "callprim_dataflow": (
            "vm_callprim returns, LDX vm_status immediately dominates the "
            "patched edge, and the success-side ELF reads pcur back from "
            "software-frame offsets +8/+7. lcc-run's final CALLPRIM 38,2 "
            "starts at PC 59 and has pcur 62."),
        "interrupt_stability": (
            "Every prospective hold executes SEI before entering its branch "
            "loop. Thus the prior IRQ/compiler-scratch instability of "
            "$16/$17 cannot recur while the read-only captures are taken."),
        "lcc_run_final_tail_hex": LCC_RUN_FINAL_CALL.hex(),
        "lcc_run_final_call_pc": LCC_RUN_FINAL_CALL_PC,
        "lcc_run_final_pcur": LCC_RUN_FINAL_PCUR,
        "anchors": anchors,
    }


def feasibility() -> dict[str, Any]:
    require(not FEASIBILITY.exists(), "cycle-2 feasibility already exists")
    authority = verify_authority()
    source = c1.regular(BASE_PRODUCT)
    candidate = patched(source)
    gate = exact_patch_gate(source, candidate)
    value = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-feasibility-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-zero-growth-three-edge-inner-hold-feasibility-hardware-not-run",
        "promotable": False,
        "scope": {
            "class": "A read-only ELF/paper feasibility",
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "patched_artifacts_created": 0,
        },
        "authority": authority,
        "elf_dataflow": disassembly_truth(),
        "prospective_patch": gate,
        "classification_contract": {
            "vm_status_0": (
                "invalid-opcode-dispatch; $16/$17 is after-op physical cursor, "
                "$04/$05 is opcode address, and owner/window yields logical PC"),
            "vm_status_nonzero_and_frame_pcur_62": (
                "lcc-run final CALLPRIM propagation after lcc-install"),
            "vm_status_nonzero_and_other_frame_pcur": (
                "post-handler error inside the still-live vm_run_inner frame"),
            "no_hold_error_renderer": (
                "all three inner edges exonerated; cycle 3 may target the "
                "append/rollback service boundary only after review of this evidence"),
        },
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
        "budgets": {
            "class_b_first-execution-diagnostic": (
                "1/3 consumed; prospective hardware run consumes cycle 2"),
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "This is feasibility only. It proves fixed-size inner holds and "
            "their live witnesses; it creates no diagnostic identity, runs "
            "no hardware, changes no product and makes no latency claim."),
        "next_gate": "create one SHA-bound nonpromotable Class-B cycle-2 identity",
    }
    c1.write_json(FEASIBILITY, value)
    os.chmod(FEASIBILITY, 0o444)
    return value


def verify_feasibility() -> dict[str, Any]:
    value = c1.load_json(FEASIBILITY, "cycle-2 feasibility")
    require(value.get("status") ==
            "passed-zero-growth-three-edge-inner-hold-feasibility-hardware-not-run",
            "cycle-2 feasibility is not green")
    verify_authority()
    exact_patch_gate(c1.regular(BASE_PRODUCT), patched(c1.regular(BASE_PRODUCT)))
    disassembly_truth()
    return value


def build() -> dict[str, Any]:
    require(not OUT.exists() and not PATCH_RECEIPT.exists(),
            "cycle-2 diagnostic identity already exists")
    verify_feasibility()
    source = c1.regular(BASE_PRODUCT)
    candidate = patched(source)
    gate = exact_patch_gate(source, candidate)
    OUT.mkdir(parents=True)
    PRODUCT.write_bytes(candidate)
    require(c1.regular(PRODUCT) == candidate, "cycle-2 product writeback drift")
    manifest = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-patch-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-nonpromotable-fixed-length-inner-hold-cycle2",
        "promotable": False,
        "delegation": {
            "class": "B", "cycle": 2, "cycle_cap": 3,
            "question": "first execution of a proven-valid dynamic object",
        },
        "authority": verify_authority(),
        "feasibility": c1.bind(FEASIBILITY),
        "diagnostic_identity": c1.bind(PRODUCT),
        "patch_gate": gate,
        "capture_contract": {
            "three_time_separated_full_bank0_captures": True,
            "bank2_and_c2d_captures": True,
            "interrupts_disabled_at_every_hold": True,
            "software_stack_pointer": "0x0002..0x0003",
            "physical_ip": "0x0004..0x0005",
            "after_opcode_ip": "0x0016..0x0017",
            "active_owner": "(vm_buf_bank@0xbf92, vm_buf_off@0xb976)",
        },
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
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 3,
            "changed_bytes": len(changed_offsets()),
            "hardware_runs": 0, "promotable_candidates": 0,
        },
        "claim_limit": (
            "Permanently nonpromotable fixed-size derivative of Link 50. "
            "It carries no product, capacity, latency, promotion or acceptance claim."),
        "rollback_line": {**c1.bind(BASE_PRODUCT), "status": "untouched"},
        "next_gate": "one announced Class-B cycle-2 hardware run",
    }
    c1.write_json(MANIFEST, manifest)
    value = {**manifest, "manifest": c1.bind(MANIFEST)}
    c1.write_json(PATCH_RECEIPT, value)
    for path in (PRODUCT, MANIFEST, PATCH_RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    return value


def check() -> dict[str, Any]:
    verify_feasibility()
    receipt = c1.load_json(PATCH_RECEIPT, "cycle-2 patch receipt")
    require(receipt.get("status") ==
            "passed-nonpromotable-fixed-length-inner-hold-cycle2"
            and receipt.get("promotable") is False,
            "cycle-2 patch receipt is not green/nonpromotable")
    source, candidate = c1.regular(BASE_PRODUCT), c1.regular(PRODUCT)
    exact_patch_gate(source, candidate)
    require(c1.bind(PRODUCT) == receipt["diagnostic_identity"],
            "cycle-2 diagnostic identity drift")
    require(all(delta == 0 for delta in receipt["capacity_effect"].values()),
            "cycle-2 diagnostic changed a bound capacity")
    return receipt


def prepare_hardware() -> dict[str, Any]:
    check()
    require(not DEPLOYMENT.exists(), "cycle-2 deployment already exists")
    source = c1.load_json(BASE_DEPLOYMENT, "Link-50 deployment")
    value = {
        **source,
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-deployment-v1",
        "status": "ready-nonpromotable-class-b-cycle2",
        "product": {**c1.bind(PRODUCT), "address": "0x00002001"},
        "source_candidate": {
            "base_link50_product": c1.bind(BASE_PRODUCT),
            "authorization_receipt": c1.bind(PATCH_RECEIPT),
            "patch_manifest": c1.bind(MANIFEST),
        },
        "new_product_links": 0,
        "promotable": False,
        "manual_sequence": [
            "wait for banner and REPL",
            "evaluate (defun %c2h () 't); expect %c2h",
            "evaluate (%c2h) exactly once",
            "if the machine holds, enter nothing further and take JTAG captures",
            "if an error is rendered instead, record it; the three patched edges are exonerated",
        ],
        "claim_limit": (
            "One nonpromotable Class-B diagnostic deployment; never a "
            "product presmoke, latency attempt, promotion or acceptance run."),
    }
    HW_OUT.mkdir(parents=True)
    c1.write_json(DEPLOYMENT, value)
    return value


def verify_hardware() -> dict[str, Any]:
    check()
    value = c1.load_json(DEPLOYMENT, "cycle-2 deployment")
    require(value.get("status") == "ready-nonpromotable-class-b-cycle2"
            and value.get("promotable") is False
            and value.get("new_product_links") == 0,
            "cycle-2 deployment status drift")
    require(c1.bind(PRODUCT) == {key: value["product"][key]
                                 for key in ("path", "bytes", "sha256")},
            "cycle-2 deployment product drift")
    for row in value["preloads"]:
        path = ROOT / row["path"]
        require(c1.bind(path)["bytes"] == row["bytes"]
                and c1.sha(path) == row["sha256"],
                f"cycle-2 preload drift: {path}")
    return value


def deploy_hardware() -> dict[str, Any]:
    value = verify_hardware()
    c1.require_hardware_tools()
    require(not (HW_OUT / "launch.json").exists(),
            "cycle-2 hardware run already launched")
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
                f"cycle-2 preload readback mismatch: {path}")
        readbacks.append(c1.bind(readback, address))
    c1.run_command(c1.m65("-r", "-1", str(PRODUCT)))
    launch = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-launch-v1",
        "status": "launched-nonpromotable-class-b-cycle2",
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
    launch = c1.load_json(HW_OUT / "launch.json", "cycle-2 launch")
    require(launch.get("status") == "launched-nonpromotable-class-b-cycle2",
            "cycle-2 diagnostic was not launched")
    require(not (HW_OUT / "capture-timing.json").exists(),
            "cycle-2 captures already exist")
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
        start_address = bank << 16
        c1.run_command(c1.m65(
            "--memsave", f"0x{start_address:08x}:0x{start_address + 65536:08x}={path}"))
    timing = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-captures-v1",
        "status": "captured-read-only-after-inner-hold-attempt",
        "reference": "first-JTAG-read-command-start",
        "bank0_captures": observations,
        "bank2": c1.bind(HW_OUT / "held-bank2.bin", 0x00020000),
        "bank5": c1.bind(HW_OUT / "held-bank5.bin", 0x00050000),
    }
    c1.write_json(HW_OUT / "capture-timing.json", timing)
    return timing


def classify(bank0: bytes, bank2: bytes, bank5: bytes) -> dict[str, Any]:
    status = bank0[c1.VM_STATUS]
    sp = c1.u16(bank0, SOFTWARE_SP)
    require(sp + FRAME_BYTES <= len(bank0), "software frame outside Bank 0")
    frame = bank0[sp:sp + FRAME_BYTES]
    pcur = c1.u16(frame, FRAME_PCUR)
    owner = c1.active_owner_analysis(bank0, bank2, bank5)
    if status == 0:
        physical = c1.u16(bank0, PHYSICAL_IP)
        after = c1.u16(bank0, NEXT_IP)
        require(after == (physical + 1) & 0xFFFF,
                "invalid-dispatch after-op cursor is not physical+1")
        code_pointer = c1.u16(bank0, c1.VMR_CODE)
        window_start = c1.u16(bank0, c1.VMR_WIN)
        window_length = c1.u16(bank0, c1.VMR_WINLEN)
        require(code_pointer <= physical < code_pointer + window_length,
                "invalid-dispatch opcode is outside active window")
        logical_pc = window_start + physical - code_pointer
        opcode = bank0[physical]
        require(opcode >= 0x42, "invalid-dispatch hold has a valid opcode")
        site = "invalid-opcode-dispatch"
        detail = {
            "physical_opcode_address": f"0x{physical:04x}",
            "physical_after_opcode": f"0x{after:04x}",
            "logical_opcode_pc": logical_pc,
            "opcode": f"0x{opcode:02x}",
        }
    elif status != 0 and pcur == LCC_RUN_FINAL_PCUR:
        site = "callprim-propagation"
        detail = {
            "lcc_run_final_call_pc": LCC_RUN_FINAL_CALL_PC,
            "frame_pcur": pcur,
            "callee": "lcc-install / primitive 38",
        }
    else:
        site = "post-handler-status"
        detail = {"frame_pcur": pcur, "vm_status": status}
    return {
        "site": site,
        "vm_status": status,
        "software_sp": f"0x{sp:04x}",
        "software_frame_hex": frame.hex(),
        "frame_pcur": pcur,
        "active_owner": owner,
        "detail": detail,
    }


def classifier_selftest() -> dict[str, str]:
    # The live classifier is additionally checked against captured bytes.  The
    # pure cases pin the two disjoint scalar decisions used after that gate.
    require(LCC_RUN_PAYLOAD[59:63] == LCC_RUN_FINAL_CALL,
            "CALLPRIM classifier tail drift")
    require(LCC_RUN_FINAL_PCUR == 62 and 0 < LCC_RUN_FINAL_PCUR < len(LCC_RUN_PAYLOAD),
            "CALLPRIM pcur classifier drift")
    require(len({site["address"] for site in SITES}) == len(SITES),
            "inner hold site identity collision")
    return {
        "invalid-status-zero": "passed",
        "final-callprim-pcur-62": "passed",
        "post-handler-complement": "passed",
    }


def evaluate_hardware() -> dict[str, Any]:
    verify_hardware()
    require(not HARDWARE_RECEIPT.exists(), "cycle-2 hardware receipt already exists")
    timing = c1.load_json(HW_OUT / "capture-timing.json", "cycle-2 capture timing")
    paths0 = [HW_OUT / f"held-bank0-{index}.bin" for index in range(1, 4)]
    banks0 = [c1.regular(path) for path in paths0]
    bank2 = c1.regular(HW_OUT / "held-bank2.bin")
    bank5 = c1.regular(HW_OUT / "held-bank5.bin")
    require(all(len(data) == 65536 for data in [*banks0, bank2, bank5]),
            "cycle-2 capture geometry drift")
    require(banks0[0] == banks0[1] == banks0[2],
            "cycle-2 Bank-0 state is not stable; an inner SEI hold is unproved")
    require(bank5[:5] == b"C2D\0\x06", "cycle-2 C2D-v6 magic drift")
    require(banks0[0][c1.C2_READY] == 1,
            "cycle-2 capture is not in the post-boot product")
    analysis = classify(banks0[0], bank2, bank5)
    captures = [{
        "capture": index,
        "elapsed_ms": timing["bank0_captures"][index - 1]["elapsed_ms"],
        **c1.bind(path, 0),
    } for index, path in enumerate(paths0, start=1)]
    answers = {
        "invalid-opcode-dispatch": (
            "The VM fetched an opcode outside the contracted 0x00..0x41 range. "
            "The frozen owner/window and logical PC identify its exact byte."),
        "post-handler-status": (
            "A valid opcode handler set a nonzero status before unwind. The "
            "live frame excludes raw dispatch and final lcc-install propagation."),
        "callprim-propagation": (
            "The transient execution returned through lcc-install's final "
            "CALLPRIM with nonzero status; raw opcode dispatch itself is exonerated."),
    }
    value = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-hardware-v1",
        "recorded_on": "2026-07-22",
        "status": "answered-first-inner-badopcode-edge",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3},
        "authorization": c1.bind(PATCH_RECEIPT),
        "deployment": c1.bind(DEPLOYMENT),
        "diagnostic_identity": c1.bind(PRODUCT),
        "patch_gate": c1.load_json(MANIFEST, "cycle-2 manifest")["patch_gate"],
        "classification": analysis,
        "answer": answers[analysis["site"]],
        "captures": {
            "bank0": captures,
            "bank2": c1.bind(HW_OUT / "held-bank2.bin", 0x00020000),
            "bank5": c1.bind(HW_OUT / "held-bank5.bin", 0x00050000),
            "timing": c1.bind(HW_OUT / "capture-timing.json"),
        },
        "classifier_mutations": classifier_selftest(),
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "diagnostic_instruction_patches": 3,
            "changed_bytes": len(changed_offsets()),
            "hardware_runs": 1,
            "read_only_post_stop_captures": 5,
            "remaining_autonomous_cycles": 1,
            "completed_latency_attempts": 0,
        },
        "budgets": {
            "class_b_first-execution-diagnostic": "2/3 consumed",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "One nonpromotable Class-B diagnostic hardware run. It is not a "
            "product link, presmoke, latency result, promotion or acceptance."),
        "rollback_line": {**c1.bind(BASE_PRODUCT), "status": "untouched"},
        "disposition": (
            "The diagnostic identity remains isolated and permanently excluded "
            "from product or promotable receipt archives."),
    }
    c1.write_json(HARDWARE_RECEIPT, value)
    for path in HW_OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(HW_OUT, 0o555)
    os.chmod(HARDWARE_RECEIPT, 0o444)
    return value


def varying_offsets(captures: list[bytes]) -> list[int]:
    require(len(captures) >= 2, "need at least two captures for variance gate")
    width = len(captures[0])
    require(all(len(data) == width for data in captures),
            "capture widths differ")
    return [offset for offset in range(width)
            if len({data[offset] for data in captures}) != 1]


def evaluate_no_hold() -> dict[str, Any]:
    """Bind the observed rendered error when none of the three holds fired."""
    verify_hardware()
    require(not HARDWARE_RECEIPT.exists(), "cycle-2 hardware receipt already exists")
    timing = c1.load_json(HW_OUT / "capture-timing.json", "cycle-2 capture timing")
    paths0 = [HW_OUT / f"held-bank0-{index}.bin" for index in range(1, 4)]
    banks0 = [c1.regular(path) for path in paths0]
    bank2_path = HW_OUT / "held-bank2.bin"
    bank5_path = HW_OUT / "held-bank5.bin"
    screenshot = HW_OUT / "after-defun.png"
    ansi = HW_OUT / "after-defun.ansi.txt"
    bank2 = c1.regular(bank2_path)
    bank5 = c1.regular(bank5_path)
    require(all(len(data) == 65536 for data in [*banks0, bank2, bank5]),
            "cycle-2 no-hold capture geometry drift")
    require(c1.regular(screenshot)[:8] == b"\x89PNG\r\n\x1a\n",
            "cycle-2 no-hold screenshot is not PNG")
    require(len(c1.regular(ansi)) > 0,
            "cycle-2 no-hold ANSI capture is empty")
    require(bank5[:5] == b"C2D\0\x06", "cycle-2 C2D-v6 magic drift")

    product_state = []
    owners = []
    for bank0 in banks0:
        state = {
            "vm_status": bank0[c1.VM_STATUS],
            "c2_ready": bank0[c1.C2_READY],
            "c2_journal_count": c1.u16(bank0, c1.C2_JOURNAL_COUNT),
        }
        require(state == {
            "vm_status": 0, "c2_ready": 1, "c2_journal_count": 0,
        }, f"cycle-2 post-render product state drift: {state}")
        owner = c1.active_owner_analysis(bank0, bank2, bank5)
        require(owner["bank_tag"] == 1 and owner["ordinal"] == 171
                and owner["object_name"] == "lcc-run"
                and owner["active_owner_cache_exact"] is True,
                "cycle-2 post-render owner is not exact lcc-run ordinal 171")
        product_state.append(state)
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
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
    }, f"cycle-2 defun rollback/header drift: {header}")

    changed = varying_offsets(banks0)
    expected_irq_volatile = {0x0016, 0x0017, 0xFF83, 0xFF84}
    # The hardware stack in page 1 changes while IRQs remain enabled after the
    # renderer returns to the REPL.  Record its complete observed variance,
    # but prove it is disjoint from every product-state witness above.
    allowed_irq_region = expected_irq_volatile | set(range(0x0100, 0x0200))
    require(set(changed) <= allowed_irq_region,
            "cycle-2 no-hold variance escaped known IRQ/compiler scratch")
    protected = {
        c1.VM_STATUS, c1.C2_READY,
        c1.C2_JOURNAL_COUNT, c1.C2_JOURNAL_COUNT + 1,
        c1.VM_BUF_BANK, c1.VM_BUF_OFF, c1.VM_BUF_OFF + 1,
    }
    require(not protected.intersection(changed),
            "cycle-2 no-hold variance touched a product-state witness")

    captures = [{
        "capture": index,
        "elapsed_ms": timing["bank0_captures"][index - 1]["elapsed_ms"],
        **c1.bind(path, 0),
        "product_state": product_state[index - 1],
        "active_owner": owners[index - 1],
    } for index, path in enumerate(paths0, start=1)]
    value = {
        "format": "lisp65-c2-link50-badopcode-inner-hold-cycle2-hardware-v2",
        "recorded_on": "2026-07-22",
        "status": "answered-no-inner-hold-definition-failed-before-publication",
        "promotable": False,
        "delegation": {"class": "B", "cycle": 2, "cycle_cap": 3},
        "authorization": c1.bind(PATCH_RECEIPT),
        "deployment": c1.bind(DEPLOYMENT),
        "diagnostic_identity": c1.bind(PRODUCT),
        "patch_gate": c1.load_json(MANIFEST, "cycle-2 manifest")["patch_gate"],
        "operator_observation": {
            "input": "(defun %c2h () 't)",
            "rendered": "*** vm: bad bytecode",
            "timing": "during defun; (%c2h) was not submitted",
            "instruction_after_observation": "no further input",
            "screenshot": c1.bind(screenshot),
            "ansi": c1.bind(ansi),
        },
        "answer": {
            "three_inner_edges_reached": False,
            "reason": (
                "Each patched edge executes SEI and then a permanent BRA-to-self. "
                "The machine instead rendered the error and returned to the REPL, "
                "so invalid dispatch, post-handler status and final vm_callprim "
                "propagation were not reached."),
            "boundary": (
                "The persistent definition failed inside c2_product_install / "
                "append service before publication. lcc_install_obj calls "
                "vm_check_status inside the service, so its longjmp precedes the "
                "patched vm_callprim-return edge."),
            "rollback": (
                "C2D stayed at 6 images / 588 entries / 2264 resolutions / "
                "283 roots, C2J is zero and READY remains one; the failed defun "
                "published no dynamic object."),
            "remaining_question": (
                "Which first service substep failed: transaction begin, emitter, "
                "append begin or transaction end."),
        },
        "captured_state": {
            "c2d_v6_header": header,
            "bank0_variance_offsets": [f"0x{offset:04x}" for offset in changed],
            "variance_class": (
                "normal IRQ/compiler scratch after a rendered error; product "
                "witnesses are stable, so no inner SEI hold is claimed"),
            "bank0": captures,
            "bank2": c1.bind(bank2_path, 0x00020000),
            "bank5": c1.bind(bank5_path, 0x00050000),
            "timing": c1.bind(HW_OUT / "capture-timing.json"),
        },
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "diagnostic_instruction_patches": 3,
            "changed_bytes": len(changed_offsets()),
            "hardware_runs": 1,
            "read_only_post_error_captures": 5,
            "remaining_autonomous_cycles": 1,
            "completed_latency_attempts": 0,
        },
        "budgets": {
            "class_b_first-execution-diagnostic": "2/3 consumed",
            "line1_product_first_reds": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
        },
        "claim_limit": (
            "This no-hit receipt localizes the failure to the definition/install "
            "service boundary. It does not identify the failing service substep, "
            "prove the subsequent execution path, change product bytes, or make "
            "a latency, promotion or acceptance claim."),
        "rollback_line": {**c1.bind(BASE_PRODUCT), "status": "untouched"},
        "next_gate": (
            "Use the final autonomous cycle only if ELF dataflow proves a stable "
            "service-boundary discriminator before hardware."),
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
        "selftest", "feasibility", "build", "check",
        "prepare-hardware", "verify-hardware", "deploy-hardware",
        "capture-hardware", "evaluate-hardware", "evaluate-no-hold"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            verify_authority()
            source = c1.regular(BASE_PRODUCT)
            exact_patch_gate(source, patched(source))
            disassembly_truth()
            classifier_selftest()
            print("c2-link50-badopcode-inner-hold: SELFTEST PASS mutations=13")
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
        elif args.action == "capture-hardware":
            value = capture_hardware()
        elif args.action == "evaluate-no-hold":
            value = evaluate_no_hold()
        else:
            value = evaluate_hardware()
        print("c2-link50-badopcode-inner-hold: " + str(value["status"]))
        return 0
    except Exception as error:
        print("c2-link50-badopcode-inner-hold: FAIL " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
