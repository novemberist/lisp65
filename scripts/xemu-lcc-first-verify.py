#!/usr/bin/env python3
"""Verify the historical lcc-first M1 convergence profile in xemu.

Raw user forms run through blob compiler lcc on vm_run without an lcc-run
wrapper. The ad-hoc M1 PRG is intentionally not a product pin.
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
    print("   %-52s => %s" % (line[:52], "OK" if ok else "FEHLT %r (%r)" % (want, zone[:60])))
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
        print("\n== lcc-first-REPL: nackte Formen laufen durch den Blob-Compiler ==")
        for line, want, wait in [
            ("(+ 1 2)", "3", 3.0),                                    # Ausdruck -> compile+run
            ("(defun sq (x) (* x x))", "sq", 3.5),                    # NACKTES defun -> lcc
            ("(sq 5)", "25", 3.0),
            ("(defun dn (n) (if (< n 1) 7 (dn (- n 1))))", "dn", 3.5),
            ("(dn 9)", "7", 3.0),
            ("(defun ad (n) (lambda (x) (+ x n)))", "ad", 4.0),       # capturing factory
            ("(funcall (ad 10) 5)", "15", 3.0),
            ("(sq q)", "***", 3.0),                                   # error path aborts cleanly
            ("(sq 6)", "36", 3.0),                                    # REPL remains usable
            # M2: defmacro without eval_env. lcc compiles the expander, installs it as a BCODE
            # macro through %set-macro, then compiles a form immediately.
            # The next form uses the macro through macroexpand-1 and funcall on BCODE.
            ("(defmacro twice (x) (list (quote +) x x))", "twice", 4.5),
            ("(twice 21)", "42", 3.5),
            ("(defun tws (x) (twice (* x x)))", "tws", 4.0),          # macro inside compiled defun
            ("(tws 4)", "32", 3.0),
        ]:
            r, prev = check(mon, prev, line, want, wait)
            ok.append(r)
    finally:
        iv.stop_xemu(xemu, keep) if hasattr(iv, "stop_xemu") else \
            (not keep and __import__("os").killpg(os.getpgid(xemu.pid), 9))

    n = sum(1 for x in ok if x)
    if all(ok):
        print("\n🎉 M1+M2 ALL PASS (%d/%d) — lcc-first-REPL inkl. BCODE-defmacro ohne eval_env" % (n, len(ok)))
        return 0
    print("\nTEILWEISE (%d/%d)" % (n, len(ok)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
