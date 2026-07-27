#!/usr/bin/env python3
"""Bind the Link-66 C1-session defun First Red before any Freezer action."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link66-"
    "cutpoints3-4-NONPROMOTABLE")
CP = RUN / "cutpoint-3"
LINK = ROOT / (
    "build/c2.2/substitution/"
    "product-link-66-single-submit-completion")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link66-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
PRODUCT = LINK / "lisp65-c2-substitution-linked.prg"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link66-single-submit-completion-"
    "structural-receipt.json")
CARRIER_RECEIPT = EVIDENCE / (
    "c2.2-link66-c1-freezer-carrier-nonpromotable-receipt.json")
DEPLOYMENT = RUN / "deployment.json"
HARDWARE_STATE = RUN / "hardware-state.json"
CONTROL = CP / "first-red-control.bin"
TRACE = CP / "first-red-trace.bin"
C2J = CP / "first-red-c2j.bin"
RECORD = CP / "first-red-completion-record.bin"
ZP = CP / "first-red-zp.bin"
FIXED = CP / "first-red-fixed.bin"
FRAME = CP / "first-red-frame.bin"
WINDOW = CP / "first-red-window.bin"
SCREEN_ANSI = CP / "not-reached-screen.ansi.txt"
SCREEN_PNG = CP / "not-reached-screen.png"
SCREEN_TEXT = CP / "not-reached-screen.txt"
RECEIPT = EVIDENCE / (
    "c2.2-link66-C1-cutpoint3-defun-hardware-first-red.json")
PRODUCT_SHA = (
    "482b0b28171515c79ee2c8fd3ad78cea37716887ba06acddac0067db8171f6b4")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"missing Link-66 First-Red artifact: {path}")
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def main() -> int:
    require(not RECEIPT.exists(), "Link-66 C1 First Red is one-shot")
    for path in (
            PRODUCT, LINK_RECEIPT, CARRIER_RECEIPT, DEPLOYMENT,
            HARDWARE_STATE, CONTROL, TRACE, C2J, RECORD, ZP, FIXED,
            FRAME, WINDOW, SCREEN_ANSI, SCREEN_PNG):
        require(path.is_file(), f"Link-66 First-Red authority absent: {path}")
    screen = re.sub(
        r"\x1b\[[0-9;:]*[A-Za-z]", "",
        SCREEN_ANSI.read_text(encoding="utf-8", errors="ignore"))
    SCREEN_TEXT.write_text(screen, encoding="utf-8")

    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    state = json.loads(HARDWARE_STATE.read_text(encoding="utf-8"))
    replay = json.loads(LINK_RECEIPT.read_text(encoding="utf-8"))
    carrier = json.loads(CARRIER_RECEIPT.read_text(encoding="utf-8"))
    control = CONTROL.read_bytes()
    trace = TRACE.read_bytes()
    c2j = C2J.read_bytes()
    record = RECORD.read_bytes()
    zp = ZP.read_bytes()
    fixed = FIXED.read_bytes()
    producer_seal = record[25] | record[26] << 8
    target_seal = binascii.crc_hqx(c2j, 0xFFFF)

    require(
        sha(PRODUCT) == PRODUCT_SHA
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and replay["status"]
        == "passed-link66-single-submit-completion-product-identity-"
           "hardware-not-run"
        and carrier["status"]
        == "passed-Link66-capacity-and-gates-awaiting-hardware"
        and state["status"] == "passed-cutpoint-2-ready-for-cutpoint-3"
        and state["next_cutpoint"] == 3,
        "Link-66 C1 First-Red authority drift")
    require(
        control == bytes((3, 0))
        and len(trace) == 8 and trace[4] == 39
        and len(c2j) == 64 and c2j[:4] == b"C2J\0"
        and len(record) == 32
        and record[24] == 0xA3 and record[31] == 2
        and producer_seal == target_seal == 0x2801
        and len(zp) == 48 and zp[0x8C - 0x70] == 0
        and fixed[0xBFDB - 0xBF00] == 0
        and "(defun %c1e () (quote t))" in screen
        and "*** vm: bad bytecode" in screen
        and "lisp65>" in screen
        and not (RUN / "cutpoint-4").exists(),
        "Link-66 defun First Red does not reproduce")

    value = {
        "format":
            "lisp65-c2.2-Link66-C1-defun-hardware-first-red-v1",
        "recorded_on": "2026-07-26",
        "status":
            "FIRST RED: Link66 defun returned bad bytecode before "
            "Cutpoint 3 and before any Freezer action",
        "promotable": False,
        "matrix_row": "C1",
        "authority": {
            "Link66_product": bind(PRODUCT, 0x2001),
            "Link66_structural_receipt": bind(LINK_RECEIPT),
            "nonpromotable_C1_carrier_receipt": bind(CARRIER_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "hardware_state_before_First_Red": bind(HARDWARE_STATE),
            "receipt_driver": bind(Path(__file__)),
        },
        "first_red": {
            "submitted_form": "(defun %c1e () (quote t))",
            "screen_status": "*** vm: bad bytecode",
            "usable_REPL_returned": True,
            "cutpoint_3_command": 3,
            "cutpoint_3_reached": 0,
            "Freezer_roundtrips": 0,
            "last_session_slot": 39,
            "c2_ready_after_error": 0,
            "latched_runtime_overlay_fault": 0,
            "postmortem": {
                "completion_mode": "0xa3 (rollback)",
                "journal_result": "2 (PREPARED)",
                "producer_C2J_seal": f"0x{producer_seal:04x}",
                "target_C2J_seal": f"0x{target_seal:04x}",
                "seal_matches": producer_seal == target_seal,
                "scope":
                    "post-error cleanup state; not claimed as the first "
                    "failing invocation",
            },
        },
        "attribution": {
            "proven": [
                "Link66 booted to a banner and usable REPL",
                "the exact long-form definition reached Session slot 39",
                "the definition failed before the Cutpoint-3 hold",
                "the product rendered bad bytecode and returned to a REPL",
                "no Freezer action occurred",
                "the postmortem C2J seal is internally consistent",
            ],
            "disproved": [
                "that the single-submit/local-observation correction alone "
                "is sufficient to make this C1 definition complete",
            ],
            "not_proven": [
                "which Slot-39 invocation first failed",
                "whether the first target read sampled stale data, failed, "
                "or compared through a different live operand",
                "C1 Cutpoint 3 or Cutpoint 4",
            ],
            "classification":
                "known Slot-39/defun failure class, observed before the "
                "new bundled-session rules; use as the pre-session "
                "diagnostic baseline",
        },
        "captures": {
            "screen": bind(SCREEN_TEXT),
            "screen_image": bind(SCREEN_PNG),
            "command_and_reached": bind(CONTROL, 0x17E0),
            "phase_trace": bind(TRACE, 0x0000C1F0),
            "completion_record": bind(RECORD, 0x0000C17C),
            "target_C2J": bind(C2J, 0x0005C640),
            "runtime_ZP": bind(ZP, 0x00000070),
            "fixed_state": bind(FIXED, 0x0000BF00),
            "frame": bind(FRAME, 0x0000FF80),
            "runtime_window": bind(WINDOW, 0x0000C356),
        },
        "execution_accounting": {
            "product_links": 1,
            "hardware_appointments_started": 1,
            "Freezer_roundtrips": 0,
            "latency_attempts_consumed": 0,
            "product_bytes_changed_by_fixture": 0,
        },
        "governance": {
            "new_bundled_session_rule":
                "this First Red is the baseline; the next physical "
                "appointment is one bundled session",
            "C1": "OPEN",
            "matrix_gate": "LOCKED",
            "acceptance_chain": "LOCKED",
        },
        "claim_limit":
            "Hardware First Red before Cutpoint 3. No C1, matrix-gate, "
            "acceptance-chain, promotion or release claim.",
        "next_gate":
            "host/ELF attribution, then one bundled device session with "
            "defun smoke, preloaded witnesses, Cutpoints 3/4 and immediate "
            "acceptance measurements while green",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link66-c1-defun-first-red: PASS "
        "slot=39 command=3 reached=0 freezer=0 "
        f"postmortem-seal=0x{producer_seal:04x}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            RuntimeError) as error:
        print("c2-link66-c1-defun-first-red: FIRST RED: " + str(error))
        raise SystemExit(2)
