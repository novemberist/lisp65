#!/usr/bin/env python3
"""Bind the Link-64 C1 Cutpoint-3 intact-long-quote First Red."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link64-"
    "cutpoints3-4-attempt4-NONPROMOTABLE")
LINK = ROOT / (
    "build/c2.2/substitution/"
    "product-link-64-nonlto-stateless-completion-length")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
DONOR = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
PRODUCT = LINK / "lisp65-c2-substitution-linked.prg"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link64-nonlto-stateless-completion-length-"
    "structural-receipt.json")
CARRIER_RECEIPT = EVIDENCE / (
    "c2.2-link64-c1-freezer-carrier-nonpromotable-receipt.json")
PRIOR_QUOTE_RECEIPT = EVIDENCE / (
    "c2.2-link64-C1-cutpoint3-virtual-key-quote-first-red.json")
DEPLOYMENT = RUN / "deployment.json"
HARDWARE_STATE = RUN / "hardware-state.json"
MANIFEST = CARRIER / (
    "runtime-overlays-session-c1-freezer-link64-stage-bound.json")
REGION1 = CARRIER / (
    "runtime-overlays-session-c1-freezer-link64-region1.bin")
BOOT_BANK5 = RUN / "boot-bank5.bin"
CONTROL = RUN / "cutpoint-3/hold-before-control.bin"
C2J = RUN / "cutpoint-3-first-red-c2j.bin"
FRAME_A = RUN / "cutpoint-3-first-red-frame-a.bin"
FRAME_B = RUN / "cutpoint-3-first-red-frame-b.bin"
TRACE = RUN / "cutpoint-3-first-red-trace.bin"
ZP = RUN / "cutpoint-3-first-red-zp-0070-009f.bin"
FIXED = RUN / "cutpoint-3-first-red-fixed-state.bin"
SCREEN = RUN / "cutpoint-3-not-reached-screen.txt"
SCREEN_PNG = RUN / "cutpoint-3-not-reached-screen.png"
PRODUCT_SOURCE = LINK / "generated-product-sources/c2_product_runtime.c"
DONOR_SOURCE = DONOR / "generated-product-sources/c2_product_runtime.c"
RECEIPT = EVIDENCE / (
    "c2.2-link64-C1-cutpoint3-long-quote-hardware-first-red.json")

PRODUCT_SHA = (
    "13c82707ae1797885ff2ddeb7bff62198bf897a9163ed63b7531df8212d49b2c")
REGION1_OFFSET = 0xBD00
ZP_BASE = 0x70
C2_READY = 0x8C
FIXED_BASE = 0xBF00
RTOV_FAULT = 0xBFDB


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"missing First-Red artifact: {path}")
    result: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def fixed_byte(data: bytes, address: int) -> int:
    return data[address - FIXED_BASE]


def main() -> int:
    require(not RECEIPT.exists(), "long-quote First Red is one-shot")
    for path in (
            PRODUCT, LINK_RECEIPT, CARRIER_RECEIPT, PRIOR_QUOTE_RECEIPT,
            DEPLOYMENT, HARDWARE_STATE, MANIFEST, REGION1, BOOT_BANK5,
            CONTROL, C2J, FRAME_A, FRAME_B, TRACE, ZP, FIXED, SCREEN,
            SCREEN_PNG, PRODUCT_SOURCE, DONOR_SOURCE):
        require(path.is_file(), f"First-Red authority absent: {path}")

    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    state = json.loads(HARDWARE_STATE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    screen = SCREEN.read_text(encoding="utf-8")
    region1 = REGION1.read_bytes()
    live_region1 = BOOT_BANK5.read_bytes()[
        REGION1_OFFSET:REGION1_OFFSET + len(region1)]
    control = CONTROL.read_bytes()
    c2j = C2J.read_bytes()
    frame_a = FRAME_A.read_bytes()
    frame_b = FRAME_B.read_bytes()
    trace = TRACE.read_bytes()
    zp = ZP.read_bytes()
    fixed = FIXED.read_bytes()
    frame_start = int.from_bytes(frame_a[3:5], "little")
    frame_end = int.from_bytes(frame_b[3:5], "little")
    frame_delta = (frame_end - frame_start) & 0xFFFF
    slots = {
        row["id"]: row for row in manifest["slice_provenance"]
        if row["id"] in (39, 40)
    }

    require(
        sha(PRODUCT) == PRODUCT_SHA
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and state["status"] == "passed-cutpoint-2-ready-for-cutpoint-3"
        and state["next_cutpoint"] == 3
        and [row["id"] for row in state["cutpoints"]] == [1, 2],
        "Link-64 hardware authority drift")
    require(
        live_region1 == region1
        and control == bytes((3, 0))
        and c2j[:4] == b"C2J\0"
        and any(c2j[4:])
        and len(trace) == 8
        and trace[6] == 39
        and frame_delta == 57
        and zp[C2_READY - ZP_BASE] == 0
        and fixed_byte(fixed, RTOV_FAULT) == 0
        and slots[39]["section"] == ".lisp65_rt_c2append_header"
        and slots[40]["section"] == ".lisp65_rt_c2append_publish_clear"
        and "(defun %c1e () (quote t))" in screen
        and "*** vm: bad bytecode" in screen
        and "lisp65>" in screen
        and sha(PRODUCT_SOURCE) == sha(DONOR_SOURCE)
        and not (RUN / "cutpoint-4").exists(),
        "long-quote Cutpoint-3 First Red does not reproduce")

    value = {
        "format":
            "lisp65-c2.2-link64-C1-cutpoint3-long-quote-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-25",
        "status":
            "FIRST RED: intact long-quote definition reports bad bytecode "
            "in slot 39 before Cutpoint 3",
        "matrix_row": "C1",
        "promotable": False,
        "authority": {
            "Link64_product": bind(PRODUCT, 0x2001),
            "Link64_structural_receipt": bind(LINK_RECEIPT),
            "nonpromotable_C1_carrier_receipt": bind(CARRIER_RECEIPT),
            "prior_dropped_apostrophe_First_Red": bind(PRIOR_QUOTE_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "hardware_state_before_First_Red": bind(HARDWARE_STATE),
            "carrier_manifest": bind(MANIFEST),
            "receipt_driver": bind(Path(__file__)),
        },
        "first_red": {
            "submitted_form": "(defun %c1e () (quote t))",
            "screen_form_bytecomplete": True,
            "screen_status": "*** vm: bad bytecode",
            "usable_REPL_returned": True,
            "Freezer_roundtrips": 0,
            "cutpoint_3_command": 3,
            "cutpoint_3_reached": 0,
            "cutpoint_4": "not-run",
            "C2J": {
                "state": "ACTIVE/nonzero",
                "magic": "C2J",
                "bytes": len(c2j),
                "sha256": sha(C2J),
            },
            "c2_ready_after_error": 0,
            "latched_runtime_overlay_fault": fixed_byte(fixed, RTOV_FAULT),
            "phase_trace": {
                "last_session_slot": 39,
                "slot_name": "c2-append-header",
                "inner_vm_entered": False,
                "next_cutpoint_owner": "slot 40 c2-append-publish-clear",
            },
            "frame_clock": {
                "start": f"0x{frame_start:04x}",
                "end": f"0x{frame_end:04x}",
                "delta_frames": frame_delta,
                "verdict": "advancing; not a global raster/IRQ stall",
            },
        },
        "attribution": {
            "proven": [
                "the cold restart reached the banner and a usable REPL",
                "the post-shelf Region-1 target is byte-identical",
                "the virtual keyboard delivered every byte of (quote t)",
                "the definition entered Session slot 39 c2-append-header",
                "the product rendered bad bytecode and returned to a REPL",
                "C2J remained active while READY was cleared",
                "Cutpoint 3 was not reached and no Freezer roundtrip occurred",
            ],
            "source_identity": {
                "product_source_sha256": sha(PRODUCT_SOURCE),
                "diagnostic_donor_source_sha256": sha(DONOR_SOURCE),
                "byteidentical": True,
            },
            "prior_harness_assumption":
                "(quote t) is hardware-equivalent to apostrophe-t",
            "prior_harness_assumption_status": "disproved on this path",
            "not_proven": [
                "that the immutable product without the diagnostic carrier "
                "reproduces the same long-quote failure",
                "whether the failure originates in long-quote emission, "
                "slot-39 completion, or abort cleanup",
                "that C1 Cutpoint 3 or Cutpoint 4 passes",
            ],
            "classification":
                "new dynamic-append/rollback product-semantics question "
                "raised by a nonpromotable carrier; not a mere input-transport "
                "failure and not yet a promotable-product defect claim",
        },
        "captures": {
            "command_and_reached": bind(CONTROL, 0x17E0),
            "C2J": bind(C2J, 0x0005C640),
            "frame_start": bind(FRAME_A, 0x0000FF80),
            "frame_end": bind(FRAME_B, 0x0000FF80),
            "phase_trace": bind(TRACE, 0x0000C1EE),
            "zero_page": bind(ZP, 0x00000070),
            "fixed_state": bind(FIXED, FIXED_BASE),
            "screen": bind(SCREEN),
            "screen_image": bind(SCREEN_PNG),
            "region1": {
                "bytes": len(region1),
                "crc16": f"0x{binascii.crc_hqx(region1, 0xFFFF):04x}",
                "expected_sha256": sha(REGION1),
                "live_sha256": hashlib.sha256(live_region1).hexdigest(),
                "byteidentical": True,
            },
        },
        "execution_accounting": {
            "current_device_appointment_runs": 1,
            "Cutpoint_3_Freezer_roundtrips": 0,
            "Cutpoint_4_runs": 0,
            "latency_attempts_consumed": 0,
            "product_bytes_changed": 0,
        },
        "claim_limit":
            "First Red before the Cutpoint-3 hold. C1 remains OPEN. No "
            "matrix-gate, promotion, acceptance-chain or release claim.",
        "next_gate":
            "Class-C review of the intact-long-quote slot-39 failure and "
            "ACTIVE-C2J/READY-zero aftermath before any further hardware run.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(
        "c2-link64-C1-cutpoint3-long-quote-first-red: BOUND "
        "slot=39 command/reached=3/0 C2J=ACTIVE READY=0 "
        f"frames=+{frame_delta} freezer=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
