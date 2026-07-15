#!/bin/sh
# B1 gate: build and run the FASL emitter on the host, then validate it independently.
set -e
cd "$(dirname "$0")/.."
cc="${HOSTCC:-cc}"
out=build/equivalence
mkdir -p "$out"

$cc -std=c99 -Wall -Wno-unused-function \
  -DLISP65_VM -DLISP65_FASL -DLISP65_EVAL_CONTROL_SF -DLISP65_EVAL_PRIMS -DLISP65_EVAL_DIV_PRIM \
  -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM \
  -DLISP65_EXT_HEAP -DEXT_CELLS=4096 -DLISP65_MARK_BITMAP -DHEAP_CELLS=12000 -DGC_ROOTS=2048 -DMAX_SYM=768 -DNAMEPOOL=16384 -DVM_DIR_MAX=128 \
  -Isrc scripts/fasl-emit-check-main.c \
  src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c src/printer.c \
  src/io.c src/interrupt.c src/screen.c \
  -o "$out/fasl-emit-check" 2> "$out/fasl-emit-check.build.log" || {
    echo "fasl-emit-check: Build fehlgeschlagen — $out/fasl-emit-check.build.log"
    grep -iE "error|undefined" "$out/fasl-emit-check.build.log" | head -6
    exit 2
  }

"$out/fasl-emit-check" "$out/fasl-test.bin"
python3 scripts/fasl-validate.py "$out/fasl-test.bin"
