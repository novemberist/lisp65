#!/bin/sh
# Read-only salvage of the live v1.5 D2 defun BADOPCODE state.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v150_name_freight_d2_badopcode.py
SESSION=build/c2.3/v1.5.0-name-freight-d2-d5
OUT=${OUT:-build/c2.3/v1.5.0-name-freight-d2-badopcode-capture}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|capture) ;;
  *) echo "usage: $0 <dry-run|capture>" >&2; exit 2 ;;
esac

python3 "$PY" check
[ "$(cat "$SESSION/next-row")" = d2-define-probe ] || {
  echo "D2 First Red is no longer the armed row" >&2; exit 3;
}
[ -e "$SESSION/row-d2-require-inspect-passed" ] && \
[ -e "$SESSION/row-d2-require-string-extra-passed" ] && \
grep -Fq '*** vm: bad bytecode' "$SESSION/row-d2-define-probe.txt" || {
  echo "bound D2 First Red state absent" >&2; exit 3;
}

if [ "$ACTION" = dry-run ]; then
  echo "READ-ONLY SALVAGE ONLY: existing live First Red, no replay"
  echo "ONE STOP: t1 plus register tuple; no resume"
  echo "READS: physical Bank 0, Bank 4 EXT/string windows, complete Bank 5 C2D domain"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
}
[ ! -e "$OUT/capture-complete" ] || {
  echo "D2 BADOPCODE salvage already consumed" >&2; exit 3;
}
mkdir -p "$OUT"

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}

# STOP-FIRST: no device read precedes the sole stop.  The serial helper records
# the complete tuple immediately after t1; every following operation is a
# physical read while the CPU remains stopped.
python3 - "$DEVICE" "$OUT/stop.log" "$OUT/registers.json" <<'PY'
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

readback 0x00000000 65536 "$OUT/physical-bank0.bin"
readback 0x00040000 27648 "$OUT/physical-bank4.bin"
readback 0x00050000 50816 "$OUT/physical-bank5.bin"

python3 - "$OUT" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
assert len((root / "physical-bank0.bin").read_bytes()) == 65536
assert len((root / "physical-bank4.bin").read_bytes()) == 27648
assert len((root / "physical-bank5.bin").read_bytes()) == 50816
registers = json.loads((root / "registers.json").read_text())
assert {"PC", "A", "X", "Y", "SP", "MAPH", "MAPL"} <= set(registers)
PY

: > "$OUT/capture-complete"
echo "D2 BADOPCODE READ-ONLY SALVAGE COMPLETE. CPU remains stopped; do not resume."
