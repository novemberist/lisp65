#!/bin/sh
# Probe whether the full Lisp stdlib can still be embedded into the Bank-0 REPL.
set -eu

cd "$(dirname "$0")/.."

profiles="${FULL_EMBED_FIT_PROFILES:-880 512 384 256 192 128}"
ship_libs="${SHIP_LIBS:-lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-sequences.lisp lib/stdlib-math.lisp lib/stdlib-plists.lisp lib/stdlib-format.lisp lib/stdlib-control.lisp}"
legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
out="${FULL_EMBED_FIT_REPORT:-$legacy_ship_dir/full-embed-fit-report.txt}"
base_dir="${FULL_EMBED_FIT_DIR:-$legacy_ship_dir/full-embed-fit}"
default_heap="${FULL_EMBED_FIT_DEFAULT_HEAP:-880}"
max_sym="${SHIP_MAX_SYM:-384}"
namepool="${SHIP_NAMEPOOL:-3072}"

mkdir -p "$(dirname "$out")" "$base_dir" build

overflow_bytes() {
  log="$1"
  awk '
    /overflowed by/ {
      for (i = 1; i <= NF; i++) {
        if ($i == "by" && (i + 1) <= NF) {
          print $(i + 1)
          exit
        }
      }
    }
  ' "$log"
}

manifest_value() {
  manifest="$1"
  key="$2"
  awk -F= -v key="$key" '$1 == key { print $2; exit }' "$manifest"
}

{
  echo "lisp65 full embedded stdlib fit report"
  echo "profiles=$profiles"
  echo "ship_libs=$ship_libs"
  echo "default_heap=$default_heap"
  echo "max_sym=$max_sym"
  echo "namepool=$namepool"
  echo
  printf '%-8s %-8s %-12s %-10s %-10s %s\n' \
    "heap" "status" "overflow" "prg_bytes" "d81_bytes" "artifact"
  printf '%-8s %-8s %-12s %-10s %-10s %s\n' \
    "----" "------" "--------" "---------" "---------" "--------"
} > "$out"

default_status="missing"
default_overflow="missing"
min_link_heap=""
min_link_prg_bytes=""
min_link_artifact=""

for heap in $profiles; do
  dir="$base_dir/heap-$heap"
  prg="$dir/lisp65-full-embed-$heap.prg"
  d81="$dir/lisp65-full-embed-$heap.d81"
  manifest="$dir/manifest.txt"
  log="$dir/build.log"

  mkdir -p "$dir"
  rm -f "$prg" "$d81" "$manifest" "$log"

  status=OK
  if ! SHIP_DIR="$dir" \
      SHIP_PRG="$prg" \
      SHIP_D81="$d81" \
      SHIP_MANIFEST="$manifest" \
      SHIP_LIBS="$ship_libs" \
      SHIP_HEAP_CELLS="$heap" \
      SHIP_MAX_SYM="$max_sym" \
      SHIP_NAMEPOOL="$namepool" \
      sh scripts/build-interim-ship.sh > "$log" 2>&1; then
    status=FAIL
  fi

  if [ "$status" = "OK" ]; then
    overflow="-"
    prg_bytes="$(manifest_value "$manifest" prg_bytes)"
    d81_bytes="$(manifest_value "$manifest" d81_bytes)"
    artifact="$prg"
    if [ -z "$min_link_heap" ] || [ "$heap" -lt "$min_link_heap" ]; then
      min_link_heap="$heap"
      min_link_prg_bytes="$prg_bytes"
      min_link_artifact="$artifact"
    fi
  else
    overflow="$(overflow_bytes "$log")"
    [ -n "$overflow" ] || overflow="unknown"
    prg_bytes="-"
    d81_bytes="-"
    artifact="$log"
  fi

  if [ "$heap" = "$default_heap" ]; then
    default_status="$status"
    default_overflow="$overflow"
  fi

  printf '%-8s %-8s %-12s %-10s %-10s %s\n' \
    "$heap" "$status" "$overflow" "$prg_bytes" "$d81_bytes" "$artifact" >> "$out"
done

if [ -n "$min_link_heap" ]; then
  min_link_status="OK"
else
  min_link_status="missing"
  min_link_heap="missing"
  min_link_prg_bytes="missing"
  min_link_artifact="missing"
fi

if [ "$default_status" = "OK" ]; then
  fit_status="default-fits"
elif [ "$min_link_status" = "OK" ]; then
  fit_status="bank0-footprint-blocked"
else
  fit_status="no-linkable-profile"
fi

{
  echo
  echo "Full embedded stdlib fit summary:"
  echo "status=$fit_status"
  echo "default_heap=$default_heap"
  echo "default_status=$default_status"
  echo "default_overflow=$default_overflow"
  echo "min_link_heap=$min_link_heap"
  echo "min_link_prg_bytes=$min_link_prg_bytes"
  echo "min_link_artifact=$min_link_artifact"
} >> "$out"

echo "==> geschrieben: $out"
