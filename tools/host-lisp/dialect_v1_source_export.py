#!/usr/bin/env python3
"""Export the frozen dialect-v1 runtime and Prelude inputs from its pinned commit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/dialect-migration-contract.json"
PRELOADS = (
    "lib/lcc.lisp",
    "lib/prelude-m1.lisp",
    "lib/stdlib-control.lisp",
    "lib/stdlib-lists.lisp",
)


class ExportError(RuntimeError):
    pass


def _git(args: list[str]) -> bytes:
    process = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False
    )
    if process.returncode != 0:
        raise ExportError(process.stderr.decode("utf-8", "replace").strip())
    return process.stdout


def _commit(contract_path: Path) -> str:
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        commit = contract["source_profile"]["source_commit"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ExportError(f"cannot read source_profile.source_commit: {exc}") from exc
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ExportError("frozen source commit is not a full lowercase SHA")
    resolved = _git(["rev-parse", f"{commit}^{{commit}}"]).decode("ascii").strip()
    if resolved != commit:
        raise ExportError("frozen source commit does not resolve exactly")
    return commit


def _paths(commit: str) -> list[str]:
    src = _git(["ls-tree", "-r", "--name-only", commit, "src"]).decode("utf-8").splitlines()
    paths = sorted(set(src) | set(PRELOADS))
    if not paths or any(not path.startswith(("src/", "lib/")) for path in paths):
        raise ExportError("frozen source inventory is invalid")
    return paths


def export(contract_path: Path, output: Path) -> None:
    commit = _commit(contract_path)
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise ExportError(f"refusing to replace non-directory export root: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    bindings = []
    for relative in _paths(commit):
        payload = _git(["show", f"{commit}:{relative}"])
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        bindings.append(
            {
                "path": relative,
                "origin": f"git:{commit}:{relative}",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    manifest = {
        "format": "lisp65-frozen-source-export-v1",
        "profile": "dialect-v1",
        "source_commit": commit,
        "bindings": bindings,
    }
    (output / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"dialect-v1-source-export: PASS commit={commit} files={len(bindings)} "
        f"output={output}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        export(args.contract, args.output)
        return 0
    except ExportError as exc:
        print(f"dialect-v1-source-export: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
