#!/bin/sh
# Per-function .text sizes of the hot resident kernel TUs, product-shaped
# defines, -Oz, pinned mos-mega65-clang.  Single-TU and through the LTO codegen
# pipeline.  NOT a product build and NOT a link.
#
#   sh scripts/kernel-diet-size.sh snapshot <outdir>     # measure this tree
#   sh scripts/kernel-diet-size.sh delta <base> <new>    # compare two snapshots
set -e
LLVM_MOS_ROOT="${LLVM_MOS_ROOT:-tools/llvm-mos}"
CC="$LLVM_MOS_ROOT/bin/mos-mega65-clang"
NM="$LLVM_MOS_ROOT/bin/llvm-nm"
SIZE="$LLVM_MOS_ROOT/bin/llvm-size"

TUS="vm mem reader printer symbol"

DEFS="-DLISP65_MEGA65_MATH_OVERRIDE -DLISP65_F011_GUARD_ASM -DVM_CODEBUF=56 \
-DLISP65_SYMPOOL_EXT -DLISP65_SYMVAL_EXT -DLISP65_NAMEOFF_EXT -DGC_ROOTS=128 \
-DLISP65_STDLIB_EXT_METADATA -DLISP65_STDLIB_EXTERNAL_BLOB -DLISP65_MARK_BITMAP \
-DLISP65_EXT_HEAP -DLISP65_SCREEN_DRIVER -DLISP65_VM_SCREEN_PRIMS \
-DLISP65_VM_STDLIB_IO_WRAPPERS -DLISP65_VM_GLOBAL_PRIMS -DLISP65_MACROEXPAND_PRIM \
-DLISP65_LCC_INSTALL -DLISP65_LCC_INSTALL_OVERLAY_SLOT_BASE=30 \
-DLISP65_BOOT_FASTPATH_SLOT_BASE=33 -DLISP65_ERROR_OVERLAY -DLISP65_ERROR_OVERLAY_SLOT=36 \
-DLISP65_LCC_INSTALL_CLOSURES -DLISP65_TREEWALK_STDLIB_BRIDGES \
-DLISP65_OUTPUT_WRAPPERS_IN_STDLIB -DLISP65_SCREEN_BULK_P_IN_STDLIB -DLISP65_TREEWALK_STRIP \
-DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DLISP65_ATTIC_LIBRARY_SHELF -DLISP65_C1_COMPILER_TIER \
-DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DEXT_CELLS=1024 -DLISP65_NURSERY_HYSTERESIS=192 \
-DLISP65_STRING_ARENA -DLISP65_FIRST_CLASS_BUFFER -DSTR_ARENA_SIZE=0x2480 \
-DDISK_EXT_BASE=0x6900 -DDISK_EXT_FILE_MAX=0x9600 -DLISP65_COMPILE_STRING \
-DLISP65_SYMFN_EXT -DSYMPOOL_EXT_OFF=0xc680 -DNAMEPOOL=10208 -DMAX_SYM=752 \
-DVM_DIR_MAX=608 -DREPL_BUF_MAX=192 -DHIST_MAX=64 -DLISP65_REPL_HISTORY_IN_BUF \
-DLISP65_REPL_BANNER_REQUIRED"
COMMON="-Oz -Wall -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA -DLISP65_REPL \
-DHEAP_CELLS=48 $DEFS -DLISP65_STDLIB_BOOT_OVERLAY_CODE -DLISP65_STAGED_BOOT_OVERLAY \
-DLISP65_RUNTIME_OVERLAY -DLISP65_STACK_GUARD -DLISP65_DIALECT_V2 -Isrc"

emit() {
  $NM -S --defined-only "$1" \
    | awk '$3=="T"||$3=="t"||$3=="W" { printf "%s %d\n", $4, strtonum("0x" $2) }'
}

snapshot() {
  out="$1"; mkdir -p "$out"
  : > "$out/sizes-nolto.txt"; : > "$out/sizes-lto.txt"; : > "$out/bss.txt"
  for t in $TUS; do
    $CC $COMMON -fno-lto -c "src/$t.c" -o "$out/$t.nolto.o"
    emit "$out/$t.nolto.o" >> "$out/sizes-nolto.txt"
    $CC $COMMON -c "src/$t.c" -o "$out/$t.bc"
    $CC $COMMON -fno-lto -x ir -c "$out/$t.bc" -o "$out/$t.lto.o"
    emit "$out/$t.lto.o" >> "$out/sizes-lto.txt"
    for k in nolto lto; do
      $SIZE "$out/$t.$k.o" \
        | awk -v t="$t" -v k="$k" 'NR==2 { printf "%-8s %-6s text=%-7d data=%-5d bss=%d\n", t, k, $1, $2, $3 }' \
        >> "$out/bss.txt"
    done
  done
  # Aggregate per symbol name (a name can occur in more than one TU) and sort in
  # the C collation join expects; a locale sort silently mis-pairs rows.
  for k in nolto lto; do
    awk '{ t[$1] += $2 } END { for (n in t) printf "%s %d\n", n, t[n] }' "$out/sizes-$k.txt" \
      | LC_ALL=C sort > "$out/.tmp" && mv "$out/.tmp" "$out/sizes-$k.txt"
  done
  printf 'nolto total .text %s\n' "$(awk '{t+=$2} END{print t}' "$out/sizes-nolto.txt")"
  printf 'lto   total .text %s\n' "$(awk '{t+=$2} END{print t}' "$out/sizes-lto.txt")"
}

delta() {
  a="$1"; b="$2"
  for k in nolto lto; do
    echo "--- $k"
    LC_ALL=C join -a1 -a2 -e 0 -o 0,1.2,2.2 "$a/sizes-$k.txt" "$b/sizes-$k.txt" \
      | awk '{ d=$3-$2; if (d!=0) printf "%8d  base=%-7d new=%-7d  %s\n", d, $2, $3, $1; t+=d }
             END { printf "%8d  TOTAL\n", t }'
  done
  echo "--- bss/data changes"
  diff "$a/bss.txt" "$b/bss.txt" && echo "(none)"
}

case "$1" in
  snapshot) shift; snapshot "$@" ;;
  delta)    shift; delta "$@" ;;
  *) echo "usage: $0 snapshot <outdir> | $0 delta <basedir> <newdir>" >&2; exit 2 ;;
esac
