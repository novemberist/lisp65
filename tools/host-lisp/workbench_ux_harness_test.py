#!/usr/bin/env python3
"""Self-test the bounded Workbench UX transport retry contract."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
UX_SCRIPT = ROOT / "scripts" / "hw-workbench-ux-smoke.sh"


FAKE_RUNNER = r'''#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]

def value(name):
    pos = args.index(name)
    return args[pos + 1]

counter_path = Path(os.environ["FAKE_JTAG_COUNTER"])
count = int(counter_path.read_text()) + 1 if counter_path.exists() else 1
counter_path.write_text(str(count))

out_dir = Path(value("--out-dir"))
prefix = value("--prefix")
form = value("--form")
out_dir.mkdir(parents=True, exist_ok=True)
text_path = out_dir / f"{prefix}.txt"

def screen(submitted, result, *, stale=False):
    def echo_rows(current):
        rendered = f"lisp65> {current}"
        rows = [rendered[index:index + 80] for index in range(0, len(rendered), 80)]
        if len(rendered) % 80 == 0:
            rows.append("")
        return rows

    lines = []
    if stale:
        lines.extend(echo_rows(form))
        lines.extend(['(42 "ux-core-ok")', "lisp65>"])
    lines.extend(echo_rows(submitted))
    lines.extend([result, "lisp65>"])
    return "\n".join(f" {line:<80.80} " for line in lines) + "\n"

mode = os.environ["FAKE_JTAG_MODE"]
if mode == "first_corrupt" and count == 1:
    text_path.write_text(screen("(+ 2022)", "2022"))
    raise SystemExit(0)
if mode == "always_corrupt":
    text_path.write_text(screen("(+ 2022)", "2022"))
    raise SystemExit(0)
if mode == "product_failure":
    text_path.write_text(screen(form, '(41 "ux-core-ok")'))
    raise SystemExit(0)
if mode == "timeout":
    raise SystemExit(124)
if mode == "stateful_failure" and prefix.endswith("mx-command-form-1"):
    text_path.write_text(screen("(corrupted setup)", "nil"))
    raise SystemExit(0)
if mode == "stale_screen":
    text_path.write_text(screen("(+ 2022)", "2022", stale=True))
    raise SystemExit(0)

phase_results = {
    "core-arith": '(42 "ux-core-ok")',
    "core-load": '"ide-load-ok"',
    "r5-harness-helpers": '"r5-harness-ok"',
    "core-kind": "bytecode",
    "extra-load": '"idex-load-ok"',
    "idex-hook-override": '"idex-hook-overridden"',
    "eval-core-load": '"ide-load-ok"',
    "eval-extra-load": '"idex-load-ok"',
    "persistence-create": "(t nil bytecode)",
    "persistence-read": '("(defun ap6-persisted () 611)")',
    "persistence-create-second": '(t ("(defun ap6-b () 613)"))',
    "persistence-replace": '(t ("(defun ap6-persisted () 612)"))',
    "persistence-remount": "0",
    "higher-order-remount-every": "t",
    "higher-order-remount-some": "3",
    "mx-command": '"M-x {find-file}"',
    "directory": '"*directory*"',
    "directory-open": '"loaded"',
    "reject-fasl-open": '"not source"',
    "reject-fasl-directory-open": '"not source"',
    "reject-fasl-save": '"not source"',
    "find-tab": '(find-file "Find file: " "DEMO")',
    "buffer-tab": '(switch-buffer "Buffer: " "b" "a")',
    "buffer-cycle": '"a"',
    "delete-forward": '"ac"',
    "kill-line": '(("ab") "cd")',
    "yank": '(("abxycd") (0 . 4))',
    "word-edit": '((0 . 4) (0 . 3) (("ab ") "cd"))',
    "document-nav": '((2 . 1) (0 . 1) (0 . 0) (2 . 3))',
    "region-edit": '(("ad") "bc")',
    "region-multiline": '(("ah") (0 . 1) ("bcd" "ef" "g"))',
    "yank-multiline": '(("acd" "ef" "gb") (2 . 1))',
    "compile-source-guard": '"not source"',
    "navigation-aliases": '("a" "b" "cd")',
    "mini-history": '(find-file "Find file: " "demo")',
    "mini-edit": '"d"',
    "search-goto": '"moved"',
    "search-repeat": '((1 . 0) "found")',
    "higher-order-idex-every": "t",
    "higher-order-idex-some": "3",
    "mx-eval-buffer": '("evaluated" 42)',
}
phase = prefix.removeprefix("probe-")
if "-form-" in phase:
    result = "nil"
elif phase.startswith("core-arith-attempt-"):
    result = phase_results["core-arith"]
else:
    result = phase_results.get(phase, "nil")
if mode == "dynamic_failure" and phase == "find-tab":
    result = '(find-file "Find file: " "WRONG")'
if mode == "hook_failure" and phase == "idex-hook-override":
    result = '"hook not overridden"'
if mode == "higher_order_failure" and phase == "higher-order-remount-every":
    result = "nil"
if mode == "higher_order_late_failure" and phase == "higher-order-idex-some":
    result = "(3 nil)"
text_path.write_text(screen(form, result))
raise SystemExit(0)
'''


def run_case(tmp: Path, mode: str, *, bootstrap_only: bool = True) -> tuple[subprocess.CompletedProcess[str], int, Path]:
    case_dir = tmp / mode
    out_dir = case_dir / "out"
    counter = case_dir / "counter"
    case_dir.mkdir(parents=True)
    command = [
        "sh",
        str(UX_SCRIPT),
        "--no-build",
        "--no-deploy",
        "--boot-wait",
        "0",
        "--wait",
        "0",
        "--form-wait",
        "0",
        "--bootstrap-retry-wait",
        "0",
        "--out-dir",
        str(out_dir),
        "--prefix",
        "probe",
    ]
    if bootstrap_only:
        command.append("--bootstrap-only")
    env = os.environ.copy()
    env.update(
        {
            "FAKE_JTAG_COUNTER": str(counter),
            "FAKE_JTAG_MODE": mode,
            "IDE_LOAD_WAIT_SEC": "0",
            "HIGHER_ORDER_IO_WAIT_SEC": "0",
            "JTAG_REPL_RUNNER": str(tmp / "fake-jtag-repl.py"),
            "UX_CORE_NONCE": "ux-core-ok",
        }
    )
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    calls = int(counter.read_text()) if counter.exists() else 0
    return result, calls, out_dir


def require(condition: bool, message: str, result: subprocess.CompletedProcess[str] | None = None) -> None:
    if condition:
        return
    detail = ""
    if result is not None:
        detail = f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    raise AssertionError(message + detail)


def main() -> int:
    harness_source = UX_SCRIPT.read_text()
    require(
        "(%ide-mini-status-line)" not in harness_source,
        "hardware harness must not call the private core mini-status helper",
    )
    require(
        "(ide-status-line x 80)" in harness_source,
        "M-x hardware oracle must use the public status-line API",
    )
    require(
        "((lambda (line) (progn (setq x (ide-step x (list (quote key) 7 nil))) line)) (ide-status-line x 80))"
        in harness_source,
        "M-x hardware oracle must release its modal state through public C-g handling",
    )
    require(
        "(set-symbol-value (quote %ide-mini) nil)" not in harness_source,
        "hardware harness must not clear the private modal global directly",
    )
    require(
        "restauriere unveraenderte Ship-D81" in harness_source
        and "run_phase post-persistence-core-load" in harness_source,
        "AP6 fixtures must not contaminate the remaining UX matrix",
    )
    hook_phase = harness_source[harness_source.index("run_phase idex-hook-override"):]
    hook_phase = hook_phase[:hook_phase.index("run_phase mx-command")]
    require(
        '(setq x (ide-make-state (ide-make-buffer "scratch" (list ""))))' in hook_phase
        and '(setq x (%ide-x (quote motion) x 1013 nil))' in hook_phase
        and '(if (eq (ide-state-message x) 1005) "idex-hook-overridden" "hook not overridden")'
        in hook_phase,
        "IDEX override must use the bounded three-form early assertion",
    )
    require(
        harness_source.count('(setq x "(every (function plusp) ")') == 2,
        "every source prefix must run in exactly two long product states",
    )
    require(
        harness_source.count(
            '(setq x "(some (function (lambda (x) (if (> x 2) x nil))) ")'
        )
        == 2,
        "some source prefix must run in exactly two long product states",
    )
    require(
        harness_source.count(
            '(setq x (string-append x (char->string 39) "(1 2 3))"))'
        )
        == 4,
        "each higher-order oracle must reconstruct the exact apostrophe source",
    )
    require(
        harness_source.count('(string-append "(setq x " x ")")') == 4,
        "each higher-order fixture must retain a result-publishing second source form",
    )
    require(
        harness_source.count('(load "h8e")') == 4
        and harness_source.count('(load "h8s")') == 4,
        "each exact higher-order source file must execute twice in each long state",
    )
    require(
        'higher_order_io_wait_sec="${HIGHER_ORDER_IO_WAIT_SEC:-12}"' in harness_source
        and '--form-wait "$current_form_wait_sec"' in harness_source,
        "higher-order save/load forms must retain their dedicated I/O wait budget",
    )
    require(
        'persistence-create|persistence-create-second|persistence-replace) phase_wait_sec="${SAVE_WAIT_SEC:-20}"'
        in harness_source,
        "persistence writes must retain their first-load/save completion budget",
    )
    require(
        harness_source.index("run_phase persistence-remount")
        < harness_source.index("run_phase higher-order-remount-every")
        < harness_source.index("run_phase higher-order-remount-some")
        < harness_source.index("Reset/Remount ohne D81-Reupload"),
        "remount higher-order chain must remain every -> some before reset",
    )
    require(
        harness_source.index("run_phase search-repeat")
        < harness_source.index("run_phase higher-order-idex-some")
        < harness_source.index("run_phase higher-order-idex-every")
        < harness_source.index("frische Workbench-Session fuer M-x eval-buffer-Smoke"),
        "IDEX higher-order chain must remain some -> every after the long search state",
    )

    with tempfile.TemporaryDirectory(prefix="lisp65-ux-harness-") as raw_tmp:
        tmp = Path(raw_tmp)
        fake = tmp / "fake-jtag-repl.py"
        fake.write_text(FAKE_RUNNER)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

        result, calls, out_dir = run_case(tmp, "first_corrupt")
        require(result.returncode == 0, "retry case must pass", result)
        require(calls == 2, "retry case must call the runner twice", result)
        require("PASS core-arith after transport retry" in result.stdout, "retry must be visible", result)
        require((out_dir / "probe-core-arith.txt").exists(), "attempt 1 evidence missing")
        require((out_dir / "probe-core-arith-attempt-2.txt").exists(), "attempt 2 evidence missing")

        result, calls, _ = run_case(tmp, "always_corrupt")
        require(result.returncode == 5, "exhausted retries must retain the echo-failure status", result)
        require(calls == 2, "retry budget must be bounded", result)

        result, calls, _ = run_case(tmp, "stale_screen")
        require(result.returncode == 5, "stale evidence must not pass", result)
        require(calls == 2, "stale evidence may only consume the bounded retry", result)

        result, calls, _ = run_case(tmp, "product_failure")
        require(result.returncode == 4, "a product failure must fail", result)
        require(calls == 1, "an exact input echo must not be retried", result)

        result, calls, _ = run_case(tmp, "timeout")
        require(result.returncode == 124, "runner timeout must propagate", result)
        require(calls == 1, "runner timeout must not be retried", result)

        result, calls, _ = run_case(tmp, "pass")
        require(result.returncode == 0, "first-pass case must pass", result)
        require(calls == 1, "first-pass case must run once", result)

        result, calls, _ = run_case(tmp, "stateful_failure", bootstrap_only=False)
        require(result.returncode == 5, "stateful setup echo failure must retain its status", result)
        require(calls == 41, "stateful setup form must fail without retry", result)

        result, calls, _ = run_case(tmp, "hook_failure", bootstrap_only=False)
        require(result.returncode == 4, "missing IDEX override must fail as a product result", result)
        require(calls == 40, "IDEX override assertion phase must be the first post-load probe", result)
        require("hook not overridden" in result.stdout, "IDEX override diagnostic drift", result)

        result, calls, out_dir = run_case(tmp, "full_pass", bootstrap_only=False)
        require(result.returncode == 0, "complete stateful happy path must pass", result)
        require(calls > 100, "complete stateful happy path must exercise all phases", result)
        require("PASS Workbench UX HW smoke" in result.stdout, "full success marker missing", result)
        require((out_dir / "probe-find-tab.txt").exists(), "find-tab oracle was not reached", result)
        require((out_dir / "probe-buffer-tab.txt").exists(), "buffer-tab oracle was not reached", result)
        require((out_dir / "probe-mini-history.txt").exists(), "mini-history oracle was not reached", result)
        require((out_dir / "probe-persistence-create.txt").exists(), "persistence create oracle was not reached", result)
        require((out_dir / "probe-persistence-create-second.txt").exists(), "second persistence create oracle was not reached", result)
        require((out_dir / "probe-persistence-replace.txt").exists(), "persistence replace oracle was not reached", result)
        require((out_dir / "probe-higher-order-remount-every.txt").exists(), "remount every oracle was not reached", result)
        require((out_dir / "probe-higher-order-remount-some.txt").exists(), "remount some oracle was not reached", result)
        require((out_dir / "probe-higher-order-idex-every.txt").exists(), "IDEX every oracle was not reached", result)
        require((out_dir / "probe-higher-order-idex-some.txt").exists(), "IDEX some oracle was not reached", result)

        result, calls, _ = run_case(tmp, "dynamic_failure", bootstrap_only=False)
        require(result.returncode == 4, "wrong dynamic end value must fail", result)
        require(calls > 20, "dynamic failure must reach the find-tab phase", result)

        result, calls, _ = run_case(tmp, "higher_order_failure", bootstrap_only=False)
        require(result.returncode == 4, "wrong higher-order verdict must fail", result)
        require(calls > 20, "higher-order failure must reach the first exact oracle", result)

        result, calls, out_dir = run_case(tmp, "higher_order_late_failure", bootstrap_only=False)
        require(result.returncode == 4, "wrong late higher-order verdict must fail", result)
        require(calls > 100, "late higher-order failure must reach the IDEX state", result)
        require((out_dir / "probe-higher-order-idex-some.txt").exists(), "late some evidence missing")
        require(
            not (out_dir / "probe-higher-order-idex-every.txt").exists(),
            "late some failure must stop before the following every oracle",
        )

    print("workbench-ux-harness selftest: PASS (12 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
