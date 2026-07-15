#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/lisp65-v2-carrier-cut-$$
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp"

cc=${HOSTCC:-cc}
report=${V2_CARRIER_CUT_REPORT:-$root/tests/bytecode/dialect-v2/evidence/capability-carrier/carrier-cut-verdict.json}
defs='-DLISP65_VM -DLISP65_V2_CARRIER_CUT -DLISP65_DIALECT_V2
-DLISP65_TREEWALK_STRIP -DLISP65_VM_NATIVE_APPLY
-DLISP65_V2_NATIVE_CAPABILITIES -DLISP65_V2_NATIVE_STRING_CODECS
-DLISP65_V2_SERVICE_REGISTRY_CLOSED -DLISP65_V2_WORKBENCH_SERVICES
-DLISP65_STRING_ARENA
-DHEAP_CELLS=512 -DGC_ROOTS=128 -DSTR_ARENA_SIZE=2048
-DMAX_SYM=128 -DNAMEPOOL=2048 -DVM_DIR_MAX=32 -DVM_CODEBUF=64'

# shellcheck disable=SC2086
"$cc" -std=c99 -Wall -Wextra -Werror -Wno-unused-function -O1 -g \
    -ffile-prefix-map="$root"=. \
    -fsanitize=address,undefined -fno-omit-frame-pointer $defs \
    -I"$root/src" "$root/scripts/v2-carrier-cut-main.c" \
    "$root/src/vm.c" "$root/src/mem.c" "$root/src/symbol.c" \
    "$root/src/interrupt.c" -o "$tmp/cut"

ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1 "$tmp/cut"
python3 "$root/tools/host-lisp/v2_carrier_state.py" --expect removed \
    --elf "$tmp/cut" --json-out "$report"

for missing in \
    LISP65_DIALECT_V2 LISP65_TREEWALK_STRIP LISP65_VM_NATIVE_APPLY \
    LISP65_V2_NATIVE_CAPABILITIES LISP65_V2_NATIVE_STRING_CODECS \
    LISP65_V2_SERVICE_REGISTRY_CLOSED
do
    reduced=$(printf '%s\n' "$defs" | sed "s/-D$missing\([[:space:]]\|$\)/\\1/g")
    # shellcheck disable=SC2086
    if "$cc" -std=c99 -I"$root/src" $reduced -c \
        "$root/scripts/v2-carrier-cut-main.c" -o "$tmp/missing.o" \
        >"$tmp/missing.log" 2>&1; then
        echo "v2-carrier-cut: FAIL missing prerequisite accepted: $missing" >&2
        exit 1
    fi
    grep -q "requires $missing" "$tmp/missing.log" || {
        echo "v2-carrier-cut: FAIL missing prerequisite lacked hard diagnostic: $missing" >&2
        cat "$tmp/missing.log" >&2
        exit 1
    }
done

printf 'v2-carrier-cut: prerequisite-negative PASS count=6\n'
