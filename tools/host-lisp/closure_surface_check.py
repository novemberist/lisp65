#!/usr/bin/env python3
"""Validate the closure surface matrix against Eval and P0 bytecode rows."""

from __future__ import annotations

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_bundle as PB  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
from mvp_prelude_m1_eval_oracle import (  # noqa: E402
    DEFAULT_PRELUDE,
    Env,
    EvalError,
    ReaderError,
    check_case,
    load_prelude,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = ROOT / "tests" / "bytecode" / "runtime" / "closure-surface-matrix.json"
ALLOWED_STATUS = {"green", "known-open", "open", "deferred"}


def _entry_name(case_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", case_id).strip("_").lower()
    return "__closure_%s" % (safe or "case")


def _run_bytecode_expr(expr: str, entry: str) -> str:
    heap = C.prepare_heap([entry])
    form = ["defun", entry, [], C.parse_one(expr)]
    name, code, helpers = C.compile_top_form_with_helpers(form, heap)
    names = [name]
    code_by_name = {name: code}
    for helper_name, helper_code in helpers:
        if helper_name in code_by_name:
            raise AssertionError("duplicate helper: %s" % helper_name)
        names.append(helper_name)
        code_by_name[helper_name] = helper_code
    bundle = PB.pack_code_objects(heap, names, code_by_name, base_addr=PB.DEFAULT_BASE_ADDR)
    directory = PB.load_bundle_directory(heap, bundle)
    vm = B.P0VM(heap=heap, directory=directory)
    result = vm.run(directory[heap.intern(entry)], [])
    return heap.obj_to_text(result)


def _validate_metadata(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("format") != "lisp65-closure-surface-matrix-v1":
        errors.append("bad format")
    cases = data.get("cases", [])
    seen = set()
    categories = set()
    for case in cases:
        case_id = case.get("id")
        if not case_id:
            errors.append("case without id")
            continue
        if case_id in seen:
            errors.append("duplicate id: %s" % case_id)
        seen.add(case_id)
        category = case.get("category")
        if not category:
            errors.append("%s: missing category" % case_id)
        else:
            categories.add(category)
        for field in ("expr", "expect", "eval", "bytecode", "target"):
            if field not in case:
                errors.append("%s: missing %s" % (case_id, field))
        for field in ("eval", "bytecode", "target"):
            status = case.get(field)
            if status is not None and status not in ALLOWED_STATUS:
                errors.append("%s: bad %s status %r" % (case_id, field, status))
        if case.get("bytecode") == "known-open" and not case.get("open_issue"):
            errors.append("%s: bytecode known-open needs open_issue" % case_id)
        if case.get("expect_bytecode_error") is not None and not case.get("expect_bytecode_error"):
            errors.append("%s: empty expect_bytecode_error" % case_id)
    required = set(data.get("required_categories", []))
    missing = sorted(required - categories)
    if missing:
        errors.append("missing required categories: %s" % ", ".join(missing))
    return errors


def main(argv: list[str]) -> int:
    matrix = Path(argv[1]) if len(argv) > 1 else DEFAULT_MATRIX
    data = json.loads(matrix.read_text(encoding="utf-8"))
    errors = _validate_metadata(data)
    if errors:
        for error in errors:
            print("FAIL %s" % error, file=sys.stderr)
        print("closure-surface-check: PASS=0 FAIL=%d" % len(errors))
        return 1

    try:
        load_prelude(DEFAULT_PRELUDE, reset=True)
    except (EvalError, ReaderError) as exc:
        print("FAIL prelude load: %s" % exc, file=sys.stderr)
        print("closure-surface-check: PASS=0 FAIL=1")
        return 1

    passed = 0
    failed = 0
    env = Env()
    for case in data["cases"]:
        if case["eval"] == "green":
            ok, message = check_case(
                {"name": case["id"], "input": case["expr"], "expect": case["expect"]},
                env,
            )
            if ok:
                passed += 1
            else:
                failed += 1
                print("FAIL eval %s" % message, file=sys.stderr)
        if case["bytecode"] == "green":
            try:
                got = _run_bytecode_expr(case["expr"], _entry_name(case["id"]))
                if got == case["expect"].lower():
                    passed += 1
                else:
                    failed += 1
                    print(
                        "FAIL bytecode %s: got %r expected %r"
                        % (case["id"], got, case["expect"].lower()),
                        file=sys.stderr,
                    )
            except Exception as exc:
                failed += 1
                print("FAIL bytecode %s: %s" % (case["id"], exc), file=sys.stderr)
        elif case["bytecode"] == "known-open" and case.get("expect_bytecode_error"):
            expected_error = case["expect_bytecode_error"]
            try:
                got = _run_bytecode_expr(case["expr"], _entry_name(case["id"]))
                failed += 1
                print(
                    "FAIL bytecode %s: expected error containing %r, got %r"
                    % (case["id"], expected_error, got),
                    file=sys.stderr,
                )
            except Exception as exc:
                message = str(exc)
                if expected_error in message:
                    passed += 1
                else:
                    failed += 1
                    print(
                        "FAIL bytecode %s: expected error containing %r, got %r"
                        % (case["id"], expected_error, message),
                        file=sys.stderr,
                    )

    print("closure-surface-check: PASS=%d FAIL=%d" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
