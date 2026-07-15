#!/bin/sh
# Runs the MEGA65 F011 load smoke against an SD image prepared for -defd81fromsd.
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 expected-string path/to/test.prg path/to/sd.img" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

expect="$1"
prg="$2"
sdimg="$3"
emu="${XMEGA65:-xmega65}"
dump="${DUMP:-build/$(basename "$prg" .prg)-f011-dump.bin}"
timeout_seconds="${XMEGA65_TIMEOUT:-90}"

[ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
[ -f "$sdimg" ] || { echo "Fehler: SD-Image fehlt: $sdimg" >&2; exit 3; }

case "$prg" in
  /*) prg_abs="$prg" ;;
  *) prg_abs="$ROOT/$prg" ;;
esac
case "$sdimg" in
  /*) sdimg_abs="$sdimg" ;;
  *) sdimg_abs="$ROOT/$sdimg" ;;
esac
case "$dump" in
  /*) dump_abs="$dump" ;;
  *) dump_abs="$ROOT/$dump" ;;
esac

sys=$(python3 -c "d=open('$prg_abs','rb').read(); i=d.index(0x9e); j=d.index(0,i); print(d[i+1:j].decode())")

mkdir -p "$(dirname "$dump_abs")"
rm -f "$dump_abs"

set +e
scripts/xmega65-safe-run.sh "$dump_abs" "$timeout_seconds" "$emu" \
  -headless \
  -testing \
  -sleepless \
  -besure \
  -fastboot \
  -prgexit \
  -sdimg "$sdimg_abs" \
  -defd81fromsd \
  -prg "$prg_abs" \
  -prgmode 65 \
  -prgtest "SYS $sys" \
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
  echo "xmega65 F011 smoke FAIL: kein Memory-Dump erzeugt" >&2
  exit 1
fi

python3 scripts/check-xemu-dump.py "$dump_abs" "$expect"
