#!/bin/sh
# One-shot nonpromotable failure-site hold for Link-71 Session slot 39.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
WAIT=${WAIT:-32}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/slot39-failure-hold-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_defstruct_link71_slot39_failure_hold.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy|arm|capture>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy|arm|capture) ;;
  *) echo "usage: $0 <deploy|arm|capture>" >&2; exit 2 ;;
esac

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$((rb_start + rb_bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$(printf '%08x' "$rb_end")=$rb_path"
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

case "$ACTION" in
deploy)
  [ ! -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 failure-hold deployment is one-shot" >&2
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
    base=$(basename "$path")
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/deploy-readback-$base"
    cmp "$path" "$OUT/deploy-readback-$base"
  done
  run_m65 -r -1 "$PRG"
  sleep "$WAIT"
  capture_screen boot
  grep -q 'lisp65>' "$OUT/boot.txt" &&
    ! grep -q '\\*\\*\\* vm:' "$OUT/boot.txt" || {
      echo "Link-71 failure hold did not reach a clean REPL" >&2
      exit 3
    }
  echo "Diagnostic ready; mount L70DEF.D81 in Freezer and return with F3."
  ;;
arm)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 failure-hold identity was not deployed" >&2
    exit 3
  }
  OUT_DIR=$OUT PREFIX=failure-hold-arm TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form "$(jq -r '.test.form' "$DEPLOY")"
  sleep 2
  capture_screen failure-hold-screen
  grep -q '(%disk-load-lib 39 1)' "$OUT/failure-hold-screen.txt" &&
    ! grep -q '\\*\\*\\* vm:' "$OUT/failure-hold-screen.txt" || {
      echo "Link-71 diagnostic did not hold before error rendering" >&2
      exit 3
    }
  echo "Failure hold armed and reached; capturing witnesses."
  ;;
capture)
  [ -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 failure-hold identity was not deployed" >&2
    exit 3
  }
  python3 "$PY" capture-pc
  capture_set() {
    cs_index=$1
    cs_dir=$OUT/capture-$cs_index
    mkdir "$cs_dir"
    readback 0x0000c17c 32 "$cs_dir/completion-record.bin"
    readback 0x0005c640 64 "$cs_dir/c2j.bin"
    readback 0x0000c0c6 304 "$cs_dir/phase-scratch.bin"
    readback 0x0000c1ee 8 "$cs_dir/trace.bin"
    readback 0x0000c356 1419 "$cs_dir/runtime-slot39.bin"
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
    rows.append({
        "index": index,
        "utc": (out / f"capture-{index}/captured-at.txt").read_text().strip(),
    })
(out / "capture-times.json").write_text(json.dumps({
    "format": "lisp65-Link71-slot39-failure-hold-times-v1",
    "interval_seconds": [0, 1, 5],
    "captures": rows,
}, indent=2, sort_keys=True) + "\n")
PY
  capture_screen failure-hold-screen
  python3 "$PY" evaluate
  echo "Link-71 failure-site witnesses captured; diagnostic retired."
  ;;
esac
