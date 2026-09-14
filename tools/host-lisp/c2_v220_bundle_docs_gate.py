#!/usr/bin/env python3
"""Exact 2.2 release seal or actual export/bundle files; never implicit fallback."""
import argparse
import hashlib
import json
import re
import subprocess
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--root", type=Path, default=ROOT,
                        help="actual source or extracted bundle root; no history fallback")
    mode.add_argument("--sealed-release", action="store_true",
                      help="explicit historical source check; not an export or bundle check")
    parser.add_argument("--bundle", action="store_true",
                        help="release notes occupy docs/release-notes.md in the bundle")
    args = parser.parse_args()
    contract = json.loads((ROOT / "config/c2-v220-bundle-docs.json").read_text())
    assert contract["release"] == "2.2.0"
    expected = contract["documents"]
    if args.sealed_release:
        if args.bundle:
            parser.error("a bundle must be checked from its actual files")
        commit = contract["historical_source_commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("unbound historical release commit")
        files = {p: subprocess.check_output(["git", "show", commit + ":" + p], cwd=ROOT)
                 for p in expected}
    else:
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
    # Neither a historical nor an actual-file check may accept a live draft
    # merely because the other source population is available.
    trial = dict(files)
    trial["docs/user-guide.md"] += b"\nLive successor draft\n"
    try:
        validate(trial, expected)
    except ValueError:
        rejected.append("live-successor-substitution")
    else:
        raise ValueError("live successor accepted as released documentation")
    print("2.2 bundle-docs: PASS mode=%s files=%d mutations=%d approval=%s" %
          ("historical-seal" if args.sealed_release else "actual-files",
           len(files), len(rejected), contract["approval"]))


if __name__ == "__main__":
    main()
