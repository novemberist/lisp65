#!/bin/sh
# One-device-session S1 freight qualification for the SHA-bound Link-67 product.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_S1_OUT:-build/post-promotion/link67-f1-f2/s1-hardware-attempt2}
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_phase_f_s1_link67.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-30}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-35}
M65=$TOOLS/m65

usage() {
  echo "usage: $0 <start|continue|finish>" >&2
  exit 2
}

case "$ACTION" in start|continue|finish) ;; *) usage ;; esac

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

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

capture_domains() {
  prefix=$1
  readback 0x00020000 65536 "$OUT/$prefix-bank2.bin"
  readback 0x00030000 65536 "$OUT/$prefix-bank3.bin"
  readback 0x00050000 65536 "$OUT/$prefix-bank5.bin"
  readback 0x0000e000 8192 "$OUT/$prefix-e000.bin"
}

run_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" \
    config/c2.2-s1-freight-session.json)
  OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen "row-$id"
    if python3 "$PY" observe-row --id "$id" \
        --screen "$OUT/row-$id.txt" > "$OUT/row-$id-observe.log" 2>&1; then
      cat "$OUT/row-$id-observe.log"
      return 0
    fi
    sleep 1
    poll=$((poll + 1))
  done
  cat "$OUT/row-$id-observe.log" >&2
  echo "S1 First Red: row $id did not produce a valid result in 30 seconds" >&2
  exit 3
}

run_pending_pre_rows() {
  position=0
  for id in \
    boot-watch f1-define-fixed f1-nary-cold f1-nary-warm \
    nullary-define-regression nullary-cold-regression \
    nullary-warm-regression f2-bitops-positive \
    f2-bitops-type-negative post-error-repl
  do
    observed=$(jq '.rows | length' "$OUT/observed-rows.json")
    if [ "$position" -ge "$observed" ]; then
      run_row "$id"
    fi
    position=$((position + 1))
  done
}

case "$ACTION" in
  start)
    rows=$(jq '.rows | length' "$OUT/observed-rows.json")
    [ "$rows" -eq 0 ] || {
      echo "S1 hardware session was already started" >&2
      exit 3
    }
    readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
    prg=$(jq -r '.product.path' "$DEPLOY")
    run_m65 -F -H -1 "$prg"
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
    run_m65 -r -1 "$prg"
    sleep 3
    capture_screen autorun-probe
    if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/autorun-probe.txt" &&
       ! grep -q 'lisp65>' "$OUT/autorun-probe.txt"; then
      run_m65 -t '~M'
    fi
    boot_poll=0
    while [ "$boot_poll" -lt "$BOOT_POLL_LIMIT" ]; do
      capture_screen boot
      grep -q 'lisp65>' "$OUT/boot.txt" && break
      sleep 1
      boot_poll=$((boot_poll + 1))
    done
    [ "$boot_poll" -lt "$BOOT_POLL_LIMIT" ] || {
        echo "S1 First Red: no Lisp REPL within boot poll limit" >&2
        exit 3
    }
    run_pending_pre_rows
    capture_domains pre-freezer
    echo "S1 rows 1-10 passed. Enter the physical Freezer and return with F3."
    ;;

  continue)
    rows=$(jq '.rows | length' "$OUT/observed-rows.json")
    [ "$rows" -ge 1 ] && [ "$rows" -lt 10 ] || {
      echo "S1 continue requires one through nine passed rows" >&2
      exit 3
    }
    run_pending_pre_rows
    capture_domains pre-freezer
    echo "S1 rows 1-10 passed. Enter the physical Freezer and return with F3."
    ;;

  finish)
    rows=$(jq '.rows | length' "$OUT/observed-rows.json")
    [ "$rows" -eq 10 ] || [ "$rows" -eq 11 ] || {
      echo "S1 finish requires ten pre-Freezer or eleven Freezer-passed rows" >&2
      exit 3
    }
    if [ "$rows" -eq 10 ]; then
      capture_domains post-freezer
      python3 tools/host-lisp/c2_phase_f_s1_freezer_adjudicate.py
    fi
    run_row post-freezer-repl
    python3 "$PY" finalize
    ;;
esac
