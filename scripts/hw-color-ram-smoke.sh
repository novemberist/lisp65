#!/bin/sh
# Build/deploy the isolated MEGA65 Color-RAM EDMA smoke. No hard reset is used.
set -eu
cd "$(dirname "$0")/.."

PRG=build/lisp65-mega65-hw-color-ram-smoke.prg
TOOLS=tools/m65tools
dry_run=0
build=1
ip=""

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          Kommandos nur ausgeben
  --no-build         vorhandenes PRG verwenden
  --ip <ipv6%iface>  MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>      m65tools-Verzeichnis
  --prg <file>       PRG statt $PRG
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
    --prg) shift; PRG="$1" ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  make hw-color-ram-smoke-prg
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$PRG" ] || { echo "Fehler: PRG fehlt: $PRG" >&2; exit 3; }
fi

set -- --tools "$TOOLS" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

echo "==> starte Color-RAM-Smoke (erwartet: gruener Rahmen, color ram pass 2/2)"
sh scripts/run-on-mega65.sh "$@"
