#!/usr/bin/env python3
"""Summarize the current F011 stdlib function-binding gap from a footprint report."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_REPORT = Path("build") / "ship" / "footprint-report.txt"


def report_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("layer="):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def chunk_expectations(path: Path) -> dict[str, tuple[int, list[str]]]:
    chunks: dict[str, tuple[int, list[str]]] = {}
    in_chunks = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "Full stdlib function chunks:":
            in_chunks = True
            continue
        if in_chunks and line == "F011 stdlib smoke diagnostics:":
            break
        match = re.match(r"^(L[0-9][0-9])\s+\S+\s+\S+\s+\S+\s+\S+\s+([0-9]+)\s*(.*)$", line)
        if match:
            names = [name for name in match.group(3).split(",") if name]
            chunks[match.group(1)] = (int(match.group(2)), names)
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", nargs="?", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    values = report_values(args.report)
    chunks = chunk_expectations(args.report)
    l11_expected, l11_names = chunks.get("L11", (0, []))

    print("f011-binding-gap")
    print(f"report={args.report}")
    print(f"runtime_functions={values.get('functions', 'missing')}")
    print(f"l11_expected_function_symbols={l11_expected or 'missing'}")
    print(f"l11_names={','.join(l11_names) if l11_names else 'missing'}")
    print(f"str11_mask={values.get('str11_mask', 'missing')}")
    print(f"str11_bound={values.get('str11_bound', 'missing')}")
    print(f"str11_missing={values.get('str11_missing', 'missing')}")

    if values.get("str11_missing") and values["str11_missing"] != "none":
        print("status=gap-observed")
    elif values.get("str11_mask") == "missing":
        print("status=no-layer-probe")
    else:
        print("status=no-str11-gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
