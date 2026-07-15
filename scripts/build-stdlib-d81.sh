#!/bin/sh
# Package the complete Lisp stdlib as small LOAD files in a D81 image.
set -eu

cd "$(dirname "$0")/.."

c1541_bin="${C1541:-c1541}"
legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
out="${STDLIB_D81:-$legacy_ship_dir/lisp65-stdlib.d81}"
chunk_dir="${STDLIB_CHUNK_DIR:-$legacy_ship_dir/stdlib-chunks}"
chunk_max="${STDLIB_CHUNK_MAX:-512}"
libs="${STDLIB_LIBS:-lib/prelude-m1.lisp lib/stdlib-strings.lisp lib/stdlib-sequences.lisp lib/stdlib-math.lisp lib/stdlib-plists.lisp lib/stdlib-format.lisp lib/stdlib-control.lisp}"
manifest="${STDLIB_MANIFEST:-$legacy_ship_dir/stdlib-d81-manifest.txt}"
load_commands="${STDLIB_LOAD_COMMANDS:-$legacy_ship_dir/load-stdlib-commands.txt}"
chunk_manifest_tmp="$(dirname "$manifest")/.stdlib-chunks-manifest.tmp"
list_log="/tmp/lisp65-stdlib-d81-list.log"

command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }

for lib in $libs; do
  [ -f "$lib" ] || { echo "Fehler: Bibliotheksdatei nicht gefunden: $lib" >&2; exit 3; }
done

mkdir -p "$(dirname "$out")" "$(dirname "$load_commands")" "$chunk_dir"

echo "==> splitte Stdlib in <= $chunk_max Byte LOAD-Dateien"
python3 scripts/split-lisp-source.py --out-dir "$chunk_dir" --max-bytes "$chunk_max" $libs > "$chunk_manifest_tmp"
mv "$chunk_manifest_tmp" "$chunk_dir/manifest.txt"

echo "==> schreibe sequenzielle Load-Kommandos"
: > "$load_commands"
for chunk in "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  printf '(load "%s")\n' "$disk_name" >> "$load_commands"
done

echo "==> packe $out"
rm -f "$out"
set -- -format "LISP65,65" d81 "$out"
for chunk in "$chunk_dir"/LOADALL "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  set -- "$@" -write "$chunk" "$disk_name,s"
done
"$c1541_bin" "$@" >/tmp/lisp65-stdlib-d81-c1541.log 2>&1 || {
  cat /tmp/lisp65-stdlib-d81-c1541.log >&2
  exit 1
}

echo "==> verifiziere D81-Directory"
"$c1541_bin" "$out" -list > "$list_log" 2>&1 || {
  cat "$list_log" >&2
  exit 1
}
for chunk in "$chunk_dir"/LOADALL "$chunk_dir"/L??; do
  [ -f "$chunk" ] || continue
  disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
  if ! grep -q "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwarteten Chunk nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 1
  fi
done

cat > "$manifest" <<EOF
lisp65 full stdlib D81
d81=$out
d81_bytes=$(stat -c%s "$out")
chunk_dir=$chunk_dir
chunk_max=$chunk_max
libs=$libs
load_entry=LOADALL
load_command=(load "loadall")
manual_load_commands=$load_commands
manual_load_command_count=$(wc -l < "$load_commands" | tr -d ' ')

chunks:
$(cat "$chunk_dir/manifest.txt")
EOF

echo "==> geschrieben:"
echo "    $out"
echo "    $manifest"
echo "    $load_commands"
