#!/bin/bash
# Diagnostic-only compiler wrapper for the Link-90 mechanism witness.
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
  -DLISP65_V14_MECHANISM_WITNESS \
  -DLISP65_V14_MECH_SHAPE_OFF=0x06e1 \
  -DLISP65_V14_MECH_SECOND_CALL_PC=0x002b \
  -DLISP65_V14_MECH_SECOND_RETURN_PC=0x002e \
  -DLISP65_V14_MECH_HELPER_OFF=0x0310 \
  "${args[@]}"
