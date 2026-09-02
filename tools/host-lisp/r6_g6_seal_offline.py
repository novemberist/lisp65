#!/usr/bin/env python3
"""Verify a sealed R6/G6 hardware-acceptance archive without a repository."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "payload"
FORMAT = "lisp65-r6-g6-hardware-archive-v1"
TOP_FORMAT = "lisp65-r6-g6-hardware-receipt-v2"
PRODUCT_SET = "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024"


class VerifyError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerifyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must contain an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise VerifyError(f"{label} must be a nonempty relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or ".." in pure.parts:
        raise VerifyError(f"{label} escapes the archive")
    return Path(*pure.parts)


def inventory(manifest: dict[str, Any]) -> None:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise VerifyError("archive file inventory is missing")
    expected: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise VerifyError(f"file inventory row malformed: {index}")
        name = relative(row["path"], f"files[{index}].path").as_posix()
        if name in expected or not name.startswith("payload/"):
            raise VerifyError(f"duplicate/non-payload inventory path: {name}")
        path = ROOT / name
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]
        ):
            raise VerifyError(f"archive payload drift: {name}")
        expected.add(name)
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in PAYLOAD.rglob("*") if path.is_file() and not path.is_symlink()
    }
    if actual != expected:
        raise VerifyError(
            f"archive inventory closure drift: missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
        )


def remote_source_binding(manifest: dict[str, Any]) -> None:
    value = manifest.get("remote_source_binding")
    if value is None:
        if manifest.get("version") == 1:
            # Historical v1 seals predate the mandatory remote-presence gate.
            return
        raise VerifyError("G6 remote source binding is missing")
    source = manifest.get("source_commit")
    if (
        not isinstance(value, dict)
        or set(value) != {
            "branch_ref", "format", "relation", "remote", "remote_head",
            "remote_transport_head", "source_commit", "source_transport_commit", "version",
        }
        or value.get("format") != "lisp65-evidence-remote-source-binding-v1"
        or value.get("version") != 1 or value.get("remote") != "github"
        or not isinstance(value.get("branch_ref"), str)
        or not value["branch_ref"].startswith("refs/heads/")
        or value.get("source_commit") != source
        or not isinstance(source, str) or len(source) != 40
        or not isinstance(value.get("source_transport_commit"), str)
        or len(value["source_transport_commit"]) != 40
        or not isinstance(value.get("remote_head"), str)
        or len(value["remote_head"]) != 40
        or not isinstance(value.get("remote_transport_head"), str)
        or len(value["remote_transport_head"]) != 40
        or value.get("relation") != "source-commit-is-remote-ancestor"
    ):
        raise VerifyError("G6 remote source binding drift")


def run(argv: list[str], cwd: Path, label: str) -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "TZ": "UTC",
        "LISP65_G6_OFFLINE_ARCHIVE": "1",
    }
    completed = subprocess.run(
        argv, cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise VerifyError(f"{label} failed:\n{completed.stdout}")


def restore_ship_modes(ship_root: Path, ship_manifest: dict[str, Any]) -> None:
    """Restore modes normalized by safe outer-tar extraction before inner verification."""
    rows = ship_manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise VerifyError("embedded Ship mode inventory is missing")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256", "mode"}:
            raise VerifyError(f"embedded Ship mode row malformed: {index}")
        mode = row["mode"]
        if not isinstance(mode, str) or len(mode) != 4 or mode[0] != "0" or any(ch not in "01234567" for ch in mode):
            raise VerifyError(f"embedded Ship mode malformed: {index}")
        path = ship_root / relative(row["path"], f"embedded Ship files[{index}].path")
        if path.is_symlink() or not path.is_file():
            raise VerifyError(f"embedded Ship file missing before mode restoration: {row['path']}")
        os.chmod(path, int(mode, 8))


def remote_binding_selftest() -> None:
    source = "1" * 40
    binding = {
        "format": "lisp65-evidence-remote-source-binding-v1",
        "version": 1,
        "remote": "github",
        "branch_ref": "refs/heads/test",
        "remote_head": "2" * 40,
        "remote_transport_head": "2" * 40,
        "source_commit": source,
        "source_transport_commit": source,
        "relation": "source-commit-is-remote-ancestor",
    }
    current = {"version": 2, "source_commit": source, "remote_source_binding": binding}
    remote_source_binding(current)
    for label, mutation in (
        ("missing", {"version": 2, "source_commit": source}),
        ("head", {**current, "remote_source_binding": {**binding, "remote_head": "2" * 39}}),
    ):
        try:
            remote_source_binding(mutation)
        except VerifyError:
            continue
        raise VerifyError(f"remote-binding selftest accepted {label} mutation")
    remote_source_binding({"version": 1, "source_commit": source})
    print("r6-g6-seal-offline: REMOTE BINDING SELFTEST PASS mutations=2 historical-v1=accepted")


def verify() -> dict[str, Any]:
    manifest = load(ROOT / "manifest.json", "G6 archive manifest")
    if (
        manifest.get("format") != FORMAT or manifest.get("version") not in {1, 2}
        or manifest.get("kind") != "hardware-acceptance" or manifest.get("status") != "sealed"
        or manifest.get("immutability") != "append-only-never-amend"
        or manifest.get("product_artifact_set_sha256") != PRODUCT_SET
        or manifest.get("result") != "passed"
        or manifest.get("reproducibility") != {
            "archive_byte_identical": True,
            "packs": 2,
            "varied_environment": ["PYTHONHASHSEED", "TZ"],
        }
    ):
        raise VerifyError("G6 archive identity or reproducibility drift")
    inventory(manifest)
    remote_source_binding(manifest)
    top_row = manifest.get("top_receipt")
    ship_row = manifest.get("ship")
    if not isinstance(top_row, dict) or set(top_row) != {"path", "sha256"}:
        raise VerifyError("G6 top receipt binding malformed")
    if not isinstance(ship_row, dict) or set(ship_row) != {"path", "manifest_sha256", "package_set_sha256"}:
        raise VerifyError("G6 Ship binding malformed")
    top_path = PAYLOAD / relative(top_row["path"], "top receipt path")
    ship_root = PAYLOAD / relative(ship_row["path"], "Ship path")
    ship_manifest = ship_root / "manifest.json"
    if sha(top_path) != top_row["sha256"] or sha(ship_manifest) != ship_row["manifest_sha256"]:
        raise VerifyError("G6 top receipt or Ship manifest SHA drift")
    top = load(top_path, "G6 top receipt")
    if (
        top.get("format") != TOP_FORMAT or top.get("status") != "passed-not-release-promoted"
        or top.get("product_artifact_set_sha256") != PRODUCT_SET
        or top.get("ship_manifest_sha256") != ship_row["manifest_sha256"]
        or top.get("counts") != {
            "G3_sealed": 9, "G6_applicable_passed": 5,
            "G6_profile_not_applicable": 1, "total": 15,
        }
        or top.get("claims") != manifest.get("claims") or top.get("result") != "passed"
    ):
        raise VerifyError("G6 top receipt claim boundary drift")
    ship_value = load(ship_manifest, "embedded Ship manifest")
    restore_ship_modes(ship_root, ship_value)
    run([sys.executable, "verify.py"], ship_root, "embedded R6 Ship verifier")
    tool = PAYLOAD / "tools/host-lisp/r6_g6.py"
    run(
        [sys.executable, str(tool), "aggregate-check", str(top_path)],
        PAYLOAD, "embedded G6 aggregate verifier",
    )
    if ship_value.get("package_set_sha256") != ship_row["package_set_sha256"]:
        raise VerifyError("embedded Ship package-set drift")
    return manifest


def main() -> int:
    try:
        if sys.argv[1:] == ["--remote-binding-selftest"]:
            remote_binding_selftest()
            return 0
        value = verify()
    except (VerifyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"r6-g6-seal-offline: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "r6-g6-seal-offline: PASS G6=5/5-applicable WP=n/a "
        f"product={value['product_artifact_set_sha256'][:12]} release=awaits-R7"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
