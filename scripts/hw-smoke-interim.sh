#!/bin/sh
# Bundled hardware smoke for the historical interim ship: build, optionally mount a D81,
# PRG per bestehendem run-on-mega65 Wrapper starten.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip=""
tools_dir="tools/m65tools"
profile="interim"
legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
prg="${SHIP_PRG:-$legacy_ship_dir/lisp65-interim.prg}"
d81="${SHIP_D81:-$legacy_ship_dir/lisp65-interim.d81}"
prg_set=0
d81_set=0

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          Kommandos nur ausgeben
  --no-build         vorhandene Artefakte verwenden
  --f011-stdlib      F011-REPL mit voller Stdlib-D81 mounten
  --ip <ipv6%iface>  MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>      m65tools-Verzeichnis
  --prg <file>       PRG statt $prg verwenden
  --d81 <file>       D81 statt $d81 verwenden
  -h|--help          diese Hilfe
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --f011-stdlib) profile="f011-stdlib" ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; tools_dir="$1" ;;
    --prg) shift; prg="$1"; prg_set=1 ;;
    --d81) shift; d81="$1"; d81_set=1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$profile" = "f011-stdlib" ]; then
  [ "$prg_set" = "1" ] || prg="${F011_SHIP_PRG:-$legacy_ship_dir/lisp65-f011-interim.prg}"
  [ "$d81_set" = "1" ] || d81="${STDLIB_D81:-$legacy_ship_dir/lisp65-stdlib.d81}"
fi

if [ "$build" = "1" ]; then
  case "$profile" in
    interim)
      echo "==> baue Interim-Ship"
      sh scripts/build-interim-ship.sh
      ;;
    f011-stdlib)
      echo "==> baue F011-REPL + Stdlib-D81"
      make f011-interim-ship stdlib-d81
      ;;
    *) echo "internal error: unknown profile $profile" >&2; exit 2 ;;
  esac
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$d81" ] || { echo "Fehler: D81 fehlt: $d81" >&2; exit 3; }
fi

set -- --tools "$tools_dir" --run --mount "$d81"
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$prg"

echo "==> starte HW-Smoke"
if [ "$profile" = "f011-stdlib" ]; then
  load_commands="${STDLIB_LOAD_COMMANDS:-$legacy_ship_dir/load-stdlib-commands.txt}"
  if [ -f "$load_commands" ]; then
    echo "==> Stdlib-Load-Kommandos: $load_commands"
  fi
fi
sh scripts/run-on-mega65.sh "$@"
