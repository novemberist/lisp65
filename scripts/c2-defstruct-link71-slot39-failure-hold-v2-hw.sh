#!/bin/sh
# Boot pristine Link 71, activate identity-preserving Slot-39 holds late.
set -eu
cd "$(dirname "$0")/.."

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-35}
OUT=build/post-promotion/link71-defstruct-header-crc-domain/slot39-failure-hold-v2-late-NONPROMOTABLE
DEPLOY=$OUT/deployment.json
PY=tools/host-lisp/c2_defstruct_link71_slot39_failure_hold_v2.py
PC=tools/host-lisp/c2_defstruct_link71_slot39_pc_capture_v2.py
M65=$TOOLS/m65

[ "$#" -eq 1 ] || {
  echo "usage: $0 <deploy|install|arm|capture>" >&2
  exit 2
}
ACTION=$1
case "$ACTION" in
  deploy|install|arm|capture) ;;
  *) echo "usage: $0 <deploy|install|arm|capture>" >&2; exit 2 ;;
esac

python3 "$PY" verify
[ -x "$M65" ] || { echo "missing JTAG loader: $M65" >&2; exit 3; }
[ -c "$DEVICE" ] || { echo "missing JTAG device: $DEVICE" >&2; exit 3; }

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  start=$1
  bytes=$2
  path=$3
  end=$((start + bytes))
  run_m65 --memsave \
    "0x$(printf '%08x' "$start"):0x$(printf '%08x' "$end")=$path"
}

capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

case "$ACTION" in
deploy)
  [ ! -e "$OUT/hardware-run.started" ] || {
    echo "Link-71 Slot-39 v2 diagnostic is one-shot" >&2
    exit 3
  }
  PRG=$(jq -r '.product.path' "$DEPLOY")
  run_m65 -F -H -1 "$PRG"
  touch "$OUT/hardware-run.started"
  jq -c '.boot_preloads[]' "$DEPLOY" |
  while IFS= read -r item; do
    path=$(printf '%s' "$item" | jq -r '.path')
    address=$(printf '%s' "$item" | jq -r '.address')
    bytes=$(printf '%s' "$item" | jq -r '.bytes')
    base=$(basename "$path")
    run_m65 -H -@ "$path@$address"
    readback "$((address))" "$bytes" "$OUT/deploy-readback-$base"
    cmp "$path" "$OUT/deploy-readback-$base"
  done
  run_m65 -r -1 "$PRG"
  poll=0
  while [ "$poll" -lt 45 ]; do
    capture_screen boot
    grep -q 'lisp65>' "$OUT/boot.txt" && break
    sleep 1
    poll=$((poll + 1))
  done
  [ "$poll" -lt 45 ] || {
    echo "Link-71 pristine boot did not reach a clean REPL" >&2
    exit 3
  }
  echo "Pristine Link 71 ready; install late Slot-39 carrier next."
  ;;
install)
  [ -e "$OUT/hardware-run.started" ] || exit 3
  [ ! -e "$OUT/late-carrier.installed" ] || {
    echo "late Slot-39 carrier installation is one-shot" >&2
    exit 3
  }
  path=$(jq -r '.late_preload.path' "$DEPLOY")
  address=$(jq -r '.late_preload.address' "$DEPLOY")
  bytes=$(jq -r '.late_preload.bytes' "$DEPLOY")
  run_m65 -H -@ "$path@$address"
  readback "$((address))" "$bytes" "$OUT/late-carrier-readback.bin"
  cmp "$path" "$OUT/late-carrier-readback.bin"
  touch "$OUT/late-carrier.installed"
  echo "Identity-preserving Slot-39 carrier installed after clean boot."
  ;;
arm)
  [ -e "$OUT/late-carrier.installed" ] || exit 3
  OUT_DIR=$OUT PREFIX=slot39-v2-arm TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form "$(jq -r '.test.form' "$DEPLOY")"
  sleep 2
  capture_screen slot39-v2-screen
  grep -q '(%disk-load-lib 39 1)' "$OUT/slot39-v2-screen.txt" || exit 3
  if grep -q '\*\*\* vm:' "$OUT/slot39-v2-screen.txt"; then
    echo "Slot-39 escaped all holds; diagnosis is incomplete."
    exit 3
  fi
  echo "Slot-39 failure hold reached; capture PC and state next."
  ;;
capture)
  [ -e "$OUT/late-carrier.installed" ] || exit 3
  python3 "$PC"
  i=1
  while [ "$i" -le 3 ]; do
    dir=$OUT/capture-$i
    mkdir "$dir"
    readback 0x0000c17c 32 "$dir/completion-record.bin"
    readback 0x0005c640 64 "$dir/c2j.bin"
    readback 0x0000c0c6 304 "$dir/phase-scratch.bin"
    readback 0x0000c356 1419 "$dir/runtime-slot39.bin"
    [ "$i" -eq 3 ] || sleep 1
    i=$((i + 1))
  done
  for name in completion-record c2j phase-scratch runtime-slot39; do
    cmp "$OUT/capture-1/$name.bin" "$OUT/capture-2/$name.bin"
    cmp "$OUT/capture-1/$name.bin" "$OUT/capture-3/$name.bin"
  done
  capture_screen slot39-v2-screen
  python3 - "$OUT" <<'PY'
from pathlib import Path
import json
import sys
out = Path(sys.argv[1])
record = (out / "capture-1/completion-record.bin").read_bytes()
c2j = (out / "capture-1/c2j.bin").read_bytes()
pc = json.loads((out / "pc-captures.json").read_text())["rows"][0]
print(json.dumps({
    "PC": pc["PC"],
    "failure_site": pc["site"],
    "completion_mode": f"0x{record[24]:02x}",
    "journal_result": record[31],
    "producer_seal": f"0x{record[25] | record[26] << 8:04x}",
    "target_nonzero_bytes": sum(bool(value) for value in c2j),
}, sort_keys=True))
PY
  echo "Slot-39 PC/state captured; diagnostic retired."
  ;;
esac
