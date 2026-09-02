#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Verify live publication parity and the immutable release-doc boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config" / "publication-drift-policy.json"
PUBLIC_EXPORT = ROOT / "tools" / "host-lisp" / "public_export.py"


class DriftError(RuntimeError):
    """Raised when publication state is inconsistent or unclassified."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("format") != "lisp65-publication-drift-policy-v1":
        raise DriftError(f"unsupported publication drift policy: {path}")
    return value


def check_live_markers(policy: dict) -> None:
    canonical = set(policy["canonical_live_documents"])
    markers = policy["required_live_markers"]
    if canonical != set(markers):
        raise DriftError("canonical document and marker inventories differ")
    for relative, required in markers.items():
        path = ROOT / relative
        if not path.is_file():
            raise DriftError(f"canonical live document missing: {relative}")
        text = path.read_text(encoding="utf-8")
        for marker in required:
            if marker not in text:
                raise DriftError(f"canonical live marker missing: {relative}: {marker}")


def check_public_checkout(public_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(PUBLIC_EXPORT), "compare", str(public_root)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        raise DriftError(result.stdout.strip())


def check_release_snapshot(policy: dict) -> tuple[str, str]:
    release = policy["release_asset"]
    archive = ROOT / release["path"]
    if not archive.is_file() or sha256(archive) != release["sha256"]:
        raise DriftError("release asset missing or SHA-256 drifted")

    frozen = release["immutable_readme"]
    with tarfile.open(archive, "r:gz") as package:
        try:
            member = package.getmember(frozen["member"])
            handle = package.extractfile(member)
        except (KeyError, tarfile.TarError) as error:
            raise DriftError(f"immutable release README missing: {error}") from error
        if handle is None:
            raise DriftError("immutable release README is not a regular file")
        readme_sha = hashlib.sha256(handle.read()).hexdigest()
    if readme_sha != frozen["sha256"]:
        raise DriftError("immutable release README SHA-256 drifted")
    if frozen.get("classification") != "tag-time-historical-snapshot":
        raise DriftError("immutable release README lacks historical classification")
    if set(frozen.get("superseded_for_user-instructions-by", [])) != set(
        policy["canonical_live_documents"]
    ):
        raise DriftError("release README supersession inventory is incomplete")
    return release["sha256"], readme_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", required=True, type=Path)
    parser.add_argument("--policy", default=DEFAULT_POLICY, type=Path)
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy.resolve())
        check_live_markers(policy)
        check_public_checkout(args.public_root.resolve())
        bundle_sha, readme_sha = check_release_snapshot(policy)
        print(
            "publication drift: passed "
            f"bundle={bundle_sha} frozen_readme={readme_sha} "
            "release_documentation=historical-snapshot-with-live-supersession"
        )
        return 0
    except (
        KeyError,
        TypeError,
        OSError,
        json.JSONDecodeError,
        tarfile.TarError,
        DriftError,
    ) as error:
        print(f"publication drift: failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
