#!/usr/bin/env python3
"""Summarize ship readiness from the generated lisp65 ship reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_FOOTPRINT = Path("build") / "ship" / "footprint-report.txt"
DEFAULT_FULL_EMBED = Path("build") / "ship" / "full-embed-fit-report.txt"
DEFAULT_F011_MATRIX = Path("build") / "ship" / "f011-stdlib-profile-matrix.txt"
DEFAULT_CONFORMANCE = Path("lib") / "tests" / "stdlib-conformance-plan.json"
REQUIRED_CONFORMANCE_CATEGORIES = {
    "control-macros",
    "lists-and-sequences",
    "strings",
    "math",
    "assoc-and-plist",
    "higher-order",
    "format-subset",
}


def key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith(("layer=", "L")):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def section_values(path: Path, header: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == header:
            in_section = True
            continue
        if not in_section:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def matrix_gaps(path: Path) -> list[int]:
    gaps: list[int] = []
    if not path.exists():
        return gaps
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 13 and parts[0].isdigit() and parts[1].isdigit():
            gap = parts[12]
            if gap.isdigit():
                gaps.append(int(gap))
    return gaps


def conformance_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "status": "missing",
            "abi_gate": "missing",
            "categories": "0",
            "active_cases": "0",
            "blocked_cases": "missing",
            "missing_categories": ",".join(sorted(REQUIRED_CONFORMANCE_CATEGORIES)),
        }

    plan = json.loads(path.read_text(encoding="utf-8"))
    categories = plan.get("categories", [])
    category_names = {
        category.get("name")
        for category in categories
        if isinstance(category, dict) and isinstance(category.get("name"), str)
    }
    active_cases = 0
    blocked_cases = 0
    for category in categories:
        if not isinstance(category, dict):
            continue
        for case in category.get("cases", []):
            if not isinstance(case, dict):
                continue
            if case.get("status") == "active":
                active_cases += 1
            elif case.get("status") == "blocked":
                blocked_cases += 1

    missing = sorted(REQUIRED_CONFORMANCE_CATEGORIES - category_names)
    abi_gate = plan.get("abi_gate", {}).get("status", "missing")
    if abi_gate == "ready" and active_cases > 0 and blocked_cases == 0 and not missing:
        status = "covered"
    elif missing:
        status = "missing-categories"
    elif blocked_cases:
        status = "blocked-cases"
    else:
        status = "waiting"

    return {
        "status": status,
        "abi_gate": str(abi_gate),
        "categories": str(len(category_names)),
        "active_cases": str(active_cases),
        "blocked_cases": str(blocked_cases),
        "missing_categories": ",".join(missing) if missing else "none",
    }


def f011_transport_status(values: dict[str, str]) -> str:
    loaded = values.get("loaded", "missing")
    chunks = values.get("chunks", "missing")
    if loaded.isdigit() and chunks.isdigit() and loaded == chunks and int(chunks) > 0:
        return "ok"
    if loaded == "missing" or chunks == "missing":
        return "missing"
    return "mismatch"


def f011_binding_status(values: dict[str, str]) -> str:
    bindings = values.get("bindings", "missing")
    if bindings == "6 mask 63":
        return "full-sentinel-bindings"
    if bindings == "missing":
        return "missing"
    return "gap-observed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    parser.add_argument("--full-embed", type=Path, default=DEFAULT_FULL_EMBED)
    parser.add_argument("--f011-matrix", type=Path, default=DEFAULT_F011_MATRIX)
    parser.add_argument("--conformance", type=Path, default=DEFAULT_CONFORMANCE)
    args = parser.parse_args()

    full_embed = key_values(args.full_embed)
    footprint = key_values(args.footprint)
    f011_gap = section_values(args.footprint, "F011 binding gap summary:")
    gaps = matrix_gaps(args.f011_matrix)
    conformance = conformance_summary(args.conformance)

    full_embed_status = full_embed.get("status", "missing")
    transport_status = f011_transport_status(footprint)
    binding_status = f011_binding_status(footprint)

    blockers: list[str] = []
    if full_embed_status != "default-fits":
        blockers.append("full-embed-bank0-footprint")
    if transport_status != "ok":
        blockers.append("f011-transport")
    if binding_status != "full-sentinel-bindings":
        blockers.append("f011-stdlib-binding-gap")

    status = "full-ship-ready" if not blockers else "interim-ready-with-known-blockers"
    full_embed_objective = (
        "ok" if full_embed_status == "default-fits" else "blocked"
    )
    f011_offline_objective = (
        "ok" if transport_status == "ok" else "blocked"
    )
    full_stdlib_runtime_objective = (
        "ok" if binding_status == "full-sentinel-bindings" else "known-blocker"
    )
    one_command_ship_objective = (
        "ok" if status == "full-ship-ready" else "interim-with-known-blockers"
    )

    print("lisp65 ship readiness")
    print(f"status={status}")
    print(f"blockers={','.join(blockers) if blockers else 'none'}")
    print(f"objective_one_command_ship_status={one_command_ship_objective}")
    print(f"objective_stdlib_conformance_status={conformance['status']}")
    print(f"objective_full_embed_status={full_embed_objective}")
    print(f"objective_f011_offline_status={f011_offline_objective}")
    print(f"objective_full_stdlib_runtime_status={full_stdlib_runtime_objective}")
    print(f"conformance_plan={args.conformance}")
    print(f"conformance_abi_gate={conformance['abi_gate']}")
    print(f"conformance_categories={conformance['categories']}")
    print(f"conformance_active_cases={conformance['active_cases']}")
    print(f"conformance_blocked_cases={conformance['blocked_cases']}")
    print(f"conformance_missing_categories={conformance['missing_categories']}")
    print(f"full_embed_report={args.full_embed}")
    print(f"full_embed_status={full_embed_status}")
    print(f"full_embed_default_heap={full_embed.get('default_heap', 'missing')}")
    print(f"full_embed_default_overflow={full_embed.get('default_overflow', 'missing')}")
    print(f"full_embed_min_link_heap={full_embed.get('min_link_heap', 'missing')}")
    print(f"f011_footprint_report={args.footprint}")
    print(f"f011_transport_status={transport_status}")
    print(f"f011_loaded={footprint.get('loaded', 'missing')}")
    print(f"f011_chunks={footprint.get('chunks', 'missing')}")
    print(f"f011_binding_status={binding_status}")
    print(f"f011_bindings={footprint.get('bindings', 'missing')}")
    print(f"f011_functions={footprint.get('functions', 'missing')}")
    print(f"f011_gap_report_status={f011_gap.get('status', 'missing')}")
    print(f"f011_gap_runtime_functions={f011_gap.get('runtime_functions', 'missing')}")
    l11_expected = f011_gap.get("l11_expected_function_symbols", "missing")
    print(f"f011_gap_l11_expected_function_symbols={l11_expected}")
    print(f"f011_gap_str11_bound={f011_gap.get('str11_bound', 'missing')}")
    print(f"f011_gap_str11_missing={f011_gap.get('str11_missing', 'missing')}")
    print(f"f011_matrix_report={args.f011_matrix}")
    print(f"f011_matrix_min_fn_gap={min(gaps) if gaps else 'missing'}")
    print(f"f011_matrix_max_fn_gap={max(gaps) if gaps else 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
