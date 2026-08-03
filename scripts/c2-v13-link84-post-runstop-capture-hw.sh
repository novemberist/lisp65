#!/bin/sh
# Reproduce the bound Link-84 D3 post-RUN/STOP #0ab state, then perform the
# single owner-authorized read-only capture.  There is deliberately no reset,
# upload or keyboard write after the first confirmed #0ab screen.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
DEPLOY=build/ship-builder/v13/closing-device-session/deployment.json
ATTR=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-link84-post-runstop-dirmiss-host-elf-attribution-receipt.json
OUT=build/ship-builder/v13/post-runstop-readback-repro
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  dry-run|run) ;;
  *) echo "usage: $0 <dry-run|run>" >&2; exit 2 ;;
esac

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

readback() (
  start=$1 bytes=$2 name=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$OUT/$name.bin"
)

verify_binding() (
  path=$1 expected_bytes=$2 expected_sha=$3
  [ -f "$path" ]
  [ "$(stat -c '%s' "$path")" = "$expected_bytes" ]
  [ "$(sha256sum "$path" | cut -d' ' -f1)" = "$expected_sha" ]
)

verify_deployment() {
  jq -e '.status == "bounded-host-elf-exhausted-class-C-readback-required"' \
    "$ATTR" >/dev/null
  [ "$(jq -r '.D3.link' "$DEPLOY")" = 84 ]
  [ "$(jq -r '.D3.release' "$DEPLOY")" = v1.3.0 ]
  [ "$(jq -r '.D3.editor_form' "$DEPLOY")" = '(edit)' ]
  [ "$(jq -r '.D3.keys' "$DEPLOY")" = 64 ]
  [ "$(jq -r '.D3.transport_mode' "$DEPLOY")" = one-key-per-invocation ]
  jq -e '.D3.preloads | length == 8' "$DEPLOY" >/dev/null
  jq -r '.authorities.deployed_link84 | .deployment, .elf, .product | [.path,.bytes,.sha256] | @tsv' "$ATTR" |
  while IFS="$(printf '\t')" read -r path bytes sha; do
    verify_binding "$path" "$bytes" "$sha"
  done
  jq -r '.D3.package_medium | [.path,.bytes,.sha256] | @tsv' "$DEPLOY" |
  while IFS="$(printf '\t')" read -r path bytes sha; do
    verify_binding "$path" "$bytes" "$sha"
  done
  jq -r '.D3.preloads[] | [.path,.bytes,.sha256] | @tsv' "$DEPLOY" |
  while IFS="$(printf '\t')" read -r path bytes sha; do
    verify_binding "$path" "$bytes" "$sha"
  done
}

ftp_package() (
  media=$(jq -r '.D3.package_medium.path' "$DEPLOY")
  remote=$(jq -r '.D3.remote_media' "$DEPLOY")
  log=$OUT/repro-upload.log
  readback_path=$OUT/repro-package-readback.d81
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

verify_deployment
mkdir -p "$OUT"

if [ "$ACTION" = dry-run ]; then
  editor_form=$(jq -r '.D3.editor_form' "$DEPLOY")
  query=$(jq -r '.D3.query_form' "$DEPLOY")
  for form in "$editor_form" "$query" '(+ 4 5)'; do
    OUT_DIR="$OUT/dry-run" PREFIX=repro TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input \
        --allow-editor-status-tail --no-readback --form "$form"
  done
  jq -e '.next_discriminator.capture | length == 11' "$ATTR" >/dev/null
  printf '%s\n' \
    'DRY-RUN: authoritative Link-84 WPLTO ELF, PRG, D81 and eight preloads are exact' \
    'DRY-RUN: current BASIC is asserted before mounting the exact Link-84 D3 medium' \
    'DRY-RUN: no reset is issued by this runner' \
    'DRY-RUN: after confirmed #0ab, only eleven --memsave reads are issued'
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

# The user already restarted the device.  Assert that exact fresh state; do
# not spend another reset or inherit an assumed boot context.
capture_screen repro-fresh-basic
grep -Eqi 'BASIC 65|READY\.' "$OUT/repro-fresh-basic.txt"
! grep -q 'lisp65>' "$OUT/repro-fresh-basic.txt"

ftp_package
sleep 45
capture_screen repro-boot
grep -q 'WORKBENCH 1.3.0' "$OUT/repro-boot.txt"
grep -q 'lisp65>' "$OUT/repro-boot.txt"

editor_form=$(jq -r '.D3.editor_form' "$DEPLOY")
OUT_DIR="$OUT" PREFIX=repro-editor-launch TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form "$editor_form"
sleep 12

keys=$(jq -r '.D3.keys' "$DEPLOY")
character=$(jq -r '.D3.character' "$DEPLOY")
inter_key=$(jq -r '.D3.transport_inter_key_seconds' "$DEPLOY")
sent=0
while [ "$sent" -lt "$keys" ]; do
  run_m65 -t "$character"
  sleep "$inter_key"
  sent=$((sent + 1))
  if [ $((sent % 8)) -eq 0 ]; then echo "quiet keys sent: $sent/$keys"; fi
done
sleep "$(jq -r '.D3.quiet_seconds' "$DEPLOY")"
capture_screen repro-editor-quiet-end
run_m65 -t '~C'
sleep 10
capture_screen repro-editor-stopped
grep -q '\*\*\* stopped (run/stop)' "$OUT/repro-editor-stopped.txt"
grep -q 'lisp65>' "$OUT/repro-editor-stopped.txt"

query=$(jq -r '.D3.query_form' "$DEPLOY")
OUT_DIR="$OUT" PREFIX=repro-editor-query TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form "$query"
sleep 10
capture_screen repro-editor-query
grep -q 'vm: undefined function #0ab' "$OUT/repro-editor-query.txt"

OUT_DIR="$OUT" PREFIX=repro-editor-trivial TIMEOUT_SEC=$TIMEOUT \
  scripts/hw-jtag-repl.sh --verified-input --allow-editor-status-tail \
    --no-readback --form '(+ 4 5)'
sleep 5
capture_screen repro-editor-trivial
grep -q 'vm: undefined function #0ab' "$OUT/repro-editor-trivial.txt"

# From here to exit: the single authorized read-only capture.  No keyboard,
# upload, reset, screenshot or product action follows the confirmed failure.
readback $((0x0000008c)) 1 c2-ready
readback $((0x00000079)) 1 rtov-busy
readback $((0x00000089)) 1 c2-phase-owner
readback $((0x0000bff3)) 4 rtov-fault-family-generation
readback $((0x0000c084)) 46 c2-runtime
readback $((0x0000c17c)) 36 abort-record-meta
readback $((0x0000c1f4)) 2 installer-trace
readback $((0x00050000)) 48 c2d-header
readback $((0x00050810)) 32 c2d-high-row63
readback $((0x00050ede)) 10 c2d-lcc-run-row171
readback $((0x0005c640)) 64 c2j

sha256sum "$OUT"/c2-ready.bin "$OUT"/rtov-busy.bin \
  "$OUT"/c2-phase-owner.bin "$OUT"/rtov-fault-family-generation.bin \
  "$OUT"/c2-runtime.bin "$OUT"/abort-record-meta.bin \
  "$OUT"/installer-trace.bin "$OUT"/c2d-header.bin \
  "$OUT"/c2d-high-row63.bin "$OUT"/c2d-lcc-run-row171.bin \
  "$OUT"/c2j.bin
