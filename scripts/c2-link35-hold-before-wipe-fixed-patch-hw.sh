#!/bin/sh
# Class-B cycle 2: exact two-byte Link-35 hold-before-wipe diagnostic.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link35-hold-before-wipe-hardware-cycle2
DEPLOY=$OUT/deployment.json
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
TIMEOUT=30
PREPARE_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) PREPARE_ONLY=1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --timeout) shift; TIMEOUT=$1 ;;
    *) echo "unexpected option: $1" >&2; exit 2 ;;
  esac
  shift
done

python3 tools/host-lisp/c2_link35_hold_before_wipe_fixed_patch.py selftest
python3 tools/host-lisp/c2_link35_hold_before_wipe_fixed_patch.py check
if [ -e "$DEPLOY" ]; then
  python3 tools/host-lisp/c2_link35_hold_before_wipe_fixed_patch.py verify-hardware
else
  python3 tools/host-lisp/c2_link35_hold_before_wipe_fixed_patch.py prepare-hardware
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

HW_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link35-hold-before-wipe-cycle2-hardware-receipt.json
[ ! -e "$HW_RECEIPT" ] || {
  echo "Class-B cycle-2 hardware run already consumed" >&2; exit 3;
}

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Class-B cycle 2/3: fixed-length E2f hold-before-wipe diagnostic"
echo "    non-promotable; exactly two operand bytes; zero capacity delta"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -F -H -1 "$PRG"
jq -c '.preloads[]' "$DEPLOY" | while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  end=$(printf '%08x' "$((address + bytes))")
  readback="$OUT/readback-$(basename "$path")"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -H -@ "$path@$address"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "$address:0x$end=$readback"
  cmp "$path" "$readback"
done

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -r -1 "$PRG"
LAUNCH_DONE_NS=$(date +%s%N)

T1_NS=$(date +%s%N)
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-1.bin"
sleep 0.5
T2_NS=$(date +%s%N)
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-2.bin"
sleep 1.5
T3_NS=$(date +%s%N)
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-3.bin"

T1_MS=$(((T1_NS - LAUNCH_DONE_NS) / 1000000))
T2_MS=$(((T2_NS - LAUNCH_DONE_NS) / 1000000))
T3_MS=$(((T3_NS - LAUNCH_DONE_NS) / 1000000))
jq -n \
  --arg reference "product-launch-command-completed" \
  --argjson t1 "$T1_MS" --argjson t2 "$T2_MS" --argjson t3 "$T3_MS" \
  '{reference:$reference,captures:[
    {capture:1,elapsed_after_launch_ms:$t1},
    {capture:2,elapsed_after_launch_ms:$t2},
    {capture:3,elapsed_after_launch_ms:$t3}
  ]}' > "$OUT/capture-timing.json"

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x00000000:0x00002000=$OUT/held-low-0000-1fff.bin"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000b960:0x0000bfe0=$OUT/held-job-and-marker-b960-bfe0.bin"

BOOT_PATH=$(jq -r '.preloads[] | select(.address == "0x08200000") | .path' "$DEPLOY")
BOOT_BYTES=$(jq -r '.preloads[] | select(.address == "0x08200000") | .bytes' "$DEPLOY")
BOOT_END=$(printf '%08x' "$((0x08200000 + BOOT_BYTES))")
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x08200000:0x$BOOT_END=$OUT/held-boot-family.bin"
cmp "$BOOT_PATH" "$OUT/held-boot-family.bin"

python3 tools/host-lisp/c2_link35_hold_before_wipe_fixed_patch.py evaluate-hardware
