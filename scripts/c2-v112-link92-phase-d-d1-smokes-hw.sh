#!/bin/sh
# Link-92 Phase-D D1 q/time/string smokes against the already-green REPL.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v112-link92-phase-d-d1-smokes.json
PY=tools/host-lisp/c2_v112_phase_d_d1_smokes.py
OUT=${OUT:-build/c2.3/v1.4.0-release/phase-d-split/d1-smokes}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|resume-d1) ;;
  *) echo "usage: $0 <dry-run|resume-d1>" >&2; exit 2 ;;
esac

python3 "$PY" check

run_exact_form() (
  prefix=$1
  form=$2
  expected=$3
  OUT_DIR=$OUT PREFIX=$prefix TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --wait 2 \
      --expect "$expected" --expect-poll 45 --form "$form"
  python3 tools/host-lisp/repl_screen_check.py \
    --screen "$OUT/$prefix.txt" --image "$OUT/$prefix.png" \
    --form-text "$form" --expect "$expected"
)

run_time_form() (
  prefix=$1
  form=$2
  OUT_DIR=$OUT PREFIX=$prefix TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --wait 3 --form "$form"
  python3 "$PY" check-time
)

if [ "$ACTION" = dry-run ]; then
  time_form=$(jq -r '.rows[] | select(.id == "time") | .form' "$CONFIG")
  q_form=$(jq -r '.rows[] | select(.id == "q") | .form' "$CONFIG")
  q_expect=$(jq -r '.rows[] | select(.id == "q") | .expect' "$CONFIG")
  OUT_DIR=$OUT PREFIX=D1-q TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --dry-run --verified-input --wait 2 \
      --expect "$q_expect" --expect-poll 45 --form "$q_form"
  OUT_DIR=$OUT PREFIX=D1-time-structural TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --dry-run --verified-input --wait 3 \
      --form "$time_form"
  echo "DRY-RUN: python3 $PY check-time"
  string_form=$(jq -r '.rows[] | select(.id == "strings") | .form' "$CONFIG")
  string_expect=$(jq -r '.rows[] | select(.id == "strings") | .expect' "$CONFIG")
  OUT_DIR=$OUT PREFIX=D1-strings TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --dry-run --verified-input --wait 2 \
      --expect "$string_expect" --expect-poll 45 --form "$string_form"
  echo "DRY-RUN: split restart q -> time(structural) -> strings"
  echo "SCOPE: D1 smokes only; no reset, remount, D3 or D2"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2
  exit 3
}
mkdir -p "$OUT"
[ ! -e "$OUT/D1-q.txt" ] && [ ! -e "$OUT/D1-time-structural.txt" ] && \
  [ ! -e "$OUT/D1-strings.txt" ] || {
  echo "D1 smoke row already consumed" >&2
  exit 3
}

capture_context() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --screenshot="$OUT/D1-resume-context.png" > "$OUT/D1-resume-context.ansi.txt"
  python3 - "$OUT/D1-resume-context.ansi.txt" "$OUT/D1-resume-context.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
  python3 tools/host-lisp/repl_screen_check.py \
    --screen "$OUT/D1-resume-context.txt" --image "$OUT/D1-resume-context.png" \
    --form-text "" --active-input
  grep -Fq "$(jq -r '.candidate.banner' "$CONFIG")" "$OUT/D1-resume-context.txt"
}

# D1-SMOKE-ORDER-BEGIN: the source gate owns this exact precedence.
capture_context
q_form=$(jq -r '.rows[] | select(.id == "q") | .form' "$CONFIG")
q_expect=$(jq -r '.rows[] | select(.id == "q") | .expect' "$CONFIG")
run_exact_form D1-q "$q_form" "$q_expect"
time_form=$(jq -r '.rows[] | select(.id == "time") | .form' "$CONFIG")
run_time_form D1-time-structural "$time_form"
string_form=$(jq -r '.rows[] | select(.id == "strings") | .form' "$CONFIG")
string_expect=$(jq -r '.rows[] | select(.id == "strings") | .expect' "$CONFIG")
run_exact_form D1-strings "$string_form" "$string_expect"
python3 "$PY" result
# D1-SMOKE-ORDER-END
