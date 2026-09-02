#!/usr/bin/env python3
"""Verify and materialize SHA-bound proof archives stored as release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/evidence-archive-assets.json"
FORMAT = "lisp65-evidence-archive-assets-v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_GIT_BLOB = 50_000_000


class AssetError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssetError(message)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(value: Any) -> str:
    require(isinstance(value, str) and value, "archive path missing")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value, f"invalid path: {value}")
    require(".." not in path.parts, f"parent traversal in path: {value}")
    return value


def load() -> dict[str, Any]:
    try:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssetError(f"cannot read asset contract: {exc}") from exc
    require(isinstance(value, dict), "asset contract must be an object")
    require(value.get("format") == FORMAT and value.get("version") == 1, "format drift")
    require(value.get("status") == "active", "asset contract is not active")
    require(value.get("repository") == "novemberist/lisp65-proof", "repository drift")
    require(value.get("release_tag") == "proof-evidence-wave2-20260718", "release tag drift")
    require(isinstance(value.get("release_url"), str), "release URL missing")
    inventory = value.get("inventory_asset")
    require(
        isinstance(inventory, dict)
        and set(inventory) == {"bytes", "name", "sha256"}
        and inventory["name"] == "lisp65-archive-inventory-20260718.json"
        and isinstance(inventory["bytes"], int)
        and SHA_RE.fullmatch(inventory["sha256"]) is not None,
        "inventory asset drift",
    )
    rows = value.get("archives")
    require(isinstance(rows, list) and rows, "archive inventory missing")
    paths: list[str] = []
    names: list[str] = []
    total = 0
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict) and set(row) == {"bytes", "path", "sha256"},
            f"archive[{index}] schema drift",
        )
        path = repo_path(row["path"])
        require(isinstance(row["bytes"], int) and row["bytes"] > 0, f"archive[{index}] size")
        require(SHA_RE.fullmatch(row["sha256"]) is not None, f"archive[{index}] SHA")
        paths.append(path)
        names.append(PurePosixPath(path).name)
        total += row["bytes"]
    require(paths == sorted(paths) and len(paths) == len(set(paths)), "archive paths drift")
    require(len(names) == len(set(names)), "release asset basenames are not unique")
    require(value.get("archive_count") == len(rows), "archive count drift")
    require(value.get("archive_bytes") == total, "archive byte total drift")
    return value


def records() -> dict[str, dict[str, Any]]:
    return {row["path"]: row for row in load()["archives"]}


def asset_record(path: str) -> dict[str, Any]:
    path = repo_path(path)
    try:
        return records()[path]
    except KeyError as exc:
        raise AssetError(f"archive is not in external asset inventory: {path}") from exc


def verify_file(path: Path, row: dict[str, Any]) -> None:
    require(path.is_file() and not path.is_symlink(), f"archive cache is not a regular file: {path}")
    require(path.stat().st_size == row["bytes"], f"archive cache size drift: {row['path']}")
    require(sha(path) == row["sha256"], f"archive cache SHA drift: {row['path']}")


def validate_git_entry(path: str, size: int) -> None:
    require(size <= MAX_GIT_BLOB, f"oversized Git blob: {size} {path}")
    require(not path.endswith(".tar.gz"), f"archive tracked in Git: {path}")
    require(path != "docs/reference/mega65-book.pdf", "third-party book tracked in Git")


def git_entry_selftest() -> None:
    validate_git_entry("docs/small.pdf", MAX_GIT_BLOB)
    for label, path, size in (
        ("oversized", "docs/large.bin", MAX_GIT_BLOB + 1),
        ("archive", "evidence/new.tar.gz", 1),
        ("book", "docs/reference/mega65-book.pdf", 1),
    ):
        try:
            validate_git_entry(path, size)
        except AssetError:
            continue
        raise AssetError(f"Git-entry selftest accepted {label}")


def index_size_gate() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0, "cannot inspect Git index")
    largest = 0
    entries = 0
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            header, encoded_path = raw.split(b"\t", 1)
            _mode, encoded_oid, stage = header.split(b" ", 2)
            path = encoded_path.decode("utf-8", "surrogateescape")
            oid = encoded_oid.decode("ascii")
        except (ValueError, UnicodeError) as exc:
            raise AssetError("malformed Git index entry") from exc
        require(stage == b"0", f"unmerged Git index entry: {path}")
        size_result = subprocess.run(
            ["git", "cat-file", "-s", oid], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        require(size_result.returncode == 0, f"cannot inspect indexed blob: {path}")
        size = int(size_result.stdout.strip())
        validate_git_entry(path, size)
        largest = max(largest, size)
        entries += 1
    print(
        f"evidence-assets: INDEX PASS entries={entries} "
        f"max-blob={largest} limit={MAX_GIT_BLOB}"
    )


def gh(*args: str, capture: bool = False) -> str:
    executable = shutil.which("gh")
    require(executable is not None, "GitHub CLI is required for release assets")
    result = subprocess.run(
        [executable, *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise AssetError(result.stderr.strip() or "GitHub CLI failed")
    return result.stdout if capture else ""


def remote_check() -> None:
    value = load()
    raw = gh(
        "api", f"repos/{value['repository']}/releases/tags/{value['release_tag']}",
        capture=True,
    )
    try:
        release = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssetError(f"invalid GitHub release response: {exc}") from exc
    expected = {PurePosixPath(row["path"]).name: row for row in value["archives"]}
    inventory = value["inventory_asset"]
    expected[inventory["name"]] = inventory
    assets = {item.get("name"): item for item in release.get("assets", [])}
    require(set(assets) == set(expected), "GitHub release asset set drift")
    for name, row in expected.items():
        item = assets[name]
        require(item.get("size") == row["bytes"], f"remote size drift: {name}")
        require(item.get("digest") == f"sha256:{row['sha256']}", f"remote SHA drift: {name}")
    print(
        f"evidence-assets: REMOTE PASS assets={len(assets)} "
        f"archive-bytes={value['archive_bytes']} tag={value['release_tag']}"
    )


def local_check(require_all: bool) -> None:
    value = load()
    present = 0
    missing = 0
    for row in value["archives"]:
        path = ROOT / row["path"]
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", row["path"]], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0
        require(not tracked, f"archive transport regressed into Git: {row['path']}")
        if path.exists():
            verify_file(path, row)
            present += 1
        else:
            missing += 1
    require(not require_all or missing == 0, f"{missing} archive assets are not materialized")
    print(
        f"evidence-assets: LOCAL PASS present={present} missing={missing} "
        f"tracked=0 require-all={'yes' if require_all else 'no'}"
    )


def materialize(paths: list[str], all_assets: bool) -> None:
    value = load()
    by_path = {row["path"]: row for row in value["archives"]}
    selected = list(by_path) if all_assets else [repo_path(path) for path in paths]
    require(bool(selected), "select at least one archive or use --all")
    for name in selected:
        require(name in by_path, f"unknown archive asset: {name}")
        row = by_path[name]
        target = ROOT / name
        if target.exists():
            verify_file(target, row)
            print(f"evidence-assets: CACHED {name}")
            continue
        with tempfile.TemporaryDirectory(prefix="lisp65-evidence-asset-") as raw_tmp:
            tmp = Path(raw_tmp)
            asset_name = PurePosixPath(name).name
            gh(
                "release", "download", value["release_tag"],
                "-R", value["repository"], "--pattern", asset_name, "--dir", str(tmp),
            )
            downloaded = tmp / asset_name
            verify_file(downloaded, row)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = target.with_name(f".{target.name}.materializing")
            shutil.copyfile(downloaded, staged)
            os.replace(staged, target)
            verify_file(target, row)
        print(f"evidence-assets: MATERIALIZED {name}")


def history_size_gate() -> None:
    process = subprocess.Popen(
        ["git", "rev-list", "--objects", "--branches", "--tags"], cwd=ROOT,
        stdout=subprocess.PIPE,
    )
    assert process.stdout is not None
    check = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)"],
        cwd=ROOT, stdin=process.stdout, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    process.stdout.close()
    process.wait()
    require(check.returncode == 0 and process.returncode == 0, "cannot inspect Git object graph")
    largest = 0
    for line in check.stdout.splitlines():
        parts = line.split(" ", 3)
        if len(parts) < 3 or parts[0] != "blob":
            continue
        size = int(parts[2])
        path = parts[3] if len(parts) == 4 else ""
        largest = max(largest, size)
        validate_git_entry(path, size)
    print(f"evidence-assets: HISTORY PASS max-blob={largest} limit={MAX_GIT_BLOB}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    local = sub.add_parser("local-check")
    local.add_argument("--require-all", action="store_true")
    sub.add_parser("remote-check")
    sub.add_parser("index-size-gate")
    sub.add_parser("history-size-gate")
    get = sub.add_parser("materialize")
    get.add_argument("path", nargs="*")
    get.add_argument("--all", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            value = load()
            git_entry_selftest()
            print(
                f"evidence-assets: SELFTEST PASS archives={value['archive_count']} "
                f"bytes={value['archive_bytes']} rejection-classes=3"
            )
        elif args.command == "local-check":
            local_check(args.require_all)
        elif args.command == "remote-check":
            remote_check()
        elif args.command == "index-size-gate":
            index_size_gate()
        elif args.command == "history-size-gate":
            history_size_gate()
        else:
            materialize(args.path, args.all)
        return 0
    except (AssetError, OSError, ValueError) as exc:
        print(f"evidence-assets: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
