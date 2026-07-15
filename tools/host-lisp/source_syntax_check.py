#!/usr/bin/env python3
"""Check the syntax of all versioned or untracked Python and shell sources."""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence


EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_INFRASTRUCTURE = 2


class InfrastructureError(RuntimeError):
    """Raised when the source check itself cannot be performed."""


def git_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InfrastructureError(f"cannot run git: {exc}") from exc

    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip()
        if not detail:
            detail = "current directory is not inside a Git work tree"
        raise InfrastructureError(detail)

    root_text = os.fsdecode(result.stdout).strip()
    if not root_text:
        raise InfrastructureError("git returned an empty work-tree path")
    return Path(root_text)


def tracked_sources(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
                "*.sh",
            ],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InfrastructureError(f"cannot run git: {exc}") from exc

    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip() or "git ls-files failed"
        raise InfrastructureError(detail)

    entries = result.stdout.split(b"\0")
    return [Path(os.fsdecode(entry)) for entry in entries if entry]


def check_python(path: Path, display_name: str) -> str | None:
    try:
        source = path.read_bytes()
    except OSError as exc:
        return f"cannot read file: {exc}"

    try:
        compile(
            source,
            display_name,
            "exec",
            flags=ast.PyCF_ONLY_AST,
            dont_inherit=True,
        )
    except (SyntaxError, ValueError) as exc:
        if isinstance(exc, SyntaxError) and exc.lineno is not None:
            location = f"line {exc.lineno}"
            if exc.offset is not None:
                location += f", column {exc.offset}"
            return f"{location}: {exc.msg}"
        return str(exc)
    return None


def check_shell(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["sh", "-n", str(path.resolve())],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise InfrastructureError(f"cannot run sh: {exc}") from exc

    if result.returncode == 0:
        return None
    detail = os.fsdecode(result.stderr).strip()
    return detail or f"sh -n exited with status {result.returncode}"


def run_check(root: Path, sources: Sequence[Path]) -> int:
    failures: list[tuple[str, Path, str]] = []
    python_count = 0
    shell_count = 0

    for relative_path in sources:
        absolute_path = root / relative_path
        if relative_path.suffix == ".py":
            python_count += 1
            error = check_python(absolute_path, os.fsdecode(relative_path))
            kind = "python"
        elif relative_path.suffix == ".sh":
            shell_count += 1
            error = check_shell(absolute_path)
            kind = "shell"
        else:
            continue
        if error is not None:
            failures.append((kind, relative_path, error))

    for kind, path, error in failures:
        print(f"source-syntax-check: FAIL {kind} {path}: {error}")

    total = python_count + shell_count
    if failures:
        print(
            "source-syntax-check: FAIL "
            f"files={total} python={python_count} shell={shell_count} "
            f"failures={len(failures)}"
        )
        return EXIT_SYNTAX

    print(
        "source-syntax-check: PASS "
        f"files={total} python={python_count} shell={shell_count} failures=0"
    )
    return EXIT_OK


def selftest() -> int:
    if shutil.which("sh") is None:
        print("source-syntax-check selftest: ERROR sh not found", file=sys.stderr)
        return EXIT_INFRASTRUCTURE

    cases = (
        ("valid.py", b"answer = 6 * 7\n", True),
        ("invalid.py", b"if True print('bad')\n", False),
        ("valid.sh", b"#!/bin/sh\nif true; then\n  :\nfi\n", True),
        ("invalid.sh", b"#!/bin/sh\nif true; then\n", False),
    )

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="source-syntax-check-") as temp_name:
        temp_dir = Path(temp_name)
        for name, contents, should_pass in cases:
            path = temp_dir / name
            path.write_bytes(contents)
            if path.suffix == ".py":
                error = check_python(path, name)
            else:
                error = check_shell(path)
            passed = error is None
            if passed != should_pass:
                expectation = "pass" if should_pass else "fail"
                failures.append(f"{name}: expected {expectation}, got {error or 'PASS'}")

        bytecode_outputs = list(temp_dir.rglob("*.pyc"))
        bytecode_dirs = list(temp_dir.rglob("__pycache__"))
        if bytecode_outputs or bytecode_dirs:
            failures.append("Python check created bytecode output")

    for failure in failures:
        print(f"source-syntax-check selftest: FAIL {failure}")
    if failures:
        print(f"source-syntax-check selftest: FAIL cases=4 failures={len(failures)}")
        return EXIT_SYNTAX

    print("source-syntax-check selftest: PASS cases=4 failures=0")
    return EXIT_OK


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="check tracked Python and shell sources for syntax errors"
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run temporary valid and invalid source cases",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.selftest:
            return selftest()
        root = git_root(Path.cwd())
        return run_check(root, tracked_sources(root))
    except InfrastructureError as exc:
        print(f"source-syntax-check: ERROR {exc}", file=sys.stderr)
        return EXIT_INFRASTRUCTURE


if __name__ == "__main__":
    raise SystemExit(main())
