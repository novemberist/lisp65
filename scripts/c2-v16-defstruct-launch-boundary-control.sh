#!/bin/sh
# Physical control row for the v1.6 D2 launch-boundary appointment.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_launch_boundary_control.py
DEPLOY=build/c2.3/v1.6-defstruct-phase-c/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-launch-boundary-appointment/control}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|stage|finish) ;;
  *) echo "usage: $0 <dry-run|stage|finish>" >&2; exit 2 ;;
esac

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
screen() {
  name=$1
  run_m65 --screenshot="$OUT/$name.png" > "$OUT/$name.ansi.txt"
  python3 - "$OUT/$name.ansi.txt" "$OUT/$name.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
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
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$OUT/readback.d81"
}

python3 "$PY" check
python3 "$PY" selftest
[ "$ACTION" != dry-run ] || { echo "D2 LAUNCH CONTROL DRY RUN PASS"; exit 0; }
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || exit 3
mkdir -p "$OUT"

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/control-stage.consumed" ] || {
    echo "control stage already consumed" >&2; exit 3;
  }
  : > "$OUT/control-stage.consumed"
  run_m65 -F
  sleep 5
  screen control-fresh-basic
  python3 - "$OUT/control-fresh-basic.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "basic 65" in text or "ready." in text
assert "break" not in text and "monitor commands" not in text
print("CONTROL FRESH BASIC ASSERT PASS")
PY
  medium=$(jq -r '.library_medium.path' "$DEPLOY")
  remote=$(jq -r '.library_remote' "$DEPLOY")
  ftp_medium "$medium" "$remote"
  product=$(jq -r '.control.prg.path' "$DEPLOY")
  run_m65 -H "$product"
  jq -c '.control.preloads[]' "$DEPLOY" | while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$address" "$bytes" "$OUT/preload-$role.bin"
    cmp "$path" "$OUT/preload-$role.bin"
  done
  run_m65 -r
  sleep 3
  screen control-launch-ready
  python3 - "$OUT/control-launch-ready.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "ready." in text
assert "break" not in text and "monitor commands" not in text
assert "lisp65>" not in text
print("CONTROL PHYSICAL-LAUNCH CONTEXT PASS")
PY
  : > "$OUT/control-stage.ready"
  echo "CONTROL STAGE READY: type RUN and press RETURN on the physical keyboard."
  exit 0
fi

[ -e "$OUT/control-stage.ready" ] || {
  echo "control stage is not ready" >&2; exit 3;
}
[ ! -e "$OUT/control-finish.consumed" ] || {
  echo "control finish already consumed" >&2; exit 3;
}
: > "$OUT/control-finish.consumed"
screen control-after-physical-run
python3 "$PY" finish --screen "$OUT/control-after-physical-run.txt"
echo "D2 LAUNCH-BOUNDARY CONTROL ROW COMPLETE"
