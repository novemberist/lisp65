#!/bin/sh
# One authorized terminal IRQ-origin row; OWNER-PHYSICAL-INPUT-ONLY.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_defstruct_irq_origin_contact.py
SISTER=tools/host-lisp/c2_defstruct_terminal_ingress_sister.py
DEPLOY=build/c2.3/defstruct-terminal-ingress-sister-link92/deployment.json
PATCH=build/c2.3/defstruct-irq-origin-contact/irq-origin-fail-capture.bin
RESET=build/c2.3/defstruct-irq-origin-contact/irq-origin-record-reset.bin
OUT=${OUT:-build/c2.3/defstruct-irq-origin-contact/device}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|stage|confirm-library|arm-after-require|wait-defstruct|capture) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-library|arm-after-require|wait-defstruct|capture>" >&2; exit 2 ;;
esac

python3 "$PY" check
python3 "$SISTER" check
if [ "$ACTION" = dry-run ]; then
  echo "STAGE: cold BASIC -> one FTP lifetime -> product mounted last -> 45s quiet"
  echo "OWNER: Freezer-mount DFTLIBOR.D81, require physically, then arm"
  echo "ARM: entry proof -> diagnostic-only 132-byte body + record -> readback -> 1s raster"
  echo "OWNER: defstruct physically -> 180s zero observation"
  echo "CAPTURE: one stop, one committed record read, CPU remains stopped"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
screen() {
  name=$1
  run_m65 --screenshot="$OUT/$name.png" > "$OUT/$name.ansi.txt"
  python3 - "$OUT/$name.ansi.txt" "$OUT/$name.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
ftp_bundle_under_basic() {
  product=$1 library=$2 product_remote=$3 library_remote=$4
  log=$OUT/media-upload.log
  : > "$log"
  # FTP-BASIC-ONLY-BEGIN: exactly one helper lifetime, before product boot.
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $product $product_remote" \
    -c "get $product_remote $OUT/product-readback.d81" \
    -c "put $library $library_remote" \
    -c "get $library_remote $OUT/library-readback.d81" \
    -c "mount $product_remote" -c exit > "$log" 2>&1 &
  # FTP-BASIC-ONLY-END
  pid=$! last=-1 progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
    if [ "$size" -ne "$last" ]; then last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2; return 124
    fi
  done
  wait "$pid"
  cmp "$product" "$OUT/product-readback.d81"
  cmp "$library" "$OUT/library-readback.d81"
}
stop_once() {
  python3 - "$DEVICE" "$OUT/final-stop.log" "$OUT/final-registers.json" <<'PY'
import json, os
from pathlib import Path
import sys, time
sys.path.insert(0, "tools/host-lisp")
import c2_defstruct_link71_slot39_failure_hold as serial
import c2_v16_corrected_view_contact as view
fd = os.open(sys.argv[1], os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
try:
    serial.configure_serial(fd)
    serial.slow_write(fd, b"t1\r")
    time.sleep(0.05)
    raw = view.command(fd, b"r", 0.05)
    Path(sys.argv[2]).write_bytes(raw)
    Path(sys.argv[3]).write_text(
        json.dumps(view.parse_registers(raw), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
finally:
    os.close(fd)
PY
}

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/contact.consumed" ] || { echo "contact already consumed" >&2; exit 3; }
  : > "$OUT/contact.consumed"
  run_m65 -F
  sleep 5
  screen fresh-basic
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  product=$(jq -r '.product_medium.path' "$DEPLOY")
  library=$(jq -r '.library_medium.path' "$DEPLOY")
  ftp_bundle_under_basic "$product" "$library" DFTINGOR.D81 DFTLIBOR.D81
  # PRODUCT-LIVE-BEGIN: no FTP token or helper call is permitted below.
  sleep 45
  screen diagnostic-boot
  grep -Fq 'WORKBENCH 1.4.0' "$OUT/diagnostic-boot.txt"
  grep -Fq 'lisp65>' "$OUT/diagnostic-boot.txt"
  : > "$OUT/freezer-mount-required"
  # PRODUCT-LIVE-END
  echo "STAGE GREEN. In Freezer mount DFTLIBOR.D81 on drive 8, return with F3, then run confirm-library."
  exit 0
fi

if [ "$ACTION" = confirm-library ]; then
  [ -e "$OUT/freezer-mount-required" ] && [ ! -e "$OUT/library-owner-confirmed" ] || {
    echo "defstruct Freezer confirmation state invalid" >&2; exit 3;
  }
  screen library-mounted
  grep -Fq 'WORKBENCH 1.4.0' "$OUT/library-mounted.txt"
  grep -Fq 'lisp65>' "$OUT/library-mounted.txt"
  : > "$OUT/library-owner-confirmed"
  echo "LIBRARY CONFIRMED. Type (require (quote defstruct)) physically; wait for visible t."
  exit 0
fi

if [ "$ACTION" = arm-after-require ]; then
  [ -e "$OUT/contact.consumed" ] && [ -e "$OUT/library-owner-confirmed" ] && [ ! -e "$OUT/armed" ] || {
    echo "arm-after-require state invalid" >&2; exit 3;
  }
  readback 0x0000c07a 1 "$OUT/entry-witness.bin"
  printf '\104' > "$OUT/entry-witness-authority.bin"
  cmp "$OUT/entry-witness-authority.bin" "$OUT/entry-witness.bin"
  run_m65 -H -@ "$PATCH@0x0000b3b0"
  run_m65 -H -@ "$RESET@0x0000c03f"
  readback 0x0000b3b0 132 "$OUT/capture-body-readback.bin"
  readback 0x0000c03f 65 "$OUT/record-reset-readback.bin"
  cmp "$PATCH" "$OUT/capture-body-readback.bin"
  cmp "$RESET" "$OUT/record-reset-readback.bin"
  run_m65 -r
  sleep 1
  : > "$OUT/armed"
  echo "ARM GREEN. Type (defstruct point x y) physically, then immediately run wait-defstruct."
  exit 0
fi

if [ "$ACTION" = wait-defstruct ]; then
  [ -e "$OUT/armed" ] && [ ! -e "$OUT/quiet-complete" ] || {
    echo "wait-defstruct state invalid" >&2; exit 3;
  }
  quiet=180
  # ACTIVE-DEFSTRUCT-BEGIN
  sleep "$quiet"
  # ACTIVE-DEFSTRUCT-END
  : > "$OUT/quiet-complete"
  echo "QUIET FLOOR COMPLETE. Inspect the physical screen once; if red, run capture."
  exit 0
fi

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/quiet-complete" ] && [ ! -e "$OUT/final-stop.log" ] || {
    echo "capture state invalid" >&2; exit 3;
  }
  stop_once
  readback 0x0000c03f 65 "$OUT/origin-record.bin"
  python3 "$PY" classify --record-file "$OUT/origin-record.bin" \
    --registers "$OUT/final-registers.json" > "$OUT/classification.json"
  cat "$OUT/classification.json"
  echo "CAPTURE COMPLETE. CPU remains stopped; do not resume or improvise."
  exit 0
fi
