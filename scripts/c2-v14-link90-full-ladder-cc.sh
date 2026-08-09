#!/bin/bash
# Diagnostic-only compiler wrapper for the Link-90 full remaining-edge ladder.
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
  -DLISP65_V14_FULL_LADDER_WITNESS \
  -DLISP65_V14_LADDER_SHAPE_OFF=0x06e1 \
  -DLISP65_V14_LADDER_FIRST_RETURN_PC=0x0024 \
  -DLISP65_V14_LADDER_HELPER_OFF=0x0310 \
  "${args[@]}"
