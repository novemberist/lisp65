#!/bin/sh
# Headless xmega65 smoke for native MEGA65 PRGs.
# The oracle is the deterministic $C000 output sink captured via -dumpmem.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 expected-string path/to/test.prg" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

EXPECT="$1"
PRG="$2"
EMU="${XMEGA65:-xmega65}"
DUMP="${DUMP:-build/$(basename "$PRG" .prg)-xmega65-dump.bin}"
LOG="${XMEGA65_LOG:-build/$(basename "$PRG" .prg)-xmega65.log}"

[ -f "$PRG" ] || { echo "xmega65 smoke FAIL: PRG fehlt: $PRG" >&2; exit 3; }

case "$PRG" in
  /*) PRG_ABS="$PRG" ;;
  *) PRG_ABS="$ROOT/$PRG" ;;
esac
case "$DUMP" in
  /*) DUMP_ABS="$DUMP" ;;
  *) DUMP_ABS="$ROOT/$DUMP" ;;
esac
case "$LOG" in
  /*) LOG_ABS="$LOG" ;;
  *) LOG_ABS="$ROOT/$LOG" ;;
esac

SYS=$(python3 -c "d=open('$PRG_ABS','rb').read(); i=d.index(0x9e); j=d.index(0,i); print(d[i+1:j].decode().strip())")

mkdir -p "$(dirname "$DUMP_ABS")" "$(dirname "$LOG_ABS")"
rm -f "$DUMP_ABS" "$LOG_ABS"

set +e
scripts/xmega65-safe-run.sh "$DUMP_ABS" "${XMEGA65_TIMEOUT:-90}" "$EMU" \
  -headless \
  -testing \
  -sleepless \
  -besure \
  -fastboot \
  -prgexit \
  -prg "$PRG_ABS" \
  -prgmode 65 \
  -prgtest "SYS $SYS" \
  -dumpmem "$DUMP_ABS" >"$LOG_ABS" 2>&1
status=$?
set -e

if [ ! -s "$DUMP_ABS" ]; then
  echo "xmega65 smoke FAIL: kein Memory-Dump erzeugt (status=$status, log=$LOG_ABS)" >&2
  if [ -s "$LOG_ABS" ]; then
    echo "xmega65 smoke log tail:" >&2
    tail -50 "$LOG_ABS" >&2
  fi
  exit 1
fi

if ! python3 scripts/check-xemu-dump.py "$DUMP_ABS" "$EXPECT"; then
  echo "xmega65 smoke FAIL: status=$status, dump=$DUMP_ABS, log=$LOG_ABS" >&2
  if [ -s "$LOG_ABS" ]; then
    echo "xmega65 smoke log tail:" >&2
    tail -50 "$LOG_ABS" >&2
  fi
  exit 1
fi

if [ "$status" -ne 0 ] && [ "$status" -ne 66 ]; then
  echo "xmega65 smoke note: emulator status=$status, dump oracle passed (log=$LOG_ABS)" >&2
fi
