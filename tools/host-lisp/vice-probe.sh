#!/bin/sh
# VICE fidelity probe: run the byte-identical original LISP 64 headlessly in x64sc,
# type probe forms through -keybuf, and take a screenshot. The original uses KERNAL
# input, so -keybuf works unlike the v2 CIA scanner.
#
# Important: write lowercase letters in the probe file because VICE -keybuf sends
# uppercase letters as shifted graphics. Lowercase host input produces unshifted
# uppercase PETSCII, which the LISP reader recognizes correctly as symbols.
#
# Usage: vice-probe.sh <probe-file> <screenshot.png>
#   REF_PRG   (default build/reference/lisp64.prg)
#   VICE      (default x64sc)
#   CYCLES    (default 70000000)
#   TIMEOUT   (default 90)
set -eu

[ "$#" -eq 2 ] || { echo "usage: $0 <probe-file> <screenshot.png>" >&2; exit 2; }
probe="$1"; shot="$2"
prg="${REF_PRG:-build/reference/lisp64.prg}"
emu="${VICE:-x64sc}"
cyc="${CYCLES:-70000000}"
tmo="${TIMEOUT:-90}"

case "$prg"  in /*) ;; *) prg="$(pwd)/$prg" ;; esac
case "$shot" in /*) ;; *) shot="$(pwd)/$shot" ;; esac
mkdir -p "$(dirname "$shot")"; rm -f "$shot"

kb="$(cat "$probe")"
set +e
timeout "$tmo" "$emu" -default -silent +sound -sounddev dummy \
  -autostartprgmode 1 -autostart "$prg" \
  -keybuf "$kb" -limitcycles "$cyc" \
  -exitscreenshot "$shot" >/dev/null 2>&1
set -e
[ -f "$shot" ] && echo "Screenshot: $shot" || { echo "kein Screenshot erzeugt" >&2; exit 1; }
