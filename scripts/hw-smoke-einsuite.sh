#!/bin/sh
# lisp65 — single-suite smoke test on physical MEGA65 hardware (Lane K, 2026-07-06).
# Builds the self-test PRG (scripts/einsuite-hw-selftest-main.c) ad hoc with the
# Reuse single-suite profile flags without editing the Makefile, verify the Etherload invariant
# that the PRG ends below $C000, and run blob + PRG through run-on-mega65.sh.
#
# Expected on device: green border and "einsuite hw-selftest PASS 10/10".
#                      red border + FAIL line naming the first failed check
#
# Usage: sh scripts/hw-smoke-einsuite.sh [--strip|--full] [--dry-run] [--no-build] [--ip <ipv6%iface>]
#   --strip  = M3 convergence profile (LISP65_TREEWALK_STRIP + EVAL_PRIMS): +3 checks
#              (defmacro without eval_env, eval from compiled code) -> pass 13/13
#   --full   = M4 profile (strip + disk load + SAVE + native bulk render), with the same 13
#              checks; disk round trips require a separately mounted D81 session
set -eu
cd "$(dirname "$0")/.."

CLANG=tools/llvm-mos/bin/mos-mega65-clang
PRG=build/lisp65-einsuite-hw-selftest.prg
BLOB=build/bytecode/stdlib-p0.ext.bin

dry_run=0; build=1; ip=""; strip=0; full=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --strip) strip=1; PRG=build/lisp65-einsuite-strip-hw-selftest.prg ;;
    --full) full=1; strip=1; PRG=build/lisp65-einsuite-full-hw-selftest.prg ;;
    --ip) shift; ip="$1" ;;
    *) echo "unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$build" = "1" ]; then
  echo "==> baue Ein-Suite (Blob im passenden Profil) + Selftest-PRG"
  if [ "$full" = "1" ]; then
    make mvp-vm-stdlib-einsuite-full >/dev/null    # Full-Suite-Blob (Kopplung!)
  else
    make mvp-vm-stdlib-einsuite >/dev/null
  fi
  FLAGS=$(sed -n 's/^M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS ?= //p' Makefile | head -1)
  HEAP=$(sed -n 's/^M65VMSTDLIB_EINSUITE_HEAP ?= //p' Makefile | head -1)
  STRIPFLAGS=""
  [ "$strip" = "1" ] && STRIPFLAGS="-DLISP65_TREEWALK_STRIP -DLISP65_EVAL_PRIMS"
  if [ "$full" = "1" ]; then
    # Mirror Makefile filter-out: bulk capability is native, not supplied by the blob.
    FLAGS=$(printf '%s' "$FLAGS" | sed 's/-DLISP65_SCREEN_BULK_P_IN_STDLIB//; s/-DMAX_SYM=481/-DMAX_SYM=560/; s/-DVM_DIR_MAX=416/-DVM_DIR_MAX=512/')
    STRIPFLAGS="$STRIPFLAGS -DMEGA65_F011_LOAD -DLISP65_DISK_LIBS -DMEGA65_F011_WRITE -DIO_BUF_MAX=1 -DLISP65_SCREEN_WRITE_STRING"
  fi
  # Match the default self-test target: runtime without main.c, plus VM and blob C.
  # Do not set LISP65_REPL; main() is the self-test.
  # shellcheck disable=SC2086
  "$CLANG" -Oz -Wall -DLISP65_VM -DLISP65_EMBED_STDLIB -DLISP65_EMBED_DMA \
    -DHEAP_CELLS="${HEAP:-48}" $FLAGS $STRIPFLAGS -Isrc -Ibuild/bytecode \
    src/eval.c src/interrupt.c src/io.c src/mem.c src/printer.c src/reader.c \
    src/repl.c src/screen.c src/symbol.c src/vm_embed.c src/vm.c \
    build/bytecode/stdlib-p0.c scripts/einsuite-hw-selftest-main.c -o "$PRG"
  sz=$(stat -c%s "$PRG")
  end=$((0x2001 + sz - 2))
  printf '    %s: %d B, prg_file_end $%04x' "$PRG" "$sz" "$end"
  if [ "$end" -ge $((0xC000)) ]; then
    printf ' -- ÜBER der etherload-Invariante $C000, ABBRUCH\n'
    exit 3
  fi
  printf ' (< $C000 OK)\n'
fi

[ -f "$PRG" ] || { echo "Fehler: PRG fehlt: $PRG" >&2; exit 3; }
[ -f "$BLOB" ] || { echo "Fehler: Blob fehlt: $BLOB" >&2; exit 3; }

set -- --preload-bin 0x050000 "$BLOB" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$PRG"

n=10; [ "$strip" = "1" ] && n=13
echo "==> starte Ein-Suite-HW-Selftest (erwartet: gruener Rahmen, pass $n/$n)"
sh scripts/run-on-mega65.sh "$@"
