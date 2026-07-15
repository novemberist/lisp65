#!/bin/sh
# Reproducible read-only HW smoke for the Workbench D81 BAM path.
#
# Normal path:
#   deploy the MVP Workbench via etherload, then read both 1581 BAM sectors over
#   the Lisp REPL using %disk-read-sector/%disk-byte. No hard JTAG reset is used.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
deploy=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-bam-read}"
wait_sec="${WAIT_SEC:-1}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
form_wait_sec="${FORM_WAIT_SEC:-3}"
timeout_sec="${TIMEOUT_SEC:-20}"
deploy_timeout="${DEPLOY_TIMEOUT_SEC:-180}"
remote_d81="${MVP_VM_SHIP_REMOTE_D81:-L65WB.D81}"
source_d81="${MVP_VM_SHIP_D81:-build/ship-candidate/lisp65-mvp-workbench.d81}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run             print commands; no Etherload/JTAG side effects
  --no-build            reuse existing MVP Workbench ship artifacts
  --no-deploy           skip Workbench deploy; assume REPL is already running
  --ip <ipv6%iface>     MEGA65 target for etherload/ftp
  --tools <dir>         m65tools directory (default: $tools_dir)
  --device <dev>        JTAG serial device (default: $device)
  --out-dir <dir>       screenshot/text output directory (default: $out_dir)
  --prefix <name>       readback filename prefix (default: $prefix)
  --wait <seconds>      wait before each screenshot (default: $wait_sec)
  --boot-wait <seconds> wait after deploy before JTAG typing (default: $boot_wait_sec)
  --form-wait <seconds> wait after each REPL form (default: $form_wait_sec)
  --timeout <seconds>   timeout for each m65 command (default: $timeout_sec)
  --deploy-timeout <s>  timeout for the deploy wrapper (default: $deploy_timeout)
  --remote-d81 <name>   D81 name on the MEGA65 SD card (default: $remote_d81)
  -h|--help             this help
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-build) build=0 ;;
    --no-deploy) deploy=0 ;;
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

mkdir -p "$out_dir"

d81_byte() {
  offset=$1
  value=$(od -An -tu1 -j "$offset" -N 1 "$source_d81" | tr -d '[:space:]')
  case "$value" in
    ''|*[!0-9]*)
      echo "Fehler: D81-Orakelbyte bei Offset $offset nicht lesbar: $source_d81" >&2
      exit 2
      ;;
  esac
  printf '%s' "$value"
}

# The BAM-read oracle belongs to the exact test medium, not to an earlier D81
# layout.  Derive the four observed bytes from the same image that deploy_workbench
# uploads.  The native receipt later embeds and SHA-binds this image.
if [ ! -f "$source_d81" ]; then
  echo "Fehler: BAM-Read-Quellmedium fehlt: $source_d81" >&2
  exit 2
fi
bam_sector_1=$(( ((40 - 1) * 40 + 1) * 256 ))
bam_sector_2=$(( ((40 - 1) * 40 + 2) * 256 ))
bam_sector_1_expect="(t $(d81_byte "$bam_sector_1") $(d81_byte $((bam_sector_1 + 1))) $(d81_byte $((bam_sector_1 + 16))) $(d81_byte $((bam_sector_1 + 250))))"
bam_sector_2_expect="(t $(d81_byte "$bam_sector_2") $(d81_byte $((bam_sector_2 + 1))) $(d81_byte $((bam_sector_2 + 16))) $(d81_byte $((bam_sector_2 + 40))))"
echo "==> BAM-Read-Orakel aus gebundenem D81: S1 $bam_sector_1_expect; S2 $bam_sector_2_expect"

deploy_workbench() {
  set -- --tools "$tools_dir" --remote-d81 "$remote_d81"
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$build" = "0" ] && set -- "$@" --no-build
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run

  echo "==> deploye MVP-Workbench fuer BAM-Read-Smoke (kein m65 -F)"
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: timeout ${deploy_timeout}s sh scripts/hw-smoke-vm-stdlib.sh $*"
    sh scripts/hw-smoke-vm-stdlib.sh "$@"
  else
    timeout "${deploy_timeout}s" sh scripts/hw-smoke-vm-stdlib.sh "$@"
  fi
}

wait_for_repl() {
  if [ "$boot_wait_sec" -gt 0 ]; then
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: sleep $boot_wait_sec"
    else
      echo "==> warte ${boot_wait_sec}s auf REPL-Boot"
      sleep "$boot_wait_sec"
    fi
  fi
}

run_phase() {
  phase=$1
  expect=$2
  forms=$out_dir/$prefix-$phase.forms
  text=$out_dir/$prefix-$phase.txt
  shift 2

  : > "$forms"
  while [ "$#" -gt 0 ]; do
    printf '%s\n' "$1" >> "$forms"
    shift
  done

  set -- --file "$forms" --prefix "$prefix-$phase" --out-dir "$out_dir" \
    --tools "$tools_dir" --device "$device" --wait "$wait_sec" \
    --form-wait "$form_wait_sec" --timeout "$timeout_sec" --expect "$expect" \
    --verified-input
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run

  echo "==> JTAG-REPL-Phase: $phase"
  scripts/hw-jtag-repl.sh "$@"

  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: pruefe Marker '$expect' in $text"
  elif grep -F "$expect" "$text" >/dev/null; then
    echo "PASS $phase: $expect"
  else
    echo "Fehler: Marker fehlt in $text: $expect" >&2
    exit 4
  fi
}

if [ "$deploy" = "1" ]; then
  deploy_workbench
else
  echo "==> ueberspringe Deploy; bestehende REPL-Session wird verwendet"
fi

wait_for_repl

run_phase core-arith "42" \
  "(+ 20 22)"

run_phase bam-sector-1 "$bam_sector_1_expect" \
  "(list (%disk-read-sector 40 1) (%disk-byte 0) (%disk-byte 1) (%disk-byte 16) (%disk-byte 250))"

run_phase bam-sector-2 "$bam_sector_2_expect" \
  "(list (%disk-read-sector 40 2) (%disk-byte 0) (%disk-byte 1) (%disk-byte 16) (%disk-byte 40))"

echo "PASS Workbench BAM-read HW smoke"
