#!/usr/bin/env python3
"""Independent validator for the normative lisp65 L65M disk-lib contract."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "bytecode" / "formats" / "p0-disk-lib-v1.json"
FIXTURE_FORMAT = "lisp65-disk-lib-container-cases-v1"

HEADER_BYTES = 38
MAX_CODE_OBJECT_BYTES = 255
MAX_GRAPH_DEPTH = 9
CODE_MAGIC = 0xB5

TOP_KEYS = {"format", "description", "goldens", "cases"}
GOLDEN_KEYS = {"id", "image_hex", "sha256", "expect"}
SUMMARY_KEYS = {
    "bytes",
    "blob_bytes",
    "metadata_bytes",
    "entry_names",
    "macro_entries",
    "literal_indices",
    "literal_nodes",
    "literal_patches",
    "max_literal_depth",
}
CASE_KEYS = {"id", "base", "mutations", "expect"}

ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_RE = re.compile(r"^(?:[0-9a-f]{2})*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ERROR_CODES = (
    "container-too-short",
    "container-length-mismatch",
    "metadata-too-short",
    "metadata-not-aligned",
    "bad-magic",
    "unsupported-version",
    "bad-header-size",
    "nonzero-header-flags",
    "nonzero-code-base",
    "header-code-length-mismatch",
    "header-metadata-length-mismatch",
    "nonzero-header-reserved",
    "empty-entry-table",
    "noncanonical-section-layout",
    "noncanonical-metadata-size",
    "nonzero-metadata-padding",
    "unterminated-string",
    "invalid-utf8",
    "invalid-string-offset",
    "empty-entry-name",
    "entry-name-too-long",
    "duplicate-entry-name",
    "nonzero-entry-bank",
    "unknown-entry-flags",
    "noncontiguous-entry",
    "entry-out-of-bounds",
    "code-object-too-large",
    "bad-code-magic",
    "missing-strict-arity",
    "optional-without-strict-arity",
    "optional-count-exceeds-nargs",
    "variadic-without-rest-local",
    "code-object-length-mismatch",
    "blob-not-covered",
    "literal-index-out-of-range",
    "invalid-node-kind",
    "nonzero-node-reserved",
    "invalid-fixnum",
    "invalid-node-fields",
    "invalid-node-name",
    "node-index-range",
    "literal-graph-cycle",
    "literal-graph-too-deep",
    "patch-coverage-mismatch",
    "patch-target-not-literal",
    "duplicate-patch-target",
    "patch-order-mismatch",
    "patch-node-out-of-range",
)
ERROR_CODE_SET = frozenset(ERROR_CODES)

RUNTIME_STATUS_BY_ERROR = {
    "container-too-short": "L65M_ERR_CONTAINER",
    "container-length-mismatch": "L65M_ERR_CONTAINER",
    "metadata-too-short": "L65M_ERR_HEADER",
    "metadata-not-aligned": "L65M_ERR_SECTIONS",
    "bad-magic": "L65M_ERR_HEADER",
    "unsupported-version": "L65M_ERR_HEADER",
    "bad-header-size": "L65M_ERR_HEADER",
    "nonzero-header-flags": "L65M_ERR_HEADER",
    "nonzero-code-base": "L65M_ERR_HEADER",
    "header-code-length-mismatch": "L65M_ERR_HEADER",
    "header-metadata-length-mismatch": "L65M_ERR_HEADER",
    "nonzero-header-reserved": "L65M_ERR_HEADER",
    "empty-entry-table": "L65M_ERR_ENTRIES",
    "noncanonical-section-layout": "L65M_ERR_SECTIONS",
    "noncanonical-metadata-size": "L65M_ERR_SECTIONS",
    "nonzero-metadata-padding": "L65M_ERR_SECTIONS",
    "unterminated-string": "L65M_ERR_STRINGS",
    "invalid-utf8": "L65M_ERR_STRINGS",
    "invalid-string-offset": "L65M_ERR_STRINGS",
    "empty-entry-name": "L65M_ERR_STRINGS",
    "entry-name-too-long": "L65M_ERR_STRINGS",
    "duplicate-entry-name": "L65M_ERR_ENTRIES",
    "nonzero-entry-bank": "L65M_ERR_ENTRIES",
    "unknown-entry-flags": "L65M_ERR_ENTRIES",
    "noncontiguous-entry": "L65M_ERR_ENTRIES",
    "entry-out-of-bounds": "L65M_ERR_ENTRIES",
    "code-object-too-large": "L65M_ERR_CODE",
    "bad-code-magic": "L65M_ERR_CODE",
    "missing-strict-arity": "L65M_ERR_CODE",
    "optional-without-strict-arity": "L65M_ERR_CODE",
    "optional-count-exceeds-nargs": "L65M_ERR_CODE",
    "variadic-without-rest-local": "L65M_ERR_CODE",
    "code-object-length-mismatch": "L65M_ERR_CODE",
    "blob-not-covered": "L65M_ERR_ENTRIES",
    "literal-index-out-of-range": "L65M_ERR_INDEX",
    "invalid-node-kind": "L65M_ERR_NODE",
    "nonzero-node-reserved": "L65M_ERR_NODE",
    "invalid-fixnum": "L65M_ERR_NODE",
    "invalid-node-fields": "L65M_ERR_NODE",
    "invalid-node-name": "L65M_ERR_STRINGS",
    "node-index-range": "L65M_ERR_NODE",
    "literal-graph-cycle": "L65M_ERR_GRAPH",
    "literal-graph-too-deep": "L65M_ERR_GRAPH",
    "patch-coverage-mismatch": "L65M_ERR_PATCH",
    "patch-target-not-literal": "L65M_ERR_PATCH",
    "duplicate-patch-target": "L65M_ERR_PATCH",
    "patch-order-mismatch": "L65M_ERR_PATCH",
    "patch-node-out-of-range": "L65M_ERR_PATCH",
}

if set(RUNTIME_STATUS_BY_ERROR) != ERROR_CODE_SET:
    raise RuntimeError("runtime status mapping must cover every contract error exactly")


class ContractError(ValueError):
    """A byte image violates one stable L65M contract rule."""

    def __init__(self, code: str, detail: str):
        if code not in ERROR_CODE_SET:
            raise ValueError(f"unknown internal error code: {code}")
        super().__init__(detail)
        self.code = code


class FixtureError(ValueError):
    """The JSON case fixture itself is malformed or internally inconsistent."""


@dataclass(frozen=True)
class Summary:
    bytes: int
    blob_bytes: int
    metadata_bytes: int
    entry_names: list[str]
    macro_entries: list[str]
    literal_indices: int
    literal_nodes: int
    literal_patches: int
    max_literal_depth: int


@dataclass(frozen=True)
class Node:
    kind: int
    value: int
    first: int
    count: int
    name_off: int


@dataclass(frozen=True)
class Golden:
    id: str
    image: bytes
    sha256: str
    expect: dict[str, Any]


@dataclass(frozen=True)
class FixtureCase:
    id: str
    base: str
    mutations: list[dict[str, Any]]
    valid: bool
    error: str | None


@dataclass(frozen=True)
class Fixture:
    goldens: dict[str, Golden]
    cases: list[FixtureCase]


@dataclass(frozen=True)
class MaterializedCase:
    id: str
    image: bytes
    valid: bool
    error: str | None
    expected_entry_count: int
    expected_patch_count: int
    expected_macro_count: int


def _raise(code: str, detail: str) -> None:
    raise ContractError(code, detail)


def _need(data: bytes, offset: int, size: int, code: str, label: str) -> None:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        _raise(code, f"{label} needs bytes [{offset},{offset + size}), size={len(data)}")


def _u8(data: bytes, offset: int, code: str, label: str) -> int:
    _need(data, offset, 1, code, label)
    return data[offset]


def _u16(data: bytes, offset: int, code: str, label: str) -> int:
    _need(data, offset, 2, code, label)
    return data[offset] | (data[offset + 1] << 8)


def _i16(data: bytes, offset: int, code: str, label: str) -> int:
    value = _u16(data, offset, code, label)
    return value - 0x10000 if value & 0x8000 else value


def _u32(data: bytes, offset: int, code: str, label: str) -> int:
    _need(data, offset, 4, code, label)
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def _align2(value: int) -> int:
    return (value + 1) & ~1


def _exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FixtureError(f"{label} must be an object")
    actual = set(value)
    missing = sorted(keys - actual)
    unknown = sorted(actual - keys)
    if missing:
        raise FixtureError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise FixtureError(f"{label} has unknown keys: {', '.join(unknown)}")
    return value


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise FixtureError(f"{label} must be a non-empty NUL-free string")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _nonempty_string(value, label)
    if not ID_RE.fullmatch(value):
        raise FixtureError(f"{label} must match {ID_RE.pattern!r}")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise FixtureError(f"{label} must be an integer >= {minimum}")
    return value


def _hex_bytes(value: Any, label: str, *, allow_empty: bool = False) -> bytes:
    if not isinstance(value, str) or not HEX_RE.fullmatch(value):
        raise FixtureError(f"{label} must be canonical lowercase even-length hex")
    if not value and not allow_empty:
        raise FixtureError(f"{label} must not be empty")
    return bytes.fromhex(value)


def _load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FixtureError(f"cannot read fixture {path}: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_strict_object)
    except FixtureError:
        raise
    except json.JSONDecodeError as exc:
        raise FixtureError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def _string_pool(pool: bytes) -> dict[int, tuple[bytes, str]]:
    strings: dict[int, tuple[bytes, str]] = {}
    pos = 0
    while pos < len(pool):
        end = pool.find(b"\x00", pos)
        if end < 0:
            _raise("unterminated-string", f"string at pool offset {pos} has no NUL terminator")
        raw = pool[pos:end]
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            _raise("invalid-utf8", f"string at pool offset {pos}: {exc}")
        strings[pos] = (raw, text)
        pos = end + 1
    return strings


def _lookup_string(
    strings: dict[int, tuple[bytes, str]],
    offset: int,
    label: str,
    *,
    allow_empty: bool,
    max_bytes: int | None = None,
) -> tuple[bytes, str]:
    if offset == 0xFFFF or offset not in strings:
        _raise("invalid-string-offset", f"{label} offset {offset} is not a string start")
    raw, text = strings[offset]
    if not allow_empty and not raw:
        _raise("invalid-node-name", f"{label} must not be empty")
    if max_bytes is not None and len(raw) > max_bytes:
        _raise("invalid-node-name", f"{label} has {len(raw)} bytes, maximum is {max_bytes}")
    return raw, text


def validate_image(image: bytes, *, require_strict_arity: bool = False) -> Summary:
    """Validate one complete disk-lib image without using any producer code."""

    data = bytes(image)
    if len(data) < 4:
        _raise("container-too-short", f"container has {len(data)} bytes, need at least 4")
    blob_len = _u16(data, 0, "container-too-short", "blob_len")
    metadata_len = _u16(data, 2, "container-too-short", "metadata_len")
    expected_file_len = 4 + blob_len + metadata_len
    if len(data) != expected_file_len:
        _raise(
            "container-length-mismatch",
            f"prefix requires {expected_file_len} bytes, file has {len(data)}",
        )

    blob = data[4 : 4 + blob_len]
    metadata = data[4 + blob_len :]
    if metadata_len < HEADER_BYTES:
        _raise("metadata-too-short", f"metadata has {metadata_len} bytes, need {HEADER_BYTES}")
    if metadata_len & 1:
        _raise("metadata-not-aligned", f"metadata length {metadata_len} is not align2")

    if metadata[0:4] != b"L65M":
        _raise("bad-magic", f"metadata magic is {metadata[0:4]!r}")
    version = _u8(metadata, 4, "metadata-too-short", "version")
    if version != 1:
        _raise("unsupported-version", f"version is {version}, expected 1")
    header_size = _u8(metadata, 5, "metadata-too-short", "header_size")
    if header_size != HEADER_BYTES:
        _raise("bad-header-size", f"header size is {header_size}, expected {HEADER_BYTES}")
    flags = _u16(metadata, 6, "metadata-too-short", "flags")
    if flags != 0:
        _raise("nonzero-header-flags", f"header flags are 0x{flags:04x}")
    code_base = _u32(metadata, 8, "metadata-too-short", "code_base")
    if code_base != 0:
        _raise("nonzero-code-base", f"disk-lib code base is 0x{code_base:08x}")
    header_blob_len = _u16(metadata, 12, "metadata-too-short", "code_bytes")
    if header_blob_len != blob_len:
        _raise(
            "header-code-length-mismatch",
            f"header code length {header_blob_len}, prefix {blob_len}",
        )
    header_metadata_len = _u16(metadata, 14, "metadata-too-short", "metadata_bytes")
    if header_metadata_len != metadata_len:
        _raise(
            "header-metadata-length-mismatch",
            f"header metadata length {header_metadata_len}, prefix {metadata_len}",
        )

    entry_count = _u16(metadata, 16, "metadata-too-short", "entry_count")
    index_count = _u16(metadata, 18, "metadata-too-short", "literal_index_count")
    node_count = _u16(metadata, 20, "metadata-too-short", "literal_node_count")
    patch_count = _u16(metadata, 22, "metadata-too-short", "literal_patch_count")
    entries_off = _u16(metadata, 24, "metadata-too-short", "entries_off")
    index_off = _u16(metadata, 26, "metadata-too-short", "literal_index_off")
    nodes_off = _u16(metadata, 28, "metadata-too-short", "literal_nodes_off")
    patches_off = _u16(metadata, 30, "metadata-too-short", "literal_patches_off")
    strings_off = _u16(metadata, 32, "metadata-too-short", "strings_off")
    strings_bytes = _u16(metadata, 34, "metadata-too-short", "strings_bytes")
    reserved = _u16(metadata, 36, "metadata-too-short", "reserved")
    if reserved != 0:
        _raise("nonzero-header-reserved", f"reserved header word is 0x{reserved:04x}")
    if entry_count == 0:
        _raise("empty-entry-table", "disk-lib must contain at least one entry")

    canonical_entries = HEADER_BYTES
    canonical_index = _align2(canonical_entries + entry_count * 8)
    canonical_nodes = _align2(canonical_index + index_count * 2)
    canonical_patches = _align2(canonical_nodes + node_count * 10)
    canonical_strings = _align2(canonical_patches + patch_count * 4)
    actual_offsets = (entries_off, index_off, nodes_off, patches_off, strings_off)
    canonical_offsets = (
        canonical_entries,
        canonical_index,
        canonical_nodes,
        canonical_patches,
        canonical_strings,
    )
    if actual_offsets != canonical_offsets:
        _raise(
            "noncanonical-section-layout",
            f"section offsets {actual_offsets}, expected {canonical_offsets}",
        )
    canonical_metadata_len = _align2(canonical_strings + strings_bytes)
    if metadata_len != canonical_metadata_len:
        _raise(
            "noncanonical-metadata-size",
            f"metadata length {metadata_len}, expected {canonical_metadata_len}",
        )
    strings_end = strings_off + strings_bytes
    if any(metadata[strings_end:]):
        _raise("nonzero-metadata-padding", "metadata align2 padding must be zero")

    strings = _string_pool(metadata[strings_off:strings_end])
    entry_names: list[str] = []
    macro_entries: list[str] = []
    seen_names: set[str] = set()
    literal_slots: list[int] = []
    cursor = 0

    for entry_index in range(entry_count):
        at = entries_off + entry_index * 8
        name_off = _u16(metadata, at, "noncanonical-section-layout", "entry.name_off")
        bank = _u8(metadata, at + 2, "noncanonical-section-layout", "entry.bank")
        entry_flags = _u8(metadata, at + 3, "noncanonical-section-layout", "entry.flags")
        offset = _u16(metadata, at + 4, "noncanonical-section-layout", "entry.off")
        length = _u16(metadata, at + 6, "noncanonical-section-layout", "entry.len")

        raw_name, name = _lookup_string(
            strings, name_off, f"entry[{entry_index}].name", allow_empty=True
        )
        if not raw_name:
            _raise("empty-entry-name", f"entry[{entry_index}] has an empty name")
        if len(raw_name) > 32:
            _raise(
                "entry-name-too-long",
                f"entry[{entry_index}] name has {len(raw_name)} bytes, maximum is 32",
            )
        if name in seen_names:
            _raise("duplicate-entry-name", f"duplicate entry name {name!r}")
        seen_names.add(name)
        entry_names.append(name)
        if bank != 0:
            _raise("nonzero-entry-bank", f"entry[{entry_index}] bank is {bank}, expected 0")
        if entry_flags & ~1:
            _raise(
                "unknown-entry-flags",
                f"entry[{entry_index}] flags are 0x{entry_flags:02x}",
            )
        if entry_flags & 1:
            macro_entries.append(name)
        if offset != cursor:
            _raise(
                "noncontiguous-entry",
                f"entry[{entry_index}] starts at {offset}, expected {cursor}",
            )
        if length < 7 or offset > blob_len or length > blob_len - offset:
            _raise(
                "entry-out-of-bounds",
                f"entry[{entry_index}] range [{offset},{offset + length}) exceeds blob {blob_len}",
            )
        if length > MAX_CODE_OBJECT_BYTES:
            _raise(
                "code-object-too-large",
                f"entry[{entry_index}] has {length} bytes, maximum is {MAX_CODE_OBJECT_BYTES}",
            )

        code = blob[offset : offset + length]
        if code[0] != CODE_MAGIC:
            _raise("bad-code-magic", f"entry[{entry_index}] code magic is 0x{code[0]:02x}")
        code_flags = code[3]
        optional_count = code_flags >> 2
        if require_strict_arity and not (code_flags & 2):
            _raise(
                "missing-strict-arity",
                f"entry[{entry_index}] lacks dialect-v2 STRICT_ARITY",
            )
        if optional_count and not (code_flags & 2):
            _raise(
                "optional-without-strict-arity",
                f"entry[{entry_index}] optional arity lacks STRICT_ARITY",
            )
        if optional_count > code[1]:
            _raise(
                "optional-count-exceeds-nargs",
                f"entry[{entry_index}] optional count exceeds nargs",
            )
        if code_flags & 1 and code[2] == 0:
            _raise(
                "variadic-without-rest-local",
                f"entry[{entry_index}] is variadic with nlocals=0",
            )
        payload_len = code[4] | (code[5] << 8)
        literal_count = code[6]
        expected_code_len = 7 + 2 * literal_count + payload_len
        if length != expected_code_len:
            _raise(
                "code-object-length-mismatch",
                f"entry[{entry_index}] length {length}, code header requires {expected_code_len}",
            )
        for literal_index in range(literal_count):
            literal_slots.append(offset + 7 + 2 * literal_index)
        cursor += length

    if cursor != blob_len:
        _raise("blob-not-covered", f"entries cover {cursor} of {blob_len} blob bytes")

    indices = [
        _u16(metadata, index_off + index * 2, "noncanonical-section-layout", "literal_index")
        for index in range(index_count)
    ]
    for index, node_index in enumerate(indices):
        if node_index >= node_count:
            _raise(
                "literal-index-out-of-range",
                f"literal_index[{index}]={node_index}, node_count={node_count}",
            )

    nodes: list[Node] = []
    for node_index in range(node_count):
        at = nodes_off + node_index * 10
        kind = _u8(metadata, at, "noncanonical-section-layout", "node.kind")
        node_reserved = _u8(metadata, at + 1, "noncanonical-section-layout", "node.reserved")
        value = _i16(metadata, at + 2, "noncanonical-section-layout", "node.value")
        first = _u16(metadata, at + 4, "noncanonical-section-layout", "node.first")
        count = _u16(metadata, at + 6, "noncanonical-section-layout", "node.count")
        name_off = _u16(metadata, at + 8, "noncanonical-section-layout", "node.name_off")
        if not 1 <= kind <= 7:
            _raise("invalid-node-kind", f"node[{node_index}] kind is {kind}")
        if node_reserved != 0:
            _raise(
                "nonzero-node-reserved",
                f"node[{node_index}] reserved byte is {node_reserved}",
            )

        if kind == 1:
            if not -16384 <= value <= 16383:
                _raise("invalid-fixnum", f"node[{node_index}] FIX value is {value}")
            if first != 0 or count != 0 or name_off != 0xFFFF:
                _raise("invalid-node-fields", f"node[{node_index}] FIX fields are noncanonical")
        elif kind in {2, 3}:
            if value != 0 or first != 0 or count != 0 or name_off != 0xFFFF:
                _raise("invalid-node-fields", f"node[{node_index}] immediate fields are noncanonical")
        elif kind == 4:
            if value != 0 or first != 0 or count != 0:
                _raise("invalid-node-fields", f"node[{node_index}] SYMBOL fields are noncanonical")
            _lookup_string(
                strings,
                name_off,
                f"node[{node_index}].symbol",
                allow_empty=False,
                max_bytes=32,
            )
        elif kind == 5:
            if value != 0 or count != 2 or name_off != 0xFFFF:
                _raise("invalid-node-fields", f"node[{node_index}] CONS fields are noncanonical")
            if first > index_count or 2 > index_count - first:
                _raise("node-index-range", f"node[{node_index}] CONS child range is out of bounds")
        elif kind == 6:
            if value != 0 or name_off != 0xFFFF:
                _raise("invalid-node-fields", f"node[{node_index}] LIST fields are noncanonical")
            if first > index_count or count > index_count - first:
                _raise("node-index-range", f"node[{node_index}] LIST child range is out of bounds")
        else:
            if value != 0 or first != 0 or count != 0:
                _raise("invalid-node-fields", f"node[{node_index}] STRING fields are noncanonical")
            _lookup_string(
                strings,
                name_off,
                f"node[{node_index}].string",
                allow_empty=True,
            )
        nodes.append(Node(kind, value, first, count, name_off))

    colors = [0] * node_count
    depths = [0] * node_count

    def visit(node_index: int, parent_depth: int) -> int:
        depth = parent_depth + 1
        if depth > MAX_GRAPH_DEPTH:
            _raise(
                "literal-graph-too-deep",
                f"literal graph exceeds depth {MAX_GRAPH_DEPTH} at node {node_index}",
            )
        if colors[node_index] == 1:
            _raise("literal-graph-cycle", f"literal graph cycles at node {node_index}")
        if colors[node_index] == 2:
            total_depth = parent_depth + depths[node_index]
            if total_depth > MAX_GRAPH_DEPTH:
                _raise(
                    "literal-graph-too-deep",
                    f"literal graph exceeds depth {MAX_GRAPH_DEPTH} at node {node_index}",
                )
            return depths[node_index]
        colors[node_index] = 1
        node = nodes[node_index]
        child_depth = 0
        if node.kind in {5, 6}:
            for child_index in indices[node.first : node.first + node.count]:
                child_depth = max(child_depth, visit(child_index, depth))
        colors[node_index] = 2
        depths[node_index] = 1 + child_depth
        return depths[node_index]

    max_depth = 0
    for node_index in range(node_count):
        max_depth = max(max_depth, visit(node_index, 0))

    if patch_count != len(literal_slots):
        _raise(
            "patch-coverage-mismatch",
            f"patch_count={patch_count}, literal slots={len(literal_slots)}",
        )
    literal_slot_set = set(literal_slots)
    seen_patch_targets: set[int] = set()
    for patch_index in range(patch_count):
        at = patches_off + patch_index * 4
        blob_offset = _u16(metadata, at, "noncanonical-section-layout", "patch.blob_offset")
        node_index = _u16(metadata, at + 2, "noncanonical-section-layout", "patch.node")
        if blob_offset in seen_patch_targets:
            _raise(
                "duplicate-patch-target",
                f"patch[{patch_index}] duplicates blob offset {blob_offset}",
            )
        if blob_offset not in literal_slot_set:
            _raise(
                "patch-target-not-literal",
                f"patch[{patch_index}] target {blob_offset} is not a littab slot",
            )
        if blob_offset != literal_slots[patch_index]:
            _raise(
                "patch-order-mismatch",
                f"patch[{patch_index}] target {blob_offset}, expected {literal_slots[patch_index]}",
            )
        if node_index >= node_count:
            _raise(
                "patch-node-out-of-range",
                f"patch[{patch_index}] node {node_index}, node_count={node_count}",
            )
        seen_patch_targets.add(blob_offset)

    return Summary(
        bytes=len(data),
        blob_bytes=blob_len,
        metadata_bytes=metadata_len,
        entry_names=entry_names,
        macro_entries=macro_entries,
        literal_indices=index_count,
        literal_nodes=node_count,
        literal_patches=patch_count,
        max_literal_depth=max_depth,
    )


def _parse_summary(value: Any, label: str) -> dict[str, Any]:
    summary = _exact_object(value, SUMMARY_KEYS, label)
    result: dict[str, Any] = {}
    for key in (
        "bytes",
        "blob_bytes",
        "metadata_bytes",
        "literal_indices",
        "literal_nodes",
        "literal_patches",
        "max_literal_depth",
    ):
        result[key] = _integer(summary[key], f"{label}.{key}")
    for key in ("entry_names", "macro_entries"):
        values = summary[key]
        if not isinstance(values, list):
            raise FixtureError(f"{label}.{key} must be a list")
        parsed = [_nonempty_string(item, f"{label}.{key}[{index}]") for index, item in enumerate(values)]
        if len(parsed) != len(set(parsed)):
            raise FixtureError(f"{label}.{key} contains duplicate names")
        result[key] = parsed
    return result


def _parse_mutation(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FixtureError(f"{label} must be an object")
    op = value.get("op")
    if op == "replace":
        mutation = _exact_object(value, {"op", "offset", "hex"}, label)
        payload = _hex_bytes(mutation["hex"], f"{label}.hex")
        return {
            "op": op,
            "offset": _integer(mutation["offset"], f"{label}.offset"),
            "hex": payload,
        }
    if op == "truncate":
        mutation = _exact_object(value, {"op", "length"}, label)
        return {"op": op, "length": _integer(mutation["length"], f"{label}.length")}
    if op == "append":
        mutation = _exact_object(value, {"op", "hex"}, label)
        return {"op": op, "hex": _hex_bytes(mutation["hex"], f"{label}.hex")}
    raise FixtureError(f"{label}.op must be replace, truncate, or append")


def load_fixture(path: Path) -> Fixture:
    data = _exact_object(_load_json(path), TOP_KEYS, "fixture")
    if data["format"] != FIXTURE_FORMAT:
        raise FixtureError(f"fixture.format must be {FIXTURE_FORMAT!r}")
    _nonempty_string(data["description"], "fixture.description")

    raw_goldens = data["goldens"]
    if not isinstance(raw_goldens, list) or not raw_goldens:
        raise FixtureError("fixture.goldens must be a non-empty list")
    goldens: dict[str, Golden] = {}
    for index, raw in enumerate(raw_goldens):
        label = f"fixture.goldens[{index}]"
        value = _exact_object(raw, GOLDEN_KEYS, label)
        golden_id = _identifier(value["id"], f"{label}.id")
        if golden_id in goldens:
            raise FixtureError(f"duplicate golden id {golden_id!r}")
        image = _hex_bytes(value["image_hex"], f"{label}.image_hex")
        sha256 = _nonempty_string(value["sha256"], f"{label}.sha256")
        if not SHA256_RE.fullmatch(sha256):
            raise FixtureError(f"{label}.sha256 must be lowercase SHA-256 hex")
        actual_sha256 = hashlib.sha256(image).hexdigest()
        if actual_sha256 != sha256:
            raise FixtureError(
                f"{label}.sha256 mismatch: fixture={sha256}, bytes={actual_sha256}"
            )
        expect = _parse_summary(value["expect"], f"{label}.expect")
        goldens[golden_id] = Golden(golden_id, image, sha256, expect)

    raw_cases = data["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise FixtureError("fixture.cases must be a non-empty list")
    cases: list[FixtureCase] = []
    case_ids: set[str] = set()
    valid_bases: set[str] = set()
    for index, raw in enumerate(raw_cases):
        label = f"fixture.cases[{index}]"
        value = _exact_object(raw, CASE_KEYS, label)
        case_id = _identifier(value["id"], f"{label}.id")
        if case_id in case_ids:
            raise FixtureError(f"duplicate case id {case_id!r}")
        case_ids.add(case_id)
        base = _identifier(value["base"], f"{label}.base")
        if base not in goldens:
            raise FixtureError(f"{label}.base references unknown golden {base!r}")
        raw_mutations = value["mutations"]
        if not isinstance(raw_mutations, list):
            raise FixtureError(f"{label}.mutations must be a list")
        mutations = [
            _parse_mutation(mutation, f"{label}.mutations[{mutation_index}]")
            for mutation_index, mutation in enumerate(raw_mutations)
        ]
        expect = value["expect"]
        if not isinstance(expect, dict) or expect.get("status") not in {"valid", "invalid"}:
            raise FixtureError(f"{label}.expect.status must be valid or invalid")
        if expect["status"] == "valid":
            _exact_object(expect, {"status"}, f"{label}.expect")
            if mutations:
                raise FixtureError(f"{label} valid case must not mutate its golden")
            valid = True
            error = None
            valid_bases.add(base)
        else:
            _exact_object(expect, {"status", "error"}, f"{label}.expect")
            error = _nonempty_string(expect["error"], f"{label}.expect.error")
            if error not in ERROR_CODE_SET:
                raise FixtureError(f"{label}.expect.error has unknown code {error!r}")
            if not mutations:
                raise FixtureError(f"{label} invalid case must contain a mutation")
            valid = False
        cases.append(FixtureCase(case_id, base, mutations, valid, error))
    missing_valid = sorted(set(goldens) - valid_bases)
    if missing_valid:
        raise FixtureError(f"goldens without a valid case: {', '.join(missing_valid)}")
    return Fixture(goldens, cases)


def materialize_case(fixture: Fixture, case: FixtureCase) -> MaterializedCase:
    golden = fixture.goldens[case.base]
    data = bytearray(golden.image)
    for mutation_index, mutation in enumerate(case.mutations):
        label = f"case {case.id!r} mutation[{mutation_index}]"
        if mutation["op"] == "replace":
            offset = mutation["offset"]
            payload = mutation["hex"]
            if offset > len(data) or len(payload) > len(data) - offset:
                raise FixtureError(f"{label} replacement exceeds {len(data)} bytes")
            data[offset : offset + len(payload)] = payload
        elif mutation["op"] == "truncate":
            length = mutation["length"]
            if length >= len(data):
                raise FixtureError(f"{label} length must be smaller than {len(data)}")
            del data[length:]
        else:
            data.extend(mutation["hex"])
    if case.valid:
        expected_entry_count = len(golden.expect["entry_names"])
        expected_patch_count = golden.expect["literal_patches"]
        expected_macro_count = len(golden.expect["macro_entries"])
    else:
        expected_entry_count = 0
        expected_patch_count = 0
        expected_macro_count = 0
    return MaterializedCase(
        case.id,
        bytes(data),
        case.valid,
        case.error,
        expected_entry_count,
        expected_patch_count,
        expected_macro_count,
    )


def materialize_fixture(fixture: Fixture) -> list[MaterializedCase]:
    return [materialize_case(fixture, case) for case in fixture.cases]


def check_fixture(path: Path) -> tuple[Fixture, list[MaterializedCase]]:
    fixture = load_fixture(path)
    for golden in fixture.goldens.values():
        try:
            summary = validate_image(golden.image)
        except ContractError as exc:
            raise FixtureError(f"golden {golden.id!r} is invalid: {exc.code}: {exc}") from exc
        actual = asdict(summary)
        if actual != golden.expect:
            raise FixtureError(
                f"golden {golden.id!r} summary mismatch: expected={golden.expect!r} actual={actual!r}"
            )

    materialized = materialize_fixture(fixture)
    for case in materialized:
        try:
            validate_image(case.image)
        except ContractError as exc:
            if case.valid:
                raise FixtureError(f"case {case.id!r} unexpectedly failed: {exc.code}: {exc}") from exc
            if exc.code != case.error:
                raise FixtureError(
                    f"case {case.id!r} error mismatch: expected={case.error!r} actual={exc.code!r}: {exc}"
                ) from exc
        else:
            if not case.valid:
                raise FixtureError(f"case {case.id!r} unexpectedly passed; expected {case.error}")
    return fixture, materialized


def render_c_header(cases: list[MaterializedCase]) -> str:
    lines = [
        "/* generated by tools/host-lisp/l65m_contract.py; do not edit */",
        "#ifndef LISP65_L65M_CONTRACT_CASES_H",
        "#define LISP65_L65M_CONTRACT_CASES_H",
        "",
        "#include <stdint.h>",
        '#include "l65m_validate.h"',
        "",
        "typedef struct {",
        "    const char *name;",
        "    const uint8_t *data;",
        "    uint16_t len;",
        "    uint8_t valid;",
        "    l65m_status expected_status;",
        "    uint16_t expected_entry_count;",
        "    uint16_t expected_patch_count;",
        "    uint16_t expected_macro_count;",
        "} l65m_contract_case;",
        "",
    ]
    for index, case in enumerate(cases):
        lines.append(f"static const uint8_t l65m_contract_data_{index}[] = {{")
        for offset in range(0, len(case.image), 12):
            chunk = case.image[offset : offset + 12]
            lines.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
        lines.extend(["};", ""])
    lines.append("static const l65m_contract_case l65m_contract_cases[] = {")
    for index, case in enumerate(cases):
        expected_status = "L65M_OK" if case.error is None else RUNTIME_STATUS_BY_ERROR[case.error]
        lines.append(
            "    { %s, l65m_contract_data_%d, %d, %d, %s, %d, %d, %d },"
            % (
                json.dumps(case.id),
                index,
                len(case.image),
                1 if case.valid else 0,
                expected_status,
                case.expected_entry_count,
                case.expected_patch_count,
                case.expected_macro_count,
            )
        )
    lines.extend(
        [
            "};",
            f"static const uint16_t l65m_contract_case_count = {len(cases)}u;",
            "",
            "#endif /* LISP65_L65M_CONTRACT_CASES_H */",
            "",
        ]
    )
    return "\n".join(lines)


def selftest() -> int:
    minimal = bytes.fromhex(
        "09003200b50000000200002b054c36354d01260000000000000900320001000000"
        "0000000026002e002e002e002e0003000000000000000000090069640000"
    )
    summary = validate_image(minimal)
    if summary.entry_names != ["id"] or summary.blob_bytes != 9:
        raise AssertionError(f"unexpected minimal summary: {summary}")
    try:
        validate_image(minimal, require_strict_arity=True)
    except ContractError as exc:
        if exc.code != "missing-strict-arity":
            raise AssertionError(f"wrong strict-profile code: {exc.code}") from exc
    else:
        raise AssertionError("v2 profile accepted a legacy CodeObject")
    strict_minimal = bytearray(minimal)
    strict_minimal[7] = 2
    strict_summary = validate_image(
        strict_minimal, require_strict_arity=True
    )
    if strict_summary.entry_names != ["id"]:
        raise AssertionError("v2 profile rejected a strict CodeObject")
    bad = bytearray(minimal)
    bad[13] = ord("X")
    try:
        validate_image(bad)
    except ContractError as exc:
        if exc.code != "bad-magic":
            raise AssertionError(f"wrong bad-magic code: {exc.code}") from exc
    else:
        raise AssertionError("bad magic passed")
    try:
        json.loads('{"x":1,"x":2}', object_pairs_hook=_strict_object)
    except FixtureError:
        pass
    else:
        raise AssertionError("duplicate JSON key passed")
    rendered = render_c_header([MaterializedCase("minimal", minimal, True, None, 1, 0, 0)])
    if (
        "static const uint16_t l65m_contract_case_count = 1u;" not in rendered
        or "l65m_contract_data_0" not in rendered
        or "L65M_OK, 1, 0, 0" not in rendered
    ):
        raise AssertionError("C header rendering failed")
    print("l65m-contract selftest: PASS cases=4")
    return 0


def _fixture_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("selftest", help="run isolated parser tests")
    check = commands.add_parser("check-fixture", help="run all normative golden and mutation cases")
    check.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    output = check.add_mutually_exclusive_group()
    output.add_argument("--emit-c-header", type=Path)
    output.add_argument("--check-c-header", type=Path)
    validate = commands.add_parser("validate", help="validate one materialized disk-lib image")
    validate.add_argument("image", type=Path)
    validate.add_argument("--require-strict-arity", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.command == "selftest":
        try:
            return selftest()
        except (AssertionError, ContractError, FixtureError) as exc:
            print(f"l65m-contract selftest: FAIL: {exc}", file=sys.stderr)
            return 1

    if args.command == "validate":
        try:
            data = args.image.read_bytes()
        except OSError as exc:
            print(f"l65m-contract: FAIL infrastructure: cannot read {args.image}: {exc}", file=sys.stderr)
            return 2
        try:
            summary = validate_image(
                data, require_strict_arity=args.require_strict_arity
            )
        except ContractError as exc:
            print(f"l65m-contract: INVALID error={exc.code} detail={exc}", file=sys.stderr)
            return 1
        print("l65m-contract: VALID " + json.dumps(asdict(summary), sort_keys=True))
        return 0

    path = _fixture_path(args.fixture)
    try:
        fixture, cases = check_fixture(path)
        header = render_c_header(cases)
        if args.emit_c_header is not None:
            args.emit_c_header.parent.mkdir(parents=True, exist_ok=True)
            args.emit_c_header.write_text(header, encoding="ascii")
        elif args.check_c_header is not None:
            try:
                actual = args.check_c_header.read_text(encoding="ascii")
            except (OSError, UnicodeError) as exc:
                raise FixtureError(f"cannot read C header {args.check_c_header}: {exc}") from exc
            if actual != header:
                raise FixtureError(f"C header is stale: {args.check_c_header}")
    except FixtureError as exc:
        print(f"l65m-contract: FIXTURE FAIL: {exc}", file=sys.stderr)
        return 1
    valid = sum(case.valid for case in cases)
    invalid = len(cases) - valid
    print(
        f"l65m-contract: PASS goldens={len(fixture.goldens)} "
        f"cases={len(cases)} valid={valid} invalid={invalid}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
