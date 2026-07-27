#!/usr/bin/env python3
"""Build and evaluate the Link-64 Slot-39 reader-return discriminator."""

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
ATTRIBUTION = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-false-host-ELF-attribution.json")
ACTIVE_FIRST_RED = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-return-hardware-first-red.json")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-slot39-reader-return-hold-NONPROMOTABLE")
CARRIER = OUT / (
    "runtime-overlays-session-link64-slot39-reader-return-hold.bin")
MANIFEST = OUT / "manifest.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-reader-return-hold-nonpromotable-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-slot39-reader-return-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-reader-return-hold-hardware-receipt.json")
HARDWARE_DRIVER = ROOT / (
    "scripts/c2-link64-slot39-reader-return-hold-hw.sh")

SLOT = 39
SLOT_FILE_OFFSET = 55040
SLOT_VMA = 0xC356
HEADER_VMA = 0xC371
POLL_VMA = 0xC706
HOLD_VMA = 0xC82C
PATCH_FILE_OFFSET = SLOT_FILE_OFFSET + (HOLD_VMA - SLOT_VMA)
PATCH_IN_SLOT = HOLD_VMA - SLOT_VMA
BEFORE = bytes.fromhex("d003")
AFTER = bytes.fromhex("d0fe")
TARGET_FAMILY_CRC = 0x472A
TAIL_BYTES = 2
RECORD_ADDRESS = 0xC17C
C2J_ADDRESS = 0x0005C640
TRACE_ADDRESS = 0xC1F0
FRAME_ADDRESS = 0xFF83
RUNTIME_ZP_ADDRESS = 0x70
CALL_ZP_ADDRESS = 0x02
CALL_ZP_BYTES = 30
OBSERVED_POINTER_OFFSET = 0x1A - CALL_ZP_ADDRESS
STACK_POINTER_OFFSET = 0


class ReaderHoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReaderHoldError(message)


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
    path.chmod(0o444)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def refresh(source: bytes, tail: bytes) -> bytes:
    require(len(tail) == TAIL_BYTES, "reader-return tail width drift")
    parsed = H.parsed(data(H.BASE_CARRIER))
    row = parsed.slices[SLOT]
    require(
        row.file_offset == SLOT_FILE_OFFSET
        and row.file_size == 1509
        and row.vma == SLOT_VMA
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE,
        "reader-return geometry drift")
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
        require(pivot in basis, "reader-return tail has no CRC solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    tail = solution.to_bytes(TAIL_BYTES, "little")
    candidate = refresh(source, tail)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "reader-return family CRC was not restored")
    return tail, candidate


def validate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(
        len(source) == len(candidate)
        and source[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == BEFORE
        and candidate[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 2] == AFTER,
        "reader-return patch identity drift")
    parsed = H.parsed(candidate)
    row = parsed.slices[SLOT]
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "reader-return family identity drift")
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
                "reader-return mutation survived")
        except (ReaderHoldError, H.HoldError, R.OverlayBankError):
            rejected.append(name)
    require(len(rejected) == 5, "reader-return mutation survived")
    changed = [
        offset for offset, (left, right) in
        enumerate(zip(source, candidate)) if left != right
    ]
    return {
        "status":
            "passed-one-byte-reader-return-hold-and-complete-v4-rebinding",
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
    poll = truth.symbol("c2_completion_poll")
    section = truth.section(poll.section)
    body = truth.section_bytes(poll.section)[
        poll.value - section.address:
        poll.value - section.address + poll.bytes]
    hold = HOLD_VMA - poll.value
    pointer = 0xC7D1 - poll.value
    require(
        poll.value == POLL_VMA
        and poll.bytes == 563
        and body[hold - 4:hold + 7]
            == bytes.fromhex("2091e6aad0034cf0c8a51f")
        and body[pointer:pointer + 13]
            == bytes.fromhex("18a502690a851aa5036900851b"),
        "reader-return edge or memory-backed capture seam absent")
    return {
        "poll_symbol": poll.name,
        "poll_address": f"0x{poll.value:04x}",
        "poll_bytes": poll.bytes,
        "reader_call": "JSR $e691 at $c828",
        "hold_address": f"0x{HOLD_VMA:04x}",
        "instruction": "BNE $c831 -> BNE $c82c",
        "dataflow": (
            "c2_stream_c2d_read return in A; TAX sets Z; BNE is taken iff "
            "the Bank-5 reader returned nonzero"),
        "capture_seam": {
            "software_stack_base": "__rc0/__rc1 at $0002/$0003",
            "observed_pointer": "__rc24/__rc25 at $001a/$001b",
            "linked_relation": "observed = software_stack_base + 10",
            "proof_bytes": "18a502690a851aa5036900851b",
            "register_state_assumptions": 0,
        },
        "outcomes": {
            "hangs": (
                "reader returned nonzero; capture the live 64-byte observed "
                "buffer before CRC comparison"),
            "bad_bytecode": "reader returned zero",
        },
    }


def prepare() -> dict[str, Any]:
    source, base_deployment = H.validate_authority()
    attribution = load(ATTRIBUTION)
    active = load(ACTIVE_FIRST_RED)
    require(
        attribution["answer"]["remaining_exact_partition"] == [
            "the linked Bank-5 reader returned zero",
            ("the reader returned nonzero but content never matched before "
             "the 64-frame timeout"),
        ]
        and attribution["next_minimal_discriminator"]["instruction_VMA"]
            == "0xc82c"
        and active["hardware_First_Red"]["binary_discriminator"]["answer"]
            == "first ACTIVE c2_completion_poll returned false",
        "reader-return attribution authority drift")
    feasibility = elf_feasibility()
    tail, candidate = solve(source)
    gate = validate(source, candidate)
    write(CARRIER, candidate)
    write_json(MANIFEST, {
        "format": "lisp65-Link64-slot39-reader-return-hold-manifest-v1",
        "status": "ready-nonpromotable-reader-return-hold",
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
            "lisp65-c2.2-Link64-slot39-reader-return-hold-patch-v1",
        "recorded_on": "2026-07-26",
        "status": "ready-authorized-nonpromotable-reader-discriminator",
        "promotable": False,
        "authority": {
            "ACTIVE_false_attribution": bind(ATTRIBUTION),
            "ACTIVE_return_hardware_First_Red": bind(ACTIVE_FIRST_RED),
            "source_carrier": bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "donor_ELF": bind(DONOR_ELF),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_DRIVER),
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
            "Nonpromotable reader-return discriminator only. C1 remains "
            "OPEN; no acceptance, promotion or release claim."),
    })

    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == H.sha(H.BASE_CARRIER):
            copy = bind(CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "reader-return deployment carrier not unique")
    write_json(DEPLOYMENT, {
        "format":
            "lisp65-c2.2-Link64-slot39-reader-return-hardware-v1",
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
        "capture_domains": {
            "call_ZP": {
                "address": f"0x{CALL_ZP_ADDRESS:08x}",
                "bytes": CALL_ZP_BYTES,
            },
            "dynamic_observed": {
                "pointer_cells": "0x001a/0x001b",
                "bytes": 64,
            },
            "completion_record": {
                "address": f"0x{RECORD_ADDRESS:08x}", "bytes": 32},
            "target_C2J": {
                "address": f"0x{C2J_ADDRESS:08x}", "bytes": 64},
            "phase_trace": {
                "address": f"0x{TRACE_ADDRESS:08x}", "bytes": 8},
            "current_frame": {
                "address": f"0x{FRAME_ADDRESS:08x}", "bytes": 5},
            "runtime_slot39": {"address": "0x0000c356", "bytes": 1509},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Nonpromotable reader-return discriminator only; C1 OPEN."),
    })
    return {
        "status": "ready",
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": gate["family_crc16"],
        "patch_file_offset": PATCH_FILE_OFFSET,
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
        "reader-return deployment binding drift")
    validate(data(H.BASE_CARRIER), data(CARRIER))
    elf_feasibility()
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"reader-return preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha_bytes(data(CARRIER)),
    }


def capture_rows() -> tuple[list[dict[str, Any]], dict[str, list[bytes]]]:
    timing = load(HW_OUT / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "reader-return timing drift")
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
            f"reader-return capture {index} drift")
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
            "target_C2J_crc16":
                f"0x{R.crc16_ccitt_false(c2j):04x}",
            "current_frame":
                f"0x{int.from_bytes(frame[:2], 'little'):04x}",
        })
    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values()),
        "reader-return fixed witnesses changed across captures")
    return rows, stable


def evaluate_hang() -> dict[str, Any]:
    verify()
    rows, stable = capture_rows()
    observations: list[bytes] = []
    pointers: list[dict[str, Any]] = []
    for index in range(1, 4):
        directory = HW_OUT / f"capture-{index}"
        zp = data(directory / "call-zp.bin")
        observed = data(directory / "observed.bin")
        pointer = load(directory / "pointer.json")
        require(
            len(zp) == CALL_ZP_BYTES and len(observed) == 64
            and pointer["relation_proven"] is True
            and pointer["observed_pointer"]
                == f"0x{int.from_bytes(zp[OBSERVED_POINTER_OFFSET:OBSERVED_POINTER_OFFSET + 2], 'little'):04x}",
            f"reader-return dynamic capture {index} drift")
        observations.append(observed)
        pointers.append(pointer)
        rows[index - 1]["observed_pointer"] = pointer["observed_pointer"]
        rows[index - 1]["observed_sha256"] = sha_bytes(observed)
        rows[index - 1]["observed_equals_target_C2J"] = (
            observed == stable["c2j"][index - 1])

    screen = data(HW_OUT / "reader-return-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm:" not in screen,
        "reader-return screen does not establish the hold")
    target = stable["c2j"][0]
    all_equal = [value == target for value in observations]
    if all_equal == [True, True, True]:
        classification = "stable-target-identical-reader-exonerated"
    elif all_equal[-1] and not all_equal[0]:
        classification = "reader-visible-content-converged-during-capture"
    elif not any(all_equal):
        classification = "stable-or-changing-nonmatching-reader-content"
    else:
        classification = "nonmonotonic-reader-content"
    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-reader-return-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "completed-reader-returned-nonzero-and-held",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "carrier": bind(CARRIER, 0x08000000),
            "hardware_driver": bind(HARDWARE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "answer": {
            "binary_outcome": "hang-at-reader-success-branch",
            "reader_return": "nonzero",
            "observed_buffer_classification": classification,
            "observed_equals_target_by_capture": all_equal,
        },
        "memory_backed_capture": {
            "relation": "observed = software_stack_base + 10",
            "register_assumptions": 0,
            "pointers": pointers,
        },
        "time_separated_captures": rows,
        "stable_fixed_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            }
            for name, values in stable.items()
        },
        "observed_witnesses": [
            {
                "index": index,
                "sha256": sha_bytes(value),
                "equals_target_C2J": value == target,
            }
            for index, value in enumerate(observations, 1)
        ],
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
            "Reader-return/content attribution only. C1 remains OPEN."),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-link64-slot39-reader-return: PASS reader=nonzero "
        f"classification={classification}")
    return value


def evaluate_bad_bytecode() -> dict[str, Any]:
    verify()
    rows, stable = capture_rows()
    screen = data(HW_OUT / "reader-return-screen.txt").decode("utf-8")
    require("*** vm: bad bytecode" in screen,
            "reader-return false outcome absent from screen")
    frames = [
        int(row["current_frame"], 16)
        for row in rows
    ]
    require(frames[0] < frames[1] < frames[2],
            "reader-return postmortem frame did not progress")
    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-reader-return-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "FIRST RED: Bank-5 reader returned zero",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "carrier": bind(CARRIER, 0x08000000),
            "hardware_driver": bind(HARDWARE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "answer": {
            "binary_outcome": "bad-bytecode-and-REPL-return",
            "reader_return": "zero",
            "verdict": (
                "c2_stream_c2d_read returned zero for the statically valid "
                "Bank-5 range $c640..$c67f"),
        },
        "time_separated_postmortem_captures": rows,
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
            "Reader-return attribution only. C1 remains OPEN."),
    }
    HARDWARE_RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("c2-link64-slot39-reader-return: PASS reader=zero FIRST_RED")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", nargs="?", default="prepare",
        choices=(
            "prepare", "verify", "evaluate-hang",
            "evaluate-bad-bytecode"))
    action = parser.parse_args().action
    value = {
        "prepare": prepare,
        "verify": verify,
        "evaluate-hang": evaluate_hang,
        "evaluate-bad-bytecode": evaluate_bad_bytecode,
    }[action]()
    if action in ("prepare", "verify"):
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReaderHoldError, H.HoldError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link64-slot39-reader-return: FIRST RED: " + str(error))
        raise SystemExit(2)
