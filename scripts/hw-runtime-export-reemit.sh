#!/bin/sh
# Re-emit the sealed Runtime Export demo through the verified Workbench.
#
# This is a Golden/provenance procedure, not a power-cycle test and not G5.
# It mutates only a fresh throwaway copy of the verified Ship-v5 D81, stages
# the manifest-bound Workbench artifacts, compiles demo -> fasl0 through the
# JTAG REPL, reads the D81 back, and requires exact Golden and host-oracle
# comparisons through runtime_export_workbench_artifact.py.
set -eu

cd "$(dirname "$0")/.."

dry_run=0
ip=""
tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
c1541_bin="${C1541:-c1541}"
python_bin="${PYTHON:-python3}"
ship_dir="${WORKBENCH_VERIFIED_DIR:-build/ship}"
source_lisp="${RUNTIME_EXPORT_REEMIT_SOURCE:-lib/runtime-core.lisp}"
capture_id="${RUNTIME_EXPORT_CAPTURE_ID:-}"
golden_l65m="${RUNTIME_EXPORT_GOLDEN_L65M:-}"
golden_preload="${RUNTIME_EXPORT_GOLDEN_PRELOAD:-}"
host_l65m="${RUNTIME_EXPORT_HOST_L65M:-build/products/runtime-core/runtime-app.ext.bin}"
host_preload="${RUNTIME_EXPORT_HOST_PRELOAD:-build/products/runtime-core/bytecode/stdlib-p0.ext.bin}"
lcc_inputs="${RUNTIME_EXPORT_LCC_INPUTS:-lib/lcc.lisp lib/lcc-fasl.lisp lib/ide-disk.lisp}"
out_dir="${OUT_DIR:-build/hw/runtime-export-reemit}"
remote_d81="${RUNTIME_EXPORT_REEMIT_REMOTE_D81:-L65RTE.D81}"
boot_wait_sec="${BOOT_WAIT_SEC:-3}"
ide_wait_sec="${IDE_LOAD_WAIT_SEC:-15}"
compile_wait_sec="${COMPILE_WAIT_SEC:-30}"
timeout_sec="${TIMEOUT_SEC:-30}"
deploy_timeout_sec="${DEPLOY_TIMEOUT_SEC:-180}"
ftp_timeout_sec="${FTP_TIMEOUT_SEC:-120}"
verify_tool="${WORKBENCH_VERIFY_TOOL:-tools/host-lisp/workbench_ship.py}"
capture_tool="${RUNTIME_EXPORT_CAPTURE_TOOL:-tools/host-lisp/runtime_export_workbench_artifact.py}"
jtag_runner="${JTAG_REPL_RUNNER:-scripts/hw-jtag-repl.sh}"

usage() {
  cat >&2 <<EOF
usage: $0 --golden-l65m <file> --golden-preload <file> [options]
  --dry-run                 print the complete procedure; write/touch nothing
  --ship-dir <dir>          strictly verified Workbench Ship-v5 directory
                            (default: $ship_dir)
  --source <file>           Runtime demo source written as D81 slot demo
                            (default: $source_lisp)
  --capture-id <id>         unique safe ID for this hardware capture (required)
  --golden-l65m <file>      sealed Workbench Golden L65M (required)
  --golden-preload <file>   sealed Workbench Golden Bank-5 payload (required)
  --host-l65m <file>        Python-P0 differential L65M (default: $host_l65m)
  --host-preload <file>     Python-P0 differential preload (default: $host_preload)
  --lcc-input <file>        replace default compiler-input pins; repeatable
  --out-dir <dir>           fresh evidence directory (default: $out_dir)
  --remote-d81 <name>       throwaway SD filename (default: $remote_d81)
  --ip <ipv6%iface>         explicit MEGA65 network target
  --tools <dir>             m65tools directory (default: $tools_dir)
  --device <dev>            JTAG/UART device (default: $device)
  --c1541 <path>            c1541 binary (default: $c1541_bin)
  --boot-wait <seconds>     wait for the Workbench REPL (default: $boot_wait_sec)
  --ide-wait <seconds>      poll budget for load-lib ide (default: $ide_wait_sec)
  --compile-wait <seconds>  poll budget for compile-file-to-lib (default: $compile_wait_sec)
  --timeout <seconds>       timeout for one JTAG operation (default: $timeout_sec)
  --deploy-timeout <sec>    timeout for preload/mount/run (default: $deploy_timeout_sec)
  --ftp-timeout <sec>       timeout for one FTP transfer (default: $ftp_timeout_sec)
  --verify-tool <file>      Workbench ship verifier (selftest injection seam)
  --capture-tool <file>     Workbench artifact capture tool
  --jtag-runner <file>      verified-input JTAG REPL runner
  -h|--help                 show this help

The live run requires exact equality to the sealed Workbench Golden. The
Python-P0 pair is recorded as a differential oracle and may differ. This
procedure performs no hard reset or power-cycle and produces no G5 claim.
EOF
  exit 2
}

need_value() {
  [ "$#" -gt 0 ] || usage
}

lcc_inputs_from_cli=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --ship-dir) shift; need_value "$@"; ship_dir=$1 ;;
    --source) shift; need_value "$@"; source_lisp=$1 ;;
    --capture-id) shift; need_value "$@"; capture_id=$1 ;;
    --golden-l65m) shift; need_value "$@"; golden_l65m=$1 ;;
    --golden-preload) shift; need_value "$@"; golden_preload=$1 ;;
    --host-l65m) shift; need_value "$@"; host_l65m=$1 ;;
    --host-preload) shift; need_value "$@"; host_preload=$1 ;;
    --lcc-input)
      shift; need_value "$@"
      if [ "$lcc_inputs_from_cli" = "0" ]; then lcc_inputs=""; fi
      lcc_inputs="${lcc_inputs}${lcc_inputs:+ }$1"
      lcc_inputs_from_cli=1
      ;;
    --out-dir) shift; need_value "$@"; out_dir=$1 ;;
    --remote-d81) shift; need_value "$@"; remote_d81=$1 ;;
    --ip) shift; need_value "$@"; ip=$1 ;;
    --tools) shift; need_value "$@"; tools_dir=$1 ;;
    --device) shift; need_value "$@"; device=$1 ;;
    --c1541) shift; need_value "$@"; c1541_bin=$1 ;;
    --boot-wait) shift; need_value "$@"; boot_wait_sec=$1 ;;
    --ide-wait) shift; need_value "$@"; ide_wait_sec=$1 ;;
    --compile-wait) shift; need_value "$@"; compile_wait_sec=$1 ;;
    --timeout) shift; need_value "$@"; timeout_sec=$1 ;;
    --deploy-timeout) shift; need_value "$@"; deploy_timeout_sec=$1 ;;
    --ftp-timeout) shift; need_value "$@"; ftp_timeout_sec=$1 ;;
    --verify-tool) shift; need_value "$@"; verify_tool=$1 ;;
    --capture-tool) shift; need_value "$@"; capture_tool=$1 ;;
    --jtag-runner) shift; need_value "$@"; jtag_runner=$1 ;;
    -h|--help) usage ;;
    -*) echo "Fehler: unbekannte Option: $1" >&2; usage ;;
    *) echo "error: unexpected argument: $1" >&2; usage ;;
  esac
  shift
done

[ -n "$golden_l65m" ] || { echo "Fehler: --golden-l65m ist erforderlich" >&2; exit 2; }
[ -n "$golden_preload" ] || { echo "Fehler: --golden-preload ist erforderlich" >&2; exit 2; }
[ -n "$capture_id" ] || { echo "Fehler: --capture-id ist erforderlich" >&2; exit 2; }
[ "${#capture_id}" -ge 8 ] || { echo "Fehler: --capture-id muss mindestens 8 Zeichen enthalten" >&2; exit 2; }
[ "${#capture_id}" -le 64 ] || { echo "Fehler: --capture-id darf hoechstens 64 Zeichen enthalten" >&2; exit 2; }
case "$capture_id" in
  [!A-Za-z0-9]*|*[!A-Za-z0-9._-]*)
    echo "Fehler: --capture-id muss mit einem alphanumerischen ASCII-Zeichen beginnen und darf danach nur ._- enthalten" >&2
    exit 2
    ;;
esac
[ -n "$lcc_inputs" ] || { echo "Fehler: mindestens ein --lcc-input ist erforderlich" >&2; exit 2; }
for numeric in "$boot_wait_sec" "$ide_wait_sec" "$compile_wait_sec" \
               "$timeout_sec" "$deploy_timeout_sec" "$ftp_timeout_sec"
do
  case "$numeric" in
    ''|*[!0-9]*) echo "Fehler: numerische Option erwartet: $numeric" >&2; exit 2 ;;
  esac
done
[ "$timeout_sec" -gt 0 ] || { echo "Fehler: --timeout muss groesser als 0 sein" >&2; exit 2; }
[ "$deploy_timeout_sec" -gt 0 ] || { echo "Fehler: --deploy-timeout muss groesser als 0 sein" >&2; exit 2; }
[ "$ftp_timeout_sec" -gt 0 ] || { echo "Fehler: --ftp-timeout muss groesser als 0 sein" >&2; exit 2; }
case "$remote_d81" in
  ''|*/*|*[!A-Za-z0-9._-]*)
    echo "Fehler: --remote-d81 muss ein sicherer SD-Dateiname ohne Pfad sein" >&2
    exit 2
    ;;
esac
case "$out_dir" in ''|/) echo "Fehler: unsicheres --out-dir" >&2; exit 2 ;; esac
for path in $lcc_inputs; do
  case "$path" in *' '*) echo "Fehler: LCC-Inputpfade duerfen keine Leerzeichen enthalten" >&2; exit 2 ;; esac
done

manifest="$ship_dir/manifest.json"
ship_prg="$ship_dir/lisp65-mvp-workbench.prg"
ship_bank5="$ship_dir/lisp65-mvp-workbench.blob.bin"
ship_attic="$ship_dir/lisp65-mvp-workbench.overlays.bin"
ship_d81="$ship_dir/lisp65-mvp-workbench.d81"
before_d81="$out_dir/before.d81"
after_d81="$out_dir/after.d81"
empty_fasl="$out_dir/empty-fasl0.bin"
demo_readback="$out_dir/before-demo.bin"
fasl_readback="$out_dir/before-fasl0.bin"
emitted_l65m="$out_dir/runtime-app.l65m"
emitted_preload="$out_dir/runtime-preload.bin"
golden_report="$out_dir/golden-diff.json"
host_report="$out_dir/host-diff.json"

print_plan() {
  echo "runtime-export Workbench re-emission plan (Golden provenance; NOT G5)"
  echo "  verify: $ship_dir as strict lisp65-workbench-ship-v5"
  echo "  source: $source_lisp -> D81:demo"
  echo "  capture: $capture_id"
  echo "  target: empty 8192-byte D81:fasl0"
  echo "  deploy: $ship_attic@0x08000000 $ship_bank5@0x050000 $ship_prg"
  echo "  medium: $before_d81 -> SD:$remote_d81 -> $after_d81"
  echo "  forms:  (load-lib \"ide\")"
  echo "          (compile-file-to-lib \"demo\" \"fasl0\")"
  echo "  Golden: $golden_l65m + $golden_preload"
  echo "  host:   $host_l65m + $host_preload"
  echo "  output: $out_dir (must be fresh)"
}

print_plan

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: $python_bin $verify_tool verify --strict --expect-format lisp65-workbench-ship-v5 --dir $ship_dir"
  echo "DRY-RUN: create fresh $out_dir; copy $ship_d81 to $before_d81"
  echo "DRY-RUN: replace D81:demo with $source_lisp and D81:fasl0 with 8192 zero bytes via $c1541_bin"
  echo "DRY-RUN: read both slots back and compare them byte-for-byte with their inputs"
  echo "DRY-RUN: $tools_dir/mega65_ftp upload $before_d81 as $remote_d81 and mount it"
  echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -H -@ $ship_attic@0x08000000"
  echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -H -@ $ship_bank5@0x050000"
  echo "DRY-RUN: timeout ${deploy_timeout_sec}s $tools_dir/m65 -l $device -r -1 $ship_prg"
  echo "DRY-RUN: $jtag_runner --verified-input --expect '\"reemit-ide-ok\"' --form '(if (load-lib \"ide\") \"reemit-ide-ok\" \"reemit-ide-fail\")'"
  echo "DRY-RUN: $jtag_runner --verified-input --expect '\"reemit-compile-ok\"' --form '(if (compile-file-to-lib \"demo\" \"fasl0\") \"reemit-compile-ok\" (ide-error))'"
  echo "DRY-RUN: $tools_dir/mega65_ftp read back $remote_d81 to $after_d81"
  echo "DRY-RUN: $python_bin $capture_tool capture --capture-id $capture_id ... --host-l65m $golden_l65m --host-preload $golden_preload --require-host-equal --require-d81-change"
  echo "DRY-RUN: $python_bin $capture_tool capture --capture-id $capture_id ... --host-l65m $host_l65m --host-preload $host_preload --require-d81-change (differential only)"
  echo "DRY-RUN PASS: no files, tools, hardware, power-cycle, or G5 receipt"
  exit 0
fi

[ ! -e "$out_dir" ] || { echo "Fehler: Evidence-Verzeichnis muss frisch sein: $out_dir" >&2; exit 3; }
for path in "$source_lisp" "$golden_l65m" "$golden_preload" "$host_l65m" \
            "$host_preload" "$verify_tool" "$capture_tool" "$jtag_runner" \
            "$ship_prg"
do
  [ -f "$path" ] && [ ! -L "$path" ] || { echo "Fehler: regulaere, symlinkfreie Datei erforderlich: $path" >&2; exit 3; }
done
for path in $lcc_inputs; do
  [ -f "$path" ] && [ ! -L "$path" ] || { echo "Fehler: LCC-Input fehlt/ist Symlink: $path" >&2; exit 3; }
done
command -v "$python_bin" >/dev/null 2>&1 || { echo "Fehler: Python fehlt: $python_bin" >&2; exit 3; }
command -v "$c1541_bin" >/dev/null 2>&1 || { echo "Fehler: c1541 fehlt: $c1541_bin" >&2; exit 3; }
command -v timeout >/dev/null 2>&1 || { echo "Fehler: timeout fehlt" >&2; exit 3; }
for tool in "$tools_dir/mega65_ftp" "$tools_dir/m65"; do
  [ -x "$tool" ] && [ ! -L "$tool" ] || { echo "Fehler: Hardwaretool fehlt/ist Symlink: $tool" >&2; exit 3; }
done

"$python_bin" "$verify_tool" verify --strict \
  --expect-format lisp65-workbench-ship-v5 --dir "$ship_dir"
for artifact in "$manifest" "$ship_prg" "$ship_bank5" "$ship_attic" "$ship_d81"; do
  [ -f "$artifact" ] && [ ! -L "$artifact" ] || { echo "Fehler: verifiziertes Ship-Artefakt fehlt/ist Symlink: $artifact" >&2; exit 3; }
done
source_bytes=$(wc -c < "$source_lisp" | tr -d ' ')
[ "$source_bytes" -le 8192 ] || { echo "Fehler: Runtime-Quelle ist groesser als demo-Slot: $source_bytes" >&2; exit 3; }

mkdir -p "$out_dir"
cp "$ship_d81" "$before_d81"
dd if=/dev/zero of="$empty_fasl" bs=8192 count=1 status=none
c1541_log="$out_dir/c1541.log"
"$c1541_bin" "$before_d81" -delete demo -delete fasl0 \
  -write "$source_lisp" "demo,s" -write "$empty_fasl" "fasl0,s" \
  >"$c1541_log" 2>&1 || { cat "$c1541_log" >&2; exit 3; }
"$c1541_bin" "$before_d81" -read demo,s "$demo_readback" >>"$c1541_log" 2>&1 || { cat "$c1541_log" >&2; exit 3; }
"$c1541_bin" "$before_d81" -read fasl0,s "$fasl_readback" >>"$c1541_log" 2>&1 || { cat "$c1541_log" >&2; exit 3; }
cmp "$source_lisp" "$demo_readback" || { echo "Fehler: D81:demo weicht von der Runtime-Quelle ab" >&2; exit 3; }
cmp "$empty_fasl" "$fasl_readback" || { echo "Fehler: D81:fasl0 ist nicht der leere 8192-B-Zielslot" >&2; exit 3; }

set -- -e -y
[ -n "$ip" ] && set -- "$@" -i "$ip"
set -- "$@" -c "put $before_d81 $remote_d81" -c "mount $remote_d81" -c exit
timeout "${ftp_timeout_sec}s" "$tools_dir/mega65_ftp" "$@"

timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -H \
  -@ "$ship_attic@0x08000000"
timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -H \
  -@ "$ship_bank5@0x050000"
timeout "${deploy_timeout_sec}s" "$tools_dir/m65" -l "$device" -r -1 "$ship_prg"
[ "$boot_wait_sec" -eq 0 ] || sleep "$boot_wait_sec"

"$jtag_runner" --tools "$tools_dir" --device "$device" \
  --out-dir "$out_dir" --prefix reemit-load-ide --verified-input \
  --timeout "$timeout_sec" --expect-poll "$ide_wait_sec" \
  --expect '"reemit-ide-ok"' \
  --form '(if (load-lib "ide") "reemit-ide-ok" "reemit-ide-fail")'
"$jtag_runner" --tools "$tools_dir" --device "$device" \
  --out-dir "$out_dir" --prefix reemit-compile --verified-input \
  --timeout "$timeout_sec" --expect-poll "$compile_wait_sec" \
  --expect '"reemit-compile-ok"' \
  --form '(if (compile-file-to-lib "demo" "fasl0") "reemit-compile-ok" (ide-error))'

rm -f "$after_d81"
set -- -e -y
[ -n "$ip" ] && set -- "$@" -i "$ip"
set -- "$@" -c "get $remote_d81 $after_d81" -c exit
timeout "${ftp_timeout_sec}s" "$tools_dir/mega65_ftp" "$@"
[ -f "$after_d81" ] && [ ! -L "$after_d81" ] || { echo "Fehler: D81-Readback fehlt" >&2; exit 3; }

run_capture() {
  compare_l65m=$1
  compare_preload=$2
  report=$3
  l65m_out=$4
  preload_out=$5
  require_equal=$6
  set -- capture --capture-id "$capture_id" \
    --source "$source_lisp" --ship-manifest "$manifest" \
    --before-d81 "$before_d81" --after-d81 "$after_d81" \
    --slot fasl0 --entry runtime-main --arity 0 \
    --l65m-out "$l65m_out" --preload-out "$preload_out" \
    --report-out "$report" --host-l65m "$compare_l65m" \
    --host-preload "$compare_preload" --require-d81-change
  [ "$require_equal" = "0" ] || set -- "$@" --require-host-equal
  for input in $lcc_inputs; do set -- "$@" --lcc-input "$input"; done
  "$python_bin" "$capture_tool" "$@"
}

run_capture "$golden_l65m" "$golden_preload" "$golden_report" \
  "$emitted_l65m" "$emitted_preload" 1
run_capture "$host_l65m" "$host_preload" "$host_report" \
  "$out_dir/host-checked-runtime-app.l65m" "$out_dir/host-checked-runtime-preload.bin" 0
cmp "$emitted_l65m" "$out_dir/host-checked-runtime-app.l65m"
cmp "$emitted_preload" "$out_dir/host-checked-runtime-preload.bin"

echo "PASS Runtime Export Workbench re-emission: Golden exact; host differential recorded"
echo "NOTE: provenance/re-emission evidence only; no power-cycle and no G5 claim"
