#!/bin/sh
# Hook-free physical-owner launch for the quiet v1.6 D2 measurement.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_d2_physical_fallback.py
DEPLOY=build/c2.3/v1.6-defstruct-d2-physical-fallback/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-physical-owner}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|stage|continue) ;;
  *) echo "usage: $0 <dry-run|stage|continue>" >&2; exit 2 ;;
esac
python3 "$PY" check
[ "$ACTION" != dry-run ] || { echo "D2 PHYSICAL FALLBACK DRY RUN PASS"; exit 0; }
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || exit 3
[ ! -e "$OUT/contact.consumed" ] || { echo "physical contact consumed" >&2; exit 3; }
mkdir -p "$OUT"; : > "$OUT/contact.consumed"
run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }
screen() {
  name=$1
  run_m65 --screenshot="$OUT/$name.png" > "$OUT/$name.ansi.txt"
  python3 - "$OUT/$name.ansi.txt" "$OUT/$name.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}
readback() {
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
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
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; return 124
    fi
  done
  wait "$pid"; cmp "$media" "$OUT/readback.d81"
}
quiet_input() {
  prefix=$1 form=$2
  OUT_DIR="$OUT" PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
}

if [ "$ACTION" = continue ]; then
  [ -e "$OUT/stage.ready" ] || {
    echo "physical stage was not proved ready" >&2; exit 3;
  }
  [ ! -e "$OUT/continue.consumed" ] || {
    echo "physical continuation already consumed" >&2; exit 3;
  }
  : > "$OUT/continue.consumed"

  # The owner has now typed RUN and RETURN on the physical keyboard.  This
  # visible prompt is the launch witness; no boot-only hook or virtual launch
  # transport remains in the method.
  screen physical-after-launch
  grep -q 'lisp65>' "$OUT/physical-after-launch.txt"
  ! grep -Eqi 'BREAK|MONITOR COMMANDS' "$OUT/physical-after-launch.txt"

  # Immediate context asserts precede both measured forms.
  readback 0x89 1 "$OUT/phase-owner.bin"
  readback 0x0005c640 64 "$OUT/c2j.bin"
  readback 0x00050000 48 "$OUT/c2d-header.bin"
  python3 - "$OUT/phase-owner.bin" "$OUT/c2j.bin" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_bytes() == b"\0"
assert Path(sys.argv[2]).read_bytes() == b"\0" * 64
PY
  initial_c2d=$(jq -r '.diagnostic_preloads[] | select(.role == "c2d-v6-code-plane") | .path' "$DEPLOY")
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

  echo "D2 PHYSICAL CAPTURE COMPLETE: do not resume or execute a second form."
  exit 0
fi

run_m65 -F; sleep 5; screen fresh-basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/fresh-basic.txt"
medium=$(jq -r '.library_medium.path' "$DEPLOY")
remote=$(jq -r '.library_remote' "$DEPLOY")
ftp_medium "$medium" "$remote"
product=$(jq -r '.physical_prg.path' "$DEPLOY")
run_m65 -H "$product"
jq -c '.diagnostic_preloads[]' "$DEPLOY" | while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  role=$(printf '%s' "$item" | jq -r '.role')
  run_m65 -H -@ "$path@$address"
  readback "$address" "$bytes" "$OUT/preload-$role.bin"
  cmp "$path" "$OUT/preload-$role.bin"
done
run_m65 -r
sleep 3
screen physical-launch-ready
grep -Eqi 'READY\.' "$OUT/physical-launch-ready.txt"
! grep -Eqi 'BREAK|MONITOR COMMANDS|lisp65>' "$OUT/physical-launch-ready.txt"
: > "$OUT/stage.ready"
echo "D2 PHYSICAL STAGE READY: type RUN and press RETURN on the physical keyboard."
