#!/usr/bin/env python3
"""Build the identity-preserving, late-activated Link-71 Slot-39 hold.

The original Slot-39 carrier rebound its record and was suitable only as a
boot-time family.  Its hardware run held before rendering but never acquired
the PC.  v2 restores the original payload CRC with two bytes that are
unreachable behind self-loop holds.  Header, directory, Slot-39 record and
outer family identity therefore remain byte-identical, allowing activation
only after a pristine boot and eliminating startup/recovery ambiguity.
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
import c2_defstruct_link71_slot39_failure_hold as V1  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold as COMMON  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold_v2 as ZERO  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


HoldError = V1.HoldError
require = V1.require

OUT = V1.BASE / "slot39-failure-hold-v2-late-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot39-failure-hold-v2.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
PATCH_RECEIPT = V1.EVIDENCE / (
    "c2.2-link71-slot39-failure-hold-v2-late-nonpromotable-receipt.json")
PC_CAPTURE = OUT / "pc-captures.json"

HOLD_PREFIX = bytes.fromhex("80 fe")
DEFAULT_UNREACHABLE = 0xEA
SOLVER_SITE_NAMES = ("null-context", "active-poll")


def carrier_offset(vma: int) -> int:
    return V1.SLOT_FILE_OFFSET + vma - V1.SLOT_VMA


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = V1.parsed(source)
    row = base.slices[V1.SLOT]
    require(
        row.file_offset == V1.SLOT_FILE_OFFSET
        and row.file_size == V1.SLOT_BYTES
        and row.vma == V1.SLOT_VMA,
        "Link-71 Slot-39 geometry drift")
    result = bytearray(source)
    solver_index = 0
    for name, vma, before, after in V1.SITES:
        offset = carrier_offset(vma)
        require(result[offset:offset + len(before)] == before,
                f"Slot-39 edge drift: {name}")
        if len(after) == 3:
            unreachable = DEFAULT_UNREACHABLE
            if name in SOLVER_SITE_NAMES:
                unreachable = solver[solver_index]
                solver_index += 1
            result[offset:offset + 3] = HOLD_PREFIX + bytes([unreachable])
        else:
            result[offset:offset + 2] = HOLD_PREFIX
    require(solver_index == 2, "solver sites drift")
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
        require(pivot in basis, "Slot-39 payload solver has no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    solver = solution.to_bytes(2, "little")
    candidate = refresh(source, solver)
    require(payload_crc(candidate) == target,
            "Slot-39 payload CRC identity was not restored")
    record_offset = R.HEADER_SIZE + V1.SLOT * R.ENTRY_SIZE
    require(
        candidate[record_offset:record_offset + R.ENTRY_SIZE]
        == source[record_offset:record_offset + R.ENTRY_SIZE],
        "Slot-39 Record identity changed")
    directory_end = R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE
    require(candidate[:directory_end] == source[:directory_end],
            "directory/header identity changed")
    require(
        R.crc16_ccitt_false(candidate) == R.crc16_ccitt_false(source),
        "Session-family CRC identity was not restored")
    return solver, candidate


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    return V1.bind(path, address)


def prepare() -> dict[str, Any]:
    source, base_deployment = V1.authority()
    V1.elf_feasibility()
    solver, candidate = solve(source)
    V1.parsed(candidate)
    V1.write(CARRIER, candidate)
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    V1.write_json(MANIFEST, {
        "format": "lisp65-Link71-slot39-failure-hold-manifest-v2",
        "status": "ready-identity-preserving-late-failure-site-hold",
        "promotable": False,
        "source": bind(V1.BASE_CARRIER, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "failure_edges": [
            {
                "name": name,
                "VMA": f"0x{vma:04x}",
                "file_offset": carrier_offset(vma),
                "before": before.hex(),
                "after": candidate[
                    carrier_offset(vma):carrier_offset(vma) + len(after)
                ].hex(),
            }
            for name, vma, before, after in V1.SITES
        ],
        "solver": {
            "bytes": solver.hex(),
            "locations": [
                {
                    "site": name,
                    "VMA": f"0x{vma + 2:04x}",
                    "reachability": "unreachable behind unconditional BRA $-2",
                }
                for name, vma, _before, after in V1.SITES
                if name in SOLVER_SITE_NAMES and len(after) == 3
            ],
        },
    })
    V1.write_json(PATCH_RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot39-failure-hold-patch-v2",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-late-Slot39-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": bind(V1.BASE_DEPLOYMENT),
            "source_carrier": bind(V1.BASE_CARRIER, 0x08000000),
            "source_ELF": bind(V1.ELF),
            "v1_patch_receipt": bind(V1.PATCH_RECEIPT),
            "driver": bind(Path(__file__).resolve()),
        },
        "correction": (
            "v1 rebound the Slot-39 record and ran as a boot carrier; v2 "
            "keeps the original payload/record/directory/family identities "
            "and is activated only after a pristine boot."),
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "proof_shape": {
            "instrumented_failure_edges": len(V1.SITES),
            "changed_file_offsets": changed,
            "carrier_bytes_delta": 0,
            "product_bytes_delta": 0,
            "slot39_payload_crc_preserved": True,
            "slot39_record_byte_identical": True,
            "directory_header_byte_identical": True,
            "family_crc16_preserved":
                f"0x{R.crc16_ccitt_false(candidate):04x}",
            "reset_stable_C2J_baseline":
                bind(ZERO.ZERO_C2J, V1.C2J_ADDRESS),
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-39 failure attribution only; "
            "require/defstruct remain unqualified."),
    })
    boot_preloads = [dict(row) for row in base_deployment["preloads"]]
    require(COMMON.data(ZERO.ZERO_C2J) == bytes(64),
            "canonical zero-C2J preload drift")
    boot_preloads.append({
        **bind(ZERO.ZERO_C2J, V1.C2J_ADDRESS),
        "role": "known-zero-C2J-diagnostic-baseline",
    })
    V1.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot39-failure-hold-late-deployment-v2",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(V1.BASE_DEPLOYMENT),
        },
        "product": base_deployment["product"],
        "media": base_deployment["media"],
        "remote_media": base_deployment["remote_media"],
        "boot_preloads": boot_preloads,
        "late_preload": {
            **bind(CARRIER, 0x08000000),
            "role": "post-boot-identity-preserving-Slot39-discriminator",
        },
        "test": {"form": "(%disk-load-lib 39 1)"},
        "capture_domains": {
            "completion_record": {
                "address": f"0x{V1.RECORD_ADDRESS:08x}", "bytes": 32},
            "phase_scratch": {
                "address": f"0x{V1.PHASE_SCRATCH_ADDRESS:08x}", "bytes": 304},
            "target_C2J": {
                "address": f"0x{V1.C2J_ADDRESS:08x}", "bytes": 64},
            "runtime_slot39": {
                "address": f"0x{V1.SLOT_VMA:08x}", "bytes": V1.SLOT_BYTES},
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
    }


def verify() -> dict[str, Any]:
    source, base_deployment = V1.authority()
    solver, candidate = solve(source)
    require(V1.data(CARRIER) == candidate, "late Slot-39 carrier drift")
    receipt = V1.load(PATCH_RECEIPT)
    deployment = V1.load(DEPLOYMENT)
    require(
        deployment["authority"]["patch_receipt"]["sha256"]
        == hashlib.sha256(V1.data(PATCH_RECEIPT)).hexdigest()
        and deployment["late_preload"]["sha256"]
        == hashlib.sha256(candidate).hexdigest()
        and deployment["product"] == base_deployment["product"]
        and receipt["status"]
        == "ready-nonpromotable-late-Slot39-discriminator",
        "late Slot-39 deployment binding drift")
    for row in deployment["boot_preloads"] + [deployment["late_preload"]]:
        path = ROOT / row["path"]
        require(
            len(V1.data(path)) == row["bytes"]
            and hashlib.sha256(V1.data(path)).hexdigest() == row["sha256"],
            f"late Slot-39 artifact drift: {path}")
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
        print(f"c2-defstruct-Link71-Slot39-hold-v2: FIRST RED: {error}")
        raise SystemExit(2)
