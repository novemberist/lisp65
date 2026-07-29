#!/bin/sh
# One-device-session qualification for Link 75 carrier + require/defstruct.
set -eu
cd "$(dirname "$0")/.."

OUT=${C2_DEFSTRUCT_HW_OUT:-build/post-promotion/link75-bound-compiler-carrier/hardware-session}
ACTION=${1:-start}
PY=tools/host-lisp/c2_link75_bound_carrier_hw.py
CONFIG=config/c2.2-link75-bound-carrier-hardware-session.json
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp

case "$ACTION" in
  start)
    if [ ! -f "$OUT/deployment.json" ]; then
      python3 "$PY" prepare
    else
      [ "$(jq '.rows | length' "$OUT/observed-rows.json")" -eq 0 ] || {
        echo "Link-75 start requires zero recorded product rows" >&2
        exit 3
      }
    fi
    ;;
  continue) [ -f "$OUT/deployment.json" ] || exit 3 ;;
  *) echo "usage: $0 [start|continue]" >&2; exit 2 ;;
esac
[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  start=$1
  bytes=$2
  path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
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

run_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$CONFIG")
  expect=$(jq -r ".rows[] | select(.id == \"$id\") | .expect" "$CONFIG")
  quiet_wait=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .quiet_wait_seconds // 0" \
    "$CONFIG")
  if [ "$quiet_wait" -gt 0 ]; then
    OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --wait "$quiet_wait" --form "$form"
  else
    OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --expect-poll 30 --wait 1 --form "$form"
  fi
  python3 "$PY" record --id "$id" --screen "$OUT/row-$id.txt"
}

run_pending_phase() {
  phase=$1
  jq -r ".rows[] | select(.phase == \"$phase\") | .id" "$CONFIG" |
  while IFS= read -r id; do
    done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
    next_id=$(jq -r ".rows[$done_rows].id // empty" "$CONFIG")
    [ "$id" != "$next_id" ] || run_row "$id"
  done
}

if [ "$ACTION" = start ]; then
  media=$(jq -r '.media.path' "$OUT/deployment.json")
  remote=$(jq -r '.remote_media' "$OUT/deployment.json")
  timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $OUT/uploaded-media-readback.d81" \
    -c exit > "$OUT/media-upload.log"
  cmp "$media" "$OUT/uploaded-media-readback.d81"

  readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
  prg=$(jq -r '.product.path' "$OUT/deployment.json")
  run_m65 -F -H -1 "$prg"
  jq -c '.preloads[]' "$OUT/deployment.json" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    base=$(basename "$path")
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/readback-$base"
    cmp "$path" "$OUT/readback-$base"
  done
  run_m65 -r -1 "$prg"

  poll=0
  while [ "$poll" -lt 45 ]; do
    capture_screen boot
    grep -q 'lisp65>' "$OUT/boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 45 ] || {
    echo "Link-75 First Red: no Lisp REPL within boot poll limit" >&2
    exit 3
  }
  run_pending_phase pre-mount
  echo "Link-75 pre-mount rows passed; mount L75CARR.D81 in Freezer, return with F3, then run: $0 continue"
  exit 0
fi

done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
next_id=$(jq -r ".rows[$done_rows].id // empty" "$CONFIG")
[ "$next_id" != require-first ] || run_row require-first

done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
next_id=$(jq -r ".rows[$done_rows].id // empty" "$CONFIG")
if [ "$next_id" = require-repeat ]; then
  readback 0x00050000 65536 "$OUT/first-repeat-before-bank5.bin"
  run_row require-repeat
  readback 0x00050000 65536 "$OUT/first-repeat-after-bank5.bin"
fi
python3 "$PY" compare-repeat --name first-repeat

for id in define-point construct-point read-point-x read-point-y \
          point-predicate copy-point functional-update canonical-place-mutation
do
  done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
  next_id=$(jq -r ".rows[$done_rows].id // empty" "$CONFIG")
  [ "$id" != "$next_id" ] || run_row "$id"
done

done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
next_id=$(jq -r ".rows[$done_rows].id // empty" "$CONFIG")
if [ "$next_id" = require-repeat-after-use ]; then
  readback 0x00050000 65536 "$OUT/post-use-repeat-before-bank5.bin"
  run_row require-repeat-after-use
  readback 0x00050000 65536 "$OUT/post-use-repeat-after-bank5.bin"
fi
python3 "$PY" compare-repeat --name post-use-repeat
python3 "$PY" finalize
