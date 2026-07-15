#!/usr/bin/env python3
"""Report stripped source/form footprint for the current lisp65 stdlib layers."""

from __future__ import annotations

import argparse
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


def strip_comments(text: str) -> str:
    out: list[str] = []
    in_string = False
    in_comment = False
    for ch in text:
        if in_comment:
            if ch == "\n":
                in_comment = False
                out.append(ch)
            continue
        if in_string:
            out.append(ch)
            if ch == '"':
                in_string = False
            continue
        if ch == ";":
            in_comment = True
            continue
        out.append(ch)
        if ch == '"':
            in_string = True
    return "".join(out)


def top_level_forms(text: str) -> list[str]:
    forms: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    for i, ch in enumerate(text):
        if start is None:
            if ch.isspace():
                continue
            start = i
        if in_string:
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced closing parenthesis")
        if start is not None and depth == 0 and not in_string and not ch.isspace():
            if ch == ")" or i + 1 == len(text):
                form = text[start : i + 1].strip()
                if form:
                    forms.append(form)
                start = None
    if start is not None:
        tail = text[start:].strip()
        if tail:
            if depth != 0 or in_string:
                raise ValueError("unterminated top-level form")
            forms.append(tail)
    return forms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="*", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()

    total_forms = 0
    total_bytes = 0
    total_max = 0
    print("stdlib-source-budget")
    print("source forms stripped_bytes max_form_bytes")
    for source in args.sources:
        forms = top_level_forms(strip_comments(source.read_text(encoding="utf-8")))
        sizes = [len((form.strip() + "\n").encode("utf-8")) for form in forms]
        stripped_bytes = sum(sizes)
        max_form = max(sizes, default=0)
        total_forms += len(forms)
        total_bytes += stripped_bytes
        total_max = max(total_max, max_form)
        print(f"{source} {len(forms)} {stripped_bytes} {max_form}")
    print(f"total_forms={total_forms}")
    print(f"total_stripped_bytes={total_bytes}")
    print(f"max_form_bytes={total_max}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
