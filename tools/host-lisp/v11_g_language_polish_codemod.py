#!/usr/bin/env python3
"""Materialize bounded 1.1-G language-polish probe variants.

The canonical Wave-1 sources remain untouched.  This wrapper first applies
the accepted C1 transform, then adds only the public bytecode wrappers needed
by the selected probe.  A private, probe-only extension of ``%c1-control`` is
provided by a copied ``vm.c`` during the real link; no Prim-ID is allocated by
this experiment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tools/host-lisp/v11_c1_lease_codemod.py"
GENERATED = ROOT / "build/bytecode/dialect-v2"
EVAL_SOURCE = GENERATED / "sources/lib/dialect-v2/eval-runtime.lisp"
SUITE = GENERATED / "suites/p0-stdlib-einsuite-core-workbench-subset.json"
VARIANTS = {"baseline", "bitops", "gc", "room", "read-string", "restart"}


class ProbeCodemodError(RuntimeError):
    pass


FORMS = {
    "bitops": """

; Probe-only 1.1-G wrappers.  The public functions are ordinary strict-arity
; bytecode functions; the private service is deliberately not a designator.
(defun logand (a b) (%c1-control 10 (cons a b)))
(defun logior (a b) (%c1-control 11 (cons a b)))
(defun logxor (a b) (%c1-control 12 (cons a b)))
(defun ash (value count) (%c1-control 13 (cons value count)))
""",
    "gc": """

(defun gc () (%c1-control 20 nil))
""",
    "room": """

(defun room () (%c1-control 21 nil))
""",
    "read-string": """

; Compose the already resident compiler reader.  A non-string deliberately
; reaches the existing string-length type guard; no new native service is
; needed for this public wrapper.
(defun read-from-string (source)
  (if (stringp source)
      (progn (%cs-read-open source) (%fasl-read-form))
      (string-length source)))
""",
    "restart": """

(defun restart-repl () (%c1-control 30 nil))
""",
}


FUNCTIONS = {
    "bitops": ["logand", "logior", "logxor", "ash"],
    "gc": ["gc"],
    "room": ["room"],
    "read-string": ["read-from-string"],
    "restart": ["restart-repl"],
}


CASES = {
    "bitops": [
        {"name": "v11-g-logand-direct", "expr": "(logand 63 42)", "expect": "42"},
        {"name": "v11-g-logand-funcall", "expr": "(funcall (function logand) 63 42)", "expect": "42"},
        {"name": "v11-g-logand-apply", "expr": "(apply (function logand) (list 63 42))", "expect": "42"},
        {"name": "v11-g-logior", "expr": "(logior 40 2)", "expect": "42"},
        {"name": "v11-g-logxor", "expr": "(logxor 43 1)", "expect": "42"},
        {"name": "v11-g-ash-left", "expr": "(ash 21 1)", "expect": "42"},
        {"name": "v11-g-ash-right", "expr": "(ash 84 -1)", "expect": "42"},
        {"name": "v11-g-bitops-negative", "expr": "(logand -1 42)", "expect": "42"},
    ],
    "gc": [
        {"name": "v11-g-gc-direct", "expr": "(gc)", "expect": "t"},
        {"name": "v11-g-gc-funcall", "expr": "(funcall (function gc))", "expect": "t"},
        {"name": "v11-g-gc-apply", "expr": "(apply (function gc) nil)", "expect": "t"},
    ],
    "room": [
        {"name": "v11-g-room-shape", "expr": "(numberp (car (room)))", "expect": "t"},
    ],
    "read-string": [
        {"name": "v11-g-read-from-string-direct", "expr": "(read-from-string \"42\")", "expect": "42"},
        {"name": "v11-g-read-from-string-funcall", "expr": "(funcall (function read-from-string) \"42\")", "expect": "42"},
        {"name": "v11-g-read-from-string-apply", "expr": "(apply (function read-from-string) (list \"42\"))", "expect": "42"},
    ],
    # Executing restart is a hardware acceptance case, not a host observation:
    # the MOS implementation intentionally does not return.
    "restart": [],
}


def _run_base(selftest: bool) -> None:
    argv = [sys.executable, str(BASE)]
    if selftest:
        argv.append("--selftest")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(argv, cwd=ROOT, env=env, check=True)


def _selftest() -> None:
    for variant, forms in FORMS.items():
        for name in FUNCTIONS[variant]:
            if forms.count(f"(defun {name} ") != 1:
                raise ProbeCodemodError(f"{variant}: missing unique {name}")
        if len({row["name"] for row in CASES[variant]}) != len(CASES[variant]):
            raise ProbeCodemodError(f"{variant}: duplicate case name")


def _apply(variant: str) -> None:
    if variant == "baseline":
        return
    EVAL_SOURCE.write_text(
        EVAL_SOURCE.read_text(encoding="utf-8").rstrip() + FORMS[variant] + "\n",
        encoding="utf-8",
    )
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    for name in FUNCTIONS[variant]:
        if name in suite["functions"]:
            raise ProbeCodemodError(f"{variant}: function already present: {name}")
        suite["functions"].append(name)
    # Do not teach the canonical P0 reference VM about the probe-private
    # extension of %c1-control.  read-from-string is the exception: it is a
    # pure composition of already canonical services and can therefore earn
    # direct/funcall/apply observations without changing the model.
    if variant == "read-string":
        suite["cases"].extend(CASES[variant])
    SUITE.write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    selftest = "--selftest" in sys.argv[1:]
    variant = os.environ.get("LISP65_V11_G_VARIANT", "baseline")
    try:
        if variant not in VARIANTS:
            raise ProbeCodemodError(f"unknown variant: {variant}")
        _run_base(selftest)
        _selftest()
        if not selftest:
            _apply(variant)
    except (OSError, ValueError, ProbeCodemodError, subprocess.CalledProcessError) as exc:
        print(f"v11-g-language-polish-codemod: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"v11-g-language-polish-codemod: PASS variant={variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
