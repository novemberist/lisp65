#!/usr/bin/env python3
"""Estimate Bytecode-Stdlib embed deltas for optional suites."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import bytecode_p0_stdlib as S  # noqa: E402


DEFAULT_BASE = ROOT / "tests" / "bytecode" / "stdlib" / "p0-stdlib-subset.json"
DEFAULT_OPTIONS = [
    ROOT / "tests" / "bytecode" / "stdlib" / "p0-string-polish-subset.json",
    ROOT / "tests" / "bytecode" / "stdlib" / "p0-fixed-point-subset.json",
]


class WhatIfError(Exception):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _merge_suite(base: dict[str, Any], options: list[dict[str, Any]]) -> dict[str, Any]:
    sources = list(base.get("sources", []))
    functions = list(base.get("functions", []))
    for option in options:
        sources.extend(option.get("sources", []))
        functions.extend(option.get("functions", []))
    return {
        "format": "lisp65-bytecode-p0-stdlib-subset-v1",
        "description": "generated what-if suite",
        "sources": _uniq(sources),
        "functions": _uniq(functions),
        "cases": list(base.get("cases", [{"name": "dummy", "expr": "nil"}])),
    }


def _metrics(suite: dict[str, Any]) -> dict[str, int]:
    try:
        (
            _heap,
            names,
            code_by_name,
            _entry_flags_by_name,
            _resident_entry_flags,
            bundle,
            _directory,
            _cases,
            _entry_names,
            _inliner,
        ) = S._compile_suite(suite, include_cases=False)
    except Exception as exc:
        raise WhatIfError(str(exc))
    literal_slots = sum(len(code_by_name[name].littab) for name in names)
    return {
        "functions": len(suite.get("functions", [])),
        "objects": len(names),
        "code_bytes": len(bundle.blob),
        "directory_bytes": len(bundle.directory_bytes()),
        "literal_slots": literal_slots,
    }


def _delta(new: dict[str, int], old: dict[str, int]) -> dict[str, int]:
    return {key: new[key] - old[key] for key in old}


def _estimate_prg_delta(delta: dict[str, int]) -> int:
    # The native PRG embeds the code blob, one vm_embed_entry per object, and
    # literal metadata. Directory bytes are the closest stable proxy for the
    # entry table across host/target layouts; literal slots proxy patch metadata.
    return delta["code_bytes"] + delta["directory_bytes"] + 4 * delta["literal_slots"]


def _print_metrics(label: str, metrics: dict[str, int]) -> None:
    print(
        "%s functions=%d objects=%d code_bytes=%d dir_bytes=%d literal_slots=%d"
        % (
            label,
            metrics["functions"],
            metrics["objects"],
            metrics["code_bytes"],
            metrics["directory_bytes"],
            metrics["literal_slots"],
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("options", nargs="*", type=Path, help="optional stdlib suite JSON files")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    args = parser.parse_args(argv)

    option_paths = args.options or DEFAULT_OPTIONS
    try:
        base = _read_json(args.base)
        options = [_read_json(path) for path in option_paths]
        base_metrics = _metrics(base)
        print("stdlib-embed-whatif: base=%s" % _rel(args.base))
        _print_metrics("  base", base_metrics)

        for path, suite in zip(option_paths, options):
            merged = _merge_suite(base, [suite])
            merged_metrics = _metrics(merged)
            delta = _delta(merged_metrics, base_metrics)
            new_functions = sorted(set(suite.get("functions", [])) - set(base.get("functions", [])))
            print("  option=%s" % _rel(path))
            print(
                "    new_functions=%d duplicate_functions=%d"
                % (len(new_functions), len(suite.get("functions", [])) - len(new_functions))
            )
            print(
                "    delta functions=%+d objects=%+d code_bytes=%+d dir_bytes=%+d literal_slots=%+d est_prg_delta=%+d"
                % (
                    delta["functions"],
                    delta["objects"],
                    delta["code_bytes"],
                    delta["directory_bytes"],
                    delta["literal_slots"],
                    _estimate_prg_delta(delta),
                )
            )

        if options:
            combined = _merge_suite(base, options)
            combined_metrics = _metrics(combined)
            delta = _delta(combined_metrics, base_metrics)
            print("  combined_options=%d" % len(options))
            print(
                "    delta functions=%+d objects=%+d code_bytes=%+d dir_bytes=%+d literal_slots=%+d est_prg_delta=%+d"
                % (
                    delta["functions"],
                    delta["objects"],
                    delta["code_bytes"],
                    delta["directory_bytes"],
                    delta["literal_slots"],
                    _estimate_prg_delta(delta),
                )
            )
    except Exception as exc:
        print("stdlib-embed-whatif: FAIL: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
