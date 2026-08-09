#!/bin/sh
# Owner-authorized ROMC-repaired physical launch + quiet D2 appointment.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_romc_repaired_d2_appointment.py
DEPLOY=build/c2.3/v1.6-defstruct-bootstrap-romc-repair/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-romc-repaired-bundled-appointment}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|stage|arm|capture) ;;
  *) echo "usage: $0 <dry-run|stage|arm|capture>" >&2; exit 2 ;;
esac

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
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
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$OUT/readback.d81"
}

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" check
  python3 "$PY" selftest
  echo "ROMC-SAFE D2 DRY RUN PASS physical-input=3 quiet=180s one-stop CPU-view"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" check >/dev/null
mkdir -p "$OUT"

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/stage.consumed" ] || { echo "stage already consumed" >&2; exit 3; }
  : > "$OUT/stage.consumed"
  run_m65 -F
  sleep 5
  screen fresh-basic
  python3 - "$OUT/fresh-basic.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "basic 65" in text or "ready." in text
assert "break" not in text and "monitor commands" not in text
PY
  medium=$(jq -r '.library_medium.path' "$DEPLOY")
  remote=$(jq -r '.library_remote' "$DEPLOY")
  ftp_medium "$medium" "$remote"
  PRODUCT=$(jq -r '.diagnostic.prg.path' "$DEPLOY")
  run_m65 -H "$PRODUCT"
  payload_bytes=$(($(wc -c < "$PRODUCT") - 2))
  readback 0x2001 "$payload_bytes" "$OUT/diagnostic-prg-payload.bin"
  python3 - "$PRODUCT" "$OUT/diagnostic-prg-payload.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes()[2:] == Path(sys.argv[2]).read_bytes()
PY
  jq -c '.diagnostic.preloads[]' "$DEPLOY" | while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/preload-$role.bin"
    cmp "$path" "$OUT/preload-$role.bin"
  done
  printf '\327' > "$OUT/boot-witness-reset.bin"
  run_m65 -H -@ "$OUT/boot-witness-reset.bin@0x0000b5c3"
  readback 0x0000b5c3 1 "$OUT/boot-witness-reset-readback.bin"
  cmp "$OUT/boot-witness-reset.bin" "$OUT/boot-witness-reset-readback.bin"
  run_m65 -r
  sleep 3
  screen launch-ready
  python3 - "$OUT/launch-ready.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "ready." in text
assert "break" not in text and "monitor commands" not in text
assert "lisp65>" not in text
PY
  : > "$OUT/stage.ready"
  echo "ROMC-SAFE D2 STAGE READY: type RUN and press RETURN physically."
  exit 0
fi

if [ "$ACTION" = arm ]; then
  [ -e "$OUT/stage.ready" ] || { echo "stage absent" >&2; exit 3; }
  [ ! -e "$OUT/arm.consumed" ] || { echo "record arm already consumed" >&2; exit 3; }
  : > "$OUT/arm.consumed"
  record=$(($(jq -r '.record.address' "$DEPLOY")))
  record_hex=0x$(printf '%08x' "$record")
  RESET=$(jq -r '.record.reset.path' "$DEPLOY")
  ARM=$(jq -r '.record.arm.path' "$DEPLOY")
  # No readback here: the owner-authorized boot witness is first read only in
  # the post-session set.  The two bound files are the canonical handoff.
  run_m65 -H -@ "$RESET@$record_hex"
  run_m65 -H -@ "$ARM@$record_hex"
  run_m65 -r
  : > "$OUT/arm.ready"
  echo "R/A/I/G RECORD ARMED: type (defstruct point x y) physically now."
  exit 0
fi

[ -e "$OUT/stage.ready" ] && [ -e "$OUT/arm.ready" ] || {
  echo "stage/arm handoff absent" >&2; exit 3;
}
exec python3 "$PY" capture --device "$DEVICE"
