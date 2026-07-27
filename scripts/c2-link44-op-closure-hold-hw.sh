#!/bin/sh
# Class-B cycle 2: exact two-byte Link-44 OP_CLOSURE hold diagnostic.
set -eu
cd "$(dirname "$0")/.."

PY=tools/host-lisp/c2_lite_v6_link44_op_closure_hold_hw.py
OUT=build/c2.2/hardware-link44-op-closure-hold-cycle2
DEPLOY=$OUT/deployment.json
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

python3 "$PY" selftest
if [ ! -e tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link44-op-closure-hold-cycle2-patch-receipt.json ]; then
  python3 "$PY" build
else
  python3 "$PY" check
fi
if [ ! -e "$DEPLOY" ]; then
  python3 "$PY" prepare-hardware
else
  python3 "$PY" verify-hardware
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link44-op-closure-hold-hardware-cycle2-receipt.json
[ ! -e "$RECEIPT" ] || { echo "Class-B cycle 2 already consumed" >&2; exit 3; }
M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Link 44 OP_CLOSURE hold — nonpromotable Class-B cycle 2/3"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"
echo "    exactly two patched operand bytes; exactly one form; six read-only captures"

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

# The cycle is not exercised until a genuinely empty Lisp prompt exists.
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
    echo "boot did not reach an empty Lisp prompt; Class-B cycle not exercised" >&2
    exit 4
  }
  sleep 2
done
chmod 0444 "$OUT/before-expression.png" "$OUT/before-expression.ansi.txt" \
  "$OUT/before-expression.txt"

scripts/hw-jtag-repl.sh --tools "$TOOLS" --device "$DEVICE" \
  --out-dir "$OUT" --prefix op-closure-one-form --verified-input --no-readback \
  --form '(list(peek 255 132)(peek 255 131)(peek 255 132))'
FORM_RETURN_NS=$(date +%s%N)

# Allow the one expression to reach the patched negative dir_find edge.  The
# first capture is "immediate" relative to confirmed hold, not to keyboard I/O.
sleep 1
capture_pair() {
  index=$1
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "0x00000016:0x0000001c=$OUT/capture-$index-zp-0016-001b.bin"
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "0x0000bfd9:0x0000c023=$OUT/capture-$index-vm-bfd9-c022.bin"
  date +%s%N
}

T1_NS=$(capture_pair 1)
sleep 0.25
T2_NS=$(capture_pair 2)
sleep 0.75
T3_NS=$(capture_pair 3)
T1_MS=$(((T1_NS - FORM_RETURN_NS) / 1000000))
T2_MS=$(((T2_NS - FORM_RETURN_NS) / 1000000))
T3_MS=$(((T3_NS - FORM_RETURN_NS) / 1000000))
jq -n --arg reference "form-return-submitted" \
  --argjson t1 "$T1_MS" --argjson t2 "$T2_MS" --argjson t3 "$T3_MS" \
  '{reference:$reference,captures:[
    {capture:1,elapsed_after_form_return_ms:$t1},
    {capture:2,elapsed_after_form_return_ms:$t2},
    {capture:3,elapsed_after_form_return_ms:$t3}
  ]}' > "$OUT/capture-timing.json"

python3 "$PY" evaluate-hardware
