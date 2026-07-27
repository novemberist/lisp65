#!/usr/bin/env python3
"""Probe the L65R-v2 executable/data split for the real Resident Island."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402
import resident_island as ISLAND  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


CONTRACT = ROOT / "config/c2-resident-island-two-record-contract.json"
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-profile-inventory-structural-receipt.json")
FIRST_RED_SHA = "35e1ac3021b70f1bd8a6f0236356f9a6dc011d401075ec46bfff9bbb8f3fc3c7"
SOURCE = ROOT / (
    "build/c2.2/substitution/product-link-33-profile-inventory-final")
SEED_ELF = SOURCE / "resident-island-seed.prg.elf"
SEED_ELF_SHA = "50c596006b4cc86f0c1cbd27e557dfb351683fa123eaf27a8ba3513827a13f28"
FINAL_LTO = SOURCE / "lisp65-c2-substitution-linked.prg.lto.o"
FINAL_LTO_SHA = "76d811ed13cb7c2512a56ec9466fc1af90f69862460b2ccc3d392774e43dd94f"
FINAL_MAP = SOURCE / "lisp65-c2-substitution-linked.prg.map"
RESOLVED = SOURCE / "resolved-profile.txt"
OUT = ROOT / "build/c2.2/substitution/link33-two-record-island-carrier-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-resident-island-two-record-contract-probe-receipt.json")
VERSION = 2
DATA_ONLY = 0x0008
KNOWN_FLAGS_V2 = R.KNOWN_FLAGS | DATA_ONLY
BOOT_BASE = 0x08200000
DESTINATION = 0x1800
COMMON_VMA = 0xC356
ENTRY_NONE = 0xFFFF
ABI_NONE = 0
CAP = 1792


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def align(value: int) -> int:
    return (value + 255) & ~255


def extract_section(elf: Path, section: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="lisp65-two-record-") as name:
        target = Path(name) / "section.bin"
        subprocess.run([
            str(P.TOOLCHAIN / "llvm-objcopy"), "-O", "binary",
            f"--only-section={section}", str(elf), str(target),
        ], check=True, capture_output=True)
        require(target.is_file(), f"section extraction absent: {section}")
        return target.read_bytes()


def symbols(elf: Path) -> dict[str, int]:
    output = subprocess.run([
        str(P.TOOLCHAIN / "llvm-nm"), "--defined-only", str(elf),
    ], check=True, capture_output=True, text=True).stdout
    result: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3:
            result[fields[-1]] = int(fields[0], 16)
    return result


def flags(text: str) -> int:
    result = 0
    for role in text.split("+"):
        result |= {"boot": R.FLAG_BOOT, "runtime": R.FLAG_RUNTIME,
                   "reusable": R.FLAG_REUSABLE}[role]
    return result


def map_sections() -> dict[str, int]:
    result: dict[str, int] = {}
    for line in FINAL_MAP.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+"
            r"(\.[^\s:]+)$", line)
        if match:
            result.setdefault(match.group(2), int(match.group(1), 16))
    return result


def contract() -> dict[str, Any]:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(value.get("format")
            == "lisp65-c2-resident-island-two-record-contract-v1",
            "two-record contract format drift")
    require(value["container"] == {
        "data_only_flag": DATA_ONLY,
        "entry_bytes": R.ENTRY_SIZE,
        "header_bytes": R.HEADER_SIZE,
        "magic": "L65R",
        "new_product_emission": "version-2-only",
        "predecessor_version": 1,
        "version": VERSION,
        "version_policy":
            "strict-version-bound-no-feature-sniffing-no-dual-decoder",
    }, "L65R-v2 container contract drift")
    require(value["capacity"]["per_record_hard_cap_bytes"] == CAP
            and value["island_carrier_record"]["entry_offset"] == ENTRY_NONE
            and value["island_carrier_record"]["flags"]
                == R.FLAG_BOOT | DATA_ONLY
            and value["island_carrier_record"]["abi_version"] == ABI_NONE,
            "data-only carrier contract drift")
    return value


def record_semantics(row: dict[str, int]) -> None:
    require(row["flags"] & ~KNOWN_FLAGS_V2 == 0, "unknown v2 record flags")
    is_data = bool(row["flags"] & DATA_ONLY)
    require(1 <= row["file_size"] <= CAP, "record size outside hard cap")
    require(row["memory_size"] == row["file_size"] and row["bss_bytes"] == 0,
            "record has noncanonical memory/BSS size")
    if is_data:
        require(row["flags"] == R.FLAG_BOOT | DATA_ONLY,
                "data carrier is not boot-only")
        require(row["entry_offset"] == ENTRY_NONE
                and row["abi_version"] == ABI_NONE
                and row["capability_mask"] == 0,
                "data carrier claims execution")
        require(row["vma"] == DESTINATION,
                "data carrier destination drift")
    else:
        require(row["vma"] == COMMON_VMA,
                "executable record VMA drift")
        require(row["entry_offset"] < row["file_size"]
                and row["abi_version"] == R.ENTRY_ABI,
                "executable record entry/ABI drift")


def encode_record(row: dict[str, int]) -> bytes:
    record_semantics(row)
    return R.ENTRY.pack(
        row["id"], row["flags"], row["file_offset"], row["file_size"],
        row["vma"], row["memory_size"], row["entry_offset"],
        row["abi_version"], row["slice_build_id"], row["crc16"],
        row["bss_bytes"], row["capability_mask"], 0)


def build_model(records: list[dict[str, Any]], build_id: int) -> bytes:
    require([row["id"] for row in records] == list(range(len(records))),
            "record IDs are not dense")
    payload_offset = align(R.HEADER_SIZE + len(records) * R.ENTRY_SIZE)
    cursor = payload_offset
    entries: list[bytes] = []
    for row in records:
        cursor = align(cursor)
        row.update({
            "file_offset": cursor,
            "file_size": len(row["data"]),
            "memory_size": len(row["data"]),
            "slice_build_id": build_id,
            "crc16": R.crc16_ccitt_false(row["data"]),
            "bss_bytes": 0,
        })
        entries.append(encode_record(row))
        cursor += len(row["data"])
    require(cursor <= 65536, "two-record model exceeds boot store")
    directory = b"".join(entries)
    directory_crc = R.crc16_ccitt_false(directory)
    header = bytearray(R.HEADER.pack(
        R.MAGIC, VERSION, R.HEADER_SIZE, R.ENTRY_SIZE, len(records), 0,
        R.BANK, 0, build_id, R.HEADER_SIZE, payload_offset, cursor,
        directory_crc, 0, 0))
    struct.pack_into("<H", header, 26, R.crc16_ccitt_false(header))
    image = bytearray(cursor)
    image[:R.HEADER_SIZE] = header
    image[R.HEADER_SIZE:R.HEADER_SIZE + len(directory)] = directory
    for row in records:
        start = row["file_offset"]
        image[start:start + row["file_size"]] = row["data"]
    return bytes(image)


def decode_model(image: bytes, expected_build_id: int) -> list[dict[str, int]]:
    require(len(image) >= R.HEADER_SIZE, "truncated v2 header")
    header = list(R.HEADER.unpack_from(image))
    require(header[0] == R.MAGIC and header[1] == VERSION,
            "wrong L65R version/magic")
    require(header[2:5] == [R.HEADER_SIZE, R.ENTRY_SIZE, 10],
            "v2 header geometry drift")
    require(header[8] == expected_build_id and header[9] == R.HEADER_SIZE,
            "v2 build/directory binding drift")
    require(header[10] == 512 and header[11] == len(image),
            "v2 payload/image size drift")
    saved_header_crc = header[13]
    copy = bytearray(image[:R.HEADER_SIZE])
    struct.pack_into("<H", copy, 26, 0)
    require(R.crc16_ccitt_false(copy) == saved_header_crc,
            "v2 header CRC mismatch")
    directory = image[R.HEADER_SIZE:R.HEADER_SIZE + 10 * R.ENTRY_SIZE]
    require(R.crc16_ccitt_false(directory) == header[12],
            "v2 directory CRC mismatch")
    rows: list[dict[str, int]] = []
    cursor = header[10]
    keys = ("id", "flags", "file_offset", "file_size", "vma",
            "memory_size", "entry_offset", "abi_version",
            "slice_build_id", "crc16", "bss_bytes", "capability_mask",
            "reserved")
    for index in range(10):
        values = R.ENTRY.unpack_from(directory, index * R.ENTRY_SIZE)
        row = dict(zip(keys, values))
        require(row["id"] == index and row["reserved"] == 0,
                "v2 record ID/reserved drift")
        require(row["slice_build_id"] == expected_build_id,
                "v2 record generation drift")
        record_semantics(row)
        cursor = align(cursor)
        require(row["file_offset"] == cursor,
                "v2 noncanonical file offset")
        end = cursor + row["file_size"]
        require(end <= len(image), "v2 record bounds exceed image")
        require(R.crc16_ccitt_false(image[cursor:end]) == row["crc16"],
                "v2 record payload CRC mismatch")
        cursor = end
        rows.append(row)
    require(cursor == len(image), "v2 image has trailing bytes")
    return rows


def install_model(image: bytes, row: dict[str, int], generation: int,
                  *, active_generation: int | None = None,
                  corrupt_target: bool = False,
                  execute: bool = False,
                  nested_overlay_load: bool = False,
                  premature_ready: bool = False,
                  return_failure: bool = False) -> dict[str, Any]:
    destination = bytearray(row["file_size"])
    ready = False
    states = ["inactive"]
    try:
        require(active_generation in (None, generation),
                "stale carrier generation")
        require(row["slice_build_id"] == generation,
                "carrier record generation mismatch")
        record_semantics(row)
        require(row["flags"] & DATA_ONLY, "carrier kind mismatch")
        require(not execute, "data-only carrier execution rejected")
        require(not nested_overlay_load,
                "overlay-to-overlay load rejected")
        require(not premature_ready, "READY before destination proof rejected")
        states.append("carrier-record-authenticated")
        start = row["file_offset"]
        payload = image[start:start + row["file_size"]]
        require(len(payload) == row["file_size"], "carrier truncated")
        require(R.crc16_ccitt_false(payload) == row["crc16"],
                "carrier source CRC mismatch")
        states.append("carrier-payload-authenticated")
        destination[:] = payload
        states.append("dma-complete")
        if corrupt_target:
            destination[0] ^= 1
        require(R.crc16_ccitt_false(destination) == row["crc16"],
                "carrier destination CRC mismatch")
        states.append("destination-authenticated")
        ready = True
        states.append("ready-published-last")
        return {"status": "passed", "ready": ready, "states": states,
                "destination_sha256": hashlib.sha256(destination).hexdigest()}
    except ProbeError as error:
        destination[:] = b"\x00" * len(destination)
        ready = False
        if return_failure:
            return {"status": "rejected-fail-closed", "ready": ready,
                    "destination_wiped": not any(destination),
                    "states": states, "diagnostic": str(error)}
        raise


def mutations(image: bytes, rows: list[dict[str, int]], build_id: int) \
        -> dict[str, str]:
    carrier = rows[9]
    cases: dict[str, str] = {}

    def reject(name: str, operation: Any) -> None:
        try:
            operation()
        except (ProbeError, struct.error):
            cases[name] = "rejected-fail-closed"
            return
        raise ProbeError(f"two-record mutation escaped: {name}")

    reject("v1-header-with-v2-data-record",
           lambda: decode_model(bytes(image[:4] + bytes([1]) + image[5:]),
                                build_id))
    for name, patch in (
        ("data-flag-absent", {"flags": R.FLAG_BOOT}),
        ("unknown-data-flag", {"flags": R.FLAG_BOOT | DATA_ONLY | 0x10}),
        ("callable-data-entry", {"entry_offset": 0}),
        ("data-abi-one", {"abi_version": 1}),
        ("runtime-data-role", {"flags": R.FLAG_RUNTIME | DATA_ONLY}),
        ("wrong-destination", {"vma": DESTINATION + 1}),
        ("zero-length", {"file_size": 0, "memory_size": 0}),
        ("over-cap", {"file_size": CAP + 1, "memory_size": CAP + 1}),
    ):
        reject(name, lambda patch=patch: record_semantics({**carrier, **patch}))
    damaged = bytearray(image)
    damaged[carrier["file_offset"]] ^= 1
    reject("source-crc-mismatch", lambda: decode_model(bytes(damaged), build_id))
    reject("stale-generation", lambda: install_model(
        image, carrier, build_id, active_generation=build_id ^ 1))
    reject("execute-data-record", lambda: install_model(
        image, carrier, build_id, execute=True))
    reject("overlay-load-during-installer", lambda: install_model(
        image, carrier, build_id, nested_overlay_load=True))
    reject("target-crc-mismatch", lambda: install_model(
        image, carrier, build_id, corrupt_target=True))
    reject("premature-ready", lambda: install_model(
        image, carrier, build_id, premature_ready=True))
    reject("truncated-carrier", lambda: decode_model(image[:-1], build_id))
    require(len(cases) == 16, "two-record mutation matrix cardinality drift")
    return cases


def protect(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "two-record probe is one-shot")
    value = contract()
    require(sha(FIRST_RED) == FIRST_RED_SHA, "Slot-37 First Red drift")
    require(sha(SEED_ELF) == SEED_ELF_SHA and sha(FINAL_LTO) == FINAL_LTO_SHA,
            "two-record source evidence drift")
    PROFILE.configure(P)
    island = ISLAND._extract(
        SEED_ELF, P.TOOLCHAIN / "llvm-nm", P.TOOLCHAIN / "llvm-objcopy")
    installer = extract_section(FINAL_LTO, ".lisp65_rt_island_00")
    baseline = value["probe_baseline"]
    require(len(island) == baseline["island_image_bytes"] == 1781
            and hashlib.sha256(island).hexdigest()
                == baseline["island_image_sha256"]
            and ISLAND.crc16(island) == baseline["island_crc16"] == 0x4C63,
            "real Island image identity drift")
    require(len(installer) == baseline["installer_code_bytes"] == 102,
            "real installer code size drift")

    syms = symbols(SEED_ELF)
    records: list[dict[str, Any]] = []
    for spec in P.BOOT_SLICE_SPECS[:8]:
        fields = spec.split(":")
        data = extract_section(SEED_ELF, fields[2])
        start, end, entry = (syms[fields[index]] for index in (3, 4, 5))
        require(start == COMMON_VMA and end - start == len(data),
                f"real boot slice span drift: {fields[1]}")
        records.append({
            "id": int(fields[0]), "name": fields[1], "data": data,
            "flags": flags(fields[6]), "vma": start,
            "entry_offset": entry - start,
            "abi_version": int(fields[7]),
            "capability_mask": int(fields[8]),
        })
    records.extend((
        {"id": 8, "name": "resident-island-installer", "data": installer,
         "flags": R.FLAG_BOOT, "vma": COMMON_VMA, "entry_offset": 0,
         "abi_version": R.ENTRY_ABI, "capability_mask": 0},
        {"id": 9, "name": "resident-island-image", "data": island,
         "flags": R.FLAG_BOOT | DATA_ONLY, "vma": DESTINATION,
         "entry_offset": ENTRY_NONE, "abi_version": ABI_NONE,
         "capability_mask": 0},
    ))
    build_id = int(sha(RESOLVED)[:8], 16)
    image = build_model(records, build_id)
    parsed = decode_model(image, build_id)
    carrier = parsed[9]
    success = install_model(image, carrier, build_id)
    require(success["ready"]
            and success["destination_sha256"] == hashlib.sha256(island).hexdigest(),
            "two-record success path did not reproduce the real Island")
    failure_cleanup = install_model(
        image, carrier, build_id, corrupt_target=True, return_failure=True)
    require(failure_cleanup["status"] == "rejected-fail-closed"
            and not failure_cleanup["ready"]
            and failure_cleanup["destination_wiped"],
            "two-record failure did not wipe destination and clear READY")
    matrix = mutations(image, parsed, build_id)

    sizes = map_sections()
    require(sizes[".lisp65_rt_island_00"] == 1883,
            "failed final combined carrier size drift")
    require(len(image) == 14325 and carrier["file_offset"] == 0x3100,
            "two-record boot-pack geometry drift")
    require(len(records) == 10 and all(row["file_size"] <= CAP for row in parsed),
            "two-record per-record cap red")
    OUT.mkdir(parents=True)
    (OUT / "island-carrier.bin").write_bytes(island)
    (OUT / "l65r-v2-two-record-boot-model.bin").write_bytes(image)
    report = {
        "format": "lisp65-c2-resident-island-two-record-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-contract-capacity-no-product-link",
        "contract": bind(CONTRACT),
        "sources": {
            "slot37_first_red": bind(FIRST_RED),
            "seed_elf": bind(SEED_ELF),
            "failed_final_lto": bind(FINAL_LTO),
            "failed_final_map": bind(FINAL_MAP),
            "resolved_profile": bind(RESOLVED),
            "canonical_profile": PROFILE.receipt_identity(),
        },
        "real_island": {
            "bytes": len(island), "crc16": ISLAND.crc16(island),
            "sha256": hashlib.sha256(island).hexdigest(),
            "placeholder_used": False,
            "source_section": ".lisp65_resident_island",
        },
        "records": {
            "installer": {
                "id": 8, "bytes": len(installer),
                "headroom_bytes": CAP - len(installer),
                "data_only": False, "entry_offset": 0, "abi_version": 1,
                "source_section_sha256": hashlib.sha256(installer).hexdigest(),
                "claim_limit": "relocatable final-LTO code size, not executable bytes",
            },
            "carrier": {
                "id": 9, "bytes": len(island),
                "headroom_bytes": CAP - len(island),
                "data_only": True, "entry_offset": ENTRY_NONE,
                "abi_version": ABI_NONE, "destination": DESTINATION,
                "file_offset": carrier["file_offset"],
                "physical_source": BOOT_BASE + carrier["file_offset"],
                "crc16": carrier["crc16"],
            },
        },
        "boot_store": {
            "record_count_before": 9, "record_count_after": 10,
            "payload_offset_before": 512, "payload_offset_after": 512,
            "illegal_combined_model_bytes": 14171,
            "two_record_model_bytes": len(image),
            "split_alignment_cost_bytes": len(image) - 14171,
            "headroom_bytes": 65536 - len(image),
            "all_ten_records_under_1792": True,
        },
        "container_format": {
            "magic": "L65R", "version": VERSION,
            "header_bytes": R.HEADER_SIZE, "entry_bytes": R.ENTRY_SIZE,
            "data_only_flag": DATA_ONLY,
            "strict_v2_only_product": True,
            "dual_decoder": False,
        },
        "publication_model": success,
        "failure_cleanup_model": failure_cleanup,
        "negative_matrix": matrix,
        "structural_rules": {
            "carrier_is_not_callable": True,
            "no_overlay_calls_overlay": True,
            "source_and_destination_crc_equal": True,
            "ready_is_last_state": success["states"][-1]
                == "ready-published-last",
            "v1_generation_invalidated_before_v2_restaging": True,
        },
        "capacity_not_measured": {
            "resident_product_bytes": "not-run",
            "bank0": "not-run", "bss": "not-run", "island": "not-run",
            "e000": "not-run", "session_store": "unchanged-by-contract-model",
        },
        "execution_accounting": {
            "real_section_extractions": 10,
            "compiler_runs": 0, "linker_runs": 0,
            "product_links": 0, "hardware_runs": 0,
        },
        "claim_limit": (
            "The exact real Island payload, L65R-v2 record semantics, boot-pack "
            "geometry and publish-last host model are proven. Target decoder, "
            "resident deltas, product link and hardware remain not-run."),
        "next_gate": (
            "separate review of L65R-v2 product implementation and a product-shaped "
            "capacity/placement probe before any Link 33"),
    }
    report_path = OUT / "two-record-contract-probe.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    receipt = {**report, "artifacts": {
        "real_carrier": bind(OUT / "island-carrier.bin"),
        "v2_boot_model": bind(OUT / "l65r-v2-two-record-boot-model.bin"),
        "report": bind(report_path),
    }}
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    protect(OUT)
    return receipt


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "two-record probe receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-contract-capacity-no-product-link",
            "two-record probe is not green")
    for row in value["artifacts"].values():
        path = ROOT / row["path"]
        require(path.is_file() and sha(path) == row["sha256"],
                f"two-record artifact drift: {path}")
    require(sha(FIRST_RED) == FIRST_RED_SHA, "rollback First Red drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = check() if args.action == "check" else run_probe()
    print("c2-resident-island-two-record-probe: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, ISLAND.IslandError, R.OverlayBankError, OSError,
            ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, struct.error) as error:
        print(f"c2-resident-island-two-record-probe: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
