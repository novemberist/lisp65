#!/usr/bin/env python3
"""Estimate expected function-cell pressure for the current stdlib layers."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import stdlib_source_budget
import stdlib_symbol_budget


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = stdlib_source_budget.DEFAULT_SOURCES
DEFAULT_EVAL = ROOT / "src" / "eval.c"


def form_head(form: str) -> tuple[str, str] | None:
    match = re.match(r"\(\s*(defun|defmacro)\s+([^\s()]+)", form)
    if not match:
        return None
    return match.group(1), match.group(2)


def source_bindings(path: Path) -> list[tuple[str, str]]:
    forms = stdlib_source_budget.top_level_forms(
        stdlib_source_budget.strip_comments(path.read_text(encoding="utf-8"))
    )
    bindings: list[tuple[str, str]] = []
    for form in forms:
        head = form_head(form)
        if head:
            bindings.append(head)
    return bindings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-c", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("sources", nargs="*", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()

    native = stdlib_symbol_budget.native_symbols(args.eval_c)
    source_names: set[str] = set()

    print("stdlib-function-budget")
    print("source defun defmacro total unique")
    for source in args.sources:
        bindings = source_bindings(source)
        defun = sum(1 for kind, _ in bindings if kind == "defun")
        defmacro = sum(1 for kind, _ in bindings if kind == "defmacro")
        names = {name for _, name in bindings}
        source_names |= names
        print(f"{source} {defun} {defmacro} {len(bindings)} {len(names)}")

    expected = native | source_names
    print(f"native_functions={len(native)}")
    print(f"source_function_bindings={len(source_names)}")
    print(f"source_native_overlaps={len(native & source_names)}")
    print(f"expected_function_symbols={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
