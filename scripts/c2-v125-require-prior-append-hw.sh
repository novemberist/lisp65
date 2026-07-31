#!/bin/sh
# Link-82 acceptance row: two ordinary appends, then require twice.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v125_require_prior_append_hardware.py
DEPLOY=build/c2.2/v1.2.5-require-prior-append-hardware/deployment.json
OUT=build/c2.2/v1.2.5-require-prior-append-hardware/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|start|evaluate) ;;
  *) echo "usage: $0 <dry-run|start|evaluate>" >&2; exit 2 ;;
esac

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  echo "DRY-RUN: cold reset; assert BASIC 65 READY.; upload/readback package"
  echo "DRY-RUN: deploy exact Link 82; execute four acceptance rows"
  echo "DRY-RUN: compare full C2D and Bank 2 across repeat; C2J CLEAR"
  exit
fi
if [ "$ACTION" = evaluate ]; then
  python3 "$PY" evaluate
  exit
fi

python3 "$PY" prepare
mkdir -p "$OUT"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}
readback() {
  start=$1 bytes=$2 path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}
capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re, sys
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
poll_text() {
  prefix=$1 pattern=$2 limit=$3
  poll=0
  while [ "$poll" -lt "$limit" ]; do
    capture_screen "$prefix"
    fail_if_red "$OUT/$prefix.png"
    grep -Fq "$pattern" "$OUT/$prefix.txt" && return 0
    sleep 1
    poll=$((poll + 1))
  done
  return 1
}
ftp_package() {
  media=$1 remote=$2
  log=$OUT/package-upload.log
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $OUT/package-readback.d81" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  last=-1
  progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last" ]; then
      last=$size
      progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  wait "$pid"
}
run_form() {
  id=$1 form=$2 expected=$3
  OUT_DIR="$OUT" PREFIX="$id-input" TIMEOUT_SEC="$TIMEOUT" \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  poll=0
  while [ "$poll" -lt 120 ]; do
    capture_screen "$id"
    fail_if_red "$OUT/$id.png"
    if python3 "$PY" screen --path "$OUT/$id.txt" \
         --form "$form" --expected "$expected" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    poll=$((poll + 1))
  done
  echo "$id produced no exact result" >&2
  return 1
}

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ]
product=$(jq -r '.candidate.product.path' "$DEPLOY")
media=$(jq -r '.candidate.package_medium.path' "$DEPLOY")

run_m65 -F
sleep 3
poll_text fresh-start 'READY.' 30
grep -q 'BASIC 65' "$OUT/fresh-start.txt"
! grep -q 'lisp65>' "$OUT/fresh-start.txt"
ftp_package "$media" L82V125.D81
cmp "$media" "$OUT/package-readback.d81"

run_m65 -H -1 "$product"
jq -c '.candidate.preloads[]' "$DEPLOY" |
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
poll_text boot 'lisp65>' 75

jq -c '.rows[]' "$DEPLOY" |
while IFS= read -r item; do
  id=$(printf '%s' "$item" | jq -r '.id')
  form=$(printf '%s' "$item" | jq -r '.form')
  expected=$(printf '%s' "$item" | jq -r '.expected')
  run_form "$id" "$form" "$expected"
  if [ "$id" = require-after-two-ordinary-appends ]; then
    readback 0x00050000 50752 "$OUT/after-first-require-c2d.bin"
    readback 0x00020000 65536 "$OUT/after-first-require-bank2.bin"
  fi
done

readback 0x00050000 50752 "$OUT/after-repeat-c2d.bin"
readback 0x00020000 65536 "$OUT/after-repeat-bank2.bin"
readback 0x0005c640 64 "$OUT/final-c2j.bin"
cmp "$OUT/after-first-require-c2d.bin" "$OUT/after-repeat-c2d.bin"
cmp "$OUT/after-first-require-bank2.bin" "$OUT/after-repeat-bank2.bin"
python3 "$PY" evaluate
