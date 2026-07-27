#!/bin/sh
# Receipt-less Link-30 fail-fast smoke with in-product frame measurements.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/hardware-presmoke-link30-hot-refill
CANDIDATE=build/c2.2/substitution/product-link-30-hot-refill
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
PREPARE_ONLY=0
BOOT_POLL_SECONDS=120
AUTHORIZATION_RECEIPT=

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --prepare-only       bind and emit the deployment/forms; do not touch hardware
  --out <dir>          output directory (default: $OUT)
  --candidate-dir <d>  candidate directory (default: $CANDIDATE)
  --authorization-receipt <file>
                        passed artifact-only replay authorizing that candidate
  --tools <dir>        m65tools directory (default: $TOOLS)
  --device <path>      JTAG serial device (default: $DEVICE)
  --boot-poll <sec>    prompt polling budget (default: $BOOT_POLL_SECONDS)
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) PREPARE_ONLY=1 ;;
    --out) shift; OUT=$1 ;;
    --candidate-dir) shift; CANDIDATE=$1 ;;
    --authorization-receipt) shift; AUTHORIZATION_RECEIPT=$1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --boot-poll) shift; BOOT_POLL_SECONDS=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

DEPLOY=$OUT/deployment.json
LATENCY=$OUT/latency
python3 tools/host-lisp/c2_hot_refill_hw_presmoke.py selftest
if [ -e "$DEPLOY" ]; then
  set -- python3 tools/host-lisp/c2_product_hw_presmoke.py verify \
    --out "$OUT" --candidate-dir "$CANDIDATE"
else
  set -- python3 tools/host-lisp/c2_product_hw_presmoke.py prepare \
    --out "$OUT" --candidate-dir "$CANDIDATE"
fi
if [ -n "$AUTHORIZATION_RECEIPT" ]; then
  set -- "$@" --authorization-receipt "$AUTHORIZATION_RECEIPT"
fi
"$@"
python3 tools/host-lisp/c2_hot_refill_hw_presmoke.py emit --out "$LATENCY"
[ "$PREPARE_ONLY" -eq 0 ] || exit 0

set -- sh scripts/c2-product-hw-presmoke.sh \
  --out "$OUT" --candidate-dir "$CANDIDATE" \
  --tools "$TOOLS" --device "$DEVICE" --timeout 30
if [ -n "$AUTHORIZATION_RECEIPT" ]; then
  set -- "$@" --authorization-receipt "$AUTHORIZATION_RECEIPT"
fi
"$@"

mkdir -p "$LATENCY"
prompt_seen=0
attempt=1
while [ "$attempt" -le "$BOOT_POLL_SECONDS" ]; do
  png="$LATENCY/boot-prompt-$attempt.png"
  ansi="$LATENCY/boot-prompt-$attempt.ansi.txt"
  text="$LATENCY/boot-prompt-$attempt.txt"
  timeout --kill-after=2s 30s "$TOOLS/m65" -l "$DEVICE" \
    --screenshot="$png" > "$ansi"
  python3 - "$ansi" "$text" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw))
PY
  if grep -Fq 'lisp65>' "$text"; then
    prompt_seen=1
    break
  fi
  sleep 1
  attempt=$((attempt + 1))
done
[ "$prompt_seen" -eq 1 ] || {
  echo "c2-hot-refill-hw-presmoke: FIRST RED no REPL in ${BOOT_POLL_SECONDS}s" >&2
  exit 1
}

run_form() {
  name=$1
  wait=$2
  sh scripts/hw-jtag-repl.sh \
    --file "$LATENCY/$name.forms" --tools "$TOOLS" --device "$DEVICE" \
    --out-dir "$LATENCY" --prefix "$name" --wait "$wait" \
    --timeout 30 --input-retry-wait 0.2 --verified-input
}

run_form boot_counter 3
run_form definition_setup 7
run_form definition_first_call 7
run_form warm_second_call 7

python3 tools/host-lisp/c2_hot_refill_hw_presmoke.py evaluate \
  --deployment "$DEPLOY" \
  --boot "$LATENCY/boot_counter.txt" \
  --cold "$LATENCY/definition_first_call.txt" \
  --warm "$LATENCY/warm_second_call.txt" \
  --out "$LATENCY/result.json"
