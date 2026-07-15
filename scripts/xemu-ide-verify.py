#!/usr/bin/env python3
"""Verify the historical interactive IDE/tree-walk route in xemu.

This remains a reference harness rather than a current product gate. It boots
the PRG and blob, starts the blocking `(ide)` loop, injects individual self-
insert keys through the $D615 matrix, and validates editor text and chrome from
Screen RAM. Shared monitor and boot helpers come from xemu-crfull-verify.py.
"""
import sys, time, os, re, importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("crfull", os.path.join(_here, "xemu-crfull-verify.py"))
crfull = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(crfull)
Mon, screen_text = crfull.Mon, crfull.screen_text
start_xemu, stop_xemu = crfull.start_xemu, crfull.stop_xemu
XEMU, SOCK, BLOB_AT, PRG_AT = crfull.XEMU, crfull.SOCK, crfull.BLOB_AT, crfull.PRG_AT


def send_key(mon, ch, shift=False):
    """Send one matrix key without appending RETURN, for editor self-insert."""
    key = Mon.SHIFTED.get(ch, ch.lower())
    sh = shift or (ch in Mon.SHIFTED)
    code = Mon.MTX[key]
    if sh: mon.cmd("sffd3616 0f", wait=0.03)
    mon.cmd("sffd3615 %02x" % code, wait=0.06)
    mon.cmd("sffd3615 7f", wait=0.03)
    if sh: mon.cmd("sffd3616 7f", wait=0.03)
    time.sleep(0.15)


def boot_product(prg, blob):
    """Start xemu, boot the product, and return (monitor, process) at the banner."""
    prg_data, blob_data = open(prg, "rb").read(), open(blob, "rb").read()
    assert prg_data[0] | (prg_data[1] << 8) == PRG_AT, "PRG is not loaded at $2001"
    payload = prg_data[2:]
    m = re.search(rb"\x9e\s*(\d+)", payload)
    if not m: raise SystemExit("BASIC stub contains no SYS")
    sysaddr = m.group(1).decode()
    if os.path.exists(SOCK): os.unlink(SOCK)
    xemu = start_xemu(["-headless", "-testing", "-sleepless", "-besure",
                       "-fastboot", "-uartmon", SOCK])
    for _ in range(40):
        if os.path.exists(SOCK): break
        time.sleep(0.5)
    time.sleep(3)
    mon = Mon(SOCK)
    for i in range(45):
        if "ready" in screen_text(mon): break
        mon.type_line(""); time.sleep(1)
    else:
        raise SystemExit("BASIC-READY kam nie")
    print("== BASIC ready (~%ds); Blob->%06x (%dB), PRG->%04x (%dB)"
          % (i, BLOB_AT, len(blob_data), PRG_AT, len(payload)))
    mon.poke_block(BLOB_AT, blob_data)
    mon.poke_block(PRG_AT, payload)
    assert mon.read_mem(PRG_AT, 8) == payload[:8], "PRG-Upload fehlgeschlagen"
    print("== SYS %s ..." % sysaddr)
    mon.type_line("SYS %s" % sysaddr)
    for _ in range(30):
        time.sleep(1)
        if "lisp65" in screen_text(mon): break
    else:
        raise SystemExit("REPL-Banner fehlt: %r" % screen_text(mon)[:200])
    print("== lisp65-REPL gebootet")
    return mon, xemu


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    prg, blob = sys.argv[1], sys.argv[2]
    keep = "--keep" in sys.argv
    mon, xemu = boot_product(prg, blob)
    ok = False
    try:
        # 1) IDE starten
        print("\n== (ide) tippen -> Editor-Loop ...")
        mon.type_line("(ide)")
        time.sleep(2.5)
        scr0 = screen_text(mon)
        print("   Screen nach (ide) [0:240]:", repr(scr0[:240]))

        # 2) Self-insert line 1 without RETURN.
        line1, line2 = "hello", "world"
        print("\n== Zeile 1 '%s' tippen ..." % line1)
        for ch in line1:
            send_key(mon, ch)
        time.sleep(1.2)
        scr1 = screen_text(mon)

        # 3) RETURN creates a new line; line 2 proves real multiline editing rather than echo.
        print("== RETURN + Zeile 2 '%s' tippen ..." % line2)
        send_key(mon, "\r")
        time.sleep(0.6)
        for ch in line2:
            send_key(mon, ch)
        time.sleep(1.2)
        scr2 = screen_text(mon)

        # Split the screen into 25 rows of 80 and show nonempty rows.
        rows = [scr2[i*80:(i+1)*80].rstrip() for i in range(25)]
        print("\n== Editor-Screen (nicht-leere Zeilen):")
        for i, r in enumerate(rows):
            if r: print("   Z%02d: %r" % (i, r))

        # 4) Oracle
        flat1, flat2 = scr1.replace(" ", ""), scr2.replace(" ", "")
        got_l1 = line1 in flat1
        got_both = line1 in flat2 and line2 in flat2
        # echtes Multi-Line: hello + world stehen in VERSCHIEDENEN Screen-Zeilen
        row_of = lambda w: next((i for i, r in enumerate(rows) if w in r.replace(" ", "")), -1)
        r1, r2 = row_of(line1), row_of(line2)
        multiline = r1 >= 0 and r2 >= 0 and r1 != r2
        got_chrome = "scratch" in scr2
        cleared = scr0.strip() == ""
        print("\n== ORACLE:")
        print("   Zeile 1 '%s' gerendert:            %s" % (line1, "JA" if got_l1 else "NEIN"))
        print("   beide Zeilen nach RETURN sichtbar:  %s" % ("JA" if got_both else "NEIN"))
        print("   auf VERSCHIEDENEN Zeilen (Z%d/Z%d):   %s" % (r1, r2, "JA" if multiline else "NEIN"))
        print("   Editor-Chrome ('scratch'):          %s" % ("JA" if got_chrome else "NEIN"))
        print("   (ide) loeschte Screen (screen-clear): %s" % ("JA" if cleared else "NEIN"))
        ok = got_l1 and got_both and multiline
        if ok:
            print("\nPASS — interaktive IDE: Multi-Line self-insert + RETURN live auf dem Vollprodukt")
        else:
            print("\nUNBESTAETIGT — siehe Screen-Dump oben")
    finally:
        stop_xemu(xemu, keep)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
