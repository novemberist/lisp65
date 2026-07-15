#!/bin/sh
# Create a small SD image with a FAT32 partition and an internal D81 file.
# This covers the xemu/F011 gap so tests do not depend on an external drive-8 mount.
set -eu

cd "$(dirname "$0")/.."

out="${F011_SDIMG:-build/f011/lisp65-f011-sd.img}"
legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
d81="${F011_D81:-$legacy_ship_dir/lisp65-interim.d81}"
size_mb="${F011_SDIMG_MB:-64}"
partition_lba="${F011_PARTITION_LBA:-2048}"
partition_offset=$((partition_lba * 512))

command -v sfdisk >/dev/null 2>&1 || { echo "Fehler: sfdisk nicht gefunden" >&2; exit 3; }
command -v mformat >/dev/null 2>&1 || { echo "Fehler: mformat nicht gefunden" >&2; exit 3; }
command -v mcopy >/dev/null 2>&1 || { echo "Fehler: mcopy nicht gefunden" >&2; exit 3; }
command -v mdir >/dev/null 2>&1 || { echo "Fehler: mdir nicht gefunden" >&2; exit 3; }

[ -f "$d81" ] || {
  echo "Fehler: D81 fehlt: $d81" >&2
  echo "Hinweis: zuerst 'make interim-ship' ausfuehren oder F011_D81 setzen." >&2
  exit 3
}

mkdir -p "$(dirname "$out")"
rm -f "$out"

echo "==> erzeuge rohes SD-Image $out (${size_mb} MiB)"
dd if=/dev/zero of="$out" bs=1M count="$size_mb" status=none

echo "==> schreibe MBR/FAT32-Partition ab LBA $partition_lba"
printf '%s\n' "${partition_lba},,c,*" | sfdisk "$out" >/tmp/lisp65-sfdisk.log 2>&1 || {
  cat /tmp/lisp65-sfdisk.log >&2
  exit 1
}

echo "==> formatiere FAT32"
MTOOLS_SKIP_CHECK=1 mformat -F -i "$out@@$partition_offset" -v LISP65 ::

echo "==> kopiere D81 ins SD-Image"
MTOOLS_SKIP_CHECK=1 mcopy -o -i "$out@@$partition_offset" "$d81" ::LISP65.D81

echo "==> verifiziere FAT-Directory"
MTOOLS_SKIP_CHECK=1 mdir -i "$out@@$partition_offset" ::

cat > "$(dirname "$out")/manifest.txt" <<EOF
lisp65 F011 offline SD image
image=$out
image_bytes=$(stat -c%s "$out")
partition_lba=$partition_lba
partition_offset=$partition_offset
d81_source=$d81
d81_name=LISP65.D81

xemu sketch:
  xmega65 -sdimg $out -headless -testing -sleepless -besure -fastboot
EOF

echo "==> geschrieben: $out"
