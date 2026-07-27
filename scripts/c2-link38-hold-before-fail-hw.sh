#!/bin/sh
# Non-promotable Link-38 hold-before-fail hardware diagnosis.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link38-c2-lite-hold-before-fail-hardware
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

PY=tools/host-lisp/c2_link38_hold_before_fail.py
if [ ! -e "$DEPLOY" ]; then
  python3 "$PY" prepare-hardware
else
  python3 "$PY" verify-hardware
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

HW_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link38-c2-lite-hold-before-fail-hardware-receipt.json
[ ! -e "$HW_RECEIPT" ] || {
  echo "Link-38 hold-before-fail hardware run already consumed" >&2
  exit 3
}

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Link 38 non-promotable hold-before-fail diagnosis"
echo "    instruction 80 f6 -> 80 fe; one changed operand byte; zero capacity delta"
echo "    diagnostic_sha=$(jq -r '.product.sha256' "$DEPLOY")"

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
sleep 2

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c85d=$OUT/held-target-1.bin"
sleep 0.25
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c85d=$OUT/held-target-2.bin"
sleep 0.75
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c85d=$OUT/held-target-3.bin"

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x00000000:0x00010000=$OUT/held-bank0-0000-ffff.bin"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000e000:0x00010000=$OUT/held-e000-ffff.bin"

BOOT_PATH=$(jq -r '.preloads[] | select(.address == "0x08200000") | .path' "$DEPLOY")
BOOT_BYTES=$(jq -r '.preloads[] | select(.address == "0x08200000") | .bytes' "$DEPLOY")
BOOT_END=$(printf '%08x' "$((0x00030000 + BOOT_BYTES))")
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x00030000:0x$BOOT_END=$OUT/held-chip-bank3-boot.bin"
cmp "$BOOT_PATH" "$OUT/held-chip-bank3-boot.bin"

python3 "$PY" evaluate-hardware
