#!/bin/sh
# Reproducible HW smoke for the interactive Workbench UX paths.
#
# Normal path:
#   build/deploy MVP Workbench via etherload, then drive short REPL forms over
#   JTAG using scripts/hw-jtag-repl.sh. No hard JTAG reset is used.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
build=1
deploy=1
ip="${MEGA65_IP:-}"
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-workbench-ux}"
wait_sec="${WAIT_SEC:-1}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
form_wait_sec="${FORM_WAIT_SEC:-3}"
higher_order_io_wait_sec="${HIGHER_ORDER_IO_WAIT_SEC:-12}"
timeout_sec="${TIMEOUT_SEC:-20}"
deploy_timeout="${DEPLOY_TIMEOUT_SEC:-180}"
remote_d81="${MVP_VM_SHIP_REMOTE_D81:-L65WB.D81}"
ship_prg="${MVP_VM_SHIP_PRG:-build/ship/lisp65-mvp-workbench.prg}"
ship_blob="${MVP_VM_SHIP_BLOB:-build/ship/lisp65-mvp-workbench.blob.bin}"
ship_overlays="${MVP_VM_SHIP_OVERLAYS:-build/ship/lisp65-mvp-workbench.overlays.bin}"
jtag_repl_runner="${JTAG_REPL_RUNNER:-scripts/hw-jtag-repl.sh}"
bootstrap_retry_wait_sec="${JTAG_BOOTSTRAP_RETRY_WAIT_SEC:-2}"
jtag_input_retry_wait_sec="${JTAG_INPUT_RETRY_WAIT_SEC:-0.2}"
core_nonce="${UX_CORE_NONCE:-ux-core-$$}"
bootstrap_only=0

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
  --bootstrap-retry-wait <seconds>
                        wait before a sentinel retry (default: $bootstrap_retry_wait_sec)
  --input-retry-wait <seconds>
                        wait around verified-input retries
                        (default: $jtag_input_retry_wait_sec)
  --bootstrap-only      stop after the transport sentinel
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
    --bootstrap-retry-wait) shift; [ "$#" -gt 0 ] || usage; bootstrap_retry_wait_sec="$1" ;;
    --input-retry-wait) shift; [ "$#" -gt 0 ] || usage; jtag_input_retry_wait_sec="$1" ;;
    --bootstrap-only) bootstrap_only=1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) echo "unerwartetes Argument: $1" >&2; usage ;;
  esac
  shift
done

case "$wait_sec" in ''|*[!0-9]*) echo "Fehler: --wait muss numerisch sein" >&2; exit 2 ;; esac
case "$boot_wait_sec" in ''|*[!0-9]*) echo "Fehler: --boot-wait muss numerisch sein" >&2; exit 2 ;; esac
case "$form_wait_sec" in ''|*[!0-9]*) echo "Fehler: --form-wait muss numerisch sein" >&2; exit 2 ;; esac
case "$higher_order_io_wait_sec" in ''|*[!0-9]*) echo "Fehler: HIGHER_ORDER_IO_WAIT_SEC muss numerisch sein" >&2; exit 2 ;; esac
case "$timeout_sec" in ''|*[!0-9]*) echo "Fehler: --timeout muss numerisch sein" >&2; exit 2 ;; esac
case "$deploy_timeout" in ''|*[!0-9]*) echo "Fehler: --deploy-timeout muss numerisch sein" >&2; exit 2 ;; esac
case "$bootstrap_retry_wait_sec" in ''|*[!0-9]*) echo "Fehler: --bootstrap-retry-wait muss numerisch sein" >&2; exit 2 ;; esac
case "$jtag_input_retry_wait_sec" in ''|.*|*.|*.*.*|*[!0-9.]*) echo "Fehler: --input-retry-wait muss eine nichtnegative Dezimalzahl sein" >&2; exit 2 ;; esac
case "$core_nonce" in ''|*[!A-Za-z0-9._-]*) echo "Fehler: UX_CORE_NONCE enthaelt unsichere Zeichen" >&2; exit 2 ;; esac
[ "$timeout_sec" -gt 0 ] || { echo "Fehler: --timeout muss groesser als 0 sein" >&2; exit 2; }
[ "$deploy_timeout" -gt 0 ] || { echo "Fehler: --deploy-timeout muss groesser als 0 sein" >&2; exit 2; }

mkdir -p "$out_dir"

deploy_workbench() {
  force_no_build=$1
  set -- --tools "$tools_dir" --remote-d81 "$remote_d81"
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  if [ "$build" = "0" ] || [ "$force_no_build" = "1" ]; then
    set -- "$@" --no-build
  fi
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run

  echo "==> deploye MVP-Workbench fuer UX-Smoke (kein m65 -F)"
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

if [ "$deploy" = "1" ]; then
  deploy_workbench 0
else
  echo "==> ueberspringe Deploy; bestehende REPL-Session wird verwendet"
fi

wait_for_repl

run_phase() {
  phase=$1
  expect=$2
  forms=$out_dir/$prefix-$phase.forms
  phase_wait_sec=$wait_sec
  max_attempts=1
  shift 2

  case "$phase" in
    core-load|extra-load|eval-core-load|eval-extra-load|persistence-reset-core-load|post-persistence-core-load) phase_wait_sec="${IDE_LOAD_WAIT_SEC:-12}" ;;
    directory-open|persistence-reset-read) phase_wait_sec="${LOAD_WAIT_SEC:-12}" ;;
    persistence-create|persistence-create-second|persistence-replace) phase_wait_sec="${SAVE_WAIT_SEC:-20}" ;;
    persistence-remount) phase_wait_sec="${REMOUNT_WAIT_SEC:-20}" ;;
    eval-buffer|mx-eval-buffer) phase_wait_sec="${EVAL_WAIT_SEC:-12}" ;;
  esac

  if [ "$phase" = "core-arith" ]; then
    max_attempts=2
  fi

  : > "$forms"
  while [ "$#" -gt 0 ]; do
    printf '%s\n' "$1" >> "$forms"
    shift
  done

  form_count=$(wc -l < "$forms")
  attempt=1
  while [ "$attempt" -le "$max_attempts" ]; do
    retry_phase=0
    form_number=0
    while IFS= read -r current_form || [ -n "$current_form" ]; do
      form_number=$((form_number + 1))
      final_form=0
      capture_wait=0
      current_form_wait_sec=$form_wait_sec
      attempt_prefix="$prefix-$phase-form-$form_number"
      case "$phase" in
        higher-order-*)
          case "$current_form" in
            "(save-buffer-to "*|"(load "*) current_form_wait_sec=$higher_order_io_wait_sec ;;
          esac
          ;;
      esac
      if [ "$form_number" -eq "$form_count" ]; then
        final_form=1
        capture_wait=$phase_wait_sec
        attempt_prefix="$prefix-$phase"
        if [ "$attempt" -gt 1 ]; then
          attempt_prefix="$prefix-$phase-attempt-$attempt"
        fi
      fi
      text=$out_dir/$attempt_prefix.txt

      set -- --form "$current_form" --prefix "$attempt_prefix" --out-dir "$out_dir" \
        --tools "$tools_dir" --device "$device" --wait "$capture_wait" \
        --form-wait "$current_form_wait_sec" --timeout "$timeout_sec" \
        --input-retry-wait "$jtag_input_retry_wait_sec" --verified-input
      [ "$dry_run" = "1" ] && set -- "$@" --dry-run

      echo "==> JTAG-REPL-Phase: $phase form $form_number/$form_count (attempt $attempt/$max_attempts)"
      runner_status=0
      if "$jtag_repl_runner" "$@"; then
        :
      else
        runner_status=$?
      fi

      if [ "$dry_run" = "1" ]; then
        continue
      fi
      if [ "$runner_status" -ne 0 ]; then
        case "$runner_status" in
          5|6|124)
            echo "R5_HARNESS_RESULT=FAIL kind=verified-input-or-capture phase=$phase status=$runner_status" >&2
            ;;
        esac
        return "$runner_status"
      fi

      set -- --screen "$text" --form-text "$current_form"
      if [ "$final_form" -eq 1 ]; then
        set -- "$@" --expect "$expect"
      else
        set -- "$@" --echo-only
      fi
      check_status=0
      if python3 tools/host-lisp/repl_screen_check.py "$@"; then
        :
      else
        check_status=$?
      fi

      if [ "$check_status" -eq 0 ]; then
        continue
      fi

      if [ "$phase" = "core-arith" ] && [ "$check_status" -eq 5 ] \
          && [ "$attempt" -lt "$max_attempts" ]; then
        echo "WARNUNG: JTAG-Transportecho weicht ab; idempotenter Sentinel wird wiederholt" >&2
        if [ "$bootstrap_retry_wait_sec" -gt 0 ]; then
          sleep "$bootstrap_retry_wait_sec"
        fi
        retry_phase=1
        break
      fi
      return "$check_status"
    done < "$forms"

    if [ "$retry_phase" -eq 1 ]; then
      attempt=$((attempt + 1))
      continue
    fi

    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: pruefe letztes Resultat '$expect' fuer Phase $phase"
    elif [ "$attempt" -gt 1 ]; then
      echo "PASS $phase after transport retry (attempt $attempt/$max_attempts): $expect"
    else
      echo "PASS $phase: $expect"
    fi
    return 0
  done

  return 4
}

# R5 harness helpers deliberately use only the public IDE surface. Directory-only
# functions have no runtime symbol by contract, so a hardware fixture must never
# call their source names directly. Reinstall these helpers after every deploy,
# because they belong to the REPL session/test closure rather than the product.
install_r5_harness_helpers() {
  run_phase r5-harness-helpers '"r5-harness-ok"' \
    '(defun r5-hw-store-buffer (buf) (progn (set-symbol-value (quote *ide-buffers*) (cons (cons (ide-buffer-name buf) buf) (symbol-value (quote *ide-buffers*)))) (quote t)))' \
    '(defun r5-hw-find-buffer (name alist) (if alist (if (string= name (car (car alist))) (cdr (car alist)) (r5-hw-find-buffer name (cdr alist))) nil))' \
    '(defun r5-hw-resume-buffer (name) ((lambda (found) (if found found (ide-make-buffer name (list "")))) (r5-hw-find-buffer name (symbol-value (quote *ide-buffers*)))))' \
    '(defun r5-hw-set-rows (state rows) (progn (rplaca (cdr (cdr (cdr (cdr (cdr (cdr state)))))) rows) state))' \
    '"r5-harness-ok"'
}

run_phase core-arith "(42 \"$core_nonce\")" \
  "(list (+ 20 22) \"$core_nonce\")"

if [ "$bootstrap_only" = "1" ]; then
  echo "PASS Workbench UX bootstrap sentinel"
  exit 0
fi

run_phase core-load "\"ide-load-ok\"" \
  "(if (load-lib \"ide\") \"ide-load-ok\" \"ide-load-fail\")"

install_r5_harness_helpers

run_phase core-kind "bytecode" \
  "(function-kind (quote compile-buffer-to-lib))"

run_phase persistence-create "(t nil bytecode)" \
  "(set-symbol-value (quote *ide-buffers*) nil)" \
  "(r5-hw-store-buffer (ide-make-buffer \"ap6src\" (list \"(defun ap6-persisted () 611)\")))" \
  "(list (save-buffer-to \"ap6src\" \"ap6src\") (ide-error) (function-kind (quote m65d-save)))"

run_phase persistence-read "(\"(defun ap6-persisted () 611)\")" \
  "(load-file-to-buffer \"ap6src\" \"ap6copy\")" \
  "(ide-buffer-lines (r5-hw-resume-buffer \"ap6copy\"))"

run_phase persistence-create-second "(t (\"(defun ap6-b () 613)\"))" \
  "(r5-hw-store-buffer (ide-make-buffer \"z6src\" (list \"(defun ap6-b () 613)\")))" \
  "(setq x (save-buffer-to \"z6src\" \"z6src\"))" \
  "(load-file-to-buffer \"z6src\" \"z6copy\")" \
  "(list x (ide-buffer-lines (r5-hw-resume-buffer \"z6copy\")))"

run_phase persistence-replace "(t (\"(defun ap6-persisted () 612)\"))" \
  "(r5-hw-store-buffer (ide-make-buffer \"ap6src\" (list \"(defun ap6-persisted () 612)\")))" \
  "(setq x (save-buffer-to \"ap6src\" \"ap6src\"))" \
  "(load-file-to-buffer \"ap6src\" \"ap6copy\")" \
  "(list x (ide-buffer-lines (r5-hw-resume-buffer \"ap6copy\")))"

run_phase persistence-remount "0" \
  "(m65d-remount)"

run_phase higher-order-remount-every "t" \
  '(setq x "(every (function plusp) ")' \
  '(setq x (string-append x (char->string 39) "(1 2 3))"))' \
  '(r5-hw-store-buffer (ide-make-buffer "h8e" (list x (string-append "(setq x " x ")"))))' \
  '(save-buffer-to "h8e" "h8e")' \
  '(load "h8e")' \
  '(load "h8e")' \
  'x'

run_phase higher-order-remount-some "3" \
  '(setq x "(some (function (lambda (x) (if (> x 2) x nil))) ")' \
  '(setq x (string-append x (char->string 39) "(1 2 3))"))' \
  '(r5-hw-store-buffer (ide-make-buffer "h8s" (list x (string-append "(setq x " x ")"))))' \
  '(save-buffer-to "h8s" "h8s")' \
  '(load "h8s")' \
  '(load "h8s")' \
  'x'

if [ "$deploy" = "1" ]; then
  set -- --tools "$tools_dir" --mount "$remote_d81" \
    --preload-bin 0x08000000 "$ship_overlays" \
    --preload-bin 0x050000 "$ship_blob" --run
  [ -n "$ip" ] && set -- "$@" --ip "$ip"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  set -- "$@" "$ship_prg"
  echo "==> Reset/Remount ohne D81-Reupload fuer AP6-Persistenz"
  sh scripts/run-on-mega65.sh "$@"
  wait_for_repl
  run_phase persistence-reset-sentinel '"ap6-reset-ok"' \
    '"ap6-reset-ok"'
  run_phase persistence-reset-core-load '"ide-load-ok"' \
    '(if (load-lib "ide") "ide-load-ok" "ide-load-fail")'
  install_r5_harness_helpers
  run_phase persistence-reset-read "((\"(defun ap6-persisted () 612)\") 612 (\"(defun ap6-b () 613)\") 613)" \
    "(load-file-to-buffer \"ap6src\" \"ap6copy\")" \
    "(load-file-to-buffer \"z6src\" \"z6copy\")" \
    "(load \"ap6src\")" \
    "(load \"z6src\")" \
    "(list (ide-buffer-lines (r5-hw-resume-buffer \"ap6copy\")) (ap6-persisted) (ide-buffer-lines (r5-hw-resume-buffer \"z6copy\")) (ap6-b))"

  echo "==> restauriere unveraenderte Ship-D81 fuer die restliche UX-Matrix"
  deploy_workbench 1
  wait_for_repl
  run_phase post-persistence-core-load '"ide-load-ok"' \
    '(if (load-lib "ide") "ide-load-ok" "ide-load-fail")'
  install_r5_harness_helpers
fi

run_phase extra-load "\"idex-load-ok\"" \
  "(if (load-lib \"idex\") \"idex-load-ok\" \"idex-load-fail\")"

run_phase idex-hook-override "\"idex-hook-overridden\"" \
  '(setq x (ide-make-state (ide-make-buffer "scratch" (list ""))))' \
  '(setq x (%ide-x (quote motion) x 1013 nil))' \
  '(if (eq (ide-state-message x) 1005) "idex-hook-overridden" "hook not overridden")'

run_phase mx-command "\"M-x {find-file}\"" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 120 nil)))" \
  "((lambda (line) (progn (setq x (ide-step x (list (quote key) 7 nil))) line)) (ide-status-line x 80))"

run_phase directory "\"*directory*\"" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 4 nil)))" \
  "(ide-buffer-name (car x))"

run_phase directory-open "\"loaded\"" \
  "(progn (setq x (ide-make-state (ide-make-buffer \"*directory*\" (list \"demo\")))) nil)" \
  "(car (cdr (setq x (ide-step x (list (quote key) 13 nil)))))"

run_phase reject-fasl-open "\"not source\"" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 6 nil)))" \
  "(setq x (ide-step x (list (quote key) 102 nil)))" \
  "(setq x (ide-step x (list (quote key) 97 nil)))" \
  "(setq x (ide-step x (list (quote key) 115 nil)))" \
  "(setq x (ide-step x (list (quote key) 108 nil)))" \
  "(setq x (ide-step x (list (quote key) 50 nil)))" \
  "(car (cdr (setq x (ide-step x (list (quote key) 13 nil)))))"

run_phase reject-fasl-directory-open "\"not source\"" \
  "(progn (setq x (ide-make-state (ide-make-buffer \"*directory*\" (list \"fasl2\")))) nil)" \
  "(car (cdr (setq x (ide-step x (list (quote key) 13 nil)))))"

run_phase reject-fasl-save "\"not source\"" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"x\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 23 nil)))" \
  "(setq x (ide-step x (list (quote key) 102 nil)))" \
  "(setq x (ide-step x (list (quote key) 97 nil)))" \
  "(setq x (ide-step x (list (quote key) 115 nil)))" \
  "(setq x (ide-step x (list (quote key) 108 nil)))" \
  "(setq x (ide-step x (list (quote key) 50 nil)))" \
  "(car (cdr (setq x (ide-step x (list (quote key) 13 nil)))))"

run_phase find-tab "(find-file \"Find file: \" \"DEMO\")" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 6 nil)))" \
  "(setq x (ide-step x (list (quote key) 9 nil)))" \
  "(setq x (symbol-value (quote %ide-mini)))" \
  "(list (car x) (car (cdr x)) (car (cdr (cdr x))))"

run_phase buffer-tab "(switch-buffer \"Buffer: \" \"b\" \"a\")" \
  "(set-symbol-value (quote *ide-buffers*) nil)" \
  "(r5-hw-store-buffer (ide-make-buffer \"a\" (list \"aa\")))" \
  "(r5-hw-store-buffer (ide-make-buffer \"b\" (list \"bb\")))" \
  "(setq x (ide-make-state (r5-hw-resume-buffer \"b\")))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 2 nil)))" \
  "(setq x (ide-step x (list (quote key) 9 nil)))" \
  "(setq x (symbol-value (quote %ide-mini)))" \
  "(list (car x) (car (cdr x)) (car (cdr (cdr x))) (car (cdr (cdr (cdr x)))))"

run_phase buffer-cycle "\"a\"" \
  "(set-symbol-value (quote *ide-buffers*) nil)" \
  "(r5-hw-store-buffer (ide-make-buffer \"a\" (list \"aa\")))" \
  "(r5-hw-store-buffer (ide-make-buffer \"b\" (list \"bb\")))" \
  "(r5-hw-store-buffer (ide-make-buffer \"c\" (list \"cc\")))" \
  "(setq x (ide-make-state (r5-hw-resume-buffer \"c\")))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 14 nil)))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 14 nil)))" \
  "(ide-buffer-name (car x))"

run_phase delete-forward "\"ac\"" \
  "(progn (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"abc\")) 0 1))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 4 nil))) nil)" \
  "(ide-current-line (car x))"

run_phase kill-line "((\"ab\") \"cd\")" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) \"\") (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"abcd\")) 0 2))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 11 nil))) nil)" \
  "(list (ide-buffer-lines (car x)) (symbol-value (quote *ide-kill-ring*)))"

run_phase yank "((\"abxycd\") (0 . 4))" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) \"xy\") (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"abcd\")) 0 2))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 25 nil))) nil)" \
  "(list (ide-buffer-lines (car x)) (ide-buffer-point (car x)))"

run_phase word-edit "((0 . 4) (0 . 3) ((\"ab \") \"cd\"))" \
  "(progn (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"(foo bar)\")) 0 0))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 15 nil))) nil)" \
  "(setq y (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"ab cd\")) 0 5)))" \
  "(progn (setq y (ide-step y (list (quote key) 21 nil))) nil)" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) \"\") (setq z (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"ab cd\")) 0 3))) nil)" \
  "(progn (setq z (ide-step z (list (quote key) 23 nil))) nil)" \
  "(list (ide-buffer-point (car x)) (ide-buffer-point (car y)) (list (ide-buffer-lines (car z)) (symbol-value (quote *ide-kill-ring*))))"

run_phase document-nav "((2 . 1) (0 . 1) (0 . 0) (2 . 3))" \
  "(progn (setq x (r5-hw-set-rows (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"a\" \"bb\" \"ccc\")) 0 1)) 4)) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 22 nil))) nil)" \
  "(progn (setq y (ide-step x (list (quote key) 26 nil))) nil)" \
  "(progn (setq a (ide-step y (list (quote key) 24 nil))) nil)" \
  "(progn (setq a (ide-step a (list (quote key) 1 nil))) nil)" \
  "(progn (setq e (ide-step y (list (quote key) 24 nil))) nil)" \
  "(progn (setq e (ide-step e (list (quote key) 5 nil))) nil)" \
  "(list (ide-buffer-point (car x)) (ide-buffer-point (car y)) (ide-buffer-point (car a)) (ide-buffer-point (car e)))"

run_phase region-edit "((\"ad\") \"bc\")" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) \"\") (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"abcd\")) 0 1))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 0 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 5 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 2 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 24 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 18 nil))) nil)" \
  "(list (ide-buffer-lines (car x)) (symbol-value (quote *ide-kill-ring*)))"

run_phase region-multiline "((\"ah\") (0 . 1) (\"bcd\" \"ef\" \"g\"))" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) \"\") (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"abcd\" \"ef\" \"gh\")) 0 1))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 0 nil))) nil)" \
  "(progn (setq x (cons (ide-set-point (car x) 2 1) (cdr x))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 24 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 18 nil))) nil)" \
  "(list (ide-buffer-lines (car x)) (ide-buffer-point (car x)) (symbol-value (quote *ide-kill-ring*)))"

run_phase yank-multiline "((\"acd\" \"ef\" \"gb\") (2 . 1))" \
  "(progn (set-symbol-value (quote *ide-kill-ring*) (list \"cd\" \"ef\" \"g\")) (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"ab\")) 0 1))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 25 nil))) nil)" \
  "(list (ide-buffer-lines (car x)) (ide-buffer-point (car x)))"

run_phase compile-source-guard "\"not source\"" \
  "(progn (compile-file-to-lib \"fasl2\" \"fasl0\") (ide-error))"

run_phase navigation-aliases "(\"a\" \"b\" \"cd\")" \
  "(progn (setq x (ide-make-state (ide-set-point (ide-make-buffer \"scratch\" (list \"ab\" \"cd\")) 0 1))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 1 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 5 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 2 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 14 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 16 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 10 nil))) nil)" \
  "(ide-buffer-lines (car x))"

run_phase mini-history "(find-file \"Find file: \" \"demo\")" \
  "(set-symbol-value (quote %ide-mini-history) (list (quote find-file) \"demo\"))" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 6 nil)))" \
  "(setq x (ide-step x (list (quote key) 16 nil)))" \
  "(setq x (symbol-value (quote %ide-mini)))" \
  "(list (car x) (car (cdr x)) (car (cdr (cdr x))))"

run_phase mini-edit "\"d\"" \
  "(set-symbol-value (quote %ide-prefix) nil)" \
  "(setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 6 nil)))" \
  "(setq x (ide-step x (list (quote key) 100 nil)))" \
  "(setq x (ide-step x (list (quote key) 101 nil)))" \
  "(setq x (ide-step x (list (quote key) 127 nil)))" \
  "(car (cdr (cdr (symbol-value (quote %ide-mini)))))"

run_phase search-goto "\"moved\"" \
  "(progn (setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"abc\" \"needle\" \"tail\")))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 19 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 110 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 13 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 12 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 51 nil))) nil)" \
  "(car (cdr (setq x (ide-step x (list (quote key) 13 nil)))))"

run_phase search-repeat "((1 . 0) \"found\")" \
  "(progn (setq x (ide-make-state (ide-make-buffer \"scratch\" (list \"abc needle\" \"needle\" \"tail\")))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 19 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 110 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 13 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 19 nil))) nil)" \
  "(progn (setq x (ide-step x (list (quote key) 19 nil))) nil)" \
  "(list (ide-buffer-point (car x)) (car (cdr x)))"

run_phase higher-order-idex-some "3" \
  '(setq x "(some (function (lambda (x) (if (> x 2) x nil))) ")' \
  '(setq x (string-append x (char->string 39) "(1 2 3))"))' \
  '(r5-hw-store-buffer (ide-make-buffer "h8s" (list x (string-append "(setq x " x ")"))))' \
  '(save-buffer-to "h8s" "h8s")' \
  '(load "h8s")' \
  '(load "h8s")' \
  'x'

run_phase higher-order-idex-every "t" \
  '(setq x "(every (function plusp) ")' \
  '(setq x (string-append x (char->string 39) "(1 2 3))"))' \
  '(r5-hw-store-buffer (ide-make-buffer "h8e" (list x (string-append "(setq x " x ")"))))' \
  '(save-buffer-to "h8e" "h8e")' \
  '(load "h8e")' \
  '(load "h8e")' \
  'x'

if [ "$deploy" = "1" ]; then
  echo "==> frische Workbench-Session fuer M-x eval-buffer-Smoke"
  deploy_workbench 1
  wait_for_repl
  run_phase eval-core-load "\"ide-load-ok\"" \
    "(if (load-lib \"ide\") \"ide-load-ok\" \"ide-load-fail\")"
  install_r5_harness_helpers
  run_phase eval-extra-load "\"idex-load-ok\"" \
    "(if (load-lib \"idex\") \"idex-load-ok\" \"idex-load-fail\")"
fi

run_phase mx-eval-buffer "(\"evaluated\" 42)" \
  "(set-symbol-value (quote *ide-buffers*) nil)" \
  "(setq x (ide-make-state (ide-make-buffer \"e\" (list \"(defun eh () 42)\" \"(eh)\"))))" \
  "(setq x (ide-step x (list (quote key) 24 nil)))" \
  "(setq x (ide-step x (list (quote key) 120 nil)))" \
  "(setq x (ide-step x (list (quote key) 101 nil)))" \
  "(setq x (ide-step x (list (quote key) 9 nil)))" \
  "(setq x (ide-step x (list (quote key) 13 nil)))" \
  "(list (ide-state-message x) (eh))"

echo "PASS Workbench UX HW smoke"
