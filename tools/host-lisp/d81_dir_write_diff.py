#!/usr/bin/env python3
"""Verify an exact two-sector D81 directory-entry write mutation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SECTOR_SIZE = 256
TRACKS = 80
SECTORS_PER_TRACK = 40
DIRECTORY_TRACK = 40
BAM_ENTRY_BASE = 16
BAM_ENTRY_SIZE = 6
DIR_ENTRY_SIZE = 32


def sector_offset(track: int, sector: int) -> int:
    if not (1 <= track <= TRACKS and 0 <= sector < SECTORS_PER_TRACK):
        raise ValueError("sector out of range T%d/S%d" % (track, sector))
    return ((track - 1) * SECTORS_PER_TRACK + sector) * SECTOR_SIZE


def bam_offsets(track: int, sector: int) -> tuple[int, int, int]:
    if not (1 <= track <= TRACKS and 0 <= sector < SECTORS_PER_TRACK):
        raise ValueError("BAM target out of range T%d/S%d" % (track, sector))
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    entry = sector_offset(DIRECTORY_TRACK, bam_sector) + BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    return entry, entry + 1 + sector // 8, 1 << (sector % 8)


def bit_count_bam(data: bytes, track: int) -> int:
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    entry = sector_offset(DIRECTORY_TRACK, bam_sector) + BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    return sum(b.bit_count() for b in data[entry + 1 : entry + BAM_ENTRY_SIZE])


def sector_free(data: bytes, track: int, sector: int) -> bool:
    _, bitmap_off, mask = bam_offsets(track, sector)
    return (data[bitmap_off] & mask) != 0


def first_free_sectors(data: bytes, track: int, start: int, count: int) -> list[int]:
    if not (0 <= start < SECTORS_PER_TRACK):
        raise ValueError("allocator start sector out of range: %d" % start)
    found = [sector for sector in range(start, SECTORS_PER_TRACK) if sector_free(data, track, sector)]
    if len(found) < count:
        raise ValueError(
            "T%d has only %d free sectors at or after S%d, need %d"
            % (track, len(found), start, count)
        )
    return found[:count]


def fold_name(name: str) -> bytes:
    raw = name.encode("ascii")
    if not raw or len(raw) > 16:
        raise ValueError("D81 filename must be 1..16 ASCII bytes")
    out = bytearray()
    for b in raw:
        if 97 <= b <= 122:
            b -= 32
        out.append(b)
    out.extend([0xA0] * (16 - len(out)))
    return bytes(out)


def dir_entry(name: str, track: int, sector: int, blocks: int) -> bytes:
    entry = bytearray(DIR_ENTRY_SIZE)
    entry[2] = 0x81
    entry[3] = track
    entry[4] = sector
    entry[5:21] = fold_name(name)
    entry[30] = blocks & 0xFF
    entry[31] = (blocks >> 8) & 0xFF
    return bytes(entry)


def changed_offsets(a: bytes, b: bytes, limit: int = 32) -> list[str]:
    out: list[str] = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append("0x%05x:%02x->%02x" % (i, x, y))
            if len(out) >= limit:
                break
    if len(a) != len(b):
        out.append("size:%d->%d" % (len(a), len(b)))
    return out


def expected_after(
    before: bytes,
    payload: bytes,
    name: str,
    track: int,
    first: int,
    second: int,
    dir_track: int,
    dir_sector: int,
    dir_entry_index: int,
    allocator_start_sector: int | None = None,
) -> bytearray:
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(before) != expected_size:
        raise ValueError("before image size %d != %d" % (len(before), expected_size))
    if not (254 < len(payload) <= 508):
        raise ValueError("payload length %d must span exactly two sectors" % len(payload))
    if not (0 <= dir_entry_index < 8):
        raise ValueError("directory entry index must be 0..7")

    count_off, bitmap_off_a, mask_a = bam_offsets(track, first)
    count_off_b, bitmap_off_b, mask_b = bam_offsets(track, second)
    if count_off_b != count_off:
        raise ValueError("sectors must live on the same BAM track entry")
    if first == second:
        raise ValueError("first and second sector must differ")
    if allocator_start_sector is not None:
        selected = first_free_sectors(before, track, allocator_start_sector, 2)
        if selected != [first, second]:
            raise ValueError(
                "allocator plan drift: first free sectors from T%d/S%d are S%d,S%d, expected S%d,S%d"
                % (track, allocator_start_sector, selected[0], selected[1], first, second)
            )

    before_count = before[count_off]
    before_bitmap_a = before[bitmap_off_a]
    before_bitmap_b = before[bitmap_off_b]
    errors: list[str] = []
    if before_count != bit_count_bam(before, track):
        errors.append(
            "before T%d free-count %d != bitmap bits %d"
            % (track, before_count, bit_count_bam(before, track))
        )
    if (before_bitmap_a & mask_a) == 0:
        errors.append("before T%d/S%d is already allocated" % (track, first))
    if (before_bitmap_b & mask_b) == 0:
        errors.append("before T%d/S%d is already allocated" % (track, second))
    if before_count < 2:
        errors.append("before T%d free-count %d cannot allocate two sectors" % (track, before_count))

    dir_base = sector_offset(dir_track, dir_sector) + dir_entry_index * DIR_ENTRY_SIZE
    if before[dir_base + 2] != 0:
        errors.append("directory slot T%d/S%d entry %d is not free" % (dir_track, dir_sector, dir_entry_index))
    if errors:
        raise ValueError("; ".join(errors))

    after = bytearray(before)
    after[count_off] = before_count - 2
    after[bitmap_off_a] = before_bitmap_a & (0xFF ^ mask_a)
    after[bitmap_off_b] = after[bitmap_off_b] & (0xFF ^ mask_b)

    first_off = sector_offset(track, first)
    second_off = sector_offset(track, second)
    first_sector = bytearray(SECTOR_SIZE)
    second_sector = bytearray(SECTOR_SIZE)
    first_sector[0] = track
    first_sector[1] = second
    first_sector[2:] = payload[:254]
    tail = payload[254:]
    second_sector[0] = 0
    second_sector[1] = len(tail) + 1
    second_sector[2 : 2 + len(tail)] = tail
    after[first_off : first_off + SECTOR_SIZE] = first_sector
    after[second_off : second_off + SECTOR_SIZE] = second_sector
    after[dir_base : dir_base + DIR_ENTRY_SIZE] = dir_entry(name, track, first, 2)
    return after


def verify(
    before: bytes,
    after: bytes,
    payload: bytes,
    name: str,
    track: int,
    first: int,
    second: int,
    dir_track: int,
    dir_sector: int,
    dir_entry_index: int,
    allocator_start_sector: int | None = None,
) -> list[str]:
    errors: list[str] = []
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(before) != expected_size:
        errors.append("before image size %d != %d" % (len(before), expected_size))
    if len(after) != expected_size:
        errors.append("after image size %d != %d" % (len(after), expected_size))
    if len(before) != len(after):
        return errors
    try:
        expected = expected_after(
            before,
            payload,
            name,
            track,
            first,
            second,
            dir_track,
            dir_sector,
            dir_entry_index,
            allocator_start_sector,
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    if bytes(expected) != after:
        errors.append(
            "unexpected D81 diff; changed offsets: %s"
            % (", ".join(changed_offsets(before, after)) or "none")
        )

    count_off, _, _ = bam_offsets(track, first)
    if after[count_off] != before[count_off] - 2:
        errors.append(
            "after free-count byte 0x%05x is %d, expected %d"
            % (count_off, after[count_off], before[count_off] - 2)
        )
    if after[count_off] != bit_count_bam(after, track):
        errors.append(
            "after T%d free-count %d != bitmap bits %d"
            % (track, after[count_off], bit_count_bam(after, track))
        )

    dir_base = sector_offset(dir_track, dir_sector) + dir_entry_index * DIR_ENTRY_SIZE
    want_entry = dir_entry(name, track, first, 2)
    if after[dir_base : dir_base + DIR_ENTRY_SIZE] != want_entry:
        errors.append("directory entry mismatch at 0x%05x" % dir_base)
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path, nargs="?")
    ap.add_argument("after", type=Path, nargs="?")
    ap.add_argument("--source", type=Path, default=Path("tests/disk/m4-dir-source.lisp"))
    ap.add_argument("--name", default="m4src")
    ap.add_argument("--track", type=int, default=45)
    ap.add_argument("--first-sector", type=int, default=8)
    ap.add_argument("--second-sector", type=int, default=9)
    ap.add_argument("--dir-track", type=int, default=40)
    ap.add_argument("--dir-sector", type=int, default=4)
    ap.add_argument("--dir-entry", type=int, default=1)
    ap.add_argument(
        "--allocator-start-sector",
        type=int,
        help="require first/second to be the allocator's first two free sectors from this sector",
    )
    ap.add_argument("--selftest", type=Path, help="verify the expected mutation in memory")
    args = ap.parse_args(argv)

    try:
        payload = args.source.read_bytes()
        if args.selftest:
            before = args.selftest.read_bytes()
            after = bytes(
                expected_after(
                    before,
                    payload,
                    args.name,
                    args.track,
                    args.first_sector,
                    args.second_sector,
                    args.dir_track,
                    args.dir_sector,
                    args.dir_entry,
                    args.allocator_start_sector,
                )
            )
        else:
            if args.before is None or args.after is None:
                ap.error("before and after are required without --selftest")
            before = args.before.read_bytes()
            after = args.after.read_bytes()
        errors = verify(
            before,
            after,
            payload,
            args.name,
            args.track,
            args.first_sector,
            args.second_sector,
            args.dir_track,
            args.dir_sector,
            args.dir_entry,
            args.allocator_start_sector,
        )
    except (OSError, ValueError) as exc:
        print("d81-dir-write-diff: FAIL:", exc, file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print("d81-dir-write-diff: FAIL:", error, file=sys.stderr)
        return 1

    count_off, bitmap_off_a, _ = bam_offsets(args.track, args.first_sector)
    _, bitmap_off_b, _ = bam_offsets(args.track, args.second_sector)
    dir_base = sector_offset(args.dir_track, args.dir_sector) + args.dir_entry * DIR_ENTRY_SIZE
    bitmap_offsets = sorted({bitmap_off_a, bitmap_off_b})
    bitmap_summary = ",".join(
        "0x%05x:0x%02x->0x%02x" % (off, before[off], after[off]) for off in bitmap_offsets
    )
    print(
        "d81-dir-write-diff: PASS name=%s T%d/S%d->S%d dir@0x%05x len=%d "
        "count@0x%05x %d->%d bitmap=%s"
        % (
            args.name,
            args.track,
            args.first_sector,
            args.second_sector,
            dir_base,
            len(payload),
            count_off,
            before[count_off],
            after[count_off],
            bitmap_summary,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
