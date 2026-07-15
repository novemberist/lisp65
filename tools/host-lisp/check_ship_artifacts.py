#!/usr/bin/env python3
"""Validate lisp65 ship artifacts against their generated manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Callable


DEFAULT_SHIP = Path("build") / "ship" / "manifest.txt"
DEFAULT_F011 = Path("build") / "ship" / "f011-manifest.txt"
DEFAULT_STDLIB = Path("build") / "ship" / "stdlib-d81-manifest.txt"
DEFAULT_AUTOLOAD = Path("build") / "f011" / "autoload-manifest.txt"
DEFAULT_STDLIB_AUTOLOAD = Path("build") / "f011" / "stdlib-autoload-manifest.txt"
D81_BYTES = 819200


@dataclass
class ArtifactPaths:
    ship: Path
    f011: Path
    stdlib: Path
    autoload: Path
    stdlib_autoload: Path


def is_data_chunk(name: str) -> bool:
    return len(name) == 3 and name.startswith("L") and name[1:].isdigit()


def key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith(("  ", "L", "LOADALL")):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def chunk_lines(path: Path) -> list[tuple[str, int]]:
    chunks: list[tuple[str, int]] = []
    if not path.exists():
        return chunks
    in_chunks = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "chunks:":
            in_chunks = True
            continue
        if not in_chunks:
            continue
        parts = line.split()
        if len(parts) >= 2 and (parts[0] == "LOADALL" or parts[0].startswith("L")):
            try:
                chunks.append((parts[0], int(parts[1])))
            except ValueError:
                continue
    return chunks


def require_file(errors: list[str], path: Path, label: str) -> int:
    if not path.exists():
        errors.append(f"{label} missing: {path}")
        return 0
    size = path.stat().st_size
    if size <= 0:
        errors.append(f"{label} empty: {path}")
    return size


def require_size(errors: list[str], path: Path, expected: str, label: str) -> None:
    if not expected.isdigit():
        errors.append(f"{label} manifest size is not numeric: {expected}")
        return
    actual = require_file(errors, path, label)
    if actual and actual != int(expected):
        errors.append(f"{label} size mismatch: manifest={expected} actual={actual} path={path}")


def d81_entries(errors: list[str], path: Path, label: str) -> set[str]:
    if shutil.which("c1541") is None:
        errors.append("c1541 missing; cannot inspect D81 directory")
        return set()
    if not path.exists():
        return set()
    proc = subprocess.run(
        ["c1541", str(path), "-list"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    if proc.returncode != 0:
        errors.append(f"{label}: c1541 -list failed for {path}: {output.strip()}")
        return set()
    return {match.group(1).strip().lower() for match in re.finditer(r'"([^"]+)"', output)}


def require_d81_entries(errors: list[str], path: Path, expected: list[str], label: str) -> None:
    entries = d81_entries(errors, path, label)
    for name in expected:
        if name.lower() not in entries:
            errors.append(f"{label}: D81 missing entry {name}: {path}")


def check_interim_manifest(
    errors: list[str],
    path: Path,
    expect_prelude: str,
    check_d81_dir: bool,
) -> None:
    values = key_values(path)
    if not values:
        errors.append(f"manifest missing or empty: {path}")
        return
    if values.get("with_prelude") != expect_prelude:
        errors.append(f"{path}: with_prelude={values.get('with_prelude')} expected {expect_prelude}")
    prg = Path(values.get("prg", "missing"))
    d81 = Path(values.get("d81", "missing"))
    require_size(errors, prg, values.get("prg_bytes", "missing"), f"{path}: prg")
    require_size(errors, d81, values.get("d81_bytes", "missing"), f"{path}: d81")
    if d81.exists() and d81.stat().st_size != D81_BYTES:
        errors.append(f"{path}: d81 size must be {D81_BYTES}: {d81.stat().st_size}")
    if check_d81_dir:
        require_d81_entries(errors, d81, ["lisp65"], f"{path}: d81")
    if expect_prelude == "1" and "lib/stdlib-strings.lisp" not in values.get("ship_libs", ""):
        errors.append(f"{path}: conservative ship must include stdlib strings")
    if expect_prelude == "0" and "MEGA65_F011_LOAD" not in values.get("extra_cflags", ""):
        errors.append(f"{path}: F011 ship must include -DMEGA65_F011_LOAD")


def check_stdlib_manifest(errors: list[str], path: Path, check_d81_dir: bool) -> None:
    values = key_values(path)
    if not values:
        errors.append(f"stdlib manifest missing or empty: {path}")
        return
    d81 = Path(values.get("d81", "missing"))
    require_size(errors, d81, values.get("d81_bytes", "missing"), "stdlib d81")
    if d81.exists() and d81.stat().st_size != D81_BYTES:
        errors.append(f"stdlib d81 size must be {D81_BYTES}: {d81.stat().st_size}")

    chunk_dir = Path(values.get("chunk_dir", "missing"))
    if not chunk_dir.is_dir():
        errors.append(f"chunk_dir missing: {chunk_dir}")
        return
    chunk_max = values.get("chunk_max", "missing")
    if not chunk_max.isdigit():
        errors.append(f"chunk_max is not numeric: {chunk_max}")
        return

    chunks = chunk_lines(path)
    if not chunks:
        errors.append(f"no chunks listed in {path}")
        return
    l_chunks = [name for name, _ in chunks if is_data_chunk(name)]
    if values.get("load_entry") != "LOADALL":
        errors.append(f"load_entry must be LOADALL: {values.get('load_entry')}")
    if values.get("manual_load_command_count") != str(len(l_chunks)):
        errors.append(
            "manual_load_command_count mismatch: "
            f"manifest={values.get('manual_load_command_count')} chunks={len(l_chunks)}"
        )
    commands = Path(values.get("manual_load_commands", "missing"))
    command_count = 0
    if commands.exists():
        command_count = len([line for line in commands.read_text(encoding="utf-8").splitlines() if line])
    else:
        errors.append(f"manual_load_commands missing: {commands}")
    if command_count and command_count != len(l_chunks):
        errors.append(f"manual load command count mismatch: file={command_count} chunks={len(l_chunks)}")

    max_bytes = int(chunk_max)
    for name, expected_size in chunks:
        chunk = chunk_dir / name
        actual = require_file(errors, chunk, f"chunk {name}")
        if actual and actual != expected_size:
            errors.append(f"chunk {name} size mismatch: manifest={expected_size} actual={actual}")
        if actual and actual > max_bytes:
            errors.append(f"chunk {name} exceeds chunk_max={max_bytes}: {actual}")
    if check_d81_dir:
        require_d81_entries(errors, d81, [name.lower() for name, _ in chunks], "stdlib d81")


def check_autoload_manifest(
    errors: list[str],
    path: Path,
    require_extra_dir: bool,
    check_d81_dir: bool,
) -> None:
    values = key_values(path)
    if not values:
        errors.append(f"autoload manifest missing or empty: {path}")
        return
    image = Path(values.get("image", "missing"))
    d81 = Path(values.get("d81", "missing"))
    prg = Path(values.get("prg", "missing"))
    require_size(errors, image, values.get("image_bytes", "missing"), f"{path}: image")
    require_file(errors, d81, f"{path}: d81")
    require_file(errors, prg, f"{path}: prg")
    sector = values.get("defd81_sector", "missing")
    if not sector.isdigit() or int(sector) <= 0:
        errors.append(f"{path}: invalid defd81_sector={sector}")
    extra_dir = values.get("extra_dir", "")
    if require_extra_dir:
        if not extra_dir:
            errors.append(f"{path}: expected extra_dir")
        elif not Path(extra_dir).is_dir():
            errors.append(f"{path}: extra_dir missing: {extra_dir}")
    if check_d81_dir:
        expected = [
            values.get("program_name", "lisp65"),
            values.get("demo_name", "demolib"),
        ]
        if extra_dir:
            for chunk in [Path(extra_dir) / "LOADALL", *sorted(Path(extra_dir).glob("L??"))]:
                if chunk.exists():
                    expected.append(chunk.name.lower())
        require_d81_entries(errors, d81, expected, f"{path}: d81")


def validate(paths: ArtifactPaths, check_d81_dir: bool = True) -> list[str]:
    errors: list[str] = []
    check_interim_manifest(errors, paths.ship, "1", check_d81_dir)
    check_interim_manifest(errors, paths.f011, "0", check_d81_dir)
    check_stdlib_manifest(errors, paths.stdlib, check_d81_dir)
    check_autoload_manifest(errors, paths.autoload, require_extra_dir=False, check_d81_dir=check_d81_dir)
    check_autoload_manifest(errors, paths.stdlib_autoload, require_extra_dir=True, check_d81_dir=check_d81_dir)
    return errors


def write_file(path: Path, size: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        if size > 0:
            out.seek(size - 1)
            out.write(b"\0")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_fixture(root: Path) -> ArtifactPaths:
    ship_prg = root / "ship" / "lisp65-interim.prg"
    ship_d81 = root / "ship" / "lisp65-interim.d81"
    f011_prg = root / "ship" / "lisp65-f011-interim.prg"
    f011_d81 = root / "ship" / "lisp65-f011-interim.d81"
    stdlib_d81 = root / "ship" / "lisp65-stdlib.d81"
    chunk_dir = root / "ship" / "stdlib-chunks"
    load_commands = root / "ship" / "load-stdlib-commands.txt"
    autoload_img = root / "f011" / "autoload.img"
    autoload_d81 = root / "f011" / "autoload.d81"
    stdlib_autoload_img = root / "f011" / "stdlib-autoload.img"
    stdlib_autoload_d81 = root / "f011" / "stdlib-autoload.d81"

    for path in [ship_prg, f011_prg, autoload_img, autoload_d81, stdlib_autoload_img, stdlib_autoload_d81]:
        write_file(path, 7)
    for path in [ship_d81, f011_d81, stdlib_d81]:
        write_file(path, D81_BYTES)
    write_file(chunk_dir / "LOADALL", 19)
    write_file(chunk_dir / "L00", 11)
    write_file(chunk_dir / "L01", 13)
    write_text(load_commands, '(load "l00")\n(load "l01")\n')

    ship_manifest = root / "ship" / "manifest.txt"
    f011_manifest = root / "ship" / "f011-manifest.txt"
    stdlib_manifest = root / "ship" / "stdlib-d81-manifest.txt"
    autoload_manifest = root / "f011" / "autoload-manifest.txt"
    stdlib_autoload_manifest = root / "f011" / "stdlib-autoload-manifest.txt"

    write_text(ship_manifest, "\n".join([
        "lisp65 interim ship",
        "with_prelude=1",
        "ship_libs=lib/prelude-m1.lisp lib/stdlib-strings.lisp",
        f"prg={ship_prg}",
        "prg_bytes=7",
        f"d81={ship_d81}",
        f"d81_bytes={D81_BYTES}",
        "",
    ]))
    write_text(f011_manifest, "\n".join([
        "lisp65 interim ship",
        "with_prelude=0",
        "ship_libs=lib/prelude-m1.lisp lib/stdlib-strings.lisp",
        "extra_cflags=-DMEGA65_F011_LOAD",
        f"prg={f011_prg}",
        "prg_bytes=7",
        f"d81={f011_d81}",
        f"d81_bytes={D81_BYTES}",
        "",
    ]))
    write_text(stdlib_manifest, "\n".join([
        "lisp65 full stdlib D81",
        f"d81={stdlib_d81}",
        f"d81_bytes={D81_BYTES}",
        f"chunk_dir={chunk_dir}",
        "chunk_max=480",
        "load_entry=LOADALL",
        f"manual_load_commands={load_commands}",
        "manual_load_command_count=2",
        "",
        "chunks:",
        "LOADALL 19",
        "L00 11 sources=lib/prelude-m1.lisp",
        "L01 13 sources=lib/stdlib-strings.lisp",
        "",
    ]))
    write_text(autoload_manifest, "\n".join([
        "lisp65 F011 autoload image",
        f"image={autoload_img}",
        "image_bytes=7",
        "defd81_sector=11552",
        f"d81={autoload_d81}",
        f"prg={f011_prg}",
        "extra_dir=",
        "",
    ]))
    write_text(stdlib_autoload_manifest, "\n".join([
        "lisp65 F011 autoload image",
        f"image={stdlib_autoload_img}",
        "image_bytes=7",
        "defd81_sector=11552",
        f"d81={stdlib_autoload_d81}",
        f"prg={f011_prg}",
        f"extra_dir={chunk_dir}",
        "",
    ]))

    return ArtifactPaths(
        ship=ship_manifest,
        f011=f011_manifest,
        stdlib=stdlib_manifest,
        autoload=autoload_manifest,
        stdlib_autoload=stdlib_autoload_manifest,
    )


def selftest() -> int:
    cases: list[tuple[str, Callable[[Path], ArtifactPaths], bool]] = []

    def valid(root: Path) -> ArtifactPaths:
        return make_fixture(root)

    def missing_chunk(root: Path) -> ArtifactPaths:
        paths = make_fixture(root)
        (root / "ship" / "stdlib-chunks" / "L01").unlink()
        return paths

    def wrong_load_count(root: Path) -> ArtifactPaths:
        paths = make_fixture(root)
        write_text(root / "ship" / "load-stdlib-commands.txt", '(load "l00")\n')
        return paths

    def bad_f011_flags(root: Path) -> ArtifactPaths:
        paths = make_fixture(root)
        text = paths.f011.read_text(encoding="utf-8").replace("-DMEGA65_F011_LOAD", "")
        write_text(paths.f011, text)
        return paths

    def missing_extra_dir(root: Path) -> ArtifactPaths:
        paths = make_fixture(root)
        text = paths.stdlib_autoload.read_text(encoding="utf-8").replace(
            f"extra_dir={root / 'ship' / 'stdlib-chunks'}",
            "extra_dir=",
        )
        write_text(paths.stdlib_autoload, text)
        return paths

    cases.extend([
        ("valid", valid, True),
        ("missing-chunk", missing_chunk, False),
        ("wrong-load-count", wrong_load_count, False),
        ("bad-f011-flags", bad_f011_flags, False),
        ("missing-stdlib-autoload-extra-dir", missing_extra_dir, False),
    ])

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-ship-artifacts-") as tmp:
        base = Path(tmp)
        for name, factory, should_pass in cases:
            root = base / name
            errors = validate(factory(root), check_d81_dir=False)
            passed = not errors
            if passed != should_pass:
                failures.append(f"{name}: expected {should_pass}, got {passed}: {'; '.join(errors)}")
    if failures:
        for failure in failures:
            print(f"ship-artifacts-check selftest FAIL: {failure}")
        return 1
    print(f"ship-artifacts-check selftest OK: {len(cases)} cases")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--ship", type=Path, default=DEFAULT_SHIP)
    parser.add_argument("--f011", type=Path, default=DEFAULT_F011)
    parser.add_argument("--stdlib", type=Path, default=DEFAULT_STDLIB)
    parser.add_argument("--autoload", type=Path, default=DEFAULT_AUTOLOAD)
    parser.add_argument("--stdlib-autoload", type=Path, default=DEFAULT_STDLIB_AUTOLOAD)
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    errors = validate(ArtifactPaths(
        ship=args.ship,
        f011=args.f011,
        stdlib=args.stdlib,
        autoload=args.autoload,
        stdlib_autoload=args.stdlib_autoload,
    ))

    if errors:
        for error in errors:
            print(f"ship-artifacts-check FAIL: {error}")
        return 1
    print("ship-artifacts-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
