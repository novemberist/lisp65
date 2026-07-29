#!/bin/sh
# Media-bound repeat of the Link-71 pre-rollback hold.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
OUT=${C2_PRE_ROLLBACK_OUT:-build/post-promotion/link71-defstruct-header-crc-domain/pre-rollback-hold-v2-media-bound-NONPROMOTABLE}
DEPLOY=$OUT/deployment.json
PY=${C2_PRE_ROLLBACK_PY:-tools/host-lisp/c2_defstruct_link71_pre_rollback_hold_v2.py}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
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
  media=$(jq -r '.media.path' "$DEPLOY")
  remote=$(jq -r '.remote_media' "$DEPLOY")
  timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $OUT/uploaded-media-readback.d81" \
    -c "mount $remote" -c exit > "$OUT/media-upload-mount.log"
  cmp "$media" "$OUT/uploaded-media-readback.d81"

  PRG=$(jq -r '.product.path' "$DEPLOY")
  if [ "${C2_PRESERVE_MOUNT_AFTER_FTP_RESET:-0}" -eq 1 ]; then
    run_m65 -H -1 "$PRG"
  else
    run_m65 -F -H -1 "$PRG"
  fi
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
  echo "Media-bound Link 71 ready; pre-rollback hold installed late."
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
  python3 - "$OUT/capture-1/phase-scratch.bin" <<'PY'
from pathlib import Path
import sys
d = Path(sys.argv[1]).read_bytes()
length = int.from_bytes(d[50:52], "little")
if length != 1925:
    raise SystemExit(f"FIRST RED: mounted-media witness length={length}, expected=1925")
print("Mounted-media witness PASS: c2_append_state.length=1925")
PY
  echo "Primary append-failure state captured; diagnostic retired."
fi
