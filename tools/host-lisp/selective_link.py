#!/usr/bin/env python3
"""Selective-link and dead-code-elimination Phase-7 prototype.

The model includes only functions and runtime primitives reachable from program
entry points. Dynamic eval/read/intern and computed funcall/apply make static
reachability undecidable, in which case the full interpreter must be bundled.
It shares the LISP 64 reader so analysis uses the same dialect.

Usage:
  selective_link.py --entry MAIN lib-a.lsp prog.lsp     # Bericht
  selective_link.py --selftest

The heuristic is conservative rather than a complete compiler: symbols in
operator position are calls, quoted data is not, constant higher-order function
arguments add their target, and dynamic function selection forces full linking.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lisp64 import read_all, Symbol, Pair  # noqa: E402

DEF_HEADS = {"DE", "DF", "DM", "DEFUN", "DEFMACRO"}
HIGHER_ORDER = {"MAPCAR", "MAPC", "MAPCAN", "MAPLIST", "MAPCON", "MAPCAR2",
                "APPLY", "FUNCALL"}
# Operators whose function argument may be computed require dynamic analysis.
FN_ARG_OPS = {"APPLY", "FUNCALL"}
# Inhaerent dynamisch (statische Erreichbarkeit unentscheidbar).
DYNAMIC_OPS = {"EVAL", "READ", "INTERN", "READ-FROM-STRING"}


def _name(x):
    return x.name if isinstance(x, Symbol) else None


def _elems(x):
    """Return proper and dotted-list elements as a Python list, stopping at non-Pair."""
    out = []
    while isinstance(x, Pair):
        out.append(x.car)
        x = x.cdr
    return out


def _is_quoted_sym(form):
    """Return the symbol name from (QUOTE s) or (FUNCTION s), otherwise None."""
    if isinstance(form, Pair) and _name(form.car) in ("QUOTE", "FUNCTION"):
        args = _elems(form.cdr)
        if len(args) == 1 and isinstance(args[0], Symbol):
            return args[0].name
    return None


class Analysis:
    def __init__(self):
        self.defs = {}        # name -> set of called names
        self.macros = set()   # names defined by DM/DEFMACRO
        self.dynamic = {}     # name -> reasons why reachability is dynamic
        self.toplevel = set()  # calls in top-level forms, excluding definitions
        self.toplevel_dyn = []

    # ---- Call extraction ---------------------------------------------------
    def _collect(self, form, calls, dyn):
        if not isinstance(form, Pair):
            return
        head = form.car
        hname = _name(head)
        if hname is None:
            # CAR may itself be a form, for example ((LAMBDA ..) ..).
            self._collect(head, calls, dyn)
            for a in _elems(form.cdr):
                self._collect(a, calls, dyn)
            return
        if hname == "QUOTE":
            return                                   # data only
        if hname == "FUNCTION":
            s = _is_quoted_sym(form)
            if s:
                calls.add(s)
            return
        calls.add(hname)
        args = _elems(form.cdr)
        if hname in DYNAMIC_OPS:
            dyn.append("%s (runtime evaluation)" % hname)
        if hname in FN_ARG_OPS and args:
            s = _is_quoted_sym(args[0])
            if s:
                calls.add(s)
            elif isinstance(args[0], Symbol):
                dyn.append("%s on computed or variable function '%s'" % (
                    hname, args[0].name))
            # A constant (QUOTE s) is safe; any other form is dynamic.
            elif isinstance(args[0], Pair) and _name(args[0].car) not in (
                    "QUOTE", "FUNCTION"):
                dyn.append("%s on computed function" % hname)
        if hname in HIGHER_ORDER and hname not in FN_ARG_OPS and args:
            s = _is_quoted_sym(args[0])
            if s:
                calls.add(s)
            elif isinstance(args[0], (Symbol, Pair)):
                dyn.append("%s with computed function argument" % hname)
        for a in args:
            self._collect(a, calls, dyn)

    # ---- Input files -------------------------------------------------------
    def add_text(self, text):
        for form in read_all(text):
            if not isinstance(form, Pair):
                continue
            head = _name(form.car)
            els = _elems(form)
            if head in DEF_HEADS and len(els) >= 3 and isinstance(els[1], Symbol):
                name = els[1].name
                calls = set()
                dyn = []
                for b in els[3:]:                    # body forms after ARGS
                    self._collect(b, calls, dyn)
                self.defs[name] = self.defs.get(name, set()) | calls
                if dyn:
                    self.dynamic.setdefault(name, []).extend(dyn)
                if head in ("DM", "DEFMACRO"):
                    self.macros.add(name)
            else:
                # A top-level call or expression contributes roots.
                calls = set()
                dyn = []
                self._collect(form, calls, dyn)
                self.toplevel |= calls
                self.toplevel_dyn += dyn

    def add_file(self, path):
        with open(path) as f:
            self.add_text(f.read())

    # ---- Erreichbarkeit ----------------------------------------------------
    def reachable(self, entries):
        seen = set()
        work = list(entries)
        prim = set()
        dyn_hits = []
        while work:
            n = work.pop()
            if n in seen:
                continue
            seen.add(n)
            if n in self.dynamic:
                dyn_hits.append((n, self.dynamic[n]))
            if n in self.defs:
                for c in self.defs[n]:
                    if c not in seen:
                        work.append(c)
            else:
                prim.add(n)                          # not defined, therefore a primitive
        reached_defs = {n for n in seen if n in self.defs}
        return reached_defs, prim, dyn_hits


def report(analysis, entries):
    reached, prim, dyn_hits = analysis.reachable(entries)
    all_defs = set(analysis.defs)
    dead = all_defs - reached
    print("Einstiegspunkte: %s" % ", ".join(sorted(entries)))
    print("Definierte Funktionen gesamt : %d" % len(all_defs))
    print("Erreichbar (zu linken)       : %d" % len(reached))
    print("Eliminierbar (Dead Code)     : %d" % len(dead))
    print("Benoetigte Runtime-Primitive : %d" % len(prim))
    if dead:
        print("  eliminiert: %s" % ", ".join(sorted(dead)))
    if analysis.toplevel_dyn or dyn_hits:
        print()
        print("DYNAMISCH -> statische Erreichbarkeit unentscheidbar:")
        for r in analysis.toplevel_dyn:
            print("  [top-level] %s" % r)
        for n, reasons in dyn_hits:
            for r in reasons:
                print("  %s: %s" % (n, r))
        print("=> VERDIKT: Interpreter buendeln (CL-Image-Modell, ~14 KB).")
    else:
        print()
        print("=> VERDIKT: statisch -> selektiv gelinktes kleines .prg "
              "(%d Funktionen + %d Primitive)." % (len(reached), len(prim)))
    return reached, prim, dead, (analysis.toplevel_dyn or dyn_hits)


# ---- Self-test -----------------------------------------------------------

def _selftest():
    # Static program containing dead code:
    #   MAIN -> HELPER -> LEAF; UNUSED is never reached.
    prog = """
    (DE LEAF (X) (PLUS X 1))
    (DE HELPER (X) (LEAF (TIMES X 2)))
    (DE UNUSED (X) (DIFFERENCE X 9))
    (DE MAIN () (HELPER 21))
    """
    a = Analysis()
    a.add_text(prog)
    reached, prim, dyn = a.reachable(["MAIN"])
    assert reached == {"MAIN", "HELPER", "LEAF"}, reached
    assert "UNUSED" not in reached
    # PLUS/TIMES are primitives; DIFFERENCE appears only in dead code.
    assert "PLUS" in prim and "TIMES" in prim, prim
    assert "DIFFERENCE" not in prim, prim
    assert not dyn

    # Higher-order calls with a constant function argument remain static.
    prog2 = """
    (DE DBL (X) (TIMES X 2))
    (DE RUN (L) (MAPCAR (QUOTE DBL) L))
    """
    a2 = Analysis(); a2.add_text(prog2)
    r2, _, dyn2 = a2.reachable(["RUN"])
    assert "DBL" in r2, r2
    assert not dyn2, dyn2

    # eval makes reachability dynamic.
    a3 = Analysis(); a3.add_text("(DE GO (F) (EVAL F))")
    _, _, dyn3 = a3.reachable(["GO"])
    assert dyn3, "EVAL should have made reachability dynamic"

    # apply to a computed function is dynamic.
    a4 = Analysis(); a4.add_text("(DE GO (F X) (APPLY F X))")
    _, _, dyn4 = a4.reachable(["GO"])
    assert dyn4, "APPLY to a variable should have been dynamic"

    # apply to a constant function is static and counts as a call.
    a5 = Analysis(); a5.add_text("(DE TGT (X) X)(DE GO (X) (APPLY (QUOTE TGT) X))")
    r5, _, dyn5 = a5.reachable(["GO"])
    assert "TGT" in r5 and not dyn5, (r5, dyn5)

    # Real library: reachability prunes unused functions.
    here = os.path.dirname(os.path.abspath(__file__))
    fx = os.path.join(here, "..", "..", "lisp", "lib-c64fx.lsp")
    if os.path.exists(fx):
        a6 = Analysis(); a6.add_file(fx)
        # Entry only through CIRCLE-POINTS; line/shape/melody sections are dead.
        # The reader uppercases symbols, so names are uppercase.
        reached6, _, _ = a6.reachable(["CIRCLE-POINTS"])
        assert "CIRCLE-POINTS" in reached6
        assert "MELODY->FREQS" not in reached6, \
            "MELODY->FREQS sollte von CIRCLE-POINTS aus unerreichbar sein"
        assert len(reached6) < len(a6.defs), "Pruning sollte Funktionen entfernen"

    print("selective_link self-test: ALLES OK")


def main(argv):
    if not argv or "--selftest" in argv:
        _selftest()
        return 0
    entries = []
    files = []
    i = 0
    while i < len(argv):
        if argv[i] == "--entry":
            entries.append(argv[i + 1].upper()); i += 2   # Reader caset hoch
        else:
            files.append(argv[i]); i += 1
    if not files:
        sys.stderr.write(__doc__)
        return 2
    a = Analysis()
    for f in files:
        a.add_file(f)
    if not entries:
        entries = sorted(a.toplevel & set(a.defs)) or ["MAIN"]
    report(a, entries)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
