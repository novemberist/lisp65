#!/bin/sh
# Final physical-keyboard acceptance for the Link-88 interactive Ship sample.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-ship-builder-v1-link88-interactive-human-test.json
OUT=build/ship-builder/v13/link88-interactive-human-test/run
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
expected_sha=$(jq -r '.image_sha256' "$CONFIG")
remote=$(jq -r '.remote' "$CONFIG")
state=$(($(jq -r '.runtime_state' "$CONFIG")))

image_sha=$(sha256sum "$image" | awk '{print $1}')
[ "$image_sha" = "$expected_sha" ] || {
  echo "Link-88 interactive image SHA drift" >&2; exit 3;
}

if [ "$ACTION" = dry-run ]; then
  [ -f "$image" ]
  echo "DRY-RUN: cold reset -> fresh BASIC -> exact committed Link-88 D81"
  echo "ASSERT: Runtime state 2 follows 312/312-proved 9-bit raster progress"
  echo "HANDS OFF: no monitor traffic after state 2"
  echo "HUMAN: type Ada and RETURN on the physical keyboard"
  echo "CAPTURE: require state 3, non-NIL result and Hello, Ada!"
  exit 0
fi

mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 4;
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
    case "$actual" in
      225|226|227|228|229)
        echo "Ship Runtime terminal state $actual before input" >&2
        return 1
        ;;
    esac
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "runtime state did not reach $expected within ${limit}s" >&2
  return 1
}

if [ "$ACTION" = capture ]; then
  readback "$state" 4 "$OUT/result.bin"
  capture_screen complete
  raw=$(od -An -tx1 "$OUT/result.bin" | tr -d ' \n')
  echo "state/result=$raw"
  case "$raw" in 03????00) ;; *)
    echo "HUMAN TEST: FIRST RED state/result=$raw" >&2; exit 5;
  esac
  [ "$raw" != "03000000" ] || {
    echo "HUMAN TEST: FIRST RED NIL result" >&2; exit 5;
  }
  if grep -Fq "$(jq -r '.expected_screen_text' "$CONFIG")" "$OUT/complete.txt"; then
    echo "HUMAN TEST: PASS greeting='$(jq -r '.expected_screen_text' "$CONFIG")'"
  else
    echo "HUMAN TEST: FIRST RED greeting absent" >&2
    exit 6
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
readback "$state" 1 "$OUT/state-before-human.bin"
[ "$(od -An -tu1 "$OUT/state-before-human.bin" | tr -d ' ')" = 2 ]
echo "READY FOR HUMAN INPUT: type Ada and RETURN on the physical keyboard."
echo "No virtual keys were sent. Do not use monitor/JTAG until capture."
