#!/bin/sh
# Link-92 Phase-D D2 conditional defstruct acceptance row.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v112-link92-phase-d-d2.json
PY=tools/host-lisp/c2_v112_phase_d_d2.py
OUT=${OUT:-build/c2.3/v1.4.0-release/phase-d-split/d2}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|start-d2|confirm-require|wait-d2|capture-green) ;;
  *) echo "usage: $0 <dry-run|start-d2|confirm-require|wait-d2|capture-green>" >&2; exit 2 ;;
esac

OUT=$OUT python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  OUT=$OUT python3 "$PY" dry-run
  echo "DRY-RUN: sibling staging -> physical require -> physical defstruct -> 180s quiet -> physical make-point"
  exit 0
fi

mkdir -p "$OUT"

if [ "$ACTION" = confirm-require ]; then
  [ -e "$OUT/ready-for-require" ] && [ ! -e "$OUT/require-owner-confirmed" ] || {
    echo "D2 require confirmation is not armed" >&2; exit 3;
  }
  date +%s > "$OUT/require-owner-confirmed"
  echo "D2 REQUIRE OWNER-CONFIRMED: type (defstruct point x y), then report sent."
  exit 0
fi

if [ "$ACTION" = wait-d2 ]; then
  [ -e "$OUT/require-owner-confirmed" ] && [ ! -e "$OUT/quiet-start-epoch" ] || {
    echo "D2 quiet window is not armed" >&2; exit 3;
  }
  quiet=$(jq -r '.row.quiet_floor_seconds' "$CONFIG")
  # WAIT-D2-BEGIN: no device access of any kind is permitted in this block.
  date +%s > "$OUT/quiet-start-epoch"
  : > "$OUT/definition-owner-confirmed"
  sleep "$quiet"
  date +%s > "$OUT/quiet-complete-epoch"
  # WAIT-D2-END
  echo "D2 QUIET FLOOR COMPLETE: look at the physical screen once."
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }

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

fail_if_red() (
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError as error:
    print(error.message)
    raise SystemExit(error.code)
PY
)

readback() (
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

fresh_start() (
  run_m65 -F
  sleep 5
  capture_screen D2-fresh-basic
  fail_if_red "$OUT/D2-fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/D2-fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/D2-fresh-basic.txt"
)

ftp_library() (
  media=$(jq -r '.identity.library_medium.path' "$CONFIG")
  remote=$(jq -r '.identity.remote' "$CONFIG")
  log=$OUT/D2-library-upload.log
  readback_path=$OUT/D2-library-readback.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!; last=-1; progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
    if [ "$size" -ne "$last" ]; then last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2; return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$readback_path"
)

load_identity() (
  product=$(jq -r '.identity.product.path' "$CONFIG")
  run_m65 -H -1 "$product"
  jq -c '.identity.preloads[]' "$CONFIG" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/D2-preload-$role.bin"
    cmp "$path" "$OUT/D2-preload-$role.bin"
  done
  c2j_address=$(($(jq -r '.identity.c2j_clear.address' "$CONFIG")))
  c2j_bytes=$(jq -r '.identity.c2j_clear.bytes' "$CONFIG")
  c2j_authority=$(jq -r '.identity.c2j_clear.authority' "$CONFIG")
  readback "$c2j_address" "$c2j_bytes" "$OUT/D2-c2j-before-run.bin"
  cmp "$c2j_authority" "$OUT/D2-c2j-before-run.bin"
  run_m65 -r -1 "$product"
  sleep "$(jq -r '.identity.boot_quiet_seconds' "$CONFIG")"
  capture_screen D2-boot
  fail_if_red "$OUT/D2-boot.png"
  grep -Fq "$(jq -r '.identity.banner' "$CONFIG")" "$OUT/D2-boot.txt"
  grep -Fq "$(jq -r '.identity.prompt' "$CONFIG")" "$OUT/D2-boot.txt"
)

if [ "$ACTION" = capture-green ]; then
  [ -e "$OUT/quiet-complete-epoch" ] && [ ! -e "$OUT/D2-final.png" ] || {
    echo "D2 green capture is not armed" >&2; exit 3;
  }
  # CAPTURE-GREEN-BEGIN
  : > "$OUT/make-owner-confirmed"
  capture_screen D2-final
  fail_if_red "$OUT/D2-final.png"
  OUT=$OUT python3 "$PY" result-green
  # CAPTURE-GREEN-END
  echo "D2 GREEN: defstruct selected for v1.4.0."
  exit 0
fi

[ ! -e "$OUT/contact.consumed" ] || {
  echo "D2 contact already consumed" >&2; exit 3;
}
: > "$OUT/contact.consumed"

# START-D2-BEGIN
fresh_start
ftp_library
load_identity
: > "$OUT/ready-for-require"
# START-D2-END

echo "D2 READY AT lisp65>: type (require 'defstruct) physically."
echo "Wait for visible t, then report t. No automated input has run."
