#!/bin/sh
# Continue the already-green v1.5 stager-liveness D1 through D2-D5.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
ROWS=config/c2-v150-link97-device-rows.json
PY=tools/host-lisp/c2_v150_stager_liveness_d2_d5.py
D1=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.5.0-link97-stager-liveness-d1-receipt.json
OUT=${OUT:-build/c2.3/v1.5.0-link97-stager-liveness-d2-d5}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}
# NO-POST-BOOT-FTP: the library was uploaded before the already-green D1 boot.

case "$ACTION" in
  dry-run|confirm-library|wait-row|capture-final) ;;
  *) echo "usage: $0 <dry-run|confirm-library|wait-row|capture-final>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  echo "D1 GREEN: no reboot and no post-boot FTP"
  echo "OWNER: Freezer-mount V15LIB.D81 on drive 8 and return with F3"
  echo "D2-D5: 19 physical forms; one postcondition after each quiet floor"
  echo "D3: guard readback after point; D5: four release-terminal <=2-frame oracles"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
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

if [ "$ACTION" = confirm-library ]; then
  [ ! -e "$OUT/library-owner-confirmed" ] || {
    echo "v1.5 continuation library already confirmed" >&2; exit 3;
  }
  D1_GREEN=$(jq -r '.status' "$D1")
  [ "$D1_GREEN" = V150-LINK97-STAGER-LIVENESS-D1-GREEN ] || {
    echo "green D1 authority absent" >&2; exit 3;
  }
  # OWNER-FREEZER-MOUNT: physical idle-REPL media change; no FTP and no reboot.
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
    echo "v1.5 continuation row is not armed" >&2; exit 3;
  }
  row=$(cat "$OUT/next-row")
  [ "$row" != COMPLETE ] || { echo "all D2-D5 rows complete" >&2; exit 3; }
  quiet=$(jq -r --arg id "$row" \
    '.rows[] | select(.id == $id) | .quiet_floor_seconds' "$ROWS")
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
    run_m65 -H --memsave \
      "0x0000b582:0x0000b592=$OUT/d3-terminal-return-guard.bin"
    python3 "$PY" verify-guard --path "$OUT/d3-terminal-return-guard.bin"
    run_m65 -r
  fi
  next=$(jq -r --arg id "$row" \
    '[.rows[].id] as $ids | ($ids | index($id)) as $at | if $at + 1 < ($ids | length) then $ids[$at + 1] else "COMPLETE" end' "$ROWS")
  printf '%s\n' "$next" > "$OUT/next-row"
  if [ "$next" = COMPLETE ]; then
    : > "$OUT/rows-complete"
    echo "D2-D5 ROWS GREEN. Run capture-final."
  else
    echo "ROW $row GREEN. Type next: $(jq -r --arg id "$next" '.rows[] | select(.id == $id) | .form' "$ROWS")"
  fi
  exit 0
fi

[ -e "$OUT/rows-complete" ] && [ ! -e "$OUT/final-capture-complete" ] || {
  echo "v1.5 continuation final-capture state invalid" >&2; exit 3;
}
run_m65 -H --memsave \
  "0x0000b582:0x0000b592=$OUT/final-terminal-return-guard.bin"
python3 "$PY" verify-guard --path "$OUT/final-terminal-return-guard.bin"
: > "$OUT/final-capture-complete"
python3 "$PY" record
echo "V1.5 D1-D5 SESSION GREEN; CPU STOPPED; OWNER HALT PENDING."
