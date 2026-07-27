#!/bin/sh
# One-shot final cycle: bounds holds plus caller reader-zero hold.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
WAIT=${WAIT:-28}
OUT=build/c2.2/hardware-link64-reader-zero-bounds-composite-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PATCH_DIR=build/c2.2/substitution/link64-c2d-reader-bounds-hold-NONPROMOTABLE
PY=tools/host-lisp/c2_link64_c2d_reader_zero_bounds_composite.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] && [ "$1" = deploy-and-arm ] || {
  echo "usage: $0 deploy-and-arm" >&2
  exit 2
}

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }
[ ! -e "$OUT/hardware-run.started" ] || {
  echo "reader-zero/bounds composite is one-shot" >&2
  exit 3
}

run_m65() {
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}
readback() {
  rb_start=$1; rb_bytes=$2; rb_path=$3
  rb_end=$(printf '%08x' "$((rb_start + rb_bytes))")
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$rb_end=$rb_path"
}
upload_and_verify() {
  uv_path=$1; uv_address=$2; uv_bytes=$3; uv_readback=$4
  run_m65 -H -@ "$uv_path@0x$(printf '%08x' "$uv_address")"
  readback "$uv_address" "$uv_bytes" "$uv_readback"
  cmp "$uv_path" "$uv_readback"
}
live_write() {
  lw_path=$1; lw_address=$2
  run_m65 -@ "$lw_path@0x$(printf '%08x' "$lw_address")"
}
screen_text() {
  st_stem=$1
  run_m65 --screenshot="$OUT/$st_stem.png" > "$OUT/$st_stem.ansi.txt"
  python3 - "$OUT/$st_stem.ansi.txt" "$OUT/$st_stem.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
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
sleep 3
screen_text autorun-probe
if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/autorun-probe.txt" &&
   ! grep -q 'lisp65>' "$OUT/autorun-probe.txt"; then
  run_m65 -t "~M"
fi
sleep "$WAIT"
screen_text boot-screen
python3 - "$OUT/boot-screen.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
if "lisp65>" not in text or "*** vm:" in text:
    raise SystemExit("reader-zero/bounds carrier did not reach clean REPL")
PY

readback 0x0000e691 87 "$OUT/reader-before-live-patch.bin"
cmp "$PATCH_DIR/c2-stream-c2d-read-original.bin" \
    "$OUT/reader-before-live-patch.bin"
for address in e6a3 e6ac e6c2 e6e7; do
  live_write "$PATCH_DIR/patch-$address.bin" "0x$address"
done
readback 0x0000e691 87 "$OUT/reader-after-live-patch.bin"
cmp "$PATCH_DIR/c2-stream-c2d-read-bounds-holds.bin" \
    "$OUT/reader-after-live-patch.bin"

run_m65 -t "$(jq -r '.test.form' "$DEPLOY")"
echo "Composite armed. Press physical RETURN; report hang or output."
