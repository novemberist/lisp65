#!/bin/sh
# Build the canonical guarded-overlay Workbench package. The PRG stays resident,
# blob.bin is the Bank-5 stdlib/boot preload; overlays.bin lives in Attic RAM.
set -eu

cd "$(dirname "$0")/.."

ship_dir="${MVP_VM_SHIP_DIR:-build/ship-candidate}"
ship_prg="${MVP_VM_SHIP_PRG:-$ship_dir/lisp65-mvp-workbench.prg}"
ship_blob="${MVP_VM_SHIP_BLOB:-$ship_dir/lisp65-mvp-workbench.blob.bin}"
ship_overlays="${MVP_VM_SHIP_OVERLAYS:-$ship_dir/lisp65-mvp-workbench.overlays.bin}"
ship_d81="${MVP_VM_SHIP_D81:-$ship_dir/lisp65-mvp-workbench.d81}"
manifest="${MVP_VM_SHIP_MANIFEST:-$ship_dir/manifest.json}"
canonical_manifest="$ship_dir/manifest.json"
build_target="${MVP_VM_SHIP_BUILD_TARGET:-workbench-overlay-stack-guard}"
guard_dir="${WORKBENCH_OVERLAY_GUARD_DIR:-build/products/workbench/overlay-stack-guard}"
footprint_src="${WORKBENCH_OVERLAY_GUARD_FOOTPRINT:-$guard_dir/footprint-audit.json}"
footprint_copy="${MVP_VM_SHIP_FOOTPRINT:-$ship_dir/mvp-vm-stdlib-footprint.txt}"
source_prg="${WORKBENCH_OVERLAY_GUARD_RESIDENT_PRG:-$guard_dir/lisp65-workbench-resident.prg}"
source_blob="${WORKBENCH_OVERLAY_GUARD_PRELOAD:-$guard_dir/stdlib-with-overlay.ext.bin}"
source_stage_manifest="${WORKBENCH_OVERLAY_GUARD_STAGE_MANIFEST:-$guard_dir/stage-manifest.json}"
source_overlays="${WORKBENCH_OVERLAY_GUARD_RUNTIME_IMAGE:-$guard_dir/lisp65-mvp-workbench.overlays.bin}"
source_overlays_manifest="${WORKBENCH_OVERLAY_GUARD_RUNTIME_MANIFEST:-$guard_dir/runtime-overlays-manifest.json}"
source_abi_contract="${WORKBENCH_OVERLAY_GUARD_ABI_CONTRACT:-$guard_dir/resolved-profile.txt}"
source_stdlib_manifest="${WORKBENCH_STDLIB_MANIFEST:-build/bytecode/profiles/workbench/stdlib-p0.manifest.json}"
d81_manifest="${MVP_VM_SHIP_D81_MANIFEST:-$ship_dir/workbench-d81-manifest.txt}"
stdlib_manifest="$ship_dir/stdlib-artifact-manifest.json"
profile_report="$ship_dir/resolved-profile.txt"
toolchain_report="$ship_dir/toolchain-report.txt"
skip_build="${MVP_VM_SHIP_SKIP_BUILD:-0}"
reproducible_paths="${MVP_VM_SHIP_REPRODUCIBLE_PATHS:-0}"

case "$skip_build" in
  0|1) ;;
  *) echo "error: MVP_VM_SHIP_SKIP_BUILD must be 0 or 1" >&2; exit 2 ;;
esac
case "$reproducible_paths" in
  0|1) ;;
  *) echo "error: MVP_VM_SHIP_REPRODUCIBLE_PATHS must be 0 or 1" >&2; exit 2 ;;
esac
[ "$manifest" = "$canonical_manifest" ] || {
  echo "Fehler: Ship-v5-Manifest muss $canonical_manifest heissen" >&2
  exit 2
}

mkdir -p "$ship_dir"
# AP3 migration cleanup: these were temporary D81 inputs before the builder
# switched to an automatically cleaned work directory.
rm -f "$ship_dir/workbench-slot.bin" "$ship_dir/workbench-demo-source.seq"

if [ "$skip_build" = 0 ]; then
  echo "==> baue MVP-Workbench-Artefakte"
  make "$build_target"
  make bytecode-p0-ide-extra-lib-artifacts bytecode-p0-m65d-lib-artifacts
else
  echo "==> verwende bereitgestellte MVP-Workbench-Artefakte"
fi
WORKBENCH_SHIP_D81="$ship_d81" \
  WORKBENCH_SHIP_D81_MANIFEST="$d81_manifest" \
  sh scripts/build-workbench-d81.sh

if [ "$reproducible_paths" = 1 ]; then
  python3 - "$d81_manifest" "$ship_d81" "$(basename "$ship_d81")" <<'PY'
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
source_path = sys.argv[2]
display_path = sys.argv[3]
content = manifest_path.read_text(encoding="utf-8")
if source_path not in content:
    raise SystemExit(f"Fehler: D81-Pfad fehlt im Manifest: {source_path}")
manifest_path.write_text(content.replace(source_path, display_path), encoding="utf-8")
PY
fi

[ -f "$source_prg" ] || { echo "Fehler: PRG fehlt: $source_prg" >&2; exit 3; }
[ -f "$source_blob" ] || { echo "Fehler: Stdlib-Blob fehlt: $source_blob" >&2; exit 3; }
[ -f "$source_overlays" ] || { echo "Fehler: Runtime-Overlay-Katalog fehlt: $source_overlays" >&2; exit 3; }
[ -f "$source_overlays_manifest" ] || { echo "Fehler: Runtime-Overlay-Manifest fehlt: $source_overlays_manifest" >&2; exit 3; }
[ -f "$ship_d81" ] || { echo "Fehler: Workbench-D81 fehlt: $ship_d81" >&2; exit 3; }
[ -f "$footprint_src" ] || { echo "Fehler: Footprint-Report fehlt: $footprint_src" >&2; exit 3; }
[ -f "$source_stdlib_manifest" ] || { echo "Fehler: Stdlib-Manifest fehlt: $source_stdlib_manifest" >&2; exit 3; }
[ -f "$source_stage_manifest" ] || { echo "Fehler: Guard-Stage-Manifest fehlt: $source_stage_manifest" >&2; exit 3; }
[ -f "$source_abi_contract" ] || { echo "Fehler: Guard-ABI-Vertrag fehlt: $source_abi_contract" >&2; exit 3; }

cp "$source_prg" "$ship_prg"
cp "$source_blob" "$ship_blob"
cp "$source_overlays" "$ship_overlays"
cp "$footprint_src" "$footprint_copy"
cp "$source_stdlib_manifest" "$stdlib_manifest"
cp "$source_abi_contract" "$profile_report"

{
  echo "format=lisp65-toolchain-report-v1"
  printf 'python='; python3 --version 2>&1 | sed -n '1p'
  printf 'make='; make --version 2>&1 | sed -n '1p'
  printf 'host_cc='; "${HOSTCC:-cc}" --version 2>&1 | sed -n '1p'
  printf 'llvm_mos='; tools/llvm-mos/bin/mos-mega65-clang --version 2>&1 | sed -n '1p'
  c1541_path="$(command -v c1541 || true)"
  if [ -n "$c1541_path" ]; then
    echo "c1541_path=$c1541_path"
    if command -v rpm >/dev/null 2>&1; then
      printf 'c1541_package='; rpm -qf --qf '%{NAME} %{VERSION}-%{RELEASE}\n' "$c1541_path" 2>/dev/null || echo unknown
    else
      echo "c1541_package=unknown"
    fi
    sha256sum "$c1541_path"
  else
    echo "c1541=missing"
  fi
  for tool in tools/llvm-mos/bin/mos-mega65-clang tools/m65tools/etherload tools/m65tools/mega65_ftp; do
    if [ -f "$tool" ]; then sha256sum "$tool"; else echo "missing=$tool"; fi
  done
} > "$toolchain_report"

python3 tools/host-lisp/workbench_ship.py candidate \
  --dir "$ship_dir" --stage-manifest "$source_stage_manifest" \
  --runtime-overlay-manifest "$source_overlays_manifest"

echo "==> geschrieben:"
echo "    $ship_prg"
echo "    $ship_blob"
echo "    $ship_overlays"
echo "    $ship_d81"
echo "    $footprint_copy"
echo "    $d81_manifest"
echo "    $manifest"
