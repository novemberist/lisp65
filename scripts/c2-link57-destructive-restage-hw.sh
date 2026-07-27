#!/bin/sh
# Same-identity C4 destructive-restage hardware fixture for Link 57.
set -eu
cd "$(dirname "$0")/.."

OUT=build/c2.2/destructive-restage-link57
FIXTURE=$OUT/fixture.json
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
TIMEOUT=30
WAIT=32
ACTION=
DRY_RUN=0
STALE_OUTPUT=
DEFINITION_OUTPUT=
CALL_OUTPUT=

usage() {
  cat >&2 <<EOF
usage: $0 <prepare|negative|confirm-negative|repair|final> [options]
  --dry-run          print hardware commands only
  --tools <dir>      m65tools directory (default: $TOOLS)
  --device <path>    JTAG serial device (default: $DEVICE)
  --timeout <sec>    timeout per JTAG operation (default: $TIMEOUT)
  --wait <sec>       boot observation wait (default: $WAIT)
  --stale-output <s> exact operator-observed stale-call output (final only)
  --definition-output <s>
                     exact definition echo (final only)
  --call-output <s>  exact fresh-call output (final only)

The five actions are ordered and single-use:
  prepare   verify the SHA-bound host fixture; never touches hardware
  negative  install the torn predecessor and capture fail-closed rejection
  confirm-negative
            bind the operator-observed E25 screen
  repair    cold-restage the same Link-57 identity and leave it at the REPL
  final     after the three printed REPL observations were confirmed, capture
            the fresh append and issue the final C4 hardware receipt
EOF
  exit 2
}

[ "$#" -gt 0 ] || usage
ACTION=$1
shift
case "$ACTION" in
  prepare|negative|confirm-negative|repair|final) ;;
  *) usage ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --timeout) shift; TIMEOUT=$1 ;;
    --wait) shift; WAIT=$1 ;;
    --stale-output) shift; STALE_OUTPUT=$1 ;;
    --definition-output) shift; DEFINITION_OUTPUT=$1 ;;
    --call-output) shift; CALL_OUTPUT=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

PY=tools/host-lisp/c2_destructive_restage.py
python3 "$PY" verify --out "$OUT"
[ "$ACTION" != prepare ] || exit 0

if [ "$ACTION" = confirm-negative ]; then
  python3 "$PY" confirm-negative --out "$OUT" --confirm-negative-screen
  exit 0
fi

M65=$TOOLS/m65
PRG=$(jq -r '.product.path' "$FIXTURE")
PRODUCT_SHA=$(jq -r '.product.sha256' "$FIXTURE")
HW_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-product-link57-destructive-restage-hardware-receipt.json

run_cmd() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'DRY-RUN:'
    for argument in "$@"; do
      printf ' %s' "$argument"
    done
    printf '\n'
  else
    "$@"
  fi
}

if [ "$DRY_RUN" -eq 0 ]; then
  [ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
  [ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }
fi

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$(printf '%08x' "$((rb_start + rb_bytes))")
  run_cmd timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" \
    --memsave "0x$(printf '%08x' "$rb_start"):0x$rb_end=$rb_path"
}

upload_and_verify() {
  uv_path=$1
  uv_address=$2
  uv_bytes=$3
  uv_readback_path=$4
  run_cmd timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -H \
    -@ "$uv_path@0x$(printf '%08x' "$uv_address")"
  readback "$uv_address" "$uv_bytes" "$uv_readback_path"
  run_cmd cmp "$uv_path" "$uv_readback_path"
}

hold_product() {
  run_cmd timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -F -H -1 "$PRG"
}

upload_normal_preloads() {
  np_label=$1
  jq -c '.normal_immutable_preloads_without_c2d[]' "$FIXTURE" |
  while IFS= read -r item; do
    np_path=$(printf '%s' "$item" | jq -r '.path')
    np_address=$(printf '%s' "$item" | jq -r '.address')
    np_bytes=$(printf '%s' "$item" | jq -r '.bytes')
    np_name=$(basename "$np_path")
    upload_and_verify "$np_path" "$np_address" "$np_bytes" \
      "$OUT/$np_label-prestart-$np_name"
  done
}

patch_stale_tuple() {
  jq -r '.volatile_tuple | to_entries[] |
    [.value.address,.value.patch.path,.value.patch.bytes,.key] | @tsv' "$FIXTURE" |
  while IFS="$(printf '\t')" read -r pt_address pt_path pt_bytes pt_name; do
    upload_and_verify "$pt_path" "$pt_address" "$pt_bytes" \
      "$OUT/negative-prestart-stale-$pt_name.bin"
  done
}

verify_bank5_post_overlay() {
  vo_label=$1
  vo_reset_image=$2
  vo_prefix="$OUT/$vo_label-prestart-bank5-prefix.bin"
  vo_scratch="$OUT/$vo_label-prestart-boot-scratch.bin"
  vo_c2j="$OUT/$vo_label-prestart-c2j.bin"
  readback 0x00050000 33840 "$vo_prefix"
  run_cmd cmp -n 33840 "$vo_reset_image" "$vo_prefix"
  readback 0x00058500 3285 "$vo_scratch"
  run_cmd cmp "$(jq -r '.bank5_reset_domain.authenticated_bootstrap_scratch.artifact.path' "$FIXTURE")" "$vo_scratch"
  readback 0x0005c640 64 "$vo_c2j"
  if [ "$vo_label" = negative ]; then
    run_cmd cmp "$OUT/active-predecessor-c2j.bin" "$vo_c2j"
  else
    run_cmd cmp "$OUT/zero-c2j.bin" "$vo_c2j"
  fi
}

echo "==> Link-57 C4 destructive restage: $ACTION"
echo "    same product SHA $PRODUCT_SHA; no product link, promotion or acceptance-chain claim"

case "$ACTION" in
  negative)
    [ ! -e "$OUT/negative-observation.json" ] || {
      echo "negative branch already consumed" >&2
      exit 3
    }
    hold_product
    upload_and_verify "$OUT/bank5-destructive-50816.bin" 0x00050000 50816 \
      "$OUT/negative-preoverlay-bank5-full.bin"
    upload_normal_preloads negative
    upload_and_verify "$OUT/stale-session-attic-sentinel.bin" 0x084fff80 64 \
      "$OUT/negative-prestart-stale-attic.bin"
    upload_and_verify "$OUT/poison-bank2-prefix.bin" 0x00020000 256 \
      "$OUT/negative-prestart-bank2-poison.bin"
    upload_and_verify "$OUT/poison-bank3-prefix.bin" 0x00030000 256 \
      "$OUT/negative-prestart-bank3-poison.bin"
    patch_stale_tuple
    verify_bank5_post_overlay negative "$OUT/bank5-destructive-50816.bin"
    run_cmd timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -r -1 "$PRG"
    run_cmd sleep "$WAIT"
    readback 0x00000000 65536 "$OUT/negative-bank0.bin"
    readback 0x00050000 50816 "$OUT/negative-bank5.bin"
    readback 0x084fff80 64 "$OUT/negative-stale-attic.bin"
    if [ "$DRY_RUN" -eq 0 ]; then
      python3 "$PY" observe-negative --out "$OUT" \
        --bank0 "$OUT/negative-bank0.bin" \
        --bank5 "$OUT/negative-bank5.bin" \
        --sentinel "$OUT/negative-stale-attic.bin"
    fi
    cat <<'EOF'
Confirm the screen before continuing. Expected:
  E25
After the operator reports exactly that result, run the confirm-negative action.
EOF
    ;;
  repair)
    [ "$(jq -r '.status // "missing"' "$OUT/negative-observation.json" 2>/dev/null || true)" = \
      passed-fail-closed-negative ] || {
      echo "repair requires the operator-confirmed negative observation" >&2
      exit 3
    }
    [ ! -e "$OUT/repair-observation.json" ] || {
      echo "repair branch already consumed" >&2
      exit 3
    }
    hold_product
    upload_and_verify "$OUT/bank5-repair-50816.bin" 0x00050000 50816 \
      "$OUT/repair-preoverlay-bank5-full.bin"
    upload_normal_preloads repair
    verify_bank5_post_overlay repair "$OUT/bank5-repair-50816.bin"
    run_cmd timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" -r -1 "$PRG"
    run_cmd sleep "$WAIT"
    readback 0x00000000 65536 "$OUT/repair-bank0.bin"
    readback 0x00020000 65536 "$OUT/repair-bank2.bin"
    readback 0x00030000 65536 "$OUT/repair-bank3.bin"
    readback 0x00050000 50816 "$OUT/repair-bank5.bin"
    readback 0x084fff80 64 "$OUT/repair-stale-attic.bin"
    if [ "$DRY_RUN" -eq 0 ]; then
      python3 "$PY" observe-repair --out "$OUT" \
        --bank0 "$OUT/repair-bank0.bin" \
        --bank2 "$OUT/repair-bank2.bin" \
        --bank3 "$OUT/repair-bank3.bin" \
        --bank5 "$OUT/repair-bank5.bin" \
        --sentinel "$OUT/repair-stale-attic.bin"
    fi
    cat <<'EOF'
The repair observation is green. At the live REPL, enter exactly:
  (%c4-stale)             expect: *** vm: undefined function
  (defun %c4fresh () 't) expect: %c4fresh
  (%c4fresh)              expect: T
Report all three observations before the final action is run.
EOF
    ;;
  final)
    [ -e "$OUT/repair-observation.json" ] || {
      echo "final requires the passed repair observation" >&2
      exit 3
    }
    [ ! -e "$HW_RECEIPT" ] || {
      echo "C4 hardware receipt already exists" >&2
      exit 3
    }
    [ -n "$STALE_OUTPUT" ] && [ -n "$DEFINITION_OUTPUT" ] && [ -n "$CALL_OUTPUT" ] || {
      echo "final requires all three exact operator outputs" >&2
      exit 3
    }
    readback 0x00000000 65536 "$OUT/final-bank0.bin"
    readback 0x00050000 50816 "$OUT/final-bank5.bin"
    if [ "$DRY_RUN" -eq 0 ]; then
      python3 "$PY" observe-final --out "$OUT" \
        --bank0 "$OUT/final-bank0.bin" \
        --bank5 "$OUT/final-bank5.bin" \
        --stale-output "$STALE_OUTPUT" \
        --definition-output "$DEFINITION_OUTPUT" \
        --call-output "$CALL_OUTPUT"
    fi
    ;;
esac
