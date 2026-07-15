#!/bin/sh
# Build a D81 containing readable demo sources plus preallocated FASL slots.
set -eu

cd "$(dirname "$0")/.."

c1541_bin="${C1541:-c1541}"
out="${DEMO_SUITE_D81:-build/demos/lisp65-demo-suite.d81}"
manifest="${DEMO_SUITE_MANIFEST:-build/demos/demo-suite-manifest.txt}"
workdir="${DEMO_SUITE_WORKDIR:-build/demos}"
slot_bytes="${DEMO_SUITE_FASL_SLOT_BYTES:-8192}"
include_ide="${DEMO_SUITE_INCLUDE_IDE_LIB:-1}"
ide_lib="${DEMO_SUITE_IDE_LIB:-build/bytecode/libs/ide.ext.bin}"
idex_lib="${DEMO_SUITE_IDEX_LIB:-build/bytecode/libs/idex.ext.bin}"
m65d_lib="${DEMO_SUITE_M65D_LIB:-build/bytecode/libs/m65d.ext.bin}"
slot_file="$workdir/fasl-slot.bin"
list_log="${TMPDIR:-/tmp}/lisp65-demo-suite-d81-list.log"
c1541_log="${TMPDIR:-/tmp}/lisp65-demo-suite-d81-c1541.log"

sources="
demos/demo-index.lisp:dindex
demos/d00-simplify.lisp:dsimp
demos/d01-strings.lisp:dstr
demos/d02-lambda.lisp:dlam
demos/d03-screen.lisp:dscr
demos/d04-adventure.lisp:dadv
demos/d05-ide-buffer.lisp:dide
demos/d06-numbers.lisp:dnum
"

slots="
fsimp
fstr
flam
fscr
fadv
fide
fnum
"

command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }
mkdir -p "$(dirname "$out")" "$(dirname "$manifest")" "$workdir"

for spec in $sources; do
  src=${spec%%:*}
  disk_name=${spec#*:}
  [ -f "$src" ] || { echo "Fehler: Demo-Quelle fehlt: $src" >&2; exit 3; }
  if [ ${#disk_name} -gt 16 ]; then
    echo "Fehler: D81-Dateiname zu lang (>16): $disk_name" >&2
    exit 3
  fi
done

for disk_name in $slots; do
  if [ ${#disk_name} -gt 16 ]; then
    echo "Fehler: FASL-Slotname zu lang (>16): $disk_name" >&2
    exit 3
  fi
done

if [ "$include_ide" = "1" ]; then
  [ -f "$ide_lib" ] || { echo "Fehler: IDE-Lib fehlt: $ide_lib" >&2; exit 3; }
  [ -f "$idex_lib" ] || { echo "Fehler: IDEX-Lib fehlt: $idex_lib" >&2; exit 3; }
  [ -f "$m65d_lib" ] || { echo "Fehler: M65D-Lib fehlt: $m65d_lib" >&2; exit 3; }
fi

dd if=/dev/zero of="$slot_file" bs="$slot_bytes" count=1 status=none

rm -f "$out"
set -- -format "L65DEMO,65" d81 "$out"
if [ "$include_ide" = "1" ]; then
  set -- "$@" -write "$ide_lib" "ide,s"
  set -- "$@" -write "$idex_lib" "idex,s"
  set -- "$@" -write "$m65d_lib" "m65d,s"
fi
for spec in $sources; do
  src=${spec%%:*}
  disk_name=${spec#*:}
  set -- "$@" -write "$src" "$disk_name,s"
done
for disk_name in $slots; do
  set -- "$@" -write "$slot_file" "$disk_name,s"
done

"$c1541_bin" "$@" >"$c1541_log" 2>&1 || {
  cat "$c1541_log" >&2
  exit 3
}

"$c1541_bin" "$out" -list >"$list_log" 2>&1 || {
  cat "$list_log" >&2
  exit 3
}

for spec in $sources; do
  disk_name=${spec#*:}
  if ! grep -qi "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwartete Quelle nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 3
  fi
done
for disk_name in $slots; do
  if ! grep -qi "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwarteten FASL-Slot nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 3
  fi
done
if [ "$include_ide" = "1" ] && ! grep -qi "\"ide\"" "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete IDE-Lib nicht: ide" >&2
  cat "$list_log" >&2
  exit 3
fi
if [ "$include_ide" = "1" ] && ! grep -qi "\"idex\"" "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete IDEX-Lib nicht: idex" >&2
  cat "$list_log" >&2
  exit 3
fi
if [ "$include_ide" = "1" ] && ! grep -qi "\"m65d\"" "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete M65D-Lib nicht: m65d" >&2
  cat "$list_log" >&2
  exit 3
fi

{
  echo "lisp65 demo suite D81"
  echo "d81=$out"
  echo "d81_bytes=$(wc -c < "$out" | tr -d ' ')"
  echo "fasl_slot_bytes=$slot_bytes"
  echo "include_ide_lib=$include_ide"
  if [ "$include_ide" = "1" ]; then
    echo "ide_lib=$ide_lib"
    echo "ide_lib_bytes=$(wc -c < "$ide_lib" | tr -d ' ')"
    echo "ide_lib_sha256=$(sha256sum "$ide_lib" | awk '{ print $1 }')"
    echo "idex_lib=$idex_lib"
    echo "idex_lib_bytes=$(wc -c < "$idex_lib" | tr -d ' ')"
    echo "idex_lib_sha256=$(sha256sum "$idex_lib" | awk '{ print $1 }')"
    echo "m65d_lib=$m65d_lib"
    echo "m65d_lib_bytes=$(wc -c < "$m65d_lib" | tr -d ' ')"
    echo "m65d_lib_sha256=$(sha256sum "$m65d_lib" | awk '{ print $1 }')"
  fi
  echo
  echo "sources:"
  for spec in $sources; do
    src=${spec%%:*}
    disk_name=${spec#*:}
    echo "  $disk_name $src bytes=$(wc -c < "$src" | tr -d ' ') sha256=$(sha256sum "$src" | awk '{ print $1 }')"
  done
  echo
  echo "fasl_slots:"
  for disk_name in $slots; do
    echo "  $disk_name bytes=$slot_bytes"
  done
  echo
  echo "manual_compile_commands:"
  echo "  (compile-file \"dsimp\" \"fsimp\") ; then (load \"fsimp\") (demo-simplify-run)"
  echo "  (compile-file \"dstr\" \"fstr\")   ; then (load \"fstr\")  (demo-strings-run)"
  echo "  (compile-file \"dlam\" \"flam\")   ; then (load \"flam\")  (demo-lambda-run)"
  echo "  (compile-file \"dscr\" \"fscr\")   ; then (load \"fscr\")  (demo-screen-run)"
  echo "  (compile-file \"dadv\" \"fadv\")   ; then (load \"fadv\")  (demo-adv-run)"
  echo "  (load-lib \"ide\")                ; Dev-Core only, before IDE demo"
  echo "  (load-lib \"idex\")               ; optional IDE comfort tier"
  echo "  (load-lib \"m65d\")               ; optional COW persistence core"
  echo "  (compile-file \"dide\" \"fide\")   ; then (load \"fide\")  (demo-ide-run)"
  echo "  (compile-file \"dnum\" \"fnum\")   ; then (load \"fnum\")  (demo-numbers-run)"
  echo
  echo "c1541_directory:"
  sed 's/^/  /' "$list_log"
} >"$manifest"

echo "==> geschrieben:"
echo "    $out"
echo "    $manifest"
