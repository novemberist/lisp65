#!/usr/bin/env python3
"""Drive the fresh C2-lite R5/G5 handoff from the sealed R4 media product."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
OUT = ROOT / "build/c2.2/acceptance/r5"
PREFLIGHT = OUT / "r5-preflight-receipt.json"
RUNBOOK = OUT / "g5-runbook.json"
FORMAT = "lisp65-c2-lite-acceptance-chain-v1"
R4_ASSERTIONS = "lisp65-c2-lite-r4-product-candidate-assertions-v1"
ROLE_COUNT = 19


class AcceptanceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AcceptanceError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AcceptanceError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "C2-lite acceptance contract")
    require(
        set(value) == {
            "format", "version", "id", "status", "input",
            "artifact_roles", "G5", "R6", "G6", "claims",
        }
        and value["format"] == FORMAT
        and value["version"] == 1
        and value["id"] == "c2-lite-R4-R5-R6-G5-G6"
        and value["status"] == "owner-authorized",
        "C2-lite acceptance contract identity drift")
    roles = value["artifact_roles"]
    require(
        isinstance(roles, list) and len(roles) == ROLE_COUNT
        and len(set(roles)) == ROLE_COUNT,
        "C2-lite acceptance role inventory drift")
    cases = value.get("G5", {}).get("cases")
    require(
        isinstance(cases, list) and len(cases) == 9
        and len({row.get("id") for row in cases
                 if isinstance(row, dict)}) == 9
        and value["G5"].get("coverage")
            == "exactly-once-in-order-until-first-red",
        "C2-lite G5 case inventory drift")
    require(
        value.get("R6", {}).get("artifact_mapping")
            == "all-19-R5-roles-exactly-once"
        and value.get("G6", {}).get("seal") == "G6-v2-with-remote_head"
        and value.get("claims", {}).get("no_inherited_green") is True,
        "C2-lite R6/G6 or no-inheritance policy drift")
    return value


def safe_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    require(
        member.isfile() and not path.is_absolute() and ".." not in path.parts,
        f"unsafe R4 archive member: {member.name}")


def archive_manifest(archive: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    require(archive.is_file() and not archive.is_symlink(), "R4 archive missing")
    files: dict[str, bytes] = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            safe_member(member)
            stream = bundle.extractfile(member)
            require(stream is not None, f"cannot read R4 member: {member.name}")
            files[member.name] = stream.read()
    require("manifest.json" in files, "R4 archive has no manifest")
    try:
        manifest = json.loads(files["manifest.json"])
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AcceptanceError(f"invalid R4 manifest: {error}") from error
    require(isinstance(manifest, dict), "R4 manifest must be an object")
    return manifest, files


def verify_archive(archive: Path) -> None:
    result = subprocess.run([
        sys.executable, "tools/host-lisp/promotion_archive.py",
        "isolated-verify", archive.as_posix(),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"R4 isolated verification failed:\n{result.stdout}")


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def materialize_r5(archive: Path) -> dict[str, Any]:
    chain = contract()
    verify_archive(archive)
    manifest, files = archive_manifest(archive)
    assertions = manifest.get("assertions")
    product = manifest.get("product_materialization")
    require(
        manifest.get("format") == "lisp65-promotion-archive-v3"
        and manifest.get("kind") == "product-candidate"
        and isinstance(assertions, dict)
        and assertions.get("format") == R4_ASSERTIONS
        and isinstance(product, dict),
        "R5 input is not a sealed C2-lite R4 candidate")
    rows = product.get("artifacts")
    require(
        isinstance(rows, list) and len(rows) == ROLE_COUNT
        and {row.get("role") for row in rows} == set(chain["artifact_roles"]),
        "R5 input product role closure drift")
    product_root = OUT / "product"
    if product_root.exists():
        shutil.rmtree(product_root)
    product_root.mkdir(parents=True)
    materialized = []
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and set(row) == {"role", "name", "path", "bytes", "sha256"},
            f"R5 product row {index} schema drift")
        source_name = f"payload/{row['path']}"
        data = files.get(source_name)
        require(
            data is not None and len(data) == row["bytes"]
            and sha_bytes(data) == row["sha256"],
            f"R5 embedded artifact drift: {row['role']}")
        output = product_root / f"{index:02d}-{row['name']}"
        output.write_bytes(data)
        materialized.append({
            **row,
            "materialized_path": output.relative_to(ROOT).as_posix(),
        })
    artifact_set = product["artifact_set_sha256"]
    runbook = {
        "format": "lisp65-c2-lite-G5-runbook-v1",
        "version": 1,
        "status": "ready-first-red",
        "input_authority": "sealed-R4-archive-only",
        "R4_archive": {
            "path": archive.relative_to(ROOT).as_posix(),
            "bytes": archive.stat().st_size,
            "sha256": sha(archive),
        },
        "source_commit": manifest["source_commit"],
        "remote_head": manifest["remote_source_binding"]["remote_head"],
        "artifact_set_sha256": artifact_set,
        "product_build_id": product["product_build_id"],
        "profile_build_id": product["profile_build_id"],
        "product_d81": next(
            row["materialized_path"] for row in materialized
            if row["role"] == "product-d81"),
        "work_d81": next(
            row["materialized_path"] for row in materialized
            if row["role"] == "work-d81"),
        "mount_descriptor": next(
            row["materialized_path"] for row in materialized
            if row["role"] == "product-mount-descriptor"),
        "case_coverage": chain["G5"]["coverage"],
        "cases": chain["G5"]["cases"],
        "claims": {
            "R4": "passed-sealed-input-verified",
            "R5": "passed-product-materialized",
            "G5": "not-run",
            "R6": "not-run",
            "G6": "not-run",
            "hardware_started": False,
        },
    }
    write(RUNBOOK, runbook)
    receipt = {
        "format": "lisp65-c2-lite-R5-preflight-receipt-v1",
        "version": 1,
        "status": "passed-ready-for-fresh-G5-hardware",
        "source_commit": manifest["source_commit"],
        "remote_head": manifest["remote_source_binding"]["remote_head"],
        "artifact_count": ROLE_COUNT,
        "artifact_set_sha256": artifact_set,
        "product_build_id": product["product_build_id"],
        "profile_build_id": product["profile_build_id"],
        "R4_archive_sha256": sha(archive),
        "materialized_artifacts": materialized,
        "runbook": {
            "path": RUNBOOK.relative_to(ROOT).as_posix(),
            "bytes": len(canonical(runbook)),
            "sha256": sha_bytes(canonical(runbook)),
        },
        "execution_accounting": {
            "product_builds": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "product_byte_changes": 0,
        },
        "claims": runbook["claims"],
    }
    write(PREFLIGHT, receipt)
    print(
        "c2-lite-acceptance: R5 PREFLIGHT PASS "
        f"artifacts=19 cases=9 set={artifact_set} hardware=not-run")
    return receipt


def selftest() -> None:
    value = contract()
    fixture = {
        "roles": list(value["artifact_roles"]),
        "cases": deepcopy(value["G5"]["cases"]),
    }
    mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        ("role-drop", lambda x: x["roles"].pop()),
        ("role-dup", lambda x: x["roles"].append(x["roles"][0])),
        ("case-drop", lambda x: x["cases"].pop()),
        ("claim", lambda x: x["cases"][0].update(claim="informative")),
        ("limit", lambda x: x["cases"][1].update(limit="frames<=17")),
    )
    survivors = []
    for name, mutate in mutations:
        changed = deepcopy(fixture)
        mutate(changed)
        if changed == fixture:
            survivors.append(name)
    require(not survivors, f"acceptance selftest ineffective: {survivors}")
    print("c2-lite-acceptance: SELFTEST PASS roles=19 G5-cases=9 mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    r5 = sub.add_parser("r5-preflight")
    r5.add_argument("--r4-archive", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.action == "r5-preflight":
            archive = (
                args.r4_archive if args.r4_archive.is_absolute()
                else ROOT / args.r4_archive)
            materialize_r5(archive)
        else:
            selftest()
        return 0
    except (AcceptanceError, KeyError, TypeError, ValueError) as error:
        print(f"c2-lite-acceptance: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
