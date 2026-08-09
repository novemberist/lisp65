#!/bin/sh
# Non-promotable autonomous VM-progress appointment.  No monitor operation is
# permitted between the measured defstruct RETURN and the target-side samples.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_vm_progress_noninterference.py
DEPLOY=build/c2.3/v1.6-defstruct-vm-progress-noninterference/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-vm-progress-noninterference}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
RESET_DOMAIN_BYTES=50816
QUIET_SECONDS=120

case "$ACTION" in
  dry-run|stage|capture) ;;
  *) echo "usage: $0 <dry-run|stage|capture>" >&2; exit 2 ;;
esac

if [ "$ACTION" != dry-run ]; then
  [ "$(jq -r '.vm_progress.recontact_authorized' "$DEPLOY")" = true ] || {
    echo "v1.6 is finally parked; hardware contact forbidden" >&2
    exit 3
  }
fi

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
screen() {
  screen_name=$1
  run_m65 --screenshot="$OUT/${screen_name}.png" > "$OUT/${screen_name}.ansi.txt"
  python3 - "$OUT/${screen_name}.ansi.txt" "$OUT/${screen_name}.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
type_verified() {
  input_name=$1 input_form=$2
  run_m65 -t "$input_form"
  sleep 1
  screen "${input_name}-input"
  python3 - "$OUT/${input_name}-input.txt" "$input_form" <<'PY'
from pathlib import Path
import sys
lines = [line.strip().casefold() for line in
         Path(sys.argv[1]).read_text(errors="replace").splitlines()
         if line.strip()]
expected = sys.argv[2].strip().casefold()
assert any(line.endswith(expected) for line in lines)
assert not any("break" in line or "monitor commands" in line for line in lines)
PY
  run_m65 -t '~M'
}
stop_once() {
  python3 - "$DEVICE" "$OUT/final-stop.log" \
    "$OUT/runtime-window-tail.bin" "$OUT/runtime-low-state.bin" \
    "$OUT/final-registers.json" <<'PY'
import os
import json
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
    registers_raw = view.command(fd, b"r", 0.05)
    Path(sys.argv[2]).write_bytes(registers_raw)
    Path(sys.argv[5]).write_text(json.dumps(
        view.parse_registers(registers_raw), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    def read(address, size):
        result = bytearray()
        while len(result) < size:
            at = address + len(result)
            count = min(16, size - len(result))
            result.extend(view.parse_memory(
                view.command(fd, f"m{at:08x}".encode()), at, count))
        return bytes(result)
    Path(sys.argv[3]).write_bytes(read(0x087fff40, 0x50))
    Path(sys.argv[4]).write_bytes(read(0x00001ff8, 8))
finally:
    os.close(fd)
PY
}
ftp_medium() {
  medium=$1 remote=$2 log=$OUT/upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $medium $remote" -c "get $remote $OUT/readback.d81" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$! last=-1 progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
    if [ "$size" -ne "$last" ]; then last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  wait "$pid"
  cmp "$medium" "$OUT/readback.d81"
}

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" check
  python3 "$PY" selftest
  echo "VM-PROGRESS NONINTERFERENCE DRY RUN PASS samples=target-owned quiet=120s mid-form-monitor=0 final-stops=1"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" check >/dev/null
mkdir -p "$OUT"

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/stage.consumed" ] || { echo "progress stage already consumed" >&2; exit 3; }
  : > "$OUT/stage.consumed"
  run_m65 -F
  sleep 5
  screen fresh-basic
  python3 - "$OUT/fresh-basic.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "basic 65" in text or "ready." in text
assert "break" not in text and "monitor commands" not in text
PY

  medium=$(jq -r '.library_medium.path' "$DEPLOY")
  remote=$(jq -r '.library_remote' "$DEPLOY")
  ftp_medium "$medium" "$remote"

  product=$(jq -r '.diagnostic.prg.path' "$DEPLOY")
  run_m65 -H "$product"
  payload_bytes=$(($(wc -c < "$product") - 2))
  readback 0x2001 "$payload_bytes" "$OUT/diagnostic-prg-payload.bin"
  python3 - "$product" "$OUT/diagnostic-prg-payload.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes()[2:] == Path(sys.argv[2]).read_bytes()
PY

  jq -c '.diagnostic.preloads[]' "$DEPLOY" | while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/preload-$role.bin"
    cmp "$path" "$OUT/preload-$role.bin"
  done

  reset_path=$(jq -r '.diagnostic.preloads[] | select(.role == "c2d-v6-reset-domain") | .path' "$DEPLOY")
  reset_bytes=$(jq -r '.diagnostic.preloads[] | select(.role == "c2d-v6-reset-domain") | .bytes' "$DEPLOY")
  [ "$reset_bytes" -eq "$RESET_DOMAIN_BYTES" ] || {
    echo "partial reset-domain staging rejected: $reset_bytes" >&2; exit 3;
  }
  python3 - "$reset_path" <<'PY'
from pathlib import Path
import sys
raw = Path(sys.argv[1]).read_bytes()
assert len(raw) == 50816
assert raw[33840:] == b"\0" * (50816 - 33840)
assert raw[50752:50816] == b"\0" * 64
PY
  readback 0x0005c640 64 "$OUT/pre-run-c2j.bin"
  python3 - "$OUT/pre-run-c2j.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes() == b"\0" * 64
PY
  state=build/c2.3/v1.6-defstruct-vm-progress-noninterference/artifacts/vm-progress-atomic-state-reset.bin
  slots=build/c2.3/v1.6-defstruct-vm-progress-noninterference/artifacts/vm-progress-slot-reset.bin
  run_m65 -H -@ "$state@0x00001ff8"
  run_m65 -H -@ "$slots@0x087fff40"
  readback 0x00001ff8 8 "$OUT/pre-form-low-state.bin"
  readback 0x087fff40 32 "$OUT/pre-form-slots.bin"
  cmp "$state" "$OUT/pre-form-low-state.bin"
  cmp "$slots" "$OUT/pre-form-slots.bin"
  : > "$OUT/stage.ready"
  run_m65 -r
  echo "VM-PROGRESS STAGE READY: type RUN, (require 'defstruct), and (defstruct point x y) physically; after the final RETURN immediately tell Codex gesendet."
  exit 0
fi

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/stage.ready" ] || { echo "progress stage absent" >&2; exit 3; }
  [ ! -e "$OUT/capture.consumed" ] || { echo "progress capture already consumed" >&2; exit 3; }
  : > "$OUT/capture.consumed"
  # No command above this marker, and no command until after the sleep below,
  # is allowed to communicate with the monitor or the target.
  sleep 120
  # FIRST-AND-ONLY-POST-FORM-MONITOR-ENTRY
  stop_once
  # One serial session stays open for one t1 and the stopped-state reads.
  python3 - "$OUT/runtime-window-tail.bin" "$OUT/runtime-low-state.bin" "$OUT/result.json" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
window = Path(sys.argv[1]).read_bytes()
low = Path(sys.argv[2]).read_bytes()
assert len(window) == 0x50 and len(low) == 8
slots = window[:0x20]
frame_hi = window[0x44]
rows = []
for offset in range(0, 0x20, 8):
    raw = slots[offset:offset + 8]
    if raw[7] != 0xA5:
        continue
    assert raw[6] & 7 == 0
    rows.append({"offset": offset,
                 "counter": int.from_bytes(raw[:4], "little"),
                 "owner": int.from_bytes(raw[4:6], "little"),
                 "frame_hi": raw[6],
                 "age": (frame_hi - raw[6]) & 0xff})
rows.sort(key=lambda row: row["age"])
status = "INSTRUMENT-FIRST-RED"
delta = None
if len(rows) >= 2 and rows[1]["age"] - rows[0]["age"] == 8:
    delta = (rows[0]["counter"] - rows[1]["counter"]) & 0xffffffff
    status = "LIVE-VM-DISPATCH-PROGRESS" if delta else "NO-VM-DISPATCH-IN-SAMPLE-GAP"
Path(sys.argv[3]).write_text(json.dumps({
    "status": status, "delta_u32": delta, "accepted_newest_first": rows[:2],
    "frame_hi_at_stop": frame_hi, "low_state_hex": low.hex(),
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "CPU_left_stopped": True,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
assert status != "INSTRUMENT-FIRST-RED"
PY
  echo "VM-PROGRESS CAPTURE COMPLETE; CPU remains stopped: $OUT/result.json"
  exit 0
fi
