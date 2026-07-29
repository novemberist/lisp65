#!/bin/sh
# Deploy the nonpromotable Link-74 LIT(1) two-timepoint identity.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-prepare}
OUT=build/post-promotion/link74-asm-z-boundary/lit1-two-timepoint-NONPROMOTABLE
PY=tools/host-lisp/c2_link74_lit1_two_timepoint_hw.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-40}

case "$ACTION" in
  prepare)
    python3 "$PY" prepare
    python3 "$PY" verify
    ;;
  verify)
    python3 "$PY" verify
    ;;
  deploy)
    python3 "$PY" verify
    [ -x "$M65" ] || {
      echo "missing MEGA65 tool: $M65" >&2
      exit 3
    }
    [ -c "$DEVICE" ] || {
      echo "missing JTAG serial device: $DEVICE" >&2
      exit 3
    }
    prg=$(jq -r '.product.path' "$OUT/deployment.json")
    timeout --kill-after=2s "${TIMEOUT}s" \
      "$M65" -l "$DEVICE" -F -H -1 "$prg"
    jq -c '.preloads[]' "$OUT/deployment.json" |
    while IFS= read -r item; do
      path=$(printf '%s' "$item" | jq -r '.path')
      address=$(printf '%s' "$item" | jq -r '.address')
      bytes=$(printf '%s' "$item" | jq -r '.bytes')
      name=$(basename "$path")
      timeout --kill-after=2s "${TIMEOUT}s" \
        "$M65" -l "$DEVICE" -H -@ "$path@$address"
      end=$((address + bytes))
      timeout --kill-after=2s "${TIMEOUT}s" \
        "$M65" -l "$DEVICE" --memsave \
        "0x$(printf '%08x' "$address"):0x$(printf '%08x' "$end")=$OUT/readback-$name"
      cmp "$path" "$OUT/readback-$name"
    done
    timeout --kill-after=2s "${TIMEOUT}s" \
      "$M65" -l "$DEVICE" -r -1 "$prg"
    echo "Link-74 LIT1 diagnostic deployed; wait for the physical REPL."
    ;;
  capture)
    python3 "$PY" capture
    ;;
  *)
    echo "usage: $0 [prepare|verify|deploy|capture]" >&2
    exit 2
    ;;
esac
