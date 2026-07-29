#!/usr/bin/env python3
"""Build a nonpromotable Link-71 Slot-40 error-edge hold carrier.

The Link-71 hardware postmortem was initially attributed to Slot 39 because
the phase trace ended in 0x27/0x81.  That pair is written by the first
rollback phase.  The preserved append state has committed=1, and the earlier
Slot-39 all-error-edge carrier reached its success edge.  This carrier
therefore instruments only the distinct, reachable publication failures in
Slot 40.  A success run remains executable: the outer-family CRC solver lives
in rollback-finalize, which is unreachable unless the instrumented path has
already stopped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = ROOT / "build/post-promotion/link71-defstruct-header-crc-domain"
FINAL = BASE / "final"
SOURCE = FINAL / "runtime-overlays-session-final.bin"
OVERFLOW = FINAL / "runtime-overlays-session-final-region1.bin"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
OUT = BASE / "slot40-failure-hold-NONPROMOTABLE"
CARRIER = OUT / "runtime-overlays-session-link71-slot40-failure-hold.bin"
MANIFEST = OUT / "manifest.json"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = EVIDENCE / (
    "c2.2-link71-slot40-failure-hold-nonpromotable-receipt.json")

SLOT = 40
SLOT_VMA = 0xC356
SLOT_FILE_OFFSET = 56576
SLOT_BYTES = 1295
SOLVER_SLOT = 45
SOLVER_FILE_OFFSET = 58880
SOLVER_VMA = 0xC385
SOLVER_BEFORE = bytes.fromhex("a2 08")
MAIN_SOURCE_BASE = 0x00030000
OVERFLOW_SOURCE_BASE = 0x0005BD00

# Each three-byte JMP is a semantically distinct error edge in the linked
# c2_append_publish_exports_phase.  BRA $-2 + NOP freezes before the common
# epilogue and before rollback can overwrite the primary phase provenance.
# The two entry preconditions are intentionally not patched: committed=1 is
# captured on hardware and the immediately preceding resolve phase owns the
# plan-marker clear.  A rendered error rather than a hold therefore remains
# a precise precondition discriminator.
SITES: tuple[tuple[str, int], ...] = (
    ("first-pass-c2d-read", 0xC49E),
    ("first-pass-symbol-domain", 0xC4A7),
    ("first-pass-symbol-tag", 0xC4B2),
    ("first-pass-symbol-high-domain", 0xC4BB),
    ("first-pass-reserved-tag-bits", 0xC4C7),
    ("first-pass-entry-ordinal-range", 0xC4CF),
    ("first-pass-row6-nonzero", 0xC4D8),
    ("first-pass-row7-nonzero", 0xC4F1),
    ("second-pass-plan-marker", 0xC53D),
    ("second-pass-c2d-read", 0xC567),
    ("rollback-journal-write", 0xC5BE),
    ("macro-allocation-nil", 0xC734),
    ("macro-allocation-oom", 0xC5EB),
)
JMP_ERROR = bytes.fromhex("4c f7 c3")
HOLD = bytes.fromhex("80 fe ea")


class HoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HoldError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent: {path}")
    return path.read_bytes()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(data(path) == value, f"generated artifact differs: {path}")
    else:
        path.write_bytes(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def parsed(image: bytes) -> R.ParsedBank:
    build_id = R.HEADER.unpack_from(image)[8]
    return R.validate_region_images(
        image, data(OVERFLOW),
        expected_build_id=build_id,
        expected_vma=SLOT_VMA,
        max_slice_bytes=1792,
        format_version=R.VERSION_V4,
        main_source_base=MAIN_SOURCE_BASE,
        overflow_source_base=OVERFLOW_SOURCE_BASE,
    )


def payload_offset(row: R.ParsedSlice, vma: int) -> int:
    return row.file_offset + vma - row.vma


def rebind_record(result: bytearray, base: R.ParsedBank, slot: int) -> None:
    row = base.slices[slot]
    record_offset = R.HEADER_SIZE + slot * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw)
    require(fields[10] != 0, f"Slot {slot} derived record CRC is zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)


def refresh(source: bytes, solver: bytes) -> bytes:
    require(len(solver) == 2, "solver width drift")
    base = parsed(source)
    slot = base.slices[SLOT]
    solver_slot = base.slices[SOLVER_SLOT]
    require(
        (slot.file_offset, slot.file_size, slot.vma)
            == (SLOT_FILE_OFFSET, SLOT_BYTES, SLOT_VMA)
        and solver_slot.file_offset == SOLVER_FILE_OFFSET
        and solver_slot.vma == SLOT_VMA,
        "Link-71 diagnostic geometry drift")
    result = bytearray(source)
    for name, vma in SITES:
        offset = payload_offset(slot, vma)
        require(result[offset:offset + 3] == JMP_ERROR,
                f"Slot-40 edge drift: {name}")
        result[offset:offset + 3] = HOLD
    solver_offset = payload_offset(solver_slot, SOLVER_VMA)
    require(result[solver_offset:solver_offset + 2] == SOLVER_BEFORE,
            "rollback-only solver bytes drift")
    result[solver_offset:solver_offset + 2] = solver
    rebind_record(result, base, SLOT)
    rebind_record(result, base, SOLVER_SLOT)
    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26,
        R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    return bytes(result)


def solve(source: bytes) -> tuple[bytes, bytes]:
    target = R.crc16_ccitt_false(source)
    baseline = R.crc16_ccitt_false(refresh(source, b"\0\0"))
    columns = [
        R.crc16_ccitt_false(
            refresh(source, (1 << bit).to_bytes(2, "little"))) ^ baseline
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
        require(pivot in basis, "two-byte family CRC solver has no solution")
        vector ^= basis[pivot][0]
        solution ^= basis[pivot][1]
    solver = solution.to_bytes(2, "little")
    candidate = refresh(source, solver)
    require(R.crc16_ccitt_false(candidate) == target,
            "outer Session-family CRC was not restored")
    return solver, candidate


def prepare() -> dict[str, Any]:
    source = data(SOURCE)
    deployment = load(BASE_DEPLOYMENT)
    require(
        deployment["product"]["sha256"]
            == "969047cb8116bb77510a0b75454053b765f74aedc482de287f3837db9a8a972e"
        and any(row["role"] == "c2-session-family-region-0"
                and row["sha256"] == sha_bytes(source)
                for row in deployment["preloads"]),
        "Link-71 deployment authority drift")
    base = parsed(source)
    solver, candidate = solve(source)
    parsed(candidate)
    require(len(candidate) == len(source), "carrier size changed")
    changed = [
        offset for offset, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]
    ]
    write(CARRIER, candidate)
    patch_rows = [
        {
            "name": name,
            "VMA": f"0x{vma:04x}",
            "file_offset": payload_offset(base.slices[SLOT], vma),
            "before": JMP_ERROR.hex(),
            "after": HOLD.hex(),
        }
        for name, vma in SITES
    ]
    write_json(MANIFEST, {
        "format": "lisp65-Link71-slot40-failure-hold-manifest-v1",
        "status": "ready-nonpromotable-publication-error-edge-hold",
        "promotable": False,
        "source": bind(SOURCE, 0x08000000),
        "candidate": bind(CARRIER, 0x08000000),
        "error_edges": patch_rows,
        "solver": {
            "slot": SOLVER_SLOT,
            "VMA": f"0x{SOLVER_VMA:04x}",
            "bytes": solver.hex(),
            "lifetime": (
                "rollback-finalize only; unreachable after Slot-40 hold and "
                "unreachable on the successful persistent plan"),
        },
    })
    write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-patch-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-Slot40-publication-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": bind(BASE_DEPLOYMENT),
            "source_carrier": bind(SOURCE, 0x08000000),
            "source_ELF": bind(ELF),
            "driver": bind(Path(__file__).resolve()),
        },
        "candidate": {
            "carrier": bind(CARRIER, 0x08000000),
            "manifest": bind(MANIFEST),
            "lifecycle": "discard after one diagnostic outcome",
        },
        "proof_shape": {
            "instrumented_error_edges": len(SITES),
            "entry_preconditions_instrumented": 0,
            "entry_preconditions_excluded_by": [
                "hardware append-state committed=1",
                "publish-plan-resolve owns the immediately preceding "
                "plan-marker clear",
            ],
            "success_path_bytes_changed": 0,
            "rollback_only_solver_bytes": 2,
            "changed_file_offsets": changed,
            "carrier_bytes_delta": 0,
            "product_bytes_delta": 0,
            "family_crc16_preserved": (
                f"0x{R.crc16_ccitt_false(candidate):04x}"),
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-40 publication attribution only; "
            "require/defstruct remains unqualified."),
    })
    preloads: list[dict[str, Any]] = []
    replaced = 0
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **bind(CARRIER, int(copy["address"], 16)),
                "role": copy["role"],
            }
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "diagnostic carrier replacement is not unique")
    write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-deployment-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(RECEIPT),
            "manifest": bind(MANIFEST),
            "source_deployment": bind(BASE_DEPLOYMENT),
        },
        "product": deployment["product"],
        "media": deployment["media"],
        "remote_media": deployment["remote_media"],
        "preloads": preloads,
        "test": {
            "form": "(%disk-load-lib 39 1)",
            "hold_meaning": (
                "PC at one patched VMA identifies the publication failure; "
                "rendered bad-bytecode identifies an entry precondition; "
                "t identifies no Slot-40 failure"),
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
    })
    return {
        "status": "ready",
        "carrier_sha256": sha_bytes(candidate),
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
        "failure_edges": len(SITES),
        "changed_bytes": len(changed),
    }


def verify() -> dict[str, Any]:
    source = data(SOURCE)
    solver, candidate = solve(source)
    require(data(CARRIER) == candidate, "diagnostic carrier drift")
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    require(
        receipt["candidate"]["carrier"]["sha256"] == sha_bytes(candidate)
        and deployment["authority"]["patch_receipt"]["sha256"]
            == sha_bytes(data(RECEIPT))
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware",
        "diagnostic binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(data(path)) == row["bytes"]
            and sha_bytes(data(path)) == row["sha256"],
            f"diagnostic preload drift: {path}")
    return {
        "status": "verified",
        "carrier_sha256": sha_bytes(candidate),
        "solver_bytes": solver.hex(),
        "failure_edges": len(SITES),
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
        print(f"c2-defstruct-Link71-Slot40-hold: FIRST RED: {error}")
        raise SystemExit(2)
