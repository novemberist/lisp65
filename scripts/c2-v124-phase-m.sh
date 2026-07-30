#!/bin/sh
# One physical Phase-M session: M1, current-core L10, M3, M4 and M5.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_V124_PHASE_M_OUT:-build/post-promotion/v124/phase-m}
DEPLOY=$OUT/deployment.json
CONFIG=config/c2.2-v1.2.4-phase-m-session.json
PY=tools/host-lisp/c2_v124_phase_m.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
EXPECT_POLL=${EXPECT_POLL:-120}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start|evaluate) ;;
  *) echo "usage: $0 <prepare|dry-run|start|evaluate>" >&2; exit 2 ;;
esac

if [ "$ACTION" = prepare ]; then
  python3 "$PY" prepare
  exit
fi

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" verify
  jq -c '.rows[]' "$CONFIG" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    form=$(printf '%s' "$row" | jq -r '.form')
    expect=$(printf '%s' "$row" | jq -r '.expected')
    OUT_DIR="$OUT/dry-run" PREFIX="$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input \
        --expect "$expect" --form "$form"
  done
  echo "c2-v124-phase-m: DRY-RUN PASS"
  exit
fi

if [ "$ACTION" = evaluate ]; then
  python3 "$PY" evaluate
  exit
fi

python3 "$PY" verify
[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}
[ ! -f tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-v1.2.4-phase-m-hardware-receipt.json ] || {
  echo "Phase-M hardware run already consumed" >&2
  exit 3
}

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  start=$1
  bytes=$2
  path=$3
  end=$((start + bytes))
  mkdir -p "$(dirname "$path")"
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
  prefix=$1
  run_m65 -F
  sleep 3
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen "$prefix"
    fail_if_red "$OUT/$prefix.png"
    if grep -Fq 'BASIC 65' "$OUT/$prefix.txt" &&
       grep -Fq 'READY.' "$OUT/$prefix.txt" &&
       ! grep -Fq 'lisp65>' "$OUT/$prefix.txt"; then
      return
    fi
    sleep 1
    poll=$((poll + 1))
  done
  echo "fresh BASIC startup state not proven" >&2
  exit 3
}

ftp_with_progress_guard() {
  media=$1
  remote=$2
  suffix=$3
  log=$OUT/media-upload-$suffix.log
  readback_path=$OUT/uploaded-media-$suffix.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $readback_path" \
    -c "mount $remote" \
    -c exit > "$log" 2>&1 &
  pid=$!
  last_size=-1
  last_progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last_size" ]; then
      last_size=$size
      last_progress=$now
    elif [ $((now - last_progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      exit 124
    fi
  done
  wait "$pid"
  cmp "$media" "$readback_path"
}

boot_candidate() {
  suffix=$1
  product=$(jq -r '.candidate.product.path' "$DEPLOY")
  run_m65 -H -1 "$product"
  jq -c '.candidate.preloads[]' "$DEPLOY" |
  while IFS= read -r row; do
    path=$(printf '%s' "$row" | jq -r '.path')
    address=$(printf '%s' "$row" | jq -r '.address')
    bytes=$(printf '%s' "$row" | jq -r '.bytes')
    role=$(printf '%s' "$row" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/$suffix-$role.bin"
    cmp "$path" "$OUT/$suffix-$role.bin"
  done
  run_m65 -r -1 "$product"
  sleep 3
  capture_screen "$suffix-autorun"
  if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/$suffix-autorun.txt" &&
     ! grep -q 'lisp65>' "$OUT/$suffix-autorun.txt"; then
    run_m65 -t '~M'
  fi
  poll=0
  while [ "$poll" -lt 75 ]; do
    capture_screen "$suffix-boot"
    fail_if_red "$OUT/$suffix-boot.png"
    grep -q 'lisp65>' "$OUT/$suffix-boot.txt" && return
    sleep 1
    poll=$((poll + 1))
  done
  echo "candidate did not reach Lisp REPL" >&2
  exit 3
}

run_row() {
  id=$1
  form=$(jq -r ".rows[]|select(.id==\"$id\")|.form" "$CONFIG")
  expect=$(jq -r ".rows[]|select(.id==\"$id\")|.expected" "$CONFIG")
  OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input \
      --expect "$expect" --expect-poll "$EXPECT_POLL" --wait 1 --form "$form"
  fail_if_red "$OUT/row-$id.png"
}

run_l10() {
  product=$(jq -r '.l10.product.path' "$DEPLOY")
  run_m65 -H -1 "$product"
  jq -c '.l10.preloads[]' "$DEPLOY" |
  while IFS= read -r row; do
    path=$(printf '%s' "$row" | jq -r '.path')
    address=$(printf '%s' "$row" | jq -r '.address')
    run_m65 -H -@ "$path@$address"
  done
  run_m65 -r -1 "$product"
  launch=$(date +%s%N)
  index=1
  for delay in 0 700 2400; do
    now=$(date +%s%N)
    target=$((launch + delay * 1000000))
    if [ "$target" -gt "$now" ]; then
      python3 - "$((target - now))" <<'PY'
import sys
import time
time.sleep(int(sys.argv[1]) / 1_000_000_000)
PY
    fi
    stamp=$(date +%s%N)
    printf '%s\n' "$(((stamp - launch) / 1000000))" \
      > "$OUT/l10-capture-$index-ms.txt"
    readback 0x0000c356 1156 "$OUT/l10-capture-$index.bin"
    index=$((index + 1))
  done
}

mkdir -p "$OUT"
fresh_start_gate fresh-start
readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
media=$(jq -r '.candidate.media.path' "$DEPLOY")
remote=$(jq -r '.candidate.remote_media' "$DEPLOY")
ftp_with_progress_guard "$media" "$remote" first
boot_candidate m1

for id in m1-helper m1-clear m1-mul-input m1-mul-low m1-mul-high \
          m1-div-clear m1-div-input m1-div-quotient m1-div-fraction; do
  run_row "$id"
done

fresh_start_gate pre-l10-basic
run_l10

fresh_start_gate post-l10-basic
ftp_with_progress_guard "$media" "$remote" second
boot_candidate m3
for id in m3-multiply m3-divide m3-half-away; do
  run_row "$id"
done

readback 0x0000ff83 2 "$OUT/time-before.bin"
date +%s%N > "$OUT/time-start-ns.txt"
sleep 4
date +%s%N > "$OUT/time-end-ns.txt"
readback 0x0000ff83 2 "$OUT/time-after.bin"

run_row m5-require-place
readback 0x0000c1f4 2 "$OUT/m5-trace.bin"
readback 0x00050000 48 "$OUT/m5-c2d-header.bin"
readback 0x000500f0 32 "$OUT/m5-place-row.bin"

python3 "$PY" evaluate
