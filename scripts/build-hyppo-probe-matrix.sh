#!/bin/sh
# Build HYPPO DOS probe variants for real MEGA65 hardware.
#
# Variants isolate case, Z length with/without NUL, and 8.3 naming.
set -eu

cd "$(dirname "$0")/.."

cc="${CC_M65:-tools/llvm-mos/bin/mos-mega65-clang}"
outdir="${HYPPO_PROBE_OUTDIR:-build}"

[ -x "$cc" ] || { echo "Fehler: Compiler nicht gefunden/ausfuehrbar: $cc" >&2; exit 3; }
mkdir -p "$outdir"

build_one() {
  label="$1"
  name="$2"
  len="$3"
  out="$outdir/hyppo-probe-$label.prg"

  printf '==> %s  name=%s zlen=%s\n' "$out" "$name" "$len"
  "$cc" -Os -Wall -Isrc \
    -DHYPPO_PROBE_NAME="\"$name\"" \
    -DHYPPO_PROBE_NAMELEN="$len" \
    scripts/mega65-hyppo-load-probe.c -o "$out"
  printf '    %s bytes\n' "$(stat -c%s "$out")"
}

build_one demolib-l6       demolib     6
build_one demolib-l7       demolib     7
build_one demolib-l8       demolib     8
build_one DEMOLIB-l6       DEMOLIB     6
build_one DEMOLIB-l7       DEMOLIB     7
build_one DEMOLIB-l8       DEMOLIB     8
build_one demolib-lsp-l11  demolib.lsp 11
build_one demolib-lsp-l12  demolib.lsp 12
build_one DEMOLIB-LSP-l11  DEMOLIB.LSP 11
build_one DEMOLIB-LSP-l12  DEMOLIB.LSP 12

cat <<'EOF'

SD-Testdateien vorbereiten, je nach Variante:
  printf '(defun sq (x) (* x x))\n' > demolib
  cp demolib demolib.lsp
  tools/m65tools/mega65_ftp -F -e \
    -c "put demolib demolib" \
    -c "put demolib DEMOLIB" \
    -c "put demolib.lsp demolib.lsp" \
    -c "put demolib.lsp DEMOLIB.LSP" \
    -c "exit"

Varianten starten:
  tools/m65tools/etherload -r build/hyppo-probe-demolib-l7.prg
  scripts/run-on-mega65.sh --dry-run --run build/hyppo-probe-demolib-l7.prg

Farbcodes stehen in scripts/mega65-hyppo-load-probe.c.
Wichtig: run-on-mega65.sh --run ist ebenfalls etherload -r; es ist kein anderer DOS-Startpfad.
EOF
