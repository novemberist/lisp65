#!/usr/bin/env python3
"""Bind the Link-64 Slot-39 ACTIVE-return discriminator First Red."""

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


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/hardware-link64-slot39-active-return-hold-NONPROMOTABLE")
CAPTURE = RUN / "returned-first-red"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-active-return-hold-nonpromotable-receipt.json")
ENTRY_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-entry-hold-hardware-receipt.json")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link64-slot39-active-return-hold-NONPROMOTABLE/"
    "runtime-overlays-session-link64-slot39-active-return-hold.bin")
READBACK_CARRIER = RUN / (
    "deploy-readback-runtime-overlays-session-link64-slot39-"
    "active-return-hold.bin")
DRIVER = ROOT / "scripts/c2-link64-slot39-active-return-hold-hw.sh"
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-return-hardware-first-red.json")

RECORD_ADDRESS = 0xc17c
C2J_ADDRESS = 0x0005c640
TRACE_ADDRESS = 0xc1f0
RUNTIME_ZP_ADDRESS = 0x70
FRAME_ADDRESS = 0xff83


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
    patch = load(PATCH_RECEIPT)
    entry = load(ENTRY_RECEIPT)
    deployment = load(RUN / "deployment.json")
    require(
        patch["status"] == "ready-nonpromotable-ACTIVE-return-discriminator"
        and patch["ELF_feasibility"]["outcomes"]["bad_bytecode"]
            == "first ACTIVE completion poll returned failure"
        and patch["patch_and_rebinding"]["after_hex"] == "d0fe"
        and entry["answer"]["first_entry_mode"] == "0xa1 (ACTIVE)"
        and entry["answer"]["first_entry_journal_result"] == "2 (PREPARED)"
        and entry["answer"]["seal_matches"] is True
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware"
        and data(CARRIER) == data(READBACK_CARRIER),
        "ACTIVE-return authority or deployment drift")

    stable: dict[str, list[bytes]] = {
        name: [] for name in (
            "completion-record", "c2j", "trace", "runtime-zp")
    }
    rows: list[dict[str, Any]] = []
    frames: list[int] = []
    for index in range(1, 4):
        directory = CAPTURE / f"capture-{index}"
        record = data(directory / "completion-record.bin")
        c2j = data(directory / "c2j.bin")
        trace = data(directory / "trace.bin")
        runtime_zp = data(directory / "runtime-zp.bin")
        frame = data(directory / "frame.bin")
        require(
            len(record) == 32 and len(c2j) == 64 and len(trace) == 8
            and len(runtime_zp) == 48 and len(frame) == 5
            and trace[4] == 39,
            f"ACTIVE-return capture {index} geometry drift")
        for name, value in (
                ("completion-record", record), ("c2j", c2j),
                ("trace", trace), ("runtime-zp", runtime_zp)):
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
            "c2_ready": runtime_zp[0x8c - RUNTIME_ZP_ADDRESS],
            "record": bind(
                directory / "completion-record.bin", RECORD_ADDRESS),
            "target_C2J": bind(directory / "c2j.bin", C2J_ADDRESS),
            "phase_trace": bind(directory / "trace.bin", TRACE_ADDRESS),
            "runtime_ZP": bind(
                directory / "runtime-zp.bin", RUNTIME_ZP_ADDRESS),
            "frame": bind(directory / "frame.bin", FRAME_ADDRESS),
        })

    require(
        all(len({sha_bytes(value) for value in values}) == 1
            for values in stable.values()),
        "ACTIVE-return postmortem changed across captures")
    record = stable["completion-record"][0]
    c2j = stable["c2j"][0]
    producer = record[25] | record[26] << 8
    target = R.crc16_ccitt_false(c2j)
    require(
        record[24] == 0xa3 and record[31] == 2
        and producer == target == 0x2801
        and c2j[:4] == b"C2J\0"
        and stable["runtime-zp"][0][0x8c - RUNTIME_ZP_ADDRESS] == 0
        and frames[0] < frames[1] < frames[2],
        "ACTIVE-return First Red postmortem drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-ACTIVE-return-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status":
            "FIRST RED: first ACTIVE completion poll returned false",
        "promotable": False,
        "authority": {
            "diagnostic_patch": bind(PATCH_RECEIPT),
            "entry_state_receipt": bind(ENTRY_RECEIPT),
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
            "screen": bind(CAPTURE / "screen.png"),
            "usable_REPL_returned": True,
            "binary_discriminator": {
                "patched_instruction": "BNE $c3e9",
                "success_outcome": "self-loop/hang",
                "failure_outcome": "bad bytecode and REPL return",
                "observed_outcome": "bad bytecode and REPL return",
                "answer": "first ACTIVE c2_completion_poll returned false",
            },
            "postmortem": {
                "completion_mode": "0xa3 (ROLLBACK)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer:04x}",
                "target_C2J_crc16": f"0x{target:04x}",
                "seal_matches": producer == target,
                "c2_ready": 0,
                "frame_progressed_across_captures": True,
            },
        },
        "attribution": {
            "proven": [
                "the exact nonpromotable carrier was uploaded "
                "byte-identically",
                "the first Slot-39 entry was ACTIVE/PREPARED with matching "
                "producer and target C2J seals before the poll",
                "the first ACTIVE completion poll returned false; its "
                "success branch was not taken",
                "rollback completed fail-closed to a usable REPL",
                "the postmortem rollback C2J remains byte-stable and matches "
                "its producer seal while IRQ frames continue",
            ],
            "disproved": [
                "failure before the first ACTIVE poll",
                "success of the first ACTIVE poll followed by a later "
                "header-phase failure",
                "a static producer/target C2J seal divergence at first entry",
            ],
            "not_yet_proven": [
                "whether the false return originates in the Bank-5 target "
                "read, the CRC comparison, or timeout/control flow",
                "whether the observed buffer ever equalled the landed C2J "
                "during the failed poll",
            ],
            "next_step": (
                "host/ELF dataflow attribution inside c2_completion_poll; "
                "no further hardware or product change before a concrete "
                "sub-path is named"),
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
            "Binary first-poll return attribution only. C1 remains OPEN; "
            "no matrix-gate, acceptance-chain, promotion or release claim."),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-link64-slot39-ACTIVE-return-first-red: PASS "
        "first_ACTIVE_poll=false postmortem=A3/PREPARED seal=0x2801")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReceiptError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-slot39-ACTIVE-return-first-red: FIRST RED: "
            + str(error))
        raise SystemExit(2)
