#!/usr/bin/env python3
"""Validate the nine decided R2 migration semantics and their family fixtures."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "dialect-v2-r2-decisions.json"
DECISION_IDS = [
    "edit-autoload",
    "ide-command-short-names",
    "key-event-blocking-semantics",
    "load-libs-migration",
    "save-m65d-contract",
    "screen-library-boundary",
    "set-public-semantics",
    "string-contains-search-result",
    "string-list-conversion-removal",
]
FAMILIES = ["ide", "strings", "system-runtime"]


class DecisionError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DecisionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DecisionError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise DecisionError(f"{label} keys drift: {actual}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(value: Any, label: str, *, verify: bool) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    text = item["path"]
    path = PurePosixPath(text) if isinstance(text, str) else None
    if (
        path is None or path.is_absolute() or path.as_posix() != text
        or ".." in path.parts or not isinstance(item["sha256"], str)
        or len(item["sha256"]) != 64
    ):
        raise DecisionError(f"{label} binding is invalid")
    absolute = ROOT / text
    if verify and (
        absolute.is_symlink() or not absolute.is_file()
        or _sha(absolute) != item["sha256"]
    ):
        raise DecisionError(f"{label} SHA drift")
    return absolute


def _fixture(value: dict[str, Any], family: str) -> dict[str, dict[str, Any]]:
    _exact(value, {"format", "family", "status", "cases"}, f"{family} fixture")
    if (
        value["format"] != "lisp65-dialect-v2-r2-decision-fixture-v1"
        or value["family"] != family or value["status"] != "normative"
        or not isinstance(value["cases"], list) or not value["cases"]
    ):
        raise DecisionError(f"{family} fixture identity drift")
    cases: dict[str, dict[str, Any]] = {}
    ids: list[str] = []
    for index, raw in enumerate(value["cases"]):
        case = _exact(raw, {"id", "decision", "forms", "expected"}, f"{family} case {index}")
        case_id = case["id"]
        if (
            not isinstance(case_id, str) or not case_id
            or case["decision"] not in DECISION_IDS
            or not isinstance(case["forms"], list) or not case["forms"]
            or any(not isinstance(form, str) or not form for form in case["forms"])
            or not isinstance(case["expected"], dict) or not case["expected"]
        ):
            raise DecisionError(f"{family} case {case_id!r} is invalid")
        ids.append(case_id)
        cases[case_id] = case
    if ids != sorted(set(ids)):
        raise DecisionError(f"{family} fixture cases must be sorted and unique")
    return cases


def validate(value: dict[str, Any], *, verify_bindings: bool = True) -> dict[str, int]:
    _exact(
        value,
        {"format", "version", "status", "composition_contract", "fixtures", "decisions"},
        "R2 decision contract",
    )
    if (
        value["format"] != "lisp65-dialect-v2-r2-decisions-v1"
        or value["version"] != 1 or value["status"] != "decided"
    ):
        raise DecisionError("R2 decision contract identity drift")

    composition_path = _binding(
        value["composition_contract"], "composition contract", verify=verify_bindings
    )
    composition = _load(composition_path, "composition contract")
    _exact(
        composition,
        {"format", "version", "status", "guaranteed_session_libraries", "optional_libraries", "user_margin", "screen_boundary"},
        "composition contract",
    )
    if (
        composition["format"] != "lisp65-v2-workbench-composition-contract-v1"
        or composition["version"] != 1 or composition["status"] != "active"
        or composition["guaranteed_session_libraries"] != ["ide", "idex", "m65d"]
        or composition["optional_libraries"] != ["m65-screen"]
        or composition["user_margin"] != {
            "symbols": 32, "directory_entries_post_align": 32, "namepool_bytes": 384,
        }
        or composition["screen_boundary"] != {
            "ide_render_route": "native-callprim-not-m65-screen-library-symbols",
            "m65_screen_in_guaranteed_composition": False,
            "capacity_rule": "adding-an-optional-library-to-the-guaranteed-session-requires-a-fresh-manifest-gate",
        }
    ):
        raise DecisionError("Workbench composition boundary drift")

    fixture_rows = value["fixtures"]
    if not isinstance(fixture_rows, list) or len(fixture_rows) != 3:
        raise DecisionError("R2 fixture binding coverage drift")
    fixture_cases: dict[str, dict[str, dict[str, Any]]] = {}
    fixture_families: list[str] = []
    for index, raw in enumerate(fixture_rows):
        item = _exact(raw, {"family", "path", "sha256"}, f"fixture binding {index}")
        family = item["family"]
        fixture_families.append(family)
        path = _binding(
            {"path": item["path"], "sha256": item["sha256"]},
            f"{family} fixture", verify=verify_bindings,
        )
        fixture_cases[family] = _fixture(_load(path, f"{family} fixture"), family)
    if fixture_families != FAMILIES:
        raise DecisionError("R2 fixture families/order drift")

    rows = value["decisions"]
    if not isinstance(rows, list) or len(rows) != 9:
        raise DecisionError("R2 decision coverage drift")
    ids: list[str] = []
    referenced: set[tuple[str, str]] = set()
    for index, raw in enumerate(rows):
        item = _exact(raw, {"id", "family", "resolution", "fixture_cases"}, f"decision {index}")
        decision_id = item["id"]
        family = item["family"]
        case_ids = item["fixture_cases"]
        if (
            decision_id not in DECISION_IDS or family not in fixture_cases
            or not isinstance(item["resolution"], str) or not item["resolution"]
            or not isinstance(case_ids, list) or not case_ids
            or case_ids != sorted(set(case_ids))
        ):
            raise DecisionError(f"decision {decision_id!r} is invalid")
        ids.append(decision_id)
        for case_id in case_ids:
            case = fixture_cases[family].get(case_id)
            if case is None or case["decision"] != decision_id:
                raise DecisionError(f"decision {decision_id} fixture reference drift")
            referenced.add((family, case_id))
    if ids != DECISION_IDS:
        raise DecisionError("R2 decision ids/order drift")
    all_cases = {
        (family, case_id)
        for family, cases in fixture_cases.items() for case_id in cases
    }
    if referenced != all_cases:
        raise DecisionError("R2 fixture case parity drift")

    strings = fixture_cases["strings"]
    if (
        strings["index-basis-zero-cross-section"]["expected"].get("basis") != "zero"
        or strings["search-no-match"]["expected"] != {"result": "nil"}
    ):
        raise DecisionError("zero-based cross-section/search miss drift")
    system = fixture_cases["system-runtime"]
    if (
        system["load-libs-first-failure"]["expected"].get("rollback_loaded_libraries") is not False
        or system["key-event-default-empty-queue"]["expected"].get("empty_queue") != "nil"
        or system["set-non-symbol-type-error"]["expected"].get("result") != "type-error"
    ):
        raise DecisionError("required R2 error/non-rollback case drift")
    ide = fixture_cases["ide"]
    if ide["edit-autoload-entry"]["expected"].get("resident") is not True:
        raise DecisionError("edit resident entry drift")

    source = (ROOT / "lib" / "ide-launch.lisp").read_text(encoding="utf-8")
    if (
        "(defun edit ()" not in source or '(load-lib "ide")' not in source
        or "(ide)" not in source
    ):
        raise DecisionError("resident edit autoload implementation is missing")
    return {"decisions": len(rows), "fixtures": len(fixture_rows), "cases": len(all_cases)}


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except DecisionError:
        return
    raise DecisionError(f"selftest mutation accepted: {label}")


def selftest() -> None:
    contract = _load(DEFAULT_CONTRACT, "R2 decision contract")
    validate(contract)
    for label, change in (
        ("decision removed", lambda value: value["decisions"].pop()),
        ("composition SHA", lambda value: value["composition_contract"].update(sha256="0" * 64)),
        ("fixture case", lambda value: value["decisions"][0].update(fixture_cases=["missing"])),
    ):
        mutated = deepcopy(contract)
        change(mutated)
        _expect_failure(label, lambda value=mutated: validate(value))
    print("dialect-v2-r2-decisions: SELFTEST PASS mutations=3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "selftest"), nargs="?", default="check")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
        else:
            path = args.contract if args.contract.is_absolute() else ROOT / args.contract
            result = validate(_load(path, "R2 decision contract"))
            print(
                "dialect-v2-r2-decisions: PASS "
                f"decisions={result['decisions']} fixtures={result['fixtures']} cases={result['cases']}"
            )
        return 0
    except (DecisionError, KeyError, TypeError, ValueError) as exc:
        print(f"dialect-v2-r2-decisions: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
