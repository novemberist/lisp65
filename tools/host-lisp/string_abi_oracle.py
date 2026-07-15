#!/usr/bin/env python3
"""Host oracle for the K-A string primitive ABI."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

from lisp64 import LispError, lisp_eval, lisp_repr, read_all  # noqa: E402


CASES = [
    ('(stringp "abc")', "T"),
    ("(stringp 65)", "NIL"),
    ('(string->list "Az")', "(65 122)"),
    ("(list->string '(65 122))", '"Az"'),
    ('(string-length "abcd")', "4"),
    ('(string-ref "Az" 1)', "122"),
    ('(string->list (list->string \'(40 41)))', "(40 41)"),
]


def eval_one(source: str) -> str:
    forms = read_all(source)
    if len(forms) != 1:
        raise AssertionError(f"expected one form: {source!r}")
    return lisp_repr(lisp_eval(forms[0]))


def main() -> int:
    failures = 0
    for source, expected in CASES:
        try:
            got = eval_one(source)
        except LispError as exc:
            print(f"FAIL {source}: raised {exc}", file=sys.stderr)
            failures += 1
            continue
        if got != expected:
            print(f"FAIL {source}: expected {expected}, got {got}", file=sys.stderr)
            failures += 1
    passed = len(CASES) - failures
    print(f"string-abi-oracle: PASS={passed} FAIL={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
