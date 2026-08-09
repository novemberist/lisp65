#!/bin/sh
# Link-92 Phase-D D1 launch only, after the v1.3 boot-choreography desk diff.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v112-link92-phase-d-boot-choreography.json
PY=tools/host-lisp/c2_v112_phase_d_boot_choreography.py
OUT=${OUT:-build/c2.3/v1.4.0-release/phase-d-split/d1-boot}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|start-d1) ;;
  *) echo "usage: $0 <dry-run|start-d1>" >&2; exit 2 ;;
esac

python3 "$PY" check
media=$(jq -r '.d1.media' "$CONFIG")
expected_sha=$(jq -r '.d1.media_sha256' "$CONFIG")
remote=$(jq -r '.d1.remote' "$CONFIG")
quiet=$(jq -r '.d1.quiet_seconds_before_first_observation' "$CONFIG")
banner=$(jq -r '.d1.expected_banner' "$CONFIG")
prompt=$(jq -r '.d1.expected_prompt' "$CONFIG")

[ "$(sha256sum "$media" | awk '{print $1}')" = "$expected_sha" ]

if [ "$ACTION" = dry-run ]; then
  echo "DRY-RUN: cold reset -> fresh BASIC assert -> exact D81 put/get/mount"
  echo "DRY-RUN: FTP mount-and-reset exit -> no second reset -> 45 seconds quiet"
  echo "ASSERT: fail-closed frame absent; WORKBENCH 1.4.0 and lisp65> visible"
  echo "SCOPE: D1 launch only; no D1 smoke, D3 or D2"
  exit 0
fi

mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

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

fresh_start() (
  prefix=$1
  run_m65 -F
  sleep 5
  capture_screen "$prefix-fresh-basic"
  fail_if_red "$OUT/$prefix-fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/$prefix-fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/$prefix-fresh-basic.txt"
)

ftp_package() (
  prefix=$1
  log=$OUT/$prefix-upload.log
  readback=$OUT/$prefix-package-readback.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $readback" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  last=-1
  progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last" ]; then
      last=$size
      progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$readback"
)

start_d1() {
  # BOOT-ORDER-BEGIN: the source gate owns this exact precedence.
  fresh_start D1
  ftp_package D1
  # The FTP helper owns the mount-and-reset exit.  No explicit reset follows.
  sleep "$quiet"
  capture_screen D1-banner
  fail_if_red "$OUT/D1-banner.png"
  grep -Fq "$banner" "$OUT/D1-banner.txt"
  grep -Fq "$prompt" "$OUT/D1-banner.txt"
  # BOOT-ORDER-END
}

start_d1
