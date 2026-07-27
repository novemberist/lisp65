#!/bin/sh
# Class-B cycle 1: preserve the first E2f destination before fail-closed wipe.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link35-hold-before-wipe-hardware-cycle1
LINK=build/c2.2/substitution/link35-hold-before-wipe-diagnostic-cycle1
AUTH=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link35-hold-before-wipe-diagnostic-cycle1-link-receipt.json
HW_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link35-hold-before-wipe-diagnostic-cycle1-hardware-receipt.json
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

python3 tools/host-lisp/c2_link35_hold_before_wipe_diagnostic.py selftest
python3 tools/host-lisp/c2_link35_hold_before_wipe_diagnostic.py check
if [ -e "$DEPLOY" ]; then
  python3 tools/host-lisp/c2_product_hw_presmoke.py verify \
    --out "$OUT" --candidate-dir "$LINK" --authorization-receipt "$AUTH"
else
  python3 tools/host-lisp/c2_product_hw_presmoke.py prepare \
    --out "$OUT" --candidate-dir "$LINK" --authorization-receipt "$AUTH"
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0
[ ! -e "$HW_RECEIPT" ] || {
  echo "Class-B cycle-1 hardware run already consumed" >&2; exit 3;
}

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Class-B cycle 1/3: non-promotable E2f hold-before-wipe diagnostic"
echo "    exactly one announced hardware run; Link 35 remains untouched"
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
sleep 3

# Three read-only observations of the exact catalog-verifier destination.
# The CPU is already held on the first failed CRC and cannot wipe the bytes.
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-1.bin"
sleep 1
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-2.bin"
sleep 3
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x0000c356:0x0000c7da=$OUT/held-target-capture-3.bin"

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

python3 tools/host-lisp/c2_link35_hold_before_wipe_diagnostic.py \
  evaluate-hardware --hardware-dir "$OUT"
