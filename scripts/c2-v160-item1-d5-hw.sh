#!/bin/sh
# Capture the release-terminal v1.6 D5 headroom row after owner input.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v160_item1_d5.py
OUT=${OUT:-build/c2.3/v1.6-item1-d5}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|capture-final) ;;
  *) echo "usage: $0 <dry-run|capture-final>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  echo "V1.6 D5: fresh accepted Item-1 product boot"
  echo "LOAD: v16core; ABSENT: repl-comfort"
  echo "OWNER: five physical forms, one per submission"
  echo "FINAL: exactly one stopped-state physical Bank-0 capture"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
}
[ -e "$OUT/rows-complete" ] && [ ! -e "$OUT/final-capture-complete" ] || {
  echo "v1.6 D5 rows are incomplete or final capture already exists" >&2; exit 3;
}
mkdir -p "$OUT"
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }

# IDLE-ONLY: every D5 form has returned before any automated observation.
run_m65 --screenshot="$OUT/final-idle.png" > "$OUT/final-idle.ansi.txt"
python3 - "$OUT/final-idle.ansi.txt" "$OUT/final-idle.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
python3 - "$OUT/final-idle.png" <<'PY'
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

# The only stop and the only physical Bank-0 capture in this D5 session.
run_m65 -H --memsave "0x00000000:0x0000c000=$OUT/final-physical-bank0.bin"
python3 "$PY" verify-headroom --path "$OUT/final-physical-bank0.bin"
: > "$OUT/final-capture-complete"
python3 "$PY" record
echo "V1.6 D5 GREEN; CPU STOPPED; CANDIDATE SEAL OPEN."
