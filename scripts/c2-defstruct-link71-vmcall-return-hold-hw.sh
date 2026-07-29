#!/bin/sh
# Reboot pristine Link 71, then hold immediately after vm_callprim returns.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
PY=tools/host-lisp/c2_defstruct_link71_vmcall_return_hold.py
SESSION=build/post-promotion/link71-defstruct-session-record-identity-hardware-replay-v3
OUT=$SESSION/vmcall-return-hold-NONPROMOTABLE
PATCH=$OUT/vmcall-return-hold.bin
RECEIPT=tests/fixtures/c2-migration-evidence/c2.2-link71-vmcall-return-hold-nonpromotable-receipt.json

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

case "${1:-}" in
  run)
    if [ -e "$RECEIPT" ]; then
      python3 "$PY" verify
    else
      python3 "$PY" prepare
    fi
    scripts/c2-defstruct-link71-session-record-identity-v3-hw.sh deploy
    run_m65 --memsave "0x000052ba:0x000052bd=$OUT/before-patch.bin"
    [ "$(xxd -p "$OUT/before-patch.bin")" = "a00d91" ]
    run_m65 -H -@ "$PATCH@0x000052ba"
    run_m65 --memsave \
      "0x000052ba:0x000052bd=$OUT/late-patch-readback.bin"
    cmp "$PATCH" "$OUT/late-patch-readback.bin"
    OUT_DIR=$OUT PREFIX=arm-vmcall-return TIMEOUT_SEC=$TIMEOUT \
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
