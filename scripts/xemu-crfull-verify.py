#!/usr/bin/env python3
"""Verify the historical crfit/compile-REPL reference profile in xemu.

This reference/equivalence harness is no longer a device-product gate. It boots
xemu through its monitor, loads the Bank-5 blob and PRG deterministically,
injects SYS through the hardware keyboard matrix, evaluates REPL and closure
forms, and checks Screen RAM. Failures include a Bank-5 diagnostic dump.
"""
import socket, subprocess, sys, time, os, signal, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOCK = os.environ.get("LISP65_XEMU_SOCK", "/tmp/lisp65-umon-%d.sock" % os.getpid())
XEMU = os.environ.get("XMEGA65", os.path.expanduser("~/.local/bin/xmega65"))
XEMU_TIMEOUT = os.environ.get("XMEGA65_TIMEOUT", "240")
BLOB_AT = 0x0050000
PRG_AT  = 0x2001

def start_xemu(args):
    """Start xmega65 through the token-cleaning safe-run wrapper."""
    safe_runner = ROOT / "scripts" / "xmega65-safe-run.sh"
    cmd = [str(safe_runner), SOCK, XEMU_TIMEOUT, XEMU] + args
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)

def stop_xemu(proc, keep=False):
    if keep:
        print("== --keep: xmega65 remains active only until the safe-run timeout (%ss)" % XEMU_TIMEOUT)
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

class Mon:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.connect(path); self.s.settimeout(3)
    def cmd(self, c, wait=0.05):
        self.s.sendall(c.encode() + b"\r"); time.sleep(wait)
        out = b""
        try:
            while True:
                chunk = self.s.recv(65536)
                if not chunk: break
                out += chunk
                if out.rstrip().endswith(b"."): break
        except socket.timeout: pass
        return out.decode(errors="replace")
    def poke_block(self, addr, data, chunk=32):
        """Write bytes with strictly serialized s commands.

        uartmon accepts only one command per send and discards the remainder, so
        wait for the '.' acknowledgement after every command.
        """
        for i in range(0, len(data), chunk):
            part = data[i:i+chunk]
            self.s.sendall(("s%x %s\r" % (addr + i, " ".join("%02x" % b for b in part))).encode())
            buf = b""; deadline = time.time() + 5
            while b"." not in buf and time.time() < deadline:
                try: buf += self.s.recv(65536)
                except socket.timeout: continue
            if b"." not in buf:
                raise RuntimeError("poke_block: no acknowledgement @%x" % (addr + i))
    def read_mem(self, addr, length):
        """Parse one or more m commands into bytes."""
        out = bytearray()
        a = addr
        while len(out) < length:
            r = self.cmd("m%x" % a, wait=0.05)
            got = False
            for m in re.finditer(r":([0-9A-Fa-f]{8}):([0-9A-Fa-f]+)", r):
                row_at = int(m.group(1), 16)
                row = bytes.fromhex(m.group(2))
                if row_at <= a < row_at + len(row):
                    out += row[a - row_at:]
                    a = row_at + len(row)
                    got = True
            if not got:
                raise RuntimeError("Monitor-Dump unlesbar @%x: %r" % (a, r[:120]))
        return bytes(out[:length])
    # $D615/6 MEGA65 virtual keys use C64 matrix scan codes, not ASCII; $7F releases.
    # Shifted characters hold LSHIFT (15) in $D616; unshifted letters map to lowercase in REPL.
    MTX = {'a':10,'b':28,'c':20,'d':18,'e':14,'f':21,'g':26,'h':29,'i':33,'j':34,'k':37,
           'l':42,'m':36,'n':39,'o':38,'p':41,'q':62,'r':17,'s':13,'t':22,'u':30,'v':31,
           'w':9,'x':23,'y':25,'z':12,
           '0':35,'1':56,'2':59,'3':8,'4':11,'5':16,'6':19,'7':24,'8':27,'9':32,
           ' ':60,'\r':1,'+':40,'-':43,'*':49,'/':55,'=':53,'.':44,',':47,':':45,';':50}
    SHIFTED = {'(':'8', ')':'9', '<':',', '>':'.', '"':'2', '!':'1'}
    def type_line(self, text):
        for ch in text + "\r":
            ch = ch if ch in self.SHIFTED else ch.lower()   # matrix maps lowercase letters only
            shift = ch in self.SHIFTED
            code = self.MTX[self.SHIFTED[ch] if shift else ch]
            if shift: self.cmd("sffd3616 0f", wait=0.03)          # press LSHIFT
            self.cmd("sffd3615 %02x" % code, wait=0.05)           # press key
            self.cmd("sffd3615 7f", wait=0.03)                    # loslassen
            if shift: self.cmd("sffd3616 7f", wait=0.03)
        time.sleep(0.5)

def screen_text(mon):
    """Screen-RAM (2 KB @0x0800) als grober ASCII-Text (MEGA65-Screencodes)."""
    raw = mon.read_mem(0x0800, 2000)
    def dec(b):
        b &= 0x7F
        if 1 <= b <= 26: return chr(ord('a') + b - 1)
        if b == 0: return '@'
        if 32 <= b <= 63: return chr(b)
        return ' '
    return "".join(dec(b) for b in raw)

def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    prg, blob = sys.argv[1], sys.argv[2]
    keep = "--keep" in sys.argv
    prg_data  = open(prg, "rb").read()
    blob_data = open(blob, "rb").read()
    assert prg_data[0] | (prg_data[1] << 8) == PRG_AT, "PRG nicht @2001"
    payload = prg_data[2:]
    m = re.search(rb"\x9e\s*(\d+)", payload)
    sysaddr = m.group(1).decode() if m else None
    if not sysaddr: raise SystemExit("kein SYS im BASIC-Stub")

    if os.path.exists(SOCK): os.unlink(SOCK)
    # Deterministic without -prg: -prgtest used to type SYS during upload and abort before the
    # L65M trailer arrived. Dismiss the splash with a key.
    # Dismiss it, wait for BASIC READY, then load blob and PRG before typing SYS.
    xemu = start_xemu(["-headless", "-testing", "-sleepless", "-besure",
                       "-fastboot", "-uartmon", SOCK])
    ok = False
    try:
        for _ in range(40):
            if os.path.exists(SOCK): break
            time.sleep(0.5)
        time.sleep(3)
        mon = Mon(SOCK)
        for i in range(45):                              # splash to READY; Return may advance it
            scr = screen_text(mon)
            if "ready" in scr: break
            mon.type_line("")                            # RETURN: Splash wegdruecken
            time.sleep(1)
        else:
            raise SystemExit("BASIC-READY kam nie (Screen: %r)" % screen_text(mon)[:200])
        print("== BASIC ready (nach ~%ds)" % i)
        print("== Blob -> 0x%06x (%d B)" % (BLOB_AT, len(blob_data)))
        mon.poke_block(BLOB_AT, blob_data)
        for probe in (0, 7694, len(blob_data) - 16):     # Anfang, L65M-Trailer-Start, Ende
            v = mon.read_mem(BLOB_AT + probe, 8)
            want = blob_data[probe:probe+8]
            print("   verify@%-5d: %s %s" % (probe, v.hex(), "OK" if v == want else "!= " + want.hex()))
            assert v == want, "Blob-Upload lueckenhaft @%d" % probe
        print("== PRG -> 0x%04x (%d B)" % (PRG_AT, len(payload)))
        mon.poke_block(PRG_AT, payload)
        assert mon.read_mem(PRG_AT, 8) == payload[:8], "PRG-Upload fehlgeschlagen"
        print("== SYS %s tippen ..." % sysaddr)
        mon.type_line("SYS %s" % sysaddr)
        scr = ""
        for _ in range(30):                              # boot: blob registration + REPL banner
            time.sleep(1)
            scr = screen_text(mon)
            if "lisp65" in scr: break
        print("== Screen nach Boot:", repr(scr[:160].strip()[:100]))
        assert "lisp65" in scr, "REPL-Banner fehlt -> bootet nicht (Screen: %r)" % scr[:200]

        # Inspect boot state before input: did blob registration run, or did lisp_abort fire?
        elf = prg + ".elf"
        syms = {}
        if os.path.exists(elf):
            nm = subprocess.run(["tools/llvm-mos/bin/llvm-nm", "--radix=x", elf],
                                capture_output=True, text=True).stdout
            for ln in nm.splitlines():
                p = ln.split()
                if len(p) == 3: syms[p[2]] = int(p[0], 16)
        def rd16(name):
            if name not in syms: return None
            d = mon.read_mem(syms[name], 2)
            return d[0] | (d[1] << 8)
        print("== Boot-Zustand: dir_n=%s ext_code_init=%s ext_code_hw=%s" %
              (rd16("dir_n"), (rd16("ext_code_init") or 0) & 0xFF, rd16("ext_code_hw")))
        if "lisp_error_msg" in syms:
            ptr = rd16("lisp_error_msg")
            if ptr:
                msg = mon.read_mem(ptr, 40)
                msg = msg.split(b"\0")[0].decode(errors="replace")
                print("== lisp_error_msg: %r  <-- STILLER BOOT-ABORT!" % msg)

        checks = [
            ("(+ 1 2)", "3"),
            ("(length (quote (9 9 9 9)))", "4"),        # stdlib blob function; input echo contains no digit 4
            # Heap churn forces GC before defun to probe the historical cons hypothesis.
            ("(length (quote (1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1)))", "16"),
            ("(defun sq (x) (* x x))", "sq"),
            ("(sq 5)", "25"),                            # historical hardware-bug case
            ("(defun adder (n) (lambda (x) (+ x n)))", "adder"),
            ("(funcall (adder 10) 5)", "15"),            # closure
            # IDE logic registered from the blob: real editor bytecode functions.
            ("(ide-event-command (quote (key 97 nil)))", "self-insert"),
            ("(string-length (ide-current-line (ide-make-buffer \"b\" (quote (\"abcde\")))))", "5"),
        ]
        fails = 0
        prev_len = len(screen_text(mon).rstrip())
        for line, want in checks:
            mon.type_line(line)
            time.sleep(1.2)
            scr = screen_text(mon)
            # Oracle: inspect only new screen content since the last input, and only after the
            # input echo, preventing echo false positives.
            new = scr[prev_len:]
            prev_len = len(scr.rstrip())
            # Echo spacing may differ; cut after the input's final character.
            key = line[-8:].replace(" ", "")
            flat = new.replace(" ", "")
            cut = flat.find(key)
            result_zone = flat[cut + len(key):] if cut >= 0 else flat
            got_ok = want.replace(" ", "") in result_zone
            print("   %-44s => %s" % (line, "OK" if got_ok else "FEHLT '%s'" % want))
            print("      echo+antwort:", repr(flat[:110]))
            if not got_ok:
                fails += 1
                if "1 1 1" in line: break   # inspect this specific main form
        if fails == 0:
            print("\nALL PASS — Vollprofil (Blob+Region) laeuft in xemu")
            ok = True
        else:
            print("\nFAILED (%d) — Diagnose:" % fails)
            print("   blob@0:", mon.read_mem(BLOB_AT, 16).hex())
            print("   region@file-end(%x):" % (BLOB_AT + len(blob_data)),
                  mon.read_mem(BLOB_AT + len(blob_data), 32).hex())
            # .bss-Zustand: Allokator + Dir-Basen via ELF-Symbole live auslesen
            elf = prg + ".elf"
            if os.path.exists(elf):
                nm = subprocess.run(["tools/llvm-mos/bin/llvm-nm", "--radix=x", elf],
                                    capture_output=True, text=True).stdout
                syms = {}
                for line in nm.splitlines():
                    p = line.split()
                    if len(p) == 3 and p[2] in ("ext_code_hw", "ext_code_init",
                                                "dir_off_base", "dir_len", "dir_n", "gc_badobj", "gc_runs", "alloc_high", "gc_frozen", "gc_bad_roots", "gc_bad_syms", "gc_bad_cells", "gc_bad_hot", "gc_bad_ext", "heap", "freelist"):
                        syms[p[2]] = int(p[0], 16)
                for name in ("ext_code_init", "ext_code_hw", "dir_n", "gc_badobj", "gc_runs", "alloc_high", "gc_frozen", "gc_bad_roots", "gc_bad_syms", "gc_bad_cells", "gc_bad_hot", "gc_bad_ext", "heap", "freelist"):
                    if name in syms:
                        d = mon.read_mem(syms[name], 2)
                        print("   %s@%04x = %04x" % (name, syms[name], d[0] | (d[1] << 8)))
                if "dir_off_base" in syms:
                    d = mon.read_mem(syms["dir_off_base"], 62)
                    print("   dir_off_base[28..30]:",
                          " ".join("%04x" % (d[i] | (d[i+1] << 8)) for i in (56, 58, 60)))
                # Hot-heap dump: all 60 cells with invalid fields marked, plus free-list walk.
                if "heap" in syms:
                    HC = 60; MAXC = 60 + 2048   # EXT_CELLS des Diag-Builds
                    raw = mon.read_mem(syms["heap"], HC * 5)
                    TN = {0:"CONS",1:"SYM",2:"PRIM",3:"CLOS",4:"MACR",5:"STR",6:"BCOD"}
                    def isbad(o): return 0 < o < 0x8000 and (o & 1) == 0 and (o >> 1) >= MAXC
                    print("   --- HOT-HEAP (nur auffaellige/belegte Zellen) ---")
                    for c in range(1, HC):
                        t = raw[c*5]; a = raw[c*5+1] | (raw[c*5+2] << 8); b = raw[c*5+3] | (raw[c*5+4] << 8)
                        if t == 0 and a == 0 and b == 0: continue
                        fa = " BAD-a" if isbad(a) else ""; fb = " BAD-b" if isbad(b) else ""
                        print("     [%2d] %-4s a=%04x b=%04x%s%s" % (c, TN.get(t, "?%d" % t), a, b, fa, fb))
                if "freelist" in syms:
                    fl = mon.read_mem(syms["freelist"], 2); head = fl[0] | (fl[1] << 8)
                    seen = set(); node = head; steps = 0; cyc = False
                    while node and (node & 1) == 0 and steps < 200:
                        idx = node >> 1
                        if idx in seen: cyc = True; break
                        seen.add(idx)
                        if idx < 60: cell = mon.read_mem(syms["heap"] + idx*5, 5)
                        else: cell = mon.read_mem(0x40000 + (idx-60)*8, 6)
                        node = cell[1] | (cell[2] << 8) if idx < 60 else cell[2] | (cell[3] << 8)
                        steps += 1
                    print("   freelist head=%04x laenge=%d%s" % (head, steps, "  ZYKLUS!" if cyc else ""))
            # Cell autopsy: parse transient main at the region, then littab and list pointer.
            # Walk the cdr chain directly in Bank 4. An intact chain isolates a broken VM read path;
            # Garbage indicates a broken write or GC path.
            main_at = 0x50000 + len(blob_data)
            hdr8 = mon.read_mem(main_at, 7)
            if hdr8[0] == 0xB5:
                nlits = hdr8[6]
                lit = mon.read_mem(main_at + 7, nlits * 2)
                print("   main-littab:", [hex(lit[k] | (lit[k+1] << 8)) for k in range(0, nlits*2, 2)])
                for k in range(0, nlits * 2, 2):
                    o = lit[k] | (lit[k+1] << 8)
                    if 0 < o < 0x8000 and (o & 1) == 0 and (o >> 1) >= 60:  # positive int16 EXT pointer
                        i = o >> 1
                        print("   walk ab EXT-Zelle %d:" % i)
                        for _ in range(6):
                            cell = mon.read_mem(0x40000 + (i - 60) * 8, 6)
                            t = cell[0]; a = cell[2] | (cell[3] << 8); b = cell[4] | (cell[5] << 8)
                            print("     zelle %-5d type=%d a=%04x b=%04x" % (i, t, a, b))
                            if b > 0 and (b & 1) == 0 and (b >> 1) >= 60: i = b >> 1
                            else: break
                        break
            # Scan Bank 5 for CO_MAGIC blobs beyond stdlib code to locate sq.
            print("   scan nach b5-Objekten in [blob_code_end..0x8000):")
            hits = []
            a = 7168
            data = mon.read_mem(BLOB_AT + a, 0x8000 - a)
            for i, b in enumerate(data):
                if b == 0xB5 and i + 6 < len(data) and data[i+1] <= 8 and data[i+3] <= 1:
                    hits.append(a + i)
            print("   b5-Kandidaten:", ["0x%04x" % h for h in hits[:12]], "…" if len(hits) > 12 else "")
    finally:
        stop_xemu(xemu, keep)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
