#!/usr/bin/env python3
"""Build and verify the sealed lisp65 1.1.0 release bundle."""

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


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/r7-release-v11-contract.json"
REGISTER = ROOT / "config/promotion-register.json"
PACKER = ROOT / "tools/host-lisp/r7_release_v11.py"
OFFLINE = ROOT / "tools/host-lisp/r7_release_v11_offline.py"
FORMAT = "lisp65-r7-release-v11-manifest-v1"
RECEIPT_FORMAT = "lisp65-r7-release-v11-receipt-v1"
ARCHIVE_ROOT = "lisp65-1.1.0"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise ReleaseError(f"{label} is not canonical")
    return value


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ReleaseError(f"{label} must be a lowercase SHA-256")
    return value


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R7 1.1 contract")
    expected_release = {
        "product": "lisp65", "version": "1.1.0", "tag": "v1.1.0",
        "tag_type": "annotated", "bundle": "releases/lisp65-1.1.0.tar.gz",
        "visibility": "public", "dialect": "v2",
    }
    expected_product = {
        "artifact_set_sha256": "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024",
        "artifact_count": 14, "product_build_id": "f144fd48",
        "product_sha_changes_during_R7": 0,
    }
    if (
        value.get("format") != "lisp65-r7-release-v11-contract-v1"
        or value.get("version") != 1
        or value.get("id") != "lisp65-public-release-v1.1.0"
        or value.get("status") != "owner-authorized"
        or value.get("release") != expected_release
        or value.get("product") != expected_product
        or value.get("capacity") != {"bank": 371, "directory": 168, "ext": 26232, "namepool": 5079, "symbols": 334}
        or value.get("policy", {}).get("negative_tests") != ["product-byte", "manifest", "source-seal", "g6-receipt", "readme", "keymap"]
    ):
        raise ReleaseError("R7 1.1 release contract semantic drift")
    for key in ("archive_sha256", "ship_manifest_sha256", "g6_receipt_sha256", "ship_packer_receipt_sha256", "static_preflight_receipt_sha256", "profile_applicability_receipt_sha256"):
        lower_sha(value.get("input", {}).get(key), f"input.{key}")
    docs = value.get("documentation")
    if not isinstance(docs, list) or docs != sorted(set(docs)):
        raise ReleaseError("R7 documentation inventory must be sorted and unique")
    for index, name in enumerate(docs):
        relative(name, f"documentation[{index}]")
    return value


def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise ReleaseError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def source_commit(value: dict[str, Any]) -> tuple[str, str, int]:
    commit = git("rev-parse", "HEAD^{commit}")
    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseError("release source commit is not canonical")
    bound = [CONTRACT, PACKER, OFFLINE] + [ROOT / name for name in value["documentation"]]
    for path in bound:
        relative_name = path.relative_to(ROOT).as_posix()
        shown = subprocess.run(["git", "show", f"{commit}:{relative_name}"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if shown.returncode or shown.stdout != path.read_bytes():
            raise ReleaseError(f"release source commit does not bind {relative_name}")
    timestamp = git("show", "-s", "--format=%cI", commit)
    epoch = git("show", "-s", "--format=%ct", commit)
    if "T" not in timestamp or not epoch.isdigit():
        raise ReleaseError("release source timestamp is unavailable")
    return commit, timestamp, int(epoch)


def registered_seal(value: dict[str, Any]) -> Path:
    register = load(REGISTER, "promotion register")
    rows = register.get("promotions")
    match = next((row for row in rows if isinstance(row, dict) and row.get("id") == value["input"]["promotion_id"]), None) if isinstance(rows, list) else None
    if (
        not isinstance(match, dict) or match.get("kind") != "hardware-acceptance"
        or match.get("archive") != value["input"]["archive"]
        or match.get("archive_sha256") != value["input"]["archive_sha256"]
    ):
        raise ReleaseError("R7 source is not the registered Wave 3 G6 seal")
    path = ROOT / relative(match["archive"], "registered seal path")
    if path.is_symlink() or not path.is_file() or sha(path) != value["input"]["archive_sha256"]:
        raise ReleaseError("registered Wave 3 G6 seal byte drift")
    return path


def safe_extract(archive_path: Path, directory: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile():
                raise ReleaseError("unsafe/non-file seal member")
        archive.extractall(directory, filter="data")


def verify_source_seal(path: Path) -> Path:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/host-lisp/r6_g6_seal.py"), "verify", str(path)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise ReleaseError(f"registered Wave 3 G6 seal failed verification:\n{completed.stdout}")
    directory = Path(tempfile.mkdtemp(prefix="lisp65-r7-v11-source-"))
    safe_extract(path, directory)
    return directory


def write_file(root: Path, name: str, data: bytes, mode: int) -> Path:
    path = root / Path(*PurePosixPath(relative(name, "release output")).parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ReleaseError(f"duplicate release output: {name}")
    path.write_bytes(data)
    os.chmod(path, mode)
    return path


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [{key: row[key] for key in ("role", "name", "bytes", "sha256")} for row in sorted(rows, key=lambda row: (row["role"], row["name"]))]
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


def public_toolchain(source: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(source))
    roles = {
        "c1541.artifact": (value["c1541"]["artifact"], "c1541-host-binary"),
        "rom": (value["rom"], "mega65-rom"),
        "sd_base": (value["sd_base"], "mega65-sd-base-image"),
        "xmega65.artifact": (value["xmega65"]["artifact"], "xmega65-launcher"),
        "xmega65.inner_artifact": (value["xmega65"]["inner_artifact"], "xmega65-emulator-binary"),
    }
    for label, (row, role) in roles.items():
        if not isinstance(row.get("path"), str) or not row["path"].startswith("/"):
            raise ReleaseError(f"expected private path missing from toolchain: {label}")
        row.pop("path")
        row["role"] = role
    return value


def absolute_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in absolute_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in absolute_strings(child)]
    return [value] if isinstance(value, str) and value.startswith("/") else []


def bound_input(path_value: str, digest: str, label: str) -> Path:
    path = ROOT / relative(path_value, label)
    if path.is_symlink() or not path.is_file() or sha(path) != digest:
        raise ReleaseError(f"{label} byte drift")
    return path


def build_directory(root: Path) -> dict[str, Any]:
    value = contract()
    commit, timestamp, _ = source_commit(value)
    seal = registered_seal(value)
    source = verify_source_seal(seal)
    try:
        ship_path = source / relative(value["input"]["ship_manifest_member"], "ship manifest member")
        g6_path = source / relative(value["input"]["g6_receipt_member"], "G6 receipt member")
        if sha(ship_path) != value["input"]["ship_manifest_sha256"] or sha(g6_path) != value["input"]["g6_receipt_sha256"]:
            raise ReleaseError("sealed Ship/G6 binding drift")
        ship = load(ship_path, "sealed R6 Ship manifest")
        g6 = load(g6_path, "sealed G6 receipt")
        product = value["product"]
        if (
            ship.get("product", {}).get("artifact_set_sha256") != product["artifact_set_sha256"]
            or ship.get("product", {}).get("artifact_count") != product["artifact_count"]
            or ship.get("product", {}).get("product_build_id") != product["product_build_id"]
            or g6.get("product_artifact_set_sha256") != product["artifact_set_sha256"]
            or g6.get("result") != "passed"
        ):
            raise ReleaseError("sealed product/G6 identity drift")
        root.mkdir(parents=True)
        modes = {row["path"]: int(row["mode"], 8) for row in ship.get("files", []) if isinstance(row, dict)}
        artifacts: list[dict[str, Any]] = []
        for row in ship.get("artifacts", []):
            ship_name = relative(row.get("ship_path"), "artifact ship path")
            source_path = ship_path.parent / Path(*PurePosixPath(ship_name).parts)
            if (
                source_path.is_symlink() or not source_path.is_file()
                or source_path.stat().st_size != row.get("bytes") or sha(source_path) != row.get("sha256")
            ):
                raise ReleaseError(f"sealed artifact drift: {row.get('role')}")
            mode = modes.get(ship_name)
            if mode not in {0o444, 0o644}:
                raise ReleaseError(f"sealed artifact mode drift: {row.get('role')}")
            write_file(root, ship_name, source_path.read_bytes(), mode)
            artifacts.append({
                "role": row["role"], "name": row["name"], "bytes": row["bytes"],
                "sha256": row["sha256"], "bundle_path": ship_name, "sealed_ship_path": ship_name,
            })
        if len(artifacts) != product["artifact_count"] or artifact_set_sha(artifacts) != product["artifact_set_sha256"]:
            raise ReleaseError("release artifact closure/set drift")

        documentation: list[dict[str, Any]] = []
        for name in value["documentation"]:
            source_doc = ROOT / name
            target = write_file(root, name, source_doc.read_bytes(), 0o444)
            documentation.append({"path": name, "bytes": target.stat().st_size, "sha256": sha(target)})
        write_file(root, "README-FIRST.txt", (ROOT / "README.md").read_bytes(), 0o444)
        write_file(root, "verify.py", OFFLINE.read_bytes(), 0o555)

        evidence: dict[str, dict[str, Any]] = {}
        def evidence_copy(label: str, name: str, source_path: Path, mode: int = 0o444) -> None:
            target = write_file(root, name, source_path.read_bytes(), mode)
            evidence[label] = {"path": name, "sha256": sha(target)}

        evidence_copy("source_seal", f"evidence/{seal.name}", seal)
        evidence_copy("g6_receipt", "evidence/g6-hardware-receipt.json", g6_path)
        evidence_copy("ship_manifest", "evidence/r6-ship-manifest.json", ship_path)
        evidence_copy("contract", "evidence/r7-release-v11-contract.json", CONTRACT)
        evidence_copy("packer", "evidence/r7_release_v11.py", PACKER)
        for label, path_key, sha_key, output_name in (
            ("ship_packer_receipt", "ship_packer_receipt", "ship_packer_receipt_sha256", "evidence/r6-ship-packer-receipt.json"),
            ("static_preflight_receipt", "static_preflight_receipt", "static_preflight_receipt_sha256", "evidence/r6-g6-static-preflight-receipt.json"),
            ("profile_applicability_receipt", "profile_applicability_receipt", "profile_applicability_receipt_sha256", "evidence/r6-g6-profile-applicability-receipt.json"),
        ):
            evidence_copy(label, output_name, bound_input(value["input"][path_key], value["input"][sha_key], label))

        toolchain = public_toolchain(ship["toolchain"])
        if absolute_strings(toolchain):
            raise ReleaseError("public toolchain retained absolute paths")
        dimensions = {name: {"baseline": amount, "candidate": amount, "delta": 0} for name, amount in value["capacity"].items()}
        rows = inventory(root)
        manifest = {
            "format": FORMAT, "version": 1, "status": "verified-before-tag",
            "release": value["release"], "source_commit": commit,
            "packed_on": timestamp, "packed_on_source": "release-source-commit-committer-timestamp",
            "input": {
                "promotion_id": value["input"]["promotion_id"],
                "archive_sha256": value["input"]["archive_sha256"],
                "ship_manifest_sha256": value["input"]["ship_manifest_sha256"],
                "g6_receipt_sha256": value["input"]["g6_receipt_sha256"],
            },
            "product": product, "claims": value["claims"], "toolchain": toolchain,
            "policy": value["policy"], "capacity_delta": dimensions,
            "artifacts": artifacts, "documentation": documentation, "evidence": evidence,
            "files": rows, "package_set_sha256": package_set_sha(rows), "result": "passed",
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_bytes(canonical(manifest)); os.chmod(manifest_path, 0o444)
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
                    info, stream = tar_info(f"{ARCHIVE_ROOT}/{path.relative_to(root).as_posix()}", path.read_bytes(), stat.S_IMODE(path.stat().st_mode), epoch)
                    archive.addfile(info, stream)


def extract_bundle(archive_path: Path, destination: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not member.isfile() or not name.parts or name.parts[0] != ARCHIVE_ROOT:
                raise ReleaseError("unsafe or foreign release archive member")
        archive.extractall(destination, filter="data")
    root = destination / ARCHIVE_ROOT
    restore_modes(root)
    return root


def restore_modes(root: Path) -> None:
    manifest = load(root / "manifest.json", "extracted release manifest")
    os.chmod(root / "manifest.json", 0o444)
    for row in manifest.get("files", []):
        path = root / relative(row.get("path"), "file path")
        os.chmod(path, int(row["mode"], 8))


def run_verifier(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=root,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )


def verify_archive(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("release bundle is missing")
    with tempfile.TemporaryDirectory(prefix="lisp65-r7-v11-verify-") as raw:
        root = extract_bundle(path, Path(raw))
        completed = run_verifier(root)
        if completed.returncode:
            raise ReleaseError(f"release bundle verification failed:\n{completed.stdout}")
        print(completed.stdout.strip())
        return load(root / "manifest.json", "release manifest")


def flip(path: Path) -> None:
    if path.stat().st_size < 1:
        raise ReleaseError("cannot mutate empty release file")
    os.chmod(path, 0o644)
    with path.open("r+b") as handle:
        offset = path.stat().st_size // 2
        handle.seek(offset); original = handle.read(1)
        handle.seek(offset); handle.write(bytes([original[0] ^ 1]))


def negative_test(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="lisp65-r7-v11-negative-") as raw:
        root = extract_bundle(path, Path(raw))
        manifest = load(root / "manifest.json", "negative-test manifest")
        source_seal = root / manifest["evidence"]["source_seal"]["path"]
        targets = {
            "product-byte": root / "components/lisp65.prg",
            "source-seal": source_seal,
            "g6-receipt": root / "evidence/g6-hardware-receipt.json",
            "readme": root / "README.md",
            "keymap": root / "docs/generated/ide-keymap.md",
        }
        for name in contract()["policy"]["negative_tests"]:
            if name == "manifest":
                target = root / "manifest.json"; original = target.read_bytes(); os.chmod(target, 0o644)
                value = load(target, "mutant manifest"); value["release"]["version"] = "9.9.9"; target.write_bytes(canonical(value))
            else:
                target = targets[name]; original = target.read_bytes() if target.stat().st_size < 32 * 1024 * 1024 else b""
                original_sha = sha(target); flip(target)
            if run_verifier(root).returncode == 0:
                raise ReleaseError(f"release verifier accepted mutation: {name}")
            if original:
                target.write_bytes(original)
            else:
                flip(target)
                if sha(target) != original_sha:
                    raise ReleaseError(f"large mutation restore failed: {name}")
            os.chmod(target, 0o444)
        final = run_verifier(root)
        if final.returncode:
            raise ReleaseError(f"release verifier failed after mutation restoration:\n{final.stdout}")
    print("lisp65-r7-v11: NEGATIVE PASS mutations=6 product-byte+manifest+source-seal+g6-receipt+readme+keymap")


def same_files(left: Path, right: Path) -> bool:
    return left.stat().st_size == right.stat().st_size and sha(left) == sha(right)


def build(output: Path, receipt_path: Path) -> None:
    value = contract(); commit, _, epoch = source_commit(value)
    if output.exists() or output.is_symlink() or receipt_path.exists() or receipt_path.is_symlink():
        raise ReleaseError("R7 bundle/receipt outputs must be fresh")
    with tempfile.TemporaryDirectory(prefix="lisp65-r7-v11-build-") as raw:
        temporary = Path(raw); root = temporary / ARCHIVE_ROOT
        manifest = build_directory(root)
        packs = (temporary / "pack-a.tar.gz", temporary / "pack-b.tar.gz")
        for pack, (seed, timezone) in zip(packs, (("11", "Etc/GMT+12"), ("991", "Pacific/Kiritimati")), strict=True):
            old_seed, old_tz = os.environ.get("PYTHONHASHSEED"), os.environ.get("TZ")
            os.environ["PYTHONHASHSEED"], os.environ["TZ"] = seed, timezone
            try: write_archive(root, pack, epoch)
            finally:
                if old_seed is None: os.environ.pop("PYTHONHASHSEED", None)
                else: os.environ["PYTHONHASHSEED"] = old_seed
                if old_tz is None: os.environ.pop("TZ", None)
                else: os.environ["TZ"] = old_tz
        if not same_files(*packs):
            raise ReleaseError("varied-environment double pack differs")
        verify_archive(packs[0]); negative_test(packs[0])
        output.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(packs[0], output)
        receipt = {
            "format": RECEIPT_FORMAT, "version": 1, "status": "passed-before-tag",
            "release": {"product": "lisp65", "version": "1.1.0", "tag": "v1.1.0", "dialect": "v2"},
            "source_commit": commit,
            "bundle": {"path": output.relative_to(ROOT).as_posix(), "bytes": output.stat().st_size, "sha256": sha(output), "manifest_sha256": sha(root / "manifest.json"), "package_set_sha256": manifest["package_set_sha256"]},
            "input": {"promotion_id": value["input"]["promotion_id"], "archive_sha256": value["input"]["archive_sha256"], "product_artifact_set_sha256": value["product"]["artifact_set_sha256"]},
            "product": {"artifact_count": 14, "byte_identical_to_seal": "14/14", "product_sha_changes_during_R7": 0},
            "reproducibility": {"packs": 2, "byte_identical": True, "axes": ["PYTHONHASHSEED", "TZ"]},
            "verification": {"offline_bundle_only": "passed", "source_seal_offline": "passed", "hardware_cases_reexecuted": 0, "negative_mutations_rejected": value["policy"]["negative_tests"]},
            "claims": value["claims"], "result": "passed",
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True); receipt_path.write_bytes(canonical(receipt))
    print(f"lisp65-r7-v11: WROTE bundle={output} bytes={output.stat().st_size} sha256={sha(output)}")


def manifest_sha_from_archive(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        stream = archive.extractfile(archive.getmember(f"{ARCHIVE_ROOT}/manifest.json"))
        if stream is None: raise ReleaseError("release archive lacks manifest")
        return sha_bytes(stream.read())


def check_receipt(receipt_path: Path, require_tag: bool) -> dict[str, Any]:
    value = load(receipt_path, "R7 1.1 receipt"); bundle = value.get("bundle", {})
    path = ROOT / relative(bundle.get("path"), "receipt bundle path")
    expected_product = {"artifact_count": 14, "byte_identical_to_seal": "14/14", "product_sha_changes_during_R7": 0}
    if (
        value.get("format") != RECEIPT_FORMAT or value.get("version") != 1
        or value.get("status") != "passed-before-tag" or value.get("result") != "passed"
        or value.get("release") != {"product": "lisp65", "version": "1.1.0", "tag": "v1.1.0", "dialect": "v2"}
        or not COMMIT_RE.fullmatch(value.get("source_commit", ""))
        or value.get("product") != expected_product or value.get("claims") != contract()["claims"]
        or path.is_symlink() or not path.is_file() or path.stat().st_size != bundle.get("bytes") or sha(path) != bundle.get("sha256")
    ):
        raise ReleaseError("R7 1.1 release receipt drift")
    manifest = verify_archive(path)
    if bundle.get("manifest_sha256") != manifest_sha_from_archive(path) or bundle.get("package_set_sha256") != manifest["package_set_sha256"]:
        raise ReleaseError("R7 1.1 receipt manifest binding drift")
    if require_tag:
        if git("cat-file", "-t", "refs/tags/v1.1.0") != "tag":
            raise ReleaseError("v1.1.0 is not annotated")
        target = git("rev-parse", "refs/tags/v1.1.0^{}")
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", value["source_commit"], target], cwd=ROOT, check=False)
        shown = subprocess.run(["git", "show", f"{target}:{receipt_path.relative_to(ROOT).as_posix()}"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ancestry.returncode or shown.returncode or shown.stdout != receipt_path.read_bytes():
            raise ReleaseError("v1.1.0 tag does not bind the verified release receipt")
    print(f"lisp65-r7-v11: RECEIPT PASS tag={'bound' if require_tag else 'not-yet-required'} bundle={bundle['sha256']}")
    return value


def selftest() -> None:
    value = contract()
    if value["product"]["artifact_count"] != 14 or value["release"]["version"] != "1.1.0":
        raise ReleaseError("R7 1.1 selftest identity drift")
    print("lisp65-r7-v11: SELFTEST PASS version=1.1.0 dialect=v2 source=registered-Wave3-G6-seal tag-after-verify")


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    build_p = sub.add_parser("build"); build_p.add_argument("--output", type=Path, required=True); build_p.add_argument("--receipt", type=Path, required=True)
    verify_p = sub.add_parser("verify"); verify_p.add_argument("archive", type=Path)
    negative_p = sub.add_parser("negative-test"); negative_p.add_argument("archive", type=Path)
    check_p = sub.add_parser("receipt-check"); check_p.add_argument("receipt", type=Path); check_p.add_argument("--require-tag", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "selftest": selftest()
        elif args.command == "build": build(rooted(args.output), rooted(args.receipt))
        elif args.command == "verify": verify_archive(rooted(args.archive))
        elif args.command == "negative-test": negative_test(rooted(args.archive))
        else: check_receipt(rooted(args.receipt), args.require_tag)
        return 0
    except (ReleaseError, OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"lisp65-r7-v11: FAIL: {exc}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
