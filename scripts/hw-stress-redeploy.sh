#!/bin/sh
# lisp65 -- repeated Etherload deploy stress, with optional JTAG readback.
# This intentionally does not call m65 -F. It validates the normal workflow where
# the MEGA65 remains remote-armed and each iteration deploys from the running
# product/test state.
set -eu
cd "$(dirname "$0")/.."

count=3
wait_sec=5
ip=""
tools_dir="tools/m65tools"
device="/dev/ttyUSB1"
out_dir="build/hw"
prefix="hw-stress-redeploy"
dry_run=0
build=1
dma_prof=0
deep=0
readback=1
expect="stress pass 15/15"
expect_set=0

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --count <n>        number of deploy cycles (default: $count)
  --wait <seconds>   wait before final JTAG readback (default: $wait_sec)
  --ip <ipv6%iface>  MEGA65 etherload target
  --tools <dir>      m65tools directory (default: $tools_dir)
  --device <dev>     m65 serial/JTAG device (default: $device)
  --out-dir <dir>    readback output directory (default: $out_dir)
  --prefix <name>    readback filename prefix (default: $prefix)
  --dma-prof         build/run the DMA profiling variant; not with --deep
  --deep <1|2>       build/run a Deep-Dive stress shard
  --no-build         reuse existing PRG/blob artifacts
  --no-readback      skip final screenshot/counter readback
  --expect <text>    text marker expected in final JTAG text dump (default: $expect)
  --no-expect        do not check final text dump
  --dry-run          print commands; no Etherload/JTAG actions
  -h|--help          this help
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --count) shift; count="$1" ;;
    --wait) shift; wait_sec="$1" ;;
    --ip) shift; ip="$1" ;;
    --tools) shift; tools_dir="$1" ;;
    --device) shift; device="$1" ;;
    --out-dir) shift; out_dir="$1" ;;
    --prefix) shift; prefix="$1" ;;
    --dma-prof) dma_prof=1 ;;
    --deep) shift; deep="$1" ;;
    --no-build) build=0 ;;
    --no-readback) readback=0 ;;
    --expect) shift; expect="$1"; expect_set=1 ;;
    --no-expect) expect="" ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

case "$count" in
  ''|*[!0-9]*) echo "Fehler: --count muss numerisch sein" >&2; exit 2 ;;
esac
[ "$count" -gt 0 ] || { echo "Fehler: --count muss >0 sein" >&2; exit 2; }
case "$wait_sec" in
  ''|*[!0-9]*) echo "Fehler: --wait muss numerisch sein" >&2; exit 2 ;;
esac
case "$deep" in
  0|1|2) ;;
  *) echo "error: --deep expects 1 or 2" >&2; exit 2 ;;
esac
if [ "$deep" != "0" ] && [ "$dma_prof" = "1" ]; then
  echo "Fehler: --deep + --dma-prof passt aktuell nicht unter die Etherload-Invariante" >&2
  exit 2
fi

if [ "$dma_prof" = "1" ]; then
  case "$prefix" in
    *-dmaprof) ;;
    *) prefix="${prefix}-dmaprof" ;;
  esac
fi
if [ "$deep" != "0" ]; then
  case "$prefix" in
    *-deep*) ;;
    *) prefix="${prefix}-deep${deep}" ;;
  esac
  [ "$expect_set" = "0" ] && expect="stress deep${deep} pass 5/5"
fi

stress_args="--tools $tools_dir"
[ -n "$ip" ] && stress_args="$stress_args --ip $ip"
[ "$dma_prof" = "1" ] && stress_args="$stress_args --dma-prof"
[ "$deep" != "0" ] && stress_args="$stress_args --deep $deep"
[ "$dry_run" = "1" ] && stress_args="$stress_args --dry-run"

if [ "$build" = "1" ]; then
  echo "==> baue Stress-Artefakte einmalig (ohne Live-Deploy)"
  # Build once, but keep deployment dry here. The loop below performs the real cycles.
  sh scripts/hw-stress-full.sh $stress_args --dry-run
fi

i=1
while [ "$i" -le "$count" ]; do
  echo "==> redeploy $i/$count (kein m65 -F)"
  sh scripts/hw-stress-full.sh $stress_args --no-build
  if [ "$dry_run" != "1" ]; then sleep 2; fi
  i=$((i + 1))
done

[ "$readback" = "1" ] || exit 0

prg="build/lisp65-hw-stress-full.prg"
[ "$deep" = "1" ] && prg="build/lisp65-hw-stress-deep1.prg"
[ "$deep" = "2" ] && prg="build/lisp65-hw-stress-deep2.prg"
[ "$dma_prof" = "1" ] && prg="${prg%.prg}-dmaprof.prg"
elf="$prg.elf"

mkdir -p "$out_dir"
shot="$out_dir/$prefix-final.png"
ansi="$out_dir/$prefix-final.ansi.txt"

echo "==> finaler JTAG-Screenshot"
if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $tools_dir/m65 -l $device --screenshot=$shot > $ansi"
else
  sleep "$wait_sec"
  "$tools_dir/m65" -l "$device" --screenshot="$shot" > "$ansi"
fi

if [ -n "$expect" ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: ANSI-strip + grep -F '$expect' $ansi"
  elif python3 - "$ansi" "$expect" <<'PY'
from pathlib import Path
import re
import sys

ansi_path, expect = sys.argv[1], sys.argv[2]
text = Path(ansi_path).read_text(errors="ignore")
clean = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", text)
sys.exit(0 if expect in clean else 1)
PY
  then
    echo "PASS marker gefunden: $expect"
  else
    echo "Fehler: PASS-Marker fehlt in $ansi: $expect" >&2
    exit 4
  fi
fi

echo "==> JTAG-Counter-Dump"
set -- --elf "$elf" --device "$device" --tools "$tools_dir" --out-dir "$out_dir" --prefix "$prefix-counters"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
python3 scripts/hw-jtag-counters.py "$@"
