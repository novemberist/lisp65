#!/bin/sh
# One authorized non-promotable Link-34 observed-CRC hardware run.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link34-observed-crc-hardware
LINK=build/c2.2/substitution/link34-observed-crc-diagnostic
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

python3 tools/host-lisp/c2_link34_island_observed_crc.py selftest
python3 tools/host-lisp/c2_link34_island_observed_crc.py check-link
if [ -e "$DEPLOY" ]; then
  python3 tools/host-lisp/c2_product_hw_presmoke.py verify \
    --out "$OUT" --candidate-dir "$LINK"
else
  python3 tools/host-lisp/c2_product_hw_presmoke.py prepare \
    --out "$OUT" --candidate-dir "$LINK"
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0
[ ! -e "$OUT/hardware-result.json" ] || {
  echo "observed-CRC hardware run already consumed" >&2; exit 3;
}

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> non-promotable Link-34 observed-CRC diagnostic"
echo "    exactly one hardware run; no product presmoke retry"
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
sleep 8
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x00000000:0x00002000=$OUT/diagnostic-low-0000-1fff.bin"

BOOT_PATH=$(jq -r '.preloads[] | select(.address == "0x08200000") | .path' "$DEPLOY")
BOOT_BYTES=$(jq -r '.preloads[] | select(.address == "0x08200000") | .bytes' "$DEPLOY")
BOOT_END=$(printf '%08x' "$((0x08200000 + BOOT_BYTES))")
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x08200000:0x$BOOT_END=$OUT/diagnostic-boot-family.bin"
cmp "$BOOT_PATH" "$OUT/diagnostic-boot-family.bin"

python3 tools/host-lisp/c2_link34_island_observed_crc.py evaluate-hardware
