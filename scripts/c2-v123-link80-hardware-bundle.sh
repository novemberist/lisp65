#!/bin/sh
# One physical session: Link-80 features first, then GC and DIRMISS diagnostics.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_V123_LINK80_HW_OUT:-build/post-promotion/v1.2.3/link80-bundled-session}
DEPLOY=$OUT/deployment.json
OBS=$OUT/observations.json
CONFIG=config/c2.2-v1.2.3-link80-bundled-hardware-session.json
PY=tools/host-lisp/c2_v123_link80_hardware_bundle.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-60}
EXPECT_POLL=${EXPECT_POLL:-120}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-75}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp

usage() {
  echo "usage: $0 <start|resume|dry-run|verify>" >&2
  exit 2
}

case "$ACTION" in start|resume|dry-run|verify) ;; *) usage ;; esac

if [ "$ACTION" = verify ]; then
  python3 "$PY" verify
  exit
fi

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" verify
  jq -r '.product_rows[].form,
    .gc_diagnostic.setup.form,
    .gc_diagnostic.workload.form,
    .dirmiss_diagnostic.form' "$CONFIG" |
  while IFS= read -r form; do
    OUT_DIR="$OUT/dry-run" PREFIX=session-form TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --form "$form"
  done
  echo "c2-v123-link80-hardware-bundle: DRY-RUN PASS"
  exit
fi

[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}

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

fail_if_terminal_frame() {
  image=$1
  if ! python3 - "$image" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError:
    raise SystemExit(1)
PY
  then
    echo "terminal First Red: red fail-closed frame" >&2
    exit 7
  fi
}

boot_phase() {
  phase=$1
  preserve_media=${2:-0}
  prg=$(jq -r ".phases.$phase.product.path" "$DEPLOY")
  if [ "$preserve_media" -eq 1 ]; then
    run_m65 -H -1 "$prg"
  else
    run_m65 -F -H -1 "$prg"
  fi
  jq -c ".phases.$phase.preloads[]" "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/$phase-readback-$role.bin"
    cmp "$path" "$OUT/$phase-readback-$role.bin"
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
    fail_if_terminal_frame "$OUT/$phase-boot.png"
    grep -q 'lisp65>' "$OUT/$phase-boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt "$BOOT_POLL_LIMIT" ] || {
    echo "terminal First Red: no Lisp REPL in phase $phase" >&2
    exit 3
  }
}

row_field() {
  id=$1
  field=$2
  jq -r \
    ".product_rows[] | select(.id == \"$id\") | .$field" \
    "$CONFIG"
}

dependencies_green() {
  id=$1
  dependencies=$(jq -r \
    ".product_rows[] | select(.id == \"$id\") | .dependencies[]" \
    "$CONFIG")
  for dependency in $dependencies; do
    status=$(jq -r \
      ".product_rows[] | select(.id == \"$dependency\") | .status" \
      "$OBS")
    case "$status" in
      passed|passed-measured|measured-informational) ;;
      *) return 1 ;;
    esac
  done
  return 0
}

record_skip_if_needed() {
  id=$1
  if dependencies_green "$id"; then
    return 1
  fi
  python3 "$PY" record-skip --id "$id" \
    --detail "one or more declared dependencies did not pass"
  return 0
}

run_exact() {
  id=$1
  if record_skip_if_needed "$id"; then return; fi
  form=$(row_field "$id" form)
  expect=$(row_field "$id" expected_result)
  status=0
  if OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --expect "$expect" --expect-poll "$EXPECT_POLL" \
        --wait 1 --form "$form"; then
    :
  else
    status=$?
  fi
  if [ "$status" -eq 0 ]; then
    python3 "$PY" record-exact --id "$id" \
      --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"
    return
  fi
  fail_if_terminal_frame "$OUT/row-$id.png"
  python3 "$PY" record-red --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png" \
    --detail "expected $expect was not observed (runner_status=$status)"
}

run_custom() {
  id=$1
  action=$2
  wait=$3
  if record_skip_if_needed "$id"; then return; fi
  form=$(row_field "$id" form)
  status=0
  if OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --wait "$wait" --form "$form"; then
    :
  else
    status=$?
  fi
  if [ "$status" -eq 0 ] &&
     python3 "$PY" "$action" --id "$id" \
       --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"; then
    return
  fi
  fail_if_terminal_frame "$OUT/row-$id.png"
  python3 "$PY" record-red --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png" \
    --detail "custom result was absent or malformed (runner_status=$status)"
}

capture_gc_memory() {
  index=$1
  dir=$OUT/gc-capture-$index
  start=$(jq '.capture.gc.zp_start' "$DEPLOY")
  bytes=$(jq '.capture.gc.zp_bytes' "$DEPLOY")
  readback "$start" "$bytes" "$dir/zp.bin"
  start=$(jq '.capture.gc.marks_address' "$DEPLOY")
  bytes=$(jq '.capture.gc.marks_bytes' "$DEPLOY")
  readback "$start" "$bytes" "$dir/marks.bin"
  start=$(jq '.capture.gc.hot_heap_address' "$DEPLOY")
  bytes=$(jq '.capture.gc.hot_heap_bytes' "$DEPLOY")
  readback "$start" "$bytes" "$dir/hot-heap.bin"
  start=$(jq '.capture.gc.ext_heap_address' "$DEPLOY")
  bytes=$(jq '.capture.gc.ext_heap_bytes' "$DEPLOY")
  readback "$start" "$bytes" "$dir/ext-heap.bin"
  start=$(jq '.capture.gc.gc_runs_address' "$DEPLOY")
  readback "$start" 2 "$dir/gc-runs.bin"
  start=$(jq '.capture.gc.hold_address' "$DEPLOY")
  readback "$start" 2 "$dir/live-patch.bin"
}

run_gc() {
  boot_phase gc_discriminator 0
  form=$(jq -r '.gc_diagnostic.setup.form' "$CONFIG")
  expect=$(jq -r '.gc_diagnostic.setup.expected_result' "$CONFIG")
  if ! OUT_DIR=$OUT PREFIX=gc-helper TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --expect "$expect" --expect-poll "$EXPECT_POLL" \
        --wait 1 --form "$form"; then
    fail_if_terminal_frame "$OUT/gc-helper.png"
    python3 "$PY" record-gc-invalid \
      --screen "$OUT/gc-helper.txt" --image "$OUT/gc-helper.png" \
      --detail "GC helper definition did not produce the exact result"
    return
  fi

  form=$(jq -r '.gc_diagnostic.workload.form' "$CONFIG")
  status=0
  if OUT_DIR=$OUT PREFIX=gc-workload TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --expect 600 --expect-poll 20 --wait 1 --form "$form"; then
    :
  else
    status=$?
  fi
  if [ "$status" -eq 0 ]; then
    python3 "$PY" record-gc-nonreproduction \
      --screen "$OUT/gc-workload.txt" --image "$OUT/gc-workload.png"
    return
  fi
  fail_if_terminal_frame "$OUT/gc-workload.png"
  if ! python3 "$PY" capture-gc-pc; then
    python3 "$PY" record-gc-invalid \
      --screen "$OUT/gc-workload.txt" --image "$OUT/gc-workload.png" \
      --detail "workload did not finish, but PC was not the alloc_oom hold"
    return
  fi
  capture_gc_memory 1
  sleep 1
  capture_gc_memory 2
  sleep 4
  capture_gc_memory 3
  python3 "$PY" evaluate-gc
}

run_dirmiss() {
  boot_phase dirmiss_post_symname 0
  form=$(jq -r '.dirmiss_diagnostic.form' "$CONFIG")
  OUT_DIR=$OUT PREFIX=dirmiss-input TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  sleep 2
  capture_screen dirmiss-held
  fail_if_terminal_frame "$OUT/dirmiss-held.png"
  if ! python3 "$PY" capture-dirmiss; then
    python3 "$PY" record-dirmiss-invalid \
      --screen "$OUT/dirmiss-held.txt" --image "$OUT/dirmiss-held.png" \
      --detail "post-symname hold or stable scratch capture was not observed"
  fi
}

case "$ACTION" in
  start)
    python3 "$PY" verify
    [ "$(jq -r '.status' "$OBS")" = hardware-not-started ] || {
      echo "Link-80 bundled session was already started" >&2
      exit 3
    }
    readback 0x0ffd3632 4 "$OUT/device-core-id.bin"

    media=$(jq -r '.phases.product.media.path' "$DEPLOY")
    remote=$(jq -r '.phases.product.remote_media' "$DEPLOY")
    timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
      -c "put $media $remote" \
      -c "get $remote $OUT/uploaded-media-readback.d81" \
      -c "mount $remote" \
      -c exit > "$OUT/media-upload.log"
    cmp "$media" "$OUT/uploaded-media-readback.d81"
    boot_phase product 1

    run_exact boot-repl
    run_exact while-smoke
    run_exact random-state-width
    run_exact random-rejection-path
    run_exact random-helper
    run_exact random-seed-store
    run_exact random-seed-reproducible
    run_exact random-range
    run_exact frame-helper
    run_exact require-frame-helper
    run_custom require-first record-frame 30
    run_custom require-repeat record-frame 3
    run_exact irq-mask-low
    run_exact irq-mask-high
    run_exact math-helper
    run_exact math-clear
    run_custom math-product-low record-informational 2
    run_custom math-product-high record-informational 2
    run_exact math-clear-after

    form=$(row_field while-run-stop form)
    OUT_DIR=$OUT PREFIX=row-while-run-stop-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep 1
    capture_screen row-while-run-stop-running
    fail_if_terminal_frame "$OUT/row-while-run-stop-running.png"
    echo "Feature rows are captured; (while t) is running."
    echo "Press physical RUN/STOP once, then run: $0 resume"
    ;;

  resume)
    python3 "$PY" verify
    capture_screen row-while-run-stop
    fail_if_terminal_frame "$OUT/row-while-run-stop.png"
    if python3 "$PY" record-run-stop \
        --screen "$OUT/row-while-run-stop.txt" \
        --image "$OUT/row-while-run-stop.png"; then
      run_exact post-run-stop-repl
    else
      python3 "$PY" record-red --id while-run-stop \
        --screen "$OUT/row-while-run-stop.txt" \
        --image "$OUT/row-while-run-stop.png" \
        --detail "physical RUN/STOP did not return stopped/live prompt"
      python3 "$PY" record-skip --id post-run-stop-repl \
        --detail "RUN/STOP dependency did not pass"
    fi

    run_gc
    run_dirmiss
    python3 "$PY" finalize
    ;;
esac
