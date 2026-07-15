#!/bin/sh
# Package the verified historical interim artifacts as a reference bundle.
set -eu

cd "$(dirname "$0")/.."

legacy_ship_dir="${LEGACY_INTERIM_SHIP_DIR:-build/legacy-interim-ship}"
release_root="${SHIP_RELEASE_ROOT:-build/release/legacy-interim/lisp65-legacy-interim}"
tarball="${SHIP_RELEASE_TARBALL:-build/release/legacy-interim/lisp65-legacy-interim.tar.gz}"
base="$(basename "$release_root")"

require_file() {
  if [ ! -f "$1" ]; then
    echo "Fehler: Release-Datei fehlt: $1" >&2
    echo "Hinweis: zuerst 'make legacy-interim-ship-check' ausfuehren." >&2
    exit 3
  fi
}

copy_file() {
  src="$1"
  dst="$2"
  mode="${3:-0644}"
  require_file "$src"
  mkdir -p "$(dirname "$release_root/$dst")"
  install -m "$mode" "$src" "$release_root/$dst"
}

rm -rf "$release_root"
mkdir -p "$release_root/artifacts" "$release_root/docs" "$release_root/scripts"

copy_file "$legacy_ship_dir/lisp65-interim.prg" artifacts/lisp65-legacy-interim.prg
copy_file "$legacy_ship_dir/lisp65-interim.d81" artifacts/lisp65-legacy-interim.d81
copy_file "$legacy_ship_dir/lisp65-f011-interim.prg" artifacts/lisp65-f011-legacy-interim.prg
copy_file "$legacy_ship_dir/lisp65-f011-interim.d81" artifacts/lisp65-f011-legacy-interim.d81
copy_file "$legacy_ship_dir/lisp65-stdlib.d81" artifacts/lisp65-legacy-stdlib.d81
copy_file "$legacy_ship_dir/load-stdlib-commands.txt" docs/load-stdlib-commands.txt
copy_file "$legacy_ship_dir/manifest.txt" docs/manifest.txt
copy_file "$legacy_ship_dir/f011-manifest.txt" docs/f011-manifest.txt
copy_file "$legacy_ship_dir/stdlib-d81-manifest.txt" docs/stdlib-d81-manifest.txt
copy_file "$legacy_ship_dir/footprint-report.txt" docs/footprint-report.txt
copy_file "$legacy_ship_dir/full-embed-fit-report.txt" docs/full-embed-fit-report.txt
copy_file "$legacy_ship_dir/f011-stdlib-profile-matrix.txt" docs/f011-stdlib-profile-matrix.txt
copy_file "$legacy_ship_dir/ship-readiness.txt" docs/ship-readiness.txt
copy_file docs/archive/pre-1.0/planning/interim-ship.md docs/archive/pre-1.0/planning/interim-ship.md
copy_file docs/archive/pre-1.0/planning/f011-stdlib-binding-gap.md docs/archive/pre-1.0/planning/f011-stdlib-binding-gap.md
copy_file scripts/run-on-mega65.sh scripts/run-on-mega65.sh 0755

cat > "$release_root/run-legacy-interim.sh" <<'EOF'
#!/bin/sh
set -eu
cd "$(dirname "$0")"
tools="${M65TOOLS:-tools/m65tools}"
set -- --tools "$tools" --run --mount artifacts/lisp65-legacy-interim.d81
[ -n "${MEGA65_IP:-}" ] && set -- "$@" --ip "$MEGA65_IP"
[ "${DRY_RUN:-0}" = "1" ] && set -- "$@" --dry-run
set -- "$@" artifacts/lisp65-legacy-interim.prg
exec sh scripts/run-on-mega65.sh "$@"
EOF
chmod 0755 "$release_root/run-legacy-interim.sh"

cat > "$release_root/run-f011-stdlib.sh" <<'EOF'
#!/bin/sh
set -eu
cd "$(dirname "$0")"
tools="${M65TOOLS:-tools/m65tools}"
echo "Stdlib-Load-Kommandos nach dem Start zeilenweise eingeben: docs/load-stdlib-commands.txt"
set -- --tools "$tools" --run --mount artifacts/lisp65-legacy-stdlib.d81
[ -n "${MEGA65_IP:-}" ] && set -- "$@" --ip "$MEGA65_IP"
[ "${DRY_RUN:-0}" = "1" ] && set -- "$@" --dry-run
set -- "$@" artifacts/lisp65-f011-legacy-interim.prg
exec sh scripts/run-on-mega65.sh "$@"
EOF
chmod 0755 "$release_root/run-f011-stdlib.sh"

commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
status="$(awk -F= '/^status=/ { print $2 }' "$legacy_ship_dir/ship-readiness.txt")"
blockers="$(awk -F= '/^blockers=/ { print $2 }' "$legacy_ship_dir/ship-readiness.txt")"

cat > "$release_root/README.txt" <<EOF
lisp65 legacy-interim reference bundle
commit=$commit
status=$status
blockers=$blockers

Contents:
- artifacts/lisp65-legacy-interim.prg + artifacts/lisp65-legacy-interim.d81:
  Conservative Bank-0 REPL with embedded Prelude+String layer.
- artifacts/lisp65-f011-legacy-interim.prg + artifacts/lisp65-legacy-stdlib.d81:
  F011 REPL plus full Lisp stdlib as sequential LOAD chunks.
- docs/load-stdlib-commands.txt:
  Manual chunk-load commands for the current non-reentrant LOADALL path.
- docs/ship-readiness.txt:
  Machine-readable readiness status and known blockers.

Run from the unpacked release root:

  DRY_RUN=1 ./run-legacy-interim.sh
  M65TOOLS=/path/to/m65tools ./run-legacy-interim.sh

For the F011 stdlib package:

  DRY_RUN=1 ./run-f011-stdlib.sh
  M65TOOLS=/path/to/m65tools ./run-f011-stdlib.sh

If auto-discovery is not enough, set MEGA65_IP to the etherload IPv6 target.
EOF

{
  echo "lisp65 legacy-interim reference manifest"
  echo "commit=$commit"
  echo "status=$status"
  echo "blockers=$blockers"
  echo "tarball=$tarball"
  echo "files:"
  (
    cd "$release_root"
    find . -type f ! -name release-manifest.txt -print | sort | while IFS= read -r file; do
      size="$(wc -c < "$file" | tr -d ' ')"
      sha="$(sha256sum "$file" | awk '{ print $1 }')"
      printf '%s %s %s\n' "$sha" "$size" "${file#./}"
    done
  )
} > "$release_root/release-manifest.txt"

mkdir -p "$(dirname "$tarball")"
tmp="$tarball.tmp"
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='@0' \
  -C "$(dirname "$release_root")" -czf "$tmp" "$base"
mv "$tmp" "$tarball"

for required in \
  artifacts/lisp65-legacy-interim.prg \
  artifacts/lisp65-legacy-interim.d81 \
  artifacts/lisp65-f011-legacy-interim.prg \
  artifacts/lisp65-legacy-stdlib.d81 \
  docs/ship-readiness.txt \
  docs/load-stdlib-commands.txt \
  run-legacy-interim.sh \
  run-f011-stdlib.sh \
  release-manifest.txt
do
  tar -tzf "$tarball" "$base/$required" >/dev/null
done

echo "==> Release-Bundle geschrieben: $tarball"
