#!/bin/sh
# One authorized receipt-less hardware run of the exact linked Link-34 leaf.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/link34-crc-leaf-hardware-probe
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

python3 tools/host-lisp/c2_link34_crc_leaf_hw_probe.py selftest
if [ -e "$OUT/deployment.json" ]; then
  python3 tools/host-lisp/c2_link34_crc_leaf_hw_probe.py verify
else
  python3 tools/host-lisp/c2_link34_crc_leaf_hw_probe.py prepare
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

M65=$TOOLS/m65
PRODUCT=build/c2.2/substitution/product-link-34-crc-asm-leaf/lisp65-c2-substitution-linked.prg
PROBE=$OUT/c2-link34-crc-leaf-hw-probe.prg
RAW=$OUT/c2-link34-crc-leaf-hw-probe.raw.bin
BUNDLE=$OUT/c2-link34-crc-inputs.bin
LEAF=$OUT/link34-rtov-crc-mem.bin
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> exact Link-34 CRC leaf hardware conformance probe"
echo "    receipt-less; no product entry, product link, or presmoke retry"

# Reset out of the E2f candidate and load its exact bytes without entering it.
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -F -H -1 "$PRODUCT"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -H -@ "$BUNDLE@0x8000"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x8000:0x99f5=$OUT/readback-inputs.bin"
cmp "$BUNDLE" "$OUT/readback-inputs.bin"

# Bind the exact linked leaf before and after the small BASIC probe is loaded.
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x222d:0x226f=$OUT/readback-leaf-before-probe.bin"
cmp "$LEAF" "$OUT/readback-leaf-before-probe.bin"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -H -1 "$PROBE"
PROBE_END=$(printf '%x' "$((0x2001 + $(stat -c %s "$RAW")))")
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x2001:0x$PROBE_END=$OUT/readback-probe.bin"
cmp "$RAW" "$OUT/readback-probe.bin"
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x222d:0x226f=$OUT/readback-leaf-after-probe.bin"
cmp "$LEAF" "$OUT/readback-leaf-after-probe.bin"

# Reloading the same tiny PRG starts its BASIC SYS line. It never enters the
# product and terminates in a colored-border loop with a fixed mailbox.
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -r -1 "$PROBE"
sleep 2
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --memsave "0x1f00:0x1f20=$OUT/hardware-mailbox.bin"
python3 tools/host-lisp/c2_link34_crc_leaf_hw_probe.py evaluate
