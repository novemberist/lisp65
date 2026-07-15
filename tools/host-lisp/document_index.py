#!/usr/bin/env python3
"""Validate the authoritative classification of tracked project documents."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any, Callable


FORMAT = "lisp65-document-index-v1"
CLASSES = ("current", "contract", "proposal", "reference", "historical")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = ROOT / "config" / "document-index.json"
ROOT_KEYS = {"format", "classes", "documents"}
ENTRY_KEYS = {"path", "class"}


class IndexError(RuntimeError):
    """The document index is malformed or has drifted from Git."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IndexError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_index(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise IndexError(f"index must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except IndexError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexError(f"cannot read document index {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IndexError("index root must be an object")
    return value


def _exact_keys(value: Any, allowed: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise IndexError(f"{label} must be an object")
    keys = set(value)
    missing = sorted(allowed - keys)
    unknown = sorted(keys - allowed - optional)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise IndexError(f"{label} has " + "; ".join(details))


def _canonical_doc_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise IndexError(f"{label} must be a non-empty string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or ".." in path.parts
        or len(path.parts) < 2
        or path.parts[0] != "docs"
        or path.suffix != ".md"
    ):
        raise IndexError(f"{label} is not a canonical docs/*.md path: {value!r}")
    return value


def tracked_documents(root: Path) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", "docs"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"").decode("utf-8", "replace").strip()
        raise IndexError(f"cannot enumerate tracked documents: {detail or exc}") from exc
    paths = tuple(
        sorted(
            item.decode("utf-8")
            for item in result.stdout.split(b"\0")
            if item and item.decode("utf-8").endswith(".md")
        )
    )
    for index, path in enumerate(paths):
        _canonical_doc_path(path, f"tracked document {index}")
    return paths


def validate_index(raw: dict[str, Any], tracked: tuple[str, ...]) -> dict[str, int]:
    _exact_keys(raw, ROOT_KEYS, set(), "index")
    if raw["format"] != FORMAT:
        raise IndexError(f"format must be {FORMAT!r}")
    if raw["classes"] != list(CLASSES):
        raise IndexError(f"classes must be the pinned ordered vocabulary {list(CLASSES)!r}")

    documents = raw["documents"]
    if not isinstance(documents, list):
        raise IndexError("documents must be a list")

    indexed: list[str] = []
    entries: dict[str, dict[str, Any]] = {}
    counts = {name: 0 for name in CLASSES}
    for number, entry in enumerate(documents):
        label = f"documents[{number}]"
        _exact_keys(entry, ENTRY_KEYS, {"superseded_by"}, label)
        path = _canonical_doc_path(entry["path"], f"{label}.path")
        doc_class = entry["class"]
        if doc_class not in CLASSES:
            raise IndexError(f"{label}.class is unsupported: {doc_class!r}")
        if path in entries:
            raise IndexError(f"duplicate document entry: {path}")
        if "superseded_by" in entry:
            _canonical_doc_path(entry["superseded_by"], f"{label}.superseded_by")
        indexed.append(path)
        entries[path] = entry
        counts[doc_class] += 1

    if indexed != sorted(indexed):
        raise IndexError("documents must be sorted lexicographically by path")

    tracked_set = set(tracked)
    indexed_set = set(indexed)
    missing = sorted(tracked_set - indexed_set)
    unknown = sorted(indexed_set - tracked_set)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing tracked documents: " + ", ".join(missing))
        if unknown:
            details.append("untracked/unknown documents: " + ", ".join(unknown))
        raise IndexError("; ".join(details))

    edges: dict[str, str] = {}
    for path, entry in entries.items():
        target = entry.get("superseded_by")
        if target is None:
            continue
        if target == path:
            raise IndexError(f"superseded_by cannot reference itself: {path}")
        if target not in entries:
            raise IndexError(f"superseded_by target is not indexed: {path} -> {target}")
        edges[path] = target

    for start in edges:
        seen: set[str] = set()
        current = start
        while current in edges:
            if current in seen:
                raise IndexError(f"superseded_by cycle contains {current}")
            seen.add(current)
            current = edges[current]
    return counts


def verify_files(root: Path, tracked: tuple[str, ...]) -> None:
    for relative in tracked:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise IndexError(f"tracked document must be a regular non-symlink file: {relative}")


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except IndexError:
        return
    raise IndexError(f"selftest mutation was accepted: {label}")


def run_selftest() -> None:
    paths = ("docs/current.md", "docs/old.md", "docs/reference/api.md")
    base: dict[str, Any] = {
        "format": FORMAT,
        "classes": list(CLASSES),
        "documents": [
            {"path": "docs/current.md", "class": "current"},
            {
                "path": "docs/old.md",
                "class": "historical",
                "superseded_by": "docs/current.md",
            },
            {"path": "docs/reference/api.md", "class": "reference"},
        ],
    }
    validate_index(base, paths)

    def mutation(change: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        def check() -> None:
            value = deepcopy(base)
            change(value)
            validate_index(value, paths)

        return check

    _expect_failure("unknown root field", mutation(lambda value: value.update(extra=True)))
    _expect_failure("wrong class vocabulary", mutation(lambda value: value["classes"].reverse()))
    _expect_failure("missing tracked document", mutation(lambda value: value["documents"].pop()))
    _expect_failure(
        "unknown document",
        mutation(lambda value: value["documents"].append({"path": "docs/z.md", "class": "proposal"})),
    )
    _expect_failure(
        "duplicate entry",
        mutation(lambda value: value["documents"].insert(1, deepcopy(value["documents"][0]))),
    )
    _expect_failure(
        "invalid class",
        mutation(lambda value: value["documents"][0].update({"class": "active"})),
    )
    _expect_failure(
        "noncanonical path",
        mutation(lambda value: value["documents"][0].update({"path": "docs/../README.md"})),
    )
    _expect_failure(
        "unsorted entries", mutation(lambda value: value["documents"].reverse())
    )
    _expect_failure(
        "missing superseded target",
        mutation(lambda value: value["documents"][1].update({"superseded_by": "docs/missing.md"})),
    )
    _expect_failure(
        "self superseded target",
        mutation(lambda value: value["documents"][1].update({"superseded_by": "docs/old.md"})),
    )

    def make_cycle(value: dict[str, Any]) -> None:
        value["documents"][0]["superseded_by"] = "docs/old.md"

    _expect_failure("superseded cycle", mutation(make_cycle))

    with tempfile.TemporaryDirectory() as temp_dir:
        duplicate_json = Path(temp_dir) / "duplicate.json"
        duplicate_json.write_text(
            '{"format":"a","format":"b","classes":[],"documents":[]}\n',
            encoding="utf-8",
        )
        _expect_failure("duplicate JSON key", lambda: load_index(duplicate_json))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.selftest:
            run_selftest()
            print("document-index: SELFTEST PASS mutations=12")
            return 0
        root = args.root.resolve()
        index_arg = args.index if args.index is not None else Path("config/document-index.json")
        index = index_arg if index_arg.is_absolute() else root / index_arg
        raw = load_index(index)
        tracked = tracked_documents(root)
        counts = validate_index(raw, tracked)
        verify_files(root, tracked)
    except IndexError as exc:
        print(f"document-index: FAIL: {exc}", file=sys.stderr)
        return 1
    summary = " ".join(f"{name}={counts[name]}" for name in CLASSES)
    print(f"document-index: PASS documents={len(tracked)} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
