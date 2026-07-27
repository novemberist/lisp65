#!/bin/sh
# Read-only postmortem for the final reader-zero/bounds composite.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
OUT=build/c2.2/hardware-link64-reader-zero-bounds-composite-NONPROMOTABLE
M65=$TOOLS/m65

[ -e "$OUT/hardware-run.started" ] || {
  echo "reader-zero/bounds composite was not deployed" >&2
  exit 3
}
[ ! -e "$OUT/capture-1" ] || {
  echo "reader-zero/bounds composite was already captured" >&2
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
capture_set() {
  cs_index=$1; cs_dir=$OUT/capture-$cs_index
  mkdir "$cs_dir"
  readback 0x0000e691 87 "$cs_dir/reader-code.bin"
  readback 0x0000c17c 32 "$cs_dir/completion-record.bin"
  readback 0x0005c640 64 "$cs_dir/c2j.bin"
  readback 0x0000c1f0 8 "$cs_dir/trace.bin"
  readback 0x00000070 48 "$cs_dir/runtime-zp.bin"
  readback 0x0000c356 1509 "$cs_dir/runtime-slot39.bin"
  readback 0x00030000 65536 "$cs_dir/bank3.bin"
  readback 0x0000ff83 5 "$cs_dir/frame.bin"
  date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$cs_dir/captured-at.txt"
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

capture_set 1; sleep 1
capture_set 2; sleep 4
capture_set 3
python3 - "$OUT" <<'PY'
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
rows = []
for index in range(1, 4):
    rows.append({
        "index": index,
        "utc": (out / f"capture-{index}/captured-at.txt").read_text().strip(),
    })
(out / "capture-times.json").write_text(json.dumps({
    "format": "lisp65-Link64-reader-zero-bounds-composite-times-v1",
    "interval_seconds": [0, 1, 5],
    "captures": rows,
}, indent=2, sort_keys=True) + "\n")
PY
screen_text composite-screen
echo "reader-zero/bounds composite First Red captured."
