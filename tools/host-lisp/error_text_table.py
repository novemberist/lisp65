#!/usr/bin/env python3
"""Build and verify a profile-bound sparse L65E-v1 error-text table."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import Any, Sequence


SCHEMA = "lisp65-error-texts-v1"
MAGIC = b"L65E"
VERSION = 1
HEADER_FORMAT = "<4sBBBBIHH"
HEADER_BYTES = struct.calcsize(HEADER_FORMAT)
CRC_OFFSET = 14
FLAG_OFFSET_INDEX = 0x01
FLAG_SPARSE = 0x02
FLAG_SHARED_REFS = 0x04
FLAG_FORMAT_MASK = 0x0F
PROFILE_SHIFT = 4
TEXT_REF_OFFSET_BITS = 10
TEXT_REF_OFFSET_MASK = (1 << TEXT_REF_OFFSET_BITS) - 1
TEXT_REF_LENGTH_SHIFT = TEXT_REF_OFFSET_BITS
TEXT_REF_LENGTH_MAX = (1 << (16 - TEXT_REF_OFFSET_BITS)) - 1
COMPILE_SENTINEL_CODES = tuple(range(49, 60))
COMPILE_SENTINEL_TEXT = "compile failed"
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
C_NAME_RE = re.compile(r"^LISP65_ERR_[A-Z][A-Z0-9_]*$")
AUDIENCES = {"user", "internal", "not-built"}
DELIVERIES = {"overlay", "resident-only"}
ROOT_KEYS = {
    "schema", "format", "version", "encoding", "selection_policy",
    "profiles", "future_contract", "entries",
}
POLICY_KEYS = {"rule", "omission", "fallback"}
POLICY = {
    "rule": "user-reachable-requires-text",
    "omission": "internal-invariant-or-not-built-only",
    "fallback": "Ehh-preserves-stable-code",
}
PROFILE_KEYS = {
    "id", "binary_id", "description", "required_audiences",
    "excluded_audiences",
}
FUTURE_KEYS = {"new_codes", "ap6_persistence", "required_workbench_domains"}
FUTURE_VALUES = {
    "new_codes": "explicit-classification-required",
    "ap6_persistence":
        "every-future-user-reachable-persistence-or-disk-code-requires-workbench-text",
}
ENTRY_KEYS = {
    "code", "id", "c_name", "text", "domain", "audience", "reason", "profiles",
}


class ErrorTextTableError(RuntimeError):
    """A deterministic specification or table failure."""


@dataclass(frozen=True)
class ErrorText:
    code: int
    id: str
    c_name: str
    text: str
    domain: str
    audience: str
    reason: str
    profiles: tuple[str, ...]
    delivery: str


@dataclass(frozen=True)
class ErrorProfile:
    id: str
    binary_id: int
    required_audiences: frozenset[str]
    excluded_audiences: frozenset[str]


@dataclass(frozen=True)
class ErrorTextSpec:
    profiles: tuple[ErrorProfile, ...]
    required_workbench_domains: frozenset[str]
    entries: tuple[ErrorText, ...]

    def profile(self, profile_id: str) -> ErrorProfile:
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        raise ErrorTextTableError(f"unknown error-text profile: {profile_id}")


@dataclass(frozen=True)
class ErrorTextTable:
    build_id: int
    profile: ErrorProfile
    entries: tuple[ErrorText, ...]
    active_codes: tuple[int, ...]
    data: bytes
    crc16: int


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ErrorTextTableError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unknown {', '.join(unknown)}")
        raise ErrorTextTableError(f"{label} has {'; '.join(details)}")


def _string_list(value: Any, label: str, allowed: set[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ErrorTextTableError(f"{label} must be a string list")
    if len(set(value)) != len(value):
        raise ErrorTextTableError(f"{label} contains duplicates")
    if allowed is not None and not set(value) <= allowed:
        raise ErrorTextTableError(f"{label} contains an unknown value")
    return tuple(value)


def _read_spec(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ErrorTextTableError(f"spec must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except ErrorTextTableError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ErrorTextTableError(f"cannot read error-text spec {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ErrorTextTableError("spec root must be an object")
    return value


def load_spec(path: Path) -> ErrorTextSpec:
    raw = _read_spec(path)
    _exact_keys(raw, ROOT_KEYS, "spec")
    if raw["schema"] != SCHEMA or raw["format"] != "L65E":
        raise ErrorTextTableError("spec schema or format is not L65E v1")
    if type(raw["version"]) is not int or raw["version"] != VERSION:
        raise ErrorTextTableError("spec version must be 1")
    if raw["encoding"] != "ascii":
        raise ErrorTextTableError("L65E v1 only accepts ASCII text")

    policy = raw["selection_policy"]
    if not isinstance(policy, dict):
        raise ErrorTextTableError("selection_policy must be an object")
    _exact_keys(policy, POLICY_KEYS, "selection_policy")
    if policy != POLICY:
        raise ErrorTextTableError("selection_policy does not state the pinned selection rule")

    future = raw["future_contract"]
    if not isinstance(future, dict):
        raise ErrorTextTableError("future_contract must be an object")
    _exact_keys(future, FUTURE_KEYS, "future_contract")
    for key, expected in FUTURE_VALUES.items():
        if future[key] != expected:
            raise ErrorTextTableError(f"future_contract.{key} is not pinned")
    required_domains = frozenset(
        _string_list(future["required_workbench_domains"],
                     "future_contract.required_workbench_domains")
    )
    if not required_domains:
        raise ErrorTextTableError("future contract must name required Workbench domains")

    raw_profiles = raw["profiles"]
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ErrorTextTableError("profiles must be a non-empty list")
    profiles: list[ErrorProfile] = []
    profile_ids: set[str] = set()
    binary_ids: set[int] = set()
    for index, value in enumerate(raw_profiles):
        label = f"profiles[{index}]"
        if not isinstance(value, dict):
            raise ErrorTextTableError(f"{label} must be an object")
        _exact_keys(value, PROFILE_KEYS, label)
        ident = value["id"]
        binary_id = value["binary_id"]
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise ErrorTextTableError(f"{label}.id is not canonical")
        if type(binary_id) is not int or not 0 <= binary_id <= 15:
            raise ErrorTextTableError(f"{label}.binary_id must be in 0..15")
        if ident in profile_ids or binary_id in binary_ids:
            raise ErrorTextTableError("profile IDs and binary IDs must be unique")
        if not isinstance(value["description"], str) or not value["description"]:
            raise ErrorTextTableError(f"{label}.description must be non-empty")
        required = frozenset(_string_list(
            value["required_audiences"], f"{label}.required_audiences", AUDIENCES
        ))
        excluded = frozenset(_string_list(
            value["excluded_audiences"], f"{label}.excluded_audiences", AUDIENCES
        ))
        if required & excluded:
            raise ErrorTextTableError(f"{label} requires and excludes the same audience")
        profile_ids.add(ident)
        binary_ids.add(binary_id)
        profiles.append(ErrorProfile(ident, binary_id, required, excluded))
    if "workbench" not in profile_ids:
        raise ErrorTextTableError("the pinned spec requires a workbench profile")

    raw_entries = raw["entries"]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ErrorTextTableError("entries must be a non-empty list")
    if len(raw_entries) > 255:
        raise ErrorTextTableError("L65E v1 supports at most 255 stable error codes")
    entries: list[ErrorText] = []
    ids: set[str] = set()
    c_names: set[str] = set()
    codes: set[int] = set()
    known_profiles = frozenset(profile_ids)
    for index, value in enumerate(raw_entries):
        label = f"entries[{index}]"
        if not isinstance(value, dict):
            raise ErrorTextTableError(f"{label} must be an object")
        missing = sorted(ENTRY_KEYS - value.keys())
        unknown = sorted(value.keys() - (ENTRY_KEYS | {"delivery"}))
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing {', '.join(missing)}")
            if unknown:
                details.append(f"unknown {', '.join(unknown)}")
            raise ErrorTextTableError(f"{label} has {'; '.join(details)}")
        code, ident, c_name = value["code"], value["id"], value["c_name"]
        text, domain = value["text"], value["domain"]
        audience, reason = value["audience"], value["reason"]
        delivery = value.get("delivery", "overlay")
        selected_profiles = _string_list(value["profiles"], f"{label}.profiles")
        if type(code) is not int or not 1 <= code <= 255:
            raise ErrorTextTableError(f"{label}.code must be in 1..255")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise ErrorTextTableError(f"{label}.id is not canonical")
        if not isinstance(c_name, str) or not C_NAME_RE.fullmatch(c_name):
            raise ErrorTextTableError(f"{label}.c_name is not a LISP65_ERR_* name")
        if not isinstance(domain, str) or not ID_RE.fullmatch(domain):
            raise ErrorTextTableError(f"{label}.domain is not canonical")
        if audience not in AUDIENCES:
            raise ErrorTextTableError(f"{label}.audience is not classified")
        if delivery not in DELIVERIES:
            raise ErrorTextTableError(f"{label}.delivery is not classified")
        if not isinstance(reason, str) or not reason or not reason.isascii():
            raise ErrorTextTableError(f"{label}.reason must be non-empty ASCII")
        if not isinstance(text, str) or not text:
            raise ErrorTextTableError(f"{label}.text must be non-empty")
        try:
            encoded = text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ErrorTextTableError(f"{label}.text is not ASCII") from exc
        if b"\0" in encoded or len(encoded) > 255:
            raise ErrorTextTableError(f"{label}.text must be 1..255 non-NUL bytes")
        if not set(selected_profiles) <= known_profiles:
            raise ErrorTextTableError(f"{label}.profiles names an unknown profile")
        if delivery == "resident-only":
            if audience != "user":
                raise ErrorTextTableError(
                    f"{label} resident-only text must remain user-facing"
                )
            if "host" not in selected_profiles or "workbench" in selected_profiles:
                raise ErrorTextTableError(
                    f"{label} resident-only text must be host-visible and absent from L65E"
                )
        if code in codes or ident in ids or c_name in c_names:
            raise ErrorTextTableError(f"{label} duplicates a stable code, id, or C name")
        for profile in profiles:
            selected = profile.id in selected_profiles
            if (audience in profile.required_audiences and not selected
                    and delivery != "resident-only"):
                raise ErrorTextTableError(
                    f"{label} violates {profile.id}: {audience} text is required"
                )
            if audience in profile.excluded_audiences and selected:
                raise ErrorTextTableError(
                    f"{label} violates {profile.id}: {audience} path is not built"
                )
        codes.add(code)
        ids.add(ident)
        c_names.add(c_name)
        entries.append(ErrorText(
            code, ident, c_name, text, domain, audience, reason, selected_profiles,
            delivery
        ))

    actual_codes = [entry.code for entry in entries]
    expected_codes = list(range(1, len(entries) + 1))
    if actual_codes != expected_codes:
        raise ErrorTextTableError(
            f"error codes must be ordered and dense 1..{len(entries)}; got {actual_codes}"
        )
    if len(entries) >= COMPILE_SENTINEL_CODES[-1]:
        sentinels = entries[COMPILE_SENTINEL_CODES[0] - 1:COMPILE_SENTINEL_CODES[-1]]
        if (tuple(entry.code for entry in sentinels) != COMPILE_SENTINEL_CODES
                or any(entry.text != COMPILE_SENTINEL_TEXT for entry in sentinels)
                or any("workbench" not in entry.profiles for entry in sentinels)):
            raise ErrorTextTableError(
                "compile sentinels must share the pinned Workbench text"
            )
    workbench_domains = {
        entry.domain for entry in entries if "workbench" in entry.profiles
    }
    missing_domains = sorted(required_domains - workbench_domains)
    if missing_domains:
        raise ErrorTextTableError(
            "workbench omits required contract domains: " + ", ".join(missing_domains)
        )
    return ErrorTextSpec(tuple(profiles), required_domains, tuple(entries))


def build_table(
    entries: tuple[ErrorText, ...], profile: ErrorProfile, build_id: int
) -> ErrorTextTable:
    if not 0 <= build_id <= 0xFFFFFFFF:
        raise ErrorTextTableError("build ID is outside uint32")
    active = tuple(entry.code for entry in entries if profile.id in entry.profiles)
    index_bytes = 2 * len(entries)
    text_offset = HEADER_BYTES + index_bytes
    selected = [entry.text for entry in entries if entry.code in active]
    chunks = sorted(set(selected))
    # Deterministic greedy shortest-superstring packing. Besides exact aliases,
    # suffix/prefix overlap pays for the per-code descriptor growth without a
    # decompressor or any runtime allocation.
    while len(chunks) > 1:
        best: tuple[int, str, int, int] | None = None
        for left_index, left in enumerate(chunks):
            for right_index, right in enumerate(chunks):
                if left_index == right_index:
                    continue
                overlap = 0
                for size in range(1, min(len(left), len(right)) + 1):
                    if left.endswith(right[:size]):
                        overlap = size
                candidate = (overlap, left + right[overlap:], left_index, right_index)
                if best is None or candidate[0] > best[0] or (
                    candidate[0] == best[0] and candidate[1] < best[1]
                ):
                    best = candidate
        assert best is not None
        _, merged, left_index, right_index = best
        chunks = [value for index, value in enumerate(chunks)
                  if index not in (left_index, right_index)]
        chunks.append(merged)
        chunks.sort()
    payload = chunks[0].encode("ascii") if chunks else b""
    if len(payload) > TEXT_REF_OFFSET_MASK + 1:
        raise ErrorTextTableError("L65E packed text payload exceeds its 10-bit offset")
    descriptors: list[int] = []
    for entry in entries:
        if entry.code not in active:
            descriptors.append(0)
            continue
        encoded = entry.text.encode("ascii")
        offset = payload.find(encoded)
        if offset < 0 or offset > TEXT_REF_OFFSET_MASK:
            raise ErrorTextTableError("L65E packed text is not addressable")
        if len(encoded) > TEXT_REF_LENGTH_MAX:
            raise ErrorTextTableError("L65E packed text exceeds its 6-bit length")
        descriptors.append((len(encoded) << TEXT_REF_LENGTH_SHIFT) | offset)
    if len(entries) >= COMPILE_SENTINEL_CODES[-1]:
        sentinel_refs = descriptors[
            COMPILE_SENTINEL_CODES[0] - 1:COMPILE_SENTINEL_CODES[-1]
        ]
        if len(set(sentinel_refs)) != 1 or payload.count(
            COMPILE_SENTINEL_TEXT.encode("ascii")
        ) != 1:
            raise ErrorTextTableError(
                "compile-sentinel text is not physically shared exactly once"
            )
    covered_bytes = text_offset + len(payload)
    if covered_bytes > 0xFFFF:
        raise ErrorTextTableError("L65E table does not fit its uint16 length")
    flags = FLAG_OFFSET_INDEX | FLAG_SHARED_REFS | (profile.binary_id << PROFILE_SHIFT)
    if len(active) != len(entries):
        flags |= FLAG_SPARSE
    header = struct.pack(
        HEADER_FORMAT, MAGIC, VERSION, HEADER_BYTES, len(entries), flags,
        build_id, covered_bytes, 0,
    )
    unbound = header + struct.pack(f"<{len(descriptors)}H", *descriptors) + payload
    crc = crc16_ccitt_false(unbound)
    data = bytearray(unbound)
    struct.pack_into("<H", data, CRC_OFFSET, crc)
    return ErrorTextTable(build_id, profile, entries, active, bytes(data), crc)


def prepare_table(spec_path: Path, profile_id: str, build_id: int) -> ErrorTextTable:
    spec = load_spec(spec_path)
    return build_table(spec.entries, spec.profile(profile_id), build_id)


def parse_table(
    data: bytes,
    expected_build_id: int | None = None,
    expected_profile_id: int | None = None,
) -> dict[str, Any]:
    if len(data) < HEADER_BYTES:
        raise ErrorTextTableError("L65E table is truncated before its header")
    magic, version, header_bytes, count, flags, build_id, covered, stored_crc = (
        struct.unpack_from(HEADER_FORMAT, data)
    )
    if magic != MAGIC:
        raise ErrorTextTableError("L65E table has bad magic")
    if version != VERSION or header_bytes != HEADER_BYTES:
        raise ErrorTextTableError("L65E table has an unsupported version or header size")
    if not flags & FLAG_OFFSET_INDEX or not flags & FLAG_SHARED_REFS or flags & (FLAG_FORMAT_MASK & ~(
        FLAG_OFFSET_INDEX | FLAG_SPARSE | FLAG_SHARED_REFS
    )):
        raise ErrorTextTableError("L65E table has unsupported format flags")
    profile_id = flags >> PROFILE_SHIFT
    if count == 0:
        raise ErrorTextTableError("L65E table has no stable error codes")
    if covered != len(data):
        raise ErrorTextTableError("L65E covered length does not match the table")
    if expected_build_id is not None and build_id != expected_build_id:
        raise ErrorTextTableError("L65E profile build ID does not match")
    if expected_profile_id is not None and profile_id != expected_profile_id:
        raise ErrorTextTableError("L65E profile ID does not match")
    text_offset = HEADER_BYTES + 2 * count
    if text_offset > len(data):
        raise ErrorTextTableError("L65E offset index is truncated")
    check = bytearray(data)
    check[CRC_OFFSET:CRC_OFFSET + 2] = b"\0\0"
    if crc16_ccitt_false(check) != stored_crc:
        raise ErrorTextTableError("L65E table CRC does not match")
    descriptors = struct.unpack_from(f"<{count}H", data, HEADER_BYTES)
    payload = data[text_offset:]
    try:
        payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ErrorTextTableError("L65E text payload is not ASCII") from exc
    if b"\0" in payload:
        raise ErrorTextTableError("L65E text payload contains NUL")
    texts: list[str | None] = []
    active_codes: list[int] = []
    offsets: list[int] = []
    lengths: list[int] = []
    for code, descriptor in enumerate(descriptors, 1):
        length = descriptor >> TEXT_REF_LENGTH_SHIFT
        relative = descriptor & TEXT_REF_OFFSET_MASK
        start = text_offset + relative
        end = start + length
        offsets.append(start)
        lengths.append(length)
        if descriptor == 0:
            texts.append(None)
        else:
            if not length or end > len(data):
                raise ErrorTextTableError("L65E shared text reference is outside the payload")
            texts.append(data[start:end].decode("ascii"))
            active_codes.append(code)
    is_sparse = len(active_codes) != count
    if bool(flags & FLAG_SPARSE) != is_sparse:
        raise ErrorTextTableError("L65E sparse flag disagrees with its shared references")
    return {
        "version": version,
        "count": count,
        "flags": flags,
        "profile_id": profile_id,
        "build_id": build_id,
        "covered_bytes": covered,
        "crc16": stored_crc,
        "text_offset": text_offset,
        "offsets": offsets,
        "lengths": lengths,
        "active_codes": active_codes,
        "texts": texts,
    }


def find_table(
    slice_payload: bytes,
    expected_build_id: int | None = None,
    expected_profile_id: int | None = None,
) -> dict[str, Any]:
    """Find exactly one canonical L65E table inside a linked overlay slice."""
    matches: list[dict[str, Any]] = []
    cursor = 0
    while True:
        offset = slice_payload.find(MAGIC, cursor)
        if offset < 0:
            break
        cursor = offset + 1
        if offset + HEADER_BYTES > len(slice_payload):
            continue
        covered = struct.unpack_from("<H", slice_payload, offset + 12)[0]
        if covered < HEADER_BYTES or offset + covered > len(slice_payload):
            continue
        candidate = slice_payload[offset:offset + covered]
        try:
            parsed = parse_table(candidate, expected_build_id, expected_profile_id)
        except ErrorTextTableError:
            continue
        matches.append({
            "offset": offset,
            "size": covered,
            "count": parsed["count"],
            "flags": parsed["flags"],
            "profile_id": parsed["profile_id"],
            "build_id": parsed["build_id"],
            "crc16": parsed["crc16"],
            "sha256": hashlib.sha256(candidate).hexdigest(),
            "active_codes": parsed["active_codes"],
            "texts": parsed["texts"],
        })
    if len(matches) != 1:
        raise ErrorTextTableError(
            f"overlay slice must contain exactly one canonical L65E table; found {len(matches)}"
        )
    return matches[0]


def _binding_macro(lines: list[str], name: str, entries: list[ErrorText]) -> None:
    if not entries:
        lines.append(f"#define {name}(X) /* none */")
        return
    lines.append(f"#define {name}(X) \\")
    for index, entry in enumerate(entries):
        suffix = " \\" if index + 1 < len(entries) else ""
        lines.append(f"    X({entry.c_name}, {entry.code}u){suffix}")


def render_header(table: ErrorTextTable) -> bytes:
    active_set = set(table.active_codes)
    active = [entry for entry in table.entries if entry.code in active_set]
    omitted = [entry for entry in table.entries if entry.code not in active_set]
    index_entries = len(table.entries)
    lines = [
        "/* Generated by error_text_table.py; do not edit. */",
        "#ifndef LISP65_ERROR_TEXT_TABLE_H",
        "#define LISP65_ERROR_TEXT_TABLE_H",
        f"#define LISP65_ERROR_TEXT_TABLE_VERSION {VERSION}u",
        "#define LISP65_ERROR_TEXT_TABLE_MAGIC_U32 0x4535364cUL",
        f"#define LISP65_ERROR_TEXT_TABLE_HEADER_BYTES {HEADER_BYTES}u",
        f"#define LISP65_ERROR_TEXT_TABLE_FLAG_OFFSET_INDEX 0x{FLAG_OFFSET_INDEX:02x}u",
        f"#define LISP65_ERROR_TEXT_TABLE_FLAG_SPARSE 0x{FLAG_SPARSE:02x}u",
        f"#define LISP65_ERROR_TEXT_TABLE_FLAG_SHARED_REFS 0x{FLAG_SHARED_REFS:02x}u",
        f"#define LISP65_ERROR_TEXT_TABLE_REF_OFFSET_MASK 0x{TEXT_REF_OFFSET_MASK:04x}u",
        f"#define LISP65_ERROR_TEXT_TABLE_REF_LENGTH_SHIFT {TEXT_REF_LENGTH_SHIFT}u",
        f"#define LISP65_ERROR_TEXT_TABLE_FLAGS 0x{table.data[7]:02x}u",
        f"#define LISP65_ERROR_TEXT_TABLE_PROFILE_ID {table.profile.binary_id}u",
        f"#define LISP65_ERROR_TEXT_TABLE_COUNT {len(table.entries)}u",
        f"#define LISP65_ERROR_TEXT_TABLE_ACTIVE_COUNT {len(active)}u",
        f"#define LISP65_ERROR_TEXT_TABLE_OMITTED_COUNT {len(omitted)}u",
        f"#define LISP65_ERROR_TEXT_TABLE_INDEX_ENTRIES {index_entries}u",
        f"#define LISP65_ERROR_TEXT_TABLE_INDEX_BYTES {index_entries * 2}u",
        f"#define LISP65_ERROR_TEXT_TABLE_TEXT_OFFSET {HEADER_BYTES + index_entries * 2}u",
        f"#define LISP65_ERROR_TEXT_TABLE_BUILD_ID 0x{table.build_id:08x}UL",
        f"#define LISP65_ERROR_TEXT_TABLE_BYTES {len(table.data)}u",
        f"#define LISP65_ERROR_TEXT_TABLE_CRC16 0x{table.crc16:04x}u",
    ]
    _binding_macro(lines, "LISP65_ERROR_TEXT_CODE_BINDINGS", list(table.entries))
    _binding_macro(lines, "LISP65_ERROR_TEXT_ACTIVE_BINDINGS", active)
    _binding_macro(lines, "LISP65_ERROR_TEXT_OMITTED_BINDINGS", omitted)
    lines.append("#define LISP65_ERROR_TEXT_TABLE_INITIALIZER { \\")
    chunks = [table.data[index:index + 12] for index in range(0, len(table.data), 12)]
    for index, chunk in enumerate(chunks):
        values = ", ".join(f"0x{value:02x}" for value in chunk)
        if index + 1 < len(chunks):
            values += ","
        lines.append(f"    {values} \\")
    lines.extend(["}", "#endif /* LISP65_ERROR_TEXT_TABLE_H */", ""])
    return "\n".join(lines).encode("ascii")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _parse_build_id(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("build ID must be an integer") from exc
    if not 0 <= result <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("build ID must fit uint32")
    return result


def _rebind_crc(data: bytearray) -> None:
    data[CRC_OFFSET:CRC_OFFSET + 2] = b"\0\0"
    struct.pack_into("<H", data, CRC_OFFSET, crc16_ccitt_false(data))


def _selftest_document(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "format": "L65E",
        "version": VERSION,
        "encoding": "ascii",
        "selection_policy": POLICY,
        "profiles": [
            {
                "id": "host", "binary_id": 0, "description": "host",
                "required_audiences": ["user", "internal", "not-built"],
                "excluded_audiences": [],
            },
            {
                "id": "workbench", "binary_id": 1, "description": "product",
                "required_audiences": ["user"],
                "excluded_audiences": ["not-built"],
            },
        ],
        "future_contract": {
            **FUTURE_VALUES,
            "required_workbench_domains": [
                "reader", "persistence", "compile-load", "oom", "stack-guard"
            ],
        },
        "entries": entries,
    }


def selftest() -> None:
    domains = ["reader", "persistence", "compile-load", "oom", "stack-guard"]
    entries = []
    for code, domain in enumerate(domains, 1):
        entries.append({
            "code": code, "id": f"active-{code}",
            "c_name": f"LISP65_ERR_ACTIVE_{code}", "text": f"active {code}",
            "domain": domain, "audience": "user", "reason": "reachable",
            "profiles": ["host", "workbench"],
        })
    entries.append({
        "code": 6, "id": "omitted", "c_name": "LISP65_ERR_OMITTED",
        "text": "host only", "domain": "legacy", "audience": "not-built",
        "reason": "not linked", "profiles": ["host"],
    })
    entries.append({
        "code": 7, "id": "resident", "c_name": "LISP65_ERR_RESIDENT",
        "text": "resident text", "domain": "deployment", "audience": "user",
        "reason": "rendered without the overlay", "profiles": ["host"],
        "delivery": "resident-only",
    })
    with tempfile.TemporaryDirectory(prefix="l65e-selftest-") as raw:
        directory = Path(raw)
        spec_path = directory / "errors.json"

        def write_document(document: dict[str, Any]) -> None:
            spec_path.write_text(json.dumps(document), encoding="ascii")

        write_document(_selftest_document(entries))
        table = prepare_table(spec_path, "workbench", 0x12345678)
        parsed = parse_table(table.data, 0x12345678, 1)
        if (parsed["active_codes"] != [1, 2, 3, 4, 5]
                or parsed["texts"][-2:] != [None, None]):
            raise ErrorTextTableError("selftest sparse table did not round-trip")
        if not parsed["flags"] & FLAG_SPARSE:
            raise ErrorTextTableError("selftest sparse table did not set its flag")
        located = find_table(b"\xaa\xbb" + table.data + b"\xcc", 0x12345678, 1)
        if located["offset"] != 2 or located["size"] != len(table.data):
            raise ErrorTextTableError("selftest did not locate the embedded table")
        if render_header(table) != render_header(
            prepare_table(spec_path, "workbench", 0x12345678)
        ):
            raise ErrorTextTableError("selftest header is not deterministic")

        mutations: dict[str, bytearray] = {}
        out_of_range = bytearray(table.data)
        struct.pack_into(
            "<H", out_of_range, HEADER_BYTES,
            (TEXT_REF_LENGTH_MAX << TEXT_REF_LENGTH_SHIFT) | TEXT_REF_OFFSET_MASK,
        )
        _rebind_crc(out_of_range)
        mutations["shared-ref-range"] = out_of_range
        zero_length = bytearray(table.data)
        struct.pack_into("<H", zero_length, HEADER_BYTES, 1)
        _rebind_crc(zero_length)
        mutations["shared-ref-zero-length"] = zero_length
        sparse_flag = bytearray(table.data)
        sparse_flag[7] &= ~FLAG_SPARSE
        _rebind_crc(sparse_flag)
        mutations["sparse-flag"] = sparse_flag
        for label, damaged in mutations.items():
            try:
                parse_table(bytes(damaged), 0x12345678, 1)
            except ErrorTextTableError:
                pass
            else:
                raise ErrorTextTableError(f"selftest accepted {label} mutation")
        try:
            parse_table(table.data, 0x12345678, 2)
        except ErrorTextTableError:
            pass
        else:
            raise ErrorTextTableError("selftest accepted a profile mismatch")
        try:
            prepare_table(spec_path, "missing", 0x12345678)
        except ErrorTextTableError:
            pass
        else:
            raise ErrorTextTableError("selftest accepted an unknown profile")

        classified = json.loads(json.dumps(_selftest_document(entries)))
        classified["entries"][0]["profiles"] = ["host"]
        write_document(classified)
        try:
            load_spec(spec_path)
        except ErrorTextTableError:
            pass
        else:
            raise ErrorTextTableError("selftest accepted an unclassified user omission")

        wrong_not_built = json.loads(json.dumps(_selftest_document(entries)))
        wrong_not_built["entries"][-2]["profiles"] = ["host", "workbench"]
        write_document(wrong_not_built)
        try:
            load_spec(spec_path)
        except ErrorTextTableError:
            pass
        else:
            raise ErrorTextTableError("selftest accepted a not-built Workbench text")

        wrong_resident = json.loads(json.dumps(_selftest_document(entries)))
        wrong_resident["entries"][-1]["profiles"] = ["host", "workbench"]
        write_document(wrong_resident)
        try:
            load_spec(spec_path)
        except ErrorTextTableError:
            pass
        else:
            raise ErrorTextTableError("selftest accepted resident text in L65E")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="generate a bound sparse C header")
    prepare.add_argument("--spec", type=Path, required=True)
    prepare.add_argument("--profile", required=True)
    prepare.add_argument("--build-id", type=_parse_build_id, required=True)
    prepare.add_argument("--header", type=Path, required=True)
    prepare.add_argument("--binary", type=Path)
    verify = subparsers.add_parser("verify", help="verify a generated binary table")
    verify.add_argument("--table", type=Path, required=True)
    verify.add_argument("--build-id", type=_parse_build_id)
    verify.add_argument("--spec", type=Path)
    verify.add_argument("--profile")
    subparsers.add_parser("selftest", help="run deterministic mutation tests")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            table = prepare_table(args.spec, args.profile, args.build_id)
            _atomic_write(args.header, render_header(table))
            if args.binary:
                _atomic_write(args.binary, table.data)
            omitted = len(table.entries) - len(table.active_codes)
            print(
                f"error-text-table: ok profile={table.profile.id} "
                f"codes={len(table.entries)} active={len(table.active_codes)} "
                f"omitted={omitted} bytes={len(table.data)} "
                f"crc16={table.crc16:04x} build_id={table.build_id:08x}"
            )
        elif args.command == "verify":
            if bool(args.spec) != bool(args.profile):
                raise ErrorTextTableError("verify requires --spec and --profile together")
            data = args.table.read_bytes()
            expected_profile_id = None
            expected_table = None
            if args.spec:
                spec = load_spec(args.spec)
                profile = spec.profile(args.profile)
                expected_profile_id = profile.binary_id
                parsed_build_id = struct.unpack_from("<I", data, 8)[0] if len(data) >= 12 else 0
                expected_table = build_table(spec.entries, profile, parsed_build_id)
            parsed = parse_table(data, args.build_id, expected_profile_id)
            if expected_table is not None and expected_table.data != data:
                raise ErrorTextTableError("L65E table differs from its selected profile spec")
            print(
                f"error-text-table: verify ok profile_id={parsed['profile_id']} "
                f"codes={parsed['count']} active={len(parsed['active_codes'])} "
                f"bytes={parsed['covered_bytes']} crc16={parsed['crc16']:04x}"
            )
        else:
            selftest()
            print("error-text-table: selftest ok cases=13")
    except (OSError, ErrorTextTableError, struct.error) as exc:
        print(f"error-text-table: error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
