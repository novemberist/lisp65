#!/usr/bin/env python3
"""Independent two-media D81 oracle for the accepted G6 Freezer boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import d81_bam_sanity as BAM
import d81_persistence_fault as D81
import m65d_blank_d81_oracle as BLANK


class OracleError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_image(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise OracleError(f"{label} must be a regular non-symlink file")
    data = path.read_bytes()
    require(len(data) == D81.IMAGE_SIZE, f"{label} is not an exact D81 image")
    return data


def sector_differences(before: bytes, after: bytes) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for track in range(1, D81.TRACKS + 1):
        for sector in range(D81.SECTORS_PER_TRACK):
            if D81.get_sector(before, track, sector) != D81.get_sector(after, track, sector):
                result.append((track, sector))
    return result


def source_state(image: bytes) -> tuple[dict[bytes, bytes], set[tuple[int, int]], set[tuple[int, int]]]:
    """Validate the source FS while permitting bounded precommit orphan blocks."""
    D81.validate_bam(image)
    _counts, bam_errors = BAM.bam_free_counts(image)
    _entries, _blocks, directory_errors = BAM.directory_entries(image)
    require(not bam_errors, "source BAM count/bitmap mismatch: " + "; ".join(bam_errors))
    require(not directory_errors, "source directory parser rejected image: " + "; ".join(directory_errors))
    files = D81.visible_files(image)
    occupied: set[tuple[int, int]] = set()
    for slot in D81.directory_slots(image):
        if slot.record[2] == 0:
            continue
        chain = set(D81.file_chain(image, slot.record))
        require(not occupied.intersection(chain), "source visible file chains overlap")
        occupied.update(chain)
    allocated = D81.allocated_sectors(image)
    require(occupied.issubset(allocated), "source exposes a chain not allocated in BAM")
    return files, occupied, allocated - occupied


def damage_class(changed: list[tuple[int, int]]) -> str:
    if not changed:
        return "none-observed"
    track, sector = changed[0]
    require((track, sector) != (40, 0), "1581 header was the foreign write target")
    if track == 40 and sector in {1, 2}:
        return "filesystem-BAM-sector-may-be-invalid"
    if track == 40 and sector >= 3:
        return "filesystem-directory-sector-may-be-invalid"
    return "data-sector-may-be-overwritten"


def verify(
    *,
    a_before_path: Path,
    a_after_path: Path,
    b_baseline_path: Path,
    b_before_path: Path,
    b_after_path: Path,
    expected_name: str,
    expected_content_path: Path,
) -> dict[str, object]:
    a_before = read_image(a_before_path, "medium A before")
    a_after = read_image(a_after_path, "medium A after")
    b_baseline = read_image(b_baseline_path, "protected medium B baseline")
    b_before = read_image(b_before_path, "medium B before")
    b_after = read_image(b_after_path, "medium B after")
    if expected_content_path.is_symlink() or not expected_content_path.is_file():
        raise OracleError("expected content must be a regular non-symlink file")
    content = expected_content_path.read_bytes()
    require(1 <= len(content) <= D81.MAX_PAYLOAD, "expected content is outside the persistence contract")

    require(b_baseline == b_before, "medium B was not restored from its protected clean baseline")
    changed_b = sector_differences(b_before, b_after)
    require(len(changed_b) <= 1, "accepted Freezer boundary exceeded one foreign sector")

    before_files, _before_occupied, before_orphans = source_state(a_before)
    after_files, _after_occupied, after_orphans = source_state(a_after)
    require(not before_orphans, "medium A baseline already contains orphan allocations")
    require(D81.get_sector(a_before, 40, 0) == D81.get_sector(a_after, 40, 0), "medium A header changed")
    wanted = D81.fold_name(expected_name).replace(bytes([0xA0]), b" ").rstrip(b" ")
    committed_files = dict(before_files)
    committed_files[wanted] = content
    if after_files == before_files:
        visibility = "unchanged-precommit"
    elif after_files == committed_files:
        visibility = "complete-committed"
    else:
        raise OracleError("medium A exposes a partial or unexpected file set")

    foreign_valid = True
    try:
        D81.validate_bam(b_after)
        _counts, bam_errors = BAM.bam_free_counts(b_after)
        _entries, _blocks, directory_errors = BAM.directory_entries(b_after)
        if bam_errors or directory_errors:
            foreign_valid = False
    except (AssertionError, ValueError):
        foreign_valid = False

    return {
        "format": "lisp65-g6-two-media-boundary-oracle-v1",
        "version": 1,
        "result": "within-owner-accepted-boundary",
        "safety_pass": False,
        "expected_file": expected_name,
        "expected_content_sha256": digest(content),
        "medium_a_before_sha256": digest(a_before),
        "medium_a_after_sha256": digest(a_after),
        "medium_a_header_unchanged": True,
        "medium_a_visibility": visibility,
        "medium_a_orphan_sector_count": len(after_orphans),
        "medium_b_baseline_sha256": digest(b_baseline),
        "medium_b_before_sha256": digest(b_before),
        "medium_b_after_sha256": digest(b_after),
        "medium_b_changed_sectors": [f"T{track}/S{sector}" for track, sector in changed_b],
        "medium_b_changed_sector_count": len(changed_b),
        "contract_limit_foreign_sector_count": 1,
        "medium_b_filesystem_valid_after": foreign_valid,
        "damage_class": damage_class(changed_b),
        "both_media_checked": True,
        "witnesses": ["full-image-sector-diff", "d81_persistence_fault", "d81_bam_sanity"],
    }


def canonical(value: dict[str, object]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="lisp65-g6-two-media-") as raw:
        root = Path(raw)
        a_before = BLANK.blank_user_image(b"G6MEDIAA", b"A1")
        content = b"two-media-oracle"
        a_committed = D81.plan_transaction(a_before, "new", "g6guard", content).final
        b = BLANK.blank_user_image(b"G6MEDIAB", b"B2")
        paths = {
            "a_before": root / "a-before.d81", "a_after": root / "a-after.d81",
            "b_baseline": root / "b-baseline.d81", "b_before": root / "b-before.d81",
            "b_after": root / "b-after.d81", "content": root / "content.bin",
        }
        for key, data in (
            ("a_before", a_before), ("a_after", a_committed), ("b_baseline", b),
            ("b_before", b), ("b_after", b), ("content", content),
        ):
            paths[key].write_bytes(data)
        report = verify(
            a_before_path=paths["a_before"], a_after_path=paths["a_after"],
            b_baseline_path=paths["b_baseline"], b_before_path=paths["b_before"],
            b_after_path=paths["b_after"], expected_name="g6guard",
            expected_content_path=paths["content"],
        )
        require(report["medium_b_changed_sector_count"] == 0, "zero-sector boundary selftest drift")

        foreign_one = bytearray(b)
        offset = D81.sector_offset(1, 0)
        foreign_one[offset + 2] ^= 0x41
        paths["a_after"].write_bytes(a_before)
        paths["b_after"].write_bytes(foreign_one)
        report = verify(
            a_before_path=paths["a_before"], a_after_path=paths["a_after"],
            b_baseline_path=paths["b_baseline"], b_before_path=paths["b_before"],
            b_after_path=paths["b_after"], expected_name="g6guard",
            expected_content_path=paths["content"],
        )
        require(report["medium_b_changed_sector_count"] == 1, "one-sector boundary selftest drift")

        foreign_two = bytearray(foreign_one)
        offset = D81.sector_offset(1, 1)
        foreign_two[offset + 2] ^= 0x42
        paths["b_after"].write_bytes(foreign_two)
        try:
            verify(
                a_before_path=paths["a_before"], a_after_path=paths["a_after"],
                b_baseline_path=paths["b_baseline"], b_before_path=paths["b_before"],
                b_after_path=paths["b_after"], expected_name="g6guard",
                expected_content_path=paths["content"],
            )
        except OracleError:
            pass
        else:
            raise OracleError("two changed sectors survived the boundary oracle")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--a-before", type=Path)
    parser.add_argument("--a-after", type=Path)
    parser.add_argument("--b-baseline", type=Path)
    parser.add_argument("--b-before", type=Path)
    parser.add_argument("--b-after", type=Path)
    parser.add_argument("--expected-name")
    parser.add_argument("--expected-content", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("g6-two-media-oracle: SELFTEST PASS accepted=2 rejected=1 safety-pass=0")
            return 0
        required = (
            args.a_before, args.a_after, args.b_baseline, args.b_before,
            args.b_after, args.expected_name, args.expected_content, args.out,
        )
        if any(value is None for value in required):
            raise OracleError("all image, expected-file and output arguments are required")
        report = verify(
            a_before_path=args.a_before, a_after_path=args.a_after,
            b_baseline_path=args.b_baseline, b_before_path=args.b_before,
            b_after_path=args.b_after, expected_name=args.expected_name,
            expected_content_path=args.expected_content,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical(report))
        print(
            "g6-two-media-oracle: BOUNDARY CHARACTERIZED "
            f"foreign-sectors={report['medium_b_changed_sector_count']} safety-pass=0"
        )
        return 0
    except (OracleError, AssertionError, ValueError, OSError, UnicodeError) as exc:
        print(f"g6-two-media-oracle: FAIL: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
