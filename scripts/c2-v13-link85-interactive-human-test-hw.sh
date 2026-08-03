#!/bin/sh
# Physical-keyboard discriminator for the Link-85 interactive Ship sample.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-ship-builder-v1-link85-interactive-human-test.json
OUT=build/ship-builder/v13/link85-interactive-human-test/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|start|capture) ;;
  *) echo "usage: $0 <dry-run|start|capture>" >&2; exit 2 ;;
esac

image=$(jq -r '.image' "$CONFIG")
remote=$(jq -r '.remote' "$CONFIG")
state=$(($(jq -r '.runtime_state' "$CONFIG")))

if [ "$ACTION" = dry-run ]; then
  [ -f "$image" ]
  echo "DRY-RUN: cold reset -> fresh BASIC -> exact D81 -> state 2 -> HANDS OFF"
  echo "HUMAN: type Ada and RETURN on the physical keyboard"
  echo "CAPTURE: read state/result and screen only after human input"
  exit 0
fi

mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
capture_screen() {
  id=$1
  run_m65 --screenshot="$OUT/$id.png" > "$OUT/$id.ansi.txt"
  python3 - "$OUT/$id.ansi.txt" "$OUT/$id.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
wait_state() {
  expected=$1 limit=$2 elapsed=0
  while [ "$elapsed" -lt "$limit" ]; do
    readback "$state" 1 "$OUT/state.bin"
    actual=$(od -An -tu1 "$OUT/state.bin" | tr -d ' ')
    [ "$actual" = "$expected" ] && return 0
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "runtime state did not reach $expected within ${limit}s" >&2
  return 1
}

if [ "$ACTION" = capture ]; then
  readback "$state" 4 "$OUT/result.bin"
  capture_screen complete
  echo "state/result=$(od -An -tx1 "$OUT/result.bin" | tr -d ' \n')"
  if grep -Fq "$(jq -r '.expected_screen_text' "$CONFIG")" "$OUT/complete.txt"; then
    echo "HUMAN TEST: PASS greeting='$(jq -r '.expected_screen_text' "$CONFIG")'"
  else
    echo "HUMAN TEST: FIRST RED greeting absent" >&2
    exit 4
  fi
  exit 0
fi

run_m65 -F
sleep 5
capture_screen fresh-basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
: > "$OUT/upload.log"
timeout --kill-after=2s 120s "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $image $remote" -c "get $remote $OUT/package-readback.d81" \
  -c "mount $remote" -c exit > "$OUT/upload.log" 2>&1
cmp "$image" "$OUT/package-readback.d81"
wait_state 2 90
capture_screen waiting-for-human
readback "$state" 1 "$OUT/state-before-human.bin"
[ "$(od -An -tu1 "$OUT/state-before-human.bin" | tr -d ' ')" = 2 ]
echo "READY FOR HUMAN INPUT: type Ada and RETURN on the physical keyboard."
echo "No virtual keys were sent."
