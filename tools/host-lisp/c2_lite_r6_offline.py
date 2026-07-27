#!/usr/bin/env python3
"""Verify a C2-lite R6 package using only bytes inside that package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
ROLE_COUNT = 19


class VerifyError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise VerifyError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "manifest missing")
    try:
        value = json.loads(
            path.read_text(encoding="ascii"),
            object_pairs_hook=strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerifyError(f"manifest unreadable: {error}") from error
    require(isinstance(value, dict), "manifest must be an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path(value: Any) -> Path:
    require(isinstance(value, str) and value, "invalid package path")
    pure = PurePosixPath(value)
    require(
        not pure.is_absolute() and pure.as_posix() == value
        and ".." not in pure.parts,
        f"unsafe package path: {value}",
    )
    return ROOT / Path(*pure.parts)


def identity_sha(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    identity = [
        {key: row[key] for key in keys}
        for row in sorted(rows, key=lambda row: tuple(row[key] for key in keys[:2]))
    ]
    return hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def verify() -> None:
    value = load(MANIFEST)
    require(
        value.get("format") == "lisp65-c2-lite-R6-package-v1"
        and value.get("version") == 1
        and value.get("status") == "passed-transform-and-package-only"
        and value.get("result") == "passed",
        "R6 manifest identity drift",
    )
    product = value.get("product")
    require(isinstance(product, dict), "product block missing")
    rows = product.get("artifacts")
    require(
        isinstance(rows, list) and len(rows) == ROLE_COUNT
        and product.get("artifact_count") == ROLE_COUNT,
        "product role count drift",
    )
    roles = []
    ship_paths = []
    for row in rows:
        require(
            isinstance(row, dict)
            and isinstance(row.get("role"), str)
            and isinstance(row.get("name"), str)
            and type(row.get("bytes")) is int
            and isinstance(row.get("sha256"), str)
            and isinstance(row.get("ship_path"), str),
            "malformed product row",
        )
        artifact = path(row["ship_path"])
        require(
            artifact.is_file() and not artifact.is_symlink()
            and artifact.stat().st_size == row["bytes"]
            and sha(artifact) == row["sha256"],
            f"product byte drift: {row['role']}",
        )
        roles.append(row["role"])
        ship_paths.append(row["ship_path"])
    require(
        len(set(roles)) == ROLE_COUNT and len(set(ship_paths)) == ROLE_COUNT,
        "product role/path duplication",
    )
    require(
        identity_sha(
            rows, ("role", "name", "bytes", "sha256"),
        ) == product.get("artifact_set_sha256"),
        "product artifact-set drift",
    )

    files = value.get("files")
    require(isinstance(files, list) and files, "file inventory missing")
    inventory_paths = []
    for row in files:
        require(
            isinstance(row, dict)
            and set(row) == {"path", "bytes", "sha256", "mode"},
            "malformed package file row",
        )
        item = path(row["path"])
        require(
            item.is_file() and not item.is_symlink()
            and item.stat().st_size == row["bytes"]
            and sha(item) == row["sha256"]
            and f"0{stat.S_IMODE(item.stat().st_mode):03o}" == row["mode"],
            f"package file drift: {row['path']}",
        )
        inventory_paths.append(row["path"])
    require(len(set(inventory_paths)) == len(files), "duplicate package file")
    actual = {
        item.relative_to(ROOT).as_posix()
        for item in ROOT.rglob("*")
        if item.is_file() and item != MANIFEST
    }
    require(actual == set(inventory_paths), "unbound package file set")
    require(
        identity_sha(
            files, ("path", "bytes", "sha256", "mode"),
        ) == value.get("package_set_sha256"),
        "package-set drift",
    )
    require(
        value.get("claims", {}).get("R6") == "passed-exact-19-role-package"
        and value.get("claims", {}).get("G6") == "not-run"
        and value.get("claims", {}).get("release") == "not-release-capable",
        "R6 claim boundary drift",
    )
    print(
        "C2-LITE R6 OFFLINE PASS "
        f"roles=19 files={len(files)} "
        f"set={product['artifact_set_sha256']}"
    )


if __name__ == "__main__":
    try:
        verify()
    except VerifyError as error:
        print(f"C2-LITE R6 OFFLINE FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
