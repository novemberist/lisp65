#!/bin/sh
# Build a D81 containing the S5 source-on-disk stdlib/IDE source package.
set -eu

cd "$(dirname "$0")/.."

c1541_bin="${C1541:-c1541}"
suite="${S5_SOURCE_SUITE:-tests/bytecode/stdlib/p0-stdlib-subset.json}"
out="${S5_SOURCE_D81:-build/s5/lisp65-s5-source.d81}"
chunk_dir="${S5_SOURCE_CHUNK_DIR:-build/s5/source-chunks}"
bundle="${S5_SOURCE_BUNDLE:-build/s5/stdlib-source.lisp}"
package_manifest="${S5_SOURCE_PACKAGE_MANIFEST:-build/s5/source-package-manifest.txt}"
manifest="${S5_SOURCE_MANIFEST:-build/s5/source-d81-manifest.txt}"
chunk_max="${S5_SOURCE_CHUNK_MAX:-30000}"
list_log="${TMPDIR:-/tmp}/lisp65-s5-source-d81-list.log"
c1541_log="${TMPDIR:-/tmp}/lisp65-s5-source-d81-c1541.log"

command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }

mkdir -p "$(dirname "$out")" "$(dirname "$manifest")" "$chunk_dir"

python3 tools/host-lisp/s5_source_package.py \
  --suite "$suite" \
  --out-dir "$chunk_dir" \
  --bundle-out "$bundle" \
  --manifest-out "$package_manifest" \
  --chunk-max "$chunk_max"

rm -f "$out"
set -- -format "L65SRC,65" d81 "$out" -write "$bundle" "stdlib,s"
for chunk in "$chunk_dir"/LOADALL "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  set -- "$@" -write "$chunk" "$disk_name,s"
done

"$c1541_bin" "$@" >"$c1541_log" 2>&1 || {
  cat "$c1541_log" >&2
  exit 3
}

"$c1541_bin" "$out" -list >"$list_log" 2>&1 || {
  cat "$list_log" >&2
  exit 3
}

for disk_name in stdlib loadall; do
  if ! grep -qi "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwartete Datei nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 3
  fi
done
for chunk in "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  if ! grep -qi "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwarteten Chunk nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 3
  fi
done

chunk_names=""
for chunk in "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  chunk_names="${chunk_names}${chunk_names:+,}$disk_name"
done

{
  echo "lisp65 S5 source D81"
  echo "d81=$out"
  echo "d81_bytes=$(wc -c < "$out" | tr -d ' ')"
  echo "suite=$suite"
  echo "bundle=$bundle"
  echo "package_manifest=$package_manifest"
  echo "chunk_dir=$chunk_dir"
  echo "chunk_max=$chunk_max"
  grep -E '^(source_count|form_count|bundle_bytes|bundle_sha256|single_file_fits_disk_scratch|disk_scratch_max|chunk_count)=' "$package_manifest"
  echo "disk_files=stdlib,loadall${chunk_names:+,$chunk_names}"
  echo
  echo "notes:"
  echo "  stdlib is the complete concatenated source bundle for inspection/offline staging."
  echo "  l00.. chunks are <= chunk_max and stay within the current S5 disk scratch limit."
  echo "  Boot-time chunk consumption/dir lookup is Lane K; this target only packages source."
  echo
  echo "c1541_directory:"
  sed 's/^/  /' "$list_log"
} >"$manifest"

echo "==> geschrieben:"
echo "    $out"
echo "    $manifest"
echo "    $package_manifest"
