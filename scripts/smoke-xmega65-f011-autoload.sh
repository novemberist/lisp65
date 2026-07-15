#!/bin/sh
# Runs a MEGA65 F011 load smoke by autoloading the test PRG from an SD-internal D81.
set -eu

if [ "$#" -lt 2 ]; then
  echo "usage: $0 expected-string [expected-string ...] path/to/sd.img" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

sdimg=""
for arg in "$@"; do sdimg="$arg"; done
emu="${XMEGA65:-xmega65}"
dump="${DUMP:-build/f011-autoload-dump.bin}"
timeout_seconds="${XMEGA65_TIMEOUT:-120}"

[ -f "$sdimg" ] || { echo "Fehler: SD-Image fehlt: $sdimg" >&2; exit 3; }

case "$sdimg" in
  /*) sdimg_abs="$sdimg" ;;
  *) sdimg_abs="$ROOT/$sdimg" ;;
esac
case "$dump" in
  /*) dump_abs="$dump" ;;
  *) dump_abs="$ROOT/$dump" ;;
esac

mkdir -p "$(dirname "$dump_abs")"
rm -f "$dump_abs"

set +e
scripts/xmega65-safe-run.sh "$dump_abs" "$timeout_seconds" "$emu" \
  -headless \
  -testing \
  -sleepless \
  -besure \
  -fastboot \
  -sdimg "$sdimg_abs" \
  -defd81fromsd \
  -autoload \
  -dumpmem "$dump_abs" >/dev/null 2>&1
status=$?
set -e

case "$status" in
  0|66) ;;
  *)
    echo "xmega65 failed with status $status" >&2
    exit "$status"
    ;;
esac

if [ ! -s "$dump_abs" ]; then
  echo "xmega65 F011 autoload smoke FAIL: kein Memory-Dump erzeugt" >&2
  exit 1
fi

while [ "$#" -gt 1 ]; do
  python3 scripts/check-xemu-dump.py "$dump_abs" "$1"
  shift
done
