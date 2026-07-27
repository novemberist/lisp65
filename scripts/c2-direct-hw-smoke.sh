#!/bin/sh
# Receipt-less fail-fast pre-smoke for direct C2 execution from an Attic shelf.
set -eu
cd "$(dirname "$0")/.."

BUILD=build/c2.1/direct-hw-smoke
SHELF=$BUILD/c2-direct-shelf.bin
PRG=$BUILD/c2-direct-hw-smoke.prg
TOOLS=tools/m65tools
dry_run=0
build=1
ip=""

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          commands only
  --no-build         reuse existing artifacts
  --ip <ipv6%iface>  MEGA65 target
  --tools <dir>      m65tools directory
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
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

[ "$build" = 0 ] || python3 tools/host-lisp/c2_direct_hw_smoke.py build

set -- --tools "$TOOLS" --run --preload-bin 0x08100000 "$SHELF"
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = 1 ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

echo "==> C2.1 direct-Attic pre-smoke (receipt-less; green border + PASS expected)"
sh scripts/run-on-mega65.sh "$@"
