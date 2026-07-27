#!/usr/bin/env python3
"""Prepare/evaluate a sealed Link-64 Slot-39 threshold-hold derivative."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import struct
import sys
import termios
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_completion_retry_length_elf_gate as LENGTH  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
BASE_CARRIER = BASE_DIR / (
    "runtime-overlays-session-c1-freezer-link64-stage-bound.bin")
BASE_MANIFEST = BASE_DIR / (
    "runtime-overlays-session-c1-freezer-link64-stage-bound.json")
OVERFLOW = BASE_DIR / (
    "runtime-overlays-session-c1-freezer-link64-region1.bin")
BASE_DEPLOYMENT = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-cutpoints3-4-attempt4-"
    "NONPROMOTABLE/deployment.json")
PRODUCT_ELF = ROOT / (
    "build/c2.2/substitution/"
    "product-link-64-nonlto-stateless-completion-length/"
    "lisp65-c2-substitution-linked.prg.elf")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-link64-C1-cutpoint3-long-quote-hardware-first-red.json")
QUOTE_RECEIPT = EVIDENCE / (
    "c2.2-link64-quote-emission-host-attribution-receipt.json")

OUT = ROOT / (
    "build/c2.2/substitution/"
    "link64-slot39-threshold-hold-NONPROMOTABLE")
PATCHED_CARRIER = OUT / (
    "runtime-overlays-session-link64-slot39-threshold-hold.bin")
PATCH_MANIFEST = OUT / "manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-threshold-hold-nonpromotable-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link64-slot39-threshold-hold-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-threshold-hold-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-link64-slot39-threshold-hold-hw.sh"
PC_CAPTURE = HW_OUT / "pc-captures.json"
DEVICE = "/dev/ttyUSB1"

SLOT = 39
EXPECTED_BUILD_ID = 0x94D09B0C
EXPECTED_VMA = 0xC356
MAX_SLICE_BYTES = 1792
TARGET_FAMILY_CRC = 0x472A
TAIL_BYTES = 2
INSTRUCTION_FILE_OFFSET = 56428
INSTRUCTION_VMA = 0xC8C2
BEFORE = bytes.fromhex("b02c")
AFTER = bytes.fromhex("b0fe")
RECORD_ADDRESS = 0xC17C
SEAL_ADDRESS = 0xC195
TRACE_ADDRESS = 0xC1F0
C2J_ADDRESS = 0x0005C640


class HoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HoldError(message)


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            f"not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value = regular(path)
    result: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(regular(path).decode("utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def write_exact(path: Path, value: bytes, mode: int = 0o444) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(regular(path) == value, f"generated artifact differs: {path}")
        return
    path.write_bytes(value)
    os.chmod(path, mode)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_exact(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def parsed(image: bytes) -> R.ParsedBank:
    return R.validate_region_images(
        image, regular(OVERFLOW),
        expected_build_id=EXPECTED_BUILD_ID,
        expected_vma=EXPECTED_VMA,
        max_slice_bytes=MAX_SLICE_BYTES,
        format_version=R.VERSION_V4)


def refresh(source: bytes, tail: bytes) -> bytes:
    require(len(tail) == TAIL_BYTES, "fixed tail width drift")
    base = parsed(regular(BASE_CARRIER))
    row = base.slices[SLOT]
    require(
        row.file_offset == 55040 and row.file_size == 1509
        and row.vma == EXPECTED_VMA
        and row.file_offset <= INSTRUCTION_FILE_OFFSET
            < row.file_offset + row.file_size,
        "Link-64 Slot-39 carrier geometry drift")
    result = bytearray(source)
    result[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] = AFTER
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    result[tail_offset:tail_offset + TAIL_BYTES] = tail

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    require(fields[0] == SLOT and fields[3] == row.file_size,
            "Link-64 Slot-39 record geometry drift")
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(record)
    require(fields[10] != 0, "derived v4 record CRC is forbidden zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
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
    vector = TARGET_FAMILY_CRC ^ baseline
    solution = 0
    while vector:
        pivot = vector.bit_length() - 1
        require(pivot in basis, "two-byte stage tail has no CRC solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    tail = solution.to_bytes(TAIL_BYTES, "little")
    candidate = refresh(source, tail)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "outer Link-64 family CRC was not restored")
    return tail, candidate


def validate_candidate(source: bytes, candidate: bytes) -> R.ParsedBank:
    require(len(source) == len(candidate), "carrier size changed")
    require(source[INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2]
            == BEFORE
            and candidate[
                INSTRUCTION_FILE_OFFSET:INSTRUCTION_FILE_OFFSET + 2] == AFTER,
            "threshold self-loop identity drift")
    value = parsed(candidate)
    require(R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
            "Link-64 family identity drift")
    return value


def mutation_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    value = validate_candidate(source, candidate)
    row = value.slices[SLOT]
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    mutations: dict[str, bytearray] = {}
    for name, offset in (
            ("opcode", INSTRUCTION_FILE_OFFSET),
            ("operand", INSTRUCTION_FILE_OFFSET + 1),
            ("payload-CRC", record_offset + 20),
            ("record-CRC", record_offset + 22),
            ("family-tail", tail_offset)):
        mutant = bytearray(candidate)
        mutant[offset] ^= 1
        mutations[name] = mutant
    rejected: list[str] = []
    for name, mutant in mutations.items():
        try:
            validate_candidate(source, bytes(mutant))
        except (HoldError, R.OverlayBankError):
            rejected.append(name)
    require(len(rejected) == len(mutations),
            "threshold-hold mutation survived")
    changed = [
        index for index, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]]
    return {
        "status": "passed-one-byte-hold-and-complete-v4-rebinding",
        "slot": SLOT,
        "section": ".lisp65_rt_c2append_header",
        "instruction_VMA": f"0x{INSTRUCTION_VMA:04x}",
        "instruction_file_offset": INSTRUCTION_FILE_OFFSET,
        "before_hex": BEFORE.hex(),
        "after_hex": AFTER.hex(),
        "executable_operand_bytes_changed": 1,
        "carrier_size_delta": 0,
        "derived_identity_bytes_changed": len(changed) - 1,
        "all_changed_file_offsets": changed,
        "payload_crc16": f"0x{row.crc16:04x}",
        "record_crc16": f"0x{row.record_crc16:04x}",
        "directory_crc16": f"0x{value.directory_crc16:04x}",
        "header_crc16": f"0x{value.header_crc16:04x}",
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
    }


def validate_authority() -> tuple[bytes, dict[str, Any]]:
    deployment = load_json(BASE_DEPLOYMENT)
    first_red = load_json(HARDWARE_FIRST_RED)
    quote = load_json(QUOTE_RECEIPT)
    require(
        sha(BASE_CARRIER)
            == "bb436ba264065ec49a76dc90f60b9226f1d59065d51ef181e9454990cc40ce1b"
        and sha(BASE_MANIFEST)
            == "d15c3329c14c877689c9da6e963a74a9683b17d03f6aa29645736bdaefe138a6"
        and sha(BASE_DEPLOYMENT)
            == "aec06ae9fdafb74298389ab356c7dc51bff4f66c170152878d8e0518bfbeb27d"
        and sha(HARDWARE_FIRST_RED)
            == "f9b8e819a7637e5a123c0b74abf4250c8c51ea0323365515ff34f43886a6d95d",
        "Link-64 hold authority drift")
    require(
        first_red["status"].startswith("FIRST RED:")
        and first_red["first_red"]["phase_trace"][
            "last_session_slot"] == 39
        and first_red["first_red"]["C2J"]["state"] == "ACTIVE/nonzero"
        and first_red["first_red"]["screen_status"]
            == "*** vm: bad bytecode"
        and quote["status"]
            == "passed-no-host-emission-divergence",
        "Link-64 First Red or quote attribution drift")
    linked = LENGTH.audit_elf(PRODUCT_ELF)
    require(
        linked["phase_call_contexts"]["call_count"] == 4
        and linked["phase_mutation_count"] == 6,
        "Link-64 linked mode attribution drift")
    return regular(BASE_CARRIER), deployment


def prepare() -> dict[str, Any]:
    source, base_deployment = validate_authority()
    tail, candidate = solve_tail(source)
    gate = mutation_gate(source, candidate)
    write_exact(PATCHED_CARRIER, candidate)
    manifest = {
        "format": "lisp65-Link64-slot39-threshold-hold-manifest-v1",
        "status": "ready-nonpromotable-threshold-hold",
        "promotable": False,
        "source": bind(BASE_CARRIER, 0x08000000),
        "candidate": bind(PATCHED_CARRIER, 0x08000000),
        "patch_and_rebinding": gate,
        "solved_post_RTS_tail": {
            "bytes_little_endian": list(tail),
            "hex": tail.hex(),
            "width": len(tail),
        },
    }
    write_json(PATCH_MANIFEST, manifest)
    receipt = {
        "format": "lisp65-c2.2-Link64-slot39-threshold-hold-patch-v1",
        "recorded_on": "2026-07-25",
        "status": "ready-nonpromotable-Link64-threshold-hold",
        "promotable": False,
        "authority": {
            "hardware_First_Red": bind(HARDWARE_FIRST_RED),
            "quote_parity_attribution": bind(QUOTE_RECEIPT),
            "source_carrier": bind(BASE_CARRIER, 0x08000000),
            "source_manifest": bind(BASE_MANIFEST),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "overflow_region": bind(OVERFLOW, 0x08300000),
            "Link64_ELF": bind(PRODUCT_ELF),
            "linked_mode_gate": bind(Path(LENGTH.__file__)),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "host_attribution": {
            "mode_swap_hypothesis": "rejected-in-final-linked-code",
            "header_poll_edges": LENGTH.audit_elf(PRODUCT_ELF)[
                "phase_call_contexts"],
            "old_end_to_end_fixture_gap": (
                "the historical exact-image oracle and linked walker did not "
                "execute the real completion phase bodies"),
            "Xemu": (
                "non-authoritative dry run did not reach the Link-64 REPL; "
                "no product inference"),
            "next_witness": (
                "hold at the 64-frame Slot-39 threshold before status "
                "destruction and capture mode/seal/result/C2J"),
        },
        "candidate": {
            "carrier": bind(PATCHED_CARRIER, 0x08000000),
            "manifest": bind(PATCH_MANIFEST),
            "identity_separate_from_Link64": True,
            "lifecycle": "discard after diagnostic capture",
        },
        "patch_and_rebinding": gate,
        "construction": {
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Nonpromotable diagnostic identity only; no product, C1, matrix, "
            "acceptance, promotion, latency, or release claim."),
    }
    write_json(PATCH_RECEIPT, receipt)

    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == sha(BASE_CARRIER):
            copy = bind(PATCHED_CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "Link-64 deployment does not uniquely name carrier")
    deployment = {
        "format": "lisp65-c2.2-Link64-slot39-threshold-hold-hardware-v1",
        "recorded_on": "2026-07-25",
        "status": "ready-nonpromotable-Link64-threshold-hold-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "patch_manifest": bind(PATCH_MANIFEST),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "test": {
            "form": "(defun %c1e () (quote t))",
            "hold_VMA": f"0x{INSTRUCTION_VMA:04x}",
            "timeout_frames": 64,
            "capture_intervals_seconds": [0, 1, 5],
        },
        "capture_domains": {
            "poll_state": {"address": "0x00000017", "bytes": 16},
            "completion_record": {
                "address": f"0x{RECORD_ADDRESS:08x}", "bytes": 32},
            "phase_trace": {
                "address": f"0x{TRACE_ADDRESS:08x}", "bytes": 8},
            "runtime_ZP": {"address": "0x00000070", "bytes": 48},
            "current_frame": {"address": "0x0000ff83", "bytes": 5},
            "target_C2J": {
                "address": f"0x{C2J_ADDRESS:08x}", "bytes": 64},
            "runtime_slot39": {
                "address": "0x0000c356", "bytes": 1509},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": receipt["claim_limit"],
    }
    write_json(DEPLOYMENT, deployment)
    return {
        "status": "ready",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def verify() -> dict[str, Any]:
    source, base_deployment = validate_authority()
    candidate = regular(PATCHED_CARRIER)
    gate = mutation_gate(source, candidate)
    receipt = load_json(PATCH_RECEIPT)
    deployment = load_json(DEPLOYMENT)
    require(
        receipt["candidate"]["carrier"]["sha256"] == sha(PATCHED_CARRIER)
        and deployment["product"] == base_deployment["product"]
        and deployment["status"]
            == "ready-nonpromotable-Link64-threshold-hold-hardware",
        "Link-64 threshold-hold binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(len(regular(path)) == row["bytes"]
                and sha(path) == row["sha256"],
                f"Link-64 threshold preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def serial_read(fd: int, seconds: float) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        timeout = min(0.02, max(0.0, deadline - time.monotonic()))
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            try:
                result.extend(os.read(fd, 8192))
            except BlockingIOError:
                pass
    return bytes(result)


def slow_write(fd: int, value: bytes) -> None:
    for byte in value:
        while True:
            try:
                if os.write(fd, bytes((byte,))):
                    break
            except BlockingIOError:
                time.sleep(0.001)


def configure_serial(fd: int) -> None:
    fcntl.fcntl(
        fd, fcntl.F_SETFL,
        fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = (
        attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE
            | termios.CRTSCTS)
    ) | termios.CS8 | termios.CLOCAL | termios.CREAD
    attrs[3] = 0
    attrs[4] = termios.B2000000
    attrs[5] = termios.B2000000
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def monitor_sync(fd: int, token: bytes) -> None:
    slow_write(fd, b"\x15#\r")
    time.sleep(0.05)
    serial_read(fd, 0.2)
    slow_write(fd, token)
    response = serial_read(fd, 0.5)
    require(token in response, "serial monitor synchronisation failed")


def capture_one_pc(fd: int, index: int) -> dict[str, Any]:
    token = f"#c8c2{index:04x}\r".encode()
    monitor_sync(fd, token)
    slow_write(fd, b"t1\r")
    time.sleep(0.02)
    slow_write(fd, b"r\r")
    raw = serial_read(fd, 0.5)
    slow_write(fd, b"t0\r")
    serial_read(fd, 0.1)
    match = re.search(rb"\n,[0-9A-Fa-f]{4}([0-9A-Fa-f]{4})", raw)
    require(match is not None, f"PC absent from register response {index}")
    pc = int(match.group(1), 16)
    return {
        "index": index,
        "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "PC": f"0x{pc:04x}",
        "raw_hex": raw.hex(),
        "inside_completion_poll": 0xC6CA <= pc < 0xC6CA + 563,
        # Register sampling single-steps the two-byte BCS loop. Depending on
        # the monitor pipeline, R reports the opcode or operand address.
        "inside_threshold_loop": pc in (INSTRUCTION_VMA,
                                        INSTRUCTION_VMA + 1),
    }


def capture_pc() -> dict[str, Any]:
    verify()
    require(not PC_CAPTURE.exists(), "Link-64 PC capture is one-shot")
    fd = os.open(DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        configure_serial(fd)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(capture_one_pc(fd, index))
    finally:
        os.close(fd)
    value = {
        "format": "lisp65-Link64-slot39-threshold-PC-captures-v2",
        "capture_intervals_seconds": [0, 1, 5],
        "device": DEVICE,
        "rows": rows,
        "capture_effect": (
            "monitor t1/r/t0 samples PC and resumes the already-running "
            "nonpromotable Slot-39 self-loop"),
    }
    write_json(PC_CAPTURE, value)
    return value


def evaluate() -> dict[str, Any]:
    verify()
    pc_capture = load_json(PC_CAPTURE)
    pc_rows = pc_capture["rows"]
    require(
        len(pc_rows) == 3
        and all(row["inside_completion_poll"] for row in pc_rows)
        and all(row["inside_threshold_loop"] for row in pc_rows),
        "Link-64 PCs do not establish the Slot-39 threshold loop")
    timing = load_json(HW_OUT / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "Link-64 capture timing drift")
    captures: list[dict[str, Any]] = []
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "poll-state", "completion-record", "trace", "runtime-zp",
            "c2j", "runtime-slot39")
    }
    for index in range(1, 4):
        directory = HW_OUT / f"capture-{index}"
        record = regular(directory / "completion-record.bin")
        c2j = regular(directory / "c2j.bin")
        values = {
            "poll-state": regular(directory / "poll-state.bin"),
            "completion-record": record,
            "trace": regular(directory / "trace.bin"),
            "runtime-zp": regular(directory / "runtime-zp.bin"),
            "c2j": c2j,
            "runtime-slot39": regular(directory / "runtime-slot39.bin"),
        }
        require(len(record) == 32 and len(c2j) == 64,
                "Link-64 threshold capture geometry drift")
        for name, data in values.items():
            stable[name].append(data)
        frame = regular(directory / "frame.bin")
        poll_state = values["poll-state"]
        poll_start = poll_state[7] | poll_state[0] << 8
        current_frame = int.from_bytes(frame[:2], "little")
        producer = record[25] | record[26] << 8
        target = R.crc16_ccitt_false(c2j)
        captures.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "mode": f"0x{record[24]:02x}",
            "producer_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches_target": producer == target,
            "journal_result": record[31],
            "poll_start": f"0x{poll_start:04x}",
            "current_frame": f"0x{current_frame:04x}",
            "external_elapsed_frames":
                (current_frame - poll_start) & 0xffff,
            "record": bind(directory / "completion-record.bin",
                           RECORD_ADDRESS),
            "C2J": bind(directory / "c2j.bin", C2J_ADDRESS),
            "poll_state": bind(directory / "poll-state.bin", 0x17),
            "phase_trace": bind(directory / "trace.bin", TRACE_ADDRESS),
            "runtime_ZP": bind(directory / "runtime-zp.bin", 0x70),
            "frame": bind(directory / "frame.bin", 0xFF83),
            "runtime_slot39": bind(
                directory / "runtime-slot39.bin", EXPECTED_VMA),
        })
    for name, values in stable.items():
        require(values[0] == values[1] == values[2],
                f"Link-64 {name} witness is not time-stable")
    window = stable["runtime-slot39"][0]
    offset = INSTRUCTION_VMA - EXPECTED_VMA
    require(
        len(window) == 1509 and window[offset:offset + 2] == AFTER,
        "runtime window is not the patched Slot-39 identity")
    first = captures[0]
    if first["mode"] == "0xa1":
        invocation = "ACTIVE-bookend"
    elif first["mode"] == "0xa2":
        invocation = "PUBLISH-header"
    elif first["mode"] == "0xa3":
        invocation = "ROLLBACK-or-pre-publish-fence"
    elif first["mode"] == "0xa4":
        invocation = "CLEAR-bookend"
    else:
        invocation = "invalid-mode"
    value = {
        "format": "lisp65-c2.2-Link64-slot39-threshold-hardware-v1",
        "recorded_on": "2026-07-25",
        "status": "completed-Link64-threshold-witness",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_SCRIPT),
            "PC_captures": bind(PC_CAPTURE),
            "capture_timing": bind(HW_OUT / "capture-times.json"),
        },
        "answer": {
            "invocation": invocation,
            "mode": first["mode"],
            "producer_seal": first["producer_seal"],
            "target_C2J_crc16": first["target_C2J_crc16"],
            "seal_matches_target":
                first["producer_seal"] == first["target_C2J_crc16"],
            "journal_result": first["journal_result"],
            "PCs": [row["PC"] for row in pc_rows],
            "external_elapsed_frames": [
                row["external_elapsed_frames"] for row in captures],
        },
        "captures": captures,
        "stable_witnesses": {
            name: {
                "byteidentical_across_three": True,
                "sha256": sha_bytes(values[0]),
            } for name, values in stable.items()
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "diagnostic_hardware_runs": 1,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": load_json(PATCH_RECEIPT)["claim_limit"],
    }
    write_json(HARDWARE_RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "capture-pc", "evaluate"))
    args = parser.parse_args()
    value = {
        "prepare": prepare, "verify": verify,
        "capture-pc": capture_pc, "evaluate": evaluate,
    }[args.action]()
    print(
        "c2-link64-slot39-threshold-hold: "
        + str(value.get("status", "ok")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HoldError, R.OverlayBankError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link64-slot39-threshold-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
