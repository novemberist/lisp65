#!/bin/sh
# Run the lisp65 equivalence suite (anti-drift rule 2).
# Build the multi-engine harness, run the corpus in separate processes, and diff the output.
# Exit 0 means no drift. Usage: sh scripts/equivalence-check.sh [corpus.lisp]
set -e
cc="${HOSTCC:-cc}"
corpus="${1:-tests/equivalence/forms.lisp}"
out=build/equivalence
mkdir -p "$out"

$cc -std=c99 -Wall -Wno-unused-function \
  -DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS -DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF -DLISP65_VM_APPLY_OPFN -DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
  -DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 -DVM_DIR_MAX=128 \
  -DIO_BUF_MAX=16 \
  -Isrc scripts/equivalence-main.c \
  src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c \
  src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c \
  -o "$out/equivalence-check"

"$out/equivalence-check" tree "$corpus" > "$out/tree.out"
"$out/equivalence-check" vm   "$corpus" > "$out/vm.out"

fail=0
if diff -u "$out/tree.out" "$out/vm.out" > "$out/drift.diff" 2>&1; then
  n=$(grep -c '=>' "$out/tree.out" || true)
  echo "equivalence-check: PASS forms=$n (Treewalk[CONTROL_SF] == Compiler)"
else
  echo "equivalence-check: DRIFT (CONTROL_SF-Route) — Treewalk vs. Compiler weichen ab:"
  grep '^[+-]' "$out/drift.diff" | grep -v '^[+-][+-]' | head -20
  echo "(voll: $out/drift.diff)"
  fail=1
fi

# ---- Second run: disk-macro route through lib/prelude-macros.lisp ----
# Treewalk omits LISP65_EVAL_CONTROL_SF; cond/and/or/case come from preloaded defmacros.
# Matching the same compiler output proves both routes semantically identical.
$cc -std=c99 -Wall -Wno-unused-function \
  -DLISP65_COMPILE_REPL -DLISP65_VM -DLISP65_VM_GLOBAL_PRIMS -DLISP65_EVAL_PRIMS -DLISP65_EVAL_DIV_PRIM -DLISP65_VM_APPLY_OPFN -DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
  -DHEAP_CELLS=8192 -DGC_ROOTS=1024 -DMAX_SYM=512 -DNAMEPOOL=8192 -DVM_DIR_MAX=128 \
  -DIO_BUF_MAX=16 \
  -Isrc scripts/equivalence-main.c \
  src/eval.c src/compile.c src/compile_repl.c src/lcc_install_overlay.c src/vm.c \
  src/mem.c src/symbol.c src/reader.c src/printer.c src/io.c src/interrupt.c src/screen.c \
  -o "$out/equivalence-nogate"

"$out/equivalence-nogate" tree "$corpus" --preload lib/prelude-macros.lisp > "$out/tree-macros.out"
if diff -u "$out/tree-macros.out" "$out/vm.out" > "$out/drift-macros.diff" 2>&1; then
  n=$(grep -c '=>' "$out/tree-macros.out" || true)
  echo "equivalence-check: PASS forms=$n (Treewalk[Disk-Makros] == Compiler)"
else
  echo "equivalence-check: DRIFT (Disk-Makro-Route):"
  grep '^[+-]' "$out/drift-macros.diff" | grep -v '^[+-][+-]' | head -20
  echo "(voll: $out/drift-macros.diff)"
  fail=1
fi

# ---- Third diff: case, macro route versus compiler; CONTROL_SF has no sf_case ----
"$out/equivalence-nogate" tree tests/equivalence/forms-case.lisp --preload lib/prelude-macros.lisp > "$out/tree-case.out"
"$out/equivalence-check"  vm   tests/equivalence/forms-case.lisp > "$out/vm-case.out"
if diff -u "$out/tree-case.out" "$out/vm-case.out" > "$out/drift-case.diff" 2>&1; then
  echo "equivalence-check: PASS case-Formen (Disk-Makro == Compiler)"
else
  echo "equivalence-check: DRIFT (case):"
  grep '^[+-]' "$out/drift-case.diff" | grep -v '^[+-][+-]' | head -10
  fail=1
fi

# ---- Macro-only sanity: broader disk-macro semantics not yet supported by the device compiler ----
"$out/equivalence-nogate" tree tests/equivalence/forms-macros-only.lisp --preload lib/prelude-macros.lisp > "$out/tree-macros-only.out"
cat > "$out/tree-macros-only.expected" <<'EOF'
(case (quote b) ((a c) 1) ((b d) 2) (otherwise 3)) => 2
(case (quote q) ((a c) 1) (otherwise 3)) => 3
(case (quote a) ((a) 11) (t 22)) => 11
EOF
if diff -u "$out/tree-macros-only.expected" "$out/tree-macros-only.out" > "$out/drift-macros-only.diff" 2>&1; then
  echo "equivalence-check: PASS macro-only case-Listenkeys"
else
  echo "equivalence-check: DRIFT (macro-only):"
  grep '^[+-]' "$out/drift-macros-only.diff" | grep -v '^[+-][+-]' | head -10
  fail=1
fi

# ---- Fourth diff: lcc byte oracle ----
# lib/lcc.lisp must emit bytes identical to the Python reference compiler.
if python3 scripts/lcc-oracle.py --binary "$out/equivalence-check" > "$out/lcc-oracle.out" 2>&1; then
  tail -1 "$out/lcc-oracle.out"
else
  echo "equivalence-check: DRIFT (lcc-Byte-Orakel):"
  grep -A2 "DRIFT" "$out/lcc-oracle.out" | head -12
  fail=1
fi
# ---- Fifth diff: execute lcc-compiled code ----
# vm = C compiler reference; lcc = Lisp compiler -> bc_assemble -> vm_run. Diff results.
"$out/equivalence-check" vm  tests/equivalence/lcc-run-forms.lisp > "$out/vm-run.out"
"$out/equivalence-check" lcc tests/equivalence/lcc-run-forms.lisp --preload lib/lcc.lisp > "$out/lcc-run.out"
if diff -u "$out/vm-run.out" "$out/lcc-run.out" > "$out/drift-lccrun.diff" 2>&1; then
  n=$(grep -c '=>' "$out/lcc-run.out" || true)
  echo "equivalence-check: PASS forms=$n (lcc-kompilierter Code läuft == C-Compiler)"
else
  echo "equivalence-check: DRIFT (lcc-Lauf-Naht):"
  grep '^[+-]' "$out/drift-lccrun.diff" | grep -v '^[+-][+-]' | head -16
  fail=1
fi
# ---- Seventh diff: macros, tree versus lcc ----
"$out/equivalence-nogate" tree tests/equivalence/lcc-macro-forms.lisp --preload lib/prelude-macros.lisp > "$out/tree-macro.out" 2>/dev/null
"$out/equivalence-check" lcc  tests/equivalence/lcc-macro-forms.lisp --preload lib/lcc.lisp > "$out/lcc-macro.out"
if diff -u "$out/tree-macro.out" "$out/lcc-macro.out" > "$out/drift-macro4.diff" 2>&1; then
  n=$(grep -c '=>' "$out/lcc-macro.out" || true)
  echo "equivalence-check: PASS forms=$n (Makros: lcc == Treewalk; C-Compiler kann das nicht)"
else
  echo "equivalence-check: DRIFT (P4-Makros):"
  grep '^[+-]' "$out/drift-macro4.diff" | grep -v '^[+-][+-]' | head -14
  fail=1
fi
# ---- Eighth diff: P5 fixed point; lcc compiles itself ----
# The corpus contains lcc's source and probes. One lane uses treewalk lcc; the other first
# compiles lcc to bytecode. An empty diff proves lcc(lcc) == lcc.
grep -v '^;' lib/lcc.lisp > "$out/fixpoint.lisp"
cat tests/equivalence/lcc-fixpoint-probes.lisp >> "$out/fixpoint.lisp"
"$out/equivalence-check" tree "$out/fixpoint.lisp" --preload lib/lcc.lisp > "$out/fix-tree.out" 2>&1
"$out/equivalence-check" lcc  "$out/fixpoint.lisp" --preload lib/lcc.lisp > "$out/fix-lcc.out" 2>&1
if diff -u "$out/fix-tree.out" "$out/fix-lcc.out" > "$out/drift-fixpoint.diff" 2>&1; then
  n=$(grep -c 'lcc-compile-obj' tests/equivalence/lcc-fixpoint-probes.lisp || true)
  echo "equivalence-check: PASS FIXPUNKT (lcc kompiliert lcc; $n Proben Bytecode-lcc == Treewalk-lcc)"
else
  echo "equivalence-check: DRIFT (P5-Fixpunkt):"
  grep '^[+-]' "$out/drift-fixpoint.diff" | grep -v '^[+-][+-]' | head -14
  fail=1
fi
# ---- Ninth diff: P6b lcc-first REPL; (lcc-run form) equals the C compiler ----
# Wrapper echoes differ, so compare only value columns.
grep -vE '^;|^$' tests/equivalence/lcc-run-forms.lisp | sed 's/.*/(lcc-run (quote &))/' > "$out/lccrepl.lisp"
"$out/equivalence-check" tree "$out/lccrepl.lisp" --preload lib/lcc.lisp > "$out/lccrepl.out" 2>&1
awk -F'=>' 'NF>1{print $NF}' "$out/vm-run.out"   > "$out/vals-vm.txt"
awk -F'=>' 'NF>1{print $NF}' "$out/lccrepl.out" > "$out/vals-lcc.txt"
if diff -u "$out/vals-vm.txt" "$out/vals-lcc.txt" > "$out/drift-lccrepl.diff" 2>&1; then
  n=$(grep -c . "$out/vals-lcc.txt" || true)
  echo "equivalence-check: PASS forms=$n (lcc-first-REPL via lcc-install-Naht == C-Compiler)"
else
  echo "equivalence-check: DRIFT (P6b lcc-first-REPL):"
  grep '^[+-]' "$out/drift-lccrepl.diff" | grep -v '^[+-][+-]' | head -12
  fail=1
fi
exit $fail
