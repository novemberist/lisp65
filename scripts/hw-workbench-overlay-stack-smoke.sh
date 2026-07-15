#!/bin/sh
# Deploy and exercise the non-default Workbench full-boot overlay prototype.
#
# The combined EXT image contains the normal Workbench stdlib followed by the
# staged descriptor/payload at its manifest-bound address.  This wrapper never
# builds or substitutes artifacts: PRG, preload, ELF and D81 must be one known
# package set supplied below.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
deploy=1
upload_d81=1
readback=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
nm="${NM:-tools/llvm-mos/bin/llvm-nm}"
objcopy="${OBJCOPY:-tools/llvm-mos/bin/llvm-objcopy}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-overlay-stack}"
resident_prg="${WORKBENCH_OVERLAY_RESIDENT_PRG:-build/products/workbench/overlay-stack-probe/lisp65-workbench-resident.prg}"
preload="${WORKBENCH_OVERLAY_PRELOAD:-build/products/workbench/overlay-stack-probe/stdlib-with-overlay.ext.bin}"
preload_addr="${WORKBENCH_OVERLAY_PRELOAD_ADDR:-0x050000}"
runtime_overlay="${WORKBENCH_RUNTIME_OVERLAY:-build/products/workbench/overlay-stack-probe/lisp65-mvp-workbench.overlays.bin}"
runtime_overlay_addr="${WORKBENCH_RUNTIME_OVERLAY_ADDR:-0x08000000}"
elf="${WORKBENCH_OVERLAY_ELF:-build/products/workbench/overlay-stack-probe/lisp65-workbench-overlay-linked.prg.elf}"
d81="${WORKBENCH_OVERLAY_D81:-build/ship/lisp65-mvp-workbench.d81}"
remote_d81="${WORKBENCH_OVERLAY_REMOTE_D81:-L65OVL.D81}"
readback_script="${WORKBENCH_OVERLAY_READBACK_SCRIPT:-scripts/hw-stack-probe-readback.py}"
ship_manifest="${WORKBENCH_SHIP_MANIFEST:-}"
ship_readback_script="${WORKBENCH_SHIP_READBACK_SCRIPT:-scripts/hw-ship-memory-readback.py}"
min_soft_margin="${MIN_SOFT_MARGIN:-256}"
min_hw_remaining="${MIN_HW_REMAINING:-32}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
boot_ready_timeout_sec="${BOOT_READY_TIMEOUT_SEC:-60}"
wait_sec="${WAIT_SEC:-1}"
form_wait_sec="${FORM_WAIT_SEC:-3}"
load_ide_budget_sec="${LOAD_IDE_BUDGET_SEC:-12}"
timeout_sec="${TIMEOUT_SEC:-20}"
deploy_timeout_sec="${DEPLOY_TIMEOUT_SEC:-180}"
readback_timeout_sec="${READBACK_TIMEOUT_SEC:-120}"

usage() {
  cat >&2 <<EOF
usage: $0 [options]
  --dry-run                 print the complete workflow; do not touch hardware
  --no-deploy               reuse an already running overlay Workbench
  --no-d81-upload           assume the remote D81 is already present
  --no-readback             skip boot/post-IDE stack readback for the
                            non-instrumented guard-only variant
  --resident-prg <file>     truncated resident PRG (default: $resident_prg)
  --preload <file>          combined stdlib + staged overlay EXT image
  --preload-addr <address>  EXT preload address (default: $preload_addr)
  --runtime-overlay <file>  immutable runtime-overlay catalog
  --runtime-overlay-addr <address>
                            catalog address (default: $runtime_overlay_addr)
  --elf <file>              final linked overlay ELF for probes/island binding
  --d81 <file>              local Workbench/IDE D81 (default: $d81)
  --remote-d81 <name>       D81 filename on MEGA65 SD (default: $remote_d81)
  --readback-script <file>  stack-probe decoder (default: $readback_script)
  --ship-manifest <file>    enable mandatory Ship-v5 memory/reset/remount proof
  --ship-readback-script <file>
                            Ship-v5 SHA readback helper (default: $ship_readback_script)
  --min-soft-margin <n>     required soft-stack margin (default: $min_soft_margin)
  --min-hw-remaining <n>    required hardware-stack remainder (default: $min_hw_remaining)
  --ip <ipv6%iface>         explicit MEGA65 network target
  --tools <dir>             m65tools directory (default: $tools_dir)
  --device <dev>            JTAG serial device (default: $device)
  --nm <file>               llvm-nm used by readback (default: $nm)
  --objcopy <file>          llvm-objcopy used by island readback (default: $objcopy)
  --out-dir <dir>           reports/screenshots directory (default: $out_dir)
  --prefix <name>           output prefix (default: $prefix)
  --boot-wait <seconds>     wait for REPL after deploy (default: $boot_wait_sec)
  --boot-ready-timeout <s>  maximum Ship-v5 island-canary wait (default: $boot_ready_timeout_sec)
  --wait <seconds>          wait before phase screenshots (default: $wait_sec)
  --form-wait <seconds>     wait after each REPL form (default: $form_wait_sec)
  --load-ide-budget <sec>   maximum load-lib IDE wall time (default: $load_ide_budget_sec)
  --timeout <seconds>       timeout for each JTAG command (default: $timeout_sec)
  --deploy-timeout <sec>    timeout for deploy wrapper (default: $deploy_timeout_sec)
  --readback-timeout <sec>  timeout for stack readback (default: $readback_timeout_sec)
  -h|--help                 show this help
EOF
  exit 2
}

need_value() {
  [ "$#" -gt 0 ] || usage
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-deploy) deploy=0 ;;
    --no-d81-upload) upload_d81=0 ;;
    --no-readback) readback=0 ;;
    --resident-prg) shift; need_value "$@"; resident_prg=$1 ;;
    --preload) shift; need_value "$@"; preload=$1 ;;
    --preload-addr) shift; need_value "$@"; preload_addr=$1 ;;
    --runtime-overlay) shift; need_value "$@"; runtime_overlay=$1 ;;
    --runtime-overlay-addr) shift; need_value "$@"; runtime_overlay_addr=$1 ;;
    --elf) shift; need_value "$@"; elf=$1 ;;
    --d81) shift; need_value "$@"; d81=$1 ;;
    --remote-d81) shift; need_value "$@"; remote_d81=$1 ;;
    --readback-script) shift; need_value "$@"; readback_script=$1 ;;
    --ship-manifest) shift; need_value "$@"; ship_manifest=$1 ;;
    --ship-readback-script) shift; need_value "$@"; ship_readback_script=$1 ;;
    --min-soft-margin) shift; need_value "$@"; min_soft_margin=$1 ;;
    --min-hw-remaining) shift; need_value "$@"; min_hw_remaining=$1 ;;
    --ip) shift; need_value "$@"; ip=$1 ;;
    --tools) shift; need_value "$@"; tools_dir=$1 ;;
    --device) shift; need_value "$@"; device=$1 ;;
    --nm) shift; need_value "$@"; nm=$1 ;;
    --objcopy) shift; need_value "$@"; objcopy=$1 ;;
    --out-dir) shift; need_value "$@"; out_dir=$1 ;;
    --prefix) shift; need_value "$@"; prefix=$1 ;;
    --boot-wait) shift; need_value "$@"; boot_wait_sec=$1 ;;
    --boot-ready-timeout) shift; need_value "$@"; boot_ready_timeout_sec=$1 ;;
    --wait) shift; need_value "$@"; wait_sec=$1 ;;
    --form-wait) shift; need_value "$@"; form_wait_sec=$1 ;;
    --load-ide-budget) shift; need_value "$@"; load_ide_budget_sec=$1 ;;
    --timeout) shift; need_value "$@"; timeout_sec=$1 ;;
    --deploy-timeout) shift; need_value "$@"; deploy_timeout_sec=$1 ;;
    --readback-timeout) shift; need_value "$@"; readback_timeout_sec=$1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

for numeric in \
  "$min_soft_margin" "$min_hw_remaining" "$boot_wait_sec" "$wait_sec" \
  "$boot_ready_timeout_sec" "$form_wait_sec" "$timeout_sec" "$deploy_timeout_sec" \
  "$readback_timeout_sec" "$load_ide_budget_sec"
do
  case "$numeric" in
    ''|*[!0-9]*) echo "Fehler: numerische Option erwartet, erhalten: $numeric" >&2; exit 2 ;;
  esac
done

[ -n "$remote_d81" ] || { echo "Fehler: --remote-d81 darf nicht leer sein" >&2; exit 2; }
case "$remote_d81" in
  */*) echo "error: --remote-d81 must be an SD filename without a path" >&2; exit 2 ;;
esac
if [ -n "$ship_manifest" ] && [ "$deploy" != "1" ]; then
  echo "Fehler: --ship-manifest erfordert den vollstaendigen zweistufigen Deploy" >&2
  exit 2
fi
if [ -n "$ship_manifest" ]; then
  if [ "$upload_d81" != "1" ]; then
    echo "Fehler: --ship-manifest erlaubt kein --no-d81-upload" >&2
    exit 2
  fi
  if [ "$preload_addr" != "0x050000" ]; then
    echo "Fehler: Ship-v5 Bank-5-Ziel muss 0x050000 sein: $preload_addr" >&2
    exit 2
  fi
  if [ "$runtime_overlay_addr" != "0x08000000" ]; then
    echo "Fehler: Ship-v5 Attic-Ziel muss 0x08000000 sein: $runtime_overlay_addr" >&2
    exit 2
  fi
  for artifact in "$resident_prg" "$preload" "$runtime_overlay"; do
    case "$artifact" in
      *@*) echo "error: G5 staging path must not contain @: $artifact" >&2; exit 2 ;;
    esac
  done
fi

echo "==> Workbench-Overlay-Artefaktvertrag"
printf '    resident_prg=%s\n' "$resident_prg"
printf '    preload=%s@%s\n' "$preload" "$preload_addr"
printf '    runtime_overlay=%s@%s\n' "$runtime_overlay" "$runtime_overlay_addr"
printf '    elf=%s\n' "$elf"
printf '    d81=%s -> %s\n' "$d81" "$remote_d81"
if [ -n "$ship_manifest" ]; then
  printf '    ship_v5_memory=%s via %s island=%s:$1800\n' \
    "$ship_manifest" "$ship_readback_script" "$elf"
else
  printf '    ship_v5_memory=disabled (diagnostic/non-Ship flow)\n'
fi
if [ "$readback" = "1" ]; then
  printf '    readback=%s soft_margin>=%s hw_remaining>=%s\n' \
    "$readback_script" "$min_soft_margin" "$min_hw_remaining"
else
  printf '    readback=skipped (guard-only variant has no LISP65_BOOT_STACK_PROBE canaries)\n'
fi

if [ "$dry_run" != "1" ]; then
  for artifact in "$resident_prg" "$preload" "$runtime_overlay" "$d81"; do
    [ -f "$artifact" ] || { echo "Fehler: Artefakt fehlt: $artifact" >&2; exit 3; }
  done
  if [ "$readback" = "1" ]; then
    [ -f "$elf" ] || { echo "Fehler: Artefakt fehlt: $elf" >&2; exit 3; }
    [ -f "$readback_script" ] || { echo "Fehler: Artefakt fehlt: $readback_script" >&2; exit 3; }
  fi
  if [ -n "$ship_manifest" ]; then
    [ -f "$ship_manifest" ] || { echo "Fehler: Ship-Manifest fehlt: $ship_manifest" >&2; exit 3; }
    [ -f "$ship_readback_script" ] || { echo "Fehler: Ship-Readback fehlt: $ship_readback_script" >&2; exit 3; }
    [ -f "$elf" ] || { echo "Fehler: manifestgebundenes Insel-ELF fehlt: $elf" >&2; exit 3; }
  fi
  [ -x "$tools_dir/mega65_ftp" ] || { echo "Fehler: $tools_dir/mega65_ftp fehlt" >&2; exit 3; }
  [ -x "$tools_dir/etherload" ] || { echo "Fehler: $tools_dir/etherload fehlt" >&2; exit 3; }
  [ -x "$tools_dir/m65" ] || { echo "Fehler: $tools_dir/m65 fehlt" >&2; exit 3; }
  if [ "$readback" = "1" ]; then
    [ -x "$nm" ] || { echo "Fehler: llvm-nm fehlt: $nm" >&2; exit 3; }
  fi
  if [ -n "$ship_manifest" ]; then
    [ -x "$nm" ] || { echo "Fehler: llvm-nm fuer Insel-Canary fehlt: $nm" >&2; exit 3; }
    [ -x "$objcopy" ] || { echo "Fehler: llvm-objcopy fuer Insel-Canary fehlt: $objcopy" >&2; exit 3; }
  fi
fi

mkdir -p "$out_dir"

if [ "$deploy" = "1" ]; then
  if [ "$upload_d81" = "1" ]; then
    set -- -e -y
    [ -n "$ip" ] && set -- "$@" -i "$ip"
    set -- "$@" -c "put $d81 $remote_d81" -c exit
    echo "==> D81 auf die MEGA65-SD uebertragen"
    if [ "$dry_run" = "1" ]; then
      printf 'DRY-RUN: %s' "$tools_dir/mega65_ftp"
      for argument in "$@"; do printf ' %s' "$argument"; done
      printf '\n'
    else
      timeout "${deploy_timeout_sec}s" "$tools_dir/mega65_ftp" "$@"
    fi
  else
    echo "==> D81-Upload uebersprungen; verwende $remote_d81 auf SD"
  fi

  if [ -n "$ship_manifest" ]; then
    echo "==> G5 Stage A: Attic und Bank 5 per JTAG laden, Resident-PRG ungelaufen halten"
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -H -@ $runtime_overlay@$runtime_overlay_addr"
      echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -H -@ $preload@$preload_addr"
      echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -H -1 $resident_prg"
    else
      timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -H \
        -@ "$runtime_overlay@$runtime_overlay_addr"
      timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -H \
        -@ "$preload@$preload_addr"
      timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -H -1 "$resident_prg"
    fi
  else
    set -- --tools "$tools_dir" --mount "$remote_d81" \
      --preload-bin "$runtime_overlay_addr" "$runtime_overlay" \
      --preload-bin "$preload_addr" "$preload" --run
    [ -n "$ip" ] && set -- "$@" --ip "$ip"
    [ "$dry_run" = "1" ] && set -- "$@" --dry-run
    set -- "$@" "$resident_prg"
    echo "==> Attic-Katalog und Bank-5-Image preloaden, dann Resident-PRG starten"
    if [ "$dry_run" = "1" ]; then
      sh scripts/run-on-mega65.sh "$@"
    else
      timeout "${deploy_timeout_sec}s" sh scripts/run-on-mega65.sh "$@"
    fi
  fi
else
  echo "==> Deploy uebersprungen; bestehende Overlay-Workbench wird verwendet"
fi

if [ -z "$ship_manifest" ] && [ "$boot_wait_sec" -gt 0 ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: sleep $boot_wait_sec"
  else
    echo "==> warte ${boot_wait_sec}s auf Overlay-Boot und REPL"
    sleep "$boot_wait_sec"
  fi
fi

run_ship_readback() {
  phase=$1
  set -- python3 "$ship_readback_script" \
    --manifest "$ship_manifest" --prg "$resident_prg" --bank5 "$preload" \
    --attic "$runtime_overlay" --d81 "$d81" --elf "$elf" \
    --nm "$nm" --objcopy "$objcopy" --phase "$phase" \
    --device "$device" --tools "$tools_dir" --out-dir "$out_dir" \
    --prefix "$prefix-ship-$phase" \
    --receipt "$out_dir/$prefix-ship-manifest-receipt.json"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  if [ "$dry_run" = "1" ]; then
    "$@"
  else
    timeout "${readback_timeout_sec}s" "$@"
  fi
}

wait_for_ship_boot_ready() {
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: poll manifest-bound island canary for up to ${boot_ready_timeout_sec}s"
    run_ship_readback post-reset
    return
  fi

  deadline=$(( $(date +%s) + boot_ready_timeout_sec ))
  attempt=1
  while :; do
    echo "==> G5 Boot-Ready-Probe $attempt: Attic-SHA und Insel-Canary"
    if run_ship_readback post-reset; then
      return
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "Fehler: manifestgebundene Insel nach ${boot_ready_timeout_sec}s nicht bootbereit" >&2
      return 1
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
}

if [ -n "$ship_manifest" ]; then
  echo "==> G5 Stage A SHA: ungelaufener PRG-Payload, Bank 5 und Attic"
  run_ship_readback staged

  set -- --tools "$tools_dir" --mount "$remote_d81" --run
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  set -- "$@" "$resident_prg"
  echo "==> G5 Stage B: kanonischer Etherload-Reset, Remount und PRG-Reload/Run"
  if [ "$dry_run" = "1" ]; then
    sh scripts/run-on-mega65.sh "$@"
  else
    timeout "${deploy_timeout_sec}s" sh scripts/run-on-mega65.sh "$@"
  fi
  if [ "$boot_wait_sec" -gt 0 ]; then
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: sleep $boot_wait_sec"
    else
      echo "==> warte ${boot_wait_sec}s auf REPL nach G5-Remount"
      sleep "$boot_wait_sec"
    fi
  fi
  echo "==> G5 Stage B Attic-SHA und Insel-Canary nach Reset und Produktboot"
  wait_for_ship_boot_ready
fi

run_stack_readback() {
  label=$1
  suffix=$2
  if [ "$readback" != "1" ]; then
    echo "==> $label uebersprungen (--no-readback: Guard-ELF hat keine LISP65_BOOT_STACK_PROBE-Canaries)"
    return
  fi
  set -- python3 "$readback_script" --elf "$elf" --device "$device" \
    --tools "$tools_dir" --nm "$nm" --out-dir "$out_dir" \
    --prefix "$prefix-$suffix" --min-soft-margin "$min_soft_margin" \
    --min-hw-remaining "$min_hw_remaining"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  echo "==> $label"
  if [ "$dry_run" = "1" ]; then
    "$@"
  else
    timeout "${readback_timeout_sec}s" "$@"
  fi
}

run_stack_readback "Runtime-Stack/Wipe-Readback" "stack"

run_phase() {
  phase=$1
  expect=$2
  phase_wait=$wait_sec
  phase_poll=0
  shift 2
  case "$phase" in
    load-ide) phase_wait=0; phase_poll=$load_ide_budget_sec ;;
    vm-bridges|gc-allocation) phase_wait=12 ;;
  esac
  forms="$out_dir/$prefix-$phase.forms"
  : > "$forms"
  while [ "$#" -gt 0 ]; do
    printf '%s\n' "$1" >> "$forms"
    shift
  done

  set -- --file "$forms" --expect "$expect" --tools "$tools_dir" \
    --device "$device" --out-dir "$out_dir" --prefix "$prefix-$phase" \
    --wait "$phase_wait" --form-wait "$form_wait_sec" --timeout "$timeout_sec" \
    --verified-input
  [ "$phase_poll" -eq 0 ] || set -- "$@" --expect-poll "$phase_poll"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  echo "==> JTAG-REPL-Probe: $phase"
  sh scripts/hw-jtag-repl.sh "$@"
}

run_phase arith-42 '"overlay-arith-42"' \
  "(+ 20 22)" \
  "(if (= (+ 20 22) 42) \"overlay-arith-42\" \"overlay-arith-fail\")"

run_phase load-ide '"overlay-ide-ok"' \
  "(if (load-lib \"ide\") \"overlay-ide-ok\" \"overlay-ide-fail\")"

run_stack_readback "Post-IDE-Stack/Wipe-Readback" "stack-post-ide"

run_phase compile-kind '"overlay-kind-bytecode"' \
  "(if (eq (function-kind (quote compile-buffer-to-lib)) (quote bytecode)) \"overlay-kind-bytecode\" \"overlay-kind-fail\")"

run_phase vm-bridges '"overlay-vm-bridges-ok"' \
  "(defun ovtw (x) (+ x 1))" \
  "(lcc-run (quote (defun ovc (x) (ovtw x))))" \
  "(lcc-run (quote (defun ovf (f x) (funcall f x))))" \
  "(if (and (= (ovc 41) 42) (= (ovf (function ovtw) 41) 42)) \"overlay-vm-bridges-ok\" \"overlay-vm-bridges-fail\")"

run_phase gc-allocation '"overlay-gc-42"' \
  "(progn (dotimes (i 400) (list i i i i)) 42)" \
  "(if (= (+ 20 22) 42) \"overlay-gc-42\" \"overlay-gc-fail\")"

run_phase reader-recovery '"overlay-reader-recovered-42"' \
  ")" \
  "(+ 20 22)" \
  "(if (= (+ 20 22) 42) \"overlay-reader-recovered-42\" \"overlay-reader-fail\")"

echo "PASS Workbench overlay stack HW smoke"
