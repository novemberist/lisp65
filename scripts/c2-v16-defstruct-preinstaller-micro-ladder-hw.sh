#!/bin/sh
# Owner-authorized one-stop pre-installer micro-ladder contact.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
BUILD_PY=tools/host-lisp/c2_v16_preinstaller_micro_ladder.py
CONTACT_PY=tools/host-lisp/c2_v16_preinstaller_micro_ladder_contact.py
DEPLOY=build/c2.3/v1.6-defstruct-preinstaller-micro-ladder/deployment.json
OUT=${OUT:-build/c2.3/v1.6-defstruct-closing-session/d2-preinstaller-micro-ladder-contact}
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
  python3 "$CONTACT_PY" selftest
  python3 "$CONTACT_PY" check
  echo "PREINSTALLER MICRO-LADDER DRY RUN PASS reset-domain=50816 C2J=CLEAR physical-RUN quiet=27.653s stops=1"
  exit 0
fi

[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
}
python3 "$BUILD_PY" check >/dev/null
python3 "$CONTACT_PY" check >/dev/null
mkdir -p "$OUT"

if [ "$ACTION" = capture ]; then
  [ -e "$OUT/stage.ready" ] || { echo "micro-ladder stage absent" >&2; exit 3; }
  exec python3 "$CONTACT_PY" capture --device "$DEVICE"
fi

[ ! -e "$OUT/stage.consumed" ] || {
  echo "micro-ladder stage already consumed" >&2; exit 3;
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

# Every preload gets a complete reset-domain readback; no prefix-only staging.
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
assert c2j == b"\0" * 64  # C2J CLEAR before RUN
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
python3 - "$OUT/stage.json" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
Path(sys.argv[1]).write_text(json.dumps({
    "status": "STAGE READY",
    "complete_reset_domain_readback": True,
    "C2J_CLEAR_before_RUN": True,
    "recorded_at": datetime.now(timezone.utc).isoformat(),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
: > "$OUT/stage.ready"
echo "PREINSTALLER MICRO-LADDER STAGE READY: type RUN and press RETURN physically."
