#!/usr/bin/env python3
"""Validate historical overwrite-in-place SAVE semantics on a copied D81.

The bit-exact io_disk_save_named model proves that chain links remain unchanged,
chain reads return source plus space padding, and a later longer save retains the
slot's full capacity. It also checks exact-capacity acceptance and one-byte-
over-capacity rejection. The original image is never modified.
"""
import sys, shutil, tempfile, os

SECTOR = 256


def sec_off(t, s):
    """Map a CBM logical sector (T 1..80, S 0..39) to a D81 byte offset."""
    return ((t - 1) * 40 + s) * SECTOR


def fold(c):
    """Mirror disk_fold: clear the high bit, map 0xA0 to space, uppercase ASCII."""
    if c > 127: c -= 128
    if 97 <= c <= 122: c -= 32
    return c


def dir_find(img, name):
    """Mirror disk_dir_find from Track 40/S0 with eight 32-byte entries per sector."""
    t, s, fuel = 40, 0, 64
    nb = [fold(ord(c)) for c in name]
    while fuel:
        fuel -= 1
        sec = img[sec_off(t, s):sec_off(t, s) + SECTOR]
        for e in range(8):
            base = e * 32
            if (sec[base + 2] & 7) == 0: continue
            ok, ended = True, False
            for i in range(16):
                if not ended and i == len(nb): ended = True
                want = 0x20 if ended else nb[i]
                if fold(sec[base + 5 + i]) != want: ok = False; break
            if ok: return sec[base + 3], sec[base + 4]
        if sec[0] == 0: return None
        t, s = sec[0], sec[1]
    return None


def chain_sectors(img, t, s):
    """Return chain tuples (track, sector, links, used); used is 254 or end-marker minus one."""
    out, fuel = [], 255
    while t and fuel:
        fuel -= 1
        sec = img[sec_off(t, s):sec_off(t, s) + SECTOR]
        nt, ns = sec[0], sec[1]
        out.append((t, s, (nt, ns), 254 if nt else ns - 1))
        t, s = nt, ns
    return out


def save(img, name, data):
    """Replik io_disk_save_named: Overwrite-in-place + Leerzeichen-Padding. 1/0."""
    start = dir_find(img, name)
    if not start: return 0
    chain = chain_sectors(img, *start)
    cap = sum(u for (_, _, _, u) in chain)
    if len(data) > cap: return 0
    n = 0
    for (t, s, _, use) in chain:
        off = sec_off(t, s)
        for i in range(use):
            img[off + 2 + i] = data[n] if n < len(data) else 0x20
            n += 1
    return 1


def chain_read(img, t, s):
    """Replik des HW-gruenen Lesers (disk_chain_to_scratch)."""
    out = bytearray()
    for (t_, s_, _, use) in chain_sectors(img, t, s):
        off = sec_off(t_, s_)
        out += img[off + 2:off + 2 + use]
    return bytes(out)


def main():
    if len(sys.argv) != 3:
        print(__doc__); return 2
    src_img, name = sys.argv[1], sys.argv[2]
    work = bytearray(open(src_img, "rb").read())
    fails = 0

    def check(label, ok):
        nonlocal fails
        print("  %-64s => %s" % (label, "OK" if ok else "FAIL"))
        if not ok: fails += 1

    start = dir_find(work, name)
    if not start:
        print("Datei %r nicht im Dir -- falsches Image?" % name); return 2
    before = chain_sectors(work, *start)
    cap = sum(u for (_, _, _, u) in before)
    print("Datei %r: Start T%d/S%d, %d Sektoren, Kapazitaet %d B" %
          (name, start[0], start[1], len(before), cap))

    src1 = b"(defun sq (x) (* x x)) (sq 6)\n"
    if len(src1) > cap:                                 # winziger Slot (z. B. loadall: 26 B)
        src1 = b"(+ 1 2)\n"
    check("Save 1 (kleine Quelle, %d B) angenommen" % len(src1),
          save(work, name, src1) == 1)
    after = chain_sectors(work, *dir_find(work, name))
    check("Invariante 1: Kette+Endmarke unveraendert",
          [(t, s, l) for (t, s, l, _) in before] == [(t, s, l) for (t, s, l, _) in after])
    got = chain_read(work, *start)
    check("Invariante 2: Chain-Read = Quelle + reines Space-Padding",
          got[:len(src1)] == src1 and set(got[len(src1):]) <= {0x20})

    pat = b"(defun cube (x) (* x (* x x))) "
    src2 = (pat * (cap // len(pat) + 1))[:cap]          # EXAKT Kapazitaet
    check("Invariante 3: Voll-Save (len == cap) nach kleinem Save ok",
          save(work, name, src2) == 1)
    check("Chain-Read nach Voll-Save = Quelle (kein Padding noetig)",
          chain_read(work, *start) == src2)
    check("Grenzfall: cap+1 wird abgelehnt", save(work, name, src2 + b"x") == 0)

    if fails == 0:
        print("ALL PASS (save-semantics-check)"); return 0
    print("FAILED: %d" % fails); return 1


if __name__ == "__main__":
    sys.exit(main())
