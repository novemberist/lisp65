#!/bin/sh
# lisp65 B4 development-core workflow gate.
# The lean core boots, IDE + PLACE load on demand, source is saved into a slot, compile-file emits
# FASL, and the result is loaded and called. The user checks interactive editing manually.
#
# Expected: green border and "einsuite hw-selftest pass 10/10".
# Usage: sh scripts/hw-b4-workflow.sh [--dry-run] [--no-build] [--ip <ipv6%iface>]
set -eu
cd "$(dirname "$0")/.."

C1541="${C1541:-c1541}"
PRG=build/lisp65-einsuite-b4-hw-selftest.prg
BLOB=build/bytecode/stdlib-p0.ext.bin
D81=build/f011/b4-workflow.d81

dry_run=0; build=1; ip=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; ip="$1" ;;
    *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  command -v "$C1541" >/dev/null 2>&1 || { echo "Fehler: c1541 fehlt" >&2; exit 3; }
  mkdir -p build/f011
  echo "==> baue Pilot-Libs + Dev-Core (Blob-Kopplung!)"
  make bytecode-p0-pilot-libs-artifacts >/dev/null
  make mvp-vm-stdlib-einsuite-core >/dev/null
  echo "==> baue B4-D81 (IDE+PLACE-Libs + Quell-/Fasl-Slots)"
  fslot=build/f011/b4-slot.bin
  python3 -c "import sys; sys.stdout.write('0' * 700)" > "$fslot"
  "$C1541" -format "b4,wf" d81 "$D81" \
    -write build/bytecode/libs/ide.ext.bin "ide,s" \
    -write build/bytecode/libs/place.ext.bin "place,s" \
    -write "$fslot" "fsrc2,s" \
    -write "$fslot" "fasl9,s" > build/f011/b4-c1541.log 2>&1 || {
      cat build/f011/b4-c1541.log >&2; exit 3; }

  echo "==> baue B4-Selftest (Dev-Core-Flags via make -n)"
  cmd=$(make -n mvp-vm-stdlib-einsuite-core | sed ':a;/\\$/{N;s/\\\n//;ba}' | grep -m1 'mos-mega65-clang')
  cmd=$(printf '%s' "$cmd" | sed 's/ src\/main\.c/ /; s/ -DLISP65_REPL / /; s/ -o [^ ]*//')
  sh -c "$cmd -DLISP65_HW_B4_WORKFLOW scripts/einsuite-hw-selftest-main.c -o $PRG"
  sz=$(stat -c%s "$PRG"); end=$((0x2001 + sz - 2))
  printf '    %s: %d B, prg_file_end $%04x' "$PRG" "$sz" "$end"
  [ "$end" -ge $((0xC000)) ] && { printf ' -- ÜBER $C000, ABBRUCH\n'; exit 3; }
  printf ' (< $C000 OK)\n'
fi

[ -f "$PRG" ] && [ -f "$BLOB" ] && [ -f "$D81" ] || { echo "Artefakte fehlen" >&2; exit 3; }

FTP=tools/m65tools/mega65_ftp
if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $FTP -e -y -c \"put $D81 B4WF.D81\""
else
  echo "==> lege D81 auf die SD"
  "$FTP" -e -y -c "put $D81 B4WF.D81"
fi

set -- --mount B4WF.D81 --preload-bin 0x050000 "$BLOB" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

echo "==> starte B4-Workflow-Selftest (erwartet: gruener Rahmen, pass 10/10)"
sh scripts/run-on-mega65.sh "$@"
