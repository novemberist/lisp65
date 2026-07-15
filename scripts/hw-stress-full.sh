#!/bin/sh
# lisp65 -- Full-profile hardware stress run on a real MEGA65.
# Builds a test-only PRG from the current mvp-vm-stdlib-einsuite-full command line,
# replacing src/main.c with scripts/hw-stress-main.c, then deploys it with the
# standard external stdlib blob preload.
set -eu
cd "$(dirname "$0")/.."

PRG=build/lisp65-hw-stress-full.prg
BLOB=build/bytecode/stdlib-p0.ext.bin
TOOLS=tools/m65tools

dry_run=0
build=1
ip=""
dma_prof=0
deep=0
prg_set=0

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          Kommandos nur ausgeben
  --no-build         vorhandenes Stress-PRG verwenden
  --ip <ipv6%iface>  MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>      m65tools-Verzeichnis
  --dma-prof         mit LISP65_DMA_PROF bauen; nicht mit --deep kombinierbar
  --deep <1|2>       Deep-Dive-Shard statt Basis-Stress (1: Runtime, 2: Stdlib/IDE)
  --prg <file>       Ausgabe-/Deploy-PRG statt $PRG
  --blob <file>      Stdlib-Blob statt $BLOB
  -h|--help          diese Hilfe
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; TOOLS="$1" ;;
    --dma-prof) dma_prof=1 ;;
    --deep) shift; deep="$1" ;;
    --prg) shift; PRG="$1"; prg_set=1 ;;
    --blob) shift; BLOB="$1" ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

case "$deep" in
  0|1|2) ;;
  *) echo "error: --deep expects 1 or 2" >&2; exit 2 ;;
esac
if [ "$deep" != "0" ] && [ "$dma_prof" = "1" ]; then
  echo "Fehler: --deep + --dma-prof passt aktuell nicht unter die Etherload-Invariante" >&2
  exit 2
fi

if [ "$prg_set" = "0" ]; then
  PRG=build/lisp65-hw-stress-full.prg
  [ "$deep" = "1" ] && PRG=build/lisp65-hw-stress-deep1.prg
  [ "$deep" = "2" ] && PRG=build/lisp65-hw-stress-deep2.prg
  if [ "$dma_prof" = "1" ]; then
    PRG=${PRG%.prg}-dmaprof.prg
  fi
fi

if [ "$build" = "1" ]; then
  echo "==> baue Full-Stdlib-Blob + Stress-PRG"
  make mvp-vm-stdlib-einsuite-full >/dev/null
  cmd=$(make -n mvp-vm-stdlib-einsuite-full \
    | sed ':a;/\\$/{N;s/\\\n//;ba}' \
    | grep -m1 'mos-mega65-clang')
  cmd=$(printf '%s' "$cmd" \
    | sed 's/[[:space:]]src\/main\.c[[:space:]]/ /; s/[[:space:]]-DLISP65_REPL[[:space:]]/ /; s/[[:space:]]-o [^[:space:]]*//')
  extra=""
  [ "$dma_prof" = "1" ] && extra="-DLISP65_DMA_PROF"
  [ "$deep" = "1" ] && extra="$extra -DLISP65_HW_STRESS_DEEP1"
  [ "$deep" = "2" ] && extra="$extra -DLISP65_HW_STRESS_DEEP2"
  # shellcheck disable=SC2086
  sh -c "$cmd $extra scripts/hw-stress-main.c -o '$PRG'"
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
  [ -f "$BLOB" ] || { echo "Fehler: Blob fehlt: $BLOB" >&2; exit 3; }
fi

set -- --tools "$TOOLS" --preload-bin 0x050000 "$BLOB" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

if [ "$deep" = "1" ]; then
  echo "==> starte Deep1-HW-Stress (erwartet: gruener Rahmen, stress deep1 pass 5/5)"
elif [ "$deep" = "2" ]; then
  echo "==> starte Deep2-HW-Stress (erwartet: gruener Rahmen, stress deep2 pass 5/5)"
else
  echo "==> starte Full-HW-Stress (erwartet: gruener Rahmen, stress pass 15/15)"
fi
sh scripts/run-on-mega65.sh "$@"
