#!/bin/sh
# Late-patch and capture the private C2D-byte leaf return on the live Link 71.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
PY=tools/host-lisp/c2_defstruct_link71_c2d_byte_return_hold.py
SESSION=build/post-promotion/link71-defstruct-session-record-identity-hardware-replay-v3
OUT=$SESSION/c2d-byte-return-hold-NONPROMOTABLE
PATCH=$OUT/c2d-byte-return-hold.bin

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

case "${1:-}" in
  run)
    if [ -e tests/fixtures/c2-migration-evidence/c2.2-link71-c2d-byte-return-hold-nonpromotable-receipt.json ]; then
      python3 "$PY" verify
    else
      python3 "$PY" prepare
    fi
    run_m65 --memsave "0x00007785:0x00007788=$OUT/before-patch.bin"
    [ "$(xxd -p "$OUT/before-patch.bin")" = "4c526b" ]
    run_m65 -H -@ "$PATCH@0x00007785"
    run_m65 --memsave \
      "0x00007785:0x00007788=$OUT/late-patch-readback.bin"
    cmp "$PATCH" "$OUT/late-patch-readback.bin"
    OUT_DIR=$OUT PREFIX=arm-c2d-byte-return TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback \
        --form '(%require-c2d-byte (cons 0 0))'
    sleep 2
    python3 "$PY" capture
    ;;
  verify)
    python3 "$PY" verify
    ;;
  *)
    echo "usage: $0 <run|verify>" >&2
    exit 2
    ;;
esac
