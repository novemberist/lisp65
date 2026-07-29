#!/usr/bin/env python3
"""Build and evaluate a nonpromotable Link-71 Slot-39 failure-site hold."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import struct
import sys
import termios
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / "build/post-promotion/link71-defstruct-header-crc-domain"
FINAL = BASE / "final"
BASE_CARRIER = FINAL / "runtime-overlays-session-final.bin"
OVERFLOW = FINAL / "runtime-overlays-session-final-region1.bin"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
FIRST_RED = EVIDENCE / (
    "c2.2-link71-place-persistent-append-header-hardware-first-red.json")
OUT = BASE / "slot39-failure-hold-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot39-failure-hold.bin"
MANIFEST = OUT / "manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link71-slot39-failure-hold-nonpromotable-receipt.json")
DEPLOYMENT = OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link71-slot39-failure-hold-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-defstruct-link71-slot39-failure-hold-hw.sh"
PC_CAPTURE = OUT / "pc-captures.json"

DEVICE = "/dev/ttyUSB1"
SLOT = 39
SLOT_VMA = 0xC356
SLOT_FILE_OFFSET = 55040
SLOT_BYTES = 1419
RECORD_ADDRESS = 0xC17C
TRACE_ADDRESS = 0xC1EE
PHASE_SCRATCH_ADDRESS = 0xC0C6
C2J_ADDRESS = 0x0005C640
MAIN_SOURCE_BASE = 0x00030000
OVERFLOW_SOURCE_BASE = 0x0005BD00
SOLVER_VMA = 0xC6C8
SOLVER_BEFORE = bytes.fromhex("0c c4")

# Every branch is an existing error exit in c2_append_header_phase.  Three-byte
# JMPs become BRA $-2 + NOP; the shared two-byte X=ERR_IO fallback becomes
# BRA $-2.  A successful path reaches none of these sites.
SITES: tuple[tuple[str, int, bytes, bytes], ...] = (
    ("null-context", 0xC3AC, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("active-poll", 0xC407, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("clear-poll", 0xC42B, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("publish-finished-precondition", 0xC464, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("pre-publish-rollback-poll", 0xC47F, bytes.fromhex("4c 6b c6"),
     bytes.fromhex("80 fe ea")),
    ("mode-or-state", 0xC55E, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("publish-header-write", 0xC59A, bytes.fromhex("4c 6b c6"),
     bytes.fromhex("80 fe ea")),
    ("publish-header-poll", 0xC5BC, bytes.fromhex("4c 6d c6"),
     bytes.fromhex("80 fe ea")),
    ("direct-stream-error", 0xC66B, bytes.fromhex("a2 01"),
     bytes.fromhex("80 fe")),
)
SITE_BY_PC = {
    pc: name for name, vma, _before, after in SITES
    for pc in (vma, vma + 1 if len(after) == 2 else vma)
}


class HoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HoldError(message)


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(data(path) == value, f"generated artifact differs: {path}")
        return
    path.write_bytes(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def parsed(image: bytes) -> R.ParsedBank:
    build_id = R.HEADER.unpack_from(image)[8]
    return R.validate_region_images(
        image, data(OVERFLOW),
        expected_build_id=build_id,
        expected_vma=SLOT_VMA,
        max_slice_bytes=1792,
        format_version=R.VERSION_V4,
        main_source_base=MAIN_SOURCE_BASE,
        overflow_source_base=OVERFLOW_SOURCE_BASE,
    )


def carrier_offset(vma: int) -> int:
    return SLOT_FILE_OFFSET + vma - SLOT_VMA


def elf_feasibility() -> dict[str, Any]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    symbol = truth.symbol("c2_append_header_phase")
    section = truth.section(symbol.section)
    section_bytes = truth.section_bytes(symbol.section)
    checks: list[dict[str, Any]] = []
    for name, vma, before, after in SITES:
        offset = vma - section.address
        require(section_bytes[offset:offset + len(before)] == before,
                f"ELF failure edge drift: {name}")
        checks.append({
            "name": name,
            "VMA": f"0x{vma:04x}",
            "before": before.hex(),
            "after": after.hex(),
        })
    solver_offset = SOLVER_VMA - section.address
    require(
        section_bytes[solver_offset:solver_offset + 2] == SOLVER_BEFORE,
        "ELF solver bytes drift")
    require(
        symbol.value == 0xC371 and symbol.section == ".lisp65_rt_c2append_header",
        "Link-71 header symbol geometry drift")
    return {
        "symbol": symbol.name,
        "symbol_VMA": f"0x{symbol.value:04x}",
        "section": symbol.section,
        "failure_edges": checks,
        "solver_VMA": f"0x{SOLVER_VMA:04x}",
        "solver_lifetime": (
            "post-success jump operand; unreachable because this diagnostic "
            "holds at every header error exit established by the First Red"),
    }


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = parsed(source)
    row = base.slices[SLOT]
    require(
        row.file_offset == SLOT_FILE_OFFSET
        and row.file_size == SLOT_BYTES
        and row.vma == SLOT_VMA,
        "Link-71 Slot-39 carrier geometry drift")
    result = bytearray(source)
    for name, vma, before, after in SITES:
        offset = carrier_offset(vma)
        require(result[offset:offset + len(before)] == before,
                f"source patch edge drift: {name}")
        result[offset:offset + len(after)] = after
    solver_offset = carrier_offset(SOLVER_VMA)
    require(
        result[solver_offset:solver_offset + 2] == SOLVER_BEFORE,
        "source solver bytes drift")
    result[solver_offset:solver_offset + 2] = solver

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw_record)
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


def solve(source: bytes) -> tuple[bytes, bytes]:
    target = R.crc16_ccitt_false(source)
    baseline = R.crc16_ccitt_false(refresh(source, b"\0\0"))
    columns = [
        R.crc16_ccitt_false(
            refresh(source, (1 << bit).to_bytes(2, "little"))) ^ baseline
        for bit in range(16)
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
    vector, solution = target ^ baseline, 0
    while vector:
        pivot = vector.bit_length() - 1
        require(pivot in basis, "two-byte family CRC solver has no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    solver = solution.to_bytes(2, "little")
    candidate = refresh(source, solver)
    require(
        R.crc16_ccitt_false(candidate) == target,
        "outer Session-family CRC was not restored")
    return solver, candidate


def validate(source: bytes, candidate: bytes) -> dict[str, Any]:
    require(len(source) == len(candidate), "carrier size changed")
    value = parsed(candidate)
    row = value.slices[SLOT]
    for name, vma, before, after in SITES:
        offset = carrier_offset(vma)
        require(
            source[offset:offset + len(before)] == before
            and candidate[offset:offset + len(after)] == after,
            f"failure-site patch identity drift: {name}")
    require(
        R.crc16_ccitt_false(candidate) == R.crc16_ccitt_false(source),
        "Session-family identity changed")
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    mutations = [
        (f"site-{name}", carrier_offset(vma))
        for name, vma, _before, _after in SITES
    ] + [
        ("payload-CRC", record_offset + 20),
        ("record-CRC", record_offset + 22),
        ("directory-CRC", 24),
        ("header-CRC", 26),
        ("family-solver", carrier_offset(SOLVER_VMA)),
    ]
    rejected: list[str] = []
    for name, offset in mutations:
        mutant = bytearray(candidate)
        mutant[offset] ^= 1
        try:
            parsed(bytes(mutant))
            require(
                R.crc16_ccitt_false(bytes(mutant))
                    == R.crc16_ccitt_false(source),
                f"mutation survived: {name}")
        except (HoldError, R.OverlayBankError):
            rejected.append(name)
    require(len(rejected) == len(mutations), "failure-hold mutation survived")
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    return {
        "slot": SLOT,
        "slot_bytes": row.file_size,
        "carrier_bytes_delta": 0,
        "product_bytes_delta": 0,
        "executable_failure_edges": len(SITES),
        "mutation_count": len(rejected),
        "mutations_rejected": rejected,
        "changed_file_offsets": changed,
        "payload_crc16": f"0x{row.crc16:04x}",
        "record_crc16": f"0x{row.record_crc16:04x}",
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
    }


def authority() -> tuple[bytes, dict[str, Any]]:
    source = data(BASE_CARRIER)
    base_deployment = load(BASE_DEPLOYMENT)
    first_red = load(FIRST_RED)
    require(
        first_red["status"].endswith("fails-in-slot39")
        and first_red["results"]["resolver_parser"]["result"] == "t"
        and first_red["results"]["failure_provenance"][
            "primary_slot_decimal"] == SLOT,
        "Link-71 First Red authority drift")
    session = [
        row for row in base_deployment["preloads"]
        if row["role"] == "c2-session-family-region-0"
    ]
    require(
        len(session) == 1
        and session[0]["sha256"] == sha_bytes(source)
        and base_deployment["product"]["sha256"]
            == "969047cb8116bb77510a0b75454053b765f74aedc482de287f3837db9a8a972e",
        "Link-71 deployment authority drift")
    parsed(source)
    return source, base_deployment


def prepare() -> dict[str, Any]:
    source, base_deployment = authority()
    feasibility = elf_feasibility()
    solver, candidate = solve(source)
    gate = validate(source, candidate)
    write(CARRIER, candidate)
    write_json(MANIFEST, {
        "format": "lisp65-Link71-slot39-failure-hold-manifest-v1",
        "status": "ready-nonpromotable-failure-site-hold",
        "promotable": False,
        "source": bind(BASE_CARRIER, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "solver_bytes": solver.hex(),
        "patch_and_rebinding": gate,
    })
    write_json(PATCH_RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot39-failure-hold-patch-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-Slot39-failure-site-discriminator",
        "promotable": False,
        "authority": {
            "hardware_First_Red": bind(FIRST_RED),
            "source_deployment": bind(BASE_DEPLOYMENT),
            "source_carrier": bind(BASE_CARRIER, 0x08000000),
            "source_ELF": bind(ELF),
            "driver": bind(Path(__file__).resolve()),
        },
        "ELF_feasibility": feasibility,
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "patch_and_rebinding": gate,
        "construction": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "all_capacity_deltas": 0,
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-39 failure attribution only; "
            "require/defstruct remains unqualified."),
    })
    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **bind(CARRIER, int(copy["address"], 16)),
                "role": copy["role"],
            }
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "diagnostic carrier replacement is not unique")
    write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot39-failure-hold-deployment-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "media": base_deployment["media"],
        "remote_media": base_deployment["remote_media"],
        "preloads": preloads,
        "test": {
            "form": "(%disk-load-lib 39 1)",
            "capture_intervals_seconds": [0, 1, 5],
            "expected_behavior": "hold at exactly one patched error exit",
        },
        "capture_domains": {
            "completion_record": {
                "address": f"0x{RECORD_ADDRESS:08x}", "bytes": 32},
            "phase_scratch": {
                "address": f"0x{PHASE_SCRATCH_ADDRESS:08x}", "bytes": 304},
            "phase_trace": {
                "address": f"0x{TRACE_ADDRESS:08x}", "bytes": 8},
            "target_C2J": {
                "address": f"0x{C2J_ADDRESS:08x}", "bytes": 64},
            "runtime_slot39": {
                "address": f"0x{SLOT_VMA:08x}", "bytes": SLOT_BYTES},
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-39 failure attribution only."),
    })
    return {
        "status": "ready",
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": gate["family_crc16"],
        "failure_sites": len(SITES),
        "mutations": gate["mutation_count"],
    }


def verify() -> dict[str, Any]:
    source, base_deployment = authority()
    candidate = data(CARRIER)
    gate = validate(source, candidate)
    receipt = load(PATCH_RECEIPT)
    deployment = load(DEPLOYMENT)
    require(
        receipt["candidate"]["carrier"]["sha256"] == sha_bytes(candidate)
        and deployment["product"] == base_deployment["product"]
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware",
        "failure-hold binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"failure-hold preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def serial_read(fd: int, seconds: float) -> bytes:
    result = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select(
            [fd], [], [], min(0.02, max(0.0, deadline - time.monotonic())))
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
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = (
        attrs[2]
        & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE
            | termios.CRTSCTS)
    ) | termios.CS8 | termios.CLOCAL | termios.CREAD
    attrs[4] = attrs[5] = termios.B2000000
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
    token = f"#c271{index:04x}\r".encode()
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
    site = SITE_BY_PC.get(pc)
    require(site is not None, f"PC 0x{pc:04x} is outside failure holds")
    return {
        "index": index,
        "captured_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "PC": f"0x{pc:04x}",
        "site": site,
        "raw_hex": raw.hex(),
    }


def capture_pc() -> dict[str, Any]:
    verify()
    require(not PC_CAPTURE.exists(), "Link-71 PC capture is one-shot")
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
    require(len({row["site"] for row in rows}) == 1,
            "PC moved between failure sites")
    value = {
        "format": "lisp65-Link71-slot39-failure-PC-captures-v1",
        "capture_intervals_seconds": [0, 1, 5],
        "device": DEVICE,
        "rows": rows,
    }
    write_json(PC_CAPTURE, value)
    return value


def evaluate() -> dict[str, Any]:
    verify()
    pc_rows = load(PC_CAPTURE)["rows"]
    require(
        len(pc_rows) == 3
        and len({row["site"] for row in pc_rows}) == 1,
        "failure-site PC evidence drift")
    timing = load(OUT / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "capture timing drift")
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "completion-record", "c2j", "phase-scratch", "trace",
            "runtime-slot39")
    }
    rows: list[dict[str, Any]] = []
    for index in range(1, 4):
        directory = OUT / f"capture-{index}"
        values = {
            "completion-record": data(directory / "completion-record.bin"),
            "c2j": data(directory / "c2j.bin"),
            "phase-scratch": data(directory / "phase-scratch.bin"),
            "trace": data(directory / "trace.bin"),
            "runtime-slot39": data(directory / "runtime-slot39.bin"),
        }
        require(
            len(values["completion-record"]) == 32
            and len(values["c2j"]) == 64
            and len(values["phase-scratch"]) == 304
            and len(values["trace"]) == 8
            and len(values["runtime-slot39"]) == SLOT_BYTES
            and values["trace"][6] == SLOT,
            f"capture {index} geometry or Slot-39 identity drift")
        for name, value in values.items():
            stable[name].append(value)
        record, c2j = values["completion-record"], values["c2j"]
        producer = record[25] | record[26] << 8
        target = R.crc16_ccitt_false(c2j)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "PC": pc_rows[index - 1]["PC"],
            "failure_site": pc_rows[index - 1]["site"],
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches_target": producer == target,
            "completion_record": bind(
                directory / "completion-record.bin", RECORD_ADDRESS),
            "target_C2J": bind(directory / "c2j.bin", C2J_ADDRESS),
            "phase_scratch": bind(
                directory / "phase-scratch.bin", PHASE_SCRATCH_ADDRESS),
            "phase_trace": bind(directory / "trace.bin", TRACE_ADDRESS),
            "runtime_slot39": bind(
                directory / "runtime-slot39.bin", SLOT_VMA),
        })
    require(
        all(values[0] == values[1] == values[2]
            for values in stable.values()),
        "failure-hold witnesses changed across captures")
    screen = data(OUT / "failure-hold-screen.txt").decode(
        "utf-8", errors="replace")
    require(
        "(%disk-load-lib 39 1)" in screen and "*** vm:" not in screen,
        "screen does not establish a pre-unwind failure hold")
    first = rows[0]
    mode_names = {
        "0xa1": "ACTIVE",
        "0xa2": "PUBLISH",
        "0xa3": "ROLLBACK",
        "0xa4": "CLEAR",
    }
    mode = mode_names.get(first["completion_mode"], "INVALID")
    site = first["failure_site"]
    value = {
        "format": "lisp65-c2.2-Link71-slot39-failure-hold-hardware-v1",
        "recorded_on": "2026-07-27",
        "status": "completed-exact-Slot39-failure-site-captured",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "carrier": bind(CARRIER, 0x08000000),
            "hardware_driver": bind(HARDWARE_SCRIPT),
            "capture_evaluator": bind(Path(__file__).resolve()),
            "PC_captures": bind(PC_CAPTURE),
        },
        "answer": {
            "failure_site": site,
            "completion_mode": f"{first['completion_mode']} ({mode})",
            "journal_result": first["journal_result"],
            "producer_seal": first["producer_seal"],
            "target_C2J_crc16": first["target_C2J_crc16"],
            "seal_matches_target": first["seal_matches_target"],
            "verdict": (
                f"the first persistent-library append reaches Slot 39 and "
                f"fails specifically at {site}; record and target witnesses "
                "are frozen before rollback or renderer cleanup"),
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
        },
        "diagnostic_lifecycle": {
            "identity": sha_bytes(data(CARRIER)),
            "eligible_for_promotion": False,
            "state": "discarded-after-capture",
        },
        "claim_limit": (
            "Slot-39 failure-site attribution only; Link 71 remains a "
            "hardware First Red."),
    }
    write_json(HARDWARE_RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "capture-pc", "evaluate"))
    action = parser.parse_args().action
    value = {
        "prepare": prepare,
        "verify": verify,
        "capture-pc": capture_pc,
        "evaluate": evaluate,
    }[action]()
    print(
        "c2-defstruct-link71-slot39-failure-hold: "
        + str(value.get("status", "ok")))
    if action in ("prepare", "verify"):
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        HoldError, R.OverlayBankError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-defstruct-link71-slot39-failure-hold: FIRST RED: "
            + str(error))
        raise SystemExit(2)
