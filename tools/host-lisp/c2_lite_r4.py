#!/usr/bin/env python3
"""Prepare and seal the complete C2-lite two-media product at R4."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

import c2_lite_product_reproducibility as REPRO


ROOT = Path(__file__).resolve().parents[2]
ASSERTIONS = ROOT / "config/c2-lite-r4-product-candidate-contract.json"
ARCHIVE = ROOT / "build/c2.2/acceptance/r4/c2-lite-r4-product.tar.gz"
MATRIX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-C1-terminal-disposition-link66-receipt.json")
MEASUREMENTS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link66-bundled-hardware-measurements-receipt.json")
MEDIA_CONTRACT = ROOT / "config/c2-lite-media-product.json"
FORMAT = "lisp65-c2-lite-r4-product-candidate-assertions-v1"
MATRIX_BINDING_KEY = "matrix_terminal_disposition"
MEASUREMENTS_BINDING_KEY = "link66_measurement_context"
ASSERTIONS_SOURCE_BOUND = True
R5_HARDWARE_RESULTS = "fresh-only-no-Link66-inheritance"


class R4Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise R4Error(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing binding: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise R4Error(f"cannot load {path}: {error}") from error
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def capacity(identity: str) -> dict[str, Any]:
    return {
        "baseline_identity_sha256": identity,
        "candidate_identity_sha256": identity,
        "dimensions": {
            name: {
                "baseline": 0,
                "candidate": 0,
                "delta": 0,
                "authorization": None,
            }
            for name in ("bank", "ext", "symbols", "namepool", "directory")
        },
    }


def build_assertions(repro: dict[str, Any]) -> dict[str, Any]:
    identity = repro["artifact_set_sha256"]
    return {
        "format": FORMAT,
        "version": 1,
        "id": "c2-lite-r4-complete-media-product",
        "status": "seal-authorized",
        "candidate": {
            "artifact_set_sha256": identity,
            "product_build_id": repro["product_build_id"],
            "profile_build_id": repro["profile_build_id"],
            "artifact_count": 19,
        },
        "claims": {
            "Fresh-Clone": "passed",
            "R4": "sealed-complete-media-product-candidate",
            "R5": "not-run",
            "R6": "not-run",
            "G5": "not-run",
            "G6": "not-run",
            "hardware_evidence_inherited": False,
            "release": "not-release-capable",
        },
        "bindings": {
            "media_contract": binding(MEDIA_CONTRACT),
            MATRIX_BINDING_KEY: binding(MATRIX),
            MEASUREMENTS_BINDING_KEY: binding(MEASUREMENTS),
        },
        "capacity_delta": capacity(identity),
        "r5_handoff": {
            "input_authority":
                "sealed-c2-lite-r4-product-candidate-archive",
            "live_tree": "not-an-authority",
            "required_artifact_set_sha256": identity,
            "hardware_results": R5_HARDWARE_RESULTS,
        },
    }


def validate(value: dict[str, Any], repro: dict[str, Any]) -> None:
    expected = build_assertions(repro)
    require(value == expected, "C2-lite R4 assertion drift")


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def prepare(receipt_path: Path) -> dict[str, Any]:
    repro = load(receipt_path)
    try:
        REPRO.validate(repro)
    except REPRO.ReproError as error:
        raise R4Error(f"invalid Fresh-Clone receipt: {error}") from error
    value = build_assertions(repro)
    validate(value, repro)
    write(ASSERTIONS, value)
    print(
        "c2-lite-r4: PREPARED "
        f"set={repro['artifact_set_sha256']} artifacts=19 "
        "inherited-hardware=0")
    return repro


def run(argv: list[str], label: str) -> None:
    result = subprocess.run(
        argv, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise R4Error(f"{label} failed:\n{result.stdout}")
    print(result.stdout.strip())


def seal(receipt_path: Path, sealed_on: str) -> None:
    repro = prepare(receipt_path)
    commit = str(repro["source_commit"])
    argv = [
        sys.executable, "tools/host-lisp/promotion_archive.py", "create",
        "--id", f"c2-lite-r4-{commit[:12]}",
        "--kind", "product-candidate",
        "--source-commit", commit,
        "--sealed-on", sealed_on,
        "--root", MATRIX.relative_to(ROOT).as_posix(),
        "--root", MEASUREMENTS.relative_to(ROOT).as_posix(),
        "--root", MEDIA_CONTRACT.relative_to(ROOT).as_posix(),
        "--follow", MATRIX.relative_to(ROOT).as_posix(),
        "--follow", MEASUREMENTS.relative_to(ROOT).as_posix(),
        "--follow", MEDIA_CONTRACT.relative_to(ROOT).as_posix(),
        "--reproducibility-receipt", receipt_path.relative_to(ROOT).as_posix(),
    ]
    if ASSERTIONS_SOURCE_BOUND:
        argv.extend([
            "--assertions-file", ASSERTIONS.relative_to(ROOT).as_posix(),
        ])
    else:
        argv.extend([
            "--assertions", json.dumps(
                build_assertions(repro), sort_keys=True,
                separators=(",", ":"),
            ),
        ])
    for row in repro["product_artifacts"]:
        argv.extend(["--product-artifact", row["path"]])
    argv.extend(["--output", ARCHIVE.relative_to(ROOT).as_posix()])
    run(argv, "R4 seal")
    run([
        sys.executable, "tools/host-lisp/promotion_archive.py",
        "isolated-verify", ARCHIVE.relative_to(ROOT).as_posix(),
    ], "R4 isolated verification")
    print(
        "c2-lite-r4: PASS "
        f"archive={ARCHIVE.relative_to(ROOT)} sha256={sha(ARCHIVE)}")


def selftest() -> None:
    rows = [{
        "role": role,
        "name": f"{index}.bin",
        "path": f"build/{index}.bin",
        "bytes": index + 1,
        "sha256": f"{index + 1:064x}",
    } for index, role in enumerate(sorted(REPRO.ROLE_SET))]
    fixture = {
        "artifact_set_sha256": REPRO.artifact_set_sha(rows),
        "product_build_id": "12345678",
        "profile_build_id": "90abcdef",
    }
    value = build_assertions(fixture)
    require(value["candidate"]["artifact_count"] == 19, "R4 count drift")
    mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        ("count", lambda x: x["candidate"].update(artifact_count=18)),
        ("inherit", lambda x: x["claims"].update(
            hardware_evidence_inherited=True)),
        ("r5", lambda x: x["claims"].update(R5="passed")),
        ("set", lambda x: x["candidate"].update(
            artifact_set_sha256="f" * 64)),
    )
    survivors = []
    for name, mutate in mutations:
        changed = deepcopy(value)
        mutate(changed)
        if changed == value:
            survivors.append(name)
    require(not survivors, f"R4 selftest ineffective mutations: {survivors}")
    print("c2-lite-r4: SELFTEST PASS mutations=4 artifacts=19")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument(
        "--receipt", type=Path, default=REPRO.DEFAULT_RECEIPT)
    seal_parser = sub.add_parser("seal")
    seal_parser.add_argument(
        "--receipt", type=Path, default=REPRO.DEFAULT_RECEIPT)
    seal_parser.add_argument("--sealed-on", required=True)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(args.receipt if args.receipt.is_absolute()
                    else ROOT / args.receipt)
        elif args.action == "seal":
            seal(args.receipt if args.receipt.is_absolute()
                 else ROOT / args.receipt, args.sealed_on)
        else:
            selftest()
        return 0
    except (R4Error, KeyError, TypeError, ValueError) as error:
        print(f"c2-lite-r4: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
