#!/bin/sh
# One-boot, four-cutpoint C1 open-transaction Freezer fixture for Link 58.
set -eu
cd "$(dirname "$0")/.."

OUT=${C2_C1_FREEZER_OUT:-build/c2.2/c1-freezer-hardware-link58-attempt4-NONPROMOTABLE}
DEPLOY=$OUT/deployment.json
PY=${C2_C1_FREEZER_PY:-tools/host-lisp/c2_c1_freezer_hw_fixture.py}
TOOLS=tools/m65tools
DEVICE=/dev/ttyUSB1
TIMEOUT=30
WAIT=25
ACTION=
CUTPOINT=
OUTPUT=
FREEZER_OUTPUT=
BUNDLED_SESSION=${C2_C1_BUNDLED_SESSION:-0}

usage() {
  cat >&2 <<EOF
usage: $0 <deploy|arm|thaw|confirm> [options]
  --cutpoint <1..4>    required for arm/thaw/confirm
  --freezer-output <s> exact operator report for thaw
  --output <s>         exact REPL call output for confirm
  --tools <dir>        m65tools directory (default: $TOOLS)
  --device <path>      JTAG serial device (default: $DEVICE)
  --timeout <sec>      timeout per JTAG operation (default: $TIMEOUT)
  --wait <sec>         boot wait (default: $WAIT)

deploy is one-shot and starts the exact Link-58 product with the Link-58-
relocation-rebound, stage-bound, nonpromotable four-slice Session carrier.
The earlier E3e, omitted-zero-C2J and cross-WPLTO-identity harness First Reds
are excluded but bound.  A visible error-free lisp65> prompt is now a boot
gate.  For each cutpoint, run arm, perform one physical Freezer roundtrip, run
thaw, report the printed call result, then run confirm.
EOF
  exit 2
}

[ "$#" -gt 0 ] || usage
ACTION=$1
shift
case "$ACTION" in
  deploy|arm|thaw|confirm) ;;
  *) usage ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --cutpoint) shift; CUTPOINT=$1 ;;
    --freezer-output) shift; FREEZER_OUTPUT=$1 ;;
    --output) shift; OUTPUT=$1 ;;
    --tools) shift; TOOLS=$1 ;;
    --device) shift; DEVICE=$1 ;;
    --timeout) shift; TIMEOUT=$1 ;;
    --wait) shift; WAIT=$1 ;;
    -h|--help) usage ;;
    *) echo "unexpected option: $1" >&2; usage ;;
  esac
  shift
done

case "$ACTION" in
  arm|thaw|confirm)
    case "$CUTPOINT" in 1|2|3|4) ;; *) usage ;; esac
    ;;
esac
[ "$ACTION" != thaw ] || [ -n "$FREEZER_OUTPUT" ] || usage
[ "$ACTION" != confirm ] || [ -n "$OUTPUT" ] || usage

python3 "$PY" verify --out "$OUT"

M65=$TOOLS/m65
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG serial device: $DEVICE" >&2; exit 3; }

run_m65() {
  timeout "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$(printf '%08x' "$((rb_start + rb_bytes))")
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$rb_end=$rb_path"
}

upload_and_verify() {
  uv_path=$1
  uv_address=$2
  uv_bytes=$3
  uv_readback=$4
  run_m65 -H -@ "$uv_path@0x$(printf '%08x' "$uv_address")"
  readback "$uv_address" "$uv_bytes" "$uv_readback"
  cmp "$uv_path" "$uv_readback"
}

live_write_byte() {
  lw_path=$1
  lw_address=$2
  run_m65 -@ "$lw_path@0x$(printf '%08x' "$lw_address")"
}

capture_domains() {
  cd_prefix=$1
  readback 0x00020000 65536 "$cd_prefix-bank2.bin"
  readback 0x00030000 65536 "$cd_prefix-bank3.bin"
  readback 0x00050000 50816 "$cd_prefix-bank5.bin"
  readback 0x0000e000 8192 "$cd_prefix-e000.bin"
}

case "$ACTION" in
  deploy)
    [ ! -e "$OUT/hardware-state.json" ] || {
      echo "C1 device run was already started" >&2
      exit 3
    }
    PRG=$(jq -r '.product.path' "$DEPLOY")
    run_m65 -F -H -1 "$PRG"
    jq -c '.preloads[]' "$DEPLOY" |
    while IFS= read -r item; do
      path=$(printf '%s' "$item" | jq -r '.path')
      address=$(printf '%s' "$item" | jq -r '.address')
      bytes=$(printf '%s' "$item" | jq -r '.bytes')
      upload_and_verify "$path" "$address" "$bytes" \
        "$OUT/deploy-readback-$(basename "$path")"
    done
    run_m65 -r -1 "$PRG"
    # The m65 autorun injector can leave its generated BASIC `run:` command
    # on screen without submitting RETURN.  Probe that exact state and finish
    # only that pending command; never type into an already-running product.
    sleep 3
    run_m65 --screenshot="$OUT/autorun-probe.png" \
      > "$OUT/autorun-probe.ansi.txt"
    python3 - "$OUT/autorun-probe.ansi.txt" "$OUT/autorun-probe.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw),
    encoding="utf-8")
PY
    if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/autorun-probe.txt" &&
       ! grep -q 'lisp65>' "$OUT/autorun-probe.txt"; then
      run_m65 -t "~M"
      echo "Completed pending m65 autorun RETURN."
    fi
    sleep "$WAIT"
    readback 0x00000000 65536 "$OUT/boot-bank0.bin"
    readback 0x00020000 65536 "$OUT/boot-bank2.bin"
    readback 0x00030000 65536 "$OUT/boot-bank3.bin"
    readback 0x00050000 50816 "$OUT/boot-bank5.bin"
    run_m65 --screenshot="$OUT/boot-screen.png" \
      > "$OUT/boot-screen.ansi.txt"
    python3 - "$OUT/boot-screen.ansi.txt" "$OUT/boot-screen.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw),
    encoding="utf-8")
PY
    python3 "$PY" observe-boot --out "$OUT"
    echo "C1 fixture booted: confirm banner and usable REPL."
    ;;

  arm)
    ROOT_CP=$OUT/cutpoint-$CUTPOINT
    [ ! -e "$ROOT_CP" ] || {
      echo "cutpoint $CUTPOINT was already armed" >&2
      exit 3
    }
    mkdir "$ROOT_CP"
    capture_domains "$ROOT_CP/baseline"
    ZERO=$OUT/command-0.bin
    live_write_byte "$ZERO" 0x17e0
    live_write_byte "$ZERO" 0x17e1
    readback 0x000017e0 2 "$ROOT_CP/control-cleared.bin"
    [ "$(od -An -tu1 "$ROOT_CP/control-cleared.bin" | tr -d ' ')" = "00" ] || {
      echo "C1 command/reached cells did not clear" >&2
      exit 3
    }
    COMMAND=$OUT/command-$CUTPOINT.bin
    live_write_byte "$COMMAND" 0x17e0
    FORM=$(jq -r ".cutpoints[] | select(.id == $CUTPOINT) | .form" "$DEPLOY")
    # m65 virtual-key injection drops the Lisp apostrophe on this keyboard
    # path.  Use the semantically identical long form so the transport cannot
    # turn a quoted constant into an unbound variable reference.
    FORM=$(printf '%s\n' "$FORM" | sed "s/'t/(quote t)/g")
    # Spell RETURN into the virtual-key stream.  The 20260722 m65 build may
    # display the whole -T payload while silently leaving its implicit RETURN
    # pending; an explicit ~M makes submission observable and deterministic.
    run_m65 -t "${FORM}~M"
    attempt=0
    while [ "$attempt" -lt 20 ]; do
      readback 0x000017e0 2 "$ROOT_CP/hold-before-control.bin"
      first=$(od -An -tu1 -N1 "$ROOT_CP/hold-before-control.bin" | tr -d ' ')
      second=$(od -An -tu1 -j1 -N1 "$ROOT_CP/hold-before-control.bin" | tr -d ' ')
      expected_second=$CUTPOINT
      [ "$CUTPOINT" -ne 4 ] || expected_second=0
      if [ "$first" = "$CUTPOINT" ] && [ "$second" = "$expected_second" ]; then
        break
      fi
      sleep 1
      attempt=$((attempt + 1))
    done
    [ "$attempt" -lt 20 ] || {
      if [ "$BUNDLED_SESSION" -eq 1 ]; then
        readback 0x000017e0 14 "$ROOT_CP/bundled-witness-1.bin"
        sleep 1
        readback 0x000017e0 14 "$ROOT_CP/bundled-witness-2.bin"
        sleep 1
        readback 0x000017e0 14 "$ROOT_CP/bundled-witness-3.bin"
        run_m65 --screenshot="$ROOT_CP/bundled-first-red.png" \
          > "$ROOT_CP/bundled-first-red.ansi.txt"
        od -An -tx1 "$ROOT_CP/bundled-witness-3.bin" |
          tr -s ' ' |
          sed 's/^/bundled witness $17e0..$17ed:/'
      fi
      echo "cutpoint $CUTPOINT was not reached" >&2
      exit 3
    }
    capture_domains "$ROOT_CP/hold-before"
    python3 "$PY" observe-hold --out "$OUT" --cutpoint "$CUTPOINT"
    echo "Cutpoint $CUTPOINT is held. Press physical Freezer once, then F3 once to return."
    ;;

  thaw)
    ROOT_CP=$OUT/cutpoint-$CUTPOINT
    [ -d "$ROOT_CP" ] || {
      echo "cutpoint $CUTPOINT is not armed" >&2
      exit 3
    }
    capture_domains "$ROOT_CP/hold-after"
    readback 0x000017e0 2 "$ROOT_CP/hold-after-control.bin"
    live_write_byte "$OUT/command-0.bin" 0x17e0
    sleep 5
    capture_domains "$ROOT_CP/post"
    python3 "$PY" observe-thaw --out "$OUT" --cutpoint "$CUTPOINT" \
      --freezer-output "$FREEZER_OUTPUT"
    CALL=$(jq -r ".cutpoints[] | select(.id == $CUTPOINT) | .call" "$DEPLOY")
    run_m65 -t "${CALL}~M"
    if [ "$CUTPOINT" -lt 4 ]; then
      echo "Report the exact output of $CALL (expected: t)."
    else
      echo "Report the exact output of $CALL (expected: *** vm: undefined function: %c1a)."
    fi
    ;;

  confirm)
    python3 "$PY" confirm-output --out "$OUT" --cutpoint "$CUTPOINT" \
      --output "$OUTPUT"
    ;;
esac
