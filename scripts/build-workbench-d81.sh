#!/bin/sh
# Build the Workbench MVP D81: IDE bytecode library plus preallocated compile targets.
set -eu

cd "$(dirname "$0")/.."

c1541_bin="${C1541:-c1541}"
out="${WORKBENCH_SHIP_D81:-build/ship/lisp65-workbench.d81}"
manifest="${WORKBENCH_SHIP_D81_MANIFEST:-build/ship/workbench-d81-manifest.txt}"
slot_bytes="${WORKBENCH_SHIP_SLOT_BYTES:-8192}"
ide_lib="${WORKBENCH_SHIP_IDE_LIB:-build/bytecode/libs/ide.ext.bin}"
idex_lib="${WORKBENCH_SHIP_IDEX_LIB:-build/bytecode/libs/idex.ext.bin}"
m65d_lib="${WORKBENCH_SHIP_M65D_LIB:-build/bytecode/libs/m65d.ext.bin}"
slots="${WORKBENCH_SHIP_SLOTS:-demo work an out fasl0 fasl1 fasl2}"
demo_source="${WORKBENCH_SHIP_DEMO_SOURCE:-demos/d06-numbers.lisp}"
demo_slot="${WORKBENCH_SHIP_DEMO_SLOT:-demo}"
list_log="${TMPDIR:-/tmp}/lisp65-workbench-d81-list.log"
c1541_log="${TMPDIR:-/tmp}/lisp65-workbench-d81-c1541.log"

cleanup_workdir=0
if [ -n "${WORKBENCH_SHIP_WORKDIR:-}" ]; then
  workdir="$WORKBENCH_SHIP_WORKDIR"
else
  workdir="$(mktemp -d "${TMPDIR:-/tmp}/lisp65-workbench-d81.XXXXXX")"
  cleanup_workdir=1
fi
slot_file="$workdir/workbench-slot.bin"
demo_file="$workdir/workbench-demo-source.seq"
cleanup() {
  if [ "$cleanup_workdir" = 1 ]; then rm -rf "$workdir"; fi
}
trap cleanup EXIT HUP INT TERM

command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }
[ -f "$ide_lib" ] || { echo "Fehler: IDE-Lib fehlt: $ide_lib" >&2; exit 3; }
[ -f "$idex_lib" ] || { echo "Fehler: IDEX-Lib fehlt: $idex_lib" >&2; exit 3; }
[ -f "$m65d_lib" ] || { echo "Fehler: M65D-Lib fehlt: $m65d_lib" >&2; exit 3; }
[ -z "$demo_source" ] || [ -f "$demo_source" ] || { echo "Fehler: Demo-Quelle fehlt: $demo_source" >&2; exit 3; }
mkdir -p "$(dirname "$out")" "$(dirname "$manifest")" "$workdir"

for disk_name in $slots; do
  if [ ${#disk_name} -gt 16 ]; then
    echo "Fehler: D81-Dateiname zu lang (>16): $disk_name" >&2
    exit 3
  fi
done

dd if=/dev/zero of="$slot_file" bs="$slot_bytes" count=1 status=none
if [ -n "$demo_source" ]; then
  demo_bytes=$(wc -c < "$demo_source" | tr -d ' ')
  if [ "$demo_bytes" -gt "$slot_bytes" ]; then
    echo "Fehler: Demo-Quelle groesser als Slot ($demo_bytes > $slot_bytes): $demo_source" >&2
    exit 3
  fi
  cp "$demo_source" "$demo_file"
fi

rm -f "$out"
# Keep IDE first; Find/Write minibuffers filter system and compile-target
# entries, while compile commands still see the full directory.
set -- -format "L65WB,65" d81 "$out" -write "$ide_lib" "ide,s" -write "$idex_lib" "idex,s" -write "$m65d_lib" "m65d,s"
for disk_name in $slots; do
  if [ -n "$demo_source" ] && [ "$disk_name" = "$demo_slot" ]; then
    set -- "$@" -write "$demo_file" "$disk_name,s"
  else
    set -- "$@" -write "$slot_file" "$disk_name,s"
  fi
done

"$c1541_bin" "$@" >"$c1541_log" 2>&1 || {
  cat "$c1541_log" >&2
  exit 3
}

"$c1541_bin" "$out" -list >"$list_log" 2>&1 || {
  cat "$list_log" >&2
  exit 3
}

if ! grep -qi '"ide"' "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete IDE-Lib nicht: ide" >&2
  cat "$list_log" >&2
  exit 3
fi
if ! grep -qi '"idex"' "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete IDEX-Lib nicht: idex" >&2
  cat "$list_log" >&2
  exit 3
fi
if ! grep -qi '"m65d"' "$list_log"; then
  echo "Fehler: D81 enthaelt erwartete M65D-Lib nicht: m65d" >&2
  cat "$list_log" >&2
  exit 3
fi
for disk_name in $slots; do
  if ! grep -qi "\"$disk_name\"" "$list_log"; then
    echo "Fehler: D81 enthaelt erwarteten Compile-Slot nicht: $disk_name" >&2
    cat "$list_log" >&2
    exit 3
  fi
done

{
  echo "lisp65 workbench MVP D81"
  echo "d81=$out"
  echo "d81_bytes=$(wc -c < "$out" | tr -d ' ')"
  echo "ide_lib=$ide_lib"
  echo "ide_lib_bytes=$(wc -c < "$ide_lib" | tr -d ' ')"
  echo "ide_lib_sha256=$(sha256sum "$ide_lib" | awk '{ print $1 }')"
  echo "idex_lib=$idex_lib"
  echo "idex_lib_bytes=$(wc -c < "$idex_lib" | tr -d ' ')"
  echo "idex_lib_sha256=$(sha256sum "$idex_lib" | awk '{ print $1 }')"
  echo "m65d_lib=$m65d_lib"
  echo "m65d_lib_bytes=$(wc -c < "$m65d_lib" | tr -d ' ')"
  echo "m65d_lib_sha256=$(sha256sum "$m65d_lib" | awk '{ print $1 }')"
  echo "slot_bytes=$slot_bytes"
  echo "slots=$slots"
  if [ -n "$demo_source" ]; then
    echo "demo_slot=$demo_slot"
    echo "demo_source=$demo_source"
    echo "demo_source_bytes=$(wc -c < "$demo_source" | tr -d ' ')"
    echo "demo_source_sha256=$(sha256sum "$demo_source" | awk '{ print $1 }')"
    echo "demo_source_padded=no"
  fi
  echo
  echo "usage:"
  echo "  (edit)                                      ; load IDE from disk and enter editor"
  echo "  (load-lib \"ide\")                            ; expose REPL persistence helpers without entering editor"
  echo "  (load-lib \"idex\")                           ; optional region/search/word/page/M-x comfort tier"
  echo "  (load-lib \"m65d\")                           ; optional COW persistence core (IDE auto-loads it)"
  echo "  (dir)                                       ; list visible D81 entries"
  echo
  echo "mvp_user_flow:"
  echo "  (load-file-to-buffer \"demo\" \"demo\")          ; read existing source slot into named buffer"
  echo "  (edit \"demo\")                               ; inspect/edit source, RUN/STOP returns to REPL"
  echo "  (save-buffer-to \"work\" \"demo\")              ; write named buffer into preallocated slot"
  echo "  (save-buffer-to \"newsrc\" \"demo\")            ; create or replace through COW persistence"
  echo "  (compile-buffer-to-lib \"fasl0\" \"demo\")      ; buffer -> L65M/FASL library slot"
  echo "  (load-lib \"fasl0\")                            ; load compiled library into the session"
  echo "  (demo-numbers-run)                          ; demo result => 42"
  echo
  echo "additional_commands:"
  echo "  (compile-file-to-lib \"demo\" \"fasl0\")        ; source slot -> L65M/FASL library slot"
  echo "  (compile-string \"(defun a()40)\" \"an\")       ; low-level string -> L65M/FASL slot"
  echo "  (compile-error)                              ; detail after failed compile-string"
  echo "  (load-lib \"an\")                             ; load compiled code from slot an"
  echo "  editor C-x C-k                              ; Compile+load current buffer to fasl0"
  echo
  echo "c1541_directory:"
  sed '/^OPENCBM:/d; s/^/  /' "$list_log"
} >"$manifest"

echo "==> geschrieben:"
echo "    $out"
echo "    $manifest"
