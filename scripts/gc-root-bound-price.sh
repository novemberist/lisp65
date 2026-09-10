#!/bin/sh
# Object price of the qq_list/append2 root bound, in the two configurations that
# matter: the product one (LISP65_TREEWALK_STRIP -- where the guarded code is
# stripped, so the price should be zero) and a non-stripped one (every host gate
# and the equivalence oracles).
# usage: sh scripts/gc-root-bound-price.sh <base-rev> [outdir]
set -e
BASE="${1:-root-index-narrowing}"
OUT="${2:-build/gc-root-bound-price}"
CC=tools/llvm-mos/bin/mos-mega65-clang
NM=tools/llvm-mos/bin/llvm-nm
SIZE=tools/llvm-mos/bin/llvm-size
rm -rf "$OUT/base" "$OUT/new"
mkdir -p "$OUT/base" "$OUT/new"
git archive "$BASE" src | tar -x -C "$OUT/base"
cp -r src "$OUT/new/src"

DEFS="-DLISP65_MEGA65_MATH_OVERRIDE -DVM_CODEBUF=56 -DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT \
-DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 -DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB \
-DLISP65_MARK_BITMAP -DLISP65_EXT_HEAP -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS \
-DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM \
-DLISP65_LCC_INSTALL -DLISP65_LCC_INSTALL_CLOSURES -DLISP65_TREEWALK_STDLIB_BRIDGES \
-DLISP65_COMPILE_STRING -DMEGA65_F011_LOAD -DMEGA65_F011_WRITE -DLISP65_DISK_LIBS \
-DIO_BUF_MAX=1 -DEXT_CELLS=1024 -DLISP65_STRING_ARENA -DSTR_ARENA_SIZE=0x2480 \
-DDISK_EXT_BASE=0x6900 -DDISK_EXT_FILE_MAX=0x9600 -DLISP65_SYMFN_EXT -DSYMPOOL_EXT_OFF=0xc680 \
-DNAMEPOOL=10208 -DMAX_SYM=752 -DVM_DIR_MAX=608 -DLISP65_EVAL_PRIMS -DLISP65_EVAL_CONTROL_SF"
COMMON="-Oz -Wall -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA -DLISP65_REPL \
-DHEAP_CELLS=48 $DEFS -DLISP65_DIALECT_V2"

price() {   # price <label> <tu> <extra defines...>
  label="$1"; tu="$2"; shift 2
  for side in base new; do
    $CC $COMMON "$@" -fno-lto -I"$OUT/$side/src" -c "$OUT/$side/src/$tu.c" -o "$OUT/$side-$label.nolto.o"
    $CC $COMMON "$@" -I"$OUT/$side/src" -c "$OUT/$side/src/$tu.c" -o "$OUT/$side-$label.bc"
    $CC $COMMON "$@" -fno-lto -x ir -c "$OUT/$side-$label.bc" -o "$OUT/$side-$label.lto.o"
  done
  for k in nolto lto; do
    b=$($SIZE "$OUT/base-$label.$k.o" | awk 'NR==2{print $1}')
    n=$($SIZE "$OUT/new-$label.$k.o"  | awk 'NR==2{print $1}')
    printf '%-22s %-6s base=%-7s new=%-7s delta=%s\n' "$label" "$k" "$b" "$n" "$((n-b))"
  done
}

echo "=== product configuration (LISP65_TREEWALK_STRIP) ==="
price eval.c-stripped eval -DLISP65_TREEWALK_STRIP
price vm.c-stripped   vm   -DLISP65_TREEWALK_STRIP -DLISP65_VM_NATIVE_APPLY -DLISP65_LCC_INSTALL_CLOSURES
echo "=== non-stripped configuration (host gates, equivalence oracles) ==="
price eval.c-full eval
price vm.c-full   vm -DLISP65_VM_NATIVE_APPLY -DLISP65_LCC_INSTALL_CLOSURES
