#!/bin/sh
# One physical appointment: post-symname, DMA attribution, canonical retry.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-verify}
BASE=build/post-promotion/link75-bound-compiler-carrier/bundled-completion-session
OUT=$BASE/hardware-symbol-read-session-v2
STAGE0=$BASE/post-symname-hold-NONPROMOTABLE/deployment.json
STAGE1=$BASE/symbol-read-completion-probe-v2-NONPROMOTABLE/deployment.json
PRODUCT=$BASE/library-media-successor/product-phase-deployment.json
PY=tools/host-lisp/c2_link75_symbol_read_completion_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}

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
  directory=$1
  prefix=$2
  run_m65 --screenshot="$directory/$prefix.png" \
    > "$directory/$prefix.ansi.txt"
  python3 - "$directory/$prefix.ansi.txt" "$directory/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

deploy() {
  deployment=$1
  deploy_output=$2
  mkdir -p "$deploy_output"
  prg=$(jq -r '.product.path' "$deployment")
  run_m65 -F -H -1 "$prg"
  jq -c '.preloads[]' "$deployment" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    name=$(basename "$path")
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$deploy_output/readback-$name"
    cmp "$path" "$deploy_output/readback-$name"
  done
  reset_rows=$(jq '[.preloads[] |
    select(.role == "c2d-v6-complete-reset-domain")] | length' "$deployment")
  if [ "$reset_rows" -eq 1 ]; then
    readback 0x0005c640 64 "$deploy_output/readback-zero-c2j.bin"
    cmp build/c2.2/destructive-restage-link57/zero-c2j.bin \
      "$deploy_output/readback-zero-c2j.bin"
  fi
  run_m65 -r -1 "$prg"
  poll=0
  while [ "$poll" -lt 60 ]; do
    capture_screen "$deploy_output" boot
    grep -q 'lisp65>' "$deploy_output/boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 60 ]
}

upload_product_media() {
  log=$1
  prg=$(jq -r '.product.path' "$PRODUCT")
  media=$(jq -r '.media.path' "$PRODUCT")
  remote=$(jq -r '.remote_media' "$PRODUCT")

  # mega65_ftp installs a fast-access helper.  Never ask it to take over a
  # live Lisp65 REPL or an SEI diagnostic hold: first establish the same
  # stopped C64/PRG context that recovered the original upload First Red.
  run_m65 -F -H -1 "$prg"
  rm -f "$OUT/uploaded-media-readback.d81"
  timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $OUT/uploaded-media-readback.d81" \
    -c exit > "$log"
  cmp "$media" "$OUT/uploaded-media-readback.d81"
}

trigger_hold() {
  prefix=$1
  form=$2
  OUT_DIR=$OUT PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
}

run_retry_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$PRODUCT")
  expect=$(jq -r ".rows[] | select(.id == \"$id\") | .expect" "$PRODUCT")
  quiet=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .quiet_wait_seconds // 0" \
    "$PRODUCT")
  if [ "$quiet" -gt 0 ]; then
    OUT_DIR=$OUT PREFIX="retry-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --expect-poll "$quiet" --wait 1 --form "$form"
  else
    OUT_DIR=$OUT PREFIX="retry-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --expect-poll 60 --wait 1 --form "$form"
  fi
  python3 "$PY" record-retry \
    --id "$id" --screen "$OUT/retry-$id.txt"
}

if [ "$ACTION" = verify ]; then
  python3 tools/host-lisp/c2_link75_library_media_successor.py verify
  python3 "$PY" verify
  exit
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

case "$ACTION" in
  start)
    python3 "$PY" initialize

    deploy "$STAGE0" "$OUT/post-symname-deployment"
    trigger_hold post-symname-input '(intern-renderer-missing)'
    sleep 1
    python3 "$PY" capture-post-symname

    deploy "$STAGE1" "$OUT/DMA-deployment"
    readback 0x00000089 1 "$OUT/dma-phase-owner-before-safe-trigger.bin"
    readback 0x00050000 65536 "$OUT/dma-bank5-before-safe-trigger.bin"
    python3 "$PY" precheck-DMA
    trigger_hold DMA-input '(intern)'
    sleep 10
    python3 "$PY" capture-DMA
    readback 0x00050000 65536 "$OUT/dma-bank5-after-safe-trigger.bin"
    python3 "$PY" finalize-DMA

    upload_product_media "$OUT/media-upload.log"
    deploy "$PRODUCT" "$OUT/canonical-deployment"
    python3 "$PY" mark-retry-ready
    echo "Diagnostics classified. Mount L75CARR.D81 in Freezer, return with F3."
    echo "Then run: $0 retry"
    ;;
  resume-DMA)
    deploy "$STAGE1" "$OUT/DMA-deployment-clear"
    readback 0x00000089 1 "$OUT/dma-phase-owner-before-safe-trigger.bin"
    readback 0x00050000 65536 "$OUT/dma-bank5-before-safe-trigger.bin"
    python3 "$PY" precheck-DMA
    trigger_hold DMA-input '(intern)'
    sleep 10
    python3 "$PY" capture-DMA
    readback 0x00050000 65536 "$OUT/dma-bank5-after-safe-trigger.bin"
    python3 "$PY" finalize-DMA

    upload_product_media "$OUT/media-upload.log"
    deploy "$PRODUCT" "$OUT/canonical-deployment"
    python3 "$PY" mark-retry-ready
    echo "Diagnostics classified. Mount L75CARR.D81 in Freezer, return with F3."
    echo "Then run: $0 retry"
    ;;
  canonical)
    upload_product_media "$OUT/media-upload.log"
    deploy "$PRODUCT" "$OUT/canonical-deployment"
    python3 "$PY" mark-retry-ready
    echo "Mount L75CARR.D81 in Freezer, return with F3."
    echo "Then run: $0 retry"
    ;;
  canonical-after-timeout)
    upload_product_media "$OUT/media-upload-retry.log"
    deploy "$PRODUCT" "$OUT/canonical-deployment"
    python3 "$PY" mark-retry-ready
    echo "Mount L75CARR.D81 in Freezer, return with F3."
    echo "Then run: $0 retry"
    ;;
  retry)
    for id in require-first require-repeat define-point construct-point \
              read-point-x read-point-y point-predicate functional-update \
              canonical-place-mutation require-repeat-after-use
    do
      case "$id" in
        require-repeat)
          readback 0x00050000 65536 \
            "$OUT/first-repeat-before-bank5.bin"
          ;;
        require-repeat-after-use)
          readback 0x00050000 65536 \
            "$OUT/post-use-repeat-before-bank5.bin"
          ;;
      esac
      run_retry_row "$id"
      case "$id" in
        require-repeat)
          readback 0x00050000 65536 \
            "$OUT/first-repeat-after-bank5.bin"
          ;;
        require-repeat-after-use)
          readback 0x00050000 65536 \
            "$OUT/post-use-repeat-after-bank5.bin"
          ;;
      esac
    done
    python3 "$PY" finalize-retry
    ;;
  *)
    echo "usage: $0 [verify|start|resume-DMA|canonical|canonical-after-timeout|retry]" >&2
    exit 2
    ;;
esac
