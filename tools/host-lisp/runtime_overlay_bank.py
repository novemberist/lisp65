#!/usr/bin/env python3
"""Pack and verify profile-bound reusable runtime overlays for MEGA65 Attic RAM."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any, Sequence


FORMAT = "lisp65-runtime-overlay-bank-v1"
BINDING_SCHEMA = "lisp65-runtime-overlay-package-v2"
MAGIC = b"L65R"
VERSION = 1
HEADER_SIZE = 32
ENTRY_SIZE = 32
MAX_SLICES = 64
ENTRY_ABI = 1
MAX_SLICE_BYTES = 1792
MAX_BOOT_SLICE_BYTES = 4096
MAX_VMA = 0xC356
VERIFIER_SLICE_COUNT = 2
# L65R-v1 freezes this byte as a format tag. Physical storage is a separate
# deployment binding since the MEGA65 ROM banks do not survive reset as RAM.
BANK = 3
BANK_SIZE = 0x10000
STORAGE_KIND = "attic-ram"
STORAGE_BASE = 0x08000000
STORAGE_LIMIT = STORAGE_BASE + BANK_SIZE
STORAGE_ADDRESS_BITS = 28
STORAGE_PERSISTENCE = "reset-stable-power-volatile"
PAYLOAD_ALIGNMENT = 0x100
CRC16_INIT = 0xFFFF
CRC16_POLY = 0x1021

# The prepare header must compile the exact same resident code path as the
# bound header. Non-zero, in-range sentinels keep every field materialized;
# the bootstrap link replaces them with authenticated catalog values.
PREPARE_VERIFIER_BINDINGS = (
    (0x0100, 0x0456, 0x0012, 0xA55A),
    (0x0600, 0x0456, 0x0012, 0x5AA5),
)

FLAG_BOOT = 0x0001
FLAG_RUNTIME = 0x0002
FLAG_REUSABLE = 0x0004
KNOWN_FLAGS = FLAG_BOOT | FLAG_RUNTIME | FLAG_REUSABLE

HEADER = struct.Struct("<4sBBBBHBBIHHIHHI")
ENTRY = struct.Struct("<HHHHHHHHIHHII")

ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SYMBOL_RE = re.compile(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$")
SECTION_RE = re.compile(r"^\.[A-Za-z0-9_.$-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

TOP_FIELDS = {
    "schema", "profile", "profile_build_id", "abi", "elf", "storage",
    "catalog", "config_header", "policy", "slices",
}
ABI_FIELDS = {"contract", "sha256"}
FILE_FIELDS = {"file", "sha256"}
STORAGE_FIELDS = {
    "format", "file", "kind", "address", "address_bits", "limit", "size",
    "build_id", "crc16", "crc16_algorithm", "sha256", "persistence",
}
CATALOG_FIELDS = {
    "magic", "version", "header_size", "entry_size", "slice_count", "flags",
    "directory_offset", "payload_offset", "directory_crc16", "header_crc16",
    "crc16_algorithm", "format_bank_tag",
}
POLICY_FIELDS = {
    "max_slices", "max_slice_bytes", "max_boot_slice_bytes", "payload_alignment",
    "common_vma", "entry_abi",
}
SLICE_FIELDS = {
    "id", "name", "section", "start_symbol", "end_symbol", "entry_symbol",
    "flags", "roles", "file_offset", "file_size", "memory_size", "vma", "end",
    "entry", "entry_offset", "abi_version", "slice_build_id", "capability_mask",
    "crc16", "sha256",
}


class OverlayBankError(RuntimeError):
    """A tool input, artifact, or canonical format invariant failed."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class SliceSpec:
    id: int
    name: str
    section: str
    start_symbol: str
    end_symbol: str
    entry_symbol: str
    flags: int
    abi_version: int
    capability_mask: int
    entry_target: str = ""


@dataclass(frozen=True)
class ExtractedSlice:
    spec: SliceSpec
    vma: int
    end: int
    entry: int
    data: bytes


@dataclass(frozen=True)
class ParsedSlice:
    id: int
    flags: int
    file_offset: int
    file_size: int
    vma: int
    memory_size: int
    entry_offset: int
    abi_version: int
    slice_build_id: int
    crc16: int
    bss_bytes: int
    capability_mask: int


@dataclass(frozen=True)
class ParsedBank:
    profile_build_id: int
    payload_offset: int
    image_size: int
    directory_crc16: int
    header_crc16: int
    slices: tuple[ParsedSlice, ...]


@dataclass(frozen=True)
class Materialized:
    image: bytes
    manifest: dict[str, Any]
    header: bytes


def _fail(code: str, detail: str) -> None:
    raise OverlayBankError(code, detail)


def _align(value: int, alignment: int = PAYLOAD_ALIGNMENT) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def _parse_int(value: str, label: str, minimum: int, maximum: int) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} is not an integer: {value!r}") from exc
    if not minimum <= result <= maximum:
        raise argparse.ArgumentTypeError(
            f"{label} must be in {minimum}..{maximum}, got {result}"
        )
    return result


def _address(value: str) -> int:
    return _parse_int(value, "runtime overlay VMA", 0, MAX_VMA)


def _positive_u16(value: str) -> int:
    return _parse_int(value, "limit", 1, 0xFFFF)


def _slice_limit(value: str) -> int:
    result = _positive_u16(value)
    if result != MAX_SLICE_BYTES:
        raise argparse.ArgumentTypeError(
            f"runtime overlay slice limit is profile-pinned to {MAX_SLICE_BYTES} bytes"
        )
    return result


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate-json-key", f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _regular_file(path: Path, label: str, *, executable: bool = False) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        _fail("missing-file", f"{label} is missing or unreadable: {path}: {exc}")
    if stat.S_ISLNK(info.st_mode):
        _fail("symlink", f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(info.st_mode):
        _fail("not-regular", f"{label} must be a regular file: {path}")
    if executable and not os.access(path, os.X_OK):
        _fail("not-executable", f"{label} is not executable: {path}")
    return info


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    _regular_file(path, "hash input")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    _regular_file(path, label)
    try:
        value = json.loads(
            path.read_text(encoding="ascii"), object_pairs_hook=_strict_object
        )
    except OverlayBankError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail("invalid-json", f"cannot read {label} {path}: {exc}")
    if not isinstance(value, dict):
        _fail("manifest-shape", f"{label} root must be an object")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def _atomic_write_many(outputs: Sequence[tuple[Path, bytes]]) -> None:
    temporaries: list[tuple[Path, Path]] = []
    try:
        for target, data in outputs:
            target.parent.mkdir(parents=True, exist_ok=True)
            _reject_symlink_path(target.parent, "output directory")
            try:
                target_info = target.lstat()
            except FileNotFoundError:
                pass
            except OSError as exc:
                _fail("output-path", f"cannot inspect output {target}: {exc}")
            else:
                if stat.S_ISLNK(target_info.st_mode):
                    _fail("symlink", f"output must not be a symlink: {target}")
                if not stat.S_ISREG(target_info.st_mode):
                    _fail("not-regular", f"existing output must be a regular file: {target}")
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.tmp.", dir=target.parent
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporaries.append((temporary, target))
        for temporary, target in temporaries:
            temporary.replace(target)
    finally:
        for temporary, _target in temporaries:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _reject_symlink_path(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            info = current.lstat()
        except OSError as exc:
            _fail("output-path", f"cannot inspect {label} component {current}: {exc}")
        if stat.S_ISLNK(info.st_mode):
            _fail("symlink", f"{label} must not traverse a symlink: {current}")


def crc16_ccitt_false(data: bytes) -> int:
    crc = CRC16_INIT
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ CRC16_POLY) & 0xFFFF
                if crc & 0x8000
                else (crc << 1) & 0xFFFF
            )
    return crc


def _roles(flags: int) -> list[str]:
    result: list[str] = []
    if flags & FLAG_BOOT:
        result.append("boot")
    if flags & FLAG_RUNTIME:
        result.append("runtime")
    if flags & FLAG_REUSABLE:
        result.append("reusable")
    return result


def _check_flags(flags: int, label: str) -> None:
    if flags & ~KNOWN_FLAGS:
        _fail("unknown-flags", f"{label} contains unknown bits 0x{flags:04x}")
    if bool(flags & FLAG_BOOT) == bool(flags & FLAG_RUNTIME):
        _fail("invalid-flags", f"{label} must select exactly one of boot or runtime")
    if flags & FLAG_REUSABLE and not flags & FLAG_RUNTIME:
        _fail("invalid-flags", f"{label} reusable requires runtime")


def _parse_flags(value: str) -> int:
    names = {"boot": FLAG_BOOT, "runtime": FLAG_RUNTIME, "reusable": FLAG_REUSABLE}
    try:
        if value.startswith(("0x", "0X")) or value.isdigit():
            flags = int(value, 0)
        else:
            flags = 0
            for name in value.split("+"):
                if name not in names:
                    raise ValueError(name)
                flags |= names[name]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid slice flags: {value!r}") from exc
    if not 0 <= flags <= 0xFFFF:
        raise argparse.ArgumentTypeError("slice flags do not fit uint16")
    try:
        _check_flags(flags, "slice flags")
    except OverlayBankError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return flags


def _payload_limit(flags: int, runtime_limit: int) -> int:
    return MAX_BOOT_SLICE_BYTES if flags & FLAG_BOOT else runtime_limit


def _slice_spec(value: str) -> SliceSpec:
    fields = value.split(":")
    if len(fields) != 10:
        raise argparse.ArgumentTypeError(
            "slice must be ID:NAME:SECTION:START:END:ENTRY:FLAGS:ABI_VERSION:CAPS:ENTRY_TARGET"
        )
    (
        id_text, name, section, start, end, entry, flags_text, abi_text,
        caps_text, entry_target,
    ) = fields
    slice_id = _parse_int(id_text, "slice ID", 0, MAX_SLICES - 1)
    if not ID_RE.fullmatch(name):
        raise argparse.ArgumentTypeError(f"slice name must match {ID_RE.pattern!r}: {name!r}")
    if not SECTION_RE.fullmatch(section):
        raise argparse.ArgumentTypeError(f"invalid slice section: {section!r}")
    for label, symbol in (
        ("start", start), ("end", end), ("entry", entry),
        ("entry target", entry_target),
    ):
        if not SYMBOL_RE.fullmatch(symbol):
            raise argparse.ArgumentTypeError(f"invalid {label} symbol: {symbol!r}")
    flags = _parse_flags(flags_text)
    abi_version = _parse_int(abi_text, "ABI version", ENTRY_ABI, ENTRY_ABI)
    capabilities = _parse_int(caps_text, "capability mask", 0, 0xFFFFFFFF)
    return SliceSpec(
        slice_id, name, section, start, end, entry, flags, abi_version,
        capabilities, entry_target
    )


def _check_specs(specs: Sequence[SliceSpec]) -> list[SliceSpec]:
    if not specs:
        _fail("empty-slices", "at least one slice is required")
    if len(specs) > MAX_SLICES:
        _fail("too-many-slices", f"slice count {len(specs)} exceeds {MAX_SLICES}")
    for label, values in (
        ("ID", [item.id for item in specs]),
        ("name", [item.name for item in specs]),
        ("section", [item.section for item in specs]),
        ("start symbol", [item.start_symbol for item in specs]),
        ("end symbol", [item.end_symbol for item in specs]),
        ("entry symbol", [item.entry_symbol for item in specs]),
    ):
        if len(set(values)) != len(values):
            _fail("duplicate-slice-spec", f"duplicate slice {label}")
    ordered = sorted(specs, key=lambda item: item.id)
    actual_ids = [item.id for item in ordered]
    expected_ids = list(range(len(ordered)))
    if actual_ids != expected_ids:
        _fail(
            "dense-slice-ids",
            f"slice IDs must be the dense sequence 0..{len(ordered) - 1}, got {actual_ids}",
        )
    return ordered


def lint_layout(args: argparse.Namespace) -> None:
    specs = _check_specs(args.slice)
    if any(not spec.entry_target for spec in specs) or len(
        {spec.entry_target for spec in specs}
    ) != len(specs):
        _fail("layout-entry-target", "entry targets must be non-empty and unique")
    for label, configured, canonical in (
        ("bank", args.expect_bank, BANK),
        ("address", args.expect_address, STORAGE_BASE),
        ("entry ABI", args.expect_entry_abi, ENTRY_ABI),
    ):
        if configured != canonical:
            _fail(
                "layout-profile",
                f"configured {label} is {configured:#x}, expected {canonical:#x}",
            )
    if args.expect_capacity != MAX_SLICES:
        _fail(
            "layout-capacity",
            f"configured catalog capacity is {args.expect_capacity}, expected {MAX_SLICES}",
        )
    if len(specs) != args.expect_count:
        _fail(
            "layout-count",
            f"configured slice count is {args.expect_count}, but {len(specs)} specs were passed",
        )
    _regular_file(args.linker, "runtime overlay linker script")
    try:
        linker = args.linker.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        _fail("layout-read", f"cannot read linker script as ASCII: {exc}")
    members = re.findall(
        r"^\s*(\.lisp65_rt_[A-Za-z0-9_.$-]+)\s*\{",
        linker,
        flags=re.MULTILINE,
    )
    expected_members = [spec.section for spec in specs]
    if members != expected_members:
        _fail(
            "layout-members",
            "linker runtime members differ from the ordered slice specs: "
            f"linker={members!r} specs={expected_members!r}",
        )
    for spec in specs:
        size_limit = _payload_limit(spec.flags, MAX_SLICE_BYTES)
        required = (
            f"{spec.start_symbol} = ADDR({spec.section})",
            f"{spec.end_symbol} = ADDR({spec.section}) + SIZEOF({spec.section})",
            f"{spec.entry_symbol} = {spec.entry_target};",
            f"ASSERT(SIZEOF({spec.section}) > 0 && SIZEOF({spec.section}) <= {size_limit}",
        )
        for fragment in required:
            if fragment not in linker:
                _fail(
                    "layout-binding",
                    f"linker binding for slice {spec.id} is missing {fragment!r}",
                )


def _nm_symbols(nm: Path, elf: Path, required: set[str]) -> dict[str, int]:
    _regular_file(nm, "llvm-nm", executable=True)
    _regular_file(elf, "final ELF")
    try:
        completed = subprocess.run(
            [str(nm), "--defined-only", str(elf)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        _fail("nm-failed", f"llvm-nm failed: {detail.strip()}")
    found: dict[str, list[int]] = {name: [] for name in required}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[-1] not in found:
            continue
        try:
            address = int(fields[0], 16)
        except ValueError:
            _fail("nm-output", f"invalid llvm-nm address: {line!r}")
        found[fields[-1]].append(address)
    result: dict[str, int] = {}
    for name, addresses in found.items():
        if len(addresses) != 1:
            _fail("nm-symbol", f"ELF must define {name!r} exactly once, found {len(addresses)}")
        result[name] = addresses[0]
    return result


def _extract_section(objcopy: Path, elf: Path, section: str, output: Path) -> bytes:
    _regular_file(objcopy, "llvm-objcopy", executable=True)
    try:
        subprocess.run(
            [
                str(objcopy), "-O", "binary", f"--only-section={section}",
                str(elf), str(output),
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        _fail("objcopy-failed", f"llvm-objcopy failed for {section}: {str(detail).strip()}")
    _regular_file(output, f"extracted section {section}")
    return output.read_bytes()


def extract_slices(
    elf: Path,
    nm: Path,
    objcopy: Path,
    specs: Sequence[SliceSpec],
    *,
    expected_vma: int,
    max_slice_bytes: int,
) -> list[ExtractedSlice]:
    ordered = _check_specs(specs)
    required = {
        symbol
        for item in ordered
        for symbol in (item.start_symbol, item.end_symbol, item.entry_symbol)
    }
    symbols = _nm_symbols(nm, elf, required)
    extracted: list[ExtractedSlice] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-runtime-overlay-extract-") as name:
        root = Path(name)
        for index, spec in enumerate(ordered):
            start = symbols[spec.start_symbol]
            end = symbols[spec.end_symbol]
            entry = symbols[spec.entry_symbol]
            if start != expected_vma:
                _fail(
                    "vma-mismatch",
                    f"slice {spec.name} VMA is 0x{start:04x}, expected 0x{expected_vma:04x}",
                )
            if not 0 <= start < end <= BANK_SIZE:
                _fail("invalid-vma", f"slice {spec.name} has invalid span 0x{start:x}..0x{end:x}")
            if not start <= entry < end:
                _fail("entry-range", f"slice {spec.name} entry lies outside its VMA span")
            size = end - start
            size_limit = _payload_limit(spec.flags, max_slice_bytes)
            if size > size_limit:
                _fail(
                    "slice-too-large",
                    f"slice {spec.name} has {size} bytes, limit is {size_limit}",
                )
            data = _extract_section(objcopy, elf, spec.section, root / f"slice-{index}.bin")
            if len(data) != size:
                _fail(
                    "section-size",
                    f"slice {spec.name} ELF span has {size} bytes, objcopy emitted {len(data)}",
                )
            if not data:
                _fail("empty-slice", f"slice {spec.name} is empty")
            extracted.append(ExtractedSlice(spec, start, end, entry, data))
    return extracted


def _profile_build_id(contract_sha256: str) -> int:
    if not SHA256_RE.fullmatch(contract_sha256):
        _fail("abi-sha", "ABI contract SHA-256 is not canonical lowercase hex")
    return int(contract_sha256[:8], 16)


def build_image(
    slices: Sequence[ExtractedSlice],
    *,
    profile_build_id: int,
    expected_vma: int,
    max_slice_bytes: int,
    max_vma: int = MAX_VMA,
) -> tuple[bytes, ParsedBank]:
    if not 0 <= profile_build_id <= 0xFFFFFFFF:
        _fail("build-id", "profile build ID does not fit uint32")
    if type(max_vma) is not int or not 0 <= max_vma <= 0xFFFF:
        _fail("invalid-vma", "maximum VMA does not fit uint16")
    if type(expected_vma) is not int or not 0 <= expected_vma <= max_vma:
        _fail("invalid-vma", f"expected VMA must be in 0..0x{max_vma:04x}")
    if not 1 <= max_slice_bytes <= 0xFFFF:
        _fail("slice-limit", "max slice bytes must fit a positive uint16")
    ordered = sorted(slices, key=lambda item: item.spec.id)
    _check_specs([item.spec for item in ordered])
    if any(item.vma != expected_vma for item in ordered):
        _fail("vma-mismatch", "all slices must use the profile VMA")

    payload_offset = _align(HEADER_SIZE + len(ordered) * ENTRY_SIZE)
    if payload_offset > 0xFFFF:
        _fail("catalog-size", "catalog payload offset does not fit uint16")
    cursor = payload_offset
    records: list[bytes] = []
    payloads: list[tuple[int, bytes]] = []
    parsed: list[ParsedSlice] = []
    for item in ordered:
        spec = item.spec
        _check_flags(spec.flags, f"slice {spec.name} flags")
        if item.end - item.vma != len(item.data):
            _fail("section-size", f"slice {spec.name} memory and file sizes differ")
        if not item.data or len(item.data) > _payload_limit(spec.flags, max_slice_bytes):
            _fail("slice-too-large", f"slice {spec.name} size is outside the profile limit")
        if item.vma + len(item.data) > BANK_SIZE:
            _fail("invalid-vma", f"slice {spec.name} exceeds Bank 0")
        if not item.vma <= item.entry < item.end:
            _fail("entry-range", f"slice {spec.name} entry lies outside the payload")
        cursor = _align(cursor)
        if cursor > 0xFFFF:
            _fail("bank-overflow", f"slice {spec.name} file offset does not fit uint16")
        if cursor + len(item.data) > BANK_SIZE:
            _fail("bank-overflow", f"slice {spec.name} exceeds the L65R-v1 64-KB window")
        crc = crc16_ccitt_false(item.data)
        entry_offset = item.entry - item.vma
        record = ENTRY.pack(
            spec.id,
            spec.flags,
            cursor,
            len(item.data),
            item.vma,
            len(item.data),
            entry_offset,
            spec.abi_version,
            profile_build_id,
            crc,
            0,
            spec.capability_mask,
            0,
        )
        records.append(record)
        payloads.append((cursor, item.data))
        parsed.append(
            ParsedSlice(
                spec.id,
                spec.flags,
                cursor,
                len(item.data),
                item.vma,
                len(item.data),
                entry_offset,
                spec.abi_version,
                profile_build_id,
                crc,
                0,
                spec.capability_mask,
            )
        )
        cursor += len(item.data)
    image_size = cursor
    directory = b"".join(records)
    directory_crc = crc16_ccitt_false(directory)
    header_without_crc = HEADER.pack(
        MAGIC,
        VERSION,
        HEADER_SIZE,
        ENTRY_SIZE,
        len(ordered),
        0,
        BANK,
        0,
        profile_build_id,
        HEADER_SIZE,
        payload_offset,
        image_size,
        directory_crc,
        0,
        0,
    )
    header_crc = crc16_ccitt_false(header_without_crc)
    header = bytearray(header_without_crc)
    struct.pack_into("<H", header, 26, header_crc)
    image = bytearray(image_size)
    image[:HEADER_SIZE] = header
    image[HEADER_SIZE : HEADER_SIZE + len(directory)] = directory
    for offset, data in payloads:
        image[offset : offset + len(data)] = data
    result = bytes(image)
    parsed_bank = ParsedBank(
        profile_build_id,
        payload_offset,
        image_size,
        directory_crc,
        header_crc,
        tuple(parsed),
    )
    validate_image(
        result,
        expected_build_id=profile_build_id,
        expected_vma=expected_vma,
        max_slice_bytes=max_slice_bytes,
        max_vma=max_vma,
    )
    return result, parsed_bank


def validate_image(
    image: bytes,
    *,
    expected_build_id: int,
    expected_vma: int,
    max_slice_bytes: int,
    max_vma: int = MAX_VMA,
) -> ParsedBank:
    if type(max_vma) is not int or not 0 <= max_vma <= 0xFFFF:
        _fail("invalid-vma", "maximum VMA does not fit uint16")
    if type(expected_vma) is not int or not 0 <= expected_vma <= max_vma:
        _fail("invalid-vma", f"expected VMA must be in 0..0x{max_vma:04x}")
    data = bytes(image)
    if len(data) < HEADER_SIZE:
        _fail("truncated-header", f"image has {len(data)} bytes, need {HEADER_SIZE}")
    fields = HEADER.unpack_from(data)
    (
        magic,
        version,
        header_size,
        entry_size,
        count,
        flags,
        bank,
        reserved_byte,
        build_id,
        directory_offset,
        payload_offset,
        image_size,
        directory_crc,
        header_crc,
        reserved_word,
    ) = fields
    if magic != MAGIC:
        _fail("bad-magic", f"catalog magic is {magic!r}")
    if version != VERSION:
        _fail("bad-version", f"catalog version is {version}")
    if header_size != HEADER_SIZE:
        _fail("bad-header-size", f"header size is {header_size}")
    if entry_size != ENTRY_SIZE:
        _fail("bad-entry-size", f"entry size is {entry_size}")
    if not 1 <= count <= MAX_SLICES:
        _fail("bad-slice-count", f"slice count is {count}")
    if flags:
        _fail("header-flags", f"header flags are 0x{flags:04x}")
    if bank != BANK:
        _fail("wrong-bank", f"catalog bank is {bank}, expected {BANK}")
    if reserved_byte or reserved_word:
        _fail("header-reserved", "header reserved fields must be zero")
    if build_id != expected_build_id:
        _fail("build-id", f"profile build ID is 0x{build_id:08x}")
    if directory_offset != HEADER_SIZE:
        _fail("directory-offset", f"directory offset is {directory_offset}")
    directory_end = directory_offset + count * ENTRY_SIZE
    canonical_payload = _align(directory_end)
    if payload_offset != canonical_payload or payload_offset > len(data):
        _fail("payload-offset", f"payload offset is {payload_offset}, expected {canonical_payload}")
    if image_size != len(data) or image_size > BANK_SIZE:
        _fail("image-size", f"header image size is {image_size}, actual is {len(data)}")
    header_copy = bytearray(data[:HEADER_SIZE])
    header_copy[26:28] = b"\x00\x00"
    if crc16_ccitt_false(header_copy) != header_crc:
        _fail("header-crc", "header CRC-16/CCITT-FALSE mismatch")
    directory = data[directory_offset:directory_end]
    if len(directory) != count * ENTRY_SIZE:
        _fail("truncated-directory", "directory exceeds the image")
    if crc16_ccitt_false(directory) != directory_crc:
        _fail("directory-crc", "directory CRC-16/CCITT-FALSE mismatch")
    if any(data[directory_end:payload_offset]):
        _fail("nonzero-padding", "catalog-to-payload padding is not zero")

    slices: list[ParsedSlice] = []
    cursor = payload_offset
    for index in range(count):
        values = ENTRY.unpack_from(directory, index * ENTRY_SIZE)
        (
            slice_id,
            slice_flags,
            file_offset,
            file_size,
            vma,
            memory_size,
            entry_offset,
            abi_version,
            slice_build_id,
            payload_crc,
            bss_bytes,
            capability_mask,
            entry_reserved,
        ) = values
        if slice_id != index:
            if index and slice_id == slices[-1].id:
                _fail("duplicate-id", f"duplicate slice ID {slice_id}")
            _fail(
                "dense-slice-ids",
                f"slice[{index}] ID is {slice_id}, expected dense slot ID {index}",
            )
        _check_flags(slice_flags, f"slice[{index}].flags")
        canonical_offset = _align(cursor)
        if file_offset != canonical_offset:
            _fail(
                "file-offset",
                f"slice[{index}] file offset is {file_offset}, expected {canonical_offset}",
            )
        if file_offset & (PAYLOAD_ALIGNMENT - 1):
            _fail("payload-alignment", f"slice[{index}] payload is not 256-byte aligned")
        if any(data[cursor:file_offset]):
            _fail("nonzero-padding", f"padding before slice[{index}] is not zero")
        if not 1 <= file_size <= _payload_limit(slice_flags, max_slice_bytes):
            _fail("slice-size", f"slice[{index}] file size is {file_size}")
        if file_offset > len(data) or file_size > len(data) - file_offset:
            _fail("slice-bounds", f"slice[{index}] payload exceeds the image")
        if memory_size != file_size or bss_bytes != 0:
            _fail("memory-size", f"slice[{index}] v1 requires memory_size=file_size and no BSS")
        if vma != expected_vma or vma + memory_size > BANK_SIZE:
            _fail("vma-mismatch", f"slice[{index}] VMA is 0x{vma:04x}")
        if entry_offset >= file_size:
            _fail("entry-range", f"slice[{index}] entry offset is outside its payload")
        if abi_version != ENTRY_ABI:
            _fail("abi-version", f"slice[{index}] ABI version must be {ENTRY_ABI}")
        if slice_build_id != expected_build_id:
            _fail("slice-build-id", f"slice[{index}] build ID does not match the profile")
        if entry_reserved:
            _fail("entry-reserved", f"slice[{index}] reserved field must be zero")
        payload = data[file_offset : file_offset + file_size]
        if crc16_ccitt_false(payload) != payload_crc:
            _fail("payload-crc", f"slice[{index}] payload CRC mismatch")
        slices.append(
            ParsedSlice(
                slice_id,
                slice_flags,
                file_offset,
                file_size,
                vma,
                memory_size,
                entry_offset,
                abi_version,
                slice_build_id,
                payload_crc,
                bss_bytes,
                capability_mask,
            )
        )
        cursor = file_offset + file_size
    if cursor != len(data):
        _fail("trailing-bytes", f"last slice ends at {cursor}, image ends at {len(data)}")
    return ParsedBank(
        build_id,
        payload_offset,
        image_size,
        directory_crc,
        header_crc,
        tuple(slices),
    )


def _verifier_bindings(
    slices: Sequence[ParsedSlice] | None,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    if slices is None:
        return PREPARE_VERIFIER_BINDINGS
    if len(slices) < VERIFIER_SLICE_COUNT:
        _fail("verifier-binding", "catalog requires verifier slices in slots 0 and 1")
    bound: list[tuple[int, int, int, int]] = []
    for slot in range(VERIFIER_SLICE_COUNT):
        entry = slices[slot]
        if entry.id != slot:
            _fail("verifier-binding", f"verifier slot {slot} has ID {entry.id}")
        if entry.flags != FLAG_RUNTIME | FLAG_REUSABLE:
            _fail(
                "verifier-binding",
                f"verifier slot {slot} must be runtime+reusable",
            )
        bound.append(
            (entry.file_offset, entry.file_size, entry.entry_offset, entry.crc16)
        )
    return (bound[0], bound[1])


def render_header(
    *,
    profile_build_id: int,
    verifier_slices: Sequence[ParsedSlice] | None = None,
) -> bytes:
    catalog, record = _verifier_bindings(verifier_slices)
    lines = [
        "/* Generated by runtime_overlay_bank.py; do not edit. */",
        "#ifndef LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H",
        "#define LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H",
        "",
        f"#define LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG 0x{BANK:02x}u",
        f"#define LISP65_RUNTIME_OVERLAY_STORAGE_BASE 0x{STORAGE_BASE:08x}UL",
        f"#define LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE 0x{STORAGE_BASE >> 20:02x}u",
        f"#define LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES 0x{BANK_SIZE:08x}UL",
        "#define LISP65_RUNTIME_OVERLAY_CATALOG_OFF 0x0000u",
        f"#define LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID 0x{profile_build_id:08x}UL",
        f"#define LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES {MAX_SLICE_BYTES}u",
        f"#define LISP65_RUNTIME_OVERLAY_BOOT_MAX_SLICE_BYTES {MAX_BOOT_SLICE_BYTES}u",
        f"#define LISP65_RUNTIME_OVERLAY_ENTRY_ABI {ENTRY_ABI}u",
        "",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF 0x{catalog[0]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE 0x{catalog[1]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET 0x{catalog[2]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16 0x{catalog[3]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF 0x{record[0]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_SIZE 0x{record[1]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_ENTRY_OFFSET 0x{record[2]:04x}u",
        f"#define LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16 0x{record[3]:04x}u",
    ]
    lines.extend(["", "#endif /* LISP65_RUNTIME_OVERLAY_BANK_CONFIG_H */", ""])
    return "\n".join(lines).encode("ascii")


def _manifest(
    *,
    profile: str,
    abi_contract: Path,
    abi_sha256: str,
    elf: Path,
    image_path: Path,
    header_path: Path,
    image: bytes,
    header: bytes,
    parsed: ParsedBank,
    slices: Sequence[ExtractedSlice],
    expected_vma: int,
    max_slice_bytes: int,
) -> dict[str, Any]:
    by_id = {item.spec.id: item for item in slices}
    records: list[dict[str, Any]] = []
    for entry in parsed.slices:
        source = by_id[entry.id]
        spec = source.spec
        records.append(
            {
                "id": entry.id,
                "name": spec.name,
                "section": spec.section,
                "start_symbol": spec.start_symbol,
                "end_symbol": spec.end_symbol,
                "entry_symbol": spec.entry_symbol,
                "flags": entry.flags,
                "roles": _roles(entry.flags),
                "file_offset": entry.file_offset,
                "file_size": entry.file_size,
                "memory_size": entry.memory_size,
                "vma": entry.vma,
                "end": entry.vma + entry.memory_size,
                "entry": entry.vma + entry.entry_offset,
                "entry_offset": entry.entry_offset,
                "abi_version": entry.abi_version,
                "slice_build_id": entry.slice_build_id,
                "capability_mask": entry.capability_mask,
                "crc16": entry.crc16,
                "sha256": _sha256_bytes(source.data),
            }
        )
    return {
        "schema": BINDING_SCHEMA,
        "profile": profile,
        "profile_build_id": parsed.profile_build_id,
        "abi": {"contract": abi_contract.name, "sha256": abi_sha256},
        "elf": {"file": elf.name, "sha256": _sha256(elf)},
        "storage": {
            "format": FORMAT,
            "file": image_path.name,
            "kind": STORAGE_KIND,
            "address": STORAGE_BASE,
            "address_bits": STORAGE_ADDRESS_BITS,
            "limit": STORAGE_LIMIT,
            "size": len(image),
            "build_id": parsed.profile_build_id,
            "crc16": crc16_ccitt_false(image),
            "crc16_algorithm": "crc-16-ccitt-false",
            "sha256": _sha256_bytes(image),
            "persistence": STORAGE_PERSISTENCE,
        },
        "catalog": {
            "magic": MAGIC.decode("ascii"),
            "version": VERSION,
            "header_size": HEADER_SIZE,
            "entry_size": ENTRY_SIZE,
            "slice_count": len(records),
            "flags": 0,
            "directory_offset": HEADER_SIZE,
            "payload_offset": parsed.payload_offset,
            "directory_crc16": parsed.directory_crc16,
            "header_crc16": parsed.header_crc16,
            "crc16_algorithm": "crc-16-ccitt-false",
            "format_bank_tag": BANK,
        },
        "config_header": {"file": header_path.name, "sha256": _sha256_bytes(header)},
        "policy": {
            "max_slices": MAX_SLICES,
            "max_slice_bytes": max_slice_bytes,
            "max_boot_slice_bytes": MAX_BOOT_SLICE_BYTES,
            "payload_alignment": PAYLOAD_ALIGNMENT,
            "common_vma": expected_vma,
            "entry_abi": ENTRY_ABI,
        },
        "slices": records,
    }


def _shape(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict):
        _fail("manifest-shape", f"{label} must be an object")
    missing = sorted(fields - set(value))
    extra = sorted(set(value) - fields)
    if missing or extra:
        _fail(
            "manifest-shape",
            f"{label} fields differ: missing={','.join(missing)} extra={','.join(extra)}",
        )


def validate_manifest(value: dict[str, Any]) -> None:
    _shape(value, TOP_FIELDS, "manifest")
    _shape(value["abi"], ABI_FIELDS, "manifest.abi")
    _shape(value["elf"], FILE_FIELDS, "manifest.elf")
    _shape(value["storage"], STORAGE_FIELDS, "manifest.storage")
    _shape(value["catalog"], CATALOG_FIELDS, "manifest.catalog")
    _shape(value["config_header"], FILE_FIELDS, "manifest.config_header")
    _shape(value["policy"], POLICY_FIELDS, "manifest.policy")
    if value["schema"] != BINDING_SCHEMA or value["storage"]["format"] != FORMAT:
        _fail(
            "manifest-format",
            f"manifest schema must be {BINDING_SCHEMA} with binary format {FORMAT}",
        )
    if not isinstance(value["profile"], str) or not value["profile"]:
        _fail("manifest-profile", "manifest profile must be a non-empty string")
    for label, digest in (
        ("ABI", value["abi"].get("sha256")),
        ("ELF", value["elf"].get("sha256")),
        ("storage", value["storage"].get("sha256")),
        ("config header", value["config_header"].get("sha256")),
    ):
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            _fail("manifest-sha", f"{label} SHA-256 is invalid")
    expected_build_id = _profile_build_id(value["abi"]["sha256"])
    if value.get("profile_build_id") != expected_build_id:
        _fail("manifest-build-id", "manifest build ID is not derived from the ABI contract SHA")
    storage = value["storage"]
    expected_storage = {
        "kind": STORAGE_KIND,
        "address": STORAGE_BASE,
        "address_bits": STORAGE_ADDRESS_BITS,
        "limit": STORAGE_LIMIT,
        "build_id": expected_build_id,
        "crc16_algorithm": "crc-16-ccitt-false",
        "persistence": STORAGE_PERSISTENCE,
    }
    for field, expected in expected_storage.items():
        if storage.get(field) != expected:
            _fail("manifest-storage", f"manifest storage {field} must be {expected!r}")
    if type(storage.get("crc16")) is not int or not 0 <= storage["crc16"] <= 0xFFFF:
        _fail("manifest-storage", "manifest storage CRC16 must be a uint16")
    catalog = value["catalog"]
    expected_catalog = {
        "magic": MAGIC.decode("ascii"),
        "version": VERSION,
        "header_size": HEADER_SIZE,
        "entry_size": ENTRY_SIZE,
        "flags": 0,
        "directory_offset": HEADER_SIZE,
        "crc16_algorithm": "crc-16-ccitt-false",
        "format_bank_tag": BANK,
    }
    for field, expected in expected_catalog.items():
        if catalog.get(field) != expected:
            _fail("manifest-catalog", f"manifest catalog {field} must be {expected!r}")
    policy = value["policy"]
    if (
        policy.get("max_slices") != MAX_SLICES
        or policy.get("max_slice_bytes") != MAX_SLICE_BYTES
        or policy.get("max_boot_slice_bytes") != MAX_BOOT_SLICE_BYTES
        or policy.get("payload_alignment") != PAYLOAD_ALIGNMENT
        or policy.get("entry_abi") != ENTRY_ABI
    ):
        _fail("manifest-policy", "manifest policy constants are invalid")
    if (
        type(policy.get("common_vma")) is not int
        or not 0 <= policy["common_vma"] <= MAX_VMA
    ):
        _fail(
            "manifest-policy",
            f"manifest common VMA must be in 0..0x{MAX_VMA:04x}",
        )
    slices = value["slices"]
    if not isinstance(slices, list) or not 1 <= len(slices) <= MAX_SLICES:
        _fail("manifest-slices", "manifest slices must be a non-empty bounded array")
    ids: list[int] = []
    for index, record in enumerate(slices):
        _shape(record, SLICE_FIELDS, f"manifest.slices[{index}]")
        ids.append(record.get("id"))
        if not isinstance(record.get("sha256"), str) or not SHA256_RE.fullmatch(record["sha256"]):
            _fail("manifest-sha", f"slice[{index}] SHA-256 is invalid")
        slice_flags = record.get("flags")
        if type(slice_flags) is not int or not 0 <= slice_flags <= 0xFFFF:
            _fail("manifest-flags", f"slice[{index}] flags must be a uint16")
        _check_flags(slice_flags, f"manifest slice[{index}].flags")
        if record.get("roles") != _roles(slice_flags):
            _fail("manifest-flags", f"slice[{index}] roles do not match flags")
        if record.get("abi_version") != ENTRY_ABI:
            _fail("manifest-abi", f"slice[{index}] ABI version must be {ENTRY_ABI}")
        if record.get("slice_build_id") != expected_build_id:
            _fail("manifest-build-id", f"slice[{index}] build ID differs from the profile")
    if any(type(item) is not int for item in ids) or ids != list(range(len(ids))):
        _fail("manifest-id-order", "manifest slice IDs must be the dense sequence 0..count-1")
    if catalog.get("slice_count") != len(slices):
        _fail("manifest-slices", "manifest catalog count differs from slice array")


def materialize(
    *,
    elf: Path,
    nm: Path,
    objcopy: Path,
    profile: str,
    abi_contract: Path,
    specs: Sequence[SliceSpec],
    expected_vma: int,
    max_slice_bytes: int,
    image_path: Path,
    header_path: Path,
) -> Materialized:
    if not profile or "\x00" in profile:
        _fail("profile", "profile must be a non-empty NUL-free string")
    if max_slice_bytes != MAX_SLICE_BYTES:
        _fail(
            "slice-limit",
            f"runtime overlay slice limit must be profile-pinned to {MAX_SLICE_BYTES}",
        )
    if type(expected_vma) is not int or not 0 <= expected_vma <= MAX_VMA:
        _fail("invalid-vma", f"expected VMA must be in 0..0x{MAX_VMA:04x}")
    _regular_file(abi_contract, "ABI contract")
    abi_sha = _sha256(abi_contract)
    build_id = _profile_build_id(abi_sha)
    slices = extract_slices(
        elf,
        nm,
        objcopy,
        specs,
        expected_vma=expected_vma,
        max_slice_bytes=max_slice_bytes,
    )
    image, parsed = build_image(
        slices,
        profile_build_id=build_id,
        expected_vma=expected_vma,
        max_slice_bytes=max_slice_bytes,
    )
    header = render_header(
        profile_build_id=build_id,
        verifier_slices=parsed.slices,
    )
    manifest = _manifest(
        profile=profile,
        abi_contract=abi_contract,
        abi_sha256=abi_sha,
        elf=elf,
        image_path=image_path,
        header_path=header_path,
        image=image,
        header=header,
        parsed=parsed,
        slices=slices,
        expected_vma=expected_vma,
        max_slice_bytes=max_slice_bytes,
    )
    validate_manifest(manifest)
    return Materialized(image, manifest, header)


def _verify_outputs(
    expected: Materialized,
    *,
    image_path: Path,
    manifest_path: Path,
    header_path: Path,
    expected_vma: int,
    max_slice_bytes: int,
) -> None:
    for path, label in (
        (image_path, "overlay bank image"),
        (manifest_path, "overlay bank manifest"),
        (header_path, "overlay bank C header"),
    ):
        _regular_file(path, label)
    actual_image = image_path.read_bytes()
    validate_image(
        actual_image,
        expected_build_id=expected.manifest["profile_build_id"],
        expected_vma=expected_vma,
        max_slice_bytes=max_slice_bytes,
    )
    if actual_image != expected.image:
        _fail("image-mismatch", "overlay bank image is not the canonical extraction of the ELF")
    actual_manifest = _read_json(manifest_path, "overlay bank manifest")
    validate_manifest(actual_manifest)
    if actual_manifest != expected.manifest:
        _fail("manifest-mismatch", "manifest is not the exact binding of inputs and image")
    try:
        actual_header = header_path.read_bytes()
    except OSError as exc:
        _fail("header-read", f"cannot read C config header: {exc}")
    if actual_header != expected.header:
        _fail("header-mismatch", "C config header is stale or noncanonical")


def pack(args: argparse.Namespace) -> None:
    expected = materialize(
        elf=args.elf,
        nm=args.nm,
        objcopy=args.objcopy,
        profile=args.profile,
        abi_contract=args.abi_contract,
        specs=args.slice,
        expected_vma=args.vma,
        max_slice_bytes=args.max_slice_bytes,
        image_path=args.image,
        header_path=args.header,
    )
    outputs = [
        (args.image, expected.image),
        (args.manifest, _json_bytes(expected.manifest)),
    ]
    if args.header_mode == "write":
        outputs.append((args.header, expected.header))
    else:
        _regular_file(args.header, "overlay bank C header")
        try:
            actual_header = args.header.read_bytes()
        except OSError as exc:
            _fail("header-read", f"cannot read C config header: {exc}")
        if actual_header != expected.header:
            _fail(
                "header-mismatch",
                "final ELF changed the bootstrap verifier binding",
            )
    _atomic_write_many(outputs)
    _verify_outputs(
        expected,
        image_path=args.image,
        manifest_path=args.manifest,
        header_path=args.header,
        expected_vma=args.vma,
        max_slice_bytes=args.max_slice_bytes,
    )


def verify(args: argparse.Namespace) -> None:
    expected = materialize(
        elf=args.elf,
        nm=args.nm,
        objcopy=args.objcopy,
        profile=args.profile,
        abi_contract=args.abi_contract,
        specs=args.slice,
        expected_vma=args.vma,
        max_slice_bytes=args.max_slice_bytes,
        image_path=args.image,
        header_path=args.header,
    )
    _verify_outputs(
        expected,
        image_path=args.image,
        manifest_path=args.manifest,
        header_path=args.header,
        expected_vma=args.vma,
        max_slice_bytes=args.max_slice_bytes,
    )


def _refresh_catalog_crcs(data: bytearray) -> None:
    if len(data) < HEADER_SIZE:
        return
    count = data[7]
    directory_end = HEADER_SIZE + count * ENTRY_SIZE
    if directory_end <= len(data):
        struct.pack_into("<H", data, 24, crc16_ccitt_false(data[HEADER_SIZE:directory_end]))
    data[26:28] = b"\x00\x00"
    struct.pack_into("<H", data, 26, crc16_ccitt_false(data[:HEADER_SIZE]))


def _refresh_header_crc(data: bytearray) -> None:
    if len(data) < HEADER_SIZE:
        return
    data[26:28] = b"\x00\x00"
    struct.pack_into("<H", data, 26, crc16_ccitt_false(data[:HEADER_SIZE]))


def _replace_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def _replace_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def selftest() -> None:
    vma = 0xC200
    max_bytes = MAX_SLICE_BYTES
    if max_bytes != 1792 or MAX_VMA != 0xC356:
        raise AssertionError("runtime window contract constants drifted")
    abi_data = b"format=lisp65-resolved-profile-v1\n"
    build_id = _profile_build_id(_sha256_bytes(abi_data))
    specs = [
        SliceSpec(0, "catalog-verifier", ".lisp65_rt_test_catalog", "catalog_start", "catalog_end", "catalog_entry", FLAG_RUNTIME | FLAG_REUSABLE, 1, 0, "test_entry_0"),
        SliceSpec(1, "record-verifier", ".lisp65_rt_test_record", "record_start", "record_end", "record_entry", FLAG_RUNTIME | FLAG_REUSABLE, 1, 1, "test_entry_1"),
        SliceSpec(2, "runtime-b", ".lisp65_rt_test_b", "b_start", "b_end", "b_entry", FLAG_RUNTIME | FLAG_REUSABLE, 1, 3, "test_entry_2"),
        SliceSpec(3, "boot-batch", ".lisp65_rt_test_boot", "boot_start", "boot_end", "boot_entry", FLAG_BOOT, 1, 0, "test_entry_3"),
    ]
    slices = [
        ExtractedSlice(specs[0], vma, vma + 31, vma + 3, bytes(range(31))),
        ExtractedSlice(specs[1], vma, vma + 257, vma + 17, bytes(range(256)) + b"A"),
        ExtractedSlice(specs[2], vma, vma + 73, vma + 5, b"runtime-b" * 8 + b"!"),
        ExtractedSlice(
            specs[3], vma, vma + MAX_SLICE_BYTES + 1, vma + 11,
            b"B" * (MAX_SLICE_BYTES + 1),
        ),
    ]
    image, parsed = build_image(
        slices,
        profile_build_id=build_id,
        expected_vma=vma,
        max_slice_bytes=max_bytes,
    )
    if validate_image(
        image,
        expected_build_id=build_id,
        expected_vma=vma,
        max_slice_bytes=max_bytes,
    ) != parsed:
        raise AssertionError("positive image parse mismatch")
    if parsed.slices[3].file_size <= MAX_SLICE_BYTES:
        raise AssertionError("boot fixture does not exercise the separate boot limit")

    boundary_spec = SliceSpec(
        0, "runtime-boundary", ".lisp65_rt_test_boundary",
        "boundary_start", "boundary_end", "boundary_entry",
        FLAG_RUNTIME | FLAG_REUSABLE, ENTRY_ABI, 0, "test_boundary_entry",
    )
    boundary_slice = ExtractedSlice(
        boundary_spec,
        MAX_VMA,
        MAX_VMA + MAX_SLICE_BYTES,
        MAX_VMA + MAX_SLICE_BYTES - 1,
        b"R" * MAX_SLICE_BYTES,
    )
    boundary_image, boundary_parsed = build_image(
        [boundary_slice],
        profile_build_id=build_id,
        expected_vma=MAX_VMA,
        max_slice_bytes=MAX_SLICE_BYTES,
    )
    if validate_image(
        boundary_image,
        expected_build_id=build_id,
        expected_vma=MAX_VMA,
        max_slice_bytes=MAX_SLICE_BYTES,
    ) != boundary_parsed:
        raise AssertionError("1792-byte runtime boundary did not round-trip")

    oversized_runtime = ExtractedSlice(
        boundary_spec,
        MAX_VMA,
        MAX_VMA + MAX_SLICE_BYTES + 1,
        MAX_VMA,
        b"R" * (MAX_SLICE_BYTES + 1),
    )
    try:
        build_image(
            [oversized_runtime],
            profile_build_id=build_id,
            expected_vma=MAX_VMA,
            max_slice_bytes=MAX_SLICE_BYTES,
        )
    except OverlayBankError as exc:
        if exc.code != "slice-too-large":
            raise AssertionError(f"1793-byte runtime boundary: got {exc.code}") from exc
    else:
        raise AssertionError("1793-byte runtime slice passed")

    excessive_vma_slice = ExtractedSlice(
        boundary_spec, MAX_VMA + 1, MAX_VMA + 2, MAX_VMA + 1, b"V",
    )
    try:
        build_image(
            [excessive_vma_slice],
            profile_build_id=build_id,
            expected_vma=MAX_VMA + 1,
            max_slice_bytes=MAX_SLICE_BYTES,
        )
    except OverlayBankError as exc:
        if exc.code != "invalid-vma":
            raise AssertionError(f"VMA ceiling: got {exc.code}") from exc
    else:
        raise AssertionError("VMA above 0xc356 passed")
    legacy_vma_image, legacy_vma_parsed = build_image(
        [excessive_vma_slice],
        profile_build_id=build_id,
        expected_vma=MAX_VMA + 1,
        max_slice_bytes=MAX_SLICE_BYTES,
        max_vma=0xFFFF,
    )
    if validate_image(
        legacy_vma_image,
        expected_build_id=build_id,
        expected_vma=MAX_VMA + 1,
        max_slice_bytes=MAX_SLICE_BYTES,
        max_vma=0xFFFF,
    ) != legacy_vma_parsed:
        raise AssertionError("explicit historical VMA allowance did not round-trip")
    try:
        validate_image(
            boundary_image,
            expected_build_id=build_id,
            expected_vma=MAX_VMA + 1,
            max_slice_bytes=MAX_SLICE_BYTES,
        )
    except OverlayBankError as exc:
        if exc.code != "invalid-vma":
            raise AssertionError(f"validation VMA ceiling: got {exc.code}") from exc
    else:
        raise AssertionError("validation accepted VMA above 0xc356")

    oversized_spec = SliceSpec(
        0, "oversized-boot", ".lisp65_rt_test_oversized_boot",
        "oversized_boot_start", "oversized_boot_end", "oversized_boot_entry",
        FLAG_BOOT, ENTRY_ABI, 0,
    )
    oversized_boot = ExtractedSlice(
        oversized_spec, vma, vma + MAX_BOOT_SLICE_BYTES + 1, vma,
        b"B" * (MAX_BOOT_SLICE_BYTES + 1),
    )
    try:
        build_image(
            [oversized_boot],
            profile_build_id=build_id,
            expected_vma=vma,
            max_slice_bytes=max_bytes,
        )
    except OverlayBankError as exc:
        if exc.code != "slice-too-large":
            raise AssertionError(f"oversized boot slice: got {exc.code}") from exc
    else:
        raise AssertionError("oversized boot slice passed")

    capacity_specs = [
        SliceSpec(
            slot,
            f"capacity-{slot:02d}",
            f".lisp65_rt_capacity_{slot:02d}",
            f"capacity_{slot:02d}_start",
            f"capacity_{slot:02d}_end",
            f"capacity_{slot:02d}_entry",
            FLAG_RUNTIME | FLAG_REUSABLE,
            ENTRY_ABI,
            0,
        )
        for slot in range(MAX_SLICES)
    ]
    capacity_slices = [
        ExtractedSlice(spec, vma, vma + 1, vma, bytes((spec.id,)))
        for spec in capacity_specs
    ]
    capacity_image, capacity_parsed = build_image(
        capacity_slices,
        profile_build_id=build_id,
        expected_vma=vma,
        max_slice_bytes=max_bytes,
    )
    if len(
        validate_image(
            capacity_image,
            expected_build_id=build_id,
            expected_vma=vma,
            max_slice_bytes=max_bytes,
        ).slices
    ) != MAX_SLICES or len(capacity_parsed.slices) != MAX_SLICES:
        raise AssertionError("full-capacity image parse mismatch")

    failures: list[str] = []
    mutation_count = 0

    def reject(name: str, mutate: Any, *, refresh: bool = False, expected: str | None = None) -> None:
        nonlocal mutation_count
        mutation_count += 1
        candidate = bytearray(image)
        mutate(candidate)
        if refresh:
            _refresh_catalog_crcs(candidate)
        try:
            validate_image(
                candidate,
                expected_build_id=build_id,
                expected_vma=vma,
                max_slice_bytes=max_bytes,
            )
        except OverlayBankError as exc:
            if expected is not None and exc.code != expected:
                failures.append(f"{name}: expected {expected}, got {exc.code}")
        else:
            failures.append(f"{name}: mutation passed")

    reject("magic", lambda b: b.__setitem__(0, ord("X")), expected="bad-magic")
    reject("version", lambda b: b.__setitem__(4, 2), expected="bad-version")
    reject("header-size", lambda b: b.__setitem__(5, 31), expected="bad-header-size")
    reject("entry-size", lambda b: b.__setitem__(6, 31), expected="bad-entry-size")
    reject("count-zero", lambda b: b.__setitem__(7, 0), expected="bad-slice-count")
    reject("count-large", lambda b: b.__setitem__(7, 65), expected="bad-slice-count")
    reject("header-flags", lambda b: _replace_u16(b, 8, 1), expected="header-flags")
    reject("bank", lambda b: b.__setitem__(10, 5), expected="wrong-bank")
    reject("reserved-byte", lambda b: b.__setitem__(11, 1), expected="header-reserved")
    reject("build-id", lambda b: _replace_u32(b, 12, build_id ^ 1), expected="build-id")
    reject("directory-offset", lambda b: _replace_u16(b, 16, 34), expected="directory-offset")
    reject("payload-offset", lambda b: _replace_u16(b, 18, parsed.payload_offset + 1), expected="payload-offset")
    reject("image-size", lambda b: _replace_u32(b, 20, len(b) - 1), expected="image-size")
    reject("directory-crc", lambda b: _replace_u16(b, 24, parsed.directory_crc16 ^ 1), expected="header-crc")
    reject("header-crc", lambda b: _replace_u16(b, 26, parsed.header_crc16 ^ 1), expected="header-crc")
    reject("reserved-word", lambda b: _replace_u32(b, 28, 1), expected="header-reserved")
    reject("truncate", lambda b: b.__delitem__(slice(-1, None)), expected="image-size")
    reject("append", lambda b: b.extend(b"\x00"), expected="image-size")

    entry0 = HEADER_SIZE
    entry1 = HEADER_SIZE + ENTRY_SIZE
    reject("id-first-not-zero", lambda b: _replace_u16(b, entry0, 3), refresh=True, expected="dense-slice-ids")
    reject("id-unsorted", lambda b: _replace_u16(b, entry1, 2), refresh=True, expected="dense-slice-ids")
    reject("id-duplicate", lambda b: _replace_u16(b, entry1, 0), refresh=True, expected="duplicate-id")
    reject("unknown-flags", lambda b: _replace_u16(b, entry0 + 2, 0x8001), refresh=True, expected="unknown-flags")
    reject("boot-runtime", lambda b: _replace_u16(b, entry0 + 2, 3), refresh=True, expected="invalid-flags")
    reject("reusable-boot", lambda b: _replace_u16(b, entry0 + 2, 5), refresh=True, expected="invalid-flags")
    reject("unaligned-offset", lambda b: _replace_u16(b, entry0 + 4, parsed.payload_offset + 1), refresh=True, expected="file-offset")
    reject("gap-offset", lambda b: _replace_u16(b, entry1 + 4, parsed.slices[1].file_offset + 256), refresh=True, expected="file-offset")
    reject("size-zero", lambda b: _replace_u16(b, entry0 + 6, 0), refresh=True, expected="slice-size")
    reject("size-limit", lambda b: _replace_u16(b, entry0 + 6, max_bytes + 1), refresh=True, expected="slice-size")
    reject("vma-mismatch", lambda b: _replace_u16(b, entry1 + 8, vma + 2), refresh=True, expected="vma-mismatch")
    reject("vma-overflow", lambda b: _replace_u16(b, entry0 + 8, 0xFFFF), refresh=True, expected="vma-mismatch")
    reject("memory-size", lambda b: _replace_u16(b, entry0 + 10, 30), refresh=True, expected="memory-size")
    reject("entry-range", lambda b: _replace_u16(b, entry0 + 12, 31), refresh=True, expected="entry-range")
    reject("abi-zero", lambda b: _replace_u16(b, entry0 + 14, 0), refresh=True, expected="abi-version")
    reject("abi-version", lambda b: _replace_u16(b, entry0 + 14, 2), refresh=True, expected="abi-version")
    reject("slice-build-id", lambda b: _replace_u32(b, entry0 + 16, build_id ^ 1), refresh=True, expected="slice-build-id")
    reject("payload-crc-field", lambda b: _replace_u16(b, entry0 + 20, parsed.slices[0].crc16 ^ 1), refresh=True, expected="payload-crc")
    reject("bss", lambda b: _replace_u16(b, entry0 + 22, 1), refresh=True, expected="memory-size")
    reject("entry-reserved", lambda b: _replace_u32(b, entry0 + 28, 1), refresh=True, expected="entry-reserved")
    reject(
        "directory-bytes-crc",
        lambda b: (_replace_u16(b, entry0 + 24, 7), _refresh_header_crc(b)),
        expected="directory-crc",
    )
    reject(
        "payload-overlap",
        lambda b: _replace_u16(b, entry1 + 4, parsed.slices[0].file_offset),
        refresh=True,
        expected="file-offset",
    )
    reject("catalog-padding", lambda b: b.__setitem__(HEADER_SIZE + len(specs) * ENTRY_SIZE, 1), expected="nonzero-padding")
    reject("payload-padding", lambda b: b.__setitem__(parsed.slices[0].file_offset + parsed.slices[0].file_size, 1), expected="nonzero-padding")
    reject("payload-byte", lambda b: b.__setitem__(parsed.slices[2].file_offset, b[parsed.slices[2].file_offset] ^ 1), expected="payload-crc")

    with tempfile.TemporaryDirectory(prefix="lisp65-runtime-overlay-bank-selftest-") as name:
        root = Path(name)
        elf = root / "final.elf"
        abi = root / "abi.txt"
        image_path = root / "bank.bin"
        header_path = root / "bank.h"
        elf.write_bytes(b"ELF fixture")
        abi.write_bytes(abi_data)
        prepared_header = render_header(profile_build_id=build_id)
        header = render_header(
            profile_build_id=build_id,
            verifier_slices=parsed.slices,
        )
        header_text = prepared_header.decode("ascii")
        for required in (
            "LISP65_RUNTIME_OVERLAY_FORMAT_BANK_TAG 0x03u",
            "LISP65_RUNTIME_OVERLAY_STORAGE_BASE 0x08000000UL",
            "LISP65_RUNTIME_OVERLAY_STORAGE_MEGABYTE 0x80u",
            "LISP65_RUNTIME_OVERLAY_STORAGE_WINDOW_BYTES 0x00010000UL",
            "LISP65_RUNTIME_OVERLAY_CATALOG_OFF 0x0000u",
            f"LISP65_RUNTIME_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
            f"LISP65_RUNTIME_OVERLAY_MAX_SLICE_BYTES {MAX_SLICE_BYTES}u",
            f"LISP65_RUNTIME_OVERLAY_ENTRY_ABI {ENTRY_ABI}u",
            "LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_OFF 0x0100u",
            "LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_FILE_SIZE 0x0456u",
            "LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_ENTRY_OFFSET 0x0012u",
            "LISP65_RUNTIME_OVERLAY_CATALOG_VERIFIER_CRC16 0xa55au",
            "LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_FILE_OFF 0x0600u",
            "LISP65_RUNTIME_OVERLAY_RECORD_VERIFIER_CRC16 0x5aa5u",
        ):
            if required not in header_text:
                failures.append(f"base-header: missing {required}")
        for forbidden in ("IMAGE_SIZE", "SLICE_COUNT", "COMMON_VMA", "SLICE_BOOT"):
            if forbidden in header_text:
                failures.append(f"base-header: forbidden ELF-derived macro {forbidden}")
        bound_text = header.decode("ascii")
        for label, entry in (("CATALOG", parsed.slices[0]), ("RECORD", parsed.slices[1])):
            for field, value in (
                ("FILE_OFF", entry.file_offset),
                ("FILE_SIZE", entry.file_size),
                ("ENTRY_OFFSET", entry.entry_offset),
                ("CRC16", entry.crc16),
            ):
                required = f"LISP65_RUNTIME_OVERLAY_{label}_VERIFIER_{field} 0x{value:04x}u"
                if required not in bound_text:
                    failures.append(f"bound-header: missing {required}")
        if prepared_header == header:
            failures.append("bound-header: sentinels were not replaced")
        layout_path = root / "runtime-overlay.ld"
        layout_lines: list[str] = []
        for spec in specs:
            layout_lines.extend(
                (
                    f"  {spec.section} {{ KEEP(*({spec.section})) }}",
                    f"{spec.start_symbol} = ADDR({spec.section});",
                    f"{spec.end_symbol} = ADDR({spec.section}) + SIZEOF({spec.section});",
                    f"{spec.entry_symbol} = {spec.entry_target};",
                    f"ASSERT(SIZEOF({spec.section}) > 0 && SIZEOF({spec.section}) <= {_payload_limit(spec.flags, MAX_SLICE_BYTES)}, \"bounded\");",
                )
            )
        layout_path.write_text("\n".join(layout_lines) + "\n", encoding="ascii")
        lint_layout(
            argparse.Namespace(
                linker=layout_path,
                expect_count=len(specs),
                expect_capacity=MAX_SLICES,
                expect_bank=BANK,
                expect_address=STORAGE_BASE,
                expect_entry_abi=ENTRY_ABI,
                slice=specs,
            )
        )
        mutation_count += 1
        try:
            lint_layout(
                argparse.Namespace(
                    linker=layout_path,
                    expect_count=len(specs) + 1,
                    expect_capacity=MAX_SLICES,
                    expect_bank=BANK,
                    expect_address=STORAGE_BASE,
                    expect_entry_abi=ENTRY_ABI,
                    slice=specs,
                )
            )
        except OverlayBankError as exc:
            if exc.code != "layout-count":
                failures.append(f"layout-count: got {exc.code}")
        else:
            failures.append("layout-count: accepted")
        mutation_count += 1
        broken_layout = layout_path.read_text(encoding="ascii").replace(
            specs[1].section, ".lisp65_rt_test_missing", 1
        )
        layout_path.write_text(broken_layout, encoding="ascii")
        try:
            lint_layout(
                argparse.Namespace(
                    linker=layout_path,
                    expect_count=len(specs),
                    expect_capacity=MAX_SLICES,
                    expect_bank=BANK,
                    expect_address=STORAGE_BASE,
                    expect_entry_abi=ENTRY_ABI,
                    slice=specs,
                )
            )
        except OverlayBankError as exc:
            if exc.code != "layout-members":
                failures.append(f"layout-members: got {exc.code}")
        else:
            failures.append("layout-members: accepted")
        mutation_count += 1
        entry_layout = "\n".join(layout_lines).replace(
            f"{specs[0].entry_symbol} = {specs[0].entry_target};",
            f"{specs[0].entry_symbol} = {specs[1].entry_target};",
        )
        layout_path.write_text(entry_layout + "\n", encoding="ascii")
        try:
            lint_layout(
                argparse.Namespace(
                    linker=layout_path,
                    expect_count=len(specs),
                    expect_capacity=MAX_SLICES,
                    expect_bank=BANK,
                    expect_address=STORAGE_BASE,
                    expect_entry_abi=ENTRY_ABI,
                    slice=specs,
                )
            )
        except OverlayBankError as exc:
            if exc.code != "layout-binding":
                failures.append(f"layout-entry-target: got {exc.code}")
        else:
            failures.append("layout-entry-target: accepted")
        manifest = _manifest(
            profile="selftest",
            abi_contract=abi,
            abi_sha256=_sha256(abi),
            elf=elf,
            image_path=image_path,
            header_path=header_path,
            image=image,
            header=header,
            parsed=parsed,
            slices=slices,
            expected_vma=vma,
            max_slice_bytes=max_bytes,
        )
        validate_manifest(manifest)

        def reject_manifest(name: str, mutate: Any) -> None:
            nonlocal mutation_count
            mutation_count += 1
            candidate = json.loads(json.dumps(manifest))
            mutate(candidate)
            try:
                validate_manifest(candidate)
                if candidate == manifest:
                    failures.append(f"{name}: mutation had no effect")
            except OverlayBankError:
                return
            failures.append(f"{name}: manifest mutation passed")

        reject_manifest("manifest-extra", lambda m: m.__setitem__("extra", 1))
        reject_manifest("manifest-missing", lambda m: m.pop("abi"))
        reject_manifest("manifest-format", lambda m: m.__setitem__("schema", "legacy"))
        reject_manifest("manifest-build-id", lambda m: m.__setitem__("profile_build_id", build_id ^ 1))
        reject_manifest("manifest-kind", lambda m: m["storage"].__setitem__("kind", "chip-ram"))
        reject_manifest("manifest-base", lambda m: m["storage"].__setitem__("address", STORAGE_BASE + 1))
        reject_manifest("manifest-limit", lambda m: m["storage"].__setitem__("limit", STORAGE_LIMIT - 1))
        reject_manifest("manifest-crc", lambda m: m["storage"].__setitem__("crc16", 0x10000))
        reject_manifest("manifest-sha", lambda m: m["storage"].__setitem__("sha256", "0"))
        reject_manifest("manifest-catalog", lambda m: m["catalog"].__setitem__("magic", "L65O"))
        reject_manifest("manifest-policy", lambda m: m["policy"].__setitem__("payload_alignment", 2))
        reject_manifest("manifest-vma", lambda m: m["policy"].__setitem__("common_vma", MAX_VMA + 1))
        reject_manifest("manifest-order", lambda m: m["slices"].reverse())
        reject_manifest("manifest-duplicate", lambda m: m["slices"][1].__setitem__("id", 0))
        reject_manifest("manifest-roles", lambda m: m["slices"][0].__setitem__("roles", ["runtime"]))
        reject_manifest("manifest-flags-type", lambda m: m["slices"][0].__setitem__("flags", "boot"))
        reject_manifest("manifest-slice-extra", lambda m: m["slices"][0].__setitem__("extra", 1))

        target = root / "artifact.bin"
        target.write_bytes(image)
        link = root / "artifact-link.bin"
        link.symlink_to(target)
        mutation_count += 1
        try:
            _regular_file(link, "selftest symlink")
        except OverlayBankError as exc:
            if exc.code != "symlink":
                failures.append(f"symlink: expected symlink, got {exc.code}")
        else:
            failures.append("symlink: accepted")

        output_link = root / "output-link.h"
        output_link.symlink_to(target)
        mutation_count += 1
        try:
            _atomic_write_many(((output_link, b"must not replace symlink\n"),))
        except OverlayBankError as exc:
            if exc.code != "symlink":
                failures.append(f"output-symlink: expected symlink, got {exc.code}")
        else:
            failures.append("output-symlink: accepted")

        duplicate = root / "duplicate.json"
        duplicate.write_text('{"schema":"a","schema":"b"}\n', encoding="ascii")
        mutation_count += 1
        try:
            _read_json(duplicate, "duplicate fixture")
        except OverlayBankError as exc:
            if exc.code != "duplicate-json-key":
                failures.append(f"duplicate-json: got {exc.code}")
        else:
            failures.append("duplicate-json: accepted")

    if mutation_count < 30:
        failures.append(f"mutation coverage too small: {mutation_count}")
    if failures:
        raise AssertionError("; ".join(failures))
    print(
        f"runtime-overlay-bank selftest: PASS slices={len(specs)} "
        f"mutations={mutation_count} image_bytes={len(image)}"
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--elf", type=Path, required=True, help="final linked ELF")
    parser.add_argument("--nm", type=Path, required=True, help="llvm-nm executable")
    parser.add_argument("--objcopy", type=Path, required=True, help="llvm-objcopy executable")
    parser.add_argument("--profile", required=True, help="exact product profile ID")
    parser.add_argument("--abi-contract", type=Path, required=True)
    parser.add_argument("--vma", type=_address, required=True, help="common Bank-0 slice VMA")
    parser.add_argument(
        "--max-slice-bytes",
        type=_slice_limit,
        default=MAX_SLICE_BYTES,
        help=f"profile-pinned slice limit (default and only valid value: {MAX_SLICE_BYTES})",
    )
    parser.add_argument(
        "--slice",
        action="append",
        type=_slice_spec,
        required=True,
        metavar="SPEC",
        help=(
            "repeatable ID:NAME:SECTION:START:END:ENTRY:FLAGS:ABI_VERSION:CAPS:ENTRY_TARGET; "
            "FLAGS is boot, runtime, runtime+reusable, or an integer"
        ),
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    parser.add_argument(
        "--header-mode",
        choices=("write", "verify"),
        default="write",
        help="write the bound header (bootstrap) or require an exact existing binding (final link)",
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_parser = commands.add_parser("pack", help="extract, pack, and verify all outputs")
    _common(pack_parser)
    verify_parser = commands.add_parser("verify", help="strictly reconstruct and verify outputs")
    _common(verify_parser)
    prepare_parser = commands.add_parser("prepare", help="emit the pre-link ABI config header")
    prepare_parser.add_argument("--abi-contract", type=Path, required=True)
    prepare_parser.add_argument("--header", type=Path, required=True)
    prepare_parser.add_argument("--profile", help="optional profile label for diagnostics")
    lint_parser = commands.add_parser(
        "lint-layout",
        help="check that configured slices exactly match linker members and bindings",
    )
    lint_parser.add_argument("--linker", type=Path, required=True)
    lint_parser.add_argument(
        "--expect-count",
        type=lambda value: _parse_int(value, "expected slice count", 1, MAX_SLICES),
        required=True,
    )
    lint_parser.add_argument(
        "--expect-capacity",
        type=lambda value: _parse_int(value, "catalog capacity", 1, 0xFF),
        required=True,
    )
    lint_parser.add_argument(
        "--expect-bank",
        type=lambda value: _parse_int(value, "storage bank", 0, 0xFF),
        required=True,
    )
    lint_parser.add_argument(
        "--expect-address",
        type=lambda value: _parse_int(value, "storage address", 0, 0x0FFFFFFF),
        required=True,
    )
    lint_parser.add_argument(
        "--expect-entry-abi",
        type=lambda value: _parse_int(value, "entry ABI", 0, 0xFFFF),
        required=True,
    )
    lint_parser.add_argument(
        "--slice",
        action="append",
        type=_slice_spec,
        required=True,
        metavar="SPEC",
    )
    commands.add_parser("selftest", help="run deterministic format and mutation tests")
    return parser.parse_args(argv)


def prepare(args: argparse.Namespace) -> int:
    _regular_file(args.abi_contract, "ABI contract")
    if args.profile is not None and (not args.profile or "\x00" in args.profile):
        _fail("profile", "profile must be a non-empty NUL-free string")
    build_id = _profile_build_id(_sha256(args.abi_contract))
    header = render_header(profile_build_id=build_id)
    _atomic_write_many(((args.header, header),))
    _regular_file(args.header, "runtime overlay config header")
    if args.header.read_bytes() != header:
        _fail("header-mismatch", "prepared C config header is not canonical")
    return build_id


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "lint-layout":
            lint_layout(args)
            print(
                f"runtime-overlay-bank: LAYOUT PASS slices={len(args.slice)} "
                f"linker={args.linker}"
            )
        elif args.command == "prepare":
            build_id = prepare(args)
            profile = f" profile={args.profile}" if args.profile else ""
            print(
                f"runtime-overlay-bank: PREPARE build_id=0x{build_id:08x}{profile} "
                f"header={args.header}"
            )
        elif args.command == "pack":
            pack(args)
            print(
                f"runtime-overlay-bank: PACK profile={args.profile} "
                f"slices={len(args.slice)} image={args.image}"
            )
        else:
            verify(args)
            print(
                f"runtime-overlay-bank: PASS profile={args.profile} "
                f"slices={len(args.slice)} image={args.image}"
            )
    except (OverlayBankError, AssertionError) as exc:
        code = getattr(exc, "code", "selftest")
        print(f"runtime-overlay-bank: FAIL error={code} detail={exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
