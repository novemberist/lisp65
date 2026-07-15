#!/bin/sh
# Build the historical interim lisp65 artifact: a native MEGA65 REPL PRG with embedded prelude,
# plus a D81 containing the same PRG.
set -eu

cd "$(dirname "$0")/.."

cc="${CC_M65:-tools/llvm-mos/bin/mos-mega65-clang}"
c1541_bin="${C1541:-c1541}"
ship_dir="${SHIP_DIR:-${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}}"
# Historical MVP default is prelude-only: Bank-0 capacity binds the complete prelude, while later
# Lisp stdlib layers exhaust the heap and abort loading. HEAP=1400 reserves REPL cells; the five
# native string primitives remain present independently. Override the library set with SHIP_LIBS.
ship_libs="${SHIP_LIBS:-${PRELUDE_LISP:-lib/prelude-m1.lisp}}"
with_prelude="${SHIP_WITH_PRELUDE:-1}"
heap_cells="${SHIP_HEAP_CELLS:-1400}"
max_sym="${SHIP_MAX_SYM:-256}"
namepool="${SHIP_NAMEPOOL:-2048}"
extra_cflags="${SHIP_EXTRA_CFLAGS:-}"
prg="${SHIP_PRG:-$ship_dir/lisp65-interim.prg}"
d81="${SHIP_D81:-$ship_dir/lisp65-interim.d81}"
manifest="${SHIP_MANIFEST:-$ship_dir/manifest.txt}"
combined="$ship_dir/stdlib-interim.lisp"
ship_header="$ship_dir/prelude_gen.h"
src_header="src/prelude_gen.h"
restore_lisp="${PRELUDE_LISP:-lib/prelude-m1.lisp}"

[ -x "$cc" ] || { echo "Fehler: Compiler nicht gefunden/ausfuehrbar: $cc" >&2; exit 3; }
command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }

mkdir -p "$ship_dir" build

had_src_header=0
if [ -f "$src_header" ]; then
  had_src_header=1
fi
restore_src_header() {
  if [ "$had_src_header" = "1" ]; then
    python3 scripts/embed-prelude.py "$restore_lisp" "$src_header"
  else
    rm -f "$src_header"
  fi
}
trap restore_src_header EXIT

prelude_cflag=""
if [ "$with_prelude" = "1" ]; then
  echo "==> buendle Stdlib: $ship_libs"
  : > "$combined"
  for lib in $ship_libs; do
    [ -f "$lib" ] || { echo "Fehler: Bibliotheksdatei nicht gefunden: $lib" >&2; exit 3; }
    cat "$lib" >> "$combined"
    printf '\n' >> "$combined"
  done

  echo "==> generiere $src_header aus $combined"
  python3 scripts/embed-prelude.py "$combined" "$src_header"
  cp "$src_header" "$ship_header"
  prelude_cflag="-DLISP65_WITH_PRELUDE"
else
  echo "==> baue ohne eingebettete Prelude/Stdlib (SHIP_WITH_PRELUDE=0)"
fi

echo "==> baue $prg"
"$cc" -Os -Wall -DHEAP_CELLS="$heap_cells" -DMAX_SYM="$max_sym" -DNAMEPOOL="$namepool" \
  $extra_cflags -DLISP65_REPL $prelude_cflag -Isrc src/*.c -o "$prg"
printf '    %s bytes\n' "$(stat -c%s "$prg")"

echo "==> packe $d81"
rm -f "$d81"
"$c1541_bin" -format "LISP65,65" d81 "$d81" -write "$prg" LISP65 >/tmp/lisp65-c1541.log 2>&1 || {
  cat /tmp/lisp65-c1541.log >&2
  exit 1
}

{
  echo "lisp65 interim ship"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "with_prelude=$with_prelude"
  echo "ship_libs=$ship_libs"
  echo "combined=$combined"
  echo "ship_header=$ship_header"
  echo "heap_cells=$heap_cells"
  echo "max_sym=$max_sym"
  echo "namepool=$namepool"
  echo "extra_cflags=$extra_cflags"
  echo "prg=$prg"
  echo "prg_bytes=$(stat -c%s "$prg")"
  echo "d81=$d81"
  echo "d81_bytes=$(stat -c%s "$d81")"
  echo
  echo "deploy:"
  echo "  tools/m65tools/etherload -r $prg"
  echo "  scripts/hw-smoke-interim.sh --dry-run"
} > "$manifest"

echo "==> geschrieben:"
echo "    $prg"
echo "    $d81"
echo "    $manifest"
