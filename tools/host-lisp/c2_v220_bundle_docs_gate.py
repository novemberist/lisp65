#!/usr/bin/env python3
"""Exact approved 2.2 documentation; check actual files, never Git fallback."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = {"README.md", "docs/user-guide.md", "docs/known-issues.md",
        "docs/language-reference.md", "docs/generated/ide-keymap.md",
        "docs/releases/2.2.0.md"}


def validate(files, expected):
    if set(expected) != DOCS:
        raise ValueError("approved document contract population drift")
    if set(files) != set(expected):
        raise ValueError("2.2 document population drift")
    for path, digest in expected.items():
        if hashlib.sha256(files[path]).hexdigest() != digest:
            raise ValueError("2.2 approved document differs: " + path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="actual source or extracted bundle root; no history fallback")
    parser.add_argument("--bundle", action="store_true",
                        help="release notes occupy docs/release-notes.md in the bundle")
    args = parser.parse_args()
    contract = json.loads((ROOT / "config/c2-v220-bundle-docs.json").read_text())
    assert contract["release"] == "2.2.0"
    expected = contract["documents"]
    files = {p: (args.root / ("docs/release-notes.md"
              if args.bundle and p == "docs/releases/2.2.0.md" else p)).read_bytes()
             for p in expected}
    validate(files, expected)
    rejected = []
    for path in expected:
        incomplete = dict(expected)
        del incomplete[path]
        try:
            validate({p: files[p] for p in incomplete}, incomplete)
        except ValueError:
            rejected.append(path + ":contract-omission")
        else:
            raise ValueError("contract omission survived")
        for kind in ("omit", "change"):
            trial = dict(files)
            if kind == "omit":
                del trial[path]
            else:
                trial[path] += b"\nUnapproved claim\n"
            try:
                validate(trial, expected)
            except ValueError:
                rejected.append(path + ":" + kind)
            else:
                raise ValueError("document mutation survived")
    print("2.2 bundle-docs: PASS actual-files=%d mutations=%d approval=%s" %
          (len(files), len(rejected), contract["approval"]))


if __name__ == "__main__":
    main()
