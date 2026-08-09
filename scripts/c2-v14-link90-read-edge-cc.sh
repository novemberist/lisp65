#!/bin/bash
# Diagnostic-only compiler wrapper for the Link-90 read/return/refill split.
set -eu
root=$(git rev-parse --show-toplevel)
args=()
for arg in "$@"; do
  if [[ "$arg" == "-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=8192" ]]; then
    args+=("-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=8160")
  else
    args+=("$arg")
  fi
done
exec "$root/tools/llvm-mos/bin/mos-mega65-clang" \
  -DLISP65_V14_READ_EDGE_WITNESS \
  -DLISP65_V14_WITNESS_SHAPE_OFF=0x06e1 \
  -DLISP65_V14_WITNESS_REFILL_PC=0x002e \
  -DLISP65_V14_WITNESS_RETURN_PC=0x0036 \
  "${args[@]}"
