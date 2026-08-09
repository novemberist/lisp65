#!/bin/sh
# Link-89 bundled v1.4 parity-pilot device session.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=tools/host-lisp/c2_v14_link89_device_session.py
CONFIG=config/c2-v14-link89-device-session.json
BASE=build/post-promotion/v14/link89-device-session
DEPLOY=$BASE/deployment.json
OUT=$BASE/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start-d1|start-d2|probe-d2-pointer|probe-d2-ship-state|probe-d2-ship-inputs|probe-d2-ship-predicates|probe-d2-vic-unlock|capture-d2|start-d3|capture-d3) ;;
  *) echo "usage: $0 <prepare|dry-run|start-d1|start-d2|probe-d2-pointer|probe-d2-ship-state|probe-d2-ship-inputs|probe-d2-ship-predicates|probe-d2-vic-unlock|capture-d2|start-d3|capture-d3>" >&2; exit 2 ;;
esac

if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

capture_screen() (
  prefix=$1
  mkdir -p "$OUT"
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re, sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
)

fail_if_red() (
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError as error:
    print(error.message)
    raise SystemExit(error.code)
PY
)

readback() (
  start=$1 bytes=$2 path=$3 end=$((start + bytes))
  mkdir -p "$(dirname "$path")"
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

fresh_start() (
  prefix=$1
  run_m65 -F
  sleep 5
  capture_screen "$prefix-fresh-basic"
  fail_if_red "$OUT/$prefix-fresh-basic.png"
  grep -Eqi 'BASIC 65|READY\.' "$OUT/$prefix-fresh-basic.txt"
  ! grep -q 'lisp65>' "$OUT/$prefix-fresh-basic.txt"
)

ftp_package() (
  media=$1 remote=$2 prefix=$3
  log=$OUT/$prefix-upload.log
  readback_path=$OUT/$prefix-readback.d81
  rm -f "$readback_path"
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true' HUP INT TERM EXIT
  last=-1
  progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last" ]; then
      last=$size; progress=$now
    elif [ $((now - progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      trap - HUP INT TERM EXIT
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  if wait "$pid"; then status=0; else status=$?; fi
  trap - HUP INT TERM EXIT
  [ "$status" -eq 0 ]
  cmp "$media" "$readback_path"
)

wait_repl() (
  prefix=$1 limit=${2:-120} elapsed=0
  expected=$(jq -r '.workbench.expected_banner' "$DEPLOY")
  while [ "$elapsed" -lt "$limit" ]; do
    capture_screen "$prefix"
    fail_if_red "$OUT/$prefix.png"
    if grep -q 'lisp65>' "$OUT/$prefix.txt" &&
       grep -Fq "$expected" "$OUT/$prefix.txt"; then
      return 0
    fi
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "Link-89 workbench context did not reach the bound REPL" >&2
  return 1
)

context_bank2() (
  phase=$1
  address=$(($(jq -r '.workbench.bank2.address' "$DEPLOY")))
  bytes=$(jq -r '.workbench.bank2.bytes' "$DEPLOY")
  path=$(jq -r '.workbench.bank2.path' "$DEPLOY")
  readback "$address" "$bytes" "$OUT/$phase-bank2.bin"
  cmp "$path" "$OUT/$phase-bank2.bin"
)

deploy_autoboot_workbench() (
  prefix=$1
  media=$(jq -r '.workbench.product_d81.path' "$DEPLOY")
  remote=$(jq -r '.workbench.remote_product' "$DEPLOY")
  fresh_start "$prefix"
  ftp_package "$media" "$remote" "$prefix-product"
  wait_repl "$prefix-boot" 150
  context_bank2 "$prefix"
)

deploy_library_workbench() (
  prefix=$1
  media=$(jq -r '.workbench.library_d81.path' "$DEPLOY")
  remote=$(jq -r '.workbench.remote_library' "$DEPLOY")
  product=$(jq -r '.workbench.resident_prg.path' "$DEPLOY")
  fresh_start "$prefix"
  ftp_package "$media" "$remote" "$prefix-library"
  run_m65 -H -1 "$product"
  jq -c '.workbench.preloads[]' "$DEPLOY" |
  while IFS= read -r row; do
    path=$(printf '%s' "$row" | jq -r '.path')
    address=$(printf '%s' "$row" | jq -r '.address')
    bytes=$(printf '%s' "$row" | jq -r '.bytes')
    role=$(printf '%s' "$row" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/$prefix-preload-$role.bin"
    cmp "$path" "$OUT/$prefix-preload-$role.bin"
  done
  run_m65 -r -1 "$product"
  sleep 12
  wait_repl "$prefix-boot" 90
  context_bank2 "$prefix"
)

run_form() (
  prefix=$1 form=$2 expected=$3 wait=${4:-3}
  OUT_DIR=$OUT PREFIX=$prefix TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --wait "$wait" \
      --expect "$expected" --expect-poll 45 --form "$form"
  fail_if_red "$OUT/$prefix.png"
)

run_error_form() (
  prefix=$1 form=$2
  OUT_DIR=$OUT PREFIX=$prefix TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --wait 4 --form "$form"
  fail_if_red "$OUT/$prefix.png"
  grep -q '\*\*\*' "$OUT/$prefix.txt"
  grep -q 'lisp65>' "$OUT/$prefix.txt"
)

quiet_form() (
  prefix=$1 form=$2 expected=$3 quiet=$4
  OUT_DIR=$OUT PREFIX=$prefix-input TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  sleep "$quiet"
  capture_screen "$prefix"
  fail_if_red "$OUT/$prefix.png"
  python3 tools/host-lisp/repl_screen_check.py \
    --screen "$OUT/$prefix.txt" --form-text "$form" --expect "$expected"
)

wait_runtime_state() (
  address=$1 expected=$2 prefix=$3 limit=${4:-120} elapsed=0
  while [ "$elapsed" -lt "$limit" ]; do
    readback "$address" 1 "$OUT/$prefix-state.bin"
    actual=$(od -An -tu1 "$OUT/$prefix-state.bin" | tr -d ' ')
    [ "$actual" = "$expected" ] && return 0
    case "$actual" in
      3|225|226|227|228|229)
        echo "$prefix terminal state $actual before expected $expected" >&2
        return 1 ;;
    esac
    sleep 2; elapsed=$((elapsed + 2))
  done
  echo "$prefix state did not reach $expected" >&2
  return 1
)

if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  jq -r '.D1.bounds_form,.D1.recovery_form,.D1.draw_forms[],.D2.pointer_probe_form,.D3.require_form,.D3.q_form,.D3.time_form,.D3.read_line_form,.D3.liveness_form' "$DEPLOY" |
  while IFS= read -r form; do
    [ -n "$form" ] || continue
    OUT_DIR=$OUT/dry-run PREFIX=form TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --no-readback --form "$form"
  done
  echo "DRY-RUN: three cold identities, exact media readbacks, CPU-side I/O witnesses"
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2; exit 3;
}
python3 "$PY" dry-run >/dev/null
mkdir -p "$OUT"

case "$ACTION" in
  start-d1)
    [ ! -e "$OUT/D1-bank2.bin" ] || { echo "D1 already consumed" >&2; exit 3; }
    deploy_autoboot_workbench D1
    bounds=$(jq -r '.D1.bounds_form' "$DEPLOY")
    run_error_form d1-bounds "$bounds"
    run_form d1-recovery "$(jq -r '.D1.recovery_form' "$DEPLOY")" 9
    index=0
    jq -r '.D1.draw_forms[]' "$DEPLOY" |
    while IFS= read -r form; do
      index=$((index + 1)); run_form "d1-draw-$index" "$form" t
    done
    echo "D1 DRAW COMPLETE: bounds, recovery and the visible panel are ready."
    ;;

  start-d2)
    [ -f "$OUT/d1-draw-3.txt" ] || { echo "D1 draw row absent" >&2; exit 3; }
    [ ! -e "$OUT/D2-state-before-key.bin" ] || { echo "D2 already consumed" >&2; exit 3; }
    image=$(jq -r '.parity_toy.image.path' "$DEPLOY")
    remote=$(jq -r '.parity_toy.remote' "$DEPLOY")
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    fresh_start D2
    ftp_package "$image" "$remote" D2-toy
    wait_runtime_state "$state" 2 D2 120
    cp "$OUT/D2-state.bin" "$OUT/D2-state-before-key.bin"
    capture_screen D2-waiting
    fail_if_red "$OUT/D2-waiting.png"
    echo "D2 READY: inspect the visible toy, then press one PHYSICAL key and listen for its SID note."
    ;;

  probe-d2-pointer)
    [ -f "$OUT/D2-terminal-e3-runtime.bin" ] || { echo "D2 E3 state absent" >&2; exit 3; }
    [ ! -e "$OUT/D2P-bank2.bin" ] || { echo "D2 pointer probe already consumed" >&2; exit 3; }
    deploy_autoboot_workbench D2P
    form=$(jq -r '.D2.pointer_probe_form' "$DEPLOY")
    OUT_DIR=$OUT PREFIX=d2-pointer TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --wait 3 --form "$form"
    fail_if_red "$OUT/d2-pointer.png"
    grep -Eq '\([0-9]+ [0-9]+ [0-9]+\)' "$OUT/d2-pointer.txt"
    echo "D2 POINTER PROBE COMPLETE"
    ;;

  probe-d2-ship-state)
    [ -f "$OUT/d2-pointer.txt" ] || { echo "D2 pointer probe absent" >&2; exit 3; }
    [ ! -e "$OUT/D2S-runtime.bin" ] || { echo "D2 Ship state probe already consumed" >&2; exit 3; }
    image=$(jq -r '.parity_toy.image.path' "$DEPLOY")
    remote=$(jq -r '.parity_toy.remote' "$DEPLOY")
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    fresh_start D2S
    ftp_package "$image" "$remote" D2S-toy
    wait_runtime_state "$state" 227 D2S 120
    readback "$state" 16 "$OUT/D2S-runtime.bin"
    readback 0x17c0 64 "$OUT/D2S-shape-slot.bin"
    readback 0x0ff8 8 "$OUT/D2S-pointer-table.bin"
    capture_screen D2S-terminal
    fail_if_red "$OUT/D2S-terminal.png"
    echo "D2 SHIP STATE PROBE COMPLETE"
    ;;

  probe-d2-ship-inputs)
    [ -f "$OUT/D2S-runtime.bin" ] || { echo "D2 Ship state probe absent" >&2; exit 3; }
    [ ! -e "$OUT/D2I-runtime.bin" ] || { echo "D2 Ship input probe already consumed" >&2; exit 3; }
    image=build/post-promotion/v14/shape-diag/v14-shape-diag.d81
    expected=86848d1df63a35f27c38bed45953f444517e1c4f1a9c28b81515ab585570b968
    actual=$(sha256sum "$image" | awk '{print $1}')
    [ "$actual" = "$expected" ] || { echo "D2 Ship input image drift" >&2; exit 3; }
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    fresh_start D2I
    ftp_package "$image" V14DIAG.D81 D2I-diag
    elapsed=0
    while [ "$elapsed" -lt 120 ]; do
      readback "$state" 1 "$OUT/D2I-state.bin"
      terminal=$(od -An -tu1 "$OUT/D2I-state.bin" | tr -d ' ')
      case "$terminal" in 3|227) break ;; 225|226|228|229) exit 4 ;; esac
      sleep 2; elapsed=$((elapsed + 2))
    done
    case "${terminal:-}" in 3|227) ;; *) echo "D2 Ship input probe did not terminate" >&2; exit 1 ;; esac
    readback "$state" 16 "$OUT/D2I-runtime.bin"
    readback 0x17a0 8 "$OUT/D2I-input-witness.bin"
    readback 0x17c0 64 "$OUT/D2I-shape-slot.bin"
    readback 0x0ff8 8 "$OUT/D2I-pointer-table.bin"
    capture_screen D2I-terminal
    fail_if_red "$OUT/D2I-terminal.png"
    echo "D2 SHIP INPUT PROBE COMPLETE state=$terminal"
    ;;

  probe-d2-ship-predicates)
    [ -f "$OUT/D2I-runtime.bin" ] || { echo "D2 Ship input probe absent" >&2; exit 3; }
    [ ! -e "$OUT/D2Q-runtime.bin" ] || { echo "D2 Ship predicate probe already consumed" >&2; exit 3; }
    image=build/post-promotion/v14/shape-diag2/v14-shape-diag2.d81
    expected=42c0f81353467817e89b21f613b850ffc35dd2078ee88bdddabdefa9d1b79d67
    actual=$(sha256sum "$image" | awk '{print $1}')
    [ "$actual" = "$expected" ] || { echo "D2 Ship predicate image drift" >&2; exit 3; }
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    fresh_start D2Q
    ftp_package "$image" V14DIAG2.D81 D2Q-diag
    elapsed=0
    while [ "$elapsed" -lt 120 ]; do
      readback "$state" 1 "$OUT/D2Q-state.bin"
      terminal=$(od -An -tu1 "$OUT/D2Q-state.bin" | tr -d ' ')
      case "$terminal" in 3|227) break ;; 225|226|228|229) exit 4 ;; esac
      sleep 2; elapsed=$((elapsed + 2))
    done
    case "${terminal:-}" in 3|227) ;; *) echo "D2 Ship predicate probe did not terminate" >&2; exit 1 ;; esac
    readback "$state" 16 "$OUT/D2Q-runtime.bin"
    readback 0x17a0 10 "$OUT/D2Q-predicate-witness.bin"
    readback 0x17c0 64 "$OUT/D2Q-shape-slot.bin"
    readback 0x0ff8 8 "$OUT/D2Q-pointer-table.bin"
    capture_screen D2Q-terminal
    fail_if_red "$OUT/D2Q-terminal.png"
    echo "D2 SHIP PREDICATE PROBE COMPLETE state=$terminal"
    ;;

  probe-d2-vic-unlock)
    [ -f "$OUT/D2Q-runtime.bin" ] || { echo "D2 Ship predicate probe absent" >&2; exit 3; }
    [ ! -e "$OUT/D2U-runtime.bin" ] || { echo "D2 VIC unlock probe already consumed" >&2; exit 3; }
    image=build/post-promotion/v14/vic-unlock-diag/v14-vic-unlock-diag.d81
    expected=3eba9f223826add79ec1954f7bdb821d564c9541a2549bca5d0dde23634c821f
    actual=$(sha256sum "$image" | awk '{print $1}')
    [ "$actual" = "$expected" ] || { echo "D2 VIC unlock image drift" >&2; exit 3; }
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    fresh_start D2U
    ftp_package "$image" V14UNLOCK.D81 D2U-diag
    elapsed=0
    while [ "$elapsed" -lt 120 ]; do
      readback "$state" 1 "$OUT/D2U-state.bin"
      terminal=$(od -An -tu1 "$OUT/D2U-state.bin" | tr -d ' ')
      case "$terminal" in 3|227) break ;; 225|226|228|229) exit 4 ;; esac
      sleep 2; elapsed=$((elapsed + 2))
    done
    case "${terminal:-}" in 3|227) ;; *) echo "D2 VIC unlock probe did not terminate" >&2; exit 1 ;; esac
    readback "$state" 16 "$OUT/D2U-runtime.bin"
    readback 0x17a0 8 "$OUT/D2U-unlock-witness.bin"
    capture_screen D2U-terminal
    fail_if_red "$OUT/D2U-terminal.png"
    echo "D2 VIC UNLOCK PROBE COMPLETE state=$terminal"
    ;;

  capture-d2)
    [ -f "$OUT/D2-state-before-key.bin" ] || { echo "D2 wait state absent" >&2; exit 3; }
    state=$(($(jq -r '.parity_toy.runtime_state' "$DEPLOY")))
    readback "$state" 4 "$OUT/D2-result.bin"
    capture_screen D2-complete
    fail_if_red "$OUT/D2-complete.png"
    raw=$(od -An -tx1 "$OUT/D2-result.bin" | tr -d ' \n')
    case "$raw" in 03????00) ;; *) echo "D2 PRODUCT FIRST RED state/result=$raw" >&2; exit 4;; esac
    [ "$raw" != 03000000 ] || { echo "D2 PRODUCT FIRST RED NIL result" >&2; exit 4; }
    echo "D2 COMPLETE state/result=$raw"
    ;;

  start-d3)
    [ -f "$OUT/D2-result.bin" ] || { echo "D2 result absent" >&2; exit 3; }
    [ ! -e "$OUT/D3-bank2.bin" ] || { echo "D3 already consumed" >&2; exit 3; }
    deploy_library_workbench D3
    header=$(($(jq -r '.D3.c2d_header.address' "$DEPLOY")))
    header_bytes=$(jq -r '.D3.c2d_header.bytes' "$DEPLOY")
    row=$(($(jq -r '.D3.place_row.address' "$DEPLOY")))
    row_bytes=$(jq -r '.D3.place_row.bytes' "$DEPLOY")
    readback "$header" "$header_bytes" "$OUT/D3-c2d-header-before.bin"
    readback "$row" "$row_bytes" "$OUT/D3-place-row-before.bin"
    form=$(jq -r '.D3.require_form' "$DEPLOY")
    quiet_form d3-require-1 "$form" t 60
    readback "$header" "$header_bytes" "$OUT/D3-c2d-header-after-1.bin"
    readback "$row" "$row_bytes" "$OUT/D3-place-row-after-1.bin"
    quiet_form d3-require-2 "$form" t 8
    readback "$header" "$header_bytes" "$OUT/D3-c2d-header-after-2.bin"
    readback "$row" "$row_bytes" "$OUT/D3-place-row-after-2.bin"
    run_form d3-q "$(jq -r '.D3.q_form' "$DEPLOY")" \
      "$(jq -r '.D3.q_expected' "$DEPLOY")"
    run_form d3-time "$(jq -r '.D3.time_form' "$DEPLOY")" \
      "$(jq -r '.D3.time_expected' "$DEPLOY")"
    form=$(jq -r '.D3.read_line_form' "$DEPLOY")
    OUT_DIR=$OUT PREFIX=d3-read-line-input TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
    echo "D3 READY: type Ada followed by RETURN on the PHYSICAL keyboard."
    ;;

  capture-d3)
    [ -f "$OUT/d3-read-line-input-input-attempt-1.txt" ] || {
      echo "D3 read-line submission absent" >&2; exit 3;
    }
    sleep 3
    capture_screen d3-read-line
    fail_if_red "$OUT/d3-read-line.png"
    python3 tools/host-lisp/repl_screen_check.py \
      --screen "$OUT/d3-read-line.txt" \
      --form-text "$(jq -r '.D3.read_line_form' "$DEPLOY")" \
      --expect "$(jq -r '.D3.read_line_expected' "$DEPLOY")"
    run_form d3-liveness "$(jq -r '.D3.liveness_form' "$DEPLOY")" 9
    echo "D3 COMPLETE: all machine rows are ready for owner-observation closure."
    ;;
esac
