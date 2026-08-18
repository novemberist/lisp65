#!/bin/sh
# Exact owner-authorized Bank-4 MAP probe; no access after mount until t1.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
ACTION=${1:-dry-run}
PY=tools/host-lisp/c2_v21_bank4_map_probe.py
SESSION=config/c2-v21-bank4-map-probe-session.json
OUT=build/c2.3/v2.1-bank4-map-probe/contact
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|contact) ;;
  *) echo "usage: $0 <dry-run|contact>" >&2; exit 2 ;;
esac

python3 "$PY" check
if [ "$ACTION" = dry-run ]; then
  echo "BANK4 MAP CONTACT DRY-RUN PASS"
  echo "fresh BASIC -> one FTP upload/readback/mount -> 75 seconds no access"
  echo "then exactly one t1 and raw-first probe/source reads; no resume"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"
[ ! -e "$OUT/contact.consumed" ] || {
  echo "Bank-4 MAP contact already consumed" >&2; exit 3;
}
: > "$OUT/contact.consumed"

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
capture_fresh_basic() (
  run_m65 --screenshot="$OUT/fresh-basic.png" > "$OUT/fresh-basic.ansi.txt"
  python3 - "$OUT/fresh-basic.ansi.txt" "$OUT/fresh-basic.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
)

product=$(jq -r '.inputs.product_medium' "$SESSION")
remote=$(jq -r '.inputs.product_remote' "$SESSION")
run_m65 -F
sleep 5
capture_fresh_basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"

log=$OUT/media-upload.log
: > "$log"
stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $product $remote" \
  -c "get $remote $OUT/product-readback.d81" \
  -c "mount $remote" -c exit > "$log" 2>&1 &
pid=$!; last=-1; progress=$(date +%s)
while kill -0 "$pid" 2>/dev/null; do
  sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
  if [ "$size" -ne "$last" ]; then last=$size; progress=$now
  elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
    kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
    echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2; exit 124
  fi
done
wait "$pid"
cmp "$product" "$OUT/product-readback.d81"

# ACTIVE-QUIET-BEGIN: no monitor, screenshot, FTP or keyboard access.
sleep "$(jq -r '.active_interval.quiet_seconds' "$SESSION")"
# ACTIVE-QUIET-END: the capture owns the sole t1 and leaves the CPU stopped.
DEVICE="$DEVICE" python3 "$PY" capture > "$OUT/capture.stdout.json"
python3 "$PY" record > "$OUT/result.stdout.json"

echo "BANK4 MAP CONTACT COMPLETE; CPU remains stopped; D3-D5 remain closed"
jq '{status, decision, target}' "$OUT/result.json"
