#!/usr/bin/env python3
"""Bind the Link-64 Slot-39 reader-return discriminator First Red."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402
import c2_link64_slot39_reader_return_hold as D  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/hardware-link64-slot39-reader-return-hold-NONPROMOTABLE")
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-reader-return-hold-nonpromotable-receipt.json")
ATTRIBUTION = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-false-host-ELF-attribution.json")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link64-slot39-reader-return-hold-NONPROMOTABLE/"
    "runtime-overlays-session-link64-slot39-reader-return-hold.bin")
READBACK_CARRIER = RUN / (
    "deploy-readback-runtime-overlays-session-link64-slot39-"
    "reader-return-hold.bin")
DRIVER = ROOT / "scripts/c2-link64-slot39-reader-return-hold-hw.sh"
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-reader-return-hold-hardware-receipt.json")

RECORD_ADDRESS = 0xC17C
C2J_ADDRESS = 0x0005C640
TRACE_ADDRESS = 0xC1F0
RUNTIME_ZP_ADDRESS = 0x70
FRAME_ADDRESS = 0xFF83
SLOT_ADDRESS = 0xC356


class ReceiptError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReceiptError(message)


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


def captured_at(path: Path) -> str:
    return datetime.fromtimestamp(
        path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    D.verify()
    patch = load(PATCH_RECEIPT)
    attribution = load(ATTRIBUTION)
    deployment = load(RUN / "deployment.json")
    require(
        patch["status"]
            == "ready-authorized-nonpromotable-reader-discriminator"
        and patch["patch_and_rebinding"]["after_hex"] == "d0fe"
        and attribution["next_minimal_discriminator"]["instruction_VMA"]
            == "0xc82c"
        and attribution["false_return_partition"][
            "reader_returned_zero"]["static_bounds_result"]
            == "$c640 + 64 == $c680 == region end; accepted"
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware"
        and data(CARRIER) == data(READBACK_CARRIER),
        "reader-return authority or deployment drift")

    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "completion-record", "c2j", "trace", "runtime-zp",
            "runtime-slot39")
    }
    rows: list[dict[str, Any]] = []
    frames: list[int] = []
    for index in range(1, 4):
        directory = RUN / f"capture-{index}"
        record = data(directory / "completion-record.bin")
        c2j = data(directory / "c2j.bin")
        trace = data(directory / "trace.bin")
        runtime_zp = data(directory / "runtime-zp.bin")
        slot = data(directory / "runtime-slot39.bin")
        frame = data(directory / "frame.bin")
        require(
            len(record) == 32 and len(c2j) == 64 and len(trace) == 8
            and len(runtime_zp) == 48 and len(slot) == 1509
            and len(frame) == 5 and trace[4] == 39
            and slot == bytes(len(slot)),
            f"reader-return capture {index} geometry or wipe drift")
        for name, value in (
                ("completion-record", record), ("c2j", c2j),
                ("trace", trace), ("runtime-zp", runtime_zp),
                ("runtime-slot39", slot)):
            stable[name].append(value)
        producer = record[25] | record[26] << 8
        target = R.crc16_ccitt_false(c2j)
        current_frame = int.from_bytes(frame[:2], "little")
        frames.append(current_frame)
        rows.append({
            "index": index,
            "captured_at_utc":
                captured_at(directory / "completion-record.bin"),
            "completion_mode": f"0x{record[24]:02x}",
            "journal_result": record[31],
            "producer_seal": f"0x{producer:04x}",
            "target_C2J_crc16": f"0x{target:04x}",
            "seal_matches": producer == target,
            "current_frame": f"0x{current_frame:04x}",
            "c2_ready": runtime_zp[0x8C - RUNTIME_ZP_ADDRESS],
            "runtime_slot39_fully_wiped": True,
            "record": bind(
                directory / "completion-record.bin", RECORD_ADDRESS),
            "target_C2J": bind(directory / "c2j.bin", C2J_ADDRESS),
            "phase_trace": bind(directory / "trace.bin", TRACE_ADDRESS),
            "runtime_ZP": bind(
                directory / "runtime-zp.bin", RUNTIME_ZP_ADDRESS),
            "runtime_slot39": bind(
                directory / "runtime-slot39.bin", SLOT_ADDRESS),
            "frame": bind(directory / "frame.bin", FRAME_ADDRESS),
        })

    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values()),
        "reader-return postmortem changed across captures")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
    producer = record[25] | record[26] << 8
    target = R.crc16_ccitt_false(c2j)
    screen = data(RUN / "reader-return-screen.txt").decode("utf-8")
    require(
        "(defun %c1e () (quote t))" in screen
        and "*** vm: bad bytecode" in screen
        and record[24] == 0xA3 and record[31] == 2
        and producer == target == 0x2801
        and c2j[:4] == b"C2J\0"
        and stable["runtime-zp"][0][0x8C - RUNTIME_ZP_ADDRESS] == 0
        and frames[0] < frames[1] < frames[2],
        "reader-return First Red postmortem drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-reader-return-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status": "FIRST RED: linked Bank-5 reader returned zero",
        "promotable": False,
        "authority": {
            "diagnostic_patch": bind(PATCH_RECEIPT),
            "prior_host_ELF_attribution": bind(ATTRIBUTION),
            "deployment": bind(RUN / "deployment.json"),
            "candidate_carrier": bind(CARRIER, 0x08000000),
            "deployed_carrier_readback":
                bind(READBACK_CARRIER, 0x08000000),
            "hardware_driver": bind(DRIVER),
            "receipt_driver": bind(Path(__file__)),
        },
        "hardware_First_Red": {
            "submitted_form": "(defun %c1e () (quote t))",
            "screen_status": "*** vm: bad bytecode",
            "screen": bind(RUN / "reader-return-screen.png"),
            "usable_REPL_returned": True,
            "binary_discriminator": {
                "patched_instruction": "BNE $c82c",
                "nonzero_outcome": "self-loop/hang at $c82c",
                "zero_outcome": "bad bytecode and REPL return",
                "observed_outcome": "bad bytecode and REPL return",
                "answer": "c2_stream_c2d_read returned zero",
            },
            "postmortem": {
                "completion_mode": "0xa3 (ROLLBACK)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer:04x}",
                "target_C2J_crc16": f"0x{target:04x}",
                "seal_matches": producer == target,
                "c2_ready": 0,
                "runtime_slot39_fully_wiped": True,
                "frame_progressed_across_captures": True,
            },
        },
        "attribution": {
            "proven": [
                "the exact nonpromotable carrier was uploaded "
                "byte-identically",
                "the post-reader BNE success edge was replaced by its own "
                "self-loop without changing carrier size",
                "bad bytecode and REPL return prove that the success edge "
                "was not taken: c2_stream_c2d_read returned zero",
                "the linked arguments are Bank 5, offset $c640, length 64; "
                "$c640 + 64 equals the accepted region end $c680",
                "rollback completed fail-closed, wiped Slot 39 completely, "
                "and preserved a usable REPL",
                "the A3/PREPARED postmortem C2J remains byte-stable and "
                "matches producer seal $2801 while IRQ frames continue",
            ],
            "disproved": [
                "reader success followed by CRC/seal nonmatch or timeout",
                "failure in the CRC comparison after a successful read",
                "a static out-of-bounds request",
                "a producer/target C2J seal divergence",
            ],
            "next_question": (
                "why c2_stream_c2d_read returns zero for the exact accepted "
                "end-of-region Bank-5 request; inspect its runtime ownership/"
                "region validation and caller-visible return contract before "
                "any product fix"),
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
            "Bank-5 reader-return attribution only. C1 remains OPEN; no "
            "matrix-gate, acceptance-chain, promotion or release claim."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded,
                "sealed reader-return hardware receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
    print(
        "c2-link64-slot39-reader-return-first-red: PASS "
        "reader=zero range=$c640..$c67f postmortem=A3/PREPARED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReceiptError, D.ReaderHoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-slot39-reader-return-first-red: FIRST RED: "
            + str(error))
        raise SystemExit(2)
