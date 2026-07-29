#!/usr/bin/env python3
"""Prove the bounded C2 session-extension contract without product changes.

The proof deliberately consumes a real L65M compiler artifact only as an
oracle input.  It reconstructs the compiler manifest, feeds that manifest and
all six product manifests through the one existing C2I-v2 emitter, emits a
one-record L65S-v4 extension, and models its atomic append into C2D-v3.
Neither this tool nor its generated fixtures are part of the product closure.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import inspect
import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_gc_root_single_source as G  # noqa: E402
import l65m_contract as L  # noqa: E402


CONTRACT = ROOT / "config/c2-session-extension-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.1-session-extension-contract.md"
GAP_CONTRACT = ROOT / "config/c2-dynamic-code-gap-proposal.json"
GAP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-dynamic-code-gap-receipt.json"
)
FULL_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-full-emission-receipt.json"
)
ROOT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-gc-root-single-source-receipt.json"
)
LEGACY_INPUT = ROOT / "build/equivalence/fasl-test.bin"
BUILD = ROOT / "build/c2.1/session-extension"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-session-extension-probe-receipt.json"
)

PROBE_BUILD_ID = 0xC2020001
SESSION_GENERATION = 1
SESSION_ATTIC_BYTES = 1024 * 1024
SESSION_ATTIC_BASE = 0x08400000
PRODUCT_SHELF_BASE = 0x08100000

C2D_HEADER_BYTES = 48
C2D_IMAGE_BYTES = 32
C2D_ENTRY_BYTES = 10
C2D_IMAGE_CAPACITY = 64
C2D_ENTRY_CAPACITY = 2048
C2D_RESOLUTION_CAPACITY = 4096
C2D_ROOT_CAPACITY = 1536
C2D_IMAGES_OFFSET = 48
C2D_ENTRIES_OFFSET = 2096
C2D_RESOLUTIONS_OFFSET = 22576
C2D_ROOTS_OFFSET = 30768
C2D_TOTAL_BYTES = 33840
C2D_REGION_BYTES = 50816
ROOT_KINDS = {F.K_STRING, F.K_PAIR}


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha(data),
    }


def artifact(path: Path, data: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha(data),
    }


def u16(data: bytes | bytearray, at: int) -> int:
    require(0 <= at <= len(data) - 2, "truncated u16")
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    require(0 <= at <= len(data) - 3, "truncated u24")
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def p24(value: int) -> bytes:
    require(0 <= value <= 0xFFFFFF, "u24 overflow")
    return bytes((value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF))


def c_string(pool: bytes, offset: int) -> str:
    require(0 <= offset < len(pool), "legacy string offset outside pool")
    end = pool.find(b"\0", offset)
    require(end >= 0, "unterminated legacy string")
    return pool[offset:end].decode("utf-8")


def legacy_manifest(image: bytes, key: str) -> tuple[dict[str, Any], bytes]:
    """Translate a validated L65M oracle into the legacy manifest vocabulary.

    This is not the candidate emitter.  It extracts the compiler's semantic
    input so the already-authorized C2 emitter can be the sole output path.
    """
    # The checked-in compiler-equivalence oracle predates the product-profile
    # STRICT_ARITY gate.  It is authoritative here for the real emitter graph
    # and byte layout, not for the already-separate ABI-profile proof.
    summary = L.validate_image(image)
    blob_len, metadata_len = u16(image, 0), u16(image, 2)
    require(4 + blob_len + metadata_len == len(image), "legacy length equation")
    blob = image[4:4 + blob_len]
    metadata = image[4 + blob_len:]
    require(metadata[:4] == b"L65M", "legacy oracle magic")
    entry_count = u16(metadata, 16)
    index_count = u16(metadata, 18)
    node_count = u16(metadata, 20)
    patch_count = u16(metadata, 22)
    entries_off = u16(metadata, 24)
    index_off = u16(metadata, 26)
    nodes_off = u16(metadata, 28)
    patches_off = u16(metadata, 30)
    strings_off = u16(metadata, 32)
    strings_bytes = u16(metadata, 34)
    strings = metadata[strings_off:strings_off + strings_bytes]
    require(index_count == 0, "real compiler oracle unexpectedly uses aggregate index")

    patches: list[dict[str, int]] = []
    node_order: list[int] = []
    for ordinal in range(patch_count):
        at = patches_off + ordinal * 4
        blob_offset, node = u16(metadata, at), u16(metadata, at + 2)
        patches.append({"blob_offset": blob_offset, "node": node})
        node_order.append(node)
    require(sorted(node_order) == list(range(node_count)),
            "compiler patch order is not a complete literal permutation")

    nodes: list[dict[str, Any]] = []
    for ordinal in range(node_count):
        at = nodes_off + ordinal * 10
        kind = metadata[at]
        value = struct.unpack_from("<h", metadata, at + 2)[0]
        first, count, name_off = (u16(metadata, at + x) for x in (4, 6, 8))
        row: dict[str, Any] = {
            "kind": kind,
            "value": value,
            "first": first,
            "count": count,
        }
        if kind in (4, 7):
            row["name"] = c_string(strings, name_off)
        nodes.append(row)

    entries: list[dict[str, Any]] = []
    literal_cursor = 0
    code_cursor = 0
    for ordinal in range(entry_count):
        at = entries_off + ordinal * 8
        name_off = u16(metadata, at)
        bank, flags = metadata[at + 2], metadata[at + 3]
        code_offset, code_length = u16(metadata, at + 4), u16(metadata, at + 6)
        require(bank == 0 and code_offset == code_cursor, "legacy entry layout drift")
        code = blob[code_offset:code_offset + code_length]
        literal_count = code[6]
        entry = {
            "blob_offset": code_offset,
            "code_flags": code[3],
            "flags": flags,
            "kind": "macro" if flags & 1 else "function",
            "length": code_length,
            "lit_count": literal_count,
            "lit_first": literal_cursor,
            "literals": node_order[literal_cursor:literal_cursor + literal_count],
            "name": c_string(strings, name_off),
        }
        entries.append(entry)
        literal_cursor += literal_count
        code_cursor += code_length
    require(literal_cursor == patch_count and code_cursor == blob_len,
            "legacy compiler entry coverage drift")
    require([row["name"] for row in entries] == summary.entry_names,
            "legacy compiler name census drift")

    manifest = {
        "format": "lisp65-c2-session-probe-legacy-input-v1",
        "name": key,
        "blob": f"build/c2.1/session-extension/{key}.code.bin",
        "blob_sha256": sha(blob),
        "code_bytes": len(blob),
        "entries": entries,
        "exports": [row["name"] for row in entries],
        "late_bound_exports": [],
        "literal_nodes": nodes,
        "literal_index": node_order,
        "literal_patches": patches,
    }
    return manifest, blob


def root_fixture(source: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(source)
    value["name"] = "session-root-fixture"
    value["blob"] = "build/c2.1/session-extension/session-root-fixture.code.bin"
    for entry in value["entries"]:
        entry["name"] = "r-" + entry["name"]
    value["exports"] = [row["name"] for row in value["entries"]]
    nodes = value["literal_nodes"]
    require(len(nodes) >= 3 and value["literal_index"][:3] == [0, 1, 2],
            "root fixture requires first three topological literals")
    nodes[0] = {"kind": 7, "value": 0, "first": 0, "count": 0,
                "name": "session-root"}
    nodes[2] = {"kind": 5, "value": 0, "first": 0, "count": 2}
    return value


@dataclass(frozen=True)
class Extension:
    data: bytes
    image: F.Emitted
    code_offset: int
    metadata_offset: int
    catalog_crc: int
    combined_crc: int


SESSION_RECORD_ID = b"SESS\0\0\0\0"


def build_extension(
        image: F.Emitted, *, build_id: int = PROBE_BUILD_ID) -> bytes:
    require(0 < build_id <= 0xFFFFFFFF,
            "extension product build identity range")
    data, _rows, _catalog_crc = F.build_shelf([image])
    candidate = bytearray(data)
    struct.pack_into("<I", candidate, 22, build_id)
    # A one-record session artifact has no record-local name namespace.  Its
    # canonical identity is the fixed SESS tag consumed by the product
    # envelope verifier; library names live once in the L65I index.
    candidate[32:40] = SESSION_RECORD_ID
    struct.pack_into(
        "<I", candidate, 18,
        zlib.crc32(candidate[32:64]) & 0xFFFFFFFF)
    return bytes(candidate)


def decode_extension(
        data: bytes, expected: F.Emitted | None = None, *,
        expected_build_id: int = PROBE_BUILD_ID) -> Extension:
    require(0 < expected_build_id <= 0xFFFFFFFF,
            "extension expected product build identity range")
    require(len(data) >= F.SHELF_HEADER_BYTES + F.SHELF_RECORD_BYTES,
            "extension shorter than header and record")
    require(data[:4] == b"L65S" and data[4] == 4, "extension magic/version")
    require(tuple(data[5:8]) == (32, 32, 1), "extension widths/count")
    catalog_offset = u16(data, 8)
    payload_offset, total = u24(data, 10), u24(data, 13)
    catalog_bytes = u16(data, 16)
    catalog_crc = struct.unpack_from("<I", data, 18)[0]
    require(catalog_offset == 32 and catalog_bytes == 32 and payload_offset == 64,
            "extension canonical section layout")
    require(total == len(data) <= 8192, "extension truncation, trailing data or size")
    require(struct.unpack_from("<I", data, 22)[0] == expected_build_id,
            "extension product build identity")
    require(u16(data, 26) == 1 and data[28:32] == b"\0" * 4,
            "extension header flags/reserved")
    record = data[32:64]
    require(zlib.crc32(record) & 0xFFFFFFFF == catalog_crc,
            "extension catalog CRC")
    require(record[:4] == SESSION_RECORD_ID[:4],
            "extension session record identity")
    require(record[30] == 1 and record[31] == 0,
            "extension record flags/reserved")
    code_offset, code_length = u24(record, 8), u16(record, 11)
    metadata_offset, metadata_length = u24(record, 13), u16(record, 16)
    require(code_length > 0 and metadata_length >= F.HEADER_BYTES,
            "extension empty code or metadata")
    require(code_offset == payload_offset and metadata_offset == code_offset + code_length,
            "extension overlap or noncanonical split")
    require(metadata_offset + metadata_length == len(data),
            "extension region arithmetic")
    code = data[code_offset:code_offset + code_length]
    metadata = data[metadata_offset:metadata_offset + metadata_length]
    require(zlib.crc32(code) & 0xFFFFFFFF == struct.unpack_from("<I", record, 18)[0],
            "extension code CRC")
    require(zlib.crc32(metadata) & 0xFFFFFFFF == struct.unpack_from("<I", record, 22)[0],
            "extension metadata CRC")
    combined_crc = struct.unpack_from("<I", record, 26)[0]
    require(zlib.crc32(code + metadata) & 0xFFFFFFFF == combined_crc,
            "extension combined image CRC")
    F.decode_c2i(code, metadata, declared_exports=None)
    if expected is None:
        # Mutation tests need no manifest reconstruction; retain an opaque marker.
        expected = F.Emitted("decoded", "session", Path("decoded"), {}, code,
                             metadata, [], {}, [], 0, {}, 0)
    else:
        require(code == expected.code and metadata == expected.metadata,
                "extension differs from emitted image")
    return Extension(data, expected, code_offset, metadata_offset,
                     catalog_crc, combined_crc)


def repair_extension_crcs(candidate: bytearray) -> None:
    record = bytearray(candidate[32:64])
    code_offset, code_length = u24(record, 8), u16(record, 11)
    metadata_offset, metadata_length = u24(record, 13), u16(record, 16)
    code = bytes(candidate[code_offset:code_offset + code_length])
    metadata = bytes(candidate[metadata_offset:metadata_offset + metadata_length])
    struct.pack_into("<I", record, 18, zlib.crc32(code) & 0xFFFFFFFF)
    struct.pack_into("<I", record, 22, zlib.crc32(metadata) & 0xFFFFFFFF)
    struct.pack_into("<I", record, 26, zlib.crc32(code + metadata) & 0xFFFFFFFF)
    candidate[32:64] = record
    struct.pack_into("<I", candidate, 18, zlib.crc32(record) & 0xFFFFFFFF)


def contract_check() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("status") == "host-probe-complete-owner-review-required",
            "session-extension contract is not in review-ready probe state")
    require(contract["single_format_rule"] == {
        "immutable_image_language": "C2I-v2 for static shelf images, interactive definitions and persistent compiled libraries",
        "outer_envelope": "one-record L65S-v4-direct with split code and C2I-v2 metadata regions",
        "device_decoder_count": 1,
        "product_emitter_count": 1,
        "legacy_l65m_product_policy": "The C2 product rejects L65M on device. Source remains portable; v1.1 compiled artifacts require recompilation or an offline migration tool. No L65M emitter or decoder may remain in the C2 product closure.",
    }, "single-format contract drift")
    require(contract["session_attic_arena"]["base"] == "0x08400000"
            and contract["session_attic_arena"]["bytes"] == SESSION_ATTIC_BYTES,
            "session Attic contract drift")
    capacities = contract["c2d_v3"]["capacities"]
    require(capacities["images"] == C2D_IMAGE_CAPACITY
            and capacities["entries"] == C2D_ENTRY_CAPACITY
            and capacities["resolutions"] == C2D_RESOLUTION_CAPACITY
            and capacities["roots"] == C2D_ROOT_CAPACITY
            and capacities["total_bytes"] == C2D_TOTAL_BYTES
            and capacities["bank5_headroom_bytes"] == C2D_REGION_BYTES - C2D_TOTAL_BYTES,
            "C2D-v3 capacity contract drift")
    require(len(contract["append_protocol"]) == 10
            and len(contract["required_probe_fixtures"]) == 12,
            "append or fixture contract closure drift")
    require(load(GAP_CONTRACT)["status"] == "option-a-owner-approved-bounded-probe-authorized",
            "dynamic-code decision is not Option A")
    return contract


def encode_header(data: bytearray, *, generation: int, image_count: int,
                  entry_count: int, resolution_count: int, root_count: int,
                  immutable_images: int, catalog_crc: int, build_id: int) -> None:
    require(0 < generation <= 0xFFFF, "session generation must be nonzero")
    header = bytearray(b"C2D\0")
    header += bytes((3, C2D_HEADER_BYTES, C2D_IMAGE_BYTES, C2D_ENTRY_BYTES))
    header += struct.pack(
        "<HHHHHHHHHHHHHHHHII",
        0, generation,
        image_count, C2D_IMAGE_CAPACITY,
        entry_count, C2D_ENTRY_CAPACITY,
        resolution_count, C2D_RESOLUTION_CAPACITY,
        root_count, C2D_ROOT_CAPACITY,
        C2D_IMAGES_OFFSET, C2D_ENTRIES_OFFSET,
        C2D_RESOLUTIONS_OFFSET, C2D_ROOTS_OFFSET,
        C2D_TOTAL_BYTES, immutable_images,
        catalog_crc, build_id,
    )
    require(len(header) == C2D_HEADER_BYTES, "C2D-v3 header width")
    data[:C2D_HEADER_BYTES] = header


def image_record(*, source_kind: int, source_slot: int, generation: int,
                 directory_base: int, entries: int, resolution_base: int,
                 resolutions: int, root_base: int, roots: int,
                 code_offset: int, code_length: int, metadata_offset: int,
                 metadata_length: int, combined_crc: int) -> bytes:
    value = bytearray((source_kind, 0, source_slot, 0))
    value += struct.pack("<HHHHHHH", generation, directory_base, entries,
                         resolution_base, resolutions, root_base, roots)
    value += p24(code_offset) + struct.pack("<H", code_length)
    value += p24(metadata_offset) + struct.pack("<H", metadata_length)
    value += struct.pack("<I", combined_crc)
    require(len(value) == C2D_IMAGE_BYTES, "C2D-v3 image width")
    return bytes(value)


def entry_record(*, image_slot: int, ordinal: int, code_length: int,
                 resolution_base: int, generation: int) -> bytes:
    value = bytes((image_slot, 0)) + struct.pack(
        "<HHHH", ordinal, code_length, resolution_base, generation)
    require(len(value) == C2D_ENTRY_BYTES, "C2D-v3 entry width")
    return value


@dataclass
class Plane:
    data: bytearray
    attic: bytearray
    attic_watermark: int
    exports: dict[str, int]
    pending_root_highwater: int
    generation: int
    catalog_crc: int
    build_id: int
    images: list[F.Emitted]

    def clone(self) -> "Plane":
        return Plane(bytearray(self.data), bytearray(self.attic), self.attic_watermark,
                     dict(self.exports), self.pending_root_highwater, self.generation,
                     self.catalog_crc, self.build_id, list(self.images))


def header_counts(data: bytes | bytearray) -> tuple[int, int, int, int]:
    return tuple(u16(data, at) for at in (12, 16, 20, 24))  # type: ignore[return-value]


def build_initial_plane(images: list[F.Emitted], shelf: bytes,
                        rows: list[dict[str, int]], catalog_crc: int,
                        *, generation: int = SESSION_GENERATION) -> Plane:
    data = bytearray(C2D_TOTAL_BYTES)
    entry_base = resolution_base = root_base = 0
    global_resolution = 0
    for slot, (image, row) in enumerate(zip(images, rows)):
        roots = sum(desc.kind in ROOT_KINDS for desc in image.descriptors)
        record = image_record(
            source_kind=0, source_slot=slot, generation=generation,
            directory_base=entry_base, entries=len(image.manifest["entries"]),
            resolution_base=resolution_base, resolutions=len(image.descriptors),
            root_base=root_base, roots=roots,
            code_offset=row["code_offset"], code_length=row["code_length"],
            metadata_offset=row["metadata_offset"], metadata_length=row["metadata_length"],
            combined_crc=zlib.crc32(image.code + image.metadata) & 0xFFFFFFFF,
        )
        at = C2D_IMAGES_OFFSET + slot * C2D_IMAGE_BYTES
        data[at:at + C2D_IMAGE_BYTES] = record
        for ordinal, entry in enumerate(image.manifest["entries"]):
            item = entry_record(
                image_slot=slot, ordinal=ordinal, code_length=int(entry["length"]),
                resolution_base=resolution_base + image.entry_first[ordinal],
                generation=generation,
            )
            pos = C2D_ENTRIES_OFFSET + (entry_base + ordinal) * C2D_ENTRY_BYTES
            data[pos:pos + C2D_ENTRY_BYTES] = item
        for descriptor in image.descriptors:
            pos = C2D_RESOLUTIONS_OFFSET + global_resolution * 2
            if descriptor.kind in ROOT_KINDS:
                struct.pack_into("<H", data, pos, root_base)
                struct.pack_into("<H", data, C2D_ROOTS_OFFSET + root_base * 2,
                                 G.pointer_for(root_base))
                root_base += 1
            else:
                struct.pack_into("<H", data, pos,
                                 G.direct_value(
                                     descriptor, global_resolution,
                                     directory_base=entry_base))
            global_resolution += 1
        entry_base += len(image.manifest["entries"])
        resolution_base += len(image.descriptors)
    require((entry_base, resolution_base, root_base) == (583, 2249, 284),
            "static C2D-v3 census")
    encode_header(data, generation=generation, image_count=6,
                  entry_count=entry_base, resolution_count=resolution_base,
                  root_count=root_base, immutable_images=6,
                  catalog_crc=catalog_crc, build_id=PROBE_BUILD_ID)
    plane = Plane(data, bytearray(SESSION_ATTIC_BYTES), 0, {}, 0,
                  generation, catalog_crc, PROBE_BUILD_ID, list(images))
    decode_plane(plane, shelf=shelf)
    return plane


def decode_plane(plane: Plane, *, shelf: bytes | None = None) -> dict[str, int]:
    data = plane.data
    require(len(data) == C2D_TOTAL_BYTES and data[:4] == b"C2D\0" and data[4] == 3,
            "C2D-v3 magic/version/length")
    require(tuple(data[5:8]) == (48, 32, 10), "C2D-v3 record widths")
    require(u16(data, 8) == 0 and u16(data, 10) == plane.generation != 0,
            "C2D-v3 flags/generation")
    image_count, entry_count, resolution_count, root_count = header_counts(data)
    require((u16(data, 14), u16(data, 18), u16(data, 22), u16(data, 26)) ==
            (64, 2048, 4096, 1536), "C2D-v3 capacities")
    require((u16(data, 28), u16(data, 30), u16(data, 32), u16(data, 34)) ==
            (48, 2096, 22576, 30768), "C2D-v3 section offsets")
    require(u16(data, 36) == C2D_TOTAL_BYTES and u16(data, 38) == 6,
            "C2D-v3 total/immutable count")
    require(struct.unpack_from("<I", data, 40)[0] == plane.catalog_crc
            and struct.unpack_from("<I", data, 44)[0] == plane.build_id,
            "C2D-v3 product identity")
    require(image_count <= 64 and entry_count <= 2048
            and resolution_count <= 4096 and root_count <= 1536,
            "C2D-v3 active count exceeds capacity")
    expected_entry = expected_resolution = expected_root = 0
    derived_attic_watermark = 0
    for slot in range(image_count):
        at = C2D_IMAGES_OFFSET + slot * C2D_IMAGE_BYTES
        source_kind, flags, source_slot, reserved = data[at:at + 4]
        generation = u16(data, at + 4)
        require(source_kind in (0, 1) and flags == reserved == 0,
                "C2D-v3 image source/flags")
        require(generation == plane.generation, "C2D-v3 stale image generation")
        require(source_slot == (slot if source_kind == 0 else slot - 6),
                "C2D-v3 source slot")
        directory_base, entries = u16(data, at + 6), u16(data, at + 8)
        resolution_base, resolutions = u16(data, at + 10), u16(data, at + 12)
        root_base, roots = u16(data, at + 14), u16(data, at + 16)
        require((directory_base, resolution_base, root_base) ==
                (expected_entry, expected_resolution, expected_root),
                "C2D-v3 image ranges are not contiguous")
        code_offset, code_length = u24(data, at + 18), u16(data, at + 21)
        metadata_offset, metadata_length = u24(data, at + 23), u16(data, at + 26)
        combined_crc = struct.unpack_from("<I", data, at + 28)[0]
        if source_kind == 0:
            require(shelf is not None and metadata_offset + metadata_length <= len(shelf),
                    "C2D-v3 product source range")
            code = shelf[code_offset:code_offset + code_length]
            metadata = shelf[metadata_offset:metadata_offset + metadata_length]
        else:
            require(metadata_offset + metadata_length <= plane.attic_watermark,
                    "C2D-v3 session source range")
            code = plane.attic[code_offset:code_offset + code_length]
            metadata = plane.attic[metadata_offset:metadata_offset + metadata_length]
            derived_attic_watermark = max(
                derived_attic_watermark, metadata_offset + metadata_length)
        require(zlib.crc32(bytes(code) + bytes(metadata)) & 0xFFFFFFFF == combined_crc,
                "C2D-v3 image identity")
        for ordinal in range(entries):
            pos = C2D_ENTRIES_OFFSET + (directory_base + ordinal) * C2D_ENTRY_BYTES
            require(data[pos] == slot and data[pos + 1] == 0
                    and u16(data, pos + 2) == ordinal
                    and u16(data, pos + 8) == plane.generation,
                    "C2D-v3 entry identity/generation")
        expected_entry += entries
        expected_resolution += resolutions
        expected_root += roots
    require((expected_entry, expected_resolution, expected_root) ==
            (entry_count, resolution_count, root_count), "C2D-v3 count closure")
    require(plane.attic_watermark == derived_attic_watermark,
            "C2D-v3 Attic watermark differs from active image derivation")
    for start, active, cap, width in (
        (C2D_IMAGES_OFFSET, image_count, 64, 32),
        (C2D_ENTRIES_OFFSET, entry_count, 2048, 10),
        (C2D_RESOLUTIONS_OFFSET, resolution_count, 4096, 2),
        (C2D_ROOTS_OFFSET, root_count, 1536, 2),
    ):
        require(all(byte == 0 for byte in data[start + active * width:start + cap * width]),
                "C2D-v3 inactive range is not zero")
    require(plane.pending_root_highwater == 0, "published plane retains pending roots")
    return {"images": image_count, "entries": entry_count,
            "resolutions": resolution_count, "roots": root_count}


def capacity_check(counts: tuple[int, int, int, int], additions: tuple[int, int, int, int],
                   watermark: int, artifact_bytes: int) -> None:
    capacities = (64, 2048, 4096, 1536)
    for label, current, add, capacity in zip(
            ("image", "entry", "resolution", "root"), counts, additions, capacities):
        require(current <= capacity and add <= capacity - current,
                f"{label} capacity exhausted")
    aligned = (watermark + 1) & ~1
    require(aligned <= SESSION_ATTIC_BYTES
            and artifact_bytes <= SESSION_ATTIC_BYTES - aligned,
            "Attic capacity exhausted")


def extension_exports(image: F.Emitted) -> list[str]:
    return [row["name"] for row in image.manifest["entries"]
            if not row.get("anonymous", False)]


def append_extension(plane: Plane, extension: Extension, *, requested_generation: int,
                     shelf: bytes, fail_at: str | None = None,
                     gc_callback: Callable[[Plane, list[int]], None] | None = None) -> dict[str, int]:
    require(requested_generation == plane.generation, "stale session generation")
    before = plane.clone()
    image = extension.image
    additions = (1, len(image.manifest["entries"]), len(image.descriptors),
                 sum(desc.kind in ROOT_KINDS for desc in image.descriptors))
    counts = header_counts(plane.data)
    capacity_check(counts, additions, plane.attic_watermark, len(extension.data))
    image_count, entry_count, resolution_count, root_count = counts
    stage_at = (plane.attic_watermark + 1) & ~1
    touched_exports: list[tuple[str, int | None]] = []
    new_roots: list[int] = []
    collections = 0

    def maybe(label: str) -> None:
        if fail_at == label:
            raise ProbeError(f"injected failure: {label}")

    try:
        plane.attic[stage_at:stage_at + len(extension.data)] = extension.data
        require(bytes(plane.attic[stage_at:stage_at + len(extension.data)]) == extension.data,
                "Attic stage readback")
        maybe("after-stage")

        local_root = 0
        for local, descriptor in enumerate(image.descriptors):
            rpos = C2D_RESOLUTIONS_OFFSET + (resolution_count + local) * 2
            if descriptor.kind in ROOT_KINDS:
                index = root_count + local_root
                value = G.pointer_for(index)
                struct.pack_into("<H", plane.data, C2D_ROOTS_OFFSET + index * 2, value)
                plane.pending_root_highwater = index + 1
                struct.pack_into("<H", plane.data, rpos, index)
                new_roots.append(value)
                if gc_callback is not None:
                    gc_callback(plane, new_roots)
                collections += 1
                local_root += 1
            else:
                struct.pack_into("<H", plane.data, rpos,
                                 G.direct_value(
                                     descriptor, resolution_count + local,
                                     directory_base=entry_count))
        maybe("after-resolve")

        record = image_record(
            source_kind=1, source_slot=image_count - 6,
            generation=plane.generation,
            directory_base=entry_count, entries=additions[1],
            resolution_base=resolution_count, resolutions=additions[2],
            root_base=root_count, roots=additions[3],
            code_offset=stage_at + extension.code_offset,
            code_length=len(image.code),
            metadata_offset=stage_at + extension.metadata_offset,
            metadata_length=len(image.metadata),
            combined_crc=extension.combined_crc,
        )
        pos = C2D_IMAGES_OFFSET + image_count * C2D_IMAGE_BYTES
        plane.data[pos:pos + C2D_IMAGE_BYTES] = record
        for ordinal, entry in enumerate(image.manifest["entries"]):
            item = entry_record(
                image_slot=image_count, ordinal=ordinal,
                code_length=int(entry["length"]),
                resolution_base=resolution_count + image.entry_first[ordinal],
                generation=plane.generation,
            )
            at = C2D_ENTRIES_OFFSET + (entry_count + ordinal) * C2D_ENTRY_BYTES
            plane.data[at:at + C2D_ENTRY_BYTES] = item
        maybe("after-records")

        for name in extension_exports(image):
            touched_exports.append((name, plane.exports.get(name)))
        maybe("after-journal")

        plane.attic_watermark = stage_at + len(extension.data)
        encode_header(
            plane.data, generation=plane.generation,
            image_count=image_count + 1, entry_count=entry_count + additions[1],
            resolution_count=resolution_count + additions[2],
            root_count=root_count + additions[3], immutable_images=6,
            catalog_crc=plane.catalog_crc, build_id=plane.build_id,
        )
        plane.pending_root_highwater = 0
        maybe("after-header")

        exports = extension_exports(image)
        for ordinal, name in enumerate(exports):
            plane.exports[name] = ((0x6000 + entry_count + ordinal) << 1) & 0xFFFF
            if ordinal == 0:
                maybe("during-export-first")
            if ordinal == len(exports) // 2:
                maybe("during-export-mid")
            if ordinal == len(exports) - 1:
                maybe("during-export-last")
        decode_plane(plane, shelf=shelf)
        plane.images.append(image)
        return {"gc_collections": collections, "new_roots": len(new_roots),
                "stage_offset": stage_at, "artifact_bytes": len(extension.data)}
    except ProbeError:
        plane.data[:] = before.data
        plane.attic[:] = before.attic
        plane.attic_watermark = before.attic_watermark
        for name, previous in reversed(touched_exports):
            if previous is None:
                plane.exports.pop(name, None)
            else:
                plane.exports[name] = previous
        plane.pending_root_highwater = 0
        plane.images = list(before.images)
        require(plane.data == before.data and plane.attic == before.attic
                and plane.exports == before.exports
                and plane.attic_watermark == before.attic_watermark,
                "append rollback differs from prior state")
        raise


def gc_check(plane: Plane, allocated: list[int]) -> None:
    committed = u16(plane.data, 24)
    highwater = max(committed, plane.pending_root_highwater)
    values = [u16(plane.data, C2D_ROOTS_OFFSET + index * 2)
              for index in range(highwater)]
    before = list(values)
    marked = {value for value in values if value}
    require(set(allocated) <= marked, "append GC lost a new root")
    after = [u16(plane.data, C2D_ROOTS_OFFSET + index * 2)
             for index in range(highwater)]
    require(after == before, "non-moving append GC wrote roots back")


def reject(label: str, operation: Callable[[], Any], fragment: str = "") -> str:
    try:
        operation()
    except (ProbeError, F.FullError, L.ContractError) as exc:
        require(not fragment or fragment in str(exc),
                f"{label} wrong diagnostic: {exc}")
        return label
    raise ProbeError(f"negative fixture accepted: {label} {fragment}")


def envelope_negatives(baseline: bytes) -> list[str]:
    cases: list[tuple[str, Callable[[bytearray], None], bool]] = [
        ("magic", lambda x: x.__setitem__(0, ord("X")), False),
        ("version", lambda x: x.__setitem__(4, 3), False),
        ("header-width", lambda x: x.__setitem__(5, 31), False),
        ("record-width", lambda x: x.__setitem__(6, 31), False),
        ("record-count", lambda x: x.__setitem__(7, 2), False),
        ("build-identity", lambda x: x.__setitem__(22, x[22] ^ 1), False),
        ("catalog-crc", lambda x: x.__setitem__(18, x[18] ^ 1), False),
        ("session-record-identity",
         lambda x: x.__setitem__(32, ord("X")), True),
        ("code-crc", lambda x: x.__setitem__(50, x[50] ^ 1), True),
        ("metadata-crc", lambda x: x.__setitem__(54, x[54] ^ 1), True),
        ("combined-crc", lambda x: x.__setitem__(58, x[58] ^ 1), True),
        ("unknown-flags", lambda x: x.__setitem__(26, 3), False),
        ("record-flags", lambda x: x.__setitem__(62, 3), True),
        ("overlap", lambda x: x.__setitem__(45, x[40]), True),
    ]
    rejected = []
    for label, mutate, repair_catalog in cases:
        candidate = bytearray(baseline)
        mutate(candidate)
        if repair_catalog:
            struct.pack_into("<I", candidate, 18,
                             zlib.crc32(candidate[32:64]) & 0xFFFFFFFF)
        rejected.append(reject(label, lambda c=bytes(candidate): decode_extension(c)))
    rejected.append(reject("trailing", lambda: decode_extension(baseline + b"\0")))
    rejected.append(reject("truncated", lambda: decode_extension(baseline[:-1])))
    candidate = bytearray(baseline)
    metadata_offset = u24(candidate, 45)
    # First C2I entry code_length_u16 is at metadata + header + 3.
    struct.pack_into("<H", candidate, metadata_offset + F.HEADER_BYTES + 3, 0)
    repair_extension_crcs(candidate)
    rejected.append(reject("zero-entry-length", lambda: decode_extension(bytes(candidate))))
    return rejected


def c2d_negatives(initial: Plane, shelf: bytes) -> list[str]:
    mutations: list[tuple[str, Callable[[Plane], None]]] = [
        ("c2d-version", lambda p: p.data.__setitem__(4, 2)),
        ("c2d-image-width", lambda p: p.data.__setitem__(6, 31)),
        ("c2d-capacity", lambda p: struct.pack_into("<H", p.data, 14, 63)),
        ("c2d-offset", lambda p: struct.pack_into("<H", p.data, 30, 2095)),
        ("c2d-build-id", lambda p: p.data.__setitem__(44, p.data[44] ^ 1)),
        ("c2d-catalog", lambda p: p.data.__setitem__(40, p.data[40] ^ 1)),
        ("c2d-source-kind", lambda p: p.data.__setitem__(C2D_IMAGES_OFFSET, 2)),
        ("c2d-stale-image-generation",
         lambda p: struct.pack_into("<H", p.data, C2D_IMAGES_OFFSET + 4, p.generation + 1)),
        ("c2d-stale-entry-generation",
         lambda p: struct.pack_into("<H", p.data, C2D_ENTRIES_OFFSET + 8, p.generation + 1)),
        ("c2d-inactive-nonzero",
         lambda p: p.data.__setitem__(C2D_IMAGES_OFFSET + 6 * 32, 1)),
        ("c2d-derived-attic-watermark", lambda p: setattr(p, "attic_watermark", 2)),
    ]
    result = []
    for label, mutate in mutations:
        candidate = initial.clone()
        mutate(candidate)
        result.append(reject(label, lambda p=candidate: decode_plane(p, shelf=shelf)))
    return result


def capacity_negatives() -> list[str]:
    labels = []
    for ordinal, label in enumerate(("image-capacity", "entry-capacity",
                                     "resolution-capacity", "root-capacity")):
        counts = [0, 0, 0, 0]
        counts[ordinal] = (64, 2048, 4096, 1536)[ordinal]
        additions = [0, 0, 0, 0]
        additions[ordinal] = 1
        labels.append(reject(label, lambda c=tuple(counts), a=tuple(additions):
                             capacity_check(c, a, 0, 1)))
    labels.append(reject("attic-capacity", lambda: capacity_check(
        (0, 0, 0, 0), (0, 0, 0, 0), SESSION_ATTIC_BYTES - 1, 2)))
    return labels


def materialize_probe_file(path: Path, data: bytes, *, write_artifacts: bool) -> None:
    if write_artifacts:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    else:
        require(path.is_file() and path.read_bytes() == data,
                f"generated probe input drift: {path}")


def build_inputs(*, write_artifacts: bool) -> tuple[
        list[F.Emitted], bytes, list[dict[str, int]], int,
        F.Emitted, F.Emitted, bytes, bytes, dict[str, Any]]:
    contract_check()
    require(LEGACY_INPUT.is_file(), "real compiler oracle missing; run make fasl-emit-check")
    legacy = LEGACY_INPUT.read_bytes()
    manifest, code = legacy_manifest(legacy, "dynamic-code")
    root_manifest = root_fixture(manifest)
    code_path = BUILD / "dynamic-code.code.bin"
    root_code_path = BUILD / "session-root-fixture.code.bin"
    manifest_path = BUILD / "dynamic-code.manifest.json"
    root_manifest_path = BUILD / "session-root-fixture.manifest.json"
    materialize_probe_file(code_path, code, write_artifacts=write_artifacts)
    materialize_probe_file(root_code_path, code, write_artifacts=write_artifacts)
    materialize_probe_file(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        write_artifacts=write_artifacts,
    )
    materialize_probe_file(
        root_manifest_path,
        (json.dumps(root_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        write_artifacts=write_artifacts,
    )

    F.contract_check()
    static = [F.emit_image(*row) for row in F.IMAGES]
    dynamic = F.emit_image("dynamic-code", "session", manifest_path)
    rooted = F.emit_image("session-root-fixture", "roots", root_manifest_path)
    shelf, rows, catalog_crc = F.build_shelf(static)
    F.verify_shelf(shelf, static, F.declared_exports(static))
    first = build_extension(dynamic)
    second = build_extension(F.emit_image("dynamic-code", "session", manifest_path))
    rooted_bytes = build_extension(rooted)
    require(first == second, "session extension is not deterministic")
    require(b"L65M" not in first and b"L65M" not in rooted_bytes,
            "candidate extension retains L65M magic")
    decode_extension(first, dynamic)
    decode_extension(rooted_bytes, rooted)
    require(reject("legacy-to-c2", lambda: decode_extension(legacy)) == "legacy-to-c2",
            "legacy reverse strictness")
    require(reject("c2-to-legacy", lambda: L.validate_image(first)) == "c2-to-legacy",
            "C2 reverse strictness")
    emitter_source = inspect.getsource(F.emit_image).encode("utf-8")
    emitter = {
        "implementation": "tools/host-lisp/c2_full_emission.py::emit_image",
        "implementation_count": 1,
        "implementation_sha256": sha(emitter_source),
        "semantic_input_calls": 8,
        "static_product_calls": 6,
        "real_compiler_derived_calls": 1,
        "root_stress_fixture_calls": 1,
        "determinism_repeat_calls": 1,
        "total_invocations": 9,
        "legacy_emitter_calls": 0,
        "legacy_patch_records_in_candidate": 0,
    }
    return static, shelf, rows, catalog_crc, dynamic, rooted, first, rooted_bytes, emitter


def collect(write_artifacts: bool) -> dict[str, Any]:
    contract = contract_check()
    (static, shelf, rows, catalog_crc, dynamic, rooted,
     dynamic_bytes, rooted_bytes, emitter) = build_inputs(write_artifacts=write_artifacts)
    dynamic_ext = decode_extension(dynamic_bytes, dynamic)
    root_ext = decode_extension(rooted_bytes, rooted)
    initial = build_initial_plane(static, shelf, rows, catalog_crc)
    initial_bytes = bytes(initial.data)

    rollback_labels = [
        "after-stage", "after-resolve", "after-records", "after-journal",
        "after-header", "during-export-first", "during-export-mid",
        "during-export-last",
    ]
    rollback_rejected = []
    for label in rollback_labels:
        candidate = initial.clone()
        before = candidate.clone()
        rollback_rejected.append(reject(
            label,
            lambda p=candidate, point=label: append_extension(
                p, dynamic_ext, requested_generation=SESSION_GENERATION,
                shelf=shelf, fail_at=point, gc_callback=gc_check),
        ))
        require(candidate.data == before.data and candidate.attic == before.attic
                and candidate.exports == before.exports
                and candidate.attic_watermark == before.attic_watermark,
                f"rollback state mismatch after {label}")

    committed = initial.clone()
    first_append = append_extension(
        committed, dynamic_ext, requested_generation=SESSION_GENERATION,
        shelf=shelf, gc_callback=gc_check)
    second_append = append_extension(
        committed, root_ext, requested_generation=SESSION_GENERATION,
        shelf=shelf, gc_callback=gc_check)
    final_counts = decode_plane(committed, shelf=shelf)
    require(final_counts == {"images": 8, "entries": 595,
                             "resolutions": 2259, "roots": 286},
            "C2D-v3 append census")
    require(first_append["new_roots"] == 0 and second_append["new_roots"] == 2
            and second_append["gc_collections"] == 2,
            "append root/GC census")

    # A cold restage creates generation 2 while Attic retains old bytes.  No
    # extension record or export survives, and injecting the old image record
    # is rejected before source-address use.
    restaged = build_initial_plane(static, shelf, rows, catalog_crc, generation=2)
    restaged.attic[:] = committed.attic
    restaged.attic_watermark = 0
    decode_plane(restaged, shelf=shelf)
    require(not restaged.exports and header_counts(restaged.data) == (6, 583, 2249, 284),
            "restage made stale Attic extension reachable")
    stale_append = reject("stale-generation-append", lambda: append_extension(
        restaged, dynamic_ext, requested_generation=1, shelf=shelf, gc_callback=gc_check))
    stale_record = restaged.clone()
    source = committed.data[C2D_IMAGES_OFFSET + 6 * 32:C2D_IMAGES_OFFSET + 7 * 32]
    stale_record.data[C2D_IMAGES_OFFSET + 6 * 32:C2D_IMAGES_OFFSET + 7 * 32] = source
    encode_header(stale_record.data, generation=2, image_count=7, entry_count=583,
                  resolution_count=2249, root_count=284, immutable_images=6,
                  catalog_crc=catalog_crc, build_id=PROBE_BUILD_ID)
    stale_record_rejected = reject("stale-generation-record", lambda: decode_plane(
        stale_record, shelf=shelf))

    envelope = envelope_negatives(dynamic_bytes)
    c2d = c2d_negatives(initial, shelf)
    capacities = capacity_negatives()

    paths = {
        "dynamic_manifest": BUILD / "dynamic-code.manifest.json",
        "root_manifest": BUILD / "session-root-fixture.manifest.json",
        "dynamic_code": BUILD / "dynamic-code.code.bin",
        "root_code": BUILD / "session-root-fixture.code.bin",
        "dynamic_extension": BUILD / "dynamic-code.l65s-v4",
        "root_extension": BUILD / "session-root-fixture.l65s-v4",
        "initial_c2d": BUILD / "initial.c2d-v3.bin",
        "committed_c2d": BUILD / "committed.c2d-v3.bin",
    }
    if write_artifacts:
        paths["dynamic_extension"].write_bytes(dynamic_bytes)
        paths["root_extension"].write_bytes(rooted_bytes)
        paths["initial_c2d"].write_bytes(initial_bytes)
        paths["committed_c2d"].write_bytes(bytes(committed.data))
    else:
        expected = {
            "dynamic_extension": dynamic_bytes,
            "root_extension": rooted_bytes,
            "initial_c2d": initial_bytes,
            "committed_c2d": bytes(committed.data),
        }
        for key, data in expected.items():
            require(paths[key].is_file() and paths[key].read_bytes() == data,
                    f"generated artifact drift: {paths[key]}")

    output_bindings = {
        key: bind(path) for key, path in paths.items()
    }
    negative_classes = envelope + c2d + capacities + rollback_rejected + [
        stale_append, stale_record_rejected, "legacy-to-c2", "c2-to-legacy"
    ]
    require(len(negative_classes) == 44 and len(set(negative_classes)) == 44,
            f"negative fixture closure count={len(negative_classes)} "
            f"unique={len(set(negative_classes))}")

    return {
        "format": "lisp65-c2-session-extension-probe-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "host-probe-complete-owner-review-required",
        "claim_limit": (
            "Bounded contract/emitter/append host proof only. It changes no product "
            "source or artifact, authorizes no capacity, makes no device, latency, "
            "compatibility or product-link claim, and leaves substitution stopped."
        ),
        "bindings": {
            "contract": bind(CONTRACT),
            "document": bind(DOCUMENT),
            "verifier": bind(Path(__file__)),
            "dynamic_gap_contract": bind(GAP_CONTRACT),
            "dynamic_gap_receipt": bind(GAP_RECEIPT),
            "full_emission_receipt": bind(FULL_RECEIPT),
            "single_source_root_receipt": bind(ROOT_RECEIPT),
            "canonical_c2_emitter": bind(ROOT / "tools/host-lisp/c2_full_emission.py"),
            "historical_l65m_validator": bind(ROOT / "tools/host-lisp/l65m_contract.py"),
            "real_compiler_oracle": bind(LEGACY_INPUT),
            "generated_probe_artifacts": output_bindings,
        },
        "verified": {
            "product_bytes_changed": 0,
            "capacity_deltas": "all-zero/not-run",
            "real_product_substitution_link_run": False,
            "single_emitter": emitter,
            "static_images": 6,
            "static_entries": 583,
            "dynamic_compiler_entries": len(dynamic.manifest["entries"]),
            "dynamic_compiler_descriptors": len(dynamic.descriptors),
            "extension_format": "one-record L65S-v4-direct/C2I-v2",
            "extension_deterministic_double_emission": True,
            "extension_bytes": len(dynamic_bytes),
            "extension_sha256": sha(dynamic_bytes),
            "legacy_patch_table_in_candidate": False,
            "strict_reverse_format_rejection": ["legacy-to-c2", "c2-to-legacy"],
            "c2d_v3_initial": {
                "bytes": C2D_TOTAL_BYTES,
                "headroom": C2D_REGION_BYTES - C2D_TOTAL_BYTES,
                "counts": {"images": 6, "entries": 583,
                           "resolutions": 2249, "roots": 284},
            },
            "c2d_v3_after_two_appends": final_counts,
            "session_attic": {
                "base": f"0x{SESSION_ATTIC_BASE:08x}",
                "capacity_bytes": SESSION_ATTIC_BYTES,
                "published_watermark": committed.attic_watermark,
                "first_append": first_append,
                "second_append": second_append,
            },
            "generation_binding": {
                "generation_1_extension_records": 2,
                "generation_2_after_restage_extension_records": 0,
                "stale_attic_bytes_physically_retained": True,
                "stale_handles_callable": 0,
                "negative_classes": [stale_append, stale_record_rejected],
            },
            "root_publication": {
                "membership_source": "C2I-v2 kinds 3 and 7 only",
                "value_storage": "canonical C2D root_values only",
                "pending_highwater_bytes": 2,
                "gc_after_each_new_heap_allocation": second_append["gc_collections"],
                "writebacks": 0,
            },
            "append_rollback_cutpoints": rollback_rejected,
            "negative_classes": negative_classes,
            "negative_class_count": len(negative_classes),
            "product_gate": contract["product_gate_after_probe"],
        },
        "next_authorized_action": (
            "Owner/reviewer evaluates this green host receipt. Product source and the "
            "real substitution link remain unauthorized until that separate decision."
        ),
    }


def encode_receipt(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def selftest() -> dict[str, Any]:
    value = collect(write_artifacts=False)
    require(value["verified"]["negative_class_count"] == 44,
            "selftest negative closure")
    require(value["verified"]["product_bytes_changed"] == 0,
            "selftest product boundary")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check", "selftest"),
                        nargs="?", default="check")
    args = parser.parse_args()
    if args.mode == "write":
        value = collect(write_artifacts=True)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(encode_receipt(value), encoding="utf-8")
        action = "WROTE"
    else:
        value = collect(write_artifacts=False)
        if args.mode == "check":
            require(RECEIPT.is_file()
                    and RECEIPT.read_text(encoding="utf-8") == encode_receipt(value),
                    "session-extension receipt drift; regenerate with mode 'write'")
            action = "PASS"
        else:
            require(value["verified"]["negative_class_count"] == 44,
                    "selftest negative closure")
            action = "SELFTEST PASS"
    print(
        "c2-session-extension: "
        f"{action} emitter=1 calls=8 static=6 dynamic=2 "
        f"c2d=8/{value['verified']['c2d_v3_after_two_appends']['entries']}/"
        f"{value['verified']['c2d_v3_after_two_appends']['resolutions']}/"
        f"{value['verified']['c2d_v3_after_two_appends']['roots']} "
        f"negatives={value['verified']['negative_class_count']} product-bytes=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProbeError, F.FullError, L.ContractError) as exc:
        print(f"c2-session-extension: FAIL: {exc}")
        raise SystemExit(1)
