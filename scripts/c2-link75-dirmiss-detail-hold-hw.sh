#!/bin/sh
# Deploy and capture the nonpromotable Link-75 pre-symname hold.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-prepare}
OUT=build/post-promotion/link75-bound-compiler-carrier/dirmiss-detail-hold-NONPROMOTABLE
PY=tools/host-lisp/c2_link75_dirmiss_detail_hold_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-40}

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

case "$ACTION" in
  prepare)
    python3 "$PY" prepare
    python3 "$PY" verify
    ;;
  verify)
    python3 "$PY" verify
    ;;
  run)
    python3 "$PY" verify
    [ -x "$M65" ] || {
      echo "missing MEGA65 tool: $M65" >&2
      exit 3
    }
    [ -c "$DEVICE" ] || {
      echo "missing JTAG serial device: $DEVICE" >&2
      exit 3
    }
    prg=$(jq -r '.product.path' "$OUT/deployment.json")
    run_m65 -F -H -1 "$prg"
    jq -c '.preloads[]' "$OUT/deployment.json" |
    while IFS= read -r item; do
      path=$(printf '%s' "$item" | jq -r '.path')
      address=$(printf '%s' "$item" | jq -r '.address')
      bytes=$(printf '%s' "$item" | jq -r '.bytes')
      name=$(basename "$path")
      run_m65 -H -@ "$path@$address"
      readback "$((address))" "$bytes" "$OUT/readback-$name"
      cmp "$path" "$OUT/readback-$name"
    done
    run_m65 -r -1 "$prg"
    poll=0
    while [ "$poll" -lt 45 ]; do
      capture_screen boot
      grep -q 'lisp65>' "$OUT/boot.txt" && break
      sleep 1
      poll=$((poll + 1))
    done
    [ "$poll" -lt 45 ] || {
      echo "Link-75 DIRMISS hold First Red: no Lisp REPL" >&2
      exit 3
    }
    OUT_DIR=$OUT PREFIX=dirmiss-hold-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback \
        --form '(intern-renderer-missing)'
    sleep 1
    python3 "$PY" capture
    ;;
  *)
    echo "usage: $0 [prepare|verify|run]" >&2
    exit 2
    ;;
esac
