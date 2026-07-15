#!/bin/sh
# Pack standalone bytecode library EXT images into a D81.
set -eu

c1541_bin="${C1541:-c1541}"
out="${BYTECODE_LIB_D81:-build/bytecode/libs/bytecode-libs.d81}"
files="${BYTECODE_LIB_FILES:-build/bytecode/libs/testlib.ext.bin:TESTLIB}"
manifest="${BYTECODE_LIB_MANIFEST:-$(dirname "$out")/bytecode-libs-d81-manifest.txt}"
log="${TMPDIR:-/tmp}/lisp65-bytecode-lib-d81-c1541.log"
list_log="${TMPDIR:-/tmp}/lisp65-bytecode-lib-d81-list.log"

command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }
mkdir -p "$(dirname "$out")" "$(dirname "$manifest")"

set -- -format "L65LIB,65" d81 "$out"
for spec in $files; do
  case "$spec" in
    *:*) src=${spec%%:*}; disk_name=${spec#*:} ;;
    *) src=$spec; disk_name=$(basename "$spec" | sed 's/\..*$//') ;;
  esac
  [ -f "$src" ] || { echo "Fehler: Bytecode-Lib fehlt: $src" >&2; exit 3; }
  if [ ${#disk_name} -gt 16 ]; then
    echo "Fehler: D81-Dateiname zu lang (>16): $disk_name" >&2
    exit 3
  fi
  set -- "$@" -write "$src" "$disk_name,s"
done

"$c1541_bin" "$@" >"$log" 2>&1 || {
  cat "$log" >&2
  exit 3
}

"$c1541_bin" "$out" -list >"$list_log" 2>&1 || {
  cat "$list_log" >&2
  exit 3
}

{
  echo "lisp65 bytecode lib D81"
  echo "d81=$out"
  echo "d81_bytes=$(wc -c < "$out" | tr -d ' ')"
  echo "files=$files"
  for spec in $files; do
    case "$spec" in
      *:*) src=${spec%%:*}; disk_name=${spec#*:} ;;
      *) src=$spec; disk_name=$(basename "$spec" | sed 's/\..*$//') ;;
    esac
    bytes=$(wc -c < "$src" | tr -d ' ')
    sha=$(sha256sum "$src" | awk '{ print $1 }')
    echo "$disk_name $src bytes=$bytes sha256=$sha"
    if ! grep -qi "\"$disk_name\"" "$list_log"; then
      echo "Fehler: D81 enthaelt erwartete Lib nicht: $disk_name" >&2
      exit 3
    fi
  done
} >"$manifest"

echo "==> geschrieben: $out"
echo "==> manifest: $manifest"
