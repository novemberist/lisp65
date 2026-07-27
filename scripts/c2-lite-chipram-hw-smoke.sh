#!/bin/sh
# Receipt-less fail-fast hardware pre-smoke for C2-lite Bank 2/3 ownership.
# It builds and runs only the isolated non-product proof target.
set -eu
cd "$(dirname "$0")/.."

BUILD=build/c2-lite/chipram-proof
PRG=$BUILD/c2-lite-chipram-proof.prg
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
dry_run=0
build=1

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          commands only
  --no-build         reuse host-verified proof artifacts
  --tools <dir>      m65tools directory
  --device <path>    JTAG serial device (default: $DEVICE)
  -h|--help          this help
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

[ "$build" = 0 ] || python3 tools/host-lisp/c2_lite_chipram_probe.py build

echo "==> C2-lite Bank-2/3 bounded pre-smoke"
echo "    receipt-less, non-product, first-red; Bank 1 untouched"
echo "    immediate post-return observation only; no convergence retry"

CORE=$BUILD/core-registers.bin
if [ "$dry_run" = 1 ]; then
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE --memsave 0x0ffd3632:0x0ffd3636=$CORE"
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE -F -H -1 $PRG"
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE -r -1 $PRG"
  exit 0
fi

[ -x "$TOOLS/m65" ] || { echo "missing JTAG loader: $TOOLS/m65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }
timeout 20s "$TOOLS/m65" -l "$DEVICE" \
  --memsave "0x0ffd3632:0x0ffd3636=$CORE"
timeout 20s "$TOOLS/m65" -l "$DEVICE" -F -H -1 "$PRG"
timeout 20s "$TOOLS/m65" -l "$DEVICE" -r -1 "$PRG"
