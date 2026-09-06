#!/usr/bin/env python3
"""Build or verify a public Workbench product with a bound source world.

The release-specific product drivers remain immutable release machinery.  This
small parameterized front end gives their public Make targets explicit build
and verify semantics and binds verification to the source tree that produced
the selected artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-workbench-product-source-signature-v1"
RELEASES = {
    "v150": ("v1.5.0", "tools/host-lisp/c2_v150_public_product.py",
             "config/c2-v150-public-build-authority.json"),
    "v160": ("v1.6.0", "tools/host-lisp/c2_v160_public_product.py",
             "config/c2-v160-public-build-authority.json"),
    "v170": ("v1.7.0", "tools/host-lisp/c2_v170_public_product.py",
             "config/c2-v170-public-build-authority.json"),
    "v180": ("v1.8.0", "tools/host-lisp/c2_v180_public_product.py",
             "config/c2-v180-public-build-authority.json"),
    "v190": ("v1.9.0", "tools/host-lisp/c2_v190_public_product.py",
             "config/c2-v190-public-build-authority.json"),
    "v200": ("v2.0.0", "tools/host-lisp/c2_v200_public_product.py",
             "config/c2-v200-public-build-authority.json"),
    "v210": ("v2.1.0", "tools/host-lisp/c2_v210_public_product.py",
             "config/c2-v210-public-build-authority.json"),
}


class ProductLifecycleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProductLifecycleError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(root: Path, path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"source-signature input must be a regular file: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def release_row(release: str, root: Path = ROOT) -> dict[str, Any]:
    require(release in RELEASES, f"unknown product release: {release}")
    version, driver_name, authority_name = RELEASES[release]
    authority_path = root / authority_name
    authority = load(authority_path)
    require(authority.get("release") == version,
            f"{release} authority release drift")
    manifest_name = authority.get("candidate_manifest_path")
    require(isinstance(manifest_name, str) and manifest_name.startswith("build/")
            and ".." not in Path(manifest_name).parts,
            f"{release} candidate manifest path is not build-owned")
    return {"id": release, "version": version,
            "driver": root / driver_name, "authority": authority_path,
            "manifest": root / manifest_name,
            "signature": (root / manifest_name).with_name("source-signature.json")}


def source_signature(release: str, root: Path = ROOT) -> dict[str, Any]:
    selected = release_row(release, root)
    rows = []
    for directory in (root / "src", root / "lib"):
        require(directory.is_dir() and not directory.is_symlink(),
                f"source-signature directory absent: {directory}")
        for path in sorted(directory.rglob("*"),
                           key=lambda item: item.relative_to(root).as_posix()):
            if path.is_symlink():
                raise ProductLifecycleError(
                    f"source-signature population contains symlink: {path}")
            if path.is_file():
                rows.append(bind(root, path))
    rows.extend((bind(root, selected["authority"]), bind(root, selected["driver"])))
    require(rows and len({row["path"] for row in rows}) == len(rows),
            "source-signature population is empty or duplicated")
    projection = [{key: row[key] for key in ("path", "bytes", "sha256")}
                  for row in rows]
    return {"algorithm": "sha256-over-canonical-file-identities",
            "population": "all regular files under src/ and lib/, plus release authority and driver",
            "file_count": len(rows), "files": rows,
            "sha256": sha(canonical(projection))}


def signature_receipt(release: str, root: Path = ROOT) -> dict[str, Any]:
    selected = release_row(release, root)
    manifest = bind(root, selected["manifest"])
    return {"format": FORMAT, "status": "passed-source-world-bound",
            "release": release, "version": selected["version"],
            "source": source_signature(release, root),
            "selected_manifest": manifest,
            "verification_order": "source-signature-before-release-driver-check"}


def run_driver(selected: dict[str, Any], action: str,
               runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
               ) -> str:
    completed = runner([sys.executable, str(selected["driver"]), action],
                       cwd=selected["driver"].parents[2], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       check=False)
    require(completed.returncode == 0,
            f"{selected['id']} product {action} failed:\n{completed.stdout}")
    print(completed.stdout.rstrip())
    return completed.stdout


def build(release: str, root: Path = ROOT) -> None:
    selected = release_row(release, root)
    before = source_signature(release, root)
    run_driver(selected, "build")
    after = source_signature(release, root)
    require(before == after, "source world changed during product build")
    receipt = signature_receipt(release, root)
    require(receipt["source"] == before, "source receipt changed after product build")
    selected["signature"].write_bytes(canonical(receipt))
    print(f"workbench-product: BUILD PASS release={release} "
          f"sources={before['file_count']} signature={before['sha256']}")


def verify_state(release: str, root: Path = ROOT) -> dict[str, Any]:
    selected = release_row(release, root)
    receipt = load(selected["signature"])
    require(receipt.get("format") == FORMAT
            and receipt.get("status") == "passed-source-world-bound"
            and receipt.get("release") == release
            and receipt.get("version") == selected["version"]
            and receipt.get("verification_order")
            == "source-signature-before-release-driver-check",
            "product source-signature receipt envelope drift")
    current = source_signature(release, root)
    require(receipt.get("source") == current,
            "product source world differs from the bytes being verified; rebuild required")
    require(receipt.get("selected_manifest") == bind(root, selected["manifest"]),
            "selected product manifest differs from source-signature receipt")
    return receipt


def verify(release: str, root: Path = ROOT,
           runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
           ) -> None:
    selected = release_row(release, root)
    receipt = verify_state(release, root)
    output = run_driver(selected, "check", runner)
    require("FULL PASS" in output,
            "release driver did not report its complete product check")
    print(f"workbench-product: VERIFY PASS release={release} "
          f"signature={receipt['source']['sha256']}")


def artifact(release: str, role: str, root: Path = ROOT) -> None:
    selected = release_row(release, root)
    value = load(selected["manifest"])
    rows = value.get("artifacts")
    require(isinstance(rows, list), "candidate manifest artifact list is absent")
    matches = [row for row in rows if isinstance(row, dict) and row.get("role") == role]
    require(len(matches) == 1 and isinstance(matches[0].get("path"), str),
            f"candidate manifest does not contain exactly one {role} artifact")
    path = root / matches[0]["path"]
    require(bind(root, path)["sha256"] == matches[0].get("sha256"),
            f"candidate {role} bytes differ from manifest")
    print(path.relative_to(root).as_posix())


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="lisp65-product-source-") as name:
        root = Path(name)
        (root / "src").mkdir()
        (root / "lib").mkdir()
        (root / "config").mkdir()
        (root / "tools/host-lisp").mkdir(parents=True)
        (root / "build/test").mkdir(parents=True)
        (root / "src/a.c").write_text("int a;\n", encoding="utf-8")
        (root / "lib/a.lisp").write_text("(defun a () 1)\n", encoding="utf-8")
        authority = root / "config/authority.json"
        authority.write_bytes(canonical({"release": "v0.0.0",
            "candidate_manifest_path": "build/test/candidate-manifest.json"}))
        driver = root / "tools/host-lisp/driver.py"
        driver.write_text("print('FULL PASS old-bytes')\n", encoding="utf-8")
        manifest = root / "build/test/candidate-manifest.json"
        manifest.write_bytes(canonical({"old": "bytes"}))
        old = RELEASES["v150"]
        RELEASES["v150"] = ("v0.0.0", "tools/host-lisp/driver.py",
                             "config/authority.json")
        try:
            receipt = signature_receipt("v150", root)
            (root / "build/test/source-signature.json").write_bytes(canonical(receipt))
            verify_state("v150", root)
            (root / "src/a.c").write_text("int changed;\n", encoding="utf-8")
            called = False

            def forbidden(*_args, **_kwargs):
                nonlocal called
                called = True
                return subprocess.CompletedProcess([], 0, "FULL PASS old-bytes\n")

            try:
                verify("v150", root, forbidden)
            except ProductLifecycleError as error:
                require("source world differs" in str(error),
                        "changed-source mutation failed for the wrong reason")
            else:
                raise ProductLifecycleError(
                    "changed source yielded verification of old product bytes")
            require(not called, "release checker ran before source signature")
        finally:
            RELEASES["v150"] = old
    print("workbench-product: SELFTEST PASS mutation=changed-source-before-old-bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify", "artifact", "selftest"))
    parser.add_argument("--release", choices=tuple(RELEASES), default="v200")
    parser.add_argument("--role", default="product-d81")
    args = parser.parse_args()
    try:
        if args.action == "build":
            build(args.release)
        elif args.action == "verify":
            verify(args.release)
        elif args.action == "artifact":
            artifact(args.release, args.role)
        else:
            selftest()
    except (OSError, ValueError, json.JSONDecodeError, ProductLifecycleError) as error:
        print(f"workbench-product: FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
