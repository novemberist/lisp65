#!/bin/sh
# Corrected quiet D2 rider: exact Link-82 diagnostic, RETURN, RAM entry witness.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_d2_choreography_closure.py
ENTRY=tools/host-lisp/c2_v16_d2_ram_entry_witness.py
LAUNCH_SCREEN=tools/host-lisp/c2_v16_d2_launch_screen.py
DEPLOY=build/c2.3/v1.6-defstruct-phase-c/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-ram-entry-witness-complete-map}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|run) ;;
  *) echo "usage: $0 <dry-run|run>" >&2; exit 2 ;;
esac

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" check
  python3 "$ENTRY" selftest --deployment "$DEPLOY"
  python3 "$LAUNCH_SCREEN" selftest
  echo "D2 CLOSING DRY RUN PASS return-submitted=1 RAM-entry-stamp=1 breakpoint=0"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
[ ! -e "$OUT/contact.consumed" ] || {
  echo "D2 closing contact already consumed" >&2; exit 3;
}
mkdir -p "$OUT"
: > "$OUT/contact.consumed"

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
fresh_basic() {
  run_m65 -F
  sleep 5
  screen fresh-basic
  grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/fresh-basic.txt"
}
ftp_medium() {
  media=$1 remote=$2 log=$OUT/upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $OUT/readback.d81" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
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
  cmp "$media" "$OUT/readback.d81"
}
quiet_input() {
  prefix=$1 form=$2
  OUT_DIR="$OUT" PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
}
deploy_diagnostic() {
  product=$(jq -r '.diagnostic.prg.path' "$DEPLOY")
  run_m65 -H -1 "$product"
  jq -c '.diagnostic.preloads[]' "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/preload-$role.bin"
    cmp "$path" "$OUT/preload-$role.bin"
  done
  run_m65 -r -1 "$product"
}

python3 "$PY" check >/dev/null
fresh_basic
medium=$(jq -r '.library_medium.path' "$DEPLOY")
remote=$(jq -r '.library_remote' "$DEPLOY")
ftp_medium "$medium" "$remote"
deploy_diagnostic
sleep 5
screen launch-before-return
python3 "$LAUNCH_SCREEN" classify --screen "$OUT/launch-before-return.txt"

# Submit exactly one RETURN through the Stage-1-proved matrix transport.  The
# entry proof no longer depends on monitor breakpoint retention: _start itself
# stamps ordinary RAM, and the stamp is read only after launch has settled.
python3 "$ENTRY" submit --deployment "$DEPLOY" --device "$DEVICE" \
  --output "$OUT/return-submit.json"
sleep 10
screen boot-after-entry
grep -q 'lisp65>' "$OUT/boot-after-entry.txt"
entry_stamp=$(jq -r '.entry_witness.stamp_address' "$DEPLOY")
readback "$entry_stamp" 1 "$OUT/entry-witness.bin"
python3 "$ENTRY" decode --deployment "$DEPLOY" \
  --input "$OUT/entry-witness.bin" --output "$OUT/entry-witness.json"

# Immediate context asserts happen before either measured form.
readback 0x89 1 "$OUT/phase-owner.bin"
readback 0x0005c640 64 "$OUT/c2j.bin"
readback 0x00050000 48 "$OUT/c2d-header.bin"
python3 - "$OUT/phase-owner.bin" "$OUT/c2j.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes() == b"\0"
assert Path(sys.argv[2]).read_bytes() == b"\0" * 64
PY
initial_c2d=$(jq -r '.diagnostic.preloads[] | select(.role == "c2d-v6-code-plane") | .path' "$DEPLOY")
cmp -n 48 "$initial_c2d" "$OUT/c2d-header.bin"
run_m65 -r

require_form=$(jq -r '.forms.require' "$DEPLOY")
quiet_input require "$require_form"
sleep 120
screen require-result
python3 tools/host-lisp/repl_screen_check.py \
  --screen "$OUT/require-result.txt" --form-text "$require_form" --expect t

record=$(($(jq -r '.record.address' "$DEPLOY")))
reset=$(jq -r '.record.reset.path' "$DEPLOY")
arm=$(jq -r '.record.arm.path' "$DEPLOY")
record_hex=0x$(printf '%08x' "$record")
run_m65 -H -@ "$reset@$record_hex"
run_m65 -H -@ "$arm@$record_hex"
run_m65 -r

defstruct_form=$(jq -r '.forms.defstruct' "$DEPLOY")
quiet_input defstruct "$defstruct_form"
sleep 180
screen first-observation

# Exactly one stop and the complete stable read set.
readback "$record" 65 "$OUT/record-1.bin"
sleep 2; readback "$record" 65 "$OUT/record-2.bin"
sleep 2; readback "$record" 65 "$OUT/record-3.bin"
cmp "$OUT/record-1.bin" "$OUT/record-2.bin"
cmp "$OUT/record-2.bin" "$OUT/record-3.bin"
readback 0 65536 "$OUT/low-ram.bin"
readback 131072 65536 "$OUT/bank2-source.bin"
readback 327680 50816 "$OUT/c2d-reset-domain.bin"

echo "D2 CLOSING CAPTURE COMPLETE: do not resume or execute a second form."
