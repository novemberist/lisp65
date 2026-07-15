#!/usr/bin/env python3
"""Verify the historical S5 source-on-disk boot path in xemu.

The harness stages Lisp source in Bank 4, records its length in directory
scratch, boots, and checks that the device compiler translates it into callable
functions. Usage: xemu-s5-verify.py <prg> [--keep].
"""
import socket, subprocess, sys, time, os, signal, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOCK = os.environ.get("LISP65_XEMU_SOCK", "/tmp/lisp65-s5-umon-%d.sock" % os.getpid())
XEMU = os.environ.get("XMEGA65", os.path.expanduser("~/.local/bin/xmega65"))
XEMU_TIMEOUT = os.environ.get("XMEGA65_TIMEOUT", "300")
DIR_AT  = 0x46C00          # DISK_EXT_DIR  (Laenge, 2 B LE)
FILE_AT = 0x46D00          # DISK_EXT_FILE (Quelltext)
PRG_AT  = 0x2001

def start_xemu(args):
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

# Source: optional file in arg2, otherwise a small built-in program.
_args = [a for a in sys.argv[2:] if not a.startswith("--")]
if _args:
    SRC = open(_args[0]).read()
    CHECKS = [("(length (quote (1 2 3)))","3"), ("(car (reverse (quote (1 2 7))))","7"),
              ("(nth 1 (quote (5 8 9)))","8"), ("(max 3 9 4)","9")]
else:
    SRC = ("(defun tri (n) (if (> n 0) (+ n (tri (- n 1))) 0))\n"
           "(defun dbl (x) (* x 2))\n(defun sqr (x) (* x x))\n")
    CHECKS = [("(tri 5)","15"),("(dbl 21)","42"),("(sqr 9)","81")]

MTX = {'a':10,'b':28,'c':20,'d':18,'e':14,'f':21,'g':26,'h':29,'i':33,'j':34,'k':37,
       'l':42,'m':36,'n':39,'o':38,'p':41,'q':62,'r':17,'s':13,'t':22,'u':30,'v':31,
       'w':9,'x':23,'y':25,'z':12,'0':35,'1':56,'2':59,'3':8,'4':11,'5':16,'6':19,
       '7':24,'8':27,'9':32,' ':60,'\r':1,'+':40,'-':43,'*':49,'/':55,'=':53,'.':44,';':50}
SH = {'(':'8',')':'9'}

class Mon:
    def __init__(s, p): s.s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.s.connect(p); s.s.settimeout(3)
    def cmd(s,c,w=0.05):
        s.s.sendall(c.encode()+b"\r"); time.sleep(w); o=b""
        try:
            while True:
                d=s.s.recv(65536)
                if not d: break
                o+=d
                if o.rstrip().endswith(b"."): break
        except socket.timeout: pass
        return o.decode(errors="replace")
    def poke(s, addr, data, chunk=32):
        for i in range(0,len(data),chunk):
            part=data[i:i+chunk]
            s.s.sendall(("s%x %s\r"%(addr+i," ".join("%02x"%b for b in part))).encode())
            buf=b""; dl=time.time()+5
            while b"." not in buf and time.time()<dl:
                try: buf+=s.s.recv(65536)
                except socket.timeout: continue
    def rd(s, addr, length):
        out=bytearray(); a=addr
        while len(out)<length:
            r=s.cmd("m%x"%a)
            g=False
            for m in re.finditer(r":([0-9A-Fa-f]{8}):([0-9A-Fa-f]+)",r):
                ra=int(m.group(1),16); row=bytes.fromhex(m.group(2))
                if ra<=a<ra+len(row): out+=row[a-ra:]; a=ra+len(row); g=True
            if not g: raise RuntimeError("dump @%x: %r"%(a,r[:80]))
        return bytes(out[:length])
    def key(s,ch):
        sh=ch in SH; ch2=SH[ch] if sh else ch.lower()
        code=MTX[ch2]
        if sh: s.cmd("sffd3616 0f",0.03)
        s.cmd("sffd3615 %02x"%code,0.05); s.cmd("sffd3615 7f",0.03)
        if sh: s.cmd("sffd3616 7f",0.03)
    def line(s,t):
        for ch in t+"\r": s.key(ch)
        time.sleep(0.6)

def screen(mon):
    raw=mon.rd(0x0800,2000)
    def dec(b):
        b&=0x7f
        if 1<=b<=26: return chr(96+b)
        if 32<=b<=63: return chr(b)
        return ' '
    return "".join(dec(b) for b in raw)

def main():
    prg=sys.argv[1]; keep="--keep" in sys.argv
    pd=open(prg,"rb").read(); assert pd[0]|(pd[1]<<8)==PRG_AT
    payload=pd[2:]; sysaddr=re.search(rb"\x9e\s*(\d+)",payload).group(1).decode()
    # --sd=<sdimg>: real F011 path; boot walks the directory and loads default-D81 chunks. Otherwise
    # Monitor-Staging (Phase-1-Proof).
    sd=None
    for a in sys.argv[2:]:
        if a.startswith("--sd="): sd=a[5:]
    if os.path.exists(SOCK): os.unlink(SOCK)
    launch=["-headless","-testing","-sleepless","-besure","-fastboot","-uartmon",SOCK]
    if sd: launch += ["-sdimg",os.path.abspath(sd),"-defd81fromsd"]
    xe=start_xemu(launch)
    ok=False
    try:
        for _ in range(40):
            if os.path.exists(SOCK): break
            time.sleep(0.5)
        time.sleep(3); mon=Mon(SOCK)
        for i in range(45):
            if "ready" in screen(mon): break
            mon.line(""); time.sleep(1)
        else: raise SystemExit("kein READY")
        global CHECKS
        src=SRC.encode()
        if sd:
            print("== SD-Modus: Boot liest Chunks l00,l01,... von der Default-D81 (%s) -- kein Staging"%sd)
            CHECKS=[("(length (quote (1 2 3)))","3"), ("(car (reverse (quote (1 2 7))))","7"),
                    ("(nth 1 (quote (5 8 9)))","8"), ("(max 3 9 4)","9"),
                    ("(ide-event-command (quote (key 97 nil)))","self-insert")]
        else:
            print("== Stage QUELLE (%d B) -> Bank4 0x%x + Laenge -> 0x%x"%(len(src),FILE_AT,DIR_AT))
            mon.poke(DIR_AT, bytes([len(src)&0xff,(len(src)>>8)&0xff]))
            mon.poke(FILE_AT, src)
            v=mon.rd(FILE_AT,8); assert v==src[:8], "Stage fehlgeschlagen: %r"%v
        print("== PRG -> 0x2001 (%d B), SYS %s"%(len(payload),sysaddr))
        mon.poke(PRG_AT,payload)
        t0=time.time(); mon.line("SYS %s"%sysaddr)
        scr=""; bar_seen=0
        for _ in range(180):
            time.sleep(1); scr=screen(mon)
            # Progress-bar proof: check row 12 for full-block screen codes (0xa0).
            try:
                row=mon.rd(0x0800+12*80, 46); blk=sum(1 for b in row[:40] if b==0xa0)
                if blk>bar_seen: bar_seen=blk
                if blk: print("   [Ladebalken: %d/40 gefuellt, %s%%]"%(blk,"".join(chr(b) for b in row[42:45] if 48<=b<=57)))
            except Exception: pass
            if "lisp65" in scr: break
        boot_s=time.time()-t0
        print("== Ladebalken max. Fuellung: %d/40 Bloecke %s"%(bar_seen,"(SICHTBAR!)" if bar_seen else "(nicht erfasst)"))
        print("== Boot-Compile-Zeit (SYS->REPL-Banner): %.1f s  (%d B Quelle)"%(boot_s,len(src)))
        print("== Screen nach Boot:",repr(scr[:120].strip()[:70]))
        assert "lisp65" in scr, "kein REPL-Banner -- Boot-Compile haengt? (%r)"%scr[:200]
        checks=CHECKS
        fails=0; prev=len(screen(mon).rstrip())
        for line,want in checks:
            mon.line(line); time.sleep(1.0); sc=screen(mon)
            new=sc[prev:]; prev=len(sc.rstrip())
            flat=new.replace(" ","")
            k=line[-6:].replace(" ",""); c=flat.find(k)
            zone=flat[c+len(k):] if c>=0 else flat
            good=want in zone
            print("   %-14s => %s   [%s]"%(line,"OK" if good else "FEHLT",repr(zone[:40])))
            if not good: fails+=1
        if fails==0:
            print("\nALL PASS -- Stdlib-QUELLE von Disk on-device kompiliert + Funktionen laufen!")
            ok=True
        else: print("\nFAILED (%d)"%fails)
    finally:
        stop_xemu(xe, keep)
    return 0 if ok else 1

if __name__=="__main__": sys.exit(main())
