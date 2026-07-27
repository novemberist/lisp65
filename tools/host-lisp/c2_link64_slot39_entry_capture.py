#!/usr/bin/env python3
"""Verify and evaluate the nonpromotable Link-64 Slot-39 entry hold."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_link64_slot39_threshold_hold as H  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/hardware-link64-slot39-entry-hold-NONPROMOTABLE")
DEPLOYMENT = RUN / "deployment.json"
FEASIBILITY = EVIDENCE / (
    "c2.2-link64-slot39-entry-hold-feasibility-receipt.json")
CARRIER = ROOT / (
    "build/c2.2/substitution/link64-slot39-entry-hold-NONPROMOTABLE/"
    "runtime-overlays-session-link64-slot39-entry-hold.bin")
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-entry-hold-hardware-receipt.json")
DRIVER = ROOT / "scripts/c2-link64-slot39-entry-hold-hw.sh"

SLOT = 39
SLOT_VMA = 0xc356
HOLD_VMA = 0xc3a2
PATCH_OFFSET_IN_SLOT = HOLD_VMA - SLOT_VMA
PATCH = bytes.fromhex("d0fe")
RECORD_ADDRESS = 0xc17c
C2J_ADDRESS = 0x0005c640
TRACE_ADDRESS = 0xc1f0


class CaptureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CaptureError(message)


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
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def verify() -> dict[str, Any]:
    deployment = load(DEPLOYMENT)
    feasibility = load(FEASIBILITY)
    require(
        deployment["status"] == "ready-awaiting-separate-hardware-authorization"
        and feasibility["status"] == "ready-nonpromotable-first-entry-hold"
        and deployment["authority"]["feasibility_receipt"]["sha256"]
            == sha_bytes(data(FEASIBILITY))
        and feasibility["candidate"]["carrier"]["sha256"]
            == sha_bytes(data(CARRIER)),
        "entry-hold authority drift")
    parsed = H.parsed(data(CARRIER))
    row = parsed.slices[SLOT]
    require(
        data(CARRIER)[row.file_offset + PATCH_OFFSET_IN_SLOT:
                      row.file_offset + PATCH_OFFSET_IN_SLOT + 2] == PATCH
        and R.crc16_ccitt_false(data(CARRIER)) == 0x472a,
        "entry-hold patch or family identity drift")
    for preload in deployment["preloads"]:
        path = ROOT / preload["path"]
        require(
            len(data(path)) == preload["bytes"]
            and sha_bytes(data(path)) == preload["sha256"],
            f"entry-hold preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha_bytes(data(CARRIER)),
        "family_crc16": "0x472a",
    }


def evaluate() -> dict[str, Any]:
    verify()
    timing = load(RUN / "capture-times.json")
    require(timing["interval_seconds"] == [0, 1, 5],
            "entry-hold timing drift")
    rows: list[dict[str, Any]] = []
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "completion-record", "c2j", "trace", "runtime-slot39")
    }
    for index in range(1, 4):
        directory = RUN / f"capture-{index}"
        record = data(directory / "completion-record.bin")
        c2j = data(directory / "c2j.bin")
        trace = data(directory / "trace.bin")
        slot = data(directory / "runtime-slot39.bin")
        zp = data(directory / "runtime-zp.bin")
        frame = data(directory / "frame.bin")
        require(
            len(record) == 32 and len(c2j) == 64 and len(trace) == 8
            and len(slot) == 1509 and len(zp) == 48 and len(frame) == 5
            and trace[4] == SLOT
            and slot[PATCH_OFFSET_IN_SLOT:
                     PATCH_OFFSET_IN_SLOT + 2] == PATCH,
            f"entry-hold capture {index} geometry or identity drift")
        for name, value in (
                ("completion-record", record), ("c2j", c2j),
                ("trace", trace), ("runtime-slot39", slot)):
            stable[name].append(value)
        producer = record[25] | record[26] << 8
        target = R.crc16_ccitt_false(c2j)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches": producer == target,
            "current_frame":
                f"0x{int.from_bytes(frame[:2], 'little'):04x}",
            "c2_ready": zp[0x8c - 0x70],
            "record": bind(directory / "completion-record.bin",
                           RECORD_ADDRESS),
            "target_C2J": bind(directory / "c2j.bin", C2J_ADDRESS),
            "phase_trace": bind(directory / "trace.bin", TRACE_ADDRESS),
            "runtime_ZP": bind(directory / "runtime-zp.bin", 0x70),
            "frame": bind(directory / "frame.bin", 0xff83),
            "runtime_slot39": bind(directory / "runtime-slot39.bin",
                                   SLOT_VMA),
        })
    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values()),
        "entry-hold authorities changed across captures")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
    mode = record[24]
    result = record[31]
    producer = record[25] | record[26] << 8
    target = R.crc16_ccitt_false(c2j)
    mode_names = {
        0xa1: "ACTIVE",
        0xa2: "PUBLISH",
        0xa3: "ROLLBACK",
        0xa4: "CLEAR",
    }
    result_names = {0: "NONE", 1: "ACTIVE", 2: "PREPARED"}
    require(mode in mode_names and result in result_names,
            "first entry carries an unknown mode or journal result")
    screen = data(RUN / "entry-hold-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm:" not in screen,
        "screen does not establish a pre-error entry hold")

    if mode == 0xa1 and result == 2 and producer == target:
        verdict = (
            "first ACTIVE entry has the required PREPARED result and a "
            "matching C2J seal; the first failure lies after entry "
            "preconditions, inside or after the initial completion poll")
    elif mode == 0xa1:
        verdict = (
            "first ACTIVE entry exposes a precondition/seal divergence "
            "before the completion poll")
    else:
        verdict = (
            "the first Slot-39 invocation is not ACTIVE; the plan/order "
            "contract is already divergent at entry")

    value = {
        "format": "lisp65-c2.2-Link64-slot39-entry-hold-hardware-v1",
        "recorded_on": "2026-07-26",
        "status": "completed-first-Slot39-entry-state-captured",
        "promotable": False,
        "authority": {
            "feasibility_receipt": bind(FEASIBILITY),
            "deployment": bind(DEPLOYMENT),
            "carrier": bind(CARRIER, 0x08000000),
            "hardware_driver": bind(DRIVER),
            "capture_evaluator": bind(Path(__file__)),
        },
        "answer": {
            "first_entry_mode": f"0x{mode:02x} ({mode_names[mode]})",
            "first_entry_journal_result":
                f"{result} ({result_names[result]})",
            "producer_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches": producer == target,
            "verdict": verdict,
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
            "Entry-state attribution only. C1 remains OPEN; no matrix-gate, "
            "acceptance-chain, promotion or release claim."),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-link64-slot39-entry-capture: PASS "
        f"mode={mode_names[mode]} result={result_names[result]} "
        f"seal_match={producer == target}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("verify", "evaluate"))
    args = parser.parse_args()
    value = verify() if args.action == "verify" else evaluate()
    if args.action == "verify":
        print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CaptureError, H.HoldError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link64-slot39-entry-capture: FIRST RED: " + str(error))
        raise SystemExit(2)
