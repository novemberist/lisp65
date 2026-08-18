#!/usr/bin/env python3
"""Derive retired successor proofs from a supplied current artifact world."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import zlib

from elf_truth import ElfTruth
import c2_final_island_identity_gate as ISLAND


ROOT = Path(__file__).resolve().parents[2]
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
SLICE_CAP = 1792


class SuccessorIdentityError(ISLAND.GateError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorIdentityError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"successor identity artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"successor identity JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def extract_section(elf: Path, section: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="c2-postlink-identity-") as tmp:
        directory = Path(tmp)
        disposable = directory / "artifact.elf"
        output = directory / "section.bin"
        shutil.copy2(elf, disposable)
        result = subprocess.run([
            str(OBJCOPY), f"--dump-section={section}={output}",
            str(disposable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False)
        require(result.returncode == 0 and output.is_file(),
                f"section extraction failed: {section}")
        return output.read_bytes()


def bank2_workbench_identity(
        elf: Path, static_root: Path,
        replacement: dict[str, Any]) -> dict[str, Any]:
    shelf_path = static_root / "product/product-shelf-v4-direct.bin"
    c2d_path = static_root / "v6-semantics/initial.c2d-v6.bin"
    code_path = static_root / "v6-semantics/bank2-static-code.bin"
    shelf = shelf_path.read_bytes()
    c2d = c2d_path.read_bytes()
    code = code_path.read_bytes()
    workbench = extract_section(elf, ".lisp65_workbench_overlay")
    crc_gate = replacement["workbench_crc_end_to_end"]
    stage_gate = replacement["bank3_stage_before_publish"]
    require(
        crc_gate["status"]
            == "passed-linked-leaf-equals-current-descriptor-emitter"
        and crc_gate["payload_bytes"] == len(workbench)
        and crc_gate["payload_sha256"] == sha_bytes(workbench)
        and stage_gate["status"] == "passed"
        and stage_gate["source_contract"]["checks"]
            ["workbench_no_longer_owns_boot_staging"] is True,
        "current Workbench carrier rows do not bind the extracted payload")
    rows: list[dict[str, Any]] = []
    cursor = 0
    for image in range(6):
        shelf_record = shelf[32 + image * 32:64 + image * 32]
        c2d_record = c2d[48 + image * 32:80 + image * 32]
        source = int.from_bytes(shelf_record[8:11], "little")
        length = int.from_bytes(shelf_record[11:13], "little")
        crc = int.from_bytes(shelf_record[18:22], "little")
        target = int.from_bytes(c2d_record[18:21], "little")
        require(
            target == cursor
            and int.from_bytes(c2d_record[21:23], "little") == length
            and source + length <= len(shelf)
            and target + length <= len(code)
            and zlib.crc32(shelf[source:source + length]) & 0xffffffff == crc
            and zlib.crc32(code[target:target + length]) & 0xffffffff == crc,
            f"current Bank-2 record {image} source/target identity red")
        rows.append({
            "image": image, "source": source, "target": target,
            "bytes": length, "crc32": f"0x{crc:08x}"})
        cursor += length
    require(cursor == len(code), "current Bank-2 records do not close plane")
    scratch = workbench + bytes(len(code) - len(workbench))
    passing = sum(
        (zlib.crc32(scratch[row["target"]:
                            row["target"] + row["bytes"]]) & 0xffffffff)
        == int(row["crc32"], 16) for row in rows)
    require(passing == 0,
            "current Workbench payload passes a Bank-2 code record")
    return {
        "status": "passed-current-bank2-records-and-workbench-negative",
        "current_schema_rows": [
            "bank3_stage_before_publish", "workbench_crc_end_to_end"],
        "records": rows, "record_count": len(rows),
        "static_plane_bytes": len(code),
        "expected_plane_all_target_crcs": "passed",
        "workbench_bytes": len(workbench),
        "workbench_sha256": sha_bytes(workbench),
        "workbench_scratch_passing_records": passing,
        "ready_if_workbench_scratch_remains": False,
        "artifacts": {
            "ELF": bind(elf), "shelf": bind(shelf_path),
            "c2d": bind(c2d_path), "expected_bank2": bind(code_path)},
    }


def roots_fronts_identity(
        elf: Path, artifact_root: Path,
        replacement: dict[str, Any]) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    section = truth.section(".lisp65_rt_c2append_roots_fronts")
    symbols = {name: truth.symbol(name) for name in (
        "c2_append_roots_phase", "c2_append_fronts_phase",
        "c2_append_roots_fronts_phase")}
    session_path = artifact_root / "runtime-overlays-session-final.bin"
    overflow_path = artifact_root / "runtime-overlays-session-final-region1.bin"
    manifest_path = artifact_root / "runtime-overlays-session-final.json"
    manifest = load(manifest_path)
    rows = [row for row in manifest["slices"]
            if row["section"] == section.name]
    capacity = replacement["capacity"]
    capacity_rows = [row for row in capacity["section_evidence"]
                     if row["section"] == section.name]
    require(
        capacity["status"] == "passed"
        and capacity["identity_status"]
            == "passed-current-contract-derived-capacity"
        and capacity["ELF"] == bind(elf)
        and 0 < section.bytes <= SLICE_CAP
        and all(symbol.section == section.name and symbol.bytes > 0
                for symbol in symbols.values())
        and ".lisp65_rt_c2append_roots" not in truth.sections_by_name
        and ".lisp65_rt_c2append_fronts" not in truth.sections_by_name
        and len(rows) == len(capacity_rows) == 1
        and rows[0]["file_size"] == capacity_rows[0]["bytes"] == section.bytes
        and rows[0]["sha256"] == capacity_rows[0]["sha256"]
        and manifest["catalog"]["slice_count"]
            == capacity["session_catalog_records"]
        and manifest["storage"]["size"] == session_path.stat().st_size
            == capacity["session_family_bytes"]
        and manifest["overflow_storage"]["used"]
            == overflow_path.stat().st_size
            == capacity["session_overflow_bytes"],
        "current roots/fronts artifact identity red")
    return {
        "status": "passed-current-one-slice-multiple-entry-identity",
        "current_schema_rows": ["capacity"],
        "section": {
            "name": section.name, "address": section.address,
            "bytes": section.bytes,
            "headroom_bytes": SLICE_CAP - section.bytes,
            "sha256": rows[0]["sha256"]},
        "entries": {
            name: {"address": symbol.value, "bytes": symbol.bytes,
                   "section": symbol.section}
            for name, symbol in symbols.items()},
        "retired_split_sections_present": False,
        "session_region0_bytes": session_path.stat().st_size,
        "session_region0_headroom_bytes":
            65536 - session_path.stat().st_size,
        "session_region1_bytes": overflow_path.stat().st_size,
        "session_region1_headroom_bytes":
            int(manifest["overflow_storage"]["capacity"])
            - overflow_path.stat().st_size,
        "session_catalog_records": manifest["catalog"]["slice_count"],
        "artifacts": {
            "ELF": bind(elf), "session": bind(session_path),
            "session_region1": bind(overflow_path),
            "session_manifest": bind(manifest_path)},
    }


def validate_final_identity_v4(
        image: bytes | bytearray, row: dict[str, Any],
        section: bytes) -> dict[str, Any]:
    slot = int(row["id"])
    record = ISLAND.raw_record(image, slot)
    values = ISLAND.record_values(record)
    start = int(row["file_offset"])
    end = start + values["file_length"]
    region_id = record[24]
    source_address = (
        values["file_offset"] | ((record[25] & 0x0f) << 16)
        | (record[26] << 20))
    require(values["slot"] == slot and values["flags"] == 9,
            "carrier record identity/flags drift")
    require(
        values["vma"] == 0x1800
        and values["memory_length"] == values["file_length"]
        and values["entry_offset"] == 0xffff and values["abi"] == 0,
        "carrier DATA_ONLY geometry drift")
    require(
        region_id in (0, 1) and region_id == int(row["region_id"])
        and record[25] & 0xf0 == 0 and record[27:] == bytes(5)
        and source_address == int(row["source_address"])
        and values["file_offset"] == (source_address & 0xffff),
        "carrier L65R-v4 region/source identity drift")
    require(
        values["record_crc16"] != 0
        and values["record_crc16"] == ISLAND.record_crc(record),
        "carrier record self-CRC drift")
    require(0 < values["file_length"] <= ISLAND.HARD_MAX
            and end <= len(image), "carrier payload bounds drift")
    payload = bytes(image[start:end])
    require(values["file_length"] == len(section),
            "carrier record length differs from final Island section")
    require(
        values["payload_crc16"] == ISLAND.crc16(payload)
        == ISLAND.crc16(section),
        "carrier record CRC differs from final Island section")
    require(payload == section,
            "carrier payload differs from final Island section")
    digest = ISLAND.sha_bytes(section)
    require(
        int(row["file_size"]) == len(section)
        and int(row["memory_size"]) == len(section)
        and int(row["crc16"]) == values["payload_crc16"]
        and row["sha256"] == digest,
        "carrier manifest differs from record/final Island section")
    return {
        "slot": slot, **values, "region_id": region_id,
        "source_address": source_address, "section_bytes": len(section),
        "section_crc16": values["payload_crc16"],
        "section_sha256": digest}


def final_island_identity(
        elf: Path, artifact_root: Path,
        replacement: dict[str, Any]) -> dict[str, Any]:
    image = artifact_root / "runtime-overlays-boot-final.bin"
    manifest = artifact_root / "runtime-overlays-boot-final.json"
    runtime = artifact_root / "generated-product-sources/vm_runtime_overlay.c"
    family = replacement["runtime_family"]["successor_bank3_pack"]["boot"]
    require(family["path"] == bind(image)["path"]
            and family["bytes"] == bind(image)["bytes"]
            and family["sha256"] == bind(image)["sha256"],
            "current runtime-family row does not bind Boot carrier")
    original = ISLAND.validate_identity
    try:
        ISLAND.validate_identity = validate_final_identity_v4
        value = ISLAND.audit(elf, image, manifest, runtime)
    finally:
        ISLAND.validate_identity = original
    carrier = ISLAND.carrier_row(load(manifest))
    require(
        value["status"]
            == "passed-final-record-equals-final-island-single-truth"
        and value["mutation_cases"] == 11
        and value["seed_runtime_comparisons"] == 0
        and value["identity"]["section_sha256"] == carrier["sha256"],
        "current final-Island semantic identity red")
    value["current_schema_rows"] = ["runtime_family"]
    value["carrier_manifest_section_sha256"] = carrier["sha256"]
    return value


def project(replacement: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    artifact_root = artifact_root.resolve()
    elf = artifact_root / "lisp65-c2-substitution-linked.prg.elf"
    static_root = artifact_root.parent / "static-plane/narrow-static"
    require(replacement.get("status") == "passed"
            and artifact_root.is_dir() and static_root.is_dir(),
            "current post-link artifact world is incomplete")
    value = {
        "bank2-target-and-workbench-identity":
            bank2_workbench_identity(elf, static_root, replacement),
        "roots-fronts-single-slice-entry-identity":
            roots_fronts_identity(elf, artifact_root, replacement),
        "final-island-carrier-identity":
            final_island_identity(elf, artifact_root, replacement),
    }
    return {
        "status": "passed-three-current-successor-identities",
        "artifact_root": artifact_root.relative_to(ROOT).as_posix(),
        "proofs": value,
    }
