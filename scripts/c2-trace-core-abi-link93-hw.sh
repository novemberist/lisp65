#!/bin/sh
# Physical Link-93 trace/restoration row; never run FTP against a live REPL.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
ROW=${2:-}
CONFIG=${CONFIG:-config/c2-trace-core-abi-device-session.json}
PY=${PY:-tools/host-lisp/c2_trace_core_abi_device_session.py}
CROSSING=tools/host-lisp/c2_live_repl_ftp_crossing_gate.py
OUT=${OUT:-build/c2.3/trace-core-abi-link93-r6/device-session-corrected}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
SESSION_LABEL=${SESSION_LABEL:-Link-93}
PRODUCT_REMOTE=${PRODUCT_REMOTE:-TRACE93.D81}

case "$ACTION" in
  dry-run|stage|confirm-library|wait-row) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-library|wait-row> [row-id]" >&2; exit 2 ;;
esac

python3 "$PY" check
python3 "$CROSSING" check

if [ "$ACTION" = dry-run ]; then
  echo "STAGE: cold BASIC -> one FTP lifetime uploads/readbacks both D81s -> product mount last"
  echo "BOOT: helper exits -> 45s zero-access boot -> exact banner/prompt"
  echo "OWNER: Freezer-mount TRACELIB.D81 on drive 8, return with F3"
  echo "ROWS: six physical forms, each quiet to its floor, one postcondition screen"
  echo "RULE: zero FTP invocations after product boot"
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
  library_remote=TRACELIB.D81
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

verify_row() {
  row=$1 prefix=$2
  form=$(jq -r --arg id "$row" '.rows[] | select(.id == $id) | .form' "$CONFIG")
  ordered=$(jq -c --arg id "$row" '.rows[] | select(.id == $id) | .expect_ordered // null' "$CONFIG")
  if [ "$ordered" != null ]; then
    python3 - "$OUT/$prefix.txt" "$form" "$ordered" <<'PY'
from pathlib import Path
import json, sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
assert sys.argv[2] in text, "submitted form absent from postcondition"
at = -1
for token in json.loads(sys.argv[3]):
    at = text.find(token, at + 1)
    assert at >= 0, f"ordered postcondition absent: {token}"
PY
  else
    expected=$(jq -r --arg id "$row" '.rows[] | select(.id == $id) | .expect[0]' "$CONFIG")
    python3 tools/host-lisp/repl_screen_check.py \
      --screen "$OUT/$prefix.txt" --image "$OUT/$prefix.png" \
      --form-text "$form" --expect "$expected"
  fi
  jq -r --arg id "$row" '.rows[] | select(.id == $id) | (.forbid // [])[]' "$CONFIG" |
  while IFS= read -r forbidden; do
    ! grep -Fq "$forbidden" "$OUT/$prefix.txt"
  done
}

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/contact.consumed" ] || { echo "$SESSION_LABEL contact already consumed" >&2; exit 3; }
  : > "$OUT/contact.consumed"
  run_m65 -F
  sleep 5
  capture_screen fresh-basic
  fail_if_red "$OUT/fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ftp_bundle_under_basic
  # PRODUCT-LIVE-BEGIN: no FTP token or helper call is permitted below.
  sleep "$(jq -r '.identity.boot_quiet_seconds' "$CONFIG")"
  capture_screen product-boot
  fail_if_red "$OUT/product-boot.png"
  grep -Fq "$(jq -r '.identity.banner' "$CONFIG")" "$OUT/product-boot.txt"
  grep -Fq "$(jq -r '.identity.prompt' "$CONFIG")" "$OUT/product-boot.txt"
  : > "$OUT/freezer-mount-required"
  # PRODUCT-LIVE-END
  echo "STAGE GREEN. In Freezer mount TRACELIB.D81 on drive 8, return with F3, then run confirm-library."
  exit 0
fi

if [ "$ACTION" = confirm-library ]; then
  [ -e "$OUT/freezer-mount-required" ] && [ ! -e "$OUT/library-owner-confirmed" ] || {
    echo "$SESSION_LABEL Freezer confirmation state invalid" >&2; exit 3;
  }
  # OWNER-FREEZER-MOUNT: physical idle-REPL media change; deliberately no FTP.
  capture_screen library-mounted
  fail_if_red "$OUT/library-mounted.png"
  grep -Fq "$(jq -r '.identity.banner' "$CONFIG")" "$OUT/library-mounted.txt"
  grep -Fq "$(jq -r '.identity.prompt' "$CONFIG")" "$OUT/library-mounted.txt"
  : > "$OUT/library-owner-confirmed"
  jq -r '.rows[0].id' "$CONFIG" > "$OUT/next-row"
  echo "LIBRARY CONFIRMED. Type: $(jq -r '.rows[0].form' "$CONFIG")"
  exit 0
fi

[ "$ACTION" = wait-row ] && [ -n "$ROW" ] || { echo "wait-row requires row-id" >&2; exit 2; }
[ -e "$OUT/library-owner-confirmed" ] && [ -e "$OUT/next-row" ] || {
  echo "$SESSION_LABEL row is not armed" >&2; exit 3;
}
[ "$(cat "$OUT/next-row")" = "$ROW" ] || { echo "$SESSION_LABEL row order mismatch" >&2; exit 3; }
quiet=$(jq -r --arg id "$ROW" '.rows[] | select(.id == $id) | .quiet_floor_seconds' "$CONFIG")
[ "$quiet" != null ] || { echo "unknown $SESSION_LABEL row: $ROW" >&2; exit 3; }
# ACTIVE-TRACE-ROW-BEGIN: no device access of any kind in this block.
sleep "$quiet"
# ACTIVE-TRACE-ROW-END
capture_screen "row-$ROW"
fail_if_red "$OUT/row-$ROW.png"
verify_row "$ROW" "row-$ROW"
: > "$OUT/row-$ROW-passed"
next=$(jq -r --arg id "$ROW" '[.rows[].id] as $ids | ($ids | index($id)) as $at | if $at + 1 < ($ids | length) then $ids[$at + 1] else "COMPLETE" end' "$CONFIG")
printf '%s\n' "$next" > "$OUT/next-row"
if [ "$next" = COMPLETE ]; then
  : > "$OUT/rows-complete"
  echo "$SESSION_LABEL SIX ROWS GREEN. Do not change media; defstruct staging follows after cold reset."
else
  form=$(jq -r --arg id "$next" '.rows[] | select(.id == $id) | .form' "$CONFIG")
  echo "ROW $ROW GREEN. Type next: $form"
fi
