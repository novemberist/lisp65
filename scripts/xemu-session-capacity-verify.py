#!/usr/bin/env python3
"""Verify persistent single-boot session capacity in xemu.

The gate protects the trailer-reclaim and VM_DIR_MAX=512 capacity fix by
installing many definitions and evaluating intermediate calls in one session.
Usage: xemu-session-capacity-verify.py <prg> <blob> [N] [--keep]. The default
is 14 definitions with one call after each definition.
"""
import importlib.util
import os
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("iv", os.path.join(_here, "xemu-ide-verify.py"))
iv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iv)


def check(mon, prev_len, line, want, wait=3.2):
    mon.type_line(line)
    time.sleep(wait)
    scr = iv.screen_text(mon)
    flat = scr[prev_len:].replace(" ", "")
    key = line[-8:].replace(" ", "")
    cut = flat.find(key)
    if cut < 0:
        flat = scr.replace(" ", "")
        cut = flat.rfind(key)
    zone = flat[cut + len(key):] if cut >= 0 else flat
    ok = want.replace(" ", "") in zone
    if not ok:
        print("   %-40s => FEHLT %r (%r)" % (line[:40], want, zone[:60]))
    return ok, len(scr.rstrip())


def main():
    keep = "--keep" in sys.argv
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(pos) < 2:
        print(__doc__)
        return 2
    prg, blob = pos[0], pos[1]
    n = int(pos[2]) if len(pos) > 2 else 14

    mon, xemu = iv.boot_product(prg, blob)
    ok = []
    try:
        prev = len(iv.screen_text(mon).rstrip())
        print("== Session-Kapazität: %d defuns + Aufrufe in EINEM Boot ==" % n)
        for i in range(1, n + 1):
            r1, prev = check(mon, prev, "(defun f%d (x) (+ x %d))" % (i, i), "f%d" % i, 3.6)
            r2, prev = check(mon, prev, "(f%d 100)" % i, str(100 + i), 3.0)
            ok.append(r1 and r2)
            print("   defun f%-2d + Aufruf => %s" % (i, "OK" if ok[-1] else "FEHLER"))
            if not ok[-1]:
                break
        if all(ok) and len(ok) == n:   # An early definition must still work at the end.
            r, prev = check(mon, prev, "(f1 41)", "42", 3.0)
            ok.append(r)
            print("   f1 lebt am Session-Ende      => %s" % ("OK" if r else "FEHLER"))
    finally:
        iv.stop_xemu(xemu, keep) if hasattr(iv, "stop_xemu") else \
            (not keep and __import__("os").killpg(os.getpgid(xemu.pid), 9))

    good = sum(1 for x in ok if x)
    if all(ok) and len(ok) == n + 1:
        print("\n🎉 KAPAZITÄT PASS — %d defuns + Aufrufe, Region+Dir halten" % n)
        return 0
    print("\nKAPAZITÄT: nach %d/%d defuns erschöpft" % (good, n))
    return 1


if __name__ == "__main__":
    sys.exit(main())
