#!/bin/sh
# Fresh nine-case v1.2.1 G5 session from the exact sealed-R4/R5 medium.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-prepare}
BASE=build/c2.2/v1.2.1-acceptance/r5
SESSION=$BASE/hardware-session-01
EVIDENCE=$SESSION/g5
DEPLOYMENT=$SESSION/deployment.json
PY=tools/host-lisp/c2_v121_g5_hardware.py
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
TIMEOUT=${TIMEOUT:-40}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp

case "$ACTION" in
  prepare|start|resume-stage|resume-runstop|resume-freezer|resume-restage|verify) ;;
  *)
    echo "usage: $0 [prepare|start|resume-stage|resume-runstop|resume-freezer|resume-restage|verify]" >&2
    exit 2
    ;;
esac

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$((rb_start + rb_bytes))
  mkdir -p "$(dirname "$rb_path")"
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$(printf '%08x' "$rb_end")=$rb_path"
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

capture_screen() {
  cs_dir=$1
  cs_prefix=$2
  mkdir -p "$cs_dir"
  run_m65 --screenshot="$cs_dir/$cs_prefix.png" \
    > "$cs_dir/$cs_prefix.ansi.txt"
  python3 - "$cs_dir/$cs_prefix.ansi.txt" "$cs_dir/$cs_prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

wait_for_repl() {
  wr_dir=$1
  wr_prefix=$2
  wr_limit=${3:-90}
  wr_poll=0
  while [ "$wr_poll" -lt "$wr_limit" ]; do
    capture_screen "$wr_dir" "$wr_prefix"
    if grep -Fq 'lisp65>' "$wr_dir/$wr_prefix.txt"; then
      grep -Fq 'WORKBENCH - DIALECT V2' "$wr_dir/$wr_prefix.txt"
      return 0
    fi
    sleep 1
    wr_poll=$((wr_poll + 1))
  done
  echo "v1.2.1 G5 FIRST RED: no product REPL after ${wr_limit}s" >&2
  return 1
}

run_form() {
  rf_dir=$1
  rf_prefix=$2
  rf_form=$3
  rf_wait=$4
  rf_expect=${5:-}
  if [ -n "$rf_expect" ]; then
    OUT_DIR=$rf_dir PREFIX=$rf_prefix TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --wait "$rf_wait" \
        --expect "$rf_expect" --expect-poll 45 --form "$rf_form"
  else
    OUT_DIR=$rf_dir PREFIX=$rf_prefix TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --wait "$rf_wait" \
        --form "$rf_form"
  fi
  python3 - "$rf_dir/$rf_prefix.txt" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for marker in ("*** vm:", "L65SYS DISK ERROR", "CHECK MEDIA"):
    if marker in text:
        raise SystemExit(f"product First Red in {sys.argv[1]}: {marker}")
if "lisp65>" not in text:
    raise SystemExit(f"no returned REPL prompt in {sys.argv[1]}")
PY
}

run_tuple() {
  rt_dir=$1
  rt_prefix=$2
  rt_form=$3
  rt_result=$4
  run_form "$rt_dir" "$rt_prefix" "$rt_form" 4
  python3 - "$rt_dir/$rt_prefix.txt" "$rt_result" <<'PY'
from pathlib import Path
import re
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
result = re.escape(sys.argv[2])
if re.search(rf"^\s*\({result}\s+\d+\s+\d+\)\s*$", text, re.M) is None:
    raise SystemExit(f"measurement tuple missing from {sys.argv[1]}")
PY
}

counter_snapshot() {
  cs_prefix=$1
  python3 scripts/hw-jtag-counters.py \
    --elf "$BASE/product/14-lisp65-c2-substitution-linked.prg.elf" \
    --tools "$TOOLS" --device "$DEVICE" \
    --out-dir "$EVIDENCE/counters" --prefix "$cs_prefix"
}

run_runtime_until_runstop() {
  run_form "$EVIDENCE" definition_setup \
    '(defun %c2h()(quote t))' 4 '%c2h'
  measure='(let((a(peek 215 250)))(let((r(eval(quote(%c2h)))))(list r a(peek 215 250))))'
  run_tuple "$EVIDENCE" definition_first_call "$measure" t
  run_tuple "$EVIDENCE" warm_second_call "$measure" t
  run_form "$EVIDENCE" published_argument_setup \
    '(defun %c2a(x)x)' 4 '%c2a'
  run_tuple "$EVIDENCE" published_argument_call \
    '(let((a(peek 215 250)))(let((r(eval(quote(%c2a 1)))))(list r a(peek 215 250))))' 1

  run_form "$EVIDENCE" gc_fill_setup \
    '(defun %c2gcfill(n)(if(= n 0)t(progn(cons n nil)(%c2gcfill(- n 1)))))' \
    5 '%c2gcfill'
  run_tuple "$EVIDENCE" gc_fill_measure \
    '(let((a(peek 215 250)))(let((r(eval(quote(%c2gcfill 400)))))(list r a(peek 215 250))))' t
  counter_snapshot after_gc
  run_tuple "$EVIDENCE" gc_envelope_measure \
    '(let((a(peek 215 250)))(let((r(eval(quote(%c2gcfill 400)))))(list r a(peek 215 250))))' t
  counter_snapshot after_gc_envelope

  run_form "$EVIDENCE/runstop" setup \
    '(defun c2loop()(c2loop))' 4 c2loop
  readback 0x00050000 33840 "$EVIDENCE/runstop/c2d-before.bin"
  OUT_DIR=$EVIDENCE/runstop PREFIX=call-active TIMEOUT_SEC=$TIMEOUT \
    scripts/hw-jtag-repl.sh --verified-input --no-readback \
      --form '(c2loop)'
  echo "G5 wartet im aktiven c2loop: RUN/STOP einmal physisch drücken."
  echo "Danach weiter mit: $0 resume-runstop"
}

python3 "$PY" prepare
[ "$ACTION" != prepare ] || exit 0

if [ "$ACTION" = verify ]; then
  python3 "$PY" verify
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tools/device unavailable" >&2
  exit 3
}

case "$ACTION" in
  start)
    [ ! -e "$SESSION/media-transport-hardware-receipt.json" ] || {
      echo "fresh G5 start was already consumed" >&2
      exit 3
    }
    media=$(jq -r '.product_d81.path' "$DEPLOYMENT")
    remote=$(jq -r '.remote_media' "$DEPLOYMENT")
    timeout --kill-after=3s 360s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
      -c "put $media $remote" \
      -c "get $remote $SESSION/uploaded-media-readback.d81" \
      -c "mount $remote" -c exit > "$SESSION/media-upload-mount.log"
    cmp "$media" "$SESSION/uploaded-media-readback.d81"
    readback 0x0ffd3632 4 "$SESSION/device-core-id.bin"
    wait_for_repl "$EVIDENCE" cold-boot 120

    for stage in bank2 bank3 session_region1 c2d; do
      address=$(jq -r ".stage_authorities.$stage.address" "$DEPLOYMENT")
      bytes=$(jq -r ".stage_authorities.$stage.bytes" "$DEPLOYMENT")
      path=$(jq -r ".stage_authorities.$stage.path" "$DEPLOYMENT")
      readback "$address" "$bytes" "$SESSION/cold-stage-$stage.bin"
      if [ "$stage" != c2d ]; then
        cmp "$path" "$SESSION/cold-stage-$stage.bin"
      fi
    done
    python3 "$PY" transport
    run_runtime_until_runstop
    ;;

  resume-stage)
    [ ! -e "$EVIDENCE/definition_setup.txt" ] || {
      echo "stage resume runtime rows were already consumed" >&2
      exit 3
    }
    capture_screen "$EVIDENCE" stage-resume
    grep -Fq 'lisp65>' "$EVIDENCE/stage-resume.txt" || {
      echo "stage resume requires the live product REPL" >&2
      exit 3
    }
    for stage in bank2 bank3 session_region1; do
      path=$(jq -r ".stage_authorities.$stage.path" "$DEPLOYMENT")
      cmp "$path" "$SESSION/cold-stage-$stage.bin"
    done
    test "$(wc -c < "$SESSION/cold-stage-c2d.bin")" -eq \
      "$(jq -r '.stage_authorities.c2d.bytes' "$DEPLOYMENT")"
    if [ -e "$SESSION/media-transport-hardware-receipt.json" ]; then
      python3 "$PY" verify
    else
      python3 "$PY" transport
    fi
    run_runtime_until_runstop
    ;;

  resume-runstop)
    [ -f "$EVIDENCE/runstop/call-active-input-attempt-1.txt" ] || {
      echo "RUN/STOP resume requires the submitted c2loop" >&2
      exit 3
    }
    capture_screen "$EVIDENCE/runstop" stopped
    grep -Fq '*** stopped (run/stop)' "$EVIDENCE/runstop/stopped.txt" || {
      echo "G5 FIRST RED: RUN/STOP landing missing" >&2
      exit 1
    }
    readback 0x00050000 33840 "$EVIDENCE/runstop/c2d-after.bin"
    cmp "$EVIDENCE/runstop/c2d-before.bin" \
      "$EVIDENCE/runstop/c2d-after.bin"
    run_form "$EVIDENCE/runstop" continuation '(+ 1 2)' 2 3

    readback 0x00020000 65536 "$EVIDENCE/freezer/bank2-before.bin"
    readback 0x00030000 65536 "$EVIDENCE/freezer/bank3-before.bin"
    readback 0x0000e000 8192 "$EVIDENCE/freezer/e000-before.bin"
    echo "G5-Freezerpunkt bereit: Freezer öffnen und ausdrücklich mit F3 zurückkehren."
    echo "Danach weiter mit: $0 resume-freezer"
    ;;

  resume-freezer)
    [ -f "$EVIDENCE/freezer/e000-before.bin" ] || {
      echo "Freezer resume requires the pre-Freezer snapshots" >&2
      exit 3
    }
    [ ! -e "$EVIDENCE/freezer/e000-after.bin" ] || {
      echo "Freezer resume was already consumed" >&2
      exit 3
    }
    readback 0x00020000 65536 "$EVIDENCE/freezer/bank2-after.bin"
    readback 0x00030000 65536 "$EVIDENCE/freezer/bank3-after.bin"
    readback 0x0000e000 8192 "$EVIDENCE/freezer/e000-after.bin"
    cmp "$EVIDENCE/freezer/bank2-before.bin" \
      "$EVIDENCE/freezer/bank2-after.bin"
    cmp "$EVIDENCE/freezer/bank3-before.bin" \
      "$EVIDENCE/freezer/bank3-after.bin"
    python3 - "$EVIDENCE/freezer/e000-before.bin" \
      "$EVIDENCE/freezer/e000-after.bin" \
      "$EVIDENCE/freezer/e000-diff.json" <<'PY'
from pathlib import Path
import json
import sys
before = Path(sys.argv[1]).read_bytes()
after = Path(sys.argv[2]).read_bytes()
rows = [
    {"address": f"0x{0xE000 + i:04x}", "before": a, "after": b}
    for i, (a, b) in enumerate(zip(before, after)) if a != b
]
Path(sys.argv[3]).write_text(
    json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="ascii")
PY
    run_form "$EVIDENCE/freezer" post_return_arithmetic '(+ 4 5)' 2 9
    run_form "$EVIDENCE/freezer" family_generation \
      '(list(peek 255 135)(peek 255 136))' 2 '(1 4)'

    readback 0x00050000 33840 "$EVIDENCE/nested/c2d-before.bin"
    run_form "$EVIDENCE/nested" nested_eval \
      '(eval(quote(%c2h)))' 3 t
    readback 0x00050000 33840 "$EVIDENCE/nested/c2d-after.bin"
    cmp "$EVIDENCE/nested/c2d-before.bin" \
      "$EVIDENCE/nested/c2d-after.bin"

    upload_and_verify "$EVIDENCE/restage/poison-bank2-prefix.bin" \
      0x00020000 256 "$EVIDENCE/restage/poison-bank2-readback.bin"
    upload_and_verify "$EVIDENCE/restage/poison-bank3-prefix.bin" \
      0x00030000 256 "$EVIDENCE/restage/poison-bank3-readback.bin"

    echo "Destruktive Ausgangslage ist gebunden: Gerät jetzt physisch kalt nach BASIC starten."
    echo "Danach weiter mit: $0 resume-restage"
    ;;

  resume-restage)
    [ -f "$EVIDENCE/restage/poison-bank2-readback.bin" ] &&
      [ -f "$EVIDENCE/restage/poison-bank3-readback.bin" ] || {
      echo "restage resume requires the verified destructive setup" >&2
      exit 3
    }
    [ ! -e "$EVIDENCE/restage/post-media-restage.txt" ] || {
      echo "restage resume was already consumed" >&2
      exit 3
    }
    capture_screen "$EVIDENCE/restage" pre-restage-basic
    grep -Fq 'READY.' "$EVIDENCE/restage/pre-restage-basic.txt" || {
      echo "restage resume requires the physical cold-start BASIC prompt" >&2
      exit 3
    }
    remote=$(jq -r '.remote_media' "$DEPLOYMENT")
    timeout --kill-after=3s 180s "$FTP" -F -l "$DEVICE" -s 2000000 -y \
      -c "mount $remote" -c exit > "$EVIDENCE/restage/media-cold-mount.log"
    wait_for_repl "$EVIDENCE/restage" post-media-restage 120

    bank2_path=$(jq -r '.stage_authorities.bank2.path' "$DEPLOYMENT")
    bank2_bytes=$(jq -r '.stage_authorities.bank2.bytes' "$DEPLOYMENT")
    readback 0x00020000 "$bank2_bytes" \
      "$EVIDENCE/restage/bank2-media-repaired.bin"
    cmp "$bank2_path" "$EVIDENCE/restage/bank2-media-repaired.bin"
    bank3_path=$(jq -r '.stage_authorities.bank3.path' "$DEPLOYMENT")
    bank3_bytes=$(jq -r '.stage_authorities.bank3.bytes' "$DEPLOYMENT")
    readback 0x00030000 "$bank3_bytes" \
      "$EVIDENCE/restage/bank3-media-repaired.bin"
    cmp "$bank3_path" "$EVIDENCE/restage/bank3-media-repaired.bin"
    run_form "$EVIDENCE/restage" post_media_restage_repl '(+ 2 3)' 2 5

    python3 "$PY" close
    python3 "$PY" verify
    echo "v1.2.1 G5: PASS — neun frische Fälle, exaktes R5-Medium."
    ;;
esac
