#!/usr/bin/env python3
"""Rebind C1 diagnostic overlays to the immutable Link-58 ELF identity.

The four C1 hold-enabled overlays were compiled in a separate WPLTO identity.
Their internal overlay relocations are correct, but seven already-resolved
calls into resident Link-58 code retained addresses from the diagnostic link.
This Class-A artifact replay uses structured llvm-readobj ELF truth to replace
only those external relocation values, rebuilds the L65R-v3 Session family,
and then restores Link 58's whole-family stage CRC with the established
unreachable post-RTS tail.

No compiler, linker, product, resident byte, floor, wall or capacity changes.
The result is a separate non-promotable C1 hardware-fixture identity.
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
from elf_truth import ElfTruth, ElfTruthError, Relocation, Symbol  # noqa: E402
import c2_c1_freezer_hybrid_carrier as H  # noqa: E402
import c2_c1_freezer_stage_binding_replay as S  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


LINK = ROOT / (
    "build/c2.2/substitution/product-link-58-matrix-addenda-fixed-block")
DIAGNOSTIC = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-cutpoints-attempt3-NONPROMOTABLE")
FAILED_CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-hybrid-stage-bound-NONPROMOTABLE")
HARDWARE = ROOT / (
    "build/c2.2/c1-freezer-hardware-link58-attempt3-NONPROMOTABLE")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-c1-freezer-link58-rebound-stage-bound-NONPROMOTABLE")
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link58-matrix-addenda-fixed-block-structural-receipt.json")
DIAGNOSTIC_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-cutpoints-attempt3-"
    "nonpromotable-structural-receipt.json")
FAILED_CARRIER_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-stage-bound-"
    "nonpromotable-receipt.json")
STAGE_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-hybrid-stage-binding-hardware-first-red.json")
ZERO_C2J_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-zero-journal-hardware-first-red.json")
CROSS_IDENTITY_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-cross-identity-relocation-"
    "hardware-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link58-c1-freezer-link58-relocation-rebind-"
    "nonpromotable-receipt.json")

LLVM_READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PRODUCT_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
VM_DIRMISS = 6
RTOV_FAULT = 0x0077
RTOV_FAMILY = 0x0079
C2_READY = 0x008C
C2J_OFFSET = 50752
C2J_BYTES = 64
EXPECTED_CHANGED = {
    (".lisp65_rt_c2append_header", 0xC508, "memcpy",
     0xB3D3, 0xB3C9),
    (".lisp65_rt_c2append_publish_clear", 0xC5ED, "alloc",
     0x4220, 0x4224),
    (".lisp65_rt_c2append_publish_clear", 0xC626, "ext_set_a",
     0x4C6D, 0x4C71),
    (".lisp65_rt_c2append_publish_clear", 0xC631, "ext_set_b",
     0x4C36, 0x4C3A),
    (".lisp65_rt_c2append_publish_clear", 0xC6AA, "set_sym_function",
     0x6826, 0x682A),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC3F5, "memcpy",
     0xB3D3, 0xB3C9),
    (".lisp65_rt_c2append_rollback_unpublish", 0xC638,
     "set_sym_function", 0x6826, 0x682A),
}
SUPPORTED_RELOCATIONS = {
    "R_MOS_ADDR8", "R_MOS_ADDR16",
    "R_MOS_ADDR16_LO", "R_MOS_ADDR16_HI",
}


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


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


def collapsed_symbol(truth: ElfTruth, name: str) -> Symbol | None:
    rows = truth.symbols_by_name.get(name, [])
    identities = {
        (row.value, row.bytes, row.section, row.section_index,
         row.symbol_type): row for row in rows
    }
    if len(identities) == 1:
        return next(iter(identities.values()))
    return None


def containing_identity(
        diagnostic: ElfTruth, base: ElfTruth, symbol: Symbol,
        address: int) -> tuple[str, int]:
    """Map one section+addend target through a unique sized ELF identity."""
    rows = [
        row for row in diagnostic.symbols
        if row.name and not row.name.startswith(".")
        and row.section == symbol.section and row.bytes > 0
        and row.value <= address < row.value + row.bytes
    ]
    geometries = {(row.value, row.bytes) for row in rows}
    require(
        len(geometries) == 1,
        "section+addend target lacks unique named interval: "
        f"{symbol.section}+0x{address - symbol.value:x} "
        f"at 0x{address:04x}")
    start, _ = next(iter(geometries))
    offset = address - start
    mapped: list[tuple[str, int]] = []
    for row in sorted(rows, key=lambda item: item.name):
        base_row = collapsed_symbol(base, row.name)
        if base_row is not None:
            mapped.append((row.name, base_row.value + offset))
    require(mapped, f"no Link-58 identity for section target at 0x{address:04x}")
    values = {value for _, value in mapped}
    require(
        len(values) == 1,
        f"aliases map section target ambiguously: {mapped}")
    preferred = sorted(
        mapped,
        key=lambda item: (
            diagnostic.symbols_by_name[item[0]][0].symbol_type != "Function",
            item[0]),
    )[0]
    return preferred


def link58_target(
        diagnostic: ElfTruth, base: ElfTruth,
        row: Relocation) -> tuple[str, int, int]:
    symbol = diagnostic.symbols[row.target_symbol_index]
    old = symbol.value + row.addend
    if symbol.section == row.source_section:
        return symbol.name, old, old
    is_section_symbol = (
        symbol.symbol_type == "Section" or symbol.name.startswith("."))
    if is_section_symbol:
        base_section = collapsed_symbol(base, symbol.name)
        require(base_section is not None,
                f"Link-58 section identity absent: {symbol.name}")
        section_relative = base_section.value + row.addend
        try:
            name, new = containing_identity(
                diagnostic, base, symbol, old)
        except RebindError:
            # Unnamed section-relative state (notably tiny BSS offsets) is
            # safe only while its final resolved value is already identical.
            require(
                section_relative == old,
                "changed section+addend target has no canonical identity: "
                f"{symbol.name}+0x{row.addend:x}")
            return symbol.name, old, old
        return name, old, new
    base_symbol = collapsed_symbol(base, symbol.name)
    require(base_symbol is not None,
            f"Link-58 symbol identity absent: {symbol.name}")
    return symbol.name, old, base_symbol.value + row.addend


def encoded(data: bytes | bytearray, index: int, kind: str) -> int:
    require(kind in SUPPORTED_RELOCATIONS,
            f"unsupported MOS relocation: {kind}")
    if kind == "R_MOS_ADDR16":
        require(index + 2 <= len(data), "u16 relocation lies outside payload")
        return data[index] | data[index + 1] << 8
    require(index < len(data), "byte relocation lies outside payload")
    return data[index]


def projected(value: int, kind: str) -> int:
    if kind == "R_MOS_ADDR16":
        return value & 0xFFFF
    if kind in ("R_MOS_ADDR8", "R_MOS_ADDR16_LO"):
        return value & 0xFF
    if kind == "R_MOS_ADDR16_HI":
        return value >> 8 & 0xFF
    raise RebindError(f"unsupported MOS relocation: {kind}")


def patch_value(data: bytearray, index: int, kind: str, value: int) -> None:
    if kind == "R_MOS_ADDR16":
        data[index:index + 2] = (value & 0xFFFF).to_bytes(2, "little")
    else:
        data[index] = projected(value, kind)


def diagnostic_payloads(
        manifest: dict[str, Any], image: bytes) -> dict[str, bytes]:
    return {
        str(row["section"]): H.payload(image, row)
        for row in manifest["slices"] if int(row["id"]) in H.AFFECTED
    }


def rebind_payloads(
        diagnostic: ElfTruth, base: ElfTruth,
        original: dict[str, bytes]) -> tuple[
            dict[str, bytes], list[dict[str, Any]], int]:
    result = {name: bytearray(data) for name, data in original.items()}
    changed: list[dict[str, Any]] = []
    internal = 0
    for row in diagnostic.relocations:
        if row.source_section not in result:
            continue
        section = diagnostic.section(row.source_section)
        symbol = diagnostic.symbols[row.target_symbol_index]
        index = row.offset - section.address
        old_encoded = encoded(result[row.source_section], index,
                              row.relocation_type)
        expected_old = projected(symbol.value + row.addend,
                                 row.relocation_type)
        require(
            old_encoded == expected_old,
            "diagnostic payload no longer encodes its structured relocation: "
            f"{row.source_section}+0x{index:x} {row.target}")
        if symbol.section == row.source_section:
            internal += 1
            continue
        name, old, new = link58_target(diagnostic, base, row)
        if old == new:
            continue
        patch_value(result[row.source_section], index, row.relocation_type, new)
        changed.append({
            "section": row.source_section,
            "section_offset": index,
            "relocation_offset": row.offset,
            "relocation_type": row.relocation_type,
            "identity": name,
            "diagnostic_value": old,
            "link58_value": new,
            "diagnostic_encoded": expected_old,
            "link58_encoded": projected(new, row.relocation_type),
        })
    observed = {
        (row["section"], row["relocation_offset"], row["identity"],
         row["diagnostic_value"], row["link58_value"])
        for row in changed
    }
    require(
        observed == EXPECTED_CHANGED and len(changed) == 7,
        f"external relocation delta set drift: {sorted(observed)}")
    return {name: bytes(data) for name, data in result.items()}, changed, internal


def validate_changed_sites(
        payloads: dict[str, bytes], changed: list[dict[str, Any]]) -> None:
    for row in changed:
        actual = encoded(
            payloads[row["section"]], row["section_offset"],
            row["relocation_type"])
        require(
            actual == row["link58_encoded"],
            f"Link-58 relocation binding absent: {row['identity']}")


def validate_cross_identity_first_red(
        failed_carrier: Path,
        changed: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "deployment": HARDWARE / "deployment.json",
        "misleading_boot_observer_state": HARDWARE / "hardware-state.json",
        "bank0": HARDWARE / "boot-bank0.bin",
        "bank2": HARDWARE / "boot-bank2.bin",
        "bank3": HARDWARE / "boot-bank3.bin",
        "bank5": HARDWARE / "boot-bank5.bin",
        "screen_png": HARDWARE / "boot-first-red.png",
        "screen_ansi": HARDWARE / "boot-first-red.ansi.txt",
        "screen_text": HARDWARE / "boot-first-red.txt",
        "session_readback": HARDWARE / (
            "deploy-readback-runtime-overlays-session-c1-freezer-"
            "stage-bound.bin"),
        "zero_C2J_readback":
            HARDWARE / "deploy-readback-zero-c2j.bin",
    }
    for name, path in required.items():
        require(path.is_file(), f"missing cross-identity First Red {name}")
    bank0 = required["bank0"].read_bytes()
    bank5 = required["bank5"].read_bytes()
    screen = required["screen_text"].read_text(
        encoding="utf-8", errors="replace")
    state = read_json(required["misleading_boot_observer_state"])
    require(
        len(bank0) == 65536 and len(bank5) == 50816
        and bank0[0x005B] == VM_DIRMISS
        and bank0[RTOV_FAULT] == 0
        and bank0[RTOV_FAMILY] == 2
        and bank0[C2_READY] == 1
        and bank5[C2J_OFFSET:C2J_OFFSET + C2J_BYTES] == bytes(C2J_BYTES)
        and "*** vm: undefined function" in screen
        and "lisp65>" not in screen
        and required["session_readback"].read_bytes()
            == failed_carrier.read_bytes()
        and required["zero_C2J_readback"].read_bytes() == bytes(C2J_BYTES)
        and state["status"] == "passed-boot-ready-for-cutpoint-1",
        "attempt-3 evidence is not the expected cross-identity First Red")
    return {
        "format": (
            "lisp65-c2.2-C1-Freezer-cross-identity-relocation-"
            "hardware-first-red-v1"),
        "status": (
            "first-red-harness-cross-identity-relocations-"
            "no-C1-cutpoint-reached"),
        "promotable": False,
        "product": bind(LINK / "lisp65-c2-substitution-linked.prg"),
        "failed_diagnostic_carrier": bind(failed_carrier),
        "hardware": {
            "boots": 1,
            "screen": "*** vm: undefined function",
            "vm_status": VM_DIRMISS,
            "vm_status_name": "VM_DIRMISS",
            "rtov_fault": 0,
            "rtov_family": 2,
            "c2_ready": 1,
            "C2J": "all-zero",
            "C1_cutpoints_reached": 0,
            "latency_attempts_consumed": 0,
        },
        "observer_gap": {
            "superseded_status":
                state["status"],
            "cause": (
                "The boot observer checked READY, C2J and Bank-2 identity but "
                "did not require a rendered banner/REPL prompt or reject a "
                "non-success vm_status. Its saved pass is preserved as "
                "superseded evidence, not reused."),
        },
        "diagnosis": {
            "class": "artifact-only-cross-WPLTO-identity-relocation-drift",
            "external_relocation_sites": len(changed),
            "sites": changed,
            "cause": (
                "Four diagnostic overlay payloads came from a separate WPLTO "
                "identity. Their internal relocations remained valid, but "
                "seven resolved calls still targeted that identity rather "
                "than the immutable Link-58 resident image."),
        },
        "captures": {name: bind(path) for name, path in required.items()},
        "claim_limit": (
            "Harness First Red only. No C1 cutpoint, matrix closure, "
            "promotion, acceptance-chain result or release claim."),
        "next_gate": (
            "structured Link-58 relocation rebind and hardened boot observer; "
            "then separate authorization for a fresh hardware run"),
    }


def main() -> int:
    require(
        not OUT.exists()
        and not RECEIPT.exists()
        and not CROSS_IDENTITY_FIRST_RED_RECEIPT.exists(),
        "C1 Link-58 relocation replay is one-shot")
    product = LINK / "lisp65-c2-substitution-linked.prg"
    base_elf = LINK / "lisp65-c2-substitution-linked.prg.elf"
    diag_elf = DIAGNOSTIC / "lisp65-c2-substitution-linked.prg.elf"
    base_image_path = LINK / "runtime-overlays-session-final.bin"
    base_manifest_path = LINK / "runtime-overlays-session-final.json"
    base_header_path = LINK / "runtime-overlay-session-final.h"
    diag_image_path = DIAGNOSTIC / "runtime-overlays-session-final.bin"
    diag_manifest_path = DIAGNOSTIC / "runtime-overlays-session-final.json"
    failed_carrier = FAILED_CARRIER / (
        "runtime-overlays-session-c1-freezer-stage-bound.bin")
    authorities = (
        product, base_elf, diag_elf, base_image_path, base_manifest_path,
        base_header_path, diag_image_path, diag_manifest_path, failed_carrier,
        LINK_RECEIPT, DIAGNOSTIC_RECEIPT, FAILED_CARRIER_RECEIPT,
        STAGE_FIRST_RED_RECEIPT, ZERO_C2J_FIRST_RED_RECEIPT, LLVM_READOBJ,
    )
    for path in authorities:
        require(path.is_file(), f"missing rebind authority: {path}")
    require(sha(product) == PRODUCT_SHA, "immutable Link-58 identity drift")

    base_manifest = read_json(base_manifest_path)
    diag_manifest = read_json(diag_manifest_path)
    base_image = base_image_path.read_bytes()
    diag_image = diag_image_path.read_bytes()
    base_rows = H.rows_by_id(base_manifest)
    diag_rows = H.rows_by_id(diag_manifest)
    require(
        set(base_rows) == set(diag_rows) == set(range(48)),
        "Session family is not the expected dense 48-slot catalog")
    base_truth = ElfTruth.read(
        base_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    diag_truth = ElfTruth.read(
        diag_elf, llvm_readobj=LLVM_READOBJ, include_section_data=True)
    original = diagnostic_payloads(diag_manifest, diag_image)
    for section, data in original.items():
        require(
            diag_truth.section_bytes(section) == data,
            f"catalog/ELF payload identity drift: {section}")
    rebound, changed, internal_count = rebind_payloads(
        diag_truth, base_truth, original)
    validate_changed_sites(rebound, changed)

    mutation_names: list[str] = []
    for row in changed:
        mutated = dict(rebound)
        data = bytearray(mutated[row["section"]])
        patch_value(
            data, row["section_offset"], row["relocation_type"],
            row["diagnostic_value"])
        mutated[row["section"]] = bytes(data)
        try:
            validate_changed_sites(mutated, changed)
        except RebindError:
            mutation_names.append(
                f"{row['section']}:{row['identity']}:diagnostic-target")
        else:
            raise RebindError(
                f"reverted relocation mutation survived: {row['identity']}")

    slices: list[R.ExtractedSlice] = []
    provenance: list[dict[str, Any]] = []
    for slot in range(48):
        base_row = base_rows[slot]
        diag_row = diag_rows[slot]
        require(
            base_row["section"] == diag_row["section"]
            and base_row["vma"] == diag_row["vma"]
            and base_row["entry_offset"] == diag_row["entry_offset"]
            and base_row["flags"] == diag_row["flags"]
            and base_row["abi_version"] == diag_row["abi_version"]
            and base_row["capability_mask"] == diag_row["capability_mask"],
            f"slice ABI/geometric drift at slot {slot}")
        if slot in H.AFFECTED:
            data = rebound[str(diag_row["section"])]
            chosen = diag_row
            source = "diagnostic-cutpoint-Link58-relocation-rebound"
        else:
            data = H.payload(base_image, base_row)
            chosen = base_row
            source = "link58-byteidentical"
        slices.append(H.extracted(chosen, data))
        provenance.append({
            "id": slot, "section": chosen["section"],
            "source": source, "bytes": len(data),
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
        "relocation-rebound carrier changed Session aggregate geometry")
    size, target_crc = S.product_stage_binding(product)
    require(len(image) == size and S.crc16(image) != target_crc,
            "pre-tail carrier unexpectedly equals outer stage binding")
    tail_word, stage_bound = S.solve_tail(image, parsed, target_crc)
    verified = R.validate_image(
        stage_bound, expected_build_id=build_id, expected_vma=common_vma,
        max_slice_bytes=max_slice, format_version=3)
    require(
        S.crc16(stage_bound) == target_crc == 0xD387
        and len(stage_bound) == 65438
        and verified.slices[39].file_size == 646
        and verified.slices[39].file_size <= 768,
        "stage-bound relocation-rebound carrier verification failed")
    header = R.render_header(
        profile_build_id=build_id, verifier_slices=verified.slices,
        format_version=3)
    require(header == base_header_path.read_bytes(),
            "resident verifier header differs from Link 58")

    first_red = validate_cross_identity_first_red(failed_carrier, changed)
    OUT.mkdir(parents=True)
    image_out = OUT / (
        "runtime-overlays-session-c1-freezer-"
        "link58-rebound-stage-bound.bin")
    manifest_out = OUT / (
        "runtime-overlays-session-c1-freezer-"
        "link58-rebound-stage-bound.json")
    header_out = OUT / "runtime-overlay-session-c1-freezer.h"
    image_out.write_bytes(stage_bound)
    header_out.write_bytes(header)
    manifest = {
        "format": (
            "lisp65-C1-Freezer-Link58-relocation-rebound-"
            "stage-bound-family-v1"),
        "status": (
            "passed-class-a-Link58-relocation-rebind-"
            "stage-replay-hardware-not-run"),
        "promotable": False,
        "profile": base_manifest["profile"],
        "profile_build_id": build_id,
        "storage": {
            "bytes": len(stage_bound),
            "headroom_bytes": 65536 - len(stage_bound),
            "sha256": sha(image_out),
            "crc16": S.crc16(stage_bound),
        },
        "catalog": {
            "version": 3,
            "slice_count": len(verified.slices),
            "directory_crc16": verified.directory_crc16,
            "header_crc16": verified.header_crc16,
        },
        "relocation_rebind": {
            "source": "structured-llvm-readobj-via-elf_truth",
            "external_sites_changed": len(changed),
            "internal_relocations_preserved": internal_count,
            "sites": changed,
        },
        "outer_link58_stage_binding": {
            "size": size, "crc16": target_crc, "match": True,
            "tail_slot": 39,
            "tail_word": f"0x{tail_word:04x}",
            "tail_bytes_little_endian":
                tail_word.to_bytes(2, "little").hex(),
        },
        "slice_provenance": provenance,
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    CROSS_IDENTITY_FIRST_RED_RECEIPT.write_text(
        json.dumps(first_red, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    receipt = {
        "format": (
            "lisp65-c2.2-C1-Freezer-Link58-relocation-rebind-"
            "replay-receipt-v1"),
        "status": (
            "passed-class-a-Link58-relocation-rebind-stage-replay-"
            "awaiting-hardware-authorization"),
        "promotable": False,
        "authority": {
            "immutable_link58_product": bind(product),
            "link58_elf": bind(base_elf),
            "diagnostic_elf": bind(diag_elf),
            "link58_receipt": bind(LINK_RECEIPT),
            "diagnostic_receipt": bind(DIAGNOSTIC_RECEIPT),
            "failed_carrier_receipt": bind(FAILED_CARRIER_RECEIPT),
            "stage_first_red": bind(STAGE_FIRST_RED_RECEIPT),
            "zero_C2J_first_red": bind(ZERO_C2J_FIRST_RED_RECEIPT),
            "cross_identity_first_red":
                bind(CROSS_IDENTITY_FIRST_RED_RECEIPT),
        },
        "artifacts": {
            "session_family": bind(image_out),
            "manifest": bind(manifest_out),
            "verifier_header": bind(header_out),
        },
        "construction": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "product_bytes_changed": 0,
            "resident_bytes_changed": 0,
            "session_family_size_delta": 0,
            "external_relocation_sites_rebound": len(changed),
            "internal_relocations_changed": 0,
            "base_slices_byteidentical": 44,
            "diagnostic_slices": 4,
            "whole_family_crc16": f"0x{target_crc:04x}",
            "whole_family_binding": "byteexact-Link58-stage-binding",
        },
        "proof": {
            "structured_ELF_truth": "passed",
            "relocation_sites": changed,
            "relocation_mutations_rejected": mutation_names,
            "relocation_mutation_count": len(mutation_names),
            "L65R_v3_validation": "passed",
            "post_RTS_tail": {
                "slot": 39, "bytes": 2,
                "word": f"0x{tail_word:04x}",
                "pack_headroom_bytes": 768 - verified.slices[39].file_size,
            },
            "verifier_header": "byteidentical-Link58",
        },
        "execution_accounting": {
            "hardware_boots": 0,
            "preceding_excluded_harness_First_Reds": 3,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Non-promotable artifact-only C1 fixture carrier. No C1 "
            "hardware result, matrix closure, promotion, acceptance-chain "
            "result or release claim."),
        "next_gate": (
            "hardened host boot observer, then separate authorization and "
            "reset for one fresh Link-58 C1 hardware run"),
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for path in (
            image_out, manifest_out, header_out,
            CROSS_IDENTITY_FIRST_RED_RECEIPT, RECEIPT):
        os.chmod(path, 0o444)
    os.chmod(OUT, 0o555)
    print(
        "c2-c1-freezer-link58-relocation-replay: PASS "
        f"product={PRODUCT_SHA} relocations={len(changed)} "
        f"carrier={sha(image_out)} session={len(stage_bound)}/65536 "
        f"headroom={65536-len(stage_bound)} crc=0x{target_crc:04x} "
        "compiler=0 linker=0 hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RebindError, ElfTruthError, H.CarrierError, S.ReplayError,
        R.OverlayBankError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-link58-relocation-replay: FIRST RED: "
            + str(error), file=sys.stderr)
        raise SystemExit(2)
