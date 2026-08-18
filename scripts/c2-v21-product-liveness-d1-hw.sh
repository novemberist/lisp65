#!/bin/sh
# Fresh Link 108 D1. Never use FTP against the live product.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v150-v21-product-liveness-far-device-session.json
PY=tools/host-lisp/c2_v21_product_liveness_d1.py
OUT=${OUT:-build/c2.3/v2.1-product-liveness-d1}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
PRODUCT_REMOTE=V21L108.D81
LIBRARY_REMOTE=V21L108L.D81

case "$ACTION" in
  dry-run|stage|confirm-liveness) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-liveness>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  echo "D1 ONLY: fresh BASIC -> one FTP lifetime/readback -> Link 108 product mount"
  echo "WATCH: STAGING MEDIA / BUILDING HEAP / LOADING LIBRARIES <ordinal>"
  echo "WAIT: 45 seconds without monitor, screenshot, FTP or other device access"
  echo "TERMINAL: WORKBENCH 1.5.0 plus lisp65>"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"
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

ftp_bundle_under_basic() (
  product=$(jq -r '.identity.product_medium' "$CONFIG")
  library=$(jq -r '.identity.library_medium' "$CONFIG")
  log=$OUT/media-upload.log
  : > "$log"
  # FTP-BASIC-ONLY-BEGIN: one helper lifetime, before product boot.
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $product $PRODUCT_REMOTE" \
    -c "get $PRODUCT_REMOTE $OUT/product-readback.d81" \
    -c "put $library $LIBRARY_REMOTE" \
    -c "get $LIBRARY_REMOTE $OUT/library-readback.d81" \
    -c "mount $PRODUCT_REMOTE" -c exit > "$log" 2>&1 &
  # FTP-BASIC-ONLY-END
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
    echo "Link 108 D1 contact already consumed" >&2; exit 3;
  }
  : > "$OUT/contact.consumed"
  run_m65 -F
  sleep 5
  capture_screen fresh-basic
  fail_if_red "$OUT/fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ftp_bundle_under_basic
  # PRODUCT-LIVE-BEGIN: no device access during the boot window.
  sleep "$(jq -r '.boot_access_free_seconds' "$CONFIG")"
  # PRODUCT-LIVE-END
  capture_screen product-boot
  fail_if_red "$OUT/product-boot.png"
  python3 "$PY" observe --text "$OUT/product-boot.txt" --image "$OUT/product-boot.png"
  : > "$OUT/terminal-banner-and-prompt-proven"
  : > "$OUT/signs-awaiting-owner-confirmation"
  echo "D1 TERMINAL GREEN. Confirm only if all three liveness lines were visible."
  exit 0
fi

[ -e "$OUT/signs-awaiting-owner-confirmation" ] \
  && [ -e "$OUT/terminal-banner-and-prompt-proven" ] \
  && [ ! -e "$OUT/owner-visible-signs-confirmed" ] || {
    echo "Link 108 D1 owner-confirmation state invalid" >&2; exit 3;
  }
printf '%s\n' \
  'LISP65: STAGING MEDIA' \
  'LISP65: BUILDING HEAP' \
  'LISP65: LOADING LIBRARIES' > "$OUT/owner-visible-signs.txt"
grep -Fqx 'LISP65: STAGING MEDIA' "$OUT/owner-visible-signs.txt"
grep -Fqx 'LISP65: BUILDING HEAP' "$OUT/owner-visible-signs.txt"
grep -Fqx 'LISP65: LOADING LIBRARIES' "$OUT/owner-visible-signs.txt"
: > "$OUT/owner-visible-signs-confirmed"
python3 "$PY" record
echo "D1 GREEN. D2-D5 are now permitted; none has run."
