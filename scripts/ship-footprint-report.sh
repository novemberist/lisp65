#!/bin/sh
# Write a compact footprint report from ship manifests.
set -eu

cd "$(dirname "$0")/.."

ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
out="${SHIP_FOOTPRINT_REPORT:-$ship_dir/footprint-report.txt}"
mkdir -p "$(dirname "$out")"

value() {
  key="$1"
  file="$2"
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$file"
}

profile_line() {
  name="$1"
  manifest="$2"
  heap="$(value heap_cells "$manifest")"
  bytes="$(value prg_bytes "$manifest")"
  libs="$(value ship_libs "$manifest")"
  printf '%-24s %10s %10s  %s\n' "$name" "$heap" "$bytes" "$libs"
}

chunk_stats() {
  manifest="$1"
  awk '
    /^L[0-9][0-9] / {
      chunks++;
      total += $2;
      if ($2 > max) max = $2;
    }
    /^LOADALL / { loadall = $2 }
    END {
      printf "chunks=%d\nloadall_bytes=%d\nmax_chunk_bytes=%d\ntotal_chunk_bytes=%d\n",
        chunks, loadall, max, total;
    }
  ' "$manifest"
}

chunk_sources() {
  manifest="$1"
  awk '
    /^L[0-9][0-9] / {
      sources = $3
      sub(/^sources=/, "", sources)
      printf "%s bytes=%s sources=%s\n", $1, $2, sources
    }
  ' "$manifest"
}

source_chunk_summary() {
  manifest="$1"
  awk '
    /^L[0-9][0-9] / {
      sources = $3
      sub(/^sources=/, "", sources)
      n = split(sources, parts, ",")
      for (i = 1; i <= n; i++) {
        source = parts[i]
        if (!(source in seen)) {
          order[++ordered] = source
          seen[source] = 1
        }
        chunks[source]++
        bytes[source] += $2
      }
    }
    END {
      for (i = 1; i <= ordered; i++) {
        source = order[i]
        printf "%s chunks=%d chunk_bytes=%d\n", source, chunks[source], bytes[source]
      }
    }
  ' "$manifest"
}

matrix_manifests() {
  find "$ship_dir/matrix" -mindepth 2 -maxdepth 2 -name manifest.txt -print 2>/dev/null | sort
}

f011_dump_line() {
  dump="$1"
  marker="$2"
  if [ ! -f "$dump" ]; then
    return 1
  fi
  strings -a "$dump" | awk -v marker="$marker" 'index($0, marker) == 1 { line = $0 } END { if (line) print line; else exit 1 }'
}

f011_dump_lines() {
  dump="$1"
  marker="$2"
  if [ ! -f "$dump" ]; then
    return 1
  fi
  strings -a "$dump" | awk -v marker="$marker" '
    index($0, marker " ") == 1 && substr($0, length(marker) + 2, 1) ~ /[0-9]/ {
      print
      found = 1
    }
    END { exit found ? 0 : 1 }
  '
}

mask_names() {
  mask="$1"
  mode="$2"
  shift 2
  bit=1
  out=""
  for name in "$@"; do
    has=$((mask & bit))
    if { [ "$mode" = bound ] && [ "$has" -ne 0 ]; } ||
       { [ "$mode" = missing ] && [ "$has" -eq 0 ]; }; then
      if [ -n "$out" ]; then
        out="$out,$name"
      else
        out="$name"
      fi
    fi
    bit=$((bit * 2))
  done
  if [ -n "$out" ]; then
    printf '%s\n' "$out"
  else
    printf 'none\n'
  fi
}

{
  echo "lisp65 ship footprint report"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo
  echo "Bank-0 embedded profiles:"
  printf '%-24s %10s %10s  %s\n' "profile" "heap_cells" "prg_bytes" "ship_libs"
  printf '%-24s %10s %10s  %s\n' "-------" "----------" "---------" "---------"
  if [ -f "$ship_dir/manifest.txt" ]; then
    profile_line default "$ship_dir/manifest.txt"
  fi
  for manifest in $(matrix_manifests); do
    profile="$(basename "$(dirname "$manifest")")"
    profile_line "$profile" "$manifest"
  done
  echo
  echo "F011 disk-load profile:"
  printf '%-24s %10s %10s  %s\n' "profile" "heap_cells" "prg_bytes" "extra_cflags"
  printf '%-24s %10s %10s  %s\n' "-------" "----------" "---------" "------------"
  if [ -f "$ship_dir/f011-manifest.txt" ]; then
    printf '%-24s %10s %10s  %s\n' \
      "f011-repl" \
      "$(value heap_cells "$ship_dir/f011-manifest.txt")" \
      "$(value prg_bytes "$ship_dir/f011-manifest.txt")" \
      "$(value extra_cflags "$ship_dir/f011-manifest.txt")"
  fi
  echo
  echo "Full stdlib D81:"
  if [ -f "$ship_dir/stdlib-d81-manifest.txt" ]; then
    echo "d81=$(value d81 "$ship_dir/stdlib-d81-manifest.txt")"
    echo "d81_bytes=$(value d81_bytes "$ship_dir/stdlib-d81-manifest.txt")"
    echo "chunk_max=$(value chunk_max "$ship_dir/stdlib-d81-manifest.txt")"
    echo "manual_load_commands=$(value manual_load_commands "$ship_dir/stdlib-d81-manifest.txt")"
    echo "manual_load_command_count=$(value manual_load_command_count "$ship_dir/stdlib-d81-manifest.txt")"
    chunk_stats "$ship_dir/stdlib-d81-manifest.txt"
    echo "chunk_sources:"
    chunk_sources "$ship_dir/stdlib-d81-manifest.txt"
    echo "source_chunks:"
    source_chunk_summary "$ship_dir/stdlib-d81-manifest.txt"
  else
    echo "missing=$ship_dir/stdlib-d81-manifest.txt"
  fi
  echo
  echo "Full stdlib source budget:"
  python3 tools/host-lisp/stdlib_source_budget.py \
    lib/prelude-m1.lisp \
    lib/stdlib-strings.lisp \
    lib/stdlib-sequences.lisp \
    lib/stdlib-math.lisp \
    lib/stdlib-plists.lisp \
    lib/stdlib-format.lisp \
    lib/stdlib-control.lisp
  echo
  echo "Full stdlib symbol budget:"
  python3 tools/host-lisp/stdlib_symbol_budget.py \
    --max-sym "${STDLIB_SYMBOL_MAX_SYM:-384}" \
    --namepool "${STDLIB_SYMBOL_NAMEPOOL:-3072}" \
    lib/prelude-m1.lisp \
    lib/stdlib-strings.lisp \
    lib/stdlib-sequences.lisp \
    lib/stdlib-math.lisp \
    lib/stdlib-plists.lisp \
    lib/stdlib-format.lisp \
    lib/stdlib-control.lisp
  echo
  echo "Full stdlib function budget:"
  python3 tools/host-lisp/stdlib_function_budget.py \
    lib/prelude-m1.lisp \
    lib/stdlib-strings.lisp \
    lib/stdlib-sequences.lisp \
    lib/stdlib-math.lisp \
    lib/stdlib-plists.lisp \
    lib/stdlib-format.lisp \
    lib/stdlib-control.lisp
  echo
  echo "Full stdlib function chunks:"
  if [ -d "$ship_dir/stdlib-chunks" ]; then
    python3 tools/host-lisp/stdlib_function_chunks.py --names "$ship_dir/stdlib-chunks"
  else
    echo "missing=$ship_dir/stdlib-chunks"
  fi
  echo
  echo "F011 stdlib smoke diagnostics:"
  dump="${F011_STDLIB_DUMP:-build/f011-autoload-dump.bin}"
  echo "dump=$dump"
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-loaded:")"; then
    echo "loaded=${line#lisp65 f011-stdlib-loaded: }"
  else
    echo "loaded=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib:")"; then
    echo "chunks=${line#lisp65 f011-stdlib: }"
  else
    echo "chunks=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-bindings:")"; then
    echo "bindings=${line#lisp65 f011-stdlib-bindings: }"
  else
    echo "bindings=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-sentinels:")"; then
    echo "sentinels=${line#lisp65 f011-stdlib-sentinels: }"
  else
    echo "sentinels=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-fns:")"; then
    echo "functions=${line#lisp65 f011-stdlib-fns: }"
  else
    echo "functions=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-free-cell-sample:")"; then
    echo "free_cell_sample=${line#lisp65 f011-stdlib-free-cell-sample: }"
  else
    echo "free_cell_sample=missing"
  fi
  echo "layers:"
  layers="$(f011_dump_lines "$dump" "lisp65 f011-stdlib-layer:" || true)"
  if [ -n "$layers" ]; then
    printf '%s\n' "$layers" | sed 's/^/layer=/'
  else
    echo "layer=missing"
  fi
  if line="$(f011_dump_line "$dump" "lisp65 f011-stdlib-layer:")"; then
    str11="$(printf '%s\n' "$line" | awk '{ for (i = 1; i < NF; i++) if ($i == "str11") { print $(i + 1); exit } }')"
    if [ -n "$str11" ]; then
      echo "str11_mask=$str11"
      echo "str11_names=%char-list=,string=,%char-list<"
      echo "str11_bound=$(mask_names "$str11" bound "%char-list=" "string=" "%char-list<")"
      echo "str11_missing=$(mask_names "$str11" missing "%char-list=" "string=" "%char-list<")"
    else
      echo "str11_mask=missing"
    fi
  else
    echo "str11_mask=missing"
  fi
  echo "notes:"
  echo "- Lower heap_cells in embedded profiles means more linker headroom, not proven runtime reserve."
  echo "- The F011 profile intentionally ships without embedded Prelude/Stdlib; it loads chunks from D81."
} > "$out"

{
  echo
  echo "F011 binding gap summary:"
  python3 tools/host-lisp/f011_binding_gap.py "$out"
} >> "$out"

echo "==> geschrieben: $out"
