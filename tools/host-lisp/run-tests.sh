#!/bin/sh
# Run every dialect-only suite on the host reference interpreter.
# Exit nonzero if any suite reports failures.
#
# Run: sh tools/host-lisp/run-tests.sh
set -e
cd "$(dirname "$0")/../.."

PY=python3
INT=tools/host-lisp/lisp64.py
PRE=lisp/prelude.lsp
fail_total=0

run() {
  label="$1"; shift
  out="$($PY $INT "$@" 2>&1)"
  printf '%s\n' "$out" | sed 's/^/  /'
  rep="$(printf '%s\n' "$out" | grep -E 'FAIL=' | tail -1)"
  f="$(printf '%s\n' "$rep" | sed -n 's/.*FAIL=\([0-9][0-9]*\).*/\1/p')"
  [ -z "$f" ] && f=0
  printf '[%s] %s\n\n' "$label" "${rep:-kein CHECK-REPORT}"
  fail_total=$((fail_total + f))
}

echo "== conformance =="
run conformance        $PRE lisp/conformance.lsp
echo "== dm-expand (DM-Makro-Mechanik: Expansion/Hygiene/Schachtelung) =="
run dmexpand           $PRE lisp/dm-expand-tests.lsp
echo "== salvage-libs (macros/arrays/sets) =="
run libs               $PRE lisp/lib-macros.lsp lisp/lib-arrays.lsp lisp/lib-sets.lsp lisp/lib-tests.lsp
echo "== trace =="
run trace              $PRE lisp/lib-trace.lsp lisp/trace-test.lsp
echo "== string/symbol =="
run strsym             $PRE lisp/string-symbol-tests.lsp
echo "== cl-compat =="
run clcompat          $PRE lisp/cl-compat.lsp lisp/cl-compat-tests.lsp
echo "== dialect-vs-cl (Pinning der Dialekt-Abweichungen) =="
run dialectvscl       $PRE lisp/cl-compat.lsp lisp/dialect-vs-cl-tests.lsp
echo "== demo-simplify (kleines symbolisches Algebra-Programm) =="
run demosimplify      $PRE lisp/cl-compat.lsp lisp/demo-simplify.lsp lisp/demo-simplify-tests.lsp
echo "== demo-calc (winziger Ausdrucks-Interpreter mit LET/IF) =="
run democalc          $PRE lisp/cl-compat.lsp lisp/demo-calc.lsp lisp/demo-calc-tests.lsp
echo "== demo-db (winzige Alist-Datenbank: PAIRLIS/ACONS/RASSOC) =="
run demodb            $PRE lisp/cl-compat.lsp lisp/demo-db.lsp lisp/demo-db-tests.lsp
echo "== demo-combined (alle MVP-Samples zusammen: Koexistenz + Kombination) =="
run democombined      $PRE lisp/cl-compat.lsp lisp/lib-diff.lsp lisp/demo-simplify.lsp lisp/demo-calc.lsp lisp/demo-db.lsp lisp/demo-combined-smoke.lsp
echo "== backquote + defmacro =="
run backquote         $PRE lisp/backquote-tests.lsp
echo "== prog-go-boundary (PROG/GO-Kontrollflussmatrix) =="
run proggoboundary    $PRE lisp/prog-go-boundary-tests.lsp
echo "== editor-core (IDE-Logik-Schicht) =="
run editor            $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/editor-tests.lsp
echo "== edit-commands (Kill/Yank, Wort-Bewegung, Suche) =="
run editcmds          $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/edit-commands-tests.lsp
echo "== buffers (Multi-Buffer, Modeline, Minibuffer) =="
run buffers           $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-buffers.lsp lisp/buffers-tests.lsp
echo "== ide-session (Keymap + Dispatch, Minibuffer-Modus) =="
run idesession        $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/ide-session-tests.lsp
echo "== ide-undo (Undo/Redo-Ring) =="
run ideundo           $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp lisp/ide-undo-tests.lsp
echo "== ide-view (Viewport/Scroll + Screen-Komposition) =="
run ideview           $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-view.lsp lisp/ide-view-tests.lsp
echo "== ide-integration (voller IDE-Stack, End-to-End-Session) =="
run ideintegration    $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp lisp/lib-ide-view.lsp lisp/ide-integration-tests.lsp
echo "== ide-editor-demo (vorfuehrbarer End-to-End-Editor, gerenderte Frames) =="
run ideeditordemo     $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp lisp/lib-ide-view.lsp lisp/ide-editor-demo.lsp
echo "== loop-subset (Bibliotheks-Makro) =="
run loop              $PRE lisp/cl-compat.lsp lisp/lib-loop.lsp lisp/loop-tests.lsp
echo "== loop-c64-load (C64-LOAD-Variante: REPEAT+FOR IN+FOR FROM+COLLECT+SUM) =="
run loopc64load       lisp/prelude.lsp lisp/seq-native-c64-load-prelude.lsp lisp/lib-loop-c64-load.lsp lisp/loop-native-c64-load-smoke.lsp
echo "== defstruct-light (Bibliotheks-Makro) =="
run struct            $PRE lisp/cl-compat.lsp lisp/lib-struct.lsp lisp/struct-tests.lsp
echo "== struct-native-smoke (minimaler Stufe-3-Smoke: Lese-/Schreibpfad) =="
run structsmoke       $PRE lisp/cl-compat.lsp lisp/lib-struct.lsp lisp/struct-native-smoke.lsp
echo "== format-subset (Host-Builtin) =="
run format            $PRE lisp/format-tests.lsp
echo "== error-model (catch/throw/unwind-protect/handler-case) =="
run errormodel        $PRE lisp/error-tests.lsp
echo "== mini-clos (Single-Dispatch) =="
run clos              $PRE lisp/cl-compat.lsp lisp/lib-clos.lsp lisp/clos-tests.lsp
echo "== mini-clos-c64-load (C64-LOAD-Variante: erster Dispatch-Keil) =="
run closc64load       lisp/prelude.lsp lisp/seq-native-c64-load-prelude.lsp lisp/cl-compat.lsp lisp/lib-clos.lsp lisp/clos-native-c64-load-smoke.lsp
echo "== paredit-subset (strukturiertes Editieren) =="
run paredit           $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp lisp/paredit-tests.lsp
echo "== ide (eval-defun + Paredit-Keymap) =="
run ide               $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp lisp/lib-ide.lsp lisp/ide-tests.lsp
echo "== combined (alle Libs zusammen, Kollisionsfreiheit) =="
run combined          $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/lib-loop.lsp lisp/lib-struct.lsp lisp/lib-clos.lsp lisp/lib-seq.lsp lisp/lib-modules.lsp lisp/editor-core.lsp lisp/lib-paredit.lsp lisp/lib-ide.lsp lisp/combined-smoke.lsp
echo "== c64hw (Phase-5-Mathematik/Konstanten) =="
run c64hw             $PRE lisp/lib-c64hw.lsp lisp/c64hw-tests.lsp
echo "== c64fx (High-Level-Algorithmen) =="
run c64fx             $PRE lisp/lib-c64hw.lsp lisp/lib-c64fx.lsp lisp/c64fx-tests.lsp
echo "== c64io (Komfort-Wrapper -> simuliertes RAM) =="
run c64io             $PRE lisp/lib-c64hw.lsp lisp/lib-c64fx.lsp lisp/lib-c64io.lsp lisp/c64io-tests.lsp
echo "== c64term (Phase-5-Ausgabe-Bruecke: Screen-Code + IDE-Frame -> Screen-RAM) =="
run c64term           $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/lib-c64hw.lsp lisp/lib-c64fx.lsp lisp/lib-c64io.lsp lisp/lib-c64term.lsp lisp/editor-core.lsp lisp/lib-edit-commands.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-undo.lsp lisp/lib-ide-view.lsp lisp/c64term-tests.lsp
echo "== c64key (Phase-5-Eingabe-Bruecke: CIA-Matrix-Scan -> IDE-Token) =="
run c64key            $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/lib-c64key.lsp lisp/c64key-tests.lsp
echo "== c64key-load (LOAD-sichere Eingabe-Bruecke mit explizitem Init) =="
run c64keyload        $PRE lisp/lib-c64key-load.lsp lisp/c64key-load-tests.lsp
echo "== mvp-c64-ide-miniprofile (Input-Token -> Session-Dispatch) =="
run mvpideprofile     $PRE lisp/lib-macros.lsp lisp/cl-compat.lsp lisp/lib-c64key-load.lsp lisp/lib-c64io.lsp lisp/lib-c64term.lsp lisp/editor-core.lsp lisp/lib-buffers.lsp lisp/lib-ide-session.lsp lisp/lib-ide-view.lsp lisp/mvp-c64-ide-miniprofile-smoke.lsp lisp/mvp-c64-ide-miniprofile-tests.lsp
echo "== platform (backend-agnostischer Plattform-Layer, Mock-Backend) =="
run platform          $PRE lisp/lib-platform.lsp lisp/platform-tests.lsp
echo "== platform-c64 (C64-Backend, simuliertes PEEK/POKE-RAM) =="
run platformc64       $PRE lisp/lib-c64hw.lsp lisp/lib-platform-c64.lsp lisp/platform-c64-tests.lsp
echo "== platform-mega65 (MEGA65-Backend-Schnitt, simuliertes PEEK/POKE-RAM) =="
run platformmega65    $PRE lisp/lib-platform.lsp lisp/lib-mega65hw.lsp lisp/lib-platform-mega65.lsp lisp/platform-mega65-tests.lsp
echo "== platform-mega65-bank4 (sichtbarer MEGA65-Bank-4-Backend-Schnitt) =="
run platformmega65bank4 $PRE lisp/lib-platform.lsp lisp/lib-mega65hw.lsp lisp/lib-platform-mega65-bank4.lsp lisp/platform-mega65-bank4-tests.lsp
echo "== platform-mega65-bank4-load (sichtbarer MEGA65-Bank-4-Backend via Lisp LOAD) =="
run platformmega65bank4load $PRE lisp/lib-platform.lsp lisp/lib-mega65hw.lsp lisp/platform-mega65-bank4-load-tests.lsp
echo "== platform-mega65-bank4-savefmt (LOAD-sichere MEGA65-Bank-4-Zeichner, simuliertes RAM) =="
run platformmega65bank4savefmt $PRE lisp/lib-platform-mega65-bank4-load.lsp lisp/platform-mega65-bank4-savefmt-tests.lsp
echo "== platform-mega65-bank4-demo-savefmt (LOAD-sichere MEGA65-Bank-4-Demo, simuliertes RAM) =="
run platformmega65bank4demosavefmt $PRE lisp/lib-platform-mega65-bank4-load.lsp lisp/platform-demo-c64-load.lsp lisp/platform-mega65-bank4-demo-savefmt-tests.lsp
echo "== platform-c64-load (C64-LOAD-sichere Platform-Zeichner, simuliertes RAM) =="
run platformc64load   $PRE lisp/lib-platform-c64-load.lsp lisp/platform-demo.lsp lisp/platform-demo-c64-load.lsp lisp/platform-c64-load-tests.lsp
echo "== platform-demo (Beispiel-App gegen die API, Mock-Backend) =="
run platformdemo      $PRE lisp/lib-platform.lsp lisp/platform-demo.lsp lisp/platform-demo-tests.lsp
echo "== modules (require/provide) =="
run modules           $PRE lisp/lib-modules.lsp lisp/module-tests.lsp
echo "== seq (Sequenz-Bibliothek) =="
run seq               $PRE lisp/cl-compat.lsp lisp/lib-seq.lsp lisp/seq-tests.lsp
echo "== seq-native-smoke (minimaler GENSYM-freier Stufe-3-Smoke) =="
run seqsmoke          $PRE lisp/cl-compat.lsp lisp/lib-seq.lsp lisp/seq-native-smoke.lsp
echo "== autoload (lazy Laden pro Datei) =="
run autoload          $PRE lisp/lib-autoload.lsp lisp/autoload-tests.lsp
echo "== c64-autoload (granulares lazy Laden der Komfortschicht) =="
run c64autoload       $PRE lisp/lib-autoload.lsp lisp/lib-c64-autoload.lsp lisp/c64-autoload-tests.lsp
echo "== diff (symbolisch, dynamisches Scoping) =="
run diff              $PRE lisp/lib-diff.lsp lisp/diff-tests.lsp
echo "== demos =="
run demos              $PRE lisp/demos.lsp
echo "== benchmarks =="
run bench              $PRE lisp/benchmarks/bench.lsp

echo "== vice-crosscheck (Host-Spiegel; Marker VICECHK <pass> <fail>) =="
cc="$($PY $INT lisp/vice-crosscheck.lsp 2>&1)"
printf '%s\n' "$cc" | sed 's/^/  /'
ccm="$(printf '%s\n' "$cc" | sed -n 's/.*VICECHK [0-9][0-9]* \([0-9][0-9]*\).*/\1/p')"
[ -z "$ccm" ] && ccm=1
printf '[vicechk] %s\n\n' "$cc"
fail_total=$((fail_total + ccm))

echo "== compact-model (4-Byte-Cons / Immediate-Fixnum / Pointer-Reversal-GC) =="
if $PY tools/host-lisp/compact-model.py >/dev/null 2>&1; then
  echo "  [compact-model] ALLES OK"
else
  echo "  [compact-model] FEHLER"; fail_total=$((fail_total + 1))
fi
echo

echo "== vm-model (Bytecode-VM: Subset + Closures + TCO) =="
if $PY tools/host-lisp/vm-model.py >/dev/null 2>&1; then
  echo "  [vm-model] ALLES OK"
else
  echo "  [vm-model] FEHLER"; fail_total=$((fail_total + 1))
fi
echo

echo "== fixedpoint-model (16.16 Festkomma) =="
if $PY tools/host-lisp/fixedpoint-model.py >/dev/null 2>&1; then
  echo "  [fixedpoint-model] ALLES OK"
else
  echo "  [fixedpoint-model] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== cpu6502 (funktionaler 6502-Kern: native Routinen ohne VICE) =="
if $PY tools/host-lisp/cpu6502.py >/dev/null 2>&1; then
  echo "  [cpu6502] ALLES OK"
else
  echo "  [cpu6502] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== cia-keyboard (Phase-5-Eingabe-Oracle: CIA-Matrix-Differenzmodell) =="
if $PY tools/host-lisp/cia_keyboard.py >/dev/null 2>&1; then
  echo "  [cia-keyboard] ALLES OK"
else
  echo "  [cia-keyboard] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== phase4-disasm (Phase-4-VM-Opcode-Disassembler + .acme-Drift) =="
if $PY tools/host-lisp/phase4_disasm.py --selftest >/dev/null 2>&1; then
  echo "  [phase4-disasm] ALLES OK"
else
  echo "  [phase4-disasm] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== phase4-vm (Host-Referenzmodell von Codex' nativer Phase-4-VM) =="
if $PY tools/host-lisp/phase4_vm.py --selftest >/dev/null 2>&1; then
  echo "  [phase4-vm] ALLES OK"
else
  echo "  [phase4-vm] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== phase4-srcexpr (Source-Expr-IR-Decoder: prueft Codex' Expected-Arrays) =="
if $PY tools/host-lisp/phase4_srcexpr.py --selftest >/dev/null 2>&1; then
  echo "  [phase4-srcexpr] ALLES OK"
else
  echo "  [phase4-srcexpr] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== selective-link (Phase-7: Dead-Code-Elimination + Dynamik-Verdikt) =="
if $PY tools/host-lisp/selective_link.py --selftest >/dev/null 2>&1; then
  echo "  [selective-link] ALLES OK"
else
  echo "  [selective-link] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== lint (.lsp Klammerbilanz + Doppeldefinitionen) =="
if $PY tools/host-lisp/lint_lsp.py; then
  echo "  [lint] OK"
else
  echo "  [lint] FEHLER (paren/syntax)"; fail_total=$((fail_total + 1))
fi
echo "== property-tests (Round-Trip + Arithmetik, generativ) =="
if $PY tools/host-lisp/property_tests.py >/dev/null 2>&1; then
  echo "  [property] ALLES OK"
else
  echo "  [property] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== repl-transcript (REPL + Break-Loop) =="
if $PY tools/host-lisp/repl_test.py >/dev/null 2>&1; then
  echo "  [repl] ALLES OK"
else
  echo "  [repl] FEHLER"; fail_total=$((fail_total + 1))
fi
echo "== host-bcvm (Differential: Tree-Walker == Bytecode-VM) =="
if $PY tools/host-lisp/host_bcvm.py >/dev/null 2>&1; then
  echo "  [host-bcvm] ALLES OK"
else
  echo "  [host-bcvm] FEHLER"; fail_total=$((fail_total + 1))
fi
echo

if [ "$fail_total" -eq 0 ]; then
  echo "ALLE SUITEN GRUEN"
  exit 0
fi
echo "FEHLER: $fail_total CHECK(s) fehlgeschlagen"
exit 1
