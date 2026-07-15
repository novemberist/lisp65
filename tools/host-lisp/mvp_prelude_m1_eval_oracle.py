#!/usr/bin/env python3
"""Evaluation oracle for the concrete M1 bootstrap Prelude functions.

This is intentionally narrower than a full interpreter. Macro expansion shape is
covered by mvp_prelude_m1_macro_oracle.py; this oracle loads the concrete
top-level defun forms from lib/prelude-m1.lisp and evaluates small functional
fixtures against a Lisp-2 function namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Callable

from mvp_cl_reader_oracle import DottedList, NIL, Reader, ReaderError, String, Symbol, print_value, read_single


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRELUDE = ROOT / "lib" / "prelude-m1.lisp"
DEFAULT_CASES = ROOT / "lib" / "tests" / "prelude-m1-eval-cases.json"
T = Symbol("T")


class EvalError(Exception):
    pass


@dataclass
class Closure:
    params: Any
    body: list[Any]
    env: "Env"


@dataclass
class Primitive:
    name: str
    fn: Callable[[list[Any]], Any]


@dataclass
class Macro:
    params: Any
    body: list[Any]
    env: "Env"


class Env:
    def __init__(self, parent: "Env | None" = None):
        self.parent = parent
        self.values: dict[str, Any] = {}

    def get(self, sym: Symbol) -> Any:
        key = sym.name
        if key in self.values:
            return self.values[key]
        if self.parent is not None:
            return self.parent.get(sym)
        if key == "T":
            return T
        return NIL

    def set(self, sym: Symbol, value: Any) -> None:
        key = sym.name
        env: Env | None = self
        while env is not None:
            if key in env.values:
                env.values[key] = value
                return
            env = env.parent
        self.values[key] = value

    def boundp(self, sym: Symbol) -> bool:
        key = sym.name
        env: Env | None = self
        while env is not None:
            if key in env.values:
                return True
            env = env.parent
        return key == "T"


FUNCTIONS: dict[str, Primitive | Closure | Macro] = {}
GENSYM_COUNTER = 0


def is_sym(value: Any, name: str) -> bool:
    return isinstance(value, Symbol) and value.name == name.upper()


def sym_name(value: Any) -> str:
    if not isinstance(value, Symbol):
        raise EvalError(f"expected symbol, got {print_value(value)}")
    return value.name


def truthy(value: Any) -> bool:
    return value != NIL


def lisp_list(items: list[Any]) -> Any:
    return NIL if not items else items


def as_list(value: Any, context: str) -> list[Any]:
    if value == NIL:
        return []
    if isinstance(value, list):
        return value
    raise EvalError(f"{context}: expected proper list, got {print_value(value)}")


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
        return NIL if len(value) <= 1 else value[1:]
    if isinstance(value, DottedList):
        return value.tail if len(value.items) == 1 else DottedList(value.items[1:], value.tail)
    return NIL


def lisp_eq(left: Any, right: Any) -> bool:
    if left == NIL and right == NIL:
        return True
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    return left is right


def cmp_chain(args: list[Any], op: str) -> Any:
    for left, right in zip(args, args[1:]):
        if op == "<":
            ok = int(left) < int(right)
        elif op == ">":
            ok = int(left) > int(right)
        elif op == "=":
            ok = int(left) == int(right)
        elif op == "<=":
            ok = int(left) <= int(right)
        elif op == ">=":
            ok = int(left) >= int(right)
        else:
            raise EvalError(f"unknown comparator {op}")
        if not ok:
            return NIL
    return T


def bind_params(params: Any, args: list[Any], parent: Env) -> Env:
    env = Env(parent)
    if isinstance(params, Symbol):
        env.values[params.name] = lisp_list(args)
        return env
    items = as_list(params, "lambda params")
    i = 0
    arg_i = 0
    while i < len(items):
        item = items[i]
        if is_sym(item, "&rest"):
            if i + 1 >= len(items):
                raise EvalError("&rest without parameter")
            env.values[sym_name(items[i + 1])] = lisp_list(args[arg_i:])
            return env
        env.values[sym_name(item)] = args[arg_i] if arg_i < len(args) else NIL
        i += 1
        arg_i += 1
    return env


def apply_callable(fn: Any, args: list[Any]) -> Any:
    if isinstance(fn, Primitive):
        return fn.fn(args)
    if isinstance(fn, Closure):
        env = bind_params(fn.params, args, fn.env)
        result: Any = NIL
        for form in fn.body:
            result = eval_expr(form, env)
        return result
    raise EvalError(f"not callable: {fn!r}")


def apply_macro(fn: Macro, args: list[Any], env: Env) -> Any:
    menv = bind_params(fn.params, args, fn.env)
    result: Any = NIL
    for form in fn.body:
        result = eval_expr(form, menv)
    return eval_expr(result, env)


def lookup_function(value: Any) -> Primitive | Closure | Macro:
    name = sym_name(value)
    if name not in FUNCTIONS:
        raise EvalError(f"undefined function {name}")
    return FUNCTIONS[name]


def eval_quasiquote(expr: Any, env: Env) -> Any:
    if isinstance(expr, list) and expr:
        if is_sym(expr[0], "unquote"):
            return eval_expr(expr[1], env) if len(expr) > 1 else NIL
        out: list[Any] = []
        for item in expr:
            if isinstance(item, list) and item and is_sym(item[0], "unquote-splicing"):
                spliced = eval_expr(item[1], env) if len(item) > 1 else NIL
                out.extend(as_list(spliced, "unquote-splicing value"))
            else:
                out.append(eval_quasiquote(item, env))
        return lisp_list(out)
    return expr


def eval_dotimes(args: list[Any], env: Env) -> Any:
    if not args:
        raise EvalError("dotimes needs a binding spec")
    spec = as_list(args[0], "dotimes spec")
    if len(spec) < 2 or len(spec) > 3 or not isinstance(spec[0], Symbol):
        raise EvalError("bad dotimes spec")
    var = spec[0]
    count = eval_expr(spec[1], env)
    loop_env = Env(env)
    n = int(count)
    i = 0
    while i < n:
        loop_env.values[var.name] = i
        for form in args[1:]:
            eval_expr(form, loop_env)
        i += 1
    loop_env.values[var.name] = n
    return eval_expr(spec[2], loop_env) if len(spec) == 3 else NIL


def eval_dolist(args: list[Any], env: Env) -> Any:
    if not args:
        raise EvalError("dolist needs a binding spec")
    spec = as_list(args[0], "dolist spec")
    if len(spec) < 2 or len(spec) > 3 or not isinstance(spec[0], Symbol):
        raise EvalError("bad dolist spec")
    var = spec[0]
    loop_env = Env(env)
    rest = eval_expr(spec[1], env)
    while isinstance(rest, list) and rest:
        loop_env.values[var.name] = rest[0]
        for form in args[1:]:
            eval_expr(form, loop_env)
        rest = NIL if len(rest) == 1 else rest[1:]
    loop_env.values[var.name] = NIL
    return eval_expr(spec[2], loop_env) if len(spec) == 3 else NIL


def eval_expr(expr: Any, env: Env) -> Any:
    if expr == NIL or isinstance(expr, (int, String)):
        return expr
    if isinstance(expr, Symbol):
        return env.get(expr)
    if isinstance(expr, DottedList):
        raise EvalError(f"cannot evaluate dotted form {print_value(expr)}")
    if not isinstance(expr, list) or not expr:
        return NIL

    op = expr[0]
    args = expr[1:]
    if is_sym(op, "quote"):
        return args[0] if args else NIL
    if is_sym(op, "quasiquote"):
        return eval_quasiquote(args[0], env) if args else NIL
    if is_sym(op, "if"):
        test = eval_expr(args[0], env) if args else NIL
        branch = args[1] if truthy(test) else (args[2] if len(args) > 2 else NIL)
        return eval_expr(branch, env)
    if is_sym(op, "progn"):
        result: Any = NIL
        for form in args:
            result = eval_expr(form, env)
        return result
    if is_sym(op, "and"):
        result: Any = T
        for form in args:
            result = eval_expr(form, env)
            if not truthy(result):
                return NIL
        return result
    if is_sym(op, "or"):
        for form in args:
            result = eval_expr(form, env)
            if truthy(result):
                return result
        return NIL
    if is_sym(op, "lambda"):
        return Closure(args[0] if args else NIL, args[1:], env)
    if is_sym(op, "function"):
        return lookup_function(args[0])
    if is_sym(op, "setq"):
        value = eval_expr(args[1], env)
        env.set(args[0], value)
        return value
    if is_sym(op, "boundp"):
        sym = eval_expr(args[0], env) if args else NIL
        return T if isinstance(sym, Symbol) and env.boundp(sym) else NIL
    if is_sym(op, "dotimes"):
        return eval_dotimes(args, env)
    if is_sym(op, "dolist"):
        return eval_dolist(args, env)

    fn = lookup_function(op) if isinstance(op, Symbol) else eval_expr(op, env)
    if isinstance(fn, Macro):
        return apply_macro(fn, args, env)
    return apply_callable(fn, [eval_expr(arg, env) for arg in args])


GLOBAL_VALUES: dict = {}


def install_primitives() -> None:
    global GENSYM_COUNTER
    GENSYM_COUNTER = 0
    FUNCTIONS.clear()
    GLOBAL_VALUES.clear()

    # Global value cells (device CALLPRIMs 19/20 plus boundp): the IDE globals
    # %ide-hint, %ide-stcache, and *ide-buffers* use only this trio, so dedicated storage is
    # sufficient and never mixes with setq on the same symbols.
    def _sym_name(v):
        if not isinstance(v, Symbol):
            raise EvalError(f"expected symbol, got {print_value(v)}")
        return v.name

    def _set_symbol_value(args):
        GLOBAL_VALUES[_sym_name(args[0])] = args[1]
        return args[1]

    def prim(name: str, fn: Callable[[list[Any]], Any]) -> None:
        FUNCTIONS[name.upper()] = Primitive(name.upper(), fn)

    def gensym(_args: list[Any]) -> Symbol:
        global GENSYM_COUNTER
        GENSYM_COUNTER += 1
        return Symbol(f"#:G{GENSYM_COUNTER}")

    prim("+", lambda args: sum(int(arg) for arg in args))
    prim("*", lambda args: product(args))
    prim("-", sub)
    prim("mod", lambda args: 0 if int(args[1]) == 0 else int(args[0]) % int(args[1]))
    prim("=", lambda args: cmp_chain(args, "="))
    prim("<", lambda args: cmp_chain(args, "<"))
    prim(">", lambda args: cmp_chain(args, ">"))
    prim("<=", lambda args: cmp_chain(args, "<="))
    prim(">=", lambda args: cmp_chain(args, ">="))
    prim("cons", lambda args: lisp_cons(args[0], args[1]))
    prim("car", lambda args: lisp_car(args[0]))
    prim("cdr", lambda args: lisp_cdr(args[0]))
    prim("eq", lambda args: T if lisp_eq(args[0], args[1]) else NIL)
    prim("eql", lambda args: T if lisp_eq(args[0], args[1]) else NIL)
    prim("list", lambda args: lisp_list(args))
    prim("funcall", lambda args: apply_callable(args[0], args[1:]))
    prim("apply", lambda args: apply_callable(args[0], as_list(args[1], "apply args")))
    prim("gensym", gensym)
    prim("numberp", lambda args: T if isinstance(args[0], int) else NIL)
    prim("symbolp", lambda args: T if isinstance(args[0], Symbol) else NIL)
    prim("stringp", lambda args: T if isinstance(args[0], String) else NIL)
    prim("string->list", lambda args: lisp_list([ord(ch) for ch in need_string(args[0]).value]))
    prim("list->string", lambda args: String("".join(chr(need_char_code(code)) for code in as_list(args[0], "list->string args"))))
    prim("string-length", lambda args: len(need_string(args[0]).value))
    prim("string-ref", string_ref)
    prim("write-char", lambda args: need_char_code(args[0]))
    prim("write-string", lambda args: need_string(args[0]))
    prim("terpri", lambda args: NIL)
    prim("prin1", lambda args: args[0])
    prim("princ", lambda args: args[0])
    prim("print", lambda args: args[0])
    prim("write", lambda args: args[0])
    prim("write-line", lambda args: need_string(args[0]))
    prim("symbol-count", lambda args: 231)
    prim("symbol-max", lambda args: 330)
    prim("number->string", lambda args: String(str(int(args[0]))))
    prim("set-symbol-value", _set_symbol_value)
    prim("symbol-value", lambda args: GLOBAL_VALUES.get(_sym_name(args[0]), NIL))
    prim("boundp", lambda args: T if _sym_name(args[0]) in GLOBAL_VALUES else NIL)


def product(args: list[Any]) -> int:
    result = 1
    for arg in args:
        result *= int(arg)
    return result


def sub(args: list[Any]) -> int:
    if not args:
        return 0
    result = int(args[0])
    if len(args) == 1:
        return -result
    for arg in args[1:]:
        result -= int(arg)
    return result


def need_string(value: Any) -> String:
    if not isinstance(value, String):
        raise EvalError(f"expected string, got {print_value(value)}")
    return value


def need_char_code(value: Any) -> int:
    code = int(value)
    if code < 0 or code > 255:
        raise EvalError(f"character code out of range: {code}")
    return code


def string_ref(args: list[Any]) -> int:
    s = need_string(args[0]).value
    i = int(args[1])
    if i < 0 or i >= len(s):
        raise EvalError("string-ref index out of range")
    return ord(s[i])


def read_all(path: Path) -> list[Any]:
    reader = Reader(path.read_text(encoding="utf-8"))
    forms: list[Any] = []
    while True:
        reader.skip_space_and_comments()
        if reader.eof():
            return forms
        forms.append(reader.read_one())


def load_prelude(path: Path, reset: bool = True) -> None:
    if reset:
        install_primitives()
    root = Env()
    for form in read_all(path):
        items = as_list(form, "top-level form")
        if not items:
            continue
        if is_sym(items[0], "defun"):
            if len(items) < 4:
                raise EvalError("defun needs name, params and body")
            FUNCTIONS[sym_name(items[1])] = Closure(items[2], items[3:], root)
        elif is_sym(items[0], "defmacro"):
            if len(items) < 4:
                raise EvalError("defmacro needs name, params and body")
            FUNCTIONS[sym_name(items[1])] = Macro(items[2], items[3:], root)
        else:
            raise EvalError(f"unsupported top-level form {print_value(form)}")


def check_case(case: dict[str, Any], env: Env) -> tuple[bool, str]:
    name = case["name"]
    got = print_value(eval_expr(read_single(case["input"]), env))
    expect = case["expect"]
    if got != expect:
        return False, f"{name}: got {got!r}, expected {expect!r}"
    return True, f"{name}: {got}"


def main(argv: list[str]) -> int:
    prelude = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRELUDE
    cases = Path(argv[2]) if len(argv) > 2 else DEFAULT_CASES
    data = json.loads(cases.read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    try:
        load_prelude(prelude)
    except (EvalError, ReaderError) as exc:
        print(f"FAIL prelude load: {exc}", file=sys.stderr)
        print("mvp-prelude-m1-eval-oracle: PASS=0 FAIL=1")
        return 1

    env = Env()
    for case in data["cases"]:
        try:
            ok, message = check_case(case, env)
        except Exception as exc:
            ok, message = False, f"{case.get('name', '<unnamed>')}: {exc}"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"mvp-prelude-m1-eval-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
