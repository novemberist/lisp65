#!/usr/bin/env python3
"""Oracle for the post-M1 standard-library conformance plan.

The checker keeps the plan structurally honest and, once the K-A ABI is ready,
evaluates every active case against the M1 Prelude plus the current Stdlib
layers. Blocked cases remain declarative and must name their substrate blocker.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from mvp_prelude_m1_eval_oracle import (
    DEFAULT_PRELUDE,
    Env,
    EvalError,
    ReaderError,
    check_case,
    load_prelude,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "lib" / "tests" / "stdlib-conformance-plan.json"
DEFAULT_STDLIBS = [
    ROOT / "lib" / "stdlib-strings.lisp",
    ROOT / "lib" / "stdlib-sequences.lisp",
    ROOT / "lib" / "stdlib-lists.lisp",
    ROOT / "lib" / "stdlib-math.lisp",
    ROOT / "lib" / "stdlib-plists.lisp",
    ROOT / "lib" / "stdlib-format.lisp",
    ROOT / "lib" / "stdlib-format-extra.lisp",
    ROOT / "lib" / "stdlib-control.lisp",
]
REQUIRED_CATEGORIES = {
    "control-macros",
    "lists-and-sequences",
    "strings",
    "math",
    "assoc-and-plist",
    "higher-order",
    "format-subset",
    "output",
}
VALID_STATUS = {"active", "blocked"}


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def check(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gate = plan.get("abi_gate", {})
    if gate.get("name") != "K-A-ABI":
        errors.append("abi_gate.name must be K-A-ABI")
    if gate.get("status") not in {"waiting", "ready"}:
        errors.append("abi_gate.status must be waiting or ready")

    categories = plan.get("categories")
    if not isinstance(categories, list):
        return ["categories must be a list"]

    seen: set[str] = set()
    active_cases = 0
    blocked_cases = 0
    for category in categories:
        if not isinstance(category, dict):
            errors.append("category entries must be objects")
            continue
        name = category.get("name")
        if not isinstance(name, str) or not name:
            errors.append("category.name must be non-empty")
            continue
        if name in seen:
            errors.append(f"{name}: duplicate category")
        seen.add(name)
        if not strings(category.get("symbols")):
            errors.append(f"{name}: symbols must be a non-empty string list")
        cases = category.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{name}: cases must be a non-empty list")
            continue
        for case in cases:
            if not isinstance(case, dict):
                errors.append(f"{name}: case entries must be objects")
                continue
            case_name = case.get("name")
            status = case.get("status")
            if not isinstance(case_name, str) or not case_name:
                errors.append(f"{name}: case.name must be non-empty")
            if not isinstance(case.get("input"), str) or not case["input"]:
                errors.append(f"{name}/{case_name}: input must be non-empty")
            if not isinstance(case.get("expect"), str):
                errors.append(f"{name}/{case_name}: expect must be a string")
            if status not in VALID_STATUS:
                errors.append(f"{name}/{case_name}: status must be active or blocked")
            elif status == "active":
                active_cases += 1
            else:
                blocked_cases += 1
                if not strings(case.get("blocked_by")):
                    errors.append(f"{name}/{case_name}: blocked case must name blocked_by")

    missing = REQUIRED_CATEGORIES - seen
    for name in sorted(missing):
        errors.append(f"{name}: missing required category")
    if active_cases == 0:
        errors.append("plan must include at least one active case")
    if gate.get("status") == "waiting" and blocked_cases == 0:
        errors.append("plan must include blocked cases while ABI is waiting")
    return errors


def active_cases(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (category["name"], case)
        for category in plan["categories"]
        for case in category["cases"]
        if case["status"] == "active"
    ]


def evaluate_active_cases(plan: dict[str, Any]) -> tuple[int, list[str]]:
    try:
        load_prelude(DEFAULT_PRELUDE, reset=True)
        for stdlib in DEFAULT_STDLIBS:
            load_prelude(stdlib, reset=False)
    except (EvalError, ReaderError) as exc:
        return 0, [f"stdlib load: {exc}"]

    env = Env()
    passed = 0
    failures: list[str] = []
    for category, case in active_cases(plan):
        try:
            ok, message = check_case(case, env)
        except Exception as exc:
            ok, message = False, f"{case.get('name', '<unnamed>')}: {exc}"
        if ok:
            passed += 1
        else:
            failures.append(f"{category}/{message}")
    return passed, failures


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PLAN
    plan = json.loads(path.read_text(encoding="utf-8"))
    errors = check(plan)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"stdlib-conformance-plan-oracle: PASS=0 FAIL={len(errors)}")
        return 1

    blocked = sum(
        1
        for category in plan["categories"]
        for case in category["cases"]
        if case["status"] == "blocked"
    )
    if plan.get("abi_gate", {}).get("status") == "ready":
        passed, failures = evaluate_active_cases(plan)
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        print(f"stdlib-conformance-plan-oracle: PASS={passed} FAIL={len(failures)} BLOCKED={blocked}")
        return 0 if not failures else 1

    cases = sum(len(category["cases"]) for category in plan["categories"])
    print(f"stdlib-conformance-plan-oracle: PASS={cases} FAIL=0 BLOCKED={blocked}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
