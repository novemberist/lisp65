#!/usr/bin/env python3
"""Bind the Link-64 Slot-39 failure that returned before the threshold hold."""

from __future__ import annotations

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
    "build/c2.2/hardware-link64-slot39-threshold-hold-NONPROMOTABLE")
CAPTURE = RUN / "early-first-red"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-threshold-hold-nonpromotable-receipt.json")
PRODUCT_GATE = EVIDENCE / (
    "c2.2-link64-completion-phase-context-replay-receipt.json")
DONOR_GATE = EVIDENCE / (
    "c2.2-link64-c1-donor-completion-phase-context-replay-receipt.json")
PRIOR_FIRST_RED = EVIDENCE / (
    "c2.2-link64-C1-cutpoint3-long-quote-hardware-first-red.json")
PRIOR_C2J = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-cutpoints3-4-attempt4-"
    "NONPROMOTABLE/cutpoint-3-first-red-c2j.bin")
PATCHED_CARRIER = ROOT / (
    "build/c2.2/substitution/link64-slot39-threshold-hold-NONPROMOTABLE/"
    "runtime-overlays-session-link64-slot39-threshold-hold.bin")
READBACK_CARRIER = RUN / (
    "deploy-readback-runtime-overlays-session-link64-slot39-threshold-hold.bin")
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-prethreshold-hardware-first-red.json")

TRACE = CAPTURE / "trace.bin"
RECORD = CAPTURE / "completion-record.bin"
C2J = CAPTURE / "c2j.bin"
RUNTIME_ZP = CAPTURE / "runtime-zp.bin"
FRAME = CAPTURE / "frame.bin"
POLL_STATE = CAPTURE / "poll-state.bin"
WINDOW = CAPTURE / "runtime-window.bin"
SCREEN = CAPTURE / "screen.txt"
SUMMARY = CAPTURE / "summary.json"


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


def main() -> int:
    patch = load(PATCH_RECEIPT)
    product_gate = load(PRODUCT_GATE)
    donor_gate = load(DONOR_GATE)
    prior = load(PRIOR_FIRST_RED)
    summary = load(SUMMARY)
    trace = data(TRACE)
    record = data(RECORD)
    c2j = data(C2J)
    runtime_zp = data(RUNTIME_ZP)
    frame = data(FRAME)
    screen = data(SCREEN).decode("utf-8")
    producer_seal = record[25] | record[26] << 8
    target_seal = R.crc16_ccitt_false(c2j)
    current_frame = int.from_bytes(frame[:2], "little")

    require(
        patch["status"] == "ready-nonpromotable-Link64-threshold-hold"
        and patch["patch_and_rebinding"]["after_hex"] == "b0fe"
        and data(PATCHED_CARRIER) == data(READBACK_CARRIER),
        "deployed threshold-hold identity drift")
    require(
        product_gate["result"]["phase_call_contexts"]["lowering_shape"]
            == "WPLTO-fused-ACTIVE-or-ROLLBACK"
        and product_gate["result"]["phase_call_contexts"]["call_count"] == 4
        and donor_gate["result"]["phase_call_contexts"]["lowering_shape"]
            == "instrumented-split-ACTIVE-and-ROLLBACK"
        and donor_gate["result"]["phase_call_contexts"]["call_count"] == 5
        and product_gate["result"]["phase_mutation_count"] == 6
        and donor_gate["result"]["phase_mutation_count"] == 6,
        "product/donor semantic completion-role replay drift")
    require(
        len(trace) == 8 and trace[4] == 39
        and len(record) == 32 and record[24] == 0xa3
        and record[31] == 2
        and len(c2j) == 64 and c2j[:4] == b"C2J\0"
        and producer_seal == target_seal == 0x2801
        and data(PRIOR_C2J) == c2j
        and len(runtime_zp) == 48 and runtime_zp[0x8c - 0x70] == 0
        and "*** vm: bad bytecode" in screen
        and "(defun %c1e () (quote t))" in screen
        and "lisp65>" in screen,
        "pre-threshold First Red evidence does not reproduce")
    require(
        summary["mode"] == "0xa3"
        and summary["journal_result"] == 2
        and summary["producer_seal"] == "0x2801"
        and summary["target_C2J_crc16"] == "0x2801",
        "capture summary drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-prethreshold-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status":
            "FIRST RED: Slot-39 returned bad bytecode before the "
            "64-frame threshold hold",
        "promotable": False,
        "authority": {
            "diagnostic_patch": bind(PATCH_RECEIPT),
            "deployment": bind(RUN / "deployment.json"),
            "patched_carrier": bind(PATCHED_CARRIER, 0x08000000),
            "deployed_carrier_readback":
                bind(READBACK_CARRIER, 0x08000000),
            "prior_Link64_First_Red": bind(PRIOR_FIRST_RED),
            "product_completion_role_replay": bind(PRODUCT_GATE),
            "instrumented_donor_completion_role_replay": bind(DONOR_GATE),
            "receipt_driver": bind(Path(__file__)),
        },
        "hardware_First_Red": {
            "submitted_form": "(defun %c1e () (quote t))",
            "screen_status": "*** vm: bad bytecode",
            "usable_REPL_returned": True,
            "last_session_slot": 39,
            "c2_ready_after_error": 0,
            "threshold_hold_reached": False,
            "threshold_frames": 64,
            "postmortem": {
                "completion_mode": "0xa3 (rollback)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer_seal:04x}",
                "target_C2J_seal": f"0x{target_seal:04x}",
                "seal_matches": producer_seal == target_seal,
                "C2J_byteidentical_to_prior_First_Red":
                    data(PRIOR_C2J) == c2j,
                "current_frame": f"0x{current_frame:04x}",
            },
        },
        "attribution": {
            "proven": [
                "the exact patched carrier was uploaded byte-identically",
                "the C1 donor carries all four semantic completion roles; "
                "ACTIVE and ROLLBACK are split into two linked call sites",
                "the definition entered Session slot 39 and returned "
                "bad bytecode to a usable REPL",
                "the patched 64-frame timeout branch was not reached",
                "the postmortem rollback record is PREPARED and its producer "
                "seal matches the complete target C2J",
            ],
            "disproved": [
                "a product-versus-donor mode/length-call divergence",
                "a timeout-path failure as the first observable cause",
                "a postmortem C2J producer/target seal divergence",
            ],
            "not_proven": [
                "which entry invocation (ACTIVE, publish, or rollback) first "
                "returned failure",
                "that the postmortem rollback record equals the record at the "
                "first failing Slot-39 entry",
                "that immutable Link64 product code reproduces this "
                "nonpromotable-carrier failure",
            ],
            "next_minimal_witness": (
                "hold at the first Slot-39 entry before its precondition and "
                "poll decisions; capture completion mode, journal result, "
                "producer seal and target C2J before cleanup can replace them"),
        },
        "captures": {
            "screen": bind(SCREEN),
            "trace": bind(TRACE, 0x0000c1f0),
            "completion_record": bind(RECORD, 0x0000c17c),
            "target_C2J": bind(C2J, 0x0005c640),
            "runtime_ZP": bind(RUNTIME_ZP, 0x00000070),
            "frame": bind(FRAME, 0x0000ff83),
            "poll_state": bind(POLL_STATE, 0x00000017),
            "post_failure_runtime_window": bind(WINDOW, 0x0000c356),
            "capture_summary": bind(SUMMARY),
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "diagnostic_hardware_executions": 1,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Nonpromotable diagnostic attribution only. C1 remains OPEN; "
            "no matrix-gate, acceptance-chain, promotion or release claim."),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-link64-slot39-prethreshold-first-red: PASS "
        f"mode=a3 result=PREPARED seal=0x{producer_seal:04x}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ReceiptError) as error:
        print(
            "c2-link64-slot39-prethreshold-first-red: FIRST RED: "
            + str(error))
        raise SystemExit(2)
