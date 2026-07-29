#!/usr/bin/env python3
"""Bind the two Slot-40 journal-clear failures for late hardware activation.

Slot 40 is a marker-selected co-resident record.  The earlier discriminators
covered its publish-exports body but not the second call made with marker
``0x6a`` to clear the export journal.  This carrier preserves the complete
publish instrumentation and adds one hold for each common clear-body failure:
invalid export bounds and C2D write failure.

The carrier is installed only after pristine Link 71 reaches its REPL.  This
avoids the startup null-context probe and leaves all product bytes unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot40_failure_hold as V1  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold_v2 as V2  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold_v3 as V3  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


HoldError = V1.HoldError
require = V1.require

OUT = V1.BASE / "slot40-clear-hold-v6-late-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot40-clear-hold-v6.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = V1.EVIDENCE / (
    "c2.2-link71-slot40-clear-hold-v6-late-nonpromotable-receipt.json")

HOLD3 = bytes.fromhex("80 fe ea")
HOLD2 = bytes.fromhex("80 fe")
CLEAR_SITES: tuple[tuple[str, int, bytes, bytes], ...] = (
    ("journal-clear-export-count-bounds",
     0xC792, bytes.fromhex("4c 2d c8"), HOLD3),
    ("journal-clear-c2d-write",
     0xC82B, bytes.fromhex("a9 01"), HOLD2),
)


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = V1.parsed(source)
    row = base.slices[V1.SLOT]
    result = bytearray(source)
    for index, (name, vma) in enumerate(V1.SITES):
        offset = V1.payload_offset(row, vma)
        require(result[offset:offset + 3] == V1.JMP_ERROR,
                f"Slot-40 publish edge drift: {name}")
        unreachable = solver[index] if index < 2 else V3.DEFAULT_UNREACHABLE
        result[offset:offset + 3] = (
            V3.HOLD_PREFIX + bytes([unreachable]))
    for name, vma, before, after in CLEAR_SITES:
        offset = V1.payload_offset(row, vma)
        require(result[offset:offset + len(before)] == before,
                f"Slot-40 clear edge drift: {name}")
        result[offset:offset + len(after)] = after
    return bytes(result)


def solve(source: bytes) -> tuple[bytes, bytes]:
    parsed = V1.parsed(source)
    row = parsed.slices[V1.SLOT]

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
        require(pivot in basis, "clear-hold CRC solver has no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    solver = solution.to_bytes(2, "little")
    candidate = refresh(source, solver)
    require(payload_crc(candidate) == target,
            "Slot-40 payload CRC identity was not restored")
    record_offset = R.HEADER_SIZE + V1.SLOT * R.ENTRY_SIZE
    require(
        candidate[record_offset:record_offset + R.ENTRY_SIZE]
        == source[record_offset:record_offset + R.ENTRY_SIZE],
        "Slot-40 Record identity changed")
    directory_end = R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE
    require(candidate[:directory_end] == source[:directory_end],
            "directory/header identity changed")
    require(
        R.crc16_ccitt_false(candidate) == R.crc16_ccitt_false(source),
        "Session-family CRC identity was not restored")
    epilogue = V1.payload_offset(row, 0xC82D)
    require(candidate[epilogue:V1.payload_offset(row, 0xC865)]
            == source[epilogue:V1.payload_offset(row, 0xC865)],
            "common clear/success epilogue changed")
    return solver, candidate


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    return V1.bind(path, address)


def boot_preloads(base: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in base["preloads"]]
    require(V1.data(V2.ZERO_C2J) == bytes(64),
            "canonical zero-C2J preload drift")
    rows.append({
        **bind(V2.ZERO_C2J, 0x0005C640),
        "role": "known-zero-C2J-diagnostic-baseline",
    })
    return rows


def prepare() -> dict[str, Any]:
    source = V1.data(V1.SOURCE)
    base_deployment = V1.load(V1.BASE_DEPLOYMENT)
    parsed = V1.parsed(source)
    row = parsed.slices[V1.SLOT]
    solver, candidate = solve(source)
    V1.parsed(candidate)
    V1.write(CARRIER, candidate)
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    V1.write_json(MANIFEST, {
        "format": "lisp65-Link71-slot40-clear-hold-manifest-v6",
        "status": "ready-late-activated-journal-clear-discriminator",
        "promotable": False,
        "source": bind(V1.SOURCE, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "publish_error_edges_retained": len(V1.SITES),
        "clear_error_edges": [
            {
                "name": name,
                "VMA": f"0x{vma:04x}",
                "file_offset": V1.payload_offset(row, vma),
                "before": before.hex(),
                "after": after.hex(),
            }
            for name, vma, before, after in CLEAR_SITES
        ],
        "solver": {
            "bytes": solver.hex(),
            "locations": [
                {
                    "VMA": f"0x{vma + 2:04x}",
                    "reachability": "unreachable behind publish BRA $-2",
                }
                for _name, vma in V1.SITES[:2]
            ],
        },
    })
    V1.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-clear-hold-patch-v6",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-Slot40-clear-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": bind(V1.BASE_DEPLOYMENT),
            "source_carrier": bind(V1.SOURCE, 0x08000000),
            "source_ELF": bind(V1.ELF),
            "driver": bind(Path(__file__).resolve()),
        },
        "correction": (
            "Slot 40 is called first for publish (marker 0x70) and then for "
            "journal clear (marker 0x6a).  v3/v5 covered only the publish "
            "body; v6 covers both clear-body error exits as well."),
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "proof_shape": {
            "instrumented_publish_error_edges": len(V1.SITES),
            "instrumented_clear_error_edges": len(CLEAR_SITES),
            "changed_file_offsets": changed,
            "carrier_bytes_delta": 0,
            "product_bytes_delta": 0,
            "common_clear_success_epilogue_byte_identical": True,
            "slot40_payload_crc_preserved": True,
            "slot40_record_byte_identical": True,
            "directory_header_byte_identical": True,
            "family_crc16_preserved":
                f"0x{R.crc16_ccitt_false(candidate):04x}",
            "reset_stable_C2J_baseline": bind(V2.ZERO_C2J, 0x0005C640),
        },
        "outcomes": {
            "PC_0xc792": "journal-clear export-count bounds rejected",
            "PC_0xc82b": "journal-clear C2D write failed",
            "normal_BADOPCODE": (
                "all Slot-40 publish and clear failures excluded; final "
                "Slot-39 C2J-CLEAR completion remains"),
        },
        "claim_limit": (
            "Nonpromotable Link-71 post-publish attribution only; require "
            "and defstruct remain unqualified."),
    })
    receipt_binding = bind(RECEIPT)
    V1.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-clear-hold-late-deployment-v6",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "receipt": receipt_binding,
            "manifest": bind(MANIFEST),
            "source_deployment": bind(V1.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "media": base_deployment["media"],
        "remote_media": base_deployment["remote_media"],
        "boot_preloads": boot_preloads(base_deployment),
        "late_preload": {
            **bind(CARRIER, 0x08000000),
            "role": "post-boot-identity-preserving-Slot40-clear-discriminator",
        },
        "test": {"form": "(%disk-load-lib 39 1)"},
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
    })
    return {
        "status": "ready",
        "carrier_sha256": hashlib.sha256(candidate).hexdigest(),
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
        "solver_bytes": solver.hex(),
        "changed_bytes": len(changed),
    }


def verify() -> dict[str, Any]:
    source = V1.data(V1.SOURCE)
    solver, candidate = solve(source)
    require(V1.data(CARRIER) == candidate, "clear carrier drift")
    receipt = V1.load(RECEIPT)
    deployment = V1.load(DEPLOYMENT)
    require(
        deployment["authority"]["receipt"]["sha256"]
        == hashlib.sha256(V1.data(RECEIPT)).hexdigest()
        and deployment["late_preload"]["sha256"]
        == hashlib.sha256(candidate).hexdigest()
        and receipt["status"]
        == "ready-nonpromotable-Slot40-clear-discriminator",
        "clear deployment binding drift")
    for row in deployment["boot_preloads"] + [deployment["late_preload"]]:
        path = ROOT / row["path"]
        require(
            len(V1.data(path)) == row["bytes"]
            and hashlib.sha256(V1.data(path)).hexdigest() == row["sha256"],
            f"clear deployment artifact drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": hashlib.sha256(candidate).hexdigest(),
        "solver_bytes": solver.hex(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify"))
    value = prepare() if parser.parse_args().action == "prepare" else verify()
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            HoldError, R.OverlayBankError) as error:
        print(f"c2-defstruct-Link71-Slot40-clear-v6: FIRST RED: {error}")
        raise SystemExit(2)
