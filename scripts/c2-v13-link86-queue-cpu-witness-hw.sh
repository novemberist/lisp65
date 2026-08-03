#!/bin/sh
# One-contact Link-86 CPU-side live-queue discriminator.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-ship-builder-v1-link86-queue-cpu-witness.json
PREP=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.3-link86-queue-cpu-witness-preparation-receipt.json
OUT=build/ship-builder/v13/link86-queue-cpu-witness/device
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|start|capture) ;;
  *) echo "usage: $0 <dry-run|start|capture>" >&2; exit 2 ;;
esac

image=$(jq -r '.diagnostic.image.path' "$PREP")
image_sha=$(jq -r '.diagnostic.image.sha256' "$PREP")
remote=$(jq -r '.remote' "$CONFIG")
waiting=$(jq -r '.waiting_value' "$CONFIG")
key=$(jq -r '.physical_key' "$CONFIG")
state=$(($(jq -r '.diagnostic.runtime_state.address' "$PREP")))
samples=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_samples") | .address' "$PREP")))
last_state=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_last_state") | .address' "$PREP")))
last_code=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_last_code") | .address' "$PREP")))
latched=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_latched") | .address' "$PREP")))
latched_state=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_latched_state") | .address' "$PREP")))
latched_code=$(($(jq -r '.diagnostic.witnesses[] | select(.name=="lisp65_ship_queue_diag_latched_code") | .address' "$PREP")))

[ "$(sha256sum "$image" | awk '{print $1}')" = "$image_sha" ] || {
  echo "diagnostic image drift" >&2; exit 3;
}
[ "$last_state" -eq $((samples + 1)) ] \
  && [ "$last_code" -eq $((samples + 2)) ] \
  && [ "$latched" -eq $((samples + 3)) ] \
  && [ "$latched_state" -eq $((samples + 4)) ] \
  && [ "$latched_code" -eq $((samples + 5)) ] || {
    echo "CPU witness RAM layout is not contiguous" >&2; exit 3;
  }
[ "$samples" -lt $((0xd000)) ] && [ "$samples" -ge $((0x0200)) ] || {
  echo "CPU witness is not ordinary RAM" >&2; exit 3;
}

if [ "$ACTION" = dry-run ]; then
  [ "$(jq -r '.limits.promotable' "$CONFIG")" = false ]
  [ "$(jq -r '.limits.product_candidate_bytes_changed' "$CONFIG")" -eq 0 ]
  [ "$(jq -r '.limits.physical_key_contacts' "$CONFIG")" -eq 1 ]
  [ "$(jq -r '.limits.virtual_keys' "$CONFIG")" -eq 0 ]
  echo "DRY-RUN PASS: cold reset -> exact diagnostic D81 -> state 2 -> sampler live"
  printf 'WITNESS RAM: state=$%04X block=$%04X..$%04X\n' \
    "$state" "$samples" "$latched_code"
  echo "HUMAN: type exactly '$key'; no RETURN, virtual key or post-key screenshot"
  echo "CAPTURE: one six-byte ordinary-RAM read; pre-registered queue-present/empty split"
  exit 0
fi

mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 4;
}
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
byte_at() { od -An -tu1 -j "$2" -N 1 "$1" | tr -d ' '; }
wait_state() {
  elapsed=0
  while [ "$elapsed" -lt 90 ]; do
    readback "$state" 1 "$OUT/state.bin"
    actual=$(byte_at "$OUT/state.bin" 0)
    [ "$actual" = "$waiting" ] && return 0
    case "$actual" in
      225|226|227|228|229)
        echo "Ship Runtime terminal state $actual before input" >&2
        return 1
        ;;
    esac
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "runtime state did not reach $waiting" >&2
  return 1
}

wait_sampler() {
  elapsed=0
  while [ "$elapsed" -lt 30 ]; do
    readback "$samples" 6 "$OUT/pre-key-witness.bin"
    pre_samples=$(byte_at "$OUT/pre-key-witness.bin" 0)
    pre_latched=$(byte_at "$OUT/pre-key-witness.bin" 3)
    [ "$pre_latched" -eq 0 ] || {
      echo "queue witness latched before human key" >&2
      return 1
    }
    [ "$pre_samples" -gt 0 ] && return 0
    sleep 1; elapsed=$((elapsed + 1))
  done
  echo "CPU sampler not live before key" >&2
  return 1
}

if [ "$ACTION" = capture ]; then
  readback "$samples" 6 "$OUT/post-key-witness.bin"
  count=$(byte_at "$OUT/post-key-witness.bin" 0)
  latch=$(byte_at "$OUT/post-key-witness.bin" 3)
  qstate=$(byte_at "$OUT/post-key-witness.bin" 4)
  qcode=$(byte_at "$OUT/post-key-witness.bin" 5)
  [ "$count" -gt 0 ] || { echo "FIRST RED: CPU sampler did not run" >&2; exit 5; }
  case "$latch:$((qstate & 0x80))" in
    1:128)
      printf 'CPU QUEUE DISCRIMINATOR: KEY PRESENT samples=%s D60A=$%02X D619=$%02X\n' \
        "$count" "$qstate" "$qcode"
      ;;
    0:0)
      printf 'CPU QUEUE DISCRIMINATOR: QUEUE EMPTY samples=%s last-D60A=$%02X last-D619=$%02X\n' \
        "$count" "$(byte_at "$OUT/post-key-witness.bin" 1)" \
        "$(byte_at "$OUT/post-key-witness.bin" 2)"
      ;;
    *)
      printf 'FIRST RED: inconsistent CPU latch=%s D60A=$%02X D619=$%02X\n' \
        "$latch" "$qstate" "$qcode" >&2
      exit 5
      ;;
  esac
  exit 0
fi

run_m65 -F
sleep 5
: > "$OUT/upload.log"
timeout --kill-after=2s 120s "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $image $remote" -c "get $remote $OUT/package-readback.d81" \
  -c "mount $remote" -c exit > "$OUT/upload.log" 2>&1
cmp "$image" "$OUT/package-readback.d81"
wait_state
wait_sampler
pre_samples=$(byte_at "$OUT/pre-key-witness.bin" 0)
pre_latched=$(byte_at "$OUT/pre-key-witness.bin" 3)
[ "$pre_samples" -gt 0 ] || { echo "CPU sampler not live before key" >&2; exit 5; }
[ "$pre_latched" -eq 0 ] || { echo "queue witness latched before human key" >&2; exit 5; }
echo "READY FOR ONE PHYSICAL KEY: type exactly '$key', then report zurück."
echo "Do not press RETURN and do not use monitor/JTAG before capture."
