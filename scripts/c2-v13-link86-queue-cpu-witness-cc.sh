#!/bin/sh
# Diagnostic-only compiler wrapper: build the Link-86 CPU-side queue witness.
set -eu
root=$(git rev-parse --show-toplevel)
exec "$root/tools/llvm-mos/bin/mos-mega65-clang" \
  -DLISP65_SHIP_QUEUE_DIAGNOSTIC "$@"
