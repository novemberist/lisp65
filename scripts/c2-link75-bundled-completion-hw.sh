#!/bin/sh
# Product-first Link-75 completion appointment; diagnostics run only afterward.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-start}
BASE=build/post-promotion/link75-bound-compiler-carrier/bundled-completion-session
OUT=$BASE/hardware
DEPLOY=$BASE/product-phase-deployment.json
DIAG_DEPLOY=$BASE/post-symname-hold-NONPROMOTABLE/deployment.json
PY=tools/host-lisp/c2_link75_bundled_completion_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
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

run_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$DEPLOY")
  expect=$(jq -r ".rows[] | select(.id == \"$id\") | .expect" "$DEPLOY")
  quiet=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .quiet_wait_seconds // 0" \
    "$DEPLOY")
  if [ "$quiet" -gt 0 ]; then
    OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --expect-poll "$quiet" --wait 1 --form "$form"
  else
    OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --expect "$expect" \
        --expect-poll 30 --wait 1 --form "$form"
  fi
  python3 "$PY" record --id "$id" --screen "$OUT/row-$id.txt"
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
  run_m65 -r -1 "$prg"
  poll=0
  while [ "$poll" -lt 45 ]; do
    capture_screen "$deploy_output" boot
    grep -q 'lisp65>' "$deploy_output/boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 45 ]
}

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

case "$ACTION" in
  start)
    python3 "$PY" initialize
    media=$(jq -r '.media.path' "$DEPLOY")
    remote=$(jq -r '.remote_media' "$DEPLOY")
    timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
      -c "put $media $remote" \
      -c "get $remote $OUT/uploaded-media-readback.d81" \
      -c exit > "$OUT/media-upload.log"
    cmp "$media" "$OUT/uploaded-media-readback.d81"
    readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
    deploy "$DEPLOY" "$OUT"
    run_row boot-watch
    run_row intern-positive
    echo "Mount L75CARR.D81 in Freezer, return with F3, then run: $0 continue"
    ;;
  continue)
    for id in require-first require-repeat define-point construct-point \
              read-point-x read-point-y point-predicate functional-update \
              canonical-place-mutation require-repeat-after-use
    do
      case "$id" in
        require-repeat)
          readback 0x00050000 65536 "$OUT/first-repeat-before-bank5.bin"
          ;;
        require-repeat-after-use)
          readback 0x00050000 65536 "$OUT/post-use-repeat-before-bank5.bin"
          ;;
      esac
      run_row "$id"
      case "$id" in
        require-repeat)
          readback 0x00050000 65536 "$OUT/first-repeat-after-bank5.bin"
          ;;
        require-repeat-after-use)
          readback 0x00050000 65536 "$OUT/post-use-repeat-after-bank5.bin"
          ;;
      esac
    done
    python3 "$PY" finalize-product
    echo "Product phase passed; run: $0 diagnostic"
    ;;
  diagnostic)
    DIAG_OUT=$OUT/post-symname-deployment
    deploy "$DIAG_DEPLOY" "$DIAG_OUT"
    OUT_DIR=$OUT PREFIX=post-symname-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback \
        --form '(intern-renderer-missing)'
    sleep 1
    python3 "$PY" capture-diagnostic
    ;;
  *)
    echo "usage: $0 [start|continue|diagnostic]" >&2
    exit 2
    ;;
esac
