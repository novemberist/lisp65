#!/bin/sh
# One-contact non-promotable Link-90 decoded-value mechanism witness.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v14_link90_mechanism_witness.py
BASE=build/post-promotion/v14/link90-mechanism-witness
DEPLOY=$BASE/deployment.json
OUT=$BASE/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|run|analyze) ;;
  *) echo "usage: $0 <prepare|dry-run|run|analyze>" >&2; exit 2 ;;
esac

if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi
if [ "$ACTION" = dry-run ]; then exec python3 "$PY" dry-run; fi
if [ "$ACTION" = analyze ]; then exec python3 "$PY" analyze; fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" dry-run >/dev/null
[ ! -e "$OUT/contact.consumed" ] || {
  echo "mechanism-witness hardware contact already consumed" >&2; exit 3;
}
mkdir -p "$OUT"
: > "$OUT/contact.consumed"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() (
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

capture_basic() {
  run_m65 --screenshot="$OUT/fresh-basic.png" > "$OUT/fresh-basic.ansi.txt"
  python3 - "$OUT/fresh-basic.ansi.txt" "$OUT/fresh-basic.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/fresh-basic.txt"
}

ftp_package() (
  media=$1 remote=$2 log=$OUT/upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $OUT/readback.d81" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true' HUP INT TERM EXIT
  last=-1 progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log") now=$(date +%s)
    if [ "$size" -ne "$last" ]; then
      last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      trap - HUP INT TERM EXIT
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  if wait "$pid"; then status=0; else status=$?; fi
  trap - HUP INT TERM EXIT
  [ "$status" -eq 0 ]
  cmp "$media" "$OUT/readback.d81"
)

run_m65 -F
sleep 5
capture_basic
image=$(jq -r '.image.path' "$DEPLOY")
remote=$(jq -r '.remote' "$DEPLOY")
ftp_package "$image" "$remote"

sleep 10
state_address=$(($(jq -r '.runtime_state.address' "$DEPLOY")))
readback "$state_address" 1 "$OUT/lisp65_runtime_state.bin"
state=$(od -An -tu1 "$OUT/lisp65_runtime_state.bin" | tr -d ' ')
[ "$state" = 227 ] || {
  echo "mechanism identity did not reach VM error state: $state" >&2; exit 1;
}

witness_address=$(($(jq -r '.witness.address' "$DEPLOY")))
witness_bytes=$(jq -r '.witness.bytes' "$DEPLOY")
readback "$witness_address" "$witness_bytes" "$OUT/mechanism_witness.bin"

python3 "$PY" analyze
