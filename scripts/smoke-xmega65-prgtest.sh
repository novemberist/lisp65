#!/bin/sh
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 path/to/program.prg path/to/screenshot.png path/to/dump.mem" >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
emulator="${XMEGA65:-xmega65}"
prg="$1"
screenshot="$2"
dump="$3"
timeout_seconds="${XMEGA65_TIMEOUT:-45}"
prgtest="${XMEGA65_PRGTEST:-SYS 2049}"

case "$prg" in
  /*) prg_abs="$prg" ;;
  *) prg_abs="$(pwd)/$prg" ;;
esac

case "$screenshot" in
  /*) screenshot_abs="$screenshot" ;;
  *) screenshot_abs="$(pwd)/$screenshot" ;;
esac

case "$dump" in
  /*) dump_abs="$dump" ;;
  *) dump_abs="$(pwd)/$dump" ;;
esac

mkdir -p "$(dirname "$screenshot_abs")" "$(dirname "$dump_abs")"
rm -f "$screenshot_abs" "$dump_abs"

set +e
"$SCRIPT_DIR/xmega65-safe-run.sh" "$dump_abs" "$timeout_seconds" "$emulator" \
  -headless \
  -testing \
  -sleepless \
  -besure \
  -prg "$prg_abs" \
  -prgmode 65 \
  -prgtest "$prgtest" \
  -screenshot "$screenshot_abs" \
  -dumpmem "$dump_abs"
status=$?
set -e

case "$status" in
  0|66) ;;
  *)
    echo "xmega65 failed with status $status" >&2
    exit "$status"
    ;;
esac

if [ ! -s "$screenshot_abs" ]; then
  echo "xmega65 did not produce screenshot: $screenshot_abs" >&2
  exit 1
fi

if [ ! -s "$dump_abs" ]; then
  echo "xmega65 did not produce memory dump: $dump_abs" >&2
  exit 1
fi

echo "xmega65 screenshot written to $screenshot_abs"
echo "xmega65 memory dump written to $dump_abs"
