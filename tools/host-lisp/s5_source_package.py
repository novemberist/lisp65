#!/usr/bin/env python3
"""Build deterministic source packages for the S5 source-on-disk path."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISK_SCRATCH_MAX = 0x9300


def load_split_module():
    path = ROOT / "scripts" / "split-lisp-source.py"
    spec = importlib.util.spec_from_file_location("split_lisp_source", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_suite(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        suite = json.load(f)
    sources = suite.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"{path}: missing non-empty sources list")
    return suite


def collect_forms(suite: dict, split_mod) -> list[tuple[Path, str]]:
    forms: list[tuple[Path, str]] = []
    for item in suite["sources"]:
        source = ROOT / item
        if not source.is_file():
            raise FileNotFoundError(source)
        text = source.read_text(encoding="utf-8")
        stripped = split_mod.strip_comments(text)
        forms.extend((Path(item), form) for form in split_mod.top_level_forms(stripped))
    return forms


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=ROOT / "tests/bytecode/stdlib/p0-stdlib-subset.json")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--bundle-out", type=Path, required=True)
    ap.add_argument("--manifest-out", type=Path, required=True)
    ap.add_argument("--chunk-max", type=int, default=30000)
    args = ap.parse_args()

    suite_path = args.suite if args.suite.is_absolute() else ROOT / args.suite
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    bundle_out = args.bundle_out if args.bundle_out.is_absolute() else ROOT / args.bundle_out
    manifest_out = args.manifest_out if args.manifest_out.is_absolute() else ROOT / args.manifest_out

    if args.chunk_max <= 0 or args.chunk_max > DISK_SCRATCH_MAX:
        raise ValueError(f"--chunk-max must be 1..{DISK_SCRATCH_MAX}")

    split_mod = load_split_module()
    suite = load_suite(suite_path)
    forms = collect_forms(suite, split_mod)
    if not forms:
        raise ValueError("suite produced no top-level forms")

    bundle_out.parent.mkdir(parents=True, exist_ok=True)
    bundle = "".join(form.strip() + "\n" for _, form in forms)
    bundle_out.write_text(bundle, encoding="utf-8")

    chunk_entries = split_mod.write_chunks(forms, out_dir, args.chunk_max)

    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    chunk_files = [path for path, _sources in chunk_entries if path.name != "LOADALL"]
    with manifest_out.open("w", encoding="utf-8") as f:
        f.write("lisp65 S5 source package\n")
        f.write(f"suite={rel(suite_path)}\n")
        f.write(f"source_count={len(suite['sources'])}\n")
        f.write(f"form_count={len(forms)}\n")
        f.write(f"bundle={rel(bundle_out)}\n")
        f.write(f"bundle_bytes={bundle_out.stat().st_size}\n")
        f.write(f"bundle_sha256={sha256(bundle_out)}\n")
        f.write(
            "single_file_fits_disk_scratch=%s\n"
            % ("yes" if bundle_out.stat().st_size <= DISK_SCRATCH_MAX else "no")
        )
        f.write(f"disk_scratch_max={DISK_SCRATCH_MAX}\n")
        f.write(f"chunk_dir={rel(out_dir)}\n")
        f.write(f"chunk_max={args.chunk_max}\n")
        f.write(f"chunk_count={len(chunk_files)}\n")
        f.write("sources:\n")
        for source in suite["sources"]:
            f.write(f"  {source}\n")
        f.write("chunks:\n")
        for path, sources in chunk_entries:
            src_note = ",".join(sources)
            f.write(
                "  %s path=%s bytes=%d sha256=%s%s\n"
                % (
                    path.name,
                    rel(path),
                    path.stat().st_size,
                    sha256(path),
                    f" sources={src_note}" if src_note else "",
                )
            )

    print(
        "s5-source-package: WROTE %s forms=%d bundle_bytes=%d chunks=%d chunk_max=%d"
        % (rel(bundle_out), len(forms), bundle_out.stat().st_size, len(chunk_files), args.chunk_max)
    )
    print("s5-source-package: manifest=%s" % rel(manifest_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
