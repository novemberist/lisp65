#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/lisp65-v2-workbench-services-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp"

cc=${HOSTCC:-cc}
defs='-DLISP65_VM -DLISP65_DIALECT_V2 -DLISP65_V2_WORKBENCH_SERVICES
-DLISP65_V2_SERVICE_REGISTRY_CLOSED -DLISP65_V2_CARRIER_CUT
-DLISP65_VM_NATIVE_APPLY
-DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS
-DLISP65_STRING_ARENA -DLISP65_EXT_HEAP -DEXT_CELLS=1024
-DHEAP_CELLS=4096 -DGC_ROOTS=256 -DSTR_ARENA_SIZE=4096
-DMAX_SYM=512 -DNAMEPOOL=8192 -DVM_DIR_MAX=128 -DVM_CODEBUF=64
-DLISP65_COMPILE_STRING -DLISP65_LCC_INSTALL -DLISP65_MACROEXPAND_PRIM
-DLISP65_TREEWALK_STRIP -DMEGA65_F011_LOAD -DMEGA65_F011_WRITE
-DLISP65_NUMERIC_ERRORS'

cut_prereqs='LISP65_VM LISP65_DIALECT_V2 LISP65_TREEWALK_STRIP
LISP65_VM_NATIVE_APPLY LISP65_V2_NATIVE_CAPABILITIES
LISP65_V2_NATIVE_STRING_CODECS LISP65_V2_SERVICE_REGISTRY_CLOSED'
for missing in $cut_prereqs; do
    prereq_defs='-DLISP65_V2_CARRIER_CUT'
    for required in $cut_prereqs; do
        if [ "$required" != "$missing" ]; then
            prereq_defs="$prereq_defs -D$required"
        fi
    done
    if printf '#include "eval.h"\n' | \
        "$cc" -std=c99 $prereq_defs -I"$root/src" -x c -c - \
        -o "$tmp/missing-$missing.o" >"$tmp/missing-$missing.log" 2>&1; then
        echo "v2-workbench-services: FAIL carrier cut accepted missing $missing" >&2
        exit 1
    fi
    grep -q 'complete staged v2 VM capability profile' \
        "$tmp/missing-$missing.log"
done

# shellcheck disable=SC2086
"$cc" -std=c99 -Wall -Wextra -Werror -Wno-unused-function \
    -fsanitize=address,undefined -fno-omit-frame-pointer $defs \
    -I"$root/src" \
    "$root/scripts/v2-workbench-services-main.c" \
    "$root/src/eval.c" "$root/src/lcc_install_overlay.c" \
    "$root/src/vm.c" "$root/src/mem.c" "$root/src/symbol.c" \
    "$root/src/reader.c" "$root/src/printer.c" \
    "$root/src/interrupt.c" "$root/src/screen.c" \
    -o "$tmp/check"

carrier_symbols=$(nm --defined-only "$tmp/check" | awk '
    $3 == "apply" || $3 == "apply_prim" ||
    $3 == "eval_vm_apply" || $3 == "eval_vm_bridge" ||
    $3 == "vm_treewalk_apply" || $3 == "vm_treewalk_call" { print $3 }
')
if [ -n "$carrier_symbols" ]; then
    echo "v2-workbench-services: FAIL carrier symbols survived cut: $carrier_symbols" >&2
    exit 1
fi
if ! nm --defined-only "$tmp/check" | awk '$3 == "vm_native_apply" { found=1 } END { exit !found }'; then
    echo 'v2-workbench-services: FAIL vm_native_apply missing from cut' >&2
    exit 1
fi

ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1 \
    "$tmp/check"
