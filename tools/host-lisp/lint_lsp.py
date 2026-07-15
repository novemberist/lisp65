#!/usr/bin/env python3
"""Static linter for the dialect-pure historical `.lsp` libraries.

Using the real reader, it checks balanced/readable forms as a hard error and
reports cross-file duplicate definitions as collision warnings. Test and smoke
files are excluded because they redefine names intentionally. Undefined-call
analysis is omitted because it would require real scope and quoted-data analysis.
"""
import sys, glob, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lisp64 as L

LIB_FILES = [
    "prelude.lsp", "lib-macros.lsp", "cl-compat.lsp", "lib-arrays.lsp",
    "lib-sets.lsp", "lib-trace.lsp", "lib-diff.lsp", "lib-loop.lsp",
    "lib-struct.lsp", "lib-clos.lsp", "lib-seq.lsp", "lib-modules.lsp",
    "editor-core.lsp", "lib-paredit.lsp", "lib-ide.lsp", "lib-c64hw.lsp",
    "lib-c64fx.lsp", "lib-c64io.lsp", "lib-autoload.lsp",
    "lib-c64-autoload.lsp", "lib-edit-commands.lsp", "lib-buffers.lsp",
    "lib-ide-session.lsp", "lib-ide-undo.lsp", "lib-ide-view.lsp",
]
DEF_HEADS = {"DE", "DF", "DM", "DEFUN", "DEFMACRO"}


def forms_of(path):
    txt = open(path).read()
    r = L.Reader(txt)
    out = []
    while True:
        f, ok = r.read()
        if not ok:
            break
        out.append(f)
    return out


def def_name(form):
    if isinstance(form, L.Pair) and isinstance(form.car, L.Symbol) and form.car.name in DEF_HEADS:
        nm = form.cdr.car if isinstance(form.cdr, L.Pair) else None
        return nm.name if isinstance(nm, L.Symbol) else None
    return None


def main():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lisp")
    base = os.path.normpath(base)
    hard = 0
    defs = {}        # name -> [files]

    for fn in LIB_FILES:
        path = os.path.join(base, fn)
        if not os.path.exists(path):
            continue
        try:
            forms = forms_of(path)
        except Exception as e:
            print("FEHLER [paren/syntax] %s: %s" % (fn, e))
            hard += 1
            continue
        for f in forms:
            nm = def_name(f)
            if nm:
                defs.setdefault(nm, []).append(fn)

    # Cross-File-Doppeldefinitionen
    dups = {n: fs for n, fs in defs.items() if len(set(fs)) > 1}
    for n in sorted(dups):
        print("WARNUNG [doppelte Definition] %s in %s" % (n, ", ".join(sorted(set(dups[n])))))

    print("lint: %d Bibliotheken, %d Definitionen, %d Doppel-Warnungen, %d harte Fehler" % (
        len(LIB_FILES), len(defs), len(dups), hard))
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
