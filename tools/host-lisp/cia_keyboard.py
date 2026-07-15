#!/usr/bin/env python3
"""Host differential oracle for the historical C64 CIA keyboard bridge.

The model covers the active-low CIA1 keyboard matrix and converts snapshots to
IDE tokens. It mirrors the loadable Lisp layer and shares its canonical scenario
table, so drift makes one side of the differential test fail.
"""
import sys

# Column-major: MATRIX[col][row]; col selects PRA and row reads PRB.
# Give non-ASCII keys ASCII names: PND=£, UP=up arrow, LEFT=left arrow.
MATRIX = [
    ["DEL", "RET", "CRSR-LR", "F7", "F1", "F3", "F5", "CRSR-UD"],
    ["3",   "W",   "A",       "4",  "Z",  "S",  "E",  "LSHIFT"],
    ["5",   "R",   "D",       "6",  "C",  "F",  "T",  "X"],
    ["7",   "Y",   "G",       "8",  "B",  "H",  "U",  "V"],
    ["9",   "I",   "J",       "0",  "M",  "K",  "O",  "N"],
    ["+",   "P",   "L",       "-",  ".",  ":",  "@",  ","],
    ["PND", "*",   ";",       "HOME", "RSHIFT", "=", "UP", "/"],
    ["1",   "LEFT","CTRL",    "2",  "SPACE", "CBM", "Q", "STOP"],
]

# Modifier positions (col,row), skipped when finding the base key.
MODS = {(1, 7), (6, 4), (7, 2), (7, 5)}   # LSHIFT, RSHIFT, CTRL, CBM
# Named keys return their name, except SPACE returns " ".
SPECIAL = {"RET", "DEL", "SPACE", "F1", "F3", "F5", "F7", "HOME", "STOP",
           "CRSR-LR", "CRSR-UD", "LEFT", "UP", "PND"}


def pos_of(name):
    for c in range(8):
        for r in range(8):
            if MATRIX[c][r] == name:
                return (c, r)
    raise KeyError(name)


def snapshot(pressed):
    """pressed = Iterable von Tastennamen -> 8 PRB-Bytes (aktiv-LOW)."""
    snap = [0xFF] * 8
    for name in pressed:
        c, r = pos_of(name)
        snap[c] &= 0xFF ^ (1 << r)
    return snap


def pressed_p(snap, c, r):
    return ((snap[c] >> r) & 1) == 0


def downcase(s):
    return s.lower() if len(s) == 1 and "A" <= s <= "Z" else s


def decode(snap):
    """Map a snapshot to an IDE token, or None for modifiers/no key."""
    hit = None
    for c in range(8):
        for r in range(8):
            if pressed_p(snap, c, r) and (c, r) not in MODS:
                hit = (c, r)
                break
        if hit:
            break
    if hit is None:
        return None
    base = MATRIX[hit[0]][hit[1]]
    if base in SPECIAL:
        return " " if base == "SPACE" else base
    ctrl = pressed_p(snap, 7, 2)
    cbm = pressed_p(snap, 7, 5)
    shift = pressed_p(snap, 1, 7) or pressed_p(snap, 6, 4)
    if ctrl:
        return "C-" + downcase(base)
    if cbm:
        return "M-" + downcase(base)
    if shift:
        return base
    return downcase(base)


# Canonical scenario table shared with lib-c64key and its specification.
SCENARIOS = [
    ("E gedrueckt",        ["E"],            "e"),
    ("SHIFT+A",            ["A", "LSHIFT"],  "A"),
    ("CTRL+E",             ["E", "CTRL"],    "C-e"),
    ("CBM+F (Meta)",       ["F", "CBM"],     "M-f"),
    ("RETURN",             ["RET"],          "RET"),
    ("SPACE",              ["SPACE"],        " "),
    ("DEL",                ["DEL"],          "DEL"),
    ("CTRL+S (Suche)",     ["S", "CTRL"],    "C-s"),
    ("CBM+D (kill-word)",  ["D", "CBM"],     "M-d"),
    ("Ziffer 7",           ["7"],            "7"),
    ("nur CTRL -> None",   ["CTRL"],         None),
    ("nichts -> None",     [],               None),
]


def _selftest():
    ok = True
    for label, keys, want in SCENARIOS:
        snap = snapshot(keys)
        got = decode(snap)
        good = got == want
        ok &= good
        bytes_str = " ".join("%02x" % b for b in snap)
        print(f"  [{'OK ' if good else 'XX '}] {label:22} snap=[{bytes_str}] -> {got!r}")
    # Round-trip invariant: one non-modifier key decodes to itself.
    for c in range(8):
        for r in range(8):
            if (c, r) in MODS:
                continue
            base = MATRIX[c][r]
            if base in SPECIAL:
                continue
            got = decode(snapshot([base]))
            if got != downcase(base):
                print(f"  [XX ] Round-Trip {base} -> {got!r}")
                ok = False
    print("ERGEBNIS:", "ALLES OK" if ok else "FEHLER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest())
