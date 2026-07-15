#!/bin/sh
# Reproducible HW smoke for the M4 directory-entry write step.
#
# This test writes only to a generated throwaway copy of the Workbench D81. It
# runs a dedicated PRG that writes a two-sector source chain, allocates the
# sectors in the BAM, writes a directory entry last, downloads the D81, verifies
# the exact host diff, then boots the Workbench against that throwaway image and
# loads the file via normal (load "m4src"). No hard JTAG reset is used.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-dir-write}"
wait_sec="${WAIT_SEC:-3}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
form_wait_sec="${FORM_WAIT_SEC:-3}"
timeout_sec="${TIMEOUT_SEC:-20}"
deploy_timeout="${DEPLOY_TIMEOUT_SEC:-180}"
remote_d81="${WORKBENCH_M4_REMOTE_D81:-L65M4.D81}"
ship_d81="${MVP_VM_SHIP_D81:-build/ship/lisp65-mvp-workbench.d81}"
before_d81="${WORKBENCH_M4_BEFORE_D81:-build/hw/workbench-m4-before.d81}"
after_d81="${WORKBENCH_M4_AFTER_D81:-build/hw/workbench-m4-after.d81}"
prg="${M65HWDIRWRITEPRG:-build/lisp65-mega65-hw-dir-write-smoke.prg}"
source_lisp="${WORKBENCH_M4_SOURCE:-tests/disk/m4-dir-source.lisp}"
target_name="${WORKBENCH_M4_NAME:-m4src}"
target_track=45
first_sector=8
second_sector=9
dir_track=40
dir_sector=4
dir_entry=2
expect="dir write pass 11/11"
restore=1
restore_armed=0
restored=0

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run             print commands; no Etherload/JTAG side effects
  --no-build            reuse existing MVP Workbench ship/test artifacts
  --ip <ipv6%iface>     MEGA65 target for etherload/ftp
  --tools <dir>         m65tools directory (default: $tools_dir)
  --device <dev>        JTAG serial device for screenshot/REPL (default: $device)
  --out-dir <dir>       screenshot/text output directory (default: $out_dir)
  --prefix <name>       readback filename prefix (default: $prefix)
  --wait <seconds>      wait before screenshot (default: $wait_sec)
  --boot-wait <seconds> wait after Workbench oracle deploy (default: $boot_wait_sec)
  --form-wait <seconds> wait after each REPL form (default: $form_wait_sec)
  --timeout <seconds>   timeout for m65 commands (default: $timeout_sec)
  --deploy-timeout <s>  timeout for Workbench deploy wrapper (default: $deploy_timeout)
  --remote-d81 <name>   throwaway D81 name on MEGA65 SD (default: $remote_d81)
  --before-d81 <file>   local throwaway image before HW run (default: $before_d81)
  --after-d81 <file>    local downloaded image after HW run (default: $after_d81)
  --source <file>       expected Lisp payload (default: $source_lisp)
  --name <file-name>    D81 directory filename (default: $target_name)
  --prg <file>          directory-write PRG (default: $prg)
  --no-restore          leave machine after the M4 oracle/readback path
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
    --boot-wait) shift; [ "$#" -gt 0 ] || usage; boot_wait_sec="$1" ;;
    --form-wait) shift; [ "$#" -gt 0 ] || usage; form_wait_sec="$1" ;;
    --timeout) shift; [ "$#" -gt 0 ] || usage; timeout_sec="$1" ;;
    --deploy-timeout) shift; [ "$#" -gt 0 ] || usage; deploy_timeout="$1" ;;
    --remote-d81) shift; [ "$#" -gt 0 ] || usage; remote_d81="$1" ;;
    --before-d81) shift; [ "$#" -gt 0 ] || usage; before_d81="$1" ;;
    --after-d81) shift; [ "$#" -gt 0 ] || usage; after_d81="$1" ;;
    --source) shift; [ "$#" -gt 0 ] || usage; source_lisp="$1" ;;
    --name) shift; [ "$#" -gt 0 ] || usage; target_name="$1" ;;
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
case "$boot_wait_sec" in ''|*[!0-9]*) echo "Fehler: --boot-wait muss numerisch sein" >&2; exit 2 ;; esac
case "$form_wait_sec" in ''|*[!0-9]*) echo "Fehler: --form-wait muss numerisch sein" >&2; exit 2 ;; esac
case "$timeout_sec" in ''|*[!0-9]*) echo "Fehler: --timeout muss numerisch sein" >&2; exit 2 ;; esac
case "$deploy_timeout" in ''|*[!0-9]*) echo "Fehler: --deploy-timeout muss numerisch sein" >&2; exit 2 ;; esac

mkdir -p "$out_dir" "$(dirname "$before_d81")" "$(dirname "$after_d81")"

if [ "$build" = "1" ]; then
  echo "==> baue MVP-Ship und Directory-Write-Test-PRG"
  make mvp-ship hw-workbench-dir-write-smoke-prg
fi

restore_workbench() {
  [ "$restore" = "1" ] || return 0
  [ "$restored" = "0" ] || return 0
  restored=1
  echo "==> stelle Workbench nach M4-Smoke wieder her"
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
  echo "DRY-RUN: python3 tools/host-lisp/d81_dir_write_diff.py --selftest $before_d81 --source $source_lisp --name $target_name --track $target_track --first-sector $first_sector --second-sector $second_sector --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
else
  [ -f "$ship_d81" ] || { echo "Fehler: Workbench-D81 fehlt: $ship_d81" >&2; exit 3; }
  [ -f "$prg" ] || { echo "Fehler: Directory-Write-PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$source_lisp" ] || { echo "Fehler: M4-Quelle fehlt: $source_lisp" >&2; exit 3; }
  cp "$ship_d81" "$before_d81"
  rm -f "$after_d81"
  python3 tools/host-lisp/d81_dir_write_diff.py --selftest "$before_d81" \
    --source "$source_lisp" --name "$target_name" \
    --track "$target_track" --first-sector "$first_sector" \
    --second-sector "$second_sector" --dir-track "$dir_track" \
    --dir-sector "$dir_sector" --dir-entry "$dir_entry"
fi

upload_throwaway() {
  ftp="$tools_dir/mega65_ftp"
  if [ "$dry_run" != "1" ]; then
    [ -x "$ftp" ] || { echo "Fehler: $ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
  fi
  echo "==> lege M4-Wegwerf-D81 auf die SD: $remote_d81"
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
  echo "==> starte M4-Directory-Write-PRG (kein m65 -F)"
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
    echo "DRY-RUN: python3 tools/host-lisp/d81_dir_write_diff.py $before_d81 $after_d81 --source $source_lisp --name $target_name --track $target_track --first-sector $first_sector --second-sector $second_sector --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
  else
    python3 tools/host-lisp/d81_dir_write_diff.py "$before_d81" "$after_d81" \
      --source "$source_lisp" --name "$target_name" \
      --track "$target_track" --first-sector "$first_sector" \
      --second-sector "$second_sector" --dir-track "$dir_track" \
      --dir-sector "$dir_sector" --dir-entry "$dir_entry"
  fi
}

deploy_oracle_workbench() {
  set -- --no-build --tools "$tools_dir" --d81 "$after_d81" --remote-d81 "$remote_d81"
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run

  echo "==> deploye Workbench fuer M4-Load-Oracle gegen $remote_d81"
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: timeout ${deploy_timeout}s sh scripts/hw-smoke-vm-stdlib.sh $*"
    sh scripts/hw-smoke-vm-stdlib.sh "$@"
  else
    timeout "${deploy_timeout}s" sh scripts/hw-smoke-vm-stdlib.sh "$@"
  fi
  if [ "$boot_wait_sec" -gt 0 ]; then
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: sleep $boot_wait_sec"
    else
      echo "==> warte ${boot_wait_sec}s auf Workbench-REPL"
      sleep "$boot_wait_sec"
    fi
  fi
}

run_oracle_phase() {
  phase=$1
  marker=$2
  form=$3
  set -- --form "$form" --prefix "$prefix-$phase" --out-dir "$out_dir" \
    --tools "$tools_dir" --device "$device" --wait "$wait_sec" \
    --form-wait "$form_wait_sec" --timeout "$timeout_sec" --expect "$marker" \
    --verified-input
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  echo "==> JTAG-REPL-Oracle: $phase"
  scripts/hw-jtag-repl.sh "$@"
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

deploy_oracle_workbench
run_oracle_phase load-dir "\"m4-load-ok\"" "(if (load \"m4src\") \"m4-load-ok\" \"m4-load-fail\")"
run_oracle_phase run-dir "767" "(m4-dir-run)"

restore_armed=0
restore_workbench

echo "PASS Workbench dir-write HW smoke"
