#!/bin/sh
# Builds an xemu SD image whose default D81 autoloads a F011 smoke PRG.
set -eu

cd "$(dirname "$0")/.."

source_sd="${F011_AUTOLOAD_SOURCE_SD:-$HOME/.local/share/xemu-lgb/mega65/mega65.img}"
out="${F011_AUTOLOAD_SDIMG:-build/f011/lisp65-f011-autoload-sd.img}"
d81="${F011_AUTOLOAD_D81:-build/f011/lisp65-f011-autoload.d81}"
prg="${F011_AUTOLOAD_PRG:-build/lisp65-mega65-f011-load-test.prg}"
demo_src="${F011_DEMO_SRC:-scripts/f011-testlib.lisp}"
program_name="${F011_AUTOLOAD_PROGRAM_NAME:-lisp65}"
demo_name="${F011_DEMO_NAME:-testlib}"
extra_dir="${F011_AUTOLOAD_EXTRA_DIR:-}"
defd81_sector="${F011_DEFD81_SECTOR:-11552}"
manifest="${F011_AUTOLOAD_MANIFEST:-build/f011/autoload-manifest.txt}"

c1541_bin="${C1541:-c1541}"
command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }
[ -f "$source_sd" ] || { echo "Fehler: XEMU-System-SD fehlt: $source_sd" >&2; exit 3; }
[ -f "$prg" ] || { echo "Fehler: PRG fehlt: $prg" >&2; exit 3; }
[ -f "$demo_src" ] || { echo "Fehler: Demo-Lib fehlt: $demo_src" >&2; exit 3; }
if [ -n "$extra_dir" ]; then
  [ -d "$extra_dir" ] || { echo "Fehler: Extra-D81-Verzeichnis fehlt: $extra_dir" >&2; exit 3; }
fi

mkdir -p "$(dirname "$out")" "$(dirname "$d81")"
rm -f "$out" "$d81"

echo "==> erzeuge Autoload-D81 $d81"
set -- -format "LISP65,65" d81 "$d81" \
  -write "$prg" "$program_name" \
  -write "$demo_src" "$demo_name,s"
if [ -n "$extra_dir" ]; then
  for chunk in "$extra_dir"/LOADALL "$extra_dir"/L??; do
    [ -f "$chunk" ] || continue
    disk_name=$(basename "$chunk" | tr '[:upper:]' '[:lower:]')
    set -- "$@" -write "$chunk" "$disk_name,s"
  done
fi
"$c1541_bin" "$@" >/tmp/lisp65-f011-autoload-c1541.log 2>&1 || {
    cat /tmp/lisp65-f011-autoload-c1541.log >&2
    exit 1
  }

echo "==> kopiere XEMU-System-SD $source_sd -> $out"
cp --reflink=auto --sparse=always "$source_sd" "$out"

echo "==> injiziere Autoload-D81 fuer -defd81fromsd bei SD-Sektor $defd81_sector"
dd if="$d81" of="$out" bs=512 seek="$defd81_sector" conv=notrunc status=none

cat > "$manifest" <<EOF
lisp65 F011 autoload image
image=$out
image_bytes=$(stat -c%s "$out")
source_sd=$source_sd
defd81_sector=$defd81_sector
d81=$d81
prg=$prg
program_name=$program_name
demo_src=$demo_src
demo_name=$demo_name
extra_dir=$extra_dir

xemu:
  xmega65 -sdimg $out -defd81fromsd -autoload -headless -testing -sleepless -besure -fastboot
EOF

echo "==> geschrieben:"
echo "    $out"
echo "    $d81"
echo "    $manifest"
