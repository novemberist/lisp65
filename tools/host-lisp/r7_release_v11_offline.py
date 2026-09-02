#!/usr/bin/env python3
"""Standard-library-only offline verifier for lisp65 1.1.0."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
FORMAT = "lisp65-r7-release-v11-manifest-v1"
PRODUCT_SET = "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024"
SOURCE_SEAL_SHA = "c6a00b232a0dcd5bc3bbf1b6ab6869ef8d97ef6720d32415d881a9bb08d206ae"
SHIP_MANIFEST_SHA = "706dc97d3811dfa0d362522358a00b7c1dd30264f7409acccec3fce07d46150e"
G6_RECEIPT_SHA = "6ecf662e5828560521701446ba907e249990aa27ebd20e9e93046ea5d6460a10"
SHIP_MEMBER = "payload/build/r6/ship/manifest.json"
G6_MEMBER = "payload/build/r6/g6/run-20260719-wave3-01/g6-hardware-receipt.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


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
        raise VerifyError(f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise VerifyError(f"{label} schema drift")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise VerifyError(f"{label} must be a lowercase SHA-256")
    return value


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerifyError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise VerifyError(f"{label} escapes the bundle")
    return value


def bundle_file(value: Any, digest: Any, label: str) -> Path:
    path = ROOT / Path(*PurePosixPath(relative(value, label)).parts)
    if path.is_symlink() or not path.is_file() or sha(path) != lower_sha(digest, label):
        raise VerifyError(f"{label} binding drift")
    return path


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [{key: row[key] for key in ("role", "name", "bytes", "sha256")} for row in sorted(rows, key=lambda row: (row["role"], row["name"]))]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [{key: row[key] for key in ("path", "bytes", "sha256", "mode")} for row in sorted(rows, key=lambda row: row["path"])]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def verify_inventory(manifest: dict[str, Any]) -> None:
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows:
        raise VerifyError("bundle inventory is empty")
    names: list[str] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"path", "bytes", "sha256", "mode"}, f"file[{index}]")
        name = relative(row["path"], f"file[{index}].path")
        path = ROOT / Path(*PurePosixPath(name).parts)
        if (
            type(row["bytes"]) is not int or row["bytes"] < 0
            or not isinstance(row["mode"], str) or not re.fullmatch(r"0[0-7]{3}", row["mode"])
            or path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]
            or sha(path) != lower_sha(row["sha256"], f"file[{index}].sha256")
            or stat.S_IMODE(path.stat().st_mode) != int(row["mode"], 8)
        ):
            raise VerifyError(f"bundle file drift: {name}")
        names.append(name)
    if names != sorted(set(names)):
        raise VerifyError("bundle paths must be sorted and unique")
    actual = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file() and not path.is_symlink() and path != MANIFEST)
    if actual != names or package_set_sha(rows) != manifest["package_set_sha256"]:
        raise VerifyError("bundle inventory is not exact")


def absolute_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in absolute_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in absolute_strings(child)]
    return [value] if isinstance(value, str) and value.startswith("/") else []


def safe_extract(path: Path, destination: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile():
                raise VerifyError("source seal contains unsafe/non-file member")
        archive.extractall(destination, filter="data")


def verify_source_seal(path: Path) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any], dict[str, Any]]:
    temporary = tempfile.TemporaryDirectory(prefix="lisp65-r7-v11-source-seal-")
    directory = Path(temporary.name)
    safe_extract(path, directory)
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        temporary.cleanup()
        raise VerifyError(f"embedded Wave 3 G6 seal failed verification:\n{completed.stdout}")
    ship_path = directory / SHIP_MEMBER
    g6_path = directory / G6_MEMBER
    if sha(ship_path) != SHIP_MANIFEST_SHA or sha(g6_path) != G6_RECEIPT_SHA:
        temporary.cleanup(); raise VerifyError("embedded Ship/G6 binding drift")
    return temporary, directory, load(ship_path, "sealed Ship manifest"), load(g6_path, "sealed G6 receipt")


def verify() -> dict[str, Any]:
    manifest = load(MANIFEST, "release manifest")
    exact(manifest, {
        "format", "version", "status", "release", "source_commit", "packed_on", "packed_on_source",
        "input", "product", "claims", "toolchain", "policy", "capacity_delta", "artifacts",
        "documentation", "evidence", "files", "package_set_sha256", "result",
    }, "manifest")
    release = {
        "product": "lisp65", "version": "1.1.0", "tag": "v1.1.0", "tag_type": "annotated",
        "bundle": "releases/lisp65-1.1.0.tar.gz", "visibility": "public", "dialect": "v2",
    }
    product = {
        "artifact_set_sha256": PRODUCT_SET, "artifact_count": 14,
        "product_build_id": "f144fd48", "product_sha_changes_during_R7": 0,
    }
    claims = {
        "G3": "passed-emulator-prefilter-only",
        "G5": "passed(14/14-hardware)-for-product-artifact-set",
        "G6": "passed(5/5-applicable); execution=single-device; product-medium-physical-write-protect=n/a-no-physical-medium-in-SD-D81-configuration",
        "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
        "definition_call_latency": "performance-bar=not-passed; documented-limitation=1.90..1.96s-occasional-longer; warm=0.20s; cure=C2/1.2",
        "release": "verified-v1.1.0-package",
    }
    if (
        manifest["format"] != FORMAT or manifest["version"] != 1 or manifest["status"] != "verified-before-tag"
        or manifest["release"] != release or manifest["product"] != product or manifest["claims"] != claims
        or not COMMIT_RE.fullmatch(manifest["source_commit"])
        or manifest["packed_on_source"] != "release-source-commit-committer-timestamp"
        or manifest["result"] != "passed" or absolute_strings(manifest["toolchain"])
    ):
        raise VerifyError("release identity/claim drift")
    verify_inventory(manifest)
    rows = manifest["artifacts"]
    if not isinstance(rows, list) or len(rows) != 14 or artifact_set_sha(rows) != PRODUCT_SET:
        raise VerifyError("release product set drift")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {"source_seal", "g6_receipt", "ship_manifest", "contract", "packer", "ship_packer_receipt", "static_preflight_receipt", "profile_applicability_receipt"}:
        raise VerifyError("evidence closure drift")
    evidence_paths: dict[str, Path] = {}
    for name, raw in evidence.items():
        binding = exact(raw, {"path", "sha256"}, f"evidence.{name}")
        evidence_paths[name] = bundle_file(binding["path"], binding["sha256"], f"evidence.{name}")
    if sha(evidence_paths["source_seal"]) != SOURCE_SEAL_SHA or sha(evidence_paths["g6_receipt"]) != G6_RECEIPT_SHA or sha(evidence_paths["ship_manifest"]) != SHIP_MANIFEST_SHA:
        raise VerifyError("primary evidence digest drift")
    temporary, directory, ship, g6 = verify_source_seal(evidence_paths["source_seal"])
    try:
        if (
            ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
            or ship.get("product", {}).get("artifact_count") != 14
            or g6.get("product_artifact_set_sha256") != PRODUCT_SET or g6.get("result") != "passed"
            or evidence_paths["g6_receipt"].read_bytes() != (directory / G6_MEMBER).read_bytes()
            or evidence_paths["ship_manifest"].read_bytes() != (directory / SHIP_MEMBER).read_bytes()
        ):
            raise VerifyError("sealed product/G6 claim drift")
        source_rows = {row["role"]: row for row in ship.get("artifacts", []) if isinstance(row, dict)}
        if len(source_rows) != 14:
            raise VerifyError("sealed artifact closure drift")
        for index, raw in enumerate(rows):
            row = exact(raw, {"role", "name", "bytes", "sha256", "bundle_path", "sealed_ship_path"}, f"artifact[{index}]")
            source = source_rows.get(row["role"])
            final_path = bundle_file(row["bundle_path"], row["sha256"], f"artifact[{index}]")
            sealed_path = directory / "payload/build/r6/ship" / relative(row["sealed_ship_path"], "sealed path")
            if (
                not isinstance(source, dict) or row["name"] != source.get("name") or row["bytes"] != source.get("bytes")
                or row["sha256"] != source.get("sha256") or row["sealed_ship_path"] != source.get("ship_path")
                or final_path.stat().st_size != row["bytes"] or sealed_path.is_symlink() or not sealed_path.is_file()
                or final_path.read_bytes() != sealed_path.read_bytes()
            ):
                raise VerifyError(f"product byte identity drift: {row['role']}")
    finally:
        temporary.cleanup()
    docs = manifest["documentation"]
    expected_docs = ["LICENSE", "LICENSE-SCOPE.md", "README.md", "RUNTIME-REDISTRIBUTION.md", "THIRD-PARTY-NOTICES.md", "docs/generated/ide-keymap.md", "docs/language-reference.md", "docs/releases/1.1.0.md", "docs/user-guide.md"]
    if not isinstance(docs, list) or [row.get("path") for row in docs] != expected_docs:
        raise VerifyError("documentation closure drift")
    for index, row in enumerate(docs):
        exact(row, {"path", "bytes", "sha256"}, f"documentation[{index}]")
        path = bundle_file(row["path"], row["sha256"], f"documentation[{index}]")
        if path.stat().st_size != row["bytes"]:
            raise VerifyError(f"documentation byte drift: {row['path']}")
    if (ROOT / "README-FIRST.txt").read_bytes() != (ROOT / "README.md").read_bytes():
        raise VerifyError("README-FIRST is not the canonical README byte stream")
    dimensions = manifest["capacity_delta"]
    expected_capacity = {"bank": 371, "directory": 168, "ext": 26232, "namepool": 5079, "symbols": 334}
    if not isinstance(dimensions, dict) or set(dimensions) != set(expected_capacity):
        raise VerifyError("capacity closure drift")
    for name, amount in expected_capacity.items():
        if dimensions[name] != {"baseline": amount, "candidate": amount, "delta": 0}:
            raise VerifyError(f"capacity drift: {name}")
    if stat.S_IMODE(MANIFEST.stat().st_mode) != 0o444:
        raise VerifyError("release manifest mode drift")
    print("lisp65-r7-v11: PASS version=1.1.0 dialect=v2 product=048639695dd7 G5=14/14 G6=5/5-applicable single-device WP=n/a")
    return manifest


def main() -> int:
    try:
        verify(); return 0
    except (VerifyError, OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"lisp65-r7-v11: FAIL: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
