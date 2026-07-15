#!/usr/bin/env python3
"""Verify a single expected D81 BAM allocation mutation."""

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
    count_off = entry
    bitmap_off = entry + 1 + sector // 8
    mask = 1 << (sector % 8)
    return count_off, bitmap_off, mask


def bit_count_bam(data: bytes, track: int) -> int:
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    entry = sector_offset(DIRECTORY_TRACK, bam_sector) + BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    return sum(b.bit_count() for b in data[entry + 1 : entry + BAM_ENTRY_SIZE])


def expected_after(before: bytes, track: int, sector: int) -> bytearray:
    count_off, bitmap_off, mask = bam_offsets(track, sector)
    before_count = before[count_off]
    before_bitmap = before[bitmap_off]
    errors: list[str] = []
    if before_count != bit_count_bam(before, track):
        errors.append(
            "before T%d free-count %d != bitmap bits %d"
            % (track, before_count, bit_count_bam(before, track))
        )
    if (before_bitmap & mask) == 0:
        errors.append("before T%d/S%d is already allocated" % (track, sector))
    if before_count == 0:
        errors.append("before T%d free-count is already zero" % track)
    if errors:
        raise ValueError("; ".join(errors))

    after = bytearray(before)
    after[count_off] = before_count - 1
    after[bitmap_off] = before_bitmap & (0xFF ^ mask)
    return after


def changed_offsets(a: bytes, b: bytes, limit: int = 16) -> list[str]:
    out: list[str] = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append("0x%05x:%02x->%02x" % (i, x, y))
            if len(out) >= limit:
                break
    if len(a) != len(b):
        out.append("size:%d->%d" % (len(a), len(b)))
    return out


def verify(before: bytes, after: bytes, track: int, sector: int) -> list[str]:
    errors: list[str] = []
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(before) != expected_size:
        errors.append("before image size %d != %d" % (len(before), expected_size))
    if len(after) != expected_size:
        errors.append("after image size %d != %d" % (len(after), expected_size))
    if len(before) != len(after):
        return errors
    try:
        expected = expected_after(before, track, sector)
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    if bytes(expected) != after:
        errors.append(
            "unexpected D81 diff; changed offsets: %s"
            % (", ".join(changed_offsets(before, after)) or "none")
        )

    count_off, bitmap_off, mask = bam_offsets(track, sector)
    if after[count_off] != before[count_off] - 1:
        errors.append(
            "after free-count byte 0x%05x is %d, expected %d"
            % (count_off, after[count_off], before[count_off] - 1)
        )
    if after[bitmap_off] != (before[bitmap_off] & (0xFF ^ mask)):
        errors.append(
            "after bitmap byte 0x%05x is 0x%02x, expected 0x%02x"
            % (bitmap_off, after[bitmap_off], before[bitmap_off] & (0xFF ^ mask))
        )
    if after[count_off] != bit_count_bam(after, track):
        errors.append(
            "after T%d free-count %d != bitmap bits %d"
            % (track, after[count_off], bit_count_bam(after, track))
        )
    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path, nargs="?")
    ap.add_argument("after", type=Path, nargs="?")
    ap.add_argument("--track", type=int, default=45)
    ap.add_argument("--sector", type=int, default=8)
    ap.add_argument("--selftest", type=Path, help="verify the expected mutation in memory")
    args = ap.parse_args(argv)

    try:
        if args.selftest:
            before = args.selftest.read_bytes()
            after = bytes(expected_after(before, args.track, args.sector))
        else:
            if args.before is None or args.after is None:
                ap.error("before and after are required without --selftest")
            before = args.before.read_bytes()
            after = args.after.read_bytes()
        errors = verify(before, after, args.track, args.sector)
    except (OSError, ValueError) as exc:
        print("d81-bam-alloc-diff: FAIL:", exc, file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print("d81-bam-alloc-diff: FAIL:", error, file=sys.stderr)
        return 1

    count_off, bitmap_off, mask = bam_offsets(args.track, args.sector)
    print(
        "d81-bam-alloc-diff: PASS T%d/S%d count@0x%05x %d->%d "
        "bitmap@0x%05x 0x%02x->0x%02x mask=0x%02x"
        % (
            args.track,
            args.sector,
            count_off,
            before[count_off],
            after[count_off],
            bitmap_off,
            before[bitmap_off],
            after[bitmap_off],
            mask,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
