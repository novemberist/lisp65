#!/bin/sh
# One quiet physical closing session for v1.3 Link 84.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=${PY:-scripts/c2-v13-closing-device.py}
DEPLOY=${DEPLOY:-build/ship-builder/v13/closing-device-session/deployment.json}
OUT=${OUT:-build/ship-builder/v13/closing-device-session/run}
D1_ORDER=${D1_ORDER:-before-D3}
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start|resume-workbench|continue-after-autoboot|evaluate) ;;
  *) echo "usage: $0 <prepare|dry-run|start|resume-workbench|continue-after-autoboot|evaluate>" >&2; exit 2 ;;
esac

if [ "$ACTION" = prepare ]; then exec python3 "$PY" prepare; fi
if [ "$ACTION" = evaluate ]; then exec python3 "$PY" evaluate; fi
if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  jq -r '.D3.editor_form, .D3.query_form, .D4[].form' "$DEPLOY" |
  while IFS= read -r form; do
    [ -n "$form" ] || continue
    OUT_DIR="$OUT/dry-run" PREFIX=quiet TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --no-readback \
        --form "$form"
  done
  echo "DRY-RUN: configured Ship identities plus independent candidate D3/D4 identities"
  echo "DRY-RUN: Ship input waits for runtime state; persistent and typing windows remain monitor-quiet"
  exit 0
fi

python3 "$PY" prepare
mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

run_m65() { timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"; }

capture_screen() (
  prefix=$1
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
  start=$1 bytes=$2 path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
)

wait_runtime_state() (
  address=$1 expected=$2 prefix=$3 limit=${4:-90}
  elapsed=0
  while [ "$elapsed" -lt "$limit" ]; do
    readback "$address" 1 "$OUT/$prefix-runtime-state.bin"
    actual=$(od -An -tu1 "$OUT/$prefix-runtime-state.bin" | tr -d ' ')
    [ "$actual" = "$expected" ] && return 0
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "$prefix runtime state did not reach $expected within ${limit}s" >&2
  return 1
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
  readback_path=$OUT/$prefix-package-readback.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
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
      echo "FTP progress guard fired after ${FTP_STALL_LIMIT}s" >&2
      return 124
    fi
  done
  wait "$pid"
  cmp "$media" "$readback_path"
)

quiet_form() (
  id=$1 form=$2 wait_seconds=$3
  allow_tail=${4:-no}
  if [ "$allow_tail" = yes ]; then
    OUT_DIR="$OUT" PREFIX="$id-input" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
        --no-readback --form "$form"
  else
    OUT_DIR="$OUT" PREFIX="$id-input" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  fi
  sleep "$wait_seconds"
  capture_screen "$id"
  fail_if_red "$OUT/$id.png"
)

deploy_workbench() (
  media_key=$1 remote_key=$2 prefix=$3
  media=$(jq -r ".D3.$media_key.path" "$DEPLOY")
  remote=$(jq -r ".D3.$remote_key" "$DEPLOY")
  fresh_start "$prefix"
  ftp_package "$media" "$remote" "$prefix"
  product=$(jq -r '.D3.product.path' "$DEPLOY")
  run_m65 -H -1 "$product"
  jq -c '.D3.preloads[]' "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    role=$(printf '%s' "$item" | jq -r '.role')
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/$prefix-preload-$role.bin"
    cmp "$path" "$OUT/$prefix-preload-$role.bin"
  done
  run_m65 -r -1 "$product"
  sleep 12
  capture_screen "$prefix-boot"
  fail_if_red "$OUT/$prefix-boot.png"
  if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/$prefix-boot.txt" &&
     ! grep -q 'lisp65>' "$OUT/$prefix-boot.txt"; then
    run_m65 -t '~M'
    sleep 10
    capture_screen "$prefix-boot"
    fail_if_red "$OUT/$prefix-boot.png"
  fi
  grep -q 'lisp65>' "$OUT/$prefix-boot.txt"
)

deploy_autoboot_workbench() (
  media_key=$1 remote_key=$2 prefix=$3
  media=$(jq -r ".D3.$media_key.path" "$DEPLOY")
  remote=$(jq -r ".D3.$remote_key" "$DEPLOY")
  fresh_start "$prefix"
  ftp_package "$media" "$remote" "$prefix"
  # This medium owns AUTOBOOT.C65.  Let it stage and start the bound product;
  # manually loading the same PRG here races the already-running AUTOBOOT path.
  sleep 45
  capture_screen "$prefix-boot"
  fail_if_red "$OUT/$prefix-boot.png"
  if grep -Eq '^[[:space:]]*run:[[:space:]]*$' "$OUT/$prefix-boot.txt" &&
     ! grep -q 'lisp65>' "$OUT/$prefix-boot.txt"; then
    run_m65 -t '~M'
    sleep 10
    capture_screen "$prefix-boot"
    fail_if_red "$OUT/$prefix-boot.png"
  fi
  grep -q 'lisp65>' "$OUT/$prefix-boot.txt"
)

run_d1() {
  jq -c '.D1[]' "$DEPLOY" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    image=$(printf '%s' "$row" | jq -r '.image.path')
    remote=$(printf '%s' "$row" | jq -r '.remote')
    quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
    state=$(printf '%s' "$row" | jq -r '.addresses.lisp65_runtime_state')
    input=$(printf '%s' "$row" | jq -r '.transport_text // empty')
    fresh_start "$id"
    ftp_package "$image" "$remote" "$id"
    if [ -n "$input" ]; then
      # State 2 is the runtime's explicit entry-running witness.  Wait for it
      # before typing: fixed wall time can inject into the pre-runtime boot
      # path, where KERNAL initialization legitimately consumes the keys.
      wait_runtime_state "$((state))" 2 "$id" 90
      run_m65 -t "$input"
    fi
    sleep "$quiet"
    readback "$((state))" 4 "$OUT/$id-result.bin"
    capture_screen "$id"
    fail_if_red "$OUT/$id.png"
  done
}

# D1: standalone images, each under its own cold identity.  Link 85 runs the
# deferred interactive sample after D3 so the reset-domain regression row is
# answered first; the historical Link-84 order remains the default.
if [ "$ACTION" = resume-workbench ] || [ "$ACTION" = continue-after-autoboot ]; then
  for id in $(jq -r '.D1[].id' "$DEPLOY"); do
    [ -s "$OUT/$id-result.bin" ]
    [ -s "$OUT/$id.png" ]
    [ -s "$OUT/$id-package-readback.d81" ]
  done
elif [ "$D1_ORDER" = before-D3 ]; then
  run_d1
fi

# D3: bound candidate editor freight, configured keys without polling.
if [ "$ACTION" = continue-after-autoboot ]; then
  capture_screen D3-autoboot-resume
  fail_if_red "$OUT/D3-autoboot-resume.png"
  grep -q 'WORKBENCH 1.3.0' "$OUT/D3-autoboot-resume.txt"
  grep -q 'lisp65>' "$OUT/D3-autoboot-resume.txt"
else
  deploy_autoboot_workbench package_medium remote_media D3-retry
fi
editor_form=$(jq -r '.D3.editor_form' "$DEPLOY")
OUT_DIR="$OUT" PREFIX=editor-launch-input TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form "$editor_form"
sleep 12
keys=$(jq -r '.D3.keys' "$DEPLOY")
character=$(jq -r '.D3.character' "$DEPLOY")
inter_key=$(jq -r '.D3.transport_inter_key_seconds' "$DEPLOY")
# One virtual-keyboard invocation per key preserves the quiet product window
# while avoiding the helper's unacknowledged multi-character queue loss.
# There are deliberately no monitor reads or screen polls between the keys.
sent=0
while [ "$sent" -lt "$keys" ]; do
  run_m65 -t "$character"
  sleep "$inter_key"
  sent=$((sent + 1))
done
sleep "$(jq -r '.D3.quiet_seconds' "$DEPLOY")"
capture_screen editor-quiet-end
fail_if_red "$OUT/editor-quiet-end.png"
run_m65 -t '~C'
sleep 10
capture_screen editor-stopped
fail_if_red "$OUT/editor-stopped.png"
grep -q '\*\*\* stopped (run/stop)' "$OUT/editor-stopped.txt"
grep -q 'lisp65>' "$OUT/editor-stopped.txt"
query=$(jq -r '.D3.query_form' "$DEPLOY")
quiet_form editor-query "$query" 10 yes
quiet_form editor-post-stop '(+ 4 5)' 5 yes

if [ "$ACTION" != resume-workbench ] &&
   [ "$ACTION" != continue-after-autoboot ] &&
   [ "$D1_ORDER" = after-D3 ]; then
  run_d1
fi

# D4: same candidate product with the identity-rebound package library medium.
deploy_workbench library_medium remote_library_media D4
jq -c '.D4[]' "$DEPLOY" |
while IFS= read -r row; do
  id=$(printf '%s' "$row" | jq -r '.id')
  form=$(printf '%s' "$row" | jq -r '.form')
  quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
  quiet_form "$id" "$form" "$quiet"
done

python3 "$PY" evaluate
