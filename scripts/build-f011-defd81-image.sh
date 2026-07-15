#!/bin/sh
# Builds an SD image for xemu's -defd81fromsd path.
set -eu

cd "$(dirname "$0")/.."

out="${F011_DEFD81_SDIMG:-build/f011/lisp65-f011-defd81-sd.img}"
d81="${F011_DEFD81_D81:-build/f011/lisp65-f011-load-test.d81}"
source_d81="${F011_DEFD81_SOURCE_D81:-}"
demo_src="${F011_DEMO_SRC:-scripts/f011-testlib.lisp}"
demo_name="${F011_DEMO_NAME:-testlib}"
size_mb="${F011_SDIMG_MB:-64}"
partition_lba="${F011_PARTITION_LBA:-2048}"
defd81_sector="${F011_DEFD81_SECTOR:-11552}"
partition_offset=$((partition_lba * 512))

c1541_bin="${C1541:-c1541}"
command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden" >&2; exit 3; }
command -v sfdisk >/dev/null 2>&1 || { echo "Fehler: sfdisk nicht gefunden" >&2; exit 3; }
command -v mformat >/dev/null 2>&1 || { echo "Fehler: mformat nicht gefunden" >&2; exit 3; }
command -v mcopy >/dev/null 2>&1 || { echo "Fehler: mcopy nicht gefunden" >&2; exit 3; }
command -v mdir >/dev/null 2>&1 || { echo "Fehler: mdir nicht gefunden" >&2; exit 3; }

mkdir -p "$(dirname "$out")" "$(dirname "$d81")"
rm -f "$out"

if [ -n "$source_d81" ]; then
  [ -f "$source_d81" ] || { echo "Fehler: Source-D81 fehlt: $source_d81" >&2; exit 3; }
  if [ "$source_d81" != "$d81" ]; then
    rm -f "$d81"
    cp "$source_d81" "$d81"
  fi
  echo "==> nutze vorbereitete D81 $d81"
else
  [ -f "$demo_src" ] || { echo "Fehler: Demo-Lib fehlt: $demo_src" >&2; exit 3; }
  rm -f "$d81"
  echo "==> erzeuge Test-D81 $d81 mit $demo_name"
  "$c1541_bin" -format "LISP65,65" d81 "$d81" -write "$demo_src" "$demo_name,s" >/tmp/lisp65-f011-c1541.log 2>&1 || {
    cat /tmp/lisp65-f011-c1541.log >&2
    exit 1
  }
fi

echo "==> erzeuge rohes SD-Image $out (${size_mb} MiB)"
dd if=/dev/zero of="$out" bs=1M count="$size_mb" status=none

echo "==> schreibe MBR/FAT32-Partition ab LBA $partition_lba"
printf '%s\n' "${partition_lba},,c,*" | sfdisk "$out" >/tmp/lisp65-f011-sfdisk.log 2>&1 || {
  cat /tmp/lisp65-f011-sfdisk.log >&2
  exit 1
}

echo "==> formatiere FAT32"
MTOOLS_SKIP_CHECK=1 mformat -F -i "$out@@$partition_offset" -v LISP65 ::

echo "==> kopiere D81 sichtbar ins FAT"
MTOOLS_SKIP_CHECK=1 mcopy -o -i "$out@@$partition_offset" "$d81" ::LISP65.D81

echo "==> injiziere D81 fuer -defd81fromsd bei SD-Sektor $defd81_sector"
dd if="$d81" of="$out" bs=512 seek="$defd81_sector" conv=notrunc status=none

echo "==> verifiziere FAT-Directory"
MTOOLS_SKIP_CHECK=1 mdir -i "$out@@$partition_offset" ::

cat > "$(dirname "$out")/defd81-manifest.txt" <<EOF
lisp65 F011 -defd81fromsd test image
image=$out
image_bytes=$(stat -c%s "$out")
partition_lba=$partition_lba
partition_offset=$partition_offset
defd81_sector=$defd81_sector
d81=$d81
source_d81=$source_d81
demo_src=$demo_src
demo_name=$demo_name

xemu:
  xmega65 -sdimg $out -defd81fromsd -headless -testing -sleepless -besure -fastboot
EOF

echo "==> geschrieben: $out"
