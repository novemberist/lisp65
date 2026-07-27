#!/bin/sh
# One-shot Link-64 Slot-39 Bank-5 reader-return discriminator.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
WAIT=${WAIT:-28}
OUT=build/c2.2/hardware-link64-slot39-reader-return-hold-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_link64_slot39_reader_return_hold.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy-and-arm|capture-hang|capture-first-red>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy-and-arm|capture-hang|capture-first-red) ;;
  *) echo "usage: $0 <deploy-and-arm|capture-hang|capture-first-red>" >&2
     exit 2 ;;
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

capture_fixed() {
  cf_dir=$1
  readback 0x0000c17c 32 "$cf_dir/completion-record.bin"
  readback 0x0005c640 64 "$cf_dir/c2j.bin"
  readback 0x0000c1f0 8 "$cf_dir/trace.bin"
  readback 0x00000070 48 "$cf_dir/runtime-zp.bin"
  readback 0x0000ff83 5 "$cf_dir/frame.bin"
  readback 0x0000c356 1509 "$cf_dir/runtime-slot39.bin"
}

write_timing() {
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
    "format": "lisp65-Link64-slot39-reader-return-times-v1",
    "interval_seconds": [0, 1, 5],
    "captures": rows,
}, indent=2, sort_keys=True) + "\n")
PY
}

case "$ACTION" in
deploy-and-arm)
  [ ! -e "$OUT/hardware-run.started" ] || {
    echo "reader-return deployment is one-shot" >&2
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
    raise SystemExit("reader-return carrier did not reach a clean REPL")
PY
  run_m65 -t "$(jq -r '.test.form' "$DEPLOY")"
  echo "Form armed. Press physical RETURN; report hang or bad bytecode."
  ;;
capture-hang)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "reader-return identity was not deployed" >&2
    exit 3
  }
  capture_set() {
    cs_index=$1; cs_dir=$OUT/capture-$cs_index
    mkdir "$cs_dir"
    readback 0x00000002 30 "$cs_dir/call-zp.bin"
    observed=$(
      python3 - "$cs_dir/call-zp.bin" "$cs_dir/pointer.json" <<'PY'
from pathlib import Path
import json
import sys
zp = Path(sys.argv[1]).read_bytes()
if len(zp) != 30:
    raise SystemExit("call-ZP capture width drift")
stack = int.from_bytes(zp[0:2], "little")
observed = int.from_bytes(zp[24:26], "little")
if observed != (stack + 10) & 0xffff:
    raise SystemExit(
        f"memory-backed pointer relation failed: {stack:04x}/{observed:04x}")
Path(sys.argv[2]).write_text(json.dumps({
    "software_stack_base": f"0x{stack:04x}",
    "observed_pointer": f"0x{observed:04x}",
    "relation": "observed = software_stack_base + 10",
    "relation_proven": True,
}, indent=2, sort_keys=True) + "\n")
print(observed)
PY
    )
    readback "$observed" 64 "$cs_dir/observed.bin"
    capture_fixed "$cs_dir"
    date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$cs_dir/captured-at.txt"
  }
  capture_set 1; sleep 1
  capture_set 2; sleep 4
  capture_set 3
  write_timing
  screen_text reader-return-screen
  python3 "$PY" evaluate-hang
  echo "reader-return success witness captured; identity retired."
  ;;
capture-first-red)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "reader-return identity was not deployed" >&2
    exit 3
  }
  capture_set() {
    cs_index=$1; cs_dir=$OUT/capture-$cs_index
    mkdir "$cs_dir"
    capture_fixed "$cs_dir"
    date -u +%Y-%m-%dT%H:%M:%S.%NZ > "$cs_dir/captured-at.txt"
  }
  capture_set 1; sleep 1
  capture_set 2; sleep 4
  capture_set 3
  write_timing
  screen_text reader-return-screen
  python3 "$PY" evaluate-bad-bytecode
  echo "reader-return zero witness captured; identity retired."
  ;;
esac
