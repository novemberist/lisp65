#!/bin/sh
# Autonomous Link-90 parity-toy target close; no virtual keyboard input.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v14_link90_parity_toy_close.py
BASE=build/post-promotion/v14/link90-parity-toy-close
DEPLOY=$BASE/deployment.json
OUT=$BASE/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start|capture) ;;
  *) echo "usage: $0 <prepare|dry-run|start|capture>" >&2; exit 2 ;;
esac

if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi
if [ "$ACTION" = dry-run ]; then exec python3 "$PY" dry-run; fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" dry-run >/dev/null
mkdir -p "$OUT"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

capture_screen() (
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
)

readback() (
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

fresh_start() (
  run_m65 -F
  sleep 5
  capture_screen fresh-basic
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/fresh-basic.txt"
)

ftp_package() (
  media=$1 remote=$2
  log=$OUT/upload.log
  readback_path=$OUT/readback.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true' HUP INT TERM EXIT
  last=-1
  progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
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
  cmp "$media" "$readback_path"
)

state_address=$(($(jq -r '.runtime.state' "$DEPLOY")))

if [ "$ACTION" = start ]; then
  [ ! -e "$OUT/state-before-key.bin" ] || {
    echo "Link-90 start already consumed" >&2; exit 3;
  }
  fresh_start
  image=$(jq -r '.image.path' "$DEPLOY")
  remote=$(jq -r '.remote' "$DEPLOY")
  ftp_package "$image" "$remote"
  elapsed=0
  while [ "$elapsed" -lt 120 ]; do
    readback "$state_address" 1 "$OUT/state.bin"
    state=$(od -An -tu1 "$OUT/state.bin" | tr -d ' ')
    [ "$state" = 2 ] && break
    case "$state" in
      3|225|226|227|228|229)
        echo "parity-toy terminal state $state before physical input" >&2
        exit 1 ;;
    esac
    sleep 2; elapsed=$((elapsed + 2))
  done
  [ "${state:-}" = 2 ] || {
    echo "parity-toy did not reach physical-input state" >&2; exit 1;
  }
  cp "$OUT/state.bin" "$OUT/state-before-key.bin"
  capture_screen waiting-physical-key
  echo "LINK 90 READY: press exactly one PHYSICAL key and listen for the SID note."
  exit 0
fi

[ -f "$OUT/state-before-key.bin" ] || {
  echo "physical-input state was not established" >&2; exit 3;
}
sleep 1
readback "$state_address" 16 "$OUT/runtime-final.bin"
state=$(od -An -tu1 -N1 "$OUT/runtime-final.bin" | tr -d ' ')
capture_screen complete
[ "$state" = 3 ] || {
  echo "parity-toy state after physical key is $state, expected 3" >&2
  exit 1
}
echo "LINK 90 TARGET COMPLETE: autonomous sprite path and physical key completed; SID remains an owner hearing observation."
