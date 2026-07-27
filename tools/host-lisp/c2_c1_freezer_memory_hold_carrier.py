#!/usr/bin/env python3
"""Build the memory-driven C1 carrier against immutable Link 58.

The WPLTO identity is an overlay donor only.  This replay keeps the immutable
Link-58 product and 44 of its 48 Session slices, rebinds the four diagnostic
slice payloads to Link 58 through structured ELF relocations, and restores the
canonical whole-family stage CRC.  It runs no compiler, linker or hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_c1_freezer_hybrid_carrier as H  # noqa: E402
import c2_c1_freezer_link58_relocation_replay as X  # noqa: E402
import c2_c1_freezer_stage_binding_replay as S  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


LINK = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
DONOR = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-memory-holds-NONPROMOTABLE")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-memory-holds-link58-rebound-"
    "stage-bound-NONPROMOTABLE")
EVIDENCE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link58-matrix-addenda-fixed-block-"
    "structural-receipt.json")
DONOR_RECEIPT = EVIDENCE / (
    "c2.2-link58-c1-freezer-memory-holds-"
    "nonpromotable-structural-receipt.json")
PRECEDENT_RECEIPT = EVIDENCE / (
    "c2.2-link58-c1-freezer-link58-relocation-rebind-"
    "nonpromotable-receipt.json")
CUTPOINT2_FIRST_RED = EVIDENCE / (
    "c2.2-link58-C1-Freezer-cutpoint2-continuation-"
    "hardware-first-red.json")
CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
SOURCE_GATE = (
    DONOR / "c1-freezer-cutpoint-source-gate.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-c1-freezer-memory-hold-carrier-"
    "nonpromotable-receipt.json")
LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")

EXPECTED_CHANGED = {
    (".lisp65_rt_c2append_header", 0xC50A, "memcpy",
     0xB3D1, 0xB3C9),
    (".lisp65_rt_c2append_publish_clear", 0xC5EF, "alloc",
     0x421E, 0x4224),
    (".lisp65_rt_c2append_publish_clear", 0xC628, "ext_set_a",
     0x4C6B, 0x4C71),
    (".lisp65_rt_c2append_publish_clear", 0xC633, "ext_set_b",
     0x4C34, 0x4C3A),
    (".lisp65_rt_c2append_publish_clear", 0xC6AC,
     "set_sym_function", 0x6824, 0x682A),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC3F5, "memcpy",
     0xB3D1, 0xB3C9),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC633,
     "set_sym_function", 0x6824, 0x682A),
}
CEILINGS = {30: 1792, 39: 768, 40: 1280, 41: 768}


class CarrierError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CarrierError(message)


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


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(),
            "memory-driven C1 carrier replay is one-shot")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    base_elf = LINK / "lisp65-c2-substitution-linked.prg.elf"
    donor_elf = DONOR / "lisp65-c2-substitution-linked.prg.elf"
    base_image_path = LINK / "runtime-overlays-session-final.bin"
    base_manifest_path = LINK / "runtime-overlays-session-final.json"
    base_header_path = LINK / "runtime-overlay-session-final.h"
    donor_image_path = DONOR / "runtime-overlays-session-final.bin"
    donor_manifest_path = DONOR / "runtime-overlays-session-final.json"
    authorities = (
        product, base_elf, donor_elf, base_image_path, base_manifest_path,
        base_header_path, donor_image_path, donor_manifest_path,
        LINK_RECEIPT, DONOR_RECEIPT, PRECEDENT_RECEIPT,
        CUTPOINT2_FIRST_RED, CONTRACT, SOURCE_GATE, LLVM_READOBJ,
    )
    for path in authorities:
        require(path.is_file(), f"missing C1 carrier authority: {path}")
    link_receipt = read_json(LINK_RECEIPT)
    donor_receipt = read_json(DONOR_RECEIPT)
    source_gate = read_json(SOURCE_GATE)
    require(
        sha(product) == PRODUCT_SHA
        and link_receipt["status"] ==
            "passed-link58-matrix-addenda-product-identity-hardware-not-run"
        and donor_receipt["status"] ==
            "passed-nonpromotable-C1-memory-hold-WPLTO-donor-"
            "hardware-not-run"
        and donor_receipt["diagnostic_identity"]["deployment_role"] ==
            "WPLTO-overlay-donor-only"
        and source_gate["format"] ==
            "lisp65-c2.2-c1-freezer-cutpoint-source-gate-v2"
        and len(source_gate["mutations_rejected"]) == 10,
        "memory-driven C1 carrier authority is incomplete")

    base_manifest = read_json(base_manifest_path)
    donor_manifest = read_json(donor_manifest_path)
    base_image = base_image_path.read_bytes()
    donor_image = donor_image_path.read_bytes()
    base_rows = H.rows_by_id(base_manifest)
    donor_rows = H.rows_by_id(donor_manifest)
    require(
        set(base_rows) == set(donor_rows) == set(range(48)),
        "Session family is not the expected dense 48-slot catalog")

    base_truth = ElfTruth.read(
        base_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    donor_truth = ElfTruth.read(
        donor_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    original = X.diagnostic_payloads(donor_manifest, donor_image)
    for section, data in original.items():
        require(
            donor_truth.section_bytes(section) == data,
            f"donor catalog/ELF payload identity drift: {section}")
    old_expected = X.EXPECTED_CHANGED
    try:
        X.EXPECTED_CHANGED = EXPECTED_CHANGED
        rebound, changed, internal_count = X.rebind_payloads(
            donor_truth, base_truth, original)
    finally:
        X.EXPECTED_CHANGED = old_expected
    X.validate_changed_sites(rebound, changed)

    mutations: list[str] = []
    for row in changed:
        mutated = dict(rebound)
        data = bytearray(mutated[row["section"]])
        X.patch_value(
            data, row["section_offset"], row["relocation_type"],
            row["diagnostic_value"])
        mutated[row["section"]] = bytes(data)
        try:
            X.validate_changed_sites(mutated, changed)
        except X.RebindError:
            mutations.append(
                f"{row['section']}:{row['identity']}:donor-target")
        else:
            raise CarrierError(
                f"reverted relocation survived: {row['identity']}")

    slices: list[R.ExtractedSlice] = []
    provenance: list[dict[str, Any]] = []
    for slot in range(48):
        base_row = base_rows[slot]
        donor_row = donor_rows[slot]
        require(
            base_row["section"] == donor_row["section"]
            and base_row["vma"] == donor_row["vma"]
            and base_row["entry_offset"] == donor_row["entry_offset"]
            and base_row["flags"] == donor_row["flags"]
            and base_row["abi_version"] == donor_row["abi_version"]
            and base_row["capability_mask"] == donor_row["capability_mask"],
            f"slice ABI/geometric drift at slot {slot}")
        if slot in H.AFFECTED:
            data = rebound[str(donor_row["section"])]
            chosen = donor_row
            source = "memory-hold-donor-Link58-relocation-rebound"
        else:
            data = H.payload(base_image, base_row)
            chosen = base_row
            source = "link58-byteidentical"
        slices.append(H.extracted(chosen, data))
        provenance.append({
            "id": slot,
            "section": chosen["section"],
            "source": source,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    build_id = int(base_manifest["profile_build_id"])
    common_vma = int(base_manifest["policy"]["common_vma"])
    max_slice = int(base_manifest["policy"]["max_slice_bytes"])
    image, parsed = R.build_image(
        slices, profile_build_id=build_id, expected_vma=common_vma,
        max_slice_bytes=max_slice, format_version=3)
    require(
        len(image) == 65438 and 65536 - len(image) == 98,
        "memory-hold carrier changed Session aggregate geometry")
    size, target_crc = S.product_stage_binding(product)
    require(len(image) == size and S.crc16(image) != target_crc,
            "pre-tail carrier unexpectedly equals outer stage binding")
    tail_word, stage_bound = S.solve_tail(image, parsed, target_crc)
    verified = R.validate_image(
        stage_bound, expected_build_id=build_id, expected_vma=common_vma,
        max_slice_bytes=max_slice, format_version=3)
    rows = {row.id: row for row in verified.slices}
    capacity: dict[str, dict[str, int]] = {}
    for slot, ceiling in CEILINGS.items():
        row = rows[slot]
        require(row.file_size <= ceiling,
                f"memory-hold slice {slot} crossed its pack quantum")
        capacity[str(slot)] = {
            "payload_bytes": row.file_size,
            "ceiling_bytes": ceiling,
            "headroom_bytes": ceiling - row.file_size,
        }
    header = R.render_header(
        profile_build_id=build_id, verifier_slices=verified.slices,
        format_version=3)
    require(
        S.crc16(stage_bound) == target_crc == 0xD387
        and len(stage_bound) == 65438
        and rows[39].file_size == 648
        and header == base_header_path.read_bytes(),
        "memory-hold stage-bound carrier verification failed")

    OUT.mkdir(parents=True)
    image_out = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link58-rebound-stage-bound.bin")
    manifest_out = OUT / (
        "runtime-overlays-session-c1-freezer-memory-holds-"
        "link58-rebound-stage-bound.json")
    header_out = OUT / "runtime-overlay-session-c1-freezer.h"
    image_out.write_bytes(stage_bound)
    header_out.write_bytes(header)
    manifest = {
        "format": (
            "lisp65-C1-Freezer-memory-hold-Link58-rebound-"
            "stage-bound-family-v1"),
        "status": "passed-nonpromotable-carrier-hardware-not-run",
        "promotable": False,
        "profile": base_manifest["profile"],
        "profile_build_id": build_id,
        "storage": {
            "bytes": len(stage_bound),
            "headroom_bytes": 65536 - len(stage_bound),
            "sha256": sha(image_out),
            "crc16": f"0x{S.crc16(stage_bound):04x}",
        },
        "catalog": {
            "version": 3,
            "slice_count": len(verified.slices),
            "directory_crc16": verified.directory_crc16,
            "header_crc16": verified.header_crc16,
        },
        "capacity": capacity,
        "relocation_rebind": {
            "source": "structured-llvm-readobj-via-elf_truth",
            "external_sites_changed": len(changed),
            "internal_relocations_preserved": internal_count,
            "sites": changed,
        },
        "outer_link58_stage_binding": {
            "size": size,
            "crc16": f"0x{target_crc:04x}",
            "match": True,
            "tail_slot": 39,
            "tail_word": f"0x{tail_word:04x}",
        },
        "slice_provenance": provenance,
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": (
            "lisp65-c2.2-C1-Freezer-memory-hold-carrier-receipt-v1"),
        "status": (
            "passed-capacity-and-gates-awaiting-separate-hardware-"
            "authorization"),
        "promotable": False,
        "authority": {
            "immutable_link58_product": bind(product),
            "link58_elf": bind(base_elf),
            "link58_receipt": bind(LINK_RECEIPT),
            "memory_hold_contract": bind(CONTRACT),
            "memory_hold_source_gate": bind(SOURCE_GATE),
            "memory_hold_WPLTO_donor": bind(donor_elf),
            "memory_hold_donor_receipt": bind(DONOR_RECEIPT),
            "structured_rebind_precedent": bind(PRECEDENT_RECEIPT),
            "cutpoint2_harness_first_red": bind(CUTPOINT2_FIRST_RED),
        },
        "artifacts": {
            "session_family": bind(image_out),
            "manifest": bind(manifest_out),
            "verifier_header": bind(header_out),
        },
        "construction": {
            "compiler_runs_after_WPLTO_probe": 0,
            "linker_runs_after_WPLTO_probe": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
            "session_family_size_delta": 0,
            "base_slices_byteidentical": 44,
            "diagnostic_slices": 4,
            "external_relocation_sites_rebound": len(changed),
            "internal_relocations_changed": 0,
            "whole_family_crc16": f"0x{target_crc:04x}",
        },
        "capacity": {
            "deployed_resident_authority": "immutable Link-58",
            "deployed_walls":
                link_receipt["fresh_replacement_gates"]["walls"],
            "session_family_bytes": len(stage_bound),
            "session_family_headroom_bytes": 65536 - len(stage_bound),
            "cutpoint_slices": capacity,
        },
        "proof": {
            "memory_driven_hold_mutations_rejected": 10,
            "structured_relocation_mutations_rejected": mutations,
            "structured_relocation_mutation_count": len(mutations),
            "L65R_v3_validation": "passed",
            "verifier_header": "byteidentical-Link58",
            "post_RTS_tail": {
                "slot": 39,
                "bytes": 2,
                "word": f"0x{tail_word:04x}",
                "pack_headroom_bytes": CEILINGS[39] - rows[39].file_size,
            },
        },
        "execution_accounting": {
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
            "C1_cutpoints_already_accepted": [1],
            "C1_cutpoints_pending": [2, 3, 4],
        },
        "claim_limit": (
            "Non-promotable matrix-C1 fixture only. No new product link, "
            "C1 closure, promotion, acceptance-chain result or release "
            "claim."),
        "next_gate": (
            "separate authorization for one device appointment covering "
            "cutpoints 2 through 4"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (image_out, manifest_out, header_out, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-memory-hold-carrier: PASS "
        f"product={PRODUCT_SHA} carrier={sha(image_out)} "
        f"session={len(stage_bound)}/65536 "
        f"headroom={65536-len(stage_bound)} "
        f"crc=0x{target_crc:04x} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CarrierError, X.RebindError, ElfTruthError, H.CarrierError,
        S.ReplayError, R.OverlayBankError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-memory-hold-carrier: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
