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
from contextlib import contextmanager
import builtins
from functools import wraps
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class EraError(RuntimeError):
    pass


@contextmanager
def host_source_world(commit: str):
    """Read-only historical Lisp/suite population for a sealed host replay.

    Does not shadow receipts, configuration, native sources, tools or build
    artifacts. Both content reads and metadata hashes see the same bytes.
    A newly introduced source absent from this era fails instead of silently
    importing it from HEAD. Scope is process-local and restored on exception.
    Returned read population identifies every authority actually consumed.
    """
    original_open, original_io_open = builtins.open, io.open
    reads, cache = {}, {}
    def selected(path):
        if not isinstance(path, (str, Path)):
            return None
        try:
            rel = Path(path).resolve().relative_to(ROOT.resolve())
        except ValueError:
            return None
        if ((rel.parts[0] == 'lib' and rel.suffix == '.lisp') or
                (rel.parts[:3] in {('tests', 'bytecode', name) for name in
                    ('libs', 'stdlib', 'runtime', 'demos', 'suites')}
                 and rel.suffix == '.json')):
            return rel.as_posix()
        return None
    def read(file, mode='r', *args, **kwargs):
        rel = selected(file)
        if rel is None:
            return original_open(file, mode, *args, **kwargs)
        if mode not in ('r', 'rt', 'rb'):
            raise EraError('write attempted inside sealed host source world: '+rel)
        if rel not in cache:
            cache[rel] = era_blob(commit, rel)
        raw = cache[rel]
        reads[rel] = dict(commit=commit, path=rel, bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest())
        if 'b' in mode:
            return io.BytesIO(raw)
        encoding = kwargs.get('encoding') or (args[1] if len(args) > 1 else None) or 'utf-8'
        errors = kwargs.get('errors') or (args[2] if len(args) > 2 else None)
        newline = kwargs.get('newline', args[3] if len(args) > 3 else None)
        return io.TextIOWrapper(io.BytesIO(raw), encoding=encoding, errors=errors, newline=newline)
    builtins.open = io.open = read
    try:
        yield reads
    finally:
        builtins.open, io.open = original_open, original_io_open


def in_host_source_world(commit: str):
    """Label a historical verification, never a live product operation."""
    def decorate(function):
        @wraps(function)
        def historical(*args, **kwargs):
            host_source_controls(commit)
            with host_source_world(commit) as reads:
                result = function(*args, **kwargs)
            if not reads:
                raise EraError('historical verification consumed no host sources')
            historical.last_source_reads = dict(reads)
            return result
        return historical
    return decorate


_tested_host_worlds = set()


def host_source_controls(commit: str) -> None:
    """Permanent sharp controls for content/metadata coupling and read-only scope."""
    if commit in _tested_host_worlds:
        return
    path = ROOT/'lib/stdlib-read-line.lisp'
    expected = era_blob(commit, path.relative_to(ROOT).as_posix())
    old_open, old_io = builtins.open, io.open
    with host_source_world(commit) as reads:
        with open(path, 'rb') as stream:
            if stream.read() != expected:
                raise EraError('built-in open imported the live source')
        if path.read_bytes() != expected or path.read_text().encode() != expected:
            raise EraError('Path content/metadata world divergence')
        recorded = reads[path.relative_to(ROOT).as_posix()]
        if recorded != dict(commit=commit, **era_bind(commit,path)):
            raise EraError('source bytes and binding disagree')
        try:
            path.open('w')
        except EraError:
            pass
        else:
            raise EraError('sealed-source write allowed')
        try:
            (ROOT/'lib/__missing_era_source_control__.lisp').read_bytes()
        except EraError:
            pass
        else:
            raise EraError('unbound source accepted')
    if builtins.open is not old_open or io.open is not old_io:
        raise EraError('source view leaked outside historical verification')
    # Substituting the later wrap source while retaining the historical SHA
    # is the exact "bound but not consumed" mutation from this conversion.
    later = era_blob('c96979bc', path.relative_to(ROOT).as_posix())
    if later == expected or hashlib.sha256(later).hexdigest() == recorded['sha256']:
        raise EraError('later-content/historical-binding mutation did not distinguish worlds')
    _tested_host_worlds.add(commit)


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
