#!/usr/bin/env python3
"""Verify the opt-in historical TREEWALK_STRIP M3 profile in xemu.

The profile omits eval_env and routes every form through blob compiler lcc-run.
The harness covers direct REPL forms, definitions, closures, macros, eval from
compiled code, eval-string, GC-root stress, and error recovery. It is not a
product pin.
"""
import importlib.util
import os
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("iv", os.path.join(_here, "xemu-ide-verify.py"))
iv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iv)


def check(mon, prev_len, line, want, wait):
    mon.type_line(line)
    time.sleep(wait)
    scr = iv.screen_text(mon)
    flat = scr[prev_len:].replace(" ", "")
    key = line[-8:].replace(" ", "")
    cut = flat.find(key)
    if cut < 0:                     # gescrollt: ganze Seite, letztes Vorkommen
        flat = scr.replace(" ", "")
        cut = flat.rfind(key)
    zone = flat[cut + len(key):] if cut >= 0 else flat
    ok = want.replace(" ", "") in zone
    print("   %-56s => %s" % (line[:56], "OK" if ok else "FEHLT %r (%r)" % (want, zone[:60])))
    return ok, len(scr.rstrip())


def main():
    keep = "--keep" in sys.argv
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(pos) < 2:
        print(__doc__)
        return 2
    prg, blob = pos[0], pos[1]

    mon, xemu = iv.boot_product(prg, blob)
    ok = []
    try:
        prev = len(iv.screen_text(mon).rstrip())
        print("\n== TREEWALK-STRIP: eval() == lcc-run, kein eval_env gelinkt ==")
        for line, want, wait in [
            ("(+ 1 2)", "3", 3.0),                                    # nackte Form -> compile+run
            ("(- 9 2 3)", "4", 3.0),                                  # VARIADISCH: Arity-Guard -> Bridge (war 7!)
            ("(- 8)", "-8", 3.0),                                     # unary minus bridge (formerly a type error)
            ("(defun sq (x) (* x x))", "sq", 3.5),
            ("(sq 5)", "25", 3.0),
            ("(defun ad (n) (lambda (x) (+ x n)))", "ad", 4.0),       # capturing Factory
            ("(funcall (ad 10) 5)", "15", 3.0),
            ("(defmacro twice (x) (list (quote +) x x))", "twice", 4.5),  # M2-Pfad unter Strip
            ("(twice 21)", "42", 3.5),
            # Pin: eval from compiled code means lcc compiles recursively while vm_run executes;
            # this stresses GC_ROOTS during convergence.
            # native do-Familie (C-Phase Fix b): konstanter Stack — 60 Iterationen
            ("(defun lo (n) (dotimes (i n i)))", "lo", 3.5),
            ("(lo 60)", "60", 4.0),
            ("(setq nq 7)", "7", 3.0),
            ("(quasiquote (a (quasiquote (b (unquote (unquote nq))))))", "unquote 7", 3.5),
            ("(eval (quote (+ 20 3)))", "23", 4.0),   # 23 is unique; a 5 would match lisp65>
            ("(defun mkg () (eval (quote (defun g5 (x) (+ x 5)))))", "mkg", 4.0),
            ("(mkg)", "g5", 4.5),                                     # defun-Compile IN vm_run
            ("(g5 2)", "7", 3.0),
            ("(eval-string \"(sq 7)\")", "49", 4.0),                  # eval-string-Routing
            ("(sq q)", "***", 3.0),                                   # Fehlerpfad
            ("(sq 6)", "36", 3.0),                                    # REPL lebt weiter
        ]:
            r, prev = check(mon, prev, line, want, wait)
            ok.append(r)
    finally:
        iv.stop_xemu(xemu, keep) if hasattr(iv, "stop_xemu") else \
            (not keep and __import__("os").killpg(os.getpgid(xemu.pid), 9))

    n = sum(1 for x in ok if x)
    if all(ok):
        print("\n🎉 M3 ALL PASS (%d/%d) — Ein-Suite OHNE Treewalk: lcc ist der einzige Evaluator" % (n, len(ok)))
        return 0
    print("\nTEILWEISE (%d/%d)" % (n, len(ok)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
