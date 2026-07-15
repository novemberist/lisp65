#!/usr/bin/env python3
"""Static oracle for lib/prelude-m1.lisp.

The M1 Prelude is a bridge, not the final Prelude. It must stay within the
current M1.3 kernel: no reader comments, no &body/&optional/&key lambda lists.
`&rest` is allowed for macros and functions now that K supports rest parameters.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from mvp_cl_reader_oracle import NIL, Reader, ReaderError, Symbol, print_value


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRELUDE = ROOT / "lib" / "prelude-m1.lisp"

CORE_OPERATORS = {
    "quote",
    "quasiquote",
    "unquote",
    "unquote-splicing",
    "if",
    "lambda",
    "setq",
    "progn",
    "defmacro",
    "function",
    "+",
    "-",
    "*",
    "mod",
    "=",
    "<",
    ">",
    "<=",
    ">=",
    "cons",
    "car",
    "cdr",
    "eq",
    "eql",
    "funcall",
    "apply",
    "set-symbol-function",
    "gensym",
    "boundp",
    "stringp",
    "string->list",
    "list->string",
    "string-length",
    "string-ref",
}

EXPECTED_TOPLEVEL = [
    ("defmacro", "defun"),
    ("defmacro", "defparameter"),
    ("defmacro", "defvar"),
    ("defmacro", "when"),
    ("defmacro", "unless"),
    ("defmacro", "and"),
    ("defmacro", "or"),
    ("defmacro", "cond"),
    ("defun", "%case-key-tests"),
    ("defun", "%case-key-test"),
    ("defun", "%case-clauses"),
    ("defmacro", "case"),
    ("defun", "not"),
    ("defun", "identity"),
    ("defun", "list"),
    ("defun", "caar"),
    ("defun", "cadr"),
    ("defun", "cdar"),
    ("defun", "cddr"),
    ("defun", "first"),
    ("defun", "rest"),
    ("defun", "second"),
    ("defun", "1+"),
    ("defun", "1-"),
    ("defun", "zerop"),
    ("defun", "plusp"),
    ("defun", "minusp"),
    ("defun", "%distinct-from-all"),
    ("defun", "/="),
    ("defun", "%append2"),
    ("defun", "%append2-rev"),
    ("defun", "append"),
    ("defun", "%append-lists"),
    ("defun", "length"),
    ("defun", "%length-from"),
    ("defun", "nth"),
    ("defun", "nthcdr"),
    ("defun", "%reverse-into"),
    ("defun", "reverse"),
    ("defun", "last"),
    ("defun", "member"),
    ("defun", "assoc"),
    ("defun", "mapcar"),
    ("defun", "%mapc"),
    ("defun", "mapc"),
    ("defun", "remove"),
    ("defun", "%remove-into"),
    ("defun", "find"),
    ("defun", "%position-from"),
    ("defun", "position"),
    ("defun", "%let-vars"),
    ("defun", "%let-vals"),
    ("defmacro", "let"),
    ("defmacro", "let*"),
]

DEFERRED_MACROS: set[str] = set()


def sym_name(value: Any) -> str | None:
    return value.name.lower() if isinstance(value, Symbol) else None


def as_list(value: Any, context: str) -> list[Any]:
    if value == NIL:
        return []
    if isinstance(value, list):
        return value
    raise ValueError(f"{context}: expected proper list, got {print_value(value)}")


def read_all(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if ";" in text:
        raise ValueError("M1 prelude must not use comments until native reader supports them")

    reader = Reader(text)
    forms: list[Any] = []
    while True:
        reader.skip_space_and_comments()
        if reader.eof():
            return forms
        forms.append(reader.read_one())


def reject_unsupported_params(params: Any, context: str) -> None:
    for param in as_list(params, context):
        name = sym_name(param)
        if name in {"&body", "&optional", "&key"}:
            raise ValueError(f"{context}: {name} is not available in M1.3")


def collect_operator_names(form: Any, out: set[str]) -> None:
    if not isinstance(form, list) or not form:
        return
    op = sym_name(form[0])
    if op is not None:
        out.add(op)
    if op == "quote":
        return
    if op == "lambda":
        for item in form[2:]:
            collect_operator_names(item, out)
        return
    if op in {"defmacro", "defun"}:
        for item in form[3:]:
            collect_operator_names(item, out)
        return
    for item in form[1:]:
        collect_operator_names(item, out)


def check_forms(forms: list[Any]) -> list[str]:
    errors: list[str] = []
    if len(forms) != len(EXPECTED_TOPLEVEL):
        errors.append(f"expected {len(EXPECTED_TOPLEVEL)} top-level forms, got {len(forms)}")

    defined: set[str] = set()
    macros: set[str] = set()
    for i, form in enumerate(forms):
        try:
            items = as_list(form, f"top-level form {i + 1}")
            head = sym_name(items[0]) if items else None
            name = sym_name(items[1]) if len(items) > 1 else None
            if i < len(EXPECTED_TOPLEVEL):
                exp_head, exp_name = EXPECTED_TOPLEVEL[i]
                if (head, name) != (exp_head, exp_name):
                    errors.append(
                        f"form {i + 1}: expected ({exp_head} {exp_name} ...), got ({head} {name} ...)"
                    )
            if head not in {"defmacro", "defun"}:
                errors.append(f"form {i + 1}: only defmacro/defun top-level forms allowed")
                continue
            if name in DEFERRED_MACROS:
                errors.append(f"{name}: needs rest/quasiquote/full macro support; keep deferred")
            if len(items) < 4:
                errors.append(f"{name}: missing params/body")
                continue
            reject_unsupported_params(items[2], name or f"form {i + 1}")
            if head == "defmacro":
                macros.add(name or "")
            else:
                defined.add(name or "")
        except (ValueError, IndexError) as exc:
            errors.append(str(exc))

    available_ops = CORE_OPERATORS | defined | macros
    for form in forms:
        used: set[str] = set()
        collect_operator_names(form, used)
        unknown = sorted(op for op in used if op not in available_ops and op not in {name for _, name in EXPECTED_TOPLEVEL})
        for op in unknown:
            errors.append(f"unknown operator in prelude source: {op}")

    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRELUDE
    try:
        forms = read_all(path)
        errors = check_forms(forms)
    except (ReaderError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"mvp-prelude-source-oracle: PASS=0 FAIL={len(errors)}")
        return 1
    print(f"mvp-prelude-source-oracle: PASS={len(forms)} FAIL=0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
