#!/usr/bin/env python3
"""Host screen-content check for the IDE minibuffer status row (Mini8 keys).

Runs the Mini8 key sequence (C-x C-f, then ``demo1234``) on the generated
dialect-v2 IDE suite in the Python P0 VM, captures the VM screen, and asserts
the exact status-row cells: the full minibuffer input is visible and the
cursor cell sits directly after it.  It also reports render cost per typed
key and for one idle render, in VM steps.

``--suite`` selects another generated suite (for example the unrepaired one
as a failing control).  Host-only; no product build, link, media or device.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import bytecode_p0 as B  # noqa: E402
import v2_string_codec_workloads as W  # noqa: E402

KEYS = [100, 101, 109, 111, 49, 50, 51, 52]  # "demo1234"
PREFIX = "Find file: "
# Active input owns the row; buffer frame and budget belong to idle status.
MAX_OPS_PER_KEY = 95000 // 8  # per-key share of the existing Mini8 budget

def row_failures(cells: list[int], text: str, cols: int) -> list[str]:
    low7 = "".join(chr(c & 127) for c in cells)
    cursor = len(text)
    failures = []
    if len(cells) != cols or not re.fullmatch(re.escape(text) + r"_ *", low7):
        failures.append(f"status row: observed={low7.rstrip()!r} expected={text + '_'!r}")
    if cursor >= len(cells) or not cells[cursor] & 128:
        failures.append(f"cursor cell {cursor} lacks the inverse bit")
    stray = [x for x, c in enumerate(cells) if x != cursor and c & 128]
    if stray:
        failures.append(f"inverse cells outside the cursor: {stray}")
    return failures

def row_selftest() -> None:
    text = PREFIX + "demo1234"
    def row(s):
        cells = list(map(ord, (s + "_").ljust(80)))
        cells[len(s)] |= 128
        return cells
    good = row(text)
    assert not row_failures(good, text, 80)
    controls = [row("-- scratch M-x " + text)]
    for index, value in ((79, ord('1')), (len(text), ord('_')),
                         (len(text) + 1, ord('_') | 128)):
        cells = good.copy(); cells[index] = value; controls.append(cells)
    assert all(row_failures(cells, text, 80) for cells in controls)

def _expr(typed: int, idle: bool) -> str:
    lines = ["(progn", " (set-symbol-value (quote %ide-prefix) nil)",
             ' (let* ((s0 (ide-make-state (ide-make-buffer "scratch" (list ""))))',
             "        (s1 (ide-step s0 (list (quote key) 24 nil)))",
             "        (s2 (ide-step s1 (list (quote key) 6 nil)))"]
    for i, code in enumerate(KEYS[:typed]):
        lines.append(f"        (s{i + 3} (%ide-input-render (ide-step s{i + 2} (list (quote key) {code} nil))))")
    last = f"s{typed + 2}"
    body = f"(%ide-input-render {last})" if idle else last
    lines.append(f"        (sz {body}))")
    lines.append("   (list (ide-state-message sz) (progn (%ide-mini-fold) (%ide-mini-status-line)))))")
    return "\n".join(lines)


def _run_case(suite: Path, typed: int, idle: bool = False) -> tuple[dict, object]:
    text = "demo1234"[:typed]
    spec = {"id": f"mini-screen-{typed}{'-idle' if idle else ''}", "suite": suite,
            "profile_role": "host-check", "expr": _expr(typed, idle),
            "expect": f'(1005 "Find file: {text}")',
            "max_ops": 10_000_000, "max_heap_churn": 10_000_000, "capture_screen": True}
    with tempfile.TemporaryDirectory() as temp:
        measured = W._measure(spec, Path(temp))
    return measured, SimpleNamespace(screen_columns=measured['screen_columns'],screen_cells=measured['screen_cells'])


def check(suite: Path) -> dict:
    measured, vm = _run_case(suite, 8)
    cols = vm.screen_columns
    cells = vm.screen_cells[-cols:]
    low7 = "".join(chr(c & 127) for c in cells)
    text = PREFIX + "demo1234"
    cursor = len(text)
    row_selftest()
    failures = row_failures(cells, text, cols)
    ops = [_run_case(suite, n)[0]["ops"] for n in (7, 8)]
    idle = _run_case(suite, 8, idle=True)[0]["ops"]
    per_key = ops[1] - ops[0]
    if per_key > MAX_OPS_PER_KEY:
        failures.append(f"per-key render cost {per_key} > {MAX_OPS_PER_KEY}")
    return {"suite": str(suite), "status_row": low7.rstrip(), "cursor_column": cursor,
            "cursor_cell": cells[cursor], "mini8_ops": measured["ops"],
            "mini8_heap_churn": measured["heap_churn"], "ops_per_typed_key": per_key,
            "ops_idle_render": idle - ops[1], "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", type=Path, default=W.V2_IDE_SUITE)
    ap.add_argument("--expect-fail", action="store_true",
                    help="control mode: succeed only if the screen assertion fails")
    args = ap.parse_args()
    report = check(args.suite.resolve())
    print(json.dumps(report, indent=2))
    failed = bool(report["failures"])
    if args.expect_fail:
        print("ide-minibuffer-screen-check: CONTROL " + ("FAILS AS EXPECTED" if failed else "UNEXPECTED PASS"))
        return 0 if failed else 1
    print("ide-minibuffer-screen-check: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
