#!/bin/sh
# Restore pristine Link 71 and let its normal boot recovery clear stale C2J.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/clean-recovery-hardware
DEPLOY=build/post-promotion/link71-defstruct-header-crc-domain/hardware-session/deployment.json
M65=$TOOLS/m65
C2J_START=0x0005c640
C2J_BYTES=64
ZERO_C2J=build/c2.2/destructive-restage-link57/zero-c2j.bin

[ "$#" -eq 1 ] && [ "$1" = run ] || {
  echo "usage: $0 run" >&2
  exit 2
}
[ ! -e "$OUT/hardware-run.started" ] || {
  echo "Link-71 clean recovery is one-shot" >&2
  exit 3
}
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }
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
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

readback "$((C2J_START))" "$C2J_BYTES" "$OUT/stale-c2j-before.bin"
PRG=$(jq -r '.product.path' "$DEPLOY")
run_m65 -F -H -1 "$PRG"
touch "$OUT/hardware-run.started"
jq -c '.preloads[]' "$DEPLOY" |
while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  base=$(basename "$path")
  run_m65 -H -@ "$path@$address"
  readback "$((address))" "$bytes" "$OUT/readback-$base"
  cmp "$path" "$OUT/readback-$base"
done
run_m65 -H -@ "$ZERO_C2J@$C2J_START"
readback "$((C2J_START))" "$C2J_BYTES" "$OUT/readback-zero-c2j.bin"
cmp "$ZERO_C2J" "$OUT/readback-zero-c2j.bin"
run_m65 -r -1 "$PRG"

poll=0
while [ "$poll" -lt 45 ]; do
  capture_screen boot
  grep -q 'lisp65>' "$OUT/boot.txt" && break
  sleep 1
  poll=$((poll + 1))
done
[ "$poll" -lt 45 ] || {
  echo "Link-71 clean recovery First Red: no Lisp REPL" >&2
  exit 3
}
readback "$((C2J_START))" "$C2J_BYTES" "$OUT/c2j-after.bin"
python3 - "$OUT/c2j-after.bin" <<'PY'
from pathlib import Path
import sys
value = Path(sys.argv[1]).read_bytes()
assert len(value) == 64
if any(value):
    raise SystemExit("Link-71 clean recovery First Red: C2J is nonzero")
PY
echo "Link-71 pristine recovery PASS: clean REPL and C2J all zero."
