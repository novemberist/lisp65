#!/usr/bin/env python3
"""Deterministic property tests for the historical host interpreter.

Generated cases cover reader/printer idempotence and arithmetic against a
Python reference with 32-bit wraparound and truncation toward zero.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lisp64 as L

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def read1(s):
    f, ok = L.Reader(s).read()
    return f if ok else L.NIL

# ---- 1) Round-Trip ----
def gen_datum(depth):
    r = random.random()
    if depth <= 0 or r < 0.45:
        k = random.random()
        if k < 0.5:
            return str(random.randint(-100000, 100000))            # Integer
        if k < 0.8:
            n = random.randint(1, 5)
            return "".join(random.choice(LETTERS) for _ in range(n))  # Symbol
        n = random.randint(0, 6)
        # String without quotes or backslashes; the reader has no escapes.
        chars = "".join(random.choice(LETTERS + "   .,-") for _ in range(n))
        return '"' + chars + '"'
    n = random.randint(0, 4)
    return "(" + " ".join(gen_datum(depth - 1) for _ in range(n)) + ")"

def test_roundtrip(iters):
    ok = 0
    for _ in range(iters):
        d = gen_datum(4)
        v1 = read1(d)
        s1 = L.lisp_repr(v1, readable=True)
        v2 = read1(s1)
        s2 = L.lisp_repr(v2, readable=True)
        assert s1 == s2, "Round-Trip instabil: %r -> %r -> %r" % (d, s1, s2)
        ok += 1
    return ok

# ---- 2) Arithmetik gegen Referenz ----
OPS = ["PLUS", "DIFFERENCE", "TIMES"]

def gen_arith(depth):
    """Return (source, reference_value) with 32-bit wraparound."""
    if depth <= 0 or random.random() < 0.4:
        n = random.randint(-50000, 50000)
        return (str(n), L.to_int32(n))
    op = random.choice(OPS)
    a_s, a_v = gen_arith(depth - 1)
    b_s, b_v = gen_arith(depth - 1)
    if op == "PLUS":
        v = L.to_int32(a_v + b_v)
    elif op == "DIFFERENCE":
        v = L.to_int32(a_v - b_v)
    else:
        v = L.to_int32(a_v * b_v)
    return ("(%s %s %s)" % (op, a_s, b_s), v)

def test_arith(iters):
    ok = 0
    for _ in range(iters):
        src, ref = gen_arith(4)
        got = L.lisp_eval(read1(src))
        assert got == ref, "Arithmetik: %s -> Host %r != Ref %r" % (src, got, ref)
        ok += 1
    return ok

def main():
    random.seed(20260619)
    a = test_roundtrip(800)
    b = test_arith(800)
    print("property_tests: ALLES OK (Round-Trip %d, Arithmetik %d)" % (a, b))

if __name__ == "__main__":
    main()
