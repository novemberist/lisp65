#!/usr/bin/env python3
"""Evaluation oracle for lib/stdlib-plists.lisp on the M1 Prelude."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from mvp_prelude_m1_eval_oracle import (
    DEFAULT_PRELUDE,
    Env,
    EvalError,
    ReaderError,
    check_case,
    load_prelude,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STDLIB = ROOT / "lib" / "stdlib-plists.lisp"
DEFAULT_CASES = ROOT / "lib" / "tests" / "stdlib-plist-eval-cases.json"


def main(argv: list[str]) -> int:
    prelude = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRELUDE
    stdlib = Path(argv[2]) if len(argv) > 2 else DEFAULT_STDLIB
    cases = Path(argv[3]) if len(argv) > 3 else DEFAULT_CASES
    data = json.loads(cases.read_text(encoding="utf-8"))

    try:
        load_prelude(prelude, reset=True)
        load_prelude(stdlib, reset=False)
    except (EvalError, ReaderError) as exc:
        print(f"FAIL stdlib load: {exc}", file=sys.stderr)
        print("stdlib-plist-eval-oracle: PASS=0 FAIL=1")
        return 1

    env = Env()
    passed = 0
    failed = 0
    for case in data["cases"]:
        try:
            ok, message = check_case(case, env)
        except Exception as exc:
            ok, message = False, f"{case.get('name', '<unnamed>')}: {exc}"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {message}", file=sys.stderr)
    print(f"stdlib-plist-eval-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
