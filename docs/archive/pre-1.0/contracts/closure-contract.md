# Closure Contract

Stand: 2026-07-02. Dieses Dokument schaerft die Closure-Grenze zwischen
Eval/Host-Compiler/P0-Bytecode-VM/MEGA65-Target. Es ist ein Vertrag fuer
Post-MVP-Arbeit und kein Auftrag, `src/**` ohne Lane-K-Claim anzufassen.

## Begriffe

- Eval: der CL-nahe Host-Eval in `tools/host-lisp/mvp_prelude_m1_eval_oracle.py`.
- Host-Compiler: `tools/host-lisp/bytecode_p0_compiler.py`.
- Bytecode-VM: `tools/host-lisp/bytecode_p0.py` plus Bundle/Directory.
- Target: Claudes native MEGA65-VM unter `src/**`.

## Gruene Flaeche

Eval muss echte lexikalische Closures abbilden:

- Lambda schliesst die zur Erzeugungszeit sichtbare lexikalische Umgebung ein.
- Innere Bindings duerfen aeussere Namen shadowen.
- Ein Lambda darf als Wert zurueckgegeben und spaeter via `funcall` aufgerufen
  werden.
- `&rest` wird beim Closure-Aufruf als proper list gebunden.

P0-Bytecode ist enger:

- Immediate Lambdas duerfen in den umgebenden Scope gelowered werden.
- Nicht-capturing Lambdas duerfen als Helper-Funktion materialisiert und per
  `funcall` genutzt werden.
- `&rest` ist fuer nicht-capturing Lambda-Helper gruen.
- First-class Closures mit Capture sind fuer Bytecode/Target Known-Open.

Die native Target-VM gilt fuer diesen Vertrag erst dann als gruen, wenn Claude
explizit einen K-Lane-Hook samt HW-/Xemu-Smoke pinnt. Bis dahin bleibt Target
fuer echte Closure-Capture-Faelle offen, selbst wenn Host-Eval gruen ist.

## Matrix

Die maschinenlesbare Quelle ist
`tests/bytecode/runtime/closure-surface-matrix.json`. `make
closure-surface-check` validiert die Matrix und fuehrt alle `eval: green`-Cases
im Host-Eval aus. Cases mit `bytecode: green` werden zusaetzlich kompiliert,
gebundelt und in der P0-Host-VM ausgefuehrt.

Known-Open-Cases werden nicht als Failures ausgefuehrt. Sie sind bewusst
dokumentierte Luecken:

- higher-order return mit Capture
- nested Lambdas, die Capture als Wert herausreichen
- `&rest` in capturing Closures
- Tailcalls ueber first-class capturing Closures

## Lane-Regel

Codex darf diesen Vertrag, Host-Matrix und Host-Compiler-Oracles in Lane L/T
pflegen. Native Closure-Materialisierung, Runtime-Environment-Layout,
GC-Integration oder neue VM-Objekttypen gehoeren zu Lane K und duerfen nur nach
explizitem Claim/Handshake in `docs/collaboration.md` umgesetzt werden.
