#!/bin/sh
# lisp65 M4 completion gate: load/save round trip on a real MEGA65.
#
# Build the round-trip D81 with TESTLIB source and preallocated save slot S6, build the full
# self-test with disk checks, deploy the D81 to SD, then run with --mount.
# SAVE overwrites the preallocated chain without BAM changes, hence the padded dummy slot.
# Rule-B load ignores the space padding.
#
# Expected on device: green border and "einsuite hw-selftest pass 17/17".
# Usage: sh scripts/hw-disk-roundtrip.sh [--fasl] [--dry-run] [--no-build] [--ip <ipv6%iface>]
#   --fasl = B3 FASL round trip: compile "fsrc" to FASL9, C-load it, and expect pass 10/10.
set -eu
cd "$(dirname "$0")/.."

C1541="${C1541:-c1541}"
CLANG=tools/llvm-mos/bin/mos-mega65-clang
FTP=tools/m65tools/mega65_ftp
D81=build/f011/roundtrip.d81
PRG=build/lisp65-einsuite-disk-hw-selftest.prg
BLOB=build/bytecode/stdlib-p0.ext.bin

dry_run=0; build=1; ip=""; fasl=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --fasl) fasl=1; PRG=build/lisp65-einsuite-fasl-hw-selftest.prg ;;
    --ip) shift; ip="$1" ;;
    *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  command -v "$C1541" >/dev/null 2>&1 || { echo "Fehler: c1541 fehlt" >&2; exit 3; }
  mkdir -p build/f011
  echo "==> baue Roundtrip-D81 (TESTLIB + Slot S6)"
  # Slot dummy: roughly 500 bytes of zero lines form a two-sector chain; content is overwritten.
  # Padding lines are harmless to load; see scripts/f011-testlib.lisp.
  slot=build/f011/s6-slot.lisp
  python3 -c "print('0\n' * 250, end='')" > "$slot"
  # FASL source (defuns only; compile-file rejects anything else) plus FASL slot.
  fsrc=build/f011/fsrc.lisp
  printf '(defun s9 (x) (* x 9))\n(defun mk9 (n) (lambda (x) (+ x n)))\n' > "$fsrc"
  fslot=build/f011/fasl9-slot.bin
  python3 -c "import sys; sys.stdout.write('0' * 600)" > "$fslot"
  "$C1541" -format "roundtrip,rt" d81 "$D81" \
    -write scripts/f011-testlib.lisp "testlib,s" \
    -write "$slot" "s6,s" \
    -write "$fsrc" "fsrc,s" \
    -write "$fslot" "fasl9,s" > build/f011/roundtrip-c1541.log 2>&1 || {
      cat build/f011/roundtrip-c1541.log >&2; exit 3; }

  if [ "$fasl" = "1" ]; then
    # B3: expand flags from the Make target so filter-out chains remain parseable.
    echo "==> build the FASL self-test from the einsuite-fasl profile via make -n"
    make mvp-vm-stdlib-einsuite-fasl >/dev/null          # artifacts and coupled blob
    cmd=$(make -n mvp-vm-stdlib-einsuite-fasl | sed ':a;/\\$/{N;s/\\\n//;ba}' | grep -m1 'mos-mega65-clang')
    cmd=$(printf '%s' "$cmd" | sed 's/ src\/main\.c/ /; s/ -DLISP65_REPL/ /; s/ -o [^ ]*//')
    sh -c "$cmd -DLISP65_HW_FASL_ROUNDTRIP scripts/einsuite-hw-selftest-main.c -o $PRG"
    sz=$(stat -c%s "$PRG"); end=$((0x2001 + sz - 2))
    printf '    %s: %d B, prg_file_end $%04x' "$PRG" "$sz" "$end"
    [ "$end" -ge $((0xC000)) ] && { printf ' -- ÜBER \$C000, ABBRUCH\n'; exit 3; }
    printf ' (< \$C000 OK)\n'
  else
  echo "==> baue Full+Disk-Selftest (Full-Suite-Blob via Target — Kopplung!)"
  make mvp-vm-stdlib-einsuite-full >/dev/null
  FLAGS=$(sed -n 's/^M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS ?= //p' Makefile | head -1 \
          | sed 's/-DLISP65_SCREEN_BULK_P_IN_STDLIB//; s/-DMAX_SYM=481/-DMAX_SYM=560/; s/-DVM_DIR_MAX=416/-DVM_DIR_MAX=512/')
  HEAP=$(sed -n 's/^M65VMSTDLIB_EINSUITE_HEAP ?= //p' Makefile | head -1)
  # shellcheck disable=SC2086
  "$CLANG" -Oz -Wall -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
    -DHEAP_CELLS="${HEAP:-48}" $FLAGS \
    -DLISP65_TREEWALK_STRIP -DLISP65_EVAL_PRIMS \
    -DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 \
    -DLISP65_SCREEN_WRITE_STRING -DLISP65_HW_DISK_ROUNDTRIP -Isrc -Ibuild/bytecode \
    src/eval.c src/interrupt.c src/io.c src/mem.c src/printer.c src/reader.c \
    src/repl.c src/screen.c src/symbol.c src/vm_embed.c src/vm.c \
    build/bytecode/stdlib-p0.c scripts/einsuite-hw-selftest-main.c -o "$PRG"
  sz=$(stat -c%s "$PRG"); end=$((0x2001 + sz - 2))
  printf '    %s: %d B, prg_file_end $%04x' "$PRG" "$sz" "$end"
  [ "$end" -ge $((0xC000)) ] && { printf ' -- ÜBER $C000, ABBRUCH\n'; exit 3; }
  printf ' (< $C000 OK)\n'
  fi
fi

[ -f "$PRG" ] && [ -f "$BLOB" ] && [ -f "$D81" ] || { echo "Artefakte fehlen" >&2; exit 3; }

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $FTP -e -y -c \"put $D81 ROUNDTRP.D81\""
else
  echo "==> lege D81 auf die SD (mega65_ftp)"
  "$FTP" -e -y -c "put $D81 ROUNDTRP.D81"
fi

set -- --mount ROUNDTRP.D81 --preload-bin 0x050000 "$BLOB" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

n=17; [ "$fasl" = "1" ] && n=10
echo "==> starte Disk-Roundtrip-Selftest (erwartet: gruener Rahmen, pass $n/$n)"
sh scripts/run-on-mega65.sh "$@"
