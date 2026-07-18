#!/usr/bin/env python3
"""Materialize bounded 1.1-M transactional-FASL probe variants.

This is deliberately a probe-only layer over the sealed Wave-1 C1 codemod.
It never edits canonical Lisp sources.  The selected variant is taken from
``LISP65_V11_M_VARIANT``:

``baseline``
    The unmodified Wave-1 product.
``composition``
    Extend ``m65d-save`` to accept a detached Buffer and route
    ``compile-string`` through the existing M65D transaction.
``dedicated``
    Add a separate, named ``m65d-save-buffer`` entry with the same transaction
    implementation and route ``compile-string`` through that entry.

Both candidates retire the historical preallocated-slot writer.  Keeping the
transaction implementation identical makes the comparison answer the actual
architecture question: extend the existing public seam, or publish another
one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LEASE = ROOT / "tools" / "host-lisp" / "v11_c1_lease_codemod.py"
GENERATED = ROOT / "build" / "bytecode" / "dialect-v2"
EVAL_SOURCE = GENERATED / "sources" / "lib" / "dialect-v2" / "eval-runtime.lisp"
M65D_SOURCE = GENERATED / "sources" / "lib" / "m65-disk.lisp"
RESIDENT_SUITE = GENERATED / "suites" / "p0-stdlib-einsuite-core-workbench-subset.json"
M65D_SUITE = GENERATED / "suites" / "p0-m65d-lib.json"
VARIANTS = {"baseline", "composition", "dedicated"}

LEGACY_SLOT_FUNCTIONS = {
    "%compile-slot-scan-entries",
    "%compile-slot-find",
    "%compile-slot-capacity",
    "%c1-slot-link-valid-p",
    "%fasl-save-sector",
    "%fasl-save-tail",
    "%fasl-commit-first",
    "%fasl-save-from-first",
    "%fasl-save-staged-v2",
}
LEGACY_SLOT_CASES = {
    "workbench-c1-slot-link-valid-tail",
    "workbench-c1-slot-link-rejects-zero-tail",
    "workbench-c1-slot-link-rejects-self-reference",
    "workbench-c1-slot-link-rejects-out-of-range",
    "workbench-compile-string-missing-slot",
    "workbench-compile-string-missing-slot-error",
    "workbench-compile-slot-capacity-host",
}


class ProbeCodemodError(RuntimeError):
    pass


def _run_lease(selftest: bool = False) -> None:
    argv = [sys.executable, str(LEASE)]
    if selftest:
        argv.append("--selftest")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(argv, cwd=ROOT, env=env, check=True)


def _skip_string(text: str, at: int) -> int:
    at += 1
    while at < len(text):
        if text[at] == "\\":
            at += 2
        elif text[at] == '"':
            return at + 1
        else:
            at += 1
    raise ProbeCodemodError("unterminated Lisp string")


def _skip_block_comment(text: str, at: int) -> int:
    depth = 1
    at += 2
    while at < len(text):
        if text.startswith("#|", at):
            depth += 1
            at += 2
        elif text.startswith("|#", at):
            depth -= 1
            at += 2
            if depth == 0:
                return at
        else:
            at += 1
    raise ProbeCodemodError("unterminated Lisp block comment")


def _form_end(text: str, start: int) -> int:
    if start >= len(text) or text[start] != "(":
        raise ProbeCodemodError("top-level form does not start with '('")
    depth = 0
    at = start
    while at < len(text):
        if text[at] == '"':
            at = _skip_string(text, at)
            continue
        if text[at] == ";":
            newline = text.find("\n", at)
            at = len(text) if newline < 0 else newline + 1
            continue
        if text.startswith("#|", at):
            at = _skip_block_comment(text, at)
            continue
        if text[at] == "(":
            depth += 1
        elif text[at] == ")":
            depth -= 1
            if depth == 0:
                return at + 1
        at += 1
    raise ProbeCodemodError("unterminated top-level form")


def _defun_span(text: str, name: str) -> tuple[int, int]:
    needle = f"(defun {name} "
    starts: list[int] = []
    at = 0
    while True:
        found = text.find(needle, at)
        if found < 0:
            break
        starts.append(found)
        at = found + len(needle)
    if len(starts) != 1:
        raise ProbeCodemodError(
            f"{name}: expected exactly one generated definition, found {len(starts)}"
        )
    return starts[0], _form_end(text, starts[0])


def _replace_defun(text: str, name: str, replacement: str | None) -> str:
    start, end = _defun_span(text, name)
    if replacement is None:
        while end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + text[end:]
    return text[:start] + replacement.rstrip() + text[end:]


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeCodemodError(f"{path}: JSON root must be an object")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _transform_eval(source: str, entry: str) -> str:
    for name in sorted(LEGACY_SLOT_FUNCTIONS):
        source = _replace_defun(source, name, None)
    compile_save = f'''(defun %c1-compile-save (source dst)
  (let ((output (%c1-compile-detached 1 source nil)))
    (if (%buffer-read 0 output)
        (let ((saved ({entry} dst output)))
          (if (= saved 0)
              (progn (set-symbol-value (quote %compile-error) nil) 't)
              (if (= saved 3)
                  (progn (set-symbol-value (quote %compile-error) "too large") nil)
                  (progn (set-symbol-value (quote %compile-error) "save failed") nil))))
        (progn (set-symbol-value (quote %compile-error) "compile failed") nil))))'''
    compile_string = '''(defun compile-string (source dst)
  (progn
    (set-symbol-value (quote %compile-error) nil)
    (if (stringp source)
        (if (stringp dst)
            (%c1-compile-save source dst)
            (progn (set-symbol-value (quote %compile-error) "bad destination") nil))
        (progn (set-symbol-value (quote %compile-error) "bad source") nil))))'''
    source = _replace_defun(source, "%c1-compile-save", compile_save)
    return _replace_defun(source, "compile-string", compile_string)


def _transform_m65d(source: str, variant: str) -> str:
    copy = '''(defun %m65d-copy (src pos count buffer)
  (dotimes (i count t)
    (%disk-poke (+ i 2)
                (if buffer
                    (%fasl-stage-get (+ pos i))
                    (string-ref src (+ pos i))))))'''
    write_chain = '''(defun %m65d-write-chain (src len chain pos buffer)
  (if chain
      (let ((pair (car chain))
            (rest (cdr chain)))
        (let ((count (if rest 254 (- len pos))))
          (if (%m65d-before-write nil nil)
              (progn
                (%m65d-clear)
                (if rest
                    (progn
                      (%disk-poke 0 (car (car rest)))
                      (%disk-poke 1 (cdr (car rest))))
                    (progn (%disk-poke 0 0) (%disk-poke 1 (+ count 1))))
                (%m65d-copy src pos count buffer)
                (if (%m65d-before-write (car pair) (cdr pair))
                    (%m65d-write-chain src len rest (+ pos count) buffer)
                    nil))
              nil)))
      t))'''
    write_plan = '''(defun %m65d-write-plan (record name src len blocks old buffer)
  (let ((chain (%m65d-find-new-chain blocks)))
    (if chain
        (if (%m65d-write-chain src len chain 0 buffer)
            (if (%m65d-claim-new chain)
                (if (%m65d-commit-dir record name (car chain) blocks)
                    (if (if (= (car record) 1)
                            (%m65d-release-old old)
                            t)
                        (%m65d-set 0 nil)
                        (%m65d-set 9 t))
                    (m65d-status))
                (m65d-status))
            (m65d-status))
        (if (= (m65d-status) 6) 6 (%m65d-set 4 nil)))))'''
    run_record = '''(defun %m65d-run-record (record name src len new-only buffer)
  (if (if new-only (= (car record) 1) nil)
      (%m65d-set 2 nil)
      (let ((blocks (%m65d-blocks-for len 0))
            (old (%m65d-old-plan record)))
        (if (if (= (car record) 1) (not old) nil)
            (m65d-status)
            (%m65d-write-plan record name src len blocks old buffer)))))'''
    run_source = '''(defun %m65d-run-source (name src new-only buffer)
  (let ((len (if buffer (%buffer-alloc 3 src) (string-length src))))
    (if (< len 1)
        (%m65d-set 3 nil)
        (if (> len 8192)
            (%m65d-set 3 nil)
            (let ((record (%m65d-find-dir name)))
              (if record
                  (%m65d-run-record record name src len new-only buffer)
                  (if (= (m65d-status) 6) 6 (%m65d-set 5 nil))))))))'''
    run_authorized = '''(defun %m65d-run-authorized (name src new-only)
  (if (%m65d-name-ok-p name)
      (let ((buffer (not (stringp src))))
        (if (if buffer (%buffer-read 0 src) t)
            (%m65d-run-source name src new-only buffer)
            (%m65d-set 3 nil)))
      (%m65d-set 1 nil)))'''
    for name, replacement in (
        ("%m65d-copy", copy),
        ("%m65d-write-chain", write_chain),
        ("%m65d-write-plan", write_plan),
        ("%m65d-run-record", run_record),
        ("%m65d-run-source", run_source),
        ("%m65d-run-authorized", run_authorized),
    ):
        source = _replace_defun(source, name, replacement)

    if variant == "composition":
        save = '''(defun m65d-save (name src)
  (%m65d-run name src nil))'''
    else:
        save = '''(defun m65d-save (name src)
  (if (stringp src) (%m65d-run name src nil) (%m65d-set 3 nil)))

(defun m65d-save-buffer (name src)
  (if (%buffer-read 0 src) (%m65d-run name src nil) (%m65d-set 3 nil)))'''
    source = _replace_defun(source, "m65d-save", save)
    save_new = '''(defun m65d-save-new (name src)
  (if (stringp src) (%m65d-run name src t) (%m65d-set 3 nil)))'''
    return _replace_defun(source, "m65d-save-new", save_new)


def _transform_suites(variant: str) -> None:
    resident = _load_object(RESIDENT_SUITE)
    resident["functions"] = [
        name for name in resident.get("functions", [])
        if name not in LEGACY_SLOT_FUNCTIONS
    ]
    resident["cases"] = [
        case for case in resident.get("cases", [])
        if case.get("name") not in LEGACY_SLOT_CASES
    ]
    resident["cases"].extend([
        {
            "name": "workbench-compile-string-bad-destination",
            "expr": "(compile-string \"(defun x () 1)\" 7)",
            "expect": "nil",
        },
        {
            "name": "workbench-compile-string-bad-destination-error",
            "expr": "(progn (compile-string \"(defun x () 1)\" 7) (compile-error))",
            "expect": "\"bad destination\"",
        },
    ])
    _write_object(RESIDENT_SUITE, resident)

    m65d = _load_object(M65D_SUITE)
    # The historical string-only source runner was just small enough to inline
    # into the authorization function.  Adding Buffer classification crosses
    # the bytecode rel8 branch range.  Keep one anonymous internal entry
    # instead of weakening the compiler limit or duplicating the transaction.
    private_inline = m65d.get("private_inline_functions")
    if not isinstance(private_inline, list) or "%m65d-run-source" not in private_inline:
        raise ProbeCodemodError("generated M65D private-inline inventory drift")
    m65d["private_inline_functions"] = [
        name for name in private_inline if name != "%m65d-run-source"
    ]
    m65d["min_private_inline_functions"] = len(m65d["private_inline_functions"])
    entry = "m65d-save" if variant == "composition" else "m65d-save-buffer"
    if variant == "dedicated":
        functions = m65d.get("functions")
        if not isinstance(functions, list) or "m65d-save" not in functions:
            raise ProbeCodemodError("generated M65D suite function inventory drift")
        functions.insert(functions.index("m65d-save") + 1, "m65d-save-buffer")
    m65d["cases"].extend([
        {
            "name": f"m65d-buffer-payload-{variant}-external",
            "expr": (
                "(let ((b (%buffer-alloc 0 3))) "
                f"(progn (%buffer-write b 0 97) (%buffer-write b 1 98) "
                f"(%buffer-write b 2 99) (set-symbol-value (quote m65d-remount) nil) "
                f"({entry} \"bufsave\" b)))"
            ),
            "expect": "0",
            "max_steps": 700000,
            "disk_files": {},
            "external_d81_oracle": {
                "name": "bufsave",
                "content": "abc",
                "expected_blocks": 1,
            },
        },
        {
            "name": f"m65d-buffer-payload-{variant}-bad-type",
            "expr": (
                "(progn (set-symbol-value (quote m65d-remount) nil) "
                f"({entry} \"bufsave\" 42))"
            ),
            "expect": "3",
        },
    ])
    _write_object(M65D_SUITE, m65d)


def materialize(variant: str) -> None:
    if variant not in VARIANTS:
        raise ProbeCodemodError(f"unknown 1.1-M variant: {variant}")
    _run_lease(False)
    if variant == "baseline":
        return
    entry = "m65d-save" if variant == "composition" else "m65d-save-buffer"
    EVAL_SOURCE.write_text(
        _transform_eval(EVAL_SOURCE.read_text(encoding="utf-8"), entry),
        encoding="utf-8",
    )
    M65D_SOURCE.write_text(
        _transform_m65d(M65D_SOURCE.read_text(encoding="utf-8"), variant),
        encoding="utf-8",
    )
    _transform_suites(variant)


def selftest() -> None:
    _run_lease(True)
    materialize("composition")
    composition_eval = EVAL_SOURCE.read_text(encoding="utf-8")
    composition_m65d = M65D_SOURCE.read_text(encoding="utf-8")
    if any(f"(defun {name} " in composition_eval for name in LEGACY_SLOT_FUNCTIONS):
        raise ProbeCodemodError("composition retained a legacy slot definition")
    if "(m65d-save dst output)" not in composition_eval:
        raise ProbeCodemodError("composition compiler route drift")
    if "(%fasl-stage-get (+ pos i))" not in composition_m65d:
        raise ProbeCodemodError("composition staged-buffer copy drift")
    materialize("dedicated")
    dedicated_eval = EVAL_SOURCE.read_text(encoding="utf-8")
    dedicated_m65d = M65D_SOURCE.read_text(encoding="utf-8")
    dedicated_suite = _load_object(M65D_SUITE)
    if "(m65d-save-buffer dst output)" not in dedicated_eval:
        raise ProbeCodemodError("dedicated compiler route drift")
    if dedicated_m65d.count("(defun m65d-save-buffer ") != 1:
        raise ProbeCodemodError("dedicated entry definition drift")
    if dedicated_suite.get("functions", []).count("m65d-save-buffer") != 1:
        raise ProbeCodemodError("dedicated entry publication drift")


def main() -> int:
    try:
        if "--selftest" in sys.argv[1:]:
            if sys.argv[1:] != ["--selftest"]:
                raise ProbeCodemodError("only --selftest is accepted")
            selftest()
            print("v11-m-transactional-fasl-codemod: SELFTEST PASS variants=2")
            return 0
        if sys.argv[1:]:
            raise ProbeCodemodError("this codemod takes no positional arguments")
        variant = os.environ.get("LISP65_V11_M_VARIANT", "composition")
        materialize(variant)
    except (OSError, ValueError, json.JSONDecodeError, ProbeCodemodError,
            subprocess.CalledProcessError) as exc:
        print(f"v11-m-transactional-fasl-codemod: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"v11-m-transactional-fasl-codemod: PASS variant={variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
