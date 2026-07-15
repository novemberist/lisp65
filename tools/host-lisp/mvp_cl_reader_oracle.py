#!/usr/bin/env python3
"""Host oracle for the CL-near lisp65 MVP reader fixtures.

This intentionally does not reuse tools/host-lisp/lisp64.py: that interpreter
models the old LISP-64 reader where, for example, (* ...) is a comment form.
The code here pins the new reader contract that the C kernel should implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

from reader_fixture import FixtureError, load_fixture


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "lib" / "tests" / "mvp-reader-cases.json"


class ReaderError(Exception):
    pass


@dataclass(frozen=True)
class Symbol:
    name: str


@dataclass(frozen=True)
class String:
    value: str


@dataclass(frozen=True)
class DottedList:
    items: tuple[Any, ...]
    tail: Any


NIL = Symbol("NIL")
INT_RE = re.compile(r"^[+-]?[0-9]+$")


class Reader:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def eof(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return "" if self.eof() else self.text[self.pos]

    def take(self) -> str:
        ch = self.peek()
        if ch:
            self.pos += 1
        return ch

    def skip_space_and_comments(self) -> None:
        while not self.eof():
            ch = self.peek()
            if ch.isspace():
                self.pos += 1
                continue
            if ch == ";":
                while not self.eof() and self.peek() != "\n":
                    self.pos += 1
                continue
            return

    def read_one(self) -> Any:
        self.skip_space_and_comments()
        if self.eof():
            raise ReaderError("unexpected end of input")
        ch = self.take()
        if ch == "(":
            return self.read_list()
        if ch == ")":
            raise ReaderError("unexpected )")
        if ch == "'":
            return [Symbol("QUOTE"), self.read_one()]
        if ch == "`":
            return [Symbol("QUASIQUOTE"), self.read_one()]
        if ch == ",":
            if self.peek() == "@":
                self.pos += 1
                return [Symbol("UNQUOTE-SPLICING"), self.read_one()]
            return [Symbol("UNQUOTE"), self.read_one()]
        if ch == '"':
            return self.read_string()
        return self.read_atom(ch)

    def read_list(self) -> Any:
        items: list[Any] = []
        while True:
            self.skip_space_and_comments()
            if self.eof():
                raise ReaderError("unclosed list")
            if self.peek() == ")":
                self.pos += 1
                return NIL if not items else items
            if self.peek() == ".":
                self.pos += 1
                if not items:
                    raise ReaderError("dot without list head")
                tail = self.read_one()
                self.skip_space_and_comments()
                if self.peek() != ")":
                    raise ReaderError("expected ) after dotted tail")
                self.pos += 1
                return DottedList(tuple(items), tail)
            items.append(self.read_one())

    def read_string(self) -> String:
        out: list[str] = []
        while not self.eof():
            ch = self.take()
            if ch == '"':
                return String("".join(out))
            if ch == "\\":
                if self.eof():
                    raise ReaderError("unfinished string escape")
                out.append(self.take())
            else:
                out.append(ch)
        raise ReaderError("unclosed string")

    def read_atom(self, first: str) -> Any:
        chars = [first]
        while not self.eof():
            ch = self.peek()
            if ch.isspace() or ch in "();'\"`,":
                break
            chars.append(self.take())
        token = "".join(chars)
        if len(token) > 32:
            raise ReaderError("token too long")
        if token == ".":
            raise ReaderError("dot outside list")
        if INT_RE.match(token):
            value = int(token)
            if value < -16384 or value > 16383:
                raise ReaderError("fixnum out of range")
            return value
        name = token.upper()
        if name == "NIL":
            return NIL
        return Symbol(name)


def read_single(text: str) -> Any:
    reader = Reader(text)
    value = reader.read_one()
    reader.skip_space_and_comments()
    if not reader.eof():
        raise ReaderError(f"trailing input at byte {reader.pos}")
    return value


def print_value(value: Any) -> str:
    if value == NIL:
        return "NIL"
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, int):
        return str(value)
    if isinstance(value, String):
        escaped = value.value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        if not value:
            return "NIL"
        return "(" + " ".join(print_value(item) for item in value) + ")"
    if isinstance(value, DottedList):
        head = " ".join(print_value(item) for item in value.items)
        return f"({head} . {print_value(value.tail)})"
    raise TypeError(f"cannot print {value!r}")


def check_case(case: dict[str, Any]) -> tuple[bool, str]:
    name = case["name"]
    wants_error = bool(case.get("error"))
    try:
        got = print_value(read_single(case["input"]))
    except ReaderError as exc:
        if wants_error:
            return True, f"{name}: expected error ({exc})"
        return False, f"{name}: unexpected error: {exc}"
    if wants_error:
        return False, f"{name}: expected reader error, got {got}"
    expect = case["expect"]
    if got != expect:
        return False, f"{name}: got {got!r}, expected {expect!r}"
    return True, f"{name}: {got}"


def main(argv: list[str]) -> int:
    fixture = Path(argv[1]) if len(argv) > 1 else DEFAULT_FIXTURE
    try:
        cases = load_fixture(fixture)
    except FixtureError as exc:
        print(f"mvp-cl-reader-oracle: FIXTURE ERROR: {exc}", file=sys.stderr)
        return 2
    passed = 0
    failed = 0
    for case in cases:
        ok, message = check_case(case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"mvp-cl-reader-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
