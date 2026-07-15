#!/bin/sh
# run-on-mega65.sh -- automated test on physical MEGA65 hardware over the network.
#
# STATUS: UNTESTED -- prepared before hardware was available. Verify command syntax
# on the first real run, especially the mega65_ftp `get` argument order.
# Network-only path; no USB cable required:
#
#   etherload  -> load and start the PRG over Ethernet/IPv6
#   the test writes its result as a file on the SD card
#   mega65_ftp -> retrieve the result over Ethernet
#   grep       -> optional marker check -> exit 0 (PASS) or 1 (FAIL)
#
# Richer readback such as screenshots and typed input requires m65 over USB UART/JTAG,
# not the network; see the hardware testing documentation.
#
# Deliberately mirrors the xemu smoke pattern (load -> run -> result -> check), but on
# physical hardware. See the archived hardware-testing record for bring-up details.
set -eu

tools_dir="tools/m65tools"
ip=""
mode="run"            # run | jump
jump_addr=""
mount_d81=""
result_remote=""
out_local=""
expect=""
wait_sec="3"
dry_run="0"
preload_count=0
preload_addr_1=""
preload_file_1=""
preload_addr_2=""
preload_file_2=""
prg=""

usage() {
  cat >&2 <<EOF
usage: $0 [options] <program.prg>
  --dry-run              Kommandos nur ausgeben, nicht ausfuehren (ohne HW nutzbar)
  --tools <dir>          Pfad zu m65tools (default: $tools_dir)
  --ip <ipv6%iface>      MEGA65-Ziel (default: Auto-Discovery via etherload/ftp)
  --run                  PRG laden und RUNen (default)
  --jump <hexaddr>       PRG laden und nach <hexaddr> springen (SYS-artig)
  --mount <NAME.D81>     D81 von der SD-Karte mounten
  --preload-bin <addr> <file>
                         binaeres Artefakt vor dem PRG laden (maximal zweimal)
  --result <SDFILE>      diese Datei nach dem Lauf von der SD-Karte holen
  --out <localfile>      Ablageort der geholten Datei (default: build/mega65/<SDFILE>)
  --expect <string>      PASS (Exit 0) genau dann, wenn <string> in der Datei steht
  --wait <seconds>       Wartezeit zwischen Run und Readback (default: $wait_sec)
  -h|--help              diese Hilfe
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --tools)   shift; tools_dir="$1" ;;
    --ip)      shift; ip="$1" ;;
    --run)     mode="run" ;;
    --jump)    shift; mode="jump"; jump_addr="$1" ;;
    --mount)   shift; mount_d81="$1" ;;
    --preload-bin)
      shift; [ "$#" -gt 0 ] || usage; preload_addr=$1
      shift; [ "$#" -gt 0 ] || usage; preload_file=$1
      preload_count=$((preload_count + 1))
      case "$preload_count" in
        1) preload_addr_1=$preload_addr; preload_file_1=$preload_file ;;
        2) preload_addr_2=$preload_addr; preload_file_2=$preload_file ;;
        *) echo "zu viele --preload-bin-Optionen (maximal zwei)" >&2; usage ;;
      esac
      ;;
    --result)  shift; result_remote="$1" ;;
    --out)     shift; out_local="$1" ;;
    --expect)  shift; expect="$1" ;;
    --wait)    shift; wait_sec="$1" ;;
    -h|--help) usage ;;
    -*)        echo "unbekannte Option: $1" >&2; usage ;;
    *)         prg="$1" ;;
  esac
  shift
done

etherload="$tools_dir/etherload"
ftp="$tools_dir/mega65_ftp"

[ -n "$prg" ] || { echo "Fehler: kein <program.prg> angegeben" >&2; usage; }

emit() {  # print in dry-run mode or execute
  if [ "$dry_run" = "1" ]; then
    printf 'DRY-RUN:'; for a in "$@"; do printf ' %s' "$a"; done; printf '\n'
  else
    "$@"
  fi
}

if [ "$dry_run" != "1" ]; then
  [ -x "$etherload" ] || { echo "Fehler: $etherload nicht ausfuehrbar/gefunden" >&2; exit 3; }
  [ -x "$ftp" ]       || { echo "Fehler: $ftp nicht ausfuehrbar/gefunden" >&2; exit 3; }
  [ -f "$prg" ]       || { echo "Fehler: PRG nicht gefunden: $prg" >&2; exit 3; }
  [ -z "$preload_file_1" ] || [ -f "$preload_file_1" ] || \
    { echo "Fehler: Preload-Binaer fehlt: $preload_file_1" >&2; exit 3; }
  [ -z "$preload_file_2" ] || [ -f "$preload_file_2" ] || \
    { echo "Fehler: Preload-Binaer fehlt: $preload_file_2" >&2; exit 3; }
fi

# --- optionale binaere Preload-Artefakte, in angegebener Reihenfolge ---
preload_index=1
while [ "$preload_index" -le "$preload_count" ]; do
  case "$preload_index" in
    1) preload_addr=$preload_addr_1; preload_file=$preload_file_1 ;;
    2) preload_addr=$preload_addr_2; preload_file=$preload_file_2 ;;
    *) echo "interner Preload-Indexfehler: $preload_index" >&2; exit 2 ;;
  esac
  set --
  [ -n "$ip" ] && set -- "$@" -i "$ip"
  set -- "$@" --halt -b "$preload_addr" "$preload_file"
  echo "== etherload (binaeres Preload-Artefakt $preload_index/$preload_count) =="
  emit "$etherload" "$@"
  preload_index=$((preload_index + 1))
done

# --- Build etherload arguments ---
set --
[ -n "$ip" ]        && set -- "$@" -i "$ip"
[ -n "$mount_d81" ] && set -- "$@" -m "$mount_d81"
case "$mode" in
  run)  set -- "$@" -r ;;
  jump) set -- "$@" -j "$jump_addr" ;;
esac
set -- "$@" "$prg"

echo "== etherload (laden + starten ueber Ethernet) =="
emit "$etherload" "$@"

# --- Readback ---
if [ -n "$result_remote" ]; then
  [ -n "$out_local" ] || out_local="build/mega65/$result_remote"
  [ "$dry_run" = "1" ] || mkdir -p "$(dirname "$out_local")"
  echo "== ${wait_sec}s warten, bis der Test '$result_remote' auf die SD schreibt =="
  emit sleep "$wait_sec"
  echo "== mega65_ftp (Ergebnis ueber Ethernet holen) =="
  if [ -n "$ip" ]; then
    emit "$ftp" -e -i "$ip" -y -c "get $result_remote $out_local" -c "exit"
  else
    emit "$ftp" -e -y -c "get $result_remote $out_local" -c "exit"
  fi
fi

# --- Marker-Check ---
if [ -n "$expect" ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: grep -q -- '$expect' '$out_local'   # PASS gdw. gefunden"
    exit 0
  fi
  if grep -q -- "$expect" "$out_local"; then
    echo "PASS: '$expect' in $out_local gefunden"
    exit 0
  else
    echo "FAIL: '$expect' NICHT in $out_local" >&2
    exit 1
  fi
fi

echo "fertig."
