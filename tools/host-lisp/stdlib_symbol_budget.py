#!/usr/bin/env python3
"""Estimate lisp65 symbol/namepool pressure for a set of Lisp sources."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = [
    ROOT / "lib" / "prelude-m1.lisp",
    ROOT / "lib" / "stdlib-strings.lisp",
    ROOT / "lib" / "stdlib-sequences.lisp",
    ROOT / "lib" / "stdlib-math.lisp",
    ROOT / "lib" / "stdlib-plists.lisp",
    ROOT / "lib" / "stdlib-format.lisp",
    ROOT / "lib" / "stdlib-control.lisp",
]
DEFAULT_EVAL = ROOT / "src" / "eval.c"


def is_number(token: str) -> bool:
    if token in {"+", "-"}:
        return False
    if token.startswith(("+", "-")):
        token = token[1:]
    return bool(token) and token.isdigit()


def native_symbols(eval_c: Path) -> set[str]:
    text = eval_c.read_text(encoding="utf-8")
    names = set(re.findall(r'defprim\("([^"]+)"', text))
    names.add("t")
    return names


def source_symbols(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    symbols: set[str] = set()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace() or ch in "()":
            i += 1
            continue
        if ch == ";":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                i += 1
            if i < len(text):
                i += 1
            continue
        if ch == "'":
            symbols.add("quote")
            i += 1
            continue
        if ch == "`":
            symbols.add("quasiquote")
            i += 1
            continue
        if ch == ",":
            if i + 1 < len(text) and text[i + 1] == "@":
                symbols.add("unquote-splicing")
                i += 2
            else:
                symbols.add("unquote")
                i += 1
            continue

        start = i
        while i < len(text) and not text[i].isspace() and text[i] not in "();":
            if text[i] in "'`,":
                break
            i += 1
        token = text[start:i]
        if not token:
            i += 1
            continue
        if token == "." or token == "nil" or is_number(token):
            continue
        symbols.add(token[:31])
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-c", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--max-sym", type=int, default=384)
    parser.add_argument("--namepool", type=int, default=3072)
    parser.add_argument("sources", nargs="*", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()

    native = native_symbols(args.eval_c)
    source = set().union(*(source_symbols(path) for path in args.sources))
    total = native | source
    namepool_bytes = sum(len(name) + 1 for name in total)

    print("stdlib-symbol-budget")
    print(f"native_symbols={len(native)}")
    print(f"source_symbols={len(source)}")
    print(f"total_symbols={len(total)}")
    print(f"namepool_bytes={namepool_bytes}")
    print(f"max_sym={args.max_sym}")
    print(f"sym_headroom={args.max_sym - len(total)}")
    print(f"namepool={args.namepool}")
    print(f"namepool_headroom={args.namepool - namepool_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
