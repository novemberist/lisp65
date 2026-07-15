#!/bin/sh
# Build the lisp65 REPL with prelude and deploy it to the MEGA65 through Etherload.
# Put the machine in remote mode with SHIFT+POUND until the power LED blinks green/yellow.
#
# Usage: scripts/deploy-repl.sh (the script changes to the repository root itself).
set -e
cd "$(dirname "$0")/.."

CLANG=tools/llvm-mos/bin/mos-mega65-clang
ETHERLOAD=tools/m65tools/etherload
OUT=build/lisp65-repl-prelude-mega65.prg

mkdir -p build
echo "==> build $OUT"
# -DHEAP_CELLS=1200: Bank 0 (~44 KiB) is tight with REPL, prelude, strings, and load buffer.
# A smaller heap leaves roughly 1.7 KiB of soft stack and avoids a prelude-load crash.
"$CLANG" -Os -DHEAP_CELLS=1200 -DLISP65_REPL -DLISP65_WITH_PRELUDE -Isrc src/*.c -o "$OUT"
echo "    $(stat -c%s "$OUT") Bytes"

echo "==> find MEGA65"
"$ETHERLOAD" --discover || {
    echo "MEGA65 not found. Is remote mode active? (SHIFT+POUND, green/yellow blinking LED)" >&2
    exit 1
}

# Use only -r: load and RUN through the BASIC stub's correct BANK 0:SYS path, without mode reset.
# Do not use -5: a C64/MEGA65 mode reset reboots and discards the freshly loaded PRG.
# It leaves RUN executing empty memory ("ready. / run").
# Do not use -j: a direct jump skips the stub's BANK 0 and corrupts the screen.
# Prerequisite: the machine shows MEGA65 READY and remote mode is armed with SHIFT+POUND.
echo "==> upload and RUN without mode reset"
"$ETHERLOAD" -r "$OUT"
echo "done."
