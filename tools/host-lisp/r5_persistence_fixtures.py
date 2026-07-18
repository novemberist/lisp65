#!/usr/bin/env python3
"""Single source for the R5 destructive persistence fixture geometry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/r5-persistence-fixtures.json"


class FixtureError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise FixtureError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise FixtureError(f"{label} keys drift: {actual}")
    return value


def load_fixtures(path: Path = CONFIG) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError(f"cannot read fixture contract: {exc}") from exc
    _exact(value, {"format", "version", "fixed_write", "save_new", "save_new_scan"}, "fixture contract")
    if value["format"] != "lisp65-r5-persistence-fixtures-v1" or value["version"] != 1:
        raise FixtureError("fixture contract identity drift")
    fixed = _exact(
        value["fixed_write"],
        {"track", "first_sector", "second_sector", "directory_track", "directory_sector", "directory_entry"},
        "fixed_write",
    )
    save = _exact(
        value["save_new"],
        {"track", "first_sector", "second_sector", "directory_track", "directory_sector", "directory_entry"},
        "save_new",
    )
    scan = _exact(
        value["save_new_scan"],
        {
            "track", "reserved_sector", "first_sector", "second_sector",
            "directory_track", "directory_sector", "directory_entry",
        },
        "save_new_scan",
    )
    for label, row in (("fixed_write", fixed), ("save_new", save), ("save_new_scan", scan)):
        for key, item in row.items():
            if not isinstance(item, int) or isinstance(item, bool):
                raise FixtureError(f"{label}.{key} must be an integer")
        if not (41 <= row["track"] <= 80):
            raise FixtureError(f"{label}.track must use BAM sector 2")
        for key in ("first_sector", "second_sector"):
            if not (0 <= row[key] < 40):
                raise FixtureError(f"{label}.{key} out of range")
        if row["second_sector"] != row["first_sector"] + 1:
            raise FixtureError(f"{label} sectors must be consecutive")
        if row["directory_track"] != 40 or not (3 <= row["directory_sector"] < 40):
            raise FixtureError(f"{label} directory geometry drift")
        if not (0 <= row["directory_entry"] < 8):
            raise FixtureError(f"{label}.directory_entry out of range")
    if scan["reserved_sector"] + 1 != scan["first_sector"]:
        raise FixtureError("save_new_scan reserve/first-sector relation drift")
    if fixed["track"] != save["track"] or fixed["track"] != scan["track"]:
        raise FixtureError("fixture tracks must share one allocator scan track")
    return value


def get_value(path: str) -> int | str:
    value: Any = load_fixtures()
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise FixtureError(f"unknown fixture field: {path}")
        value = value[part]
    if not isinstance(value, (int, str)) or isinstance(value, bool):
        raise FixtureError(f"fixture field is not scalar: {path}")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "get"))
    parser.add_argument("field", nargs="?")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            if args.field is not None:
                raise FixtureError("check takes no field")
            value = load_fixtures()
            fixed = value["fixed_write"]
            print(
                "R5 persistence fixtures: PASS "
                f"fixed=T{fixed['track']}/S{fixed['first_sector']}-S{fixed['second_sector']}"
            )
        else:
            if args.field is None:
                raise FixtureError("get requires a field")
            print(get_value(args.field))
    except FixtureError as exc:
        print(f"r5-persistence-fixtures: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
