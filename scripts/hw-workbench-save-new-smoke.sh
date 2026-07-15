#!/bin/sh
# Reproducible HW smoke for Lisp save-new allocator prototypes.
#
# This test writes only to a generated throwaway copy of the Workbench D81. It
# runs a dedicated PRG that evaluates a Lisp allocator, creates a source file,
# downloads the D81, verifies the exact host diff, then boots the Workbench
# against that throwaway image and loads the file via normal (load "<name>").
# No hard JTAG reset is used.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
c1541_bin="${C1541:-c1541}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-save-new}"
wait_sec="${WAIT_SEC:-10}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
form_wait_sec="${FORM_WAIT_SEC:-3}"
timeout_sec="${TIMEOUT_SEC:-20}"
deploy_timeout="${DEPLOY_TIMEOUT_SEC:-180}"
remote_d81="${WORKBENCH_M5_REMOTE_D81:-L65M5.D81}"
ship_d81="${MVP_VM_SHIP_D81:-build/ship/lisp65-mvp-workbench.d81}"
before_d81="${WORKBENCH_M5_BEFORE_D81:-build/hw/workbench-m5-before.d81}"
after_d81="${WORKBENCH_M5_AFTER_D81:-build/hw/workbench-m5-after.d81}"
prg="${M65HWSAVENEWPRG:-build/lisp65-mega65-hw-save-new-smoke.prg}"
source_lisp="${WORKBENCH_M5_SOURCE:-tests/disk/m5-new-source.lisp}"
alloc_lisp="${WORKBENCH_M5_ALLOC_SOURCE:-lib/m65-disk-alloc.lisp}"
target_name="${WORKBENCH_M5_NAME:-m5src}"
alloc_name="${WORKBENCH_M5_ALLOC_NAME:-m5alloc}"
target_track="${WORKBENCH_M5_TRACK:-45}"
first_sector="${WORKBENCH_M5_FIRST_SECTOR:-26}"
second_sector="${WORKBENCH_M5_SECOND_SECTOR:-27}"
dir_track="${WORKBENCH_M5_DIR_TRACK:-40}"
dir_sector="${WORKBENCH_M5_DIR_SECTOR:-4}"
dir_entry="${WORKBENCH_M5_DIR_ENTRY:-3}"
expect="save new pass 5/5"
restore=1
restore_armed=0
restored=0
reserve_track="${WORKBENCH_M5_RESERVE_TRACK:-}"
reserve_sector="${WORKBENCH_M5_RESERVE_SECTOR:-}"
diff_mode="${WORKBENCH_M5_DIFF_MODE:-fixed}"
load_ok="${SAVE_NEW_LOAD_OK:-m5-load-ok}"
load_fail="${SAVE_NEW_LOAD_FAIL:-m5-load-fail}"
run_form="${SAVE_NEW_RUN_FORM:-(m5-new-run)}"
run_expect="${SAVE_NEW_RUN_EXPECT:-797}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run             print commands; no Etherload/JTAG side effects
  --no-build            reuse existing MVP Workbench ship/test artifacts
  --ip <ipv6%iface>     MEGA65 target for etherload/ftp
  --tools <dir>         m65tools directory (default: $tools_dir)
  --c1541 <path>        c1541 binary (default: $c1541_bin)
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
  --alloc-source <file> allocator Lisp loaded as $alloc_name (default: $alloc_lisp)
  --alloc-name <name>   allocator D81 filename (default: $alloc_name)
  --name <file-name>    D81 directory filename (default: $target_name)
  --track <n>           expected data track (default: $target_track)
  --first-sector <n>    expected first data sector (default: $first_sector)
  --second-sector <n>   expected second data sector (default: $second_sector)
  --dir-track <n>       expected directory track (default: $dir_track)
  --dir-sector <n>      expected directory sector (default: $dir_sector)
  --dir-entry <n>       expected directory entry index (default: $dir_entry)
  --generic-diff        verify via BAM-derived variable-chain oracle
  --reserve-track <n>   reserve T<n>/S<sector> in the throwaway BAM before run
  --reserve-sector <n>  reserve T<track>/S<n> in the throwaway BAM before run
  --load-ok <text>      load oracle success string (default: $load_ok)
  --load-fail <text>    load oracle failure string (default: $load_fail)
  --run-form <form>     Workbench oracle form after load (default: $run_form)
  --run-expect <text>   expected output marker for --run-form (default: $run_expect)
  --prg <file>          save-new PRG (default: $prg)
  --no-restore          leave machine after the save-new oracle/readback path
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
    --c1541) shift; [ "$#" -gt 0 ] || usage; c1541_bin="$1" ;;
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
    --alloc-source) shift; [ "$#" -gt 0 ] || usage; alloc_lisp="$1" ;;
    --alloc-name) shift; [ "$#" -gt 0 ] || usage; alloc_name="$1" ;;
    --name) shift; [ "$#" -gt 0 ] || usage; target_name="$1" ;;
    --track) shift; [ "$#" -gt 0 ] || usage; target_track="$1" ;;
    --first-sector) shift; [ "$#" -gt 0 ] || usage; first_sector="$1" ;;
    --second-sector) shift; [ "$#" -gt 0 ] || usage; second_sector="$1" ;;
    --dir-track) shift; [ "$#" -gt 0 ] || usage; dir_track="$1" ;;
    --dir-sector) shift; [ "$#" -gt 0 ] || usage; dir_sector="$1" ;;
    --dir-entry) shift; [ "$#" -gt 0 ] || usage; dir_entry="$1" ;;
    --generic-diff) diff_mode="generic" ;;
    --reserve-track) shift; [ "$#" -gt 0 ] || usage; reserve_track="$1" ;;
    --reserve-sector) shift; [ "$#" -gt 0 ] || usage; reserve_sector="$1"; [ -n "$reserve_track" ] || reserve_track="$target_track" ;;
    --load-ok) shift; [ "$#" -gt 0 ] || usage; load_ok="$1" ;;
    --load-fail) shift; [ "$#" -gt 0 ] || usage; load_fail="$1" ;;
    --run-form) shift; [ "$#" -gt 0 ] || usage; run_form="$1" ;;
    --run-expect) shift; [ "$#" -gt 0 ] || usage; run_expect="$1" ;;
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
case "$diff_mode" in fixed|generic) ;; *) echo "Fehler: Diff-Modus muss fixed oder generic sein" >&2; exit 2 ;; esac
case "$target_track" in ''|*[!0-9]*) echo "Fehler: --track muss numerisch sein" >&2; exit 2 ;; esac
case "$first_sector" in ''|*[!0-9]*) echo "Fehler: --first-sector muss numerisch sein" >&2; exit 2 ;; esac
case "$second_sector" in ''|*[!0-9]*) echo "Fehler: --second-sector muss numerisch sein" >&2; exit 2 ;; esac
case "$dir_track" in ''|*[!0-9]*) echo "Fehler: --dir-track muss numerisch sein" >&2; exit 2 ;; esac
case "$dir_sector" in ''|*[!0-9]*) echo "Fehler: --dir-sector muss numerisch sein" >&2; exit 2 ;; esac
case "$dir_entry" in ''|*[!0-9]*) echo "Fehler: --dir-entry muss numerisch sein" >&2; exit 2 ;; esac
if [ -n "$reserve_sector" ]; then
  [ -n "$reserve_track" ] || reserve_track="$target_track"
  case "$reserve_track" in ''|*[!0-9]*) echo "Fehler: Reserve-Track muss numerisch sein" >&2; exit 2 ;; esac
  case "$reserve_sector" in ''|*[!0-9]*) echo "Fehler: --reserve-sector muss numerisch sein" >&2; exit 2 ;; esac
fi

mkdir -p "$out_dir" "$(dirname "$before_d81")" "$(dirname "$after_d81")"

if [ "$build" = "1" ]; then
  echo "==> baue MVP-Ship und Save-New-Test-PRG"
  make mvp-ship hw-workbench-save-new-smoke-prg
fi

restore_workbench() {
  [ "$restore" = "1" ] || return 0
  [ "$restored" = "0" ] || return 0
  restored=1
  echo "==> stelle Workbench nach save-new-Smoke wieder her"
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
  echo "DRY-RUN: $c1541_bin $before_d81 -write $alloc_lisp $alloc_name,s"
  if [ -n "$reserve_sector" ]; then
    echo "DRY-RUN: python3 tools/host-lisp/d81_bam_reserve_sector.py $before_d81 --track $reserve_track --sector $reserve_sector"
  fi
  echo "DRY-RUN: rm -f $after_d81"
  if [ "$diff_mode" = "generic" ]; then
    echo "DRY-RUN: python3 tools/host-lisp/d81_save_new_diff.py --selftest $before_d81 --source $source_lisp --name $target_name --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
  else
    echo "DRY-RUN: python3 tools/host-lisp/d81_dir_write_diff.py --selftest $before_d81 --source $source_lisp --name $target_name --track $target_track --first-sector $first_sector --second-sector $second_sector --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
  fi
else
  [ -f "$ship_d81" ] || { echo "Fehler: Workbench-D81 fehlt: $ship_d81" >&2; exit 3; }
  [ -f "$prg" ] || { echo "Fehler: Save-New-PRG fehlt: $prg" >&2; exit 3; }
  [ -f "$source_lisp" ] || { echo "Fehler: M5-Quelle fehlt: $source_lisp" >&2; exit 3; }
  [ -f "$alloc_lisp" ] || { echo "Fehler: M5-Allocator fehlt: $alloc_lisp" >&2; exit 3; }
  command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 nicht gefunden: $c1541_bin" >&2; exit 3; }
  cp "$ship_d81" "$before_d81"
  "$c1541_bin" "$before_d81" -write "$alloc_lisp" "$alloc_name,s" >/tmp/lisp65-m5-c1541.log 2>&1 || {
    cat /tmp/lisp65-m5-c1541.log >&2
    exit 3
  }
  if [ -n "$reserve_sector" ]; then
    python3 tools/host-lisp/d81_bam_reserve_sector.py "$before_d81" \
      --track "$reserve_track" --sector "$reserve_sector"
  fi
  rm -f "$after_d81"
  if [ "$diff_mode" = "generic" ]; then
    python3 tools/host-lisp/d81_save_new_diff.py --selftest "$before_d81" \
      --source "$source_lisp" --name "$target_name" \
      --dir-track "$dir_track" --dir-sector "$dir_sector" --dir-entry "$dir_entry"
  else
    python3 tools/host-lisp/d81_dir_write_diff.py --selftest "$before_d81" \
      --source "$source_lisp" --name "$target_name" \
      --track "$target_track" --first-sector "$first_sector" \
      --second-sector "$second_sector" --dir-track "$dir_track" \
      --dir-sector "$dir_sector" --dir-entry "$dir_entry"
  fi
fi

upload_throwaway() {
  ftp="$tools_dir/mega65_ftp"
  if [ "$dry_run" != "1" ]; then
    [ -x "$ftp" ] || { echo "Fehler: $ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
  fi
  echo "==> lege save-new-Wegwerf-D81 auf die SD: $remote_d81"
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
  echo "==> starte Save-New-PRG (kein m65 -F)"
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
    if [ "$diff_mode" = "generic" ]; then
      echo "DRY-RUN: python3 tools/host-lisp/d81_save_new_diff.py $before_d81 $after_d81 --source $source_lisp --name $target_name --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
    else
      echo "DRY-RUN: python3 tools/host-lisp/d81_dir_write_diff.py $before_d81 $after_d81 --source $source_lisp --name $target_name --track $target_track --first-sector $first_sector --second-sector $second_sector --dir-track $dir_track --dir-sector $dir_sector --dir-entry $dir_entry"
    fi
  else
    if [ "$diff_mode" = "generic" ]; then
      python3 tools/host-lisp/d81_save_new_diff.py "$before_d81" "$after_d81" \
        --source "$source_lisp" --name "$target_name" \
        --dir-track "$dir_track" --dir-sector "$dir_sector" --dir-entry "$dir_entry"
    else
      python3 tools/host-lisp/d81_dir_write_diff.py "$before_d81" "$after_d81" \
        --source "$source_lisp" --name "$target_name" \
        --track "$target_track" --first-sector "$first_sector" \
        --second-sector "$second_sector" --dir-track "$dir_track" \
        --dir-sector "$dir_sector" --dir-entry "$dir_entry"
    fi
  fi
}

deploy_oracle_workbench() {
  set -- --no-build --tools "$tools_dir" --d81 "$after_d81" --remote-d81 "$remote_d81"
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run

  echo "==> deploye Workbench fuer save-new-Load-Oracle gegen $remote_d81"
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
if [ "$screen_status" != "0" ]; then
  echo "Fehler: sichtbarer Marker fehlt: $expect" >&2
  exit "$screen_status"
fi
fetch_after_image
verify_after_image

deploy_oracle_workbench
run_oracle_phase load-save-new "\"$load_ok\"" "(if (load \"$target_name\") \"$load_ok\" \"$load_fail\")"
run_oracle_phase run-save-new "$run_expect" "$run_form"

restore_armed=0
restore_workbench

echo "PASS Workbench save-new HW smoke"
