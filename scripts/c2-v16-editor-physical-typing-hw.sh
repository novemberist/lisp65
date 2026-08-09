#!/bin/sh
# Physical 64-key rider for the v1.6 bundled closing appointment.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PHASE_C_PY=tools/host-lisp/c2_v16_defstruct_phase_c.py
CLOSURE=tools/host-lisp/c2_v16_d2_choreography_closure.py
DEPLOY=build/c2.3/v1.6-defstruct-phase-c/deployment.json
OUT=build/c2.3/v1.6-defstruct-closing-session/d1
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
PHYSICAL_TEXT='1234567 1234567 1234567 1234567 1234567 1234567 1234567 12345678'

case "$ACTION" in
  dry-run|start|capture) ;;
  *) echo "usage: $0 <dry-run|start|capture>" >&2; exit 2 ;;
esac

text_bytes=$(printf %s "$PHYSICAL_TEXT" | wc -c)
[ "$text_bytes" -eq 64 ] || { echo "physical fixture is not 64 bytes" >&2; exit 3; }

if [ "$ACTION" = dry-run ]; then
  python3 "$CLOSURE" check >/dev/null
  echo "D1 PHYSICAL DRY RUN PASS keys=64 per-key-observations=0"
  echo "TYPE EXACTLY (without RETURN): $PHYSICAL_TEXT"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
screen() {
  name=$1
  run_m65 --screenshot="$OUT/$name.png" > "$OUT/$name.ansi.txt"
  python3 - "$OUT/$name.ansi.txt" "$OUT/$name.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
ftp_medium() {
  media=$1 remote=$2 log=$OUT/upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $OUT/readback.d81" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$! last=-1 progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
    if [ "$size" -ne "$last" ]; then last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2; return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$OUT/readback.d81"
}
capture_buffer() {
  prefix=$1
  readback 0x59 2 "$OUT/$prefix-nsym.bin"
  readback 0x0005c680 10208 "$OUT/$prefix-namepool.bin"
  readback 0x0005ee60 1504 "$OUT/$prefix-symval.bin"
  readback 0x0005f440 1504 "$OUT/$prefix-nameoff.bin"
  readback 0x0000c25d 240 "$OUT/$prefix-heap.bin"
  readback 0x00040000 8192 "$OUT/$prefix-ext.bin"
  readback 0x22 2 "$OUT/$prefix-str-cur-off.bin"
  readback 0x00042000 9344 "$OUT/$prefix-arena-2000.bin"
  readback 0x00044480 9344 "$OUT/$prefix-arena-4480.bin"
}

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/physical-window-active" ] || {
    echo "physical window was not armed" >&2; exit 3;
  }
  capture_buffer d1-final-memory
  screen final
  if python3 "$PHASE_C_PY" check-d1-buffer --directory "$OUT" \
      --prefix d1-final-memory --expected-fill 64; then
    : > "$OUT/physical-row-passed"
    echo "D1 PHYSICAL PASS submitted=64 persisted=64"
  else
    python3 "$PHASE_C_PY" capture-d1-hang --directory "$OUT" --device "$DEVICE"
    echo "D1 PHYSICAL FIRST RED: final buffer is not 64; CPU left stopped" >&2
    exit 4
  fi
  exit 0
fi

[ ! -e "$OUT/contact.consumed" ] || {
  echo "D1 physical contact already consumed" >&2; exit 3;
}
mkdir -p "$OUT"
: > "$OUT/contact.consumed"
run_m65 -F
sleep 5
screen fresh-basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
! grep -q 'lisp65>' "$OUT/fresh-basic.txt"
media=$(jq -r '.ordinary_product_D1.path' "$DEPLOY")
ftp_medium "$media" LISP65-V16-D1-PHYSICAL.D81
sleep 45
screen boot
grep -q 'lisp65>' "$OUT/boot.txt"
OUT_DIR="$OUT" PREFIX=editor TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --no-readback --form '(ide"measure3")'
sleep 12
screen editor-context
grep -Eq -- '-- measure3( \*)? L[0-9]+ --' "$OUT/editor-context.txt"
capture_buffer d1-context
python3 "$PHASE_C_PY" check-d1-buffer --directory "$OUT"
run_m65 -r
: > "$OUT/physical-window-active"
echo "D1 PHYSICAL WINDOW ACTIVE: no monitor traffic until capture."
echo "TYPE EXACTLY, WITHOUT RETURN:"
echo "$PHYSICAL_TEXT"
