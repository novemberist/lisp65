#!/usr/bin/env python3
"""Host-only Eval oracle for lib/ide-buffer.lisp."""

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
DEFAULT_IDE_LIB = ROOT / "lib" / "ide-buffer.lisp"
DEFAULT_CASES = ROOT / "lib" / "tests" / "ide-buffer-eval-cases.json"


def main(argv: list[str]) -> int:
    prelude = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRELUDE
    ide_lib = Path(argv[2]) if len(argv) > 2 else DEFAULT_IDE_LIB
    cases = Path(argv[3]) if len(argv) > 3 else DEFAULT_CASES
    data = json.loads(cases.read_text(encoding="utf-8"))

    try:
        load_prelude(prelude, reset=True)
        load_prelude(ide_lib, reset=False)
    except (EvalError, ReaderError) as exc:
        print(f"FAIL ide-buffer load: {exc}", file=sys.stderr)
        print("ide-buffer-eval-oracle: PASS=0 FAIL=1")
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
    print(f"ide-buffer-eval-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
