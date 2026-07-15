#!/usr/bin/env python3
"""Schema validation for the normative lisp65 reader fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


FIXTURE_FORMAT = "lisp65-reader-cases-v1"
FIXTURE_KEYS = {"format", "description", "cases"}
SUCCESS_CASE_KEYS = {"name", "input", "expect"}
ERROR_CASE_KEYS = {"name", "input", "error"}


class FixtureError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def validate_fixture(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise FixtureError("top level must be an object")
    if set(data) != FIXTURE_KEYS:
        raise FixtureError(
            f"top-level keys must be exactly {sorted(FIXTURE_KEYS)}, got {sorted(data)}"
        )
    if data["format"] != FIXTURE_FORMAT:
        raise FixtureError(
            f"format must be {FIXTURE_FORMAT!r}, got {data['format']!r}"
        )
    if not isinstance(data["description"], str) or not data["description"].strip():
        raise FixtureError("description must be a non-empty string")
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise FixtureError("cases must be a non-empty array")

    names: set[str] = set()
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            raise FixtureError(f"{label} must be an object")
        keys = set(case)
        if keys not in (SUCCESS_CASE_KEYS, ERROR_CASE_KEYS):
            raise FixtureError(
                f"{label} keys must be exactly {sorted(SUCCESS_CASE_KEYS)} or "
                f"{sorted(ERROR_CASE_KEYS)}, got {sorted(keys)}"
            )
        name = case["name"]
        if not isinstance(name, str) or not name.strip():
            raise FixtureError(f"{label}.name must be a non-empty string")
        if name in names:
            raise FixtureError(f"{label}.name duplicates {name!r}")
        names.add(name)
        if not isinstance(case["input"], str):
            raise FixtureError(f"{label}.input must be a string")
        if keys == SUCCESS_CASE_KEYS:
            if not isinstance(case["expect"], str):
                raise FixtureError(f"{label}.expect must be a string")
        elif case["error"] is not True:
            raise FixtureError(f"{label}.error must be true")
    return cases


def load_fixture(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FixtureError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_strict_object)
    except FixtureError:
        raise
    except json.JSONDecodeError as exc:
        raise FixtureError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return validate_fixture(data)


def selftest() -> int:
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lisp65-reader-fixture-") as temp_name:
        root = Path(temp_name)
        good = root / "good.json"
        good.write_text(
            json.dumps(
                {
                    "format": FIXTURE_FORMAT,
                    "description": "selftest",
                    "cases": [{"name": "nil", "input": "nil", "expect": "NIL"}],
                }
            ),
            encoding="ascii",
        )
        if len(load_fixture(good)) != 1:
            raise AssertionError("valid fixture did not load")
        cases += 1

        duplicate = root / "duplicate.json"
        duplicate.write_text(
            '{"format":"wrong","format":"%s","description":"x","cases":[]}\n'
            % FIXTURE_FORMAT,
            encoding="ascii",
        )
        try:
            load_fixture(duplicate)
        except FixtureError as exc:
            if "duplicate JSON key" not in str(exc):
                raise AssertionError(f"wrong duplicate-key error: {exc}") from exc
        else:
            raise AssertionError("duplicate JSON key was accepted")
        cases += 1

        invalid_utf8 = root / "invalid-utf8.json"
        invalid_utf8.write_bytes(b"\xff")
        try:
            load_fixture(invalid_utf8)
        except FixtureError as exc:
            if "cannot read" not in str(exc):
                raise AssertionError(f"wrong UTF-8 error: {exc}") from exc
        else:
            raise AssertionError("invalid UTF-8 was accepted")
        cases += 1

    print(f"reader-fixture selftest: PASS cases={cases}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", required=True)
    parser.parse_args(argv)
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
