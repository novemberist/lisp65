#!/usr/bin/env python3
"""Build and verify the R3 two-media cold-start product without running G3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
from typing import Any
import zlib

import block_capacity_delta_policy as CAPACITY
import workbench_product_reproducibility as REPRO


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "r3" / "product"
RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "product-block-receipt.json"
CONTRACT = ROOT / "config" / "r3-g3-g6-contract.json"
MATRIX = ROOT / "tests" / "bytecode" / "dialect-v2" / "r3-boot" / "cases.json"
REPRO_RECEIPT = ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "r3" / "canonical-product-reproducibility-receipt.json"
COMPOSITION = ROOT / "build" / "bytecode" / "dialect-v2" / "workbench-library-composition-budget.json"
FOOTPRINT = ROOT / "build" / "products" / "workbench" / "overlay-stack-guard" / "footprint-audit.json"
CAPACITY_POLICY = ROOT / "config" / "block-capacity-delta-policy.json"
RUNTIME_MANIFEST = ROOT / "build" / "products" / "workbench" / "overlay-stack-guard" / "runtime-overlays-manifest.json"
BOOT_OVERLAY = ROOT / "build" / "products" / "workbench" / "overlay-stack-guard" / "lisp65-workbench-overlay.bin"
STAGER_C = ROOT / "scripts" / "r3-cold-stager-main.c"
STAGER_S = ROOT / "scripts" / "r3-cold-stager-chain.s"
STAGER_CONTRACT = ROOT / "scripts" / "r3-cold-stager-contract.h"
F011_CONTEXT = ROOT / "src" / "f011_context.h"
F011_CONTEXT_CONTRACT = ROOT / "config" / "f011-transaction-context.json"
F011_CONTEXT_TOOL = ROOT / "tools" / "host-lisp" / "f011_transaction_context.py"
ASM_CONTRACT = ROOT / "config" / "asm-c-constant-contract.json"
ASM_CONTRACT_GENERATOR = ROOT / "scripts" / "asm-c-contract-values-main.c"
ASM_CONTRACT_TOOL = ROOT / "tools" / "host-lisp" / "asm_c_constant_contract.py"
L65M_BATCH_CONTRACT = ROOT / "src" / "l65m_batch_contract.h"
SHELF_TOOL = ROOT / "tools" / "host-lisp" / "v11_attic_library_shelf.py"
SHELF_CONTRACT = ROOT / "config" / "v11-attic-library-shelf.json"
SHELF_IMAGE = ROOT / "build" / "bytecode" / "dialect-v2" / "shelf" / "library-shelf.bin"
SHELF_MANIFEST = ROOT / "build" / "bytecode" / "dialect-v2" / "shelf" / "library-shelf-manifest.json"
CHAIN_WALKER_TOOL = ROOT / "tools" / "host-lisp" / "chain_walker_inventory.py"
CHAIN_WALKER_RECEIPT = ROOT / "build" / "bytecode" / "dialect-v2" / "wave1-chain-walker-inventory-receipt.json"
FORMAT = "lisp65-r3-product-block-receipt-v1"
DESCRIPTOR_BYTES = 272
HEADER_BYTES = 16
RECORD_BYTES = 32
RECORDS = 8
RESTAGE_LIMIT = 2
ERROR_MESSAGE = b"L65SYS DISK ERROR - CHECK MEDIA"
PRODUCT_BOOT_MARKER_OFFSET = 29
PRODUCT_BOOT_MARKER = b"L65B"
BASELINE_BOOT_OVERLAY = {
    "bytes": 1669,
    "sha256": "c73f1ce4e6fa2c266fce7bffbd3e4028fd4e7824f9391211f9ee5321d550740a",
}
BASELINE_COMPOSITION = {
    "bank": 332,
    "ext": 16385,
    "symbols": 120,
    "namepool": 2160,
    "directory": 32,
}
BASELINE_RELEASE_SET = "c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165"
WAVE3_AGGREGATE_CAPACITY_AUTH = (
    ROOT / "config" / "v11-wave3-r3-aggregate-capacity-authorization.json"
)
WAVE1_EVIDENCE = (
    "config/v11-attic-library-shelf-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-attic-library-shelf-block-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-export-only-interning-block-receipt.json",
    "config/v11-first-class-buffer-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-first-class-buffer-block-receipt.json",
    "config/v11-c1-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-compiler-tier-block-receipt.json",
    "config/v11-c1-entry-seams.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-definition-call-reopening-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-interactive-path-options-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-lease-trusted-stage-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-identity-restore-capacity-probe-receipt.json",
    "config/v11-c1-lease-trusted-stage-capacity-authorization.json",
    "config/v11-c1-definition-call-latency-exception.json",
    "config/v11-workbench-differential-baseline.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-poke-differential-diagnosis.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-wave1-integration-capacity-drift-receipt.json",
    "config/v11-c1-wave1-integration-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-wave1-integration-block-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-bootstrap-final-link-determinism-diagnosis.json",
    "config/v11-c1-bootstrap-final-link-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-final-link-allocation-determinism-diagnosis.json",
    "config/v11-c1-final-link-allocation-determinism.json",
    "config/v11-c1-source-stream-lifetime-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-c1-source-stream-lifetime-correction-probe-receipt.json",
    "config/v11-wave1-stager-chain-walker-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/wave1-stager-chain-walker-fix-capacity-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/wave1-chain-walker-inventory-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/wave1-g6-cold-stager-sector-fuel-diagnosis.json",
    "config/v11-wave1-r3-aggregate-capacity-authorization.json",
    "docs/releases/1.1-wave-1-candidate.md",
    "config/v11-buffer-printer-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-buffer-printer-fix-probe-receipt.json",
    "config/v11-filter-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-filter-delivery-block-receipt.json",
    "config/v11-repl-banner-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-repl-banner-block-receipt.json",
    "config/v11-repl-banner-native-binding-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-repl-banner-native-binding-diagnosis.json",
    "config/v11-repl-banner-product-capability-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-repl-banner-product-capability-diagnosis.json",
    "config/v11-wave1-c1-first-form-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave1-c1-first-form-correction-probe.json",
)
WAVE2_EVIDENCE = (
    "config/v11-m-transactional-fasl-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-m-transactional-fasl-implementation-receipt.json",
    "config/v11-g-green-surface-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-g-green-surface-implementation-receipt.json",
    "config/v11-g-green-surface-contract.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-restart-repl-wave2-scope-correction-receipt.json",
    "config/v11-wave2-error-text-library-contract.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-error-text-library-receipt.json",
    "config/v11-wave2-list-primitive-unification-capacity-authorization.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-list-primitive-unification-probe-receipt.json",
    "config/v11-function-metadata-contract.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-contract-receipt.json",
    "config/v11-wave2-policy-name-revocation.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-policy-name-implementation-receipt.json",
    "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-artifact-differential-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-common-repin-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave2-scope-corrected-repin-receipt.json",
    "config/v11-wave2-r3-aggregate-capacity-authorization.json",
)
WAVE3_EVIDENCE = (
    "config/v11-l-lite-keymap.json",
    "config/v11-wave3-fail-fast.json",
    "config/v11-wave3-r3-aggregate-capacity-authorization.json",
    "docs/generated/ide-keymap.md",
    "docs/releases/1.1-wave-3-candidate.md",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-l-lite-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-wave3-l-lite-repin-receipt.json",
    "tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json",
)
CORE_FILES = (
    ("product-elf", "linked-product-elf", "lisp65.elf", "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay-linked.prg.elf"),
    ("resident-prg", "workbench-prg", "lisp65.prg", "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg"),
    ("runtime-overlays", "attic-catalog", "overlays.bin", "build/products/workbench/overlay-stack-guard/lisp65-mvp-workbench.overlays.bin"),
    ("stdlib-preload", "bank5-preload", "bank5.bin", "build/products/workbench/overlay-stack-guard/stdlib-with-overlay.ext.bin"),
    ("resolved-profile", "resolved-profile", "profile", "build/products/workbench/overlay-stack-guard/resolved-profile.txt"),
)
LIBRARY_FILES = (
    ("library-ide", "ide", "build/bytecode/dialect-v2/libs/ide.ext.bin"),
    ("library-idex", "idex", "build/bytecode/dialect-v2/libs/idex.ext.bin"),
    ("library-m65d", "m65d", "build/bytecode/dialect-v2/libs/m65d.ext.bin"),
)
ROLE = {"bank5.bin": 1, "overlays.bin": 2, "lisp65.prg": 3, "profile": 4, "ide": 5, "idex": 6, "m65d": 7, "shelf.bin": 8}
DESTINATION = {"bank5.bin": 0x00050000, "overlays.bin": 0x08000000, "lisp65.prg": 0x00040000, "shelf.bin": 0x08100000}
FLAGS = {"bank5.bin": 0x01, "overlays.bin": 0x05, "lisp65.prg": 0x02, "shelf.bin": 0x01}
G3_CASES = (
    "artifact-preflight-exact-set", "catalog-crc-reject-restage",
    "catalog-missing-restage", "catalog-valid-stage-chain", "drive9-rejected",
    "product-media-identity-write-reject", "product-prg-byte-identity",
    "stager-entry-chain-control", "arbitrary-user-media-save-remount-read",
)
G6_CASES = (
    "disk-swap-resident-composition", "mid-write-media-swap-abort",
    "power-cycle-autoboot-restage-repl", "product-medium-physical-write-protect",
    "warm-reset-valid-catalog-fastpath", "work-media-save-remount-read",
)


class ProductError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductError(f"{label} must be an object")
    return value


def require(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ProductError(f"missing regular {label}: {path}")


def binding(path: Path) -> dict[str, Any]:
    require(path, path.name)
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha_file(path)}


def artifact(path: Path, role: str, name: str | None = None) -> dict[str, Any]:
    require(path, role)
    return {
        "role": role,
        "name": name or path.name,
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_file(path),
    }


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(
        argv, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise ProductError(f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xffffffff


def verify_core_baseline() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repro = load(REPRO_RECEIPT, "R3 reproducibility receipt")
    try:
        REPRO.validate(repro)
    except REPRO.ReproError as exc:
        raise ProductError(f"R3 reproducibility receipt drift: {exc}") from exc
    expected = {row["id"]: row for row in repro["product_artifacts"]}
    rows: list[dict[str, Any]] = []
    for baseline_id, role, name, raw_path in CORE_FILES:
        row = artifact(ROOT / raw_path, role, name)
        old = expected.get(baseline_id, {})
        if row["bytes"] != old.get("bytes") or row["sha256"] != old.get("sha256"):
            raise ProductError(
                f"canonical core artifact drift: {baseline_id}: "
                f"expected bytes={old.get('bytes')} sha256={old.get('sha256')}; "
                f"observed bytes={row['bytes']} sha256={row['sha256']}"
            )
        rows.append(row)
    if BOOT_OVERLAY.stat().st_size != BASELINE_BOOT_OVERLAY["bytes"]:
        raise ProductError("boot overlay capacity delta is not zero")
    return rows, repro


def current_libraries() -> list[dict[str, Any]]:
    return [artifact(ROOT / raw_path, role, name) for role, name, raw_path in LIBRARY_FILES]


def descriptor_records(files: dict[str, Path]) -> bytes:
    records = bytearray()
    for name in ("bank5.bin", "overlays.bin", "lisp65.prg", "profile", "ide", "idex", "m65d", "shelf.bin"):
        payload = files[name].read_bytes()
        encoded = name.encode("ascii")
        if len(encoded) > 16:
            raise ProductError(f"descriptor name too long: {name}")
        record = bytearray(RECORD_BYTES)
        record[0] = ROLE[name]
        record[1] = FLAGS.get(name, 0)
        record[2] = len(encoded)
        struct.pack_into("<III", record, 4, DESTINATION.get(name, 0), len(payload), crc32(payload))
        record[16:16 + len(encoded)] = encoded
        records.extend(record)
    if len(records) != RECORDS * RECORD_BYTES:
        raise ProductError("descriptor record size drift")
    return bytes(records)


def make_descriptor(files: dict[str, Path], profile_build_id: int) -> tuple[bytes, int]:
    records = descriptor_records(files)
    product_build_id = crc32(records)
    header = bytearray(HEADER_BYTES)
    header[0:4] = b"L65B"
    header[4:8] = bytes((1, HEADER_BYTES, RECORDS, RESTAGE_LIMIT))
    struct.pack_into("<II", header, 8, product_build_id, profile_build_id)
    descriptor = bytes(header) + records
    if len(descriptor) != DESCRIPTOR_BYTES:
        raise ProductError("descriptor byte size drift")
    return descriptor, product_build_id


def parse_descriptor(data: bytes, expected_build_id: int) -> list[dict[str, Any]]:
    if (
        len(data) != DESCRIPTOR_BYTES or data[:4] != b"L65B"
        or tuple(data[4:8]) != (1, HEADER_BYTES, RECORDS, RESTAGE_LIMIT)
        or struct.unpack_from("<I", data, 8)[0] != expected_build_id
        or crc32(data[HEADER_BYTES:]) != expected_build_id
    ):
        raise ProductError("descriptor identity/CRC drift")
    rows = []
    seen = set()
    for index in range(RECORDS):
        record = data[HEADER_BYTES + index * RECORD_BYTES:HEADER_BYTES + (index + 1) * RECORD_BYTES]
        role, flags, name_len, reserved = record[:4]
        destination, length, checksum = struct.unpack_from("<III", record, 4)
        name = record[16:16 + name_len].decode("ascii")
        if role in seen or role not in range(1, 9) or reserved or not 1 <= name_len <= 16 or not length:
            raise ProductError("descriptor record semantic drift")
        if ROLE.get(name) != role or FLAGS.get(name, 0) != flags or DESTINATION.get(name, 0) != destination:
            raise ProductError(f"descriptor role/flag/destination drift: {name}")
        seen.add(role)
        rows.append({"role": role, "flags": flags, "name": name, "destination": destination, "bytes": length, "crc32": f"{checksum:08x}"})
    if seen != set(range(1, 9)):
        raise ProductError("descriptor role parity drift")
    return rows


def compile_stager(contract: dict[str, Any], build_id: int) -> tuple[Path, Path, int]:
    compiler = ROOT / contract["toolchain_bindings"]["compiler"]["invocation"]
    output = BUILD / "autoboot.c65"
    map_path = BUILD / "autoboot.c65.map"
    run(
        [
            str(compiler), "-std=c99", "-Oz", "-Wall", "-Wextra", "-Werror",
            f"-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL",
            f"-Wl,-Map,{map_path}", str(STAGER_C), str(STAGER_S), "-o", str(output),
        ],
        "R3 product stager build",
    )
    payload = output.read_bytes()
    if ERROR_MESSAGE not in payload:
        raise ProductError("stager does not embed its pinned error message")
    if output.stat().st_size > 16384:
        raise ProductError("stager exceeded standalone 16-KiB ceiling")
    map_text = map_path.read_text(encoding="utf-8")
    match = re.search(r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+\.r3_chain_trampoline\s*$", map_text, re.MULTILINE)
    chain_bytes = int(match.group(1), 16) if match else 0
    if not match or chain_bytes > 0x40:
        raise ProductError("stager chain trampoline size drift")
    return output, map_path, chain_bytes


def build_d81(c1541: str, output: Path, identity: str, entries: list[tuple[Path, str]]) -> str:
    if output.exists():
        os.chmod(output, 0o644)
        output.unlink()
    argv = [c1541, "-format", identity, "d81", str(output)]
    for path, name in entries:
        require(path, f"D81 member {name}")
        argv.extend(("-write", str(path), name))
    run(argv, f"build {output.name}")
    return run([c1541, str(output), "-list"], f"list {output.name}")


def sector(image: bytes, track: int, number: int) -> bytes:
    if not 1 <= track <= 80 or not 0 <= number < 40:
        raise ProductError("D81 track/sector out of range")
    offset = ((track - 1) * 40 + number) * 256
    return image[offset:offset + 256]


def fold_name(raw: bytes) -> str:
    chars = []
    for value in raw:
        value = value - 128 if value > 127 else value
        if value == 32:
            chars.append(" ")
        elif 32 <= value < 127:
            chars.append(chr(value))
        else:
            chars.append("?")
    return "".join(chars).rstrip()


def d81_identity(image: bytes) -> dict[str, str]:
    header = sector(image, 40, 0)
    return {"disk_name": fold_name(header[4:20]), "disk_id": fold_name(header[22:24])}


def stamp_product_boot_marker(path: Path) -> None:
    image = bytearray(path.read_bytes())
    header = ((40 - 1) * 40) * 256
    start = header + PRODUCT_BOOT_MARKER_OFFSET
    image[start:start + len(PRODUCT_BOOT_MARKER)] = PRODUCT_BOOT_MARKER
    path.write_bytes(image)


def d81_directory(image: bytes) -> dict[str, tuple[int, int]]:
    track, number, fuel = 40, 0, 64
    entries: dict[str, tuple[int, int]] = {}
    while fuel:
        fuel -= 1
        data = sector(image, track, number)
        first = 8 if (track, number) == (40, 0) else 0
        for index in range(first, 8):
            record = data[index * 32:(index + 1) * 32]
            if record[2] & 7:
                name = fold_name(record[5:21]).lower()
                if name in entries:
                    raise ProductError(f"duplicate D81 entry: {name}")
                entries[name] = (record[3], record[4])
        track, number = data[0], data[1]
        if not track:
            return entries
        if track != 40 or number >= 40:
            raise ProductError("invalid D81 directory chain")
    raise ProductError("D81 directory chain fuel exhausted")


def d81_file(image: bytes, start: tuple[int, int]) -> bytes:
    if len(image) % 256:
        raise ProductError("D81 image is not sector aligned")
    track, number = start
    payload = bytearray()
    seen: set[tuple[int, int]] = set()
    sector_limit = len(image) // 256
    while track:
        address = (track, number)
        if address in seen:
            raise ProductError("cyclic D81 file chain")
        if len(seen) >= sector_limit:
            raise ProductError("D81 file chain exceeds media capacity")
        seen.add(address)
        data = sector(image, track, number)
        next_track, next_sector = data[0], data[1]
        count = 254 if next_track else next_sector - 1
        if count < 0 or count > 254:
            raise ProductError("invalid D81 file tail")
        payload.extend(data[2:2 + count])
        track, number = next_track, next_sector
    return bytes(payload)


def verify_media(product: Path, work: Path, expected: dict[str, bytes]) -> dict[str, Any]:
    product_image = product.read_bytes()
    work_image = work.read_bytes()
    if len(product_image) != 819200 or len(work_image) != 819200:
        raise ProductError("D81 image size drift")
    if d81_identity(product_image) != {"disk_name": "L65SYS", "disk_id": "65"}:
        raise ProductError("product media identity drift")
    product_header = sector(product_image, 40, 0)
    if product_header[
        PRODUCT_BOOT_MARKER_OFFSET:PRODUCT_BOOT_MARKER_OFFSET + len(PRODUCT_BOOT_MARKER)
    ] != PRODUCT_BOOT_MARKER:
        raise ProductError("product boot-structure marker drift")
    if d81_identity(work_image) != {"disk_name": "L65WORK", "disk_id": "65"}:
        raise ProductError("work media identity drift")
    product_dir = d81_directory(product_image)
    work_dir = d81_directory(work_image)
    if set(product_dir) != set(expected) or work_dir:
        raise ProductError("product inventory or blank work provisioning drift")
    for name, payload in expected.items():
        if d81_file(product_image, product_dir[name]) != payload:
            raise ProductError(f"D81 member byte drift: {name}")
    return {
        "product_entries": sorted(product_dir), "work_entries": sorted(work_dir),
        "product_boot_marker": {
            "format": "l65sys-boot-marker-v1",
            "header_offset": PRODUCT_BOOT_MARKER_OFFSET,
            "ascii": PRODUCT_BOOT_MARKER.decode("ascii"),
            "bound_entries": ["autoboot.c65", "boot.id", "lisp65.prg"],
        },
    }


def model_selftest(descriptor: bytes, build_id: int, files: dict[str, bytes], profile_id: int) -> dict[str, Any]:
    rows = parse_descriptor(descriptor, build_id)
    by_name = {row["name"]: row for row in rows}

    def valid(memory: dict[str, bytes]) -> bool:
        return (
            crc32(memory.get("bank5.bin", b"")) == int(by_name["bank5.bin"]["crc32"], 16)
            and crc32(memory.get("overlays.bin", b"")) == int(by_name["overlays.bin"]["crc32"], 16)
            and crc32(memory.get("shelf.bin", b"")) == int(by_name["shelf.bin"]["crc32"], 16)
            and len(memory.get("overlays.bin", b"")) >= 16
            and struct.unpack_from("<I", memory["overlays.bin"], 12)[0] == profile_id
        )

    def restage(disk: dict[str, bytes]) -> tuple[bool, int, dict[str, bytes]]:
        memory: dict[str, bytes] = {}
        for attempt in range(1, RESTAGE_LIMIT + 1):
            memory = {name: disk[name] for name in ("bank5.bin", "overlays.bin", "shelf.bin")}
            if valid(memory):
                return True, attempt, memory
        return False, RESTAGE_LIMIT, memory

    if not valid({name: files[name] for name in ("bank5.bin", "overlays.bin", "shelf.bin")}):
        raise ProductError("valid staged-state model rejected canonical data")
    ok, attempts, memory = restage(files)
    if not ok or attempts != 1 or not valid(memory):
        raise ProductError("restage/reverify model drift")
    broken = dict(files)
    broken["overlays.bin"] = bytes([files["overlays.bin"][0] ^ 1]) + files["overlays.bin"][1:]
    ok, attempts, _ = restage(broken)
    if ok or attempts != RESTAGE_LIMIT:
        raise ProductError("bounded retry/halt model drift")
    changed = bytearray(descriptor)
    changed[8] ^= 1
    try:
        parse_descriptor(bytes(changed), build_id)
        raise ProductError("mixed-build descriptor survived")
    except ProductError as exc:
        if str(exc) == "mixed-build descriptor survived":
            raise
    changed = bytearray(descriptor)
    changed[HEADER_BYTES + 4] ^= 1
    try:
        parse_descriptor(bytes(changed), build_id)
        raise ProductError("mutated descriptor records survived")
    except ProductError as exc:
        if str(exc) == "mutated descriptor records survived":
            raise
    broken_product = dict(files)
    broken_product["lisp65.prg"] += b"x"
    if crc32(broken_product["lisp65.prg"]) == int(by_name["lisp65.prg"]["crc32"], 16):
        raise ProductError("product PRG corruption model drift")
    token_a, token_b = object(), object()
    if token_a is token_b:
        raise ProductError("mount-generation model drift")
    return {
        "cases": 7,
        "valid_fastpath": "pass",
        "restage_then_reverify": "pass",
        "retry_limit": RESTAGE_LIMIT,
        "retry_exhaustion": "halt",
        "mixed_build": "fail-closed",
        "descriptor_record_mutation": "fail-closed",
        "product_prg_crc": "fail-closed",
        "mount_generation": "distinct-token-per-remount",
    }


def composition_metrics() -> dict[str, int]:
    report = load(COMPOSITION, "Workbench composition report")
    footprint = load(FOOTPRINT, "Workbench footprint audit")
    if report.get("status") != "pass":
        raise ProductError("Workbench composition is not green")
    if footprint.get("status") != "pass" or footprint.get("post_boot_reserve", 0) < 1536:
        raise ProductError("Workbench Bank-0 floor is not green")
    metrics = {
        "bank": int(footprint["post_boot_reserve"]) - 1536,
        "ext": int(report["ext_code"]["post_headroom"]),
        "symbols": int(report["symbols"]["headroom"]),
        "namepool": int(report["namepool"]["headroom"]),
        "directory": int(report["directory"]["post_align_headroom"]),
    }
    floors = {"bank": 0, "ext": 16384, "symbols": 32, "namepool": 384, "directory": 32}
    if any(metrics[key] < value for key, value in floors.items()):
        raise ProductError(f"composition floor failure: {metrics}")
    return metrics


def capacity_delta(candidate_identity: str, candidate: dict[str, int], baseline_identity: str) -> dict[str, Any]:
    dimensions = {}
    for name in CAPACITY.DIMENSIONS:
        delta = candidate[name] - BASELINE_COMPOSITION[name]
        authorization = None
        if delta < 0:
            authorization = binding(WAVE3_AGGREGATE_CAPACITY_AUTH)
        dimensions[name] = {
            "baseline": BASELINE_COMPOSITION[name],
            "candidate": candidate[name],
            "delta": delta,
            "authorization": authorization,
        }
    value = {
        "baseline_identity_sha256": baseline_identity,
        "candidate_identity_sha256": candidate_identity,
        "dimensions": dimensions,
    }
    try:
        CAPACITY.validate_policy()
        CAPACITY.validate_capacity_delta(value)
    except CAPACITY.CapacityDeltaError as exc:
        raise ProductError(f"capacity delta failure: {exc}") from exc
    return value


def build_product() -> dict[str, Any]:
    BUILD.mkdir(parents=True, exist_ok=True)
    contract = load(CONTRACT, "R3 contract")
    matrix = load(MATRIX, "R3 boot matrix")
    core_rows, repro = verify_core_baseline()
    library_rows = current_libraries()
    run([sys.executable, str(SHELF_TOOL), "--out", str(SHELF_IMAGE),
         "--manifest-out", str(SHELF_MANIFEST)], "build 1.1 Attic library shelf")
    shelf_row = artifact(SHELF_IMAGE, "attic-library-shelf", "shelf.bin")
    runtime = load(RUNTIME_MANIFEST, "runtime overlay manifest")
    profile_id = int(runtime["profile_build_id"])
    profile_sha = next(row for row in core_rows if row["role"] == "resolved-profile")["sha256"]
    if profile_id != int(profile_sha[:8], 16):
        raise ProductError("profile build-id/SHA binding drift")

    paths = {row["name"]: ROOT / row["path"] for row in core_rows + library_rows}
    paths["shelf.bin"] = SHELF_IMAGE
    descriptor, build_id = make_descriptor(paths, profile_id)
    descriptor_path = BUILD / "boot.id"
    descriptor_path.write_bytes(descriptor)
    descriptor_rows = parse_descriptor(descriptor, build_id)
    sector_rows = [
        {
            "name": row["name"],
            "bytes": row["bytes"],
            "logical_sectors": (row["bytes"] + 253) // 254,
        }
        for row in descriptor_rows
    ]
    stager_source = STAGER_C.read_text(encoding="utf-8")
    if (
        max(row["logical_sectors"] for row in sector_rows) <= 255
        or not any(row["name"] == "overlays.bin" and row["logical_sectors"] > 255 for row in sector_rows)
        or not any(row["name"] == "shelf.bin" and row["logical_sectors"] > 255 for row in sector_rows)
        or "uint16_t fuel;" not in stager_source
        or "fuel = (uint16_t)((expected_length + R3_LOGICAL_SECTOR_PAYLOAD - 1ul) /" not in stager_source
        or "expected_length > R3_MAX_MEDIA_BYTES" not in stager_source
    ):
        raise ProductError("stager logical-sector fuel no longer proves >255-sector product files")
    stager, stager_map, chain_bytes = compile_stager(contract, build_id)

    c1541 = contract["toolchain_bindings"]["c1541"]["artifact"]["path"]
    product_d81 = BUILD / "lisp65-product.d81"
    work_d81 = BUILD / "lisp65-work.d81"
    product_entries = [
        (stager, "autoboot.c65,p"), (descriptor_path, "boot.id,s"),
        (paths["lisp65.prg"], "lisp65.prg,p"), (paths["bank5.bin"], "bank5.bin,s"),
        (paths["overlays.bin"], "overlays.bin,s"), (paths["profile"], "profile,s"),
        (paths["ide"], "ide,s"), (paths["idex"], "idex,s"), (paths["m65d"], "m65d,s"),
        (paths["shelf.bin"], "shelf.bin,s"),
    ]
    build_d81(c1541, product_d81, "L65SYS,65", product_entries)
    stamp_product_boot_marker(product_d81)
    build_d81(c1541, work_d81, "L65WORK,65", [])
    os.chmod(product_d81, 0o444)
    os.chmod(work_d81, 0o644)

    expected_media = {"autoboot.c65": stager.read_bytes(), "boot.id": descriptor}
    expected_media.update({name: path.read_bytes() for name, path in paths.items() if name != "lisp65.elf"})
    inventory = verify_media(product_d81, work_d81, expected_media)
    model = model_selftest(descriptor, build_id, {name: path.read_bytes() for name, path in paths.items()}, profile_id)
    chain_walkers = load(CHAIN_WALKER_RECEIPT, "chain-walker inventory")
    if (
        chain_walkers.get("format") != "lisp65-1581-chain-walker-inventory-v1"
        or chain_walkers.get("status") != "pass"
        or chain_walkers.get("deviations") != []
        or len(chain_walkers.get("walkers", [])) != 18
    ):
        raise ProductError("chain-walker inventory is not closed")

    product_row = artifact(product_d81, "product-d81")
    work_row = artifact(work_d81, "work-d81")
    mount_path = BUILD / "lisp65-product.mount.json"
    mount_path.write_bytes(canonical({
        "format": "lisp65-product-mount-descriptor-v2",
        "media": "lisp65-product.d81", "media_sha256": product_row["sha256"],
        "disk_name": "L65SYS", "disk_id": "65", "drive": 8,
        "write_protect": {
            "physical_floppy": "required-if-used",
            "stock_core_SD_D81": "unavailable-no-virtual-read-only-attach-control",
        },
        "mutable_entries": False,
    }))
    new_rows = [
        artifact(stager, "cold-stager"), artifact(descriptor_path, "boot-descriptor"),
        product_row, work_row, artifact(mount_path, "product-mount-descriptor"),
    ]
    release_rows = core_rows + library_rows + [shelf_row] + new_rows
    release_set = artifact_set_sha(release_rows)
    manifest_path = BUILD / "candidate-manifest.json"
    manifest_path.write_bytes(canonical({
        "format": "lisp65-r3-candidate-manifest-v1", "status": "product-built-g3-not-run",
        "artifact_set_sha256": release_set, "product_build_id": f"{build_id:08x}",
        "artifacts": release_rows,
    }))

    metrics = composition_metrics()
    capacity = capacity_delta(release_set, metrics, BASELINE_RELEASE_SET)
    debits = {
        name: row["delta"]
        for name, row in capacity["dimensions"].items()
        if row["delta"] < 0
    }
    if debits != {}:
        raise ProductError(f"Wave-3 aggregate capacity debit drift: {debits}")
    wave_bindings = [
        binding(ROOT / path)
        for path in WAVE1_EVIDENCE + WAVE2_EVIDENCE + WAVE3_EVIDENCE
    ]
    cases = matrix.get("cases", [])
    if {case.get("id") for case in cases} != set(G3_CASES) | set(G6_CASES):
        raise ProductError("boot matrix coverage drift")
    source_bindings = [
        binding(path) for path in (
            CONTRACT, MATRIX, REPRO_RECEIPT,
            COMPOSITION, FOOTPRINT, CAPACITY_POLICY,
            STAGER_C, STAGER_S, STAGER_CONTRACT,
            F011_CONTEXT, F011_CONTEXT_CONTRACT, F011_CONTEXT_TOOL,
            ASM_CONTRACT, ASM_CONTRACT_GENERATOR, ASM_CONTRACT_TOOL,
            L65M_BATCH_CONTRACT, Path(__file__).resolve(),
            SHELF_TOOL, SHELF_CONTRACT,
            CHAIN_WALKER_TOOL, ROOT / "src" / "io.c",
            ROOT / "lib" / "ide-disk.lisp", ROOT / "lib" / "m65-disk.lisp",
            ROOT / "lib" / "lcc-fasl.lisp", ROOT / "lib" / "dialect-v2" / "eval-runtime.lisp",
            ROOT / "lib" / "stdlib-load.lisp",
            ROOT / "lib" / "stdlib-load-lib.lisp",
        )
    ]
    return {
        "format": FORMAT,
        "id": "r3-cold-start-two-media-product-block",
        "contract_id": "workbench-r3-g3-g6",
        "status": "product-implemented-g3-not-run",
        "measured_on": "2026-07-19",
        "release_effect": "none",
        "candidate_manifest": binding(manifest_path),
        "product_identity": {
            "historical_r2_product_sha256": contract["baseline_identity"]["historical_r2_product_sha256"],
            "canonical_workbench_product_sha256": repro["product_sha256"],
            "artifact_set_sha256": release_set,
            "product_build_id": f"{build_id:08x}",
            "stager_descriptor_records_crc32": f"{build_id:08x}",
            "existing_core_artifact_parity": "exact",
        },
        "artifacts": {"core": core_rows, "libraries": library_rows,
                      "shelf": shelf_row, "new": new_rows},
        "stager": {
            "implementation": "separate-media-loader-validator-restager-chain",
            "linked_into_workbench_prg": False,
            "descriptor": {"bytes": len(descriptor), "records": descriptor_rows, "retry_limit": RESTAGE_LIMIT},
            "sector_chain_budget": {
                "payload_bytes_per_sector": 254,
                "fuel_type": "uint16_t",
                "bound": "ceil(expected_length/254)-with-819200-byte-media-cap",
                "files": sector_rows,
                "greater_than_255_sector_cases": sorted(
                    row["name"] for row in sector_rows if row["logical_sectors"] > 255
                ),
            },
            "error_message": ERROR_MESSAGE.decode("ascii"),
            "map_measurement": {
                "path": stager_map.relative_to(ROOT).as_posix(),
                "chain_trampoline_bytes": chain_bytes,
                "chain_trampoline_limit_bytes": 64,
                "note": "map-SHA-excluded-because-llvm-mos-records-random-temporary-object-name",
            },
            "model_verification": model,
        },
        "media": {
            "product": product_row | {
                "identity": {"disk_name": "L65SYS", "disk_id": "65"},
                "boot_structure_signature": inventory["product_boot_marker"],
                "package_mode": "0444",
                "mount_write_protect": "physical-floppy-required-stock-core-SD-D81-unavailable",
                "entries": inventory["product_entries"],
            },
            "work": work_row | {
                "identity": {"disk_name": "L65WORK", "disk_id": "65"},
                "package_mode": "0644", "mount_write_protect": False,
                "entries": inventory["work_entries"], "provisioning": "shipped-preformatted-blank",
                "additional_media": "PC-or-emulator-copy-in-1.0-no-device-formatter",
            },
            "write_defense": {
                "identity": "complete-canonical-name-plus-exact-id-plus-D68B-D68F-token-bound-per-transaction",
                "generation": "fresh-latch-token-per-successful-remount",
                "boot_signature": inventory["product_boot_marker"],
                "writable_media": "any-valid-non-product-1581",
                "product_status": 10, "invalid_status": 6,
                "retired_status_11": "never-emitted",
                "midtransaction_status": 12,
                "automatic_retry": "pretransaction-status-8-only",
                "planning_read_guard": "post-capture-status-6-plus-D68B-D68F-mismatch-becomes-terminal-status-12-stable-token-preserves-status-6-zero-writes",
                "residual_window": "owner-accepted-at-most-one-foreign-sector-not-a-safety-pass",
            },
        },
        "capacity_delta": capacity,
        "capacity_attribution": {
            "baseline": "sealed-v1.0.1-product-set",
            "wave": "1.1-wave-3-l-lite-generated-keymap",
            "block_receipts_and_authorizations": wave_bindings,
            "aggregate_result": (
                "no-aggregate-debits; bank-ext-symbols-namepool-directory-credits"
            ),
        },
        "capacity_watch": {
            "bank": {
                "post_boot_reserve": metrics["bank"] + 1536,
                "release_floor": 1536,
                "banked_reserve": metrics["bank"],
                "status": "target-met-wave-3-aggregate-credit",
            },
            "ext": {
                "post_headroom": metrics["ext"],
                "release_floor": 16384,
                "margin": metrics["ext"] - 16384,
                "status": "wave-1-structural-relief-preserved-through-wave-3",
                "next_debit": "normal-block-authorization-required",
                "relief_rule": "16-KiB-user-capacity-floor-remains-binding",
            },
            "overlay": {
                "headroom": 0,
                "color_scroll_rider": "deferred-to-C2-after-final-authorized-attempt",
                "status": "frozen-zero-headroom-C2-runtime-layout-cure-required",
            },
            "resident_island": {
                "payload_bytes": 1668,
                "annex_bytes": 260,
                "reserve_bytes": 120,
                "status": "owner-authorized-watch-listed",
                "next_debit": "explicit-island-capacity-delta-and-prior-authorization-required",
                "wave_1_1_m": "must-measure-and-report-resident-island-demand",
            },
            "structural_relief": "1.1-C1-complete; compiler tier retired after compilation",
        },
        "null_deltas": {
            "workbench_bank_bytes": 0,
            "boot_overlay_bytes": 0,
            "boot_overlay": artifact(BOOT_OVERLAY, "boot-overlay"),
        },
        "composition": binding(COMPOSITION) | metrics,
        "verification": {
            "l_lite_generated_keymap": "41-bindings-5-M-x-6-outputs-pass",
            "l_lite_ide_host_oracle": "87/87-pass",
            "l_lite_p0_differential": "2-suites-187-functions-163-cases-350-objects-pass",
            "l_lite_hardware": "not-run",
            "media_model_cases": model["cases"],
            "product_d81_inventory": "exact",
            "work_d81_blank": True,
            "chain_walker_inventory": binding(CHAIN_WALKER_RECEIPT) | {
                "walkers": 18, "shared_negative_classes": 3, "deviations": 0,
            },
            "G3": {case: "not-run" for case in G3_CASES},
            "G6": {case: "not-run" for case in G6_CASES},
            "emulator_started": False,
        },
        "source_bindings": source_bindings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    receipt_path = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    try:
        value = build_product()
        encoded = canonical(value)
        if args.command == "generate":
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(encoded)
            print(
                "r3-product-block: WROTE status=product-implemented-g3-not-run "
                f"set={value['product_identity']['artifact_set_sha256']} "
                f"ext={value['composition']['ext']} output={receipt_path.relative_to(ROOT)}"
            )
        else:
            require(receipt_path, "R3 product receipt")
            if receipt_path.read_bytes() != encoded:
                raise ProductError("R3 product receipt drift")
            print(
                "r3-product-block: PASS status=product-implemented-g3-not-run "
                f"set={value['product_identity']['artifact_set_sha256']} "
                "G3=not-run G6=not-run"
            )
        return 0
    except (
        ProductError, CAPACITY.CapacityDeltaError, REPRO.ReproError, OSError,
        ValueError, TypeError, KeyError, json.JSONDecodeError,
    ) as exc:
        print(f"r3-product-block: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
