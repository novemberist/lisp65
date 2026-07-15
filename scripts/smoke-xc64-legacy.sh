#!/bin/sh
# lisp65 — historischer C64/GO64-Headless-Smoke.
# Not part of the MEGA65 MVP gate. Use only through legacy-xc64-* Make targets.
#
# Usage: scripts/smoke-xc64-legacy.sh ["erwarteter String" [path/to/test.prg]]
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

LLVM=tools/llvm-mos/bin
PRG="${2:-build/lisp65-c64-test.prg}"
DUMP="${DUMP:-build/$(basename "$PRG" .prg)-xemu-dump.bin}"
LOG="${XEMU_LOG:-build/$(basename "$PRG" .prg)-xemu.log}"
EXPECT="${1:-lisp65 print: (+ 1 2)}"
EMU="${XMEGA65:-xmega65}"

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

mkdir -p build
if [ $# -lt 2 ]; then
  "$LLVM/mos-c64-clang" -Os -DLISP65_XEMU_TEST src/*.c -o "$PRG"
fi

# Read the SYS start address from the PRG's BASIC stub.
SYS=$(python3 -c "d=open('$PRG_ABS','rb').read(); i=d.index(0x9e); j=d.index(0,i); print(d[i+1:j].decode())")

mkdir -p "$(dirname "$DUMP_ABS")" "$(dirname "$LOG_ABS")"
rm -f "$DUMP_ABS" "$LOG_ABS"
set +e
scripts/xmega65-safe-run.sh "$DUMP_ABS" "${XEMU_TIMEOUT:-60}" "$EMU" \
  -headless -testing -sleepless -besure -fastboot \
  -prgexit -prg "$PRG_ABS" -prgmode 64 -prgtest "SYS $SYS" -dumpmem "$DUMP_ABS" >"$LOG_ABS" 2>&1
status=$?
set -e

if [ ! -s "$DUMP_ABS" ]; then
  echo "xemu smoke FAIL: kein Memory-Dump erzeugt (status=$status, log=$LOG_ABS)" >&2
  if [ -s "$LOG_ABS" ]; then
    echo "xemu smoke log tail:" >&2
    tail -40 "$LOG_ABS" >&2
  fi
  exit 1
fi

if ! python3 scripts/check-xemu-dump.py "$DUMP_ABS" "$EXPECT"; then
  echo "xemu smoke FAIL: status=$status, dump=$DUMP_ABS, log=$LOG_ABS" >&2
  if [ -s "$LOG_ABS" ]; then
    echo "xemu smoke log tail:" >&2
    tail -40 "$LOG_ABS" >&2
  fi
  exit 1
fi

if [ "$status" -ne 0 ] && [ "$status" -ne 66 ]; then
  echo "xemu smoke note: emulator status=$status, dump oracle passed (log=$LOG_ABS)" >&2
fi
