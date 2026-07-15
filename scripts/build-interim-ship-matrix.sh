#!/bin/sh
# Build the documented historical Bank-0 interim-ship profiles as separate artifacts.
set -eu

cd "$(dirname "$0")/.."
ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"

run_profile() {
  name="$1"
  heap="$2"
  libs="$3"
  out_dir="$ship_dir/matrix/$name"

  echo "==> Matrix-Profil $name (HEAP_CELLS=$heap)"
  SHIP_DIR="$out_dir" \
    SHIP_PRG="$out_dir/lisp65-$name.prg" \
    SHIP_D81="$out_dir/lisp65-$name.d81" \
    SHIP_MANIFEST="$out_dir/manifest.txt" \
    SHIP_LIBS="$libs" \
    SHIP_HEAP_CELLS="$heap" \
    sh scripts/build-interim-ship.sh
}

run_profile "strings-math" 820 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-math.lisp"
run_profile "strings-plists" 802 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-plists.lisp"
run_profile "strings-math-plists" 748 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-math.lisp lib/stdlib-plists.lisp"
run_profile "strings-format" 620 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-format.lisp"
run_profile "strings-control" 650 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-control.lisp"
run_profile "strings-sequences" 773 "lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-sequences.lisp"

echo "==> Matrix geschrieben: $ship_dir/matrix"
