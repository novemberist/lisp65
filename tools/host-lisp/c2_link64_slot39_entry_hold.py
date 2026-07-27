#!/usr/bin/env python3
"""Prepare a zero-growth hold at the first Link-64 Slot-39 entry."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_link64_slot39_threshold_hold as H  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DONOR_ELF = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE/"
    "lisp65-c2-substitution-linked.prg.elf")
FIRST_RED = EVIDENCE / (
    "c2.2-link64-slot39-prethreshold-hardware-first-red.json")
DONOR_GATE = EVIDENCE / (
    "c2.2-link64-c1-donor-completion-phase-context-replay-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/link64-slot39-entry-hold-NONPROMOTABLE")
CARRIER = OUT / "runtime-overlays-session-link64-slot39-entry-hold.bin"
MANIFEST = OUT / "manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-entry-hold-feasibility-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-slot39-entry-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"

SLOT = 39
SLOT_FILE_OFFSET = 55040
SLOT_VMA = 0xc356
HEADER_VMA = 0xc371
HOLD_VMA = 0xc3a2
PATCH_FILE_OFFSET = SLOT_FILE_OFFSET + (HOLD_VMA - SLOT_VMA)
BEFORE = bytes.fromhex("d009")
AFTER = bytes.fromhex("d0fe")
TARGET_FAMILY_CRC = 0x472a
TAIL_BYTES = 2


class EntryHoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise EntryHoldError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def refresh(source: bytes, tail: bytes) -> bytes:
    require(len(tail) == TAIL_BYTES, "entry-hold tail width drift")
    parsed = H.parsed(H.regular(H.BASE_CARRIER))
    row = parsed.slices[SLOT]
    require(
        row.file_offset == SLOT_FILE_OFFSET
        and row.file_size == 1509
        and row.vma == SLOT_VMA
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE,
        "Link-64 entry-hold geometry drift")
    result = bytearray(source)
    result[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] = AFTER
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    result[tail_offset:tail_offset + TAIL_BYTES] = tail

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(record)
    require(fields[10] != 0, "derived v4 record CRC is forbidden zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26,
        R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    return bytes(result)


def solve_tail(source: bytes) -> tuple[bytes, bytes]:
    baseline = R.crc16_ccitt_false(refresh(source, bytes(TAIL_BYTES)))
    columns = [
        R.crc16_ccitt_false(
            refresh(source, (1 << bit).to_bytes(TAIL_BYTES, "little")))
        ^ baseline
        for bit in range(TAIL_BYTES * 8)
    ]
    basis: dict[int, tuple[int, int]] = {}
    for bit, column in enumerate(columns):
        vector, mask = column, 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                vector ^= basis[pivot][0]
                mask ^= basis[pivot][1]
            else:
                basis[pivot] = vector, mask
                break
    vector, solution = TARGET_FAMILY_CRC ^ baseline, 0
    while vector:
        pivot = vector.bit_length() - 1
        require(pivot in basis, "entry-hold tail has no CRC solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    tail = solution.to_bytes(TAIL_BYTES, "little")
    candidate = refresh(source, tail)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "entry-hold outer family CRC was not restored")
    return tail, candidate


def validate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(
        len(source) == len(candidate)
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE
        and candidate[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == AFTER,
        "entry-hold patch identity drift")
    parsed = H.parsed(candidate)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "entry-hold family identity drift")
    row = parsed.slices[SLOT]
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    rejected: list[str] = []
    for name, offset in (
            ("opcode", PATCH_FILE_OFFSET),
            ("operand", PATCH_FILE_OFFSET + 1),
            ("payload-CRC", record_offset + 20),
            ("record-CRC", record_offset + 22),
            ("family-tail", tail_offset)):
        mutant = bytearray(candidate)
        mutant[offset] ^= 1
        try:
            test = H.parsed(bytes(mutant))
            require(
                bytes(mutant)[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2]
                    == AFTER
                and R.crc16_ccitt_false(bytes(mutant)) == TARGET_FAMILY_CRC
                and test.slices[SLOT].vma == SLOT_VMA,
                "mutated entry-hold survived")
        except (EntryHoldError, H.HoldError, R.OverlayBankError):
            rejected.append(name)
    require(len(rejected) == 5, "entry-hold mutation survived")
    changed = [
        offset for offset, (left, right) in
        enumerate(zip(source, candidate)) if left != right
    ]
    return {
        "status": "passed-one-byte-entry-hold-and-complete-v4-rebinding",
        "slot": SLOT,
        "section": ".lisp65_rt_c2append_header",
        "instruction_VMA": f"0x{HOLD_VMA:04x}",
        "instruction_file_offset": PATCH_FILE_OFFSET,
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "executable_operand_bytes_changed": 1,
        "carrier_size_delta": 0,
        "derived_identity_bytes_changed": len(changed) - 1,
        "all_changed_file_offsets": changed,
        "payload_crc16": f"0x{row.crc16:04x}",
        "record_crc16": f"0x{row.record_crc16:04x}",
        "directory_crc16": f"0x{parsed.directory_crc16:04x}",
        "header_crc16": f"0x{parsed.header_crc16:04x}",
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
    }


def elf_feasibility() -> dict[str, Any]:
    truth = ElfTruth.read(
        DONOR_ELF, llvm_readobj=H.LENGTH.READOBJ, include_section_data=True)
    header = truth.symbol("c2_append_header_phase")
    section = truth.section(header.section)
    body = truth.section_bytes(header.section)[
        header.value - section.address:
        header.value - section.address + header.bytes]
    offset = HOLD_VMA - HEADER_VMA
    require(
        header.value == HEADER_VMA and body[offset:offset + 2] == BEFORE,
        "entry-hold branch absent from donor ELF")
    trace_store = bytes.fromhex("8cf4c1")
    require(
        trace_store in body[:offset]
        and body[offset + 2:offset + 9] == bytes.fromhex(
            "a416c404d0034c"),
        "entry hold is not after trace and before mode dispatch")
    return {
        "header_symbol": header.name,
        "header_address": f"0x{header.value:04x}",
        "header_bytes": header.bytes,
        "hold_address": f"0x{HOLD_VMA:04x}",
        "instruction": "BNE $c3ad -> BNE $c3a2",
        "branch_predicate": (
            "the high byte of the non-NULL phase-scratch context differs "
            "from zero; the self-loop is therefore entered before mode read"),
        "trace_stamped_before_hold": True,
        "completion_record_untouched_before_hold": True,
        "register_liveness_assumptions": 0,
        "capture_authorities": [
            "c2_append_state.record[24..31] at $c17c",
            "target C2J[64] at $0005c640",
            "phase trace at $c1f0",
        ],
    }


def main() -> int:
    source, base_deployment = H.validate_authority()
    first_red = H.load_json(FIRST_RED)
    donor_gate = H.load_json(DONOR_GATE)
    require(
        first_red["hardware_First_Red"]["threshold_hold_reached"] is False
        and donor_gate["result"]["phase_call_contexts"]["call_count"] == 5,
        "entry-hold authority drift")
    feasibility = elf_feasibility()
    tail, candidate = solve_tail(source)
    gate = validate(source, candidate)
    H.write_exact(CARRIER, candidate)
    H.write_json(MANIFEST, {
        "format": "lisp65-Link64-slot39-entry-hold-manifest-v1",
        "status": "ready-nonpromotable-entry-hold",
        "promotable": False,
        "source": H.bind(H.BASE_CARRIER, 0x08000000),
        "candidate": H.bind(CARRIER, 0x08000000),
        "patch_and_rebinding": gate,
        "solved_post_RTS_tail": {
            "hex": tail.hex(),
            "bytes_little_endian": list(tail),
        },
    })
    H.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link64-slot39-entry-hold-feasibility-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-nonpromotable-first-entry-hold",
        "promotable": False,
        "authority": {
            "prethreshold_First_Red": H.bind(FIRST_RED),
            "source_carrier": H.bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": H.bind(H.BASE_DEPLOYMENT),
            "donor_ELF": H.bind(DONOR_ELF),
            "donor_completion_role_replay": H.bind(DONOR_GATE),
            "driver": H.bind(Path(__file__)),
        },
        "ELF_feasibility": feasibility,
        "candidate": {
            "carrier": H.bind(CARRIER, 0x08000000),
            "manifest": H.bind(MANIFEST),
            "identity_separate_from_Link64": True,
            "lifecycle": "discard after one diagnostic capture",
        },
        "patch_and_rebinding": gate,
        "construction": {
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "all_capacity_deltas": 0,
        },
        "claim_limit": (
            "Feasibility and nonpromotable diagnostic artifact only. "
            "No product, C1, matrix, acceptance or release claim."),
    })

    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == H.sha(H.BASE_CARRIER):
            copy = H.bind(CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "entry-hold deployment carrier is not unique")
    H.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link64-slot39-entry-hold-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-awaiting-separate-hardware-authorization",
        "promotable": False,
        "authority": {
            "feasibility_receipt": H.bind(RECEIPT),
            "manifest": H.bind(MANIFEST),
            "source_deployment": H.bind(H.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "test": {
            "form": "(defun %c1e () (quote t))",
            "hold_VMA": f"0x{HOLD_VMA:04x}",
            "capture_intervals_seconds": [0, 1, 5],
            "expected_witness": (
                "the first Slot-39 mode/result/seal/C2J before any poll or "
                "cleanup mutation"),
        },
        "capture_domains": {
            "completion_record": {"address": "0x0000c17c", "bytes": 32},
            "target_C2J": {"address": "0x0005c640", "bytes": 64},
            "phase_trace": {"address": "0x0000c1f0", "bytes": 8},
            "runtime_ZP": {"address": "0x00000070", "bytes": 48},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Nonpromotable entry-state diagnostic only; C1 remains OPEN."),
    })
    print(
        "c2-link64-slot39-entry-hold: PASS "
        f"patch={PATCH_FILE_OFFSET} carrier={sha_bytes(candidate)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EntryHoldError, H.HoldError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link64-slot39-entry-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
