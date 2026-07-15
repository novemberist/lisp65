#!/usr/bin/env python3
"""Split Lisp source files into small top-level-form chunks for disk LOAD."""

from __future__ import annotations

import argparse
from pathlib import Path


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
            # Atoms are complete at following whitespace; parenthesized forms here.
            if ch == ")" or (i + 1 == len(text)):
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


def add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def write_chunks(forms: list[tuple[Path, str]], out_dir: Path, max_bytes: int) -> list[tuple[Path, list[str]]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():
        if old.is_file():
            old.unlink()

    chunks: list[tuple[str, list[str]]] = []
    current = ""
    current_sources: list[str] = []
    for source, form in forms:
        item = form.strip() + "\n"
        size = len(item.encode("utf-8"))
        if size > max_bytes:
            raise ValueError(f"single form exceeds chunk size ({size} > {max_bytes}): {form[:60]}")
        if current and len((current + item).encode("utf-8")) > max_bytes:
            chunks.append((current, current_sources))
            current = ""
            current_sources = []
        current += item
        add_unique(current_sources, str(source))
    if current:
        chunks.append((current, current_sources))

    if len(chunks) > 100:
        raise ValueError("too many chunks for L00..L99 naming")

    paths: list[tuple[Path, list[str]]] = []
    for i, (chunk, sources) in enumerate(chunks):
        path = out_dir / f"L{i:02d}"
        path.write_text(chunk, encoding="utf-8")
        paths.append((path, sources))

    loadall = "".join(f'(load "l{i:02d}")\n' for i in range(len(chunks)))
    if len(loadall.encode("utf-8")) > max_bytes:
        raise ValueError("LOADALL exceeds chunk size")
    loadall_path = out_dir / "LOADALL"
    loadall_path.write_text(loadall, encoding="utf-8")
    return [(loadall_path, []), *paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--max-bytes", type=int, default=480)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()

    forms: list[tuple[Path, str]] = []
    for source in args.sources:
        forms.extend(
            (source, form)
            for form in top_level_forms(strip_comments(source.read_text(encoding="utf-8")))
        )

    paths = write_chunks(forms, args.out_dir, args.max_bytes)
    for path, sources in paths:
        suffix = f" sources={','.join(sources)}" if sources else ""
        print(f"{path.name} {path.stat().st_size}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
