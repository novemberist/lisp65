#!/bin/sh
# Build and run the readable demo suite on real MEGA65 hardware.
#
# No hard JTAG reset is used here.  The normal path is:
#   build Dev-Core/FASL + demo D81 -> FTP put DEMOS.D81 -> etherload -> JTAG screenshot.
set -eu
cd "$(dirname "$0")/.."

SHARD="${SHARD:-all}"
PRG_BASE="${DEMO_SUITE_HW_PRG_BASE:-build/lisp65-hw-demo-suite}"
PRG="${DEMO_SUITE_HW_PRG:-}"
BLOB="${DEMO_SUITE_HW_BLOB:-build/bytecode/stdlib-p0.ext.bin}"
D81="${DEMO_SUITE_D81:-build/demos/lisp65-demo-suite.d81}"
REMOTE_D81="${DEMO_SUITE_REMOTE_D81:-DEMOS.D81}"
TOOLS="${TOOLS:-tools/m65tools}"
FTP="$TOOLS/mega65_ftp"
DEVICE="${DEVICE:-/dev/ttyUSB1}"
OUT_DIR="${OUT_DIR:-build/hw}"
PREFIX="${PREFIX:-hw-demo-suite}"
WAIT_SEC="${WAIT_SEC:-8}"
EXPECT="${EXPECT:-}"

dry_run=0
build=1
readback=1
ip=""

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          print commands without Etherload/JTAG side effects
  --no-build         reuse existing PRG/blob/D81 artifacts
  --ip <ipv6%iface>  MEGA65 target for etherload/ftp
  --tools <dir>      m65tools directory (default: $TOOLS)
  --device <dev>     JTAG serial device (default: $DEVICE)
  --out-dir <dir>    readback output directory (default: $OUT_DIR)
  --prefix <name>    readback filename prefix (default: $PREFIX)
  --shard <name>     core, screen, advnum, ide, or all (default: $SHARD)
  --wait <seconds>   wait before JTAG screenshot (default: $WAIT_SEC)
  --no-readback      skip JTAG screenshot/marker/counter readback
  -h|--help          this help
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; TOOLS="$1"; FTP="$TOOLS/mega65_ftp" ;;
    --device) shift; DEVICE="$1" ;;
    --out-dir) shift; OUT_DIR="$1" ;;
    --prefix) shift; PREFIX="$1" ;;
    --shard) shift; SHARD="$1" ;;
    --wait) shift; WAIT_SEC="$1" ;;
    --no-readback) readback=0 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$SHARD" = "all" ]; then
  for shard in core screen advnum ide; do
    set -- --shard "$shard" --wait "$WAIT_SEC" --tools "$TOOLS" --device "$DEVICE" --out-dir "$OUT_DIR"
    [ -n "$ip" ] && set -- "$@" --ip "$ip"
    [ "$dry_run" = "1" ] && set -- "$@" --dry-run
    [ "$build" = "0" ] && set -- "$@" --no-build
    [ "$readback" = "0" ] && set -- "$@" --no-readback
    sh scripts/hw-demo-suite.sh "$@"
  done
  exit 0
fi

case "$SHARD" in
  core)
    [ -n "$PRG" ] || PRG="$PRG_BASE-core.prg"
    [ -n "$EXPECT" ] || EXPECT="demo core pass 9/9"
    cflag="-DLISP65_DEMO_SHARD_CORE"
    ;;
  screen)
    [ -n "$PRG" ] || PRG="$PRG_BASE-screen.prg"
    [ -n "$EXPECT" ] || EXPECT="demo screen pass 3/3"
    cflag="-DLISP65_DEMO_SHARD_SCREEN"
    ;;
  advnum)
    [ -n "$PRG" ] || PRG="$PRG_BASE-advnum.prg"
    [ -n "$EXPECT" ] || EXPECT="demo advnum pass 6/6"
    cflag="-DLISP65_DEMO_SHARD_ADVNUM"
    ;;
  ide)
    [ -n "$PRG" ] || PRG="$PRG_BASE-ide.prg"
    [ -n "$EXPECT" ] || EXPECT="demo ide pass 4/4"
    cflag="-DLISP65_DEMO_SHARD_IDE"
    ;;
  *)
    echo "Fehler: --shard erwartet core, screen, advnum, ide oder all" >&2
    exit 2
    ;;
esac
PREFIX="$PREFIX-$SHARD"

if [ "$build" = "1" ]; then
  echo "==> baue Dev-Core-Blob, IDE-Lib und Demo-D81"
  make mvp-vm-stdlib-einsuite-core >/dev/null
  make demo-suite-d81 >/dev/null

  echo "==> baue Demo-HW-Runner (Dev-Core-Flags via make -n)"
  cmd=$(make -n mvp-vm-stdlib-einsuite-core \
    | sed ':a;/\\$/{N;s/\\\n//;ba}' \
    | grep -m1 'mos-mega65-clang')
  cmd=$(printf '%s' "$cmd" \
    | sed 's/[[:space:]]src\/main\.c[[:space:]]/ /; s/[[:space:]]-DLISP65_REPL[[:space:]]/ /; s/[[:space:]]-o [^[:space:]]*//')
  sh -c "$cmd $cflag scripts/hw-demo-suite-main.c -o '$PRG'"
  sz=$(stat -c%s "$PRG")
  end=$((0x2001 + sz - 2))
  printf '    %s: %d B, prg_file_end $%04x' "$PRG" "$sz" "$end"
  if [ "$end" -ge $((0xC000)) ]; then
    printf ' -- UEBER der etherload-Invariante $C000, ABBRUCH\n'
    exit 3
  fi
  printf ' (< $C000 OK)\n'
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$PRG" ] || { echo "Fehler: PRG fehlt: $PRG" >&2; exit 3; }
  [ -f "$PRG.elf" ] || { echo "Fehler: ELF fehlt: $PRG.elf" >&2; exit 3; }
  [ -f "$BLOB" ] || { echo "Fehler: Blob fehlt: $BLOB" >&2; exit 3; }
  [ -f "$D81" ] || { echo "Fehler: Demo-D81 fehlt: $D81" >&2; exit 3; }
fi

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $FTP -e -y -c \"put $D81 $REMOTE_D81\""
else
  echo "==> lege Demo-D81 auf die SD"
  if [ -n "$ip" ]; then
    "$FTP" -e -i "$ip" -y -c "put $D81 $REMOTE_D81"
  else
    "$FTP" -e -y -c "put $D81 $REMOTE_D81"
  fi
fi

set -- --tools "$TOOLS" --mount "$REMOTE_D81" --preload-bin 0x050000 "$BLOB" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

echo "==> starte Demo-Suite (erwartet: gruener Rahmen, $EXPECT)"
sh scripts/run-on-mega65.sh "$@"

[ "$readback" = "1" ] || exit 0

mkdir -p "$OUT_DIR"
shot="$OUT_DIR/$PREFIX.png"
ansi="$OUT_DIR/$PREFIX.ansi.txt"

echo "==> JTAG-Screenshot nach ${WAIT_SEC}s"
if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $TOOLS/m65 -l $DEVICE --screenshot=$shot > $ansi"
else
  sleep "$WAIT_SEC"
  "$TOOLS/m65" -l "$DEVICE" --screenshot="$shot" > "$ansi"
fi

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: ANSI-strip + grep -F '$EXPECT' $ansi"
elif python3 - "$ansi" "$EXPECT" <<'PY'
from pathlib import Path
import re
import sys

ansi_path, expect = sys.argv[1], sys.argv[2]
text = Path(ansi_path).read_text(errors="ignore")
clean = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", text)
sys.exit(0 if expect in clean else 1)
PY
then
  echo "PASS marker gefunden: $EXPECT"
else
  echo "Fehler: PASS-Marker fehlt in $ansi: $EXPECT" >&2
  exit 4
fi

echo "==> JTAG-Counter-Dump"
set -- --elf "$PRG.elf" --device "$DEVICE" --tools "$TOOLS" --out-dir "$OUT_DIR" --prefix "$PREFIX-counters"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
python3 scripts/hw-jtag-counters.py "$@"
