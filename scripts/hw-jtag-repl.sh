#!/bin/sh
# Send one-line Lisp REPL forms over JTAG/UART and optionally capture a screen.
#
# Important: m65 -T already appends RETURN. Do not pass embedded newlines; they
# are typed as characters by the virtual keyboard path.
set -eu

cd "$(dirname "$0")/.."

tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
out_dir="${OUT_DIR:-build/hw}"
prefix="${PREFIX:-hw-jtag-repl}"
wait_sec="${WAIT_SEC:-1}"
form_wait_sec="${FORM_WAIT_SEC:-0}"
timeout_sec="${TIMEOUT_SEC:-20}"
input_retry_wait_sec="${INPUT_RETRY_WAIT_SEC:-0.2}"
timeout_kill_after_sec="${TIMEOUT_KILL_AFTER_SEC:-2}"
dry_run=0
readback=1
verified_input=0
expect=""
expect_poll_sec=0
forms_tmp=""
submitted_epoch=0

cleanup() {
  [ -z "$forms_tmp" ] || rm -f "$forms_tmp"
}
trap cleanup 0

usage() {
  cat >&2 <<EOF
usage: $0 [options] [form ...]
  --form <expr>      Lisp form to type and submit; may be repeated
  --file <path>      read one REPL form per non-empty, non-comment line
  --expect <text>    require the exact latest REPL result
  --expect-poll <s>  poll for the exact result up to this many seconds
  --tools <dir>      m65tools directory (default: $tools_dir)
  --device <dev>     JTAG serial device (default: $device)
  --out-dir <dir>    screenshot/text output directory (default: $out_dir)
  --prefix <name>    screenshot/text filename prefix (default: $prefix)
  --wait <seconds>   wait before screenshot (default: $wait_sec)
  --form-wait <sec>  wait after each submitted form (default: $form_wait_sec)
  --timeout <sec>    timeout for each m65 command (default: $timeout_sec)
  --timeout-kill-after <sec>
                      force-kill grace after timeout (default: $timeout_kill_after_sec)
  --input-retry-wait <sec>
                      wait around verified-input retries (default: $input_retry_wait_sec)
  --verified-input  verify active input before sending RETURN (max 3 attempts)
  --no-readback      skip screenshot/text capture
  --dry-run          print commands, do not touch hardware
  -h|--help          this help
EOF
  exit 2
}

mk_forms_tmp() {
  if [ -z "$forms_tmp" ]; then
    mkdir -p "$out_dir"
    forms_tmp=$(mktemp "$out_dir/$prefix.forms.XXXXXX")
  fi
}

add_form() {
  form=$1
  carriage_return=$(printf '\r')
  case "$form" in
    *"
"*|*"$carriage_return"*)
      echo "Fehler: REPL-Form enthaelt LF/CR; m65 interpretiert CR als RETURN" >&2
      exit 2
      ;;
    *"~"*)
      echo "Fehler: REPL-Form enthaelt '~'; m65 reserviert Tilde-Sequenzen fuer Steuertasten" >&2
      exit 2
      ;;
  esac
  mk_forms_tmp
  printf '%s\n' "$form" >> "$forms_tmp"
}

add_file() {
  file=$1
  [ -f "$file" ] || { echo "Fehler: Form-Datei fehlt: $file" >&2; exit 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|";"*|"#"*) ;;
      *) add_form "$line" ;;
    esac
  done < "$file"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --form) shift; [ "$#" -gt 0 ] || usage; add_form "$1" ;;
    --file) shift; [ "$#" -gt 0 ] || usage; add_file "$1" ;;
    --expect) shift; [ "$#" -gt 0 ] || usage; expect="$1" ;;
    --expect-poll) shift; [ "$#" -gt 0 ] || usage; expect_poll_sec="$1" ;;
    --tools) shift; [ "$#" -gt 0 ] || usage; tools_dir="$1" ;;
    --device) shift; [ "$#" -gt 0 ] || usage; device="$1" ;;
    --out-dir) shift; [ "$#" -gt 0 ] || usage; out_dir="$1" ;;
    --prefix) shift; [ "$#" -gt 0 ] || usage; prefix="$1" ;;
    --wait) shift; [ "$#" -gt 0 ] || usage; wait_sec="$1" ;;
    --form-wait) shift; [ "$#" -gt 0 ] || usage; form_wait_sec="$1" ;;
    --timeout) shift; [ "$#" -gt 0 ] || usage; timeout_sec="$1" ;;
    --timeout-kill-after) shift; [ "$#" -gt 0 ] || usage; timeout_kill_after_sec="$1" ;;
    --input-retry-wait) shift; [ "$#" -gt 0 ] || usage; input_retry_wait_sec="$1" ;;
    --verified-input) verified_input=1 ;;
    --no-readback) readback=0 ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage ;;
    -*) echo "unbekannte Option: $1" >&2; usage ;;
    *) add_form "$1" ;;
  esac
  shift
done

[ -n "$forms_tmp" ] || usage

case "$form_wait_sec" in
  ''|*[!0-9]*) echo "Fehler: --form-wait muss numerisch sein" >&2; exit 2 ;;
esac
case "$timeout_sec" in
  ''|*[!0-9]*) echo "Fehler: --timeout muss numerisch sein" >&2; exit 2 ;;
esac
[ "$timeout_sec" -gt 0 ] || { echo "Fehler: --timeout muss groesser als 0 sein" >&2; exit 2; }
case "$expect_poll_sec" in
  ''|*[!0-9]*) echo "Fehler: --expect-poll muss numerisch sein" >&2; exit 2 ;;
esac
[ "$expect_poll_sec" -eq 0 ] || [ -n "$expect" ] || {
  echo "Fehler: --expect-poll erfordert --expect" >&2
  exit 2
}
case "$timeout_kill_after_sec" in
  ''|*[!0-9]*) echo "Fehler: --timeout-kill-after muss numerisch sein" >&2; exit 2 ;;
esac
[ "$timeout_kill_after_sec" -gt 0 ] || { echo "Fehler: --timeout-kill-after muss groesser als 0 sein" >&2; exit 2; }
case "$input_retry_wait_sec" in
  ''|.*|*.|*.*.*|*[!0-9.]*) echo "Fehler: --input-retry-wait muss eine nichtnegative Dezimalzahl sein" >&2; exit 2 ;;
esac

m65="$tools_dir/m65"
if [ "$dry_run" != "1" ]; then
  [ -x "$m65" ] || { echo "Fehler: $m65 nicht ausfuehrbar/gefunden" >&2; exit 3; }
fi

run_m65() {
  timeout --kill-after="${timeout_kill_after_sec}s" "${timeout_sec}s" "$m65" "$@"
}

send_form() {
  form=$1
  submit=$2
  type_option=-t
  [ "$submit" -eq 1 ] && type_option=-T
  if [ "$dry_run" = "1" ]; then
    printf 'DRY-RUN: timeout --kill-after=%ss %ss %s -l %s %s %s\n' \
      "$timeout_kill_after_sec" "$timeout_sec" "$m65" "$device" "$type_option" "$form"
  else
    run_m65 -l "$device" "$type_option" "$form"
  fi
}

capture_screen() {
  capture_prefix=$1
  captured_shot="$out_dir/$capture_prefix.png"
  captured_ansi="$out_dir/$capture_prefix.ansi.txt"
  captured_text="$out_dir/$capture_prefix.txt"
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: timeout --kill-after=${timeout_kill_after_sec}s ${timeout_sec}s $m65 -l $device --screenshot=$captured_shot > $captured_ansi"
    echo "DRY-RUN: strip ANSI $captured_ansi > $captured_text"
    return
  fi
  capture_status=0
  if run_m65 -l "$device" --screenshot="$captured_shot" > "$captured_ansi"; then
    :
  else
    capture_status=$?
  fi
  [ "$capture_status" -eq 0 ] || return "$capture_status"
  python3 - "$captured_ansi" "$captured_text" <<'PY'
from pathlib import Path
import re
import sys

ansi_path, text_path = sys.argv[1], sys.argv[2]
raw = Path(ansi_path).read_text(errors="ignore")
clean = re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw)
Path(text_path).write_text(clean)
PY
}

clear_active_input() {
  form=$1
  clear_prefix=$2
  clear_count=$((${#form} * 2 + 16))
  clear_keys=""
  clear_number=0
  while [ "$clear_number" -lt "$clear_count" ]; do
    clear_keys="${clear_keys}~T"
    clear_number=$((clear_number + 1))
  done
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: timeout --kill-after=${timeout_kill_after_sec}s ${timeout_sec}s $m65 -l $device -t <${clear_count}x INST/DEL>"
    echo "DRY-RUN: verify empty active input after clear"
  else
    clear_status=0
    if run_m65 -l "$device" -t "$clear_keys"; then
      :
    else
      clear_status=$?
    fi
    [ "$clear_status" -eq 0 ] || return "$clear_status"
    sleep "$input_retry_wait_sec"
    empty_capture_status=0
    if capture_screen "$clear_prefix"; then
      :
    else
      empty_capture_status=$?
    fi
    [ "$empty_capture_status" -eq 0 ] || return "$empty_capture_status"
    empty_check_status=0
    if python3 tools/host-lisp/repl_screen_check.py \
        --screen "$captured_text" --form-text "" --active-input; then
      :
    else
      empty_check_status=$?
    fi
    return "$empty_check_status"
  fi
}

discard_active_input() {
  discard_form=$1
  discard_prefix=$2
  if clear_active_input "$discard_form" "$discard_prefix"; then
    return 0
  else
    discard_status=$?
  fi
  echo "WARNUNG: aktive JTAG-Eingabe konnte nicht nachweislich geleert werden (rc=$discard_status)" >&2
  return "$discard_status"
}

send_return() {
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: timeout --kill-after=${timeout_kill_after_sec}s ${timeout_sec}s $m65 -l $device -t ~M"
  else
    run_m65 -l "$device" -t '~M'
  fi
}

send_form_verified() {
  form=$1
  input_attempt=1
  while [ "$input_attempt" -le 3 ]; do
    type_status=0
    if send_form "$form" 0; then
      :
    else
      type_status=$?
    fi
    if [ "$type_status" -ne 0 ]; then
      discard_active_input "$form" "$prefix-type-failure-clear" || :
      return "$type_status"
    fi
    if [ "$dry_run" != "1" ]; then
      sleep "$input_retry_wait_sec"
    fi
    capture_status=0
    if capture_screen "$prefix-input-attempt-$input_attempt"; then
      :
    else
      capture_status=$?
    fi
    if [ "$capture_status" -ne 0 ]; then
      discard_active_input "$form" "$prefix-capture-failure-clear" || :
      return "$capture_status"
    fi
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: verify active input echo for attempt $input_attempt/3"
      send_return
      return $?
    fi

    input_status=0
    if python3 tools/host-lisp/repl_screen_check.py \
        --screen "$captured_text" --form-text "$form" --active-input; then
      send_return
      return $?
    else
      input_status=$?
    fi
    if [ "$input_status" -ne 5 ]; then
      discard_active_input "$form" "$prefix-check-failure-clear" || :
      return "$input_status"
    fi
    echo "WARNUNG: aktives JTAG-Echo weicht ab; nicht ausgefuehrte Eingabe wird verworfen" >&2
    clear_active_input "$form" "$prefix-input-attempt-$input_attempt-clear"
    if [ "$input_attempt" -eq 3 ]; then
      return "$input_status"
    fi
    input_attempt=$((input_attempt + 1))
  done
  return 5
}

while IFS= read -r form || [ -n "$form" ]; do
  if [ "$verified_input" = "1" ]; then
    send_form_verified "$form"
  else
    send_form "$form" 1
  fi
  if [ "$dry_run" = "1" ]; then
    submitted_epoch=0
  else
    submitted_epoch=$(date +%s)
  fi
  if [ "$form_wait_sec" -gt 0 ]; then
    if [ "$dry_run" = "1" ]; then
      echo "DRY-RUN: sleep $form_wait_sec"
    else
      sleep "$form_wait_sec"
    fi
  fi
done < "$forms_tmp"

[ "$readback" = "1" ] || exit 0

capture_ready=0
if [ "$expect_poll_sec" -gt 0 ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: poll exact REPL result for at most ${expect_poll_sec}s"
    capture_screen "$prefix"
    capture_ready=1
  else
    deadline=$((submitted_epoch + expect_poll_sec))
    while :; do
      capture_screen "$prefix"
      capture_ready=1
      if python3 tools/host-lisp/repl_screen_check.py \
          --screen "$captured_text" --forms "$forms_tmp" \
          --expect "$expect" >/dev/null 2>&1; then
        break
      fi
      [ "$(date +%s)" -lt "$deadline" ] || break
      sleep 1
    done
  fi
fi
if [ "$capture_ready" != "1" ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: sleep $wait_sec"
  else
    sleep "$wait_sec"
  fi
  capture_screen "$prefix"
fi
shot=$captured_shot
ansi=$captured_ansi
text=$captured_text

check_status=0
if [ -n "$expect" ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: python3 tools/host-lisp/repl_screen_check.py --screen $text --forms $forms_tmp --expect '$expect'"
  elif python3 tools/host-lisp/repl_screen_check.py \
      --screen "$text" --forms "$forms_tmp" --expect "$expect"; then
    echo "PASS letztes REPL-Resultat: $expect"
  else
    check_status=$?
  fi
fi

if [ "$expect_poll_sec" -gt 0 ]; then
  timing="$out_dir/$prefix-timing.json"
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: write polling timing report $timing"
  else
    completed_epoch=$(date +%s)
    elapsed_seconds=$((completed_epoch - submitted_epoch))
    if [ "$check_status" -eq 0 ] && \
       [ "$elapsed_seconds" -gt "$expect_poll_sec" ]; then
      check_status=8
    fi
    python3 - "$timing" "$submitted_epoch" "$completed_epoch" \
        "$expect_poll_sec" "$check_status" <<'PY'
from pathlib import Path
import json
import sys

path, submitted, completed, budget, status = sys.argv[1:]
value = {
    "schema": "lisp65-jtag-repl-timing-v1",
    "status": "pass" if int(status) == 0 else "fail",
    "submitted_epoch": int(submitted),
    "completed_epoch": int(completed),
    "elapsed_seconds": int(completed) - int(submitted),
    "budget_seconds": int(budget),
}
Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
  fi
fi
if [ "$check_status" -ne 0 ]; then
  echo "Fehler: letztes REPL-Resultat in $text ist nicht exakt: $expect" >&2
  exit "$check_status"
fi

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: Ausgaben: $shot $ansi $text"
else
  echo "Ausgaben: $shot $ansi $text"
fi
