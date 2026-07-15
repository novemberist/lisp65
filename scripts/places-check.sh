#!/bin/sh
# Host gate for the setf MVP in lib/stdlib-places.lisp across treewalk and lcc paths.
set -e
cd "$(dirname "$0")/.."
cc="${HOSTCC:-cc}"
out=build/equivalence
mkdir -p "$out"

$cc -std=c99 -Wall -Wno-unused-function \
  -DLISP65_VM -DLISP65_EVAL_CONTROL_SF -DLISP65_EVAL_DIV_PRIM \
  -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM -DLISP65_LCC_INSTALL \
  -DLISP65_LCC_INSTALL_CLOSURES \
  -DHEAP_CELLS=12000 -DGC_ROOTS=2048 -DMAX_SYM=768 -DNAMEPOOL=16384 -DVM_DIR_MAX=128 \
  -Isrc scripts/places-check-main.c \
  src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c \
  src/io.c src/interrupt.c src/screen.c \
  -o "$out/places-check" 2> "$out/places-check.build.log" || {
    echo "places-check: Build fehlgeschlagen — $out/places-check.build.log"
    grep -iE "error|undefined" "$out/places-check.build.log" | head -6
    exit 2
  }
"$out/places-check"
