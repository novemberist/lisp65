#!/usr/bin/env python3
"""Model both authorized L65S-v4 layouts and bind their reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-l65s-v4-probe-contract.json"
SHELF_CONTRACT = ROOT / "config/v11-attic-library-shelf.json"
AUDIT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-shelf-metadata-audit-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l65s-v4-layout-model-receipt.json"
)
MAGIC = b"L65S"
VERSION = 4
HEADER_BYTES = 32
RECORD_BYTES = 32
PAYLOAD_OFF = 192
FLAG_SPLIT = 1
ENVELOPE = 512 * 1024
FUTURE_RECORDS = 4


class ModelError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def p24(value: int) -> bytes:
    require(0 <= value <= 0x6FFFFF, f"u24 Attic-relative value out of range: {value}")
    return bytes((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))


def u24(data: bytes, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def header(flags: int, count: int, total: int, catalog: bytes, build_id: int) -> bytes:
    value = bytearray(HEADER_BYTES)
    value[:8] = MAGIC + bytes((VERSION, HEADER_BYTES, RECORD_BYTES, count))
    struct.pack_into("<H", value, 8, HEADER_BYTES)
    value[10:13] = p24(PAYLOAD_OFF)
    value[13:16] = p24(total)
    struct.pack_into("<H", value, 16, len(catalog))
    struct.pack_into("<I", value, 18, zlib.crc32(catalog) & 0xFFFFFFFF)
    struct.pack_into("<I", value, 22, build_id)
    struct.pack_into("<H", value, 26, flags)
    return bytes(value)


def inputs() -> list[dict[str, Any]]:
    shelf = load(SHELF_CONTRACT)
    rows = []
    for item in shelf["containers"]:
        manifest_path = ROOT / item["manifest"]
        manifest = load(manifest_path)
        image_path = ROOT / manifest["external_image"]["path"]
        data = image_path.read_bytes()
        require(len(data) >= 4, f"short container: {item['key']}")
        code = struct.unpack_from("<H", data, 0)[0]
        metadata = struct.unpack_from("<H", data, 2)[0]
        require(len(data) == 4 + code + metadata, f"container length drift: {item['key']}")
        rows.append({
            "key": item["key"],
            "data": data,
            "container": bind(image_path),
            "code_region": data[:4 + code],
            "metadata_region": data[4 + code:],
        })
    require([row["key"] for row in rows] == ["ide", "idex", "m65d", "buffer", "lcc"],
            "canonical shelf order drift")
    return rows


def name(key: str) -> bytes:
    raw = key.encode("ascii")
    require(0 < len(raw) < 8, f"invalid key: {key}")
    return (raw + b"\0").ljust(8, b"\0")


def widening(rows: list[dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]]]:
    payload = bytearray()
    catalog = bytearray()
    public = []
    offset = PAYLOAD_OFF
    for row in rows:
        data = row["data"]
        item = bytearray(RECORD_BYTES)
        item[:8] = name(row["key"])
        item[8:11] = p24(offset)
        struct.pack_into("<H", item, 11, len(data))
        struct.pack_into("<I", item, 13, zlib.crc32(data) & 0xFFFFFFFF)
        item[17:29] = hashlib.sha256(data).digest()[:12]
        catalog.extend(item)
        payload.extend(data)
        public.append({"key": row["key"], "container_off": offset,
                       "container_bytes": len(data), "container_sha256": sha(data)})
        offset += len(data)
    identity = hashlib.sha256(bytes(catalog) + bytes(payload)).digest()
    result = header(0, len(rows), offset, bytes(catalog),
                    int.from_bytes(identity[:4], "little")) + bytes(catalog) + bytes(payload)
    require(len(result) == offset, "widening layout did not close")
    return result, public


def split(rows: list[dict[str, Any]]) -> tuple[bytes, list[dict[str, Any]]]:
    code_payload = b"".join(row["code_region"] for row in rows)
    metadata_payload = b"".join(row["metadata_region"] for row in rows)
    code_cursor = PAYLOAD_OFF
    metadata_cursor = PAYLOAD_OFF + len(code_payload)
    catalog = bytearray()
    public = []
    for row in rows:
        code = row["code_region"]
        metadata = row["metadata_region"]
        item = bytearray(RECORD_BYTES)
        item[:8] = name(row["key"])
        item[8:11] = p24(code_cursor)
        struct.pack_into("<H", item, 11, len(code))
        item[13:16] = p24(metadata_cursor)
        struct.pack_into("<H", item, 16, len(metadata))
        struct.pack_into("<I", item, 18, zlib.crc32(code) & 0xFFFFFFFF)
        struct.pack_into("<I", item, 22, zlib.crc32(metadata) & 0xFFFFFFFF)
        struct.pack_into("<I", item, 26, zlib.crc32(row["data"]) & 0xFFFFFFFF)
        item[30] = FLAG_SPLIT
        catalog.extend(item)
        reconstructed = code + metadata
        require(reconstructed == row["data"], f"split reconstruction drift: {row['key']}")
        public.append({
            "key": row["key"],
            "code_region_off": code_cursor,
            "code_region_bytes": len(code),
            "metadata_region_off": metadata_cursor,
            "metadata_region_bytes": len(metadata),
            "reconstructed_container_sha256": sha(reconstructed),
        })
        code_cursor += len(code)
        metadata_cursor += len(metadata)
    payload = code_payload + metadata_payload
    total = PAYLOAD_OFF + len(payload)
    identity = hashlib.sha256(bytes(catalog) + payload).digest()
    result = header(FLAG_SPLIT, len(rows), total, bytes(catalog),
                    int.from_bytes(identity[:4], "little")) + bytes(catalog) + payload
    require(len(result) == total, "split layout did not close")
    return result, public


def verify_split(image: bytes, rows: list[dict[str, Any]]) -> None:
    require(image[:4] == MAGIC and image[4] == VERSION and image[26] == FLAG_SPLIT,
            "split header drift")
    count = image[7]
    require(count == len(rows), "split count drift")
    require(u24(image, 13) == len(image), "split total drift")
    catalog = image[HEADER_BYTES:HEADER_BYTES + count * RECORD_BYTES]
    require(zlib.crc32(catalog) & 0xFFFFFFFF == struct.unpack_from("<I", image, 18)[0],
            "split catalog CRC drift")
    for index, row in enumerate(rows):
        item = catalog[index * RECORD_BYTES:(index + 1) * RECORD_BYTES]
        code_off, code_len = u24(item, 8), struct.unpack_from("<H", item, 11)[0]
        metadata_off, metadata_len = u24(item, 13), struct.unpack_from("<H", item, 16)[0]
        code = image[code_off:code_off + code_len]
        metadata = image[metadata_off:metadata_off + metadata_len]
        require(zlib.crc32(code) & 0xFFFFFFFF == struct.unpack_from("<I", item, 18)[0],
                f"code CRC drift: {row['key']}")
        require(zlib.crc32(metadata) & 0xFFFFFFFF == struct.unpack_from("<I", item, 22)[0],
                f"metadata CRC drift: {row['key']}")
        reconstructed = code + metadata
        require(zlib.crc32(reconstructed) & 0xFFFFFFFF == struct.unpack_from("<I", item, 26)[0],
                f"container CRC drift: {row['key']}")
        require(reconstructed == row["data"], f"container reconstruction drift: {row['key']}")


def collect(out_dir: Path) -> dict[str, Any]:
    contract = load(CONTRACT)
    audit = load(AUDIT)
    require(audit["status"] == "audit-confirmed-input-to-one-v4-probe",
            "metadata audit is not bound for the probe")
    require(audit["totals"]["metadata"] == 36260
            and audit["totals"]["literal_machinery"] == 27744,
            "metadata audit totals drift")
    rows = inputs()
    pure, pure_rows = widening(rows)
    split_image, split_rows = split(rows)
    verify_split(split_image, rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    pure_path = out_dir / "library-shelf-v4-widening.bin"
    split_path = out_dir / "library-shelf-v4-split.bin"
    pure_path.write_bytes(pure)
    split_path.write_bytes(split_image)

    def projection(current: int) -> dict[str, int]:
        reserved = FUTURE_RECORDS * RECORD_BYTES
        return {
            "probe_envelope_bytes": ENVELOPE,
            "current_bytes": current,
            "future_record_bytes_reserved": reserved,
            "remaining_combined_future_region_bytes": ENVELOPE - current - reserved,
        }

    receipt = {
        "format": "lisp65-v11-l65s-v4-layout-model-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "both-layouts-modeled-split-selected-for-one-real-link",
        "claim_limit": (
            "This receipt proves format arithmetic, exact reconstruction of the five "
            "current L65M containers and a bounded aggregate Wave-3 envelope. It does "
            "not claim the four future modules have been built or that any product "
            "capacity gate passes."
        ),
        "bindings": {
            "contract": bind(CONTRACT),
            "metadata_audit": bind(AUDIT),
            "shelf_contract": bind(SHELF_CONTRACT),
        },
        "confirmed_audit": {
            "metadata_bytes": 36260,
            "literal_machinery_bytes": 27744,
            "raw_string_pool_bytes": 5347,
            "string_regions_with_alignment_bytes": 5350,
            "metadata_percent_of_payload_region": 55.634,
            "metadata_percent_of_whole_shelf": 55.4706,
        },
        "variants": {
            "catalog-widening-only": {
                "artifact": bind(pure_path),
                "rows": pure_rows,
                "projection": projection(len(pure)),
                "assessment": "Smallest decoder change; reuses only the u24 staging address in C2.0.",
            },
            "catalog-widening-plus-metadata-regions": {
                "artifact": bind(split_path),
                "rows": split_rows,
                "projection": projection(len(split_image)),
                "assessment": (
                    "Same reset-persistent artifact and exact L65M reconstruction, but "
                    "also establishes C2.0's immutable-code/load-time-metadata boundary."
                ),
                "selected_for_real_link": True,
            },
        },
        "side_file_assessment": {
            "d81_only": "rejected: not available after the documented single disk swap",
            "second_attic_artifact": "possible but adds a second boot identity and preload contract; not selected",
            "same_shelf_regions": "selected: reset-persistent and identity-bound by one shelf manifest",
        },
        "wave3_projection": {
            "roles_reserved": contract["wave3_projection"]["roles"],
            "meaning": (
                "The exact remaining value is a combined payload/region budget for the "
                "four roles, not a claim that any individual unbuilt module fits."
            ),
        },
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="l65s-v4-model-", dir=ROOT / "build") as raw:
        first = collect(Path(raw) / "first")
        first_receipt = RECEIPT.read_bytes()
        second = collect(Path(raw) / "second")
        require(first["confirmed_audit"] == second["confirmed_audit"], "model result drift")
        # Paths differ between temporary runs; bind the selected image contents directly.
        first_image = Path(raw) / "first/library-shelf-v4-split.bin"
        second_image = Path(raw) / "second/library-shelf-v4-split.bin"
        require(first_image.read_bytes() == second_image.read_bytes(), "split model is nondeterministic")
        require(first_receipt != b"", "empty receipt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    parser.add_argument("--out-dir", type=Path,
                        default=ROOT / "build/probes/v11-l65s-v4/model")
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
    result = collect(args.out_dir)
    if args.command == "check":
        recorded = load(RECEIPT)
        require(recorded == result, "recorded v4 model receipt drift")
    selected = result["variants"]["catalog-widening-plus-metadata-regions"]
    print("v11-l65s-v4-model: PASS "
          f"split={selected['artifact']['bytes']} "
          f"future={selected['projection']['remaining_combined_future_region_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
