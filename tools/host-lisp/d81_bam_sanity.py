#!/usr/bin/env python3
"""Read-only BAM sanity checks for lisp65 D81 images."""

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


def sector(data: bytes, track: int, sector_no: int) -> bytes:
    if not (1 <= track <= TRACKS and 0 <= sector_no < SECTORS_PER_TRACK):
        raise ValueError("sector out of range T%d/S%d" % (track, sector_no))
    off = ((track - 1) * SECTORS_PER_TRACK + sector_no) * SECTOR_SIZE
    return data[off : off + SECTOR_SIZE]


def bam_entry(data: bytes, track: int) -> tuple[int, bytes]:
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    off = BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    entry = sector(data, DIRECTORY_TRACK, bam_sector)[off : off + BAM_ENTRY_SIZE]
    if len(entry) != BAM_ENTRY_SIZE:
        raise ValueError("short BAM entry for track %d" % track)
    return entry[0], entry[1:]


def bam_free_counts(data: bytes) -> tuple[list[int], list[str]]:
    errors: list[str] = []
    counts: list[int] = []
    for track in range(1, TRACKS + 1):
        free_count, bitmap = bam_entry(data, track)
        bit_count = sum(byte.bit_count() for byte in bitmap)
        counts.append(free_count)
        if free_count != bit_count:
            errors.append(
                "track %d free-count %d != bitmap bits %d" % (track, free_count, bit_count)
            )
    return counts, errors


def directory_entries(data: bytes) -> tuple[int, int, list[str]]:
    header = sector(data, DIRECTORY_TRACK, 0)
    track, sector_no = header[0], header[1]
    seen: set[tuple[int, int]] = set()
    entries = 0
    blocks = 0
    errors: list[str] = []
    fuel = 64
    while track and fuel:
        fuel -= 1
        key = (track, sector_no)
        if key in seen:
            errors.append("directory loop at T%d/S%d" % key)
            break
        seen.add(key)
        sec = sector(data, track, sector_no)
        for entry_index in range(8):
            base = entry_index * 32
            file_type = sec[base + 2]
            if file_type:
                entries += 1
                blocks += sec[base + 30] | (sec[base + 31] << 8)
        track, sector_no = sec[0], sec[1]
    if fuel == 0:
        errors.append("directory walk exhausted fuel")
    return entries, blocks, errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--expect-free-blocks", type=int)
    ap.add_argument("--expect-file-blocks", type=int)
    args = ap.parse_args(argv)

    data = args.image.read_bytes()
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    errors: list[str] = []
    if len(data) != expected_size:
        errors.append("image size %d != %d" % (len(data), expected_size))

    bam1 = sector(data, DIRECTORY_TRACK, 1)
    bam2 = sector(data, DIRECTORY_TRACK, 2)
    if (bam1[0], bam1[1]) != (DIRECTORY_TRACK, 2):
        errors.append("BAM sector T40/S1 link is %d/%d, expected 40/2" % (bam1[0], bam1[1]))
    if (bam2[0], bam2[1]) != (0, 0xFF):
        errors.append("BAM sector T40/S2 link is %d/%d, expected 0/255" % (bam2[0], bam2[1]))

    counts, bam_errors = bam_free_counts(data)
    errors.extend(bam_errors)
    dir_entries, file_blocks, dir_errors = directory_entries(data)
    errors.extend(dir_errors)

    track40_free = counts[DIRECTORY_TRACK - 1]
    bam_free_total = sum(counts)
    free_blocks = bam_free_total - track40_free
    non_directory_blocks = (TRACKS - 1) * SECTORS_PER_TRACK
    if free_blocks + file_blocks != non_directory_blocks:
        errors.append(
            "free_blocks + file_blocks = %d, expected %d"
            % (free_blocks + file_blocks, non_directory_blocks)
        )
    if args.expect_free_blocks is not None and free_blocks != args.expect_free_blocks:
        errors.append("free_blocks %d != expected %d" % (free_blocks, args.expect_free_blocks))
    if args.expect_file_blocks is not None and file_blocks != args.expect_file_blocks:
        errors.append("file_blocks %d != expected %d" % (file_blocks, args.expect_file_blocks))

    if errors:
        for error in errors:
            print("d81-bam-sanity: FAIL:", error, file=sys.stderr)
        return 1

    print(
        "d81-bam-sanity: PASS image=%s free_blocks=%d file_blocks=%d "
        "dir_entries=%d track40_free=%d"
        % (args.image, free_blocks, file_blocks, dir_entries, track40_free)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
