#!/usr/bin/env python3
"""Verify a D81 save-new mutation with a variable-length sector chain."""

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


def bit_count_bam(data: bytes | bytearray, track: int) -> int:
    bam_sector = 1 if track <= 40 else 2
    index = (track - 1) if track <= 40 else (track - 41)
    entry = sector_offset(DIRECTORY_TRACK, bam_sector) + BAM_ENTRY_BASE + BAM_ENTRY_SIZE * index
    return sum(b.bit_count() for b in data[entry + 1 : entry + BAM_ENTRY_SIZE])


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


def changed_offsets(a: bytes | bytearray, b: bytes | bytearray, limit: int = 32) -> list[str]:
    out: list[str] = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append("0x%05x:%02x->%02x" % (i, x, y))
            if len(out) >= limit:
                break
    if len(a) != len(b):
        out.append("size:%d->%d" % (len(a), len(b)))
    return out


def folded_dir_name(entry: bytes) -> bytes:
    out = bytearray()
    for b in entry[5:21]:
        if b == 0xA0:
            out.append(32)
        else:
            c = b - 128 if b > 127 else b
            if 97 <= c <= 122:
                c -= 32
            out.append(c)
    return bytes(out)


def find_dir_slot(data: bytes, name: str, dir_track: int, dir_sector: int, requested: int | None) -> int:
    if dir_track != DIRECTORY_TRACK or dir_sector != 4:
        raise ValueError("M7 prototype only scans directory T40/S4")
    sec_off = sector_offset(dir_track, dir_sector)
    sec = data[sec_off : sec_off + SECTOR_SIZE]
    if len(sec) != SECTOR_SIZE:
        raise ValueError("short directory sector")
    if (sec[0], sec[1]) != (0, 0xFF):
        raise ValueError("directory sector T%d/S%d link is %d/%d, expected 0/255" % (dir_track, dir_sector, sec[0], sec[1]))

    want = fold_name(name).replace(b"\xA0", b" ")
    first_free = -1
    for entry_index in range(8):
        base = entry_index * DIR_ENTRY_SIZE
        entry = sec[base : base + DIR_ENTRY_SIZE]
        if entry[2] == 0:
            if first_free < 0:
                first_free = entry_index
        elif folded_dir_name(entry) == want:
            raise ValueError("directory already contains %s in entry %d" % (name, entry_index))

    if requested is not None:
        if not (0 <= requested < 8):
            raise ValueError("directory entry index must be 0..7")
        base = requested * DIR_ENTRY_SIZE
        if sec[base + 2] != 0:
            raise ValueError("directory slot T%d/S%d entry %d is not free" % (dir_track, dir_sector, requested))
        return requested
    if first_free < 0:
        raise ValueError("no free directory entry in T%d/S%d" % (dir_track, dir_sector))
    return first_free


def free_sector(data: bytes, track: int, sector: int) -> bool:
    _, bitmap_off, mask = bam_offsets(track, sector)
    return (data[bitmap_off] & mask) != 0


def scan_tracks() -> list[int]:
    return list(range(1, 40)) + list(range(41, TRACKS + 1))


def find_free_chain(data: bytes, blocks: int) -> list[tuple[int, int]]:
    chain: list[tuple[int, int]] = []
    for track in scan_tracks():
        count_off, _, _ = bam_offsets(track, 0)
        if data[count_off] != bit_count_bam(data, track):
            raise ValueError(
                "before T%d free-count %d != bitmap bits %d"
                % (track, data[count_off], bit_count_bam(data, track))
            )
        for sector in range(SECTORS_PER_TRACK):
            if free_sector(data, track, sector):
                chain.append((track, sector))
                if len(chain) == blocks:
                    return chain
    raise ValueError("not enough free sectors for %d-block file" % blocks)


def expected_after(
    before: bytes,
    payload: bytes,
    name: str,
    dir_track: int,
    dir_sector: int,
    dir_entry_index: int | None,
) -> tuple[bytearray, list[tuple[int, int]], int]:
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(before) != expected_size:
        raise ValueError("before image size %d != %d" % (len(before), expected_size))
    if not (0 < len(payload) <= 1016):
        raise ValueError("payload length %d must be 1..1016 bytes" % len(payload))

    blocks = (len(payload) + 253) // 254
    chain = find_free_chain(before, blocks)
    slot = find_dir_slot(before, name, dir_track, dir_sector, dir_entry_index)

    after = bytearray(before)
    touched: dict[int, int] = {}
    for track, sector in chain:
        count_off, bitmap_off, mask = bam_offsets(track, sector)
        if before[count_off] < 1:
            raise ValueError("before T%d has no free sectors" % track)
        if (before[bitmap_off] & mask) == 0:
            raise ValueError("before T%d/S%d is already allocated" % (track, sector))
        after[bitmap_off] &= 0xFF ^ mask
        touched[track] = touched.get(track, 0) + 1

    for track, count in touched.items():
        count_off, _, _ = bam_offsets(track, 0)
        after[count_off] = before[count_off] - count
        if after[count_off] != bit_count_bam(after, track):
            raise ValueError(
                "internal BAM mismatch for T%d after expected mutation: %d != %d"
                % (track, after[count_off], bit_count_bam(after, track))
            )

    pos = 0
    for index, (track, sector) in enumerate(chain):
        sec = bytearray(SECTOR_SIZE)
        if index + 1 < len(chain):
            next_track, next_sector = chain[index + 1]
            sec[0] = next_track
            sec[1] = next_sector
            chunk = payload[pos : pos + 254]
            if len(chunk) != 254:
                raise ValueError("internal short non-final chunk")
        else:
            chunk = payload[pos:]
            sec[0] = 0
            sec[1] = len(chunk) + 1
        sec[2 : 2 + len(chunk)] = chunk
        sec_off = sector_offset(track, sector)
        after[sec_off : sec_off + SECTOR_SIZE] = sec
        pos += len(chunk)

    first_track, first_sector = chain[0]
    dir_base = sector_offset(dir_track, dir_sector) + slot * DIR_ENTRY_SIZE
    after[dir_base : dir_base + DIR_ENTRY_SIZE] = dir_entry(name, first_track, first_sector, blocks)
    return after, chain, slot


def chain_text(chain: list[tuple[int, int]]) -> str:
    return "->".join("T%d/S%d" % (track, sector) for track, sector in chain)


def verify(
    before: bytes,
    after: bytes,
    payload: bytes,
    name: str,
    dir_track: int,
    dir_sector: int,
    dir_entry_index: int | None,
) -> tuple[list[str], list[tuple[int, int]], int]:
    errors: list[str] = []
    expected_size = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
    if len(before) != expected_size:
        errors.append("before image size %d != %d" % (len(before), expected_size))
    if len(after) != expected_size:
        errors.append("after image size %d != %d" % (len(after), expected_size))
    if len(before) != len(after):
        return errors, [], -1
    try:
        expected, chain, slot = expected_after(before, payload, name, dir_track, dir_sector, dir_entry_index)
    except ValueError as exc:
        errors.append(str(exc))
        return errors, [], -1
    if bytes(expected) != after:
        errors.append(
            "unexpected D81 diff; actual changes: %s; expected/actual mismatch: %s"
            % (
                ", ".join(changed_offsets(before, after)) or "none",
                ", ".join(changed_offsets(expected, after)) or "none",
            )
        )
    return errors, chain, slot


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path, nargs="?")
    ap.add_argument("after", type=Path, nargs="?")
    ap.add_argument("--source", type=Path, default=Path("tests/disk/m7-var-source.lisp"))
    ap.add_argument("--name", default="m7src")
    ap.add_argument("--dir-track", type=int, default=40)
    ap.add_argument("--dir-sector", type=int, default=4)
    ap.add_argument("--dir-entry", type=int)
    ap.add_argument("--selftest", type=Path, help="verify the expected mutation in memory")
    args = ap.parse_args(argv)

    try:
        payload = args.source.read_bytes()
        if args.selftest:
            before = args.selftest.read_bytes()
            _, chain, slot = expected_after(
                before, payload, args.name, args.dir_track, args.dir_sector, args.dir_entry
            )
            print(
                "d81-save-new-diff: PASS selftest name=%s chain=%s len=%d dir_entry=%d"
                % (args.name, chain_text(chain), len(payload), slot)
            )
            return 0
        if args.before is None or args.after is None:
            ap.error("before and after are required unless --selftest is used")
        before = args.before.read_bytes()
        after = args.after.read_bytes()
        errors, chain, slot = verify(
            before, after, payload, args.name, args.dir_track, args.dir_sector, args.dir_entry
        )
        if errors:
            for error in errors:
                print("d81-save-new-diff: FAIL:", error, file=sys.stderr)
            return 1
        print(
            "d81-save-new-diff: PASS name=%s chain=%s len=%d dir_entry=%d"
            % (args.name, chain_text(chain), len(payload), slot)
        )
        return 0
    except (OSError, ValueError) as exc:
        print("d81-save-new-diff: FAIL:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
