#!/usr/bin/env python3
"""Seal the final reader-zero/bounds composite First Red."""

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
import c2_link64_c2d_reader_zero_bounds_composite as C  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OUT = C.HW_OUT
CAPTURE_DRIVER = ROOT / (
    "scripts/c2-link64-reader-zero-bounds-composite-capture.sh")
RECEIPT = EVIDENCE / (
    "c2.2-link64-reader-zero-bounds-composite-hardware-first-red.json")


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


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
    C.verify()
    timing = load(OUT / "capture-times.json")
    require(
        timing["format"]
            == "lisp65-Link64-reader-zero-bounds-composite-times-v1"
        and timing["interval_seconds"] == [0, 1, 5],
        "composite capture timing drift")

    carrier = data(C.CARRIER)
    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "reader-code", "completion-record", "c2j", "trace",
            "runtime-zp", "runtime-slot39", "bank3")
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
            "bank3": data(directory / "bank3.bin"),
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
            and len(values["bank3"]) == 65536
            and values["bank3"][:len(carrier)] == carrier
            and len(frame) == 5,
            f"composite capture {index} geometry or identity drift")
        for name, value in values.items():
            stable[name].append(value)
        current_frame = int.from_bytes(frame[:2], "little")
        frames.append(current_frame)
        rows.append({
            "index": index,
            "captured_at_utc": timing["captures"][index - 1]["utc"],
            "current_frame": f"0x{current_frame:04x}",
            "bounds_holds_still_installed": True,
            "bank3_carrier_byteidentical": True,
            "slot39_fully_wiped": True,
        })

    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values())
        and frames[0] < frames[1] < frames[2],
        "composite witnesses changed or frames did not progress")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
    runtime_zp = stable["runtime-zp"][0]
    producer = record[25] | record[26] << 8
    target = R.crc16_ccitt_false(c2j)
    screen = data(OUT / "composite-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm: bad bytecode" in screen
        and record[24] == 0xA3 and record[31] == 2
        and producer == target == 0x2801
        and c2j[:4] == b"C2J\0"
        and runtime_zp[0x8C - 0x70] == 0
        and carrier[C.ZERO_JMP_FILE_OFFSET:
                    C.ZERO_JMP_FILE_OFFSET + 2] == C.ZERO_AFTER,
        "composite First Red postmortem drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-reader-zero-bounds-composite-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status":
            "FIRST RED: reader succeeded; completion failed later",
        "promotable": False,
        "authority": {
            "composite_contract": bind(C.RECEIPT),
            "deployment": bind(C.DEPLOYMENT),
            "candidate_carrier": bind(C.CARRIER, 0x08000000),
            "capture_driver": bind(CAPTURE_DRIVER),
            "evaluator": bind(Path(__file__)),
        },
        "binary_discriminator": {
            "bounds_reject_outcome":
                "self-loop at one of four live $e691 reject edges",
            "other_reader_zero_outcome":
                "self-loop at carrier $c82e",
            "reader_success_later_failure_outcome":
                "bad bytecode and REPL return",
            "observed_outcome": "bad bytecode and REPL return",
            "answer": (
                "c2_stream_c2d_read returned nonzero; the completion poll "
                "failed after the reader return"),
        },
        "hardware_evidence": {
            "bounds_holds_persisted_after_failure": True,
            "bank3_store_matches_composite_carrier": True,
            "carrier_zero_exit_patch": "JMP $c82e self-loop",
            "zero_exit_was_not_taken": True,
            "postmortem": {
                "last_slot": stable["trace"][0][4],
                "completion_mode": "0xa3 (ROLLBACK)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer:04x}",
                "target_C2J_crc16": f"0x{target:04x}",
                "seal_matches_after_rollback": True,
                "c2_ready": 0,
                "runtime_slot39_fully_wiped": True,
                "frames_progressed": True,
            },
        },
        "attribution": {
            "proven": [
                "the final Bank-3 store is byteidentical to the composite "
                "carrier carrying the zero-exit self-loop",
                "all four live bounds-edge holds remained installed",
                "no hold fired, so the reader returned nonzero",
                "bad bytecode therefore arose in content comparison or "
                "timeout handling after the successful read",
                "rollback remained fail-closed and restored a usable REPL",
            ],
            "disproved_in_this_episode": [
                "offset bounds rejection",
                "length bounds rejection",
                "any other zero return from c2_stream_c2d_read",
            ],
            "remaining_product_question": (
                "which post-read condition makes the successful ACTIVE "
                "completion poll fail: observed-target CRC/seal mismatch "
                "or the 64-frame timeout path"),
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
            "commissioned_diagnostic_cycles_consumed": "3/3",
            "latency_attempts_consumed": 0,
        },
        "diagnostic_lifecycle": {
            "eligible_for_promotion": False,
            "state": "discarded-after-final-cycle",
        },
        "claim_limit": (
            "The reader-return question is closed for this episode. "
            "The post-read product-semantic question requires Class-C "
            "review; C1 remains OPEN."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded, "sealed composite receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        RECEIPT.chmod(0o444)
    print(
        "c2-link64-reader-zero-bounds-composite: PASS "
        "reader=nonzero later-poll-failure cycles=3/3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, C.CompositeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-reader-zero-bounds-composite: FIRST RED: "
            + str(error))
        raise SystemExit(2)
