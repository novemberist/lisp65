#!/usr/bin/env python3
"""Bind an authority as the era that sealed it saw it, not as it is today.

A sealed receipt witnesses the world of its own run.  When such a receipt
binds a path in the working tree, every later edit to that path drifts a
record that did not change -- and the drift is paid for with a rebind
receipt, then another.  Binding the authority to the commit that sealed the
record ends that treadmill: the reconstruction reproduces the reviewed bytes
exactly, and living code is free to move.

This is provenance only.  Whatever a gate verifies about live content --
media artifacts, counts, geometry, readbacks -- stays live.
"""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class EraError(RuntimeError):
    pass


def era_blob(commit: str, path: str) -> bytes:
    """Read a tracked path exactly as `commit` carried it."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise EraError(f"era authority unreadable: {commit}:{path}: {detail}")
    return result.stdout


def era_bind(commit: str, path: Path | str) -> dict[str, Any]:
    """Bind {path, bytes, sha256} from the sealing era, not the working tree."""
    if isinstance(path, Path):
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    else:
        name = path
    raw = era_blob(commit, name)
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def stable_recorded_on(receipt: Path) -> str:
    """Preserve a receipt's creation date across later verification runs."""
    if receipt.is_file():
        try:
            value = json.loads(receipt.read_text(encoding="utf-8"))
            recorded = value.get("recorded_on")
            if isinstance(recorded, str):
                date.fromisoformat(recorded)
                return recorded
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            pass
    return date.today().isoformat()


def selftest() -> None:
    """The era view must differ from the living view when the file moved."""
    tracked = "config/c2-v150-release-contract.json"
    bound = era_bind("HEAD", tracked)
    if set(bound) != {"path", "bytes", "sha256"}:
        raise EraError("era binding shape drift")
    if era_blob("HEAD", tracked) == era_blob("c4d9bfa7~1", tracked):
        raise EraError("era views collapsed across a known content change")
    try:
        era_blob("HEAD", "tools/host-lisp/does-not-exist.py")
    except EraError:
        pass
    else:
        raise EraError("a missing era authority was bound silently")
    with tempfile.TemporaryDirectory() as directory:
        receipt = Path(directory) / "receipt.json"
        receipt.write_text('{"recorded_on":"2000-01-02"}\n', encoding="utf-8")
        if stable_recorded_on(receipt) != "2000-01-02":
            raise EraError("an existing receipt date was rewritten")
    print("evidence-era: SELFTEST PASS shape=3 missing=rejected date=stable")


if __name__ == "__main__":
    selftest()
