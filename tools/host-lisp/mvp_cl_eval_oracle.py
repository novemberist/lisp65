#!/usr/bin/env python3
"""Host oracle for the lisp65 MVP evaluator fixtures.

This models the Phase-1/M1.2 evaluator contract: self-evaluation, quote, if and
the first primitive set. It is deliberately small; environments, lambda, let and
proper error signalling belong to later milestones.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from mvp_cl_reader_oracle import (
    DEFAULT_FIXTURE as READER_FIXTURE,
    DottedList,
    NIL,
    ReaderError,
    String,
    Symbol,
    print_value,
    read_single,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "lib" / "tests" / "mvp-eval-cases.json"


class EvalError(Exception):
    pass


def is_symbol(value: Any, name: str) -> bool:
    return isinstance(value, Symbol) and value.name == name.upper()


def is_nil(value: Any) -> bool:
    return value == NIL


def as_args(value: Any) -> list[Any]:
    if value == NIL:
        return []
    if isinstance(value, list):
        return value
    raise EvalError(f"expected proper argument list, got {print_value(value)}")


def lisp_cons(head: Any, tail: Any) -> Any:
    if tail == NIL:
        return [head]
    if isinstance(tail, list):
        return [head, *tail]
    if isinstance(tail, DottedList):
        return DottedList((head, *tail.items), tail.tail)
    return DottedList((head,), tail)


def lisp_car(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    if isinstance(value, DottedList) and value.items:
        return value.items[0]
    return NIL


def lisp_cdr(value: Any) -> Any:
    if isinstance(value, list):
        if len(value) <= 1:
            return NIL
        return value[1:]
    if isinstance(value, DottedList):
        if len(value.items) == 1:
            return value.tail
        return DottedList(value.items[1:], value.tail)
    return NIL


def lisp_eq(left: Any, right: Any) -> bool:
    if left == NIL and right == NIL:
        return True
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    return left is right


def eval_form(expr: Any) -> Any:
    if expr == NIL or isinstance(expr, (int, String, Symbol)):
        return expr
    if isinstance(expr, DottedList):
        raise EvalError(f"cannot evaluate dotted form {print_value(expr)}")
    if not isinstance(expr, list) or not expr:
        return NIL

    op = expr[0]
    args = expr[1:]
    if is_symbol(op, "quote"):
        return args[0] if args else NIL
    if is_symbol(op, "if"):
        test = eval_form(args[0]) if args else NIL
        branch = args[1] if not is_nil(test) else (args[2] if len(args) > 2 else NIL)
        return eval_form(branch)
    return apply_prim(op, args)


def apply_prim(op: Any, args: list[Any]) -> Any:
    if is_symbol(op, "+"):
        return sum(int(eval_form(arg)) for arg in args)
    if is_symbol(op, "*"):
        result = 1
        for arg in args:
            result *= int(eval_form(arg))
        return result
    if is_symbol(op, "-"):
        if not args:
            return 0
        result = int(eval_form(args[0]))
        if len(args) == 1:
            return -result
        for arg in args[1:]:
            result -= int(eval_form(arg))
        return result
    if is_symbol(op, "cons"):
        return lisp_cons(eval_form(args[0]), eval_form(args[1]))
    if is_symbol(op, "car"):
        return lisp_car(eval_form(args[0]))
    if is_symbol(op, "cdr"):
        return lisp_cdr(eval_form(args[0]))
    if is_symbol(op, "eq"):
        return Symbol("T") if lisp_eq(eval_form(args[0]), eval_form(args[1])) else NIL
    return NIL


def check_case(case: dict[str, Any]) -> tuple[bool, str]:
    name = case["name"]
    try:
        got = print_value(eval_form(read_single(case["input"])))
    except (EvalError, ReaderError, IndexError, TypeError, ValueError) as exc:
        return False, f"{name}: unexpected error: {exc}"
    expect = case["expect"]
    if got != expect:
        return False, f"{name}: got {got!r}, expected {expect!r}"
    return True, f"{name}: {got}"


def main(argv: list[str]) -> int:
    fixture = Path(argv[1]) if len(argv) > 1 else DEFAULT_FIXTURE
    # Keep the import visible to linters and to humans reading command output paths.
    _ = READER_FIXTURE
    data = json.loads(fixture.read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in data["cases"]:
        ok, message = check_case(case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"mvp-cl-eval-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
