#!/usr/bin/env python3
"""Fetch and verify the externally installed lisp65 third-party toolchain."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "config/toolchain-manifest.json"


class ToolchainError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "lisp65-external-toolchain-manifest-v1":
        raise ToolchainError("unsupported toolchain manifest")
    return data


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_identity(root: Path) -> dict:
    if not root.is_dir():
        raise ToolchainError(f"toolchain directory missing: {root}")
    digest = hashlib.sha256()
    regular_files = symlinks = regular_file_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(path).encode("utf-8") + b"\0")
            symlinks += 1
        elif path.is_file():
            mode = b"x" if os.access(path, os.X_OK) else b"-"
            content = file_sha256(path).encode("ascii")
            digest.update(b"F\0" + relative + b"\0" + mode + b"\0" + content + b"\0")
            regular_files += 1
            regular_file_bytes += path.stat().st_size
    return {
        "regular_files": regular_files,
        "symlinks": symlinks,
        "regular_file_bytes": regular_file_bytes,
        "sha256": digest.hexdigest(),
    }


def verify_package(name: str, package: dict, tool_root: Path) -> dict:
    install = tool_root / Path(package["install_directory"]).name
    failures = []
    for relative, expected in package["required_files"].items():
        path = install / relative
        if not (path.is_file() or path.is_symlink()):
            failures.append(f"missing:{relative}")
            continue
        actual = file_sha256(path)
        if actual != expected:
            failures.append(f"sha256:{relative}:{actual}")
    identity = tree_identity(install)
    for field, expected in package["installed_tree"].items():
        if identity[field] != expected:
            failures.append(f"tree:{field}:{identity[field]}")
    if failures:
        raise ToolchainError(f"{name} verification failed: " + ", ".join(failures))
    return {"package": name, "path": str(install), "tree": identity, "status": "exact-binary-match"}


def verify_archive(path: Path, contract: dict) -> None:
    if not path.is_file():
        raise ToolchainError(f"archive missing: {path}")
    if path.stat().st_size != contract["bytes"]:
        raise ToolchainError(f"archive size mismatch: {path}")
    actual = file_sha256(path)
    if actual != contract["sha256"]:
        raise ToolchainError(f"archive SHA-256 mismatch: {path}: {actual}")


def fetch_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    with urllib.request.urlopen(url) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    partial.replace(destination)


def safe_extract_tar_xz(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, mode="r:xz") as bundle:
        base = destination.resolve()
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != base and base not in target.parents:
                raise ToolchainError(f"unsafe archive member: {member.name}")
        bundle.extractall(destination, filter="data")


def extract_m65tools(archive: Path, destination: Path) -> None:
    seven_zip = shutil.which("7z") or shutil.which("7zz")
    if seven_zip is None:
        raise ToolchainError("7z/7zz is required to extract the MEGA65 tools archive")
    with tempfile.TemporaryDirectory(prefix="lisp65-m65tools-") as temp:
        subprocess.run(
            [seven_zip, "x", "-y", f"-o{temp}", str(archive)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        roots = [path for path in Path(temp).iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise ToolchainError("MEGA65 tools archive has an unexpected root")
        shutil.copytree(roots[0], destination, symlinks=True)


def command_verify(args) -> int:
    manifest = load_manifest(args.manifest)
    results = []
    for name, package in manifest["packages"].items():
        if name == "mega65_tools" and args.product_build_only and not (args.tool_root / "m65tools").exists():
            results.append({"package": name, "status": "not-required-for-product-build"})
            continue
        results.append(verify_package(name, package, args.tool_root))
    print(json.dumps({"schema": "lisp65-toolchain-verification-v1", "status": "pass", "packages": results}, sort_keys=True))
    return 0


def command_fetch(args) -> int:
    manifest = load_manifest(args.manifest)
    cache = args.cache.resolve()
    tool_root = args.tool_root.resolve()
    tool_root.mkdir(parents=True, exist_ok=True)
    llvm = manifest["packages"]["llvm_mos"]
    llvm_archive = cache / llvm["exact_archive"]["name"]
    if not llvm_archive.exists():
        fetch_file(llvm["exact_archive"]["url"], llvm_archive)
    verify_archive(llvm_archive, llvm["exact_archive"])
    llvm_dest = tool_root / "llvm-mos"
    if llvm_dest.exists():
        shutil.rmtree(llvm_dest)
    safe_extract_tar_xz(llvm_archive, tool_root)
    results = [verify_package("llvm_mos", llvm, tool_root)]

    m65 = manifest["packages"]["mega65_tools"]
    if args.m65tools_archive:
        archive = args.m65tools_archive.resolve()
        verify_archive(archive, m65["exact_archive"])
        m65_dest = tool_root / "m65tools"
        if m65_dest.exists():
            shutil.rmtree(m65_dest)
        extract_m65tools(archive, m65_dest)
        results.append(verify_package("mega65_tools", m65, tool_root))
    else:
        results.append({
            "package": "mega65_tools",
            "status": "not-installed",
            "reason": "optional for product builds; pass --m65tools-archive for hardware deployment",
        })
    print(json.dumps({"schema": "lisp65-toolchain-fetch-v1", "status": "pass", "packages": results}, sort_keys=True))
    return 0


def command_selftest(_args) -> int:
    with tempfile.TemporaryDirectory(prefix="lisp65-toolchain-selftest-") as temp:
        root = Path(temp)
        (root / "bin").mkdir()
        tool = root / "bin/tool"
        tool.write_bytes(b"tool\n")
        tool.chmod(0o755)
        (root / "alias").symlink_to("bin/tool")
        first = tree_identity(root)
        if first["regular_files"] != 1 or first["symlinks"] != 1:
            raise ToolchainError("tree identity count selftest failed")
        tool.write_bytes(b"tampered\n")
        second = tree_identity(root)
        if first["sha256"] == second["sha256"]:
            raise ToolchainError("tree identity mutation selftest failed")
    print("toolchain-external: SELFTEST PASS mutation=rejected")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--tool-root", type=Path, default=ROOT / "tools")
    verify.add_argument("--product-build-only", action="store_true")
    verify.set_defaults(func=command_verify)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--tool-root", type=Path, default=ROOT / "tools")
    fetch.add_argument("--cache", type=Path, default=Path.home() / ".cache/lisp65/toolchains")
    fetch.add_argument("--m65tools-archive", type=Path)
    fetch.set_defaults(func=command_fetch)
    selftest = sub.add_parser("selftest")
    selftest.set_defaults(func=command_selftest)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, subprocess.CalledProcessError, ToolchainError, tarfile.TarError) as error:
        print(f"toolchain-external: FAIL: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
