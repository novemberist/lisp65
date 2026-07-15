#!/usr/bin/env python3
"""Validate the historical S5 boot directory walk against a real source D81.

This host copy of io_disk_load_named covers the Track 40/S0 chain, bounded fuel,
case-folded 1581 names, and used-entry checks without relying on xemu F011
mounting. The expected layout contains l00 and l01 but no l02.
"""
import sys

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "build/s5/lisp65-s5-source.d81"
    d = open(path, "rb").read()

    def rd_sector(t, s):                       # logischer 1581-Sektor -> 256 B (lineare D81-Abbildung)
        o = ((t - 1) * 40 + s) * 256
        return d[o:o + 256]

    def fold(c):
        if c > 127: c -= 128                   # 0xA0-Padding -> Space
        if 97 <= c <= 122: c -= 32             # lower -> upper
        return c

    def load_named(name):
        track, sector, fuel = 40, 0, 64
        while fuel > 0:
            fuel -= 1
            sec = rd_sector(track, sector)
            for e in range(8):
                base = e * 32
                if (sec[base + 2] & 7) == 0:   # Eintrag frei
                    continue
                match, ended = True, False
                for i in range(16):
                    if not ended and (i >= len(name) or name[i] == '\0'):
                        ended = True
                    nc = 32 if ended else fold(ord(name[i]))
                    if fold(sec[base + 5 + i]) != nc:
                        match = False
                        break
                if match:
                    return (sec[base + 3], sec[base + 4])
            nt, ns = sec[0], sec[1]
            if nt == 0:
                return None
            track, sector = nt, ns
        return None

    l00, l01, l02 = load_named("l00"), load_named("l01"), load_named("l02")
    print("l00 ->", l00, "| l01 ->", l01, "| l02 ->", l02)
    ok = (l00 is not None) and (l01 is not None) and (l02 is None)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
