#!/usr/bin/env python3
"""Reject newly added German source comments after the v1.1.0 baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BASELINE = "v1.1.0"
SOURCE_ROOTS = ("src", "lib", "scripts", "tools")
GERMAN_CHARS = re.compile(r"[äöüÄÖÜß]")
GERMAN_WORDS = re.compile(
    r"\b(?:aber|auch|beim|bereits|damit|dann|dass|diese|dieser|einen|eine|"
    r"fuer|gegen|hier|immer|kein|keine|muss|nicht|noch|oder|ohne|sonst|"
    r"pruefen|schreiben|abbrechen|sowie|ueber|unter|vom|vor|wenn|wird|zur|zum)\b",
    re.IGNORECASE,
)


class CommentLanguageError(RuntimeError):
    pass


def comment_text(line: str) -> str | None:
    stripped = line.lstrip()
    if stripped.startswith("#!"):
        return None
    if stripped.startswith(";;"):
        return stripped[2:]
    if stripped.startswith("//"):
        return stripped[2:]
    if stripped.startswith("/*"):
        return stripped[2:]
    if stripped.startswith("*") and not stripped.startswith("*/"):
        return stripped[1:]
    if stripped.startswith("#") and not re.match(
        r"#\s*(?:include|define|if|ifdef|ifndef|elif|else|endif|pragma|error)\b",
        stripped,
    ):
        return stripped[1:]
    return None


def looks_german(text: str) -> bool:
    if GERMAN_CHARS.search(text):
        return True
    return len(GERMAN_WORDS.findall(text)) >= 2


def added_lines(diff: str) -> list[tuple[str, str]]:
    path = ""
    found: list[tuple[str, str]] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            found.append((path, line[1:]))
    return found


def git_diff() -> str:
    command = [
        "git", "diff", "--no-ext-diff", "--unified=0", BASELINE, "--",
        *SOURCE_ROOTS,
    ]
    process = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode:
        raise CommentLanguageError(process.stderr.strip() or "git diff failed")
    return process.stdout


def check_diff(diff: str) -> list[str]:
    failures = []
    for path, line in added_lines(diff):
        text = comment_text(line)
        if text is not None and looks_german(text):
            failures.append(f"{path}: {line.strip()}")
    return failures


def selftest() -> None:
    good = """+++ b/src/good.c
+// Keep the transaction bound to one medium.
+++ b/lib/good.lisp
+;; Return NIL when no entry exists.
"""
    bad = """+++ b/src/bad.c
+// Dieser Pfad muss immer vor dem Trigger laufen.
+++ b/lib/bad.lisp
+;; Puffer vor dem Schreiben pruefen und dann abbrechen.
"""
    if check_diff(good):
        raise CommentLanguageError("English self-test comments were rejected")
    failures = check_diff(bad)
    if len(failures) != 2:
        raise CommentLanguageError(f"German mutations accepted: {failures}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("comment-language: SELFTEST PASS mutations=2")
        return 0
    failures = check_diff(git_diff())
    if failures:
        print("comment-language: FAIL newly added German source comments:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"comment-language: PASS baseline={BASELINE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
