#!/bin/sh
# One-shot nonpromotable Slot-40 loaded-entry discriminator for Link 71.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
WAIT=${WAIT:-32}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/slot40-entry-hold-v2-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_defstruct_link71_slot40_entry_hold.py
M65=$TOOLS/m65
PHASE_START=0x0000c0c6
PHASE_BYTES=304

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy|arm|capture>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy|arm|capture) ;;
  *) echo "usage: $0 <deploy|arm|capture>" >&2; exit 2 ;;
esac

python3 "$PY"
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
    echo "Link-71 Slot-40 entry diagnostic deployment is one-shot" >&2
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
      echo "Link-71 Slot-40 entry diagnostic did not reach a clean REPL" >&2
      exit 3
    }
  echo "Slot-40 entry diagnostic ready."
  ;;
arm)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-40 entry diagnostic is not deployed" >&2
    exit 3
  }
  OUT_DIR=$OUT PREFIX=slot40-entry-arm TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form "$(jq -r '.test.form' "$DEPLOY")"
  sleep 2
  capture_screen slot40-entry-screen
  grep -q '(%disk-load-lib 39 1)' "$OUT/slot40-entry-screen.txt" || {
    echo "Slot-40 entry diagnostic form was not delivered" >&2
    exit 3
  }
  if grep -q '\*\*\* vm: bad bytecode' "$OUT/slot40-entry-screen.txt"; then
    echo "Slot-40 record was rejected before its first instruction."
  elif grep -Eq '(^|[[:space:]])t([[:space:]]|$)' \
      "$OUT/slot40-entry-screen.txt"; then
    echo "Slot-40 unexpectedly completed; entry hold was not reached."
    exit 3
  else
    echo "Slot-40 loaded-entry hold reached; capture next."
  fi
  ;;
capture)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-40 entry diagnostic is not deployed" >&2
    exit 3
  }
  i=1
  while [ "$i" -le 3 ]; do
    readback "$PHASE_START" "$PHASE_BYTES" \
      "$OUT/entry-phase-scratch-$i.bin"
    [ "$i" -eq 3 ] || sleep 1
    i=$((i + 1))
  done
  cmp "$OUT/entry-phase-scratch-1.bin" \
      "$OUT/entry-phase-scratch-2.bin"
  cmp "$OUT/entry-phase-scratch-1.bin" \
      "$OUT/entry-phase-scratch-3.bin"
  capture_screen slot40-entry-screen
  python3 - "$OUT/entry-phase-scratch-1.bin" <<'PY'
from pathlib import Path
import json
import sys
data = Path(sys.argv[1]).read_bytes()
assert len(data) == 304
print(json.dumps({
    "staged": data[0xee],
    "committed": data[0xef],
    "plan_marker_record_22": data[0xcc],
    "completion_marker_record_24": data[0xce],
    "fused_marker_record_23": data[0xcd],
    "trace_primary": data[0x12e],
    "trace_lock": data[0x12f],
}, sort_keys=True))
PY
  echo "Slot-40 loaded-entry state captured; diagnostic retired."
  ;;
esac
