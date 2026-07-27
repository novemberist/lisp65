#!/usr/bin/env python3
"""Bind the Link-62 C1 Cutpoint-3 pre-Freezer hardware First Red.

The post-shelf Region-1 stage completed and the product reached a usable
REPL.  The first Cutpoint-3 definition then entered the append-header slice
but did not reach the contracted hold.  This is a read-only attribution over
the already captured device state; only the evidence receipt is written.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RUN = ROOT / (
    "build/c2.2/c1-freezer-hardware-link62-"
    "cutpoints3-4-NONPROMOTABLE")
LINK = ROOT / (
    "build/c2.2/substitution/product-link-62-post-shelf-region1")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link62-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE")
PRODUCT = LINK / "lisp65-c2-substitution-linked.prg"
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link62-post-shelf-region1-structural-receipt.json")
CARRIER_RECEIPT = EVIDENCE / (
    "c2.2-link62-c1-freezer-carrier-nonpromotable-receipt.json")
DEPLOYMENT = RUN / "deployment.json"
HARDWARE_STATE = RUN / "hardware-state.json"
MANIFEST = CARRIER / (
    "runtime-overlays-session-c1-freezer-link62-stage-bound.json")
REGION1 = CARRIER / (
    "runtime-overlays-session-c1-freezer-link62-region1.bin")
BOOT_BANK5 = RUN / "boot-bank5.bin"
CONTROL = RUN / "cutpoint-3/hold-before-control.bin"
C2J = RUN / "first-red-c2j.bin"
FRAME_A = RUN / "first-red-frame-a.bin"
FRAME_B = RUN / "first-red-frame-b.bin"
TRACE = RUN / "first-red-trace.bin"
ZP = RUN / "first-red-zp-0070-009f.bin"
FIXED = RUN / "first-red-fixed-state.bin"
SCREEN = RUN / "first-red-screen.png"
SCREEN_ANSI = RUN / "first-red-screen.ansi.txt"
BOOT_SCREEN = RUN / "boot-screen.png"
PRODUCT_SOURCE = LINK / "generated-product-sources/c2_product_runtime.c"
DONOR_SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE/"
    "generated-product-sources/c2_product_runtime.c")
RECEIPT = EVIDENCE / (
    "c2.2-link62-C1-Freezer-cutpoint3-"
    "prefreezer-hardware-first-red.json")

PRODUCT_SHA = (
    "85fc3cad0eded7fd6a9079194a25b59415d86f2eb99ccec7d684ac756a831b3f")
REGION1_OFFSET = 0xBD00
REGION1_CRC = 0x66C6
ZP_BASE = 0x70
C2_READY = 0x8C
FIXED_BASE = 0xBF00
RTOV_FAULT = 0xBFDB
RTOV_FAMILY = 0xBFDC
RTOV_GENERATION = 0xBFDD


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def fixed_byte(data: bytes, address: int) -> int:
    offset = address - FIXED_BASE
    require(0 <= offset < len(data), f"fixed capture misses {address:#06x}")
    return data[offset]


def main() -> int:
    require(not RECEIPT.exists(), "Cutpoint-3 First-Red receipt is one-shot")
    for path in (
            PRODUCT, LINK_RECEIPT, CARRIER_RECEIPT, DEPLOYMENT,
            HARDWARE_STATE, MANIFEST, REGION1, BOOT_BANK5, CONTROL, C2J,
            FRAME_A, FRAME_B, TRACE, ZP, FIXED, SCREEN, SCREEN_ANSI,
            BOOT_SCREEN, PRODUCT_SOURCE, DONOR_SOURCE):
        require(path.is_file(), f"First-Red authority absent: {path}")

    link = read_json(LINK_RECEIPT)
    carrier = read_json(CARRIER_RECEIPT)
    deployment = read_json(DEPLOYMENT)
    state = read_json(HARDWARE_STATE)
    manifest = read_json(MANIFEST)
    region1 = REGION1.read_bytes()
    bank5 = BOOT_BANK5.read_bytes()
    live_region1 = bank5[
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
    slot39 = [
        row for row in manifest["slice_provenance"] if row["id"] == 39]

    require(
        sha(PRODUCT) == PRODUCT_SHA
        and link["status"]
            == "passed-link62-pure-full-replay-all-gates-green"
        and link["authority"]["product"]["sha256"] == PRODUCT_SHA
        and carrier["status"]
            == "passed-Link62-capacity-and-gates-awaiting-hardware"
        and deployment["status"]
            == "ready-nonpromotable-Link62-cutpoints-3-and-4"
        and deployment["product"]["sha256"] == PRODUCT_SHA
        and state["status"] == "passed-cutpoint-2-ready-for-cutpoint-3"
        and state["next_cutpoint"] == 3
        and state["current_device_appointment_runs"] == 1,
        "Link-62 hardware authority drift")

    require(
        len(region1) == 1956
        and live_region1 == region1
        and crc16(region1) == REGION1_CRC
        and zp[C2_READY - ZP_BASE] == 1
        and fixed_byte(fixed, RTOV_FAULT) == 0,
        "post-shelf Region-1 stage did not pass before this First Red")
    require(
        control == bytes((3, 0))
        and c2j[:4] == b"C2J\0"
        and c2j != bytes(len(c2j))
        and len(trace) == 8
        and trace[4] == 39
        and trace[5] == 0
        and len(frame_a) == len(frame_b) == 8
        and 0 < frame_delta < 256
        and len(slot39) == 1
        and slot39[0]["section"] == ".lisp65_rt_c2append_header"
        and slot39[0]["source"] == "Link62-C1-donor-ELF-rebound"
        and sha(PRODUCT_SOURCE) == sha(DONOR_SOURCE)
        and not (RUN / "cutpoint-4").exists()
        and not (EVIDENCE /
                 "c2.2-link62-C1-Freezer-four-cutpoint-hardware-receipt.json"
                 ).exists(),
        "Cutpoint-3 pre-Freezer First Red does not reproduce")

    receipt = {
        "format":
            "lisp65-c2.2-Link62-C1-cutpoint3-prefreezer-"
            "hardware-first-red-v1",
        "recorded_on": "2026-07-24",
        "status":
            "FIRST RED: append header entered; Cutpoint 3 not reached",
        "matrix_row": "C1",
        "promotable": False,
        "authority": {
            "Link62_product": bind(PRODUCT, 0x2001),
            "Link62_structural_receipt": bind(LINK_RECEIPT),
            "nonpromotable_C1_carrier_receipt": bind(CARRIER_RECEIPT),
            "deployment": bind(DEPLOYMENT),
            "hardware_state_before_First_Red": bind(HARDWARE_STATE),
            "carrier_manifest": bind(MANIFEST),
            "driver": bind(Path(__file__)),
        },
        "post_shelf_region1_verdict": {
            "status": "passed-on-hardware-before-First-Red",
            "durable_source": "0x08300000",
            "runtime_target": "0x0005bd00",
            "bytes": len(region1),
            "crc16": "0x66c6",
            "expected_sha256": sha(REGION1),
            "live_sha256": hashlib.sha256(live_region1).hexdigest(),
            "byteidentical": True,
            "c2_ready": 1,
            "rtov_fault": 0,
            "boot_screen": bind(BOOT_SCREEN),
        },
        "first_red": {
            "operator_action":
                "armed Cutpoint 3 and submitted (defun %c1e () 't)",
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
            "phase_trace": {
                "last_session_slot": 39,
                "slot_name": "c2-append-header",
                "section": slot39[0]["section"],
                "inner_vm_entered": False,
                "next_cutpoint_owner": "slot 40 c2-append-publish-clear",
            },
            "frame_clock": {
                "start": f"0x{frame_start:04x}",
                "end": f"0x{frame_end:04x}",
                "delta_frames": frame_delta,
                "verdict": "advancing; not a global raster/IRQ stall",
            },
            "latched_runtime_overlay_fault": fixed_byte(fixed, RTOV_FAULT),
            "runtime_overlay_family_capture":
                fixed_byte(fixed, RTOV_FAMILY),
            "runtime_overlay_generation_capture":
                fixed_byte(fixed, RTOV_GENERATION),
            "screen": bind(SCREEN),
        },
        "attribution": {
            "proven": [
                "Link62 boot reached the banner and a usable REPL",
                "post-shelf Region-1 target is byte-identical and CRC-correct",
                "the definition entered Session slot 39 c2-append-header",
                "C2J remained active while the frame clock advanced",
                "Cutpoint 3 was not reached and no Freezer roundtrip occurred",
            ],
            "source_identity": {
                "product_source_sha256": sha(PRODUCT_SOURCE),
                "diagnostic_donor_source_sha256": sha(DONOR_SOURCE),
                "byteidentical": True,
            },
            "not_proven": [
                "the exact instruction at which slot 39 stopped",
                "whether the stop is in c2_completion_poll, its Bank-5 read, "
                "or timeout accounting",
                "that the immutable product without the diagnostic carrier "
                "would reproduce the stop",
            ],
            "classification":
                "new append/write-completion boundary product question "
                "raised by a nonpromotable carrier; not a Region-1-stage "
                "regression and not yet a promotable-product defect claim",
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
            "screen_ansi": bind(SCREEN_ANSI),
        },
        "execution_accounting": {
            "Link62_product_links": 1,
            "current_device_appointment_runs": 1,
            "Cutpoint_3_Freezer_roundtrips": 0,
            "Cutpoint_4_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "First Red before the Cutpoint-3 hold. C1 remains OPEN. No "
            "Cutpoint-3/4, matrix-gate, promotion, acceptance-chain or "
            "release claim."),
        "next_gate": (
            "Class-C review of the slot-39 completion boundary. No retry: "
            "first perform bounded host/ELF attribution of the observed "
            "header path, then authorize any diagnostic or product change."),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    for path in (
            CONTROL, C2J, FRAME_A, FRAME_B, TRACE, ZP, FIXED, SCREEN,
            SCREEN_ANSI):
        os.chmod(path, 0o444)
    print(
        "c2-link62-C1-cutpoint3-prefreezer-first-red: PASS "
        f"region1=66c6 READY=1 fault=0 slot=39 C2J=ACTIVE "
        f"frames=+{frame_delta} command/reached=3/0 Freezer=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-link62-C1-cutpoint3-prefreezer-first-red: FAIL "
            + str(error),
            file=sys.stderr,
        )
        raise SystemExit(2)
