#!/bin/sh
# Final Class-B cycle 3: stable c2_dma_list identity at OP_CLOSURE dir_find.
set -eu
cd "$(dirname "$0")/.."

PY=tools/host-lisp/c2_lite_v6_link44_op_closure_cycle3_hw.py
OUT=build/c2.2/hardware-link44-op-closure-stable-descriptor-cycle3
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

if [ ! -e "$DEPLOY" ]; then
  python3 "$PY" prepare
else
  python3 "$PY" verify
fi
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link44-op-closure-stable-descriptor-hardware-cycle3-receipt.json
[ ! -e "$RECEIPT" ] || { echo "Class-B cycle 3 already consumed" >&2; exit 3; }
M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$DEPLOY")
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

echo "==> Link 44 OP_CLOSURE stable descriptor — final Class-B cycle 3/3"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"
echo "    existing two-byte hold; one form; descriptor/nameoff/name each captured 3x"

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
    echo "boot did not reach an empty Lisp prompt; final Class-B cycle not exercised" >&2
    exit 4
  }
  sleep 2
done
chmod 0444 "$OUT/before-expression.png" "$OUT/before-expression.ansi.txt" \
  "$OUT/before-expression.txt"

scripts/hw-jtag-repl.sh --tools "$TOOLS" --device "$DEVICE" \
  --out-dir "$OUT" --prefix op-closure-cycle3-one-form --verified-input --no-readback \
  --form '(list(peek 255 132)(peek 255 131)(peek 255 132))'
FORM_RETURN_NS=$(date +%s%N)

sleep 1
capture() {
  start=$1
  end=$2
  path=$3
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" --memsave "$start:$end=$path"
  date +%s%N
}

D1_NS=$(capture 0x0000ba00 0x0000ba0c "$OUT/capture-1-dma-list-ba00-ba0b.bin")
sleep 0.25
D2_NS=$(capture 0x0000ba00 0x0000ba0c "$OUT/capture-2-dma-list-ba00-ba0b.bin")
sleep 0.75
D3_NS=$(capture 0x0000ba00 0x0000ba0c "$OUT/capture-3-dma-list-ba00-ba0b.bin")
python3 "$PY" capture-plan

if [ "$(jq -r '.status' "$OUT/descriptor-capture-plan.json")" = \
     "passed-stable-descriptor-ready-for-nameoff-capture" ]; then
  NO_START=$(jq -r '.nameoff_capture.start' "$OUT/descriptor-capture-plan.json")
  NO_END=$(jq -r '.nameoff_capture.end_exclusive' "$OUT/descriptor-capture-plan.json")
  N1_NS=$(capture "$NO_START" "$NO_END" "$OUT/capture-1-nameoff.bin")
  sleep 0.25
  N2_NS=$(capture "$NO_START" "$NO_END" "$OUT/capture-2-nameoff.bin")
  sleep 0.75
  N3_NS=$(capture "$NO_START" "$NO_END" "$OUT/capture-3-nameoff.bin")
  python3 "$PY" name-plan
else
  N1_NS=$D3_NS
  N2_NS=$D3_NS
  N3_NS=$D3_NS
fi

if [ -e "$OUT/name-capture-plan.json" ] && \
   [ "$(jq -r '.status' "$OUT/name-capture-plan.json")" = \
     "passed-stable-nameoff-ready-for-name-capture" ]; then
  NAME_START=$(jq -r '.name_capture.start' "$OUT/name-capture-plan.json")
  NAME_END=$(jq -r '.name_capture.end_exclusive' "$OUT/name-capture-plan.json")
  S1_NS=$(capture "$NAME_START" "$NAME_END" "$OUT/capture-1-symbol-name-window.bin")
  sleep 0.25
  S2_NS=$(capture "$NAME_START" "$NAME_END" "$OUT/capture-2-symbol-name-window.bin")
  sleep 0.75
  S3_NS=$(capture "$NAME_START" "$NAME_END" "$OUT/capture-3-symbol-name-window.bin")
else
  S1_NS=$N3_NS
  S2_NS=$N3_NS
  S3_NS=$N3_NS
fi

python3 - "$OUT/capture-timing.json" "$FORM_RETURN_NS" \
  "$D1_NS" "$D2_NS" "$D3_NS" "$N1_NS" "$N2_NS" "$N3_NS" \
  "$S1_NS" "$S2_NS" "$S3_NS" <<'PY'
import json
from pathlib import Path
import sys
out = Path(sys.argv[1])
base = int(sys.argv[2])
values = [int(item) for item in sys.argv[3:]]
groups = ("descriptor", "nameoff", "name")
payload = {"reference": "form-return-submitted", "groups": {}}
for group_index, group in enumerate(groups):
    payload["groups"][group] = [
        {"capture": index + 1,
         "elapsed_after_form_return_ms":
             (values[group_index * 3 + index] - base) // 1_000_000}
        for index in range(3)]
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

python3 "$PY" evaluate
