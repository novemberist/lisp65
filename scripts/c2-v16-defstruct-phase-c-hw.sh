#!/bin/sh
# One bundled quiet Phase-D session for the non-promotable Link-82 identity.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_defstruct_phase_c.py
DEPLOY=build/c2.3/v1.6-defstruct-phase-c/deployment.json
OUT_ROOT=build/c2.3/v1.6-defstruct-phase-c/run
CONTACT=${CONTACT:-1}
case "$CONTACT" in 1|2) ;; *) echo "CONTACT must be 1 or 2" >&2; exit 2;; esac
OUT=$OUT_ROOT/contact-$CONTACT
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|run|resume-d2|reserve-d2) ;;
  *) echo "usage: $0 <prepare|dry-run|run|resume-d2|reserve-d2>" >&2; exit 2 ;;
esac
if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi
if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  echo "D1: cold reset -> exact v1.3.0 medium -> 64 quiet keys -> final buffer/REPL only"
  echo "D2: cold reset -> exact library medium -> diagnostic PRG + seven bound preloads"
  echo "D2: assert C2J CLEAR, owner NONE, initial C2D header -> require quiet -> reset/arm"
  echo "D2: defstruct quiet 180s -> one first observation -> one stop -> complete read set x3"
  echo "GUARDS: FTP progress 120s; zero monitor/screen access while either measured form is active"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" dry-run >/dev/null
if [ "$ACTION" = resume-d2 ]; then
  [ -e "$OUT/contact.consumed" ] && [ -e "$OUT/d1-hang-one-stop-packet.json" ] || {
    echo "D2 continuation requires this contact's captured D1 hang" >&2; exit 3;
  }
  [ ! -e "$OUT/d2-first-observation.png" ] || {
    echo "D2 already reached its first observation" >&2; exit 3;
  }
elif [ "$ACTION" = reserve-d2 ]; then
  [ "$CONTACT" = 2 ] && [ -e "$OUT_ROOT/contact-1/contact.consumed" ] &&
      [ -e "$OUT_ROOT/contact-1/d2-boot.txt" ] || {
    echo "D2 setup reserve requires contact 1's captured boot First Red" >&2; exit 3;
  }
  [ ! -e "$OUT/contact.consumed" ] || {
    echo "Phase-C setup reserve already consumed" >&2; exit 3;
  }
  mkdir -p "$OUT"
  : > "$OUT/contact.consumed"
else
  [ ! -e "$OUT/contact.consumed" ] || {
    echo "Phase-C hardware contact already consumed" >&2; exit 3;
  }
  [ "$CONTACT" = 1 ] || [ -e "$OUT_ROOT/contact-1/contact.consumed" ] || {
    echo "reserve requires a consumed contact 1 and its owner review" >&2; exit 3;
  }
  mkdir -p "$OUT"
  : > "$OUT/contact.consumed"
fi

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
  prefix=$1
  run_m65 -F
  sleep 5
  screen "$prefix-fresh-basic"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/$prefix-fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/$prefix-fresh-basic.txt"
}
ftp_medium() {
  media=$1 remote=$2 prefix=$3 log=$OUT/$prefix-upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $OUT/$prefix-readback.d81" \
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
  cmp "$media" "$OUT/$prefix-readback.d81"
}
quiet_input() {
  prefix=$1 form=$2
  OUT_DIR="$OUT" PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
}
capture_d1_buffer() {
  prefix=$1
  readback 0x59 2 "$OUT/$prefix-nsym.bin"
  readback 0x0005c680 10208 "$OUT/$prefix-namepool.bin"
  readback 0x0005ee60 1504 "$OUT/$prefix-symval.bin"
  readback 0x0005f440 1504 "$OUT/$prefix-nameoff.bin"
  readback 0x0000c25d 240 "$OUT/$prefix-heap.bin"
  readback 0x00040000 8192 "$OUT/$prefix-ext.bin"
  readback 0x22 2 "$OUT/$prefix-str-cur-off.bin"
  readback 0x00042000 9344 "$OUT/$prefix-arena-2000.bin"
  readback 0x00044480 9344 "$OUT/$prefix-arena-4480.bin"
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
    readback "$((address))" "$bytes" "$OUT/d2-preload-$role.bin"
    cmp "$path" "$OUT/d2-preload-$role.bin"
  done
  run_m65 -r -1 "$product"
}

if [ "$ACTION" = run ]; then
# D1 — released ordinary product, no per-key observation.
fresh_basic d1
d1=$(jq -r '.ordinary_product_D1.path' "$DEPLOY")
ftp_medium "$d1" LISP65-V16-D1.D81 d1
sleep 45
screen d1-boot
grep -q 'lisp65>' "$OUT/d1-boot.txt"
quiet_input d1-editor '(ide"measure3")'
sleep 12
screen d1-editor-context
grep -Eq -- '-- measure3( \*)? L[0-9]+ --' "$OUT/d1-editor-context.txt"
# The status row is only a UI assertion.  Buffer truth comes from direct
# memory while held, once before the measured key sequence and never per key.
capture_d1_buffer d1-context
python3 "$PY" check-d1-buffer --directory "$OUT"
run_m65 -r
i=0
while [ "$i" -lt 64 ]; do run_m65 -t a; i=$((i + 1)); done
sleep 60
screen d1-final
# This is the only post-key observation.  Its memory read either proves all 64
# keys or leaves the CPU stopped for the standing queue/gc/PC hang packet.
capture_d1_buffer d1-final-memory
if python3 "$PY" check-d1-buffer --directory "$OUT" \
    --prefix d1-final-memory --expected-fill 64; then
  run_m65 -r
  run_m65 -t '~C'
  sleep 8
  screen d1-repl
  grep -q 'lisp65>' "$OUT/d1-repl.txt"
else
  python3 "$PY" capture-d1-hang --directory "$OUT" --device "$DEVICE"
  echo "D1 quiet-typing postcondition failed; continuing to cold-isolated D2" >&2
fi
fi

# D2 — exact library medium plus separately loaded diagnostic sibling.  This
# is the historical Link-82 deployment model: library bytes never change.
# A cold reset prevents D1 contamination.
fresh_basic d2
medium=$(jq -r '.library_medium.path' "$DEPLOY")
remote=$(jq -r '.library_remote' "$DEPLOY")
ftp_medium "$medium" "$remote" d2
deploy_diagnostic
sleep 5
screen d2-boot
if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/d2-boot.txt" &&
   ! grep -q 'lisp65>' "$OUT/d2-boot.txt"; then
  run_m65 -t '~M'
  sleep 10
  screen d2-boot
fi
grep -q 'lisp65>' "$OUT/d2-boot.txt"

# Immediate-context asserts happen before the measured form, under one hold.
# The initial header comparison proves there are no persistent Session rows.
readback 0x89 1 "$OUT/d2-phase-owner.bin"
readback 0x0005c640 64 "$OUT/d2-c2j.bin"
readback 0x00050000 48 "$OUT/d2-c2d-header.bin"
python3 - "$OUT/d2-phase-owner.bin" "$OUT/d2-c2j.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes() == b"\0"
assert Path(sys.argv[2]).read_bytes() == b"\0" * 64
PY
initial_c2d=$(jq -r '.diagnostic.preloads[] | select(.role == "c2d-v6-code-plane") | .path' "$DEPLOY")
cmp -n 48 "$initial_c2d" "$OUT/d2-c2d-header.bin"
run_m65 -r

require_form=$(jq -r '.forms.require' "$DEPLOY")
quiet_input d2-require "$require_form"
# No access inside the fixed window.  The single observation closes the form.
sleep 120
screen d2-require-result
python3 tools/host-lisp/repl_screen_check.py \
  --screen "$OUT/d2-require-result.txt" --form-text "$require_form" --expect t

record=$(($(jq -r '.record.address' "$DEPLOY")))
reset=$(jq -r '.record.reset.path' "$DEPLOY")
arm=$(jq -r '.record.arm.path' "$DEPLOY")
record_hex=0x$(printf '%08x' "$record")
run_m65 -H -@ "$reset@$record_hex"
run_m65 -H -@ "$arm@$record_hex"
run_m65 -r

defstruct_form=$(jq -r '.forms.defstruct' "$DEPLOY")
quiet_input d2-defstruct "$defstruct_form"
# The active interval is intentionally opaque: no screenshot, peek or ack.
sleep 180
screen d2-first-observation

# Exactly one stop, then the complete read set.  Repeated -H reads keep the CPU held.
readback "$record" 65 "$OUT/record-1.bin"
sleep 2; readback "$record" 65 "$OUT/record-2.bin"
sleep 2; readback "$record" 65 "$OUT/record-3.bin"
cmp "$OUT/record-1.bin" "$OUT/record-2.bin"
cmp "$OUT/record-2.bin" "$OUT/record-3.bin"
readback 0 65536 "$OUT/low-ram.bin"
readback 131072 65536 "$OUT/bank2-source.bin"
readback 327680 50816 "$OUT/c2d-reset-domain.bin"

echo "PHASE D CAPTURE COMPLETE: do not resume or execute a second form."
