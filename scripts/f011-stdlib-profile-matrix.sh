#!/bin/sh
# Probe F011 stdlib smoke behavior across tight Bank-0 heap/root profiles.
set -eu

cd "$(dirname "$0")/.."

profiles="${F011_STDLIB_PROFILE_MATRIX:-1254:256 1275:128 1300:96 1300:64}"
legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
out="${F011_STDLIB_PROFILE_REPORT:-$legacy_ship_dir/f011-stdlib-profile-matrix.txt}"
mkdir -p "$(dirname "$out")" build

ship_libs="${SHIP_LIBS:-lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-sequences.lisp lib/stdlib-math.lisp lib/stdlib-plists.lisp lib/stdlib-format.lisp lib/stdlib-control.lisp}"

dump_line() {
  dump="$1"
  marker="$2"
  [ -f "$dump" ] || return 1
  strings -a "$dump" | awk -v marker="$marker" '
    index($0, marker) == 1 { line = $0 }
    END { if (line) print line; else exit 1 }
  '
}

dump_value() {
  dump="$1"
  marker="$2"
  if line="$(dump_line "$dump" "$marker")"; then
    printf '%s\n' "${line#"$marker" }"
  else
    printf 'missing\n'
  fi
}

expected_function_symbols() {
  python3 tools/host-lisp/stdlib_function_budget.py $ship_libs | awk -F= '
    $1 == "expected_function_symbols" { print $2; found = 1 }
    END { if (!found) exit 1 }
  '
}

is_uint() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

runtime_function_count() {
  value="$1"
  set -- $value
  if is_uint "${1:-}"; then
    printf '%s\n' "$1"
  else
    printf 'missing\n'
  fi
}

function_gap() {
  expected="$1"
  runtime="$2"
  if is_uint "$expected" && is_uint "$runtime"; then
    printf '%s\n' "$((expected - runtime))"
  else
    printf 'missing\n'
  fi
}

expected_fns="$(expected_function_symbols)"

{
  echo "lisp65 f011 stdlib profile matrix"
  echo "profiles=$profiles"
  echo "expected_function_symbols=$expected_fns"
  echo
  printf '%-10s %-8s %-8s %-8s %-8s %-16s %-10s %-16s %-8s %-16s %s\n' \
    "heap" "roots" "status" "loaded" "chunks" "bindings" "sentinels" "functions" "fn_gap" "free_cells" "dump"
  printf '%-10s %-8s %-8s %-8s %-8s %-16s %-10s %-16s %-8s %-16s %s\n' \
    "----" "-----" "------" "------" "------" "--------" "---------" "---------" "------" "----------" "----"
} > "$out"

for profile in $profiles; do
  heap="${profile%%:*}"
  roots="${profile#*:}"
  dump="build/f011-stdlib-profile-${heap}-${roots}.bin"
  log="build/f011-stdlib-profile-${heap}-${roots}.log"

  rm -f "$dump" "$log"
  status=OK
  if ! DUMP="$dump" make xemu-f011-stdlib-smoke \
      M65F011_STDLIB_SMOKE_HEAP="$heap" \
      M65F011_STDLIB_SMOKE_EXTRA_CFLAGS="-DGC_ROOTS=$roots" \
      > "$log" 2>&1; then
    status=FAIL
  fi

  loaded="$(dump_value "$dump" "lisp65 f011-stdlib-loaded:")"
  chunks="$(dump_value "$dump" "lisp65 f011-stdlib:")"
  bindings="$(dump_value "$dump" "lisp65 f011-stdlib-bindings:")"
  sentinels="$(dump_value "$dump" "lisp65 f011-stdlib-sentinels:")"
  functions="$(dump_value "$dump" "lisp65 f011-stdlib-fns:")"
  runtime_fns="$(runtime_function_count "$functions")"
  fn_gap="$(function_gap "$expected_fns" "$runtime_fns")"
  free_cells="$(dump_value "$dump" "lisp65 f011-stdlib-free-cell-sample:")"

  printf '%-10s %-8s %-8s %-8s %-8s %-16s %-10s %-16s %-8s %-16s %s\n' \
    "$heap" "$roots" "$status" "$loaded" "$chunks" "$bindings" "$sentinels" "$functions" "$fn_gap" "$free_cells" "$dump" \
    >> "$out"
done

echo "==> geschrieben: $out"
