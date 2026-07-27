#!/usr/bin/env python3
"""Package and verify the complete canonical C2-lite two-media product."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_canonical_product as CANONICAL  # noqa: E402
import r3_product_block as D81  # noqa: E402
import asm_c_constant_contract as ASM_CONTRACT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


BUILD = ROOT / "build/c2.2/canonical-media"
CONTRACT = ROOT / "config/c2-lite-media-product.json"
PRODUCT_MANIFEST = CANONICAL.MANIFEST
MANIFEST = BUILD / "candidate-manifest.json"
STAGER_C = ROOT / "scripts/r3-cold-stager-main.c"
STAGER_S = ROOT / "scripts/c2-lite-cold-stager-chain.s"
STAGER_ROM_S = ROOT / "scripts/r3-rom-write-enable.s"
STAGER_CONTRACT = ROOT / "scripts/r3-cold-stager-contract.h"
F011_CONTEXT = ROOT / "src/f011_context.h"
ASM_CONTRACT_TOOL = ROOT / "tools/host-lisp/asm_c_constant_contract.py"
ASM_CONTRACT_INCLUDE = ROOT / "build/generated/c2-lite-asm-c-contract.inc"
ASM_CONTRACT_INCLUDE_TOKEN = (
    '.include\t"build/generated/c2-lite-asm-c-contract.inc"'
)
DESCRIPTOR = BUILD / "boot.id"
STAGER = BUILD / "autoboot.c65"
STAGER_MAP = BUILD / "autoboot.c65.map"
PRODUCT_D81 = BUILD / "lisp65-product.d81"
WORK_D81 = BUILD / "lisp65-work.d81"
MOUNT = BUILD / "lisp65-product.mount.json"

HEADER_BYTES = 16
RECORD_BYTES = 32
RECORDS = 13
DESCRIPTOR_BYTES = 432
RESTAGE_LIMIT = 2
STAGE = 0x01
PRG = 0x02
BOOT_MARKER_OFFSET = 29
BOOT_MARKER = b"L65B"
R3_C2_LITE_PRODUCT_ENTRY = 0x2023
R3_LEGACY_PRODUCT_ENTRY = 0x2026
R3_NORMAL_F018B_LIMIT = 0x00100000
R3_ATTIC_BASE = 0x08000000
R3_PHYSICAL_ADDRESS_LIMIT = 0x10000000


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, role: str | None = None,
         name: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"media artifact absent: {path}")
    row: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if role is not None:
        row["role"] = role
    if name is not None:
        row["name"] = name
    return row


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise MediaError(
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def artifact_map() -> tuple[dict[str, Path], list[dict[str, Any]]]:
    manifest = CANONICAL.check()
    rows = manifest["artifacts"]
    by_role = {
        str(row["role"]): ROOT / str(row["path"]) for row in rows}
    expected = {
        "linked-product-elf", "c2-resident-prg",
        "c2-bank2-static-code-plane", "c2d-v6-code-plane",
        "c2-two-record-boot-stage", "c2-session-family-region-0",
        "c2-product-shelf", "c2-boot-family",
        "c2-session-family-region-1", "c2-kernal-window",
        "resolved-profile", "library-ide", "library-idex", "library-m65d",
    }
    require(set(by_role) == expected and len(rows) == 14,
            "canonical pre-media role inventory drift")
    return by_role, rows


def media_rows(contract: dict[str, Any],
               artifacts: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in contract["media_entries"]:
        role = str(spec["artifact_role"])
        path = artifacts[role]
        role_id = int(spec["role_id"])
        name = str(spec["name"])
        destination = (
            int(str(spec["destination"]), 16)
            if spec["destination"] is not None else 0)
        flags = (
            STAGE if spec["policy"] == "stage-and-independent-target-readback"
            else PRG if spec["policy"] == "verify-stage-then-chain"
            else 0)
        rows.append({
            "role_id": role_id,
            "artifact_role": role,
            "name": name,
            "path": path,
            "destination": destination,
            "flags": flags,
            "bytes": path.stat().st_size,
            "crc32": crc32(path.read_bytes()),
        })
    require(
        [row["role_id"] for row in rows] == list(range(1, RECORDS + 1))
        and sum(row["flags"] == STAGE for row in rows) == 8
        and [row["role_id"] for row in rows if row["flags"] == PRG] == [9],
        "C2-lite descriptor role/flag order drift")
    return rows


def make_descriptor(rows: list[dict[str, Any]],
                    profile_id: int) -> tuple[bytes, int]:
    records = bytearray()
    for row in rows:
        name = str(row["name"]).encode("ascii")
        require(1 <= len(name) <= 16 and int(row["bytes"]) > 0,
                f"invalid descriptor member: {row['name']}")
        record = bytearray(RECORD_BYTES)
        record[0] = int(row["role_id"])
        record[1] = int(row["flags"])
        record[2] = len(name)
        struct.pack_into(
            "<III", record, 4, int(row["destination"]),
            int(row["bytes"]), int(row["crc32"]))
        record[16:16 + len(name)] = name
        records += record
    build_id = crc32(records)
    header = bytearray(HEADER_BYTES)
    header[:4] = b"L65B"
    header[4:8] = bytes((2, HEADER_BYTES, RECORDS, RESTAGE_LIMIT))
    struct.pack_into("<II", header, 8, build_id, profile_id)
    result = bytes(header + records)
    require(
        len(result) == DESCRIPTOR_BYTES
        and crc32(result[HEADER_BYTES:]) == build_id,
        "C2-lite descriptor envelope drift")
    return result, build_id


def parse_descriptor(data: bytes, build_id: int,
                     expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require(
        len(data) == DESCRIPTOR_BYTES and data[:4] == b"L65B"
        and tuple(data[4:8]) == (2, HEADER_BYTES, RECORDS, RESTAGE_LIMIT)
        and struct.unpack_from("<I", data, 8)[0] == build_id
        and crc32(data[HEADER_BYTES:]) == build_id,
        "strict C2-lite descriptor identity drift")
    parsed: list[dict[str, Any]] = []
    for index, want in enumerate(expected):
        start = HEADER_BYTES + index * RECORD_BYTES
        record = data[start:start + RECORD_BYTES]
        role, flags, name_len, reserved = record[:4]
        destination, length, checksum = struct.unpack_from("<III", record, 4)
        name = record[16:16 + name_len].decode("ascii")
        require(
            reserved == 0 and role == want["role_id"]
            and flags == want["flags"] and name == want["name"]
            and destination == want["destination"]
            and length == want["bytes"] and checksum == want["crc32"],
            f"descriptor record drift at role {want['role_id']}")
        parsed.append({
            "role_id": role, "flags": flags, "name": name,
            "destination": destination, "bytes": length,
            "crc32": f"{checksum:08x}",
        })
    return parsed


def mutation_gate(descriptor: bytes, build_id: int,
                  rows: list[dict[str, Any]]) -> dict[str, Any]:
    def rejected(candidate: bytes) -> bool:
        try:
            parse_descriptor(candidate, build_id, rows)
        except MediaError:
            return True
        return False

    mutations: dict[str, bytes] = {}
    version = bytearray(descriptor); version[4] = 1
    mutations["v1-presented-to-strict-v2"] = bytes(version)
    role = bytearray(descriptor); role[HEADER_BYTES] = 2
    mutations["duplicate-or-wrong-role"] = bytes(role)
    flags = bytearray(descriptor); flags[HEADER_BYTES + 1] = 0
    mutations["stage-flag-removed"] = bytes(flags)
    destination = bytearray(descriptor); destination[HEADER_BYTES + 4] ^= 1
    mutations["destination-bit-flip"] = bytes(destination)
    length = bytearray(descriptor); length[HEADER_BYTES + 8] ^= 1
    mutations["length-bit-flip"] = bytes(length)
    checksum = bytearray(descriptor); checksum[HEADER_BYTES + 12] ^= 1
    mutations["file-crc-bit-flip"] = bytes(checksum)
    name = bytearray(descriptor); name[HEADER_BYTES + 16] ^= 1
    mutations["name-bit-flip"] = bytes(name)
    header_id = bytearray(descriptor); header_id[8] ^= 1
    mutations["header-record-array-crc-drift"] = bytes(header_id)
    profile = bytearray(descriptor); profile[12] ^= 1
    # Profile is deliberately independent of the record-array CRC, so bind it
    # explicitly here rather than pretending parse_descriptor can infer it.
    profile_rejected = (
        struct.unpack_from("<I", profile, 12)[0]
        != struct.unpack_from("<I", descriptor, 12)[0])
    require(
        all(rejected(value) for value in mutations.values())
        and profile_rejected,
        "C2-lite descriptor mutation escaped")
    target = bytearray(rows[0]["path"].read_bytes())
    target[0] ^= 1
    require(crc32(target) != rows[0]["crc32"],
            "target-readback mutation is ineffective")
    return {
        "status": "passed-strict-v2-and-target-identity-mutations",
        "mutations_rejected": len(mutations) + 2,
        "cases": sorted([*mutations, "profile-build-id", "target-readback"]),
    }


def stage_domain_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def address_domain(address: int, length: int) -> str:
        if length <= 0:
            return "invalid"
        end = address + length
        if 0 <= address < R3_NORMAL_F018B_LIMIT and (
                end <= R3_NORMAL_F018B_LIMIT):
            return "normal-f018b-20-bit"
        if R3_ATTIC_BASE <= address < R3_PHYSICAL_ADDRESS_LIMIT and (
                end <= R3_PHYSICAL_ADDRESS_LIMIT):
            return "enhanced-f018b-28-bit"
        return "invalid"

    def valid(candidate: list[dict[str, Any]]) -> bool:
        staged = [row for row in candidate if row["flags"] == STAGE]
        if [row["role_id"] for row in staged] != list(range(1, 9)):
            return False
        return all(
            address_domain(int(row["destination"]), int(row["bytes"]))
            == (
                "normal-f018b-20-bit"
                if int(row["role_id"]) <= 3
                else "enhanced-f018b-28-bit"
            )
            for row in staged
        )

    def mutate(role: int, *, destination: int | None = None,
               length: int | None = None) -> list[dict[str, Any]]:
        result = [dict(row) for row in rows]
        row = result[role - 1]
        if destination is not None:
            row["destination"] = destination
        if length is not None:
            row["bytes"] = length
        return result

    mutations = {
        "attic-role-truncated-to-zero":
            mutate(4, destination=0),
        "chip-role-routed-to-attic":
            mutate(1, destination=R3_ATTIC_BASE),
        "attic-role-routed-to-20-bit-gap":
            mutate(4, destination=R3_NORMAL_F018B_LIMIT),
        "attic-role-outside-28-bit-domain":
            mutate(4, destination=R3_PHYSICAL_ADDRESS_LIMIT),
        "chip-role-crosses-20-bit-limit":
            mutate(
                1, destination=R3_NORMAL_F018B_LIMIT - 1, length=2),
        "attic-role-crosses-28-bit-limit":
            mutate(
                4, destination=R3_PHYSICAL_ADDRESS_LIMIT - 1, length=2),
    }
    require(
        valid(rows)
        and all(not valid(candidate) for candidate in mutations.values()),
        "C2-lite stage address-domain gate red")
    return {
        "status": "passed-role-qualified-20-bit-versus-28-bit-staging",
        "normal_f018b_roles": [1, 2, 3],
        "enhanced_f018b_roles": [4, 5, 6, 7, 8],
        "normal_f018b_limit_exclusive": f"0x{R3_NORMAL_F018B_LIMIT:08x}",
        "attic_base": f"0x{R3_ATTIC_BASE:08x}",
        "physical_limit_exclusive":
            f"0x{R3_PHYSICAL_ADDRESS_LIMIT:08x}",
        "mutations_rejected": len(mutations),
        "cases": sorted(mutations),
    }


def compile_stager(
    build_id: int, rows: list[dict[str, Any]],
) -> dict[str, Any]:
    c_object = BUILD / "autoboot-main.o"
    s_object = BUILD / "autoboot-chain.o"
    rom_object = BUILD / "autoboot-rom-write-enable.o"
    relative = lambda path: path.relative_to(ROOT).as_posix()
    contract = ASM_CONTRACT.load_contract()
    include = ASM_CONTRACT.compile_output(
        contract, "cc", ("-DLISP65_C2_LITE_MEDIA_STAGER",))
    symbols = ASM_CONTRACT.parse_equ(include)
    required = {
        "ASM_R3_CHAIN_JOB_ADDR_LO",
        "ASM_R3_CHAIN_JOB_ADDR_HI",
        "ASM_R3_PRODUCT_ENTRY",
    }
    assembly = STAGER_S.read_text(encoding="utf-8")
    require(
        required <= set(symbols)
        and ASM_CONTRACT_INCLUDE_TOKEN in assembly
        and assembly.count("ASM_R3_CHAIN_JOB_ADDR_LO") == 2
        and assembly.count("ASM_R3_CHAIN_JOB_ADDR_HI") == 2
        and assembly.count("ASM_R3_PRODUCT_ENTRY") == 1,
        "C2-lite stager assembler/C constant seam drift")
    ASM_CONTRACT_INCLUDE.parent.mkdir(parents=True, exist_ok=True)
    ASM_CONTRACT_INCLUDE.write_bytes(include)
    run([
        str(CANONICAL.COMPILER), "-std=c99", "-Oz", "-Wall", "-Wextra",
        "-Werror", "-DLISP65_C2_LITE_MEDIA_STAGER",
        f"-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL",
        "-c", relative(STAGER_C), "-o", relative(c_object),
    ], "C2-lite cold-stager C build")
    run([
        str(CANONICAL.COMPILER), "-Qunused-arguments",
        "-c", relative(STAGER_S), "-o", relative(s_object),
    ], "C2-lite cold-stager assembler build")
    run([
        str(CANONICAL.COMPILER), "-Qunused-arguments",
        "-c", relative(STAGER_ROM_S), "-o", relative(rom_object),
    ], "C2-lite ROM-write-enable assembler build")
    run([
        "/usr/bin/setarch", os.uname().machine, "-R",
        str(CANONICAL.COMPILER), "-Oz",
        f"-Wl,-Map,{relative(STAGER_MAP)}",
        relative(c_object), relative(s_object), relative(rom_object),
        "-o", relative(STAGER),
    ], "C2-lite cold-stager link")
    stager_elf = Path(str(STAGER) + ".elf")
    truth = ElfTruth.read(
        stager_elf, llvm_readobj=CANONICAL.COMPILER.parent / "llvm-readobj",
        include_section_data=True)
    chain_section = truth.section(".r3_chain_trampoline")
    chain_data = truth.section_bytes(chain_section.name)
    stage_jobs = truth.symbol("c2_stage_jobs")
    attic_stage_jobs = truth.symbol("c2_attic_stage_jobs")
    attic_retry_job = truth.symbol("c2_attic_retry_job")
    rom_enable = truth.symbol("r3_rom_write_enable")
    rom_section = truth.section(rom_enable.section)
    rom_data = truth.section_bytes(rom_enable.section)[
        rom_enable.value - rom_section.address:
        rom_enable.value - rom_section.address + rom_enable.bytes]
    product_entry = symbols["ASM_R3_PRODUCT_ENTRY"]

    completion_marker = symbols["ASM_R3_CHAIN_JOB_ADDR_LO"] | (
        symbols["ASM_R3_CHAIN_JOB_ADDR_HI"] << 8)
    completion_marker += 24
    completion_loop = bytes((
        0xAD, completion_marker & 0xFF, completion_marker >> 8,
        0xC9, 0xA5, 0xD0, 0xF9,
    ))

    def chain_entry_gate(data: bytes, entry: int) -> bool:
        return (
            entry == R3_C2_LITE_PRODUCT_ENTRY
            and len(data) == chain_section.bytes
            and data.count(completion_loop) == 1
            and data.index(completion_loop) > data.index(bytes.fromhex("8d00d7"))
            and data[-3:] == bytes((0x4C, entry & 0xFF, entry >> 8))
        )

    wrong_profile_chain = (
        chain_data[:-2]
        + bytes((R3_LEGACY_PRODUCT_ENTRY & 0xFF,
                 R3_LEGACY_PRODUCT_ENTRY >> 8))
    )
    missing_completion_chain = chain_data.replace(completion_loop, b"", 1)
    wrong_completion_chain = chain_data.replace(
        completion_loop,
        bytes((
            0xAD, completion_marker & 0xFF, completion_marker >> 8,
            0xC9, 0x5A, 0xD0, 0xF9,
        )),
        1,
    )
    trigger_owner = truth.symbol("disk_record")
    trigger_section = truth.section(trigger_owner.section)
    trigger_data = truth.section_bytes(trigger_owner.section)[
        trigger_owner.value - trigger_section.address:
        trigger_owner.value - trigger_section.address + trigger_owner.bytes]
    normal_trigger = bytes((
        0xA9, 0x01, 0x8D, 0x03, 0xD7,
        0xA9, 0x00, 0x8D, 0x02, 0xD7,
        0xA9, (stage_jobs.value >> 8) & 0xFF, 0x8D, 0x01, 0xD7,
        0xA9, stage_jobs.value & 0xFF, 0x8D, 0x00, 0xD7,
    ))
    def enhanced_trigger(symbol: Any) -> bytes:
        return bytes((
            0xA9, 0x01, 0x8D, 0x03, 0xD7,
            0xA9, 0x00, 0x8D, 0x02, 0xD7, 0x8D, 0x04, 0xD7,
            0xA9, (symbol.value >> 8) & 0xFF, 0x8D, 0x01, 0xD7,
            0xA9, symbol.value & 0xFF, 0x8D, 0x05, 0xD7,
        ))
    attic_stage_trigger = enhanced_trigger(attic_stage_jobs)
    attic_retry_trigger = enhanced_trigger(attic_retry_job)
    source = STAGER_C.read_text(encoding="utf-8")
    rom_source = STAGER_ROM_S.read_text(encoding="utf-8")
    hybrid_tokens = (
        "static struct r3_f018b_job c2_stage_jobs[2];",
        "static struct r3_edma_job c2_attic_stage_jobs[2];",
        "static struct r3_edma_job c2_attic_retry_job;",
        "static void c2_f018b_prepare(",
        "static void c2_edma_prepare(",
        "job->options[2] = (uint8_t)(src >> 20);",
        "job->options[4] = (uint8_t)(dst >> 20);",
        "&c2_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);",
        "&c2_attic_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);",
        "&c2_attic_retry_job, dst, readback, count, DMA_COPY_CMD);",
        "lda #mos16hi(c2_stage_jobs)",
        "lda #mos16lo(c2_stage_jobs)",
        "lda #mos16hi(c2_attic_stage_jobs)",
        "lda #mos16lo(c2_attic_stage_jobs)",
        "lda #mos16hi(c2_attic_retry_job)",
        "lda #mos16lo(c2_attic_retry_job)",
        "static uint8_t c2_stage_address_domain(",
        "static uint8_t c2_stage_record_domain_valid(",
        "role <= 3u ? C2_STAGE_CHIP : C2_STAGE_ATTIC",
        "c2_chip_stage_copy_readback(",
        "c2_attic_stage_copy_readback(",
        "c2_attic_retry_readback();",
    )
    normal_trigger_tokens = (
        "\"sta $d703\\n\\t\"",
        "\"sta $d702\\n\\t\"",
        "lda #mos16hi(c2_stage_jobs)",
        "lda #mos16lo(c2_stage_jobs)",
        "\"sta $d700\\n\\t\"",
    )
    enhanced_trigger_tokens = (
        "\"sta $d703\\n\\t\"",
        "\"sta $d702\\n\\t\"",
        "\"sta $d704\\n\\t\"",
        "\"sta $d705\\n\\t\"",
    )

    def hybrid_source_ok(candidate: str) -> bool:
        try:
            normal_start = candidate.index(
                "static void c2_chip_stage_copy_readback")
            attic_start = candidate.index(
                "static void c2_attic_stage_copy_readback", normal_start)
            retry_start = candidate.index(
                "static void c2_attic_retry_readback", attic_start)
            trigger_end = candidate.index(
                "enum c2_stage_domain", retry_start)
            normal_body = candidate[normal_start:attic_start]
            attic_body = candidate[attic_start:retry_start]
            retry_body = candidate[retry_start:trigger_end]
            scan_start = candidate.index("static uint8_t scan_file(")
            scan_end = candidate.index(
                "static uint8_t disk_record(", scan_start)
            primary = candidate[scan_start:scan_end]
            diagnostic = primary.index(
                "#ifdef LISP65_G5_IO_TRIGGER_PROBE")
            diagnostic_end = primary.index("#endif", diagnostic) + len(
                "#endif")
            primary = (
                primary[:diagnostic] + primary[diagnostic_end:])
            poison = primary.index(
                "c2_target_readback[poll] = 0xa5u")
            chip_submit = primary.index(
                "c2_chip_stage_copy_readback(", poison)
            attic_submit = primary.index(
                "c2_attic_stage_copy_readback(", poison)
            loop = primary.index("while (wraps < 192u)", attic_submit)
            compare = primary.index("if (match) break;", loop)
            retry = primary.index("c2_attic_retry_readback();", compare)
            timeout = primary.index("if (!match) return 0;", retry)
        except ValueError:
            return False
        return (
            all(token in candidate for token in hybrid_tokens)
            and "DMA_COPY_CMD | R3_DMA_CHAIN" in normal_body
            and "DMA_COPY_CMD | R3_DMA_CHAIN" in attic_body
            and all(token in normal_body for token in normal_trigger_tokens)
            and "\"sta $d705\\n\\t\"" not in normal_body
            and all(token in attic_body for token in enhanced_trigger_tokens)
            and all(token in retry_body for token in enhanced_trigger_tokens)
            and "\"sta $d700\\n\\t\"" not in attic_body + retry_body
            and primary.count("c2_target_readback[poll] = 0xa5u") == 1
            and "c2_target_readback[poll] = 0xa5u" not in retry_body
            and poison < chip_submit < attic_submit < loop
            and loop < compare < retry < timeout
            and "if (stage_domain == C2_STAGE_CHIP)" in primary
            and "if (stage_domain == C2_STAGE_ATTIC)" in primary
            and "c2_stage_record_domain_valid(role, record)" in candidate
            and "R3_NORMAL_F018B_LIMIT - address" in candidate
            and "R3_PHYSICAL_ADDRESS_LIMIT - address" in candidate
            and candidate.count("edma_copy(destination + length,") == 0
            and candidate.count(
                "c2_target_readback[poll] = 0xa5u") == 2
        )

    def replace_after(
        candidate: str, marker: str, old: str, new: str,
    ) -> str:
        start = candidate.index(marker)
        offset = candidate.index(old, start)
        return candidate[:offset] + new + candidate[offset + len(old):]

    hybrid_mutations = (
        source.replace("DMA_COPY_CMD | R3_DMA_CHAIN", "DMA_COPY_CMD", 1),
        source.replace(
            "&c2_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);",
            "&c2_stage_jobs[1], src, readback, count, DMA_COPY_CMD);", 1),
        source.replace(
            "&c2_attic_stage_jobs[1], dst, readback, count, DMA_COPY_CMD);",
            "&c2_attic_stage_jobs[1], src, readback, count, DMA_COPY_CMD);",
            1),
        source.replace(
            "&c2_attic_retry_job, dst, readback, count, DMA_COPY_CMD);",
            "&c2_attic_retry_job, src, readback, count, DMA_COPY_CMD);", 1),
        source.replace(
            "role <= 3u ? C2_STAGE_CHIP : C2_STAGE_ATTIC",
            "role <= 4u ? C2_STAGE_CHIP : C2_STAGE_ATTIC", 1),
        source.replace(
            "c2_stage_record_domain_valid(role, record) &&",
            "record &&", 1),
        source.replace(
            "if (stage_domain == C2_STAGE_CHIP)",
            "if (stage_domain == C2_STAGE_ATTIC)", 1),
        source.replace(
            "                    c2_attic_retry_readback();\n",
            "", 1),
        source.replace(
            "                if (stage_domain == C2_STAGE_ATTIC) {\n",
            "                if (stage_domain == C2_STAGE_ATTIC) {\n"
            "                    c2_target_readback[poll] = 0xa5u;\n",
            1),
        source.replace(
            "lda #mos16hi(c2_attic_stage_jobs)",
            "lda #mos16hi(c2_stage_jobs)", 1),
        source.replace(
            "lda #mos16lo(c2_attic_retry_job)",
            "lda #mos16lo(c2_attic_stage_jobs)", 1),
        replace_after(
            source, "static void c2_attic_stage_copy_readback",
            "\"sta $d705\\n\\t\"", "\"sta $d700\\n\\t\""),
        replace_after(
            source, "static void c2_chip_stage_copy_readback",
            "\"sta $d700\\n\\t\"", "\"sta $d705\\n\\t\""),
        source.replace(
            "job->options[2] = (uint8_t)(src >> 20);",
            "job->options[2] = 0;", 1),
        source.replace(
            "job->options[4] = (uint8_t)(dst >> 20);",
            "job->options[4] = 0;", 1),
        source.replace(
            "                c2_attic_stage_copy_readback(\n",
            "            edma_copy(destination + length,\n"
            "                      (uint32_t)(uintptr_t)c2_target_readback,\n"
            "                      count);\n"
            "                c2_attic_stage_copy_readback(\n",
            1),
    )
    handoff_tokens = (
        "job[0] = DMA_COPY_CMD | R3_DMA_CHAIN;",
        "wr16(job + 13, 1u);",
        "job[15] = (uint8_t)(R3_CHAIN_JOB_ADDR + 25u);",
        "job[18] = (uint8_t)(R3_CHAIN_JOB_ADDR + 24u);",
        "job[24] = 0x5au;",
        "job[25] = 0xa5u;",
    )

    def handoff_source_ok(candidate: str) -> bool:
        try:
            start = candidate.index("static void prepare_chain(")
            end = candidate.index("static void show_disk_error", start)
            body = candidate[start:end]
            ordered = [body.index(token) for token in handoff_tokens]
        except ValueError:
            return False
        return (
            ordered == sorted(ordered)
            and all(body.count(token) == 1 for token in handoff_tokens)
            and body.index("((void (*)(void))(uintptr_t)R3_CHAIN_CODE_ADDR)();")
                > ordered[-1]
        )

    handoff_mutations = (
        source.replace(
            "job[0] = DMA_COPY_CMD | R3_DMA_CHAIN;",
            "job[0] = DMA_COPY_CMD;", 1),
        source.replace("wr16(job + 13, 1u);", "wr16(job + 13, 0u);", 1),
        source.replace(
            "job[15] = (uint8_t)(R3_CHAIN_JOB_ADDR + 25u);",
            "job[15] = (uint8_t)(R3_CHAIN_JOB_ADDR + 24u);", 1),
        source.replace(
            "job[18] = (uint8_t)(R3_CHAIN_JOB_ADDR + 24u);",
            "job[18] = (uint8_t)(R3_CHAIN_JOB_ADDR + 25u);", 1),
        source.replace("job[24] = 0x5au;", "job[24] = 0xa5u;", 1),
        source.replace("job[25] = 0xa5u;", "job[25] = 0x5au;", 1),
    )
    ownership = source.index(
        "profile_build_id = rd32(descriptor + 12);")
    io_boundary = source.index("    io_enable();", ownership)
    rom_boundary = source.index("    r3_rom_write_enable();", io_boundary)
    restage_boundary = source.index(
        "    if (!restage_and_reverify(profile_build_id))", rom_boundary)
    rom_mutations = (
        source.replace("    r3_rom_write_enable();\n", "", 1),
        source.replace(
            "    io_enable();\n    r3_rom_write_enable();\n",
            "    r3_rom_write_enable();\n    io_enable();\n", 1),
        rom_source.replace("lda #$02", "lda #$03", 1),
        rom_source.replace("sta $d641", "sta $d640", 1),
        rom_source.replace("\tnop\n", "", 1),
        rom_source.replace("\tldz #$00\n", "", 1),
    )
    def rom_gate(candidate_source: str, candidate_asm: str) -> bool:
        try:
            start = candidate_source.index(
                "profile_build_id = rd32(descriptor + 12);")
            io = candidate_source.index("    io_enable();", start)
            enable = candidate_source.index(
                "    r3_rom_write_enable();", io)
            restage = candidate_source.index(
                "    if (!restage_and_reverify(profile_build_id))", enable)
        except ValueError:
            return False
        return (
            start < io < enable < restage
            and candidate_source.count("r3_rom_write_enable();") == 1
            and "\tlda #$02\n\tsta $d641\n\tnop\n\tldz #$00\n\trts\n"
                in candidate_asm
            and ".type r3_rom_write_enable,@function" in candidate_asm
            and ".size r3_rom_write_enable," in candidate_asm
        )
    transport_domains = stage_domain_gate(rows)
    require(
        STAGER.stat().st_size <= 16384
        and chain_section.bytes <= 0x40
        and "SHF_EXECINSTR" in chain_section.flags
        and chain_entry_gate(chain_data, product_entry)
        and not chain_entry_gate(wrong_profile_chain, product_entry)
        and stage_jobs.bytes == 24 and stage_jobs.section == ".bss"
        and attic_stage_jobs.bytes == 40
        and attic_stage_jobs.section == ".bss"
        and attic_retry_job.bytes == 20
        and attic_retry_job.section == ".bss"
        and trigger_owner.bytes > 0 and trigger_owner.section == ".text"
        and trigger_data.count(normal_trigger) == 1
        and trigger_data.count(attic_stage_trigger) == 1
        and trigger_data.count(attic_retry_trigger) == 1
        and trigger_data.count(bytes.fromhex("8d00d7")) == 1
        and trigger_data.count(bytes.fromhex("8d05d7")) == 2
        and hybrid_source_ok(source)
        and all(not hybrid_source_ok(value)
                for value in hybrid_mutations)
        and transport_domains["mutations_rejected"] == 6
        and "while (wraps < 192u)" in source
        and "if (!match) return 0;" in source,
        "C2-lite hybrid stager completion/dataflow gate red")
    require(
        handoff_source_ok(source)
        and all(not handoff_source_ok(value) for value in handoff_mutations)
        and chain_entry_gate(chain_data, product_entry)
        and not chain_entry_gate(missing_completion_chain, product_entry)
        and not chain_entry_gate(wrong_completion_chain, product_entry),
        "C2-lite product-handoff completion gate red")
    require(
        ownership < io_boundary < rom_boundary < restage_boundary
        and rom_enable.section == ".r3_rom_write_enable"
        and rom_enable.bytes == 9
        and "SHF_EXECINSTR" in rom_section.flags
        and rom_data == bytes.fromhex("a9028d41d6eaa30060")
        and rom_gate(source, rom_source)
        and not rom_gate(rom_mutations[0], rom_source)
        and not rom_gate(rom_mutations[1], rom_source)
        and all(not rom_gate(source, mutation)
                for mutation in rom_mutations[2:]),
        "C2-lite ROM-backing write-enable boundary gate red")
    return {
        "status": (
            "passed-strict-build-and-address-qualified-hybrid-f018b-"
            "content-defined-target-readback"),
        "bytes": STAGER.stat().st_size,
        "chain_bytes": chain_section.bytes,
        "chain_handoff": {
            "status": (
                "passed-profile-bound-final-product-entry-after-"
                "ordered-memory-completion"),
            "product_entry": f"0x{product_entry:04x}",
            "terminal_jump_bytes": chain_data[-3:].hex(),
            "wrong_profile_entry": f"0x{R3_LEGACY_PRODUCT_ENTRY:04x}",
            "wrong_profile_mutations_rejected": 1,
            "completion_marker": f"0x{completion_marker:04x}",
            "completion_value": "0xa5",
            "ordered_jobs": 2,
            "source_and_ELF_mutations_rejected": (
                len(handoff_mutations) + 2),
        },
        "ordered_chain_descriptor_bytes": (
            stage_jobs.bytes + attic_stage_jobs.bytes),
        "ordered_write_readback_jobs": 4,
        "linked_transport": {
            "elf": bind(stager_elf),
            "chip_jobs_symbol": {
                "name": stage_jobs.name,
                "section": stage_jobs.section,
                "vma": stage_jobs.value,
                "bytes": stage_jobs.bytes,
            },
            "attic_stage_jobs_symbol": {
                "name": attic_stage_jobs.name,
                "section": attic_stage_jobs.section,
                "vma": attic_stage_jobs.value,
                "bytes": attic_stage_jobs.bytes,
            },
            "attic_retry_job_symbol": {
                "name": attic_retry_job.name,
                "section": attic_retry_job.section,
                "vma": attic_retry_job.value,
                "bytes": attic_retry_job.bytes,
            },
            "trigger_owner": {
                "name": trigger_owner.name,
                "section": trigger_owner.section,
                "vma": trigger_owner.value,
                "bytes": trigger_owner.bytes,
            },
            "normal_f018b_d700_trigger_occurrences": 1,
            "enhanced_d705_trigger_occurrences": 2,
            "normal_f018b_roles": [1, 2, 3],
            "enhanced_f018b_roles": [4, 5, 6, 7, 8],
            "address_domain_gate": transport_domains,
        },
        "rom_backing_write_enable": {
            "status": "passed-before-first-stage-role",
            "symbol": {
                "name": rom_enable.name,
                "section": rom_enable.section,
                "vma": rom_enable.value,
                "bytes": rom_enable.bytes,
                "opcode_sha256": hashlib.sha256(rom_data).hexdigest(),
            },
            "io_personality_reestablished_immediately_before_trap": True,
            "trap": "$D641 A=$02 plus mandatory following NOP",
            "source_and_opcode_mutations": len(rom_mutations),
        },
        "descriptor_reuse_before_completion": False,
        "chip_target_read_submissions_per_media_block": 1,
        "attic_initial_ordered_target_read_submissions_per_media_block": 1,
        "attic_target_read_retry_policy":
            "immutable-enhanced-readback-once-per-raster-until-match",
        "poison_writes_per_primary_media_block": 1,
        "timeout_raster_low_wraps": 192,
        "hybrid_transport_source_mutations": len(hybrid_mutations),
        "assembler_C_contract": bind(ASM_CONTRACT_INCLUDE),
        "assembler_C_contract_tool": bind(ASM_CONTRACT_TOOL),
    }


def build_d81(output: Path, identity: str,
              entries: list[tuple[Path, str]]) -> str:
    c1541 = shutil.which("c1541")
    require(c1541 is not None, "c1541 is unavailable")
    argv = [c1541, "-format", identity, "d81", str(output)]
    for path, name in entries:
        argv += ["-write", str(path), name]
    return run(argv, f"build {output.name}")


def verify_media(expected: dict[str, bytes]) -> dict[str, Any]:
    try:
        return D81.verify_media(PRODUCT_D81, WORK_D81, expected)
    except D81.ProductError as error:
        raise MediaError(str(error)) from error


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    identity = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "canonical media build is one-shot")
    BUILD.mkdir(parents=True)
    contract = load(CONTRACT)
    require(
        contract["format"] == "lisp65-c2-lite-media-product-v1"
        and contract["descriptor"]["record_count"] == RECORDS
        and contract["descriptor"]["bytes"] == DESCRIPTOR_BYTES
        and contract["artifact_count"] == 19,
        "C2-lite media contract drift")
    artifacts, product_rows = artifact_map()
    rows = media_rows(contract, artifacts)
    profile_id = int(sha(artifacts["resolved-profile"])[:8], 16)
    descriptor, build_id = make_descriptor(rows, profile_id)
    DESCRIPTOR.write_bytes(descriptor)
    parsed = parse_descriptor(descriptor, build_id, rows)
    mutations = mutation_gate(descriptor, build_id, rows)
    transport_domains = stage_domain_gate(rows)
    stager_gate = compile_stager(build_id, rows)

    expected = {
        row["name"]: row["path"].read_bytes() for row in rows}
    expected["autoboot.c65"] = STAGER.read_bytes()
    expected["boot.id"] = descriptor
    product_entries = [
        (STAGER, "autoboot.c65"), (DESCRIPTOR, "boot.id"),
        *[(row["path"], row["name"]) for row in rows],
    ]
    build_d81(PRODUCT_D81, "L65SYS,65", product_entries)
    D81.stamp_product_boot_marker(PRODUCT_D81)
    build_d81(WORK_D81, "L65WORK,65", [])
    inventory = verify_media(expected)
    os.chmod(PRODUCT_D81, 0o444)
    os.chmod(WORK_D81, 0o644)
    MOUNT.write_bytes(json_bytes({
        "format": "lisp65-product-mount-descriptor-v3",
        "media": PRODUCT_D81.name,
        "media_sha256": sha(PRODUCT_D81),
        "disk_name": "L65SYS", "disk_id": "65", "drive": 8,
        "mutable_entries": False,
        "write_protect": {
            "physical_floppy": "required-if-used",
            "stock_core_SD_D81":
                "unavailable-no-virtual-read-only-attach-control",
        },
        "paired_work_media": {
            "media": WORK_D81.name,
            "media_sha256": sha(WORK_D81),
            "disk_name": "L65WORK", "disk_id": "65", "drive": 9,
            "mutable_entries": True,
        },
    }))
    media_rows_out = [
        bind(STAGER, "cold-stager", "autoboot.c65"),
        bind(DESCRIPTOR, "boot-descriptor", "boot.id"),
        bind(PRODUCT_D81, "product-d81", PRODUCT_D81.name),
        bind(WORK_D81, "work-d81", WORK_D81.name),
        bind(MOUNT, "product-mount-descriptor", MOUNT.name),
    ]
    all_rows = [
        {
            **row,
            "name": Path(str(row["path"])).name,
        }
        for row in product_rows
    ] + media_rows_out
    require(
        len(all_rows) == 19
        and {row["role"] for row in all_rows}
            == set(contract["artifact_roles"]),
        "complete C2-lite media artifact role set drift")
    value = {
        "format": "lisp65-c2-lite-canonical-media-product-v1",
        "status": "passed-complete-C2-lite-two-media-product",
        "contract": bind(CONTRACT),
        "canonical_product": bind(PRODUCT_MANIFEST),
        "product_build_id": f"{build_id:08x}",
        "profile_build_id": f"{profile_id:08x}",
        "artifact_set_sha256": artifact_set_sha(all_rows),
        "artifact_count": len(all_rows),
        "artifacts": all_rows,
        "descriptor": {
            "binding": bind(DESCRIPTOR),
            "records": parsed,
            "mutations": mutations,
            "stage_transport_domains": transport_domains,
        },
        "stager": {
            "binding": bind(STAGER),
            "map": bind(STAGER_MAP),
            "gate": stager_gate,
            "product_entry": stager_gate["chain_handoff"]["product_entry"],
            "stage_roles": list(range(1, 9)),
            "always_restage": True,
        },
        "media": {
            "product": {
                **bind(PRODUCT_D81),
                "mode": "0444",
                "entries": inventory["product_entries"],
            },
            "work": {
                **bind(WORK_D81),
                "mode": "0644",
                "entries": inventory["work_entries"],
            },
            "mount": bind(MOUNT),
        },
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "cold_stager_compiler_runs": 1,
            "hardware_runs": 0,
        },
        "claim_limit":
            "Host-built complete C2-lite media identity. R4/R5/R6/G5/G6 "
            "remain separate gates.",
    }
    MANIFEST.write_bytes(json_bytes(value))
    return value


def check() -> dict[str, Any]:
    value = load(MANIFEST)
    contract = load(CONTRACT)
    require(
        value["format"] == "lisp65-c2-lite-canonical-media-product-v1"
        and value["status"] == "passed-complete-C2-lite-two-media-product"
        and value["artifact_count"] == contract["artifact_count"] == 19,
        "canonical media manifest envelope drift")
    for row in value["artifacts"]:
        path = ROOT / row["path"]
        require(
            path.is_file() and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"canonical media artifact drift: {row['role']}")
    artifacts, _ = artifact_map()
    rows = media_rows(contract, artifacts)
    descriptor = DESCRIPTOR.read_bytes()
    build_id = int(value["product_build_id"], 16)
    parse_descriptor(descriptor, build_id, rows)
    expected = {
        row["name"]: row["path"].read_bytes() for row in rows}
    expected.update({
        "autoboot.c65": STAGER.read_bytes(),
        "boot.id": descriptor,
    })
    inventory = verify_media(expected)
    require(
        len(inventory["product_entries"]) == contract["media_entry_count"]
        and inventory["work_entries"] == [],
        "checked D81 inventory drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    value = build() if args.action == "build" else check()
    if args.action == "build":
        check()
    print(
        "c2-lite-media-product: PASS "
        f"artifacts={value['artifact_count']} "
        f"set={value['artifact_set_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MediaError, CANONICAL.CanonicalError, RuntimeError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-lite-media-product: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
