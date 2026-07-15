#!/usr/bin/env python3
"""Historical 16.16 fixed-point bit-layout model.

The 6502-independent model explores reuse of 32-bit add/subtract, shifted
multiply/divide, integer conversion, contagion, reader literals, and printer
output. Division truncates toward zero.
"""

import sys

M = 0xFFFFFFFF
SCALE = 1 << 16        # 16 fractional bits
ULP = 1.0 / SCALE


def s32(x):
    x &= M
    return x - 0x100000000 if x >= 0x80000000 else x

def trunc_div(n, d):
    sign = -1 if (n < 0) != (d < 0) else 1
    return sign * (abs(n) // abs(d))

# --- Konvertierung ---
def from_int(n):
    return s32(n << 16)

def from_float(f):
    return s32(int(round(f * SCALE)))

def to_float(r):
    return r / SCALE

def to_int(r):                 # Fix -> Int, Truncation toward zero
    return trunc_div(r, SCALE)

# --- Arithmetik (alle Ergebnisse 32-bit-gewrappt) ---
def fadd(a, b):                # IDENTISCH zur Integer-Addition (reuse!)
    return s32(a + b)

def fsub(a, b):
    return s32(a - b)

def fneg(a):
    return s32(-a)

def fabs_(a):
    return s32(abs(a))

def fmul(a, b):                # 32x32 -> 64, dann >>16
    return s32(trunc_div(a * b, SCALE))

def fdiv(a, b):                # (a<<16) / b
    return s32(trunc_div(a << 16, b))

def flessp(a, b):
    return a < b

def feq(a, b):
    return a == b

# --- Reader: token -> ('INT', n) or ('FIX', raw) ---
def parse_number(tok):
    t, neg = tok, False
    if t[:1] in "+-":
        neg = t[0] == "-"; t = t[1:]
    if "." in t:
        ip, fp = t.split(".", 1)
        ip = ip or "0"
        ival = int(ip) if ip else 0
        fval = int(round(int(fp) / (10 ** len(fp)) * SCALE)) if fp else 0
        raw = (ival << 16) + fval
        return ("FIX", s32(-raw if neg else raw))
    n = int(t)
    return ("INT", -n if neg else n)

# --- Printer: 16.16 -> Dezimalstring ---
def fmt_fix(raw, digits=5):
    neg = raw < 0
    mag = -raw if neg else raw
    ip = mag >> 16
    frac = mag & 0xFFFF
    ds = []
    for _ in range(digits):
        frac *= 10
        ds.append(str(frac >> 16))
        frac &= 0xFFFF
    s = "".join(ds).rstrip("0") or "0"
    return ("-" if neg else "") + f"{ip}.{s}"

# --- Kontagion Int<->Fix ---
def promote(a, b):
    if a[0] == "FIX" or b[0] == "FIX":
        ra = a[1] if a[0] == "FIX" else from_int(a[1])
        rb = b[1] if b[0] == "FIX" else from_int(b[1])
        return "FIX", ra, rb
    return "INT", a[1], b[1]

def add_tagged(a, b):
    dom, ra, rb = promote(a, b)
    if dom == "INT":
        return ("INT", ra + rb)
    return ("FIX", fadd(ra, rb))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def report(label, ok):
    print(f"  [{'OK ' if ok else 'XX '}] {label}")
    return ok

def approx(raw, expected):
    return abs(to_float(raw) - expected) <= ULP + 1e-12

def main():
    allok = True

    print("== 1. Repräsentation & Konvertierung ==")
    allok &= report("from_int(1) = $00010000", from_int(1) == 0x10000)
    allok &= report("from_float(1.5) = $00018000", from_float(1.5) == 0x18000)
    allok &= report("to_float(from_int(3)) = 3.0", to_float(from_int(3)) == 3.0)
    allok &= report("to_int(from_float(3.9)) = 3 (trunc)", to_int(from_float(3.9)) == 3)
    allok &= report("to_int(from_float(-3.9)) = -3 (trunc toward 0)",
                    to_int(from_float(-3.9)) == -3)

    print("\n== 2. Reader (Literal -> 16.16) ==")
    allok &= report('"1.5"  -> FIX 1.5', parse_number("1.5") == ("FIX", 0x18000))
    allok &= report('".5"   -> FIX 0.5', parse_number(".5") == ("FIX", 0x8000))
    allok &= report('"-0.25"-> FIX -0.25', approx(parse_number("-0.25")[1], -0.25))
    allok &= report('"3"    -> INT 3', parse_number("3") == ("INT", 3))
    allok &= report('"0.1"  -> innerhalb 1 ULP', approx(parse_number("0.1")[1], 0.1))

    print("\n== 3. Printer (16.16 -> String) ==")
    allok &= report("fmt(1.5) = '1.5'", fmt_fix(0x18000) == "1.5")
    allok &= report("fmt(from_int(2)) = '2.0'", fmt_fix(from_int(2)) == "2.0")
    allok &= report("fmt(-0.25) = '-0.25'", fmt_fix(from_float(-0.25)) == "-0.25")
    allok &= report("roundtrip parse(fmt(x)) ~ x",
                    approx(parse_number(fmt_fix(from_float(3.14159)))[1], 3.14159))

    print("\n== 4. Arithmetik ==")
    allok &= report("Add ist Integer-Add: fadd == s32(a+b)",
                    fadd(from_float(1.5), from_float(2.25)) == s32(from_float(1.5) + from_float(2.25)))
    allok &= report("1.5 + 2.25 = 3.75", approx(fadd(from_float(1.5), from_float(2.25)), 3.75))
    allok &= report("1.0 - 0.25 = 0.75", approx(fsub(from_int(1), from_float(0.25)), 0.75))
    allok &= report("1.5 * 2.0 = 3.0", approx(fmul(from_float(1.5), from_int(2)), 3.0))
    allok &= report("0.5 * 0.5 = 0.25", approx(fmul(from_float(0.5), from_float(0.5)), 0.25))
    allok &= report("-1.5 * 2 = -3.0", approx(fmul(from_float(-1.5), from_int(2)), -3.0))
    allok &= report("7.0 / 2.0 = 3.5", approx(fdiv(from_int(7), from_int(2)), 3.5))
    allok &= report("1.0 / 4.0 = 0.25", approx(fdiv(from_int(1), from_int(4)), 0.25))
    allok &= report("1.0 / 3.0 ~ 0.33333 (trunc)", approx(fdiv(from_int(1), from_int(3)), 1/3))

    print("\n== 5. Vergleiche & Kontagion ==")
    allok &= report("1.5 < 2.25", flessp(from_float(1.5), from_float(2.25)))
    allok &= report("nicht 2.0 < 2.0", not flessp(from_int(2), from_float(2.0)))
    dom, val = add_tagged(("INT", 2), ("FIX", from_float(1.5)))
    allok &= report(f"INT 2 + FIX 1.5 -> {dom} {fmt_fix(val) if dom=='FIX' else val}",
                    dom == "FIX" and approx(val, 3.5))

    print("\n== 6. Grenzen (16.16) ==")
    allok &= report("Bereich ~ +-32768; from_int(32767) ok",
                    to_float(from_int(32767)) == 32767.0)
    allok &= report("from_int(40000) wrappt (out of range, dokumentiert)",
                    to_float(from_int(40000)) != 40000.0)

    print()
    print("ERGEBNIS:", "ALLES OK" if allok else "FEHLER")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
