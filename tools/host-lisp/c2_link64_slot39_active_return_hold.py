#!/usr/bin/env python3
"""Build and evaluate the Link-64 Slot-39 ACTIVE return discriminator."""

from __future__ import annotations

import argparse
import hashlib
import json
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
ENTRY_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-entry-hold-hardware-receipt.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-slot39-active-return-hold-NONPROMOTABLE")
CARRIER = OUT / (
    "runtime-overlays-session-link64-slot39-active-return-hold.bin")
MANIFEST = OUT / "manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-active-return-hold-nonpromotable-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-slot39-active-return-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-active-return-hold-hardware-receipt.json")
HARDWARE_DRIVER = ROOT / (
    "scripts/c2-link64-slot39-active-return-hold-hw.sh")

SLOT = 39
SLOT_FILE_OFFSET = 55040
SLOT_VMA = 0xc356
HEADER_VMA = 0xc371
HOLD_VMA = 0xc3e9
PATCH_FILE_OFFSET = SLOT_FILE_OFFSET + (HOLD_VMA - SLOT_VMA)
PATCH_IN_SLOT = HOLD_VMA - SLOT_VMA
BEFORE = bytes.fromhex("d003")
AFTER = bytes.fromhex("d0fe")
TARGET_FAMILY_CRC = 0x472a
TAIL_BYTES = 2


class ActiveHoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ActiveHoldError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value = data(path)
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(data(path) == value, f"generated artifact differs: {path}")
        return
    path.write_bytes(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def refresh(source: bytes, tail: bytes) -> bytes:
    require(len(tail) == TAIL_BYTES, "ACTIVE-return tail width drift")
    parsed = H.parsed(data(H.BASE_CARRIER))
    row = parsed.slices[SLOT]
    require(
        row.file_offset == SLOT_FILE_OFFSET
        and row.file_size == 1509
        and row.vma == SLOT_VMA
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE,
        "ACTIVE-return geometry drift")
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


def solve(source: bytes) -> tuple[bytes, bytes]:
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
        require(pivot in basis, "ACTIVE-return tail has no CRC solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    tail = solution.to_bytes(TAIL_BYTES, "little")
    candidate = refresh(source, tail)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "ACTIVE-return family CRC was not restored")
    return tail, candidate


def validate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(
        len(source) == len(candidate)
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE
        and candidate[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == AFTER,
        "ACTIVE-return patch identity drift")
    parsed = H.parsed(candidate)
    row = parsed.slices[SLOT]
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "ACTIVE-return family identity drift")
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
                and test.slices[SLOT].vma == SLOT_VMA
                and R.crc16_ccitt_false(bytes(mutant))
                    == TARGET_FAMILY_CRC,
                "ACTIVE-return mutation survived")
        except (ActiveHoldError, H.HoldError, R.OverlayBankError):
            rejected.append(name)
    require(len(rejected) == 5, "ACTIVE-return mutation survived")
    changed = [
        offset for offset, (left, right) in
        enumerate(zip(source, candidate)) if left != right
    ]
    return {
        "status":
            "passed-one-byte-ACTIVE-return-hold-and-complete-v4-rebinding",
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
        header.value == HEADER_VMA
        and body[offset - 3:offset + 5] == bytes.fromhex(
            "a201a8d0034ca9c6"),
        "ACTIVE-return discriminator edge absent from donor ELF")
    return {
        "header_symbol": header.name,
        "header_address": f"0x{header.value:04x}",
        "hold_address": f"0x{HOLD_VMA:04x}",
        "instruction": "BNE $c3ee -> BNE $c3e9",
        "dataflow": (
            "c2_completion_poll return in A; TAY sets Z; BNE is taken "
            "iff the first ACTIVE poll returned nonzero"),
        "outcomes": {
            "hangs": "first ACTIVE completion poll returned success",
            "bad_bytecode": "first ACTIVE completion poll returned failure",
        },
        "external_register_capture_required": False,
    }


def prepare() -> dict[str, Any]:
    source, base_deployment = H.validate_authority()
    entry = load(ENTRY_RECEIPT)
    require(
        entry["answer"]["first_entry_mode"] == "0xa1 (ACTIVE)"
        and entry["answer"]["first_entry_journal_result"]
            == "2 (PREPARED)"
        and entry["answer"]["seal_matches"] is True,
        "ACTIVE-return authority drift")
    feasibility = elf_feasibility()
    tail, candidate = solve(source)
    gate = validate(source, candidate)
    write(CARRIER, candidate)
    write_json(MANIFEST, {
        "format": "lisp65-Link64-slot39-ACTIVE-return-hold-manifest-v1",
        "status": "ready-nonpromotable-ACTIVE-return-hold",
        "promotable": False,
        "source": bind(H.BASE_CARRIER, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "patch_and_rebinding": gate,
        "solved_post_RTS_tail": {
            "hex": tail.hex(),
            "bytes_little_endian": list(tail),
        },
    })
    write_json(RECEIPT, {
        "format":
            "lisp65-c2.2-Link64-slot39-ACTIVE-return-hold-patch-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-nonpromotable-ACTIVE-return-discriminator",
        "promotable": False,
        "authority": {
            "entry_hold_hardware_receipt": bind(ENTRY_RECEIPT),
            "source_carrier": bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "donor_ELF": bind(DONOR_ELF),
            "driver": bind(Path(__file__)),
        },
        "ELF_feasibility": feasibility,
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "identity_separate_from_Link64": True,
            "lifecycle": "discard after one diagnostic outcome",
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
            "Nonpromotable binary discriminator only. C1 remains OPEN."),
    })
    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == H.sha(H.BASE_CARRIER):
            copy = bind(CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "ACTIVE-return deployment carrier not unique")
    write_json(DEPLOYMENT, {
        "format":
            "lisp65-c2.2-Link64-slot39-ACTIVE-return-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "test": {
            "form": "(defun %c1e () (quote t))",
            "hold_VMA": f"0x{HOLD_VMA:04x}",
            "capture_intervals_seconds": [0, 1, 5],
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Nonpromotable ACTIVE-return discriminator only; C1 OPEN."),
    })
    return {
        "status": "ready",
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def verify() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    receipt = load(RECEIPT)
    require(
        deployment["status"] == "ready-authorized-nonpromotable-hardware"
        and deployment["authority"]["patch_receipt"]["sha256"]
            == sha_bytes(data(RECEIPT))
        and receipt["candidate"]["carrier"]["sha256"]
            == sha_bytes(data(CARRIER)),
        "ACTIVE-return deployment binding drift")
    validate(data(H.BASE_CARRIER), data(CARRIER))
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"ACTIVE-return preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha_bytes(data(CARRIER)),
    }


def evaluate_hang() -> dict[str, Any]:
    verify()
    timing = load(HW_OUT / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "ACTIVE-return timing drift")
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "completion-record", "c2j", "trace", "runtime-slot39")
    }
    rows: list[dict[str, Any]] = []
    for index in range(1, 4):
        directory = HW_OUT / f"capture-{index}"
        record = data(directory / "completion-record.bin")
        c2j = data(directory / "c2j.bin")
        trace = data(directory / "trace.bin")
        slot = data(directory / "runtime-slot39.bin")
        frame = data(directory / "frame.bin")
        require(
            len(record) == 32 and len(c2j) == 64 and len(trace) == 8
            and len(slot) == 1509 and len(frame) == 5
            and trace[4] == SLOT
            and slot[PATCH_IN_SLOT:PATCH_IN_SLOT + 2] == AFTER,
            f"ACTIVE-return capture {index} drift")
        for name, value in (
                ("completion-record", record), ("c2j", c2j),
                ("trace", trace), ("runtime-slot39", slot)):
            stable[name].append(value)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{record[25] | record[26] << 8:04x}",
            "target_C2J_crc16": f"0x{R.crc16_ccitt_false(c2j):04x}",
            "current_frame":
                f"0x{int.from_bytes(frame[:2], 'little'):04x}",
        })
    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values()),
        "ACTIVE-return hold changed across captures")
    screen = data(HW_OUT / "active-return-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm:" not in screen,
        "ACTIVE-return screen does not establish the success hold")
    record, c2j = stable["completion-record"][0], stable["c2j"][0]
    require(
        record[24] == 0xa1 and record[31] == 2
        and (record[25] | record[26] << 8)
            == R.crc16_ccitt_false(c2j) == 0x2801,
        "ACTIVE-return hold lost its entry authority")
    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-ACTIVE-return-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "completed-first-ACTIVE-poll-returned-success",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "carrier": bind(CARRIER, 0x08000000),
            "hardware_driver": bind(HARDWARE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "answer": {
            "binary_outcome": "hang-at-success-branch",
            "first_ACTIVE_poll_return": 1,
            "verdict": (
                "the first ACTIVE completion poll succeeded; the original "
                "Slot-39 failure occurs at a later header invocation or "
                "after the ACTIVE success path"),
        },
        "time_separated_captures": rows,
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            }
            for name, values in stable.items()
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "diagnostic_hardware_runs": 1,
            "latency_attempts_consumed": 0,
        },
        "diagnostic_lifecycle": {
            "identity": sha_bytes(data(CARRIER)),
            "eligible_for_promotion": False,
            "state": "discarded-after-capture",
        },
        "claim_limit": (
            "Binary return attribution only. C1 remains OPEN; no "
            "acceptance-chain, promotion or release claim."),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("c2-link64-slot39-ACTIVE-return: PASS first_poll=success")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", nargs="?", default="prepare",
        choices=("prepare", "verify", "evaluate-hang"))
    action = parser.parse_args().action
    value = {
        "prepare": prepare,
        "verify": verify,
        "evaluate-hang": evaluate_hang,
    }[action]()
    if action != "evaluate-hang":
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ActiveHoldError, H.HoldError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link64-slot39-ACTIVE-return: FIRST RED: " + str(error))
        raise SystemExit(2)
