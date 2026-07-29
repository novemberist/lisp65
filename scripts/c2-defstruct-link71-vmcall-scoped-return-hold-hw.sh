#!/bin/sh
# Prim-ID-67-scoped hold after the complete vm_callprim epilogue.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
PY=tools/host-lisp/c2_defstruct_link71_vmcall_scoped_return_hold.py
SESSION=build/post-promotion/link71-defstruct-session-record-identity-hardware-replay-v3
OUT=$SESSION/vmcall-scoped-return-hold-NONPROMOTABLE
RECEIPT=tests/fixtures/c2-migration-evidence/c2.2-link71-vmcall-scoped-return-hold-nonpromotable-receipt.json
DEPLOY=$SESSION/deployment.json
DIAGNOSTIC_PRG=$OUT/lisp65-Link71-vmcall-scoped-return-NONPROMOTABLE.prg
PRELOAD=$OUT/scoped-return-preload.bin

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

write_and_verify() {
  path=$1
  address=$2
  name=$3
  bytes=$(wc -c < "$path")
  end=$((address + bytes))
  run_m65 -H -@ "$path@$address"
  run_m65 --memsave \
    "0x$(printf '%08x' "$address"):0x$(printf '%08x' "$end")=$OUT/readback-$name.bin"
  cmp "$path" "$OUT/readback-$name.bin"
}

capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

deploy_and_arm_diagnostic() {
  python3 "$PY" prepare
  prg=$DIAGNOSTIC_PRG
  run_m65 -H -1 "$prg"
  jq -c '.preloads[]' "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    run_m65 -H -@ "$path@$address"
  done
  run_m65 -H -@ "$PRELOAD@0x17a0"
  run_m65 -r -1 "$prg"
  # No JTAG or virtual-keyboard episode after RUN.  The physical operator
  # observes the REPL and submits the commissioned form.
  sleep 25
}

case "${1:-}" in
  deploy)
    deploy_and_arm_diagnostic
    echo "diagnostic ready; type the commissioned form on the physical keyboard"
    ;;
  arm)
    python3 "$PY" arm
    ;;
  capture)
    python3 "$PY" capture
    ;;
  run)
    deploy_and_arm_diagnostic
    OUT_DIR=$OUT PREFIX=arm-scoped-return TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --no-readback \
        --form '(%require-c2d-byte (cons 0 0))'
    sleep 2
    python3 "$PY" capture
    ;;
  verify)
    python3 "$PY" verify
    ;;
  *)
    echo "usage: $0 <deploy|arm|capture|run|verify>" >&2
    exit 2
    ;;
esac
