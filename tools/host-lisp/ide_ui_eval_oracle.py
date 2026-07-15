#!/usr/bin/env python3
"""Host-only Eval oracle for the full IDE UI plus optional IDEX tier."""

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
DEFAULT_STRINGS_LIB = ROOT / "lib" / "stdlib-strings.lisp"
DEFAULT_IDE_BUFFER_LIB = ROOT / "lib" / "ide-buffer.lisp"
DEFAULT_IDE_STATUS_LIB = ROOT / "lib" / "ide-status.lisp"
DEFAULT_IDE_SYNTAX_LIB = ROOT / "lib" / "ide-syntax.lisp"
DEFAULT_IDE_UI_LIB = ROOT / "lib" / "ide-ui.lisp"
DEFAULT_IDE_EXTRA_LIB = ROOT / "lib" / "ide-extra.lisp"
DEFAULT_CASES = ROOT / "lib" / "tests" / "ide-ui-eval-cases.json"


def main(argv: list[str]) -> int:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    prelude = Path(argv[1]) if len(argv) > 1 else DEFAULT_PRELUDE
    strings_lib = Path(argv[2]) if len(argv) > 2 else DEFAULT_STRINGS_LIB
    buffer_lib = Path(argv[3]) if len(argv) > 3 else DEFAULT_IDE_BUFFER_LIB
    status_lib = Path(argv[4]) if len(argv) > 4 else DEFAULT_IDE_STATUS_LIB
    ui_lib = Path(argv[5]) if len(argv) > 5 else DEFAULT_IDE_UI_LIB
    cases = Path(argv[6]) if len(argv) > 6 else DEFAULT_CASES
    data = json.loads(cases.read_text(encoding="utf-8"))

    try:
        load_prelude(prelude, reset=True)
        load_prelude(strings_lib, reset=False)
        load_prelude(buffer_lib, reset=False)
        load_prelude(status_lib, reset=False)
        load_prelude(DEFAULT_IDE_SYNTAX_LIB, reset=False)   # Syntax-Feature (ide-ui ruft %ide-hl-walk/split-indented)
        load_prelude(ui_lib, reset=False)
        load_prelude(DEFAULT_IDE_EXTRA_LIB, reset=False)
    except (EvalError, ReaderError) as exc:
        print(f"FAIL ide-ui load: {exc}", file=sys.stderr)
        print("ide-ui-eval-oracle: PASS=0 FAIL=1")
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
    print(f"ide-ui-eval-oracle: PASS={passed} FAIL={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
