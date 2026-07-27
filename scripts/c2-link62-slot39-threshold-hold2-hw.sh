#!/bin/sh
# One-shot rebound, nonpromotable Link-62 Slot-39 threshold hold.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
WAIT=${WAIT:-28}
OUT=build/c2.2/hardware-link62-slot39-threshold-hold2-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_link62_slot39_threshold_hold2.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] && [ "$1" = "deploy-and-capture" ] || {
  echo "usage: $0 deploy-and-capture" >&2
  exit 2
}

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }
[ ! -e "$OUT/hardware-run.started" ] || {
  echo "threshold-hold2 hardware run is one-shot" >&2
  exit 3
}

run_m65() {
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$(printf '%08x' "$((rb_start + rb_bytes))")
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$rb_end=$rb_path"
}

upload_and_verify() {
  uv_path=$1
  uv_address=$2
  uv_bytes=$3
  uv_readback=$4
  run_m65 -H -@ "$uv_path@0x$(printf '%08x' "$uv_address")"
  readback "$uv_address" "$uv_bytes" "$uv_readback"
  cmp "$uv_path" "$uv_readback"
}

PRG=$(jq -r '.product.path' "$DEPLOY")
run_m65 -F -H -1 "$PRG"
touch "$OUT/hardware-run.started"
jq -c '.preloads[]' "$DEPLOY" |
while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  upload_and_verify "$path" "$address" "$bytes" \
    "$OUT/deploy-readback-$(basename "$path")"
done
run_m65 -r -1 "$PRG"
sleep "$WAIT"

run_m65 --screenshot="$OUT/boot-screen.png" > "$OUT/boot-screen.ansi.txt"
python3 - "$OUT/boot-screen.ansi.txt" "$OUT/boot-screen.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
text = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw)
Path(sys.argv[2]).write_text(text, encoding="utf-8")
if "lisp65>" not in text or "*** vm:" in text:
    raise SystemExit("threshold-hold2 boot did not reach a clean REPL")
PY

run_m65 -T "$(jq -r '.test.form' "$DEPLOY")"
sleep 4
timeout 15s "$M65" -l "$DEVICE" -B c8ca \
  > "$OUT/threshold-pc.txt" 2>&1
readback 0x0000c356 1526 "$OUT/runtime-slot39.bin"

capture_set() {
  cs_index=$1
  cs_dir=$OUT/capture-$cs_index
  mkdir "$cs_dir"
  readback 0x00000017 8 "$cs_dir/start-zp.bin"
  readback 0x0000c17c 32 "$cs_dir/completion-record.bin"
  readback 0x0000c1f0 8 "$cs_dir/trace.bin"
  readback 0x00000070 48 "$cs_dir/runtime-zp.bin"
  readback 0x0000ff83 5 "$cs_dir/frame.bin"
  readback 0x0005c640 64 "$cs_dir/c2j.bin"
  date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$cs_dir/captured-at.txt"
}

capture_set 1
sleep 1
capture_set 2
sleep 4
capture_set 3

python3 - "$OUT" <<'PY'
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
rows = []
for index in range(1, 4):
    raw = (out / f"capture-{index}/captured-at.txt").read_text().strip()
    rows.append({"index": index, "utc": raw})
(out / "capture-times.json").write_text(json.dumps({
    "format": "lisp65-Link62-slot39-threshold-hold2-times-v1",
    "interval_seconds": [0, 1, 5],
    "captures": rows,
}, indent=2, sort_keys=True) + "\n")
PY

run_m65 --screenshot="$OUT/threshold-screen.png" \
  > "$OUT/threshold-screen.ansi.txt"
python3 "$PY" evaluate
echo "Rebound threshold-hold captured and diagnostic identity retired."
