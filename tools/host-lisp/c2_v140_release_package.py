#!/usr/bin/env python3
"""Prepare and verify the four immutable v1.4.0 Halt-#2 assets."""

from __future__ import annotations

import argparse
from io import BytesIO
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.4.0"
RELEASE = f"v{VERSION}"
TOP = f"lisp65-{VERSION}"
SOURCE_EPOCH = 1786233600
PREPARED_ON = "2026-08-09"
AUTHORITY = ROOT / "config/c2-lite-public-build-authority.json"
SHARED_MANIFEST = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5/shared-system/"
    "candidate-manifest.json")
BASE_MANIFEST = ROOT / (
    "build/c2.3/v1.4.0-candidate-media-link92-r5-split/"
    "base-candidate-manifest.json")
DEFAULT_CLEAN_RECEIPT = ROOT / (
    "build/release-v1.4.0/v1.4.0-public-clean-build-receipt.json")

ROLE_PATHS = {
    "boot-descriptor": "components/00-boot.id",
    "c2-bank2-static-code-plane": "components/01-bank2-static-code.bin",
    "c2-boot-family": "components/02-runtime-overlays-boot-final.bin",
    "c2-kernal-window": "components/03-c2-product-kernal-window.bin",
    "c2-product-shelf": "components/04-product-shelf-v4-direct.bin",
    "c2-resident-prg": "components/05-lisp65-c2-substitution-linked.prg",
    "c2-session-family-region-0":
        "components/06-runtime-overlays-session-final.bin",
    "c2-session-family-region-1":
        "components/07-runtime-overlays-session-final-region1.bin",
    "c2-two-record-boot-stage": "components/08-bootstage.bin",
    "c2d-v6-code-plane": "components/09-c2d-v6-reset-domain.bin",
    "cold-stager": "components/10-autoboot.c65",
    "library-ide": "components/11-ide.ext.bin",
    "library-idex": "components/12-idex.ext.bin",
    "library-m65d": "components/13-m65d.ext.bin",
    "resolved-profile": "components/14-resolved-profile.txt",
    "linked-product-elf": "proof/product/lisp65-c2-lite-product.elf",
    "product-d81": "media/lisp65-product.d81",
    "product-mount-descriptor": "media/lisp65-product.mount.json",
    "work-d81": "media/lisp65-work.d81",
    "optional-library-d81": "media/lisp65-library.d81",
    "optional-library-index": "libraries/l65index",
    "library-string-extra": "libraries/string-extra.l65s",
    "library-inspect": "libraries/inspect.l65s",
}

DOCUMENTS = {
    "docs/release-notes.md": ROOT / "docs/releases/1.4.0.md",
    "docs/user-guide.md": ROOT / "docs/user-guide.md",
    "docs/language-reference.md": ROOT / "docs/language-reference.md",
    "docs/known-issues.md": ROOT / "docs/known-issues.md",
}

PROOFS = {
    "proof/shared-candidate-manifest.json": SHARED_MANIFEST,
    "proof/base-candidate-manifest.json": BASE_MANIFEST,
    "proof/release-closure.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.12-release-closure-receipt.json"),
    "proof/d1-boot-device.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.12-link92-r5-phase-d-split-d1-boot-device-receipt.json"),
    "proof/d1-smoke-device.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.12-link92-r5-phase-d-split-d1-smoke-device-receipt.json"),
    "proof/d3-device.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.12-link92-r5-phase-d-d3-device-receipt.json"),
    "proof/d2-selector-device.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.12-link92-r5-phase-d-d2-device-receipt.json"),
}


class PackageError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    require(
        value == path.as_posix() and not path.is_absolute()
        and value not in ("", ".") and ".." not in path.parts,
        f"unsafe package path: {value!r}")
    return value


def write_file(root: Path, relative: str, data: bytes, mode: int) -> Path:
    safe_relative(relative)
    path = root / relative
    require(not path.exists() and not path.is_symlink(),
            f"duplicate package path: {relative}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)
    return path


def identity_sha(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    projection = [
        {key: row[key] for key in keys}
        for row in sorted(rows, key=lambda row: tuple(row[key] for key in keys))
    ]
    return sha_bytes(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode())


def file_inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        require(not path.is_symlink(), f"package symlink: {path}")
        if path.is_file() and path != root / "manifest.json":
            rows.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "mode": f"0{stat.S_IMODE(path.stat().st_mode):03o}",
            })
    return rows


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    return identity_sha(rows, ("path", "bytes", "sha256", "mode"))


def run(argv: list[str], *, cwd: Path, label: str,
        env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise PackageError(
            f"{label} failed ({completed.returncode}):\n{completed.stdout}")
    return completed.stdout


def artifact_sources() -> dict[str, dict[str, Any]]:
    shared = load(SHARED_MANIFEST, "shared candidate manifest")
    base = load(BASE_MANIFEST, "base candidate manifest")
    require(
        shared.get("status") == "passed-complete-C2-lite-two-media-product"
        and shared.get("artifact_count") == 19,
        "shared candidate is not the accepted 19-role set")
    require(
        base.get("status") == "passed-closed-base-split-media-candidate"
        and base.get("variant") == "base"
        and base.get("selection", {}).get("conditional_defstruct_public") is False,
        "base candidate selection drift")
    rows = {row["role"]: dict(row) for row in shared["artifacts"]}
    library = base["library"]
    rows.update({
        "optional-library-d81": {
            "role": "optional-library-d81", "name": "lisp65-library.d81",
            **library["D81"]},
        "optional-library-index": {
            "role": "optional-library-index", "name": "l65index",
            **library["index"]},
        "library-string-extra": {
            "role": "library-string-extra", "name": "string-extra.l65s",
            **library["artifacts"]["string-extra"]},
        "library-inspect": {
            "role": "library-inspect", "name": "inspect.l65s",
            **library["artifacts"]["inspect"]},
    })
    require(set(rows) == set(ROLE_PATHS), "accepted role inventory drift")
    return rows


def validate_authorities(clean_receipt: Path, source_commit: str
                         ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    auth = load(AUTHORITY, "public build authority")
    clean = load(clean_receipt, "public clean-build receipt")
    sources = artifact_sources()
    sealed = auth.get("sealed_roles")
    require(
        auth.get("format") == "lisp65-c2-lite-public-build-authority-v2"
        and auth.get("release") == RELEASE
        and auth.get("selected_variant") == "base"
        and auth.get("artifact_count") == 23
        and isinstance(sealed, dict) and len(sealed) == 23,
        "public build authority drift")
    require(
        clean.get("format")
            == "lisp65-c2-lite-public-clean-build-receipt-v2"
        and clean.get("status") == "passed"
        and clean.get("source_commit") == source_commit
        and clean.get("artifact_count") == 23
        and clean.get("selected_variant") == "base"
        and clean.get("private_evidence_inputs") == 0
        and isinstance(clean.get("builds"), list)
        and len(clean["builds"]) == 2,
        "public clean-build qualification drift")
    clean_rows = {row["role"]: row for row in clean["artifacts"]}
    result: list[dict[str, Any]] = []
    for role in sorted(ROLE_PATHS):
        row = sources[role]
        source = ROOT / row["path"]
        require(
            source.is_file() and not source.is_symlink()
            and source.stat().st_size == row["bytes"]
            and sha(source) == row["sha256"],
            f"accepted artifact bytes drift: {role}")
        expected = sealed.get(role)
        observed = clean_rows.get(role)
        require(
            expected == {"bytes": row["bytes"], "sha256": row["sha256"]}
            and observed == {
                "role": role, "name": row["name"], "bytes": row["bytes"],
                "sha256": row["sha256"]},
            f"accepted/public-clean authority mismatch: {role}")
        result.append({
            "role": role, "name": row["name"],
            "ship_path": ROLE_PATHS[role], "source": source,
            "bytes": row["bytes"], "sha256": row["sha256"],
        })
    identity_rows = [{
        key: row[key] for key in ("role", "name", "bytes", "sha256")
    } for row in result]
    require(
        identity_sha(identity_rows, ("role", "name", "bytes", "sha256"))
            == auth["sealed_product_artifact_set_sha256"]
            == clean["artifact_set_sha256"],
        "23-role artifact-set identity drift")
    return clean, result


def readme(product_set: str) -> bytes:
    return (
        "LISP65 WORKBENCH 1.4.0\n"
        "========================\n\n"
        "This is the Halt-#1-selected Base release package.\n"
        f"Product artifact set: {product_set}\n\n"
        "Before use, run:  python3 verify.py\n\n"
        "Media:\n"
        "  media/lisp65-product.d81  bootable, read-only system medium\n"
        "  media/lisp65-work.d81     blank writable work medium\n"
        "  media/lisp65-library.d81  optional v1.4 libraries\n\n"
        "Optional packages:\n"
        "  (require 'string-extra)   capitalize, string-split\n"
        "  (require 'inspect)        who-calls\n\n"
        "Not delivered: trace, untrace, defstruct.\n"
        "See docs/release-notes.md and docs/known-issues.md.\n"
    ).encode("ascii")


VERIFIER = r'''#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"

def fail(message):
    print(f"lisp65 1.4.0 offline verification: FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def identity(rows, keys):
    projection = [
        {key: row[key] for key in keys}
        for row in sorted(rows, key=lambda row: tuple(row[key] for key in keys))
    ]
    return hashlib.sha256(json.dumps(
        projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

try:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
except Exception as error:
    fail(f"manifest unreadable: {error}")
if not (
    value.get("format") == "lisp65-v1.4.0-release-package-v1"
    and value.get("version") == 1
    and value.get("release") == "v1.4.0"
    and value.get("status") == "prepared-awaiting-owner-publication"
    and value.get("selected_variant") == "base"
    and value.get("release_authorized") is False
):
    fail("manifest envelope drift")
product = value.get("product", {})
rows = product.get("artifacts")
if not (isinstance(rows, list) and len(rows) == 23
        and product.get("artifact_count") == 23):
    fail("23-role inventory missing")
roles = set()
role_paths = set()
for row in rows:
    if set(row) != {"role", "name", "ship_path", "bytes", "sha256"}:
        fail("malformed product row")
    path = ROOT / row["ship_path"]
    if not (path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and digest(path) == row["sha256"]):
        fail(f"product byte drift: {row['role']}")
    roles.add(row["role"])
    role_paths.add(row["ship_path"])
if len(roles) != 23 or len(role_paths) != 23:
    fail("duplicate role or product path")
if identity(rows, ("role", "name", "bytes", "sha256")) \
        != product.get("artifact_set_sha256"):
    fail("artifact-set identity drift")
files = value.get("files")
if not isinstance(files, list) or not files:
    fail("package inventory missing")
bound = set()
for row in files:
    if set(row) != {"path", "bytes", "sha256", "mode"}:
        fail("malformed package row")
    path = ROOT / row["path"]
    mode = f"0{stat.S_IMODE(path.stat().st_mode):03o}" if path.exists() else ""
    if not (path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and digest(path) == row["sha256"] and mode == row["mode"]):
        fail(f"package byte/mode drift: {row['path']}")
    bound.add(row["path"])
actual = {
    path.relative_to(ROOT).as_posix()
    for path in ROOT.rglob("*") if path.is_file() and path != MANIFEST
}
if actual != bound or len(bound) != len(files):
    fail("unbound or duplicate package file")
if identity(files, ("path", "bytes", "sha256", "mode")) \
        != value.get("package_set_sha256"):
    fail("package-set identity drift")
claims = value.get("claims", {})
if not (
    claims.get("defstruct") == "not-delivered-D2-delivery-red-only"
    and claims.get("trace") == "not-delivered-awaits-core-ABI"
    and claims.get("editor") == "physical-64-of-64-no-stall-claim"
):
    fail("claim boundary drift")
print(
    "lisp65 1.4.0 offline verification: PASS "
    f"roles=23 files={len(files)} set={product['artifact_set_sha256']}")
'''.encode("ascii")


def build_product(root: Path, source_commit: str, clean: dict[str, Any],
                  artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    public_rows: list[dict[str, Any]] = []
    for row in artifacts:
        mode = 0o644 if row["role"] == "work-d81" else 0o444
        written = write_file(
            root, row["ship_path"], row["source"].read_bytes(), mode)
        require(sha(written) == row["sha256"],
                f"package copy drift: {row['role']}")
        public_rows.append({
            key: row[key]
            for key in ("role", "name", "ship_path", "bytes", "sha256")
        })
    for relative, source in DOCUMENTS.items():
        require(source.is_file(), f"release document missing: {source}")
        write_file(root, relative, source.read_bytes(), 0o444)
    for relative, source in PROOFS.items():
        require(source.is_file(), f"release proof missing: {source}")
        write_file(root, relative, source.read_bytes(), 0o444)
    write_file(root, "README-FIRST.txt", readme(clean["artifact_set_sha256"]), 0o444)
    write_file(root, "verify.py", VERIFIER, 0o555)
    files = file_inventory(root)
    manifest = {
        "format": "lisp65-v1.4.0-release-package-v1",
        "version": 1,
        "release": RELEASE,
        "status": "prepared-awaiting-owner-publication",
        "release_authorized": False,
        "selected_variant": "base",
        "source_commit": source_commit,
        "prepared_on": PREPARED_ON,
        "product": {
            "artifact_count": 23,
            "artifact_set_sha256": clean["artifact_set_sha256"],
            "product_build_id": clean["product_build_id"],
            "profile_build_id": clean["profile_build_id"],
            "resident_delta_bytes": 0,
            "bank2_reserve_bytes": 14270,
            "artifacts": public_rows,
        },
        "clean_build": {
            "builds": 2,
            "entry_point": clean["entry_point"],
            "private_evidence_inputs": 0,
            "source_commit": source_commit,
        },
        "claims": {
            "banner": "WORKBENCH 1.4.0-on-physical-MEGA65",
            "surface": ["who-calls", "capitalize", "string-split"],
            "defstruct": "not-delivered-D2-delivery-red-only",
            "trace": "not-delivered-awaits-core-ABI",
            "untrace": "not-delivered-awaits-core-ABI",
            "editor": "physical-64-of-64-no-stall-claim",
            "D2_mechanism": "not-claimed",
        },
        "files": files,
        "package_set_sha256": package_set_sha(files),
    }
    write_file(root, "manifest.json", canonical(manifest), 0o444)
    return manifest


def tar_entries_from_directory(root: Path) -> list[tuple[str, int, bytes]]:
    result: list[tuple[str, int, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        require(not path.is_symlink(), f"archive input symlink: {path}")
        if path.is_file():
            result.append((
                f"{TOP}/{path.relative_to(root).as_posix()}",
                stat.S_IMODE(path.stat().st_mode), path.read_bytes()))
    return result


def git_source_entries(repository: Path, source_commit: str
                       ) -> list[tuple[str, int, bytes]]:
    output = subprocess.run(
        ["git", "ls-tree", "-rz", source_commit], cwd=repository,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(output.returncode == 0, "cannot enumerate public source commit")
    rows: list[tuple[str, int, bytes]] = []
    for raw in output.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, encoded_path = raw.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split()
        require(kind == "blob" and mode in ("100644", "100755"),
                f"unsupported public source object: {encoded_path!r}")
        relative = encoded_path.decode("utf-8")
        safe_relative(relative)
        blob = subprocess.run(
            ["git", "cat-file", "blob", object_id], cwd=repository,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(blob.returncode == 0, f"cannot read source blob: {relative}")
        rows.append((
            f"{TOP}/{relative}",
            0o755 if mode == "100755" else 0o644,
            blob.stdout))
    require(any(name.endswith("/PUBLIC-SOURCE-MANIFEST.json")
                for name, _, _ in rows),
            "public source commit lacks its embedded source manifest")
    return sorted(rows)


def deterministic_tar_gz(entries: list[tuple[str, int, bytes]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    directories = {TOP}
    for name, _, _ in entries:
        parts = PurePosixPath(name).parts
        for index in range(1, len(parts)):
            directories.add(PurePosixPath(*parts[:index]).as_posix())
    with output.open("wb") as raw:
        with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, compresslevel=9,
                mtime=0) as compressed:
            with tarfile.open(
                    fileobj=compressed, mode="w",
                    format=tarfile.GNU_FORMAT) as archive:
                for name in sorted(directories):
                    info = tarfile.TarInfo(name + "/")
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = SOURCE_EPOCH
                    archive.addfile(info)
                for name, mode, data in sorted(entries):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = mode
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = SOURCE_EPOCH
                    archive.addfile(info, BytesIO(data))


def verify_product(root: Path) -> str:
    return run(
        [sys.executable, "verify.py"], cwd=root,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
        label="embedded product verification").strip()


def verify_source_archive(archive: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="lisp65-v140-source-verify-") as raw:
        root = Path(raw)
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(root, filter="fully_trusted")
        source = root / TOP
        sys.path.insert(0, str(ROOT / "tools/host-lisp"))
        import public_export  # pylint: disable=import-outside-toplevel
        errors = public_export.verify_snapshot(source)
        require(not errors, "source archive manifest failed: " + "; ".join(errors))
        manifest = load(
            source / "PUBLIC-SOURCE-MANIFEST.json", "source manifest")
        return int(manifest["file_count"])


def verify_product_archive(archive: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="lisp65-v140-product-verify-") as raw:
        root = Path(raw)
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(root, filter="fully_trusted")
        return verify_product(root / TOP)


def prepare(source_repository: Path, source_commit: str,
            clean_receipt: Path, output: Path) -> dict[str, Any]:
    source_repository = source_repository.resolve()
    resolved = run(
        ["git", "rev-parse", f"{source_commit}^{{commit}}"],
        cwd=source_repository, label="resolve public candidate").strip()
    require(resolved == source_commit and len(resolved) == 40,
            "source commit must be the exact full candidate identity")
    for source in DOCUMENTS.values():
        relative = source.relative_to(ROOT).as_posix()
        candidate = subprocess.run(
            ["git", "show", f"{source_commit}:{relative}"],
            cwd=source_repository, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False)
        require(
            candidate.returncode == 0 and candidate.stdout == source.read_bytes(),
            f"release document differs from public candidate: {relative}")
    clean, artifacts = validate_authorities(clean_receipt, source_commit)
    release_root = ROOT / "build/release-v1.4.0"
    stage_a = release_root / "pack-product-a" / TOP
    stage_b = release_root / "pack-product-b" / TOP
    manifest_a = build_product(stage_a, source_commit, clean, artifacts)
    manifest_b = build_product(stage_b, source_commit, clean, artifacts)
    require(manifest_a == manifest_b, "varied product staging differs")
    verify_a = verify_product(stage_a)
    verify_b = verify_product(stage_b)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    product_a = release_root / "lisp65-1.4.0-product-a.tar.gz"
    product_b = release_root / "lisp65-1.4.0-product-b.tar.gz"
    deterministic_tar_gz(tar_entries_from_directory(stage_a), product_a)
    deterministic_tar_gz(tar_entries_from_directory(stage_b), product_b)
    require(product_a.read_bytes() == product_b.read_bytes(),
            "product double-pack is not byte-identical")
    product_asset = output / f"{TOP}.tar.gz"
    product_asset.write_bytes(product_a.read_bytes())
    product_verify = verify_product_archive(product_asset)

    source_entries = git_source_entries(source_repository, source_commit)
    source_a = release_root / "lisp65-1.4.0-source-a.tar.gz"
    source_b = release_root / "lisp65-1.4.0-source-b.tar.gz"
    deterministic_tar_gz(source_entries, source_a)
    deterministic_tar_gz(source_entries, source_b)
    require(source_a.read_bytes() == source_b.read_bytes(),
            "source double-pack is not byte-identical")
    source_asset = output / f"{TOP}-source.tar.gz"
    source_asset.write_bytes(source_a.read_bytes())
    source_files = verify_source_archive(source_asset)

    manifest_asset = output / f"{TOP}-manifest.json"
    manifest_asset.write_bytes(canonical(manifest_a))
    clean_asset = output / f"{TOP}-clean-build-receipt.json"
    clean_asset.write_bytes(clean_receipt.read_bytes())
    require(load(clean_asset, "copied clean receipt") == clean,
            "clean-build receipt copy drift")
    assets = []
    for path in (product_asset, manifest_asset, source_asset, clean_asset):
        assets.append({
            "name": path.name, "bytes": path.stat().st_size,
            "sha256": sha(path)})
    result = {
        "format": "lisp65-v140-release-package-preparation-v1",
        "status": "passed-awaiting-halt-2",
        "release": RELEASE,
        "source_commit": source_commit,
        "source_parent": run(
            ["git", "show", "-s", "--format=%P", source_commit],
            cwd=source_repository, label="read public candidate parent").strip(),
        "source_tree": run(
            ["git", "show", "-s", "--format=%T", source_commit],
            cwd=source_repository, label="read public candidate tree").strip(),
        "product": {
            "artifact_count": 23,
            "artifact_set_sha256": clean["artifact_set_sha256"],
            "selected_variant": "base",
            "selected_library_d81_sha256":
                "1a77a2f5d71c58ef8e9650316d7d0103675fd419b5aa96d37e8f44e7b24186b7",
            "resident_delta_bytes": 0,
            "bank2_reserve_bytes": 14270,
        },
        "clean_build": {
            "builds": 2, "source_commit": source_commit,
            "private_evidence_inputs": 0,
            "receipt_sha256": sha(clean_asset),
        },
        "verification": {
            "product_stage_a": verify_a,
            "product_stage_b": verify_b,
            "product_archive": product_verify,
            "product_double_pack": "passed-byte-identical",
            "source_double_pack": "passed-byte-identical",
            "source_manifest_files": source_files,
        },
        "assets": assets,
        "authorization": {
            "required_owner_word": "Publish",
            "decision": None,
            "public_refs_changed": 0,
            "public_releases_changed": 0,
        },
    }
    receipt = release_root / "v1.4.0-package-preparation-receipt.json"
    receipt.write_bytes(canonical(result))
    return result


def check(publish: Path) -> dict[str, Any]:
    manifest_path = publish / f"{TOP}-manifest.json"
    clean_path = publish / f"{TOP}-clean-build-receipt.json"
    product_path = publish / f"{TOP}.tar.gz"
    source_path = publish / f"{TOP}-source.tar.gz"
    for path in (manifest_path, clean_path, product_path, source_path):
        require(path.is_file() and not path.is_symlink(),
                f"release asset missing: {path.name}")
    require(
        {path.name for path in publish.iterdir()} == {
            path.name for path in (
                manifest_path, clean_path, product_path, source_path)},
        "publish directory is not the exact four-asset set")
    manifest = load(manifest_path, "release manifest")
    clean = load(clean_path, "clean-build receipt")
    require(
        manifest.get("source_commit") == clean.get("source_commit")
        and manifest.get("product", {}).get("artifact_set_sha256")
            == clean.get("artifact_set_sha256"),
        "release asset authority mismatch")
    verify_product_archive(product_path)
    verify_source_archive(source_path)
    return {
        "assets": 4, "roles": 23,
        "source_commit": clean["source_commit"],
        "artifact_set_sha256": clean["artifact_set_sha256"],
    }


def selftest() -> None:
    rows = [{
        "path": "a", "bytes": 1, "sha256": "0" * 64, "mode": "0444"
    }, {
        "path": "b", "bytes": 2, "sha256": "1" * 64, "mode": "0555"
    }]
    baseline = package_set_sha(rows)
    mutations = []
    for key, value in (
            ("path", "c"), ("bytes", 3), ("sha256", "2" * 64),
            ("mode", "0644")):
        candidate = [dict(row) for row in rows]
        candidate[0][key] = value
        mutations.append(package_set_sha(candidate) != baseline)
    require(all(mutations), "package identity mutation survived")
    with tempfile.TemporaryDirectory(prefix="lisp65-v140-tar-selftest-") as raw:
        root = Path(raw)
        entries = [(f"{TOP}/a", 0o444, b"a")]
        first, second = root / "a.tar.gz", root / "b.tar.gz"
        deterministic_tar_gz(entries, first)
        deterministic_tar_gz(entries, second)
        require(first.read_bytes() == second.read_bytes(),
                "deterministic tar selftest failed")
    print("c2-v140-release-package: SELFTEST PASS mutations=4 double-pack=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("selftest")
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-repository", type=Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument(
        "--clean-receipt", type=Path, default=DEFAULT_CLEAN_RECEIPT)
    prepare_parser.add_argument(
        "--output", type=Path,
        default=ROOT / "build/release-v1.4.0/publish")
    check_parser = sub.add_parser("check")
    check_parser.add_argument(
        "--publish", type=Path,
        default=ROOT / "build/release-v1.4.0/publish")
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
        elif args.action == "prepare":
            result = prepare(
                args.source_repository, args.source_commit,
                args.clean_receipt.resolve(), args.output.resolve())
            print(
                "c2-v140-release-package: PREPARED "
                f"assets=4 roles=23 source={result['source_commit']} "
                f"set={result['product']['artifact_set_sha256']}")
        else:
            result = check(args.publish.resolve())
            print(
                "c2-v140-release-package: CHECK PASS "
                f"assets={result['assets']} roles={result['roles']} "
                f"source={result['source_commit']}")
        return 0
    except (PackageError, OSError, KeyError, ValueError) as error:
        print(f"c2-v140-release-package: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
