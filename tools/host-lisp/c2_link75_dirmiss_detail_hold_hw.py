#!/usr/bin/env python3
"""Build and capture Link 75's nonpromotable DIRMISS-detail hold."""

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
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
FINAL = BASE / "final"
BASE_DEPLOYMENT = BASE / "hardware-session/deployment.json"
MANIFEST = BASE / "canonical-product-manifest.json"
PRODUCT = FINAL / "lisp65-c2-substitution-linked.prg"
ELF = FINAL / "lisp65-c2-substitution-linked.prg.elf"
SESSION = FINAL / "runtime-overlays-session-final.bin"
SESSION_JSON = FINAL / "runtime-overlays-session-final.json"
SESSION_REGION1 = FINAL / "runtime-overlays-session-final-region1.bin"
BOOT_JSON = FINAL / "runtime-overlays-boot-final.json"
PUBLISH_LAST = FINAL / "runtime-verifier-publish-last.json"
BOUND_TABLE = FINAL / "runtime-overlay-verifier-bindings.bin"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bound-carrier-dirmiss-hardware-first-red.json")

OUT = BASE / "dirmiss-detail-hold-NONPROMOTABLE"
DIAGNOSTIC_SESSION = OUT / (
    "runtime-overlays-session-link75-dirmiss-detail-hold-NONPROMOTABLE.bin")
DIAGNOSTIC_SESSION_JSON = OUT / (
    "runtime-overlays-session-link75-dirmiss-detail-hold-NONPROMOTABLE.json")
DIAGNOSTIC_PRODUCT = OUT / (
    "lisp65-link75-dirmiss-detail-hold-NONPROMOTABLE.prg")
DIAGNOSTIC_BINDING = OUT / "runtime-overlay-verifier-bindings.bin"
DEPLOYMENT = OUT / "deployment.json"
CAPTURE = OUT / "capture-summary.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-dirmiss-detail-hold-nonpromotable-receipt.json")
HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-dirmiss-detail-hold-receipt-update-harness-first-red.json")

LOAD_ADDRESS = 0x2001
SESSION_ADDRESS = 0x08000000
SESSION_REGION1_ADDRESS = 0x08300000
SESSION_MAIN_SOURCE_BASE = 0x00030000
SESSION_REGION1_SOURCE_BASE = 0x0005BD00
SLOT = 47
SLOT_VMA = 0xC356
SLOT_FILE_OFFSET = 0xEA00
SLOT_BYTES = 0x04BA
HOLD_VMA = 0xC46F
PATCH_FILE_OFFSET = 0xEB19
PATCH_BEFORE = bytes.fromhex("20 f9 92")
PATCH_AFTER = bytes.fromhex("80 fe 92")

PENDING_SYMBOL = 0xB9E7
RENDER_DETAIL = 0x0006
NSYM = 0x005B
NPOOL = 0xBE18
SYM_NAME_SCRATCH = 0xC1F6
SYM_NAME_SCRATCH_BYTES = 34
C2_DMA_LIST = 0xB9D1
C2_DMA_LIST_BYTES = 12
SYMPOOL_PHYSICAL = 0x0005C680
NAMEOFF_PHYSICAL = 0x0005F440
SYMI_BASE = 0x7000
EXPECTED_NAME = "intern-renderer-missing"


class HoldError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HoldError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == value, f"generated artifact drift: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(value)
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_bytes(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
            "ascii"))


def replace_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


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


def parsed_session(image: bytes) -> R.ParsedBank:
    build_id = R.HEADER.unpack_from(image)[8]
    return R.validate_region_images(
        image,
        SESSION_REGION1.read_bytes(),
        expected_build_id=build_id,
        expected_vma=SLOT_VMA,
        max_slice_bytes=1792,
        format_version=R.VERSION_V4,
        main_source_base=SESSION_MAIN_SOURCE_BASE,
        overflow_source_base=SESSION_REGION1_SOURCE_BASE,
    )


def patch_session(source: bytes) -> tuple[bytes, dict[str, Any]]:
    base = parsed_session(source)
    row = base.slices[SLOT]
    require(
        row.id == SLOT
        and row.file_offset == SLOT_FILE_OFFSET
        and row.file_size == SLOT_BYTES
        and row.vma == SLOT_VMA
        and PATCH_FILE_OFFSET
            == row.file_offset + HOLD_VMA - row.vma,
        "Link-75 DIRMISS renderer geometry drift",
    )
    result = bytearray(source)
    require(
        result[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 3] == PATCH_BEFORE,
        "Link-75 pre-symname instruction drift",
    )
    result[PATCH_FILE_OFFSET:PATCH_FILE_OFFSET + 3] = PATCH_AFTER

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(result, record_offset))
    old_payload_crc = fields[9]
    old_record_crc = fields[10]
    fields[9] = R.crc16_ccitt_false(
        result[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw_record)
    require(fields[10] != 0, "derived v4 record CRC is forbidden zero")
    result[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    directory_end = R.HEADER_SIZE + len(base.slices) * R.ENTRY_SIZE
    old_directory_crc = u16(result, 24)
    old_header_crc = u16(result, 26)
    struct.pack_into(
        "<H", result, 24,
        R.crc16_ccitt_false(result[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", result, 26, 0)
    struct.pack_into(
        "<H", result, 26, R.crc16_ccitt_false(result[:R.HEADER_SIZE]))
    candidate = bytes(result)
    verified = parsed_session(candidate)
    derived = verified.slices[SLOT]
    require(
        derived.crc16 == fields[9]
        and derived.record_crc16 == fields[10],
        "patched DIRMISS record did not validate",
    )
    return candidate, {
        "record_offset": record_offset,
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


def diagnostic_session_json(
        source: dict[str, Any], candidate: bytes,
        crc: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(source)
    value["schema"] = (
        "lisp65-runtime-overlay-bank-v4-link75-dirmiss-hold-"
        "nonpromotable")
    value.setdefault("policy", {})["promotable"] = False
    value["policy"]["diagnostic_identity"] = (
        "Link75-DIRMISS-detail-pre-symname-hold-NONPROMOTABLE")
    row = value["slices"][SLOT]
    payload = candidate[
        row["file_offset"]:row["file_offset"] + row["file_size"]]
    row["crc16"] = int(crc["new_payload_crc16"], 16)
    row["record_crc16"] = int(crc["new_record_crc16"], 16)
    row["sha256"] = sha_bytes(payload)
    value["catalog"]["directory_crc16"] = int(
        crc["new_directory_crc16"], 16)
    value["catalog"]["header_crc16"] = int(
        crc["new_header_crc16"], 16)
    value["storage"]["crc16"] = int(crc["new_family_crc16"], 16)
    value["storage"]["sha256"] = sha_bytes(candidate)
    value["storage"]["file"] = DIAGNOSTIC_SESSION.name
    return value


def patch_product(
        source: bytes, new_session_crc: int) -> tuple[bytes, bytes, dict[str, Any]]:
    publish = load(PUBLISH_LAST)
    binding = BOUND_TABLE.read_bytes()
    require(
        publish["bytes"] == len(binding) == 40
        and publish["file_offset"] + len(binding) <= len(source)
        and source[
            publish["file_offset"]:publish["file_offset"] + len(binding)
        ] == binding,
        "Link-75 publish-last binding geometry drift",
    )
    old_session_crc = u16(binding, 38)
    require(
        old_session_crc == R.crc16_ccitt_false(SESSION.read_bytes()),
        "Link-75 session-stage binding is not canonical",
    )
    candidate_binding = bytearray(binding)
    struct.pack_into("<H", candidate_binding, 38, new_session_crc)
    result = bytearray(source)
    start = publish["file_offset"]
    result[start:start + len(candidate_binding)] = candidate_binding
    return bytes(result), bytes(candidate_binding), {
        "section": publish["section"],
        "address": f"0x{publish['address']:04x}",
        "file_offset": start,
        "session_stage_crc_file_offset": start + 38,
        "old_session_stage_crc16": f"0x{old_session_crc:04x}",
        "new_session_stage_crc16": f"0x{new_session_crc:04x}",
    }


def mutation_gate(
        candidate_session: bytes, candidate_product: bytes,
        crc: dict[str, Any], binding: dict[str, Any]) -> list[str]:
    rejected: list[str] = []
    record_offset = int(crc["record_offset"])
    for label, offset, old in (
        ("stale-payload-crc", record_offset + 20,
         int(crc["old_payload_crc16"], 16).to_bytes(2, "little")),
        ("stale-record-crc", record_offset + 22,
         int(crc["old_record_crc16"], 16).to_bytes(2, "little")),
        ("stale-directory-crc", 24,
         int(crc["old_directory_crc16"], 16).to_bytes(2, "little")),
        ("stale-header-crc", 26,
         int(crc["old_header_crc16"], 16).to_bytes(2, "little")),
    ):
        mutant = bytearray(candidate_session)
        mutant[offset:offset + 2] = old
        try:
            parsed_session(bytes(mutant))
        except R.OverlayBankError:
            rejected.append(label)
        else:
            raise HoldError(f"session mutation accepted: {label}")
    opcode_mutant = bytearray(candidate_session)
    opcode_mutant[PATCH_FILE_OFFSET] = PATCH_BEFORE[0]
    try:
        parsed_session(bytes(opcode_mutant))
    except R.OverlayBankError:
        rejected.append("hold-opcode-restored-with-stale-derived-identity")
    else:
        raise HoldError("hold-opcode mutation accepted")
    stale_product = bytearray(candidate_product)
    offset = int(binding["session_stage_crc_file_offset"])
    stale_product[offset:offset + 2] = int(
        binding["old_session_stage_crc16"], 16).to_bytes(2, "little")
    require(
        u16(stale_product, offset)
        != int(binding["new_session_stage_crc16"], 16),
        "stale product session binding mutation was ineffective",
    )
    rejected.append("stale-product-session-stage-binding")
    return rejected


def prepare() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Link-75 DIRMISS hold is one-shot")
    manifest = load(MANIFEST)
    deployment = load(BASE_DEPLOYMENT)
    first_red = load(FIRST_RED)
    require(
        manifest["identity"]["resident_prg_sha256"] == sha(PRODUCT)
        and manifest["identity"]["linked_elf_sha256"] == sha(ELF)
        and first_red["status"]
            == "FIRST-RED-DIRMISS-full-symbol-rendering-independent-of-stale-carrier",
        "Link-75 DIRMISS-hold authority drift",
    )
    source_session = SESSION.read_bytes()
    source_product = PRODUCT.read_bytes()
    candidate_session, crc = patch_session(source_session)
    new_family_crc = R.crc16_ccitt_false(candidate_session)
    candidate_product, candidate_binding, binding = patch_product(
        source_product, new_family_crc)
    require(
        len(candidate_session) == len(source_session)
        and len(candidate_product) == len(source_product),
        "diagnostic artifact size changed",
    )
    mutations = mutation_gate(
        candidate_session, candidate_product, crc, binding)
    require(
        SESSION.read_bytes() == source_session
        and PRODUCT.read_bytes() == source_product,
        "Link 75 authority was modified",
    )

    OUT.mkdir(parents=True)
    write_bytes(DIAGNOSTIC_SESSION, candidate_session)
    write_bytes(DIAGNOSTIC_PRODUCT, candidate_product)
    write_bytes(DIAGNOSTIC_BINDING, candidate_binding)
    write_json(
        DIAGNOSTIC_SESSION_JSON,
        diagnostic_session_json(
            load(SESSION_JSON), candidate_session, crc))

    preloads: list[dict[str, Any]] = []
    replacements = 0
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2-session-family-region-0":
            copy = {
                **bind(DIAGNOSTIC_SESSION, int(copy["address"], 16)),
                "role": copy["role"],
            }
            replacements += 1
        preloads.append(copy)
    require(replacements == 1, "session-family replacement is not unique")
    value = {
        "format": "lisp65-c2.2-link75-dirmiss-detail-hold-deployment-v1",
        "recorded_on": "2026-07-28",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "product": {
            **bind(DIAGNOSTIC_PRODUCT, LOAD_ADDRESS),
            "role": "c2-resident-prg",
        },
        "elf_authority": bind(ELF),
        "preloads": preloads,
        "test": {
            "form": "(intern-renderer-missing)",
            "hold_VMA": f"0x{HOLD_VMA:04x}",
            "capture_intervals_seconds": [0, 1, 4],
            "expected_behavior":
                "self-loop immediately before symname; no renderer output",
        },
        "capture_domains": {
            "context_transport": {
                "renderer_detail": {
                    "address": f"0x{RENDER_DETAIL:08x}", "bytes": 2},
                "pending_symbol": {
                    "address": f"0x{PENDING_SYMBOL:08x}", "bytes": 2},
            },
            "VM_installer_identity": {
                "nsym": {"address": f"0x{NSYM:08x}", "bytes": 2},
                "expected_rule": "detail SYMI index equals nsym-1",
            },
            "symbol_storage": {
                "nameoff_base": f"0x{NAMEOFF_PHYSICAL:08x}",
                "sympool_base": f"0x{SYMPOOL_PHYSICAL:08x}",
                "expected_name": EXPECTED_NAME,
            },
            "read_edge": {
                "pre_read_sym_name_scratch": {
                    "address": f"0x{SYM_NAME_SCRATCH:08x}",
                    "bytes": SYM_NAME_SCRATCH_BYTES,
                },
                "pre_read_DMA_descriptor": {
                    "address": f"0x{C2_DMA_LIST:08x}",
                    "bytes": C2_DMA_LIST_BYTES,
                },
            },
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "One nonpromotable Link-75 target-only DIRMISS-detail "
            "discriminator. Link 75 and product qualification are untouched."),
    }
    write_json(DEPLOYMENT, value)

    changed_session = [
        index for index, pair in enumerate(
            zip(source_session, candidate_session)) if pair[0] != pair[1]]
    changed_product = [
        index for index, pair in enumerate(
            zip(source_product, candidate_product)) if pair[0] != pair[1]]
    receipt = {
        "format": "lisp65-c2.2-link75-dirmiss-detail-hold-patch-v1",
        "recorded_on": "2026-07-28",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "product": bind(PRODUCT, LOAD_ADDRESS),
            "ELF": bind(ELF),
            "session_family": bind(SESSION, SESSION_ADDRESS),
            "session_catalog": bind(SESSION_JSON),
            "base_deployment": bind(BASE_DEPLOYMENT),
            "hardware_First_Red": bind(FIRST_RED),
            "driver": bind(Path(__file__).resolve()),
        },
        "diagnostic_identity": {
            "product": bind(DIAGNOSTIC_PRODUCT, LOAD_ADDRESS),
            "session_family": bind(
                DIAGNOSTIC_SESSION, SESSION_ADDRESS),
            "session_catalog": bind(DIAGNOSTIC_SESSION_JSON),
            "publish_last_binding": bind(DIAGNOSTIC_BINDING),
            "deployment": bind(DEPLOYMENT),
            "lifecycle":
                "discard after one adjudicated three-capture hardware run",
        },
        "patches": [
            {
                "name": "hold-immediately-before-symname",
                "runtime_address": f"0x{HOLD_VMA:04x}",
                "session_family_file_offset": PATCH_FILE_OFFSET,
                "before": PATCH_BEFORE.hex(),
                "after": PATCH_AFTER.hex(),
            },
            {
                "name": "session-family-publish-last-rebind",
                **binding,
            },
        ],
        "identity_rebind": crc,
        "proof": {
            "mutations_rejected": mutations,
            "mutation_count": len(mutations),
            "session_bytes_changed": len(changed_session),
            "session_changed_file_offsets": changed_session,
            "product_bytes_changed": len(changed_product),
            "product_changed_file_offsets": changed_product,
            "artifact_size_deltas": {
                "session_family": 0,
                "resident_PRG": 0,
                "session_region1": 0,
            },
            "source_Link75_unchanged": True,
            "four_disjoint_capture_layers": [
                "context-transport",
                "VM-installer-identity",
                "symbol-storage",
                "symname-read-edge",
            ],
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Follow-up #1 DIRMISS display attribution only. Main stale-carrier "
            "fault is already fixed; no product or promotion claim."),
    }
    write_json(RECEIPT, receipt)
    return {
        "status": "ready",
        "diagnostic_product_sha256": sha(DIAGNOSTIC_PRODUCT),
        "diagnostic_session_sha256": sha(DIAGNOSTIC_SESSION),
        "session_family_crc16": f"0x{new_family_crc:04x}",
        "mutations": f"{len(mutations)}/{len(mutations)}",
        "artifact_size_delta": 0,
    }


def verify() -> dict[str, Any]:
    receipt = load(RECEIPT)
    deployment = load(DEPLOYMENT)
    candidate_session, crc = patch_session(SESSION.read_bytes())
    new_family_crc = R.crc16_ccitt_false(candidate_session)
    candidate_product, candidate_binding, binding = patch_product(
        PRODUCT.read_bytes(), new_family_crc)
    require(
        DIAGNOSTIC_SESSION.read_bytes() == candidate_session
        and DIAGNOSTIC_PRODUCT.read_bytes() == candidate_product
        and DIAGNOSTIC_BINDING.read_bytes() == candidate_binding,
        "diagnostic identity drift",
    )
    mutations = mutation_gate(
        candidate_session, candidate_product, crc, binding)
    require(
        receipt["status"] in (
            "ready-authorized-nonpromotable-hardware",
            "completed-discarded-nonpromotable-dirmiss-capture",
        )
        and deployment["status"]
            == "ready-authorized-nonpromotable-hardware",
        "diagnostic receipt/deployment drift",
    )
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"diagnostic preload drift: {path}",
        )
    require(
        (ROOT / deployment["product"]["path"]).read_bytes()
            == candidate_product,
        "diagnostic product deployment drift",
    )
    return {
        "status": "verified",
        "product": sha(DIAGNOSTIC_PRODUCT),
        "session": sha(DIAGNOSTIC_SESSION),
        "session_family_crc16": f"0x{new_family_crc:04x}",
        "mutations": f"{len(mutations)}/{len(mutations)}",
    }


def command(fd: int, value: bytes, wait: float = 0.02) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.3)


def read_registers(fd: int) -> dict[str, Any]:
    raw = command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})",
        raw,
    )
    require(match is not None, "register row absent")
    pc = int(match.group(1), 16)
    require(pc == HOLD_VMA,
            f"expected hold PC 0x{HOLD_VMA:04x}, found 0x{pc:04x}")
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
        require(
            match is not None,
            f"memory row absent at 0x{current:08x}: {raw!r}",
        )
        value.extend(bytes.fromhex(match.group(1).decode()))
    return bytes(value[:size])


def symi_index(word: int) -> int | None:
    if word & 1 or not 0xE000 <= word <= 0xFFFE:
        return None
    return (word >> 1) - SYMI_BASE


def symbol_storage(fd: int, index: int | None) -> dict[str, Any]:
    if index is None or not 0 <= index < 752:
        return {
            "index": index,
            "valid_index": False,
            "name": None,
        }
    nameoff_address = NAMEOFF_PHYSICAL + index * 2
    nameoff_raw = read_block(fd, nameoff_address, 2)
    nameoff = u16(nameoff_raw)
    raw = read_block(fd, SYMPOOL_PHYSICAL + nameoff, 34)
    name = raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
    return {
        "index": index,
        "valid_index": True,
        "nameoff_address": f"0x{nameoff_address:08x}",
        "nameoff_hex": nameoff_raw.hex(),
        "nameoff": nameoff,
        "name_address": f"0x{SYMPOOL_PHYSICAL + nameoff:08x}",
        "name_bytes_hex": raw.hex(),
        "name": name,
    }


def live_snapshot(fd: int, index: int) -> dict[str, Any]:
    detail_raw = read_block(fd, RENDER_DETAIL, 2)
    pending_raw = read_block(fd, PENDING_SYMBOL, 2)
    nsym_raw = read_block(fd, NSYM, 2)
    npool_raw = read_block(fd, NPOOL, 2)
    scratch = read_block(fd, SYM_NAME_SCRATCH, SYM_NAME_SCRATCH_BYTES)
    dma = read_block(fd, C2_DMA_LIST, C2_DMA_LIST_BYTES)
    live_patch = read_block(fd, HOLD_VMA, 3)
    detail = u16(detail_raw)
    pending = u16(pending_raw)
    nsym = u16(nsym_raw)
    detail_index = symi_index(detail)
    pending_index = symi_index(pending)
    expected_index = nsym - 1 if 0 < nsym <= 752 else None
    detail_storage = symbol_storage(fd, detail_index)
    expected_storage = (
        detail_storage
        if expected_index == detail_index
        else symbol_storage(fd, expected_index))
    return {
        "index": index,
        "captured_at_utc":
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "live_patch_hex": live_patch.hex(),
        "context_transport": {
            "renderer_detail_hex": detail_raw.hex(),
            "renderer_detail_word": f"0x{detail:04x}",
            "pending_symbol_hex": pending_raw.hex(),
            "pending_symbol_word": f"0x{pending:04x}",
            "equal": detail == pending,
        },
        "VM_installer_identity": {
            "detail_SYMI_index": detail_index,
            "pending_SYMI_index": pending_index,
            "nsym_hex": nsym_raw.hex(),
            "nsym": nsym,
            "expected_last_symbol_index": expected_index,
            "detail_is_expected_last_symbol":
                detail_index is not None and detail_index == expected_index,
        },
        "symbol_storage": {
            "npool_hex": npool_raw.hex(),
            "npool": u16(npool_raw),
            "detail": detail_storage,
            "expected_last": expected_storage,
            "expected_name": EXPECTED_NAME,
            "expected_last_name_matches":
                expected_storage.get("name") == EXPECTED_NAME,
        },
        "read_edge": {
            "sym_name_scratch_before_read_hex": scratch.hex(),
            "DMA_descriptor_before_read_hex": dma.hex(),
            "symname_not_yet_called": True,
        },
    }


def adjudicate(row: dict[str, Any]) -> str:
    context = row["context_transport"]
    identity = row["VM_installer_identity"]
    storage = row["symbol_storage"]
    if not context["equal"]:
        return "context-transport"
    if not identity["detail_is_expected_last_symbol"]:
        return "VM-installer-identity"
    if not storage["expected_last_name_matches"]:
        return "symbol-storage"
    return "symname-read-edge"


def capture() -> dict[str, Any]:
    verify()
    require(not CAPTURE.exists(), "DIRMISS-detail capture is one-shot")
    fd = os.open(
        SERIAL.DEVICE, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        SERIAL.configure_serial(fd)
        SERIAL.monitor_sync(fd, b"#c275dirmiss\r")
        command(fd, b"t1", 0.05)
        registers = read_registers(fd)
        rows: list[dict[str, Any]] = []
        for index, delay in enumerate((0, 1, 4), 1):
            if delay:
                time.sleep(delay)
            rows.append(live_snapshot(fd, index))
    finally:
        os.close(fd)
    require(
        all(row["live_patch_hex"] == PATCH_AFTER.hex() for row in rows),
        "live pre-symname hold bytes drift",
    )
    stable_projection = [
        (
            row["context_transport"],
            row["VM_installer_identity"],
            row["symbol_storage"],
        )
        for row in rows
    ]
    require(
        all(value == stable_projection[0] for value in stable_projection[1:]),
        "DIRMISS witnesses changed across three captures",
    )
    outcome = adjudicate(rows[0])
    value = {
        "format": "lisp65-c2.2-link75-dirmiss-detail-capture-v1",
        "recorded_on": "2026-07-28",
        "device": SERIAL.DEVICE,
        "CPU_left_stopped": True,
        "registers": registers,
        "captures": rows,
        "capture_count": len(rows),
        "stable_across_all_captures": True,
        "outcome": outcome,
        "adjudication_order": [
            "context-transport",
            "VM-installer-identity",
            "symbol-storage",
            "symname-read-edge",
        ],
        "claim_limit": (
            "One Link-75 nonpromotable target-only DIRMISS-detail "
            "attribution. Product qualification is not claimed."),
    }
    write_json(CAPTURE, value)
    receipt = load(RECEIPT)
    receipt["status"] = "completed-discarded-nonpromotable-dirmiss-capture"
    receipt["capture"] = bind(CAPTURE)
    receipt["hardware_result"] = {
        "outcome": outcome,
        "captures": len(rows),
        "stable": True,
        "CPU_left_stopped": True,
    }
    receipt["execution_accounting"]["hardware_runs"] = 1
    receipt["diagnostic_identity"]["lifecycle"] = (
        "discarded; retained as nonpromotable evidence only")
    replace_json(RECEIPT, receipt)
    return value


def finalize_existing_capture() -> dict[str, Any]:
    verify()
    value = load(CAPTURE)
    require(
        value["format"] == "lisp65-c2.2-link75-dirmiss-detail-capture-v1"
        and value["capture_count"] == 3
        and value["stable_across_all_captures"] is True
        and value["CPU_left_stopped"] is True,
        "saved DIRMISS capture is incomplete",
    )
    write_json(HARNESS_FIRST_RED, {
        "format":
            "lisp65-c2.2-link75-dirmiss-detail-harness-first-red-v1",
        "recorded_on": "2026-07-28",
        "status": "closed-evidence-writer-only-no-hardware-replay",
        "symptom": (
            "The three captures and capture-summary were written, then the "
            "immutable-artifact writer rejected the intentional ready-to-"
            "completed receipt transition."),
        "scope": "harness/evidence bookkeeping only",
        "hardware_effect": {
            "additional_runs": 0,
            "saved_capture_reused": bind(CAPTURE),
            "CPU_was_left_stopped": True,
        },
        "correction": (
            "Receipt completion uses an atomic replacing JSON writer; "
            "immutable generated identities retain the drift-rejecting writer."),
        "driver": bind(Path(__file__).resolve()),
    })
    receipt = load(RECEIPT)
    receipt["status"] = "completed-discarded-nonpromotable-dirmiss-capture"
    receipt["capture"] = bind(CAPTURE)
    receipt["harness_First_Red"] = bind(HARNESS_FIRST_RED)
    receipt["authority"]["driver"] = bind(Path(__file__).resolve())
    receipt["hardware_result"] = {
        "outcome": value["outcome"],
        "captures": value["capture_count"],
        "stable": value["stable_across_all_captures"],
        "CPU_left_stopped": value["CPU_left_stopped"],
    }
    receipt["execution_accounting"]["hardware_runs"] = 1
    receipt["diagnostic_identity"]["lifecycle"] = (
        "discarded; retained as nonpromotable evidence only")
    replace_json(RECEIPT, receipt)
    return {
        "status": receipt["status"],
        "outcome": value["outcome"],
        "captures": value["capture_count"],
        "hardware_runs": 1,
        "additional_hardware_runs": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("prepare", "verify", "capture", "finalize"))
    action = parser.parse_args().action
    value = (
        prepare() if action == "prepare"
        else verify() if action == "verify"
        else capture() if action == "capture"
        else finalize_existing_capture())
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
            HoldError, R.OverlayBankError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link75-dirmiss-detail-hold: FIRST RED: " + str(error))
        raise SystemExit(2)
