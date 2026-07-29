#!/bin/sh
# One-shot success-path-preserving Slot-40 discriminator for Link 71.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
WAIT=${WAIT:-32}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/slot40-failure-hold-v3-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_defstruct_link71_slot40_failure_hold_v3.py
PC=tools/host-lisp/c2_defstruct_link71_slot40_pc_capture_v3.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy|arm|capture>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy|arm|capture) ;;
  *) echo "usage: $0 <deploy|arm|capture>" >&2; exit 2 ;;
esac

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$((rb_start + rb_bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$(printf '%08x' "$rb_end")=$rb_path"
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

case "$ACTION" in
deploy)
  [ ! -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-40 v3 diagnostic deployment is one-shot" >&2
    exit 3
  }
  PRG=$(jq -r '.product.path' "$DEPLOY")
  run_m65 -F -H -1 "$PRG"
  touch "$OUT/hardware-run.started"
  jq -c '.preloads[]' "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    base=$(basename "$path")
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/deploy-readback-$base"
    cmp "$path" "$OUT/deploy-readback-$base"
  done
  run_m65 -r -1 "$PRG"
  sleep "$WAIT"
  capture_screen boot
  grep -q 'lisp65>' "$OUT/boot.txt" &&
    ! grep -q '\*\*\* vm:' "$OUT/boot.txt" || {
      echo "Link-71 Slot-40 v3 diagnostic did not reach a clean REPL" >&2
      exit 3
    }
  echo "Slot-40 v3 diagnostic ready."
  ;;
arm)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-40 v3 diagnostic is not deployed" >&2
    exit 3
  }
  OUT_DIR=$OUT PREFIX=slot40-v3-arm TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form "$(jq -r '.test.form' "$DEPLOY")"
  sleep 2
  capture_screen slot40-v3-screen
  grep -q '(%disk-load-lib 39 1)' "$OUT/slot40-v3-screen.txt" || {
    echo "Slot-40 v3 diagnostic form was not delivered" >&2
    exit 3
  }
  if grep -q '\*\*\* vm: bad bytecode' "$OUT/slot40-v3-screen.txt"; then
    echo "Slot-40 failed outside the instrumented publication edges."
  elif grep -Eq '(^|[[:space:]])t([[:space:]]|$)' \
      "$OUT/slot40-v3-screen.txt"; then
    echo "Slot-40 completed; no publication error reproduced."
  else
    echo "Slot-40 v3 error hold reached; capture PC next."
  fi
  ;;
capture)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-40 v3 diagnostic is not deployed" >&2
    exit 3
  }
  python3 "$PC"
  capture_screen slot40-v3-screen
  echo "Slot-40 v3 failure PC captured; diagnostic retired."
  ;;
esac
