#!/usr/bin/env python3
"""Repair the C1 diagnostic carrier's immutable Link-58 stage binding.

Link 58 binds the complete Session-family image by size and CRC-16 before it
publishes the family.  The first artifact-only C1 carrier kept the size but
changed four cold overlay payloads, so the real product correctly rejected its
different whole-image CRC before any C1 cutpoint could run.

This Class-A replay changes no product, compiler or linker output.  It extends
the diagnostic header-phase payload by two unreachable bytes after its final
RTS, refreshes the ordinary L65R-v3 catalog proofs, and solves those two bytes
so the complete diagnostic carrier has Link 58's already-published stage CRC.
The result is a separate, non-promotable harness identity.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import runtime_overlay_bank as R  # noqa: E402


LINK = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-hybrid-carrier-NONPROMOTABLE")
FIRST_RED = ROOT / "build/c2.2/c1-freezer-hardware-link58-NONPROMOTABLE"
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-hybrid-stage-bound-NONPROMOTABLE")
SOURCE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-carrier-nonpromotable-receipt.json")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-stage-binding-hardware-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-stage-bound-"
    "nonpromotable-receipt.json")

PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
SLOT = 39
SECTION = ".lisp65_rt_c2append_header"
PACK_CEILING = 768
RTS = 0x60
RTOV_FAULT = 0x0077
RTOV_FAMILY = 0x0079
C2_READY = 0x008C
EXPECTED_STAGE_ERROR = 23


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def crc16(data: bytes) -> int:
    result = binascii.crc_hqx(data, 0xFFFF)
    require(result == R.crc16_ccitt_false(data),
            "host CRC implementations disagree")
    return result


def product_stage_binding(product: Path) -> tuple[int, int]:
    data = product.read_bytes()
    require(len(data) >= 2, "Link-58 PRG is truncated")
    load = data[0] | data[1] << 8
    address = 0xB96E
    offset = 2 + address - load
    require(0 <= offset <= len(data) - 8,
            "Link-58 family-stage table lies outside PRG")
    boot_size, boot_crc, session_size, session_crc = struct.unpack_from(
        "<4H", data, offset)
    require(
        boot_size == 18935
        and boot_crc == 0xB990
        and session_size == 65438
        and session_crc == 0xD387,
        "Link-58 family-stage binding drift")
    return session_size, session_crc


def refresh(image: bytes, word: int, parsed: R.ParsedBank) -> bytes:
    """Extend slot 39 by one u16 and refresh every dependent L65R proof."""
    require(0 <= word <= 0xFFFF, "tail word is outside u16")
    row = parsed.slices[SLOT]
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    data = bytearray(image)
    fields = list(R.ENTRY.unpack_from(data, record_offset))
    require(
        fields[0] == SLOT
        and fields[2] == row.file_offset
        and fields[3] == row.file_size
        and fields[5] == row.file_size,
        "diagnostic header record drift")
    old_size = fields[3]
    new_size = old_size + 2
    next_offset = parsed.slices[SLOT + 1].file_offset
    require(
        new_size <= PACK_CEILING
        and row.file_offset + new_size < next_offset
        and data[row.file_offset + old_size - 1] == RTS
        and not any(data[row.file_offset + old_size:next_offset]),
        "slot 39 has no proved post-RTS tail capacity")
    data[
        row.file_offset + old_size:row.file_offset + new_size
    ] = word.to_bytes(2, "little")
    fields[3] = new_size
    fields[5] = new_size
    fields[9] = crc16(data[row.file_offset:row.file_offset + new_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = crc16(raw_record)
    require(fields[10] != 0, "derived L65R-v3 record CRC is forbidden zero")
    data[
        record_offset:record_offset + R.ENTRY_SIZE
    ] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", data, 24, crc16(data[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", data, 26, 0)
    struct.pack_into("<H", data, 26, crc16(data[:R.HEADER_SIZE]))
    return bytes(data)


def solve_tail(image: bytes, parsed: R.ParsedBank, target: int) -> tuple[int, bytes]:
    """Solve the affine two-byte tail -> whole-image CRC map over GF(2)."""
    baseline = crc16(refresh(image, 0, parsed))
    columns = [
        crc16(refresh(image, 1 << bit, parsed)) ^ baseline
        for bit in range(16)
    ]
    basis: dict[int, tuple[int, int]] = {}
    for bit, column in enumerate(columns):
        vector = column
        mask = 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                old_vector, old_mask = basis[pivot]
                vector ^= old_vector
                mask ^= old_mask
            else:
                basis[pivot] = (vector, mask)
                break
    vector = target ^ baseline
    solution = 0
    while vector:
        pivot = vector.bit_length() - 1
        require(pivot in basis, "stage CRC has no two-byte tail solution")
        old_vector, old_mask = basis[pivot]
        vector ^= old_vector
        solution ^= old_mask
    result = refresh(image, solution, parsed)
    require(crc16(result) == target, "stage-bound carrier CRC solve failed")
    return solution, result


def validate_first_red(product: Path, source_image: Path) -> dict[str, Any]:
    required = {
        "bank0": FIRST_RED / "boot-bank0.bin",
        "bank2": FIRST_RED / "boot-bank2.bin",
        "bank3": FIRST_RED / "boot-bank3.bin",
        "bank5": FIRST_RED / "boot-bank5.bin",
        "screen": FIRST_RED / "boot-first-red.png",
        "screen_text": FIRST_RED / "boot-first-red.ansi.txt",
        "session_readback":
            FIRST_RED /
            "deploy-readback-runtime-overlays-session-c1-freezer.bin",
    }
    for name, path in required.items():
        require(path.is_file(), f"missing first-red {name}: {path}")
    low = required["bank0"].read_bytes()
    require(
        len(low) == 65536
        and low[RTOV_FAULT] == EXPECTED_STAGE_ERROR
        and low[RTOV_FAMILY] == 0
        and low[C2_READY] == 0
        and required["session_readback"].read_bytes() ==
            source_image.read_bytes(),
        "hardware First Red is not the expected pre-publication stage reject")
    return {
        "format": "lisp65-c2.2-C1-Freezer-stage-binding-first-red-v1",
        "status": "first-red-harness-stage-binding-no-C1-cutpoint-reached",
        "promotable": False,
        "product": bind(product),
        "diagnostic_carrier": bind(source_image),
        "hardware": {
            "boots": 1,
            "rtov_fault": EXPECTED_STAGE_ERROR,
            "rtov_fault_name": "VM_RUNTIME_OVERLAY_ERR_FAMILY_STAGE",
            "rtov_family": 0,
            "c2_ready": 0,
            "screen": "E3e runtime family staging failed; redeploy",
            "latency_attempts_consumed": 0,
            "C1_cutpoints_reached": 0,
        },
        "captures": {name: bind(path) for name, path in required.items()},
        "diagnosis": {
            "link58_expected_session_size": 65438,
            "link58_expected_session_crc16": "0xd387",
            "diagnostic_session_size": source_image.stat().st_size,
            "diagnostic_session_crc16": f"0x{crc16(source_image.read_bytes()):04x}",
            "cause": (
                "The artifact-only carrier replaced four overlay payloads but "
                "retained Link 58's immutable resident whole-family stage "
                "binding. The product correctly rejected the new outer CRC "
                "before Session publication."),
        },
        "claim_limit": (
            "Harness First Red only. No product defect, C1 result, promotion, "
            "acceptance-chain result or release claim."),
        "next_gate": (
            "Class-A stage-binding replay, then separate authorization for "
            "a new qualified C1 hardware run"),
    }


def main() -> int:
    require(
        not OUT.exists()
        and not RECEIPT.exists()
        and not FIRST_RED_RECEIPT.exists(),
        "C1 stage-binding replay is one-shot")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    base_manifest_path = LINK / "runtime-overlays-session-final.json"
    source_image = SOURCE / "runtime-overlays-session-c1-freezer.bin"
    source_manifest_path = SOURCE / "runtime-overlays-session-c1-freezer.json"
    for path in (
            product, base_manifest_path, source_image, source_manifest_path,
            SOURCE_RECEIPT):
        require(path.is_file(), f"missing replay authority: {path}")
    require(sha(product) == PRODUCT_SHA, "immutable Link-58 identity drift")
    source_receipt = read_json(SOURCE_RECEIPT)
    source_manifest = read_json(source_manifest_path)
    base_manifest = read_json(base_manifest_path)
    require(
        source_receipt["status"] ==
            "passed-nonpromotable-carrier-hardware-not-run"
        and source_manifest["status"] ==
            "passed-artifact-only-nonpromotable-carrier"
        and source_manifest["affected_slices"][SECTION]["payload_bytes"] == 644,
        "source C1 carrier authority drift")
    first_red = validate_first_red(product, source_image)

    size, target_crc = product_stage_binding(product)
    image = source_image.read_bytes()
    require(
        len(image) == size
        and crc16(image) == int(source_manifest["storage"]["crc16"])
        and crc16(image) != target_crc
        and int(base_manifest["storage"]["size"]) == size
        and int(base_manifest["storage"]["crc16"]) == target_crc,
        "outer stage-binding diagnosis drift")
    build_id = int(source_manifest["profile_build_id"])
    parsed = R.validate_image(
        image,
        expected_build_id=build_id,
        expected_vma=0xC356,
        max_slice_bytes=1792,
        format_version=3,
    )
    tail_word, stage_bound = solve_tail(image, parsed, target_crc)
    verified = R.validate_image(
        stage_bound,
        expected_build_id=build_id,
        expected_vma=0xC356,
        max_slice_bytes=1792,
        format_version=3,
    )
    old_row = parsed.slices[SLOT]
    new_row = verified.slices[SLOT]
    old_payload = image[
        old_row.file_offset:old_row.file_offset + old_row.file_size]
    new_payload = stage_bound[
        new_row.file_offset:new_row.file_offset + new_row.file_size]
    require(
        new_payload[:-2] == old_payload
        and old_payload[-1] == RTS
        and new_payload[-2:] == tail_word.to_bytes(2, "little")
        and new_row.file_size == old_row.file_size + 2
        and new_row.file_size == 646
        and PACK_CEILING - new_row.file_size == 122,
        "stage-bound tail escaped the proved post-RTS extension")
    changed = [
        index for index, (before, after) in
        enumerate(zip(image, stage_bound)) if before != after
    ]
    require(len(changed) == 12, "stage-bound carrier changed unexpected bytes")

    mutations = []
    for name, mutated in (
        ("tail-low", tail_word ^ 0x0001),
        ("tail-high", tail_word ^ 0x0100),
    ):
        candidate = refresh(image, mutated, parsed)
        require(crc16(candidate) != target_crc,
                f"{name} mutation retained the stage CRC")
        mutations.append(name)
    require(
        crc16(stage_bound[:-1]) != target_crc
        and crc16(image) != target_crc,
        "missing-tail or unbound-source mutation retained the stage CRC")
    mutations.extend(("missing-tail", "unbound-source"))

    OUT.mkdir(parents=True)
    image_out = OUT / "runtime-overlays-session-c1-freezer-stage-bound.bin"
    manifest_out = OUT / "runtime-overlays-session-c1-freezer-stage-bound.json"
    image_out.write_bytes(stage_bound)
    manifest = {
        "format": "lisp65-C1-Freezer-hybrid-stage-bound-family-v1",
        "status": "passed-class-a-stage-binding-replay-hardware-not-run",
        "promotable": False,
        "profile": source_manifest["profile"],
        "profile_build_id": build_id,
        "storage": {
            "bytes": len(stage_bound),
            "headroom_bytes": 65536 - len(stage_bound),
            "sha256": sha(image_out),
            "crc16": crc16(stage_bound),
        },
        "outer_link58_stage_binding": {
            "size": size,
            "crc16": target_crc,
            "match": True,
        },
        "tail_extension": {
            "slot": SLOT,
            "section": SECTION,
            "old_file_size": old_row.file_size,
            "new_file_size": new_row.file_size,
            "bytes": tail_word.to_bytes(2, "little").hex(),
            "position": "immediately after final RTS",
            "execution_role": "unreachable-inert-diagnostic-carrier-tail",
            "pack_ceiling_bytes": PACK_CEILING,
            "headroom_bytes": PACK_CEILING - new_row.file_size,
        },
        "catalog": {
            "version": 3,
            "slice_count": len(verified.slices),
            "directory_crc16": verified.directory_crc16,
            "header_crc16": verified.header_crc16,
        },
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    FIRST_RED_RECEIPT.write_text(
        json.dumps(first_red, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": "lisp65-c2.2-C1-Freezer-stage-binding-replay-receipt-v1",
        "status": "passed-class-a-replay-awaiting-new-hardware-authorization",
        "promotable": False,
        "authority": {
            "immutable_link58_product": bind(product),
            "source_carrier": bind(source_image),
            "source_carrier_receipt": bind(SOURCE_RECEIPT),
            "hardware_first_red": bind(FIRST_RED_RECEIPT),
        },
        "artifacts": {
            "session_family": bind(image_out),
            "manifest": bind(manifest_out),
        },
        "construction": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
            "session_family_size_delta": 0,
            "slice_payload_prefixes_changed": 0,
            "diagnostic_tail_bytes_added": 2,
            "catalog_proofs_refreshed": [
                "payload CRC", "record CRC", "directory CRC", "header CRC"],
            "whole_family_crc16": f"0x{target_crc:04x}",
            "whole_family_binding": "byteexact-Link58-stage-binding",
        },
        "proof": {
            "tail_predecessor_opcode": "0x60 RTS",
            "tail_word": f"0x{tail_word:04x}",
            "tail_bytes_little_endian": tail_word.to_bytes(2, "little").hex(),
            "changed_image_bytes": len(changed),
            "L65R_v3_validation": "passed",
            "mutations_rejected": mutations,
        },
        "execution_accounting": {
            "failed_hardware_boots_recorded": 1,
            "qualified_C1_hardware_runs": 0,
            "C1_cutpoints_reached": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Class-A harness correction only. The artifact is non-promotable "
            "and makes no C1, product, promotion or acceptance-chain claim."),
        "next_gate": (
            "separate authorization for one fresh qualified hardware run; "
            "the failed deployment identity must not be reused"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (
            image_out, manifest_out, FIRST_RED_RECEIPT, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-stage-binding-replay: PASS "
        f"product={PRODUCT_SHA} source_crc=0x{crc16(image):04x} "
        f"bound_crc=0x{crc16(stage_bound):04x} "
        f"tail={tail_word.to_bytes(2, 'little').hex()} "
        "compiler=0 linker=0 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ReplayError, R.OverlayBankError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-stage-binding-replay: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
