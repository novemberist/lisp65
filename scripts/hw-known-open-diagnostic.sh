#!/bin/sh
# Reproducible hardware diagnostic path for runtime known-open VM cases.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip=""
tools_dir="tools/m65tools"
step_limit="${M65VMSTDLIB_DIAG_STEP_LIMIT:-20000}"
prg="${M65VMSTDLIBDIAGPRG:-build/lisp65-mega65-vm-stdlib-known-open-diagnostic.prg}"
blob="${BYTECODE_KNOWN_OPEN_DIAG_BLOB:-build/bytecode/known-open-diagnostic/stdlib-p0.blob.bin}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run             Kommandos nur ausgeben
  --no-build            vorhandenes Diagnose-PRG verwenden
  --ip <ipv6%iface>     MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>         m65tools-Verzeichnis
  --step-limit <n>      VM_STEP_LIMIT fuer den Build (default: $step_limit)
  --prg <file>          PRG statt $prg verwenden
  --blob <file>         Diagnose-Blob statt $blob verwenden
  -h|--help             diese Hilfe
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; tools_dir="$1" ;;
    --step-limit) shift; step_limit="$1" ;;
    --prg) shift; prg="$1" ;;
    --blob) shift; blob="$1" ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  echo "==> baue Known-Open-Diagnose-PRG"
  make M65VMSTDLIB_DIAG_STEP_LIMIT="$step_limit" mvp-vm-stdlib-known-open-diagnostic
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$blob" ] || { echo "Fehler: Diagnose-Blob fehlt: $blob" >&2; exit 3; }
fi

set -- --tools "$tools_dir" --preload-bin 0x050000 "$blob" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$prg"

echo "==> starte Known-Open-HW-Diagnose"
echo "==> Build-Flags: -DVM_STEP_LIMIT=$step_limit -DLISP65_VM_DIAGNOSTICS"
echo "==> Embed: minimaler Diagnose-Bytecode (plusp/every/some), nicht die volle Produkt-Stdlib"
echo "==> manuelle REPL-Proben nach Boot:"
echo "    (every (function plusp) '(1 2 3))"
echo "      erwartet: t; bei Watchdog: vm: step limit ... pc=\$.... op=\$.. sp=\$.... fn=..."
echo "    (some (function (lambda (x) (if (> x 2) x nil))) '(1 2 3))"
echo "      erwartet: 3; bei Watchdog: dieselbe Diagnosezeile notieren"
echo "==> keine xmega65-Session wird durch dieses Skript gestartet."
sh scripts/run-on-mega65.sh "$@"
