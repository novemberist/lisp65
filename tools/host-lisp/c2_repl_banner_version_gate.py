#!/usr/bin/env python3
"""Bind the visible Workbench banner to the canonical release version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "lib/repl-banner.lisp"
AUTHORITY = ROOT / "config/v12-known-issues.json"
SUBTITLE_PREFIX = "WORKBENCH "
SUBTITLE_CENTER_COLUMN = 55
SUBTITLE_PATTERN = re.compile(
    r'\(defun %banner-subtitle \(\)\s*'
    r'\(let \(\(text "([^"]+)"\)\)\s*'
    r'\(dotimes \(index ([0-9]+) nil\)\s*'
    r'\(screen-put-char \(\+ ([0-9]+) index\) 7 '
    r'\(string-ref text index\) 15\)\)\)\)',
    re.MULTILINE,
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def validate(source: str, authority: dict[str, Any]) -> dict[str, Any]:
    require(
        authority.get("format") == "lisp65-v12-known-issues-register-v1",
        "release authority format drift",
    )
    release = authority.get("release")
    require(
        isinstance(release, str)
        and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", release) is not None,
        "release authority has no canonical semantic version",
    )
    matches = list(SUBTITLE_PATTERN.finditer(source))
    require(len(matches) == 1, "expected exactly one canonical banner subtitle body")
    text, length_text, start_text = matches[0].groups()
    expected_text = SUBTITLE_PREFIX + release
    expected_length = len(expected_text)
    expected_start = SUBTITLE_CENTER_COLUMN - expected_length // 2
    require(text == expected_text, "banner release text drift")
    require(int(length_text) == expected_length, "banner subtitle length drift")
    require(int(start_text) == expected_start, "banner subtitle centering drift")
    require(
        source.count(expected_text) == 1,
        "canonical release subtitle must occur exactly once",
    )
    return {
        "release": release,
        "subtitle": expected_text,
        "length": expected_length,
        "start_column": expected_start,
        "center_column": SUBTITLE_CENTER_COLUMN,
    }


def selftest(source: str, authority: dict[str, Any]) -> int:
    result = validate(source, authority)
    major, minor, patch = (int(part) for part in result["release"].split("."))
    next_release = f"{major}.{minor}.{patch + 1}"
    mutations: list[tuple[str, str, dict[str, Any]]] = [
        (
            "stale-version",
            source.replace(result["subtitle"], "WORKBENCH 1.2.2", 1),
            authority,
        ),
        (
            "wrong-length",
            source.replace(
                f"(dotimes (index {result['length']} nil)",
                f"(dotimes (index {result['length'] + 1} nil)",
                1,
            ),
            authority,
        ),
        (
            "wrong-centering",
            source.replace(
                f"(screen-put-char (+ {result['start_column']} index)",
                f"(screen-put-char (+ {result['start_column'] - 1} index)",
                1,
            ),
            authority,
        ),
        (
            "release-bump-without-banner",
            source,
            {**authority, "release": next_release},
        ),
    ]
    for label, mutant_source, mutant_authority in mutations:
        try:
            validate(mutant_source, mutant_authority)
        except GateError:
            continue
        raise GateError(f"mutation accepted: {label}")
    return len(mutations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        source = SOURCE.read_text(encoding="utf-8")
        authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
        mutations = selftest(source, authority) if args.selftest else 0
        result = validate(source, authority)
        suffix = f" mutations={mutations}" if args.selftest else ""
        print(
            "c2-repl-banner-version: PASS "
            f"subtitle={result['subtitle']!r} length={result['length']} "
            f"start={result['start_column']}{suffix}"
        )
        return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"c2-repl-banner-version: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
