#!/usr/bin/env python3
"""Prove the two R7 public-manifest prerequisites before release promotion."""

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
CONTRACT = ROOT / "config/r7-release-manifest-contract.json"
REGISTER = ROOT / "config/promotion-register.json"
SEAL_TOOL = ROOT / "tools/host-lisp/r6_g6_seal.py"
TOOL = ROOT / "tools/host-lisp/r7_manifest_prerequisites.py"
FORMAT = "lisp65-r7-public-manifest-prerequisites-v1"
RECEIPT_FORMAT = "lisp65-r7-manifest-prerequisites-receipt-v1"
PRODUCT_SET = "c41b9643ada1195f48c384d9d582a3d870a68c4ccc3dee9500dc86a7f009c165"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class PrerequisiteError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PrerequisiteError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PrerequisiteError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrerequisiteError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise PrerequisiteError(f"{label} must contain an object")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R7 manifest contract")
    if (
        value.get("format") != "lisp65-r7-release-manifest-contract-v1"
        or value.get("version") != 1 or value.get("id") != "r7-public-manifest-prerequisites"
        or value.get("status") != "authorized-for-prerequisite-proof"
        or value.get("input") != {
            "promotion_id": "r6-g6-hardware-acceptance-aed1595",
            "archive_sha256": "b339a274a97c947025ce66b09cd54ce5af73e24d8a99328fcb0659ffa605ddba",
            "product_artifact_set_sha256": PRODUCT_SET,
            "ship_manifest_sha256": "323d6f497c1849af3916cfbe9c3f0d73936eaa72f271d97412666f25369f6764",
        }
        or value.get("determinism") != {
            "packed_on_source": "bound-source-commit-committer-timestamp",
            "wall_clock_source": "forbidden",
            "double_pack_axes": ["PYTHONHASHSEED", "TZ"],
            "cross_midnight": "required-two-observed-local-dates",
        }
        or value.get("claims") != {
            "product_sha_changes": 0,
            "G6_source": "registered-r6-hardware-acceptance-seal",
            "release_effect": "none-prerequisite-proof-only",
        }
    ):
        raise PrerequisiteError("R7 manifest contract semantic drift")
    roles = value.get("public_toolchain_roles")
    if not isinstance(roles, dict) or set(roles) != {
        "c1541.artifact", "rom", "sd_base", "xmega65.artifact", "xmega65.inner_artifact",
    } or len(set(roles.values())) != 5:
        raise PrerequisiteError("R7 public toolchain role map drift")
    return value


def canonical_commit(value: str) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise PrerequisiteError("source commit must be a full lowercase Git commit")
    completed = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if completed.returncode or completed.stdout.strip() != value:
        raise PrerequisiteError("source commit is unavailable or non-canonical")
    for path in (CONTRACT, TOOL):
        relative = path.relative_to(ROOT).as_posix()
        shown = subprocess.run(
            ["git", "show", f"{value}:{relative}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if shown.returncode or shown.stdout != path.read_bytes():
            raise PrerequisiteError(f"source commit does not bind R7 input: {relative}")
    return value


def commit_timestamp(value: str) -> str:
    completed = subprocess.run(
        ["git", "show", "-s", "--format=%cI", value], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    result = completed.stdout.strip()
    if completed.returncode or "T" not in result or not (result.endswith("Z") or re.search(r"[+-][0-9]{2}:[0-9]{2}$", result)):
        raise PrerequisiteError("source commit timestamp is unavailable")
    return result


def registered_archive(value: dict[str, Any]) -> Path:
    register = load(REGISTER, "promotion register")
    rows = register.get("promotions")
    expected = value["input"]
    row = next((item for item in rows if item.get("id") == expected["promotion_id"]), None) if isinstance(rows, list) else None
    if (
        not isinstance(row, dict) or row.get("kind") != "hardware-acceptance"
        or row.get("archive_sha256") != expected["archive_sha256"]
        or not isinstance(row.get("archive"), str)
    ):
        raise PrerequisiteError("R7 input is not the registered R6 acceptance seal")
    archive = ROOT / row["archive"]
    if archive.is_symlink() or not archive.is_file() or sha(archive) != expected["archive_sha256"]:
        raise PrerequisiteError("registered R6 acceptance archive byte drift")
    return archive


def safe_extract(archive: Path, directory: Path) -> None:
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise PrerequisiteError("unsafe R6 acceptance archive member")
        source.extractall(directory)


def public_toolchain(source: dict[str, Any], roles: dict[str, str]) -> dict[str, Any]:
    result = deepcopy(source)
    targets = {
        "c1541.artifact": result["c1541"]["artifact"],
        "rom": result["rom"],
        "sd_base": result["sd_base"],
        "xmega65.artifact": result["xmega65"]["artifact"],
        "xmega65.inner_artifact": result["xmega65"]["inner_artifact"],
    }
    for key, row in targets.items():
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"].startswith("/"):
            raise PrerequisiteError(f"expected absolute private path is absent: {key}")
        row.pop("path")
        row["role"] = roles[key]
    return result


def absolute_strings(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(absolute_strings(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(absolute_strings(item, f"{prefix}[{index}]"))
    elif isinstance(value, str) and value.startswith("/"):
        found.append(prefix)
    return found


def manifest_value(source_commit: str) -> dict[str, Any]:
    source_commit = canonical_commit(source_commit)
    value = contract()
    archive = registered_archive(value)
    verified = subprocess.run(
        [sys.executable, str(SEAL_TOOL), "verify", str(archive)], cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "TZ": "UTC"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if verified.returncode:
        raise PrerequisiteError(f"registered R6 acceptance seal failed verification:\n{verified.stdout}")
    with tempfile.TemporaryDirectory(prefix="r7-manifest-source-") as raw:
        extracted = Path(raw)
        safe_extract(archive, extracted)
        ship_path = extracted / "payload/build/r6/ship/manifest.json"
        top_path = extracted / "payload/build/r6/g6/run-20260715-02-preflight-212f957/g6-hardware-receipt.json"
        ship = load(ship_path, "sealed R6 Ship manifest")
        top = load(top_path, "sealed G6 top receipt")
        if (
            sha(ship_path) != value["input"]["ship_manifest_sha256"]
            or ship.get("product", {}).get("artifact_set_sha256") != PRODUCT_SET
            or top.get("product_artifact_set_sha256") != PRODUCT_SET
            or top.get("result") != "passed"
        ):
            raise PrerequisiteError("sealed R6 Ship/G6 identity drift")
        toolchain = public_toolchain(ship["toolchain"], value["public_toolchain_roles"])
        if absolute_strings(toolchain):
            raise PrerequisiteError(f"public toolchain retained absolute paths: {absolute_strings(toolchain)}")
        artifacts = deepcopy(ship["artifacts"])
        if len(artifacts) != 13 or any(row.get("identity") != "byte-identical-from-R5-archive" for row in artifacts):
            raise PrerequisiteError("public manifest artifact identity drift")
        return {
            "format": FORMAT, "version": 1,
            "status": "prerequisites-proven-not-release",
            "source_commit": source_commit,
            "packed_on": commit_timestamp(source_commit),
            "packed_on_source": "bound-source-commit-committer-timestamp",
            "input": {
                "promotion_id": value["input"]["promotion_id"],
                "archive_sha256": value["input"]["archive_sha256"],
                "ship_manifest_sha256": value["input"]["ship_manifest_sha256"],
            },
            "product": {
                "artifact_set_sha256": PRODUCT_SET,
                "artifact_count": 13, "product_sha_changes": 0,
            },
            "toolchain": toolchain,
            "artifacts": artifacts,
            "claims": top["claims"],
            "release_effect": "none-prerequisite-proof-only",
            "result": "passed",
        }


def write_manifest(source_commit: str, output: Path) -> None:
    data = canonical(manifest_value(source_commit))
    if output.exists() or output.is_symlink():
        raise PrerequisiteError(f"R7 manifest output must be fresh: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f"r7-manifest-prerequisites: EMIT PASS sha256={sha_bytes(data)} packed_on=commit")


def local_date(environment: dict[str, str]) -> str:
    completed = subprocess.run(
        ["date", "+%F"], env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, check=False,
    )
    result = completed.stdout.strip()
    if completed.returncode or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", result):
        raise PrerequisiteError("cannot measure local date for cross-midnight proof")
    return result


def preflight(source_commit: str, manifest_output: Path, receipt_output: Path) -> None:
    source_commit = canonical_commit(source_commit)
    if manifest_output.exists() or manifest_output.is_symlink() or receipt_output.exists() or receipt_output.is_symlink():
        raise PrerequisiteError("R7 prerequisite outputs must be fresh")
    axes = (("11", "Etc/GMT+12"), ("991", "Pacific/Kiritimati"))
    with tempfile.TemporaryDirectory(prefix="r7-manifest-double-pack-") as raw:
        temporary = Path(raw)
        outputs: list[Path] = []
        observed_dates: list[str] = []
        for index, (hashseed, timezone) in enumerate(axes):
            output = temporary / f"manifest-{index}.json"
            environment = {
                **os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": hashseed, "TZ": timezone,
            }
            completed = subprocess.run(
                [sys.executable, str(TOOL), "emit", "--source-commit", source_commit, "--out", str(output)],
                cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, check=False,
            )
            if completed.returncode:
                raise PrerequisiteError(f"R7 varied manifest build failed:\n{completed.stdout}")
            outputs.append(output)
            observed_dates.append(local_date(environment))
        left, right = (path.read_bytes() for path in outputs)
        if left != right or len(set(observed_dates)) != 2:
            raise PrerequisiteError("R7 cross-midnight varied double pack did not prove determinism")
        manifest = load(outputs[0], "R7 public manifest preview")
        if manifest["packed_on"] != commit_timestamp(source_commit) or absolute_strings(manifest["toolchain"]):
            raise PrerequisiteError("R7 public manifest prerequisite proof drift")
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        manifest_output.write_bytes(left)
        receipt = {
            "format": RECEIPT_FORMAT, "version": 1,
            "status": "passed-prerequisites-only",
            "source_commit": source_commit,
            "contract": {"path": CONTRACT.relative_to(ROOT).as_posix(), "sha256": sha(CONTRACT)},
            "input": contract()["input"],
            "manifest": {
                "path": manifest_output.relative_to(ROOT).as_posix(),
                "sha256": sha_bytes(left), "format": FORMAT,
            },
            "public_paths": {
                "absolute_path_count": 0,
                "role_count": 5,
                "roles": sorted(contract()["public_toolchain_roles"].values()),
            },
            "determinism": {
                "packs": 2, "byte_identical": True,
                "axes": ["PYTHONHASHSEED", "TZ"],
                "timezones": [axis[1] for axis in axes],
                "observed_local_dates": observed_dates,
                "cross_midnight": True,
                "packed_on": manifest["packed_on"],
                "packed_on_source": "bound-source-commit-committer-timestamp",
            },
            "product": {"artifact_set_sha256": PRODUCT_SET, "artifact_count": 13, "product_sha_changes": 0},
            "claims": {"G6": "source-seal-passed", "release": "not-promoted"},
            "result": "passed",
        }
        receipt_output.parent.mkdir(parents=True, exist_ok=True)
        receipt_output.write_bytes(canonical(receipt))
    print(
        f"r7-manifest-prerequisites: PASS paths=roles packed_on=commit "
        f"cross-midnight={observed_dates[0]}->{observed_dates[1]} product-delta=0 release=no"
    )


def verify_receipt(receipt_path: Path, manifest_path: Path) -> None:
    value = load(receipt_path, "R7 prerequisite receipt")
    manifest = load(manifest_path, "R7 public manifest preview")
    if (
        value.get("format") != RECEIPT_FORMAT or value.get("version") != 1
        or value.get("status") != "passed-prerequisites-only" or value.get("result") != "passed"
        or value.get("manifest", {}).get("sha256") != sha(manifest_path)
        or manifest.get("source_commit") != value.get("source_commit")
        or manifest.get("packed_on") != commit_timestamp(value["source_commit"])
        or absolute_strings(manifest.get("toolchain"))
        or value.get("public_paths", {}).get("absolute_path_count") != 0
        or value.get("determinism", {}).get("byte_identical") is not True
        or value.get("determinism", {}).get("cross_midnight") is not True
        or len(set(value.get("determinism", {}).get("observed_local_dates", []))) != 2
        or value.get("product") != {"artifact_set_sha256": PRODUCT_SET, "artifact_count": 13, "product_sha_changes": 0}
    ):
        raise PrerequisiteError("R7 prerequisite receipt semantic drift")
    print("r7-manifest-prerequisites: CHECK PASS paths=roles packed_on=commit cross-midnight=true release=no")


def selftest() -> None:
    value = contract()
    sample = {
        "c1541": {"artifact": {"path": "/usr/bin/c1541", "sha256": "1" * 64, "bytes": 1}},
        "rom": {"path": "/home/user/MEGA65.ROM", "sha256": "2" * 64, "bytes": 2},
        "sd_base": {"path": "/home/user/mega65.img", "sha256": "3" * 64, "bytes": 3},
        "xmega65": {
            "artifact": {"path": "/home/user/xmega65", "sha256": "4" * 64, "bytes": 4},
            "inner_artifact": {"path": "/bin/xmega65", "sha256": "5" * 64, "bytes": 5},
        },
    }
    public = public_toolchain(sample, value["public_toolchain_roles"])
    if absolute_strings(public) or len({row["role"] for row in (
        public["c1541"]["artifact"], public["rom"], public["sd_base"],
        public["xmega65"]["artifact"], public["xmega65"]["inner_artifact"],
    )}) != 5:
        raise PrerequisiteError("R7 role rewrite positive selftest failed")
    broken = deepcopy(public)
    broken["rom"]["path"] = "/home/user/MEGA65.ROM"
    if not absolute_strings(broken):
        raise PrerequisiteError("R7 absolute-path mutation survived selftest")
    print("r7-manifest-prerequisites: SELFTEST PASS role-rewrite=deny-capable packed_on=commit-only")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    emit = sub.add_parser("emit")
    emit.add_argument("--source-commit", required=True)
    emit.add_argument("--out", type=Path, required=True)
    preflight_parser = sub.add_parser("preflight")
    preflight_parser.add_argument("--source-commit", required=True)
    preflight_parser.add_argument("--manifest-out", type=Path, required=True)
    preflight_parser.add_argument("--receipt-out", type=Path, required=True)
    check = sub.add_parser("check")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--receipt", type=Path, required=True)
    return result


def rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "emit":
            write_manifest(args.source_commit, rooted(args.out))
        elif args.command == "preflight":
            preflight(args.source_commit, rooted(args.manifest_out), rooted(args.receipt_out))
        else:
            verify_receipt(rooted(args.receipt), rooted(args.manifest))
        return 0
    except (
        PrerequisiteError, OSError, UnicodeError, ValueError, KeyError,
        TypeError, json.JSONDecodeError, tarfile.TarError,
    ) as exc:
        print(f"r7-manifest-prerequisites: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
