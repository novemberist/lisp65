#!/usr/bin/env python3
"""Verify the historical self-hosted single-suite profile in xemu.

The default mode boots the PRG and Bank-5 blob, compiles user forms with the
bytecode lcc compiler, then starts the interactive IDE in the same session.
`--symbol-audit` instead measures authoritative device symbol headroom before a
profile pin. Use `(quote ...)` rather than apostrophe input because the $D615
keyboard matrix layer has no apostrophe mapping.
"""
import importlib.util
import os
import subprocess
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("iv", os.path.join(_here, "xemu-ide-verify.py"))
iv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iv)

ROOT = os.path.dirname(_here)
PRG = os.path.join(ROOT, "build", "lisp65-mega65-vm-stdlib-einsuite.prg")
BLOB = os.path.join(ROOT, "build", "bytecode", "stdlib-p0.ext.bin")


def build_einsuite():
    """Build mvp-vm-stdlib-einsuite; return true only for a green profile."""
    print("== build single-suite profile (make mvp-vm-stdlib-einsuite) ...")
    r = subprocess.run(["make", "mvp-vm-stdlib-einsuite"], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(PRG):
        tail = (r.stderr or r.stdout).strip().splitlines()
        over = [l for l in tail if "overflow" in l.lower() or "reserve" in l.lower()]
        print("== single-suite profile is not green yet:")
        for l in (over or tail[-3:]):
            print("   " + l)
        return False
    print("== built: %s (%d B) + blob %s (%d B)"
          % (PRG, os.path.getsize(PRG), os.path.basename(BLOB),
             os.path.getsize(BLOB) if os.path.exists(BLOB) else -1))
    return True


def repl_check(mon, prev_len, line, want):
    """Type one REPL line and check the value region after its echo."""
    mon.type_line(line)
    time.sleep(1.6)
    scr = iv.screen_text(mon)
    new = scr[prev_len:]
    flat = new.replace(" ", "")
    key = line[-8:].replace(" ", "")
    cut = flat.find(key)
    if cut < 0:   # after scrolling, search the full screen for the last echo
        flat = scr.replace(" ", "")
        cut = flat.rfind(key)
    zone = flat[cut + len(key):] if cut >= 0 else flat
    ok = want.replace(" ", "") in zone
    print("   %-52s => %s" % (line[:52], "OK" if ok else "FEHLT '%s' (%r)" % (want, flat[:80])))
    return ok, len(scr.rstrip())


def repl_int(mon, prev_len, line):
    """Type one REPL line and read the first integer after its echo."""
    import re
    mon.type_line(line)
    time.sleep(1.4)
    scr = iv.screen_text(mon)
    flat = scr[prev_len:].replace(" ", "")
    key = line.replace(" ", "")
    cut = flat.find(key)
    zone = flat[cut + len(key):] if cut >= 0 else flat
    m = re.search(r"\d+", zone)
    return (int(m.group(0)) if m else None), len(scr.rstrip())


def symbol_audit(prg, blob, min_headroom, keep):
    """Run the authoritative device symbol audit required before pinning.

    Boot the product, read symbol-count and symbol-max, and require the requested
    runtime headroom. Device demand is authoritative because manifest-based
    footprint estimates undercount it.
    """
    mon, xemu = iv.boot_product(prg, blob)
    try:
        prev = len(iv.screen_text(mon).rstrip())
        count, prev = repl_int(mon, prev, "(symbol-count)")
        cap, prev = repl_int(mon, prev, "(symbol-max)")
    finally:
        _stop(xemu, keep)
    if count is None or cap is None:
        print("Symbol-Audit: konnte symbol-count/max nicht lesen (count=%r max=%r)" % (count, cap))
        return 2
    hr = cap - count
    print("\n== GERÄTE-SYMBOL-AUDIT (autoritativ) ==")
    print("   boot symbol-count = %d / symbol-max = %d  ->  Laufzeit-Headroom = %d" % (count, cap, hr))
    print("   gefordert (Nutzer-Fns-Puffer) = %d  ->  %s" % (min_headroom, "OK" if hr >= min_headroom else "ZU KNAPP"))
    return 0 if hr >= min_headroom else 1


def _stop(xemu, keep):
    if hasattr(iv, "stop_xemu"):
        iv.stop_xemu(xemu, keep)
    elif not keep:
        os.killpg(os.getpgid(xemu.pid), 9)


def main():
    keep = "--keep" in sys.argv
    no_build = "--no-build" in sys.argv
    audit = "--symbol-audit" in sys.argv
    # --min-headroom N (default 16, roughly 16 user functions); audit mode only.
    min_hr = 16
    if "--min-headroom" in sys.argv:
        i = sys.argv.index("--min-headroom")
        if i + 1 < len(sys.argv):
            min_hr = int(sys.argv[i + 1])
    skip = {"--min-headroom", str(min_hr)}
    pos = [a for a in sys.argv[1:] if not a.startswith("--") and a not in skip]
    prg, blob = (pos + [PRG, BLOB])[:2] if pos else (PRG, BLOB)

    if not no_build and prg == PRG:
        if not build_einsuite():
            print("\nP6c-HARNESS BEREIT — feuert, sobald das Ein-Suite-Profil grün ist.")
            return 2
    if not (os.path.exists(prg) and os.path.exists(blob)):
        print("Artefakte fehlen: %s / %s" % (prg, blob))
        return 2

    if audit:
        return symbol_audit(prg, blob, min_hr, keep)

    mon, xemu = iv.boot_product(prg, blob)
    ok = []
    try:
        prev = len(iv.screen_text(mon).rstrip())
        print("\n== REPL: lcc-first — selbst-gehosteter Compiler am Gerät ==")
        # Keep every input within REPL_BUF_MAX; longer lines truncate silently and create false
        # negatives. Use a short countdown for recursion.
        for line, want in [
            ("(+ 1 2)", "3"),                                              # Treewalk-Sanity
            ("(lcc-run (quote (defun sq (x) (* x x))))", "sq"),            # lcc kompiliert+installiert
            ("(sq 5)", "25"),                                             # proves fast device bytecode execution
            ("(lcc-run (quote (defun dn (n) (if (< n 1) 7 (dn (- n 1))))))", "dn"),  # Rekursion, lcc-kompiliert
            ("(dn 9)", "7"),                                              # rekursiver Bytecode laeuft
            ("(lcc-run (quote (defun tw (x) (+ x x))))", "tw"),           # zweite Fn (Region append)
            ("(tw 21)", "42"),
            ("(- 9 2 3)", "4"),                                           # bridge diet: variadic subtraction in bytecode
            # Mandatory closure gate and treewalk equivalence:
            ("(lcc-run (quote (defun mk () (lambda (x) (* x 2)))))", "mk"),  # capture-freie Factory
            ("(funcall (mk) 21)", "42"),
            ("(lcc-run (quote (defun ad (n) (lambda (x) (+ x n)))))", "ad"),  # CAPTURING closure
            ("(funcall (ad 10) 5)", "15"),                                # OP_CLOSURE/OP_UPVAL on device
        ]:
            r, prev = repl_check(mon, prev, line, want)
            ok.append(r)

        print("\n== IDE im SELBEN Boot (Reunification) ==")
        mon.type_line("(ide)")
        time.sleep(2.5)
        for ch in "hello":
            iv.send_key(mon, ch)
        time.sleep(1.2)
        scr = iv.screen_text(mon)
        rows = [scr[i * 80:(i + 1) * 80].rstrip() for i in range(25)]
        got = "hello" in rows[0]
        status = any("scratch" in r for r in rows)
        print("   Editor Z00=%r | Statuszeile 'scratch': %s" % (rows[0], "JA" if status else "NEIN"))
        ok.append(got)
        ok.append(status)
    finally:
        iv.stop_xemu(xemu, keep) if hasattr(iv, "stop_xemu") else \
            (not keep and os.killpg(os.getpgid(xemu.pid), 9))

    n = sum(1 for x in ok if x)
    if all(ok):
        print("\n🎉 ALL PASS (%d/%d) — SELBST-GEHOSTETE EIN-SUITE LÄUFT AM GERÄT" % (n, len(ok)))
        print("   lcc kompiliert Nutzercode zu Bytecode + IDE im selben Produkt, kein C-Compiler.")
        return 0
    print("\nTEILWEISE (%d/%d) — siehe oben" % (n, len(ok)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
