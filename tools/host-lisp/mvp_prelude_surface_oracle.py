#!/usr/bin/env python3
"""Static oracle for the first lisp65 Prelude surface.

This is not a Lisp evaluator. It checks the contract in lib/prelude-surface.json:
Lane L may assume only the minimal core from docs/archive/pre-1.0/reference/core-vs-library.md, and every
Prelude dependency must be either core or another declared Prelude symbol.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SURFACE = ROOT / "lib" / "prelude-surface.json"


def canonical(name: str) -> str:
    return name.lower()


def load_surface(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_string_list(
    errors: list[str],
    context: str,
    record: dict[str, Any],
    field: str,
) -> list[str]:
    value = record.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{context}: {field} must be a list of strings")
        return []
    return [canonical(item) for item in value]


def collect_deferred(
    surface: dict[str, Any],
    errors: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    deferred_records: dict[str, dict[str, Any]] = {}
    deferred_stages: dict[str, str] = {}

    for stage in surface.get("deferred", []):
        stage_name = stage.get("stage")
        kind = stage.get("kind")
        symbols = stage.get("symbols", {})
        if not isinstance(stage_name, str) or not stage_name:
            errors.append("deferred stage must have a non-empty stage name")
            stage_name = "<unknown>"
        if not isinstance(kind, str) or not kind:
            errors.append(f"{stage_name}: deferred stage must declare kind")
        if isinstance(symbols, list):
            items = ((name, {}) for name in symbols)
        elif isinstance(symbols, dict):
            items = symbols.items()
        else:
            errors.append(f"{stage_name}: symbols must be a list or object")
            continue

        for name, record in items:
            if not isinstance(name, str) or not name:
                errors.append(f"{stage_name}: deferred symbol names must be non-empty strings")
                continue
            key = canonical(name)
            if key in deferred_records:
                errors.append(
                    f"{name}: duplicate deferred symbol, first seen in {deferred_stages[key]}"
                )
            if record is None:
                record = {}
            if not isinstance(record, dict):
                errors.append(f"{name}: deferred metadata must be an object")
                record = {}
            deferred_records[key] = record
            deferred_stages[key] = stage_name

    return deferred_records, deferred_stages


def check_surface(surface: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if surface.get("lisp_model") != "lisp-2":
        errors.append("surface must declare lisp_model=lisp-2")

    core_names = set()
    for group in ("special_forms", "macro_mechanism", "primitives"):
        core_names.update(canonical(name) for name in surface["core"].get(group, []))

    library_names: dict[str, str] = {}
    dependencies: dict[str, list[str]] = {}
    for stage in surface["library"]:
        for name, deps in stage["symbols"].items():
            key = canonical(name)
            if key in core_names:
                errors.append(f"{name}: library symbol duplicates core name")
            if key in library_names:
                errors.append(f"{name}: duplicate library symbol, first seen in {library_names[key]}")
            library_names[key] = stage["stage"]
            dependencies[key] = [canonical(dep) for dep in deps]

    available = core_names | set(library_names)
    for name, deps in dependencies.items():
        for dep in deps:
            if dep == name:
                continue
            if dep not in available:
                errors.append(f"{name}: unknown dependency {dep}")

    deferred_records, deferred_stages = collect_deferred(surface, errors)
    deferred = set(deferred_records)

    overlap = deferred & set(library_names)
    for name in sorted(overlap):
        errors.append(f"{name}: appears in both library and deferred")
    core_overlap = deferred & core_names
    for name in sorted(core_overlap):
        errors.append(f"{name}: appears in both core and deferred")

    deferred_available = available | deferred
    for name, record in deferred_records.items():
        context = f"{name} ({deferred_stages[name]})"
        reason = record.get("reason")
        if reason is not None and (not isinstance(reason, str) or not reason):
            errors.append(f"{context}: reason must be a non-empty string")
        category = record.get("category")
        if category is not None and (not isinstance(category, str) or not category):
            errors.append(f"{context}: category must be a non-empty string")

        for dep in require_string_list(errors, context, record, "depends_on"):
            if dep == name:
                errors.append(f"{context}: depends_on must not include itself")
            elif dep not in deferred_available:
                errors.append(f"{context}: unknown deferred dependency {dep}")
        require_string_list(errors, context, record, "requires_core")
        require_string_list(errors, context, record, "blocked_by")

    if "define" in core_names:
        errors.append("core contract must not include Scheme-style define")
    if "lambda" not in core_names or "set-symbol-function" not in core_names:
        errors.append("core contract must include lambda and set-symbol-function before defun can run")
    if "defmacro" not in core_names:
        errors.append("core contract must include defmacro until macro definition can be bootstrapped")
    if "function" not in core_names or "funcall" not in core_names:
        errors.append("Lisp-2 contract must include function and funcall")
    if "macro-expansion-hook" not in core_names:
        errors.append("core contract must include macro-expansion-hook")

    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_SURFACE
    surface = load_surface(path)
    errors = check_surface(surface)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"mvp-prelude-surface-oracle: PASS=0 FAIL={len(errors)}")
        return 1

    count = sum(len(stage["symbols"]) for stage in surface["library"])
    deferred = sum(len(stage.get("symbols", [])) for stage in surface.get("deferred", []))
    print(f"mvp-prelude-surface-oracle: PASS={count} FAIL=0 DEFERRED={deferred}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
