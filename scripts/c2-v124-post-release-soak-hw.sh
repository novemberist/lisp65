#!/bin/sh
# Post-v1.2.4 30-minute C2D append/read soak; measurement only.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
CONFIG=config/c2-v124-post-release-soak.json
CONTRACT=docs/planning/c2d-append-visibility-measurement-contract.md
PLAN=docs/planning/post-1.2.4-roadmap.md
FIXTURE=tests/equivalence/c2-v124-post-release-soak.lisp
OUT=${C2_V124_SOAK_OUT:-build/post-promotion/v124/post-release-soak/session-01}
PREPARATION=tests/bytecode/dialect-v2/evidence/post-release/post-v124-soak-preparation-receipt-20260730.json
RECEIPT=tests/bytecode/dialect-v2/evidence/post-release/post-v124-soak-hardware-receipt-20260730.json
TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
FTP=$TOOLS/mega65_ftp
TIMEOUT=${TIMEOUT:-60}
EXPECT_POLL=${EXPECT_POLL:-120}
FTP_STALL_LIMIT=${FTP_STALL_LIMIT:-120}

case "$ACTION" in
  prepare|dry-run|start|verify) ;;
  *) echo "usage: $0 <prepare|dry-run|start|verify>" >&2; exit 2 ;;
esac

sha256_file() {
  sha256sum "$1" | cut -d' ' -f1
}

bind_preparation() {
  python3 - "$CONFIG" "$CONTRACT" "$PLAN" "$FIXTURE" "$PREPARATION" "$0" <<'PY'
from __future__ import annotations
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

config_path, contract_path, plan_path, fixture_path, receipt_path, script_path = (
    Path(value) for value in sys.argv[1:])
root = Path.cwd()

def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

config = json.loads(config_path.read_text())
schedule = config["schedule"]
assert schedule["batches"] * schedule["cycles_per_batch"] == 1860
assert schedule["minimum_cycles"] == 1800
assert (schedule["batches"] - 1) * schedule["start_interval_seconds"] >= 1800
assert len(config["persistent_definitions"]) == 6
assert [row["batch"] for row in config["persistent_definitions"]] == [5, 10, 15, 20, 25, 30]

for role in ("d81", "elf"):
    row = config["released_product"][role]
    path = root / row["path"]
    data = path.read_bytes()
    assert len(data) == row["bytes"]
    assert hashlib.sha256(data).hexdigest() == row["sha256"]

sys.path.insert(0, str(root / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
truth = ElfTruth.read(
    root / config["released_product"]["elf"]["path"],
    llvm_readobj=root / "tools/llvm-mos/bin/llvm-readobj")
for symbol, expected in (
    ("gc_runs", config["addresses"]["gc_runs"]),
    ("mem_oom", config["addresses"]["mem_oom"]),
    ("gc_badobj", config["addresses"]["gc_badobj"]),
    ("lisp65_c2_phase_scratch", 0xC0C6),
):
    assert truth.symbol(symbol).value == expected, (symbol, truth.symbol(symbol).value, expected)
assert config["addresses"]["trace"] == truth.symbol("lisp65_c2_phase_scratch").value + 302

binary = root / "build/equivalence/dialect-v2-equivalence-check"
assert binary.is_file()
host = {}
for mode in ("vm", "lcc"):
    command = [str(binary), mode, str(root / fixture_path)]
    if mode == "lcc":
        command += ["--preload", str(root / "lib/lcc.lisp")]
    result = subprocess.run(
        command, cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=180, check=False)
    assert result.returncode == 0, (mode, result.stdout[-4000:])
    assert "=> %s" in result.stdout and "=> %sr" in result.stdout, (
        mode, result.stdout[-4000:])
    host[mode] = {
        "status": "passed-exact-helper-definitions-compiled",
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "lines": len(result.stdout.splitlines()),
    }

session_result = subprocess.run(
    ["make", "--no-print-directory", "c2-product-session-host-check"],
    cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    timeout=180, check=False)
assert session_result.returncode == 0, session_result.stdout[-4000:]
assert (
    "c2-product-session-host: PASS cases=2 appends=3"
    in session_result.stdout
    and "mutations=12" in session_result.stdout
), session_result.stdout[-4000:]
host["product_session"] = {
    "status": "passed-real-emitter-append-resolution-materialization-lane",
    "stdout_sha256":
        hashlib.sha256(session_result.stdout.encode()).hexdigest(),
    "cases": 2,
    "persistent_appends": 3,
    "mutations_rejected": 12,
}

value = {
    "format": "lisp65-c2.2-v1.2.4-post-release-soak-preparation-v1",
    "recorded_on": date.today().isoformat(),
    "status": "prepared-host-green-nonpromotable-soak",
    "schedule": {
        **schedule,
        "bound_cycles": schedule["batches"] * schedule["cycles_per_batch"],
        "bound_start_span_seconds":
            (schedule["batches"] - 1) * schedule["start_interval_seconds"],
    },
    "host_dry_run": host,
    "released_product": config["released_product"],
    "target_ELF_witnesses": {
        name: f"0x{config['addresses'][name]:08x}"
        for name in ("gc_runs", "mem_oom", "gc_badobj", "trace")
    },
    "safety": {
        "product_bytes_changed": 0,
        "product_links": 0,
        "cold_reset_and_fresh_BASIC_gate": True,
        "ftp_progress_guard_seconds": 120,
        "first_anomaly_action": "stop feature activity, capture only",
        "readback_map": ["trace", "c2d_header", "place_row", "C2J", "phase_owner", "GC counters"],
    },
    "authority": {
        "config": bind(config_path),
        "contract": bind(contract_path),
        "roadmap": bind(plan_path),
        "host_fixture": bind(fixture_path),
        "runner": bind(script_path),
    },
    "claim_limit": config["claim_limit"],
}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
print(
    "c2-v124-post-release-soak: PREPARE PASS "
    "cycles=1860 span=1800s helper-compilers=2/2 session-host=2-cases")
PY
}

bind_preparation
[ "$ACTION" != prepare ] || exit 0

if [ "$ACTION" = dry-run ]; then
  jq -r '.setup[].form,
    .batch.work_form,
    .batch.require_form,
    .batch.status_form,
    .persistent_definitions[] | if type == "object" then .form,.call else . end' \
    "$CONFIG" |
  while IFS= read -r form; do
    [ -n "$form" ] || continue
    OUT_DIR="$OUT/dry-run" PREFIX=soak-form TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --dry-run --verified-input --form "$form"
  done
  echo "DRY-RUN: cold reset; prove fresh BASIC; guarded FTP; 31x60 cycles over 1800s"
  echo "DRY-RUN: stop on first anomaly and capture trace/header/place/C2J/GC map"
  exit 0
fi

if [ "$ACTION" = verify ]; then
  python3 - "$CONFIG" "$PREPARATION" "$RECEIPT" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
config_path, preparation_path, receipt_path = map(Path, sys.argv[1:])
config = json.loads(config_path.read_text())
preparation = json.loads(preparation_path.read_text())
receipt = json.loads(receipt_path.read_text())
assert preparation["status"] == "prepared-host-green-nonpromotable-soak"
assert receipt["status"] == "passed-clean-1860-cycle-30-minute-soak"
assert receipt["result"]["completed_cycles"] >= config["schedule"]["minimum_cycles"]
assert receipt["result"]["elapsed_seconds"] >= config["schedule"]["minimum_session_seconds"]
assert receipt["result"]["semantic_mismatches"] == 0
assert receipt["result"]["mem_oom"] == 0
assert receipt["result"]["gc_badobj_delta"] == 0
assert receipt["result"]["gc_runs_delta"] > 0
assert receipt["result"]["all_product_completion_CRCs_passed"]
assert receipt["result"]["require_rows"] == config["schedule"]["batches"]
assert receipt["result"]["persistent_definitions"] == len(config["persistent_definitions"])
print(
    "c2-v124-post-release-soak: VERIFY PASS "
    f"cycles={receipt['result']['completed_cycles']} "
    f"seconds={receipt['result']['elapsed_seconds']} "
    f"gc={receipt['result']['gc_runs_delta']}")
PY
  exit 0
fi

[ -x "$M65" ] && [ -x "$FTP" ] || {
  echo "missing MEGA65 tools" >&2
  exit 3
}
[ -c "$DEVICE" ] || {
  echo "missing JTAG serial device: $DEVICE" >&2
  exit 3
}
[ ! -e "$RECEIPT" ] || {
  echo "soak hardware receipt already exists" >&2
  exit 3
}

mkdir -p "$OUT"

run_m65() {
  timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" "$@"
}

readback() {
  rb_start=$1
  rb_bytes=$2
  rb_path=$3
  rb_end=$((rb_start + rb_bytes))
  mkdir -p "$(dirname "$rb_path")"
  run_m65 --memsave \
    "0x$(printf '%08x' "$rb_start"):0x$(printf '%08x' "$rb_end")=$rb_path"
}

capture_screen() {
  prefix=$1
  run_m65 --screenshot="$OUT/$prefix.png" > "$OUT/$prefix.ansi.txt"
  python3 - "$OUT/$prefix.ansi.txt" "$OUT/$prefix.txt" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_text(errors="ignore")
Path(sys.argv[2]).write_text(
    re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", raw), encoding="utf-8")
PY
}

fail_if_red() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
try:
    repl_screen_check.check_fail_closed_frame(Path(sys.argv[1]))
except repl_screen_check.CheckError as error:
    print(error.message)
    raise SystemExit(error.code)
PY
}

fresh_start_gate() {
  run_m65 -F
  sleep 3
  poll=0
  while [ "$poll" -lt 30 ]; do
    capture_screen fresh-start
    fail_if_red "$OUT/fresh-start.png"
    if grep -Fq 'BASIC 65' "$OUT/fresh-start.txt" &&
       grep -Fq 'READY.' "$OUT/fresh-start.txt" &&
       ! grep -Fq 'lisp65>' "$OUT/fresh-start.txt"; then
      return
    fi
    sleep 1
    poll=$((poll + 1))
  done
  echo "soak FIRST RED: fresh BASIC startup state not proven" >&2
  exit 3
}

ftp_with_progress_guard() {
  media=$1
  remote=$2
  log=$OUT/media-upload.log
  readback_path=$OUT/uploaded-media.d81
  : > "$log"
  stdbuf -oL -eL "$FTP" -0 5 -F -l "$DEVICE" -s 2000000 -y \
    -c "put $media $remote" \
    -c "get $remote $readback_path" \
    -c "mount $remote" -c exit > "$log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true' HUP INT TERM EXIT
  last_size=-1
  last_progress=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    size=$(wc -c < "$log")
    now=$(date +%s)
    if [ "$size" -ne "$last_size" ]; then
      last_size=$size
      last_progress=$now
    elif [ $((now - last_progress)) -ge "$FTP_STALL_LIMIT" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      trap - HUP INT TERM EXIT
      echo "soak FIRST RED: FTP stalled for ${FTP_STALL_LIMIT}s" >&2
      exit 124
    fi
  done
  wait "$pid"
  trap - HUP INT TERM EXIT
  cmp "$media" "$readback_path"
}

wait_for_repl() {
  poll=0
  while [ "$poll" -lt 120 ]; do
    capture_screen product-boot
    fail_if_red "$OUT/product-boot.png"
    if grep -Fq 'lisp65>' "$OUT/product-boot.txt"; then
      grep -Fq 'WORKBENCH 1.2.4' "$OUT/product-boot.txt"
      return
    fi
    sleep 1
    poll=$((poll + 1))
  done
  echo "soak FIRST RED: v1.2.4 REPL absent after 120s" >&2
  exit 3
}

capture_state() {
  prefix=$1
  readback "$(jq '.addresses.trace' "$CONFIG")" 2 "$OUT/$prefix-trace.bin"
  readback "$(jq '.addresses.c2d_header' "$CONFIG")" \
    "$(jq '.addresses.c2d_header_bytes' "$CONFIG")" "$OUT/$prefix-c2d-header.bin"
  readback "$(jq '.addresses.place_row' "$CONFIG")" \
    "$(jq '.addresses.place_row_bytes' "$CONFIG")" "$OUT/$prefix-place-row.bin"
  readback "$(jq '.addresses.c2j' "$CONFIG")" \
    "$(jq '.addresses.c2j_bytes' "$CONFIG")" "$OUT/$prefix-c2j.bin"
  readback "$(jq '.addresses.phase_owner' "$CONFIG")" 1 "$OUT/$prefix-phase-owner.bin"
  readback "$(jq '.addresses.gc_runs' "$CONFIG")" 2 "$OUT/$prefix-gc-runs.bin"
  readback "$(jq '.addresses.mem_oom' "$CONFIG")" 1 "$OUT/$prefix-mem-oom.bin"
  readback "$(jq '.addresses.gc_badobj' "$CONFIG")" 2 "$OUT/$prefix-gc-badobj.bin"
}

anomaly() {
  prefix=$1
  detail=$2
  echo "soak ANOMALY: $detail" >&2
  capture_screen "$prefix-screen" || true
  capture_state "$prefix" || true
  python3 - "$CONFIG" "$PREPARATION" "$OUT" "$prefix" "$detail" <<'PY'
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
config_path, prep_path, out_path = map(Path, sys.argv[1:4])
prefix, detail = sys.argv[4:]
value = {
    "format": "lisp65-c2.2-v1.2.4-post-release-soak-anomaly-v1",
    "recorded_on": date.today().isoformat(),
    "status": "stopped-on-first-anomaly",
    "detail": detail,
    "capture_prefix": prefix,
    "preparation": {
        "path": prep_path.as_posix(),
        "sha256": hashlib.sha256(prep_path.read_bytes()).hexdigest(),
    },
    "claim_limit": json.loads(config_path.read_text())["claim_limit"],
}
(out_path / "first-anomaly.json").write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
  exit 9
}

run_exact() {
  prefix=$1
  form=$2
  expected=$3
  if ! OUT_DIR=$OUT PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --wait 1 \
        --expect "$expected" --expect-poll "$EXPECT_POLL" --form "$form"; then
    anomaly "$prefix" "form failed or returned a non-exact result: $form"
  fi
  if ! fail_if_red "$OUT/$prefix.png"; then
    anomaly "$prefix" "red fail-closed frame after form: $form"
  fi
}

run_status() {
  prefix=$1
  expected_cycles=$2
  form=$(jq -r '.batch.status_form' "$CONFIG")
  if ! OUT_DIR=$OUT PREFIX="$prefix" TIMEOUT_SEC=$TIMEOUT \
      scripts/hw-jtag-repl.sh --verified-input --wait 1 --form "$form"; then
    anomaly "$prefix" "status form transport failed"
  fi
  if ! fail_if_red "$OUT/$prefix.png"; then
    anomaly "$prefix" "red fail-closed frame at status"
  fi
  if ! python3 - "$OUT/$prefix.txt" "$form" "$expected_cycles" "$OUT/$prefix-status.json" <<'PY'
from pathlib import Path
import json
import re
import sys
sys.path.insert(0, "tools/host-lisp")
import repl_screen_check
screen, form, expected, output = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), Path(sys.argv[4])
repl_screen_check.check_latest_result(screen, form, None)
matches = re.findall(
    r"^\s*\((\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\)\s*$",
    screen.read_text(errors="replace"), re.M)
if not matches:
    raise SystemExit("status tuple absent")
cycles, mismatches, gc_lo, gc_hi, oom, bad_lo, bad_hi = map(int, matches[-1])
if cycles != expected:
    raise SystemExit(f"cycle counter mismatch: {cycles} != {expected}")
if mismatches != 0 or oom != 0:
    raise SystemExit(f"status anomaly: mismatches={mismatches} oom={oom}")
value = {
    "cycles": cycles,
    "mismatches": mismatches,
    "gc_runs": gc_lo | (gc_hi << 8),
    "mem_oom": oom,
    "gc_badobj": bad_lo | (bad_hi << 8),
}
output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
  then
    anomaly "$prefix" "status tuple absent or anomalous"
  fi
}

check_quiescent() {
  prefix=$1
  python3 - "$CONFIG" "$OUT" "$prefix" <<'PY'
from pathlib import Path
import json
import struct
import sys
config = json.loads(Path(sys.argv[1]).read_text())
out, prefix = Path(sys.argv[2]), sys.argv[3]
header = (out / f"{prefix}-c2d-header.bin").read_bytes()
c2j = (out / f"{prefix}-c2j.bin").read_bytes()
owner = (out / f"{prefix}-phase-owner.bin").read_bytes()
oom = (out / f"{prefix}-mem-oom.bin").read_bytes()
assert len(header) == 48 and header[:4] == b"C2D\0"
assert struct.unpack_from("<H", header, 8)[0] == config["quiescent_invariants"]["transient_handle_watermark_u16"]
assert c2j == bytes(config["addresses"]["c2j_bytes"])
assert owner == bytes([config["quiescent_invariants"]["phase_owner"]])
assert oom == bytes([config["quiescent_invariants"]["mem_oom"]])
PY
}

media=$(jq -r '.released_product.d81.path' "$CONFIG")
remote=$(jq -r '.released_product.remote_media' "$CONFIG")
fresh_start_gate
readback 0x0ffd3632 4 "$OUT/device-core-id.bin"
ftp_with_progress_guard "$media" "$remote"
wait_for_repl

jq -c '.setup[]' "$CONFIG" |
while IFS= read -r row; do
  id=$(printf '%s' "$row" | jq -r '.id')
  form=$(printf '%s' "$row" | jq -r '.form')
  expected=$(printf '%s' "$row" | jq -r '.expected')
  run_exact "setup-$id" "$form" "$expected"
done

capture_state baseline
check_quiescent baseline || anomaly baseline "baseline is not quiescent"
date +%s > "$OUT/session-start-epoch.txt"
date +%s%N > "$OUT/session-start-ns.txt"
start=$(cat "$OUT/session-start-epoch.txt")
batches=$(jq '.schedule.batches' "$CONFIG")
cycles_per_batch=$(jq '.schedule.cycles_per_batch' "$CONFIG")
interval=$(jq '.schedule.start_interval_seconds' "$CONFIG")
batch=1

while [ "$batch" -le "$batches" ]; do
  target=$((start + (batch - 1) * interval))
  now=$(date +%s)
  if [ "$target" -gt "$now" ]; then
    sleep $((target - now))
  fi
  printf 'SOAK batch %02d/%02d start elapsed=%ss\\n' \
    "$batch" "$batches" "$(( $(date +%s) - start ))"

  definition=$(jq -c \
    ".persistent_definitions[] | select(.batch == $batch)" "$CONFIG")
  if [ -n "$definition" ]; then
    run_exact "batch-$(printf '%02d' "$batch")-definition" \
      "$(printf '%s' "$definition" | jq -r '.form')" \
      "$(printf '%s' "$definition" | jq -r '.expected')"
    run_exact "batch-$(printf '%02d' "$batch")-definition-call" \
      "$(printf '%s' "$definition" | jq -r '.call')" \
      "$(printf '%s' "$definition" | jq -r '.call_expected')"
  fi

  prefix="batch-$(printf '%02d' "$batch")-pre"
  capture_state "$prefix"
  check_quiescent "$prefix" || anomaly "$prefix" "pre-batch state is not quiescent"

  run_exact "batch-$(printf '%02d' "$batch")-require" \
    "$(jq -r '.batch.require_form' "$CONFIG")" \
    "$(jq -r '.batch.require_expected' "$CONFIG")"
  capture_state "batch-$(printf '%02d' "$batch")-post-require"
  check_quiescent "batch-$(printf '%02d' "$batch")-post-require" ||
    anomaly "batch-$(printf '%02d' "$batch")-post-require" \
      "require left non-quiescent state"
  cmp "$OUT/$prefix-c2d-header.bin" \
    "$OUT/batch-$(printf '%02d' "$batch")-post-require-c2d-header.bin" ||
    anomaly "batch-$(printf '%02d' "$batch")-post-require" \
      "idempotent require changed the C2D header"
  cmp "$OUT/$prefix-place-row.bin" \
    "$OUT/batch-$(printf '%02d' "$batch")-post-require-place-row.bin" ||
    anomaly "batch-$(printf '%02d' "$batch")-post-require" \
      "idempotent require changed the place row"

  run_exact "batch-$(printf '%02d' "$batch")-work" \
    "$(jq -r '.batch.work_form' "$CONFIG")" \
    "$(jq -r '.batch.work_expected' "$CONFIG")"
  post="batch-$(printf '%02d' "$batch")-post"
  capture_state "$post"
  check_quiescent "$post" || anomaly "$post" "post-batch state is not quiescent"
  cmp "$OUT/$prefix-c2d-header.bin" "$OUT/$post-c2d-header.bin" ||
    anomaly "$post" "transient cycles changed the persistent C2D header"
  cmp "$OUT/$prefix-place-row.bin" "$OUT/$post-place-row.bin" ||
    anomaly "$post" "transient cycles changed the place row"

  expected_cycles=$((batch * cycles_per_batch))
  run_status "batch-$(printf '%02d' "$batch")-status" "$expected_cycles"
  echo "$batch $(date +%s) $expected_cycles" >> "$OUT/batch-timeline.txt"
  batch=$((batch + 1))
done

date +%s%N > "$OUT/session-end-ns.txt"
capture_state final
check_quiescent final || anomaly final "final state is not quiescent"
capture_screen final-screen
fail_if_red "$OUT/final-screen.png" || anomaly final "red frame at final capture"

python3 - "$CONFIG" "$CONTRACT" "$PLAN" "$PREPARATION" "$RECEIPT" "$OUT" "$0" <<'PY'
from __future__ import annotations
from datetime import date
import hashlib
import json
from pathlib import Path
import struct
import sys

config_path, contract_path, plan_path, preparation_path, receipt_path, out_path, script_path = (
    Path(value) for value in sys.argv[1:])
config = json.loads(config_path.read_text())

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def bind(path: Path, address: int | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value

statuses = [
    json.loads(path.read_text())
    for path in sorted(out_path.glob("batch-*-status-status.json"))]
assert len(statuses) == config["schedule"]["batches"]
assert statuses[-1]["cycles"] == (
    config["schedule"]["batches"] * config["schedule"]["cycles_per_batch"])
assert all(row["mismatches"] == 0 and row["mem_oom"] == 0 for row in statuses)
assert all(
    right["cycles"] - left["cycles"] == config["schedule"]["cycles_per_batch"]
    for left, right in zip(statuses, statuses[1:]))

start_ns = int((out_path / "session-start-ns.txt").read_text())
end_ns = int((out_path / "session-end-ns.txt").read_text())
elapsed = (end_ns - start_ns) // 1_000_000_000
assert elapsed >= config["schedule"]["minimum_session_seconds"]

baseline_gc = struct.unpack("<H", (out_path / "baseline-gc-runs.bin").read_bytes())[0]
final_gc = struct.unpack("<H", (out_path / "final-gc-runs.bin").read_bytes())[0]
baseline_bad = struct.unpack("<H", (out_path / "baseline-gc-badobj.bin").read_bytes())[0]
final_bad = struct.unpack("<H", (out_path / "final-gc-badobj.bin").read_bytes())[0]
final_oom = (out_path / "final-mem-oom.bin").read_bytes()[0]
assert final_gc > baseline_gc
assert final_bad == baseline_bad
assert final_oom == 0

timeline = [
    tuple(map(int, row.split()))
    for row in (out_path / "batch-timeline.txt").read_text().splitlines()]
assert len(timeline) == config["schedule"]["batches"]
assert timeline[-1][1] - timeline[0][1] >= config["schedule"]["minimum_session_seconds"]

value = {
    "format": "lisp65-c2.2-v1.2.4-post-release-soak-hardware-v1",
    "recorded_on": date.today().isoformat(),
    "status": "passed-clean-1860-cycle-30-minute-soak",
    "device": {
        "core_register": bind(out_path / "device-core-id.bin", 0x0FFD3632),
    },
    "released_product": config["released_product"],
    "result": {
        "completed_cycles": statuses[-1]["cycles"],
        "semantic_mismatches": statuses[-1]["mismatches"],
        "elapsed_seconds": elapsed,
        "batches": len(statuses),
        "require_rows": len(statuses),
        "persistent_definitions": len(config["persistent_definitions"]),
        "gc_runs_before": baseline_gc,
        "gc_runs_after": final_gc,
        "gc_runs_delta": final_gc - baseline_gc,
        "gc_badobj_before": baseline_bad,
        "gc_badobj_after": final_bad,
        "gc_badobj_delta": final_bad - baseline_bad,
        "mem_oom": final_oom,
        "all_product_completion_CRCs_passed": True,
        "completion_CRC_basis": (
            "Every completed nested eval crosses the released C2-lite "
            "append/read path whose four transaction boundaries accept only "
            "after content-defined target CRC convergence; any failed "
            "completion returns an error and stops this runner."
        ),
        "c2j_clear_after_every_batch": True,
        "phase_owner_none_after_every_batch": True,
        "transient_watermark_quiescent_after_every_batch": True,
        "persistent_header_and_place_row_unchanged_by_each_transient_batch": True,
        "idempotent_require_header_and_row_unchanged_each_batch": True,
    },
    "interpretation": {
        "pre_registered_outcome": "bounded-exoneration-at-soak-scale",
        "chip_ram_L10_variant": "retired-at-1860-cycle-30-minute-scale",
        "intermittent_family": "not-closed",
        "next_suspect": "session-accumulated state rather than Chip-RAM transport",
    },
    "evidence": {
        "timeline": bind(out_path / "batch-timeline.txt"),
        "final_screen_text": bind(out_path / "final-screen.txt"),
        "final_screen_png": bind(out_path / "final-screen.png"),
        "final_trace": bind(out_path / "final-trace.bin", config["addresses"]["trace"]),
        "final_c2d_header": bind(out_path / "final-c2d-header.bin", config["addresses"]["c2d_header"]),
        "final_place_row": bind(out_path / "final-place-row.bin", config["addresses"]["place_row"]),
        "final_c2j": bind(out_path / "final-c2j.bin", config["addresses"]["c2j"]),
        "final_gc_runs": bind(out_path / "final-gc-runs.bin", config["addresses"]["gc_runs"]),
    },
    "execution_accounting": {
        "physical_device_sessions": 1,
        "cold_resets": 1,
        "product_links": 0,
        "product_bytes_changed": 0,
        "promotable_candidates": 0,
    },
    "authority": {
        "config": bind(config_path),
        "contract": bind(contract_path),
        "roadmap": bind(plan_path),
        "preparation": bind(preparation_path),
        "runner": bind(script_path),
    },
    "claim_limit": config["claim_limit"],
}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
print(
    "c2-v124-post-release-soak: PASS "
    f"cycles={value['result']['completed_cycles']} "
    f"seconds={elapsed} gc={value['result']['gc_runs_delta']} "
    "mismatch=0")
PY

"$0" verify
