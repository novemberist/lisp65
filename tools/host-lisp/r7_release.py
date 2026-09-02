#!/usr/bin/env python3
"""Materialize, verify and record the private lisp65 1.0.1-light bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

from history_transport_rewrite import resolve_commit


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/r7-release-contract.json"
REGISTER = ROOT / "config/promotion-register.json"
PREREQ_MANIFEST = ROOT / "tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites.json"
PREREQ_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/r7/public-manifest-prerequisites-receipt.json"
CURRENT_SHIP_MANIFEST = ROOT / "build/r6/ship/manifest.json"
PACKAGE_REBIND = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-101-package-rebind-receipt.json"
STATIC_PREFLIGHT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-101-static-preflight-receipt.json"
PROFILE_APPLICABILITY = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/r6-g6-101-profile-applicability-receipt.json"
PACKER = ROOT / "tools/host-lisp/r7_release.py"
OFFLINE = ROOT / "tools/host-lisp/r7_release_offline.py"
FORMAT = "lisp65-r7-release-manifest-v1"
RECEIPT_FORMAT = "lisp65-r7-release-receipt-v1"
PRODUCT_SET = "c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165"
SOURCE_COMMIT = "547947116b9660042488a63c0ae336c4cb926eeb"
SOURCE_SEAL_SHA = "b339a274a97c947025ce66b09cd54ce5af73e24d8a99328fcb0659ffa605ddba"
SEALED_SHIP_MANIFEST_SHA = "323d6f497c1849af3916cfbe9c3f0d73936eaa72f271d97412666f25369f6764"
G6_RECEIPT_SHA = "edcca70cc747be2b42ab20ee96c74dceb46e490125dc4c6d740a7d1b4c369b7d"
CURRENT_SHIP_MANIFEST_SHA = "e04f3f99589ba956ec2e9bb21e932a4f4bb5fe18e85a07fe463c42252d2c8801"
PACKAGE_REBIND_SHA = "18b3993cc3b1946ba925dd5ad2f26dd378959e0656d1d44e27b461785131f80a"
STATIC_PREFLIGHT_SHA = "c920bab3dcbdfc4b48e4b9bbd1eb3aec6d8150124910843e246db439171981b6"
PROFILE_APPLICABILITY_SHA = "68004ed076eff7c0c7d1d91030279a18fc061b7ee9cd06df960726a6c4fadd17"
ARCHIVE_ROOT = "lisp65-1.0.1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"{label} must contain an object")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise ReleaseError(f"{label} is not canonical")
    return value


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R7 release contract")
    if (
        value.get("format") != "lisp65-r7-release-contract-v1"
        or value.get("version") != 1 or value.get("id") != "lisp65-private-release-v1.0.1-light"
        or value.get("status") != "owner-authorized"
        or value.get("release") != {
            "product": "lisp65", "version": "1.0.1", "tag": "v1.0.1",
            "tag_type": "annotated", "tag_target": SOURCE_COMMIT,
            "bundle": "releases/lisp65-1.0.1.tar.gz", "visibility": "private-mirror",
        }
        or value.get("product") != {
            "dialect": "v2", "artifact_set_sha256": PRODUCT_SET,
            "artifact_count": 13, "product_sha_changes": 0,
        }
        or value.get("input") != {
            "promotion_id": "r6-g6-hardware-acceptance-aed1595",
            "archive": "tests/bytecode/dialect-v2/evidence/promotions/r6-g6-hardware-acceptance-aed1595.tar.gz",
            "archive_sha256": SOURCE_SEAL_SHA,
            "ship_manifest_sha256": SEALED_SHIP_MANIFEST_SHA,
            "g6_receipt_sha256": G6_RECEIPT_SHA,
            "current_ship_manifest": CURRENT_SHIP_MANIFEST.relative_to(ROOT).as_posix(),
            "current_ship_manifest_sha256": CURRENT_SHIP_MANIFEST_SHA,
            "package_rebind_receipt": PACKAGE_REBIND.relative_to(ROOT).as_posix(),
            "package_rebind_receipt_sha256": PACKAGE_REBIND_SHA,
            "static_preflight_receipt": STATIC_PREFLIGHT.relative_to(ROOT).as_posix(),
            "static_preflight_receipt_sha256": STATIC_PREFLIGHT_SHA,
            "profile_applicability_receipt": PROFILE_APPLICABILITY.relative_to(ROOT).as_posix(),
            "profile_applicability_receipt_sha256": PROFILE_APPLICABILITY_SHA,
        }
        or value.get("prerequisites") != {
            "manifest": PREREQ_MANIFEST.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(PREREQ_MANIFEST),
            "receipt": PREREQ_RECEIPT.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(PREREQ_RECEIPT),
        }
        or value.get("policy") != {
            "operation": "documentation-and-package-only",
            "product_byte_source": "registered-r6-g6-seal-only",
            "live_tree_product_authority": False,
            "product_byte_identity": "required-against-sealed-r6-ship-for-all-13-artifacts",
            "self_contained": True,
            "offline_verification": "bundle-alone-no-repository-no-network",
            "double_pack_axes": ["PYTHONHASHSEED", "TZ"],
            "negative_tests": ["product-byte", "manifest", "source-seal", "package-rebind", "readme"],
            "tag_after_bundle_verification": True,
        }
        or value.get("claims") != {
            "G3": "passed-emulator-prefilter-only",
            "G5": "passed-for-product-artifact-set",
            "G6": "G6: 5/5 anwendbare Hardwarefälle bestanden; product-medium-physical-write-protect n/a: kein physisches Medium in der SD-D81-Konfiguration",
            "release": "private-release-v1.0.1-light",
        }
    ):
        raise ReleaseError("R7 release contract semantic drift")
    return value


def git_value(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise ReleaseError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def source_commit_timestamp() -> tuple[str, int]:
    transport_commit = resolve_commit(SOURCE_COMMIT)
    if git_value("rev-parse", f"{transport_commit}^{{commit}}") != transport_commit:
        raise ReleaseError("R7 tag target is unavailable")
    timestamp = git_value("show", "-s", "--format=%cI", transport_commit)
    epoch = git_value("show", "-s", "--format=%ct", transport_commit)
    if not epoch.isdigit() or "T" not in timestamp:
        raise ReleaseError("R7 tag-target timestamp is unavailable")
    return timestamp, int(epoch)


def registered_seal(value: dict[str, Any]) -> Path:
    register = load(REGISTER, "promotion register")
    rows = register.get("promotions")
    match = next((row for row in rows if isinstance(row, dict) and row.get("id") == value["input"]["promotion_id"]), None) if isinstance(rows, list) else None
    if (
        not isinstance(match, dict) or match.get("kind") != "hardware-acceptance"
        or match.get("archive") != value["input"]["archive"]
        or match.get("archive_sha256") != SOURCE_SEAL_SHA
    ):
        raise ReleaseError("R7 source is not the registered G6 acceptance seal")
    path = ROOT / Path(*PurePosixPath(value["input"]["archive"]).parts)
    if path.is_symlink() or not path.is_file() or sha(path) != SOURCE_SEAL_SHA:
        raise ReleaseError("registered G6 acceptance seal byte drift")
    return path


def safe_extract(archive_path: Path, directory: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile():
                raise ReleaseError("unsafe/non-file source seal member")
        archive.extractall(directory, filter="data")


def verify_source_seal(path: Path) -> Path:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/host-lisp/r6_g6_seal.py"), "verify", str(path)],
        cwd=ROOT, env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise ReleaseError(f"registered G6 acceptance seal failed verification:\n{completed.stdout}")
    directory = Path(tempfile.mkdtemp(prefix="lisp65-r7-source-"))
    safe_extract(path, directory)
    return directory


def verify_package_rebind() -> tuple[dict[str, Any], dict[str, Any]]:
    bindings = (
        (CURRENT_SHIP_MANIFEST, CURRENT_SHIP_MANIFEST_SHA, "current R6 Ship manifest"),
        (PACKAGE_REBIND, PACKAGE_REBIND_SHA, "1.0.1 package-rebind receipt"),
        (STATIC_PREFLIGHT, STATIC_PREFLIGHT_SHA, "1.0.1 static-preflight receipt"),
        (PROFILE_APPLICABILITY, PROFILE_APPLICABILITY_SHA, "1.0.1 profile-applicability receipt"),
    )
    for path, digest, label in bindings:
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise ReleaseError(f"{label} byte drift")
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "tools/host-lisp/r6_package_rebind_101.py"),
            "verify", str(PACKAGE_REBIND), "--ship", str(CURRENT_SHIP_MANIFEST.parent),
            "--preflight", str(STATIC_PREFLIGHT),
        ],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise ReleaseError(f"1.0.1 package rebind failed verification:\n{completed.stdout}")
    current = load(CURRENT_SHIP_MANIFEST, "current R6 Ship manifest")
    rebind = load(PACKAGE_REBIND, "1.0.1 package-rebind receipt")
    if (
        current.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        or rebind.get("status") != "passed-no-hardware-rerun"
        or rebind.get("result") != "passed"
        or rebind.get("product_identity", {}).get("new_artifact_set_sha256") != PRODUCT_SET
        or rebind.get("product_identity", {}).get("historical_artifact_set_sha256") != PRODUCT_SET
        or rebind.get("product_identity", {}).get("byte_identical_artifacts") != 13
        or rebind.get("product_identity", {}).get("product_sha_changes") != 0
        or rebind.get("receipt_policy", {}).get("hardware_cases_reexecuted") != 0
        or rebind.get("receipt_policy", {}).get("hardware_receipts_reused") != 5
    ):
        raise ReleaseError("1.0.1 package-rebind semantic drift")
    return current, rebind


def write_file(root: Path, name: str, data: bytes, mode: int) -> Path:
    relative(name, "release output")
    path = root / Path(*PurePosixPath(name).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ReleaseError(f"duplicate release output: {name}")
    path.write_bytes(data)
    os.chmod(path, mode)
    return path


def readme_bytes() -> bytes:
    return (
        "LISP65 WORKBENCH 1.0.1 - DIALECT V2\n"
        "=====================================\n\n"
        "Release 1.0.1 corrects packaging and documentation only.\n"
        "Its 13 product artifacts are byte-identical to the hardware-accepted 1.0.0 set.\n\n"
        f"Source commit: {SOURCE_COMMIT}\n"
        f"Product artifact set: {PRODUCT_SET}\n"
        f"G6 source seal: {SOURCE_SEAL_SHA}\n"
        "G3: PASSED (emulator prefilter only)\n"
        "G5: PASSED (14/14 hardware cases)\n"
        "G6: PASSED (5/5 profile-applicable hardware cases)\n"
        "Product-medium physical write protect: N/A in the stock-core SD-D81 profile.\n\n"
        "Before use, run:  python3 verify.py\n\n"
        "One-drive flow:\n"
        "1. Mount media/lisp65-product.d81 as L65SYS in drive 8 and boot.\n"
        "2. Wait for staging, chaining, and the REPL.\n"
        "3. Load IDE, IDEX, and M65D while L65SYS is still mounted.\n"
        "4. Then swap once to your own valid 1581 disk.\n"
        "5. media/lisp65-work.d81 is supplied as a convenient blank work disk.\n"
        "6. Every valid non-product 1581 disk is writable; L65SYS is denied by identity.\n\n"
        "First session:\n"
        "  (+ 20 22)\n"
        "  (load-lib \"ide\")\n"
        "  (load-lib \"idex\")\n"
        "  (load-lib \"m65d\")\n"
        "  ; now swap once to your work disk\n"
        "  (dir)\n"
        "  (edit)\n\n"
        "If a save reports a media-change error, check both disks and explicitly retry.\n"
        "The supplied work image has no preallocated FASL slots; persistent compilation\n"
        "is not available out of the box. Do not change media during expert-only legacy\n"
        "compiler writes to externally provisioned slots.\n"
        "There is no on-device formatter in 1.0.1.\n"
    ).encode("ascii")


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ReleaseError(f"release output contains symlink: {path}")
        if path.is_file() and path != root / "manifest.json":
            rows.append({
                "path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                "sha256": sha(path), "mode": f"0{stat.S_IMODE(path.stat().st_mode):03o}",
            })
    return rows


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [{key: row[key] for key in ("path", "bytes", "sha256", "mode")} for row in rows]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def build_directory(root: Path) -> dict[str, Any]:
    value = contract()
    timestamp, _ = source_commit_timestamp()
    seal = registered_seal(value)
    source = verify_source_seal(seal)
    try:
        current_ship, rebind = verify_package_rebind()
        sealed_ship = source / "payload/build/r6/ship"
        ship_manifest_path = sealed_ship / "manifest.json"
        top_path = source / "payload/build/r6/g6/run-20260715-02-preflight-212f957/g6-hardware-receipt.json"
        if sha(ship_manifest_path) != SEALED_SHIP_MANIFEST_SHA or sha(top_path) != G6_RECEIPT_SHA:
            raise ReleaseError("sealed Ship/G6 receipt binding drift")
        ship = load(ship_manifest_path, "sealed R6 Ship manifest")
        top = load(top_path, "sealed G6 receipt")
        prerequisite = load(PREREQ_MANIFEST, "R7 prerequisite manifest")
        if (
            ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
            or top.get("product_artifact_set_sha256") != PRODUCT_SET or top.get("result") != "passed"
            or prerequisite.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        ):
            raise ReleaseError("R7 source product/claim drift")
        current_rows = {
            row["role"]: row for row in current_ship.get("artifacts", []) if isinstance(row, dict) and isinstance(row.get("role"), str)
        }
        sealed_rows = {
            row["role"]: row for row in ship.get("artifacts", []) if isinstance(row, dict) and isinstance(row.get("role"), str)
        }
        if len(current_rows) != 13 or len(sealed_rows) != 13 or set(current_rows) != set(sealed_rows):
            raise ReleaseError("R7 current/sealed artifact closure drift")
        for role, sealed_row in sealed_rows.items():
            current_row = current_rows[role]
            if any(current_row.get(key) != sealed_row.get(key) for key in ("name", "bytes", "sha256", "ship_path")):
                raise ReleaseError(f"R7 current package product drift: {role}")
        root.mkdir(parents=True)
        file_modes = {row["path"]: int(row["mode"], 8) for row in ship.get("files", []) if isinstance(row, dict)}
        artifacts: list[dict[str, Any]] = []
        for row in ship.get("artifacts", []):
            if not isinstance(row, dict):
                raise ReleaseError("sealed Ship artifact row malformed")
            ship_path = relative(row["ship_path"], "sealed ship artifact path")
            source_path = sealed_ship / Path(*PurePosixPath(ship_path).parts)
            if (
                source_path.is_symlink() or not source_path.is_file()
                or source_path.stat().st_size != row["bytes"] or sha(source_path) != row["sha256"]
            ):
                raise ReleaseError(f"sealed Ship artifact byte drift: {row.get('role')}")
            mode = file_modes.get(ship_path)
            if mode not in {0o444, 0o644}:
                raise ReleaseError(f"sealed Ship artifact mode drift: {row.get('role')}")
            written = write_file(root, ship_path, source_path.read_bytes(), mode)
            if written.read_bytes() != source_path.read_bytes():
                raise ReleaseError(f"R7 copy is not byte-identical: {row.get('role')}")
            artifacts.append({
                "role": row["role"], "name": row["name"], "bytes": row["bytes"], "sha256": row["sha256"],
                "bundle_path": ship_path, "sealed_ship_path": ship_path,
            })
        if len(artifacts) != 13 or artifact_set_sha(artifacts) != PRODUCT_SET:
            raise ReleaseError("R7 artifact closure/set drift")
        write_file(root, "README-FIRST.txt", readme_bytes(), 0o444)
        write_file(root, "verify.py", OFFLINE.read_bytes(), 0o555)
        seal_out = write_file(root, f"evidence/{seal.name}", seal.read_bytes(), 0o444)
        top_out = write_file(root, "evidence/g6-hardware-receipt.json", top_path.read_bytes(), 0o444)
        prereq_manifest_out = write_file(root, "evidence/public-manifest-prerequisites.json", PREREQ_MANIFEST.read_bytes(), 0o444)
        prereq_receipt_out = write_file(root, "evidence/public-manifest-prerequisites-receipt.json", PREREQ_RECEIPT.read_bytes(), 0o444)
        contract_out = write_file(root, "evidence/r7-release-contract.json", CONTRACT.read_bytes(), 0o444)
        packer_out = write_file(root, "evidence/r7_release.py", PACKER.read_bytes(), 0o444)
        current_ship_out = write_file(root, "evidence/r6-ship-1.0.1-manifest.json", CURRENT_SHIP_MANIFEST.read_bytes(), 0o444)
        rebind_out = write_file(root, "evidence/r6-g6-1.0.1-package-rebind-receipt.json", PACKAGE_REBIND.read_bytes(), 0o444)
        preflight_out = write_file(root, "evidence/r6-g6-1.0.1-static-preflight-receipt.json", STATIC_PREFLIGHT.read_bytes(), 0o444)
        profile_out = write_file(root, "evidence/r6-g6-1.0.1-profile-applicability-receipt.json", PROFILE_APPLICABILITY.read_bytes(), 0o444)
        rows = inventory(root)
        dimensions = {name: {"baseline": amount, "candidate": amount, "delta": 0} for name, amount in {"bank": 332, "ext": 16385, "symbols": 120, "namepool": 2160, "directory": 32}.items()}
        manifest = {
            "format": FORMAT, "version": 1, "status": "private-release",
            "release": {"product": "lisp65", "version": "1.0.1", "tag": "v1.0.1", "visibility": "private-mirror", "dialect": "v2"},
            "source_commit": SOURCE_COMMIT, "packed_on": timestamp,
            "packed_on_source": "tag-target-committer-timestamp",
            "input": {
                "promotion_id": value["input"]["promotion_id"],
                "archive_sha256": SOURCE_SEAL_SHA,
                "sealed_ship_manifest_sha256": SEALED_SHIP_MANIFEST_SHA,
                "g6_receipt_sha256": G6_RECEIPT_SHA,
                "current_ship_manifest_sha256": CURRENT_SHIP_MANIFEST_SHA,
                "package_rebind_receipt_sha256": PACKAGE_REBIND_SHA,
                "static_preflight_receipt_sha256": STATIC_PREFLIGHT_SHA,
                "profile_applicability_receipt_sha256": PROFILE_APPLICABILITY_SHA,
            },
            "product": {"artifact_set_sha256": PRODUCT_SET, "artifact_count": 13, "product_sha_changes": 0},
            "claims": value["claims"], "toolchain": prerequisite["toolchain"],
            "evidence": {
                "source_seal": {"path": seal_out.relative_to(root).as_posix(), "sha256": sha(seal_out)},
                "g6_receipt": {"path": top_out.relative_to(root).as_posix(), "sha256": sha(top_out)},
                "prerequisite_manifest": {"path": prereq_manifest_out.relative_to(root).as_posix(), "sha256": sha(prereq_manifest_out)},
                "prerequisite_receipt": {"path": prereq_receipt_out.relative_to(root).as_posix(), "sha256": sha(prereq_receipt_out)},
                "contract": {"path": contract_out.relative_to(root).as_posix(), "sha256": sha(contract_out)},
                "packer": {"path": packer_out.relative_to(root).as_posix(), "sha256": sha(packer_out)},
                "current_ship_manifest": {"path": current_ship_out.relative_to(root).as_posix(), "sha256": sha(current_ship_out)},
                "package_rebind_receipt": {"path": rebind_out.relative_to(root).as_posix(), "sha256": sha(rebind_out)},
                "static_preflight_receipt": {"path": preflight_out.relative_to(root).as_posix(), "sha256": sha(preflight_out)},
                "profile_applicability_receipt": {"path": profile_out.relative_to(root).as_posix(), "sha256": sha(profile_out)},
            },
            "policy": {
                "operation": "documentation-and-package-only",
                "product_byte_source": "registered-r6-g6-seal-only",
                "product_byte_identity": "13/13-byte-identical-to-sealed-r6-ship-and-current-r6-package",
                "hardware_receipt_policy": "5/5-SHA-bound-G6-receipts-reused-0-hardware-cases-reexecuted",
                "offline_verification": "bundle-alone-no-repository-no-network",
            },
            "capacity_delta": dimensions, "artifacts": artifacts, "files": rows,
            "package_set_sha256": package_set_sha(rows), "result": "passed",
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_bytes(canonical(manifest))
        os.chmod(manifest_path, 0o444)
        return manifest
    finally:
        shutil.rmtree(source)


def tar_info(name: str, data: bytes, mode: int, epoch: int) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name)
    info.size = len(data); info.mode = mode; info.mtime = epoch
    info.uid = 0; info.gid = 0; info.uname = ""; info.gname = ""
    return info, io.BytesIO(data)


def write_archive(root: Path, output: Path, epoch: int) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
                for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                    if path.is_symlink() or not path.is_file():
                        continue
                    name = f"{ARCHIVE_ROOT}/{path.relative_to(root).as_posix()}"
                    info, stream = tar_info(name, path.read_bytes(), stat.S_IMODE(path.stat().st_mode), epoch)
                    archive.addfile(info, stream)


def extract_bundle(archive_path: Path, destination: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile() or not name.parts or name.parts[0] != ARCHIVE_ROOT:
                raise ReleaseError("unsafe or foreign release archive member")
        archive.extractall(destination, filter="data")
    root = destination / ARCHIVE_ROOT
    restore_bundle_modes(root)
    return root


def restore_bundle_modes(root: Path) -> None:
    manifest_path = root / "manifest.json"
    value = load(manifest_path, "extracted release manifest")
    rows = value.get("files")
    if not isinstance(rows, list):
        raise ReleaseError("extracted release manifest lacks file modes")
    os.chmod(manifest_path, 0o444)
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256", "mode"}
            or not isinstance(row["mode"], str) or not re.fullmatch(r"0[0-7]{3}", row["mode"])
        ):
            raise ReleaseError(f"extracted release file mode is malformed: {index}")
        path = root / Path(*PurePosixPath(relative(row["path"], f"file[{index}].path")).parts)
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"extracted release file is missing: {row['path']}")
        os.chmod(path, int(row["mode"], 8))


def run_verifier(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=root,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )


def verify_archive(archive_path: Path) -> dict[str, Any]:
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ReleaseError("release bundle is missing")
    with tempfile.TemporaryDirectory(prefix="lisp65-r7-verify-") as raw:
        root = extract_bundle(archive_path, Path(raw))
        completed = run_verifier(root)
        if completed.returncode:
            raise ReleaseError(f"release bundle verification failed:\n{completed.stdout}")
        print(completed.stdout.strip())
        return load(root / "manifest.json", "release manifest")


def mutate(path: Path) -> None:
    os.chmod(path, 0o644)
    data = bytearray(path.read_bytes())
    if not data:
        raise ReleaseError("cannot mutate empty release file")
    data[len(data) // 2] ^= 1
    path.write_bytes(data)


def negative_test(archive_path: Path) -> None:
    for name in contract()["policy"]["negative_tests"]:
        with tempfile.TemporaryDirectory(prefix=f"lisp65-r7-negative-{name}-") as raw:
            root = extract_bundle(archive_path, Path(raw))
            if name == "product-byte":
                mutate(root / "components/lisp65.prg")
            elif name == "manifest":
                path = root / "manifest.json"; os.chmod(path, 0o644)
                value = load(path, "mutant release manifest"); value["release"]["version"] = "9.9.9"
                path.write_bytes(canonical(value)); os.chmod(path, 0o444)
            elif name == "source-seal":
                mutate(root / "evidence/r6-g6-hardware-acceptance-aed1595.tar.gz")
            elif name == "package-rebind":
                mutate(root / "evidence/r6-g6-1.0.1-package-rebind-receipt.json")
            elif name == "readme":
                mutate(root / "README-FIRST.txt")
            else:
                raise ReleaseError(f"unknown R7 mutation: {name}")
            if run_verifier(root).returncode == 0:
                raise ReleaseError(f"release verifier accepted mutation: {name}")
    print("lisp65-r7-release: NEGATIVE PASS mutations=5 product-byte+manifest+source-seal+package-rebind+readme")


def same_files(first: Path, second: Path) -> bool:
    if first.stat().st_size != second.stat().st_size or sha(first) != sha(second):
        return False
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            a, b = left.read(1024 * 1024), right.read(1024 * 1024)
            if a != b:
                return False
            if not a:
                return True


def build(output: Path, receipt_path: Path) -> None:
    value = contract(); _, epoch = source_commit_timestamp()
    if output.exists() or output.is_symlink() or receipt_path.exists() or receipt_path.is_symlink():
        raise ReleaseError("R7 bundle/receipt outputs must be fresh")
    with tempfile.TemporaryDirectory(prefix="lisp65-r7-build-") as raw:
        temporary = Path(raw); root = temporary / ARCHIVE_ROOT
        manifest = build_directory(root)
        archives = [temporary / "pack-a.tar.gz", temporary / "pack-b.tar.gz"]
        environments = (("1", "Etc/GMT+12"), ("777", "Pacific/Kiritimati"))
        for archive_path, (hashseed, timezone) in zip(archives, environments, strict=True):
            old_seed, old_tz = os.environ.get("PYTHONHASHSEED"), os.environ.get("TZ")
            os.environ["PYTHONHASHSEED"], os.environ["TZ"] = hashseed, timezone
            try:
                write_archive(root, archive_path, epoch)
            finally:
                if old_seed is None: os.environ.pop("PYTHONHASHSEED", None)
                else: os.environ["PYTHONHASHSEED"] = old_seed
                if old_tz is None: os.environ.pop("TZ", None)
                else: os.environ["TZ"] = old_tz
        if not same_files(*archives):
            raise ReleaseError("R7 varied-environment double pack differs")
        verify_archive(archives[0]); negative_test(archives[0])
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archives[0], output)
        receipt = {
            "format": RECEIPT_FORMAT, "version": 1, "status": "passed-before-tag",
            "release": {"product": "lisp65", "version": "1.0.1", "tag": "v1.0.1", "tag_target": SOURCE_COMMIT, "dialect": "v2"},
            "bundle": {"path": output.relative_to(ROOT).as_posix(), "bytes": output.stat().st_size, "sha256": sha(output), "manifest_sha256": sha(root / "manifest.json"), "package_set_sha256": manifest["package_set_sha256"]},
            "input": {
                "promotion_id": value["input"]["promotion_id"],
                "archive_sha256": SOURCE_SEAL_SHA,
                "current_ship_manifest_sha256": CURRENT_SHIP_MANIFEST_SHA,
                "package_rebind_receipt_sha256": PACKAGE_REBIND_SHA,
                "product_artifact_set_sha256": PRODUCT_SET,
            },
            "product": {"artifact_count": 13, "byte_identical_to_seal": "13/13", "product_sha_changes": 0},
            "reproducibility": {"packs": 2, "byte_identical": True, "axes": ["PYTHONHASHSEED", "TZ"]},
            "verification": {
                "offline_bundle_only": "passed", "source_seal_offline": "passed",
                "package_rebind_offline": "passed", "hardware_cases_reexecuted": 0,
                "negative_mutations_rejected": ["product-byte", "manifest", "source-seal", "package-rebind", "readme"],
            },
            "claims": value["claims"], "result": "passed",
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True); receipt_path.write_bytes(canonical(receipt))
    print(f"lisp65-r7-release: WROTE bundle={output} bytes={output.stat().st_size} sha256={sha(output)}")


def check_receipt(receipt_path: Path, *, require_tag: bool) -> dict[str, Any]:
    value = load(receipt_path, "R7 release receipt")
    bundle = value.get("bundle", {}); path = ROOT / relative(bundle.get("path"), "receipt bundle path")
    if (
        value.get("format") != RECEIPT_FORMAT or value.get("version") != 1
        or value.get("status") != "passed-before-tag" or value.get("result") != "passed"
        or value.get("release") != {"product": "lisp65", "version": "1.0.1", "tag": "v1.0.1", "tag_target": SOURCE_COMMIT, "dialect": "v2"}
        or value.get("input") != {
            "promotion_id": "r6-g6-hardware-acceptance-aed1595", "archive_sha256": SOURCE_SEAL_SHA,
            "current_ship_manifest_sha256": CURRENT_SHIP_MANIFEST_SHA,
            "package_rebind_receipt_sha256": PACKAGE_REBIND_SHA,
            "product_artifact_set_sha256": PRODUCT_SET,
        }
        or path.is_symlink() or not path.is_file() or path.stat().st_size != bundle.get("bytes") or sha(path) != bundle.get("sha256")
        or value.get("product") != {"artifact_count": 13, "byte_identical_to_seal": "13/13", "product_sha_changes": 0}
        or value.get("reproducibility") != {"packs": 2, "byte_identical": True, "axes": ["PYTHONHASHSEED", "TZ"]}
        or value.get("verification") != {
            "offline_bundle_only": "passed", "source_seal_offline": "passed",
            "package_rebind_offline": "passed", "hardware_cases_reexecuted": 0,
            "negative_mutations_rejected": ["product-byte", "manifest", "source-seal", "package-rebind", "readme"],
        }
        or value.get("claims") != contract()["claims"]
    ):
        raise ReleaseError("R7 release receipt drift")
    manifest = verify_archive(path)
    if bundle.get("manifest_sha256") != manifest_sha_from_archive(path) or bundle.get("package_set_sha256") != manifest["package_set_sha256"]:
        raise ReleaseError("R7 release receipt manifest binding drift")
    if require_tag:
        if git_value("rev-parse", "refs/tags/v1.0.1^{}") != resolve_commit(SOURCE_COMMIT):
            raise ReleaseError("v1.0.1 does not peel to the authorized tag target")
        if git_value("cat-file", "-t", "refs/tags/v1.0.1") != "tag":
            raise ReleaseError("v1.0.1 is not annotated")
    print(f"lisp65-r7-release: RECEIPT PASS tag={'bound' if require_tag else 'not-yet-required'} bundle={bundle['sha256']}")
    return value


def manifest_sha_from_archive(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        member = archive.getmember(f"{ARCHIVE_ROOT}/manifest.json")
        stream = archive.extractfile(member)
        if stream is None:
            raise ReleaseError("release archive lacks manifest")
        return sha_bytes(stream.read())


def selftest() -> None:
    value = contract()
    if value["release"]["tag_target"] != SOURCE_COMMIT or value["product"]["dialect"] != "v2":
        raise ReleaseError("R7 selftest identity drift")
    print("lisp65-r7-release: SELFTEST PASS version=1.0.1 dialect=v2 source=registered-G6-seal+package-rebind tag-after-verify")


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__); sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    build_p = sub.add_parser("build"); build_p.add_argument("--output", type=Path, required=True); build_p.add_argument("--receipt", type=Path, required=True)
    verify_p = sub.add_parser("verify"); verify_p.add_argument("archive", type=Path)
    negative_p = sub.add_parser("negative-test"); negative_p.add_argument("archive", type=Path)
    check_p = sub.add_parser("receipt-check"); check_p.add_argument("receipt", type=Path); check_p.add_argument("--require-tag", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest": selftest()
        elif args.command == "build": build(rooted(args.output), rooted(args.receipt))
        elif args.command == "verify": verify_archive(rooted(args.archive))
        elif args.command == "negative-test": negative_test(rooted(args.archive))
        else: check_receipt(rooted(args.receipt), require_tag=args.require_tag)
        return 0
    except (ReleaseError, OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"lisp65-r7-release: FAIL: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
