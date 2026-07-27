#!/usr/bin/env python3
"""Bind Link 41's resident-Island seed/final identity hardware First Red."""

from __future__ import annotations

from binascii import crc_hqx
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-41-c2-lite-v6-roots-fronts-coresident-replay3")
HW = ROOT / "build/c2.2/hardware-presmoke-link41-roots-fronts"
CAPTURE = HW / "line1-first-red"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-roots-fronts-coresident-replay3-"
    "structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link41-c2-lite-v6-island-seed-identity-"
    "hardware-first-red.json")

PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
BOOT = CANDIDATE / "runtime-overlays-boot-final.bin"
BOOT_MANIFEST = CANDIDATE / "runtime-overlays-boot-final.json"
SEED_HEADER = CANDIDATE / "resident-island.h"
RUNTIME_SOURCE = CANDIDATE / "generated-product-sources/vm_runtime_overlay.c"
DEPLOYMENT = HW / "deployment.json"

EXPECTED_SHA256 = {
    PRODUCT: "91a5e69d7308dfc31123ff2421fe8b3de56f4a18491a8b35b3378212327ec405",
    ELF: "44570b11d6265529f029bccb162a2c35f2d54ba1fd7df88fbe4c9a6e4172b313",
    STRUCTURAL: "d4836a3aab7398f372e029c919016d9c4fd9a5ce57867a90e590d17b80ca6ab8",
    BOOT: "23b2523171b459e3eef8a3104c22de3a1128b22378c618ff404c582767531ebb",
    DEPLOYMENT: "67d5951bb7956c56436514bf8fdc6ce1a17b65b03b5c44261cf9c16dd44eed67",
    SEED_HEADER: "5645fa276e72318ab280f45bdf8b8487d7000dcec56102829c2180197751a42d",
    RUNTIME_SOURCE: "11c4e60085ced2572fb79c41ee4cb717536b22092bdb558239c3494953957c4c",
}


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def seed_bytes() -> bytes:
    text = SEED_HEADER.read_text(encoding="utf-8")
    require("#define LISP65_RESIDENT_ISLAND_BYTES" in text,
            "resident-Island seed-byte macro absent")
    body = text.split("#define LISP65_RESIDENT_ISLAND_BYTES", 1)[1]
    body = body.split("\n#endif", 1)[0]
    return bytes(int(value, 16) for value in
                 re.findall(r"0x([0-9a-fA-F]{2})(?![0-9a-fA-F])", body))


def main() -> None:
    require(not RECEIPT.exists(), "Link-41 First-Red receipt already exists")
    for path, expected in EXPECTED_SHA256.items():
        require(sha(path) == expected, f"bound evidence drift: {path}")

    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(deployment["product"]["sha256"] == EXPECTED_SHA256[PRODUCT]
            and deployment["status"] == "ready-receipt-less",
            "hardware deployment does not bind Link 41")
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(structural["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-41 structural authority is not the accepted prerequisite")

    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    symbol_values = {
        name: truth.symbol(name).value for name in (
            "rtov_call_context", "rtov_call_result", "rtov_fault",
            "rtov_family", "rtov_island_state", "rtov_loaded_len",
            "c2_ready", "c2_runtime")
    }
    require(symbol_values == {
        "rtov_call_context": 0x006e,
        "rtov_call_result": 0x0070,
        "rtov_fault": 0x0078,
        "rtov_family": 0x0079,
        "rtov_island_state": 0x007a,
        "rtov_loaded_len": 0x007b,
        "c2_ready": 0x008c,
        "c2_runtime": 0xc084,
    }, f"Link-41 state-symbol geometry drift: {symbol_values}")

    low = (CAPTURE / "low-0000-0200.bin").read_bytes()
    soft_stack = (CAPTURE / "soft-stack-c900-d000.bin").read_bytes()
    island = (CAPTURE / "island-1800-2000.bin").read_bytes()
    bank3 = (CAPTURE / "bank3-live.bin").read_bytes()
    require(len(low) == 0x200 and len(soft_stack) == 0x700
            and len(island) == 0x800 and len(bank3) == 0x10000,
            "hardware capture geometry drift")

    frame_address = u16(low, symbol_values["rtov_call_context"])
    require(0xc900 <= frame_address <= 0xd000 - 52,
            f"verify-frame pointer outside captured soft stack: 0x{frame_address:04x}")
    frame_offset = frame_address - 0xc900
    frame = soft_stack[frame_offset:frame_offset + 52]
    record = frame[18:50]
    frame_values = {
        "read_pointer": u16(frame, 0),
        "file_offset": u16(frame, 2),
        "file_length": u16(frame, 4),
        "entry_offset": u16(frame, 6),
        "payload_crc16": u16(frame, 8),
        "payload_offset": u16(frame, 10),
        "image_limit": u16(frame, 12),
        "flags": u16(frame, 14),
        "slot": frame[16],
        "count": frame[17],
        "seal": u16(frame, 50),
    }
    require(frame_values == {
        "read_pointer": 0xae1f,
        "file_offset": 0x3400,
        "file_length": 0x0507,
        "entry_offset": 0x0180,
        "payload_crc16": 0x6d4d,
        "payload_offset": 0x0200,
        "image_limit": 0x4052,
        "flags": 1,
        "slot": 9,
        "count": 11,
        "seal": 0x211e,
    }, f"captured verifier frame drift: {frame_values}")

    record_values = {
        "slot": u16(record, 0),
        "flags": u16(record, 2),
        "file_offset": u16(record, 4),
        "file_length": u16(record, 6),
        "vma": u16(record, 8),
        "memory_length": u16(record, 10),
        "entry_offset": u16(record, 12),
        "abi": u16(record, 14),
        "build_id": int.from_bytes(record[16:20], "little"),
        "payload_crc16": u16(record, 20),
        "record_crc16": u16(record, 22),
    }
    require(record_values == {
        "slot": 10,
        "flags": 9,
        "file_offset": 0x3a00,
        "file_length": 0x0652,
        "vma": 0x1800,
        "memory_length": 0x0652,
        "entry_offset": 0xffff,
        "abi": 0,
        "build_id": 0xa1062184,
        "payload_crc16": 0x56d6,
        "record_crc16": 0xfb38,
    }, f"captured carrier record drift: {record_values}")
    require(record[24:] == bytes(8), "carrier reserved tail is not zero")

    boot = BOOT.read_bytes()
    require(bank3[:len(boot)] == boot,
            "live Bank 3 differs from the exact deployed Boot family")
    begin = record_values["file_offset"]
    end = begin + record_values["file_length"]
    final_island = boot[begin:end]
    require(len(final_island) == 1618
            and crc_hqx(final_island, 0xffff) == 0x56d6
            and sha_bytes(final_island) ==
            "0839114acb60cc1f406fc7de0fefbad694daf95f668289534b319d3ddb2666a1",
            "final carrier payload identity drift")

    manifest = json.loads(BOOT_MANIFEST.read_text(encoding="utf-8"))
    carriers = [row for row in manifest["slices"]
                if row.get("id") == 10]
    require(len(carriers) == 1, "Boot carrier manifest identity is not unique")
    carrier = carriers[0]
    require(carrier["name"] == "resident-island-image"
            and carrier["section"] == ".lisp65_resident_island"
            and carrier["file_offset"] == begin
            and carrier["file_size"] == len(final_island)
            and carrier["crc16"] == 0x56d6
            and carrier["sha256"] == sha_bytes(final_island),
            "final carrier manifest differs from captured record/payload")

    seed = seed_bytes()
    require(len(seed) == 1618 and crc_hqx(seed, 0xffff) == 0x72b1
            and sha_bytes(seed) ==
            "cb07cc9cba10c3e819b4fac781e516769cfd6dcaa8cd9c1f05ca0162e2d8bdb7",
            "materialized seed identity drift")
    differences = [
        {"offset": offset, "seed": old, "final": new,
         "delta": new - old}
        for offset, (old, new) in enumerate(zip(seed, final_island))
        if old != new
    ]
    require(len(differences) == 20
            and differences[0]["offset"] == 1073
            and differences[-1]["offset"] == 1236,
            f"seed/final difference set drift: {differences}")

    source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    require("payload_crc != LISP65_RESIDENT_ISLAND_CRC16" in source
            and "file_len != LISP65_RESIDENT_ISLAND_LENGTH" in source,
            "target no longer rejects the carrier against seed identity")

    hardware_state = {
        "rtov_call_context": frame_address,
        "rtov_call_result": u16(low, symbol_values["rtov_call_result"]),
        "rtov_fault": low[symbol_values["rtov_fault"]],
        "rtov_family": low[symbol_values["rtov_family"]],
        "rtov_loaded_len": u16(low, symbol_values["rtov_loaded_len"]),
        "c2_ready": low[symbol_values["c2_ready"]],
    }
    require(hardware_state == {
        "rtov_call_context": 0xcf9b,
        "rtov_call_result": 0x1800,
        "rtov_fault": 20,
        "rtov_family": 1,
        "rtov_loaded_len": 0,
        "c2_ready": 0,
    }, f"unexpected Link-41 First-Red state: {hardware_state}")
    require(not any(island), "resident Island was not wiped fail-closed")

    receipt = {
        "format": "lisp65-c2-lite-v6-link41-island-seed-identity-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-final-carrier-identity-rejected-by-seed-island-crc",
        "candidate": {
            "product": bind(PRODUCT),
            "elf": bind(ELF),
            "structural_authority": bind(STRUCTURAL),
            "deployment": bind(DEPLOYMENT),
        },
        "hardware": {
            "operator_observation": (
                "blue background, white text: E2f runtime island invalid; redeploy"),
            "line_reached": 1,
            "latency_measurements_completed": 0,
            "two_attempt_rule_slots_consumed": 0,
            "state": hardware_state,
            "decoded": {
                "family": "boot",
                "outer_fault": "VM_RUNTIME_OVERLAY_ERR_ISLAND",
                "c2_published": False,
                "resident_island_after_failure": "2048 zero bytes; fail-closed wipe passed",
            },
        },
        "authenticated_handoff": {
            "verify_frame_address": f"0x{frame_address:04x}",
            "executable_installer_record": frame_values,
            "carrier_record": record_values,
            "carrier_record_raw_hex": record.hex(),
        },
        "transport_exoneration": {
            "bank3_boot_prefix_byteidentical": True,
            "bytes": len(boot),
            "carrier_source_byteidentical": True,
            "carrier_source_sha256": sha_bytes(final_island),
            "carrier_source_crc16": "0x56d6",
        },
        "identity_split": {
            "final_carrier": {
                "bytes": len(final_island),
                "crc16": "0x56d6",
                "sha256": sha_bytes(final_island),
                "authority": "final Boot-family carrier record and payload",
            },
            "compiled_seed": {
                "bytes": len(seed),
                "crc16": "0x72b1",
                "sha256": sha_bytes(seed),
                "authority": "resident-island.h generated from prerequisite seed link",
            },
            "different_bytes": len(differences),
            "difference_offset_first": differences[0]["offset"],
            "difference_offset_last": differences[-1]["offset"],
            "differences": differences,
            "mechanism": (
                "The final single product link moved absolute references inside the "
                "resident Island after resident-island.h had materialized the seed. "
                "The final carrier record correctly binds CRC 0x56d6, but "
                "vm_resident_island_install still compares it with the prerequisite "
                "seed constant 0x72b1 and returns its inner CRC error before copy."),
        },
        "class_c_design_question": {
            "recommended_direction": (
                "Make the authenticated final carrier record the single runtime "
                "identity. Carry its file length and CRC with its existing source "
                "offset through the lifetime-exclusive batch tuple into the finalizer; "
                "retain hard bounds, record CRC, payload convergence and target CRC, "
                "but remove target comparisons against prerequisite seed identity."),
            "permanent_gate": (
                "Bind the final carrier record length/CRC/SHA to the actual final "
                ".lisp65_resident_island bytes and reject any surviving target-runtime "
                "comparison against resident-island seed length/CRC."),
            "alternative_not_selected": (
                "A post-link publish-last patch of seed constants would add another "
                "binding surface; it requires separate Class-C review if preferred."),
        },
        "evidence": {
            "boot_family": bind(BOOT),
            "boot_manifest": bind(BOOT_MANIFEST),
            "seed_header": bind(SEED_HEADER),
            "target_runtime_source": bind(RUNTIME_SOURCE),
            "captures": {
                path.name: bind(path)
                for path in sorted(CAPTURE.iterdir()) if path.is_file()
            },
        },
        "claim_limit": (
            "Read-only diagnosis of one Link-41 receipt-less hardware First Red. "
            "It proves exact Bank-3 transport, a final-carrier/seed identity split, "
            "and fail-closed rejection before READY. It is not a product fix, retry, "
            "latency measurement, promotion or acceptance."),
        "next_gate": (
            "Class-C review of the carrier-as-single-runtime-identity contract and a "
            "product-shaped capacity/semantic probe; no hardware retry is authorized."),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    RECEIPT.chmod(0o444)
    print(RECEIPT.relative_to(ROOT))
    print(sha(RECEIPT))
    print(receipt["status"])


if __name__ == "__main__":
    main()
