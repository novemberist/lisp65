#!/usr/bin/env python3
"""Build the identity- and success-path-preserving Slot-40 hold carrier.

v2 correctly moved its CRC compensation into Slot 40, but put it over the
live common ``LDA status; RTS`` epilogue.  v3 uses the unreachable third byte
behind two ``BRA $-2`` holds as the two CRC-solver bytes.  All thirteen holds,
the complete success path, and every externally consumed identity therefore
remain valid simultaneously.
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
import runtime_overlay_bank as R  # noqa: E402


HoldError = V1.HoldError
require = V1.require
write_json = V1.write_json

OUT = V1.BASE / "slot40-failure-hold-v3-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot40-failure-hold-v3.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = V1.EVIDENCE / (
    "c2.2-link71-slot40-failure-hold-v3-nonpromotable-receipt.json")

HOLD_PREFIX = bytes.fromhex("80 fe")
DEFAULT_UNREACHABLE = 0xEA
SOLVER_SITES = V1.SITES[:2]


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = V1.parsed(source)
    row = base.slices[V1.SLOT]
    result = bytearray(source)
    for index, (name, vma) in enumerate(V1.SITES):
        offset = V1.payload_offset(row, vma)
        require(result[offset:offset + 3] == V1.JMP_ERROR,
                f"Slot-40 edge drift: {name}")
        unreachable = solver[index] if index < 2 else DEFAULT_UNREACHABLE
        result[offset:offset + 3] = HOLD_PREFIX + bytes([unreachable])
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
        require(pivot in basis, "unreachable-byte CRC solver has no solution")
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
    require(
        candidate[V1.payload_offset(row, 0xC862):
                  V1.payload_offset(row, 0xC865)]
        == source[V1.payload_offset(row, 0xC862):
                  V1.payload_offset(row, 0xC865)],
        "live Slot-40 return epilogue changed")
    return solver, candidate


def candidate_preloads(
        deployment: dict[str, Any], candidate: bytes) -> list[dict[str, Any]]:
    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **V1.bind(CARRIER, int(copy["address"], 16)),
                "role": copy["role"],
            }
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "diagnostic carrier replacement is not unique")
    require(V1.data(V2.ZERO_C2J) == bytes(64),
            "canonical zero-C2J preload drift")
    preloads.append({
        **V1.bind(V2.ZERO_C2J, 0x0005C640),
        "role": "known-zero-C2J-diagnostic-baseline",
    })
    require(
        any(row["sha256"] == hashlib.sha256(candidate).hexdigest()
            for row in preloads),
        "candidate preload binding missing")
    return preloads


def prepare() -> dict[str, Any]:
    source = V1.data(V1.SOURCE)
    deployment = V1.load(V1.BASE_DEPLOYMENT)
    base = V1.parsed(source)
    solver, candidate = solve(source)
    V1.parsed(candidate)
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    V1.write(CARRIER, candidate)
    edge_rows = []
    for index, (name, vma) in enumerate(V1.SITES):
        offset = V1.payload_offset(base.slices[V1.SLOT], vma)
        edge_rows.append({
            "name": name,
            "VMA": f"0x{vma:04x}",
            "file_offset": offset,
            "before": V1.JMP_ERROR.hex(),
            "after": candidate[offset:offset + 3].hex(),
            "unreachable_solver_byte": index < 2,
        })
    V1.write_json(MANIFEST, {
        "format": "lisp65-Link71-slot40-failure-hold-manifest-v3",
        "status": "ready-identity-and-success-path-preserving-error-hold",
        "promotable": False,
        "source": V1.bind(V1.SOURCE, 0x08000000),
        "candidate": V1.bind(CARRIER, 0x08000000),
        "error_edges": edge_rows,
        "solver": {
            "bytes": solver.hex(),
            "locations": [
                {
                    "site": name,
                    "VMA": f"0x{vma + 2:04x}",
                    "reachability": "unreachable behind unconditional BRA $-2",
                }
                for name, vma in SOLVER_SITES
            ],
        },
    })
    V1.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-patch-v3",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-Slot40-publication-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": V1.bind(V1.BASE_DEPLOYMENT),
            "source_carrier": V1.bind(V1.SOURCE, 0x08000000),
            "source_ELF": V1.bind(V1.ELF),
            "driver": V1.bind(Path(__file__).resolve()),
        },
        "corrections": {
            "v1": (
                "cross-record solver changed Slot 40's externally expected "
                "Record CRC and was rejected before execution"),
            "v2": (
                "in-record solver overwrote the live common LDA-status/RTS "
                "epilogue at $C862..$C864 and broke the success return"),
            "v3": (
                "solver bytes occupy only the unreachable third bytes behind "
                "two unconditional self-loop holds"),
        },
        "candidate": {
            "carrier": V1.bind(CARRIER, 0x08000000),
            "manifest": V1.bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "proof_shape": {
            "instrumented_error_edges": len(V1.SITES),
            "changed_file_offsets": changed,
            "carrier_bytes_delta": 0,
            "product_bytes_delta": 0,
            "success_path_byte_identical_outside_error_edges": True,
            "live_return_epilogue_byte_identical": True,
            "slot40_payload_crc_preserved": True,
            "slot40_record_byte_identical": True,
            "directory_header_byte_identical": True,
            "family_crc16_preserved": (
                f"0x{R.crc16_ccitt_false(candidate):04x}"),
            "reset_stable_C2J_baseline": V1.bind(
                V2.ZERO_C2J, 0x0005C640),
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-40 publication attribution only; "
            "require/defstruct remains unqualified."),
    })
    V1.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-deployment-v3",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": V1.bind(RECEIPT),
            "manifest": V1.bind(MANIFEST),
            "source_deployment": V1.bind(V1.BASE_DEPLOYMENT),
        },
        "product": deployment["product"],
        "media": deployment["media"],
        "remote_media": deployment["remote_media"],
        "preloads": candidate_preloads(deployment, candidate),
        "test": {
            "form": "(%disk-load-lib 39 1)",
            "hold_meaning": (
                "PC at one patched VMA identifies the first publication "
                "failure; t identifies no Slot-40 failure"),
        },
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
        "failure_edges": len(V1.SITES),
        "changed_bytes": len(changed),
    }


def verify() -> dict[str, Any]:
    source = V1.data(V1.SOURCE)
    solver, candidate = solve(source)
    require(V1.data(CARRIER) == candidate, "diagnostic carrier drift")
    receipt = V1.load(RECEIPT)
    deployment = V1.load(DEPLOYMENT)
    require(
        receipt["candidate"]["carrier"]["sha256"]
        == hashlib.sha256(candidate).hexdigest()
        and deployment["authority"]["patch_receipt"]["sha256"]
        == hashlib.sha256(V1.data(RECEIPT)).hexdigest()
        and deployment["status"]
        == "ready-authorized-nonpromotable-hardware",
        "diagnostic binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(V1.data(path)) == row["bytes"]
            and hashlib.sha256(V1.data(path)).hexdigest() == row["sha256"],
            f"diagnostic preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": hashlib.sha256(candidate).hexdigest(),
        "solver_bytes": solver.hex(),
        "failure_edges": len(V1.SITES),
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
        print(f"c2-defstruct-Link71-Slot40-hold-v3: FIRST RED: {error}")
        raise SystemExit(2)
