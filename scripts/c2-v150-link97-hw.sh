#!/bin/sh
# Owner-guided v1.5 Link-97 D1-D5 session. Never use FTP against a live REPL.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v150-link97-device-session.json
ROWS=config/c2-v150-link97-device-rows.json
PY=tools/host-lisp/c2_v150_device_session.py
OUT=${OUT:-build/c2.3/v1.5.0-link97-device-session}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
PRODUCT_REMOTE=V15L97.D81
LIBRARY_REMOTE=V15LIB.D81

case "$ACTION" in
  dry-run|stage|confirm-liveness|confirm-library|wait-row|capture-final) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-liveness|confirm-library|wait-row|capture-final>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  echo "D1: fresh BASIC -> one FTP lifetime/readback -> product mount last -> 45s untouched boot"
  echo "OWNER: observe all three LISP65 boot-life signs; confirm them explicitly"
  echo "MOUNT: Freezer-mount V15LIB.D81 on drive 8 and return with F3"
  echo "D2-D5: physical forms only; one postcondition after each quiet floor"
  echo "D3: guard readback only after (point 3 4); D5: four <=2-frame time oracles"
  echo "RULE: no FTP invocation after product boot; no polling during an active form"
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
  product_remote=$PRODUCT_REMOTE
  library_remote=$LIBRARY_REMOTE
  log=$OUT/media-upload.log
  : > "$log"
  # FTP-BASIC-ONLY-BEGIN: exactly one helper lifetime, before product boot.
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $product $product_remote" \
    -c "get $product_remote $OUT/product-readback.d81" \
    -c "put $library $library_remote" \
    -c "get $library_remote $OUT/library-readback.d81" \
    -c "mount $product_remote" -c exit > "$log" 2>&1 &
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
  [ ! -e "$OUT/contact.consumed" ] || { echo "v1.5 D1-D5 contact already consumed" >&2; exit 3; }
  : > "$OUT/contact.consumed"
  run_m65 -F
  sleep 5
  capture_screen fresh-basic
  fail_if_red "$OUT/fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ftp_bundle_under_basic
  # PRODUCT-LIVE-BEGIN: no FTP token or helper call is permitted below.
  sleep "$(jq -r '.boot_access_free_seconds' "$CONFIG")"
  capture_screen product-boot
  fail_if_red "$OUT/product-boot.png"
  grep -Fq 'WORKBENCH 1.5.0' "$OUT/product-boot.txt"
  grep -Fq 'lisp65>' "$OUT/product-boot.txt"
  : > "$OUT/freezer-mount-required"
  # PRODUCT-LIVE-END
  echo "D1 TERMINAL GREEN. Confirm the three visible boot-life signs with confirm-liveness."
  exit 0
fi

if [ "$ACTION" = confirm-liveness ]; then
  [ -e "$OUT/freezer-mount-required" ] && [ ! -e "$OUT/boot-liveness-owner-confirmed" ] || {
    echo "v1.5 boot-liveness confirmation state invalid" >&2; exit 3;
  }
  : > "$OUT/boot-liveness-owner-confirmed"
  echo "D1 GREEN. In Freezer mount V15LIB.D81 on drive 8, return with F3, then run confirm-library."
  exit 0
fi

if [ "$ACTION" = confirm-library ]; then
  [ -e "$OUT/freezer-mount-required" ] && [ -e "$OUT/boot-liveness-owner-confirmed" ] \
    && [ ! -e "$OUT/library-owner-confirmed" ] || {
      echo "v1.5 Freezer confirmation state invalid" >&2; exit 3;
    }
  # OWNER-FREEZER-MOUNT: physical idle-REPL media change; deliberately no FTP.
  capture_screen library-mounted
  fail_if_red "$OUT/library-mounted.png"
  grep -Fq 'WORKBENCH 1.5.0' "$OUT/library-mounted.txt"
  grep -Fq 'lisp65>' "$OUT/library-mounted.txt"
  : > "$OUT/library-owner-confirmed"
  jq -r '.rows[0].id' "$ROWS" > "$OUT/next-row"
  echo "LIBRARY CONFIRMED. Type exactly: $(jq -r '.rows[0].form' "$ROWS")"
  exit 0
fi

if [ "$ACTION" = wait-row ]; then
  [ -e "$OUT/library-owner-confirmed" ] && [ -e "$OUT/next-row" ] || {
    echo "v1.5 row is not armed" >&2; exit 3;
  }
  row=$(cat "$OUT/next-row")
  [ "$row" != COMPLETE ] || { echo "all D1-D5 rows already complete" >&2; exit 3; }
  quiet=$(jq -r --arg id "$row" '.rows[] | select(.id == $id) | .quiet_floor_seconds' "$ROWS")
  [ "$quiet" != null ] || { echo "unknown v1.5 row: $row" >&2; exit 3; }
  # ACTIVE-FORM-BEGIN: no device access of any kind in this block.
  sleep "$quiet"
  # ACTIVE-FORM-END
  capture_screen "row-$row"
  fail_if_red "$OUT/row-$row.png"
  python3 "$PY" verify-row --row "$row" \
    --text "$OUT/row-$row.txt" --image "$OUT/row-$row.png"
  : > "$OUT/row-$row-passed"
  if [ "$row" = d3-make-point ]; then
    run_m65 -H --memsave "0x0000b582:0x0000b592=$OUT/d3-terminal-return-guard.bin"
    python3 "$PY" verify-guard --path "$OUT/d3-terminal-return-guard.bin"
    run_m65 -r
  fi
  next=$(jq -r --arg id "$row" '[.rows[].id] as $ids | ($ids | index($id)) as $at | if $at + 1 < ($ids | length) then $ids[$at + 1] else "COMPLETE" end' "$ROWS")
  printf '%s\n' "$next" > "$OUT/next-row"
  if [ "$next" = COMPLETE ]; then
    : > "$OUT/rows-complete"
    echo "D1-D5 ROWS GREEN. Run capture-final for the standing post-session readback."
  else
    echo "ROW $row GREEN. Type next: $(jq -r --arg id "$next" '.rows[] | select(.id == $id) | .form' "$ROWS")"
  fi
  exit 0
fi

[ -e "$OUT/rows-complete" ] && [ ! -e "$OUT/final-capture-complete" ] || {
  echo "v1.5 final capture state invalid" >&2; exit 3;
}
run_m65 -H --memsave "0x0000b582:0x0000b592=$OUT/final-terminal-return-guard.bin"
python3 "$PY" verify-guard --path "$OUT/final-terminal-return-guard.bin"
: > "$OUT/final-capture-complete"
python3 "$PY" record
echo "V1.5 D1-D5 SESSION GREEN; CPU STOPPED; OWNER HALT PENDING."
