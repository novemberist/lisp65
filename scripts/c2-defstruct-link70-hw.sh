#!/bin/sh
# One-device-session hardware qualification for Link 70 require + defstruct.
set -eu
cd "$(dirname "$0")/.."

OUT=${C2_DEFSTRUCT_HW_OUT:-build/post-promotion/link70-defstruct-header-crc/hardware-session}
ACTION=${1:-start}
PY=${C2_DEFSTRUCT_HW_PY:-tools/host-lisp/c2_defstruct_link70_hw.py}
CONFIG=${C2_DEFSTRUCT_HW_CONFIG:-config/c2.2-defstruct-link70-hardware-session.json}
LABEL=${C2_DEFSTRUCT_HW_LABEL:-Link-70}
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
        echo "$LABEL session is not resumable before product rows" >&2
        exit 3
      }
    ;;
  deploy)
    [ -f "$OUT/deployment.json" ] &&
      [ -f "$OUT/uploaded-media-readback.d81" ] &&
      [ "$(jq '.rows | length' "$OUT/observed-rows.json")" -eq 0 ] || {
        echo "$LABEL deploy requires uploaded media and zero product rows" >&2
        exit 3
      }
    ;;
  continue)
    [ -f "$OUT/deployment.json" ] || exit 3
    ;;
  *)
    echo "usage: $0 [start|resume|deploy|continue]" >&2
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

if [ "$ACTION" != continue ]; then
  media=$(jq -r '.media.path' "$OUT/deployment.json")
  remote=$(jq -r '.remote_media' "$OUT/deployment.json")
  if [ "$ACTION" != deploy ]; then
    if [ "${C2_AUTO_MOUNT_MEDIA:-0}" -eq 1 ]; then
      timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
        -c "put $media $remote" \
        -c "get $remote $OUT/uploaded-media-readback.d81" \
        -c "mount $remote" \
        -c exit > "$OUT/media-upload.log"
    else
      timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
        -c "put $media $remote" \
        -c "get $remote $OUT/uploaded-media-readback.d81" \
        -c exit > "$OUT/media-upload.log"
    fi
  fi
  cmp "$media" "$OUT/uploaded-media-readback.d81"

  readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
  prg=$(jq -r '.product.path' "$OUT/deployment.json")
  if [ "${C2_PRESERVE_MOUNT_AFTER_FTP_RESET:-0}" -eq 1 ]; then
    run_m65 -H -1 "$prg"
  else
    run_m65 -F -H -1 "$prg"
  fi
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
    echo "$LABEL First Red: no Lisp REPL within boot poll limit" >&2
    exit 3
  }

  if [ "${C2_AUTO_MOUNT_MEDIA:-0}" -eq 1 ]; then
    echo "$LABEL product ready; $remote is already mounted"
  else
    echo "$LABEL product ready; mount $remote in Freezer and return with F3"
  fi
  exit 0
fi

done_rows=$(jq '.rows | length' "$OUT/observed-rows.json")
[ "$done_rows" -ge 1 ] || run_row boot-watch
[ "$done_rows" -ge 2 ] || run_row require-first
if [ "$done_rows" -lt 3 ]; then
  readback 0x00050000 65536 "$OUT/first-repeat-before-bank5.bin"
  run_row require-repeat
  readback 0x00050000 65536 "$OUT/first-repeat-after-bank5.bin"
fi
python3 "$PY" compare-repeat --name first-repeat
[ "$done_rows" -ge 4 ] || run_row define-point
[ "$done_rows" -ge 5 ] || run_row construct-point
[ "$done_rows" -ge 6 ] || run_row read-point-x
[ "$done_rows" -ge 7 ] || run_row read-point-y
[ "$done_rows" -ge 8 ] || run_row point-predicate
[ "$done_rows" -ge 9 ] || run_row copy-point
[ "$done_rows" -ge 10 ] || run_row functional-update
[ "$done_rows" -ge 11 ] || run_row canonical-place-mutation
if [ "$done_rows" -lt 12 ]; then
  readback 0x00050000 65536 "$OUT/post-use-repeat-before-bank5.bin"
  run_row require-repeat-after-use
  readback 0x00050000 65536 "$OUT/post-use-repeat-after-bank5.bin"
  python3 "$PY" compare-repeat --name post-use-repeat
fi
if [ "$done_rows" -ge 12 ] &&
   [ -f "$OUT/post-use-repeat-before-bank5.bin" ] &&
   [ -f "$OUT/post-use-repeat-after-bank5.bin" ]; then
  python3 "$PY" compare-repeat --name post-use-repeat
fi

python3 "$PY" finalize
