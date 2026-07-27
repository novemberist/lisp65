#!/usr/bin/env python3
"""Bind the four C1 cutpoint overlays to immutable Link 60.

The diagnostic WPLTO identity supplies only four cold region-0 payloads.
Structured ELF relocations are rebound to the deployed Link-60 resident
identity, region 1 remains byte-identical, and an unreachable two-byte tail
restores Link 60's already-published main-family CRC.  No compiler, linker,
product or hardware action occurs here.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_c1_freezer_hybrid_carrier as H  # noqa: E402
import c2_c1_freezer_link58_relocation_replay as X  # noqa: E402
import c2_c1_freezer_stage_binding_replay as S  # noqa: E402
import c2_c1_freezer_cutpoint_build_link60 as DONOR_BUILD  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / (
    "build/c2.2/substitution/product-link-60-two-region-e000-s1-completion")
DONOR = DONOR_BUILD.OUT
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-rebound-stage-bound-NONPROMOTABLE")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link60-two-region-e000-s1-structural-receipt.json")
LINK_RECEIPT_STATUS = (
    "passed-link60-two-region-E000-S1-product-identity-hardware-not-run")
DONOR_RECEIPT = DONOR_BUILD.RECEIPT
DONOR_RECEIPT_STATUS = (
    "passed-nonpromotable-Link60-C1-overlay-donor-hardware-not-run")
CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
SOURCE_GATE = DONOR / "c1-freezer-cutpoint-source-gate.json"
RECEIPT = EVIDENCE / (
    "c2.2-link60-c1-freezer-carrier-nonpromotable-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PRODUCT_SHA = (
    "7fc3bb84acf6039ea34ff863ba4f6d39458400a7848ae7077a8085ccd9cf2416")
EXPECTED_SESSION_CRC: int | None = 0x7753
OVERFLOW_SHA = (
    "38e5771ab7f6840d487715d473a63b8e3ea268a23c6993928be7535152ad7b6b")
TABLE_BASE = 0xB972
STAGE_TUPLE = TABLE_BASE + 32
FORMAT_VERSION = 4
MAIN_BYTES = 64926
OVERFLOW_BYTES = 1956
HEADER_TAIL_SLOT = 39
HEADER_PACK_CEILING = 1536
TAIL_BYTES: int | None = 2
TAIL_MAX_BYTES = 9
AFFECTED = DONOR_BUILD.AFFECTED


class CarrierError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CarrierError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Link-60 C1 carrier artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def payload(image: bytes, row: dict[str, Any]) -> bytes:
    start = int(row["file_offset"])
    end = start + int(row["file_size"])
    require(0 <= start < end <= len(image),
            f"payload outside its region: {row['section']}")
    result = image[start:end]
    require(hashlib.sha256(result).hexdigest() == row["sha256"],
            f"manifest payload SHA drift: {row['section']}")
    return result


def extracted(row: dict[str, Any], data: bytes) -> R.ExtractedSlice:
    require(row["entry"] is not None,
            "C1 carrier accepts executable slices only")
    spec = R.SliceSpec(
        id=int(row["id"]),
        name=str(row["name"]),
        section=str(row["section"]),
        start_symbol=str(row["start_symbol"]),
        end_symbol=str(row["end_symbol"]),
        entry_symbol=str(row["entry_symbol"]),
        flags=int(row["flags"]),
        abi_version=int(row["abi_version"]),
        capability_mask=0,
        region_id=int(row["region_id"]),
    )
    vma = int(row["vma"])
    entry = int(row["entry"])
    return R.ExtractedSlice(spec, vma, vma + len(data), entry, data)


def stage_binding(product: Path) -> tuple[int, int, dict[str, Any]]:
    data = product.read_bytes()
    require(len(data) >= 2, "Link-60 PRG is truncated")
    load = int.from_bytes(data[:2], "little")
    offset = 2 + STAGE_TUPLE - load
    require(0 <= offset <= len(data) - 8,
            "Link-60 family-stage tuple lies outside PRG")
    boot_size, boot_crc, session_size, session_crc = struct.unpack_from(
        "<4H", data, offset)
    boot_manifest = read_json(
        product.parent / "runtime-overlays-boot-final.json")
    boot_storage = boot_manifest["storage"]
    session_storage = read_json(
        product.parent / "runtime-overlays-session-final.json")["storage"]
    require(
        (boot_size, boot_crc, session_size, session_crc)
        == (int(boot_storage["size"]), int(boot_storage["crc16"]),
            int(session_storage["size"]), int(session_storage["crc16"]))
        and (
            EXPECTED_SESSION_CRC is None
            or session_crc == EXPECTED_SESSION_CRC
        ),
        "Link-60 family-stage tuple drift")
    return session_size, session_crc, {
        "address": f"0x{STAGE_TUPLE:04x}",
        "boot_size": boot_size,
        "boot_crc16": f"0x{boot_crc:04x}",
        "session_size": session_size,
        "session_crc16": f"0x{session_crc:04x}",
    }


def rebind_payloads(
        diagnostic: ElfTruth, base: ElfTruth,
        original: dict[str, bytes],
) -> tuple[dict[str, bytes], list[dict[str, Any]], int, int]:
    """Rebind every structured external relocation, without a stale list."""
    result = {name: bytearray(data) for name, data in original.items()}
    changed: list[dict[str, Any]] = []
    internal = 0
    external_equal = 0
    for row in diagnostic.relocations:
        if row.source_section not in result:
            continue
        section = diagnostic.section(row.source_section)
        symbol = diagnostic.symbols[row.target_symbol_index]
        index = row.offset - section.address
        old_encoded = X.encoded(
            result[row.source_section], index, row.relocation_type)
        expected_old = X.projected(
            symbol.value + row.addend, row.relocation_type)
        require(
            old_encoded == expected_old,
            "donor payload no longer encodes its ELF relocation: "
            f"{row.source_section}+0x{index:x} {row.target}")
        if symbol.section == row.source_section:
            internal += 1
            continue
        name, old, new = X.link58_target(diagnostic, base, row)
        if old == new:
            external_equal += 1
            continue
        X.patch_value(
            result[row.source_section], index, row.relocation_type, new)
        changed.append({
            "section": row.source_section,
            "section_offset": index,
            "relocation_offset": row.offset,
            "relocation_type": row.relocation_type,
            "identity": name,
            "donor_value": old,
            "link60_value": new,
            "donor_encoded": expected_old,
            "link60_encoded": X.projected(new, row.relocation_type),
        })
    require(
        external_equal + len(changed) > 0,
        "diagnostic donor has no structured external relocations")
    identities = {
        (row["section"], row["section_offset"], row["relocation_type"])
        for row in changed
    }
    require(len(identities) == len(changed),
            "duplicate structured relocation identity in donor")
    rebound = {name: bytes(data) for name, data in result.items()}
    validate_rebound(rebound, changed)
    return rebound, changed, internal, external_equal


def validate_rebound(
        payloads: dict[str, bytes], changed: list[dict[str, Any]],
) -> None:
    for row in changed:
        actual = X.encoded(
            payloads[row["section"]], row["section_offset"],
            row["relocation_type"])
        require(
            actual == row["link60_encoded"],
            f"Link-60 relocation binding absent: {row['identity']}")


def refresh_tail(
        image: bytes, tail: bytes, parsed: R.ParsedBank) -> bytes:
    """Bind an unreachable post-RTS tail of arbitrary small width."""
    require(tail, "diagnostic carrier tail is empty")
    row = parsed.slices[HEADER_TAIL_SLOT]
    record_offset = R.HEADER_SIZE + HEADER_TAIL_SLOT * R.ENTRY_SIZE
    data = bytearray(image)
    fields = list(R.ENTRY.unpack_from(data, record_offset))
    old_size = fields[3]
    new_size = old_size + len(tail)
    next_offset = parsed.slices[HEADER_TAIL_SLOT + 1].file_offset
    require(
        fields[0] == HEADER_TAIL_SLOT
        and fields[2] == row.file_offset
        and fields[3] == row.file_size
        and fields[5] == row.file_size
        and new_size <= HEADER_PACK_CEILING
        and row.file_offset + new_size < next_offset
        and data[row.file_offset + old_size - 1] == S.RTS
        and not any(data[row.file_offset + old_size:next_offset]),
        "header slot has no proved post-RTS tail capacity")
    data[row.file_offset + old_size:row.file_offset + new_size] = tail
    fields[3] = new_size
    fields[5] = new_size
    fields[9] = S.crc16(
        data[row.file_offset:row.file_offset + new_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = S.crc16(raw_record)
    require(fields[10] != 0, "derived v4 record CRC is forbidden zero")
    data[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)
    directory_end = R.HEADER_SIZE + len(parsed.slices) * R.ENTRY_SIZE
    struct.pack_into(
        "<H", data, 24,
        S.crc16(data[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", data, 26, 0)
    struct.pack_into("<H", data, 26, S.crc16(data[:R.HEADER_SIZE]))
    return bytes(data)


def solve_tail(
        image: bytes, parsed: R.ParsedBank, target: int,
        width: int) -> tuple[int, bytes]:
    """Solve a width-byte affine tail -> complete-family CRC map."""
    require(2 <= width <= 8, "diagnostic carrier tail width out of range")
    baseline = S.crc16(refresh_tail(image, bytes(width), parsed))
    columns = [
        S.crc16(refresh_tail(
            image, (1 << bit).to_bytes(width, "little"), parsed))
        ^ baseline
        for bit in range(width * 8)
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
        require(
            pivot in basis,
            "stage CRC has no bounded tail solution "
            f"(width={width}, rank={len(basis)}, residual=0x{vector:04x})")
        old_vector, old_mask = basis[pivot]
        vector ^= old_vector
        solution ^= old_mask
    result = refresh_tail(
        image, solution.to_bytes(width, "little"), parsed)
    require(S.crc16(result) == target,
            "stage-bound carrier CRC solve failed")
    return solution, result


def solve_smallest_tail(
        image: bytes, parsed: R.ParsedBank, target: int,
) -> tuple[int, bytes, int]:
    """Use the historical fixed width or the smallest feasible width."""
    if TAIL_BYTES is not None:
        solution, result = solve_tail(
            image, parsed, target, TAIL_BYTES)
        return solution, result, TAIL_BYTES
    failures: list[str] = []
    for width in range(2, TAIL_MAX_BYTES + 1):
        try:
            solution, result = solve_tail(
                image, parsed, target, width)
        except CarrierError as error:
            failures.append(str(error))
            continue
        return solution, result, width
    raise CarrierError(
        "no post-RTS tail width can bind the stage CRC: "
        + "; ".join(failures))


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-60 C1 carrier is one-shot")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    base_elf = Path(str(product) + ".elf")
    donor_elf = DONOR / "lisp65-c2-substitution-linked.prg.elf"
    base_main_path = LINK / "runtime-overlays-session-final.bin"
    base_overflow_path = LINK / "runtime-overlays-session-final-region1.bin"
    base_manifest_path = LINK / "runtime-overlays-session-final.json"
    base_header_path = LINK / "runtime-overlay-session-final.h"
    donor_main_path = DONOR / "runtime-overlays-session-final.bin"
    donor_overflow_path = (
        DONOR / "runtime-overlays-session-final-region1.bin")
    donor_manifest_path = DONOR / "runtime-overlays-session-final.json"
    authorities = (
        product, base_elf, donor_elf, base_main_path, base_overflow_path,
        base_manifest_path, base_header_path, donor_main_path,
        donor_overflow_path, donor_manifest_path, LINK_RECEIPT,
        DONOR_RECEIPT, CONTRACT, SOURCE_GATE, LLVM_READOBJ,
    )
    for path in authorities:
        require(path.is_file(), f"missing Link-60 carrier authority: {path}")
    link_receipt = read_json(LINK_RECEIPT)
    donor_receipt = read_json(DONOR_RECEIPT)
    source_gate = read_json(SOURCE_GATE)
    require(
        sha(product) == PRODUCT_SHA
        and link_receipt["status"] == LINK_RECEIPT_STATUS
        and donor_receipt["status"] == DONOR_RECEIPT_STATUS
        and source_gate["source"]["product_bytes"] == 0
        and len(source_gate["mutations_rejected"]) == 10
        and sha(base_overflow_path) == sha(donor_overflow_path)
        == OVERFLOW_SHA,
        "Link-60 carrier authority is incomplete")

    base_manifest = read_json(base_manifest_path)
    donor_manifest = read_json(donor_manifest_path)
    base_rows = H.rows_by_id(base_manifest)
    donor_rows = H.rows_by_id(donor_manifest)
    require(
        set(base_rows) == set(donor_rows) == set(range(51))
        and base_manifest["catalog"]["version"]
        == donor_manifest["catalog"]["version"] == FORMAT_VERSION,
        "Session catalog is not the expected dense L65R-v4 family")
    base_main = base_main_path.read_bytes()
    base_overflow = base_overflow_path.read_bytes()
    donor_main = donor_main_path.read_bytes()

    base_truth = ElfTruth.read(
        base_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    donor_truth = ElfTruth.read(
        donor_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    original = {
        section: payload(donor_main, donor_rows[slot])
        for slot, section in AFFECTED.items()
    }
    for section, data in original.items():
        require(donor_truth.section_bytes(section) == data,
                f"donor ELF/catalog payload drift: {section}")
    rebound, changed, internal_count, external_equal = rebind_payloads(
        donor_truth, base_truth, original)

    mutations: list[str] = []
    for row in changed:
        mutated = dict(rebound)
        data = bytearray(mutated[row["section"]])
        X.patch_value(
            data, row["section_offset"], row["relocation_type"],
            row["donor_value"])
        mutated[row["section"]] = bytes(data)
        try:
            validate_rebound(mutated, changed)
        except CarrierError:
            mutations.append(
                f"{row['section']}:{row['identity']}:donor-target")
        else:
            raise CarrierError(
                f"reverted relocation survived: {row['identity']}")

    slices: list[R.ExtractedSlice] = []
    provenance: list[dict[str, Any]] = []
    for slot in range(51):
        base_row = base_rows[slot]
        donor_row = donor_rows[slot]
        require(
            base_row["section"] == donor_row["section"]
            and base_row["vma"] == donor_row["vma"]
            and base_row["entry_offset"] == donor_row["entry_offset"]
            and base_row["flags"] == donor_row["flags"]
            and base_row["abi_version"] == donor_row["abi_version"]
            and base_row["region_id"] == donor_row["region_id"],
            f"slice ABI/region drift at slot {slot}")
        if slot in AFFECTED:
            data = rebound[str(donor_row["section"])]
            chosen = donor_row
            source = "Link60-C1-donor-ELF-rebound"
        else:
            region = (
                base_main if int(base_row["region_id"]) == 0
                else base_overflow)
            data = payload(region, base_row)
            chosen = base_row
            source = (
                "Link60-region0-byteidentical"
                if int(base_row["region_id"]) == 0
                else "Link60-region1-byteidentical")
        slices.append(extracted(chosen, data))
        provenance.append({
            "id": slot,
            "section": chosen["section"],
            "region_id": int(chosen["region_id"]),
            "source": source,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    build_id = int(base_manifest["profile_build_id"])
    common_vma = int(base_manifest["policy"]["common_vma"])
    max_slice = int(base_manifest["policy"]["max_slice_bytes"])
    main, overflow, parsed = R.build_region_images(
        slices,
        profile_build_id=build_id,
        expected_vma=common_vma,
        max_slice_bytes=max_slice,
        format_version=FORMAT_VERSION,
    )
    size, target_crc, tuple_value = stage_binding(product)
    require(
        len(main) == size == MAIN_BYTES
        and len(overflow) == OVERFLOW_BYTES
        and overflow == base_overflow
        and S.crc16(main) != target_crc,
        "pre-tail Link-60 carrier geometry or distinction is invalid")
    old_slot = S.SLOT
    old_ceiling = S.PACK_CEILING
    try:
        S.SLOT = HEADER_TAIL_SLOT
        S.PACK_CEILING = HEADER_PACK_CEILING
        tail_word, stage_bound, tail_width = solve_smallest_tail(
            main, parsed, target_crc)
    finally:
        S.SLOT = old_slot
        S.PACK_CEILING = old_ceiling
    verified = R.validate_region_images(
        stage_bound,
        overflow,
        expected_build_id=build_id,
        expected_vma=common_vma,
        max_slice_bytes=max_slice,
        format_version=FORMAT_VERSION,
    )
    rows = {row.id: row for row in verified.slices}
    header = R.render_header(
        profile_build_id=build_id,
        verifier_slices=verified.slices,
        format_version=FORMAT_VERSION,
    )
    require(
        S.crc16(stage_bound) == target_crc
        and (
            EXPECTED_SESSION_CRC is None
            or target_crc == EXPECTED_SESSION_CRC
        )
        and len(stage_bound) == MAIN_BYTES
        and len(overflow) == OVERFLOW_BYTES
        and rows[HEADER_TAIL_SLOT].file_size <= HEADER_PACK_CEILING
        and header == base_header_path.read_bytes(),
        "Link-60 stage-bound v4 carrier verification failed")

    OUT.mkdir(parents=True)
    main_out = OUT / (
        "runtime-overlays-session-c1-freezer-link60-stage-bound.bin")
    overflow_out = OUT / (
        "runtime-overlays-session-c1-freezer-link60-region1.bin")
    manifest_out = OUT / (
        "runtime-overlays-session-c1-freezer-link60-stage-bound.json")
    header_out = OUT / "runtime-overlay-session-c1-freezer.h"
    main_out.write_bytes(stage_bound)
    overflow_out.write_bytes(overflow)
    header_out.write_bytes(header)
    manifest = {
        "format":
            "lisp65-C1-Freezer-Link60-v4-rebound-stage-bound-family-v1",
        "status":
            "passed-nonpromotable-carrier-awaiting-hardware-authorization",
        "promotable": False,
        "profile": base_manifest["profile"],
        "profile_build_id": build_id,
        "catalog": {
            "version": FORMAT_VERSION,
            "slice_count": len(verified.slices),
            "directory_crc16": verified.directory_crc16,
            "header_crc16": verified.header_crc16,
        },
        "storage": {
            "main_bytes": len(stage_bound),
            "main_headroom_bytes": 65536 - len(stage_bound),
            "main_crc16": f"0x{S.crc16(stage_bound):04x}",
            "main_sha256": sha(main_out),
            "region1_bytes": len(overflow),
            "region1_capacity_bytes": 2032,
            "region1_headroom_bytes": 2032 - len(overflow),
            "region1_crc16": f"0x{S.crc16(overflow):04x}",
            "region1_sha256": sha(overflow_out),
        },
        "relocation_rebind": {
            "source": "structured-llvm-readobj-via-elf_truth",
            "external_sites_changed": len(changed),
            "external_sites_already_link60_exact": external_equal,
            "internal_relocations_preserved": internal_count,
            "sites": changed,
        },
        "outer_link60_stage_binding": {
            **tuple_value,
            "match": True,
            "tail_slot": HEADER_TAIL_SLOT,
            "tail_word": f"0x{tail_word:0{tail_width * 2}x}",
            "tail_bytes_little_endian":
                list(tail_word.to_bytes(tail_width, "little")),
            "tail_width_bytes": tail_width,
        },
        "slice_provenance": provenance,
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format":
            "lisp65-c2.2-Link60-C1-Freezer-v4-carrier-receipt-v1",
        "recorded_on": "2026-07-24",
        "status":
            "passed-capacity-and-gates-awaiting-separate-hardware-run",
        "promotable": False,
        "authority": {
            "immutable_link60_product": bind(product),
            "link60_elf": bind(base_elf),
            "link60_receipt": bind(LINK_RECEIPT),
            "diagnostic_WPLTO_donor": bind(donor_elf),
            "diagnostic_donor_receipt": bind(DONOR_RECEIPT),
            "cutpoint_contract": bind(CONTRACT),
            "cutpoint_source_gate": bind(SOURCE_GATE),
            "driver": bind(Path(__file__)),
        },
        "artifacts": {
            "session_main": bind(main_out),
            "session_region1": bind(overflow_out),
            "manifest": bind(manifest_out),
            "verifier_header": bind(header_out),
        },
        "construction": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
            "main_region_size_delta": 0,
            "region1_size_delta": 0,
            "base_slices_byteidentical": 47,
            "diagnostic_slices": 4,
            "external_relocation_sites_rebound": len(changed),
            "external_relocation_sites_already_exact": external_equal,
            "internal_relocations_changed": 0,
            "main_family_crc16": f"0x{target_crc:04x}",
            "region1_byteidentical_Link60": True,
        },
        "capacity": {
            "deployed_resident_authority": "immutable Link 60",
            "deployed_walls": link_receipt["walls"],
            "session_main_bytes": len(stage_bound),
            "session_main_headroom_bytes": 65536 - len(stage_bound),
            "session_region1_bytes": len(overflow),
            "session_region1_headroom_bytes": 2032 - len(overflow),
            "cutpoint_slices": {
                str(slot): {
                    "section": AFFECTED[slot],
                    "payload_bytes": rows[slot].file_size,
                    "pack_ceiling_bytes": (
                        HEADER_PACK_CEILING
                        if slot == HEADER_TAIL_SLOT else
                        ((rows[slot].file_size + 255) & ~255)),
                }
                for slot in sorted(AFFECTED)
            },
        },
        "proof": {
            "memory_driven_hold_mutations_rejected": 10,
            "structured_relocation_mutations_rejected": mutations,
            "structured_relocation_mutation_count": len(mutations),
            "structured_external_relocations_already_exact":
                external_equal,
            "L65R_v4_two_region_validation": "passed",
            "verifier_header": "byteidentical-Link60",
            "main_stage_tuple": tuple_value,
            "post_RTS_tail": {
                "slot": HEADER_TAIL_SLOT,
                "bytes": 2,
                "word": f"0x{tail_word:04x}",
            },
        },
        "execution_accounting": {
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
            "C1_cutpoints_already_accepted": [1, 2],
            "C1_cutpoints_pending": [3, 4],
        },
        "claim_limit": (
            "Non-promotable matrix-C1 fixture only. No product link, "
            "promotion, acceptance-chain result or release claim."),
        "next_gate": (
            "prepare and verify one Link-60 hardware appointment for "
            "cutpoint 3 with episode latch and cutpoint 4 with write barriers"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (main_out, overflow_out, manifest_out, header_out, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-carrier-link60: PASS "
        f"main={len(stage_bound)} crc=0x{target_crc:04x} "
        f"region1={len(overflow)} rebindings={len(changed)} "
        "hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CarrierError, X.RebindError, S.ReplayError, R.OverlayBankError,
        ElfTruthError, OSError, ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-carrier-link60: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
