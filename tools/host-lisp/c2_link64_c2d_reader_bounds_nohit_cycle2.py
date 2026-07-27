#!/usr/bin/env python3
"""Seal cycle 2's no-hit C2D-reader bounds outcome."""

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
PRIOR = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-hardware-receipt.json")
OUT = ROOT / (
    "build/c2.2/hardware-link64-c2d-reader-bounds-hold-cycle2-"
    "NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"
CAPTURE_DRIVER = ROOT / (
    "scripts/c2-link64-c2d-reader-bounds-hold-cycle2-capture.sh")
RECEIPT = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-cycle2-hardware-receipt.json")


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
    prior = load(PRIOR)
    deployment = load(DEPLOYMENT)
    timing = load(OUT / "capture-times.json")
    require(
        prior["answer"]["runtime_bounds_rejection_observed"] is False
        and deployment["diagnostic_cycle"] == 2
        and timing["format"]
            == "lisp65-Link64-c2d-reader-bounds-nohit-times-v2"
        and timing["interval_seconds"] == [0, 1, 5],
        "cycle-2 no-hit authority drift")

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
            "completion-record":
                data(directory / "completion-record.bin"),
            "c2j": data(directory / "c2j.bin"),
            "trace": data(directory / "trace.bin"),
            "runtime-zp": data(directory / "runtime-zp.bin"),
            "runtime-slot39": data(directory / "runtime-slot39.bin"),
        }
        frame = data(directory / "frame.bin")
        require(
            values["reader-code"] == data(D.PATCHED_READER)
            and len(values["completion-record"]) == 32
            and len(values["c2j"]) == 64
            and len(values["trace"]) == 8
            and values["trace"][4] == 39
            and len(values["runtime-zp"]) == 48
            and len(values["runtime-slot39"]) == 1509
            and not any(values["runtime-slot39"])
            and len(frame) == 5,
            f"cycle-2 no-hit capture {index} drift")
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
        "cycle-2 witnesses changed or frames did not progress")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
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
        and runtime_zp[0x8C - 0x70] == 0,
        "cycle-2 First Red postmortem drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-c2d-reader-bounds-nohit-hardware-v2",
        "recorded_on": "2026-07-26",
        "status":
            "NO HIT cycle 2: no C2D-reader bounds rejection",
        "promotable": False,
        "authority": {
            "cycle_1_nohit": bind(PRIOR),
            "cycle_2_deployment": bind(DEPLOYMENT),
            "patched_reader": bind(D.PATCHED_READER, D.READER_VMA),
            "capture_driver": bind(CAPTURE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "answer": {
            "runtime_bounds_rejection_observed": False,
            "consecutive_nohit_episodes": 2,
            "remaining_cycle_3_question": (
                "combine the four bounds-edge holds with a hold on the "
                "caller's reader-zero exit, separating bounds rejection, "
                "other zero return, and later poll failure"),
        },
        "postmortem": {
            "last_slot": stable["trace"][0][4],
            "completion_mode": "0xa3 (ROLLBACK)",
            "journal_result": "2 (PREPARED)",
            "producer_C2J_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches": True,
            "c2_ready": 0,
            "slot39_fully_wiped": True,
            "frames_progressed": True,
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
            "Second no-hit episode only. C1 and the intermittent "
            "reader-zero cause remain OPEN."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded, "sealed cycle-2 receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        RECEIPT.chmod(0o444)
    print(
        "c2-link64-reader-bounds-nohit-cycle2: PASS "
        "bounds-reject=0 slot=39 mode=A3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (NoHitError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-reader-bounds-nohit-cycle2: FIRST RED: "
            + str(error))
        raise SystemExit(2)
