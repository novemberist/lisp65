#!/bin/sh
# One-site, JTAG-raw, nonpromotable Class-B cycle 1 for Link 44.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/hardware-link44-vm-run-dir-latch-cycle1
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_lite_v6_link44_vm_run_dir_latch_hw.py
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
TIMEOUT=30
BOOT_TIMEOUT=75
PREPARE_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) PREPARE_ONLY=1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --timeout) shift; TIMEOUT=$1 ;;
    --boot-timeout) shift; BOOT_TIMEOUT=$1 ;;
    *) echo "unexpected option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ ! -e "$DEPLOY" ]; then
  python3 "$PY" prepare
else
  python3 "$PY" verify
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link44-vm-run-dir-latch-hardware-cycle1-receipt.json
[ ! -e "$RECEIPT" ] || { echo "Class-B cycle 1 already consumed" >&2; exit 3; }
M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Link 44 vm_run_dir one-site latch — nonpromotable Class-B cycle 1/3"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"
echo '    exactly one form; raw latch $BFC3..$BFC6; no latency claim'

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -F -H -1 "$PRG"
jq -c '.preloads[]' "$DEPLOY" | while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  end=$(printf '%08x' "$((address + bytes))")
  readback="$OUT/readback-$(basename "$path")"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -H -@ "$path@$address"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "$address:0x$end=$readback"
  cmp "$path" "$readback"
  chmod 0444 "$readback"
done
timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -r -1 "$PRG"

# Do not type until a genuinely empty Lisp prompt is visible. This poll is
# read-only and submits no form, so a slow boot cannot consume the cycle.
deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
while :; do
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --screenshot="$OUT/before-expression.png" > "$OUT/before-expression.ansi.txt"
  python3 - "$OUT/before-expression.ansi.txt" "$OUT/before-expression.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw))
PY
  if python3 tools/host-lisp/repl_screen_check.py \
      --screen "$OUT/before-expression.txt" --form-text "" --active-input \
      >/dev/null 2>&1; then
    break
  fi
  [ "$(date +%s)" -lt "$deadline" ] || {
    echo "boot did not reach an empty Lisp prompt; cycle not exercised" >&2
    exit 4
  }
  sleep 2
done
chmod 0444 "$OUT/before-expression.png" "$OUT/before-expression.ansi.txt" \
  "$OUT/before-expression.txt"

scripts/hw-jtag-repl.sh --tools "$TOOLS" --device "$DEVICE" \
  --out-dir "$OUT" --prefix vm-run-dir-one-form --verified-input --no-readback \
  --form '(list(peek 255 132)(peek 255 131)(peek 255 132))'

# Poll only the four agreed scratch bytes.  0x8201 proves that site 1 fired;
# timeout still produces the final four-byte witness for the sequential move.
poll_deadline=$(( $(date +%s) + 12 ))
while :; do
  rm -f "$OUT/latch-poll.bin"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "0x0000bfc3:0x0000bfc7=$OUT/latch-poll.bin"
  if python3 - "$OUT/latch-poll.bin" <<'PY'
from pathlib import Path
import struct, sys
raw = Path(sys.argv[1]).read_bytes()
raise SystemExit(0 if len(raw) == 4 and struct.unpack("<HH", raw)[1] == 0x8201 else 1)
PY
  then
    break
  fi
  [ "$(date +%s)" -lt "$poll_deadline" ] || break
  sleep 0.25
done
mv "$OUT/latch-poll.bin" "$OUT/latch-bfc3-bfc6.bin"

timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
  --screenshot="$OUT/after-expression.png" > "$OUT/after-expression.ansi.txt"
python3 - "$OUT/after-expression.ansi.txt" "$OUT/after-expression.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw))
PY

python3 "$PY" evaluate
