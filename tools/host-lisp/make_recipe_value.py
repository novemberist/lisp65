#!/usr/bin/env python3
"""Resolve dynamic Make recipe values fail-closed, never while parsing Makefiles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


class ValueError_(RuntimeError):
    pass


def git(*args: str, root: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode or not value:
        raise ValueError_(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return value


def json_get(path: Path, dotted: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError_(f"JSON input is not a regular file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    for key in dotted.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError_(f"JSON key is absent: {dotted}")
        value = value[key]
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError_(f"JSON value is not a scalar string/integer: {dotted}")
    return str(value)


def hash_files(paths: list[Path]) -> str:
    if not paths:
        raise ValueError_("hash-files population is empty")
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if path.is_symlink() or not path.is_file():
            raise ValueError_(f"hash input is not a regular file: {path}")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"  ")
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="lisp65-make-value-") as name:
        root = Path(name)
        path = root / "a.json"
        path.write_text('{"a":{"b":7}}\n', encoding="utf-8")
        if json_get(path, "a.b") != "7":
            raise ValueError_("JSON scalar selftest failed")
        first = hash_files([path])
        path.write_text('{"a":{"b":8}}\n', encoding="utf-8")
        if hash_files([path]) == first:
            raise ValueError_("hash mutation survived")
        try:
            git("rev-parse", "HEAD", root=root)
        except ValueError_:
            pass
        else:
            raise ValueError_("Git lookup did not fail closed outside a repository")
    print("make-recipe-value: SELFTEST PASS mutations=2 parse-time-shell=forbidden")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    item = sub.add_parser("json-get")
    item.add_argument("path", type=Path)
    item.add_argument("key")
    hashed = sub.add_parser("hash-files")
    hashed.add_argument("paths", nargs="+", type=Path)
    head = sub.add_parser("git-head")
    date = sub.add_parser("git-date")
    date.add_argument("commit")
    short = sub.add_parser("git-short")
    short.add_argument("commit")
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.action == "json-get":
            print(json_get(args.path, args.key))
        elif args.action == "hash-files":
            print(hash_files(args.paths)[:40])
        elif args.action == "git-head":
            print(git("rev-parse", "HEAD"))
        elif args.action == "git-date":
            print(git("show", "-s", "--format=%cs", args.commit))
        elif args.action == "git-short":
            print(git("rev-parse", "--short=7", args.commit))
        else:
            selftest()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError_) as error:
        print(f"make-recipe-value: FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
