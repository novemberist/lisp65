#!/bin/sh
# Pristine Link 71 plus a late hold at the common pre-rollback edge.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/pre-rollback-hold-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_defstruct_link71_pre_rollback_hold.py
M65=$TOOLS/m65
ZERO_C2J=build/c2.2/destructive-restage-link57/zero-c2j.bin

[ "$#" -eq 1 ] || { echo "usage: $0 <deploy|arm|capture>" >&2; exit 2; }
ACTION=$1
case "$ACTION" in deploy|arm|capture) ;; *) exit 2 ;; esac
python3 "$PY" verify

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}
readback() {
  start=$1; bytes=$2; path=$3; end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

case "$ACTION" in
deploy)
  [ ! -e "$OUT/hardware-run.started" ] || exit 3
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
  run_m65 -H -@ "$ZERO_C2J@0x0005c640"
  run_m65 -r -1 "$PRG"
  poll=0
  while [ "$poll" -lt 45 ]; do
    capture_screen boot
    grep -q 'lisp65>' "$OUT/boot.txt" && break
    sleep 1; poll=$((poll + 1))
  done
  [ "$poll" -lt 45 ] || exit 3
  path=$(jq -r '.late_patch.path' "$DEPLOY")
  address=$(jq -r '.late_patch.address' "$DEPLOY")
  bytes=$(jq -r '.late_patch.bytes' "$DEPLOY")
  run_m65 -H -@ "$path@$address"
  readback "$((address))" "$bytes" "$OUT/late-patch-readback.bin"
  cmp "$path" "$OUT/late-patch-readback.bin"
  echo "Pristine Link 71 ready; pre-rollback hold installed late."
  ;;
arm)
  OUT_DIR=$OUT PREFIX=pre-rollback-arm TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form "$(jq -r '.test.form' "$DEPLOY")"
  sleep 3
  python3 "$PY" capture
  ;;
capture)
  python3 "$PY" capture
  ;;
esac

if [ "$ACTION" = arm ] || [ "$ACTION" = capture ]; then
  i=1
  while [ "$i" -le 3 ]; do
    dir=$OUT/capture-$i; mkdir "$dir"
    readback 0x00000000 160 "$dir/zero-page.bin"
    readback 0x0000bfeb 21 "$dir/rtov-tail.bin"
    readback 0x0000c0c6 304 "$dir/phase-scratch.bin"
    readback 0x0005c640 64 "$dir/c2j.bin"
    [ "$i" -eq 3 ] || sleep 1
    i=$((i + 1))
  done
  for name in zero-page rtov-tail phase-scratch c2j; do
    cmp "$OUT/capture-1/$name.bin" "$OUT/capture-2/$name.bin"
    cmp "$OUT/capture-1/$name.bin" "$OUT/capture-3/$name.bin"
  done
  capture_screen pre-rollback-hold
  echo "Primary append-failure state captured; diagnostic retired."
fi
