#!/usr/bin/env python3
"""Create the writable R5 Workbench test medium from the sealed Work D81."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SLOTS = ("demo", "work", "an", "out", "fasl0", "fasl1", "fasl2")


class MediaError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(path: Path, label: str) -> Path:
    path = path.resolve()
    if path.is_symlink() or not path.is_file():
        raise MediaError(f"{label} must be a regular non-symlink file: {path}")
    return path


def run(command: list[str], label: str) -> str:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if completed.returncode:
        raise MediaError(f"{label} failed ({completed.returncode}):\n{completed.stdout}")
    return completed.stdout


def build(args: argparse.Namespace) -> None:
    out = args.out.resolve()
    manifest = args.manifest.resolve()
    if out.exists() or out.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise MediaError("test-medium outputs must be fresh")
    work = require(args.work_d81, "sealed Work D81")
    ide = require(args.ide, "IDE library")
    idex = require(args.idex, "IDEX library")
    m65d = require(args.m65d, "M65D library")
    demo = require(args.demo, "demo source")
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(work, out)
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-test-media-") as raw:
        root = Path(raw)
        slot = root / "slot.bin"
        slot.write_bytes(bytes(args.slot_bytes))
        command = [args.c1541, str(out)]
        for source, name in ((ide, "ide"), (idex, "idex"), (m65d, "m65d")):
            command += ["-write", str(source), f"{name},s"]
        for name in SLOTS:
            command += ["-write", str(demo if name == "demo" else slot), f"{name},s"]
        listing = run(command, "populate R5 test Work D81")
    listing = run([args.c1541, str(out), "-list"], "list R5 test Work D81")
    for name in ("ide", "idex", "m65d", *SLOTS):
        if f'"{name}"' not in listing.lower():
            raise MediaError(f"R5 test Work D81 lacks {name}")
    if '"l65work' not in listing.lower() or " 65 " not in listing.lower():
        raise MediaError("R5 test Work D81 lost the sealed L65WORK,65 media identity")
    value = {
        "format": "lisp65-r5-workbench-test-media-v1",
        "version": 1,
        "role": "test-closure-only-not-product",
        "media_identity": {"name": "L65WORK", "id": "65"},
        "source_work_d81": {"name": work.name, "sha256": sha(work)},
        "libraries": [
            {"id": "ide", "name": ide.name, "sha256": sha(ide)},
            {"id": "idex", "name": idex.name, "sha256": sha(idex)},
            {"id": "m65d", "name": m65d.name, "sha256": sha(m65d)},
        ],
        "slots": list(SLOTS),
        "slot_bytes": args.slot_bytes,
        "output": {"name": out.name, "bytes": out.stat().st_size, "sha256": sha(out)},
        "result": "passed",
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"R5 Workbench test medium: PASS media=L65WORK,65 bytes={out.stat().st_size} role=test-closure")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-d81", type=Path, required=True)
    parser.add_argument("--ide", type=Path, required=True)
    parser.add_argument("--idex", type=Path, required=True)
    parser.add_argument("--m65d", type=Path, required=True)
    parser.add_argument("--demo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--slot-bytes", type=int, default=8192)
    parser.add_argument("--c1541", default="c1541")
    args = parser.parse_args()
    try:
        build(args)
    except (MediaError, OSError, ValueError) as exc:
        print(f"R5 Workbench test medium: FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
