#!/usr/bin/env python3
"""Capture Link 75's diagnostics-first symbol-read completion session.

Both diagnostic identities are nonpromotable.  Stage 0 holds immediately
after symname returns.  Stage 1 exercises homogeneous and real-shape mixed
DMA traffic before the canonical require/defstruct retry is allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import c2_defstruct_link69_hw as DEFSTRUCT  # noqa: E402
import c2_link75_dirmiss_detail_hold_hw as MEMORY  # noqa: E402
import c2_symbol_read_completion_inventory as INVENTORY  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


BASE = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/"
    "bundled-completion-session")
OUT = BASE / "hardware-symbol-read-session-v2"
STATE = OUT / "session-state.json"
STAGE0_CAPTURE = OUT / "post-symname-capture.json"
STAGE0_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-post-symname-hardware-v2-receipt.json")
DMA_CAPTURE_FIRST_RED = OUT / "dma-capture.json"
DMA_CAPTURE = OUT / "dma-capture-safe-trigger.json"
DMA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-hardware-receipt.json")
PRECHECK_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-precondition-harness-first-red.json")
TRIGGER_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-trigger-harness-first-red.json")
MEDIA_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-media-upload-harness-first-red.json")

SESSION_CONFIG = ROOT / "config/c2.2-link75-bundled-completion-session.json"
INVESTIGATION = ROOT / "config/c2-symbol-read-completion-investigation.json"
STAGE0_DEPLOYMENT = BASE / (
    "post-symname-hold-NONPROMOTABLE/deployment.json")
STAGE1_DIR = BASE / "symbol-read-completion-probe-v2-NONPROMOTABLE"
STAGE1_DEPLOYMENT = STAGE1_DIR / "deployment.json"
STAGE1_PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-symbol-read-completion-probe-preparation-receipt.json")
PRODUCT_DEPLOYMENT = (
    BASE / "library-media-successor/product-phase-deployment.json")
RESET_SUCCESSOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-reset-domain-successor-receipt.json")
MEDIA_SUCCESSOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-library-media-successor-receipt.json")
RESET_READBACK = OUT / "canonical-deployment/readback-c2d-v6-reset-domain.bin"
RESET_C2J_READBACK = OUT / "canonical-deployment/readback-zero-c2j.bin"
MEDIA_READBACK = OUT / "uploaded-media-readback.d81"
PRODUCT_OBSERVATIONS = OUT / "canonical-retry-observations.json"
PRODUCT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-require-defstruct-retry-hardware-receipt.json")
DEFSTRUCT_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-defstruct-red-frame-hardware-first-red.json")
DEFSTRUCT_DECISION = ROOT / (
    "docs/planning/c2.2-link75-defstruct-red-frame-owner-decision.md")
DEFSTRUCT_PARK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-defstruct-park-owner-decision-receipt.json")

STAGE0_PC = 0xC472
STAGE0_SCRATCH = 0xC1F6
STAGE0_SCRATCH_BYTES = 34
STAGE0_EXPECTED = b"intern-renderer-missing"
STAGE1_PC = 0xC7C7
TRACE_ADDRESS = 0xC0C6
TRACE_BYTES = 304
WITNESS_ADDRESS = 0xC7D1
WITNESS_BYTES = 96
PHASE_OWNER_ADDRESS = 0x0089
C2J_OFFSET = 0xC640
C2J_BYTES = 64
PUBLISHED_C2D_END = 0x8430
SCRATCH_BYTES = 64
BANK5_BYTES = 65536
PROBE_COMPLETE = 0xA5


class HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HardwareError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_once(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"one-shot evidence already exists: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    write_once(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii"),
    )


def replace_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
        "ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def verify_deployment(path: Path) -> dict[str, Any]:
    value = load(path)
    require(value["promotable"] is False, "diagnostic became promotable")
    for row in [value["product"], *value["preloads"]]:
        artifact = ROOT / row["path"]
        require(
            artifact.stat().st_size == row["bytes"]
            and sha(artifact) == row["sha256"],
            f"deployment artifact drift: {artifact}",
        )
    return value


def authority() -> tuple[dict[str, Any], dict[str, Any]]:
    session = load(SESSION_CONFIG)
    investigation = load(INVESTIGATION)
    media_successor = load(MEDIA_SUCCESSOR_RECEIPT)
    stage0 = verify_deployment(STAGE0_DEPLOYMENT)
    stage1 = verify_deployment(STAGE1_DEPLOYMENT)
    product = load(PRODUCT_DEPLOYMENT)
    for row in [product["product"], *product["preloads"], product["media"]]:
        artifact = ROOT / row["path"]
        require(
            artifact.stat().st_size == row["bytes"]
            and sha(artifact) == row["sha256"],
            f"canonical deployment artifact drift: {artifact}",
        )
    preparation = load(STAGE1_PREPARATION)
    require(
        session["format"]
            == "lisp65-c2.2-link75-bundled-completion-session-v2"
        and session["policy"]["product_before_diagnostics"] is False
        and investigation["format"]
            == "lisp65-c2-symbol-read-completion-investigation-v2"
        and preparation["status"]
            == "passed-nonpromotable-single-paired-mixed-DMA-probe-prepared"
        and stage0["rows"][0]["id"] == "post-symname-return-hold"
        and stage1["rows"][0]["id"] == "symbol-read-completion-probe"
        and product["status"]
            == "ready-product-phase-after-library-envelope-rebind"
        and media_successor["status"]
            == "passed-Link75-product-bound-SESS-media-no-product-link"
        and product["cold_reset_contract"]["c2j"] == [50752, 50816],
        "diagnostics-first session authority drift",
    )
    return stage0, stage1


def initialize() -> dict[str, Any]:
    authority()
    require(
        not any(path.exists() for path in (
            STATE, STAGE0_CAPTURE, STAGE0_RECEIPT,
            DMA_CAPTURE_FIRST_RED, DMA_CAPTURE, DMA_RECEIPT,
            PRODUCT_OBSERVATIONS, PRODUCT_RECEIPT)),
        "diagnostics-first hardware evidence already exists",
    )
    value = {
        "format":
            "lisp65-c2.2-link75-symbol-read-hardware-session-state-v2",
        "recorded_on": "2026-07-28",
        "status": "initialized-awaiting-post-symname-deploy",
        "order": [
            "post-symname-hold",
            "DMA-single-paired-mixed",
            "canonical-require-retry",
        ],
        "authority": {
            "session": bind(SESSION_CONFIG),
            "investigation": bind(INVESTIGATION),
            "stage0": bind(STAGE0_DEPLOYMENT),
            "stage1": bind(STAGE1_DEPLOYMENT),
            "stage1_preparation": bind(STAGE1_PREPARATION),
        },
    }
    replace_json(STATE, value)
    return {"status": value["status"]}


def state(expected: str) -> dict[str, Any]:
    value = load(STATE)
    require(value["status"] == expected,
            f"hardware session order drift: {value['status']} != {expected}")
    return value


def command(fd: int, value: bytes, wait: float = 0.03) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def read_registers(fd: int, expected_pc: int) -> dict[str, Any]:
    raw = command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw,
    )
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == expected_pc,
            f"expected hold PC 0x{expected_pc:04x}, got 0x{pc:04x}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width)
        in enumerate(zip(names, widths), 1)
    }


def capture_post_symname() -> dict[str, Any]:
    session = state("initialized-awaiting-post-symname-deploy")
    require(not STAGE0_CAPTURE.exists(), "post-symname capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c275postsymv2\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd, STAGE0_PC)
        rows = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            scratch = MEMORY.read_block(
                fd, STAGE0_SCRATCH, STAGE0_SCRATCH_BYTES)
            patch = MEMORY.read_block(fd, STAGE0_PC, 2)
            rows.append({
                "index": index,
                "scratch_hex": scratch.hex(),
                "scratch_name": scratch.split(b"\0", 1)[0].decode(
                    "ascii", errors="replace"),
                "matches_expected":
                    scratch.startswith(STAGE0_EXPECTED + b"\0"),
                "live_patch_hex": patch.hex(),
            })
    finally:
        os.close(fd)
    require(
        all(row["live_patch_hex"] == "80fe" for row in rows),
        "live post-symname patch drift",
    )
    stable = [
        (row["scratch_hex"], row["live_patch_hex"]) for row in rows]
    require(all(row == stable[0] for row in stable[1:]),
            "post-symname capture changed across time")
    scratch_matches = all(row["matches_expected"] for row in rows)
    outcome = (
        "R-post-symname-scratch-correct-renderer-consumption"
        if scratch_matches else
        "S-post-symname-scratch-damaged-reader-interval")
    capture = {
        "format": "lisp65-c2.2-link75-post-symname-capture-v2",
        "recorded_on": "2026-07-28",
        "status": "completed-stable-three-capture-post-symname-hold",
        "promotable": False,
        "registers": registers,
        "captures": rows,
        "outcome": outcome,
        "DMA_stage_required_independently": True,
        "CPU_left_stopped": True,
    }
    write_json_once(STAGE0_CAPTURE, capture)
    receipt = {
        "format": "lisp65-c2.2-link75-post-symname-hardware-v2",
        "recorded_on": "2026-07-28",
        "status": outcome,
        "promotable": False,
        "deployment": bind(STAGE0_DEPLOYMENT),
        "capture": bind(STAGE0_CAPTURE),
        "next_gate": "unconditional DMA single/paired/mixed stage",
        "execution_accounting": {
            "physical_device_sessions": 1,
            "diagnostic_deployments": 1,
            "new_product_links": 0,
        },
        "claim_limit": "Post-symname boundary only; no product-fix claim.",
    }
    write_json_once(STAGE0_RECEIPT, receipt)
    session["status"] = "post-symname-complete-awaiting-DMA-precheck"
    session["post_symname"] = {
        "outcome": outcome,
        "capture": bind(STAGE0_CAPTURE),
    }
    replace_json(STATE, session)
    return {"status": outcome, "captures": len(rows)}


def precheck_dma() -> dict[str, Any]:
    session = state("post-symname-complete-awaiting-DMA-precheck")
    phase_owner = OUT / "dma-phase-owner-before-safe-trigger.bin"
    bank5 = OUT / "dma-bank5-before-safe-trigger.bin"
    require(
        phase_owner.read_bytes() == b"\0",
        "phase owner is not NONE before DMA probe")
    before = bank5.read_bytes()
    require(len(before) == BANK5_BYTES, "Bank-5 precheck width drift")
    require(before[:2] == b"C2", "live C2D magic is not C2")
    require(
        before[C2J_OFFSET:C2J_OFFSET + C2J_BYTES]
            == bytes(C2J_BYTES),
        "C2J is not CLEAR before DMA probe",
    )
    session["status"] = "DMA-prechecked-awaiting-trigger"
    session["DMA_precheck"] = {
        "phase_owner": bind(phase_owner),
        "bank5_before": bind(bank5),
        "published_c2d_end": f"0x{PUBLISHED_C2D_END:04x}",
        "C2J": "CLEAR",
    }
    replace_json(STATE, session)
    return {"status": session["status"], "C2J": "CLEAR"}


def capture_dma() -> dict[str, Any]:
    session = state("DMA-prechecked-awaiting-trigger")
    require(not DMA_CAPTURE.exists(), "DMA capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    raw_rows: list[tuple[bytes, bytes]] = []
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c275dmav2\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd, STAGE1_PC)
        for delay in (0, 1, 4):
            if delay:
                time.sleep(delay)
            raw_rows.append((
                MEMORY.read_block(fd, TRACE_ADDRESS, TRACE_BYTES),
                MEMORY.read_block(fd, WITNESS_ADDRESS, WITNESS_BYTES),
            ))
    finally:
        os.close(fd)
    require(
        all(row == raw_rows[0] for row in raw_rows[1:]),
        "DMA trace/witness changed across captures",
    )
    trace_path = OUT / "dma-trace-safe-trigger.bin"
    witness_path = OUT / "dma-witness-safe-trigger.bin"
    write_once(trace_path, raw_rows[0][0])
    write_once(witness_path, raw_rows[0][1])
    trace = raw_rows[0][0]
    require(
        trace[:4] == b"SRD2" and trace[4] == 2
        and trace[5] == PROBE_COMPLETE and trace[6] == 3,
        "DMA probe did not reach its complete hold",
    )
    capture = {
        "format": "lisp65-c2.2-link75-symbol-read-DMA-capture-v1",
        "recorded_on": "2026-07-28",
        "status": "captured-stable-three-times-pending-Bank5-adjudication",
        "promotable": False,
        "registers": registers,
        "capture_intervals_seconds": [0, 1, 5],
        "trace": bind(trace_path),
        "witness": bind(witness_path),
        "CPU_left_stopped": True,
    }
    write_json_once(DMA_CAPTURE, capture)
    session["status"] = "DMA-captured-awaiting-Bank5-after"
    session["DMA_capture"] = bind(DMA_CAPTURE)
    replace_json(STATE, session)
    return {"status": capture["status"], "captures": 3}


def u16(value: bytes, offset: int) -> int:
    return struct.unpack_from("<H", value, offset)[0]


def bitmap(value: bytes) -> tuple[int, ...]:
    require(len(value) == 32, "bitmap width drift")
    return tuple(
        index for index in range(256)
        if value[index >> 3] & (1 << (index & 7)))


def parse_measurement(
        trace: bytes, witness: bytes) -> tuple[
            dict[str, Any],
            tuple[tuple[tuple[int, ...], ...], ...],
            tuple[int, int, int]]:
    require(
        len(trace) == TRACE_BYTES and len(witness) == WITNESS_BYTES,
        "DMA capture width drift",
    )
    # llvm-mos target layout is align=1.  The trace's five reserved bytes
    # occupy offsets 11..15; its three bitmap families start at 16/112/208.
    prim_base = 16
    roundtrip_base = prim_base + 3 * 32
    cell_base = roundtrip_base + 3 * 32
    batches = tuple(
        (
            bitmap(trace[prim_base + batch * 32:
                         prim_base + (batch + 1) * 32]),
            bitmap(trace[roundtrip_base + batch * 32:
                         roundtrip_base + (batch + 1) * 32]),
            bitmap(trace[cell_base + batch * 32:
                         cell_base + (batch + 1) * 32]),
        )
        for batch in range(3)
    )
    hashes = tuple(u16(witness, 12 + 2 * batch) for batch in range(3))
    parsed = {
        "trace": {
            "magic": trace[:4].decode("ascii"),
            "version": trace[4],
            "status": f"0x{trace[5]:02x}",
            "completed_batches": trace[6],
            "first_failure": {
                "step": trace[7],
                "batch": trace[8],
                "iteration": trace[9],
                "byte": trace[10],
                "expected": f"0x{u16(witness, 0):04x}",
                "observed": f"0x{u16(witness, 2):04x}",
            },
            "failure_iterations": [
                {
                    "batch": index,
                    "Prim67": list(row[0]),
                    "record_roundtrip": list(row[1]),
                    "cell_word": list(row[2]),
                }
                for index, row in enumerate(batches)
            ],
        },
        "witness": {
            "single_immediate_hex": witness[18:20].hex(),
            "single_settled_hex": witness[20:22].hex(),
            "paired_first_hex": witness[22:24].hex(),
            "paired_second_hex": witness[24:26].hex(),
            "single_immediate_mismatches": u16(witness, 4),
            "single_settled_mismatches": u16(witness, 6),
            "paired_first_mismatches": u16(witness, 8),
            "paired_second_mismatches": u16(witness, 10),
            "observation_hashes": [
                f"0x{value:04x}" for value in hashes],
            "cell_word": f"0x{u16(witness, 94):04x}",
            "first_expected": f"0x{u16(witness, 0):04x}",
            "first_observed": f"0x{u16(witness, 2):04x}",
        },
    }
    return parsed, batches, hashes


def decoder_selftest() -> dict[str, Any]:
    trace = bytearray(TRACE_BYTES)
    witness = bytearray(WITNESS_BYTES)
    trace[:7] = b"SRD2" + bytes((2, PROBE_COMPLETE, 3))
    trace[16 + 32 + 1] = 1 << 1       # Prim67 batch 1, iteration 9.
    trace[112 + 64 + 2] = 1 << 1      # Roundtrip batch 2, iteration 17.
    trace[208 + 31] = 1 << 7          # Cell batch 0, iteration 255.
    struct.pack_into("<HHHHHH", witness, 0, 0x1111, 0x2222,
                     3, 2, 1, 4)
    struct.pack_into("<HHH", witness, 12, 0x3301, 0x3302, 0x3303)
    witness[18:26] = bytes.fromhex("4332433243324332")
    struct.pack_into("<H", witness, 94, 0x0060)
    parsed, batches, hashes = parse_measurement(bytes(trace), bytes(witness))
    require(
        batches == (
            ((), (), (255,)),
            ((9,), (), ()),
            ((), (17,), ()))
        and hashes == (0x3301, 0x3302, 0x3303)
        and parsed["witness"]["single_immediate_mismatches"] == 3
        and parsed["witness"]["single_settled_mismatches"] == 2
        and parsed["witness"]["paired_first_mismatches"] == 1
        and parsed["witness"]["paired_second_mismatches"] == 4
        and parsed["witness"]["cell_word"] == "0x0060",
        "target-layout DMA capture decoder selftest failed",
    )
    return {"status": "passed", "assertions": 9}


def finalize_dma() -> dict[str, Any]:
    session = state("DMA-captured-awaiting-Bank5-after")
    capture = load(DMA_CAPTURE)
    before_path = OUT / "dma-bank5-before-safe-trigger.bin"
    after_path = OUT / "dma-bank5-after-safe-trigger.bin"
    before = before_path.read_bytes()
    after = after_path.read_bytes()
    require(
        len(before) == len(after) == BANK5_BYTES,
        "Bank-5 before/after width drift",
    )
    changed = [
        offset for offset, pair in enumerate(zip(before, after))
        if pair[0] != pair[1]]
    allowed = set(range(
        PUBLISHED_C2D_END, PUBLISHED_C2D_END + SCRATCH_BYTES))
    forbidden = [offset for offset in changed if offset not in allowed]
    if forbidden:
        raise HardwareError(
            f"DMA probe changed published byte 0x{forbidden[0]:04x}")
    expected_tail = bytes(
        0xA5 ^ 0xFF ^ ((byte * 3) & 0xFF)
        for byte in range(SCRATCH_BYTES))
    require(
        after[PUBLISHED_C2D_END:PUBLISHED_C2D_END + SCRATCH_BYTES]
            == expected_tail,
        "Bank-5 scratch does not contain the final deterministic seed",
    )
    require(
        after[C2J_OFFSET:C2J_OFFSET + C2J_BYTES] == bytes(C2J_BYTES),
        "DMA probe changed C2J",
    )
    trace = (OUT / "dma-trace-safe-trigger.bin").read_bytes()
    witness = (OUT / "dma-witness-safe-trigger.bin").read_bytes()
    parsed, batches, hashes = parse_measurement(trace, witness)
    post = load(STAGE0_CAPTURE)
    w = parsed["witness"]
    classification = INVENTORY.classify_campaign(
        post_symname_scratch_matches=(
            post["outcome"].startswith("R-")),
        single_immediate_mismatches=w["single_immediate_mismatches"],
        single_settled_mismatches=w["single_settled_mismatches"],
        paired_first_mismatches=w["paired_first_mismatches"],
        paired_second_mismatches=w["paired_second_mismatches"],
        mixed_failure_batches=batches,
        observation_hashes=hashes,
    )
    if classification["mixed"].startswith("M0-"):
        require(hashes[0] == hashes[1] == hashes[2],
                "clean bitmaps carry divergent observation hashes")
    result = {
        "format":
            "lisp65-c2.2-link75-symbol-read-completion-hardware-v1",
        "recorded_on": "2026-07-28",
        "status": "completed-classified-DMA-before-require",
        "promotable": False,
        "classification": classification,
        "measurement": parsed,
        "Bank5_safety": {
            "before": bind(before_path),
            "after": bind(after_path),
            "changed_offsets": [f"0x{x:04x}" for x in changed],
            "changed_bytes": len(changed),
            "allowed_span": "0x8430..0x846f",
            "published_bytes_byteidentical": True,
            "C2J_CLEAR_after": True,
        },
        "evidence": {
            "preparation": bind(STAGE1_PREPARATION),
            "deployment": bind(STAGE1_DEPLOYMENT),
            "post_symname": bind(STAGE0_RECEIPT),
            "capture": bind(DMA_CAPTURE),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "diagnostic_deployments": 2,
            "new_product_links": 0,
            "product_byte_changes": 0,
        },
        "next_gate": "canonical Link75 require/defstruct retry",
        "claim_limit": (
            "Nonpromotable target DMA attribution only; classification does "
            "not itself authorize a product fix."),
    }
    write_json_once(DMA_RECEIPT, result)
    capture["status"] = "completed-classified-DMA-before-require"
    capture["classification"] = classification
    capture["Bank5_after"] = bind(after_path)
    replace_json(DMA_CAPTURE, capture)
    session["status"] = "DMA-classified-awaiting-canonical-require-retry"
    session["DMA_result"] = {
        "classification": classification,
        "receipt": bind(DMA_RECEIPT),
    }
    replace_json(STATE, session)
    return {
        "status": result["status"],
        "classification": classification,
        "changed_bytes": len(changed),
    }


def rebind_clear_fixture() -> dict[str, Any]:
    session = state("post-symname-complete-awaiting-DMA-precheck")
    old_owner = OUT / "dma-phase-owner-before.bin"
    old_bank5 = OUT / "dma-bank5-before.bin"
    before = old_bank5.read_bytes()
    require(
        old_owner.read_bytes() == b"\0"
        and len(before) == BANK5_BYTES
        and before[C2J_OFFSET:C2J_OFFSET + C2J_BYTES] == bytes((0x10,)) * 64
        and not DMA_CAPTURE.exists(),
        "caught precondition First Red is not the observed 64x$10 state",
    )
    receipt = {
        "format":
            "lisp65-c2.2-link75-symbol-read-precondition-harness-first-red-v1",
        "recorded_on": "2026-07-28",
        "status": "FIRST-RED-before-DMA-trigger-C2J-not-CLEAR",
        "finding": (
            "The diagnostic contract required C2J=CLEAR but the deployment "
            "did not establish its 64-byte zero baseline; live bytes were "
            "64 copies of $10 while phase owner was NONE."),
        "classification": "harness-precondition-not-product",
        "trigger_executed": False,
        "evidence": {
            "phase_owner": bind(old_owner),
            "Bank5_before": bind(old_bank5),
            "post_symname": bind(STAGE0_RECEIPT),
        },
        "correction": (
            "Stage-1 deployment now loads and readback-verifies a bound "
            "64-byte zero-C2J fixture before the diagnostic product runs."),
        "execution_accounting": {
            "DMA_rows_run": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Pre-trigger diagnostic harness state only; no product or DMA "
            "completion result."),
    }
    write_json_once(PRECHECK_FIRST_RED, receipt)
    authority()
    session["authority"]["stage1"] = bind(STAGE1_DEPLOYMENT)
    session["authority"]["stage1_preparation"] = bind(STAGE1_PREPARATION)
    session["DMA_precondition_first_red"] = bind(PRECHECK_FIRST_RED)
    replace_json(STATE, session)
    return {
        "status": receipt["status"],
        "trigger_executed": False,
        "next": "controlled Stage-1 redeploy with bound CLEAR fixture",
    }


def rebind_safe_trigger() -> dict[str, Any]:
    session = state("DMA-captured-awaiting-Bank5-after")
    before_path = OUT / "dma-bank5-before-clear.bin"
    after_path = OUT / "dma-bank5-after.bin"
    before = before_path.read_bytes()
    after = after_path.read_bytes()
    changed = [
        offset for offset, pair in enumerate(zip(before, after))
        if pair[0] != pair[1]]
    expected_harness = (
        set(range(PUBLISHED_C2D_END,
                  PUBLISHED_C2D_END + SCRATCH_BYTES))
        | set(range(0xC4F0, 0xC4F7))
        | set(range(0xE4CC, 0xE4E8))
        | set(range(0xF8C0, 0xF8C2)))
    require(
        len(before) == len(after) == BANK5_BYTES
        and set(changed).issubset(expected_harness)
        and DMA_CAPTURE_FIRST_RED.exists()
        and not DMA_CAPTURE.exists(),
        "caught unsafe-trigger First Red does not match observed spans",
    )
    trace = (OUT / "dma-trace.bin").read_bytes()
    witness = (OUT / "dma-witness.bin").read_bytes()
    parsed, batches, hashes = parse_measurement(trace, witness)
    require(
        not any(bitmap_row for batch in batches for bitmap_row in batch)
        and hashes[0] == hashes[1] == hashes[2],
        "unsafe-trigger capture was not internally clean",
    )
    receipt = {
        "format":
            "lisp65-c2.2-link75-symbol-read-trigger-harness-first-red-v1",
        "recorded_on": "2026-07-28",
        "status": "FIRST-RED-clean-DMA-capture-unsafe-new-symbol-trigger",
        "finding": (
            "The unknown symbol used to enter the diagnostic overlay was "
            "interned by the REPL compiler, changing namepool/nameoff plus "
            "transient emitter-root workspace outside the probe-owned span."),
        "classification": "harness-trigger-not-product-or-DMA",
        "captured_measurement_not_claimed": {
            "all_failure_bitmaps_zero": True,
            "observation_hashes": [
                f"0x{value:04x}" for value in hashes],
            "reason": (
                "The accepted safety contract forbids persistent trigger "
                "side effects even when the probe observations are clean."),
        },
        "changed_offsets": [f"0x{x:04x}" for x in changed],
        "evidence": {
            "before": bind(before_path),
            "after": bind(after_path),
            "capture": bind(DMA_CAPTURE_FIRST_RED),
        },
        "correction": (
            "Use (intern): an already-interned primitive with deliberately "
            "wrong arity enters the same error overlay without creating a "
            "diagnostic symbol or literal root."),
        "execution_accounting": {
            "DMA_rows_claimed": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Harness-trigger First Red only; the clean observations are not "
            "promoted as the DMA result."),
    }
    write_json_once(TRIGGER_FIRST_RED, receipt)
    authority()
    session["authority"]["stage1"] = bind(STAGE1_DEPLOYMENT)
    session["authority"]["stage1_preparation"] = bind(STAGE1_PREPARATION)
    session["DMA_trigger_first_red"] = bind(TRIGGER_FIRST_RED)
    session["status"] = "post-symname-complete-awaiting-DMA-precheck"
    replace_json(STATE, session)
    return {
        "status": receipt["status"],
        "measurement_claimed": False,
        "next": "controlled Stage-1 redeploy with existing-primitive trigger",
    }


def mark_retry_ready() -> dict[str, Any]:
    session = load(STATE)
    require(
        session["status"] in (
            "DMA-classified-awaiting-canonical-require-retry",
            "canonical-deployed-awaiting-Freezer-mount",
        ),
        "canonical retry state cannot accept reset-domain successor",
    )
    deployment = load(PRODUCT_DEPLOYMENT)
    reset_rows = [
        row for row in deployment["preloads"]
        if row["role"] == "c2d-v6-complete-reset-domain"
    ]
    media = ROOT / deployment["media"]["path"]
    require(
        len(reset_rows) == 1
        and RESET_READBACK.read_bytes()
            == (ROOT / reset_rows[0]["path"]).read_bytes()
        and RESET_C2J_READBACK.read_bytes() == bytes(64)
        and MEDIA_READBACK.read_bytes() == media.read_bytes(),
        "canonical reset-domain/media readback is not qualified",
    )
    session["authority"]["reset_domain_successor"] = bind(
        RESET_SUCCESSOR_RECEIPT)
    session["authority"]["library_media_successor"] = bind(
        MEDIA_SUCCESSOR_RECEIPT)
    session["reset_domain_precondition"] = {
        "full_readback": bind(RESET_READBACK),
        "c2j_zero_readback": bind(RESET_C2J_READBACK),
        "status": "passed-before-product-release",
    }
    session["library_media_precondition"] = {
        "upload_readback": bind(MEDIA_READBACK),
        "deployment": bind(PRODUCT_DEPLOYMENT),
        "status": "passed-Link75-product-bound-SESS-before-retry",
    }
    session["status"] = "canonical-deployed-awaiting-Freezer-mount"
    replace_json(STATE, session)
    return {"status": session["status"]}


def record_media_timeout() -> dict[str, Any]:
    session = state("DMA-classified-awaiting-canonical-require-retry")
    log = OUT / "media-upload.log"
    readback = OUT / "uploaded-media-readback.d81"
    require(
        log.is_file() and log.stat().st_size == 0 and not readback.exists(),
        "media timeout evidence does not match the observed no-progress state",
    )
    receipt = {
        "format":
            "lisp65-c2.2-link75-media-upload-harness-first-red-v1",
        "recorded_on": "2026-07-28",
        "status": "FIRST-RED-FTP-no-progress-from-stopped-diagnostic",
        "finding": (
            "mega65_ftp installed its fast-access routine while the target "
            "was stopped in the SEI diagnostic hold, then produced no byte "
            "of log or readback before the bound 360-second timeout."),
        "classification": "hardware-tool-context-not-product",
        "correction": (
            "Reset/load the canonical PRG first, then repeat the same D81 "
            "put/get and byte comparison before the full canonical deploy."),
        "evidence": {
            "empty_log": bind(log),
            "session": bind(STATE),
            "DMA": bind(DMA_RECEIPT),
        },
        "execution_accounting": {
            "media_uploads_completed": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": "FTP harness context only; no media or product result.",
    }
    write_json_once(MEDIA_FIRST_RED, receipt)
    session["media_upload_first_red"] = bind(MEDIA_FIRST_RED)
    replace_json(STATE, session)
    return {"status": receipt["status"], "readback_bytes": 0}


def record_retry(row_id: str, screen: Path) -> dict[str, Any]:
    session = load(STATE)
    require(
        session["status"] in (
            "canonical-deployed-awaiting-Freezer-mount",
            "canonical-retry-in-progress"),
        "canonical retry is not authorized yet",
    )
    deployment = load(PRODUCT_DEPLOYMENT)
    rows = deployment["rows"][2:]
    observations = (
        load(PRODUCT_OBSERVATIONS)
        if PRODUCT_OBSERVATIONS.exists()
        else {
            "format":
                "lisp65-c2.2-link75-require-defstruct-retry-observations-v1",
            "status": "hardware-in-progress",
            "rows": [],
        })
    position = len(observations["rows"])
    require(position < len(rows), "all canonical retry rows are recorded")
    expected = rows[position]
    require(row_id == expected["id"], "canonical retry row order drift")
    if not screen.is_absolute():
        screen = ROOT / screen
    try:
        SCREEN.check_latest_result(
            screen, expected["form"], expected["expect"])
    except SCREEN.CheckError as error:
        raise HardwareError(
            f"canonical retry First Red at {row_id}: {error.message}") from error
    observations["rows"].append({
        **expected,
        "screen": bind(screen),
        "status": "passed-exact-screen-result",
    })
    observations["status"] = (
        "hardware-complete-pending-finalize"
        if len(observations["rows"]) == len(rows)
        else "hardware-in-progress")
    replace_json(PRODUCT_OBSERVATIONS, observations)
    session["status"] = "canonical-retry-in-progress"
    replace_json(STATE, session)
    return {
        "status": "passed",
        "id": row_id,
        "position": position + 1,
        "total": len(rows),
    }


def record_defstruct_red_frame() -> dict[str, Any]:
    session = state("canonical-retry-in-progress")
    observations = load(PRODUCT_OBSERVATIONS)
    require(
        [row["id"] for row in observations["rows"]]
            == ["require-first", "require-repeat"],
        "defstruct First Red did not follow the two accepted require rows",
    )
    image = OUT / "retry-define-point.png"
    text = OUT / "retry-define-point.txt"
    try:
        SCREEN.check_fail_closed_frame(image)
    except SCREEN.CheckError as error:
        require(
            error.code == SCREEN.FAIL_CLOSED_FRAME,
            f"defstruct screenshot is not a fail-closed frame: {error}",
        )
    else:
        raise HardwareError("defstruct screenshot lacks the red frame")
    SCREEN.check_active_input(text, "(defstruct point x y)")
    dma = load(DMA_RECEIPT)
    require(
        dma["classification"]["homogeneous"]
            == "C-homogeneous-lanes-stable"
        and dma["classification"]["mixed"]
            == "M0-mixed-sequence-stable"
        and dma["classification"]["fix_class"]
            == "no-reproduction-no-fix",
        "defstruct disposition tried to reopen a nonfailing DMA result",
    )
    receipt = {
        "format":
            "lisp65-c2.2-link75-defstruct-red-frame-first-red-v1",
        "recorded_on": "2026-07-28",
        "status":
            "FIRST-RED-defstruct-fail-closed-owner-disposition-required",
        "hardware": {
            "accepted_rows": observations["rows"],
            "failing_form": "(defstruct point x y)",
            "visible_result": None,
            "trailing_prompt": False,
            "red_fail_closed_frame": True,
            "screen": bind(image),
            "screen_text": bind(text),
        },
        "closed_preconditions": {
            "library_media":
                session["library_media_precondition"],
            "DMA": {
                "receipt": bind(DMA_RECEIPT),
                "homogeneous": "stable",
                "mixed": "stable",
                "classification": "no-reproduction-no-fix",
            },
            "require_first": "t",
            "require_repeat": "t",
        },
        "classification": (
            "new defstruct-expansion fail-closed First Red; not the repaired "
            "compiler-carrier failure, not the stale L65S envelope, and not "
            "a reproduced small-read DMA failure"
        ),
        "disposition_boundary": {
            "no_more_pre_measurement_hypotheses": True,
            "DMA_rerun_authorized": False,
            "automatic_retry_authorized": False,
            "product_or_library_fix_authorized": False,
            "next":
                "owner chooses park-defstruct or separately commissions a "
                "new bounded defstruct-expansion investigation",
        },
        "execution_accounting": {
            "new_product_links": 0,
            "product_bytes_changed": 0,
            "defstruct_results_claimed": 0,
        },
        "claim_limit": (
            "The two require rows are hardware-proven. No defstruct surface "
            "or cause is claimed from this First Red."
        ),
    }
    write_json_once(DEFSTRUCT_FIRST_RED, receipt)
    session["status"] = "FIRST-RED-defstruct-owner-disposition-required"
    session["defstruct_first_red"] = bind(DEFSTRUCT_FIRST_RED)
    replace_json(STATE, session)
    return {"status": receipt["status"]}


def record_defstruct_park() -> dict[str, Any]:
    session = state("FIRST-RED-defstruct-owner-disposition-required")
    first_red = load(DEFSTRUCT_FIRST_RED)
    decision = DEFSTRUCT_DECISION.read_text(encoding="utf-8")
    require(
        first_red["status"]
            == "FIRST-RED-defstruct-fail-closed-owner-disposition-required"
        and "Owner decision (2026-07-28): **Option A" in decision
        and "R-1." in decision
        and "R-2." in decision
        and "R-3." in decision,
        "defstruct park decision/restart package is incomplete",
    )
    receipt = {
        "format":
            "lisp65-c2.2-link75-defstruct-owner-park-decision-v1",
        "recorded_on": "2026-07-28",
        "status": "closed-defstruct-parked-no-further-runs",
        "owner_decision": "Option A",
        "effect": {
            "defstruct_active_1_2_x_freight": False,
            "require_foundation_hardware_proven": True,
            "released_v1_2_0_changed": False,
            "product_bytes_changed": 0,
            "new_product_links": 0,
            "additional_hardware_runs_authorized": 0,
        },
        "restart": {
            "requires_new_explicit_commission": True,
            "package": bind(DEFSTRUCT_DECISION),
            "entries": [
                "R-1-unmasked-interrupt-source-gap",
                "R-2-require-latency-attribution",
                "R-3-read-and-attribute-before-hypotheses",
            ],
        },
        "evidence": {
            "First_Red": bind(DEFSTRUCT_FIRST_RED),
            "DMA": bind(DMA_RECEIPT),
            "library_media": bind(MEDIA_SUCCESSOR_RECEIPT),
            "accepted_observations": bind(PRODUCT_OBSERVATIONS),
        },
        "claim_limit": (
            "Closes active defstruct freight only. It neither diagnoses the "
            "red frame nor promotes the defstruct library."
        ),
    }
    write_json_once(DEFSTRUCT_PARK_RECEIPT, receipt)
    session["status"] = "closed-defstruct-parked"
    session["defstruct_owner_decision"] = bind(DEFSTRUCT_PARK_RECEIPT)
    replace_json(STATE, session)
    return {"status": receipt["status"]}


def compare_repeat(name: str) -> dict[str, Any]:
    before_path = OUT / f"{name}-before-bank5.bin"
    after_path = OUT / f"{name}-after-bank5.bin"
    before = before_path.read_bytes()
    after = after_path.read_bytes()
    require(
        len(before) == len(after) == BANK5_BYTES,
        f"require repeat capture width drift: {name}",
    )
    before_cells = DEFSTRUCT.require_transient_cells(before)
    after_cells = DEFSTRUCT.require_transient_cells(after)
    require(before_cells == after_cells,
            f"resolver cell coordinates drift: {name}")
    allowed = {
        offset + byte
        for _, offset in before_cells.values()
        for byte in range(2)
    }
    changed = [
        offset for offset, pair in enumerate(zip(before, after))
        if pair[0] != pair[1]]
    forbidden = [offset for offset in changed if offset not in allowed]
    require(not forbidden,
            f"require repeat changed contracted byte 0x{forbidden[0]:04x}")
    return {
        "id": name,
        "before": bind(before_path),
        "after": bind(after_path),
        "changed_offsets": [f"0x{x:04x}" for x in changed],
        "contracted_immutable_bytes": len(before) - len(allowed),
        "status": "passed-generation-idempotence-no-product-state-drift",
    }


def finalize_retry() -> dict[str, Any]:
    session = state("canonical-retry-in-progress")
    deployment = load(PRODUCT_DEPLOYMENT)
    observations = load(PRODUCT_OBSERVATIONS)
    expected_ids = [row["id"] for row in deployment["rows"][2:]]
    require(
        [row["id"] for row in observations["rows"]] == expected_ids,
        "canonical retry rows are incomplete",
    )
    repeats = [
        compare_repeat("first-repeat"),
        compare_repeat("post-use-repeat"),
    ]
    receipt = {
        "format":
            "lisp65-c2.2-link75-require-defstruct-retry-hardware-v1",
        "recorded_on": "2026-07-28",
        "status": "passed-Link75-require-defstruct-after-DMA-attribution",
        "candidate": {
            "link": 75,
            "product": deployment["product"],
            "ELF": deployment["elf"],
            "media": deployment["media"],
        },
        "results": {
            "rows": observations["rows"],
            "require_idempotence": repeats,
            "defstruct": {
                "definition": "t",
                "constructor": "(point 3 4)",
                "accessors": [3, 4],
                "predicate": "t",
                "functional_update": "(point 3 8)",
                "canonical_place_mutation": "(point 9 4)",
            },
        },
        "evidence": {
            "session": bind(STATE),
            "DMA": bind(DMA_RECEIPT),
            "deployment": bind(PRODUCT_DEPLOYMENT),
            "observations": bind(PRODUCT_OBSERVATIONS),
        },
        "execution_accounting": {
            "physical_device_sessions": 1,
            "diagnostic_deployments": 2,
            "canonical_deployments": 1,
            "new_product_links": 0,
        },
        "claim_limit": (
            "Link75 require/defstruct retry after the independently "
            "classified DMA measurement; no new product identity."),
    }
    write_json_once(PRODUCT_RECEIPT, receipt)
    session["status"] = "complete"
    session["canonical_retry"] = bind(PRODUCT_RECEIPT)
    replace_json(STATE, session)
    return {
        "status": receipt["status"],
        "rows": len(observations["rows"]),
    }


def verify() -> dict[str, Any]:
    stage0, stage1 = authority()
    return {
        "status": "verified-ready-diagnostics-first",
        "stage0_product": stage0["product"]["sha256"],
        "stage1_product": stage1["product"]["sha256"],
        "stage1_iterations": stage1["rows"][0]["iterations_per_batch"],
        "stage1_batches": stage1["rows"][0]["batches"],
        "capture_decoder": decoder_selftest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "verify", "initialize", "capture-post-symname",
        "precheck-DMA", "capture-DMA", "finalize-DMA",
        "rebind-clear-fixture", "rebind-safe-trigger",
        "record-media-timeout", "mark-retry-ready",
        "record-retry", "record-defstruct-red-frame",
        "record-defstruct-park", "finalize-retry"))
    parser.add_argument("--id")
    parser.add_argument("--screen", type=Path)
    args = parser.parse_args()
    actions = {
        "verify": verify,
        "initialize": initialize,
        "capture-post-symname": capture_post_symname,
        "precheck-DMA": precheck_dma,
        "capture-DMA": capture_dma,
        "finalize-DMA": finalize_dma,
        "rebind-clear-fixture": rebind_clear_fixture,
        "rebind-safe-trigger": rebind_safe_trigger,
        "record-media-timeout": record_media_timeout,
        "mark-retry-ready": mark_retry_ready,
        "record-defstruct-red-frame": record_defstruct_red_frame,
        "record-defstruct-park": record_defstruct_park,
    }
    if args.action == "record-retry":
        require(args.id is not None and args.screen is not None,
                "record-retry requires --id and --screen")
        result = record_retry(args.id, args.screen)
    elif args.action == "finalize-retry":
        result = finalize_retry()
    else:
        result = actions[args.action]()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        HardwareError, SERIAL.HoldError, MEMORY.HoldError,
        OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-link75-symbol-read-completion-hw: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
