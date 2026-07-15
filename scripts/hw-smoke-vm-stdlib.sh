#!/bin/sh
# Reproducible hardware smoke path for the current MVP Workbench product ship.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip="${MEGA65_IP:-}"
tools_dir="tools/m65tools"
prg="${MVP_VM_SHIP_PRG:-build/ship/lisp65-mvp-workbench.prg}"
blob="${MVP_VM_SHIP_BLOB:-build/ship/lisp65-mvp-workbench.blob.bin}"
overlays="${MVP_VM_SHIP_OVERLAYS:-build/ship/lisp65-mvp-workbench.overlays.bin}"
d81="${MVP_VM_SHIP_D81:-build/ship/lisp65-mvp-workbench.d81}"
remote_d81="${MVP_VM_SHIP_REMOTE_D81:-L65WB.D81}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run          Kommandos nur ausgeben
  --no-build         vorhandenes Ship-PRG verwenden
  --ip <ipv6%iface>  MEGA65-Ziel fuer run-on-mega65.sh
  --tools <dir>      m65tools-Verzeichnis
  --prg <file>       PRG statt $prg verwenden
  --blob <file>      Stdlib-Blob statt $blob verwenden
  --overlays <file>  Runtime-Overlay-Katalog statt $overlays verwenden
  --d81 <file>       Workbench-D81 statt $d81 verwenden
  --remote-d81 <n>   D81-Name auf der MEGA65-SD (default: $remote_d81)
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
    --overlays) shift; overlays="$1" ;;
    --d81) shift; d81="$1" ;;
    --remote-d81) shift; remote_d81="$1" ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  echo "==> baue MVP-Workbench-Ship"
  make mvp-ship
fi

if [ "$dry_run" != "1" ]; then
  [ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$blob" ] || { echo "Fehler: Stdlib-Blob fehlt: $blob" >&2; exit 3; }
  [ -f "$overlays" ] || { echo "Fehler: Runtime-Overlay-Katalog fehlt: $overlays" >&2; exit 3; }
  [ -f "$d81" ] || { echo "Fehler: Workbench-D81 fehlt: $d81" >&2; exit 3; }
  [ -x "$tools_dir/mega65_ftp" ] || { echo "Fehler: $tools_dir/mega65_ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
fi

if [ "$dry_run" = "1" ]; then
  if [ -n "$ip" ]; then
    echo "DRY-RUN: $tools_dir/mega65_ftp -e -i $ip -y -c \"put $d81 $remote_d81\" -c \"exit\""
  else
    echo "DRY-RUN: $tools_dir/mega65_ftp -e -y -c \"put $d81 $remote_d81\" -c \"exit\""
  fi
else
  echo "==> lege Workbench-D81 auf die SD: $remote_d81"
  if [ -n "$ip" ]; then
    "$tools_dir/mega65_ftp" -e -i "$ip" -y -c "put $d81 $remote_d81" -c "exit"
  else
    "$tools_dir/mega65_ftp" -e -y -c "put $d81 $remote_d81" -c "exit"
  fi
fi

set -- --tools "$tools_dir" --mount "$remote_d81" \
  --preload-bin 0x08000000 "$overlays" --preload-bin 0x050000 "$blob" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$prg"

echo "==> starte MVP-Workbench-HW-Smoke"
echo "==> erwarteter manueller REPL-Check nach Boot (Workbench-Pfad):"
echo "    (+ 20 22)                                                => 42"
echo "    (load-lib \"ide\")                                       => t"
echo "    (load-lib \"idex\")                                      => t (optional comfort tier)"
echo "    (symbol-count) / (symbol-max)                            => roughly 648 / 720"
echo "    (function-kind (quote compile-buffer-to-lib))           => bytecode"
echo "    (function-kind (quote eval-buffer))                     => bytecode"
echo "    (dir)                                                   => list contains ide/idex/demo/work/fasl0"
echo "    (load-file-to-buffer \"demo\" \"demo\")                    => t"
echo "    (eval-buffer \"demo\")                                   => t"
echo "    (demo-numbers-run)                                      => 42"
echo "    (edit \"demo\")                                           => inspect/edit source, RUN/STOP returns"
echo "    (save-buffer-to \"work\" \"demo\")                         => t"
echo "    (load-file-to-buffer \"work\" \"copy\")                    => t"
echo "    (compile-buffer-to-lib \"fasl0\" \"demo\")                => t"
echo "    (load-lib \"fasl0\")                                     => t"
echo "    (demo-numbers-run)                                      => 42"
echo "    (compile-string \"(defun x () 1)\" \"noslot\")              => nil"
echo "    (compile-error)                                         => \"slot missing\""
echo "==> optionaler Core-Compile-Smoke: in frischer Session vor IDE laden"
echo "    (compile-string \"(defun a()40)(defun b()(+ (a)2))\" \"an\") => t"
echo "    (load-lib \"an\")                                         => t"
echo "    (b)                                                      => 42"
sh scripts/run-on-mega65.sh "$@"
