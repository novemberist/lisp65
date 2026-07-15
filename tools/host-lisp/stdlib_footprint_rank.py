#!/usr/bin/env python3
"""Rank embedded stdlib bytecode objects from a generated manifest."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bytecode_p0_compiler as C  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "build" / "bytecode" / "stdlib-p0.manifest.json"
DEFAULT_SUITE = ROOT / "tests" / "bytecode" / "stdlib" / "p0-stdlib-subset.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_map(suite: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for source in suite.get("sources", []):
        path = ROOT / source
        for form in C.parse_all(path.read_text(encoding="utf-8")):
            if isinstance(form, list) and len(form) >= 4 and form[0] == "defun":
                out[form[1]] = source
    return out


def _print_entries(title: str, entries: list[dict], source_by_name: dict[str, str], limit: int) -> None:
    print(title)
    for entry in entries[:limit]:
        source = source_by_name.get(entry["name"], "?")
        print("  %4d  %-30s  %s" % (entry["length"], entry["name"], source))


def _blob_path(manifest_path: Path, manifest: dict) -> Path:
    blob = Path(manifest["blob"])
    if blob.is_absolute():
        return blob
    return ROOT / blob


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument(
        "--focus",
        default="",
        help="optional regex for a focused ranking, e.g. 'string|char|trim|subseq|search'",
    )
    parser.add_argument("--duplicate-min", type=int, default=20)
    args = parser.parse_args(argv[1:])

    manifest = _load_json(args.manifest)
    suite = _load_json(args.suite)
    entries = list(manifest.get("entries", []))
    source_by_name = _source_map(suite)

    print(
        "stdlib-footprint-rank: objects=%d code_bytes=%d directory_bytes=%d literal_nodes=%d literal_patches=%d"
        % (
            len(entries),
            int(manifest.get("code_bytes", 0)),
            int(manifest.get("directory_bytes", 0)),
            len(manifest.get("literal_nodes", [])),
            len(manifest.get("literal_patches", [])),
        )
    )

    ranked = sorted(entries, key=lambda entry: (-entry["length"], entry["name"]))
    _print_entries("top objects:", ranked, source_by_name, args.top)

    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for entry in entries:
        source = source_by_name.get(entry["name"], "?")
        totals[source][0] += int(entry["length"])
        totals[source][1] += 1
    print("by source:")
    for source, (size, count) in sorted(totals.items(), key=lambda item: (-item[1][0], item[0])):
        print("  %4d  %3d  %s" % (size, count, source))

    if args.focus:
        pattern = re.compile(args.focus)
        focused = [entry for entry in ranked if pattern.search(entry["name"])]
        _print_entries("focused objects (%s):" % args.focus, focused, source_by_name, args.top)

    blob = _blob_path(args.manifest, manifest).read_bytes()
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        start = int(entry["blob_offset"])
        end = start + int(entry["length"])
        digest = hashlib.sha256(blob[start:end]).hexdigest()
        by_hash[digest].append(entry)
    duplicate_groups = [
        group
        for group in by_hash.values()
        if len(group) > 1 and int(group[0]["length"]) >= args.duplicate_min
    ]
    print("exact duplicate code objects >= %d bytes:" % args.duplicate_min)
    if not duplicate_groups:
        print("  none")
    for group in sorted(duplicate_groups, key=lambda items: (-items[0]["length"], items[0]["name"])):
        names = ", ".join(entry["name"] for entry in group)
        print("  %4d  %s" % (group[0]["length"], names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
