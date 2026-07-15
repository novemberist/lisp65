#!/bin/sh
# Reproducible hardware smoke path for the M6 compile-REPL profile.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip=""
tools_dir="tools/m65tools"
prg="${M65VMSTDLIBCOMPILEPRG:-build/lisp65-mega65-vm-stdlib-compile-repl.prg}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          print commands only
  --no-build         use an existing compile-REPL PRG
  --ip <ipv6%iface>  MEGA65 target for run-on-mega65.sh
  --tools <dir>      m65tools directory
  --prg <file>       PRG instead of $prg
  --blob <file>      ignored; lean compile-REPL smoke does not preload a blob
  -h|--help          this help
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
    --blob) shift; echo "warning: --blob is ignored by lean compile-REPL smoke" >&2 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *) echo "unexpected argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  echo "==> build M6 compile-REPL profile"
  make mvp-vm-stdlib-compile-repl
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$prg" ] || { echo "error: PRG missing: $prg" >&2; exit 3; }
fi

set -- --tools "$tools_dir" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$prg"

echo "==> start M6 compile-REPL HW smoke"
echo "==> expected manual checks once the compile-REPL profile links and boots:"
echo "    (+ 1 2)                                  => 3"
echo "    (progn (setq m6g 41) (+ m6g 1))          => 42"
echo "    (defun sq (x) (* x x))                   => sq"
echo "    (sq 5)                                   => 25"
echo "    (case 2 (1 10) (2 20) (t 30))            => 20"
echo "==> lean profile: no stdlib blob preload; user definitions live in Bank 5 from offset 0."
sh scripts/run-on-mega65.sh "$@"
