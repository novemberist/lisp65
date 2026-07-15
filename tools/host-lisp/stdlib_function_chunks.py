#!/usr/bin/env python3
"""Report cumulative function-cell expectations for chunked stdlib LOAD files."""

from __future__ import annotations

import argparse
from pathlib import Path

import stdlib_function_budget
import stdlib_source_budget
import stdlib_symbol_budget


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHUNK_DIR = ROOT / "build" / "ship" / "stdlib-chunks"
DEFAULT_EVAL = ROOT / "src" / "eval.c"


def chunk_paths(chunk_dir: Path) -> list[Path]:
    return sorted(
        path for path in chunk_dir.iterdir()
        if path.is_file() and len(path.name) == 3 and path.name[0] == "L"
    )


def chunk_bindings(path: Path) -> list[tuple[str, str]]:
    forms = stdlib_source_budget.top_level_forms(
        stdlib_source_budget.strip_comments(path.read_text(encoding="utf-8"))
    )
    bindings: list[tuple[str, str]] = []
    for form in forms:
        head = stdlib_function_budget.form_head(form)
        if head:
            bindings.append(head)
    return bindings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-c", type=Path, default=DEFAULT_EVAL)
    parser.add_argument(
        "--names",
        action="store_true",
        help="append comma-separated function/macro names defined by each chunk",
    )
    parser.add_argument("chunk_dir", nargs="?", type=Path, default=DEFAULT_CHUNK_DIR)
    args = parser.parse_args()

    native = stdlib_symbol_budget.native_symbols(args.eval_c)
    cumulative: set[str] = set()

    print("stdlib-function-chunks")
    header = "chunk defun defmacro chunk_unique cumulative_source expected_function_symbols"
    if args.names:
        header += " names"
    print(header)
    for path in chunk_paths(args.chunk_dir):
        bindings = chunk_bindings(path)
        defun = sum(1 for kind, _ in bindings if kind == "defun")
        defmacro = sum(1 for kind, _ in bindings if kind == "defmacro")
        ordered_names = [name for _, name in bindings]
        names = set(ordered_names)
        cumulative |= names
        expected = native | cumulative
        line = (
            f"{path.name} {defun} {defmacro} {len(names)} "
            f"{len(cumulative)} {len(expected)}"
        )
        if args.names:
            line += f" {','.join(ordered_names)}"
        print(line)

    print(f"native_functions={len(native)}")
    print(f"total_source_function_bindings={len(cumulative)}")
    print(f"source_native_overlaps={len(native & cumulative)}")
    print(f"expected_function_symbols={len(native | cumulative)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
