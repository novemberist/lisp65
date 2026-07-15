#!/usr/bin/env python3
"""Build and verify the Workbench EXT-staged boot overlay prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any, Sequence


LAYOUT_SCHEMA = "lisp65-workbench-overlay-layout-v1"
MANIFEST_SCHEMA = "lisp65-workbench-staged-overlay-v1"
DESCRIPTOR_MAGIC = b"L65O"
DESCRIPTOR_VERSION = 1
DESCRIPTOR_SIZE = 18
STAGE_ALIGNMENT = 0x100
BANK_SIZE = 0x10000
PRG_HEADER_SIZE = 2
ENTRY_SYMBOL = "vm_workbench_boot_overlay_entry"
L65M_HEADER_FORMAT = "<4sBBHIHHHHHHHHHHHHH"
L65M_HEADER_SIZE = struct.calcsize(L65M_HEADER_FORMAT)
L65M_LITERAL_KINDS = {
    1: "fix", 2: "nil", 3: "t", 4: "symbol", 5: "cons", 6: "list", 7: "string",
}

SYMBOLS = {
    "overlay_base": "__lisp65_workbench_overlay_start",
    "overlay_end": "__lisp65_workbench_overlay_end",
    "overlay_entry": "__lisp65_workbench_overlay_entry",
    "resident_file_end": "__lisp65_workbench_resident_file_end",
    "bss_end": "__bss_end",
    "stack": "__stack",
}


class StageError(RuntimeError):
    """A deterministic artifact or binding failure."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StageError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict[str, Any]:
    _regular_file(path, label)
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except StageError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StageError(f"{label} root must be an object")
    return value


def _regular_file(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise StageError(f"{label} is missing or unreadable: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise StageError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        raise StageError(f"{label} must be a regular file: {path}")
    return info


def _sha256(path: Path) -> str:
    _regular_file(path, "hash input")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with temporary.open("wb") as output:
            output.write(data)
        temporary.replace(path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def _parse_address(value: Any, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as exc:
            raise StageError(f"{label} is not an integer address: {value!r}") from exc
    else:
        raise StageError(f"{label} is not an integer address")
    if not 0 <= result < 0x10000000:
        raise StageError(f"{label} is outside the MEGA65 address space")
    return result


def _stdlib_layout(stdlib_ext: Path, stdlib_manifest: Path) -> tuple[int, int, int]:
    size = _regular_file(stdlib_ext, "stdlib EXT image").st_size
    manifest = _read_json(stdlib_manifest, "stdlib manifest")
    base = _parse_address(manifest.get("base_addr"), "stdlib manifest base_addr")
    end = base + size
    stage_base = (end + STAGE_ALIGNMENT - 1) & ~(STAGE_ALIGNMENT - 1)
    if stage_base >= 0x10000000:
        raise StageError("aligned overlay stage base exceeds the MEGA65 address space")
    return base, end, stage_base


def _exact_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise StageError(f"{label} must be an integer")
    return value


def stdlib_literal_envelope(data: bytes, metadata_offset: int) -> dict[str, int]:
    if metadata_offset < 0 or metadata_offset + L65M_HEADER_SIZE > len(data):
        raise StageError("boot stdlib literal envelope has no complete L65M header")
    fields = struct.unpack_from(L65M_HEADER_FORMAT, data, metadata_offset)
    magic, version, header_size = fields[:3]
    metadata_bytes = fields[6]
    node_count = fields[9]
    patch_count = fields[10]
    nodes_off = fields[13]
    if magic != b"L65M" or version != 1 or header_size != L65M_HEADER_SIZE:
        raise StageError("boot stdlib literal envelope has an invalid L65M header")
    if (metadata_bytes < L65M_HEADER_SIZE
            or metadata_offset + metadata_bytes > len(data)
            or nodes_off < L65M_HEADER_SIZE
            or nodes_off + node_count * 10 > metadata_bytes):
        raise StageError("boot stdlib literal envelope is outside L65M metadata")
    counts = {name: 0 for name in L65M_LITERAL_KINDS.values()}
    for index in range(node_count):
        kind = data[metadata_offset + nodes_off + index * 10]
        name = L65M_LITERAL_KINDS.get(kind)
        if name is None:
            raise StageError(f"boot stdlib literal node[{index}] has unknown kind {kind}")
        counts[name] += 1
    return {
        "node_count": node_count,
        "patch_count": patch_count,
        **counts,
    }


def _stdlib_boot_binding(stdlib_ext: Path, stdlib_manifest: Path) -> dict[str, int]:
    data = stdlib_ext.read_bytes()
    manifest = _read_json(stdlib_manifest, "stdlib manifest")
    base = _parse_address(manifest.get("base_addr"), "stdlib manifest base_addr")
    external = manifest.get("external_image")
    if not isinstance(external, dict):
        raise StageError("stdlib manifest has no external_image binding")
    code_bytes = _exact_int(external.get("code_bytes"), "external_image code_bytes")
    metadata_bytes = _exact_int(
        external.get("metadata_bytes"), "external_image metadata_bytes"
    )
    image_bytes = _exact_int(external.get("bytes"), "external_image bytes")
    metadata_offset = _exact_int(
        external.get("metadata_offset"), "external_image metadata_offset"
    )
    if external.get("format") != "lisp65-bytecode-p0-ext-image-v1":
        raise StageError("stdlib external image has the wrong format")
    if external.get("file_header_format") != "none" or external.get("file_header_bytes") != 0:
        raise StageError("boot stdlib image must not have a disk-library prefix")
    if external.get("sha256") != hashlib.sha256(data).hexdigest():
        raise StageError("stdlib external image SHA does not match its manifest")
    if (image_bytes != len(data) or metadata_offset != code_bytes
            or code_bytes + metadata_bytes != image_bytes):
        raise StageError("stdlib external image spans are inconsistent")
    if base // BANK_SIZE != (base + image_bytes - 1) // BANK_SIZE:
        raise StageError("boot stdlib image crosses an EXT-bank boundary")
    if metadata_bytes < L65M_HEADER_SIZE:
        raise StageError("boot stdlib L65M metadata is too short")
    fields = struct.unpack_from(L65M_HEADER_FORMAT, data, metadata_offset)
    (magic, version, header_size, flags, header_base, header_code_bytes,
     header_metadata_bytes, entry_count, index_count, node_count, patch_count,
     entries_off, index_off, nodes_off, patches_off, strings_off, strings_bytes,
     reserved) = fields
    if magic != b"L65M" or version != 1 or header_size != L65M_HEADER_SIZE:
        raise StageError("boot stdlib has an invalid L65M header")
    if flags or reserved or header_base != base:
        raise StageError("boot stdlib L65M profile fields are inconsistent")
    if header_code_bytes != code_bytes or header_metadata_bytes != metadata_bytes:
        raise StageError("boot stdlib L65M spans differ from the manifest")
    sections = (
        (entries_off, entry_count * 8, "entries"),
        (index_off, index_count * 2, "literal index"),
        (nodes_off, node_count * 10, "literal nodes"),
        (patches_off, patch_count * 4, "literal patches"),
        (strings_off, strings_bytes, "strings"),
    )
    for off, length, label in sections:
        if off < L65M_HEADER_SIZE or off + length > metadata_bytes:
            raise StageError(f"boot stdlib {label} section is outside L65M metadata")
    literal_envelope = stdlib_literal_envelope(data, metadata_offset)
    if (literal_envelope["node_count"] != node_count
            or literal_envelope["patch_count"] != patch_count):
        raise StageError("boot stdlib literal envelope differs from the L65M binding")
    patch_nodes = [
        struct.unpack_from(
            "<H", data, metadata_offset + patches_off + index * 4 + 2
        )[0]
        for index in range(patch_count)
    ]
    expected_patches = sum(
        _exact_int(entry.get("lit_count"), "stdlib manifest entry lit_count")
        for entry in manifest.get("entries", [])
    )
    if patch_count != expected_patches or any(node >= node_count for node in patch_nodes):
        raise StageError(
            "boot stdlib patches must cover every CodeObject literal root with a valid node"
        )
    return {
        "bank": base // BANK_SIZE,
        "off": base % BANK_SIZE,
        "image_bytes": image_bytes,
        "image_crc16": crc16_ccitt_false(data),
        "blob_bytes": code_bytes,
        "metadata_bytes": metadata_bytes,
        "entry_count": entry_count,
        "index_count": index_count,
        "node_count": node_count,
        "patch_count": patch_count,
        "entries_off": entries_off,
        "index_off": index_off,
        "nodes_off": nodes_off,
        "patches_off": patches_off,
        "strings_off": strings_off,
        "strings_bytes": strings_bytes,
        **{
            f"lit_{name}_count": literal_envelope[name]
            for name in L65M_LITERAL_KINDS.values()
        },
    }


def _build_id(contract: Path) -> int:
    digest = _sha256(contract)
    return int(digest[:8], 16)


def write_header(
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    output: Path,
) -> None:
    _, _, stage_base = _stdlib_layout(stdlib_ext, stdlib_manifest)
    stdlib = _stdlib_boot_binding(stdlib_ext, stdlib_manifest)
    build_id = _build_id(contract)
    bank = stage_base // BANK_SIZE
    off = stage_base % BANK_SIZE
    if bank > 0xFF:
        raise StageError("overlay stage bank does not fit the device descriptor")
    content = (
        "/* Generated by workbench_overlay_stage.py; do not edit. */\n"
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H\n"
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H\n"
        f"#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x{bank:02x}u\n"
        f"#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x{off:04x}u\n"
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL\n"
        f"#define LISP65_BOOT_STDLIB_PROFILE_BUILD_ID 0x{build_id:08x}UL\n"
        f"#define LISP65_BOOT_STDLIB_BANK 0x{stdlib['bank']:02x}u\n"
        f"#define LISP65_BOOT_STDLIB_OFF 0x{stdlib['off']:04x}u\n"
        f"#define LISP65_BOOT_STDLIB_IMAGE_BYTES {stdlib['image_bytes']}u\n"
        f"#define LISP65_BOOT_STDLIB_IMAGE_CRC16 0x{stdlib['image_crc16']:04x}u\n"
        f"#define LISP65_BOOT_STDLIB_BLOB_BYTES {stdlib['blob_bytes']}u\n"
        f"#define LISP65_BOOT_STDLIB_METADATA_BYTES {stdlib['metadata_bytes']}u\n"
        f"#define LISP65_BOOT_STDLIB_ENTRY_COUNT {stdlib['entry_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_INDEX_COUNT {stdlib['index_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_NODE_COUNT {stdlib['node_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_PATCH_COUNT {stdlib['patch_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_FIX_COUNT {stdlib['lit_fix_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_NIL_COUNT {stdlib['lit_nil_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_T_COUNT {stdlib['lit_t_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT {stdlib['lit_symbol_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_CONS_COUNT {stdlib['lit_cons_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_LIST_COUNT {stdlib['lit_list_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_LIT_STRING_COUNT {stdlib['lit_string_count']}u\n"
        f"#define LISP65_BOOT_STDLIB_ENTRIES_OFF {stdlib['entries_off']}u\n"
        f"#define LISP65_BOOT_STDLIB_INDEX_OFF {stdlib['index_off']}u\n"
        f"#define LISP65_BOOT_STDLIB_NODES_OFF {stdlib['nodes_off']}u\n"
        f"#define LISP65_BOOT_STDLIB_PATCHES_OFF {stdlib['patches_off']}u\n"
        f"#define LISP65_BOOT_STDLIB_STRINGS_OFF {stdlib['strings_off']}u\n"
        f"#define LISP65_BOOT_STDLIB_STRINGS_BYTES {stdlib['strings_bytes']}u\n"
        "#endif\n"
    ).encode("ascii")
    _atomic_write(output, content)


def _nm_symbols(nm: Path, elf: Path) -> dict[str, int]:
    _regular_file(nm, "nm tool")
    _regular_file(elf, "linked ELF")
    try:
        completed = subprocess.run(
            [str(nm), "--defined-only", str(elf)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise StageError(f"nm failed: {detail.strip()}") from exc
    found: dict[str, list[int]] = {name: [] for name in SYMBOLS.values()}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[-1] not in found:
            continue
        try:
            address = int(fields[0], 16)
        except ValueError as exc:
            raise StageError(f"invalid nm address in line: {line!r}") from exc
        found[fields[-1]].append(address)
    result: dict[str, int] = {}
    for key, symbol in SYMBOLS.items():
        values = found[symbol]
        if len(values) != 1:
            raise StageError(f"ELF must define {symbol} exactly once (found {len(values)})")
        result[key] = values[0]
    return result


def _prg_span(path: Path) -> tuple[int, int, bytes]:
    _regular_file(path, "linked PRG")
    data = path.read_bytes()
    if len(data) <= PRG_HEADER_SIZE:
        raise StageError("linked PRG is too short")
    load_base = data[0] | (data[1] << 8)
    file_end = load_base + len(data) - PRG_HEADER_SIZE
    if file_end > BANK_SIZE:
        raise StageError("linked PRG payload exceeds Bank 0")
    return load_base, file_end, data


def derive_layout(
    elf: Path,
    nm: Path,
    linked_prg: Path,
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    stage_limit: int,
) -> dict[str, Any]:
    symbols = _nm_symbols(nm, elf)
    load_base, linked_file_end, _ = _prg_span(linked_prg)
    stdlib_base, stdlib_end, stage_base = _stdlib_layout(stdlib_ext, stdlib_manifest)
    base = symbols["overlay_base"]
    end = symbols["overlay_end"]
    entry = symbols["overlay_entry"]
    resident_end = symbols["resident_file_end"]
    if not 0 <= base < end <= BANK_SIZE:
        raise StageError("ELF overlay span is not a non-empty Bank-0 range")
    if not base <= entry < end:
        raise StageError("ELF overlay entry lies outside its payload")
    if symbols["bss_end"] >= base:
        raise StageError("ELF overlay overlaps resident BSS")
    if end > symbols["stack"] - 0x200:
        raise StageError("ELF overlay leaves less than 512 bytes for boot stack")
    if not load_base < resident_end <= linked_file_end:
        raise StageError("resident file end is outside the linked PRG payload")
    if stage_base // BANK_SIZE > 0xFF:
        raise StageError("overlay stage bank does not fit the descriptor")
    stage_end_offset = stage_base % BANK_SIZE + DESCRIPTOR_SIZE + (end - base)
    if not 0 < stage_limit <= BANK_SIZE:
        raise StageError("overlay stage limit must be a within-bank address in 1..65536")
    if stage_end_offset > stage_limit:
        raise StageError(
            f"overlay stage end 0x{stage_end_offset:04x} exceeds profile limit 0x{stage_limit:04x}"
        )
    return {
        "schema": LAYOUT_SCHEMA,
        "build_id": _build_id(contract),
        "overlay": {
            "base": base,
            "end": end,
            "entry": entry,
            "entry_symbol": ENTRY_SYMBOL,
            "size": end - base,
        },
        "resident": {
            "load_base": load_base,
            "file_end": resident_end,
        },
        "memory": {
            "bss_end": symbols["bss_end"],
            "stack": symbols["stack"],
            "runtime_stack_gap": symbols["stack"] - symbols["bss_end"],
            "boot_stack_gap": symbols["stack"] - end,
        },
        "stage": {
            "address": stage_base,
            "bank": stage_base // BANK_SIZE,
            "offset": stage_base % BANK_SIZE,
            "limit_offset": stage_limit,
            "end_offset": stage_end_offset,
        },
        "stdlib": {
            "base": stdlib_base,
            "end": stdlib_end,
            "size": stdlib_end - stdlib_base,
        },
    }


def _read_layout(path: Path) -> dict[str, Any]:
    value = _read_json(path, "overlay layout")
    if value.get("schema") != LAYOUT_SCHEMA:
        raise StageError(f"layout schema must be {LAYOUT_SCHEMA}")
    return value


def extract_resident(linked_prg: Path, layout_path: Path, output: Path) -> None:
    layout = _read_layout(layout_path)
    load_base, _, data = _prg_span(linked_prg)
    resident = layout.get("resident")
    if not isinstance(resident, dict) or resident.get("load_base") != load_base:
        raise StageError("layout resident load base does not match linked PRG")
    file_end = resident.get("file_end")
    if type(file_end) is not int or not load_base < file_end <= BANK_SIZE:
        raise StageError("layout resident file end is invalid")
    size = file_end - load_base + PRG_HEADER_SIZE
    if size > len(data):
        raise StageError("resident span exceeds linked PRG")
    _atomic_write(output, data[:size])


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def audit(
    layout_path: Path,
    output: Path,
    *,
    min_runtime_stack_gap: int,
    min_boot_stack_gap: int,
    boot_stack_gap_target: int,
    min_post_boot_reserve: int,
    post_boot_reserve_target: int,
) -> dict[str, Any]:
    layout = _read_layout(layout_path)
    memory = layout.get("memory")
    if not isinstance(memory, dict):
        raise StageError("layout has no memory record")
    runtime_gap = memory.get("runtime_stack_gap")
    boot_gap = memory.get("boot_stack_gap")
    if type(runtime_gap) is not int or type(boot_gap) is not int:
        raise StageError("layout memory gaps must be integers")
    post_reserve = runtime_gap - min_runtime_stack_gap
    checks = {
        "runtime_stack_gap": runtime_gap >= min_runtime_stack_gap,
        "boot_stack_gap": boot_gap >= min_boot_stack_gap,
        "post_boot_reserve": post_reserve >= min_post_boot_reserve,
    }
    result = {
        "schema": "lisp65-workbench-overlay-audit-v1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "runtime_stack_gap": runtime_gap,
        "min_runtime_stack_gap": min_runtime_stack_gap,
        "boot_stack_gap": boot_gap,
        "min_boot_stack_gap": min_boot_stack_gap,
        "boot_stack_gap_target": boot_stack_gap_target,
        "boot_target_status": "met" if boot_gap >= boot_stack_gap_target else "miss",
        "boot_target_deficit": max(0, boot_stack_gap_target - boot_gap),
        "post_boot_reserve": post_reserve,
        "min_post_boot_reserve": min_post_boot_reserve,
        "post_boot_reserve_target": post_boot_reserve_target,
        "target_status": "met" if post_reserve >= post_boot_reserve_target else "miss",
        "target_deficit": max(0, post_boot_reserve_target - post_reserve),
        "resident_file_end": layout["resident"]["file_end"],
        "overlay_base": layout["overlay"]["base"],
        "overlay_end": layout["overlay"]["end"],
    }
    _atomic_write(output, _json_bytes(result))
    if result["status"] != "pass":
        failed = ",".join(name for name, passed in checks.items() if not passed)
        raise StageError(f"overlay footprint audit failed: {failed}")
    return result


def _descriptor(layout: dict[str, Any], overlay: bytes) -> bytes:
    record = layout["overlay"]
    build_id = layout["build_id"]
    base = record["base"]
    entry = record["entry"]
    size = record["size"]
    if len(overlay) != size:
        raise StageError(f"raw overlay size mismatch: ELF={size} actual={len(overlay)}")
    if any(type(value) is not int for value in (build_id, base, entry, size)):
        raise StageError("descriptor layout fields must be integers")
    if not 0 <= build_id <= 0xFFFFFFFF:
        raise StageError("build ID does not fit 32 bits")
    if not 0 <= base <= 0xFFFF or not 0 <= entry <= 0xFFFF or not 0 < size <= 0xFFFF:
        raise StageError("overlay descriptor field does not fit 16 bits")
    return struct.pack(
        "<4sBBIHHHH",
        DESCRIPTOR_MAGIC,
        DESCRIPTOR_VERSION,
        DESCRIPTOR_SIZE,
        build_id,
        base,
        entry,
        size,
        crc16_ccitt_false(overlay),
    )


def _resident_info(path: Path, layout: dict[str, Any]) -> dict[str, Any]:
    load_base, file_end, data = _prg_span(path)
    expected = layout["resident"]
    if load_base != expected["load_base"] or file_end != expected["file_end"]:
        raise StageError("resident PRG address span does not match final ELF layout")
    return {
        "file": path.name,
        "load_base": load_base,
        "file_end": file_end,
        "size": len(data),
        "sha256": _sha256(path),
    }


def _expected_outputs(
    *,
    profile: str,
    layout: dict[str, Any],
    overlay_path: Path,
    resident_path: Path,
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    stage_name: str,
    preload_name: str,
) -> tuple[bytes, bytes, dict[str, Any]]:
    overlay = overlay_path.read_bytes()
    descriptor = _descriptor(layout, overlay)
    stage = descriptor + overlay
    stdlib = stdlib_ext.read_bytes()
    stdlib_record = layout["stdlib"]
    stage_record = layout["stage"]
    padding = stage_record["address"] - stdlib_record["end"]
    if not 0 <= padding < STAGE_ALIGNMENT:
        raise StageError("stage is not the first 256-byte boundary after the stdlib image")
    if stage_record["offset"] + len(stage) > BANK_SIZE:
        raise StageError("descriptor plus overlay crosses an EXT-bank boundary")
    if stage_record["offset"] + len(stage) != stage_record["end_offset"]:
        raise StageError("stage end is not bound to descriptor plus overlay length")
    if stage_record["end_offset"] > stage_record["limit_offset"]:
        raise StageError("descriptor plus overlay reaches the Bank-5 namepool")
    preload = stdlib + bytes(padding) + stage
    crc = crc16_ccitt_false(overlay)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "profile": profile,
        "build_id": layout["build_id"],
        "descriptor": {
            "magic": DESCRIPTOR_MAGIC.decode("ascii"),
            "version": DESCRIPTOR_VERSION,
            "header_size": DESCRIPTOR_SIZE,
            "crc16": crc,
            "crc16_algorithm": "crc-16-ccitt-false",
        },
        "overlay": {
            **layout["overlay"],
            "file": overlay_path.name,
            "sha256": hashlib.sha256(overlay).hexdigest(),
        },
        "resident": _resident_info(resident_path, layout),
        "stage": {
            **stage_record,
            "file": stage_name,
            "padding_after_stdlib": padding,
            "size": len(stage),
            "sha256": hashlib.sha256(stage).hexdigest(),
        },
        "preload": {
            "base": stdlib_record["base"],
            "end": stdlib_record["base"] + len(preload),
            "file": preload_name,
            "size": len(preload),
            "sha256": hashlib.sha256(preload).hexdigest(),
        },
        "stdlib": {
            **stdlib_record,
            "file": stdlib_ext.name,
            "sha256": _sha256(stdlib_ext),
            "manifest": stdlib_manifest.name,
            "manifest_sha256": _sha256(stdlib_manifest),
        },
        "abi": {
            "contract": contract.name,
            "contract_id": "workbench-staged-overlay-abi-v1",
            "contract_sha256": _sha256(contract),
        },
    }
    return stage, preload, manifest


def pack(
    *,
    profile: str,
    layout_path: Path,
    overlay: Path,
    resident: Path,
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    stage_out: Path,
    preload_out: Path,
    manifest_out: Path,
) -> None:
    for path, label in (
        (overlay, "raw overlay"),
        (resident, "resident PRG"),
        (stdlib_ext, "stdlib EXT image"),
        (stdlib_manifest, "stdlib manifest"),
        (contract, "ABI contract"),
    ):
        _regular_file(path, label)
    layout = _read_layout(layout_path)
    stage, preload, manifest = _expected_outputs(
        profile=profile,
        layout=layout,
        overlay_path=overlay,
        resident_path=resident,
        stdlib_ext=stdlib_ext,
        stdlib_manifest=stdlib_manifest,
        contract=contract,
        stage_name=stage_out.name,
        preload_name=preload_out.name,
    )
    _atomic_write(stage_out, stage)
    _atomic_write(preload_out, preload)
    _atomic_write(manifest_out, _json_bytes(manifest))


def verify(
    *,
    profile: str,
    elf: Path,
    nm: Path,
    linked_prg: Path,
    layout_path: Path,
    overlay: Path,
    resident: Path,
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    stage: Path,
    preload: Path,
    manifest_path: Path,
    stage_limit: int,
) -> None:
    actual_layout = _read_layout(layout_path)
    derived = derive_layout(
        elf, nm, linked_prg, stdlib_ext, stdlib_manifest, contract, stage_limit
    )
    if actual_layout != derived:
        raise StageError("layout JSON is not an exact projection of the final ELF and inputs")
    _verify_outputs(
        profile=profile,
        layout=derived,
        overlay=overlay,
        resident=resident,
        stdlib_ext=stdlib_ext,
        stdlib_manifest=stdlib_manifest,
        contract=contract,
        stage=stage,
        preload=preload,
        manifest_path=manifest_path,
    )


def _verify_outputs(
    *,
    profile: str,
    layout: dict[str, Any],
    overlay: Path,
    resident: Path,
    stdlib_ext: Path,
    stdlib_manifest: Path,
    contract: Path,
    stage: Path,
    preload: Path,
    manifest_path: Path,
) -> None:
    for path, label in (
        (overlay, "raw overlay"),
        (resident, "resident PRG"),
        (stdlib_ext, "stdlib EXT image"),
        (stdlib_manifest, "stdlib manifest"),
        (contract, "ABI contract"),
        (stage, "staged descriptor/payload"),
        (preload, "combined EXT preload"),
        (manifest_path, "stage manifest"),
    ):
        _regular_file(path, label)
    expected_stage, expected_preload, expected_manifest = _expected_outputs(
        profile=profile,
        layout=layout,
        overlay_path=overlay,
        resident_path=resident,
        stdlib_ext=stdlib_ext,
        stdlib_manifest=stdlib_manifest,
        contract=contract,
        stage_name=stage.name,
        preload_name=preload.name,
    )
    _regular_file(stage, "staged descriptor/payload")
    _regular_file(preload, "combined EXT preload")
    if stage.read_bytes() != expected_stage:
        raise StageError("stage artifact does not match descriptor and raw overlay")
    if preload.read_bytes() != expected_preload:
        raise StageError("combined preload does not match stdlib padding and stage")
    actual_manifest = _read_json(manifest_path, "stage manifest")
    if actual_manifest != expected_manifest:
        raise StageError("stage manifest is not the exact strict binding of its inputs")


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="lisp65-workbench-overlay-stage-") as name:
        root = Path(name)
        stdlib = root / "stdlib.ext.bin"
        stdlib_manifest = root / "stdlib.manifest.json"
        contract = root / "contract.txt"
        overlay = root / "overlay.bin"
        resident = root / "resident.prg"
        layout_path = root / "layout.json"
        stage = root / "stage.bin"
        preload = root / "preload.ext.bin"
        manifest = root / "manifest.json"
        header_out = root / "stage-config.h"
        code = bytes(range(1, 18))
        index = struct.pack("<H", 0)
        node = struct.pack("<BBHHHH", 1, 0, 42, 0, 0, 0)
        patch = struct.pack("<HH", 0, 0)
        metadata_bytes = L65M_HEADER_SIZE + len(index) + len(node) + len(patch)
        metadata = struct.pack(
            L65M_HEADER_FORMAT,
            b"L65M", 1, L65M_HEADER_SIZE, 0, 0x050000,
            len(code), metadata_bytes,
            0, 1, 1, 1,
            L65M_HEADER_SIZE, L65M_HEADER_SIZE,
            L65M_HEADER_SIZE + len(index),
            L65M_HEADER_SIZE + len(index) + len(node),
            metadata_bytes, 0, 0,
        ) + index + node + patch
        stdlib_data = code + metadata
        stdlib.write_bytes(stdlib_data)
        _atomic_write(stdlib_manifest, _json_bytes({
            "base_addr": "0x050000",
            "entries": [{"lit_count": 1}],
            "external_image": {
                "bytes": len(stdlib_data),
                "code_bytes": len(code),
                "file_header_bytes": 0,
                "file_header_format": "none",
                "format": "lisp65-bytecode-p0-ext-image-v1",
                "metadata_bytes": len(metadata),
                "metadata_offset": len(code),
                "sha256": hashlib.sha256(stdlib_data).hexdigest(),
            },
        }))
        contract.write_text("profile=test\nflags=-Oz\n", encoding="ascii")
        overlay.write_bytes(bytes(range(1, 80)))
        load_base = 0x2001
        resident_end = 0x20FF
        resident.write_bytes(struct.pack("<H", load_base) + bytes(resident_end - load_base))
        _, stdlib_end, stage_base = _stdlib_layout(stdlib, stdlib_manifest)
        layout = {
            "schema": LAYOUT_SCHEMA,
            "build_id": _build_id(contract),
            "overlay": {
                "base": 0xC000,
                "end": 0xC000 + overlay.stat().st_size,
                "entry": 0xC008,
                "entry_symbol": ENTRY_SYMBOL,
                "size": overlay.stat().st_size,
            },
            "resident": {"load_base": load_base, "file_end": resident_end},
            "memory": {
                "bss_end": 0xB800,
                "stack": 0xD000,
                "runtime_stack_gap": 0x1800,
                "boot_stack_gap": 0xD000 - (0xC000 + overlay.stat().st_size),
            },
            "stage": {
                "address": stage_base,
                "bank": stage_base // BANK_SIZE,
                "offset": stage_base % BANK_SIZE,
                "limit_offset": 0xF000,
                "end_offset": stage_base % BANK_SIZE + DESCRIPTOR_SIZE + overlay.stat().st_size,
            },
            "stdlib": {"base": 0x50000, "end": stdlib_end, "size": stdlib.stat().st_size},
        }
        _atomic_write(layout_path, _json_bytes(layout))
        pack(
            profile="selftest",
            layout_path=layout_path,
            overlay=overlay,
            resident=resident,
            stdlib_ext=stdlib,
            stdlib_manifest=stdlib_manifest,
            contract=contract,
            stage_out=stage,
            preload_out=preload,
            manifest_out=manifest,
        )
        expected_stage, expected_preload, expected_manifest = _expected_outputs(
            profile="selftest",
            layout=layout,
            overlay_path=overlay,
            resident_path=resident,
            stdlib_ext=stdlib,
            stdlib_manifest=stdlib_manifest,
            contract=contract,
            stage_name=stage.name,
            preload_name=preload.name,
        )
        failures: list[str] = []
        try:
            write_header(stdlib, stdlib_manifest, contract, header_out)
            header_text = header_out.read_text(encoding="ascii")
            required_header_values = (
                f"LISP65_BOOT_STDLIB_IMAGE_BYTES {len(stdlib_data)}u",
                f"LISP65_BOOT_STDLIB_IMAGE_CRC16 0x{crc16_ccitt_false(stdlib_data):04x}u",
                f"LISP65_BOOT_STDLIB_BLOB_BYTES {len(code)}u",
                "LISP65_BOOT_STDLIB_ENTRY_COUNT 0u",
                "LISP65_BOOT_STDLIB_LIT_FIX_COUNT 1u",
                "LISP65_BOOT_STDLIB_LIT_SYMBOL_COUNT 0u",
                "LISP65_BOOT_STDLIB_LIT_CONS_COUNT 0u",
            )
            if any(value not in header_text for value in required_header_values):
                failures.append("positive-boot-binding-header")
        except StageError:
            failures.append("positive-boot-binding-header")
        if stage.read_bytes() != expected_stage:
            failures.append("positive-stage")
        if preload.read_bytes() != expected_preload:
            failures.append("positive-preload")
        if _read_json(manifest, "selftest manifest") != expected_manifest:
            failures.append("positive-manifest")
        try:
            _verify_outputs(
                profile="selftest", layout=layout, overlay=overlay, resident=resident,
                stdlib_ext=stdlib, stdlib_manifest=stdlib_manifest, contract=contract,
                stage=stage, preload=preload, manifest_path=manifest,
            )
        except StageError:
            failures.append("positive-strict-verify")
        descriptor = stage.read_bytes()[:DESCRIPTOR_SIZE]
        fields = struct.unpack("<4sBBIHHHH", descriptor)
        if fields[:2] != (DESCRIPTOR_MAGIC, DESCRIPTOR_VERSION) or fields[2] != DESCRIPTOR_SIZE:
            failures.append("descriptor-header")
        if fields[-1] != crc16_ccitt_false(overlay.read_bytes()):
            failures.append("descriptor-crc")
        if crc16_ccitt_false(b"123456789") != 0x29B1:
            failures.append("crc-known-vector")
        def rejects(label: str, path: Path, content: bytes) -> None:
            original = path.read_bytes()
            path.write_bytes(content)
            try:
                _verify_outputs(
                    profile="selftest", layout=layout, overlay=overlay, resident=resident,
                    stdlib_ext=stdlib, stdlib_manifest=stdlib_manifest, contract=contract,
                    stage=stage, preload=preload, manifest_path=manifest,
                )
            except StageError:
                pass
            else:
                failures.append(label)
            finally:
                path.write_bytes(original)

        mutated = bytearray(expected_stage)
        mutated[-1] ^= 1
        rejects("mutation-stage", stage, bytes(mutated))
        mutated = bytearray(expected_preload)
        mutated[-1] ^= 1
        rejects("mutation-preload", preload, bytes(mutated))
        changed_manifest = dict(expected_manifest)
        changed_manifest["build_id"] ^= 1
        rejects("mutation-manifest", manifest, _json_bytes(changed_manifest))
        rejects("mutation-contract", contract, contract.read_bytes() + b"changed=1\n")
        original_stdlib = stdlib.read_bytes()
        mutated_stdlib = bytearray(original_stdlib)
        mutated_stdlib[0] ^= 1
        stdlib.write_bytes(mutated_stdlib)
        try:
            write_header(stdlib, stdlib_manifest, contract, header_out)
        except StageError:
            pass
        else:
            failures.append("boot-binding-sha-mutation")
        finally:
            stdlib.write_bytes(original_stdlib)
        original_stdlib_manifest = stdlib_manifest.read_bytes()
        mutated_stdlib = bytearray(original_stdlib)
        mutated_stdlib[len(code) + L65M_HEADER_SIZE + len(index)] = 0xff
        stdlib.write_bytes(mutated_stdlib)
        changed_stdlib_manifest = _read_json(stdlib_manifest, "selftest stdlib manifest")
        changed_stdlib_manifest["external_image"]["sha256"] = hashlib.sha256(
            mutated_stdlib
        ).hexdigest()
        _atomic_write(stdlib_manifest, _json_bytes(changed_stdlib_manifest))
        try:
            write_header(stdlib, stdlib_manifest, contract, header_out)
        except StageError as exc:
            if "unknown kind" not in str(exc):
                failures.append("boot-binding-literal-kind-error")
        else:
            failures.append("boot-binding-literal-kind-mutation")
        finally:
            stdlib.write_bytes(original_stdlib)
            stdlib_manifest.write_bytes(original_stdlib_manifest)
        mutated_stdlib = bytearray(original_stdlib)
        patch_node_at = len(code) + L65M_HEADER_SIZE + len(index) + len(node) + 2
        mutated_stdlib[patch_node_at:patch_node_at + 2] = struct.pack("<H", 1)
        stdlib.write_bytes(mutated_stdlib)
        changed_stdlib_manifest = _read_json(stdlib_manifest, "selftest stdlib manifest")
        changed_stdlib_manifest["external_image"]["sha256"] = hashlib.sha256(
            mutated_stdlib
        ).hexdigest()
        _atomic_write(stdlib_manifest, _json_bytes(changed_stdlib_manifest))
        try:
            write_header(stdlib, stdlib_manifest, contract, header_out)
        except StageError as exc:
            if "every CodeObject literal root" not in str(exc):
                failures.append("boot-binding-patch-coverage-error")
        else:
            failures.append("boot-binding-patch-coverage-mutation")
        finally:
            stdlib.write_bytes(original_stdlib)
            stdlib_manifest.write_bytes(original_stdlib_manifest)
        tight_layout = json.loads(json.dumps(layout))
        tight_layout["stage"]["limit_offset"] = tight_layout["stage"]["end_offset"] - 1
        try:
            _expected_outputs(
                profile="selftest", layout=tight_layout, overlay_path=overlay,
                resident_path=resident, stdlib_ext=stdlib,
                stdlib_manifest=stdlib_manifest, contract=contract,
                stage_name=stage.name, preload_name=preload.name,
            )
        except StageError:
            pass
        else:
            failures.append("stage-namepool-limit")
        if expected_preload[: stdlib.stat().st_size] != stdlib.read_bytes():
            failures.append("preload-prefix")
        if failures:
            raise StageError("selftest failures: " + ",".join(failures))
    print("workbench-overlay-stage selftest: PASS cases=17 failures=0")


def _common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stdlib-ext", type=Path, required=True)
    parser.add_argument("--stdlib-manifest", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)


def _artifact_inputs(parser: argparse.ArgumentParser) -> None:
    _common_inputs(parser)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--resident", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--preload", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profile", required=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    _common_inputs(prepare_parser)
    prepare_parser.add_argument("--out-header", type=Path, required=True)
    layout_parser = subparsers.add_parser("layout")
    _common_inputs(layout_parser)
    layout_parser.add_argument("--elf", type=Path, required=True)
    layout_parser.add_argument("--nm", type=Path, required=True)
    layout_parser.add_argument("--linked-prg", type=Path, required=True)
    layout_parser.add_argument("--out", type=Path, required=True)
    layout_parser.add_argument("--stage-limit", type=lambda value: int(value, 0), required=True)
    extract_parser = subparsers.add_parser("extract-resident")
    extract_parser.add_argument("--linked-prg", type=Path, required=True)
    extract_parser.add_argument("--layout", type=Path, required=True)
    extract_parser.add_argument("--out", type=Path, required=True)
    pack_parser = subparsers.add_parser("pack")
    _artifact_inputs(pack_parser)
    verify_parser = subparsers.add_parser("verify")
    _artifact_inputs(verify_parser)
    verify_parser.add_argument("--elf", type=Path, required=True)
    verify_parser.add_argument("--nm", type=Path, required=True)
    verify_parser.add_argument("--linked-prg", type=Path, required=True)
    verify_parser.add_argument("--stage-limit", type=lambda value: int(value, 0), required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--layout", type=Path, required=True)
    audit_parser.add_argument("--out", type=Path, required=True)
    audit_parser.add_argument("--min-runtime-stack-gap", type=int, required=True)
    audit_parser.add_argument("--min-boot-stack-gap", type=int, required=True)
    audit_parser.add_argument("--boot-stack-gap-target", type=int, required=True)
    audit_parser.add_argument("--min-post-boot-reserve", type=int, required=True)
    audit_parser.add_argument("--post-boot-reserve-target", type=int, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            write_header(args.stdlib_ext, args.stdlib_manifest, args.contract, args.out_header)
            print(f"workbench-overlay-stage: PREPARED {args.out_header}")
        elif args.command == "layout":
            value = derive_layout(
                args.elf, args.nm, args.linked_prg,
                args.stdlib_ext, args.stdlib_manifest, args.contract, args.stage_limit,
            )
            _atomic_write(args.out, _json_bytes(value))
            print(f"workbench-overlay-stage: LAYOUT {args.out}")
        elif args.command == "extract-resident":
            extract_resident(args.linked_prg, args.layout, args.out)
            print(f"workbench-overlay-stage: RESIDENT {args.out} bytes={args.out.stat().st_size}")
        elif args.command == "pack":
            pack(
                profile=args.profile, layout_path=args.layout,
                overlay=args.overlay, resident=args.resident,
                stdlib_ext=args.stdlib_ext, stdlib_manifest=args.stdlib_manifest,
                contract=args.contract, stage_out=args.stage,
                preload_out=args.preload, manifest_out=args.manifest,
            )
            print(f"workbench-overlay-stage: PACK {args.manifest}")
        elif args.command == "verify":
            verify(
                profile=args.profile, elf=args.elf, nm=args.nm,
                linked_prg=args.linked_prg, layout_path=args.layout,
                overlay=args.overlay, resident=args.resident,
                stdlib_ext=args.stdlib_ext, stdlib_manifest=args.stdlib_manifest,
                contract=args.contract, stage=args.stage,
                preload=args.preload, manifest_path=args.manifest,
                stage_limit=args.stage_limit,
            )
            print(f"workbench-overlay-stage: PASS profile={args.profile}")
        elif args.command == "audit":
            result = audit(
                args.layout, args.out,
                min_runtime_stack_gap=args.min_runtime_stack_gap,
                min_boot_stack_gap=args.min_boot_stack_gap,
                boot_stack_gap_target=args.boot_stack_gap_target,
                min_post_boot_reserve=args.min_post_boot_reserve,
                post_boot_reserve_target=args.post_boot_reserve_target,
            )
            print(
                "workbench-overlay-audit: PASS "
                f"post_boot_reserve={result['post_boot_reserve']} "
                f"target={result['post_boot_reserve_target']} "
                f"target_status={result['target_status']} "
                f"target_deficit={result['target_deficit']} "
                f"boot_stack_gap={result['boot_stack_gap']} "
                f"boot_target={result['boot_stack_gap_target']} "
                f"boot_target_status={result['boot_target_status']}"
            )
        else:
            selftest()
    except StageError as exc:
        print(f"workbench-overlay-stage: FAIL {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
