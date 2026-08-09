#!/bin/bash
# Diagnostic-only compiler wrapper: Link-90 VM fault site plus live VIC geometry.
set -eu
root=$(git rev-parse --show-toplevel)
args=()
for arg in "$@"; do
  if [[ "$arg" == "-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=8192" ]]; then
    # The product's 8 KiB wall remains untouched.  This non-promotable
    # diagnostic Runtime spends some of that reserve on write-only witnesses;
    # the preparation gate binds the remaining real stack/heap distance.
    args+=("-Wl,--defsym=__lisp65_runtime_core_inline_required_post_boot_reserve_param=8160")
  else
    args+=("$arg")
  fi
done
exec "$root/tools/llvm-mos/bin/mos-mega65-clang" \
  -DLISP65_VM_FAULT_CAPTURE \
  -DLISP65_V14_SPRITE_FAULT_DIAGNOSTIC \
  "${args[@]}"
