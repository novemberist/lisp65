#!/bin/sh
# Read-only Link-86 physical-key queue discriminator.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-ship-builder-v1-link86-queue-discriminator.json
OUT=build/ship-builder/v13/link86-queue-discriminator/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|start|capture) ;;
  *) echo "usage: $0 <dry-run|start|capture>" >&2; exit 2 ;;
esac

image=$(jq -r '.image' "$CONFIG")
expected_sha=$(jq -r '.image_sha256' "$CONFIG")
remote=$(jq -r '.remote' "$CONFIG")
state=$(($(jq -r '.runtime_state' "$CONFIG")))
waiting=$(jq -r '.runtime_waiting_value' "$CONFIG")
queue_state=$(($(jq -r '.read_only_addresses.queue_state' "$CONFIG")))
queue_code=$(($(jq -r '.read_only_addresses.queue_code' "$CONFIG")))
key=$(jq -r '.physical_key' "$CONFIG")

[ "$(sha256sum "$image" | awk '{print $1}')" = "$expected_sha" ] || {
  echo "Link-86 interactive image SHA drift" >&2; exit 3;
}

# This historical session is superseded as a live-I/O discriminator.  Keep
# its exact body for receipt archaeology, but refuse every entry point so a
# new device contact cannot be prepared around an invalid capture primitive.
echo "FIRST RED: Link-86 queue discriminator superseded; --memsave is RAM-under-I/O" >&2
exit 5

if [ "$ACTION" = dry-run ]; then
  [ -f "$image" ]
  [ "$queue_state" -eq $((0xd60a)) ]
  [ "$queue_code" -eq $((0xd619)) ]
  [ "$(jq -r '.limits.product_bytes' "$CONFIG")" -eq 0 ]
  [ "$(jq -r '.limits.product_links' "$CONFIG")" -eq 0 ]
  [ "$(jq -r '.limits.physical_keys' "$CONFIG")" -eq 1 ]
  [ "$(jq -r '.limits.post_key_memory_reads' "$CONFIG")" -eq 2 ]
  [ "$(jq -r '.limits.virtual_keys' "$CONFIG")" -eq 0 ]
  [ "$(jq -r '.limits.screen_captures_after_key' "$CONFIG")" -eq 0 ]
  echo "DRY-RUN: cold reset -> fresh BASIC -> exact unchanged Link-86 D81 -> state 2"
  echo "HANDS OFF: no monitor traffic while the operator types exactly '$key'"
  echo "CAPTURE: one byte at D60A and one byte at D619; no dequeue, screenshot or virtual key"
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
wait_state() {
  expected=$1 limit=$2 elapsed=0
  while [ "$elapsed" -lt "$limit" ]; do
    readback "$state" 1 "$OUT/state.bin"
    actual=$(od -An -tu1 "$OUT/state.bin" | tr -d ' ')
    [ "$actual" = "$expected" ] && return 0
    case "$actual" in
      225|226|227|228|229)
        echo "Ship Runtime terminal state $actual before input" >&2
        return 1
        ;;
    esac
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "runtime state did not reach $expected within ${limit}s" >&2
  return 1
}

if [ "$ACTION" = capture ]; then
  # m65 --memsave uses the monitor RAM view.  In the mapped I/O page it reads
  # the RAM underneath $D000, not the live device registers (the G6 BUFSEL
  # First Red established the same boundary).  A live $D60A/$D619 capture must
  # first use target code to copy the registers into ordinary RAM.
  echo "FIRST RED: --memsave cannot witness live D60A/D619; use a target-native I/O witness" >&2
  exit 5
  # These are the only two post-key reads.  Reading D619 does not dequeue;
  # only a write to D619 advances the queue head.
  readback "$queue_state" 1 "$OUT/d60a.bin"
  readback "$queue_code" 1 "$OUT/d619.bin"
  d60a=$(od -An -tx1 "$OUT/d60a.bin" | tr -d ' \n')
  d619=$(od -An -tx1 "$OUT/d619.bin" | tr -d ' \n')
  printf '{"d60a":"0x%s","d619":"0x%s"}\n' "$d60a" "$d619" \
    > "$OUT/queue.json"
  if [ $((0x$d60a & 0x80)) -ne 0 ]; then
    echo "QUEUE DISCRIMINATOR: KEY PRESENT D60A=0x$d60a D619=0x$d619"
  else
    echo "QUEUE DISCRIMINATOR: QUEUE EMPTY D60A=0x$d60a D619=0x$d619"
  fi
  exit 0
fi

run_m65 -F
sleep 5
: > "$OUT/upload.log"
timeout --kill-after=2s 120s "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
  -c "put $image $remote" -c "get $remote $OUT/package-readback.d81" \
  -c "mount $remote" -c exit > "$OUT/upload.log" 2>&1
cmp "$image" "$OUT/package-readback.d81"
wait_state "$waiting" 90
readback "$state" 1 "$OUT/state-before-human.bin"
[ "$(od -An -tu1 "$OUT/state-before-human.bin" | tr -d ' ')" = "$waiting" ]
echo "READY FOR ONE PHYSICAL KEY: type exactly '$key', then report zurück."
echo "Do not press RETURN. No virtual key was sent. Do not use monitor/JTAG until capture."
