#!/bin/sh
# Receipt-less fail-fast hardware pre-smoke for a SHA-bound C2 candidate.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/hardware-presmoke-link25
DEPLOY=$OUT/deployment.json
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
TIMEOUT=30
prepare_only=0
dry_run=0
candidate_dir=
authorization_receipt=

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --prepare-only     verify and prepare artifacts, do not touch hardware
  --dry-run          print hardware commands only
  --out <dir>        pre-smoke preparation directory
  --candidate-dir <dir>
                     structurally passed candidate directory (receipt-less)
  --authorization-receipt <file>
                     passed artifact-only replay authorizing that candidate
  --tools <dir>      m65tools directory (default: $TOOLS)
  --device <path>    JTAG serial device (default: $DEVICE)
  --timeout <sec>    timeout per hardware operation (default: $TIMEOUT)
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prepare-only) prepare_only=1 ;;
    --dry-run) dry_run=1 ;;
    --out) shift; OUT=$1; DEPLOY=$OUT/deployment.json ;;
    --candidate-dir) shift; candidate_dir=$1 ;;
    --authorization-receipt) shift; authorization_receipt=$1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --timeout) shift; TIMEOUT=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

if [ -e "$DEPLOY" ]; then
  if [ -n "$candidate_dir" ]; then
    set -- python3 tools/host-lisp/c2_product_hw_presmoke.py verify --out "$OUT" \
      --candidate-dir "$candidate_dir"
    if [ -n "$authorization_receipt" ]; then
      set -- "$@" --authorization-receipt "$authorization_receipt"
    fi
    "$@"
  else
    python3 tools/host-lisp/c2_product_hw_presmoke.py verify --out "$OUT"
  fi
else
  if [ -n "$candidate_dir" ]; then
    set -- python3 tools/host-lisp/c2_product_hw_presmoke.py prepare --out "$OUT" \
      --candidate-dir "$candidate_dir"
    if [ -n "$authorization_receipt" ]; then
      set -- "$@" --authorization-receipt "$authorization_receipt"
    fi
    "$@"
  else
    python3 tools/host-lisp/c2_product_hw_presmoke.py prepare --out "$OUT"
  fi
fi

echo "==> SHA-bound C2 product pre-smoke"
echo "    receipt-less, fail-fast, no promotion and no acceptance claim"
echo "    product_sha=$(jq -r '.product.sha256' "$DEPLOY")"

[ "$prepare_only" = 0 ] || exit 0

PRG=$(jq -r '.product.path' "$DEPLOY")
run_cmd() {
  if [ "$dry_run" = 1 ]; then
    printf 'DRY-RUN:'
    for argument in "$@"; do printf ' %s' "$argument"; done
    printf '\n'
  else
    "$@"
  fi
}

if [ "$dry_run" = 0 ]; then
  [ -x "$TOOLS/m65" ] || { echo "missing JTAG loader: $TOOLS/m65" >&2; exit 3; }
  [ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }
fi

# Reset and place the exact PRG in low memory without starting it. Every
# external image is then injected and independently read back before the
# owned window is published by the product itself.
run_cmd timeout "${TIMEOUT}s" "$TOOLS/m65" -l "$DEVICE" -F -H -1 "$PRG"

jq -c '.preloads[]' "$DEPLOY" | while IFS= read -r item; do
  path=$(printf '%s' "$item" | jq -r '.path')
  address=$(printf '%s' "$item" | jq -r '.address')
  bytes=$(printf '%s' "$item" | jq -r '.bytes')
  end=$(printf '%08x' "$((address + bytes))")
  name=$(basename "$path")
  readback="$OUT/readback-$name"
  run_cmd timeout "${TIMEOUT}s" "$TOOLS/m65" -l "$DEVICE" -H -@ "$path@$address"
  run_cmd timeout "${TIMEOUT}s" "$TOOLS/m65" -l "$DEVICE" \
    --memsave "$address:0x$end=$readback"
  run_cmd cmp "$path" "$readback"
done

# Reloading the same SHA-bound PRG cannot alter the verified Attic inputs.
# It starts normal CRT/bootstrap execution; the product performs the actual
# publish-last $E000 handoff and CRC check on-device.
run_cmd timeout "${TIMEOUT}s" "$TOOLS/m65" -l "$DEVICE" -r -1 "$PRG"

cat <<'EOF'
Manual receipt-less sequence (stop on the first deviation):
  1. Confirm the Lisp65 banner and a usable REPL.
  2. Evaluate (+ 1 2); expect 3.
  3. Read (peek 255 135) and (peek 255 136); expect 1 and 4.
  4. Read (peek 255 131) twice less than five seconds apart; values must advance.
  5. Define (defun c2loop () (c2loop)), call (c2loop), then press RUN/STOP;
     expect the stopped message and a usable REPL.
  6. Open and leave the Freezer. Confirm the REPL remains usable, then evaluate
     (+ 4 5); expect 9. Re-read $FF87/$FF88; expect 1 and 4.
  7. Enter the editor and physically sample Control-Space and Meta-X; both must
     produce their generated L-full actions. Exit with C-x C-c.
This is a fail-fast smoke only. Do not create an acceptance receipt from it.
EOF
