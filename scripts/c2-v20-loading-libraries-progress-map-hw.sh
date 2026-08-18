#!/bin/sh
# Autonomous bundled MAP CPU-transport probe plus target progress ring.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
ACTION=${1:-dry-run}
SESSION=config/c2-v20-loading-libraries-progress-map-session.json
PROBE=tools/host-lisp/c2_v20_map_cpu_transport_probe.py
CONTACT=tools/host-lisp/c2_v20_loading_libraries_progress_map_contact.py
OUT=build/c2.3/v2.0-loading-libraries-progress-map/contact
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

python3 "$PROBE" check
python3 "$CONTACT" selftest >/dev/null
python3 "$CONTACT" preflight >/dev/null

if [ "$ACTION" = dry-run ]; then
  echo "BUNDLED CONTACT DRY-RUN PASS"
  echo "fresh BASIC -> one FTP lifetime/readback/mount -> 180 seconds target-only sampling"
  echo "then exactly one t1 and raw-first reads in the same stopped session"
  echo "owner keyboard=0; active observations=0; D1-D5=closed"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"
[ ! -e "$OUT/contact.consumed" ] || {
  echo "bundled autonomous contact already consumed" >&2; exit 3;
}
: > "$OUT/contact.consumed"

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

product=$(jq -r '.inputs.product_medium' "$SESSION")
library=$(jq -r '.inputs.library_medium' "$SESSION")
product_remote=$(jq -r '.inputs.product_remote' "$SESSION")
library_remote=$(jq -r '.inputs.library_remote' "$SESSION")

run_m65 -F
sleep 5
capture_screen fresh-basic
fail_if_red "$OUT/fresh-basic.png"
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"

log=$OUT/media-upload.log
: > "$log"
stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $product $product_remote" \
  -c "get $product_remote $OUT/product-readback.d81" \
  -c "put $library $library_remote" \
  -c "get $library_remote $OUT/library-readback.d81" \
  -c "mount $product_remote" -c exit > "$log" 2>&1 &
pid=$!; last=-1; progress=$(date +%s)
while kill -0 "$pid" 2>/dev/null; do
  sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
  if [ "$size" -ne "$last" ]; then last=$size; progress=$now
  elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
    exit 124
  fi
done
wait "$pid"
cmp "$product" "$OUT/product-readback.d81"
cmp "$library" "$OUT/library-readback.d81"

# ACTIVE-QUIET-BEGIN: the product and only its owned raster IRQ touch target
# state.  No monitor, screenshot, FTP or owner keyboard action is permitted.
sleep "$(jq -r '.active_interval.quiet_seconds' "$SESSION")"
# ACTIVE-QUIET-END: the sole final t1 below ends the target-owned interval.

DEVICE="$DEVICE" python3 "$CONTACT" capture > "$OUT/capture.stdout.json"
python3 "$CONTACT" record > "$OUT/result.stdout.json"
python3 "$CONTACT" check >/dev/null

echo "BUNDLED CONTACT COMPLETE; CPU remains stopped; D1-D5 remain closed"
jq '{probe, progress_ring}' "$OUT/result.json"
