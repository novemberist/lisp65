#!/usr/bin/env python3
"""Bound the Link-62 Slot-39 completion First Red to host/ELF evidence.

This is deliberately read-only with respect to every product, carrier and
hardware artifact.  It distinguishes the linked completion poll, its Bank-5
read path and its timeout arithmetic, then records exactly which runtime
witnesses were not captured.  It does not diagnose by inference from the
Slot-39 provenance byte: that byte is a first-error stamp, not a program
counter.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import zlib

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools/llvm-mos/bin"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT_DIR = ROOT / "build/c2.2/substitution/product-link-62-post-shelf-region1"
DONOR_DIR = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
CARRIER_DIR = ROOT / (
    "build/c2.2/substitution/"
    "link62-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link62-"
    "cutpoints3-4-NONPROMOTABLE")

PRODUCT_ELF = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg.elf"
DONOR_ELF = DONOR_DIR / "lisp65-c2-substitution-linked.prg.elf"
PRODUCT_SOURCE = PRODUCT_DIR / "generated-product-sources/c2_product_runtime.c"
DONOR_SOURCE = DONOR_DIR / "generated-product-sources/c2_product_runtime.c"
CARRIER = CARRIER_DIR / (
    "runtime-overlays-session-c1-freezer-link62-stage-bound.bin")
MANIFEST = CARRIER_DIR / (
    "runtime-overlays-session-c1-freezer-link62-stage-bound.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link62-C1-Freezer-cutpoint3-"
    "prefreezer-hardware-first-red.json")
TRACE = RUN / "first-red-trace.bin"
ZP = RUN / "first-red-zp-0070-009f.bin"
C2J = RUN / "first-red-c2j.bin"
FRAME_A = RUN / "first-red-frame-a.bin"
FRAME_B = RUN / "first-red-frame-b.bin"
CONTRACT = ROOT / "config/c2-cpu-chip-write-completion-contract.json"
COMPLETION_GATE = ROOT / "tools/host-lisp/c2_cpu_chip_write_completion_gate.py"
RUNTIME_SOURCE = ROOT / "src/c2_product_runtime.c"
DMA_SOURCE = ROOT / "src/c2_platform_dma.c"
IRQ_SOURCE = ROOT / "src/c2_kernal_window.s"
RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-completion-host-elf-attribution.json")

HEADER_SECTION = ".lisp65_rt_c2append_header"
SLOT_39 = 39
TIMEOUT_FRAMES = 64
ZP_BASE = 0x70
PHASE_SCRATCH_INSTALL_SLOT_OFFSET = 302
PHASE_SCRATCH_RECORD_OFFSET = 182
PHASE_SCRATCH_SEAL_OFFSET = PHASE_SCRATCH_RECORD_OFFSET + 25


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"missing attribution authority: {path}")
    result: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    require(
        symbol.bytes > 0
        and 0 <= start <= section.bytes
        and start + symbol.bytes <= section.bytes,
        f"invalid sized ELF symbol: {name}")
    return truth.section_bytes(symbol.section)[start:start + symbol.bytes]


def bytes_at(truth: ElfTruth, section_name: str, address: int,
             length: int) -> bytes:
    section = truth.section(section_name)
    start = address - section.address
    require(
        0 <= start and start + length <= section.bytes,
        f"ELF address outside {section_name}: {address:#x}")
    return truth.section_bytes(section_name)[start:start + length]


def compiled_timeout_decision(start: int, current: int) -> bool:
    """Model the exact SEC/SBC/high-byte/CMP sequence at $c8b1..$c8ca."""
    start_low, start_high = start & 0xFF, start >> 8
    current_low, current_high = current & 0xFF, current >> 8
    carry = current_low >= start_low
    low_delta = (current_low - start_low) & 0xFF
    high_delta = (current_high - start_high - (0 if carry else 1)) & 0xFF
    return high_delta != 0 or low_delta >= TIMEOUT_FRAMES


def prove_timeout_arithmetic() -> int:
    cases = 0
    for start in (0x0000, 0x35C8, 0xFFE0):
        for delta in range(0x10000):
            current = (start + delta) & 0xFFFF
            require(
                compiled_timeout_decision(start, current)
                == (delta >= TIMEOUT_FRAMES),
                f"timeout arithmetic mismatch: {start:#06x}+{delta:#06x}")
            cases += 1
    return cases


def build() -> dict[str, Any]:
    for path in (
            PRODUCT_ELF, DONOR_ELF, PRODUCT_SOURCE, DONOR_SOURCE, CARRIER,
            MANIFEST, FIRST_RED, TRACE, ZP, C2J, FRAME_A, FRAME_B, CONTRACT,
            COMPLETION_GATE, RUNTIME_SOURCE, DMA_SOURCE, IRQ_SOURCE):
        require(path.is_file(), f"attribution input absent: {path}")

    product = ElfTruth.read(
        PRODUCT_ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    donor = ElfTruth.read(
        DONOR_ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate_source = COMPLETION_GATE.read_text(encoding="utf-8")

    require(
        first_red["status"]
            == "FIRST RED: append header entered; Cutpoint 3 not reached"
        and contract["completion"]["timeout_frames"] == TIMEOUT_FRAMES,
        "First-Red or timeout authority drift")
    require(
        sha(PRODUCT_SOURCE) == sha(DONOR_SOURCE),
        "product/donor generated runtime source differs")

    header = donor.section(HEADER_SECTION)
    header_bytes = donor.section_bytes(HEADER_SECTION)
    header_symbol = donor.symbol("c2_append_header_phase")
    poll = donor.symbol("c2_completion_poll")
    reader = donor.symbol("c2_stream_c2d_read")
    scratch = donor.symbol("lisp65_c2_phase_scratch")
    rollback_plan = symbol_bytes(donor, "lisp65_c2_append_rollback_plan")
    require(
        header.address == header_symbol.value == 0xC356
        and header.bytes == header_symbol.bytes + poll.bytes
        and header.bytes == 1526
        and poll.value == 0xC6FF
        and poll.bytes == 589
        and reader.value == 0xE691
        and reader.bytes == 87,
        "Slot-39 ELF geometry drift")

    slots = [row for row in manifest["slice_provenance"]
             if row["id"] == SLOT_39]
    require(
        len(slots) == 1
        and slots[0]["section"] == HEADER_SECTION
        and slots[0]["bytes"] == len(header_bytes)
        and slots[0]["sha256"] == hashlib.sha256(header_bytes).hexdigest(),
        "Slot-39 carrier provenance drift")
    carrier = CARRIER.read_bytes()
    occurrences = [
        index for index in range(len(carrier))
        if carrier.startswith(header_bytes, index)]
    require(
        occurrences == [55040]
        and carrier[55040 + len(header_bytes):
                    55040 + len(header_bytes) + 6]
            == bytes.fromhex("4f dc 00 00 00 00"),
        "Slot-39 final-carrier binding drift")

    # Exact linked path: bounded frame sample, one Bank-5 read, one CRC leaf,
    # and a modulo-correct >=64-frame decision.
    require(
        bytes_at(donor, HEADER_SECTION, 0xC757, 17)
            == bytes.fromhex(
                "ad84ffae83ffac84ff8406c506d0f18517")
        and bytes_at(donor, HEADER_SECTION, 0xC7F6, 3)
            == bytes.fromhex("2091e6")
        and bytes_at(donor, HEADER_SECTION, 0xC86F, 3)
            == bytes.fromhex("202d22")
        and bytes_at(donor, HEADER_SECTION, 0xC8A2, 15)
            == bytes.fromhex("ac84ffad83ffae84ff8604c404d0f1")
        and bytes_at(donor, HEADER_SECTION, 0xC8B1, 33)
            == bytes.fromhex(
                "38e51e850498e517a6208606aad006"
                "a604e0408002c9006408b0034cd6c74c03c9"),
        "linked completion-poll instruction sequence drift")
    crc_relocations = [
        row for row in donor.relocations
        if row.source_section == HEADER_SECTION
        and poll.value <= row.offset < poll.value + poll.bytes
        and row.target == "rtov_crc_mem"]
    require(
        len(crc_relocations) == 1
        and crc_relocations[0].offset == 0xC870
        and crc_relocations[0].relocation_type == "R_MOS_ADDR16",
        "Slot-39 CRC relocation identity drift")
    timeout_cases = prove_timeout_arithmetic()

    read_bytes = symbol_bytes(donor, "c2_stream_c2d_read")
    vm_load = symbol_bytes(donor, "vm_code_load")
    dma = symbol_bytes(donor, "c2_facade_target_c2_dma")
    require(
        bytes.fromhex("20c4b5a2018a60") in read_bytes
        and vm_load.endswith(bytes.fromhex("984cc7b5"))
        and dma.endswith(bytes.fromhex(
            "a9008d02d7a9b98d01d7a9b98d00d760")),
        "Bank-5 reader/DMA call chain drift")
    require(
        read_bytes.count(bytes.fromhex("20c4b5")) == 1
        and bytes.fromhex("8d00d7") not in read_bytes
        and bytes.fromhex("8d00d7") not in vm_load
        and dma.count(bytes.fromhex("8d00d7")) == 1,
        "Bank-5 reader unexpectedly acquired a private submit loop")

    irq = donor.section_bytes(".lisp65_c2_kernal_window.irq_handler")
    nmi = donor.section_bytes(
        ".lisp65_c2_kernal_window.nmi_and_freezer_return")
    require(
        bytes.fromhex("ee83ffd003ee84ff") in irq
        and bytes.fromhex("8517") not in irq
        and bytes.fromhex("851e") not in irq
        and nmi == bytes.fromhex("48ad0dddee85ff6840"),
        "frame IRQ/NMI ownership drift")

    trace = TRACE.read_bytes()
    zp = ZP.read_bytes()
    c2j = C2J.read_bytes()
    frame_a = FRAME_A.read_bytes()
    frame_b = FRAME_B.read_bytes()
    require(
        len(trace) == 8 and trace[4] == SLOT_39 and trace[5] == 0
        and len(zp) == 48 and len(c2j) == 64
        and len(frame_a) == len(frame_b) == 8,
        "hardware capture shape drift")
    actual_trace_base = (
        scratch.value + PHASE_SCRATCH_INSTALL_SLOT_OFFSET - 4)
    historical_trace_base = int(
        first_red["captures"]["phase_trace"]["address"], 16)
    require(
        scratch.value == 0xC0C6
        and actual_trace_base == 0xC1F0
        and historical_trace_base == 0xC1EE,
        "phase-trace correction premise drift")

    rtov_busy = donor.symbol("rtov_busy")
    rtov_loaded_len = donor.symbol("rtov_loaded_len")
    require(
        zp[rtov_busy.value - ZP_BASE] == 1
        and int.from_bytes(
            zp[rtov_loaded_len.value - ZP_BASE:
               rtov_loaded_len.value - ZP_BASE + 2], "little")
            == len(header_bytes) + 6,
        "runtime overlay was not executing the unique Slot-39 record")
    frame_start = int.from_bytes(frame_a[3:5], "little")
    frame_end = int.from_bytes(frame_b[3:5], "little")
    frame_delta = (frame_end - frame_start) & 0xFFFF
    require(
        frame_start == 0x35C8 and frame_end == 0x3602
        and frame_delta == 58
        and frame_a[5] == frame_b[5] == 0,
        "frame/NMI capture drift")

    target_crc32 = int.from_bytes(c2j[60:64], "little")
    calculated_crc32 = zlib.crc32(c2j[:60]) & 0xFFFFFFFF
    target_seal = binascii.crc_hqx(c2j, 0xFFFF)
    require(
        c2j[:4] == b"C2J\0"
        and target_crc32 == calculated_crc32 == 0x0F6A0FC2
        and target_seal == 0x2801,
        "captured C2J is not a final valid target record")

    # Slot 39 is both the first and last element of the rollback plan.  A
    # timeout in the initial call can therefore be followed by another
    # Slot-39 poll before the first locked cleanup stamp (Slot 41).
    require(
        rollback_plan == bytes((39, 41, 42, 43, 44, 45, 40, 39, 0)),
        "rollback plan identity drift")

    require(
        "completion-timeout-removed" in gate_source
        and "ElfTruth" not in gate_source
        and "llvm-readobj" not in gate_source,
        "completion gate coverage premise drift")

    seal_address = scratch.value + PHASE_SCRATCH_SEAL_OFFSET
    patch_opcode_offset = occurrences[0] + (0xC8CA - header.address)
    require(
        carrier[patch_opcode_offset:patch_opcode_offset + 2]
            == bytes.fromhex("b003"),
        "proposed threshold-hold patch site drift")

    return {
        "format":
            "lisp65-c2.2-Link62-slot39-completion-host-ELF-attribution-v1",
        "recorded_on": "2026-07-24",
        "status": (
            "FIRST RED: linked poll and timeout are bounded; current captures "
            "do not prove non-convergence or a missing timeout"),
        "promotable": False,
        "scope": {
            "class": "bounded-host-ELF-attribution",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "historical_receipts_modified": 0,
        },
        "authority": {
            "product_ELF": bind(PRODUCT_ELF),
            "diagnostic_donor_ELF": bind(DONOR_ELF),
            "final_nonpromotable_carrier": bind(CARRIER, 0x08000000),
            "carrier_manifest": bind(MANIFEST),
            "hardware_First_Red": bind(FIRST_RED),
            "completion_contract": bind(CONTRACT),
            "completion_gate": bind(COMPLETION_GATE),
            "product_generated_runtime": bind(PRODUCT_SOURCE),
            "donor_generated_runtime": bind(DONOR_SOURCE),
            "runtime_source": bind(RUNTIME_SOURCE),
            "DMA_source": bind(DMA_SOURCE),
            "IRQ_source": bind(IRQ_SOURCE),
            "attribution_driver": bind(Path(__file__)),
        },
        "capture_address_correction": {
            "classification": "additive evidence-metadata correction",
            "historical_receipt_preserved": True,
            "historical_address": "0x0000c1ee",
            "derived_address": "0x0000c1f0",
            "derivation": (
                "lisp65_c2_phase_scratch $c0c6 + install-slot offset 302 "
                "- capture index 4"),
            "cross_check": {
                "trace_bytes": trace.hex(),
                "index_4_slot": trace[4],
                "index_5_lock_flags": trace[5],
            },
            "semantic_effect": (
                "none: Slot 39 and unlocked-first-stamp remain the same"),
        },
        "linked_slot39": {
            "section": HEADER_SECTION,
            "VMA": "0x0000c356",
            "payload_bytes": len(header_bytes),
            "final_carrier_offset": occurrences[0],
            "final_carrier_occurrences": len(occurrences),
            "final_carrier_SHA256": hashlib.sha256(header_bytes).hexdigest(),
            "runtime_loaded_bytes": len(header_bytes) + 6,
            "rtov_busy": 1,
            "unique_length_owner": SLOT_39,
        },
        "poll_attribution": {
            "symbol": "c2_completion_poll",
            "VMA": "0x0000c6ff",
            "bytes": poll.bytes,
            "Bank5_read_call": {
                "call_VMA": "0x0000c7f6",
                "target": "c2_stream_c2d_read",
                "target_VMA": "0x0000e691",
                "target_bytes": reader.bytes,
                "software_poll_inside_reader": False,
                "DMA_submit": "one STA $d700 followed by RTS",
            },
            "target_identity_call": {
                "call_VMA": "0x0000c86f",
                "target": "rtov_crc_mem",
                "relocation_operand_VMA": "0x0000c870",
                "captured_target_C2J": {
                    "format_CRC32": "0x0f6a0fc2",
                    "format_CRC32_valid": True,
                    "computed_bookend_CRC16": "0x2801",
                },
                "missing_runtime_witness": {
                    "name": "C2AW_C2J_SEAL",
                    "address": f"0x{seal_address:08x}",
                    "bytes": 2,
                    "effect": (
                        "the target is valid now, but the capture cannot prove "
                        "that the poll compared it with 0x2801"),
                },
            },
        },
        "timeout_attribution": {
            "contract_frames": TIMEOUT_FRAMES,
            "start_sample_VMA": "0x0000c757",
            "current_sample_VMA": "0x0000c8a2",
            "decision_VMA": "0x0000c8b1",
            "threshold_branch_VMA": "0x0000c8ca",
            "linked_sequence_verdict": (
                "correct unsigned 16-bit modulo delta; exits false at "
                "elapsed >= 64 whenever control returns from the read/CRC body"),
            "exhaustive_model_cases": timeout_cases,
            "external_samples": {
                "first": f"0x{frame_start:04x}",
                "second": f"0x{frame_end:04x}",
                "delta": frame_delta,
                "threshold_crossed_from_poll_start": "not-proven",
                "reason": (
                    "the only bound external delta is 58 (<64), and the poll's "
                    "private start value at $17/$1e was not captured"),
            },
            "IRQ_verdict": {
                "raster_clock_advanced": True,
                "NMI_count": 0,
                "poll_start_cells_written_by_IRQ_or_NMI": False,
            },
        },
        "control_flow_qualification": {
            "phase_stamp_semantics": (
                "first phase provenance, not a current-PC witness"),
            "slot39_is_rollback_first_and_last": True,
            "rollback_plan": list(rollback_plan),
            "lock_flags": trace[5],
            "implication": (
                "the capture is compatible with either the initial Slot-39 "
                "poll or a rollback Slot-39 poll entered after an earlier "
                "timeout already fired"),
            "missing_runtime_witnesses": [
                "current PC",
                "poll start at $17/$1e",
                "scratch C2J seal at $c195/$c196",
                "completion mode/result bytes in c2_append_state.record",
            ],
        },
        "answers": {
            "why_slot39_did_not_converge": (
                "not decidable from the captured state: the landed C2J is "
                "valid and has seal 0x2801, but the producer seal used by the "
                "poll was not captured"),
            "why_timeout_did_not_fire": (
                "the premise is not established: the linked timeout is "
                "present and total, only 58 external frames were bound without "
                "the poll start, and the same Slot 39 can be re-entered by "
                "rollback after a prior timeout"),
            "static_suspects": {
                "unbounded_poll_loop": "refuted",
                "software_loop_in_Bank5_reader": "refuted",
                "missing_or_malformed_timeout_branch": "refuted",
            },
            "classification": (
                "evidence-model First Red; no product fix is justified yet"),
        },
        "checker_gap": {
            "finding": (
                "the existing completion gate checks source tokens and a host "
                "model; it does not prove the linked target timeout path or "
                "bind runtime start/seal witnesses"),
            "product_semantics_finding": False,
            "authorized_change_in_this_step": "none",
        },
        "recommended_next_class_C_question": {
            "action": (
                "authorize one nonpromotable threshold-hold diagnostic, not a "
                "product change"),
            "post_link_patch": {
                "carrier_file_offset_opcode": patch_opcode_offset,
                "carrier_file_offset_operand": patch_opcode_offset + 1,
                "VMA": "0x0000c8ca",
                "before": "b0 03",
                "after": "b0 fe",
                "effect": (
                    "self-loop only when the linked elapsed>=64 decision fires"),
            },
            "required_captures": [
                "PC at/near $c8ca",
                "$17/$1e poll start",
                "$ff83/$ff84 current frame",
                "$c195/$c196 producer seal",
                "C2J $05c640..$05c67f",
                "completion mode/result bytes",
            ],
            "decision_rule": (
                "threshold hold reached proves the timeout arithmetic executed; "
                "seal mismatch attributes non-convergence. No hold redirects "
                "the next attribution to the exact current PC/callee."),
        },
        "captures": {
            "phase_trace": bind(TRACE, actual_trace_base),
            "zero_page": bind(ZP, ZP_BASE),
            "C2J": bind(C2J, 0x0005C640),
            "frame_first": bind(FRAME_A, 0x0000FF80),
            "frame_second": bind(FRAME_B, 0x0000FF80),
        },
        "claim_limit": (
            "No product defect, product fix, WPLTO, new link, hardware replay, "
            "C1 closure, matrix-gate or acceptance-chain claim."),
    }


def main() -> int:
    value = build()
    serialized = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if RECEIPT.exists():
        require(
            RECEIPT.read_text(encoding="utf-8") == serialized,
            "existing attribution receipt differs")
    else:
        RECEIPT.write_text(serialized, encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
    print(
        "c2-link62-slot39-completion-attribution: FIRST RED "
        "linked-timeout-bounded runtime-witnesses-missing")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link62-slot39-completion-attribution: FIRST RED: "
            + str(error))
        raise SystemExit(2)
