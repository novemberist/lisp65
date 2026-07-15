#!/bin/sh
# Reproducible hardware selftest path for the MVP VM stdlib PRG.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip=""
tools_dir="tools/m65tools"
prg="${M65VMSTDLIBSELFTESTPRG:-build/lisp65-mega65-vm-stdlib-hw-selftest.prg}"
blob="${BYTECODE_STDLIB_BLOB:-build/bytecode/stdlib-p0.ext.bin}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          Kommandos nur ausgeben
  --no-build         vorhandenes Selftest-PRG verwenden
  --ip <ipv6%iface>  MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>      m65tools-Verzeichnis
  --prg <file>       PRG statt $prg verwenden
  --blob <file>      Stdlib-Blob statt $blob verwenden
  -h|--help          diese Hilfe
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; tools_dir="$1" ;;
    --prg) shift; prg="$1" ;;
    --blob) shift; blob="$1" ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  echo "==> baue MVP-VM-Stdlib-HW-Selftest"
  make mvp-vm-stdlib-hw-selftest
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$blob" ] || { echo "Fehler: Stdlib-Blob fehlt: $blob" >&2; exit 3; }
fi

set -- --tools "$tools_dir" --preload-bin 0x050000 "$blob" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$prg"

echo "==> starte MVP-VM-Stdlib-HW-Selftest"
echo "==> erwartetes Ergebnis am Geraet:"
echo "    gruen: lisp65 hw-selftest PASS 11/11"
echo "    rot:   lisp65 hw-selftest FAIL ..."
sh scripts/run-on-mega65.sh "$@"
