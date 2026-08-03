#!/bin/sh
# One owner-authorized corrected contact for the Link-85 interactive Ship row.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v13_link85_interactive_retry.py
CONFIG=config/c2-ship-builder-v1-link85-interactive-retry.json
OUT=build/ship-builder/v13/link85-interactive-retry/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  prepare|dry-run|start|evaluate) ;;
  *) echo "usage: $0 <prepare|dry-run|start|evaluate>" >&2; exit 2 ;;
esac
if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi
if [ "$ACTION" = evaluate ]; then exec python3 "$PY" evaluate; fi
if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  echo "DRY-RUN: cold reset -> exact D81 -> state 2 -> A/Ad/Ada screen acks -> RETURN/state 3"
  exit 0
fi

python3 "$PY" prepare
mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
capture() {
  id=$1
  run_m65 --screenshot="$OUT/$id.png" > "$OUT/$id.ansi.txt"
  python3 - "$OUT/$id.ansi.txt" "$OUT/$id.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
  python3 - "$OUT/$id.png" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
PY
}
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
wait_state() {
  expected=$1 limit=$2 elapsed=0 address=$(($(jq -r '.runtime_state' "$CONFIG")))
  while [ "$elapsed" -lt "$limit" ]; do
    readback "$address" 1 "$OUT/state.bin"
    actual=$(od -An -tu1 "$OUT/state.bin" | tr -d ' ')
    [ "$actual" = "$expected" ] && return 0
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "runtime state did not reach $expected within ${limit}s" >&2
  return 1
}

run_m65 -F
sleep 5
capture fresh-basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
image=$(jq -r '.image' "$CONFIG")
remote=$(jq -r '.remote' "$CONFIG")
log=$OUT/upload.log
: > "$log"
timeout --kill-after=2s 120s "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $image $remote" -c "get $remote $OUT/package-readback.d81" \
  -c "mount $remote" -c exit > "$log" 2>&1
cmp "$image" "$OUT/package-readback.d81"
wait_state 2 90

index=1
for key in A d a; do
  run_m65 -t "$key"
  sleep 2
  capture "ack-$index"
  expected=$(jq -r ".sequence[$((index - 1))].screen_ack" "$CONFIG")
  grep -Fq "$expected" "$OUT/ack-$index.txt"
  index=$((index + 1))
done
run_m65 -t '~M'
wait_state 3 90
state=$(($(jq -r '.runtime_state' "$CONFIG")))
readback "$state" 4 "$OUT/result.bin"
capture complete
grep -Fq "$(jq -r '.expected_screen_text' "$CONFIG")" "$OUT/complete.txt"
python3 "$PY" evaluate
