#!/bin/sh
# One Link-77 device session: while, random, IRQ ownership and DIRMISS.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_LINK77_HW_OUT:-build/post-promotion/link77-random-while/phase-v-bundled-hardware}
DEPLOY=$OUT/deployment.json
OBS=$OUT/observed-rows.json
CONFIG=config/c2.2-link77-phase-v-bundled-hardware-session.json
PY=tools/host-lisp/c2_phase_v_link77_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-60}
EXPECT_POLL=${EXPECT_POLL:-240}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-60}
M65=$TOOLS/m65

usage() {
  echo "usage: $0 <start|resume|finish|verify>" >&2
  exit 2
}

case "$ACTION" in start|resume|finish|verify) ;; *) usage ;; esac

if [ "$ACTION" = verify ]; then
  python3 "$PY" verify
  exit
fi

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

run_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$CONFIG")
  expect=$(jq -r ".rows[] | select(.id == \"$id\") | .expected_result" \
    "$CONFIG")
  OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input \
      --expect "$expect" --expect-poll "$EXPECT_POLL" \
      --wait 1 --form "$form"
  python3 "$PY" record-row --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"
}

run_dirmiss() {
  id=dirmiss-full-name
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$CONFIG")
  OUT_DIR=$OUT PREFIX="row-$id-input" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen "row-$id"
    if grep -Eq '^[[:space:]]*\\*\\*\\* undefined function:[[:space:]]*intern-renderer-missing[[:space:]]*$' \
        "$OUT/row-$id.txt" &&
       grep -Eq '^[[:space:]]*lisp65>[[:space:]]*$' "$OUT/row-$id.txt"; then
      break
    fi
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 30 ] || {
    echo "Link-77 First Red: full DIRMISS row absent after 30 seconds" >&2
    exit 3
  }
  python3 "$PY" record-row --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"
}

case "$ACTION" in
  start)
    python3 "$PY" verify
    rows=$(jq '.rows | length' "$OBS")
    [ "$rows" -eq 0 ] || {
      echo "Link-77 hardware session was already started" >&2
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
      echo "Link-77 First Red: no Lisp REPL within boot poll limit" >&2
      exit 3
    }

    for id in \
      boot-repl while-zero while-multiple while-nonboolean-truth \
      while-long-constant-stack while-allocation-gc
    do
      run_row "$id"
    done

    form=$(jq -r '.rows[] | select(.id == "while-run-stop") | .form' \
      "$CONFIG")
    OUT_DIR=$OUT PREFIX=row-while-run-stop-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 1
    capture_screen row-while-run-stop-running
    echo "Link-77 rows 1-6 passed; infinite while is running."
    echo "Press physical RUN/STOP once, then run: $0 finish"
    ;;

  resume)
    rows=$(jq '.rows | length' "$OBS")
    [ "$rows" -ge 1 ] && [ "$rows" -le 5 ] || {
      echo "Link-77 resume requires one through five pre-GC rows" >&2
      exit 3
    }
    capture_screen resume-probe
    grep -Eq '^[[:space:]]*lisp65>[[:space:]]*$' "$OUT/resume-probe.txt" || {
      echo "Link-77 First Red: resumed device is not at a live Lisp prompt" >&2
      exit 3
    }
    python3 - "$OUT/resume-probe.png" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
PY

    case "$rows" in
      1) remaining="while-zero while-multiple while-nonboolean-truth while-long-constant-stack while-allocation-gc" ;;
      2) remaining="while-multiple while-nonboolean-truth while-long-constant-stack while-allocation-gc" ;;
      3) remaining="while-nonboolean-truth while-long-constant-stack while-allocation-gc" ;;
      4) remaining="while-long-constant-stack while-allocation-gc" ;;
      5) remaining="while-allocation-gc" ;;
    esac
    for id in $remaining
    do
      run_row "$id"
    done

    form=$(jq -r '.rows[] | select(.id == "while-run-stop") | .form' \
      "$CONFIG")
    OUT_DIR=$OUT PREFIX=row-while-run-stop-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 1
    capture_screen row-while-run-stop-running
    echo "Link-77 rows 1-6 passed; infinite while is running."
    echo "Press physical RUN/STOP once, then run: $0 finish"
    ;;

  finish)
    rows=$(jq '.rows | length' "$OBS")
    [ "$rows" -eq 6 ] || {
      echo "Link-77 finish requires six passed pre-RUN/STOP rows" >&2
      exit 3
    }
    capture_screen row-while-run-stop
    python3 "$PY" record-run-stop \
      --screen "$OUT/row-while-run-stop.txt" \
      --image "$OUT/row-while-run-stop.png"

    run_row post-run-stop-repl
    run_row random-state-width
    run_row random-rejection-path
    run_row random-seed-reproducible
    run_row random-range
    run_row irq-mask-readback
    run_dirmiss
    run_row post-dirmiss-repl
    python3 "$PY" finalize
    ;;
esac
