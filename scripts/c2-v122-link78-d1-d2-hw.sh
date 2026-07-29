#!/bin/sh
# One Link-78 device session: D1 full DIRMISS name, then D2's three lines.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
OUT=${C2_LINK78_HW_OUT:-build/post-release/link78-dirmiss-renderer/d1-d2-bundled-session}
DEPLOY=$OUT/deployment.json
OBS=$OUT/observed-rows.json
CONFIG=config/c2.2-link78-d1-d2-bundled-hardware-session.json
PY=tools/host-lisp/c2_v122_link78_d1_d2_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-60}
BOOT_POLL_LIMIT=${BOOT_POLL_LIMIT:-75}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp

usage() {
  echo "usage: $0 <start|verify>" >&2
  exit 2
}

case "$ACTION" in start|verify) ;; *) usage ;; esac

if [ "$ACTION" = verify ]; then
  python3 "$PY" verify
  exit
fi

[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}

python3 "$PY" verify
[ "$(jq '.rows | length' "$OBS")" -eq 0 ] || {
  echo "Link-78 D1/D2 session was already started" >&2
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

record_stop() {
  id=$1
  detail=$2
  python3 "$PY" record-stop --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png" \
    --detail "$detail"
  exit 4
}

run_result_row() {
  id=$1
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$CONFIG")
  expect=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .expected_result" "$CONFIG")
  poll=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .expect_poll_seconds" "$CONFIG")
  if OUT_DIR=$OUT PREFIX="row-$id" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input \
        --expect "$expect" --expect-poll "$poll" \
        --wait 1 --form "$form"; then
    python3 "$PY" record-row --id "$id" \
      --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"
  else
    if python3 - "$OUT/row-$id.png" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError:
    raise SystemExit(1)
PY
    then
      detail="exact result absent within ${poll}s"
    else
      detail="red fail-closed frame detected while awaiting the exact result"
    fi
    record_stop "$id" "$detail"
  fi
}

run_dirmiss() {
  id=dirmiss-full-name
  form=$(jq -r ".rows[] | select(.id == \"$id\") | .form" "$CONFIG")
  poll_limit=$(jq -r \
    ".rows[] | select(.id == \"$id\") | .expect_poll_seconds" "$CONFIG")
  if ! OUT_DIR=$OUT PREFIX="row-$id-input" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback \
        --form "$form"; then
    capture_screen "row-$id"
    record_stop "$id" "verified input transport failed"
  fi
  poll=0
  while [ "$poll" -lt "$poll_limit" ]; do
    capture_screen "row-$id"
    if grep -Eq \
        '^[[:space:]]*\*\*\* undefined function:[[:space:]]*intern-renderer-missing[[:space:]]*$' \
        "$OUT/row-$id.txt" &&
       grep -Eq '^[[:space:]]*lisp65>[[:space:]]*$' \
        "$OUT/row-$id.txt"; then
      break
    fi
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt "$poll_limit" ] ||
    record_stop "$id" "complete DIRMISS name and live prompt absent within ${poll_limit}s"
  python3 "$PY" record-row --id "$id" \
    --screen "$OUT/row-$id.txt" --image "$OUT/row-$id.png"
}

media=$(jq -r '.media.path' "$DEPLOY")
remote=$(jq -r '.remote_media' "$DEPLOY")
timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
  -c "put $media $remote" \
  -c "get $remote $OUT/uploaded-media-readback.d81" \
  -c "mount $remote" \
  -c exit > "$OUT/media-upload.log"
cmp "$media" "$OUT/uploaded-media-readback.d81"

readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
prg=$(jq -r '.product.path' "$DEPLOY")
# The FTP reset established the mounted D81. Do not issue a second full reset
# while loading the Link-78 product and its bound preloads.
run_m65 -H -1 "$prg"
jq -c '.preloads[]' "$DEPLOY" |
while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  base=$(basename "$path")
  run_m65 -H -@ "$path@$address"
  readback "$((address))" "$bytes" "$OUT/readback-$base"
  cmp "$path" "$OUT/readback-$base"
done
run_m65 -r -1 "$prg"

sleep 3
capture_screen autorun-probe
if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/autorun-probe.txt" &&
   ! grep -q 'lisp65>' "$OUT/autorun-probe.txt"; then
  run_m65 -t '~M'
fi
boot_poll=0
while [ "$boot_poll" -lt "$BOOT_POLL_LIMIT" ]; do
  capture_screen boot
  grep -q 'lisp65>' "$OUT/boot.txt" && break
  sleep 1
  boot_poll=$((boot_poll + 1))
done
[ "$boot_poll" -lt "$BOOT_POLL_LIMIT" ] || {
  echo "Link-78 session terminal: no Lisp REPL within boot poll limit" >&2
  exit 3
}

run_dirmiss
run_result_row post-dirmiss-repl
run_result_row require-defstruct
run_result_row define-point
run_result_row construct-point
python3 "$PY" finalize
