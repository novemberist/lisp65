#!/usr/bin/env python3
"""Rebind unchanged G6 case receipts to the lisp65 1.0.1-light package."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/host-lisp/r6_package_rebind_101.py"
OLD_SEAL = ROOT / "tests/bytecode/dialect-v2/evidence/promotions/r6-g6-hardware-acceptance-aed1595.tar.gz"
OLD_SEAL_SHA = "b339a274a97c947025ce66b09cd54ce5af73e24d8a99328fcb0659ffa605ddba"
OLD_TOP_REL = "payload/build/r6/g6/run-20260715-02-preflight-212f957/g6-hardware-receipt.json"
OLD_TOP_SHA = "edcca70cc747be2b42ab20ee96c74dceb46e490125dc4c6d740a7d1b4c369b7d"
OLD_SHIP_REL = "payload/build/r6/ship/manifest.json"
OLD_SHIP_SHA = "323d6f497c1849af3916cfbe9c3f0d73936eaa72f271d97412666f25369f6764"
PRODUCT_SET = "c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165"
FORMAT = "lisp65-r6-package-rebind-101-v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class RebindError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RebindError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RebindError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RebindError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise RebindError(f"{label} must contain an object")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RebindError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise RebindError(f"{label} is not canonical")
    return value


def run_verifier(root: Path, label: str) -> None:
    verifier = root / "verify.py"
    if verifier.is_symlink() or not verifier.is_file():
        raise RebindError(f"{label} lacks an offline verifier")
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=root,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
        },
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if completed.returncode:
        raise RebindError(f"{label} offline verification failed: {completed.stdout.strip()}")


def safe_extract(archive_path: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or not member.isfile():
                    raise RebindError("historical G6 seal contains an unsafe member")
            archive.extractall(destination, filter="data")
    except (OSError, tarfile.TarError) as exc:
        raise RebindError(f"cannot extract historical G6 seal: {exc}") from exc


def source_commit(value: str, *, historical: bool = False) -> tuple[str, str]:
    if not COMMIT_RE.fullmatch(value):
        raise RebindError("source commit must be a full lowercase commit")
    completed = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if completed.returncode or completed.stdout.strip() != value:
        raise RebindError("source commit is unavailable")
    if not historical:
        materialized = subprocess.run(
            ["git", "show", f"{value}:{TOOL.relative_to(ROOT).as_posix()}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if materialized.returncode or materialized.stdout != TOOL.read_bytes():
            raise RebindError("source commit does not bind the rebind verifier")
    date = subprocess.run(
        ["git", "show", "-s", "--format=%cs", value], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
    ).stdout.strip()
    return value, date


def artifact_map(manifest: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    rows = manifest.get("artifacts")
    if not isinstance(rows, list) or len(rows) != 13:
        raise RebindError(f"{label} must enumerate 13 product artifacts")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("role"), str):
            raise RebindError(f"{label} contains a malformed artifact")
        role = row["role"]
        if role in result:
            raise RebindError(f"{label} repeats role {role}")
        if not SHA_RE.fullmatch(str(row.get("sha256", ""))) or type(row.get("bytes")) is not int:
            raise RebindError(f"{label} artifact binding is malformed: {role}")
        result[role] = row
    return result


def compare_artifacts(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if set(old) != set(new) or len(old) != 13:
        raise RebindError("historical/new package artifact roles differ")
    result = []
    for role in sorted(old):
        left, right = old[role], new[role]
        for key in ("name", "bytes", "sha256"):
            if left.get(key) != right.get(key):
                raise RebindError(f"product artifact changed during package repair: {role}:{key}")
        result.append({
            "role": role, "name": right["name"], "bytes": right["bytes"],
            "sha256": right["sha256"], "byte_identical": True,
        })
    return result


def historical_state() -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any], dict[str, Any]]:
    if sha(OLD_SEAL) != OLD_SEAL_SHA:
        raise RebindError("historical G6 seal SHA drift")
    temporary = tempfile.TemporaryDirectory(prefix="lisp65-r6-101-old-g6-")
    root = Path(temporary.name)
    try:
        safe_extract(OLD_SEAL, root)
        run_verifier(root, "historical G6 seal")
        top_path = root / OLD_TOP_REL
        ship_path = root / OLD_SHIP_REL
        if sha(top_path) != OLD_TOP_SHA or sha(ship_path) != OLD_SHIP_SHA:
            raise RebindError("historical G6 top/Ship binding drift")
        top = load(top_path, "historical G6 top receipt")
        ship = load(ship_path, "historical R6 Ship manifest")
        if (
            top.get("result") != "passed"
            or top.get("product_artifact_set_sha256") != PRODUCT_SET
            or top.get("ship_manifest_sha256") != OLD_SHIP_SHA
            or ship.get("result") != "passed"
            or ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        ):
            raise RebindError("historical G6 product/claim drift")
        cases = top.get("cases")
        if not isinstance(cases, list) or len(cases) != 5:
            raise RebindError("historical G6 case inventory drift")
        for row in cases:
            receipt_path = root / "payload" / Path(*PurePosixPath(relative(row["receipt"], "case receipt")).parts)
            if sha(receipt_path) != row.get("receipt_sha256"):
                raise RebindError(f"historical G6 case receipt drift: {row.get('id')}")
            receipt = load(receipt_path, "historical G6 case receipt")
            if (
                receipt.get("result") != "passed"
                or receipt.get("product_artifact_set_sha256") != PRODUCT_SET
                or receipt.get("cycle_id") != row.get("cycle_id")
            ):
                raise RebindError(f"historical G6 case semantic drift: {row.get('id')}")
        return temporary, root, top, ship
    except Exception:
        temporary.cleanup()
        raise


def new_state(ship_root: Path, preflight_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_verifier(ship_root, "1.0.1 R6 package")
    manifest_path = ship_root / "manifest.json"
    manifest = load(manifest_path, "1.0.1 R6 manifest")
    preflight = load(preflight_path, "1.0.1 static preflight")
    if (
        manifest.get("result") != "passed"
        or manifest.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
        or preflight.get("result") != "passed"
        or preflight.get("ship", {}).get("manifest_sha256") != sha(manifest_path)
        or preflight.get("ship", {}).get("product_artifact_set_sha256") != PRODUCT_SET
        or preflight.get("counts") != {
            "total": 15, "sealed_G3_pass": 9,
            "G6_ready_not_run": 5, "G6_profile_not_applicable": 1,
        }
    ):
        raise RebindError("1.0.1 package/preflight binding drift")
    return manifest, preflight


def receipt_value(*, commit: str, ship_root: Path, preflight_path: Path) -> dict[str, Any]:
    commit, measured_on = source_commit(commit)
    temporary, _, old_top, old_ship = historical_state()
    try:
        new_ship, _ = new_state(ship_root, preflight_path)
        artifacts = compare_artifacts(
            artifact_map(old_ship, "historical R6 Ship"),
            artifact_map(new_ship, "1.0.1 R6 Ship"),
        )
        cases = [
            {
                "id": row["id"], "cycle_id": row["cycle_id"],
                "historical_receipt": row["receipt"],
                "historical_receipt_sha256": row["receipt_sha256"],
                "status": "passed-product-sha-bound-reused",
            }
            for row in old_top["cases"]
        ]
        return {
            "format": FORMAT, "version": 1,
            "id": "lisp65-1.0.1-light-package-rebind",
            "status": "passed-no-hardware-rerun",
            "source_commit": commit, "measured_on": measured_on,
            "release": {"version": "1.0.1", "scope": "package-and-documentation-only"},
            "historical_g6": {
                "archive": OLD_SEAL.relative_to(ROOT).as_posix(),
                "archive_sha256": OLD_SEAL_SHA,
                "top_receipt": OLD_TOP_REL,
                "top_receipt_sha256": OLD_TOP_SHA,
                "ship_manifest_sha256": OLD_SHIP_SHA,
                "cases": cases,
            },
            "new_package": {
                "ship_manifest": (ship_root / "manifest.json").relative_to(ROOT).as_posix(),
                "ship_manifest_sha256": sha(ship_root / "manifest.json"),
                "package_set_sha256": new_ship["package_set_sha256"],
                "static_preflight": preflight_path.relative_to(ROOT).as_posix(),
                "static_preflight_sha256": sha(preflight_path),
            },
            "product_identity": {
                "historical_artifact_set_sha256": PRODUCT_SET,
                "new_artifact_set_sha256": PRODUCT_SET,
                "artifact_count": 13,
                "byte_identical_artifacts": 13,
                "product_sha_changes": 0,
                "artifacts": artifacts,
            },
            "receipt_policy": {
                "rule": "passed SHA-bound case receipts survive package-only changes when every product artifact is byte-identical",
                "hardware_cases_reexecuted": 0,
                "hardware_receipts_reused": 5,
                "offline_historical_seal_verification": "passed",
                "new_static_preflight": "passed",
            },
            "claims": old_top["claims"] | {"release": "eligible-for-1.0.1-package-promotion"},
            "result": "passed",
        }
    finally:
        temporary.cleanup()


def create(*, commit: str, ship_root: Path, preflight_path: Path, output: Path) -> None:
    value = receipt_value(commit=commit, ship_root=ship_root, preflight_path=preflight_path)
    if output.exists() or output.is_symlink():
        raise RebindError(f"rebind receipt output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(value))
    verify(path=output, ship_root=ship_root, preflight_path=preflight_path)
    print("r6-package-rebind-101: PASS artifacts=13/13 G6-receipts=5/5 power-cycles=0")


def verify(*, path: Path, ship_root: Path, preflight_path: Path) -> None:
    actual = load(path, "1.0.1 package rebind receipt")
    commit, _ = source_commit(str(actual.get("source_commit", "")), historical=True)
    expected = receipt_value(commit=commit, ship_root=ship_root, preflight_path=preflight_path)
    if actual != expected:
        raise RebindError("1.0.1 package rebind receipt drift")
    print("r6-package-rebind-101: VERIFY PASS artifacts=13/13 G6-receipts=5/5")


def selftest() -> None:
    rows = {
        f"role-{index}": {"role": f"role-{index}", "name": f"n{index}", "bytes": index + 1, "sha256": f"{index:064x}"}
        for index in range(13)
    }
    if len(compare_artifacts(rows, deepcopy(rows))) != 13:
        raise RebindError("valid artifact fixture was rejected")
    for label, mutate in (
        ("missing", lambda value: value.pop("role-0")),
        ("sha", lambda value: value["role-0"].__setitem__("sha256", "f" * 64)),
        ("size", lambda value: value["role-0"].__setitem__("bytes", 99)),
    ):
        candidate = deepcopy(rows)
        mutate(candidate)
        try:
            compare_artifacts(rows, candidate)
        except RebindError:
            continue
        raise RebindError(f"negative artifact mutation was accepted: {label}")
    print("r6-package-rebind-101: SELFTEST PASS mutations=3")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    create_parser = sub.add_parser("create")
    create_parser.add_argument("--source-commit", required=True)
    create_parser.add_argument("--ship", type=Path, default=Path("build/r6/ship"))
    create_parser.add_argument("--preflight", type=Path, required=True)
    create_parser.add_argument("--out", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("receipt", type=Path)
    verify_parser.add_argument("--ship", type=Path, default=Path("build/r6/ship"))
    verify_parser.add_argument("--preflight", type=Path, required=True)
    return result


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "create":
            create(
                commit=args.source_commit, ship_root=rooted(args.ship),
                preflight_path=rooted(args.preflight), output=rooted(args.out),
            )
        else:
            verify(
                path=rooted(args.receipt), ship_root=rooted(args.ship),
                preflight_path=rooted(args.preflight),
            )
        return 0
    except (RebindError, OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"r6-package-rebind-101: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
