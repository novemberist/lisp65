#!/bin/sh
# One-device-session hardware qualification for Link 69 require + defstruct.
set -eu
cd "$(dirname "$0")/.."

OUT=${C2_DEFSTRUCT_HW_OUT:-build/post-promotion/link69-defstruct-foundations/hardware-session}
ACTION=${1:-start}
DEPLOY=1
PY=tools/host-lisp/c2_defstruct_link69_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp

case "$ACTION" in
  start)
    python3 "$PY" prepare
    ;;
  resume)
    [ -f "$OUT/deployment.json" ] &&
      [ "$(jq '.rows | length' "$OUT/observed-rows.json")" -eq 0 ] || {
        echo "Link-69 hardware session is not resumable before product rows" >&2
        exit 3
      }
    ;;
  continue)
    [ -f "$OUT/deployment.json" ] &&
      [ "$(jq '.rows | length' "$OUT/observed-rows.json")" -eq 1 ] || {
        echo "Link-69 continue requires exactly the passed boot-watch row" >&2
        exit 3
      }
    DEPLOY=0
    ;;
  *)
    echo "usage: $0 [start|resume|continue]" >&2
    exit 2
    ;;
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
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" \
    config/c2.2-defstruct-link69-hardware-session.json)
  expect=$(jq -r ".rows[] | select(.id == \"$id\") | .expect" \
    config/c2.2-defstruct-link69-hardware-session.json)
  OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
      --expect-poll 25 --wait 1 --form "$form"
  python3 "$PY" record --id "$id" --screen "$OUT/row-$id.txt"
}

if [ "$DEPLOY" -eq 1 ]; then
  media=$(jq -r '.media.path' "$OUT/deployment.json")
  remote=$(jq -r '.remote_media' "$OUT/deployment.json")
  timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $OUT/uploaded-media-readback.d81" \
    -c "mount $remote" -c exit > "$OUT/media-upload-mount.log"
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
  while [ "$poll" -lt 40 ]; do
    capture_screen boot
    grep -q 'lisp65>' "$OUT/boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 40 ] || {
    echo "Link-69 First Red: no Lisp REPL within boot poll limit" >&2
    exit 3
  }
  run_row boot-watch
else
  capture_screen continue-repl
  grep -q 'lisp65>' "$OUT/continue-repl.txt" || {
    echo "Link-69 continue requires the live Lisp REPL" >&2
    exit 3
  }
fi
run_row require-first
readback 0x00050000 65536 "$OUT/first-repeat-before-bank5.bin"
run_row require-repeat
readback 0x00050000 65536 "$OUT/first-repeat-after-bank5.bin"
cmp "$OUT/first-repeat-before-bank5.bin" \
  "$OUT/first-repeat-after-bank5.bin"

run_row define-point
run_row construct-point
run_row read-point-x
run_row read-point-y
run_row point-predicate
run_row copy-point
run_row functional-update
run_row canonical-place-mutation
readback 0x00050000 65536 "$OUT/post-use-repeat-before-bank5.bin"
run_row require-repeat-after-use
readback 0x00050000 65536 "$OUT/post-use-repeat-after-bank5.bin"
cmp "$OUT/post-use-repeat-before-bank5.bin" \
  "$OUT/post-use-repeat-after-bank5.bin"

python3 "$PY" finalize
