#!/bin/sh
# Focused physical-hardware proof for the four owner-bound public C1 seams.
# This is reopening evidence only.  It deliberately cannot emit an R5/G5 case
# receipt; the full matrix remains at 0/14 until the optimized product is pinned.
set -eu

cd "$(dirname "$0")/.."

tools_dir="${TOOLS:-tools/m65tools}"
device="${DEVICE:-/dev/ttyUSB1}"
ip="${MEGA65_IP:-}"
out_dir="${OUT_DIR:-build/hw/v11-c1-entry-seams}"
remote_d81="${REMOTE_D81:-C1SEAM.D81}"
resident="${RESIDENT_PRG:-build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg}"
preload="${PRELOAD:-build/products/workbench/overlay-stack-guard/stdlib-with-overlay.ext.bin}"
overlays="${RUNTIME_OVERLAYS:-build/products/workbench/overlay-stack-guard/lisp65-mvp-workbench.overlays.bin}"
shelf="${ATTIC_SHELF:-build/bytecode/dialect-v2/shelf/library-shelf.bin}"
# Reuse the immutable test-closure medium from the stopped Wave-1 G5 attempt.
# The C1 reopening changes C/overlay bytes, not IDE/M65D or the preallocated
# compile slots.  A fresh D81 build is deliberately not substituted here: its
# current source gate is independently red on sealed private-name history.
d81="${WORK_D81:-build/r5-global-g5/workbench-test.d81}"
form_wait="${FORM_WAIT_SEC:-8}"
poll="${EXPECT_POLL_SEC:-20}"
dry_run=0
upload_d81=1

usage() {
  cat >&2 <<EOF
usage: $0 [--dry-run] [--no-d81-upload] [--ip <ipv6%iface>] [--device <dev>] [--tools <dir>]
          [--out-dir <dir>] [--remote-d81 <name>] [--form-wait <seconds>]
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --no-d81-upload) upload_d81=0 ;;
    --ip) shift; [ "$#" -gt 0 ] || usage; ip=$1 ;;
    --device) shift; [ "$#" -gt 0 ] || usage; device=$1 ;;
    --tools) shift; [ "$#" -gt 0 ] || usage; tools_dir=$1 ;;
    --out-dir) shift; [ "$#" -gt 0 ] || usage; out_dir=$1 ;;
    --remote-d81) shift; [ "$#" -gt 0 ] || usage; remote_d81=$1 ;;
    --form-wait) shift; [ "$#" -gt 0 ] || usage; form_wait=$1 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
  shift
done

case "$remote_d81" in
  ""|*/*) echo "invalid remote D81 name: $remote_d81" >&2; exit 2 ;;
esac
case "$form_wait" in
  ""|*[!0-9]*) echo "--form-wait must be an integer" >&2; exit 2 ;;
esac

for artifact in "$resident" "$preload" "$overlays" "$shelf" "$d81"; do
  [ -f "$artifact" ] || { echo "missing artifact: $artifact" >&2; exit 3; }
done

mkdir -p "$out_dir"
seam_dir="$out_dir/generated"

echo "==> host gates: overlap rollback and generated seam parity"
make --no-print-directory \
  v11-c1-compiler-lifetime-check vm-ext-code-reclaim-smoke v11-c1-entry-seam-check
python3 tools/host-lisp/v11_c1_entry_seams.py --emit "$seam_dir"

if [ "$upload_d81" = "1" ]; then
  if [ "$dry_run" = "1" ]; then
    echo "DRY-RUN: upload $d81 as $remote_d81"
  else
    set -- -e -y
    [ -n "$ip" ] && set -- "$@" -i "$ip"
    "$tools_dir/mega65_ftp" "$@" -c "put $d81 $remote_d81" -c exit
  fi
else
  echo "==> D81 upload skipped; using already uploaded $remote_d81"
fi

set -- --tools "$tools_dir" --mount "$remote_d81" \
  --preload-bin 0x08000000 "$overlays" \
  --preload-bin 0x050000 "$preload" \
  --preload-bin 0x08100000 "$shelf" --run
[ -n "$ip" ] && set -- "$@" --ip "$ip"
[ "$dry_run" = "1" ] && set -- "$@" --dry-run
set -- "$@" "$resident"
sh scripts/run-on-mega65.sh "$@"

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: sleep 3"
else
  sleep 3
fi

run_repl() {
  case_id=$1
  expected=$2
  forms=$3
  set -- --file "$forms" --expect "$expected" --expect-poll "$poll" \
    --form-wait "$form_wait" --verified-input --tools "$tools_dir" \
    --device "$device" --out-dir "$out_dir" --prefix "c1-seam-$case_id"
  [ "$dry_run" = "1" ] && set -- "$@" --dry-run
  sh scripts/hw-jtag-repl.sh "$@"
}

ide_forms="$out_dir/load-ide.forms"
printf '%s\n' \
  '(if (load-lib "ide") "c1-seam-ide-loaded" "c1-seam-ide-fail")' \
  > "$ide_forms"
run_repl load-ide '"c1-seam-ide-loaded"' "$ide_forms"

tab=$(printf '\t')
while IFS="$tab" read -r seam expected forms; do
  run_repl "$seam" "$expected" "$forms"
done < "$seam_dir/cases.tsv"

if [ "$dry_run" = "1" ]; then
  echo "DRY-RUN: receipt omitted"
  exit 0
fi

python3 - "$out_dir" "$resident" "$preload" "$overlays" "$shelf" "$d81" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

out = Path(sys.argv[1])
artifact_paths = [Path(value) for value in sys.argv[2:]]
root = Path.cwd()
contract = Path("config/v11-c1-entry-seams.json")
decision = Path("config/v11-c1-architecture-decision.json")
cases = json.loads(contract.read_text(encoding="utf-8"))["cases"]

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

transcripts = {"load-ide": out / "c1-seam-load-ide.txt"}
for case in cases:
    transcripts[case["id"]] = out / f"c1-seam-{case['id']}.txt"
for path in transcripts.values():
    if not path.is_file():
        raise SystemExit(f"missing transcript: {path}")

receipt = {
    "schema": "lisp65-v11-c1-entry-seam-hardware-v1",
    "status": "pass",
    "claim": "focused reopening evidence only; not an R5/G5 case receipt",
    "g5_cases_claimed": 0,
    "contract": {"path": str(contract), "sha256": digest(contract)},
    "decision": {"path": str(decision), "sha256": digest(decision)},
    "artifacts": [
        {"path": str(path), "size": path.stat().st_size, "sha256": digest(path)}
        for path in artifact_paths
    ],
    "host_gates": {
        "nested_transient_success": True,
        "overlap_rejected_without_mutation": True,
        "seam_decision_parity": True,
    },
    "hardware_cases": [
        {
            "id": case["id"],
            "entry": case["entry"],
            "expected": case["expect"],
            "transcript": str(transcripts[case["id"]]),
            "transcript_sha256": digest(transcripts[case["id"]]),
        }
        for case in cases
    ],
}
path = out / "c1-entry-seam-hardware-receipt.json"
path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {path}")
PY

echo "PASS: four generated C1 entry seams on physical hardware"
