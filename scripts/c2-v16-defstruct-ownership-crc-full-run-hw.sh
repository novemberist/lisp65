#!/bin/sh
# Owner-authorized G4-corrected physical boot + quiet defstruct full run.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_ownership_crc_full_run.py
DEPLOY=build/c2.3/v1.6-defstruct-ownership-crc-bound/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-ownership-crc-full-run}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}
RESET_DOMAIN_BYTES=50816

case "$ACTION" in
  dry-run|stage|verify-boot|arm|capture) ;;
  *) echo "usage: $0 <dry-run|stage|verify-boot|arm|capture>" >&2; exit 2 ;;
esac

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
  echo "OWNERSHIP-CRC FULL-RUN DRY RUN PASS reset-domain=50816 C2J=CLEAR physical-input=3 quiet=180s stops=1"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" check >/dev/null
mkdir -p "$OUT"

if [ "$ACTION" = stage ]; then
  [ ! -e "$OUT/stage.consumed" ] || { echo "full-run stage already consumed" >&2; exit 3; }
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

  PRODUCT=$(jq -r '.diagnostic.prg.path' "$DEPLOY")
  run_m65 -H "$PRODUCT"
  payload_bytes=$(($(wc -c < "$PRODUCT") - 2))
  readback 0x2001 "$payload_bytes" "$OUT/diagnostic-prg-payload.bin"
  python3 - "$PRODUCT" "$OUT/diagnostic-prg-payload.bin" <<'PY'
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

  reset_rows=$(jq '[.diagnostic.preloads[] | select(.role == "c2d-v6-reset-domain")] | length' "$DEPLOY")
  [ "$reset_rows" -eq 1 ] || { echo "one reset-domain preload required" >&2; exit 3; }
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
c2j = Path(sys.argv[1]).read_bytes()
assert c2j == b"\0" * 64
PY
  python3 - "$OUT/stage.json" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
Path(sys.argv[1]).write_text(json.dumps({
    "status": "STAGE READY", "complete_reset_domain_readback": True,
    "C2J_CLEAR_before_RUN": True,
    "recorded_at": datetime.now(timezone.utc).isoformat(),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  : > "$OUT/stage.ready"
  # This is the final monitor operation before the owner's physical RUN.
  run_m65 -r
  echo "OWNERSHIP-CRC FULL RUN STAGE READY: type RUN and press RETURN physically."
  exit 0
fi

if [ "$ACTION" = verify-boot ]; then
  [ -e "$OUT/stage.ready" ] || { echo "full-run stage absent" >&2; exit 3; }
  [ ! -e "$OUT/boot.consumed" ] || { echo "boot verification already consumed" >&2; exit 3; }
  : > "$OUT/boot.consumed"
  sleep 27.653
  screen boot-first-observation
  python3 - "$OUT/boot-first-observation.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "lisp65>" in text
assert "monitor commands" not in text
PY
  : > "$OUT/boot.ready"
  echo "BOOT PROMPT VERIFIED: type (require 'defstruct) physically and wait for t."
  exit 0
fi

if [ "$ACTION" = arm ]; then
  [ -e "$OUT/boot.ready" ] || { echo "verified boot absent" >&2; exit 3; }
  [ ! -e "$OUT/arm.consumed" ] || { echo "record arm already consumed" >&2; exit 3; }
  : > "$OUT/arm.consumed"
  screen require-result
  python3 - "$OUT/require-result.txt" <<'PY'
from pathlib import Path
import sys
lines = [line.strip().casefold() for line in
         Path(sys.argv[1]).read_text(errors="replace").splitlines() if line.strip()]
assert "lisp65>" in "\n".join(lines)
assert "t" in lines
PY
  record=$(($(jq -r '.record.address' "$DEPLOY")))
  record_hex=0x$(printf '%08x' "$record")
  RESET=$(jq -r '.record.reset.path' "$DEPLOY")
  ARM=$(jq -r '.record.arm.path' "$DEPLOY")
  # No readback after the owner-visible require result: reset and arm are the
  # canonical handoff, and the first observation belongs after defstruct.
  run_m65 -H -@ "$RESET@$record_hex"
  run_m65 -H -@ "$ARM@$record_hex"
  : > "$OUT/arm.ready"
  run_m65 -r
  echo "R/A/I/G RECORD ARMED: type (defstruct point x y) physically, then immediately return here."
  exit 0
fi

[ -e "$OUT/stage.ready" ] && [ -e "$OUT/boot.ready" ] && [ -e "$OUT/arm.ready" ] || {
  echo "stage/boot/arm handoff incomplete" >&2; exit 3;
}
exec python3 "$PY" capture --device "$DEVICE"
