#!/bin/sh
# Nonpromotable v1.2.4 Chip-RAM append-visibility curve.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v124_chipram_visibility_curve.py
DEPLOY=build/post-promotion/v124/chipram-visibility/preparation/deployment.json
OUT=${C2_V124_CURVE_OUT:-build/post-promotion/v124/chipram-visibility/hardware-session-01}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}
POLL_LIMIT=${POLL_LIMIT:-30}

case "$ACTION" in
  dry-run|start|evaluate) ;;
  *) echo "usage: $0 <dry-run|start|evaluate>" >&2; exit 2 ;;
esac

python3 "$PY" prepare

if [ "$ACTION" = dry-run ]; then
  echo "DRY-RUN: cold reset and assert BASIC 65 + READY"
  echo "DRY-RUN: stage exact accepted G5 C2D at 0x00050000"
  echo "DRY-RUN: assert phase-owner=0 and C2J=64x00"
  echo "DRY-RUN: capture Bank5 baseline, run nonpromotable curve"
  echo "DRY-RUN: capture mailbox, 4x256 curve, Bank5, C2J and require peek map"
  python3 "$PY" selftest
  exit
fi

if [ "$ACTION" = evaluate ]; then
  python3 "$PY" evaluate --out "$OUT"
  exit
fi

[ -x "$M65" ] || { echo "missing MEGA65 tool: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

mkdir -p "$OUT"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  start=$1
  bytes=$2
  path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}

capture_screen() {
  run_m65 --screenshot="$OUT/fresh-start.png" > "$OUT/fresh-start.ansi.txt"
  python3 - "$OUT/fresh-start.ansi.txt" "$OUT/fresh-start.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

fresh_start_gate() {
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen
    if grep -Fq 'BASIC 65' "$OUT/fresh-start.txt" &&
       grep -Fq 'READY.' "$OUT/fresh-start.txt" &&
       ! grep -Fq 'lisp65>' "$OUT/fresh-start.txt"; then
      return 0
    fi
    sleep 1
    poll=$((poll + 1))
  done
  return 1
}

prg=$(jq -r '.prg.path' "$DEPLOY")
c2d=$(jq -r '.accepted_G5_C2D_stage.path' "$DEPLOY")
c2d_bytes=$(jq -r '.accepted_G5_C2D_stage.bytes' "$DEPLOY")
c2d_sha=$(jq -r '.accepted_G5_C2D_stage.sha256' "$DEPLOY")
mailbox=$(jq -r '.addresses.mailbox' "$DEPLOY")
mailbox_bytes=$(jq -r '.addresses.mailbox_bytes' "$DEPLOY")
phase_owner=$(jq -r '.addresses.phase_owner' "$DEPLOY")
c2j=$(jq -r '.addresses.C2J' "$DEPLOY")
c2j_bytes=$(jq -r '.addresses.C2J_bytes' "$DEPLOY")
bank5=$(jq -r '.addresses.Bank5' "$DEPLOY")
bank5_bytes=$(jq -r '.addresses.Bank5_bytes' "$DEPLOY")
curve=$(jq -r '.geometry.probe_curve.address' "$DEPLOY")
curve_bytes=$(jq -r '.geometry.probe_curve.bytes' "$DEPLOY")
zero_c2j=$(jq -r '.zero_c2j.path' "$DEPLOY")

run_m65 -F
sleep 3
fresh_start_gate || {
  echo "fresh BASIC startup state not proven after cold reset" >&2
  exit 3
}

run_m65 -H -@ "$c2d@0x00050000"
readback "$bank5" "$c2d_bytes" "$OUT/c2d-stage-readback.bin"
printf '%s  %s\n' "$c2d_sha" "$OUT/c2d-stage-readback.bin" |
  sha256sum -c -

run_m65 -H -@ "$zero_c2j@0x0005c640"
readback "$phase_owner" 1 "$OUT/phase-owner-before.bin"
readback "$c2j" "$c2j_bytes" "$OUT/c2j-before.bin"
python3 - "$OUT/phase-owner-before.bin" "$OUT/c2j-before.bin" <<'PY'
from pathlib import Path
import sys
if Path(sys.argv[1]).read_bytes() != b"\0":
    raise SystemExit("phase owner is not NONE before curve")
if Path(sys.argv[2]).read_bytes() != bytes(64):
    raise SystemExit("C2J is not CLEAR before curve")
PY
readback "$bank5" "$bank5_bytes" "$OUT/bank5-before.bin"

run_m65 -r -1 "$prg"
poll=0
while [ "$poll" -lt "$POLL_LIMIT" ]; do
  readback "$mailbox" "$mailbox_bytes" "$OUT/mailbox-poll.bin"
  state=$(od -An -tu1 -j5 -N1 "$OUT/mailbox-poll.bin" | tr -d ' ')
  [ "$state" = 165 ] && break
  sleep 1
  poll=$((poll + 1))
done
[ "$poll" -lt "$POLL_LIMIT" ] || {
  echo "curve completion mailbox timed out" >&2
  exit 4
}
mv "$OUT/mailbox-poll.bin" "$OUT/mailbox.bin"

readback "$curve" "$curve_bytes" "$OUT/curve.bin"
readback "$bank5" "$bank5_bytes" "$OUT/bank5-after.bin"
readback "$phase_owner" 1 "$OUT/phase-owner-after.bin"
readback "$c2j" "$c2j_bytes" "$OUT/c2j-after.bin"
readback 0x0000c1f4 2 "$OUT/require-trace.bin"
readback 0x00050000 48 "$OUT/c2d-header.bin"
readback 0x000500f0 32 "$OUT/place-row.bin"

python3 "$PY" evaluate --out "$OUT"
