#!/usr/bin/env python3
"""Scripted transcript tests for the historical REPL and break loop.

The suite drives L.repl() through captured stdin/stdout and covers normal
evaluation, error inspection and abort back to top level, and top-level
CATCH/THROW.
"""
import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lisp64 as L

def run_repl(script):
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(script)
    sys.stdout = io.StringIO()
    try:
        L.repl()
        return sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = old_in, old_out

def must(out, needle):
    assert needle in out, "missing from transcript: %r\n--- transcript ---\n%s" % (needle, out)

def main():
    ok = 0

    # 1) Normal evaluation.
    out = run_repl("(PLUS 1 2)\n")
    must(out, "3"); ok += 1

    # 2) Error -> break loop -> inspect -> abort -> top level.
    out = run_repl("(PLUS 1 2)\n(ERROR \"boom\")\n(PLUS 10 20)\n\n(PLUS 100 1)\n")
    must(out, "3"); ok += 1                              # first top-level evaluation
    must(out, "Break"); ok += 1                          # entered break loop
    must(out, "boom"); ok += 1                           # condition message
    must(out, "30"); ok += 1                             # evaluation inside break loop
    must(out, "Top-Level"); ok += 1                      # aborted back to top level
    must(out, "101"); ok += 1                            # normal evaluation resumes

    # 3) An internal unbound error also enters the break loop.
    out = run_repl("NICHTGEBUNDEN\n\n")
    must(out, "Break"); ok += 1

    # 4) Top-level CATCH/THROW returns 42 without a break loop.
    out = run_repl("(CATCH (QUOTE TAG) (THROW (QUOTE TAG) 42))\n")
    must(out, "42"); ok += 1
    assert "Break" not in out, out; ok += 1

    print("repl_test: ALLES OK (%d Asserts)" % ok)

if __name__ == "__main__":
    main()
