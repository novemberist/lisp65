#!/bin/sh
# Link-92 Phase-D D3 split-library smokes and quiet physical editor row.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v112-link92-phase-d-d3.json
PY=tools/host-lisp/c2_v112_phase_d_d3.py
BUFFER_PY=tools/host-lisp/c2_v16_defstruct_phase_c.py
OUT=${OUT:-build/c2.3/v1.4.0-release/phase-d-split/d3}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|start-d3|capture-d3) ;;
  *) echo "usage: $0 <dry-run|start-d3|capture-d3>" >&2; exit 2 ;;
esac

python3 "$PY" check

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  jq -c '.libraries.requires[]' "$CONFIG" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    require_form=$(printf '%s' "$row" | jq -r '.form')
    OUT_DIR=$OUT PREFIX="D3-require-$id-input" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --no-readback \
        --form "$require_form"
  done
  jq -c '.libraries.rows[]' "$CONFIG" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    form=$(printf '%s' "$row" | jq -r '.form')
    expected=$(printf '%s' "$row" | jq -r '.expect')
    OUT_DIR=$OUT PREFIX="D3-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --wait 3 \
        --expect "$expected" --expect-poll 60 --form "$form"
  done
  OUT_DIR=$OUT PREFIX=D3-editor-input TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --dry-run --verified-input \
      --allow-editor-status-tail --no-readback \
      --form "$(jq -r '.editor.form' "$CONFIG")"
  echo "DRY-RUN: full identity -> split libraries -> quiet physical editor window"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
mkdir -p "$OUT"

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }

capture_screen() (
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
)

fail_if_red() (
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError as error:
    print(error.message)
    raise SystemExit(error.code)
PY
)

readback() (
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  run_m65 -H --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

fresh_start() (
  run_m65 -F
  sleep 5
  capture_screen D3-fresh-basic
  fail_if_red "$OUT/D3-fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/D3-fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/D3-fresh-basic.txt"
)

ftp_library() (
  media=$(jq -r '.identity.library_medium.path' "$CONFIG")
  remote=$(jq -r '.identity.remote' "$CONFIG")
  log=$OUT/D3-library-upload.log
  readback_path=$OUT/D3-library-readback.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!; last=-1; progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2; size=$(wc -c < "$log"); now=$(date +%s)
    if [ "$size" -ne "$last" ]; then last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2; return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$readback_path"
)

load_identity() (
  product=$(jq -r '.identity.product.path' "$CONFIG")
  run_m65 -H -1 "$product"
  jq -c '.identity.preloads[]' "$CONFIG" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/D3-preload-$role.bin"
    cmp "$path" "$OUT/D3-preload-$role.bin"
  done
  c2j_address=$(($(jq -r '.identity.c2j_clear.address' "$CONFIG")))
  c2j_bytes=$(jq -r '.identity.c2j_clear.bytes' "$CONFIG")
  c2j_authority=$(jq -r '.identity.c2j_clear.authority' "$CONFIG")
  readback "$c2j_address" "$c2j_bytes" "$OUT/D3-c2j-before-run.bin"
  cmp "$c2j_authority" "$OUT/D3-c2j-before-run.bin"
  run_m65 -r -1 "$product"
  sleep "$(jq -r '.identity.boot_quiet_seconds' "$CONFIG")"
  capture_screen D3-boot
  fail_if_red "$OUT/D3-boot.png"
  grep -Fq "$(jq -r '.identity.banner' "$CONFIG")" "$OUT/D3-boot.txt"
  grep -Fq "$(jq -r '.identity.prompt' "$CONFIG")" "$OUT/D3-boot.txt"
)

run_exact_form() (
  prefix=$1 form=$2 expected=$3
  OUT_DIR=$OUT PREFIX=$prefix TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --wait 3 \
      --expect "$expected" --expect-poll 60 --form "$form"
)

run_quiet_requires() (
  jq -c '.libraries.requires[]' "$CONFIG" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    form=$(printf '%s' "$row" | jq -r '.form')
    expected=$(printf '%s' "$row" | jq -r '.expect')
    quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
    OUT_DIR=$OUT PREFIX="D3-require-$id-input" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    sleep "$quiet"
    capture_screen "D3-require-$id"
    fail_if_red "$OUT/D3-require-$id.png"
    python3 tools/host-lisp/repl_screen_check.py \
      --screen "$OUT/D3-require-$id.txt" --image "$OUT/D3-require-$id.png" \
      --form-text "$form" --expect "$expected"
  done
)

capture_buffer() {
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

if [ "$ACTION" = capture-d3 ]; then
  [ -e "$OUT/physical-window-active" ] || {
    echo "D3 physical window was not armed" >&2; exit 3;
  }
  [ ! -e "$OUT/physical-row-passed" ] || {
    echo "D3 physical row already captured" >&2; exit 3;
  }
  capture_buffer d3-final
  capture_screen D3-editor-final
  fail_if_red "$OUT/D3-editor-final.png"
  if python3 "$BUFFER_PY" check-d1-buffer --directory "$OUT" \
      --prefix d3-final --expected-fill 64; then
    : > "$OUT/physical-row-passed"
    python3 "$PY" result
    echo "D3 PHYSICAL PASS submitted=64 persisted=64"
  else
    python3 "$BUFFER_PY" capture-d1-hang --directory "$OUT" --device "$DEVICE"
    echo "D3 PHYSICAL FIRST RED: final buffer is not 64; CPU left stopped" >&2
    exit 4
  fi
  exit 0
fi

[ ! -e "$OUT/contact.consumed" ] || {
  echo "D3 contact already consumed" >&2; exit 3;
}
: > "$OUT/contact.consumed"

# D3-ORDER-BEGIN: the source gate owns this complete precedence.
fresh_start
ftp_library
load_identity
run_quiet_requires
jq -c '.libraries.rows[]' "$CONFIG" |
while IFS= read -r row; do
  id=$(printf '%s' "$row" | jq -r '.id')
  form=$(printf '%s' "$row" | jq -r '.form')
  expected=$(printf '%s' "$row" | jq -r '.expect')
  run_exact_form "D3-$id" "$form" "$expected"
done
python3 "$PY" check-libraries
editor_form=$(jq -r '.editor.form' "$CONFIG")
OUT_DIR=$OUT PREFIX=D3-editor-input TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form "$editor_form"
sleep "$(jq -r '.editor.context_wait_seconds' "$CONFIG")"
capture_screen D3-editor-context
fail_if_red "$OUT/D3-editor-context.png"
grep -Eq -- '-- measure3( \*)? L[0-9]+ --' "$OUT/D3-editor-context.txt"
capture_buffer d3-context
python3 "$BUFFER_PY" check-d1-buffer --directory "$OUT" --prefix d3-context
run_m65 -r
: > "$OUT/physical-window-active"
# D3-ORDER-END

echo "D3 PHYSICAL WINDOW ACTIVE: no monitor traffic until capture-d3."
echo "TYPE EXACTLY, WITHOUT RETURN:"
jq -r '.editor.physical_text' "$CONFIG"
