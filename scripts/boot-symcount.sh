#!/bin/sh
# Exact host-side boot symbol count. Build profile-specific eval_init and report sym_count.
# This deterministic, device-free check accounts for symbols omitted by manifest estimates.
#
# Usage: sh scripts/boot-symcount.sh <profile> [min-runtime-headroom]
#   profile = einsuite | default (selects EXTRA_CFLAGS and blob suite)
set -e
cc="${HOSTCC:-cc}"
profile="${1:-einsuite}"
min_rt="${2:-0}"
out=build/equivalence
mkdir -p "$out"

grabflags() { sed -n "s/^$1 ?= //p" Makefile | head -1; }
case "$profile" in
  einsuite) FLAGS=$(grabflags M65VMSTDLIB_EINSUITE_EXTRA_CFLAGS)
            SUITE=tests/bytecode/stdlib/p0-stdlib-einsuite-subset.json ;;
  default)  FLAGS=$(grabflags M65VMSTDLIB_EXTRA_CFLAGS)
            SUITE=tests/bytecode/stdlib/p0-stdlib-subset.json ;;
  *) echo "unknown profile: $profile (einsuite|default)"; exit 2 ;;
esac

# Run only C-side eval_init because blob boot is device assembly. Reuse profile flags without
# EMBED_DMA, which is the device DMA/assembly path.
$cc -std=c99 -Wall -Wno-unused-function \
  -DLISP65_VM $(echo "$FLAGS" | sed 's/-DLISP65_SYMPOOL_EXT//; s/-DLISP65_SYMVAL_EXT//; s/-DLISP65_NAMEOFF_EXT//; s/-DLISP65_STDLIB_EXT_METADATA//; s/-DLISP65_STDLIB_EXTERNAL_BLOB//') \
  -Isrc -Ibuild/bytecode \
  scripts/boot-symcount-main.c \
  src/eval.c src/vm.c src/mem.c src/symbol.c src/reader.c \
  src/printer.c src/interrupt.c src/screen.c src/io.c \
  -o "$out/boot-symcount" 2>"$out/boot-symcount.build.log" || {
    echo "boot-symcount: Build fehlgeschlagen ($profile) — siehe $out/boot-symcount.build.log"
    grep -iE "error|undefined" "$out/boot-symcount.build.log" | head -6
    exit 2
  }

echo "== Profil: $profile =="
"$out/boot-symcount" "$min_rt"
