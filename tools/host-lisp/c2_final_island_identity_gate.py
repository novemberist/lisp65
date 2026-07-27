#!/usr/bin/env python3
"""Single-truth gate for the final L65R Resident-Island carrier.

The prerequisite seed link is deliberately not an identity source.  Product
gates compare the emitted final carrier record and payload with the actual
final ELF section extracted from a disposable copy.
"""

from __future__ import annotations

import argparse
from binascii import crc_hqx
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/vm_runtime_overlay.c"
OBJCOPY = ROOT / "tools/llvm-mos/bin/llvm-objcopy"
HEADER_BYTES = 32
RECORD_BYTES = 32
RECORD_CRC_OFFSET = 22
HARD_MAX = 1792


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def u16(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def put16(data: bytearray, offset: int, value: int) -> None:
    data[offset:offset + 2] = value.to_bytes(2, "little")


def crc16(data: bytes | bytearray) -> int:
    return crc_hqx(bytes(data), 0xffff)


def record_crc(record: bytes | bytearray) -> int:
    value = bytearray(record)
    require(len(value) == RECORD_BYTES, "carrier record width drift")
    value[RECORD_CRC_OFFSET:RECORD_CRC_OFFSET + 2] = b"\0\0"
    return crc16(value)


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise GateError(f"unterminated function: {signature}")


def source_contract_text(source: str) -> dict[str, bool]:
    install = function_body(source, "vm_resident_island_install(void *opaque)")
    finalize = function_body(source, "vm_resident_island_finalize(void *opaque)")
    checks = {
        "record_length_is_not_compared_with_seed":
            "file_len != LISP65_RESIDENT_ISLAND_LENGTH" not in install,
        "record_crc_is_not_compared_with_seed":
            "payload_crc != LISP65_RESIDENT_ISLAND_CRC16" not in install,
        "finalizer_has_no_seed_identity":
            "LISP65_RESIDENT_ISLAND_LENGTH" not in finalize
            and "LISP65_RESIDENT_ISLAND_CRC16" not in finalize,
        "phase0_publishes_offset": "rtov_batch_entry = file_off;" in install,
        "phase0_publishes_crc": "rtov_batch_crc = payload_crc;" in install,
        "phase0_publishes_length":
            "RTOV_INSTALL_CONTEXT = (void *)(uintptr_t)file_len;" in install,
        "phase1_consumes_offset":
            "uint16_t file_off = rtov_batch_entry;" in finalize,
        "phase1_consumes_crc":
            "uint16_t payload_crc = rtov_batch_crc;" in finalize,
        "phase1_consumes_length":
            ("uint16_t file_len = (uint16_t)(uintptr_t)"
             "RTOV_INSTALL_CONTEXT;") in finalize,
        "phase1_clears_offset": "rtov_batch_entry = 0;" in finalize,
        "phase1_clears_crc": "rtov_batch_crc = 0;" in finalize,
        "phase1_clears_length": "RTOV_INSTALL_CONTEXT = 0;" in finalize,
        "phase1_rejects_empty_offset": "if (!file_off || !file_len" in finalize,
        "phase1_uses_record_length":
            "RTOV_ISLAND_TARGET, file_len, payload_crc" in finalize,
        "phase1_uses_record_crc":
            "file_len) == payload_crc" in finalize,
    }
    clear = finalize.find("rtov_batch_entry = 0;")
    read = finalize.find("rtov_read(file_off")
    checks["handoff_retired_before_destination_read"] = (
        clear >= 0 and read >= 0 and clear < read)
    require(all(checks.values()), "final-Island source contract red: " +
            str([name for name, passed in checks.items() if not passed]))
    return checks


def source_gate(path: Path = RUNTIME) -> dict[str, Any]:
    checks = source_contract_text(path.read_text(encoding="utf-8"))
    return {"status": "passed-final-carrier-runtime-single-truth-source",
            "checks": checks, "source": bind(path)}


def extract_final_island(elf: Path) -> bytes:
    require(elf.is_file(), f"ELF absent: {elf}")
    with tempfile.TemporaryDirectory(prefix="c2-final-island-") as directory:
        directory_path = Path(directory)
        disposable = directory_path / "disposable.elf"
        output = directory_path / "resident-island.bin"
        shutil.copy2(elf, disposable)
        subprocess.run([
            str(OBJCOPY),
            f"--dump-section=.lisp65_resident_island={output}",
            str(disposable),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        require(output.is_file(), "final Island section extraction absent")
        return output.read_bytes()


def carrier_row(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("slices")
    require(isinstance(rows, list), "Boot manifest has no slice list")
    matches = [row for row in rows if isinstance(row, dict)
               and row.get("name") == "resident-island-image"]
    require(len(matches) == 1, "final Island carrier is not unique")
    return matches[0]


def raw_record(image: bytes | bytearray, slot: int) -> bytes:
    start = HEADER_BYTES + slot * RECORD_BYTES
    end = start + RECORD_BYTES
    require(0 <= start < end <= len(image), "carrier record outside image")
    return bytes(image[start:end])


def record_values(record: bytes) -> dict[str, int]:
    require(len(record) == RECORD_BYTES, "carrier record width drift")
    return {
        "slot": u16(record, 0), "flags": u16(record, 2),
        "file_offset": u16(record, 4), "file_length": u16(record, 6),
        "vma": u16(record, 8), "memory_length": u16(record, 10),
        "entry_offset": u16(record, 12), "abi": u16(record, 14),
        "build_id": int.from_bytes(record[16:20], "little"),
        "payload_crc16": u16(record, 20),
        "record_crc16": u16(record, 22),
    }


def validate_identity(image: bytes | bytearray, row: dict[str, Any],
                      section: bytes) -> dict[str, Any]:
    slot = int(row["id"])
    record = raw_record(image, slot)
    values = record_values(record)
    start = values["file_offset"]
    end = start + values["file_length"]
    require(values["slot"] == slot and values["flags"] == 9,
            "carrier record identity/flags drift")
    require(values["vma"] == 0x1800
            and values["memory_length"] == values["file_length"]
            and values["entry_offset"] == 0xffff and values["abi"] == 0,
            "carrier DATA_ONLY geometry drift")
    require(record[24:] == bytes(8), "carrier reserved tail is nonzero")
    require(values["record_crc16"] != 0
            and values["record_crc16"] == record_crc(record),
            "carrier record self-CRC drift")
    require(0 < values["file_length"] <= HARD_MAX
            and end <= len(image), "carrier payload bounds drift")
    payload = bytes(image[start:end])
    require(values["file_length"] == len(section),
            "carrier record length differs from final Island section")
    require(values["payload_crc16"] == crc16(payload) == crc16(section),
            "carrier record CRC differs from final Island section")
    require(payload == section, "carrier payload differs from final section")
    digest = sha_bytes(section)
    require(int(row["file_offset"]) == start
            and int(row["file_size"]) == len(section)
            and int(row["memory_size"]) == len(section)
            and int(row["crc16"]) == values["payload_crc16"]
            and row["sha256"] == digest,
            "carrier manifest differs from record/final section")
    return {"slot": slot, **values, "section_bytes": len(section),
            "section_crc16": values["payload_crc16"],
            "section_sha256": digest}


def handoff_consume(offset: int, length: int, crc: int,
                    *, already_consumed: bool = False) -> tuple[int, int, int]:
    if already_consumed or not offset or not length or length > HARD_MAX \
            or offset & 255:
        raise GateError("invalid final-Island phase handoff")
    return offset, length, crc


def mutation_gate(source: str, image: bytes, row: dict[str, Any],
                  section: bytes) -> dict[str, str]:
    cases: dict[str, str] = {}

    def rejected(name: str, operation: Any) -> None:
        try:
            operation()
        except GateError:
            cases[name] = "rejected-fail-closed"
        else:
            raise GateError(f"final-Island gate accepted mutation: {name}")

    def changed_record(field_offset: int, value: int) -> bytearray:
        changed = bytearray(image)
        record_at = HEADER_BYTES + int(row["id"]) * RECORD_BYTES
        put16(changed, record_at + field_offset, value)
        record = bytearray(changed[record_at:record_at + RECORD_BYTES])
        put16(record, RECORD_CRC_OFFSET, record_crc(record))
        changed[record_at:record_at + RECORD_BYTES] = record
        return changed

    rejected("record-length", lambda: validate_identity(
        changed_record(6, len(section) - 1), row, section))
    rejected("record-payload-crc", lambda: validate_identity(
        changed_record(20, crc16(section) ^ 1), row, section))
    payload_mutant = bytearray(image)
    payload_mutant[int(row["file_offset"])] ^= 1
    rejected("carrier-payload", lambda: validate_identity(
        payload_mutant, row, section))
    section_mutant = bytearray(section)
    section_mutant[-1] ^= 1
    rejected("final-section", lambda: validate_identity(
        image, row, bytes(section_mutant)))
    manifest_mutant = copy.deepcopy(row)
    manifest_mutant["sha256"] = "0" * 64
    rejected("manifest-sha", lambda: validate_identity(
        image, manifest_mutant, section))

    rejected("source-seed-crc", lambda: source_contract_text(
        source.replace(
            "(end < file_off || end > frame->image_limit)))",
            ("(end < file_off || end > frame->image_limit)) ||\n"
             "            payload_crc != LISP65_RESIDENT_ISLAND_CRC16)"),
            1)))
    rejected("source-missing-length-handoff", lambda: source_contract_text(
        source.replace(
            "RTOV_INSTALL_CONTEXT = (void *)(uintptr_t)file_len;", "", 1)))
    rejected("source-seed-finalizer", lambda: source_contract_text(
        source.replace("RTOV_ISLAND_TARGET, file_len, payload_crc",
                       ("RTOV_ISLAND_TARGET, LISP65_RESIDENT_ISLAND_LENGTH, "
                        "LISP65_RESIDENT_ISLAND_CRC16"), 1)))
    rejected("zero-handoff", lambda: handoff_consume(0, 0, 0))
    rejected("partial-handoff", lambda: handoff_consume(0, len(section),
                                                         crc16(section)))
    rejected("replayed-handoff", lambda: handoff_consume(
        int(row["file_offset"]), len(section), crc16(section),
        already_consumed=True))
    require(len(cases) == 11 and
            set(cases.values()) == {"rejected-fail-closed"},
            "final-Island mutation matrix incomplete")
    return cases


def audit(elf: Path, image_path: Path, manifest_path: Path,
          runtime_source: Path, output: Path | None = None) -> dict[str, Any]:
    elf = elf.resolve()
    image_path = image_path.resolve()
    manifest_path = manifest_path.resolve()
    runtime_source = runtime_source.resolve()
    if output is not None:
        output = output.resolve()
    source = runtime_source.read_text(encoding="utf-8")
    source_result = source_gate(runtime_source)
    image = image_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = carrier_row(manifest)
    section = extract_final_island(elf)
    identity = validate_identity(image, row, section)
    mutations = mutation_gate(source, image, row, section)
    value = {
        "format": "lisp65-c2-final-island-single-runtime-identity-gate-v1",
        "status": "passed-final-record-equals-final-island-single-truth",
        "source_contract": source_result,
        "identity": identity,
        "mutation_matrix": mutations,
        "mutation_cases": len(mutations),
        "seed_runtime_comparisons": 0,
        "artifacts": {"elf": bind(elf), "boot_family": bind(image_path),
                      "boot_manifest": bind(manifest_path)},
        "extraction_rule": (
            "actual final section extracted only from a disposable ELF copy"),
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    return value


def check_source() -> dict[str, Any]:
    source = RUNTIME.read_text(encoding="utf-8")
    result = source_gate()
    # Source-only mutations close the check-source half without needing a
    # product artifact. Product-shaped gates run the full eleven cases.
    for name, mutant in {
        "seed-crc": source.replace(
            "(end < file_off || end > frame->image_limit)))",
            ("(end < file_off || end > frame->image_limit)) ||\n"
             "            payload_crc != LISP65_RESIDENT_ISLAND_CRC16)"), 1),
        "missing-length": source.replace(
            "RTOV_INSTALL_CONTEXT = (void *)(uintptr_t)file_len;", "", 1),
        "seed-finalizer": source.replace(
            "RTOV_ISLAND_TARGET, file_len, payload_crc",
            ("RTOV_ISLAND_TARGET, LISP65_RESIDENT_ISLAND_LENGTH, "
             "LISP65_RESIDENT_ISLAND_CRC16"), 1),
    }.items():
        try:
            source_contract_text(mutant)
        except GateError:
            continue
        raise GateError(f"source contract accepted mutation: {name}")
    result["source_mutations_rejected"] = 3
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-source")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--elf", type=Path, required=True)
    audit_parser.add_argument("--image", type=Path, required=True)
    audit_parser.add_argument("--manifest", type=Path, required=True)
    audit_parser.add_argument("--runtime-source", type=Path, default=RUNTIME)
    audit_parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "check-source":
        value = check_source()
    else:
        value = audit(args.elf, args.image, args.manifest,
                      args.runtime_source, args.out)
    print("c2-final-island-identity: " + value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
