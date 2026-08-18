#!/bin/sh
# Crossing-free Link-108 D1 successor. No automated access after product mount.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v150-v21-product-liveness-far-device-session.json
PY=tools/host-lisp/c2_v21_product_liveness_phase1_successor.py
OUT=${OUT:-build/c2.3/v2.1-product-liveness-phase1-successor}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
PRODUCT_REMOTE=V21L108S.D81
LIBRARY_REMOTE=V21L108SL.D81

case "$ACTION" in
  dry-run|stage|confirm-terminal) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-terminal>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  echo "D1 ONLY: fresh BASIC -> one FTP lifetime/readback -> product mount"
  echo "AFTER MOUNT: zero automated device access; physical owner observation only"
  echo "EXPECT: STAGING MEDIA / BUILDING HEAP / LOADING LIBRARIES / WORKBENCH / prompt"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"
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

ftp_bundle_under_basic() (
  product=$(jq -r '.identity.product_medium' "$CONFIG")
  library=$(jq -r '.identity.library_medium' "$CONFIG")
  log=$OUT/media-upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $product $PRODUCT_REMOTE" \
    -c "get $PRODUCT_REMOTE $OUT/product-readback.d81" \
    -c "put $library $LIBRARY_REMOTE" \
    -c "get $LIBRARY_REMOTE $OUT/library-readback.d81" \
    -c "mount $PRODUCT_REMOTE" -c exit > "$log" 2>&1 &
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
  cmp "$product" "$OUT/product-readback.d81"
  cmp "$library" "$OUT/library-readback.d81"
)

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/contact.consumed" ] || {
    echo "crossing-free D1 contact already consumed" >&2; exit 3;
  }
  : > "$OUT/contact.consumed"
  run_m65 -F
  sleep 5
  capture_fresh_basic
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ftp_bundle_under_basic
  # PRODUCT-LIVE-BEGIN: no automated device access from here onward.
  sleep "$(jq -r '.boot_access_free_seconds' "$CONFIG")"
  : > "$OUT/owner-observation-awaiting"
  echo "OWNER OBSERVE PHYSICALLY. Do not run monitor, screenshot, FTP or freezer."
  exit 0
fi

[ -e "$OUT/owner-observation-awaiting" ] \
  && [ ! -e "$OUT/owner-terminal-confirmed" ] || {
    echo "crossing-free D1 owner-confirmation state invalid" >&2; exit 3;
  }
printf '%s\n' \
  'LISP65: STAGING MEDIA' \
  'LISP65: BUILDING HEAP' \
  'LISP65: LOADING LIBRARIES' \
  'WORKBENCH 1.5.0' \
  'lisp65>' > "$OUT/owner-visible-postcondition.txt"
: > "$OUT/owner-terminal-confirmed"
python3 "$PY" record
echo "D1 GREEN. D2-D5 are now permitted; none has run."
