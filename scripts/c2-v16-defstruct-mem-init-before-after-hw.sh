#!/bin/sh
# Owner-authorized one-stop mem_init before/after witness contact.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v16_mem_init_before_after_contact.py
BUILD_PY=tools/host-lisp/c2_v16_mem_init_before_after.py
DEPLOY=build/c2.3/v1.6-defstruct-mem-init-before-after/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-mem-init-before-after-repeat-contact}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}
RESET_DOMAIN_BYTES=50816

case "$ACTION" in
  dry-run|stage|capture) ;;
  *) echo "usage: $0 <dry-run|stage|capture>" >&2; exit 2 ;;
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

if [ "$ACTION" = dry-run ]; then
  python3 "$BUILD_PY" check
  python3 "$PY" selftest
  python3 "$PY" prepare
  python3 "$PY" check
  echo "MEM_INIT BEFORE/AFTER DRY RUN PASS cold-reset physical-RUN quiet=27.653s stops=1"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
}
python3 "$BUILD_PY" check >/dev/null
python3 "$PY" check >/dev/null
mkdir -p "$OUT"

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/stage.ready" ] || { echo "before/after stage absent" >&2; exit 3; }
  exec python3 "$PY" capture --device "$DEVICE"
fi

[ ! -e "$OUT/stage.consumed" ] || {
  echo "before/after stage already consumed" >&2; exit 3;
}
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

RESET=$(jq -r '.mem_init_witness.reset.path' "$DEPLOY")
run_m65 -H -@ "$RESET@0x0000b582"
readback 0x0000b582 10 "$OUT/mem-init-witness-reset-readback.bin"
cmp "$RESET" "$OUT/mem-init-witness-reset-readback.bin"
readback 0x0005c640 64 "$OUT/pre-run-c2j.bin"
python3 - "$OUT/pre-run-c2j.bin" <<'PY'
from pathlib import Path
import sys
c2j = Path(sys.argv[1]).read_bytes()
assert c2j == b"\0" * 64
PY
run_m65 -r
sleep 3
screen launch-ready
python3 - "$OUT/launch-ready.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(errors="replace").casefold()
assert "ready." in text
assert "break" not in text and "monitor commands" not in text
assert "lisp65>" not in text
PY
: > "$OUT/stage.ready"
echo "MEM_INIT BEFORE/AFTER STAGE READY: type RUN and press RETURN physically."
