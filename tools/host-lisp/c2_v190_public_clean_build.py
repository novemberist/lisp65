#!/usr/bin/env python3
"""Qualify v1.9.0 in two varied fresh public-source clones."""

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
AUTHORITY = Path("config/c2-v190-public-build-authority.json")
PUBLIC_MANIFEST = Path("PUBLIC-SOURCE-MANIFEST.json")
BUILD_COMMAND = ("make", "--no-print-directory", "workbench-product-v190")
AXES = (
    {
        "id": "v190-public-clean-a",
        "PYTHONHASHSEED": "17027",
        "SOURCE_DATE_EPOCH": "946684800",
        "TZ": "Pacific/Pago_Pago",
        "UMASK": "027",
    },
    {
        "id": "v190-public-clean-b",
        "PYTHONHASHSEED": "170987653",
        "SOURCE_DATE_EPOCH": "1988150400",
        "TZ": "Pacific/Kiritimati",
        "UMASK": "077",
    },
)
MUTATION_LEDGER = {
    "artifact_removed": "rejected",
    "build_identity_changed": "rejected",
    "private_evidence_added": "rejected",
    "source_manifest_changed": "rejected",
    "second_build_removed": "rejected",
    "wplto_cycle_added": "rejected",
}


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
            + "\n".join(result.stdout.splitlines()[-180:]))
    return result.stdout


def authority(root: Path) -> dict[str, Any]:
    value = load(root / AUTHORITY, "v1.9 public authority")
    roles = value.get("sealed_roles")
    require(
        value.get("format") == "lisp65-c2-public-build-authority-v7"
        and value.get("release") == "v1.9.0"
        and value.get("selected_variant") == "v1.9-native-capture-client-native-prompt-editor"
        and value.get("entry_point") == "make workbench-product-v190"
        and value.get("build_model")
            == "candidate-source-plane-plus-one-WPLTO"
        and value.get("private_evidence_is_build_input") is False
        and value.get("artifact_count") == 19
        and isinstance(roles, dict) and len(roles) == 19,
        "v1.9 public authority envelope drift")
    for role, row in roles.items():
        require(
            isinstance(role, str) and isinstance(row, dict)
            and set(row) == {"bytes", "sha256"}
            and type(row["bytes"]) is int and row["bytes"] > 0
            and isinstance(row["sha256"], str)
            and len(row["sha256"]) == 64,
            f"v1.9 sealed role drift: {role}")
    return value


def artifact_projection(root: Path, manifest: dict[str, Any],
                        expected: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("artifacts")
    require(
        manifest.get("format") == "lisp65-v1.9-public-selected-product-v1"
        and manifest.get("status")
            == "passed-public-source-selected-v1.9-A+B-product"
        and manifest.get("private_evidence_inputs") == 0
        and manifest.get("selector") == "v1.9-native-capture-client-native-prompt-editor"
        and manifest.get("artifact_count") == len(expected)
        and isinstance(rows, list) and len(rows) == len(expected),
        "v1.9 selected manifest envelope drift")
    result: list[dict[str, Any]] = []
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"role", "name", "path", "bytes", "sha256"},
            "v1.9 selected artifact schema drift")
        role = str(row["role"])
        path = root / str(row["path"])
        require(
            role in expected and path.is_file() and not path.is_symlink()
            and path.stat().st_size == row["bytes"]
            and sha(path) == row["sha256"],
            f"v1.9 selected artifact binding drift: {role}")
        require(
            row["bytes"] == expected[role]["bytes"]
            and row["sha256"] == expected[role]["sha256"],
            f"v1.9 clean build differs from sealed role: {role}")
        result.append({key: row[key]
                       for key in ("role", "name", "bytes", "sha256")})
    require({row["role"] for row in result} == set(expected),
            "v1.9 clean-build role inventory drift")
    return sorted(result, key=lambda row: (row["role"], row["name"]))


def check_root(root: Path) -> dict[str, Any]:
    auth = authority(root)
    manifest_path = root / str(auth["candidate_manifest_path"])
    manifest = load(manifest_path, "v1.9 selected manifest")
    rows = artifact_projection(root, manifest, auth["sealed_roles"])
    require(
        manifest.get("artifact_set_sha256")
            == auth["sealed_product_artifact_set_sha256"],
        "v1.9 aggregate differs from sealed artifact set")
    source_path = root / PUBLIC_MANIFEST
    source = load(source_path, "public source manifest")
    require(
        source.get("format") == "lisp65-public-source-manifest-v1"
        and source.get("source_tree_clean") is True
        and source.get("file_count") == len(source.get("files", [])),
        "public source manifest envelope drift")
    return {
        "artifact_set_sha256": manifest["artifact_set_sha256"],
        "product_build_id": manifest["product_build_id"],
        "profile_build_id": manifest["profile_build_id"],
        "manifest_sha256": sha(manifest_path),
        "public_source_manifest_sha256": sha(source_path),
        "public_source_tree_sha256": source["tree_sha256"],
        "artifacts": rows,
    }


def resolve_commit(repository: Path, revision: str) -> str:
    value = run(
        ["git", "rev-parse", f"{revision}^{{commit}}"], cwd=repository,
        label="resolve v1.9 public source commit").strip()
    require(len(value) == 40
            and all(character in "0123456789abcdef" for character in value),
            "v1.9 public source commit is not a full commit identity")
    return value


def build_clone(parent: Path, repository: Path, commit: str,
                toolchain: Path, axis: dict[str, str]) -> dict[str, Any]:
    checkout = parent / axis["id"]
    environment = os.environ.copy()
    environment["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(["git", "clone", "--no-local", "--no-checkout",
         str(repository), str(checkout)], cwd=parent, env=environment,
        label=f"clone {axis['id']}")
    run(["git", "checkout", "--detach", commit], cwd=checkout,
        env=environment, label=f"checkout {axis['id']}")
    bundled = checkout / "tools/llvm-mos"
    require(not bundled.exists() and not bundled.is_symlink(),
            "public clone unexpectedly contains a bundled LLVM-MOS tree")
    bundled.symlink_to(toolchain, target_is_directory=True)
    environment.update({key: axis[key]
                        for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")})
    environment["LLVM_MOS_ROOT"] = str(toolchain)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    output = run(
        ["sh", "-c", f"umask {axis['UMASK']} && {' '.join(BUILD_COMMAND)}"],
        cwd=checkout, env=environment,
        label=f"{axis['id']} v1.9 public build")
    require(output.count(
        "v1.9 public product: LINK PASS WPLTO=1 evidence=0") == 1,
        f"{axis['id']} does not prove exactly one WPLTO/link")
    require(output.count(
        "v1.9 public product: MEDIA PASS roles=19") == 1,
        f"{axis['id']} Completion rebuilt product inputs")
    require(output.count(
        "v1.9 public product: FULL PASS roles=19 evidence=0") == 1,
        f"{axis['id']} does not prove the full public closure")
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached-public-checkout",
        "command": " ".join(BUILD_COMMAND),
        "environment": {key: axis[key] for key in
                        ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "UMASK")},
        "log_lines": len(output.splitlines()),
        "wplto_product_link_cycles": 1,
        "completion_product_rebuilds": 0,
        **check_root(checkout),
    }


def validate_receipt(value: dict[str, Any]) -> None:
    required = {
        "format", "version", "status", "measured_on", "source_commit",
        "source_repository_role", "entry_point", "private_evidence_inputs",
        "public_source_manifest_sha256", "public_source_tree_sha256",
        "builds", "selected_variant", "artifact_count",
        "artifact_set_sha256", "product_build_id", "profile_build_id",
        "artifacts", "mutations", "result", "claim_limit",
    }
    require(set(value) == required, "v1.9 clean-build receipt schema drift")
    require(
        value["format"] == "lisp65-c2-v190-public-clean-build-receipt-v1"
        and value["version"] == 1 and value["status"] == "passed"
        and value["source_repository_role"]
            == "curated-public-source-candidate"
        and value["entry_point"] == "make workbench-product-v190"
        and value["private_evidence_inputs"] == 0
        and value["selected_variant"] == "v1.9-native-capture-client-native-prompt-editor"
        and value["artifact_count"] == 19
        and value["result"]
            == "two-varied-fresh-public-clones-reproduce-v1.9-role-set",
        "v1.9 clean-build receipt envelope drift")
    require(isinstance(value["builds"], list) and len(value["builds"]) == 2
            and value["builds"][0]["environment"]
                != value["builds"][1]["environment"],
            "v1.9 receipt lacks two varied fresh builds")
    require(isinstance(value["artifacts"], list)
            and len(value["artifacts"]) == 19,
            "v1.9 receipt artifact inventory drift")
    for build in value["builds"]:
        require(
            build["artifact_set_sha256"] == value["artifact_set_sha256"]
            and build["product_build_id"] == value["product_build_id"]
            and build["profile_build_id"] == value["profile_build_id"]
            and build["public_source_manifest_sha256"]
                == value["public_source_manifest_sha256"]
            and build["public_source_tree_sha256"]
                == value["public_source_tree_sha256"]
            and build["wplto_product_link_cycles"] == 1
            and build["completion_product_rebuilds"] == 0,
            "v1.9 receipt build identity or lifecycle drift")
    require(value["mutations"] == MUTATION_LEDGER,
            "v1.9 clean-build mutation ledger drift")


def mutation_proof(value: dict[str, Any]) -> dict[str, str]:
    mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        ("artifact_removed", lambda item: item["artifacts"].pop()),
        ("build_identity_changed", lambda item: item["builds"][1].update(
            artifact_set_sha256="0" * 64)),
        ("private_evidence_added", lambda item: item.update(
            private_evidence_inputs=1)),
        ("source_manifest_changed", lambda item: item["builds"][1].update(
            public_source_manifest_sha256="0" * 64)),
        ("second_build_removed", lambda item: item["builds"].pop()),
        ("wplto_cycle_added", lambda item: item["builds"][0].update(
            wplto_product_link_cycles=2)),
    )
    result: dict[str, str] = {}
    for label, mutate in mutations:
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_receipt(candidate)
        except CleanBuildError:
            result[label] = "rejected"
            continue
        raise CleanBuildError(f"v1.9 clean-build mutation survived: {label}")
    return result


def qualify(repository: Path, revision: str, output: Path,
            toolchain: Path) -> dict[str, Any]:
    repository = repository.resolve()
    toolchain = toolchain.resolve()
    require((repository / ".git").exists(),
            "v1.9 public source repository is not a Git checkout")
    require((toolchain / "bin/mos-mega65-clang").is_file(),
            "pinned LLVM-MOS toolchain is absent")
    require(shutil.which("c1541") is not None, "c1541 is unavailable")
    commit = resolve_commit(repository, revision)
    with tempfile.TemporaryDirectory(
            prefix="lisp65-v190-public-clean-build-") as raw:
        builds = [build_clone(Path(raw), repository, commit, toolchain, axis)
                  for axis in AXES]
    first, second = builds
    for field in ("artifact_set_sha256", "product_build_id",
                  "profile_build_id", "public_source_manifest_sha256",
                  "public_source_tree_sha256", "artifacts"):
        require(first[field] == second[field],
                f"varied v1.9 public builds diverged: {field}")
    value = {
        "format": "lisp65-c2-v190-public-clean-build-receipt-v1",
        "version": 1, "status": "passed",
        "measured_on": date.today().isoformat(),
        "source_commit": commit,
        "source_repository_role": "curated-public-source-candidate",
        "entry_point": "make workbench-product-v190",
        "private_evidence_inputs": 0,
        "public_source_manifest_sha256": first["public_source_manifest_sha256"],
        "public_source_tree_sha256": first["public_source_tree_sha256"],
        "builds": [{key: build[key] for key in (
            "id", "clone", "command", "environment", "log_lines",
            "wplto_product_link_cycles", "completion_product_rebuilds",
            "artifact_set_sha256", "product_build_id", "profile_build_id",
            "manifest_sha256", "public_source_manifest_sha256",
            "public_source_tree_sha256")} for build in builds],
        "selected_variant": "v1.9-native-capture-client-native-prompt-editor",
        "artifact_count": len(first["artifacts"]),
        "artifact_set_sha256": first["artifact_set_sha256"],
        "product_build_id": first["product_build_id"],
        "profile_build_id": first["profile_build_id"],
        "artifacts": first["artifacts"],
        "mutations": deepcopy(MUTATION_LEDGER),
        "result": "two-varied-fresh-public-clones-reproduce-v1.9-role-set",
        "claim_limit": (
            "This receipt qualifies public source reproduction of the "
            "Halt-A-selected v1.9 product. It does not publish, tag, release, "
            "or extend hardware acceptance claims."),
    }
    require(mutation_proof(value) == MUTATION_LEDGER,
            "v1.9 clean-build mutation proof drift")
    validate_receipt(value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(value))
    return value


def selftest() -> None:
    rows = [{"role": f"role-{index}", "name": f"{index}.bin",
             "bytes": index + 1, "sha256": f"{index + 1:064x}"}
            for index in range(19)]
    build = {
        "id": "a", "clone": "fresh-no-local-detached-public-checkout",
        "command": "make --no-print-directory workbench-product-v190",
        "environment": {"PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1",
                        "TZ": "A", "UMASK": "027"},
        "log_lines": 1, "wplto_product_link_cycles": 1,
        "completion_product_rebuilds": 0,
        "artifact_set_sha256": "a" * 64,
        "product_build_id": "12345678", "profile_build_id": "90abcdef",
        "manifest_sha256": "b" * 64,
        "public_source_manifest_sha256": "c" * 64,
        "public_source_tree_sha256": "d" * 64,
    }
    value = {
        "format": "lisp65-c2-v190-public-clean-build-receipt-v1",
        "version": 1, "status": "passed", "measured_on": "2026-08-27",
        "source_commit": "e" * 40,
        "source_repository_role": "curated-public-source-candidate",
        "entry_point": "make workbench-product-v190",
        "private_evidence_inputs": 0,
        "public_source_manifest_sha256": "c" * 64,
        "public_source_tree_sha256": "d" * 64,
        "builds": [build, deepcopy(build)],
        "selected_variant": "v1.9-native-capture-client-native-prompt-editor",
        "artifact_count": 19, "artifact_set_sha256": "a" * 64,
        "product_build_id": "12345678", "profile_build_id": "90abcdef",
        "artifacts": rows, "mutations": deepcopy(MUTATION_LEDGER),
        "result": "two-varied-fresh-public-clones-reproduce-v1.9-role-set",
        "claim_limit": "selftest",
    }
    value["builds"][1]["id"] = "b"
    value["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2",
        "TZ": "B", "UMASK": "077"}
    require(mutation_proof(value) == MUTATION_LEDGER,
            "v1.9 clean-build selftest mutation proof drift")
    validate_receipt(value)
    print("c2-v190-public-clean-build: SELFTEST PASS mutations=6 roles=19")


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
            print("c2-v190-public-clean-build: LOCAL PASS "
                  f"roles={len(value['artifacts'])} "
                  f"set={value['artifact_set_sha256']}")
        elif args.action == "qualify":
            output = args.output if args.output.is_absolute() \
                else ROOT / args.output
            value = qualify(args.source_repository, args.source_commit,
                            output, args.llvm_mos_root)
            print("c2-v190-public-clean-build: QUALIFIED "
                  f"builds=2 roles={value['artifact_count']} "
                  f"set={value['artifact_set_sha256']} receipt={output}")
        else:
            receipt = args.receipt if args.receipt.is_absolute() \
                else ROOT / args.receipt
            value = load(receipt, "v1.9 public clean-build receipt")
            validate_receipt(value)
            print("c2-v190-public-clean-build: RECEIPT PASS "
                  f"builds=2 roles={value['artifact_count']} "
                  f"set={value['artifact_set_sha256']}")
        return 0
    except (CleanBuildError, OSError, ValueError, KeyError,
            subprocess.SubprocessError, json.JSONDecodeError) as error:
        print("c2-v190-public-clean-build: FIRST RED: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
