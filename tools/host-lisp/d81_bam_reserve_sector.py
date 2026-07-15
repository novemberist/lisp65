#!/usr/bin/env python3
"""Reserve one sector in a D81 BAM, in place.

This is test scaffolding for allocator smokes: it creates a consistent
"already allocated" BAM bit without adding a directory entry.
"""

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
    return entry, entry + 1 + sector // 8, 1 << (sector % 8)


def bit_count_bam(data: bytes, track: int) -> int:
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    entry = sector_offset(DIRECTORY_TRACK, bam_sector) + BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    return sum(b.bit_count() for b in data[entry + 1 : entry + BAM_ENTRY_SIZE])


def reserve(path: Path, track: int, sector: int) -> str:
    data = bytearray(path.read_bytes())
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(data) != expected_size:
        raise ValueError("image size %d != %d" % (len(data), expected_size))
    count_off, bitmap_off, mask = bam_offsets(track, sector)
    before_count = data[count_off]
    before_bits = bit_count_bam(data, track)
    before_bitmap = data[bitmap_off]
    if before_count != before_bits:
        raise ValueError("T%d free-count %d != bitmap bits %d" % (track, before_count, before_bits))
    if (before_bitmap & mask) == 0:
        raise ValueError("T%d/S%d already allocated" % (track, sector))
    if before_count < 1:
        raise ValueError("T%d has no free sectors" % track)
    data[count_off] = before_count - 1
    data[bitmap_off] = before_bitmap & (0xFF ^ mask)
    if data[count_off] != bit_count_bam(data, track):
        raise ValueError("internal error after reserve")
    path.write_bytes(data)
    return (
        "d81-bam-reserve: PASS T%d/S%d count@0x%05x %d->%d "
        "bitmap@0x%05x 0x%02x->0x%02x"
        % (track, sector, count_off, before_count, data[count_off], bitmap_off, before_bitmap, data[bitmap_off])
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--track", type=int, required=True)
    ap.add_argument("--sector", type=int, required=True)
    args = ap.parse_args(argv)
    try:
        print(reserve(args.image, args.track, args.sector))
    except (OSError, ValueError) as exc:
        print("d81-bam-reserve: FAIL:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
