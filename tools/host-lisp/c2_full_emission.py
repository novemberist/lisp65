#!/usr/bin/env python3
"""Emit and decode the complete six-image C2I-v2/C2D-v1 host model.

This is still an architecture proof.  It normalizes the current product code
blobs into immutable C2 code regions, lowers every legacy literal through the
owner-approved C2I-v2 contract, builds the exact L65S-v4-direct and C2D-v1
envelopes, and decodes all of them independently.  It does not modify or link
the product runtime.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any, Callable
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c2_direct_proof as V1  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2i-v2-contract.json"
DOCUMENT = ROOT / "docs/planning/c2.1-full-emission.md"
CORE = ROOT / "config/c2-address-identity-contract.json"
ENVELOPE = ROOT / "config/c2-metadata-envelope-proposal.json"
RECURSIVE = ROOT / "config/c2-recursive-literal-proposal.json"
SYMBOL = ROOT / "config/c2-symbol-literal-proposal.json"
SESSION = ROOT / "config/c2-session-directory-proposal.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.1-full-emission-receipt.json"
)
BUILD = ROOT / "build/c2.1/full-emission"

IMAGES = (
    ("stdlib-p0", "stdlib", ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"),
    ("ide", "ide", ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"),
    ("idex", "idex", ROOT / "build/bytecode/dialect-v2/libs/idex.manifest.json"),
    ("m65d", "m65d", ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json"),
    ("buffer", "buffer", ROOT / "build/bytecode/dialect-v2/libs/buffer.manifest.json"),
    ("lcc", "lcc", ROOT / "build/bytecode/dialect-v2/libs/lcc.manifest.json"),
)

HEADER_BYTES = 24
ENTRY_BYTES = 16
LITERAL_BYTES = 8
C2I_VERSION = 2
ANONYMOUS = 0xFFFF
K_NIL = 0
K_TRUE = 1
K_FIXNUM = 2
K_STRING = 3
K_ENTRY = 4
K_EXPORT = 5
K_NATIVE = 6
K_PAIR = 7
K_SYMBOL = 8

SHELF_HEADER_BYTES = 32
SHELF_RECORD_BYTES = 32
SHELF_SPLIT = 1
C2D_HEADER_BYTES = 32
C2D_IMAGE_BYTES = 20
C2D_ENTRY_BYTES = 10
SESSION_GENERATION = 1
BANK5_SESSION_BYTES = 50816


class FullError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FullError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind_path(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def artifact(path: str, data: bytes) -> dict[str, Any]:
    return {"path": path, "bytes": len(data), "sha256": sha(data)}


def p24(value: int) -> bytes:
    require(0 <= value <= 0xFFFFFF, f"u24 overflow: {value}")
    return bytes((value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF))


def u16(data: bytes, at: int) -> int:
    require(at + 2 <= len(data), "truncated u16")
    return data[at] | data[at + 1] << 8


def u24(data: bytes, at: int) -> int:
    require(at + 3 <= len(data), "truncated u24")
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


class StringPool:
    def __init__(self) -> None:
        self.data = bytearray()
        self.offsets: dict[bytes, int] = {}

    def add(self, raw: bytes) -> int:
        require(len(raw) <= 0xFFFF, "C2 string exceeds u16 length")
        if raw not in self.offsets:
            offset = len(self.data)
            require(offset <= 0xFFFFFF, "C2 string offset exceeds u24")
            self.offsets[raw] = offset
            self.data += struct.pack("<H", len(raw)) + raw
        return self.offsets[raw]


@dataclass(frozen=True)
class Desc:
    kind: int
    arg0: int = 0
    arg1: int = 0

    def encode(self) -> bytes:
        require(0 <= self.kind <= K_SYMBOL, "descriptor kind out of range")
        require(0 <= self.arg0 <= 0xFFFF and 0 <= self.arg1 <= 0xFFFFFF,
                "descriptor argument overflow")
        return bytes((self.kind, 0)) + struct.pack("<H", self.arg0) + p24(self.arg1) + b"\0"


@dataclass
class Emitted:
    key: str
    shelf_name: str
    manifest_path: Path
    manifest: dict[str, Any]
    code: bytes
    metadata: bytes
    descriptors: list[Desc]
    old_to_new: dict[int, int]
    entry_first: list[int]
    pair_depth: int
    kind_counts: dict[int, int]
    semantic_checks: int


def canonical_name(raw: bytes) -> bool:
    return 1 <= len(raw) <= 255 and all(0x21 <= byte <= 0x7E for byte in raw)


def legacy_symbol_descriptor_kind(provenance: str) -> int:
    if provenance == "legacy-value":
        return K_SYMBOL
    if provenance == "compiler-proven-export-edge":
        return K_EXPORT
    raise FullError("name spelling is not export provenance")


def normalized_code(manifest: dict[str, Any]) -> bytes:
    blob_path = ROOT / manifest["blob"]
    original = blob_path.read_bytes()
    require(sha(original) == manifest["blob_sha256"], "manifest blob SHA drift")
    require(len(original) == int(manifest["code_bytes"]), "manifest code size drift")
    code = bytearray(original)
    patches = manifest["literal_patches"]
    patch_offsets = [int(row["blob_offset"]) for row in patches]
    require(patch_offsets == sorted(patch_offsets) and len(set(patch_offsets)) == len(patch_offsets),
            "literal patches are not unique and ordered")
    expected: list[tuple[int, int]] = []
    index = manifest["literal_index"]
    cursor = 0
    for ordinal, entry in enumerate(manifest["entries"]):
        start, length = int(entry["blob_offset"]), int(entry["length"])
        require(start == cursor and 0 < length <= 0xFFFF and start + length <= len(code),
                f"entry coverage drift: {ordinal}")
        raw = code[start:start + length]
        require(len(raw) >= 7 and raw[0] == 0xB5, f"bad code header: {ordinal}")
        literals = raw[6]
        require(literals == int(entry["lit_count"]), f"literal count drift: {ordinal}")
        payload = u16(raw, 4)
        require(7 + literals * 2 + payload == length, f"code length equation drift: {ordinal}")
        first = int(entry["lit_first"])
        require(first + literals <= len(index), f"entry literal index range: {ordinal}")
        for local in range(literals):
            expected.append((start + 7 + local * 2, int(index[first + local])))
        cursor += length
    require(cursor == len(code), "entries do not cover code blob")
    actual = [(int(row["blob_offset"]), int(row["node"])) for row in patches]
    require(actual == expected, "code-slot/literal-index binding drift")
    for offset, _node in actual:
        require(offset + 2 <= len(code), "literal slot outside code")
        code[offset:offset + 2] = b"\0\0"
    return bytes(code)


def old_children(manifest: dict[str, Any], node: dict[str, Any]) -> list[int]:
    first, count = int(node["first"]), int(node["count"])
    index = manifest["literal_index"]
    require(first <= len(index) and count <= len(index) - first, "old child range outside index")
    return [int(value) for value in index[first:first + count]]


def fingerprint_atom(tag: bytes, payload: bytes = b"") -> bytes:
    return hashlib.sha256(tag + struct.pack("<I", len(payload)) + payload).digest()


def legacy_fingerprints(manifest: dict[str, Any]) -> list[bytes]:
    result: list[bytes] = []
    for ordinal, node in enumerate(manifest["literal_nodes"]):
        kind = int(node["kind"])
        if kind == 1:
            value = int(node["value"])
            require(-16384 <= value <= 16383, "legacy fixnum outside dialect")
            current = fingerprint_atom(b"F", struct.pack("<h", value))
        elif kind == 2:
            current = fingerprint_atom(b"N")
        elif kind == 3:
            current = fingerprint_atom(b"T")
        elif kind == 4:
            current = fingerprint_atom(b"Y", node["name"].encode("ascii"))
        elif kind == 7:
            current = fingerprint_atom(b"S", node["name"].encode("utf-8"))
        elif kind == 8:
            current = fingerprint_atom(b"E", struct.pack("<H", int(node["first"])))
        elif kind in (5, 6):
            children = old_children(manifest, node)
            require(all(child < ordinal for child in children), "legacy aggregate is not backward-only")
            if kind == 5:
                require(len(children) == 2, "legacy CONS does not have two children")
                current = fingerprint_atom(b"P", result[children[0]] + result[children[1]])
            else:
                current = fingerprint_atom(b"N")
                for child in reversed(children):
                    current = fingerprint_atom(b"P", result[child] + current)
        else:
            raise FullError(f"unsupported legacy literal kind: {kind}")
        result.append(current)
    return result


def emit_image(key: str, shelf_name: str, manifest_path: Path) -> Emitted:
    manifest = load(manifest_path)
    nodes = manifest["literal_nodes"]
    order = [int(value) for value in manifest["literal_index"]]
    require(len(order) == len(nodes) and sorted(order) == list(range(len(nodes))),
            f"literal_index is not a complete permutation: {key}")
    position = {node: index for index, node in enumerate(order)}
    for ordinal, node in enumerate(nodes):
        if int(node["kind"]) in (5, 6):
            require(all(position[child] < position[ordinal] for child in old_children(manifest, node)),
                    f"literal_index is not topological: {key}/{ordinal}")

    pool = StringPool()
    late = set(manifest.get("late_bound_exports", []))
    for entry in manifest["entries"]:
        if not entry.get("anonymous", False):
            raw = entry["name"].encode("ascii")
            require(canonical_name(raw), f"noncanonical export name: {key}/{entry['name']}")
            require(pool.add(raw) < ANONYMOUS, "export-name offset reaches anonymous sentinel")

    descriptors: list[Desc] = []
    old_to_new: dict[int, int] = {}
    prepared_tail: dict[int, int] = {}
    emitted: set[int] = set()
    has_list = any(int(node["kind"]) == 6 for node in nodes)
    nil_index: int | None = None
    if has_list:
        nil_index = len(descriptors)
        descriptors.append(Desc(K_NIL))

    def append(desc: Desc) -> int:
        index = len(descriptors)
        descriptors.append(desc)
        return index

    def prepare_list(node_id: int) -> None:
        if node_id in prepared_tail:
            return
        children = old_children(manifest, nodes[node_id])
        require(children and nil_index is not None, "empty LIST is not present in approved census")
        require(all(child in old_to_new for child in children), "LIST child not emitted before parent")
        tail = nil_index
        for child in reversed(children[1:]):
            tail = append(Desc(K_PAIR, old_to_new[child], tail))
        prepared_tail[node_id] = tail

    def emit_node(node_id: int) -> None:
        require(node_id not in emitted, f"literal node emitted twice: {key}/{node_id}")
        node = nodes[node_id]
        kind = int(node["kind"])
        if kind == 1:
            value = int(node["value"])
            require(-16384 <= value <= 16383, "fixnum outside dialect")
            desc = Desc(K_FIXNUM, value & 0xFFFF)
        elif kind == 2:
            desc = Desc(K_NIL)
        elif kind == 3:
            desc = Desc(K_TRUE)
        elif kind == 4:
            raw = node["name"].encode("ascii")
            require(canonical_name(raw), "general symbol is not canonical ASCII")
            desc = Desc(legacy_symbol_descriptor_kind("legacy-value"), len(raw), pool.add(raw))
        elif kind == 5:
            children = old_children(manifest, node)
            require(len(children) == 2 and all(child in old_to_new for child in children),
                    "CONS children are not available")
            desc = Desc(K_PAIR, old_to_new[children[0]], old_to_new[children[1]])
        elif kind == 6:
            prepare_list(node_id)
            children = old_children(manifest, node)
            desc = Desc(K_PAIR, old_to_new[children[0]], prepared_tail[node_id])
        elif kind == 7:
            raw = node["name"].encode("utf-8")
            desc = Desc(K_STRING, len(raw), pool.add(raw))
        elif kind == 8:
            target = int(node["first"])
            require(0 <= target < len(manifest["entries"]), "entry-ref target outside image")
            desc = Desc(K_ENTRY, target)
        else:
            raise FullError(f"unsupported literal kind: {kind}")
        old_to_new[node_id] = append(desc)
        emitted.add(node_id)

    entries = manifest["entries"]
    entry_first: list[int] = []
    cursor = 0
    for ordinal, entry in enumerate(entries):
        first, count = int(entry["lit_first"]), int(entry["lit_count"])
        require(cursor <= first and first + count <= len(order), f"entry literal order overlap: {key}/{ordinal}")
        while cursor < first:
            emit_node(order[cursor])
            cursor += 1
        roots = order[first:first + count]
        for node_id in roots:
            if int(nodes[node_id]["kind"]) == 6:
                prepare_list(node_id)
        entry_first.append(len(descriptors))
        for node_id in roots:
            emit_node(node_id)
        cursor = first + count
    while cursor < len(order):
        emit_node(order[cursor])
        cursor += 1
    require(len(emitted) == len(nodes), f"literal emission is incomplete: {key}")

    code = normalized_code(manifest)
    entry_blob = bytearray()
    for ordinal, entry in enumerate(entries):
        start, length = int(entry["blob_offset"]), int(entry["length"])
        raw = code[start:start + length]
        anonymous = bool(entry.get("anonymous", False))
        name_offset = ANONYMOUS
        flags = 0
        if not anonymous:
            name = entry["name"].encode("ascii")
            name_offset = pool.add(name)
            require(name_offset < ANONYMOUS, "export name reaches anonymous sentinel")
            if entry.get("kind") == "macro":
                flags |= 1
            if entry["name"] in late:
                flags |= 2
        record = bytearray()
        record += p24(start)
        record += struct.pack("<H", length)
        record += struct.pack("<H", entry_first[ordinal])
        record += bytes((int(entry["lit_count"]),))
        record += struct.pack("<H", name_offset)
        record += bytes((raw[1], flags))
        record += struct.pack("<H", ordinal)
        record += b"\0\0"
        require(len(record) == ENTRY_BYTES, "C2I entry width drift")
        entry_blob += record

    descriptor_blob = b"".join(item.encode() for item in descriptors)
    strings = bytes(pool.data)
    require(len(entries) <= 0xFFFF and len(descriptors) <= 0xFFFF and len(strings) <= 0xFFFF,
            "C2I local count exceeds u16")
    entries_offset = HEADER_BYTES
    literals_offset = entries_offset + len(entry_blob)
    strings_offset = literals_offset + len(descriptor_blob)
    require(strings_offset <= 0xFFFF, "C2I section offset exceeds u16")
    header = bytearray(b"C2I\0")
    header += bytes((C2I_VERSION, HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES))
    header += struct.pack("<HHHHHHHH", 0, len(entries), len(descriptors), entries_offset,
                          literals_offset, strings_offset, len(strings), 0)
    require(len(header) == HEADER_BYTES, "C2I header width drift")
    metadata = bytes(header) + bytes(entry_blob) + descriptor_blob + strings
    if len(metadata) & 1:
        metadata += b"\0"

    decoded = decode_c2i(code, metadata, declared_exports=None)
    legacy = legacy_fingerprints(manifest)
    checks = 0
    for old, expected in enumerate(legacy):
        require(decoded["fingerprints"][old_to_new[old]] == expected,
                f"literal semantic mismatch: {key}/{old}")
        checks += 1
    counts = {kind: 0 for kind in range(K_SYMBOL + 1)}
    for item in descriptors:
        counts[item.kind] += 1
    return Emitted(key, shelf_name, manifest_path, manifest, code, metadata,
                   descriptors, old_to_new, entry_first, decoded["max_pair_depth"],
                   counts, checks)


def string_records(pool: bytes) -> dict[int, bytes]:
    result: dict[int, bytes] = {}
    cursor = 0
    while cursor < len(pool):
        length = u16(pool, cursor)
        end = cursor + 2 + length
        require(end <= len(pool), "string record crosses pool")
        result[cursor] = pool[cursor + 2:end]
        cursor = end
    return result


def decode_c2i(code: bytes, metadata: bytes, declared_exports: set[bytes] | None) -> dict[str, Any]:
    require(len(metadata) >= HEADER_BYTES, "metadata shorter than C2I header")
    require(metadata[:4] == b"C2I\0" and metadata[4] == C2I_VERSION,
            "C2I-v2 decoder rejects magic or version")
    require(tuple(metadata[5:8]) == (HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES),
            "C2I record width mismatch")
    require(u16(metadata, 8) == 0 and u16(metadata, 22) == 0, "C2I header flags/reserved")
    entry_count, literal_count = u16(metadata, 10), u16(metadata, 12)
    entries_offset, literals_offset, strings_offset = u16(metadata, 14), u16(metadata, 16), u16(metadata, 18)
    strings_bytes = u16(metadata, 20)
    require(entries_offset == HEADER_BYTES, "C2I entry section is not contiguous")
    require(literals_offset == entries_offset + entry_count * ENTRY_BYTES,
            "C2I literal section arithmetic")
    require(strings_offset == literals_offset + literal_count * LITERAL_BYTES,
            "C2I string section arithmetic")
    unaligned = strings_offset + strings_bytes
    require((unaligned + 1) & ~1 == len(metadata), "C2I total length mismatch")
    if unaligned != len(metadata):
        require(metadata[-1] == 0, "C2I nonzero alignment byte")
    records = string_records(metadata[strings_offset:unaligned])
    descriptors: list[Desc] = []
    fingerprints: list[bytes] = []
    depths: list[int] = []
    max_depth = 0
    for index in range(literal_count):
        at = literals_offset + index * LITERAL_BYTES
        kind, flags = metadata[at], metadata[at + 1]
        arg0, arg1, reserved = u16(metadata, at + 2), u24(metadata, at + 4), metadata[at + 7]
        require(kind <= K_SYMBOL, "unknown C2I-v2 literal kind")
        require(flags == 0 and reserved == 0, "nonzero literal flags/reserved")
        if kind in (K_NIL, K_TRUE):
            require(arg0 == 0 and arg1 == 0, "immediate has nonzero argument")
            fp, depth = fingerprint_atom(b"N" if kind == K_NIL else b"T"), 0
        elif kind == K_FIXNUM:
            signed = arg0 - 0x10000 if arg0 & 0x8000 else arg0
            require(-16384 <= signed <= 16383 and arg1 == 0, "fixnum descriptor invalid")
            fp, depth = fingerprint_atom(b"F", struct.pack("<h", signed)), 0
        elif kind in (K_STRING, K_EXPORT, K_SYMBOL):
            require(arg1 in records and len(records[arg1]) == arg0, "string descriptor invalid")
            raw = records[arg1]
            if kind in (K_EXPORT, K_SYMBOL):
                require(canonical_name(raw), "symbol/export name is not canonical")
            if kind == K_EXPORT and declared_exports is not None:
                require(raw in declared_exports, "kind-5 edge names undeclared export")
            tag = b"S" if kind == K_STRING else (b"X" if kind == K_EXPORT else b"Y")
            fp, depth = fingerprint_atom(tag, raw), 0
        elif kind == K_ENTRY:
            require(arg0 < entry_count and arg1 == 0, "entry-ref descriptor invalid")
            fp, depth = fingerprint_atom(b"E", struct.pack("<H", arg0)), 0
        elif kind == K_NATIVE:
            require(arg1 == 0, "native descriptor unused argument")
            fp, depth = fingerprint_atom(b"R", struct.pack("<H", arg0)), 0
        else:
            require(arg0 < index and arg1 < index and arg1 <= 0xFFFF,
                    "pair descriptor is not strictly backward")
            fp = fingerprint_atom(b"P", fingerprints[arg0] + fingerprints[arg1])
            depth = max(depths[arg0], depths[arg1]) + 1
            max_depth = max(max_depth, depth)
        descriptors.append(Desc(kind, arg0, arg1))
        fingerprints.append(fp)
        depths.append(depth)

    late_bound: set[int] = set()
    entries = []
    for ordinal in range(entry_count):
        at = entries_offset + ordinal * ENTRY_BYTES
        code_offset, code_length = u24(metadata, at), u16(metadata, at + 3)
        first, count = u16(metadata, at + 5), metadata[at + 7]
        name_offset, arity, flags = u16(metadata, at + 8), metadata[at + 10], metadata[at + 11]
        diagnostic, reserved = u16(metadata, at + 12), u16(metadata, at + 14)
        require(code_length and code_offset + code_length <= len(code), "entry code range invalid")
        require(first + count <= literal_count, "entry resolution range invalid")
        require(flags & ~3 == 0 and reserved == 0, "entry flags/reserved invalid")
        if name_offset == ANONYMOUS:
            require(flags == 0, "anonymous entry has export flags")
        else:
            require(name_offset in records and canonical_name(records[name_offset]), "entry export name invalid")
        if flags & 2:
            late_bound.add(ordinal)
        raw = code[code_offset:code_offset + code_length]
        require(len(raw) >= 7 and raw[0] == 0xB5, "entry code header invalid")
        payload, code_literals = u16(raw, 4), raw[6]
        require(raw[1] == arity and code_literals == count, "entry/header arity or literal count")
        require(7 + code_literals * 2 + payload == code_length, "entry code length equation")
        require(all(byte == 0 for byte in raw[7:7 + 2 * code_literals]),
                "immutable code literal slots are nonzero")
        entries.append((code_offset, code_length, first, count, diagnostic))
    for item in descriptors:
        if item.kind == K_ENTRY:
            require(item.arg0 not in late_bound, "ordinal targets late-bound export")
    return {"entries": entries, "descriptors": descriptors, "fingerprints": fingerprints,
            "max_pair_depth": max_depth, "strings": records}


def build_shelf(images: list[Emitted]) -> tuple[bytes, list[dict[str, int]], int]:
    payload_offset = SHELF_HEADER_BYTES + len(images) * SHELF_RECORD_BYTES
    code_cursor = payload_offset
    metadata_cursor = code_cursor + sum(len(image.code) for image in images)
    catalog = bytearray()
    rows: list[dict[str, int]] = []
    for image in images:
        name = (image.shelf_name.encode("ascii") + b"\0").ljust(8, b"\0")
        require(len(name) == 8, "shelf name does not fit record")
        record = bytearray(SHELF_RECORD_BYTES)
        record[:8] = name
        record[8:11] = p24(code_cursor)
        struct.pack_into("<H", record, 11, len(image.code))
        record[13:16] = p24(metadata_cursor)
        struct.pack_into("<H", record, 16, len(image.metadata))
        struct.pack_into("<I", record, 18, zlib.crc32(image.code) & 0xFFFFFFFF)
        struct.pack_into("<I", record, 22, zlib.crc32(image.metadata) & 0xFFFFFFFF)
        struct.pack_into("<I", record, 26, zlib.crc32(image.code + image.metadata) & 0xFFFFFFFF)
        record[30] = SHELF_SPLIT
        catalog += record
        rows.append({"code_offset": code_cursor, "metadata_offset": metadata_cursor,
                     "code_length": len(image.code), "metadata_length": len(image.metadata)})
        code_cursor += len(image.code)
        metadata_cursor += len(image.metadata)
    payload = b"".join(image.code for image in images) + b"".join(image.metadata for image in images)
    total = payload_offset + len(payload)
    build_id = int.from_bytes(hashlib.sha256(bytes(catalog) + payload).digest()[:4], "little")
    header = bytearray(SHELF_HEADER_BYTES)
    header[:8] = b"L65S" + bytes((4, SHELF_HEADER_BYTES, SHELF_RECORD_BYTES, len(images)))
    struct.pack_into("<H", header, 8, SHELF_HEADER_BYTES)
    header[10:13] = p24(payload_offset)
    header[13:16] = p24(total)
    struct.pack_into("<H", header, 16, len(catalog))
    struct.pack_into("<I", header, 18, zlib.crc32(catalog) & 0xFFFFFFFF)
    struct.pack_into("<I", header, 22, build_id)
    struct.pack_into("<H", header, 26, SHELF_SPLIT)
    shelf = bytes(header) + bytes(catalog) + payload
    require(len(shelf) == total, "shelf layout did not close")
    return shelf, rows, zlib.crc32(catalog) & 0xFFFFFFFF


def build_c2d(images: list[Emitted], shelf_rows: list[dict[str, int]], catalog_crc: int) -> bytes:
    image_blob = bytearray()
    entry_blob = bytearray()
    resolution_blob = bytearray()
    directory_base = 0
    resolution_base = 0
    for slot, (image, shelf) in enumerate(zip(images, shelf_rows)):
        record = bytearray()
        record += bytes((slot, 0))
        record += struct.pack("<HHHH", directory_base, len(image.manifest["entries"]),
                              resolution_base, len(image.descriptors))
        record += p24(shelf["code_offset"]) + p24(shelf["metadata_offset"])
        record += struct.pack("<HH", shelf["code_length"], shelf["metadata_length"])
        require(len(record) == C2D_IMAGE_BYTES, "C2D image width drift")
        image_blob += record
        for ordinal, entry in enumerate(image.manifest["entries"]):
            item = bytearray((slot, 0))
            item += struct.pack("<HHHH", ordinal, int(entry["length"]),
                                resolution_base + image.entry_first[ordinal], SESSION_GENERATION)
            require(len(item) == C2D_ENTRY_BYTES, "C2D entry width drift")
            entry_blob += item
        for _descriptor in image.descriptors:
            token = len(resolution_blob) // 2 + 1
            require(token <= 0x7FFF, "host resolution token overflow")
            resolution_blob += struct.pack("<H", token)
        directory_base += len(image.manifest["entries"])
        resolution_base += len(image.descriptors)
    images_offset = C2D_HEADER_BYTES
    entries_offset = images_offset + len(image_blob)
    resolutions_offset = entries_offset + len(entry_blob)
    total = resolutions_offset + len(resolution_blob)
    require(total <= BANK5_SESSION_BYTES and total <= 0xFFFF, "C2D exceeds Bank-5 session region")
    header = bytearray(b"C2D\0")
    header += bytes((1, C2D_HEADER_BYTES, C2D_IMAGE_BYTES, C2D_ENTRY_BYTES))
    header += struct.pack("<HHHHHHHHHHI", 0, SESSION_GENERATION, len(images), directory_base,
                          resolution_base, images_offset, entries_offset, resolutions_offset,
                          total, 0, catalog_crc)
    require(len(header) == C2D_HEADER_BYTES, "C2D header width drift")
    return bytes(header) + bytes(image_blob) + bytes(entry_blob) + bytes(resolution_blob)


def decode_c2d(data: bytes, images: list[Emitted], shelf_rows: list[dict[str, int]], catalog_crc: int) -> dict[str, int]:
    require(len(data) >= C2D_HEADER_BYTES and data[:4] == b"C2D\0" and data[4] == 1,
            "bad C2D magic or version")
    require(tuple(data[5:8]) == (C2D_HEADER_BYTES, C2D_IMAGE_BYTES, C2D_ENTRY_BYTES),
            "C2D record width mismatch")
    require(u16(data, 8) == 0 and u16(data, 10) != 0, "C2D flags/generation invalid")
    image_count, entry_count, resolution_count = u16(data, 12), u16(data, 14), u16(data, 16)
    images_offset, entries_offset, resolutions_offset, total = u16(data, 18), u16(data, 20), u16(data, 22), u16(data, 24)
    require(u16(data, 26) == 0 and struct.unpack_from("<I", data, 28)[0] == catalog_crc,
            "C2D reserved/catalog identity invalid")
    require(image_count == len(images) and entry_count == sum(len(x.manifest["entries"]) for x in images)
            and resolution_count == sum(len(x.descriptors) for x in images), "C2D count mismatch")
    require(images_offset == C2D_HEADER_BYTES, "C2D image offset mismatch")
    require(entries_offset == images_offset + image_count * C2D_IMAGE_BYTES, "C2D entry arithmetic")
    require(resolutions_offset == entries_offset + entry_count * C2D_ENTRY_BYTES, "C2D resolution arithmetic")
    require(total == resolutions_offset + resolution_count * 2 == len(data), "C2D total arithmetic")
    directory_base = resolution_base = 0
    for slot, (image, shelf) in enumerate(zip(images, shelf_rows)):
        at = images_offset + slot * C2D_IMAGE_BYTES
        require(data[at] == slot and data[at + 1] == 0, "C2D image slot/flags")
        require(u16(data, at + 2) == directory_base and u16(data, at + 4) == len(image.manifest["entries"]),
                "C2D image directory range")
        require(u16(data, at + 6) == resolution_base and u16(data, at + 8) == len(image.descriptors),
                "C2D image resolution range")
        require(u24(data, at + 10) == shelf["code_offset"] and u24(data, at + 13) == shelf["metadata_offset"],
                "C2D image region offset")
        require(u16(data, at + 16) == shelf["code_length"] and u16(data, at + 18) == shelf["metadata_length"],
                "C2D image region length")
        for ordinal, entry in enumerate(image.manifest["entries"]):
            pos = entries_offset + (directory_base + ordinal) * C2D_ENTRY_BYTES
            require(data[pos] == slot and data[pos + 1] == 0 and u16(data, pos + 2) == ordinal,
                    "C2D entry identity")
            require(u16(data, pos + 4) == int(entry["length"]), "C2D/C2I entry length mismatch")
            require(u16(data, pos + 6) == resolution_base + image.entry_first[ordinal],
                    "C2D entry resolution base")
            require(u16(data, pos + 8) == SESSION_GENERATION, "C2D entry generation")
        directory_base += len(image.manifest["entries"])
        resolution_base += len(image.descriptors)
    return {"images": image_count, "entries": entry_count, "resolutions": resolution_count,
            "bytes": total, "headroom": BANK5_SESSION_BYTES - total}


def declared_exports(images: list[Emitted]) -> set[bytes]:
    return {name.encode("ascii") for image in images for name in image.manifest.get("exports", [])}


def verify_shelf(shelf: bytes, images: list[Emitted], exports: set[bytes]) -> None:
    require(shelf[:4] == b"L65S" and shelf[4] == 4, "C2 shelf version")
    require(tuple(shelf[5:7]) == (SHELF_HEADER_BYTES, SHELF_RECORD_BYTES), "shelf widths")
    count = shelf[7]
    payload = u24(shelf, 10)
    require(count == len(images) and payload == SHELF_HEADER_BYTES + count * SHELF_RECORD_BYTES,
            "shelf count/payload")
    require(u24(shelf, 13) == len(shelf), "shelf total")
    catalog = shelf[SHELF_HEADER_BYTES:payload]
    require(u16(shelf, 16) == len(catalog) and zlib.crc32(catalog) & 0xFFFFFFFF == struct.unpack_from("<I", shelf, 18)[0],
            "shelf catalog identity")
    require(u16(shelf, 26) == SHELF_SPLIT and shelf[28:32] == b"\0" * 4, "shelf flags/reserved")
    for slot, image in enumerate(images):
        record = catalog[slot * SHELF_RECORD_BYTES:(slot + 1) * SHELF_RECORD_BYTES]
        code_at, code_len, meta_at, meta_len = u24(record, 8), u16(record, 11), u24(record, 13), u16(record, 16)
        code, metadata = shelf[code_at:code_at + code_len], shelf[meta_at:meta_at + meta_len]
        require(code == image.code and metadata == image.metadata, "shelf region binding")
        require(zlib.crc32(code) & 0xFFFFFFFF == struct.unpack_from("<I", record, 18)[0], "shelf code CRC")
        require(zlib.crc32(metadata) & 0xFFFFFFFF == struct.unpack_from("<I", record, 22)[0], "shelf metadata CRC")
        require(zlib.crc32(code + metadata) & 0xFFFFFFFF == struct.unpack_from("<I", record, 26)[0], "shelf image CRC")
        decode_c2i(code, metadata, exports)


def contract_check() -> None:
    contract = load(CONTRACT)
    require(contract.get("status") == "owner-approved-full-composition-emission-authorized",
            "C2I-v2 contract not authorized")
    require(contract["header"] == {"magic": "C2I\\0", "format_version": 2,
                                   "header_bytes": 24, "entry_bytes": 16,
                                   "literal_bytes": 8, "flags": 0}, "C2I-v2 header contract drift")
    kinds = contract["literal_kinds"]
    require([row["id"] for row in kinds] == list(range(9)) and kinds[7]["name"] == "backward-cons-pair"
            and kinds[8]["name"] == "general-symbol-name-offset-u24", "C2I-v2 kind table drift")
    require("only kind 5" in contract["symbol_provenance"]["call_graph_consumers"]
            and "Kind 8 is invisible" in contract["symbol_provenance"]["call_graph_consumers"],
            "call-graph consumer boundary drift")
    require(load(RECURSIVE)["status"] == "owner-approved-option-a-c2i-v2-authorized"
            and load(SYMBOL)["status"] == "owner-approved-option-a-c2i-v2-authorized"
            and load(SESSION)["status"] == "owner-approved-option-a-product-layout-authorized",
            "C2 prerequisite approval missing")


def build_all() -> tuple[list[Emitted], bytes, bytes, dict[str, Any]]:
    contract_check()
    images = [emit_image(*row) for row in IMAGES]
    require(sum(len(x.manifest["entries"]) for x in images) == 583, "full entry census drift")
    require(sum(len(x.manifest["literal_nodes"]) for x in images) == 2084, "old literal census drift")
    require(sum(len(x.descriptors) for x in images) == 2249, "lowered descriptor census drift")
    require(sum(x.kind_counts[K_SYMBOL] for x in images) == 979, "general-symbol lowering drift")
    require(sum(x.kind_counts[K_EXPORT] for x in images) == 0, "spelling fabricated kind-5 edges")
    require(sum(x.kind_counts[K_PAIR] for x in images) == 168, "cons lowering count drift")
    require(sum(x.kind_counts[K_NIL] for x in images) == 1, "shared lowering NIL drift")
    require(max(x.pair_depth for x in images) == 74, "pair depth drift")
    shelf, shelf_rows, catalog_crc = build_shelf(images)
    exports = declared_exports(images)
    verify_shelf(shelf, images, exports)
    c2d = build_c2d(images, shelf_rows, catalog_crc)
    c2d_facts = decode_c2d(c2d, images, shelf_rows, catalog_crc)
    require(c2d_facts == {"images": 6, "entries": 583, "resolutions": 2249,
                          "bytes": 10480, "headroom": 40336}, "C2D final arithmetic drift")
    facts = {
        "images": 6,
        "entries": 583,
        "legacy_literal_nodes": 2084,
        "c2i_v2_descriptors": 2249,
        "semantic_node_checks": sum(x.semantic_checks for x in images),
        "general_symbol_kind8": 979,
        "proven_export_edges_kind5": 0,
        "cons_pairs_kind7": 168,
        "lowering_nil_descriptors": 1,
        "maximum_pair_depth": 74,
        "resolver_passes": 1,
        "decoder_recursion": 0,
        "sharing_fixture_same_descriptor": sharing_fixture(),
        "c2d": c2d_facts,
    }
    return images, shelf, c2d, facts


def expect(label: str, operation: Callable[[], Any], fragment: str) -> str:
    try:
        operation()
    except FullError as error:
        require(fragment in str(error), f"{label} wrong diagnostic: {error}")
        return label
    raise FullError(f"{label} mutation accepted")


def symbol_fixture(raw: bytes) -> tuple[bytes, bytes]:
    pool = struct.pack("<H", len(raw)) + raw
    descriptor = Desc(K_SYMBOL, len(raw), 0).encode()
    entries_offset = HEADER_BYTES
    literals_offset = entries_offset
    strings_offset = literals_offset + LITERAL_BYTES
    header = bytearray(b"C2I\0")
    header += bytes((C2I_VERSION, HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES))
    header += struct.pack("<HHHHHHHH", 0, 0, 1, entries_offset, literals_offset,
                          strings_offset, len(pool), 0)
    metadata = bytes(header) + descriptor + pool
    if len(metadata) & 1:
        metadata += b"\0"
    return b"", metadata


def v1_decode_v2(code: bytes, metadata: bytes) -> None:
    try:
        V1.decode_image(code, metadata)
    except V1.ProofError as error:
        raise FullError(str(error)) from error


def sharing_fixture() -> bool:
    # (shared shared): both pair cars retain descriptor ordinal 1.
    descriptors = [Desc(K_NIL), Desc(K_SYMBOL, 6, 0),
                   Desc(K_PAIR, 1, 0), Desc(K_PAIR, 1, 2)]
    pool = struct.pack("<H", 6) + b"shared"
    header = bytearray(b"C2I\0")
    header += bytes((C2I_VERSION, HEADER_BYTES, ENTRY_BYTES, LITERAL_BYTES))
    header += struct.pack("<HHHHHHHH", 0, 0, len(descriptors), HEADER_BYTES,
                          HEADER_BYTES, HEADER_BYTES + len(descriptors) * LITERAL_BYTES,
                          len(pool), 0)
    metadata = bytes(header) + b"".join(item.encode() for item in descriptors) + pool
    decoded = decode_c2i(b"", metadata, set())
    values = decoded["descriptors"]
    return values[2].arg0 == values[3].arg0 == 1


def negative_matrix(images: list[Emitted]) -> list[str]:
    ide = next(image for image in images if image.key == "ide")
    exports = declared_exports(images)
    labels: list[str] = []
    meta = ide.metadata
    literals = u16(meta, 16)
    pair = next(i for i, item in enumerate(ide.descriptors) if item.kind == K_PAIR)
    symbol = next(i for i, item in enumerate(ide.descriptors) if item.kind == K_SYMBOL)
    pair_at, symbol_at = literals + pair * LITERAL_BYTES, literals + symbol * LITERAL_BYTES

    bad = bytearray(meta); bad[4] = 1
    labels.append(expect("v1-presented-to-v2", lambda: decode_c2i(ide.code, bytes(bad), exports), "rejects magic or version"))
    labels.append(expect("v2-presented-to-v1", lambda: v1_decode_v2(ide.code, meta), "bad C2I magic or version"))
    bad = bytearray(meta); struct.pack_into("<H", bad, pair_at + 2, pair)
    labels.append(expect("pair-self-reference", lambda: decode_c2i(ide.code, bytes(bad), exports), "strictly backward"))
    bad = bytearray(meta); struct.pack_into("<H", bad, pair_at + 2, pair + 1)
    labels.append(expect("pair-forward-reference", lambda: decode_c2i(ide.code, bytes(bad), exports), "strictly backward"))
    bad = bytearray(meta); bad[symbol_at + 1] = 1
    labels.append(expect("kind8-flags", lambda: decode_c2i(ide.code, bytes(bad), exports), "flags/reserved"))
    bad = bytearray(meta); bad[symbol_at] = K_EXPORT
    labels.append(expect("spelling-is-not-export-provenance", lambda: decode_c2i(ide.code, bytes(bad), exports), "undeclared export"))
    bad = bytearray(meta); bad[symbol_at + 4:symbol_at + 7] = p24(1)
    labels.append(expect("kind8-nonboundary-offset", lambda: decode_c2i(ide.code, bytes(bad), exports), "string descriptor"))
    bad = bytearray(meta); struct.pack_into("<H", bad, symbol_at + 2, u16(bad, symbol_at + 2) + 1)
    labels.append(expect("kind8-length-mismatch", lambda: decode_c2i(ide.code, bytes(bad), exports), "string descriptor"))
    labels.append(expect("kind8-empty-name", lambda: decode_c2i(*symbol_fixture(b""), exports), "not canonical"))
    labels.append(expect("kind8-name-over-255", lambda: decode_c2i(*symbol_fixture(b"a" * 256), exports), "not canonical"))
    labels.append(expect("kind8-nonascii-name", lambda: decode_c2i(*symbol_fixture(b"\x80"), exports), "not canonical"))
    labels.append(expect("kind8-whitespace-name", lambda: decode_c2i(*symbol_fixture(b"a b"), exports), "not canonical"))
    labels.append(expect("spelling-provenance-rejected", lambda: legacy_symbol_descriptor_kind("spelling-match"), "spelling is not export provenance"))
    bad = bytearray(meta); struct.pack_into("<H", bad, HEADER_BYTES + 3, 0)
    labels.append(expect("zero-entry-length", lambda: decode_c2i(ide.code, bytes(bad), exports), "entry code range"))
    bad = bytearray(meta); bad[0:4] = b"C2X\0"
    labels.append(expect("bad-magic", lambda: decode_c2i(ide.code, bytes(bad), exports), "rejects magic or version"))
    require(len(labels) == 15, "negative matrix closure")
    return labels


def write_outputs(out: Path, images: list[Emitted], shelf: bytes, c2d: bytes) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for image in images:
        (out / f"{image.key}.code.bin").write_bytes(image.code)
        (out / f"{image.key}.c2i.bin").write_bytes(image.metadata)
    (out / "product-shelf-v4-direct.bin").write_bytes(shelf)
    (out / "session-directory-c2d-v1.bin").write_bytes(c2d)


def collect(out: Path) -> dict[str, Any]:
    images, shelf, c2d, facts = build_all()
    negatives = negative_matrix(images)
    write_outputs(out, images, shelf, c2d)
    rows = []
    for image in images:
        rows.append({
            "key": image.key,
            "entries": len(image.manifest["entries"]),
            "legacy_nodes": len(image.manifest["literal_nodes"]),
            "c2i_v2_descriptors": len(image.descriptors),
            "kind8_symbols": image.kind_counts[K_SYMBOL],
            "kind7_pairs": image.kind_counts[K_PAIR],
            "maximum_pair_depth": image.pair_depth,
            "code": artifact(f"build/c2.1/full-emission/{image.key}.code.bin", image.code),
            "metadata": artifact(f"build/c2.1/full-emission/{image.key}.c2i.bin", image.metadata),
        })
    return {
        "format": "lisp65-c2.1-full-emission-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "host-emission-and-decode-passed-product-link-not-run",
        "claim_limit": (
            "This receipt proves complete six-image C2I-v2 emission/decoding, canonical "
            "literal lowering, strict kind-5/kind-8 separation, the L65S-v4-direct host "
            "envelope and exact C2D-v1 arithmetic. It changes no product byte, authorizes "
            "no capacity, and does not claim a target decoder, product link or device run."
        ),
        "bindings": {
            "contract": bind_path(CONTRACT), "document": bind_path(DOCUMENT),
            "core": bind_path(CORE),
            "envelope": bind_path(ENVELOPE), "recursive": bind_path(RECURSIVE),
            "symbol": bind_path(SYMBOL), "session": bind_path(SESSION),
            "verifier": bind_path(Path(__file__)),
            "manifests": [bind_path(path) for _key, _name, path in IMAGES],
        },
        "facts": facts,
        "images": rows,
        "artifacts": {
            "shelf": artifact("build/c2.1/full-emission/product-shelf-v4-direct.bin", shelf),
            "session_directory": artifact("build/c2.1/full-emission/session-directory-c2d-v1.bin", c2d),
        },
        "negative_matrix": {"passed": len(negatives), "cases": negatives},
        "consumer_gate": {
            "call_evidence_kind": 5,
            "general_symbol_kind": 8,
            "kind5_edges_in_legacy_conversion": 0,
            "kind8_nodes_in_legacy_conversion": 979,
            "name_equality_used_as_provenance": False,
        },
        "product_bytes_changed": 0,
        "capacity_delta": "not-applicable-host-architecture-proof",
        "next_action": "Independent target decoder and real product-layout substitution link",
    }


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def selftest() -> None:
    images, _shelf, _c2d, facts = build_all()
    require(facts["semantic_node_checks"] == 2084 and facts["decoder_recursion"] == 0,
            "semantic/iterative closure")
    require(len(negative_matrix(images)) == 15 and sharing_fixture(), "negative/sharing closure")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
        print("c2-full-emission: SELFTEST PASS semantics=2084 negatives=15 recursion=0 sharing=1")
        return 0
    if args.action == "write":
        data = canonical(collect(BUILD))
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(data, encoding="utf-8")
        verb = "WROTE"
    else:
        with tempfile.TemporaryDirectory(prefix="lisp65-c2-full-") as raw:
            data = canonical(collect(Path(raw)))
        require(RECEIPT.is_file() and RECEIPT.read_text(encoding="utf-8") == data,
                "C2 full-emission receipt drift; regenerate with write")
        verb = "PASS"
    print(f"c2-full-emission: {verb} images=6 entries=583 descriptors=2249 c2d=10480")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
