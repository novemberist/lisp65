#!/bin/sh
# Reproducible HW smoke for the first destructive BAM step (M2).
#
# This test writes only to a generated throwaway copy of the Workbench D81. It
# runs a dedicated PRG, then downloads the D81 and verifies that only the
# expected BAM bytes changed. No hard JTAG reset is used. The default live path
# restores the current Workbench afterwards because mega65_ftp readback can leave
# the machine in BASIC.
set -eu

cd "$(dirname "$0")/.."

fixture_get() {
  python3 tools/host-lisp/r5_persistence_fixtures.py get "$1"
}

dry_run=0
build=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-bam-alloc}"
wait_sec="${WAIT_SEC:-3}"
timeout_sec="${TIMEOUT_SEC:-20}"
remote_d81="${WORKBENCH_M2_REMOTE_D81:-L65M2.D81}"
ship_d81="${MVP_VM_SHIP_D81:-build/ship/lisp65-mvp-workbench.d81}"
before_d81="${WORKBENCH_M2_BEFORE_D81:-build/hw/workbench-m2-before.d81}"
after_d81="${WORKBENCH_M2_AFTER_D81:-build/hw/workbench-m2-after.d81}"
prg="${M65HWBAMALLOCPRG:-build/lisp65-mega65-hw-bam-alloc-smoke.prg}"
restore=1
restore_armed=0
restored=0
target_track="$(fixture_get fixed_write.track)"
target_sector="$(fixture_get fixed_write.first_sector)"
expect="bam alloc pass 4/4"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run             print commands; no Etherload/JTAG side effects
  --no-build            reuse existing MVP Workbench ship/test artifacts
  --ip <ipv6%iface>     MEGA65 target for etherload/ftp
  --tools <dir>         m65tools directory (default: $tools_dir)
  --device <dev>        JTAG serial device for screenshot (default: $device)
  --out-dir <dir>       screenshot/text output directory (default: $out_dir)
  --prefix <name>       readback filename prefix (default: $prefix)
  --wait <seconds>      wait before screenshot/fetch (default: $wait_sec)
  --timeout <seconds>   timeout for m65 commands (default: $timeout_sec)
  --remote-d81 <name>   throwaway D81 name on MEGA65 SD (default: $remote_d81)
  --before-d81 <file>   local throwaway image before HW run (default: $before_d81)
  --after-d81 <file>    local downloaded image after HW run (default: $after_d81)
  --track <n>           fixture data track (default: $target_track)
  --sector <n>          fixture data sector (default: $target_sector)
  --prg <file>          BAM alloc PRG (default: $prg)
  --no-restore          leave machine after the M2 mini-PRG/readback path
  --restore-workbench   redeploy Workbench after live test (default)
  -h|--help             this help
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --ip) shift; [ "$#" -gt 0 ] || usage; ip="$1" ;;
    --tools) shift; [ "$#" -gt 0 ] || usage; tools_dir="$1" ;;
    --device) shift; [ "$#" -gt 0 ] || usage; device="$1" ;;
    --out-dir) shift; [ "$#" -gt 0 ] || usage; out_dir="$1" ;;
    --prefix) shift; [ "$#" -gt 0 ] || usage; prefix="$1" ;;
    --wait) shift; [ "$#" -gt 0 ] || usage; wait_sec="$1" ;;
    --timeout) shift; [ "$#" -gt 0 ] || usage; timeout_sec="$1" ;;
    --remote-d81) shift; [ "$#" -gt 0 ] || usage; remote_d81="$1" ;;
    --before-d81) shift; [ "$#" -gt 0 ] || usage; before_d81="$1" ;;
    --after-d81) shift; [ "$#" -gt 0 ] || usage; after_d81="$1" ;;
    --track) shift; [ "$#" -gt 0 ] || usage; target_track="$1" ;;
    --sector) shift; [ "$#" -gt 0 ] || usage; target_sector="$1" ;;
    --prg) shift; [ "$#" -gt 0 ] || usage; prg="$1" ;;
    --no-restore) restore=0 ;;
    --restore-workbench) restore=1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

case "$wait_sec" in ''|*[!0-9]*) echo "Fehler: --wait muss numerisch sein" >&2; exit 2 ;; esac
case "$timeout_sec" in ''|*[!0-9]*) echo "Fehler: --timeout muss numerisch sein" >&2; exit 2 ;; esac
case "$target_track" in ''|*[!0-9]*) echo "Fehler: --track muss numerisch sein" >&2; exit 2 ;; esac
case "$target_sector" in ''|*[!0-9]*) echo "Fehler: --sector muss numerisch sein" >&2; exit 2 ;; esac

mkdir -p "$out_dir" "$(dirname "$before_d81")" "$(dirname "$after_d81")"

if [ "$build" = "1" ]; then
  echo "==> baue MVP-Ship und BAM-Alloc-Test-PRG"
  make mvp-ship hw-workbench-bam-alloc-smoke-prg
fi

restore_workbench() {
  [ "$restore" = "1" ] || return 0
  [ "$restored" = "0" ] || return 0
  restored=1
  echo "==> stelle Workbench nach M2-Smoke wieder her"
  set -- --no-build --tools "$tools_dir"
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  sh scripts/hw-smoke-vm-stdlib.sh "$@"
}

on_exit() {
  status=$?
  restore_status=0
  trap - EXIT
  if [ "$restore_armed" = "1" ]; then
    restore_workbench || restore_status=$?
  fi
  if [ "$status" != "0" ]; then
    exit "$status"
  fi
  exit "$restore_status"
}

trap on_exit EXIT

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: cp $ship_d81 $before_d81"
  echo "DRY-RUN: rm -f $after_d81"
  echo "DRY-RUN: python3 tools/host-lisp/d81_bam_alloc_diff.py --selftest $before_d81 --track $target_track --sector $target_sector"
else
  [ -f "$ship_d81" ] || { echo "Fehler: Workbench-D81 fehlt: $ship_d81" >&2; exit 3; }
  [ -f "$prg" ] || { echo "Fehler: BAM-Alloc-PRG fehlt: $prg" >&2; exit 3; }
  cp "$ship_d81" "$before_d81"
  rm -f "$after_d81"
  python3 tools/host-lisp/d81_bam_alloc_diff.py --selftest "$before_d81" \
    --track "$target_track" --sector "$target_sector"
fi

upload_throwaway() {
  ftp="$tools_dir/mega65_ftp"
  if [ "$dry_run" != "1" ]; then
    [ -x "$ftp" ] || { echo "Fehler: $ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
  fi
  echo "==> lege M2-Wegwerf-D81 auf die SD: $remote_d81"
  if [ "$dry_run" = "1" ]; then
    if [ -n "$ip" ]; then
      echo "DRY-RUN: $ftp -e -i $ip -y -c \"put $before_d81 $remote_d81\" -c \"exit\""
    else
      echo "DRY-RUN: $ftp -e -y -c \"put $before_d81 $remote_d81\" -c \"exit\""
    fi
  elif [ -n "$ip" ]; then
    "$ftp" -e -i "$ip" -y -c "put $before_d81 $remote_d81" -c "exit"
  else
    "$ftp" -e -y -c "put $before_d81 $remote_d81" -c "exit"
  fi
}

run_prg() {
  set -- --tools "$tools_dir" --mount "$remote_d81" --run
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  set -- "$@" "$prg"
  echo "==> starte M2-BAM-Alloc-PRG (kein m65 -F)"
  sh scripts/run-on-mega65.sh "$@"
}

capture_screen() {
  shot="$out_dir/$prefix.png"
  ansi="$out_dir/$prefix.ansi.txt"
  text="$out_dir/$prefix.txt"
  m65="$tools_dir/m65"
  if [ "$dry_run" != "1" ]; then
    [ -x "$m65" ] || { echo "Fehler: $m65 nicht ausfuehrbar/gefunden" >&2; return 3; }
  fi
  echo "==> pruefe sichtbaren Marker: $expect"
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: sleep $wait_sec"
    echo "DRY-RUN: timeout ${timeout_sec}s $m65 -l $device --screenshot=$shot > $ansi"
    echo "DRY-RUN: strip ANSI $ansi > $text"
    echo "DRY-RUN: grep -F '$expect' $text"
    return 0
  fi
  sleep "$wait_sec"
  timeout "${timeout_sec}s" "$m65" -l "$device" --screenshot="$shot" > "$ansi"
  python3 - "$ansi" "$text" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw))
PY
  grep -F "$expect" "$text" >/dev/null
}

fetch_after_image() {
  ftp="$tools_dir/mega65_ftp"
  if [ "$dry_run" != "1" ]; then
    [ -x "$ftp" ] || { echo "Fehler: $ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
  fi
  echo "==> hole mutierte Wegwerf-D81 zurueck: $remote_d81 -> $after_d81"
  if [ "$dry_run" = "1" ]; then
    if [ -n "$ip" ]; then
      echo "DRY-RUN: $ftp -e -i $ip -y -c \"get $remote_d81 $after_d81\" -c \"exit\""
    else
      echo "DRY-RUN: $ftp -e -y -c \"get $remote_d81 $after_d81\" -c \"exit\""
    fi
  elif [ -n "$ip" ]; then
    "$ftp" -e -i "$ip" -y -c "get $remote_d81 $after_d81" -c "exit"
  else
    "$ftp" -e -y -c "get $remote_d81 $after_d81" -c "exit"
  fi
}

verify_after_image() {
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: python3 tools/host-lisp/d81_bam_alloc_diff.py $before_d81 $after_d81 --track $target_track --sector $target_sector"
  else
    python3 tools/host-lisp/d81_bam_alloc_diff.py "$before_d81" "$after_d81" \
      --track "$target_track" --sector "$target_sector"
  fi
}

upload_throwaway
restore_armed=1
run_prg

screen_status=0
capture_screen || screen_status=$?
fetch_after_image
verify_after_image

if [ "$screen_status" != "0" ]; then
  echo "Fehler: sichtbarer Marker fehlt: $expect" >&2
  exit "$screen_status"
fi

restore_armed=0
restore_workbench

echo "PASS Workbench BAM-alloc HW smoke"
