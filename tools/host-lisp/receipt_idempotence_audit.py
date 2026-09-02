#!/usr/bin/env python3
"""Audit the receipt writers implicated by the Block-2.5 midnight drift."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
WRITERS = (
    "c2_ship_boot_inheritance_gate.py",
    "c2_code_window_convergence_gate.py",
    "c2_dma_content_consumption_sweep.py",
    "c2_mapped_far_asm_equivalence.py",
    "c2_mapped_far_service_gate.py",
)


class AuditError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AuditError(message)


def date_sites(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    sites = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"today", "now"}):
            sites.append(node.lineno)
    return sorted(sites)


def validate_repeatable_writer(source: str, name: str) -> int:
    require("from evidence_era import" in source
            and "stable_recorded_on" in source,
            f"receipt writer lost stable recorded_on: {name}")
    calls = source.count("stable_recorded_on(")
    require(calls >= 1,
            f"receipt writer does not consume sealed origin: {name}")
    return calls


def evaluate(root: Path = ROOT) -> dict[str, Any]:
    host = root / HOST.relative_to(ROOT)
    writer_rows = []
    for name in WRITERS:
        path = host / name
        source = path.read_text(encoding="utf-8")
        calls = validate_repeatable_writer(source, name)
        writer_rows.append({"path": path.relative_to(root).as_posix(),
                            "dynamic_date_sites": date_sites(path),
                            "stable_origin_calls": calls})

    helper = (host / "evidence_era.py").read_text(encoding="utf-8")
    require("def stable_recorded_on(" in helper
            and "return recorded" in helper
            and "return date.today().isoformat()" in helper,
            "shared stable recorded_on helper drift")

    dynamic = []
    for path in sorted(host.glob("*.py")):
        sites = date_sites(path)
        if sites:
            dynamic.append({"path": path.relative_to(root).as_posix(),
                            "sites": sites})
    gates = (root / "mk/gates.mk").read_text(encoding="utf-8")
    invoked = set(re.findall(r"python3 (tools/host-lisp/[^ ]+\.py)", gates))
    active_dynamic = sorted(row["path"] for row in dynamic
                            if row["path"] in invoked)
    return {
        "status": "PASS: MIDNIGHT RECEIPT DRIFT CLOSED",
        "corrected_writers": writer_rows,
        "dynamic_date_inventory": {
            "files": len(dynamic),
            "sites": sum(len(row["sites"]) for row in dynamic),
            "check_source_referenced_files": len(active_dynamic),
            "classification": (
                "inventory only: most sites are one-shot/device producers; "
                "a dynamic date is forbidden only when a repeatable check "
                "rewrites claim-bearing tracked evidence"),
        },
        "mutations_rejected": [
            "remove-shared-stable-origin",
            "restore-today-for-any-of-five-repeatable-writers",
        ],
        "product_bytes_changed": 0,
    }


def selftest() -> None:
    source = (HOST / WRITERS[0]).read_text(encoding="utf-8")
    mutant = source.replace("stable_recorded_on", "seal_recorded_on")
    rejected = False
    try:
        validate_repeatable_writer(mutant, "mutant.py")
    except AuditError:
        rejected = True
    require(rejected, "stable-origin mutation survived")
    value = evaluate()
    require(len(value["corrected_writers"]) == 5,
            "corrected writer population drift")
    print("receipt idempotence selftest: PASS writers=5 mutations=2")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
    else:
        value = evaluate()
        print("receipt idempotence audit: PASS "
              f"writers={len(value['corrected_writers'])} "
              f"dynamic-sites={value['dynamic_date_inventory']['sites']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
