#!/bin/sh
# One quiet physical session for Ship-v1, defstruct and the parked editor row.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
PY=scripts/c2-ship-builder-v1-device.py
DEPLOY=build/ship-builder/v1-device-session/deployment.json
OUT=build/ship-builder/v1-device-session/run
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start|evaluate|prepare-completion|dry-run-completion|complete|evaluate-completion) ;;
  *) echo "usage: $0 <prepare|dry-run|start|evaluate|prepare-completion|dry-run-completion|complete|evaluate-completion>" >&2; exit 2 ;;
esac

case "$ACTION" in
  prepare-completion|dry-run-completion|complete|evaluate-completion)
    OUT=build/ship-builder/v1-device-session/run-completion
    ;;
esac

if [ "$ACTION" = prepare ]; then
  exec python3 "$PY" prepare
fi
if [ "$ACTION" = prepare-completion ]; then
  exec python3 "$PY" prepare-completion
fi
if [ "$ACTION" = dry-run ]; then
  python3 "$PY" dry-run
  jq -r '.D2.rows[].form, .D3.editor_form, .D3.query_form, .D4[].form' "$DEPLOY" |
  while IFS= read -r form; do
    [ -n "$form" ] || continue
    OUT_DIR="$OUT/dry-run" PREFIX=quiet TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --no-readback \
        --form "$form"
  done
  echo "DRY-RUN: every identity starts with cold reset + one fresh-BASIC assert"
  echo "DRY-RUN: no monitor traffic during Ship boot, persistent forms or editor typing"
  exit 0
fi
if [ "$ACTION" = dry-run-completion ]; then
  python3 "$PY" dry-run-completion
  jq -r '.D3.editor_form, .D3.query_form, .D4[].form' "$DEPLOY" |
  while IFS= read -r form; do
    [ -n "$form" ] || continue
    OUT_DIR="$OUT/dry-run" PREFIX=quiet TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --no-readback \
        --form "$form"
  done
  echo "DRY-RUN: completion is D1+D3+D4 only; D2 is never entered"
  echo "DRY-RUN: D1 relies on the FTP helper's mount-and-reset exit; no second reset"
  exit 0
fi
if [ "$ACTION" = evaluate ]; then
  exec python3 "$PY" evaluate
fi
if [ "$ACTION" = evaluate-completion ]; then
  exec python3 "$PY" evaluate-completion
fi

if [ "$ACTION" = complete ]; then
  python3 "$PY" prepare-completion
else
  python3 "$PY" prepare
fi
mkdir -p "$OUT"
[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

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
    -c "put $media $remote" \
    -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  last=-1
  progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last" ]; then
      last=$size
      progress=$now
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
  OUT_DIR="$OUT" PREFIX="$id-input" TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback --form "$form"
  # Binding rule: no monitor access in this complete quiet window.
  sleep "$wait_seconds"
  capture_screen "$id"
  fail_if_red "$OUT/$id.png"
)

deploy_workbench() (
  section=$1 prefix=$2 media_key=$3 remote_key=$4
  media=$(jq -r ".$section.$media_key.path" "$DEPLOY")
  remote=$(jq -r ".$section.$remote_key" "$DEPLOY")
  fresh_start "$prefix"
  ftp_package "$media" "$remote" "$prefix"
  product=$(jq -r ".$section.product.path" "$DEPLOY")
  run_m65 -H -1 "$product"
  jq -c ".$section.preloads[]" "$DEPLOY" |
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
    capture_screen "$prefix-boot-return"
    fail_if_red "$OUT/$prefix-boot-return.png"
    grep -q 'lisp65>' "$OUT/$prefix-boot-return.txt"
  else
    grep -q 'lisp65>' "$OUT/$prefix-boot.txt"
  fi
)

# D1: three standalone images, each through its own power-on identity.
jq -c '.D1[]' "$DEPLOY" |
while IFS= read -r row; do
  id=$(printf '%s' "$row" | jq -r '.id')
  image=$(printf '%s' "$row" | jq -r '.image.path')
  remote=$(printf '%s' "$row" | jq -r '.remote')
  quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
  state=$(printf '%s' "$row" | jq -r '.addresses.lisp65_runtime_state')
  fresh_start "$id"
  ftp_package "$image" "$remote" "$id"
  # No monitor traffic while the stager, preload and entry execute.
  sleep "$quiet"
  readback "$((state))" 4 "$OUT/$id-result.bin"
  capture_screen "$id"
  fail_if_red "$OUT/$id.png"
done

# D2 is historical and is never entered by the owner-authorized completion.
if [ "$ACTION" = start ]; then
  deploy_workbench D2 D2 defstruct_media remote_media
  jq -c '.D2.rows[]' "$DEPLOY" |
  while IFS= read -r row; do
    id=$(printf '%s' "$row" | jq -r '.id')
    form=$(printf '%s' "$row" | jq -r '.form')
    quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
    quiet_form "$id" "$form" "$quiet"
  done
else
  deploy_workbench D2 D4 defstruct_media remote_media
fi
# D4: released v1.2.5 product, freshly rebound library medium.
jq -c '.D4[]' "$DEPLOY" |
while IFS= read -r row; do
  id=$(printf '%s' "$row" | jq -r '.id')
  form=$(printf '%s' "$row" | jq -r '.form')
  quiet=$(printf '%s' "$row" | jq -r '.quiet_seconds')
  quiet_form "$id" "$form" "$quiet"
done
if [ "$ACTION" = start ]; then
  jq -r '.D2.readbacks | to_entries[] | [.key,.value[0],.value[1]] | @tsv' "$DEPLOY" |
  while IFS="$(printf '\t')" read -r name address bytes; do
    readback "$((address))" "$bytes" "$OUT/D2-$name.bin"
  done
fi

# D3: parked Link 83, 64 normal keys with zero monitor traffic while typing.
deploy_workbench D3 D3 package_medium remote_media
editor_form=$(jq -r '.D3.editor_form' "$DEPLOY")
OUT_DIR="$OUT" PREFIX=editor-launch-input TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form "$editor_form"
sleep 12
keys=$(jq -r '.D3.keys' "$DEPLOY")
character=$(jq -r '.D3.character' "$DEPLOY")
payload=$(python3 - "$character" "$keys" <<'PY'
import sys
print(sys.argv[1] * int(sys.argv[2]), end="")
PY
)
run_m65 -t "$payload"
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
quiet_form editor-query "$query" 10
quiet_form editor-post-stop '(+ 4 5)' 5

if [ "$ACTION" = complete ]; then
  python3 "$PY" evaluate-completion
else
  python3 "$PY" evaluate
fi
