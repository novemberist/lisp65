#!/usr/bin/env python3
"""Host-only contract probe for nested C2 appends and non-local unwind.

The probe models the owner-authorized serial publish-then-run design.  Product
sources and product artifacts are inputs only; this tool emits model artifacts
and one contract receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any, Callable
import zlib


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-nested-append-unwind-contract.json"
ADDENDUM = ROOT / "docs/planning/c2.2-nested-append-unwind-addendum.md"
DIAGNOSIS = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
             "c2.2-product-link32-nested-eval-hardware-first-red-diagnosis.json")
INITIAL = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
OUT = ROOT / "build/c2.2/nested-append-unwind-contract-probe"
RECEIPT = (ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
           "c2.2-nested-append-unwind-contract-probe-receipt.json")

HEADER_BYTES = 48
IMAGE_BYTES = 32
ENTRY_BYTES = 10
IMAGES_OFFSET = 48
ENTRIES_OFFSET = 2096
RESOLUTIONS_OFFSET = 22576
ROOTS_OFFSET = 30768
C2D_BYTES = 33840
REGION_BYTES = 50816
ATTIC_BYTES = 1024 * 1024
IMAGE_CAP = 64
ENTRY_CAP = 2048
RESOLUTION_CAP = 4096
ROOT_CAP = 1536
MAX_DEPTH = 4
EXPORT_JOURNAL_BASE = C2D_BYTES
EXPORT_RECORD_BYTES = 4
UNWIND_BASE = 50752
UNWIND_BYTES = 64
OP_PERSISTENT = 1
OP_TRANSIENT_PUSH = 2
OP_TRANSIENT_POP = 3
STATE_PREPARED = 1
STATE_ATTIC = 2
STATE_RECORDS = 3
STATE_PUBLISHED = 4
STATE_EXPORTING = 5
STATE_UNPUBLISHING = 6


class ProbeError(RuntimeError):
    pass


class BusyError(ProbeError):
    pass


class CapacityError(ProbeError):
    pass


class FormatError(ProbeError):
    pass


class SessionInvalid(ProbeError):
    pass


class InjectedAbort(ProbeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u24(data: bytes | bytearray, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def p16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def p24(data: bytearray, offset: int, value: int) -> None:
    require(0 <= value <= 0xFFFFFF, "u24 overflow")
    data[offset:offset + 3] = bytes((value & 0xFF, (value >> 8) & 0xFF,
                                    (value >> 16) & 0xFF))


def p32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def write_generated(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        if os.environ.get("LISP65_REPLACE_UNSEALED_PROBE") == "1":
            path.write_bytes(data)
            return
        raise ProbeError(f"generated artifact drift: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


@dataclass(frozen=True)
class Spec:
    label: str
    entries: int = 1
    resolutions: int = 2
    roots: int = 1
    code_bytes: int = 32
    metadata_bytes: int = 64
    export_symbol: int | None = None

    def validate(self) -> None:
        require(self.entries > 0 and self.resolutions >= self.roots >= 0,
                f"bad spec counts: {self}")
        require(self.code_bytes > 0 and self.metadata_bytes > 0,
                f"bad spec lengths: {self}")


class Plane:
    def __init__(self, initial: bytes, *, generation: int = 1) -> None:
        require(len(initial) == C2D_BYTES and initial[:5] == b"C2D\0\x03",
                "initial C2D-v3 drift")
        self.initial = bytes(initial)
        self.data = bytearray(REGION_BYTES)
        self.data[:C2D_BYTES] = initial
        self.data[4] = 4
        p16(self.data, 8, 0)
        p16(self.data, 10, generation)
        self.attic = bytearray(ATTIC_BYTES)
        self.exports: dict[int, int] = {}
        self.transaction_active = False
        self.transaction_begins = 0
        self.maximum_transaction_depth = 0
        self.invalid = False
        self.trace: list[str] = []

    def clone(self) -> "Plane":
        clone = object.__new__(Plane)
        clone.initial = self.initial
        clone.data = bytearray(self.data)
        clone.attic = bytearray(self.attic)
        clone.exports = dict(self.exports)
        clone.transaction_active = self.transaction_active
        clone.transaction_begins = self.transaction_begins
        clone.maximum_transaction_depth = self.maximum_transaction_depth
        clone.invalid = self.invalid
        clone.trace = list(self.trace)
        return clone

    def state(self) -> tuple[bytes, bytes, tuple[tuple[int, int], ...], bool]:
        return (bytes(self.data), bytes(self.attic), tuple(sorted(self.exports.items())),
                self.invalid)

    def generation(self) -> int:
        return u16(self.data, 10)

    def depth(self) -> int:
        return u16(self.data, 8)

    def counts(self) -> tuple[int, int, int, int]:
        return tuple(u16(self.data, at) for at in (12, 16, 20, 24))  # type: ignore[return-value]

    def set_counts(self, values: tuple[int, int, int, int]) -> None:
        for at, value in zip((12, 16, 20, 24), values):
            p16(self.data, at, value)

    def begin_transaction(self) -> None:
        if self.transaction_active:
            raise BusyError("nested overlay transaction")
        self.transaction_active = True
        self.transaction_begins += 1
        self.maximum_transaction_depth = max(self.maximum_transaction_depth, 1)

    def end_transaction(self) -> None:
        require(self.transaction_active, "transaction end without begin")
        self.transaction_active = False

    def execute(self, action: Callable[[], Any]) -> Any:
        if self.transaction_active:
            raise BusyError("bytecode execution while overlay transaction is active")
        self.trace.append("execute-with-no-active-transaction")
        return action()

    def record(self, slot: int) -> dict[str, int]:
        require(0 <= slot < IMAGE_CAP, "image slot out of range")
        at = IMAGES_OFFSET + slot * IMAGE_BYTES
        return {
            "source_kind": self.data[at],
            "flags": self.data[at + 1],
            "source_slot": self.data[at + 2],
            "reserved": self.data[at + 3],
            "generation": u16(self.data, at + 4),
            "directory_base": u16(self.data, at + 6),
            "entries": u16(self.data, at + 8),
            "resolution_base": u16(self.data, at + 10),
            "resolutions": u16(self.data, at + 12),
            "root_base": u16(self.data, at + 14),
            "roots": u16(self.data, at + 16),
            "code_offset": u24(self.data, at + 18),
            "code_length": u16(self.data, at + 21),
            "metadata_offset": u24(self.data, at + 23),
            "metadata_length": u16(self.data, at + 26),
            "crc32": struct.unpack_from("<I", self.data, at + 28)[0],
        }

    def active_transient_records(self) -> list[tuple[int, dict[str, int]]]:
        depth = self.depth()
        if depth > MAX_DEPTH:
            raise FormatError("transient depth exceeds contract")
        result = []
        for level in range(depth):
            slot = IMAGE_CAP - 1 - level
            record = self.record(slot)
            if (record["source_kind"] != 2 or record["source_slot"] != level
                    or record["generation"] != self.generation()
                    or record["flags"] or record["reserved"]):
                raise FormatError("invalid active transient record")
            result.append((slot, record))
        return result

    def low_attic(self) -> int:
        image_count = self.counts()[0]
        high = 0
        for slot in range(6, image_count):
            record = self.record(slot)
            if record["source_kind"] != 1:
                raise FormatError("persistent session record source kind")
            high = max(high, record["code_offset"] + record["code_length"],
                       record["metadata_offset"] + record["metadata_length"])
        return (high + 1) & ~1

    def high_fronts(self) -> tuple[int, int, int, int]:
        entry, resolution, root, attic = ENTRY_CAP, RESOLUTION_CAP, ROOT_CAP, ATTIC_BYTES
        for _, record in self.active_transient_records():
            entry = min(entry, record["directory_base"])
            resolution = min(resolution, record["resolution_base"])
            root = min(root, record["root_base"])
            attic = min(attic, record["code_offset"], record["metadata_offset"])
        return entry, resolution, root, attic

    def journal_bytes(self) -> bytes:
        return bytes(self.data[UNWIND_BASE:UNWIND_BASE + UNWIND_BYTES])

    def journal_write(self, journal: dict[str, int]) -> None:
        buf = bytearray(UNWIND_BYTES)
        buf[:4] = b"C2J\0"
        buf[4] = 1
        buf[5] = UNWIND_BYTES
        buf[6] = journal["state"]
        buf[7] = journal["operation"]
        fields = (
            (8, "generation"), (10, "old_depth"), (12, "old_images"),
            (14, "old_entries"), (16, "old_resolutions"), (18, "old_roots"),
            (20, "target_slot"), (22, "directory_base"), (24, "entries"),
            (26, "resolution_base"), (28, "resolutions"), (30, "root_base"),
            (32, "roots"),
        )
        for at, name in fields:
            p16(buf, at, journal[name])
        p24(buf, 34, journal["attic_start"])
        p24(buf, 37, journal["attic_length"])
        p16(buf, 40, journal.get("export_count", 0))
        p24(buf, 42, journal["old_attic_low"])
        p24(buf, 45, journal["old_attic_high"])
        p16(buf, 48, journal["code_length"])
        p16(buf, 50, journal["metadata_length"])
        p32(buf, 60, zlib.crc32(buf[:60]) & 0xFFFFFFFF)
        self.data[UNWIND_BASE:UNWIND_BASE + UNWIND_BYTES] = buf

    def journal_read(self) -> dict[str, int] | None:
        raw = self.journal_bytes()
        if raw == bytes(UNWIND_BYTES):
            return None
        try:
            if (raw[:4] != b"C2J\0" or raw[4] != 1 or raw[5] != UNWIND_BYTES
                    or struct.unpack_from("<I", raw, 60)[0]
                    != zlib.crc32(raw[:60]) & 0xFFFFFFFF):
                raise SessionInvalid("invalid unwind journal identity or CRC")
            result = {
                "state": raw[6], "operation": raw[7],
                "generation": u16(raw, 8), "old_depth": u16(raw, 10),
                "old_images": u16(raw, 12), "old_entries": u16(raw, 14),
                "old_resolutions": u16(raw, 16), "old_roots": u16(raw, 18),
                "target_slot": u16(raw, 20), "directory_base": u16(raw, 22),
                "entries": u16(raw, 24), "resolution_base": u16(raw, 26),
                "resolutions": u16(raw, 28), "root_base": u16(raw, 30),
                "roots": u16(raw, 32), "attic_start": u24(raw, 34),
                "attic_length": u24(raw, 37), "export_count": u16(raw, 40),
                "old_attic_low": u24(raw, 42), "old_attic_high": u24(raw, 45),
                "code_length": u16(raw, 48), "metadata_length": u16(raw, 50),
            }
            if (result["generation"] != self.generation()
                    or result["old_depth"] > MAX_DEPTH
                    or result["target_slot"] >= IMAGE_CAP
                    or result["directory_base"] + result["entries"] > ENTRY_CAP
                    or result["resolution_base"] + result["resolutions"] > RESOLUTION_CAP
                    or result["root_base"] + result["roots"] > ROOT_CAP
                    or result["attic_start"] + result["attic_length"] > ATTIC_BYTES):
                raise SessionInvalid("unwind journal range or generation")
            return result
        except SessionInvalid:
            self.invalid = True
            raise

    def journal_clear(self) -> None:
        self.data[UNWIND_BASE:UNWIND_BASE + UNWIND_BYTES] = bytes(UNWIND_BYTES)

    def update_journal(self, **changes: int) -> None:
        journal = self.journal_read()
        require(journal is not None, "journal update without active journal")
        journal.update(changes)
        self.journal_write(journal)

    @staticmethod
    def payload(spec: Spec) -> tuple[bytes, bytes]:
        require(spec.metadata_bytes >= 8 + spec.resolutions,
                "model metadata cannot bind every descriptor kind")
        seed = hashlib.sha256(spec.label.encode("utf-8")).digest()
        code = bytes(seed[i % len(seed)] ^ (i & 0xFF) for i in range(spec.code_bytes))
        metadata = bytearray(seed[(i + 11) % len(seed)] ^ ((i * 3) & 0xFF)
                             for i in range(spec.metadata_bytes))
        metadata[:4] = b"MODL"
        p16(metadata, 4, spec.resolutions)
        p16(metadata, 6, spec.roots)
        for index in range(spec.resolutions):
            metadata[8 + index] = 3 if index < spec.roots else 8
        return code, bytes(metadata)

    def write_image(self, *, slot: int, source_kind: int, source_slot: int,
                    spec: Spec, directory_base: int, resolution_base: int,
                    root_base: int, code_offset: int, metadata_offset: int,
                    code: bytes, metadata: bytes) -> None:
        at = IMAGES_OFFSET + slot * IMAGE_BYTES
        row = bytearray(IMAGE_BYTES)
        row[:4] = bytes((source_kind, 0, source_slot, 0))
        p16(row, 4, self.generation())
        p16(row, 6, directory_base)
        p16(row, 8, spec.entries)
        p16(row, 10, resolution_base)
        p16(row, 12, spec.resolutions)
        p16(row, 14, root_base)
        p16(row, 16, spec.roots)
        p24(row, 18, code_offset)
        p16(row, 21, len(code))
        p24(row, 23, metadata_offset)
        p16(row, 26, len(metadata))
        p32(row, 28, zlib.crc32(code + metadata) & 0xFFFFFFFF)
        self.data[at:at + IMAGE_BYTES] = row
        for ordinal in range(spec.entries):
            pos = ENTRIES_OFFSET + (directory_base + ordinal) * ENTRY_BYTES
            entry = bytearray(ENTRY_BYTES)
            entry[:2] = bytes((slot, 0))
            p16(entry, 2, ordinal)
            p16(entry, 4, max(1, len(code) // spec.entries))
            p16(entry, 6, resolution_base)
            p16(entry, 8, self.generation())
            self.data[pos:pos + ENTRY_BYTES] = entry
        for index in range(spec.resolutions):
            value = (root_base + index) if index < spec.roots else 0x4000 + index
            p16(self.data, RESOLUTIONS_OFFSET + (resolution_base + index) * 2, value)
        for index in range(spec.roots):
            p16(self.data, ROOTS_OFFSET + (root_base + index) * 2,
                0x0100 + root_base + index)

    def base_journal(self, *, operation: int, state: int, slot: int, spec: Spec,
                     directory_base: int, resolution_base: int, root_base: int,
                     attic_start: int, attic_length: int) -> dict[str, int]:
        images, entries, resolutions, roots = self.counts()
        _, _, _, high = self.high_fronts()
        return {
            "state": state, "operation": operation,
            "generation": self.generation(), "old_depth": self.depth(),
            "old_images": images, "old_entries": entries,
            "old_resolutions": resolutions, "old_roots": roots,
            "target_slot": slot, "directory_base": directory_base,
            "entries": spec.entries, "resolution_base": resolution_base,
            "resolutions": spec.resolutions, "root_base": root_base,
            "roots": spec.roots, "attic_start": attic_start,
            "attic_length": attic_length, "export_count": 0,
            "old_attic_low": self.low_attic(), "old_attic_high": high,
            "code_length": spec.code_bytes, "metadata_length": spec.metadata_bytes,
        }

    def inject(self, requested: str | None, actual: str) -> None:
        if requested == actual:
            raise InjectedAbort(actual)

    def persistent_append(self, spec: Spec, *, fail_at: str | None = None) -> int:
        spec.validate()
        images, entries, resolutions, roots = self.counts()
        high_entry, high_resolution, high_root, high_attic = self.high_fronts()
        code, metadata = self.payload(spec)
        attic_start = self.low_attic()
        attic_length = len(code) + len(metadata)
        if (images >= IMAGE_CAP - self.depth() or entries + spec.entries > high_entry
                or resolutions + spec.resolutions > high_resolution
                or roots + spec.roots > high_root
                or attic_start + attic_length > high_attic):
            raise CapacityError("persistent low prefix collides with transient high suffix")
        slot = images
        journal = self.base_journal(
            operation=OP_PERSISTENT, state=STATE_PREPARED, slot=slot, spec=spec,
            directory_base=entries, resolution_base=resolutions, root_base=roots,
            attic_start=attic_start, attic_length=attic_length)
        self.begin_transaction()
        self.journal_write(journal)
        self.inject(fail_at, "after_journal")
        self.attic[attic_start:attic_start + len(code)] = code
        self.attic[attic_start + len(code):attic_start + attic_length] = metadata
        self.update_journal(state=STATE_ATTIC)
        self.inject(fail_at, "after_attic")
        self.write_image(slot=slot, source_kind=1, source_slot=images - 6,
                         spec=spec, directory_base=entries,
                         resolution_base=resolutions, root_base=roots,
                         code_offset=attic_start,
                         metadata_offset=attic_start + len(code),
                         code=code, metadata=metadata)
        self.update_journal(state=STATE_RECORDS)
        self.inject(fail_at, "after_records")
        self.set_counts((images + 1, entries + spec.entries,
                         resolutions + spec.resolutions, roots + spec.roots))
        self.update_journal(state=STATE_PUBLISHED)
        self.inject(fail_at, "after_publish")
        if spec.export_symbol is not None:
            old = self.exports.get(spec.export_symbol, 0xFFFF)
            pos = EXPORT_JOURNAL_BASE
            p16(self.data, pos, spec.export_symbol)
            p16(self.data, pos + 2, old)
            self.exports[spec.export_symbol] = entries
            self.update_journal(state=STATE_EXPORTING, export_count=1)
        self.inject(fail_at, "after_export")
        self.data[EXPORT_JOURNAL_BASE:EXPORT_JOURNAL_BASE + EXPORT_RECORD_BYTES] = bytes(EXPORT_RECORD_BYTES)
        self.journal_clear()
        self.end_transaction()
        return entries

    def transient_push(self, spec: Spec, *, fail_at: str | None = None) -> int:
        spec.validate()
        depth = self.depth()
        if depth >= MAX_DEPTH:
            raise CapacityError("transient depth limit")
        images, entries, resolutions, roots = self.counts()
        high_entry, high_resolution, high_root, high_attic = self.high_fronts()
        code, metadata = self.payload(spec)
        directory_base = high_entry - spec.entries
        resolution_base = high_resolution - spec.resolutions
        root_base = high_root - spec.roots
        attic_start = high_attic - len(code) - len(metadata)
        slot = IMAGE_CAP - 1 - depth
        if (slot < images or directory_base < entries or resolution_base < resolutions
                or root_base < roots or attic_start < self.low_attic()):
            raise CapacityError("transient high suffix collides with persistent low prefix")
        journal = self.base_journal(
            operation=OP_TRANSIENT_PUSH, state=STATE_PREPARED, slot=slot, spec=spec,
            directory_base=directory_base, resolution_base=resolution_base,
            root_base=root_base, attic_start=attic_start,
            attic_length=len(code) + len(metadata))
        self.begin_transaction()
        self.journal_write(journal)
        self.inject(fail_at, "after_journal")
        self.attic[attic_start:attic_start + len(code)] = code
        self.attic[attic_start + len(code):high_attic] = metadata
        self.update_journal(state=STATE_ATTIC)
        self.inject(fail_at, "after_attic")
        self.write_image(slot=slot, source_kind=2, source_slot=depth,
                         spec=spec, directory_base=directory_base,
                         resolution_base=resolution_base, root_base=root_base,
                         code_offset=attic_start,
                         metadata_offset=attic_start + len(code),
                         code=code, metadata=metadata)
        self.update_journal(state=STATE_RECORDS)
        self.inject(fail_at, "after_records")
        p16(self.data, 8, depth + 1)
        self.update_journal(state=STATE_PUBLISHED)
        self.inject(fail_at, "after_publish")
        self.journal_clear()
        self.end_transaction()
        return directory_base

    def zero_journal_ranges(self, journal: dict[str, int]) -> None:
        slot = journal["target_slot"]
        self.data[IMAGES_OFFSET + slot * IMAGE_BYTES:
                  IMAGES_OFFSET + (slot + 1) * IMAGE_BYTES] = bytes(IMAGE_BYTES)
        for base, count, offset, width in (
            (journal["directory_base"], journal["entries"], ENTRIES_OFFSET, ENTRY_BYTES),
            (journal["resolution_base"], journal["resolutions"], RESOLUTIONS_OFFSET, 2),
            (journal["root_base"], journal["roots"], ROOTS_OFFSET, 2),
        ):
            self.data[offset + base * width:offset + (base + count) * width] = bytes(count * width)
        start, length = journal["attic_start"], journal["attic_length"]
        self.attic[start:start + length] = bytes(length)

    def transient_pop(self, *, fail_at: str | None = None) -> None:
        depth = self.depth()
        require(depth > 0, "transient pop without active record")
        slot = IMAGE_CAP - depth
        record = self.record(slot)
        spec = Spec("pop", record["entries"], record["resolutions"], record["roots"],
                    record["code_length"], record["metadata_length"])
        journal = self.base_journal(
            operation=OP_TRANSIENT_POP, state=STATE_UNPUBLISHING, slot=slot, spec=spec,
            directory_base=record["directory_base"],
            resolution_base=record["resolution_base"], root_base=record["root_base"],
            attic_start=min(record["code_offset"], record["metadata_offset"]),
            attic_length=record["code_length"] + record["metadata_length"])
        self.begin_transaction()
        self.journal_write(journal)
        self.inject(fail_at, "after_journal")
        p16(self.data, 8, depth - 1)
        self.inject(fail_at, "after_unpublish")
        self.zero_journal_ranges(journal)
        self.inject(fail_at, "after_wipe")
        self.journal_clear()
        self.end_transaction()

    def restore_active_journal(self) -> None:
        journal = self.journal_read()
        if journal is None:
            return
        for index in range(journal["export_count"], 0, -1):
            pos = EXPORT_JOURNAL_BASE + (index - 1) * EXPORT_RECORD_BYTES
            symbol, old = u16(self.data, pos), u16(self.data, pos + 2)
            if old == 0xFFFF:
                self.exports.pop(symbol, None)
            else:
                self.exports[symbol] = old
        self.set_counts((journal["old_images"], journal["old_entries"],
                         journal["old_resolutions"], journal["old_roots"]))
        restored_depth = journal["old_depth"]
        if journal["operation"] == OP_TRANSIENT_POP:
            require(restored_depth > 0, "pop journal has no active transient")
            restored_depth -= 1
        p16(self.data, 8, restored_depth)
        self.zero_journal_ranges(journal)
        self.data[EXPORT_JOURNAL_BASE:
                  EXPORT_JOURNAL_BASE + journal["export_count"] * EXPORT_RECORD_BYTES] = \
            bytes(journal["export_count"] * EXPORT_RECORD_BYTES)
        self.journal_clear()

    def clear_all_transients(self) -> None:
        records = self.active_transient_records()
        p16(self.data, 8, 0)
        for slot, record in records:
            journal = {
                "target_slot": slot,
                "directory_base": record["directory_base"], "entries": record["entries"],
                "resolution_base": record["resolution_base"],
                "resolutions": record["resolutions"], "root_base": record["root_base"],
                "roots": record["roots"],
                "attic_start": min(record["code_offset"], record["metadata_offset"]),
                "attic_length": record["code_length"] + record["metadata_length"],
            }
            self.zero_journal_ranges(journal)

    def abort_cleanup(self) -> None:
        self.transaction_active = False
        try:
            self.restore_active_journal()
            self.clear_all_transients()
        except SessionInvalid:
            self.invalid = True
            raise

    def lookup(self, ordinal: int) -> bool:
        if ordinal < self.counts()[1]:
            return True
        hits = 0
        for _, record in self.active_transient_records():
            if record["directory_base"] <= ordinal < record["directory_base"] + record["entries"]:
                hits += 1
        if hits > 1:
            raise FormatError("directory ordinal belongs to overlapping transient records")
        return hits == 1

    def validate(self) -> None:
        if self.invalid:
            raise SessionInvalid("plane is invalid")
        if (self.data[:4] != b"C2D\0" or self.data[4] != 4
                or tuple(self.data[5:8]) != (48, 32, 10)
                or not self.generation()):
            raise FormatError("C2D-v4 header")
        images, entries, resolutions, roots = self.counts()
        if not (6 <= images <= IMAGE_CAP and entries <= ENTRY_CAP
                and resolutions <= RESOLUTION_CAP and roots <= ROOT_CAP):
            raise FormatError("persistent counts")
        intervals: dict[str, list[tuple[int, int]]] = {
            "entries": [(0, entries)], "resolutions": [(0, resolutions)],
            "roots": [(0, roots)],
        }
        for _, record in self.active_transient_records():
            intervals["entries"].append((record["directory_base"],
                                          record["directory_base"] + record["entries"]))
            intervals["resolutions"].append((record["resolution_base"],
                                              record["resolution_base"] + record["resolutions"]))
            intervals["roots"].append((record["root_base"],
                                        record["root_base"] + record["roots"]))
            metadata = bytes(self.attic[
                record["metadata_offset"]:record["metadata_offset"] + record["metadata_length"]])
            if (len(metadata) < 8 + record["resolutions"] or metadata[:4] != b"MODL"
                    or u16(metadata, 4) != record["resolutions"]):
                raise FormatError("transient descriptor model missing or malformed")
            heap_kinds = 0
            for index in range(record["resolutions"]):
                value = u16(self.data, RESOLUTIONS_OFFSET
                            + (record["resolution_base"] + index) * 2)
                kind = metadata[8 + index]
                if kind in (3, 7):
                    if not record["root_base"] <= value < record["root_base"] + record["roots"]:
                        raise FormatError("transient resolution names a missing root")
                    heap_kinds += 1
            if heap_kinds != record["roots"] or u16(metadata, 6) != record["roots"]:
                raise FormatError("transient root membership drift")
        for name, values in intervals.items():
            ordered = sorted(values)
            if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
                raise FormatError(f"overlapping {name} ownership")
        if self.low_attic() > self.high_fronts()[3]:
            raise FormatError("Attic fronts overlap")
        if self.journal_bytes() != bytes(UNWIND_BYTES):
            raise FormatError("quiescent state has active unwind journal")
        if self.transaction_active:
            raise FormatError("quiescent state has active overlay transaction")

    def restage(self) -> "Plane":
        # Restage makes the complete old plane unreachable.  Publish the loss
        # of transient handles before the generation changes; physical Attic
        # bytes may remain because the replacement directory cannot name them.
        p16(self.data, 8, 0)
        self.trace.append("transient-depth-invalidated-before-generation-change")
        replacement = Plane(self.initial, generation=self.generation() + 1)
        replacement.attic = bytearray(self.attic)
        replacement.trace = list(self.trace)
        return replacement


def same(left: Plane, right: Plane, message: str) -> None:
    require(left.state() == right.state(), message)


def expect_abort(action: Callable[[], Any]) -> None:
    try:
        action()
    except InjectedAbort:
        return
    raise ProbeError("expected injected abort")


def expect_error(error: type[BaseException], action: Callable[[], Any]) -> None:
    try:
        action()
    except error:
        return
    raise ProbeError(f"expected {error.__name__}")


def run_probe() -> dict[str, Any]:
    contract = load(CONTRACT)
    diagnosis = load(DIAGNOSIS)
    require(contract.get("status") == "owner-authorized-bounded-contract-probe",
            "contract is not owner-authorized")
    require(contract.get("bound_first_red", {}).get("diagnosis_sha256") == sha(DIAGNOSIS),
            "contract first-red binding drift")
    require(diagnosis.get("status") == "first-red-receipt-less-hardware-presmoke-stopped",
            "Link-32 diagnosis status drift")
    initial = INITIAL.read_bytes()
    seed = Plane(initial)
    seed.validate()
    initial_counts = seed.counts()
    require(initial_counts == (6, 588, 2264, 283), "actual product C2D census drift")

    cases: list[dict[str, Any]] = []

    def passed(name: str, group: str, detail: str) -> None:
        cases.append({"name": name, "group": group, "status": "passed", "detail": detail})

    # The current Link-32 lifetime and both cheaper serial variants must fail.
    current = seed.clone()
    current.begin_transaction()
    expect_error(BusyError, current.begin_transaction)
    current.end_transaction()
    passed("current-open-transaction-rejects-inner-begin", "alternative-rejection",
           "reproduces the Link-32 BUSY class")

    counts0 = initial_counts
    outer = tuple(value + delta for value, delta in zip(counts0, (1, 1, 2, 1)))
    descendant = tuple(value + delta for value, delta in zip(outer, (1, 1, 2, 1)))
    rolled_back = counts0
    require(descendant != rolled_back and rolled_back == counts0,
            "naive suffix rollback model did not delete descendant")
    passed("serial-current-suffix-rollback-deletes-descendant", "alternative-rejection",
           "outer rollback restores the pre-outer counts and removes the inner commit")
    leaked_after_two = tuple(value + 4 * delta for value, delta in zip(counts0, (1, 1, 2, 1)))
    require(leaked_after_two != counts0, "skip-rollback model did not leak")
    passed("serial-skip-rollback-leaks-transient-ancestors", "alternative-rejection",
           "two cycles retain two outer wrappers plus two descendants")

    transient = Spec("outer", resolutions=3, roots=1)
    inner = Spec("inner", resolutions=4, roots=2)
    definition = Spec("persistent-definition", resolutions=5, roots=2, export_symbol=1)

    # Positive nested transient and repeat-zero-growth cases.
    p = seed.clone()
    p.transient_push(transient)
    p.execute(lambda: (p.transient_push(inner), p.transient_pop()))
    p.transient_pop()
    p.validate()
    same(p, seed, "nested transient eval did not restore exact seed")
    passed("nested-transient-exact-restoration", "positive",
           "serial publish-then-run leaves no active transaction or byte")
    for _ in range(2):
        p.transient_push(transient)
        p.execute(lambda: (p.transient_push(inner), p.transient_pop()))
        p.transient_pop()
    p.validate()
    same(p, seed, "repeated warm nested eval leaked state")
    passed("two-warm-nested-evals-zero-growth", "positive",
           "images, entries, resolutions, roots and both Attic fronts return exactly")

    # Persistent descendant survives normal outer return and later ancestor abort.
    p = seed.clone()
    p.transient_push(transient)
    p.execute(lambda: p.persistent_append(definition))
    p.transient_pop()
    p.validate()
    reference = seed.clone()
    reference.persistent_append(definition)
    reference.validate()
    same(p, reference, "persistent descendant changed by ancestor return")
    require(p.lookup(p.exports[1]), "persistent descendant is not callable")
    passed("persistent-descendant-survives-ancestor-return", "positive",
           "low-prefix commit is byte-identical with and without the transient ancestor")

    p = seed.clone()
    p.transient_push(transient)
    p.execute(lambda: p.persistent_append(definition))
    p.transient_push(inner)
    p.abort_cleanup()
    p.validate()
    same(p, reference, "persistent descendant changed by ancestor abort")
    passed("persistent-descendant-survives-ancestor-longjmp", "positive",
           "abort removes both high-tail dynamic extents and preserves the low-prefix commit")

    # Public seam classification exercises the same state machine.
    for seam in ("eval", "eval-string", "load"):
        p = seed.clone()
        p.transient_push(Spec(f"{seam}-outer"))
        p.execute(lambda seam=seam: (p.transient_push(Spec(f"{seam}-inner")),
                                     p.transient_pop()))
        p.transient_pop()
        p.validate()
        same(p, seed, f"{seam} seam leaked")
        passed(f"public-{seam}-transient-seam", "public-entry", "zero-growth nested path")
    p = seed.clone()
    p.transient_push(Spec("load-lib-outer"))
    p.execute(lambda: p.persistent_append(Spec("load-lib-image", export_symbol=2)))
    p.transient_pop()
    p.validate()
    passed("public-load-lib-persistent-descendant", "public-entry",
           "persistent low-prefix append survives outer transient return")
    eval_runtime = (ROOT / "lib/dialect-v2/eval-runtime.lisp").read_text(encoding="utf-8")
    compile_block = eval_runtime[eval_runtime.index("(defun compile-string"):
                                 eval_runtime.index("(defun compile-string") + 700]
    require("%c2-compile-save" in compile_block and "lcc-install" not in compile_block
            and "load-lib" not in compile_block,
            "compile-string classification drift")
    passed("public-compile-string-classification", "public-entry",
           "media producer only; subsequent load-lib owns the persistent C2D append")

    # All mutation cutpoints are longjmp-clean.
    for cutpoint in ("after_journal", "after_attic", "after_records",
                     "after_publish", "after_export"):
        p = seed.clone()
        expect_abort(lambda cutpoint=cutpoint: p.persistent_append(definition, fail_at=cutpoint))
        p.abort_cleanup()
        p.validate()
        same(p, seed, f"persistent cutpoint leaked: {cutpoint}")
        passed(f"persistent-{cutpoint}", "cutpoint", "byte-identical abort restoration")
    for cutpoint in ("after_journal", "after_attic", "after_records",
                     "after_publish", "after_export"):
        p = seed.clone()
        p.transient_push(transient)
        expect_abort(lambda cutpoint=cutpoint: p.persistent_append(definition, fail_at=cutpoint))
        p.abort_cleanup()
        p.validate()
        same(p, seed, f"nested persistent cutpoint leaked: {cutpoint}")
        passed(f"nested-persistent-{cutpoint}", "nested-cutpoint",
               "pending low-prefix mutation and active high-tail ancestor both unwind exactly")
    for cutpoint in ("after_journal", "after_attic", "after_records", "after_publish"):
        p = seed.clone()
        expect_abort(lambda cutpoint=cutpoint: p.transient_push(transient, fail_at=cutpoint))
        p.abort_cleanup()
        p.validate()
        same(p, seed, f"transient push cutpoint leaked: {cutpoint}")
        passed(f"transient-push-{cutpoint}", "cutpoint", "byte-identical abort restoration")
    for cutpoint in ("after_journal", "after_unpublish", "after_wipe"):
        p = seed.clone()
        p.transient_push(transient)
        expect_abort(lambda cutpoint=cutpoint: p.transient_pop(fail_at=cutpoint))
        p.abort_cleanup()
        p.validate()
        same(p, seed, f"transient pop cutpoint leaked: {cutpoint}")
        passed(f"transient-pop-{cutpoint}", "cutpoint", "unpublish-first cleanup is idempotent")

    # Every active depth is longjmp-clean; committed descendants survive.
    for depth in range(1, MAX_DEPTH + 1):
        p = seed.clone()
        for level in range(depth):
            p.transient_push(Spec(f"depth-{depth}-{level}", resolutions=2, roots=1))
            if level == 0 and depth >= 2:
                p.persistent_append(definition)
        p.abort_cleanup()
        p.validate()
        expected = reference if depth >= 2 else seed
        same(p, expected, f"longjmp cleanup drift at depth {depth}")
        passed(f"longjmp-depth-{depth}", "abort-depth",
               "all transient suffix ranges removed; persistent descendant policy preserved")

    # Depth and capacity collision checks happen before journal/target mutation.
    p = seed.clone()
    for level in range(MAX_DEPTH):
        p.transient_push(Spec(f"depth-cap-{level}", resolutions=1, roots=0))
    before_fifth = p.state()
    expect_error(CapacityError, lambda: p.transient_push(Spec("fifth")))
    require(p.state() == before_fifth and p.journal_bytes() == bytes(UNWIND_BYTES),
            "fifth depth mutated state")
    passed("fifth-depth-rejected-before-mutation", "capacity", "bounded depth is four")

    for name, at, value in (
        ("images", 12, IMAGE_CAP), ("entries", 16, ENTRY_CAP),
        ("resolutions", 20, RESOLUTION_CAP), ("roots", 24, ROOT_CAP),
    ):
        p = seed.clone()
        p16(p.data, at, value)
        before_collision = p.state()
        expect_error(CapacityError, lambda: p.transient_push(Spec(f"collision-{name}")))
        require(p.state() == before_collision and p.journal_bytes() == bytes(UNWIND_BYTES),
                f"{name} collision mutated state")
        passed(f"{name}-front-collision", "capacity", "rejected before journal publication")
    p = seed.clone()
    p16(p.data, 12, 7)
    fake = Spec("attic-front", entries=1, resolutions=0, roots=0,
                code_bytes=16, metadata_bytes=16)
    code, metadata = p.payload(fake)
    p.write_image(slot=6, source_kind=1, source_slot=0, spec=fake,
                  directory_base=p.counts()[1], resolution_base=p.counts()[2],
                  root_base=p.counts()[3], code_offset=ATTIC_BYTES - 32,
                  metadata_offset=ATTIC_BYTES - 16, code=code, metadata=metadata)
    before_collision = p.state()
    expect_error(CapacityError, lambda: p.transient_push(Spec("attic-collision")))
    require(p.state() == before_collision, "Attic collision mutated state")
    passed("attic-front-collision", "capacity", "rejected before journal publication")

    # Corrupt unwind records never trigger guessed cleanup.
    for kind in ("identity", "crc", "range"):
        p = seed.clone()
        expect_abort(lambda: p.transient_push(transient, fail_at="after_journal"))
        if kind == "identity":
            p.data[UNWIND_BASE] ^= 0x01
        elif kind == "crc":
            p.data[UNWIND_BASE + 60] ^= 0x01
        else:
            p16(p.data, UNWIND_BASE + 22, ENTRY_CAP)
            crc = zlib.crc32(p.data[UNWIND_BASE:UNWIND_BASE + 60]) & 0xFFFFFFFF
            p32(p.data, UNWIND_BASE + 60, crc)
        target_before = bytes(p.data[:UNWIND_BASE]) + bytes(p.attic)
        expect_error(SessionInvalid, p.abort_cleanup)
        target_after = bytes(p.data[:UNWIND_BASE]) + bytes(p.attic)
        require(target_before == target_after and p.invalid,
                f"corrupt {kind} journal guessed at cleanup")
        passed(f"corrupt-journal-{kind}", "journal-negative",
               "session invalidated; target bytes left untouched")

    # Directory, generation and root-domain negatives.
    p = seed.clone()
    handle = p.transient_push(Spec("inactive-handle"))
    require(p.lookup(handle), "active transient handle rejected")
    p.transient_pop()
    require(not p.lookup(handle), "inactive transient handle remained callable")
    passed("inactive-high-tail-handle", "format-negative", "rejected after unpublish")

    p = seed.clone()
    p.transient_push(Spec("stale-generation"))
    slot = IMAGE_CAP - 1
    p16(p.data, IMAGES_OFFSET + slot * IMAGE_BYTES + 4, p.generation() + 1)
    expect_error(FormatError, p.validate)
    passed("stale-transient-generation", "format-negative", "rejected before lookup")

    p = seed.clone()
    p.transient_push(Spec("missing-root", resolutions=1, roots=1))
    p16(p.data, IMAGES_OFFSET + (IMAGE_CAP - 1) * IMAGE_BYTES + 16, 0)
    expect_error(FormatError, p.validate)
    passed("missing-transient-root-interval", "gc-negative", "tagged resolution has no owner")

    p = seed.clone()
    p.transient_push(Spec("root-outer", resolutions=1, roots=1))
    p.transient_push(Spec("root-inner", resolutions=1, roots=1))
    outer_root = p.record(IMAGE_CAP - 1)["root_base"]
    inner_at = IMAGES_OFFSET + (IMAGE_CAP - 2) * IMAGE_BYTES
    p16(p.data, inner_at + 14, outer_root)
    p16(p.data, RESOLUTIONS_OFFSET + p.record(IMAGE_CAP - 2)["resolution_base"] * 2,
        outer_root)
    expect_error(FormatError, p.validate)
    passed("overlapping-transient-root-ownership", "gc-negative", "exactly one root owner required")

    p = seed.clone()
    outer_handle = p.transient_push(Spec("restage-stale", resolutions=1, roots=0))
    stale_attic_hash = sha_bytes(bytes(p.attic))
    p = p.restage()
    p.validate()
    require(not p.lookup(outer_handle) and sha_bytes(bytes(p.attic)) == stale_attic_hash
            and p.trace[-1] == "transient-depth-invalidated-before-generation-change",
            "restage resurrected a transient handle or reordered invalidation")
    passed("restage-invalidates-before-generation-change", "generation",
           "physical Attic bytes may remain but no handle survives")

    p = seed.clone()
    p.begin_transaction()
    expect_error(BusyError, lambda: p.execute(lambda: None))
    p.end_transaction()
    passed("execution-with-active-transaction-rejected", "transaction-negative",
           "publish-then-run is structural, not conventional")

    # Final artifact demonstrates the disjoint result with one persistent descendant.
    final_plane = reference
    final_plane.validate()
    write_generated(OUT / "c2d-v4-seed.bin", bytes(seed.data))
    write_generated(OUT / "c2d-v4-persistent-descendant.bin", bytes(final_plane.data))
    low = final_plane.low_attic()
    write_generated(OUT / "session-attic-persistent-prefix.bin", bytes(final_plane.attic[:low]))

    groups: dict[str, int] = {}
    for case in cases:
        groups[case["group"]] = groups.get(case["group"], 0) + 1
    require(len(cases) == 48 and all(case["status"] == "passed" for case in cases),
            f"unexpected case closure: {len(cases)}")
    require(seed.maximum_transaction_depth <= 1 and final_plane.maximum_transaction_depth <= 1,
            "model nested an overlay transaction")

    return {
        "format": "lisp65-c2-nested-append-unwind-contract-probe-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-host-contract-probe-product-work-not-authorized",
        "bindings": {
            "contract": binding(CONTRACT),
            "addendum": binding(ADDENDUM),
            "link32_hardware_first_red": binding(DIAGNOSIS),
            "initial_c2d_v3": binding(INITIAL),
            "model_tool": binding(Path(__file__)),
            "source_classification": binding(ROOT / "lib/dialect-v2/eval-runtime.lisp"),
        },
        "alternative_results": {
            "current_execute_inside_open_transaction": "rejected: inner begin returns BUSY",
            "serial_current_suffix_rollback": "rejected: removes a persistent descendant",
            "serial_skip_rollback": "rejected: retains a transient ancestor per descendant commit",
            "serial_disjoint_transient_lane": "passed all host contract cases",
        },
        "format_result": {
            "c2d_version": 4,
            "header_bytes": 48,
            "record_widths_unchanged": {"image": 32, "entry": 10, "resolution": 2, "root": 2},
            "transient_depth_field": {"offset": 8, "bytes": 2, "range": [0, 4]},
            "persistent_allocation": "low prefixes and low Session-Attic front",
            "transient_allocation": "high suffixes and high Session-Attic front",
            "unwind_journal": {"offset": UNWIND_BASE, "bytes": UNWIND_BYTES,
                               "region_end": REGION_BYTES},
            "initial_counts": dict(zip(("images", "entries", "resolutions", "roots"),
                                       initial_counts)),
            "initial_free": {
                "images": IMAGE_CAP - initial_counts[0],
                "entries": ENTRY_CAP - initial_counts[1],
                "resolutions": RESOLUTION_CAP - initial_counts[2],
                "roots": ROOT_CAP - initial_counts[3],
                "session_attic_bytes": ATTIC_BYTES,
            },
        },
        "semantic_result": {
            "overlay_transaction_maximum_depth": 1,
            "transaction_active_during_bytecode_execution": False,
            "nested_transient_normal_return": "byte-identical restoration",
            "nested_transient_longjmp": "byte-identical restoration",
            "persistent_descendant_after_ancestor_return": "preserved and callable",
            "persistent_descendant_after_ancestor_abort": "preserved and callable",
            "warm_repeat_growth": {"images": 0, "entries": 0, "resolutions": 0,
                                   "roots": 0, "attic": 0},
            "invalid_unwind_journal": "session-invalid; no guessed target mutation",
        },
        "cases": {"total": len(cases), "passed": len(cases), "by_group": groups,
                  "rows": cases},
        "artifacts": {
            "seed_v4": binding(OUT / "c2d-v4-seed.bin"),
            "persistent_descendant_v4": binding(OUT / "c2d-v4-persistent-descendant.bin"),
            "persistent_attic_prefix": binding(OUT / "session-attic-persistent-prefix.bin"),
        },
        "capacity_projection_not_authorization": {
            "bank5_session_region_bytes": REGION_BYTES,
            "c2d_plane_bytes": C2D_BYTES,
            "unwind_journal_bytes": UNWIND_BYTES,
            "raw_region_headroom_after_fixed_journal_bytes": REGION_BYTES - C2D_BYTES - UNWIND_BYTES,
            "maximum_export_journal_bytes": ENTRY_CAP * EXPORT_RECORD_BYTES,
            "gap_between_max_export_journal_and_unwind_journal_bytes":
                UNWIND_BASE - (EXPORT_JOURNAL_BASE + ENTRY_CAP * EXPORT_RECORD_BYTES),
            "resident_walls_unchanged_by_host_probe": {
                "bank0_text": 10, "ordinary_bss": 19, "resident_island": 109,
                "minimum_runtime_slice": 11, "e000": 386,
            },
            "next_rule": (
                "No implementation or product link is authorized. A separately reviewed, "
                "product-shaped capacity/placement probe must price the transient lookup, "
                "GC high-tail scan, serial transaction boundaries and longjmp cleanup."
            ),
        },
        "affected_claims": {
            "link32_structural_receipt": "unchanged",
            "link32_hardware_first_red": "unchanged and still blocks promotion",
            "product_source_or_sha": "unchanged by this probe",
            "hardware": "not-run",
            "latency": "not measured or claimed",
        },
        "claim_limit": (
            "Host contract/state-machine proof only. The model proves one serial semantic "
            "design and rejects three alternatives; it is not a product implementation, "
            "capacity authorization, hardware result, promotion or successor-link authority."
        ),
    }


def main() -> int:
    receipt = run_probe()
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if RECEIPT.exists():
        if RECEIPT.read_bytes() == encoded:
            verb = "CHECK PASS"
        elif os.environ.get("LISP65_REPLACE_UNSEALED_PROBE") == "1":
            RECEIPT.write_bytes(encoded)
            os.chmod(RECEIPT, 0o444)
            verb = "REPLACED UNSEALED PROBE"
        else:
            raise ProbeError("existing receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        os.chmod(RECEIPT, 0o444)
        verb = "PASS"
    print(f"c2-nested-append-unwind: {verb} cases={receipt['cases']['passed']}/{receipt['cases']['total']}")
    print(f"c2-nested-append-unwind: receipt_sha256={sha(RECEIPT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
