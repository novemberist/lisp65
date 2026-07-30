#!/bin/sh
# Read-only Link-80 require discriminator: exact product/media, two peeks.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_V123_REQUIRE_DISC_OUT:-build/post-promotion/v1.2.3/link80-require-discriminator}
PY=tools/host-lisp/c2_v123_link80_require_device_discriminator.py
DEPLOY=build/post-promotion/v1.2.3/link80-bundled-session/deployment.json
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-75}
RESULT_POLL_LIMIT=${RESULT_POLL_LIMIT:-90}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
PRIOR_HW=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-v1.2.3-link80-require-device-discriminator-hardware-receipt.json
FORM='(require(quote place))'

case "$ACTION" in
  dry-run|start|evaluate) ;;
  *) echo "usage: $0 <dry-run|start|evaluate>" >&2; exit 2 ;;
esac

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  echo "DRY-RUN: cold reset: $M65 -l $DEVICE -F"
  echo "DRY-RUN: fresh-state gate: BASIC 65 + READY.; reject lisp65> and red frame"
  echo "DRY-RUN: FTP log progress guard: ${FTP_STALL_LIMIT}s"
  OUT_DIR="$OUT/dry-run" PREFIX=require TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --dry-run --verified-input --form "$FORM"
  echo "DRY-RUN: read 0x0000c1f4+2, 0x00050000+48, 0x000500f0+32 twice"
  exit
fi

if [ "$ACTION" = evaluate ]; then
  python3 "$PY" evaluate --out "$OUT"
  exit
fi

python3 "$PY" prepare
[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}

mkdir -p "$OUT"
contacts=0
if [ -f "$OUT/contact-count.txt" ]; then
  contacts=$(cat "$OUT/contact-count.txt")
elif [ -f "$PRIOR_HW" ]; then
  contacts=$(jq -r '.hardware_contacts' "$PRIOR_HW")
fi
contacts=$((contacts + 1))
[ "$contacts" -eq 3 ] || {
  echo "hardware contact budget exhausted" >&2
  exit 3
}
printf '%s\n' "$contacts" > "$OUT/contact-count.txt"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  start=$1
  bytes=$2
  path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}

capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

fail_if_red() {
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
}

fresh_start_gate() {
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen fresh-start
    fail_if_red "$OUT/fresh-start.png"
    if grep -Fq 'BASIC 65' "$OUT/fresh-start.txt" &&
       grep -Fq 'READY.' "$OUT/fresh-start.txt" &&
       ! grep -Fq 'lisp65>' "$OUT/fresh-start.txt"; then
      return 0
    fi
    sleep 1
    poll=$((poll + 1))
  done
  return 1
}

ftp_with_progress_guard() {
  media=$1
  remote=$2
  log=$OUT/media-upload.log
  readback_path=$OUT/uploaded-media-readback.d81
  rm -f "$readback_path"
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $readback_path" \
    -c "mount $remote" \
    -c exit > "$log" 2>&1 &
  ftp_pid=$!
  trap 'kill "$ftp_pid" 2>/dev/null || true' HUP INT TERM EXIT
  last_size=-1
  last_progress=$(date +%s)
  while kill -0 "$ftp_pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last_size" ]; then
      last_size=$size
      last_progress=$now
    elif [ $((now - last_progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$ftp_pid" 2>/dev/null || true
      wait "$ftp_pid" 2>/dev/null || true
      trap - HUP INT TERM EXIT
      echo "FTP progress guard: no log movement for ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  if wait "$ftp_pid"; then
    status=0
  else
    status=$?
  fi
  trap - HUP INT TERM EXIT
  return "$status"
}

poll_repl() {
  prefix=$1
  poll=0
  while [ "$poll" -lt "$BOOT_POLL_LIMIT" ]; do
    capture_screen "$prefix"
    fail_if_red "$OUT/$prefix.png"
    grep -q 'lisp65>' "$OUT/$prefix.txt" && return 0
    sleep 1
    poll=$((poll + 1))
  done
  return 1
}

poll_result() {
  prefix=$1
  poll=0
  while [ "$poll" -lt "$RESULT_POLL_LIMIT" ]; do
    capture_screen "$prefix"
    fail_if_red "$OUT/$prefix.png"
    if python3 "$PY" screen-result --screen "$OUT/$prefix.txt" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    poll=$((poll + 1))
  done
  return 1
}

capture_witnesses() {
  prefix=$1
  readback 0x0000c1f4 2 "$OUT/$prefix-trace.bin"
  readback 0x00050000 48 "$OUT/$prefix-c2d-header.bin"
  readback 0x000500f0 32 "$OUT/$prefix-place-row.bin"
}

phase=$(jq '.phases.product' "$DEPLOY")
media=$(printf '%s' "$phase" | jq -r '.media.path')
remote=$(printf '%s' "$phase" | jq -r '.remote_media')
product=$(printf '%s' "$phase" | jq -r '.product.path')

run_m65 -F
sleep 3
fresh_start_gate || {
  echo "fresh BASIC startup state not proven after cold reset" >&2
  exit 3
}
ftp_with_progress_guard "$media" "$remote"
cmp "$media" "$OUT/uploaded-media-readback.d81"

run_m65 -H -1 "$product"
printf '%s' "$phase" | jq -c '.preloads[]' |
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
sleep 3

capture_screen boot-autorun
if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/boot-autorun.txt" &&
   ! grep -q 'lisp65>' "$OUT/boot-autorun.txt"; then
  run_m65 -t '~M'
fi
poll_repl boot || {
  echo "no Lisp REPL after exact Link-80 deployment" >&2
  exit 3
}
capture_witnesses baseline

attempt=1
while [ "$attempt" -le 2 ]; do
  OUT_DIR="$OUT" PREFIX="attempt-$attempt-input" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$FORM"
  poll_result "attempt-$attempt" || {
    echo "require attempt $attempt did not return t or nil" >&2
    exit 4
  }
  capture_witnesses "attempt-$attempt"
  attempt=$((attempt + 1))
done

python3 "$PY" evaluate --out "$OUT"
