#!/bin/sh
# One-shot Link-64 Slot-39 ACTIVE-return binary discriminator.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
WAIT=${WAIT:-28}
OUT=build/c2.2/hardware-link64-slot39-active-return-hold-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_link64_slot39_active_return_hold.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy-and-arm|capture-hang>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy-and-arm|capture-hang) ;;
  *) echo "usage: $0 <deploy-and-arm|capture-hang>" >&2; exit 2 ;;
esac

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }

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

case "$ACTION" in
deploy-and-arm)
  [ ! -e "$OUT/hardware-run.started" ] || {
    echo "ACTIVE-return deployment is one-shot" >&2
    exit 3
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
  run_m65 --screenshot="$OUT/autorun-probe.png" \
    > "$OUT/autorun-probe.ansi.txt"
  python3 - "$OUT/autorun-probe.ansi.txt" "$OUT/autorun-probe.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
  if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/autorun-probe.txt" &&
     ! grep -q 'lisp65>' "$OUT/autorun-probe.txt"; then
    run_m65 -t "~M"
  fi
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
    raise SystemExit("ACTIVE-return carrier did not reach a clean REPL")
PY
  run_m65 -t "$(jq -r '.test.form' "$DEPLOY")"
  echo "Form armed. Press physical RETURN; report hang or bad bytecode."
  ;;
capture-hang)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "ACTIVE-return identity was not deployed" >&2
    exit 3
  }
  capture_set() {
    cs_index=$1; cs_dir=$OUT/capture-$cs_index
    mkdir "$cs_dir"
    readback 0x0000c17c 32 "$cs_dir/completion-record.bin"
    readback 0x0005c640 64 "$cs_dir/c2j.bin"
    readback 0x0000c1f0 8 "$cs_dir/trace.bin"
    readback 0x00000070 48 "$cs_dir/runtime-zp.bin"
    readback 0x0000ff83 5 "$cs_dir/frame.bin"
    readback 0x0000c356 1509 "$cs_dir/runtime-slot39.bin"
    date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$cs_dir/captured-at.txt"
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
    "format": "lisp65-Link64-slot39-ACTIVE-return-times-v1",
    "interval_seconds": [0, 1, 5],
    "captures": rows,
}, indent=2, sort_keys=True) + "\n")
PY
  run_m65 --screenshot="$OUT/active-return-screen.png" \
    > "$OUT/active-return-screen.ansi.txt"
  python3 - "$OUT/active-return-screen.ansi.txt" \
    "$OUT/active-return-screen.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
  python3 "$PY" evaluate-hang
  echo "ACTIVE-return success witness captured; identity retired."
  ;;
esac
