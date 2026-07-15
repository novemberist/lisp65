#!/usr/bin/env python3
"""Memory-model prototype for four-byte conses and pointer-reversal GC.

The host-independent model explores immediate fixnums and a four-byte cell with
16-bit CAR/CDR slots. Bit zero tags fixnums, zero is NIL, and aligned even values
are pointers. GC mark/phase data therefore uses a side bitmap rather than the
pointer low bit. Pointer reversal supplies the stackless traversal benefit.
"""

import argparse
import importlib.util
from pathlib import Path
import sys

HOST_LISP = Path(__file__).resolve().with_name("lisp64.py")
_HOST = None

CELL = 4
MARK = 1
PHASE_CDR = 2


def _load_host_lisp():
    global _HOST
    if _HOST is None:
        spec = importlib.util.spec_from_file_location("lisp64_host", str(HOST_LISP))
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        _HOST = module
    return _HOST


class ProfileStats:
    def __init__(self):
        self.pairs = 0
        self.symbols = 0
        self.strings = 0
        self.fixnums = 0
        self.plist_entries = 0
        self.symbol_name_bytes = 0
        self.plist_key_bytes = 0
        self.string_bytes = 0

class Heap:
    def __init__(self, ncells):
        self.ncells = ncells
        self.mem = bytearray((ncells + 1) * CELL)   # Zelle 0 reserviert (=NIL)
        self.meta = bytearray(ncells + 1)
        self.free_head = 0
        self.alloc_count = 0
        self.gc_runs = 0
        # Build a linear free list over cells 1..ncells.
        for i in range(ncells, 0, -1):
            addr = i * CELL
            self._set_car(addr, self.free_head)
            self.free_head = addr

    # --- Value encoding ---
    @staticmethod
    def fixnum(n):
        return ((n << 1) | 1) & 0xFFFF

    @staticmethod
    def is_fixnum(v):
        return (v & 1) == 1

    @staticmethod
    def fixval(v):
        n = v >> 1
        return n - 0x8000 if n >= 0x4000 else n

    @staticmethod
    def is_pointer(v):
        return v != 0 and (v & 1) == 0

    # --- Field access ---
    def _car(self, c):
        return self.mem[c] | (self.mem[c + 1] << 8)

    def _cdr(self, c):
        return self.mem[c + 2] | (self.mem[c + 3] << 8)

    def _set_car(self, c, v):
        self.mem[c] = v & 0xFF
        self.mem[c + 1] = (v >> 8) & 0xFF

    def _set_cdr(self, c, v):
        self.mem[c + 2] = v & 0xFF
        self.mem[c + 3] = (v >> 8) & 0xFF

    # --- Meta ---
    def _idx(self, c):
        return c // CELL

    def marked(self, c):
        return (self.meta[self._idx(c)] & MARK) != 0

    def _set_mark(self, c):
        self.meta[self._idx(c)] |= MARK

    def _phase_cdr(self, c):
        return (self.meta[self._idx(c)] & PHASE_CDR) != 0

    def _set_phase_cdr(self, c):
        self.meta[self._idx(c)] |= PHASE_CDR

    def _clear_phase(self, c):
        self.meta[self._idx(c)] &= ~PHASE_CDR

    # --- Allocation ---
    def cons(self, a, b, roots):
        if self.free_head == 0:
            self.gc(roots)
            if self.free_head == 0:
                raise MemoryError("Heap voll (auch nach GC)")
        c = self.free_head
        self.free_head = self._car(c)
        self._set_car(c, a)
        self._set_cdr(c, b)
        self.alloc_count += 1
        return c

    def free_cells(self):
        n = 0
        c = self.free_head
        while c != 0:
            n += 1
            c = self._car(c)
        return n

    # --- GC: pointer-reversal/Schorr-Waite mark + sweep ---
    def gc(self, roots, recursive=False):
        self.gc_runs += 1
        for i in range(self.ncells + 1):
            self.meta[i] = 0
        for r in roots:
            if recursive:
                self._mark_recursive(r)
            else:
                self._mark_pointer_reversal(r)
        # Return unmarked cells to the free list.
        self.free_head = 0
        freed = 0
        for i in range(1, self.ncells + 1):
            addr = i * CELL
            if not self.marked(addr):
                self._set_car(addr, self.free_head)
                self.free_head = addr
                freed += 1
        return freed

    def _mark_recursive(self, v):
        # Recursive baseline modeling an O(depth) mark stack.
        if not self.is_pointer(v) or self.marked(v):
            return
        self._set_mark(v)
        self._mark_recursive(self._car(v))
        self._mark_recursive(self._cdr(v))

    def _mark_pointer_reversal(self, root):
        # Schorr-Waite: stackless, with return links in cell fields and phase in metadata.
        if not self.is_pointer(root) or self.marked(root):
            return
        cur = root
        prev = 0
        self._set_mark(cur)
        while True:
            if not self._phase_cdr(cur):
                child = self._car(cur)
                if self.is_pointer(child) and not self.marked(child):
                    self._set_car(cur, prev)       # reverse pointer for the return path
                    prev = cur
                    cur = child
                    self._set_mark(cur)
                else:
                    self._set_phase_cdr(cur)
            else:
                child = self._cdr(cur)
                if self.is_pointer(child) and not self.marked(child):
                    self._set_cdr(cur, prev)
                    prev = cur
                    cur = child
                    self._set_mark(cur)
                else:
                    if prev == 0:
                        return
                    if not self._phase_cdr(prev):
                        gp = self._car(prev)
                        self._set_car(prev, cur)   # restore the return path
                        self._set_phase_cdr(prev)
                        cur = prev
                        prev = gp
                    else:
                        gp = self._cdr(prev)
                        self._set_cdr(prev, cur)
                        cur = prev
                        prev = gp


# ---------------------------------------------------------------------------
# Demonstrations
# ---------------------------------------------------------------------------

def report(label, ok):
    print(f"  [{'OK ' if ok else 'XX '}] {label}")
    return ok


def to_pylist(h, v):
    out = []
    while h.is_pointer(v):
        car = h._car(v)
        out.append(h.fixval(car) if h.is_fixnum(car) else ("ptr" if h.is_pointer(car) else "nil"))
        v = h._cdr(v)
    return out


def _profile_roots(profile_path):
    host = _load_host_lisp()
    prelude = Path(profile_path).resolve().with_name("prelude.lsp")
    if prelude.exists():
        host.load_file(str(prelude))
    host.load_file(str(profile_path))
    sym = host.SYMTAB.get("HEAP-PROFILE-ROOTS")
    if sym is None:
        raise RuntimeError("HEAP-PROFILE-ROOTS nicht gesetzt")
    if sym.bound:
        return sym.value
    fn = host.resolve_function(sym)
    if fn is None:
        raise RuntimeError("HEAP-PROFILE-ROOTS ist nicht gebunden und kein Aufrufziel")
    return host.lisp_eval(host.cons(sym, host.NIL))


def _collect_heap_profile_values(host_value, host):
    stats = ProfileStats()
    seen_pairs = set()
    seen_symbols = set()
    seen_strings = set()
    stack = [host_value]
    while stack:
        value = stack.pop()
        if value is host.NIL:
            continue
        if isinstance(value, host.Pair):
            key = id(value)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            stats.pairs += 1
            stack.append(value.car)
            stack.append(value.cdr)
            continue
        if isinstance(value, host.Symbol):
            if value in (host.NIL, host.T):
                continue
            key = id(value)
            if key in seen_symbols:
                continue
            seen_symbols.add(key)
            stats.symbols += 1
            stats.symbol_name_bytes += len(value.name)
            if value.bound:
                stack.append(value.value)
            for pkey, pval in value.plist.items():
                stats.plist_entries += 1
                if isinstance(pkey, str):
                    stats.plist_key_bytes += len(pkey)
                    stack.append(pkey)
                else:
                    stack.append(pkey.name if isinstance(pkey, host.Symbol) else str(pkey))
                stack.append(pval)
            continue
        if isinstance(value, host.Str):
            key = id(value)
            if key in seen_strings:
                continue
            seen_strings.add(key)
            stats.strings += 1
            stats.string_bytes += len(value.s)
            continue
        if isinstance(value, int):
            stats.fixnums += 1
            continue
    return stats


def _iter_roots(raw_roots, host):
    if isinstance(raw_roots, host.Pair):
        cur = raw_roots
        while isinstance(cur, host.Pair):
            yield cur.car
            cur = cur.cdr
        if cur is not host.NIL:
            yield cur
    else:
        yield raw_roots


def _run_heap_profile(profile_path):
    host = _load_host_lisp()
    roots = _profile_roots(profile_path)
    total = ProfileStats()
    for item in _iter_roots(roots, host):
        sub = _collect_heap_profile_values(item, host)
        total.pairs += sub.pairs
        total.symbols += sub.symbols
        total.strings += sub.strings
        total.fixnums += sub.fixnums
        total.plist_entries += sub.plist_entries
        total.symbol_name_bytes += sub.symbol_name_bytes
        total.plist_key_bytes += sub.plist_key_bytes
        total.string_bytes += sub.string_bytes

    # Per-cons cost model: car and cdr require four pointer bytes. Compact2 splits those bytes
    # between inline-next and a sidecar; it does not make a two-byte cons. Its gain is 5 -> 4 bytes
    # versus Classic5, before fixed page machinery.
    CLASSIC5_PER_CONS = 5            # current active layout: Data2+Next2+Flag1
    FOURBYTE_PER_CONS = 4            # Car2+Cdr2, immediate fixnums, no sidecar
    COMPACT2_PER_CONS = 2 + 2       # two-byte inline-next plus two-byte data sidecar
    # Fixed Compact2 page machinery from the experiment: 768 bytes of metadata plus a 512-byte
    # page table. Large heaps grow this lower bound with page count.
    COMPACT2_FIXED = 768 + 512

    # Non-cons payloads are identical in every layout, so report them separately.
    shared = (total.string_bytes + total.strings * 2
              + total.symbol_name_bytes + total.plist_key_bytes
              + total.plist_entries * 2)

    cons_c5 = total.pairs * CLASSIC5_PER_CONS
    cons_4 = total.pairs * FOURBYTE_PER_CONS
    cons_c2 = total.pairs * COMPACT2_PER_CONS + COMPACT2_FIXED

    total_c5 = cons_c5 + shared
    total_4 = cons_4 + shared
    total_c2 = cons_c2 + shared

    print("== 5. HEAP-PROFILE (lisp64.py, ehrliches Cons-Kostenmodell) ==")
    print(f"  Wurzeln: {len(list(_iter_roots(roots, host)))}")
    print("  Erreichbare Objekte:")
    print(f"    CONS-Paare: {total.pairs}")
    print(f"    Symbole  : {total.symbols}")
    print(f"    Strings  : {total.strings} (payload {total.string_bytes} Bytes)")
    print(f"    Property-Eintraege: {total.plist_entries}")
    print(f"  Geteilte Nicht-Cons-Nutzdaten (in allen Layouts gleich): {shared} Bytes")
    print("  Cons-Speicher (nur die Paare):")
    print(f"    Classic5 (aktiv): {cons_c5:>6} B  ({CLASSIC5_PER_CONS} B/Cons)")
    print(f"    4-Byte-Cons     : {cons_4:>6} B  ({FOURBYTE_PER_CONS} B/Cons)")
    print(f"    Compact2        : {cons_c2:>6} B  ({COMPACT2_PER_CONS} B/Cons + {COMPACT2_FIXED} B fix)")
    print("  Gesamt (Cons + geteilte Nutzdaten):")
    print(f"    Classic5 : {total_c5:>6} B ({total_c5/1024:.2f} KiB)")
    print(f"    4-Byte   : {total_4:>6} B ({total_4/1024:.2f} KiB)")
    print(f"    Compact2 : {total_c2:>6} B ({total_c2/1024:.2f} KiB)")
    print("  Deltas:")
    print(f"    4-Byte vs Classic5 : {cons_4 - cons_c5:+d} B (Hebel 5->4 B/Cons)")
    print(f"    Compact2 vs 4-Byte : {cons_c2 - cons_4:+d} B (gleiche B/Cons, + fixe Maschinerie)")

    # Heap-size sweep: Compact2 matches four-byte per-cons cost but retains fixed overhead.
    print("  Heapgroessen-Sweep (reine Cons, ohne geteilte Nutzdaten):")
    print(f"    {'N Cons':>8} {'Classic5':>10} {'4-Byte':>10} {'Compact2':>10} {'C2-4B':>8}")
    for n in (100, 500, 1000, 3000, 7000):
        c5 = n * CLASSIC5_PER_CONS
        f4 = n * FOURBYTE_PER_CONS
        c2 = n * COMPACT2_PER_CONS + COMPACT2_FIXED
        print(f"    {n:>8} {c5:>10} {f4:>10} {c2:>10} {c2-f4:>+8}")
    print("  Lesart: Compact2 macht eine Cons NICHT kleiner als 4-Byte (4 B = 2")
    print("  inline + 2 Sidecar); der fixe Page-Overhead macht es netto schlechter.")
    print("  Realer Hebel ggue. dem aktiven Classic5 ist 5->4 B/Cons -> 4-Byte-Cons.")
    print("ERGEBNIS: HEAP-PROFILE-ANALYSE ENDE")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--heap-profile",
        type=Path,
        help="Pfad zu lisp/heap-profile.lsp für optionalen Heap-Profilelauf",
    )
    args = parser.parse_args()

    if args.heap_profile:
        try:
            return _run_heap_profile(args.heap_profile)
        except Exception as exc:
            print("compact-model --heap-profile: FEHLER:", exc, file=sys.stderr)
            return 1

    allok = True
    print("== 1. Immediate-Fixnums (Low-Bit-Tag) ==")
    for n in (0, 1, -1, 42, -42, 16383, -16384):
        enc = Heap.fixnum(n)
        dec = Heap.fixval(enc)
        ok = (dec == n) and Heap.is_fixnum(enc) and not Heap.is_pointer(enc)
        allok &= report(f"fixnum {n} -> enc ${enc:04X} -> {dec}", ok)
    allok &= report("Pointer vs Fixnum unterscheidbar (bit0)", Heap.is_pointer(4) and not Heap.is_fixnum(4))

    print("\n== 2. 4-Byte-Cons + GC (Pointer-Reversal) ==")
    h = Heap(64)
    free0 = h.free_cells()
    # List (10 20 30) with immediate fixnums in car fields.
    roots = [0]
    lst = 0
    for n in (30, 20, 10):
        lst = h.cons(Heap.fixnum(n), lst, [lst] + roots)
    roots = [lst]
    # Allocate a few unreachable garbage cells.
    garbage = h.cons(Heap.fixnum(99), 0, roots + [lst])
    garbage = h.cons(Heap.fixnum(98), garbage, roots)  # garbage remains unreferenced
    used_before = free0 - h.free_cells()
    freed = h.gc(roots)
    live = to_pylist(h, lst)
    allok &= report(f"Liste überlebt GC: {live}", live == [10, 20, 30])
    allok &= report(f"Müll eingesammelt (freed={freed}, frei={h.free_cells()}/{free0})",
                    h.free_cells() == free0 - 3)  # only the three list cells remain live
    # Fixnums in car fields consume no cells.
    allok &= report("Fixnums in CARs sind Immediate (0 Extra-Zellen)", used_before == 5)

    print("\n== 3. Stackless-Robustheit: tiefe Liste ==")
    DEPTH = 4000
    h2 = Heap(DEPTH + 16)
    deep = 0
    r = [0]
    for i in range(DEPTH):
        deep = h2.cons(Heap.fixnum(i & 1), deep, [deep])
    # Pointer reversal marks a deep list without a stack.
    h2.gc([deep])
    allok &= report(f"Pointer-Reversal-GC markiert Tiefe {DEPTH} (frei={h2.free_cells()})",
                    h2.free_cells() == (DEPTH + 16) - DEPTH)
    # Recursive variant fails at Python's recursion limit, modeling mark-stack overflow.
    rec_failed = False
    try:
        h2.gc([deep], recursive=True)
    except RecursionError:
        rec_failed = True
    allok &= report(f"Rekursiver Mark scheitert an Tiefe {DEPTH} (Stack-Overflow-Analogon): "
                    f"{'ja' if rec_failed else 'NEIN'}", rec_failed)

    print("\n== 4. Speichergewinn durch Immediate-Fixnums ==")
    N = 500
    h3 = Heap(2 * N + 16)
    r = [0]
    lst = 0
    for i in range(N):
        lst = h3.cons(Heap.fixnum(i), lst, [lst])
    immediate_cells = h3.alloc_count
    boxed_cells = 2 * N  # model: every boxed number would add one cell
    allok &= report(f"Immediate: {immediate_cells} Zellen für {N}-Liste; "
                    f"geboxt wären ~{boxed_cells} (Faktor {boxed_cells/immediate_cells:.1f}x)",
                    immediate_cells == N)

    print()
    print("ERGEBNIS:", "ALLES OK" if allok else "FEHLER")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
