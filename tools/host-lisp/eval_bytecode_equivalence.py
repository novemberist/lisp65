#!/usr/bin/env python3
"""Compare the M1 host evaluator and P0 host bytecode VM on shared expressions."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as S  # noqa: E402
from mvp_cl_reader_oracle import DottedList, NIL, String, Symbol, read_single  # noqa: E402
from mvp_prelude_m1_eval_oracle import (  # noqa: E402
    Env,
    EvalError,
    ReaderError,
    eval_expr,
    load_prelude,
)


DEFAULT_GLOB = ROOT / "tests" / "bytecode" / "equivalence" / "*.json"
FORMAT = "lisp65-eval-bytecode-equivalence-v1"


class EquivalenceError(Exception):
    pass


def _default_paths() -> list[Path]:
    return [Path(path) for path in sorted(glob.glob(str(DEFAULT_GLOB)))]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_eval_text(value: Any) -> str:
    if value == NIL:
        return "nil"
    if isinstance(value, Symbol):
        return value.name.lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, String):
        return '"' + value.value + '"'
    if isinstance(value, list):
        if not value:
            return "nil"
        return "(" + " ".join(_canonical_eval_text(item) for item in value) + ")"
    if isinstance(value, DottedList):
        head = " ".join(_canonical_eval_text(item) for item in value.items)
        return "(" + head + " . " + _canonical_eval_text(value.tail) + ")"
    raise EquivalenceError("cannot render eval value: %r" % (value,))


def _load_eval_sources(sources: list[str]) -> None:
    if not sources:
        raise EquivalenceError("suite has no sources")
    for i, source in enumerate(sources):
        try:
            load_prelude(ROOT / source, reset=(i == 0))
        except (EvalError, ReaderError) as exc:
            raise EquivalenceError("eval source load failed for %s: %s" % (source, exc))


def _eval_case(expr: str, env: Env) -> str:
    try:
        value = eval_expr(read_single(expr), env)
    except Exception as exc:
        raise EquivalenceError("eval failed: %s" % exc)
    return _canonical_eval_text(value)


def _bytecode_results(path: Path, suite: dict[str, Any]) -> tuple[dict[str, str], int]:
    p0_suite = {
        "format": "lisp65-bytecode-p0-stdlib-subset-v1",
        "sources": list(suite.get("sources", [])),
        "functions": list(suite.get("functions", [])),
        "cases": [{"name": case["name"], "expr": case["expr"]} for case in suite.get("cases", [])],
    }
    try:
        (
            heap,
            _names,
            _code_by_name,
            entry_flags_by_name,
            resident_entry_flags,
            _bundle,
            directory,
            cases,
            entry_names,
            _inliner,
        ) = S._compile_suite(p0_suite)
    except Exception as exc:
        raise EquivalenceError("bytecode compile failed for %s: %s" % (path, exc))
    macro_symbols = S._macro_symbol_objs(heap, entry_flags_by_name, resident_entry_flags)
    results: dict[str, str] = {}
    total_steps = 0
    for case, entry in zip(cases, entry_names):
        entry_obj = heap.intern(entry)
        if entry_obj not in directory:
            raise EquivalenceError("%s: missing bytecode entry %s" % (case["name"], entry))
        try:
            vm = B.P0VM(heap=heap, directory=directory, macro_symbols=macro_symbols)
            result = vm.run(directory[entry_obj], [])
        except Exception as exc:
            raise EquivalenceError("%s: bytecode VM failed: %s" % (case["name"], exc))
        total_steps += vm.steps
        results[case["name"]] = heap.obj_to_text(result)
    return results, total_steps


def _check_suite(path: Path, suite: dict[str, Any], verbose: bool = False) -> tuple[int, int]:
    if suite.get("format") != FORMAT:
        raise EquivalenceError("%s: bad format %r" % (path, suite.get("format")))
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EquivalenceError("%s: cases must be a non-empty list" % path)
    _load_eval_sources(list(suite.get("sources", [])))
    env = Env()
    bytecode, steps = _bytecode_results(path, suite)

    passed = 0
    for case in cases:
        name = case.get("name")
        expr = case.get("expr")
        if not isinstance(name, str) or not name:
            raise EquivalenceError("%s: case missing name" % path)
        if not isinstance(expr, str) or not expr:
            raise EquivalenceError("%s/%s: case missing expr" % (path, name))
        eval_text = _eval_case(expr, env)
        bytecode_text = bytecode.get(name)
        if eval_text != bytecode_text:
            raise EquivalenceError(
                "%s/%s: eval %r != bytecode %r" % (path, name, eval_text, bytecode_text)
            )
        expect = case.get("expect")
        if expect is not None and eval_text != expect:
            raise EquivalenceError(
                "%s/%s: got %r, expected %r" % (path, name, eval_text, expect)
            )
        passed += 1
        if verbose:
            print("PASS %-28s result=%s" % (name, eval_text))
    return passed, steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, help="equivalence suite JSON files")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    paths = args.paths or _default_paths()
    if not paths:
        print("eval-bytecode-equivalence-check: no suites found", file=sys.stderr)
        return 1
    suites = 0
    cases = 0
    steps = 0
    try:
        for path in paths:
            passed, suite_steps = _check_suite(path, _read_json(path), verbose=args.verbose)
            suites += 1
            cases += passed
            steps += suite_steps
    except Exception as exc:
        print("eval-bytecode-equivalence-check: FAIL: %s" % exc, file=sys.stderr)
        return 1
    print(
        "eval-bytecode-equivalence-check: PASS suites=%d cases=%d bytecode_steps=%d"
        % (suites, cases, steps)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
