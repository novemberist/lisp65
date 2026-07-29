#!/bin/sh
# Load PLACE, arm the common rollback hold, then capture without resuming.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
PY=tools/host-lisp/c2_defstruct_link71_sess_pre_rollback_capture.py
SESSION=build/post-promotion/link71-defstruct-session-record-identity-hardware-replay-v3
OUT=$SESSION/defstruct-only-pre-rollback-safe-NONPROMOTABLE
PATCH=$OUT/pre-rollback-hold.bin

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

case "${1:-}" in
  run)
    python3 "$PY" prepare
    OUT_DIR=$OUT PREFIX=load-place TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect t \
        --expect-poll 30 --wait 1 --form '(%disk-load-lib 39 1)'
    run_m65 --memsave "0x0000e9bc:0x0000e9bf=$OUT/before-patch.bin"
    [ "$(xxd -p "$OUT/before-patch.bin")" = "20e3e9" ]
    run_m65 -H -@ "$PATCH@0x0000e9bc"
    run_m65 --memsave \
      "0x0000e9bc:0x0000e9bf=$OUT/late-patch-readback.bin"
    cmp "$PATCH" "$OUT/late-patch-readback.bin"
    OUT_DIR=$OUT PREFIX=arm-defstruct TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback \
        --form '(require (quote defstruct))'
    sleep 3
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
