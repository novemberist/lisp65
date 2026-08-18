#!/bin/sh
# Physical current-carrier terminal-ingress row; OWNER-PHYSICAL-INPUT-ONLY.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_defstruct_terminal_ingress_sister.py
CROSSING=tools/host-lisp/c2_live_repl_ftp_crossing_gate.py
DEPLOY=build/c2.3/defstruct-terminal-ingress-sister-link92/deployment.json
OUT=${OUT:-build/c2.3/defstruct-terminal-ingress-sister-link92/device}
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
python3 "$CROSSING" check
if [ "$ACTION" = dry-run ]; then
  echo "STAGE: cold BASIC -> one FTP lifetime uploads/readbacks both D81s -> product mount last"
  echo "BOOT: 45s quiet -> exact banner/prompt -> owner Freezer-mounts DFTLIB92.D81"
  echo "OWNER: confirm-library -> type require physically; after visible t call arm-after-require"
  echo "ARM: read boot witness -> reset/arm record and progress -> 1s raster rearm"
  echo "OWNER: type defstruct physically; call wait-defstruct immediately after RETURN"
  echo "WAIT: 180s with zero automated target access; inspect physical screen once"
  echo "CAPTURE: exactly one stop; tuple + stable record + progress + source planes"
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
  ftp_bundle_under_basic "$product" "$library" DFTING92.D81 DFTLIB92.D81
  # PRODUCT-LIVE-BEGIN: no FTP token or helper call is permitted below.
  sleep 45
  screen diagnostic-boot
  grep -Fq 'WORKBENCH 1.4.0' "$OUT/diagnostic-boot.txt"
  grep -Fq 'lisp65>' "$OUT/diagnostic-boot.txt"
  : > "$OUT/freezer-mount-required"
  # PRODUCT-LIVE-END
  echo "STAGE GREEN. In Freezer mount DFTLIB92.D81 on drive 8, return with F3, then run confirm-library."
  exit 0
fi

if [ "$ACTION" = confirm-library ]; then
  [ -e "$OUT/freezer-mount-required" ] && [ ! -e "$OUT/library-owner-confirmed" ] || {
    echo "defstruct Freezer confirmation state invalid" >&2; exit 3;
  }
  # OWNER-FREEZER-MOUNT: physical idle-REPL media change; deliberately no FTP.
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
  # This monitor crossing is before the measured form.  Its first source-less
  # return is followed by a full second of owned rasters before owner input.
  readback 0x0000c07a 1 "$OUT/entry-witness.bin"
  printf '\104' > "$OUT/entry-witness-authority.bin"
  cmp "$OUT/entry-witness-authority.bin" "$OUT/entry-witness.bin"
  record_reset=$(jq -r '.record.reset.path' "$DEPLOY")
  record_arm=$(jq -r '.record.arm.path' "$DEPLOY")
  progress_reset=$(jq -r '.progress.reset.path' "$DEPLOY")
  run_m65 -H -@ "$record_reset@0x0000c03f"
  run_m65 -H -@ "$record_arm@0x0000c03f"
  run_m65 -H -@ "$progress_reset@0x0000b5ac"
  readback 0x0000c03f 65 "$OUT/record-armed.bin"
  readback 0x0000b5ac 24 "$OUT/progress-armed.bin"
  python3 - "$OUT/record-armed.bin" "$record_reset" "$OUT/progress-armed.bin" "$progress_reset" <<'PY'
from pathlib import Path
import sys
record = bytearray(Path(sys.argv[2]).read_bytes()); record[0] = 0xA1
assert Path(sys.argv[1]).read_bytes() == bytes(record)
assert Path(sys.argv[3]).read_bytes() == Path(sys.argv[4]).read_bytes()
PY
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
  quiet=$(jq -r '.quiet_floor_seconds' "$DEPLOY")
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
  readback 0x0000c03f 65 "$OUT/record-1.bin"
  sleep 2; readback 0x0000c03f 65 "$OUT/record-2.bin"
  sleep 2; readback 0x0000c03f 65 "$OUT/record-3.bin"
  cmp "$OUT/record-1.bin" "$OUT/record-2.bin"
  cmp "$OUT/record-2.bin" "$OUT/record-3.bin"
  readback 0x0000b582 66 "$OUT/progress.bin"
  readback 0x00020000 65536 "$OUT/bank2-source.bin"
  readback 0x00050000 50816 "$OUT/c2d-reset-domain.bin"
  readback 0x087fe000 8192 "$OUT/window-physical.bin"
  echo "CAPTURE COMPLETE. CPU remains stopped; do not resume or improvise."
  exit 0
fi
