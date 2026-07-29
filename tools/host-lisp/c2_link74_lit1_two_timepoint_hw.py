#!/usr/bin/env python3
"""Build and capture Link 74's nonpromotable LIT(1) discriminator."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


BASE = ROOT / "build/post-promotion/link74-asm-z-boundary"
FINAL = BASE / "final"
MANIFEST = BASE / "canonical-product-manifest.json"
PRODUCT = FINAL / "lisp65-c2-substitution-linked.prg"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
BOOT = FINAL / "runtime-overlays-boot-final.bin"
BOOT_JSON = FINAL / "runtime-overlays-boot-final.json"
BOOT_OVERFLOW = FINAL / "runtime-overlays-boot-final-region1.bin"
PREFLIGHT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link74-lit1-two-timepoint-preflight-receipt.json")
CONTRACT = ROOT / "config/c2.2-link74-lit1-two-timepoint-discriminator.json"

OUT = BASE / "lit1-two-timepoint-NONPROMOTABLE"
DIAGNOSTIC_PRODUCT = OUT / "lisp65-link74-lit1-two-timepoint-NONPROMOTABLE.prg"
DIAGNOSTIC_BOOT = OUT / "runtime-overlays-boot-link74-lit1-NONPROMOTABLE.bin"
DIAGNOSTIC_BOOT_JSON = OUT / (
    "runtime-overlays-boot-link74-lit1-NONPROMOTABLE.json")
DEPLOYMENT = OUT / "deployment.json"
CAPTURE = OUT / "capture-summary.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link74-lit1-two-timepoint-nonpromotable-receipt.json")

LOAD_ADDRESS = 0x2001
BOOT_ADDRESS = 0x08200000
C2D_ADDRESS = 0x00050000
BOOT_SLOT = 11
BOOT_VMA = 0x1800
INITIAL_PC = 0x1E8F
INITIAL_BEFORE = bytes.fromhex("a9 33 80")
INITIAL_AFTER = bytes.fromhex("4c 8f 1e")
INITIAL_BOOT_OFFSET = 0x4B8F
RELOAD_PC = 0x543B
RELOAD_BEFORE = bytes.fromhex("a2 a7 a0")
RELOAD_AFTER = bytes.fromhex("4c 3b 54")
RELOAD_PRG_OFFSET = 0x343C
BOOT_BINDING_ADDRESS = 0xB9AC
BOOT_BINDING_PRG_OFFSET = 0x99AD
BOOT_BINDING_BEFORE = bytes.fromhex("6e bb")

VM_CODEBUF = 0xBFA0
VM_CODEBUF_HEADER_BYTES = 11
VM_LIT1 = 0xBFA9
VM_BUF_OFF = 0xB9B2
VM_BUF_BANK = 0xBFD8
C2_RUNTIME = 0xC084
C2_RUNTIME_BYTES = 46
C2_ENTRIES_OFFSET = 20
C2_RESOLUTIONS_OFFSET = 22
C2D_ENTRY_BYTES = 10
SYMPOOL_PHYSICAL = 0x0005C680
NAMEOFF_PHYSICAL = 0x0005F440
SYMI_BASE = 0x7000

ROLE_ADDRESS = {
    "c2d-v6-code-plane": 0x00050000,
    "c2-two-record-boot-stage": 0x00058500,
    "c2-session-family-region-0": 0x08000000,
    "c2-product-shelf": 0x08100000,
    "c2-boot-family": BOOT_ADDRESS,
    "c2-session-family-region-1": 0x08300000,
    "c2-kernal-window": 0x087FE000,
}


class HardwareError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HardwareError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == value, f"generated artifact drift: {path}")
    else:
        path.write_bytes(value)


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(path, json_bytes(value))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"bound artifact absent: {path}")
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def u16(value: bytes | bytearray, offset: int = 0) -> int:
    return int.from_bytes(value[offset:offset + 2], "little")


def parsed_boot(image: bytes) -> R.ParsedBank:
    build_id = R.HEADER.unpack_from(image)[8]
    return R.validate_region_images(
        image, BOOT_OVERFLOW.read_bytes(),
        expected_build_id=build_id, expected_vma=0xC356,
        max_slice_bytes=4096, format_version=R.VERSION_V4,
        main_source_base=BOOT_ADDRESS,
        overflow_source_base=0x08300000)


def patch_boot(source: bytes) -> tuple[bytes, dict[str, Any]]:
    base = parsed_boot(source)
    row = base.slices[BOOT_SLOT]
    require(
        row.file_offset == 17664 and row.file_size == 1738
        and row.vma == BOOT_VMA
        and INITIAL_BOOT_OFFSET
        == row.file_offset + INITIAL_PC - row.vma,
        "resident-island carrier geometry drift")
    result = bytearray(source)
    require(
        result[INITIAL_BOOT_OFFSET:INITIAL_BOOT_OFFSET + 3]
        == INITIAL_BEFORE,
        "initial checkpoint bytes drift")
    result[INITIAL_BOOT_OFFSET:INITIAL_BOOT_OFFSET + 3] = INITIAL_AFTER

    record_offset = R.HEADER_SIZE + BOOT_SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    old_payload_crc = fields[9]
    old_record_crc = fields[10]
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw_record)
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    old_directory_crc = u16(result, 24)
    old_header_crc = u16(result, 26)
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26,
        R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    candidate = bytes(result)
    verified = parsed_boot(candidate)
    derived = verified.slices[BOOT_SLOT]
    require(
        derived.crc16 == fields[9]
        and derived.record_crc16 == fields[10],
        "patched resident-island record did not validate")
    return candidate, {
        "old_payload_crc16": f"0x{old_payload_crc:04x}",
        "new_payload_crc16": f"0x{fields[9]:04x}",
        "old_record_crc16": f"0x{old_record_crc:04x}",
        "new_record_crc16": f"0x{fields[10]:04x}",
        "old_directory_crc16": f"0x{old_directory_crc:04x}",
        "new_directory_crc16": f"0x{verified.directory_crc16:04x}",
        "old_header_crc16": f"0x{old_header_crc:04x}",
        "new_header_crc16": f"0x{verified.header_crc16:04x}",
        "old_family_crc16": f"0x{R.crc16_ccitt_false(source):04x}",
        "new_family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
    }


def patch_product(source: bytes, boot_crc: int) -> bytes:
    require(u16(source) == LOAD_ADDRESS, "Link-74 PRG load address drift")
    require(
        RELOAD_PRG_OFFSET == 2 + RELOAD_PC - LOAD_ADDRESS
        and source[RELOAD_PRG_OFFSET:RELOAD_PRG_OFFSET + 3]
        == RELOAD_BEFORE,
        "reload checkpoint PRG provenance drift")
    require(
        BOOT_BINDING_PRG_OFFSET
        == 2 + BOOT_BINDING_ADDRESS - LOAD_ADDRESS
        and source[
            BOOT_BINDING_PRG_OFFSET:BOOT_BINDING_PRG_OFFSET + 2]
        == BOOT_BINDING_BEFORE,
        "boot-family publish-last binding drift")
    result = bytearray(source)
    result[RELOAD_PRG_OFFSET:RELOAD_PRG_OFFSET + 3] = RELOAD_AFTER
    result[
        BOOT_BINDING_PRG_OFFSET:BOOT_BINDING_PRG_OFFSET + 2
    ] = boot_crc.to_bytes(2, "little")
    return bytes(result)


def diagnostic_boot_json(
        source: dict[str, Any], candidate: bytes,
        crc: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(source)
    value["schema"] = (
        "lisp65-runtime-overlay-bank-v4-link74-lit1-nonpromotable")
    value["policy"]["promotable"] = False
    value["policy"]["diagnostic_identity"] = (
        "Link74-LIT1-two-timepoint-NONPROMOTABLE")
    row = value["slices"][BOOT_SLOT]
    payload = candidate[row["file_offset"]:
                        row["file_offset"] + row["file_size"]]
    row["crc16"] = int(crc["new_payload_crc16"], 16)
    row["record_crc16"] = int(crc["new_record_crc16"], 16)
    row["sha256"] = sha_bytes(payload)
    value["catalog"]["directory_crc16"] = int(
        crc["new_directory_crc16"], 16)
    value["catalog"]["header_crc16"] = int(crc["new_header_crc16"], 16)
    value["storage"]["crc16"] = int(crc["new_family_crc16"], 16)
    value["storage"]["sha256"] = sha_bytes(candidate)
    value["storage"]["file"] = DIAGNOSTIC_BOOT.name
    return value


def mutation_gate(
        candidate_boot: bytes, candidate_product: bytes, family_crc: int,
        crc: dict[str, Any]) -> list[str]:
    mutations: list[str] = []
    for label, offset, before in (
        ("stale-payload-crc",
         R.HEADER_SIZE + BOOT_SLOT * R.ENTRY_SIZE + 20,
         int(crc["old_payload_crc16"], 16).to_bytes(2, "little")),
        ("stale-record-crc",
         R.HEADER_SIZE + BOOT_SLOT * R.ENTRY_SIZE + 22,
         int(crc["old_record_crc16"], 16).to_bytes(2, "little")),
        ("stale-directory-crc", 24,
         int(crc["old_directory_crc16"], 16).to_bytes(2, "little")),
        ("stale-header-crc", 26,
         int(crc["old_header_crc16"], 16).to_bytes(2, "little")),
    ):
        mutant = bytearray(candidate_boot)
        mutant[offset:offset + 2] = before
        try:
            parsed_boot(bytes(mutant))
        except R.OverlayBankError:
            mutations.append(label)
        else:
            raise HardwareError(f"carrier mutation accepted: {label}")
    stale_product = bytearray(candidate_product)
    stale_product[
        BOOT_BINDING_PRG_OFFSET:BOOT_BINDING_PRG_OFFSET + 2
    ] = BOOT_BINDING_BEFORE
    require(
        u16(stale_product, BOOT_BINDING_PRG_OFFSET) != family_crc,
        "stale product family binding mutation was not effective")
    mutations.append("stale-product-family-binding")
    return mutations


def prepare() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-74 discriminator is one-shot")
    preflight = load(PREFLIGHT)
    contract = load(CONTRACT)
    manifest = load(MANIFEST)
    require(
        preflight["status"]
        == "passed-prequalified-target-discriminator-hardware-not-run"
        and contract["status"] == "prequalified-spec-no-hardware"
        and manifest["identity"]["resident_prg_sha256"] == sha(PRODUCT)
        and manifest["identity"]["linked_elf_sha256"] == sha(ELF),
        "Link-74 preflight authority drift")
    source_boot = BOOT.read_bytes()
    source_product = PRODUCT.read_bytes()
    candidate_boot, crc = patch_boot(source_boot)
    family_crc = R.crc16_ccitt_false(candidate_boot)
    candidate_product = patch_product(source_product, family_crc)
    require(len(candidate_boot) == len(source_boot)
            and len(candidate_product) == len(source_product),
            "diagnostic artifact size changed")
    require(PRODUCT.read_bytes() == source_product
            and BOOT.read_bytes() == source_boot,
            "Link 74 source authority was modified")

    # Class mutations: each stale identity must be rejected independently.
    mutations = mutation_gate(
        candidate_boot, candidate_product, family_crc, crc)

    OUT.mkdir(parents=True)
    write_bytes(DIAGNOSTIC_BOOT, candidate_boot)
    write_bytes(DIAGNOSTIC_PRODUCT, candidate_product)
    write_json(
        DIAGNOSTIC_BOOT_JSON,
        diagnostic_boot_json(load(BOOT_JSON), candidate_boot, crc))

    roles = {row["role"]: row for row in manifest["artifacts"]}
    preloads: list[dict[str, Any]] = []
    for role, address in ROLE_ADDRESS.items():
        if role == "c2-boot-family":
            preloads.append({
                **bind(DIAGNOSTIC_BOOT, address),
                "role": role,
            })
        else:
            row = roles[role]
            path = ROOT / row["path"]
            require(sha(path) == row["sha256"]
                    and path.stat().st_size == row["bytes"],
                    f"Link-74 role drift: {role}")
            preloads.append({**row, "address": f"0x{address:08x}"})
    deployment = {
        "format": "lisp65-c2.2-link74-lit1-two-timepoint-deployment-v1",
        "recorded_on": "2026-07-28",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "product": {
            **bind(DIAGNOSTIC_PRODUCT, LOAD_ADDRESS),
            "role": "c2-resident-prg",
        },
        "elf": bind(ELF),
        "preloads": preloads,
        "test": {
            "definition":
                "(defun %is (n) (if (> n 0) (progn (intern \"abc\") "
                "(%is (- n 1))) t))",
            "invocation": "(%is 3)",
            "input": "physical keyboard; no JTAG input episode",
            "capture": (
                "run capture action once invocation is visibly held; it "
                "captures both checkpoints in one device session"),
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
    }
    write_json(DEPLOYMENT, deployment)
    changed_boot = [
        index for index, pair in enumerate(zip(source_boot, candidate_boot))
        if pair[0] != pair[1]]
    changed_product = [
        index for index, pair in enumerate(
            zip(source_product, candidate_product))
        if pair[0] != pair[1]]
    receipt = {
        "format": "lisp65-c2.2-link74-lit1-two-timepoint-patch-v1",
        "recorded_on": "2026-07-28",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "product": bind(PRODUCT, LOAD_ADDRESS),
            "ELF": bind(ELF),
            "boot_family": bind(BOOT, BOOT_ADDRESS),
            "contract": bind(CONTRACT),
            "preflight": bind(PREFLIGHT),
            "manifest": bind(MANIFEST),
            "driver": bind(Path(__file__).resolve()),
        },
        "diagnostic_identity": {
            "product": bind(DIAGNOSTIC_PRODUCT, LOAD_ADDRESS),
            "boot_family": bind(DIAGNOSTIC_BOOT, BOOT_ADDRESS),
            "boot_catalog": bind(DIAGNOSTIC_BOOT_JSON),
            "deployment": bind(DEPLOYMENT),
            "lifecycle": "discard after one adjudicated hardware session",
        },
        "patches": [
            {
                "name": "initial-before-prim68-takeover",
                "runtime_address": "0x1e8f",
                "boot_family_file_offset": INITIAL_BOOT_OFFSET,
                "before": INITIAL_BEFORE.hex(),
                "after": INITIAL_AFTER.hex(),
            },
            {
                "name": "reload-before-literal-consumption",
                "runtime_address": "0x543b",
                "PRG_file_offset": RELOAD_PRG_OFFSET,
                "before": RELOAD_BEFORE.hex(),
                "after": RELOAD_AFTER.hex(),
            },
            {
                "name": "boot-family-publish-last-rebind",
                "runtime_address": "0xb9ac",
                "PRG_file_offset": BOOT_BINDING_PRG_OFFSET,
                "before": BOOT_BINDING_BEFORE.hex(),
                "after": family_crc.to_bytes(2, "little").hex(),
            },
        ],
        "identity_rebind": crc,
        "proof": {
            "mutations_rejected": mutations,
            "mutation_count": len(mutations),
            "boot_bytes_changed": len(changed_boot),
            "boot_changed_file_offsets": changed_boot,
            "product_bytes_changed": len(changed_product),
            "product_changed_file_offsets": changed_product,
            "artifact_byte_deltas": 0,
            "source_Link74_unchanged": True,
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "One nonpromotable target-only LIT(1) discriminator. No product, "
            "require, defstruct, release or promotion qualification."),
    }
    write_json(RECEIPT, receipt)
    return {
        "status": "ready",
        "diagnostic_product_sha256": sha(DIAGNOSTIC_PRODUCT),
        "diagnostic_boot_sha256": sha(DIAGNOSTIC_BOOT),
        "boot_family_crc16": f"0x{family_crc:04x}",
        "mutations": f"{len(mutations)}/{len(mutations)}",
    }


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    candidate_boot, crc = patch_boot(BOOT.read_bytes())
    family_crc = R.crc16_ccitt_false(candidate_boot)
    candidate_product = patch_product(PRODUCT.read_bytes(), family_crc)
    require(DIAGNOSTIC_BOOT.read_bytes() == candidate_boot,
            "diagnostic boot family drift")
    require(DIAGNOSTIC_PRODUCT.read_bytes() == candidate_product,
            "diagnostic product drift")
    mutations = mutation_gate(
        candidate_boot, candidate_product, family_crc, crc)
    require(
        receipt["status"] in (
            "ready-authorized-nonpromotable-hardware",
            "completed-nonpromotable-two-timepoint-capture")
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware"
        and receipt["identity_rebind"] == crc,
        "diagnostic receipt drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(path.stat().st_size == row["bytes"]
                and sha(path) == row["sha256"],
                f"diagnostic preload drift: {path}")
    return {
        "status": "verified",
        "product": sha(DIAGNOSTIC_PRODUCT),
        "boot": sha(DIAGNOSTIC_BOOT),
        "boot_family_crc16": f"0x{family_crc:04x}",
        "mutations": f"{len(mutations)}/{len(mutations)}",
    }


def command(fd: int, value: bytes, wait: float = 0.02) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.3)


def read_registers(fd: int, expected_pc: int) -> dict[str, Any]:
    raw = command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw)
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == expected_pc,
            f"expected hold PC 0x{expected_pc:04x}, found 0x{pc:04x}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {
        name: f"0x{int(match.group(index), 16):0{width}x}"
        for index, (name, width)
        in enumerate(zip(names, widths), 1)
    } | {"raw_hex": raw.hex()}


def read_block(fd: int, address: int, size: int) -> bytes:
    value = bytearray()
    for offset in range(0, size, 16):
        current = address + offset
        raw = command(fd, f"m{current:08x}".encode())
        match = re.search(
            fr":{current:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
        require(match is not None,
                f"memory row absent at 0x{current:08x}: {raw!r}")
        value.extend(bytes.fromhex(match.group(1).decode()))
    return bytes(value[:size])


def write_block(fd: int, address: int, value: bytes) -> None:
    for offset in range(0, len(value), 16):
        chunk = value[offset:offset + 16]
        command(
            fd, (
                f"s{address + offset:08x} "
                + " ".join(f"{byte:02x}" for byte in chunk)
            ).encode(), 0.05)


def live_snapshot(fd: int, checkpoint: str, index: int) -> dict[str, Any]:
    code = read_block(fd, VM_CODEBUF, VM_CODEBUF_HEADER_BYTES)
    ordinal_raw = read_block(fd, VM_BUF_OFF, 2)
    bank = read_block(fd, VM_BUF_BANK, 1)
    runtime = read_block(fd, C2_RUNTIME, C2_RUNTIME_BYTES)
    ordinal = u16(ordinal_raw)
    entries = u16(runtime, C2_ENTRIES_OFFSET)
    resolutions = u16(runtime, C2_RESOLUTIONS_OFFSET)
    entry_address = C2D_ADDRESS + entries + ordinal * C2D_ENTRY_BYTES
    entry = read_block(fd, entry_address, C2D_ENTRY_BYTES)
    require(entry[1] >= 2, "live owner has fewer than two literals")
    resolution_base = u16(entry, 6)
    expected_address = (
        C2D_ADDRESS + resolutions + (resolution_base + 1) * 2)
    expected = read_block(fd, expected_address, 2)
    word = u16(expected)
    require(
        (word & 1) == 0 and 0xE000 <= word <= 0xFFFE,
        f"live C2D LIT(1) is not SYMI: 0x{word:04x}")
    symbol_index = (word >> 1) - SYMI_BASE
    nameoff_address = NAMEOFF_PHYSICAL + symbol_index * 2
    nameoff_raw = read_block(fd, nameoff_address, 2)
    nameoff = u16(nameoff_raw)
    name_raw = read_block(fd, SYMPOOL_PHYSICAL + nameoff, 8)
    name = name_raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
    return {
        "checkpoint": checkpoint,
        "index": index,
        "captured_at_utc":
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_header_hex": code.hex(),
        "LIT1_hex": code[9:11].hex(),
        "owner_bank": f"0x{bank[0]:02x}",
        "owner_ordinal": ordinal,
        "runtime_context_hex": runtime.hex(),
        "entries_offset": entries,
        "resolutions_offset": resolutions,
        "entry_address": f"0x{entry_address:08x}",
        "entry_hex": entry.hex(),
        "resolution_base": resolution_base,
        "expected_address": f"0x{expected_address:08x}",
        "expected_LIT1_hex": expected.hex(),
        "expected_word": f"0x{word:04x}",
        "symbol_index": symbol_index,
        "nameoff_address": f"0x{nameoff_address:08x}",
        "nameoff": nameoff,
        "live_symbol_name": name,
        "materialized_matches_C2D": code[9:11] == expected,
        "live_symbol_is_percent_is": name == "%is",
    }


def capture_checkpoint(
        fd: int, name: str, pc: int) -> dict[str, Any]:
    command(fd, b"t1", 0.05)
    registers = read_registers(fd, pc)
    rows: list[dict[str, Any]] = []
    for index, delay in enumerate((0, 1, 4), 1):
        if delay:
            time.sleep(delay)
        rows.append(live_snapshot(fd, name, index))
    stable_keys = (
        "code_header_hex", "LIT1_hex", "owner_bank", "owner_ordinal",
        "runtime_context_hex", "entry_hex", "expected_LIT1_hex",
        "live_symbol_name")
    require(
        all(len({row[key] for row in rows}) == 1 for key in stable_keys),
        f"{name} witnesses changed across three captures")
    return {"registers": registers, "snapshots": rows}


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "two-timepoint capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    left_stopped = False
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c274lit1a\r")
        initial = capture_checkpoint(
            fd, "initial-before-prim68-takeover", INITIAL_PC)
        require(
            read_block(fd, INITIAL_PC, 3) == INITIAL_AFTER,
            "initial live hold bytes drift")
        write_block(fd, INITIAL_PC, INITIAL_BEFORE)
        require(
            read_block(fd, INITIAL_PC, 3) == INITIAL_BEFORE,
            "initial checkpoint restore/readback failed")
        command(fd, b"t0", 0.05)
        time.sleep(1)

        SERIAL.monitor_sync(fd, b"#c274lit1b\r")
        reloaded = capture_checkpoint(
            fd, "reload-before-literal-consumption", RELOAD_PC)
        left_stopped = True
    finally:
        os.close(fd)
    require(left_stopped, "second checkpoint was not left stopped")
    first = initial["snapshots"][0]
    second = reloaded["snapshots"][0]
    require(
        first["owner_ordinal"] == second["owner_ordinal"]
        and first["expected_LIT1_hex"] == second["expected_LIT1_hex"],
        "two checkpoints do not describe one live owner truth")
    both_match = (
        first["materialized_matches_C2D"]
        and second["materialized_matches_C2D"]
        and first["live_symbol_is_percent_is"]
        and second["live_symbol_is_percent_is"])
    if both_match:
        outcome = "transport-correct-consumption-fault"
    else:
        outcome = "transport-or-materialization-fault"
    value = {
        "format": "lisp65-c2.2-link74-lit1-two-timepoint-capture-v1",
        "recorded_on": "2026-07-28",
        "device": SERIAL.DEVICE,
        "CPU_left_stopped": True,
        "initial_checkpoint": initial,
        "reload_checkpoint": reloaded,
        "same_live_owner": True,
        "outcome": outcome,
        "adjudication": {
            "initial_matches_live_C2D": first["materialized_matches_C2D"],
            "reload_matches_live_C2D": second["materialized_matches_C2D"],
            "live_C2D_symbol_name": first["live_symbol_name"],
            "initial_LIT1_hex": first["LIT1_hex"],
            "reload_LIT1_hex": second["LIT1_hex"],
            "live_C2D_expected_hex": first["expected_LIT1_hex"],
        },
        "claim_limit": (
            "One Link-74 nonpromotable target-only LIT(1) discriminator; "
            "product qualification is not claimed."),
    }
    write_json(CAPTURE, value)
    receipt = load(RECEIPT)
    receipt["status"] = "completed-nonpromotable-two-timepoint-capture"
    receipt["capture"] = bind(CAPTURE)
    receipt["hardware_result"] = value["adjudication"] | {
        "outcome": outcome}
    receipt["execution_accounting"]["hardware_runs"] = 1
    write_json(RECEIPT, receipt)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "capture"))
    action = parser.parse_args().action
    if action == "prepare":
        value = prepare()
    elif action == "verify":
        value = verify()
    else:
        value = capture()
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
            HardwareError, R.OverlayBankError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-link74-lit1-two-timepoint-hw: FIRST RED: " + str(error))
        raise SystemExit(2)
