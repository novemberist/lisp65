#!/usr/bin/env python3
"""Prepare and twice verify the four immutable v1.6.0 Halt-#2 assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v140_release_package as COMMON  # noqa: E402


VERSION = "1.6.0"
RELEASE = f"v{VERSION}"
TOP = f"lisp65-{VERSION}"
PREPARED_ON = "2026-08-25"
SOURCE_EPOCH = 1787616000
AUTHORITY = ROOT / "config/c2-v160-public-build-authority.json"
DEFAULT_CLEAN_RECEIPT = ROOT / (
    "build/release-v1.6.0/v1.6.0-public-clean-build-receipt.json")
DEFAULT_PRODUCT_ROOT = ROOT

COMMON.TOP = TOP
COMMON.SOURCE_EPOCH = SOURCE_EPOCH

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
    "library-v16core": "libraries/v16core.l65s",
}

DOCUMENTS = {
    "docs/release-notes.md": ROOT / "docs/releases/1.6.0.md",
    "docs/user-guide.md": ROOT / "docs/user-guide.md",
    "docs/language-reference.md": ROOT / "docs/language-reference.md",
    "docs/known-issues.md": ROOT / "docs/known-issues.md",
}

PROOFS = {
    "proof/device-session.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.6-item1-only-r1-public2-device-result-receipt.json"),
    "proof/d5-headroom.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.6-item1-d5-result-receipt.json"),
    "proof/candidate-seal.json": ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-v1.6-candidate-seal-receipt.json"),
}


class PackageError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PackageError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def run(argv: list[str], *, cwd: Path, label: str) -> str:
    result = subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"{label} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout


def artifact_sources(product_root: Path) -> dict[str, dict[str, Any]]:
    authority = load(AUTHORITY, "v1.6 public authority")
    relative = authority["candidate_manifest_path"]
    manifest = load(product_root / relative, "selected public product manifest")
    rows = {row["role"]: dict(row) for row in manifest.get("artifacts", [])}
    require(
        manifest.get("format") == "lisp65-v1.6-public-selected-product-v1"
        and manifest.get("status")
            == "passed-public-source-selected-v1.6-item1-product"
        and manifest.get("artifact_count") == 22
        and manifest.get("artifact_set_sha256")
            == authority["sealed_product_artifact_set_sha256"]
        and set(rows) == set(ROLE_PATHS),
        "selected v1.6 product manifest drift")
    for role, row in rows.items():
        source = product_root / row["path"]
        expected = authority["sealed_roles"][role]
        require(
            source.is_file() and not source.is_symlink()
            and source.stat().st_size == row["bytes"] == expected["bytes"]
            and sha(source) == row["sha256"] == expected["sha256"],
            f"selected v1.6 product byte drift: {role}")
        row["source"] = source
    return rows


def validate_authorities(product_root: Path, clean_receipt: Path,
                         source_commit: str
                         ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    authority = load(AUTHORITY, "v1.6 public authority")
    clean = load(clean_receipt, "v1.6 clean-build receipt")
    sources = artifact_sources(product_root)
    require(
        authority.get("format") == "lisp65-c2-public-build-authority-v4"
        and authority.get("release") == RELEASE
        and authority.get("selected_variant") == "v1.6-item-1-only"
        and authority.get("artifact_count") == 22
        and clean.get("format")
            == "lisp65-c2-v160-public-clean-build-receipt-v1"
        and clean.get("status") == "passed"
        and clean.get("source_commit") == source_commit
        and clean.get("artifact_count") == 22
        and clean.get("selected_variant") == "v1.6-item-1-only"
        and clean.get("private_evidence_inputs") == 0
        and isinstance(clean.get("builds"), list) and len(clean["builds"]) == 2
        and clean.get("artifact_set_sha256")
            == authority["sealed_product_artifact_set_sha256"],
        "v1.6 public authority/clean-build mismatch")
    clean_rows = {row["role"]: row for row in clean["artifacts"]}
    result = []
    for role in sorted(ROLE_PATHS):
        row = sources[role]
        require(clean_rows.get(role) == {
            key: row[key] for key in ("role", "name", "bytes", "sha256")},
            f"clean build differs from selected artifact: {role}")
        result.append({
            "role": role, "name": row["name"],
            "ship_path": ROLE_PATHS[role], "source": row["source"],
            "bytes": row["bytes"], "sha256": row["sha256"],
        })
    return clean, result


def readme(product_set: str) -> bytes:
    return (
        "LISP65 WORKBENCH 1.6.0\n"
        "========================\n\n"
        "This is the Halt-#1-selected v1.6 release package.\n"
        f"Product artifact set: {product_set}\n\n"
        "Before use, run:  python3 verify.py\n\n"
        "Media:\n"
        "  media/lisp65-product.d81  bootable, read-only system medium\n"
        "  media/lisp65-work.d81     blank writable work medium\n"
        "  media/lisp65-library.d81  optional v1.6 libraries\n\n"
        "Optional package:\n"
        "  (require 'v16core)        insertion-mode REPL navigation\n\n"
        "See docs/release-notes.md and docs/known-issues.md.\n"
    ).encode("ascii")


VERIFIER = r'''#!/usr/bin/env python3
import hashlib, json, stat, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
def fail(message):
    print(f"lisp65 1.6.0 offline verification: FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def identity(rows, keys):
    projection = [{key: row[key] for key in keys}
                  for row in sorted(rows, key=lambda row: tuple(row[key] for key in keys))]
    return hashlib.sha256(json.dumps(projection, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
try: value = json.loads(MANIFEST.read_text(encoding="utf-8"))
except Exception as error: fail(f"manifest unreadable: {error}")
if not (value.get("format") == "lisp65-v1.6.0-release-package-v1"
        and value.get("release") == "v1.6.0"
        and value.get("status") == "prepared-awaiting-owner-publication"
        and value.get("release_authorized") is False
        and value.get("selected_variant") == "v1.6-item-1-only"):
    fail("manifest envelope drift")
product = value.get("product", {}); rows = product.get("artifacts")
if not (isinstance(rows, list) and len(rows) == 22
        and product.get("artifact_count") == 22): fail("22-role inventory missing")
roles = set(); paths = set()
for row in rows:
    if set(row) != {"role", "name", "ship_path", "bytes", "sha256"}:
        fail("malformed product row")
    path = ROOT / row["ship_path"]
    if not (path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and digest(path) == row["sha256"]): fail(f"product drift: {row['role']}")
    roles.add(row["role"]); paths.add(row["ship_path"])
if len(roles) != 22 or len(paths) != 22: fail("duplicate role or ship path")
if identity(rows, ("role", "name", "bytes", "sha256")) \
        != product.get("artifact_set_sha256"): fail("artifact-set identity drift")
files = value.get("files"); bound = set()
if not isinstance(files, list): fail("package inventory missing")
for row in files:
    path = ROOT / row["path"]
    mode = f"0{stat.S_IMODE(path.stat().st_mode):03o}" if path.exists() else ""
    if not (path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]
            and mode == row["mode"]): fail(f"package drift: {row['path']}")
    bound.add(row["path"])
actual = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*")
          if path.is_file() and path != MANIFEST}
if actual != bound or len(bound) != len(files): fail("unbound package file")
if identity(files, ("path", "bytes", "sha256", "mode")) \
        != value.get("package_set_sha256"): fail("package-set identity drift")
claims = value.get("claims", {})
if not (claims.get("cursor_navigation") == "hardware-green-insertion-mode"
        and claims.get("boot_refill") == "MAP-CPU-content-converged"
        and claims.get("retired_overlay_recovery")
            == "hardware-green-type-error-to-native-prompt"
        and claims.get("comfort_repl") == "not-delivered"
        and claims.get("line_atomic_input") == "not-claimed"):
    fail("claim boundary drift")
print(f"lisp65 1.6.0 offline verification: PASS roles=22 files={len(files)} "
      f"set={product['artifact_set_sha256']}")
'''.encode("ascii")


def build_product(root: Path, source_commit: str, clean: dict[str, Any],
                  artifacts: list[dict[str, Any]], product_root: Path
                  ) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    public_rows = []
    for row in artifacts:
        mode = 0o644 if row["role"] == "work-d81" else 0o444
        COMMON.write_file(root, row["ship_path"], row["source"].read_bytes(), mode)
        public_rows.append({key: row[key] for key in
                            ("role", "name", "ship_path", "bytes", "sha256")})
    for relative, source in DOCUMENTS.items():
        require(source.is_file(), f"release document missing: {source}")
        COMMON.write_file(root, relative, source.read_bytes(), 0o444)
    for relative, source in PROOFS.items():
        require(source.is_file(), f"release proof missing: {source}")
        COMMON.write_file(root, relative, source.read_bytes(), 0o444)
    selected_manifest = product_root / load(
        AUTHORITY, "authority")["candidate_manifest_path"]
    COMMON.write_file(root, "proof/public-selected-manifest.json",
                      selected_manifest.read_bytes(), 0o444)
    COMMON.write_file(root, "README-FIRST.txt",
                      readme(clean["artifact_set_sha256"]), 0o444)
    COMMON.write_file(root, "verify.py", VERIFIER, 0o555)
    files = COMMON.file_inventory(root)
    manifest = {
        "format": "lisp65-v1.6.0-release-package-v1",
        "version": 1, "release": RELEASE,
        "status": "prepared-awaiting-owner-publication",
        "release_authorized": False,
        "selected_variant": "v1.6-item-1-only",
        "source_commit": source_commit, "prepared_on": PREPARED_ON,
        "product": {
            "artifact_count": 22,
            "artifact_set_sha256": clean["artifact_set_sha256"],
            "product_build_id": clean["product_build_id"],
            "profile_build_id": clean["profile_build_id"],
            "user_headroom": {"symbol_slots": 105, "namepool_bytes": 1413},
            "artifacts": public_rows,
        },
        "clean_build": {"builds": 2, "entry_point": clean["entry_point"],
                        "private_evidence_inputs": 0,
                        "source_commit": source_commit},
        "claims": {
            "banner": "WORKBENCH 1.6.0-on-physical-MEGA65",
            "surface": ["v16core", "cursor-left", "cursor-right",
                        "control-b", "control-f", "control-a", "control-e",
                        "delete-backward", "control-d"],
            "cursor_navigation": "hardware-green-insertion-mode",
            "boot_refill": "MAP-CPU-content-converged",
            "retired_overlay_recovery":
                "hardware-green-type-error-to-native-prompt",
            "comfort_repl": "not-delivered",
            "line_atomic_input": "not-claimed",
        },
        "files": files, "package_set_sha256": COMMON.package_set_sha(files),
    }
    COMMON.write_file(root, "manifest.json", canonical(manifest), 0o444)
    return manifest


def prepare(source_repository: Path, source_commit: str, product_root: Path,
            clean_receipt: Path, output: Path) -> dict[str, Any]:
    source_repository = source_repository.resolve()
    source_commit = run(
        ["git", "rev-parse", f"{source_commit}^{{commit}}"],
        cwd=source_repository, label="resolve public candidate").strip()
    clean, artifacts = validate_authorities(
        product_root.resolve(), clean_receipt, source_commit)
    release_root = ROOT / "build/release-v1.6.0"
    stage_a = release_root / "pack-product-a" / TOP
    stage_b = release_root / "pack-product-b" / TOP
    manifest_a = build_product(
        stage_a, source_commit, clean, artifacts, product_root.resolve())
    manifest_b = build_product(
        stage_b, source_commit, clean, artifacts, product_root.resolve())
    require(manifest_a == manifest_b, "v1.6 varied product staging differs")
    stage_verify = [COMMON.verify_product(stage_a), COMMON.verify_product(stage_b)]

    product_a = release_root / f"{TOP}-product-a.tar.gz"
    product_b = release_root / f"{TOP}-product-b.tar.gz"
    COMMON.deterministic_tar_gz(COMMON.tar_entries_from_directory(stage_a), product_a)
    COMMON.deterministic_tar_gz(COMMON.tar_entries_from_directory(stage_b), product_b)
    require(product_a.read_bytes() == product_b.read_bytes(),
            "v1.6 product double-pack differs")
    product_archive_verify = [COMMON.verify_product_archive(product_a),
                              COMMON.verify_product_archive(product_b)]

    source_entries = COMMON.git_source_entries(source_repository, source_commit)
    source_a = release_root / f"{TOP}-source-a.tar.gz"
    source_b = release_root / f"{TOP}-source-b.tar.gz"
    COMMON.deterministic_tar_gz(source_entries, source_a)
    COMMON.deterministic_tar_gz(source_entries, source_b)
    require(source_a.read_bytes() == source_b.read_bytes(),
            "v1.6 source double-pack differs")
    source_archive_verify = [COMMON.verify_source_archive(source_a),
                             COMMON.verify_source_archive(source_b)]

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    product_asset = output / f"{TOP}.tar.gz"
    source_asset = output / f"{TOP}-source.tar.gz"
    manifest_asset = output / f"{TOP}-manifest.json"
    clean_asset = output / f"{TOP}-clean-build-receipt.json"
    product_asset.write_bytes(product_a.read_bytes())
    source_asset.write_bytes(source_a.read_bytes())
    manifest_asset.write_bytes(canonical(manifest_a))
    clean_asset.write_bytes(clean_receipt.read_bytes())
    final_verify = [COMMON.verify_product_archive(product_asset),
                    COMMON.verify_source_archive(source_asset)]
    assets = [{"name": path.name, "bytes": path.stat().st_size,
               "sha256": sha(path)} for path in
              (product_asset, manifest_asset, source_asset, clean_asset)]
    value = {
        "format": "lisp65-v160-release-package-preparation-v1",
        "status": "passed-awaiting-halt-2", "release": RELEASE,
        "source_commit": source_commit,
        "source_parent": run(
            ["git", "show", "-s", "--format=%P", source_commit],
            cwd=source_repository, label="read candidate parent").strip(),
        "source_tree": run(
            ["git", "show", "-s", "--format=%T", source_commit],
            cwd=source_repository, label="read candidate tree").strip(),
        "product": {"artifact_count": 22,
                    "artifact_set_sha256": clean["artifact_set_sha256"],
                    "selected_variant": "v1.6-item-1-only",
                    "selected_library_d81_sha256":
                        load(AUTHORITY, "authority")["sealed_roles"]
                            ["optional-library-d81"]["sha256"],
                    "delivered_library_roles": ["v16core"]},
        "clean_build": {"builds": 2, "source_commit": source_commit,
                        "private_evidence_inputs": 0,
                        "receipt_sha256": sha(clean_asset)},
        "verification": {
            "product_stage_readbacks": stage_verify,
            "product_archive_readbacks": product_archive_verify,
            "source_archive_file_counts": source_archive_verify,
            "final_asset_readback": final_verify,
            "product_double_pack": "passed-byte-identical",
            "source_double_pack": "passed-byte-identical",
        },
        "assets": assets,
        "authorization": {"required_owner_word": "Publish", "decision": None,
                          "public_refs_changed": 0,
                          "public_releases_changed": 0},
    }
    receipt = release_root / "v1.6.0-package-preparation-receipt.json"
    receipt.write_bytes(canonical(value))
    return value


def check(publish: Path) -> dict[str, Any]:
    expected = {
        f"{TOP}.tar.gz", f"{TOP}-source.tar.gz",
        f"{TOP}-manifest.json", f"{TOP}-clean-build-receipt.json"}
    require(publish.is_dir()
            and {path.name for path in publish.iterdir()} == expected,
            "v1.6 publish directory is not the exact four-asset set")
    manifest = load(publish / f"{TOP}-manifest.json", "release manifest")
    clean = load(publish / f"{TOP}-clean-build-receipt.json", "clean receipt")
    require(manifest.get("source_commit") == clean.get("source_commit")
            and manifest.get("product", {}).get("artifact_set_sha256")
                == clean.get("artifact_set_sha256"),
            "v1.6 release asset authority mismatch")
    COMMON.verify_product_archive(publish / f"{TOP}.tar.gz")
    COMMON.verify_source_archive(publish / f"{TOP}-source.tar.gz")
    return {"assets": 4, "roles": 22,
            "source_commit": clean["source_commit"],
            "artifact_set_sha256": clean["artifact_set_sha256"]}


def selftest() -> None:
    rows = [{"path": "a", "bytes": 1, "sha256": "0" * 64, "mode": "0444"},
            {"path": "b", "bytes": 2, "sha256": "1" * 64, "mode": "0555"}]
    baseline = COMMON.package_set_sha(rows)
    for key, value in (("path", "c"), ("bytes", 3),
                       ("sha256", "2" * 64), ("mode", "0644")):
        candidate = [dict(row) for row in rows]; candidate[0][key] = value
        require(COMMON.package_set_sha(candidate) != baseline,
                f"v1.6 package mutation survived: {key}")
    with tempfile.TemporaryDirectory(prefix="lisp65-v160-tar-selftest-") as raw:
        first, second = Path(raw) / "a.tar.gz", Path(raw) / "b.tar.gz"
        entries = [(f"{TOP}/a", 0o444, b"a")]
        COMMON.deterministic_tar_gz(entries, first)
        COMMON.deterministic_tar_gz(entries, second)
        require(first.read_bytes() == second.read_bytes(),
                "v1.6 deterministic archive selftest failed")
    print("c2-v160-release-package: SELFTEST PASS mutations=4 double-pack=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("selftest")
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-repository", type=Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    prepare_parser.add_argument("--product-root", type=Path,
                                default=DEFAULT_PRODUCT_ROOT)
    prepare_parser.add_argument("--clean-receipt", type=Path,
                                default=DEFAULT_CLEAN_RECEIPT)
    prepare_parser.add_argument("--output", type=Path,
                                default=ROOT / "build/release-v1.6.0/publish")
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--publish", type=Path,
                              default=ROOT / "build/release-v1.6.0/publish")
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
        elif args.action == "prepare":
            result = prepare(args.source_repository, args.source_commit,
                             args.product_root, args.clean_receipt.resolve(),
                             args.output.resolve())
            print("c2-v160-release-package: PREPARED "
                  f"assets=4 roles=22 source={result['source_commit']} "
                  f"set={result['product']['artifact_set_sha256']}")
        else:
            result = check(args.publish.resolve())
            print("c2-v160-release-package: CHECK PASS "
                  f"assets=4 roles=22 source={result['source_commit']}")
        return 0
    except (PackageError, COMMON.PackageError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v160-release-package: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
