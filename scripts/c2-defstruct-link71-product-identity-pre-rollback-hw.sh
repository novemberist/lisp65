#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

OUT=build/post-promotion/link71-defstruct-product-identity-pre-rollback-hold-NONPROMOTABLE
PY=tools/host-lisp/c2_defstruct_link71_product_identity_pre_rollback_hold.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
PATCH=$OUT/pre-rollback-hold.bin

case "${1:-}" in
  prepare)
    python3 "$PY" prepare
    ;;
  arm-current)
    python3 "$PY" verify
    timeout --kill-after=2s 35s "$M65" -l "$DEVICE" \
      --memsave "0x0000e9bc:0x0000e9bf=$OUT/before-patch.bin"
    [ "$(xxd -p "$OUT/before-patch.bin")" = "20e3e9" ]
    timeout --kill-after=2s 35s "$M65" -l "$DEVICE" \
      -H -@ "$PATCH@0x0000e9bc"
    timeout --kill-after=2s 35s "$M65" -l "$DEVICE" \
      --memsave "0x0000e9bc:0x0000e9bf=$OUT/late-patch-readback.bin"
    cmp "$PATCH" "$OUT/late-patch-readback.bin"
    export C2_PRE_ROLLBACK_OUT=$OUT
    export C2_PRE_ROLLBACK_PY=$PY
    exec sh scripts/c2-defstruct-link71-pre-rollback-hold-v2-hw.sh arm
    ;;
  *)
    echo "usage: $0 <prepare|arm-current>" >&2
    exit 2
    ;;
esac
