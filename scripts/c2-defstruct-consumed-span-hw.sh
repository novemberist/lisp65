#!/bin/sh
# Closing defstruct consumed-span row; OWNER-PHYSICAL-INPUT-ONLY.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_defstruct_consumed_span.py
BASE_RUNNER=scripts/c2-defstruct-terminal-ingress-hw.sh
BASE_DEPLOY=build/c2.3/defstruct-terminal-ingress-sister-link92/deployment.json
DEPLOY=build/c2.3/defstruct-consumed-span-closing/deployment.json
OUT=${OUT:-build/c2.3/defstruct-consumed-span-closing/device}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}

case "$ACTION" in
  dry-run|stage|confirm-library|arm-after-require|wait-defstruct|capture) ;;
  *) echo "usage: $0 <dry-run|stage|confirm-library|arm-after-require|wait-defstruct|capture>" >&2; exit 2 ;;
esac

python3 "$PY" check
if [ "$ACTION" = dry-run ]; then
  echo "STAGE/BOOT: proven terminal-ingress choreography, full reset domain, Freezer library mount"
  echo "OWNER: require physically; after visible t call arm-after-require"
  echo "ARM: one pre-form monitor crossing installs target-owned two-span capture"
  echo "OWNER: defstruct physically; 180s with zero automated target access"
  echo "CAPTURE: exactly one stop; tuple first; only then span/ring/source-plane reads"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
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

if [ "$ACTION" = stage ] || [ "$ACTION" = confirm-library ] || \
   [ "$ACTION" = wait-defstruct ]; then
  OUT="$OUT" "$BASE_RUNNER" "$ACTION"
  exit 0
fi

if [ "$ACTION" = arm-after-require ]; then
  [ -e "$OUT/contact.consumed" ] && [ -e "$OUT/library-owner-confirmed" ] && \
    [ ! -e "$OUT/armed" ] || {
      echo "arm-after-require state invalid" >&2; exit 3;
    }
  # PRE-FORM-MONITOR-BEGIN: no target access follows after resume until capture.
  readback 0x0000c07a 1 "$OUT/entry-witness.bin"
  python3 - "$OUT/entry-witness.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes() == b"\x44"
PY
  record_reset=$(jq -r '.record.reset.path' "$BASE_DEPLOY")
  record_arm=$(jq -r '.record.arm.path' "$BASE_DEPLOY")
  run_m65 -H -@ "$record_reset@0x0000c03f"
  run_m65 -H -@ "$record_arm@0x0000c03f"
  run_m65 -H -@ \
    "build/c2.3/defstruct-consumed-span-closing/artifacts/dispatch-restore.bin@0x0000467d"
  run_m65 -H -@ \
    "build/c2.3/defstruct-consumed-span-closing/artifacts/terminal-and-span-capture.bin@0x0000b3b0"
  run_m65 -H -@ \
    "build/c2.3/defstruct-consumed-span-closing/artifacts/refill-capture-call.bin@0x0000c038"
  run_m65 -H -@ \
    "build/c2.3/defstruct-consumed-span-closing/artifacts/consumed-span-reset.bin@0x0000b582"
  readback 0x0000c03f 65 "$OUT/record-armed.bin"
  readback 0x0000467d 3 "$OUT/dispatch-armed.bin"
  readback 0x0000b3b0 154 "$OUT/code0-armed.bin"
  readback 0x0000c038 4 "$OUT/code1-armed.bin"
  readback 0x0000b582 66 "$OUT/spans-armed.bin"
  python3 - "$OUT/record-armed.bin" "$record_reset" \
      "$OUT/dispatch-armed.bin" "$OUT/code0-armed.bin" \
      "$OUT/code1-armed.bin" "$OUT/spans-armed.bin" <<'PY'
from pathlib import Path
import sys
record = bytearray(Path(sys.argv[2]).read_bytes())
record[0] = 0xA1
assert Path(sys.argv[1]).read_bytes() == bytes(record)
expected = (
    "dispatch-restore.bin", "terminal-and-span-capture.bin",
    "refill-capture-call.bin", "consumed-span-reset.bin")
root = Path("build/c2.3/defstruct-consumed-span-closing/artifacts")
for observed, name in zip(sys.argv[3:], expected, strict=True):
    assert Path(observed).read_bytes() == (root / name).read_bytes()
PY
  run_m65 -r
  sleep 1
  # PRE-FORM-MONITOR-END
  : > "$OUT/armed"
  echo "ARM GREEN. Type (defstruct point x y) physically, then immediately run wait-defstruct."
  exit 0
fi

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/quiet-complete" ] && [ ! -e "$OUT/final-stop.log" ] || {
    echo "capture state invalid" >&2; exit 3;
  }
  # Static artifacts/authority have already been reconstructed by PY check.
  stop_once
  # TUPLE-BEFORE-MEMORY: a mismatch aborts before the first target memory read.
  python3 - "$OUT/final-registers.json" "$DEPLOY" <<'PY'
import json
from pathlib import Path
import sys
registers = json.loads(Path(sys.argv[1]).read_text())
deploy = json.loads(Path(sys.argv[2]).read_text())
for name, expected in deploy["tuple_before_any_memory_read"].items():
    actual = registers[name]
    if actual.lower() != expected.lower():
        raise SystemExit(f"final tuple mismatch: {name}={actual}, expected {expected}")
PY
  readback 0x0000b582 66 "$OUT/consumed-spans.bin"
  readback 0x0000c03f 65 "$OUT/terminal-ring.bin"
  readback 0x00020000 65536 "$OUT/bank2-source.bin"
  readback 0x00050000 50816 "$OUT/c2d-reset-domain.bin"
  python3 "$PY" result-record
  python3 "$PY" result-check
  echo "CLOSING CAPTURE COMPLETE. CPU remains stopped; do not resume or improvise."
  exit 0
fi
