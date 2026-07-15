#!/usr/bin/env python3
"""Macroexpansion oracle for the first lisp65 Prelude.

The cases in lib/tests/prelude-macro-cases.json pin expansion shape only. They
do not evaluate the expanded forms. This lets Lane L define the Prelude contract
against the current CL-like Lisp-2 core.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from mvp_cl_reader_oracle import NIL, Symbol, print_value, read_single


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "lib" / "tests" / "prelude-macro-cases.json"
SURFACE = ROOT / "lib" / "prelude-surface.json"


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


def form_body(forms: list[Any]) -> Any:
    if not forms:
        return NIL
    if len(forms) == 1:
        return forms[0]
    return [sym("progn"), *forms]


def quote(value: Any) -> Any:
    return [sym("quote"), value]


def expand_defun(args: list[Any]) -> Any:
    if len(args) < 3:
        raise MacroError("defun needs name, params and body")
    name, params, *body = args
    return [sym("set-symbol-function"), quote(name), [sym("lambda"), params, form_body(body)]]


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
    return [sym("if"), test, form_body(body), NIL]


def expand_unless(args: list[Any]) -> Any:
    if not args:
        raise MacroError("unless needs a test")
    test, *body = args
    return [sym("if"), test, NIL, form_body(body)]


def expand_and(args: list[Any]) -> Any:
    if not args:
        return sym("t")
    if len(args) == 1:
        return args[0]
    return [sym("if"), args[0], expand_and(args[1:]), NIL]


def expand_or(args: list[Any], counters: dict[str, int]) -> Any:
    if not args:
        return NIL
    if len(args) == 1:
        return args[0]
    tmp = gensym("or", counters)
    return [sym("let"), [[tmp, args[0]]], [sym("if"), tmp, tmp, [sym("or"), *args[1:]]]]


def expand_cond(args: list[Any]) -> Any:
    if not args:
        return NIL
    clause = as_list(args[0], "cond clause")
    if not clause:
        raise MacroError("cond clause cannot be empty")
    test, *body = clause
    if not body and len(args) == 1:
        return [sym("or"), test, NIL]
    then_form = [sym("or"), test, NIL] if not body else form_body(body)
    return [sym("if"), test, then_form, expand_cond(args[1:])]


def expand_let(args: list[Any]) -> Any:
    if len(args) < 2:
        raise MacroError("let needs bindings and body")
    bindings = as_list(args[0], "let bindings")
    names: list[Any] = []
    values: list[Any] = []
    for binding in bindings:
        pair = as_list(binding, "let binding")
        if len(pair) == 1:
            names.append(pair[0])
            values.append(NIL)
        elif len(pair) == 2:
            names.append(pair[0])
            values.append(pair[1])
        else:
            raise MacroError("let binding has too many elements")
    return [[sym("lambda"), names, form_body(args[1:])], *values]


def expand_let_star(args: list[Any]) -> Any:
    if len(args) < 2:
        raise MacroError("let* needs bindings and body")
    bindings = as_list(args[0], "let* bindings")
    body = args[1:]
    if not bindings:
        return [sym("let"), [], *body]
    first = bindings[0]
    rest = bindings[1:]
    return [sym("let"), [first], [sym("let*"), rest, *body]]


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
        cond_clauses.append([test, form_body(body)])
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
    if is_sym(op, "function"):
        return form
    if not isinstance(op, Symbol):
        raise MacroError(f"no expander for {print_value(op)}")
    if op.name == "OR":
        return expand_or(items[1:], counters)
    if op.name == "CASE":
        return expand_case(items[1:], counters)
    if op.name not in EXPANDERS:
        raise MacroError(f"no expander for {print_value(op)}")
    return EXPANDERS[op.name](items[1:])


def surface_macros() -> set[str]:
    data = json.loads(SURFACE.read_text(encoding="utf-8"))
    macros: set[str] = set()
    for stage in data["library"]:
        if stage.get("kind") == "macro":
            macros.update(name.upper() for name in stage["symbols"])
    return macros


def check_case(case: dict[str, Any], macros: set[str]) -> tuple[bool, str]:
    name = case["name"]
    macro = case["macro"].upper()
    if macro != "FUNCTION" and macro not in macros:
        return False, f"{name}: macro {macro} is not declared in prelude-surface.json"
    got = print_value(expand(read_single(case["input"])))
    expect = print_value(read_single(case["expect"]))
    if got != expect:
        return False, f"{name}: got {got!r}, expected {expect!r}"
    return True, f"{name}: {got}"


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CASES
    data = json.loads(path.read_text(encoding="utf-8"))
    macros = surface_macros()
    passed = 0
    failed = 0
    for case in data["cases"]:
        try:
            ok, message = check_case(case, macros)
        except Exception as exc:  # keep case-level diagnostics concise
            ok, message = False, f"{case.get('name', '<unnamed>')}: {exc}"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"mvp-prelude-macro-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
