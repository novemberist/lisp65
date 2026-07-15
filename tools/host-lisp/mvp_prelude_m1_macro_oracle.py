#!/usr/bin/env python3
"""Macroexpansion oracle for the concrete M1 bootstrap Prelude.

This intentionally differs from mvp_prelude_macro_oracle.py: that file pins the
future target surface, while this one pins what lib/prelude-m1.lisp can express on
the current kernel.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from mvp_cl_reader_oracle import NIL, Symbol, print_value, read_single


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "lib" / "tests" / "prelude-m1-macro-cases.json"


class MacroError(Exception):
    pass


def sym(name: str) -> Symbol:
    return Symbol(name.upper())


def gensym(prefix: str, counters: dict[str, int]) -> Symbol:
    key = prefix.upper()
    count = counters.get(key, 0)
    counters[key] = count + 1
    return sym(f"#:{key}{count}")


def is_sym(value: Any, name: str) -> bool:
    return isinstance(value, Symbol) and value.name == name.upper()


def as_list(value: Any, context: str) -> list[Any]:
    if value == NIL:
        return []
    if isinstance(value, list):
        return value
    raise MacroError(f"{context}: expected proper list, got {print_value(value)}")


def quote(value: Any) -> Any:
    return [sym("quote"), value]


def expand_defun(args: list[Any]) -> Any:
    if len(args) < 2:
        raise MacroError("defun needs name and params")
    name, params, *body = args
    return [sym("set-symbol-function"), quote(name), [sym("lambda"), params, *body]]


def expand_defparameter(args: list[Any]) -> Any:
    if len(args) < 2:
        raise MacroError("defparameter needs name and init form")
    name, init, *_ = args
    return [sym("progn"), [sym("setq"), name, init], quote(name)]


def expand_defvar(args: list[Any]) -> Any:
    if not args:
        raise MacroError("defvar needs name")
    name = args[0]
    init = args[1] if len(args) > 1 else NIL
    init_form = [sym("setq"), name, init] if len(args) > 1 else NIL
    return [sym("progn"), [sym("if"), [sym("boundp"), quote(name)], NIL, init_form], quote(name)]


def expand_when(args: list[Any]) -> Any:
    if not args:
        raise MacroError("when needs a test")
    test, *body = args
    return [sym("if"), test, [sym("progn"), *body], NIL]


def expand_unless(args: list[Any]) -> Any:
    if not args:
        raise MacroError("unless needs a test")
    test, *body = args
    return [sym("if"), test, NIL, [sym("progn"), *body]]


def expand_and(args: list[Any]) -> Any:
    if not args:
        return sym("t")
    if len(args) == 1:
        return args[0]
    return [sym("if"), args[0], [sym("and"), *args[1:]], NIL]


def expand_or(args: list[Any], counters: dict[str, int]) -> Any:
    if not args:
        return NIL
    if len(args) == 1:
        return args[0]
    tmp = gensym("or", counters)
    return [[sym("lambda"), [tmp], [sym("if"), tmp, tmp, [sym("or"), *args[1:]]]], args[0]]


def expand_cond(args: list[Any]) -> Any:
    if not args:
        return NIL
    clause = as_list(args[0], "cond clause")
    if not clause:
        raise MacroError("cond clause cannot be empty")
    test, *body = clause
    if body:
        then_form = [sym("progn"), *body]
    else:
        then_form = [sym("or"), test, [sym("cond"), *args[1:]]]
    return [sym("if"), test, then_form, [sym("cond"), *args[1:]]]


def let_vars(bindings: list[Any]) -> list[Any]:
    return [as_list(binding, "let binding")[0] for binding in bindings]


def let_vals(bindings: list[Any]) -> list[Any]:
    vals: list[Any] = []
    for binding in bindings:
        pair = as_list(binding, "let binding")
        vals.append(pair[1] if len(pair) > 1 else NIL)
    return vals


def expand_let(args: list[Any]) -> Any:
    if len(args) < 1:
        raise MacroError("let needs bindings")
    bindings = as_list(args[0], "let bindings")
    body = args[1:]
    return [[sym("lambda"), let_vars(bindings), *body], *let_vals(bindings)]


def expand_let_star(args: list[Any]) -> Any:
    if len(args) < 1:
        raise MacroError("let* needs bindings")
    bindings = as_list(args[0], "let* bindings")
    body = args[1:]
    if not bindings:
        return [sym("let"), [], *body]
    return [sym("let"), [bindings[0]], [sym("let*"), bindings[1:], *body]]


def case_key_test(tmp: Symbol, key_spec: Any) -> Any:
    if isinstance(key_spec, list):
        tests = [[sym("eql"), tmp, quote(key)] for key in key_spec]
        return [sym("or"), *tests]
    return [sym("eql"), tmp, quote(key_spec)]


def expand_case(args: list[Any], counters: dict[str, int]) -> Any:
    if len(args) < 2:
        raise MacroError("case needs keyform and clauses")
    keyform, *clauses = args
    tmp = gensym("case", counters)
    cond_clauses: list[Any] = []
    for raw_clause in clauses:
        clause = as_list(raw_clause, "case clause")
        if len(clause) < 2:
            raise MacroError("case clause needs key(s) and body")
        key_spec, *body = clause
        if is_sym(key_spec, "otherwise") or is_sym(key_spec, "t"):
            test = sym("t")
        else:
            test = case_key_test(tmp, key_spec)
        cond_clauses.append([test, *body])
    return [sym("let"), [[tmp, keyform]], [sym("cond"), *cond_clauses]]


EXPANDERS = {
    "DEFUN": expand_defun,
    "DEFPARAMETER": expand_defparameter,
    "DEFVAR": expand_defvar,
    "WHEN": expand_when,
    "UNLESS": expand_unless,
    "AND": expand_and,
    "COND": expand_cond,
    "LET": expand_let,
    "LET*": expand_let_star,
}


def expand(form: Any) -> Any:
    counters: dict[str, int] = {}
    items = as_list(form, "macro form")
    if not items:
        raise MacroError("empty macro form")
    op = items[0]
    if not isinstance(op, Symbol):
        raise MacroError(f"no M1 expander for {print_value(op)}")
    if op.name == "OR":
        return expand_or(items[1:], counters)
    if op.name == "CASE":
        return expand_case(items[1:], counters)
    if op.name not in EXPANDERS:
        raise MacroError(f"no M1 expander for {print_value(op)}")
    return EXPANDERS[op.name](items[1:])


def check_case(case: dict[str, Any]) -> tuple[bool, str]:
    name = case["name"]
    got = print_value(expand(read_single(case["input"])))
    expect = print_value(read_single(case["expect"]))
    if got != expect:
        return False, f"{name}: got {got!r}, expected {expect!r}"
    return True, f"{name}: {got}"


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CASES
    data = json.loads(path.read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in data["cases"]:
        try:
            ok, message = check_case(case)
        except Exception as exc:
            ok, message = False, f"{case.get('name', '<unnamed>')}: {exc}"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"mvp-prelude-m1-macro-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
