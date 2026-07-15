#!/usr/bin/env python3
"""Verify the self-contained internal CP5/G5 evidence archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "cp5-g5-67400c05/manifest.json"
)
FORMAT = "lisp65-v2-capability-carrier-cp5-g5-archive-v1"
PASS_MARKER = (
    "v2-capability-carrier-internal-g5-receipt: "
    "PASS cases=14 physical_power_cycles=4 g5=passed"
)


class ArchiveError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchiveError(f"{label} must contain an object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ArchiveError(f"{label} must be a nonempty path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise ArchiveError(f"{label} escapes the repository")
    return ROOT / pure


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    names: set[str] = set()
    for member in members:
        pure = PurePosixPath(member.name)
        if (
            not member.name
            or pure.is_absolute()
            or ".." in pure.parts
            or member.issym()
            or member.islnk()
            or not (member.isfile() or member.isdir())
        ):
            raise ArchiveError(f"unsafe archive member: {member.name!r}")
        if member.name in names:
            raise ArchiveError(f"duplicate archive member: {member.name}")
        if member.uid != 0 or member.gid != 0 or member.mtime != 0:
            raise ArchiveError(f"nondeterministic archive metadata: {member.name}")
        names.add(member.name)
    return members


def verify(manifest_path: Path) -> None:
    manifest = _load(manifest_path, "CP5/G5 archive manifest")
    expected_keys = {
        "format", "status", "product_identity_sha256", "source_commit",
        "cases", "physical_power_cycles", "archive", "candidate", "receipt",
        "receipt_sha256", "verifier", "contract", "authority",
    }
    if set(manifest) != expected_keys:
        raise ArchiveError("CP5/G5 archive manifest fields drift")
    if (
        manifest["format"] != FORMAT
        or manifest["status"] != "passed"
        or manifest["cases"] != 14
        or manifest["physical_power_cycles"] != 4
        or manifest["authority"] != {
            "checkpoint_5_hardware_condition": "passed",
            "global_profile_switch": "none",
            "release": "none",
            "shippable": False,
        }
    ):
        raise ArchiveError("CP5/G5 archive identity or authority drift")
    binding = manifest["archive"]
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "bytes"}:
        raise ArchiveError("CP5/G5 archive binding fields drift")
    archive_path = _repo_path(binding["path"], "archive.path")
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ArchiveError("CP5/G5 archive must be a regular file")
    if archive_path.stat().st_size != binding["bytes"] or _sha(archive_path) != binding["sha256"]:
        raise ArchiveError("CP5/G5 archive size/SHA drift")

    with tempfile.TemporaryDirectory(prefix="lisp65-cp5-g5-archive-") as raw:
        root = Path(raw)
        with tarfile.open(archive_path, "r:gz") as archive:
            members = _safe_members(archive)
            archive.extractall(root, members=members)
        candidate = root / manifest["candidate"]
        receipt = root / manifest["receipt"]
        verifier = root / manifest["verifier"]
        contract = root / manifest["contract"]
        for path, label in (
            (candidate, "candidate"), (receipt, "receipt"),
            (verifier, "verifier"), (contract, "contract"),
        ):
            if path.is_symlink() or not path.is_file():
                raise ArchiveError(f"archive lacks {label}: {path.relative_to(root)}")
        if _sha(receipt) != manifest["receipt_sha256"]:
            raise ArchiveError("archived top receipt SHA drift")
        candidate_value = _load(candidate, "archived candidate")
        if (
            candidate_value.get("product_identity_sha256")
            != manifest["product_identity_sha256"]
            or candidate_value.get("source_commit") != manifest["source_commit"]
            or candidate_value.get("shippable") is not False
        ):
            raise ArchiveError("archived candidate identity/authority drift")
        result = subprocess.run(
            [
                sys.executable, str(verifier.relative_to(root)),
                "--contract", str(contract.relative_to(root)),
                "verify-receipt", "--receipt", str(receipt.relative_to(root)),
            ],
            cwd=root, text=True, capture_output=True, timeout=120,
        )
        if result.returncode != 0 or PASS_MARKER not in result.stdout:
            detail = (result.stderr or result.stdout).strip()
            raise ArchiveError(f"archived G5 verifier failed: {detail}")
    print(
        "v2-cp5-g5-archive: PASS "
        f"product={manifest['product_identity_sha256'][:12]} cases=14 cycles=4"
    )


def selftest() -> None:
    for bad in ("../escape", "/absolute"):
        try:
            _repo_path(bad, "mutation")
        except ArchiveError:
            continue
        raise ArchiveError(f"unsafe path mutation accepted: {bad}")
    print("v2-cp5-g5-archive: SELFTEST PASS mutations=2")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("command", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
    else:
        verify(args.manifest.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArchiveError, OSError, tarfile.TarError, subprocess.SubprocessError) as exc:
        print(f"v2-cp5-g5-archive: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
