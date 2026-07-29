#!/usr/bin/env python3
"""Add the Slot-40 dispatcher/publish precondition hold to carrier v3."""

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
write_json = V1.write_json

OUT = V1.BASE / "slot40-failure-hold-v4-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot40-failure-hold-v4.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = V1.EVIDENCE / (
    "c2.2-link71-slot40-failure-hold-v4-nonpromotable-receipt.json")

# Both dispatcher failure paths are redirected to the existing publish
# precondition epilogue.  That epilogue is then replaced by a self-loop.
COMMON_HOLD_VMA = 0xC3F7
COMMON_BEFORE = bytes.fromhex("a5 1c")
NULL_CONTEXT_BRA_VMA = 0xC376
NULL_CONTEXT_BEFORE = bytes.fromhex("80 1f")
NULL_CONTEXT_AFTER = bytes.fromhex("80 7f")
INVALID_MARKER_BNE_VMA = 0xC38C
INVALID_MARKER_BEFORE = bytes.fromhex("d0 09")
INVALID_MARKER_AFTER = bytes.fromhex("d0 69")


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = V1.parsed(source)
    row = base.slices[V1.SLOT]
    result = bytearray(source)
    for index, (name, vma) in enumerate(V1.SITES):
        offset = V1.payload_offset(row, vma)
        require(result[offset:offset + 3] == V1.JMP_ERROR,
                f"Slot-40 edge drift: {name}")
        unreachable = (
            solver[index] if index < 2 else V3.DEFAULT_UNREACHABLE)
        result[offset:offset + 3] = (
            V3.HOLD_PREFIX + bytes([unreachable]))
    patches = (
        (COMMON_HOLD_VMA, COMMON_BEFORE, V3.HOLD_PREFIX),
        (NULL_CONTEXT_BRA_VMA, NULL_CONTEXT_BEFORE, NULL_CONTEXT_AFTER),
        (INVALID_MARKER_BNE_VMA,
         INVALID_MARKER_BEFORE, INVALID_MARKER_AFTER),
    )
    for vma, before, after in patches:
        offset = V1.payload_offset(row, vma)
        require(result[offset:offset + len(before)] == before,
                f"Slot-40 precondition patch drift at 0x{vma:04x}")
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
        require(pivot in basis, "precondition carrier CRC solver has no solution")
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
    epilogue = V1.payload_offset(row, 0xC862)
    require(candidate[epilogue:epilogue + 3] == source[epilogue:epilogue + 3],
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
    row = base.slices[V1.SLOT]
    solver, candidate = solve(source)
    V1.parsed(candidate)
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    V1.write(CARRIER, candidate)
    edge_rows = []
    for index, (name, vma) in enumerate(V1.SITES):
        offset = V1.payload_offset(row, vma)
        edge_rows.append({
            "name": name,
            "VMA": f"0x{vma:04x}",
            "file_offset": offset,
            "before": V1.JMP_ERROR.hex(),
            "after": candidate[offset:offset + 3].hex(),
            "unreachable_solver_byte": index < 2,
        })
    V1.write_json(MANIFEST, {
        "format": "lisp65-Link71-slot40-failure-hold-manifest-v4",
        "status": "ready-all-error-and-entry-precondition-hold",
        "promotable": False,
        "source": V1.bind(V1.SOURCE, 0x08000000),
        "candidate": V1.bind(CARRIER, 0x08000000),
        "error_edges": edge_rows,
        "entry_precondition_hold": {
            "VMA": f"0x{COMMON_HOLD_VMA:04x}",
            "meaning": (
                "null dispatcher context, invalid fused marker, committed=0 "
                "or nonzero publish-plan marker; ZP and phase capture "
                "distinguish them"),
        },
        "dispatcher_redirects": [
            {
                "VMA": f"0x{NULL_CONTEXT_BRA_VMA:04x}",
                "before": NULL_CONTEXT_BEFORE.hex(),
                "after": NULL_CONTEXT_AFTER.hex(),
            },
            {
                "VMA": f"0x{INVALID_MARKER_BNE_VMA:04x}",
                "before": INVALID_MARKER_BEFORE.hex(),
                "after": INVALID_MARKER_AFTER.hex(),
            },
        ],
        "solver": {
            "bytes": solver.hex(),
            "locations": [
                {
                    "site": name,
                    "VMA": f"0x{vma + 2:04x}",
                    "reachability": "unreachable behind unconditional BRA $-2",
                }
                for name, vma in V3.SOLVER_SITES
            ],
        },
    })
    V1.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-patch-v4",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-complete-Slot40-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": V1.bind(V1.BASE_DEPLOYMENT),
            "source_carrier": V1.bind(V1.SOURCE, 0x08000000),
            "source_ELF": V1.bind(V1.ELF),
            "driver": V1.bind(Path(__file__).resolve()),
        },
        "v3_result": (
            "Fresh zero-C2J hardware run returned BADOPCODE with no one of "
            "the thirteen content-error holds reached; the remaining domain "
            "is the dispatcher/export precondition envelope."),
        "candidate": {
            "carrier": V1.bind(CARRIER, 0x08000000),
            "manifest": V1.bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "proof_shape": {
            "instrumented_content_error_edges": len(V1.SITES),
            "instrumented_common_entry_precondition_edges": 4,
            "changed_file_offsets": changed,
            "carrier_bytes_delta": 0,
            "product_bytes_delta": 0,
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
            "Nonpromotable Link-71 Slot-40 attribution only; require and "
            "defstruct remain unqualified."),
    })
    V1.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-deployment-v4",
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
        "content_error_edges": len(V1.SITES),
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
        == hashlib.sha256(V1.data(RECEIPT)).hexdigest(),
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
        "content_error_edges": len(V1.SITES),
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
        print(f"c2-defstruct-Link71-Slot40-hold-v4: FIRST RED: {error}")
        raise SystemExit(2)
