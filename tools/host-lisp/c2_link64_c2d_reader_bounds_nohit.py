#!/usr/bin/env python3
"""Seal the no-hit outcome of the Link-64 C2D-reader bounds holds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_link64_c2d_reader_bounds_hold as D  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-hardware-receipt.json")
OUT = D.HW_OUT
RUNTIME_ZP_ADDRESS = 0x70
RUNTIME_SLOT_ADDRESS = 0xC356
RUNTIME_SLOT_BYTES = 1509


class NoHitError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise NoHitError(message)


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


def main() -> int:
    D.verify()
    timing = load(OUT / "capture-times.json")
    require(
        timing["format"] == "lisp65-Link64-c2d-reader-bounds-nohit-times-v1"
        and timing["interval_seconds"] == [0, 1, 5],
        "no-hit timing authority drift")

    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "reader-code", "completion-record", "c2j", "trace",
            "runtime-zp", "runtime-slot39")
    }
    frames: list[int] = []
    rows: list[dict[str, Any]] = []
    for index in range(1, 4):
        directory = OUT / f"capture-{index}"
        values = {
            "reader-code": data(directory / "reader-code.bin"),
            "completion-record": data(
                directory / "completion-record.bin"),
            "c2j": data(directory / "c2j.bin"),
            "trace": data(directory / "trace.bin"),
            "runtime-zp": data(directory / "runtime-zp.bin"),
            "runtime-slot39": data(directory / "runtime-slot39.bin"),
        }
        frame = data(directory / "frame.bin")
        require(
            len(values["reader-code"]) == D.READER_BYTES
            and values["reader-code"] == data(D.PATCHED_READER)
            and len(values["completion-record"]) == 32
            and len(values["c2j"]) == 64
            and len(values["trace"]) == 8
            and values["trace"][4] == 39
            and len(values["runtime-zp"]) == 48
            and len(values["runtime-slot39"]) == RUNTIME_SLOT_BYTES
            and not any(values["runtime-slot39"])
            and len(frame) == 5,
            f"no-hit capture {index} geometry or identity drift")
        for name, value in values.items():
            stable[name].append(value)
        current_frame = int.from_bytes(frame[:2], "little")
        frames.append(current_frame)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "current_frame": f"0x{current_frame:04x}",
            "reader_holds_still_installed": True,
            "slot39_fully_wiped": True,
        })

    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values())
        and frames[0] < frames[1] < frames[2],
        "no-hit postmortem changed or frames did not progress")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
    trace = stable["trace"][0]
    runtime_zp = stable["runtime-zp"][0]
    producer = record[25] | record[26] << 8
    target = R.crc16_ccitt_false(c2j)
    screen = data(OUT / "reader-bounds-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm: bad bytecode" in screen
        and record[24] == 0xA3 and record[31] == 2
        and producer == target == 0x2801
        and c2j[:4] == b"C2J\0"
        and runtime_zp[0x8C - RUNTIME_ZP_ADDRESS] == 0,
        "no-hit First Red postmortem drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-c2d-reader-bounds-nohit-hardware-v1",
        "recorded_on": "2026-07-26",
        "status":
            "NO HIT: no C2D-reader bounds rejection in this episode",
        "promotable": False,
        "authority": {
            "host_ELF_attribution": bind(D.RECEIPT),
            "deployment": bind(D.DEPLOYMENT),
            "patched_reader": bind(D.PATCHED_READER, D.READER_VMA),
            "capture_driver": bind(D.HARDWARE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "hardware_outcome": {
            "submitted_form": "(defun %c1e () (quote t))",
            "screen_status": "*** vm: bad bytecode",
            "screen": bind(OUT / "reader-bounds-screen.png"),
            "reader_bounds_holds": {
                "count": len(D.PATCHES),
                "installed_before_form": True,
                "persisted_byteidentically_after_failure": True,
                "any_hold_taken": False,
            },
            "postmortem": {
                "phase_trace": list(trace),
                "last_slot": trace[4],
                "completion_mode": "0xa3 (ROLLBACK)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer:04x}",
                "target_C2J_crc16": f"0x{target:04x}",
                "seal_matches": True,
                "c2_ready": 0,
                "runtime_slot39_fully_wiped": True,
                "frames_progressed": True,
            },
        },
        "answer": {
            "exact_meet_comparison_exonerated": True,
            "runtime_bounds_rejection_observed": False,
            "prior_reader_zero_episode_reproduced": False,
            "interpretation": (
                "The intermittent reader-zero outcome did not recur. "
                "This episode reached fail-closed bad bytecode through a "
                "later or different false path; it supplies no runtime "
                "operand value and does not contradict the earlier "
                "reader-return discriminator."),
        },
        "time_separated_captures": rows,
        "stable_witnesses": {
            **{
                f"{name}_sha256": sha_bytes(values[0])
                for name, values in stable.items()
            },
            "byteidentical_across_three": True,
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "diagnostic_hardware_runs": 1,
            "latency_attempts_consumed": 0,
        },
        "diagnostic_lifecycle": {
            "eligible_for_promotion": False,
            "state": "discarded-after-no-hit",
        },
        "claim_limit": (
            "One no-hit episode only. The intermittent reader-zero cause "
            "remains open; C1 remains OPEN."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded, "sealed no-hit receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        RECEIPT.chmod(0o444)
    print(
        "c2-link64-reader-bounds-nohit: PASS "
        "bounds-reject=0 slot=39 mode=A3 frames=progressing")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NoHitError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link64-reader-bounds-nohit: FIRST RED: " + str(error))
        raise SystemExit(2)
