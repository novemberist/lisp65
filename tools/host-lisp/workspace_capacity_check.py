#!/usr/bin/env python3
"""Fail closed before suites when the workspace cannot safely record results."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


DEFAULT_MIN_FREE_BYTES = 4 * 1024 * 1024 * 1024
DEFAULT_MAX_BTRFS_METADATA_PERCENT = 85.0
WRITE_PROBE_BYTES = 128 * 1024


class CapacityError(Exception):
    """The workspace cannot safely absorb a suite run and Git update."""


def parse_btrfs_metadata_percent(output: str) -> float:
    match = re.search(
        r"^Metadata(?:,[^:]+)?:.*\(([0-9]+(?:\.[0-9]+)?)%\)\s*$",
        output,
        flags=re.MULTILINE,
    )
    if match is None:
        raise CapacityError("cannot parse Btrfs metadata usage")
    return float(match.group(1))


def evaluate_capacity(
    *,
    free_bytes: int,
    min_free_bytes: int,
    fs_type: str,
    btrfs_metadata_percent: float | None,
    max_btrfs_metadata_percent: float,
) -> None:
    if free_bytes < min_free_bytes:
        raise CapacityError(
            f"free bytes {free_bytes} below required {min_free_bytes}"
        )
    if fs_type == "btrfs":
        if btrfs_metadata_percent is None:
            raise CapacityError("Btrfs metadata usage is unavailable")
        if btrfs_metadata_percent >= max_btrfs_metadata_percent:
            raise CapacityError(
                "Btrfs metadata usage "
                f"{btrfs_metadata_percent:.2f}% reaches limit "
                f"{max_btrfs_metadata_percent:.2f}%"
            )


def run_command(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        timeout=15,
    )


def filesystem_type(root: Path) -> str:
    result = run_command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(root)], cwd=root)
    if result.returncode != 0 or not result.stdout.strip():
        raise CapacityError(f"cannot determine filesystem type: {result.stderr.strip()}")
    return result.stdout.strip().splitlines()[0]


def btrfs_metadata_percent(root: Path) -> float:
    result = run_command(["btrfs", "filesystem", "usage", "-b", str(root)], cwd=root)
    if result.returncode != 0:
        raise CapacityError(f"cannot read Btrfs usage: {result.stderr.strip()}")
    return parse_btrfs_metadata_percent(result.stdout)


def git_dir(root: Path) -> Path:
    result = run_command(["git", "rev-parse", "--path-format=absolute", "--git-dir"], cwd=root)
    if result.returncode != 0:
        raise CapacityError(f"cannot locate Git directory: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def atomic_git_write_probe(directory: Path) -> None:
    source = directory / f".lisp65-capacity-{os.getpid()}.tmp"
    target = directory / f".lisp65-capacity-{os.getpid()}.done"
    try:
        with source.open("xb") as handle:
            handle.write(b"\0" * WRITE_PROBE_BYTES)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(source, target)
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise CapacityError(f"atomic Git-directory write probe failed: {exc}") from exc
    finally:
        source.unlink(missing_ok=True)
        target.unlink(missing_ok=True)


def git_index_write_probe(root: Path, directory: Path) -> None:
    output = directory / f".lisp65-capacity-index-{os.getpid()}"
    try:
        result = run_command(
            ["git", "read-tree", f"--index-output={output}", "HEAD"], cwd=root
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise CapacityError(f"Git index write probe failed: {detail}")
    finally:
        output.unlink(missing_ok=True)


def positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise CapacityError(f"{name} must be an integer") from exc
    if value < 0:
        raise CapacityError(f"{name} must not be negative")
    return value


def positive_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise CapacityError(f"{name} must be numeric") from exc
    if not 0.0 < value <= 100.0:
        raise CapacityError(f"{name} must be in the interval (0, 100]")
    return value


def selftest() -> None:
    sample = """\
Data,single: Size:1000, Used:500 (50.00%)
Metadata,DUP: Size:1000, Used:887 (88.70%)
"""
    assert parse_btrfs_metadata_percent(sample) == 88.7
    evaluate_capacity(
        free_bytes=8_000,
        min_free_bytes=4_000,
        fs_type="ext4",
        btrfs_metadata_percent=None,
        max_btrfs_metadata_percent=85.0,
    )
    failures = 0
    cases = (
        dict(
            free_bytes=3_999,
            min_free_bytes=4_000,
            fs_type="ext4",
            btrfs_metadata_percent=None,
            max_btrfs_metadata_percent=85.0,
        ),
        dict(
            free_bytes=8_000,
            min_free_bytes=4_000,
            fs_type="btrfs",
            btrfs_metadata_percent=None,
            max_btrfs_metadata_percent=85.0,
        ),
        dict(
            free_bytes=8_000,
            min_free_bytes=4_000,
            fs_type="btrfs",
            btrfs_metadata_percent=85.0,
            max_btrfs_metadata_percent=85.0,
        ),
    )
    for case in cases:
        try:
            evaluate_capacity(**case)
        except CapacityError:
            failures += 1
    if failures != len(cases):
        raise CapacityError(f"selftest rejected {failures}/{len(cases)} bad cases")
    try:
        parse_btrfs_metadata_percent("Metadata: unavailable")
    except CapacityError:
        failures += 1
    if failures != len(cases) + 1:
        raise CapacityError("selftest accepted malformed Btrfs output")
    print(f"workspace-capacity-check selftest: PASS cases={len(cases) + 2}")


def check(root: Path) -> None:
    root = root.resolve()
    stats = os.statvfs(root)
    free_bytes = stats.f_bavail * stats.f_frsize
    min_free_bytes = positive_int_env(
        "LISP65_MIN_WORKSPACE_FREE_BYTES", DEFAULT_MIN_FREE_BYTES
    )
    max_metadata = positive_float_env(
        "LISP65_MAX_BTRFS_METADATA_PERCENT", DEFAULT_MAX_BTRFS_METADATA_PERCENT
    )
    fs_type = filesystem_type(root)
    metadata = btrfs_metadata_percent(root) if fs_type == "btrfs" else None
    evaluate_capacity(
        free_bytes=free_bytes,
        min_free_bytes=min_free_bytes,
        fs_type=fs_type,
        btrfs_metadata_percent=metadata,
        max_btrfs_metadata_percent=max_metadata,
    )
    directory = git_dir(root)
    atomic_git_write_probe(directory)
    git_index_write_probe(root, directory)
    metadata_text = "n/a" if metadata is None else f"{metadata:.2f}%"
    print(
        "workspace-capacity-check: PASS "
        f"fs={fs_type} free_bytes={free_bytes} min_free_bytes={min_free_bytes} "
        f"btrfs_metadata={metadata_text} max_btrfs_metadata={max_metadata:.2f}% "
        "git_write=ok"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            check(args.root)
    except (CapacityError, OSError, subprocess.SubprocessError) as exc:
        print(f"workspace-capacity-check: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
