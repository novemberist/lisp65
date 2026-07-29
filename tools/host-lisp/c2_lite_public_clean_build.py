#!/usr/bin/env python3
"""Qualify the public C2-lite entry point in two varied fresh clones."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "config/c2-lite-public-build-authority.json"
MANIFEST = ROOT / (
    "build/c2.2/v1.2.2-candidate-media/candidate-manifest.json")
BUILD_COMMAND = ("make", "--no-print-directory", "workbench-product")
AXES = (
    {
        "id": "public-clean-a",
        "PYTHONHASHSEED": "23",
        "SOURCE_DATE_EPOCH": "1009843200",
        "TZ": "Pacific/Pago_Pago",
    },
    {
        "id": "public-clean-b",
        "PYTHONHASHSEED": "987654329",
        "SOURCE_DATE_EPOCH": "1956528000",
        "TZ": "Pacific/Kiritimati",
    },
)


class CleanBuildError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CleanBuildError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanBuildError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def run(argv: list[str] | tuple[str, ...], *, cwd: Path,
        env: dict[str, str] | None = None, label: str) -> str:
    result = subprocess.run(
        argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise CleanBuildError(
            f"{label} failed ({result.returncode}):\n"
            + "\n".join(result.stdout.splitlines()[-160:]))
    return result.stdout


def authority(root: Path = ROOT) -> dict[str, Any]:
    value = load(
        root / "config/c2-lite-public-build-authority.json",
        "public build authority")
    roles = value.get("sealed_roles")
    identity = value.get("sealed_profile_identity")
    legacy = value.get("sealed_legacy_profile_fields")
    require(
        value.get("format") == "lisp65-c2-lite-public-build-authority-v1"
        and value.get("version") == 1
        and value.get("build_model")
            == "fresh-source-single-emitter-plus-one-WPLTO"
        and value.get("private_evidence_is_build_input") is False
        and value.get("entry_point") == "make workbench-product"
        and value.get("artifact_count") == 19
        and isinstance(identity, dict)
        and set(identity) == {"field", "sha256", "meaning"}
        and identity.get("field") == "direct_entry_contract_sha256"
        and isinstance(identity.get("sha256"), str)
        and len(identity["sha256"]) == 64
        and all(character in "0123456789abcdef"
                for character in identity["sha256"])
        and isinstance(identity.get("meaning"), str)
        and "private historical receipt bytes are not build inputs"
            in identity["meaning"]
        and isinstance(legacy, dict)
        and set(legacy) == {
            "persistent_publish_plan", "v2_profile_parity_sha256", "meaning"}
        and legacy.get("persistent_publish_plan") == "38,39,40,41,0"
        and legacy.get("v2_profile_parity_sha256")
            == "4bfee9b37e9f50a556c6ca4819d368231650789995775c43f01b1ba4e8d68db9"
        and "identity only" in str(legacy.get("meaning", ""))
        and "37,38,39,40,0" in str(legacy.get("meaning", ""))
        and "current structured-ELF profile-parity gate"
            in str(legacy.get("meaning", ""))
        and isinstance(roles, dict) and len(roles) == 19,
        "public build authority envelope drift")
    for role, row in roles.items():
        require(
            isinstance(role, str) and isinstance(row, dict)
            and set(row) == {"bytes", "sha256"}
            and type(row["bytes"]) is int and row["bytes"] > 0
            and isinstance(row["sha256"], str)
            and len(row["sha256"]) == 64,
            f"sealed role authority drift: {role}")
    return value


def artifact_projection(
        root: Path, manifest: dict[str, Any],
        expected: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("artifacts")
    require(
        manifest.get("format")
            == "lisp65-c2-lite-canonical-media-product-v1"
        and manifest.get("status")
            == "passed-complete-C2-lite-two-media-product"
        and manifest.get("artifact_count") == 19
        and isinstance(rows, list) and len(rows) == 19,
        "canonical media manifest envelope drift")
    result: list[dict[str, Any]] = []
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"role", "name", "path", "bytes", "sha256"},
            "canonical media artifact schema drift")
        role = str(row["role"])
        path = root / str(row["path"])
        require(
            role in expected
            and not path.is_symlink() and path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"canonical media artifact binding drift: {role}")
        want = expected[role]
        require(
            row["bytes"] == want["bytes"]
            and row["sha256"] == want["sha256"],
            f"clean build differs from sealed role: {role}")
        result.append({
            key: row[key]
            for key in ("role", "name", "bytes", "sha256")
        })
    require(
        {row["role"] for row in result} == set(expected),
        "clean build role inventory differs from sealed authority")
    return sorted(result, key=lambda row: (row["role"], row["name"]))


def check_root(root: Path) -> dict[str, Any]:
    auth = authority(root)
    manifest_path = root / (
        "build/c2.2/v1.2.2-candidate-media/candidate-manifest.json")
    manifest = load(manifest_path, "v1.2.2 public media manifest")
    rows = artifact_projection(root, manifest, auth["sealed_roles"])
    require(
        manifest.get("artifact_set_sha256")
            == auth["sealed_product_artifact_set_sha256"],
        "canonical aggregate differs from the sealed product artifact set")
    return {
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "product_build_id": manifest["product_build_id"],
        "profile_build_id": manifest["profile_build_id"],
        "manifest_sha256": sha(manifest_path),
        "artifacts": rows,
    }


def resolve_commit(repository: Path, revision: str) -> str:
    value = run(
        ["git", "rev-parse", f"{revision}^{{commit}}"], cwd=repository,
        label="resolve public source commit").strip()
    require(
        len(value) == 40
        and all(character in "0123456789abcdef" for character in value),
        "public source commit is not a full commit identity")
    return value


def build_clone(parent: Path, repository: Path, commit: str,
                toolchain: Path, axis: dict[str, str]) -> dict[str, Any]:
    checkout = parent / axis["id"]
    environment = os.environ.copy()
    environment["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(
        ["git", "clone", "--no-local", "--no-checkout",
         str(repository), str(checkout)],
        cwd=parent, env=environment, label=f"clone {axis['id']}")
    run(
        ["git", "checkout", "--detach", commit],
        cwd=checkout, env=environment, label=f"checkout {axis['id']}")
    bundled = checkout / "tools/llvm-mos"
    require(
        not bundled.exists() and not bundled.is_symlink(),
        "public clone unexpectedly contains a bundled LLVM-MOS tree")
    bundled.symlink_to(toolchain, target_is_directory=True)
    environment.update({
        key: axis[key]
        for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")
    })
    environment["LLVM_MOS_ROOT"] = str(toolchain)
    output = run(
        BUILD_COMMAND, cwd=checkout, env=environment,
        label=f"{axis['id']} public workbench-product")
    result = check_root(checkout)
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached-public-checkout",
        "command": " ".join(BUILD_COMMAND),
        "environment": {
            key: axis[key]
            for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")
        },
        "log_lines": len(output.splitlines()),
        **result,
    }


def qualify(repository: Path, revision: str, output: Path,
            toolchain: Path) -> dict[str, Any]:
    repository = repository.resolve()
    toolchain = toolchain.resolve()
    require(
        (repository / ".git").exists()
        or (repository / ".git").is_file(),
        "source repository is not a Git checkout")
    require(
        (toolchain / "bin/mos-mega65-clang").is_file(),
        "pinned LLVM-MOS toolchain is absent")
    require(shutil.which("c1541") is not None, "c1541 is unavailable")
    commit = resolve_commit(repository, revision)
    with tempfile.TemporaryDirectory(
            prefix="lisp65-public-clean-build-") as raw:
        builds = [
            build_clone(Path(raw), repository, commit, toolchain, axis)
            for axis in AXES
        ]
    first, second = builds
    for field in (
            "artifact_set_sha256", "product_build_id", "profile_build_id",
            "artifacts"):
        require(
            first[field] == second[field],
            f"varied public clean builds diverged: {field}")
    value = {
        "format": "lisp65-c2-lite-public-clean-build-receipt-v1",
        "version": 1,
        "status": "passed",
        "measured_on": date.today().isoformat(),
        "source_commit": commit,
        "source_repository_role": "curated-public-source-snapshot",
        "entry_point": "make workbench-product",
        "private_evidence_inputs": 0,
        "builds": [{
            key: build[key] for key in (
                "id", "clone", "command", "environment", "log_lines",
                "artifact_set_sha256", "product_build_id",
                "profile_build_id", "manifest_sha256")
        } for build in builds],
        "artifact_count": 19,
        "artifact_set_sha256": first["artifact_set_sha256"],
        "product_build_id": first["product_build_id"],
        "profile_build_id": first["profile_build_id"],
        "artifacts": first["artifacts"],
        "result":
            "two-varied-fresh-public-clones-reproduce-the-sealed-role-set",
    }
    validate_receipt(value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(value))
    return value


def validate_receipt(value: dict[str, Any]) -> None:
    required = {
        "format", "version", "status", "measured_on", "source_commit",
        "source_repository_role", "entry_point", "private_evidence_inputs",
        "builds", "artifact_count", "artifact_set_sha256",
        "product_build_id", "profile_build_id", "artifacts", "result",
    }
    require(set(value) == required, "public clean-build receipt schema drift")
    require(
        value["format"] == "lisp65-c2-lite-public-clean-build-receipt-v1"
        and value["version"] == 1 and value["status"] == "passed"
        and value["source_repository_role"]
            == "curated-public-source-snapshot"
        and value["entry_point"] == "make workbench-product"
        and value["private_evidence_inputs"] == 0
        and value["artifact_count"] == 19
        and value["result"]
            == "two-varied-fresh-public-clones-reproduce-the-sealed-role-set",
        "public clean-build receipt envelope drift")
    require(
        isinstance(value["builds"], list) and len(value["builds"]) == 2
        and value["builds"][0]["environment"]
            != value["builds"][1]["environment"],
        "public clean-build receipt lacks two varied builds")
    require(
        isinstance(value["artifacts"], list)
        and len(value["artifacts"]) == 19,
        "public clean-build receipt artifact inventory drift")
    for build in value["builds"]:
        require(
            build["artifact_set_sha256"] == value["artifact_set_sha256"]
            and build["product_build_id"] == value["product_build_id"]
            and build["profile_build_id"] == value["profile_build_id"],
            "public clean-build receipt build identity drift")


def selftest() -> None:
    rows = [{
        "role": f"role-{index}", "name": f"{index}.bin",
        "bytes": index + 1, "sha256": f"{index + 1:064x}",
    } for index in range(19)]
    build = {
        "id": "a", "clone": "fresh-no-local-detached-public-checkout",
        "command": "make --no-print-directory workbench-product",
        "environment": {
            "PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1", "TZ": "A"},
        "log_lines": 1, "artifact_set_sha256": "a" * 64,
        "product_build_id": "12345678", "profile_build_id": "90abcdef",
        "manifest_sha256": "b" * 64,
    }
    value = {
        "format": "lisp65-c2-lite-public-clean-build-receipt-v1",
        "version": 1, "status": "passed", "measured_on": "2026-07-27",
        "source_commit": "c" * 40,
        "source_repository_role": "curated-public-source-snapshot",
        "entry_point": "make workbench-product",
        "private_evidence_inputs": 0,
        "builds": [build, deepcopy(build)],
        "artifact_count": 19, "artifact_set_sha256": "a" * 64,
        "product_build_id": "12345678", "profile_build_id": "90abcdef",
        "artifacts": rows,
        "result":
            "two-varied-fresh-public-clones-reproduce-the-sealed-role-set",
    }
    value["builds"][1]["id"] = "b"
    value["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2", "TZ": "B"}
    validate_receipt(value)
    mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        ("status", lambda item: item.update(status="failed")),
        ("evidence", lambda item: item.update(private_evidence_inputs=1)),
        ("one-build", lambda item: item["builds"].pop()),
        ("same-axis", lambda item: item["builds"][1].update(
            environment=deepcopy(item["builds"][0]["environment"]))),
        ("identity", lambda item: item["builds"][1].update(
            product_build_id="00000000")),
    )
    for label, mutate in mutations:
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_receipt(candidate)
        except CleanBuildError:
            continue
        raise CleanBuildError(f"selftest mutation survived: {label}")
    print(
        "c2-lite-public-clean-build: SELFTEST PASS "
        f"mutations={len(mutations)} roles=19")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("selftest")
    sub.add_parser("check-local")
    qualify_parser = sub.add_parser("qualify")
    qualify_parser.add_argument("--source-repository", type=Path, required=True)
    qualify_parser.add_argument("--source-commit", required=True)
    qualify_parser.add_argument("--output", type=Path, required=True)
    qualify_parser.add_argument(
        "--llvm-mos-root", type=Path,
        default=Path(os.environ.get(
            "LLVM_MOS_ROOT", str(ROOT / "tools/llvm-mos"))))
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            selftest()
        elif args.action == "check-local":
            value = check_root(ROOT)
            print(
                "c2-lite-public-clean-build: LOCAL PASS "
                f"roles=19 set={value['artifact_set_sha256']}")
        elif args.action == "qualify":
            output = args.output
            if not output.is_absolute():
                output = ROOT / output
            value = qualify(
                args.source_repository, args.source_commit, output,
                args.llvm_mos_root)
            print(
                "c2-lite-public-clean-build: QUALIFIED "
                f"builds=2 roles=19 set={value['artifact_set_sha256']} "
                f"receipt={output}")
        else:
            receipt = args.receipt
            if not receipt.is_absolute():
                receipt = ROOT / receipt
            value = load(receipt, "public clean-build receipt")
            validate_receipt(value)
            print(
                "c2-lite-public-clean-build: RECEIPT PASS "
                f"builds=2 roles=19 set={value['artifact_set_sha256']}")
        return 0
    except (
        CleanBuildError, OSError, ValueError, KeyError,
        subprocess.SubprocessError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-lite-public-clean-build: FIRST RED: " + str(error),
            file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
