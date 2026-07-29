#!/usr/bin/env python3
"""Freeze Link-71 at the first successfully loaded Slot-40 instruction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot40_failure_hold as H  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


OUT = H.BASE / "slot40-entry-hold-v2-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot40-entry-hold-v2.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = H.EVIDENCE / (
    "c2.2-link71-slot40-entry-hold-v2-nonpromotable-receipt.json")
ENTRY_VMA = 0xC360
ENTRY_BEFORE = bytes.fromhex("a2 00 86")
ENTRY_HOLD = bytes.fromhex("80 fe ea")
# The solver must live in the patched Slot-40 payload itself.  The runtime
# catalog carries an external expected Record CRC, so compensating in another
# slot preserves the family CRC but still makes Slot 40 unloadable.  These
# final two pre-RTS bytes are unreachable after the entry hold.
SOLVER_VMA = 0xC863
SOLVER_BEFORE = bytes.fromhex("12 60")


def refresh(source: bytes, solver: bytes) -> bytes:
    base = H.parsed(source)
    result = bytearray(source)
    entry_offset = H.payload_offset(base.slices[H.SLOT], ENTRY_VMA)
    solver_offset = H.payload_offset(base.slices[H.SLOT], SOLVER_VMA)
    H.require(result[entry_offset:entry_offset + 3] == ENTRY_BEFORE,
              "Slot-40 entry bytes drift")
    H.require(result[solver_offset:solver_offset + 2] == SOLVER_BEFORE,
              "Slot-40 entry solver bytes drift")
    result[entry_offset:entry_offset + 3] = ENTRY_HOLD
    result[solver_offset:solver_offset + 2] = solver
    return bytes(result)


def solve(source: bytes) -> tuple[bytes, bytes]:
    parsed = H.parsed(source)
    row = parsed.slices[H.SLOT]

    def payload_crc(value: bytes) -> int:
        return R.crc16_ccitt_false(
            value[row.file_offset:row.file_offset + row.file_size])

    target = payload_crc(source)
    baseline = payload_crc(refresh(source, b"\0\0"))
    columns = [
        payload_crc(refresh(source, (1 << bit).to_bytes(2, "little")))
        ^ baseline
        for bit in range(16)
    ]
    basis: dict[int, tuple[int, int]] = {}
    for bit, column in enumerate(columns):
        vector, mask = column, 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                vector ^= basis[pivot][0]
                mask ^= basis[pivot][1]
            else:
                basis[pivot] = vector, mask
                break
    vector, solution = target ^ baseline, 0
    while vector:
        pivot = vector.bit_length() - 1
        H.require(pivot in basis, "entry-hold CRC solver has no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    solver = solution.to_bytes(2, "little")
    candidate = refresh(source, solver)
    H.require(payload_crc(candidate) == target,
              "entry-hold Slot-40 payload CRC was not restored")
    record_offset = R.HEADER_SIZE + H.SLOT * R.ENTRY_SIZE
    H.require(
        candidate[record_offset:record_offset + R.ENTRY_SIZE]
        == source[record_offset:record_offset + R.ENTRY_SIZE],
        "entry-hold Slot-40 record identity changed")
    H.require(
        candidate[:R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE]
        == source[:R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE],
        "entry-hold directory/header identity changed")
    H.require(R.crc16_ccitt_false(candidate)
              == R.crc16_ccitt_false(source),
              "entry-hold family CRC was not restored")
    return solver, candidate


def main() -> int:
    H.verify()
    source = H.data(H.SOURCE)
    base_deployment = H.load(H.BASE_DEPLOYMENT)
    solver, candidate = solve(source)
    H.parsed(candidate)
    H.write(CARRIER, candidate)
    H.write_json(MANIFEST, {
        "format": "lisp65-Link71-slot40-entry-hold-manifest-v2",
        "status": "ready-nonpromotable-loaded-entry-hold",
        "promotable": False,
        "source": H.bind(H.CARRIER, 0x08000000),
        "candidate": H.bind(CARRIER, 0x08000000),
        "entry_patch": {
            "VMA": f"0x{ENTRY_VMA:04x}",
            "before": ENTRY_BEFORE.hex(),
            "after": ENTRY_HOLD.hex(),
        },
        "solver": {
            "slot": H.SLOT,
            "VMA": f"0x{SOLVER_VMA:04x}",
            "bytes": solver.hex(),
            "binding": (
                "restores the original Slot-40 payload CRC, hence the "
                "external Record CRC, directory, header and family identity"),
        },
    })
    H.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-entry-hold-v2",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-Slot40-loaded-entry-witness",
        "promotable": False,
        "authority": {
            "source_carrier": H.bind(H.SOURCE, 0x08000000),
            "source_deployment": H.bind(H.BASE_DEPLOYMENT),
            "driver": H.bind(Path(__file__).resolve()),
        },
        "candidate": {
            "carrier": H.bind(CARRIER, 0x08000000),
            "manifest": H.bind(MANIFEST),
        },
        "purpose": (
            "Distinguish runtime record-load rejection from an executed "
            "Slot-40 entry precondition, and freeze committed/plan-marker "
            "bytes before rollback."),
        "v1_correction": (
            "v1 restored the family CRC with bytes in Slot 45 but changed "
            "Slot 40's externally expected Record CRC; hardware correctly "
            "rejected that diagnostic carrier before its first instruction."),
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0
        }
    })
    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **H.bind(CARRIER, int(copy["address"], 16)),
                "role": copy["role"],
            }
            replaced += 1
        preloads.append(copy)
    H.require(replaced == 1, "entry-hold carrier replacement is not unique")
    H.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-entry-hold-deployment-v2",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "receipt": H.bind(RECEIPT),
            "manifest": H.bind(MANIFEST),
            "source_deployment": H.bind(H.DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "media": base_deployment["media"],
        "remote_media": base_deployment["remote_media"],
        "preloads": preloads,
        "test": {"form": "(%disk-load-lib 39 1)"},
    })
    print(json.dumps({
        "status": "ready",
        "carrier_sha256": hashlib.sha256(candidate).hexdigest(),
        "solver": solver.hex(),
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            H.HoldError, R.OverlayBankError) as error:
        print(f"c2-defstruct-Link71-Slot40-entry: FIRST RED: {error}")
        raise SystemExit(2)
