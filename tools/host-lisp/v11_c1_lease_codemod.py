#!/usr/bin/env python3
"""Canonical C1 lease transform layered over the base v2 codemod.

The canonical Lisp sources remain untouched. This wrapper first regenerates
the ordinary build tree and then changes only generated product copies. The
same transform was priced and accepted as the hardware probe-11 candidate.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tools/host-lisp/v2_workbench_codemod.py"
GENERATED = ROOT / "build/bytecode/dialect-v2/sources"


class LeaseCodemodError(RuntimeError):
    pass


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise LeaseCodemodError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def transform_eval(source: str) -> str:
    old_compile = '''  (if (%c1-control 0 (quote %c1-compile))
      (if (%disk-load-lib "lcc")
          (if (%c1-control 1 nil)
              (%c1-control 2 (%c1-compile mode first second))
              (progn (%c1-control 2 nil) nil))
          (progn (%c1-control 2 nil) nil))
      nil))
'''
    new_compile = '''  (if (eq (function-kind (quote %c1-compile)) (quote bytecode))
      (let ((compiled (%c1-compile mode first second)))
        (if compiled compiled (progn (%c1-control 2 nil) nil)))
      (if (%c1-control 0 (quote %c1-compile))
          (if (%disk-load-lib "lcc")
              (if (%c1-control 1 nil)
                  (let ((compiled (%c1-compile mode first second)))
                    (if compiled compiled (progn (%c1-control 2 nil) nil)))
                  (progn (%c1-control 2 nil) nil))
              (progn (%c1-control 2 nil) nil))
          nil)))
'''
    source = replace_once(source, old_compile, new_compile, "compiler-tier reuse")
    old = """(defun lcc-run (form)
  (let ((compiled (%c1-compile-detached 0 form nil)))
    (cond ((if (consp form) (eq (car form) 'defmacro) nil)
           (%set-macro (car (cdr form)) (lcc-install compiled nil)))
          ((if (consp form) (eq (car form) 'defun) nil)
           (lcc-install compiled (car (cdr form))))
          (t (lcc-install compiled 't)))))
"""
    new = """(defun lcc-run (form)
  (let ((compiled (%c1-compile-detached 0 form nil)))
    (cond ((if (consp form) (eq (car form) 'defmacro) nil)
           (progn
             (%c1-control 2 nil)
             (%set-macro (car (cdr form)) (lcc-install compiled nil))))
          ((if (consp form) (eq (car form) 'defun) nil)
           (progn
             (%c1-control 2 nil)
             (lcc-install compiled (car (cdr form)))))
          (t (if (cdr compiled)
                 (progn (%c1-control 2 nil) (lcc-install compiled 't))
                 (lcc-install compiled 't))))))
"""
    return replace_once(source, old, new, "retire before persistent install")


def transform_load_lib(source: str) -> str:
    start = source.find("(defun load-lib (name)\n")
    end_marker = "\n(defun %load-libs-seq (names)\n"
    end = source.find(end_marker, start)
    if start < 0 or end < 0:
        raise LeaseCodemodError("foreign library retirement: function anchor missing")
    comment_start = source.rfind("\n\n;", start, end)
    if comment_start >= start:
        end = comment_start
    original = source[start:end]
    if original.count("(defun load-lib (name)") != 1:
        raise LeaseCodemodError("foreign library retirement: ambiguous function")
    first, rest = original.split("\n", 1)
    indented = "\n".join("  " + line for line in rest.splitlines())
    replacement = (
        first + "\n  (progn\n"
        "    ; A foreign library may append persistent Bank-5 code. Retirement\n"
        "    ; is the last operation before the ordinary loader can append.\n"
        "    (%c1-control 2 nil)\n" + indented + ")"
    )
    return source[:start] + replacement + source[end:]


def validate_c2_profile(eval_source: str, load_source: str) -> None:
    """C2 retires the C1 lease rather than transforming it in generated code."""
    forbidden = (
        "%c1-control",
        "%c1-compile",
        '(%disk-load-lib "lcc")',
    )
    combined = eval_source + "\n" + load_source
    present = [item for item in forbidden if item in combined]
    if present:
        raise LeaseCodemodError(
            "mixed C1/C2 generated profile: " + ", ".join(present))
    required = (
        "(defun lcc-run (form)",
        "(%c2-control 0 nil)",
        "(%c2-control 1",
        "(%c2-control 2 nil)",
        "(defun %c2-compile-source (source)",
    )
    missing = [item for item in required if item not in eval_source]
    if missing:
        raise LeaseCodemodError(
            "C2 single-emitter profile missing: " + ", ".join(missing))
    if eval_source.count("(defun lcc-run (form)") != 1:
        raise LeaseCodemodError("C2 lcc-run entry is not single-source")


def run_base(selftest: bool) -> None:
    command = [sys.executable, str(BASE)]
    if selftest:
        command.append("--selftest")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def selftest() -> None:
    eval_fixture = '''(defun %c1-compile-detached (mode first second)
  (if (%c1-control 0 (quote %c1-compile))
      (if (%disk-load-lib "lcc")
          (if (%c1-control 1 nil)
              (%c1-control 2 (%c1-compile mode first second))
              (progn (%c1-control 2 nil) nil))
          (progn (%c1-control 2 nil) nil))
      nil))

(defun lcc-run (form)
  (let ((compiled (%c1-compile-detached 0 form nil)))
    (cond ((if (consp form) (eq (car form) 'defmacro) nil)
           (%set-macro (car (cdr form)) (lcc-install compiled nil)))
          ((if (consp form) (eq (car form) 'defun) nil)
           (lcc-install compiled (car (cdr form))))
          (t (lcc-install compiled 't)))))
'''
    transformed = transform_eval(eval_fixture)
    if transformed.count("(function-kind (quote %c1-compile))") != 1 or \
            transformed.count("(%c1-control 2 nil)") != 7:
        raise LeaseCodemodError("eval transformation selftest failed")
    load_path = ROOT / "lib/stdlib-load-lib.lisp"
    transformed_load = transform_load_lib(load_path.read_text(encoding="utf-8"))
    if transformed_load.count("(%c1-control 2 nil)") != 1:
        raise LeaseCodemodError("load-lib transformation selftest failed")
    c2_fixture = '''(defun lcc-run (form) (%c2-compile-form form))
(defun %c2-compile-source (source)
  (if (%c2-control 0 nil)
      (%c2-control 1 source)
      (%c2-control 2 nil)))
'''
    validate_c2_profile(c2_fixture, "(defun load-lib (name) name)\n")
    try:
        validate_c2_profile(
            c2_fixture + "(%c1-control 2 nil)\n",
            "(defun load-lib (name) name)\n",
        )
    except LeaseCodemodError:
        pass
    else:
        raise LeaseCodemodError("mixed C1/C2 profile mutation was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            run_base(True)
            selftest()
            print("v11-c1-lease-codemod: SELFTEST PASS")
            return 0
        run_base(False)
        eval_path = GENERATED / "lib/dialect-v2/eval-runtime.lisp"
        load_path = GENERATED / "lib/stdlib-load-lib.lisp"
        eval_source = eval_path.read_text(encoding="utf-8")
        load_source = load_path.read_text(encoding="utf-8")
        if "%c2-control" in eval_source:
            validate_c2_profile(eval_source, load_source)
            print("v11-c1-lease-codemod: PASS profile=c2-single-emitter generated-probe-sources=0")
            return 0
        transformed_eval = transform_eval(eval_source)
        eval_path.write_text(transformed_eval, encoding="utf-8")
        load_path.write_text(transform_load_lib(load_source), encoding="utf-8")
    except (LeaseCodemodError, OSError, subprocess.CalledProcessError) as exc:
        print(f"v11-c1-lease-codemod: FAIL: {exc}")
        return 1
    print("v11-c1-lease-codemod: PASS generated-probe-sources=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
