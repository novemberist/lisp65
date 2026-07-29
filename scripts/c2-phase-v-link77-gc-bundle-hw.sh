#!/bin/sh
# One physical appointment: GC discriminator, independent Link-77 rows,
# physical RUN/STOP, then the nonpromotable post-symname hold.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_LINK77_GC_OUT:-build/post-promotion/link77-random-while/gc-discriminator-bundled-session}
DEPLOY=$OUT/deployment.json
OBS=$OUT/observations.json
PY=tools/host-lisp/c2_phase_v_link77_gc_bundle.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-60}
EXPECT_POLL=${EXPECT_POLL:-240}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-60}
M65=$TOOLS/m65

usage() {
  echo "usage: $0 <start|continue-after-gc|resume|verify>" >&2
  exit 2
}

case "$ACTION" in start|continue-after-gc|resume|verify) ;; *) usage ;; esac

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
  mkdir -p "$(dirname "$path")"
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

boot_phase() {
  phase=$1
  prg=$(jq -r ".phases.$phase.product.path" "$DEPLOY")
  run_m65 -F -H -1 "$prg"
  jq -c ".phases.$phase.preloads[]" "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    tag=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/$phase-readback-$tag.bin"
    cmp "$path" "$OUT/$phase-readback-$tag.bin"
  done
  run_m65 -r -1 "$prg"
  sleep 3
  capture_screen "$phase-autorun"
  if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/$phase-autorun.txt" &&
     ! grep -q 'lisp65>' "$OUT/$phase-autorun.txt"; then
    run_m65 -t '~M'
  fi
  poll=0
  while [ "$poll" -lt "$BOOT_POLL_LIMIT" ]; do
    capture_screen "$phase-boot"
    grep -q 'lisp65>' "$OUT/$phase-boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt "$BOOT_POLL_LIMIT" ] || {
    echo "terminal First Red: no Lisp REPL in phase $phase" >&2
    exit 3
  }
}

row_form() {
  id=$1
  jq -r \
    ".phases.independent_product_rows.rows[] | select(.id == \"$id\") | .form" \
    "$DEPLOY"
}

row_expect() {
  id=$1
  jq -r \
    ".phases.independent_product_rows.rows[] | select(.id == \"$id\") | .expected_result" \
    "$DEPLOY"
}

run_product_row() {
  id=$1
  form=$(row_form "$id")
  expect=$(row_expect "$id")
  status=0
  if OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --expect "$expect" --expect-poll "$EXPECT_POLL" \
        --wait 1 --form "$form"; then
    :
  else
    status=$?
  fi
  if [ "$status" -eq 0 ] &&
     python3 "$PY" record-product --id "$id" \
       --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"; then
    return
  fi
  # A fail-closed frame is still terminal: the recorder rejects it. Otherwise
  # bind the row-local red and continue with independent rows.
  python3 "$PY" record-product-red --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png" \
    --detail "expected $expect was not observed (runner_status=$status)"
}

capture_gc_memory() {
  index=$1
  dir=$OUT/gc-capture-$index
  readback 0x0000003b 85 "$dir/zp.bin"
  readback 0x0000bbf0 134 "$dir/marks.bin"
  readback 0x0000c25d 240 "$dir/hot-heap.bin"
  readback 0x00040000 8192 "$dir/ext-heap.bin"
  readback 0x0000b9ee 2 "$dir/gc-runs.bin"
  readback 0x00003ec2 2 "$dir/live-patch.bin"
}

case "$ACTION" in
  start)
    python3 "$PY" verify
    [ "$(jq -r '.status' "$OBS")" = hardware-not-started ] || {
      echo "Link-77 GC bundle was already started" >&2
      exit 3
    }
    readback 0x0ffd3632 4 "$OUT/device-core-id.bin"

    boot_phase gc_discriminator
    form=$(jq -r '.phases.gc_discriminator.test.form' "$DEPLOY")
    OUT_DIR=$OUT PREFIX=gc-row-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 3
    python3 "$PY" capture-gc-pc
    capture_gc_memory 1
    sleep 1
    capture_gc_memory 2
    sleep 4
    capture_gc_memory 3
    python3 "$PY" evaluate-gc

    boot_phase independent_product_rows
    for id in \
      random-state-width random-rejection-path \
      random-seed-reproducible random-range irq-mask-readback
    do
      run_product_row "$id"
    done

    form=$(row_form while-run-stop)
    OUT_DIR=$OUT PREFIX=row-while-run-stop-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 1
    capture_screen row-while-run-stop-running
    echo "GC, random and IRQ rows are captured; (while t) is running."
    echo "Press physical RUN/STOP once, then run: $0 resume"
    ;;

  continue-after-gc)
    python3 "$PY" verify
    [ "$(jq -r '.status' "$OBS")" \
        = gc-nonreproduction-awaiting-independent-product-rows ] || {
      echo "GC non-reproduction has not been bound" >&2
      exit 3
    }
    boot_phase independent_product_rows
    for id in \
      random-state-width random-rejection-path \
      random-seed-reproducible random-range irq-mask-readback
    do
      run_product_row "$id"
    done

    form=$(row_form while-run-stop)
    OUT_DIR=$OUT PREFIX=row-while-run-stop-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 1
    capture_screen row-while-run-stop-running
    echo "Independent random and IRQ rows are captured; (while t) is running."
    echo "Press physical RUN/STOP once, then run: $0 resume"
    ;;

  resume)
    capture_screen row-while-run-stop
    if python3 "$PY" record-run-stop \
        --screen "$OUT/row-while-run-stop.txt" \
        --image "$OUT/row-while-run-stop.png"; then
      run_product_row post-run-stop-repl
    else
      python3 "$PY" record-product-red --id while-run-stop \
        --screen "$OUT/row-while-run-stop.txt" \
        --image "$OUT/row-while-run-stop.png" \
        --detail "physical RUN/STOP result was not a clean stopped/live-prompt row"
    fi

    boot_phase dirmiss_post_symname
    form=$(jq -r '.phases.dirmiss_post_symname.test.form' "$DEPLOY")
    OUT_DIR=$OUT PREFIX=dirmiss-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 2
    python3 "$PY" capture-dirmiss
    python3 "$PY" finalize
    ;;
esac
