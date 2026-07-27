#!/bin/sh
# One authorized non-promotable Link-34 inner-status diagnostic hardware run.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link34-island-status-latch-hardware
LINK=build/c2.2/substitution/link34-island-status-latch-diagnostic
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

python3 tools/host-lisp/c2_link34_island_status_latch.py selftest
python3 tools/host-lisp/c2_link34_island_status_latch.py check-probe
python3 tools/host-lisp/c2_link34_island_status_latch.py check-link
if [ -e "$DEPLOY" ]; then
  python3 tools/host-lisp/c2_product_hw_presmoke.py verify \
    --out "$OUT" --candidate-dir "$LINK"
else
  python3 tools/host-lisp/c2_product_hw_presmoke.py prepare \
    --out "$OUT" --candidate-dir "$LINK"
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> non-promotable Link-34 Island status-latch diagnostic"
echo "    exactly one hardware run; no product presmoke retry"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"

# Load without entering, inject all six exact bound images, and verify every
# preload before starting the non-promotable diagnostic identity.
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

# Enter once. Link 34 failed before the Island installer, so eight seconds is
# deliberately ample while remaining a bounded diagnostic wait.
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

python3 tools/host-lisp/c2_link34_island_status_latch.py evaluate-hardware
