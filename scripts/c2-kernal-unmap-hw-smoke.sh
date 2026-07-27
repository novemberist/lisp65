#!/bin/sh
# Receipt-less fail-fast hardware pre-smoke for the bounded C2 KERNAL-unmap
# proof.  It does not build or run a product candidate.
set -eu
cd "$(dirname "$0")/.."

BUILD=build/c2.2/kernal-unmap
WINDOW=$BUILD/c2-kernal-window.bin
PRG=$BUILD/c2-kernal-unmap-proof.prg
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
dry_run=0
build=1
ip=""

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          commands only
  --no-build         reuse existing proof artifacts
  --ip <ipv6%iface>  MEGA65 target
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
    --ip) shift; ip=$1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

[ "$build" = 0 ] || python3 tools/host-lisp/c2_kernal_unmap_probe.py build

echo "==> C2 KERNAL-unmap bounded pre-smoke"
echo "    receipt-less, non-product, first-red; product substitution link remains locked"
echo "    host-verified Attic source; device publishes E-window only in closed handoff"

# Every current host transport uses $f700 as scratch.  That address is inside
# the physical $e000-$ffff window which this proof deliberately owns, so even
# a readback or controller launch after a host-side E-window write corrupts the
# object under test.  Bind an Attic source instead; the running controller DMA
# publishes it after handoff closure, with no intervening host operation.
ATTIC_STAGE=0x087fe000
READBACK=$BUILD/c2-kernal-window-staged-readback.bin
if [ "$dry_run" = 1 ]; then
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE -F -H -1 $PRG"
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE -H -@ $WINDOW@$ATTIC_STAGE"
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE --memsave $ATTIC_STAGE:0x08800000=$READBACK"
  echo "DRY-RUN: cmp $WINDOW $READBACK"
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE -r -1 $PRG"
  exit 0
fi

[ -x "$TOOLS/m65" ] || { echo "missing JTAG loader: $TOOLS/m65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }
# A prior first-red target deliberately spins forever with interrupts masked.
# Force a platform reset before loading so a retry cannot resume inside the
# old fail-closed loop while merely replacing its bytes underneath the CPU.
timeout 20s "$TOOLS/m65" -l "$DEVICE" -F -H -1 "$PRG"
timeout 20s "$TOOLS/m65" -l "$DEVICE" -H -@ "$WINDOW@$ATTIC_STAGE"
timeout 20s "$TOOLS/m65" -l "$DEVICE" \
  --memsave "$ATTIC_STAGE:0x08800000=$READBACK"
cmp "$WINDOW" "$READBACK" || {
  echo "FIRST RED: staged Attic window source differs from the proof image" >&2
  exit 1
}
timeout 20s "$TOOLS/m65" -l "$DEVICE" -r -1 "$PRG"
