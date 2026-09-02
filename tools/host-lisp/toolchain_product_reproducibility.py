#!/usr/bin/env python3
"""Prove that a manifest-fetched toolchain reproduces the sealed product set."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable
from zoneinfo import ZoneInfo

import toolchain_external


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools" / "host-lisp" / "toolchain_product_reproducibility.py"
MANIFEST = ROOT / "config" / "toolchain-manifest.json"
DEFAULT_RECEIPT = (
    ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence" / "post-release"
    / "toolchain-externalization-receipt.json"
)
FORMAT = "lisp65-toolchain-product-reproduction-v1"
BUILD_COMMANDS = (
    ("make", "-s", "workbench-overlay-stack-guard", "v2-workbench-library-composition-check"),
    (
        "python3", "tools/host-lisp/toolchain_product_reproducibility.py", "materialize",
    ),
)
SEALED_PLANNING_RECEIPT_SHA256 = "07c102f3e91a7e17fa6cce21ff7007838ef8877b7d94d9b6b3ef14c4a4dc47ec"
AXES = (
    {
        "id": "fresh-clone-seed-101-utc-2003",
        "PYTHONHASHSEED": "101",
        "SOURCE_DATE_EPOCH": "1041379200",
        "TZ": "UTC",
    },
    {
        "id": "fresh-clone-seed-8675309-kiritimati-2033",
        "PYTHONHASHSEED": "8675309",
        "SOURCE_DATE_EPOCH": "1988150400",
        "TZ": "Pacific/Kiritimati",
    },
)


class ReproError(RuntimeError):
    pass


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


def lower_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReproError(f"{label} is not a lowercase SHA-256")
    return value


def run(argv: tuple[str, ...] | list[str], *, cwd: Path, env: dict[str, str], label: str) -> str:
    result = subprocess.run(
        argv, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-120:])
        raise ReproError(f"{label} failed ({result.returncode}):\n{tail}")
    return result.stdout


def full_commit(value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    commit = result.stdout.strip() if result.returncode == 0 else ""
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ReproError(f"invalid source commit: {value!r}")
    return commit


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReproError(f"{label} must be an object")
    return value


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def verify_external_toolchain(tool_root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for name, package in manifest["packages"].items():
        verified = toolchain_external.verify_package(name, package, tool_root)
        results.append({
            "package": verified["package"],
            "status": verified["status"],
            "tree": verified["tree"],
        })
    return results


def materialize_product() -> None:
    """Build R3 product bytes without revalidating a sealed receipt against live paths.

    The historical product builder predates the snapshot doctrine and asks its sealed
    post-capture capacity receipt to re-open a mutable planning archive.  1.1-K binds
    that receipt by its frozen SHA instead, while retaining every value-level check in
    the product builder and independently comparing all output bytes with the release
    product-set identity.
    """
    import r3_product_block

    sealed = r3_product_block.PLANNING_CAPACITY_RECEIPT
    if sha(sealed) != SEALED_PLANNING_RECEIPT_SHA256:
        raise ReproError("sealed post-capture planning receipt identity drift")

    def snapshot_bound_validate(_receipt: dict[str, Any]) -> None:
        if sha(sealed) != SEALED_PLANNING_RECEIPT_SHA256:
            raise ReproError("sealed post-capture planning receipt changed during materialization")

    r3_product_block.PLANNING_CAPACITY.validate = snapshot_bound_validate
    receipt = r3_product_block.build_product()
    if receipt.get("status") != "product-implemented-g3-not-run":
        raise ReproError("product materializer claim drift")
    receipt_path = r3_product_block.BUILD / "product-block-receipt.json"
    receipt_path.write_bytes(canonical(receipt))
    print(
        "toolchain-product-reproducibility: MATERIALIZED "
        f"set={receipt['product_identity']['artifact_set_sha256']}"
    )


def install_tool_links(checkout: Path, tool_root: Path) -> None:
    for name in ("llvm-mos", "m65tools"):
        source = tool_root / name
        if not source.is_dir():
            raise ReproError(f"external tool directory missing: {name}")
        target = checkout / "tools" / name
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        target.symlink_to(source.resolve(), target_is_directory=True)


def build_one(
    parent: Path, commit: str, axis: dict[str, str], tool_root: Path,
    manifest_sha256: str, expected_set: str,
) -> dict[str, Any]:
    checkout = parent / axis["id"]
    clone_env = os.environ.copy()
    clone_env["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(
        ["git", "clone", "--no-local", "--no-checkout", str(ROOT), str(checkout)],
        cwd=parent, env=clone_env, label=f"clone {axis['id']}",
    )
    run(
        ["git", "checkout", "--detach", commit], cwd=checkout, env=clone_env,
        label=f"checkout {axis['id']}",
    )
    clone_manifest = checkout / "config" / "toolchain-manifest.json"
    if sha(clone_manifest) != manifest_sha256:
        raise ReproError(f"toolchain manifest drift in {axis['id']}")
    install_tool_links(checkout, tool_root)

    environment = os.environ.copy()
    environment.update({key: axis[key] for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ")})
    environment["LLVM_MOS_ROOT"] = str((tool_root / "llvm-mos").resolve())
    environment["M65TOOLS_ROOT"] = str((tool_root / "m65tools").resolve())
    outputs = []
    for index, command in enumerate(BUILD_COMMANDS):
        outputs.append(
            run(command, cwd=checkout, env=environment, label=f"build {axis['id']} step {index + 1}")
        )

    manifest_path = checkout / "build" / "r3" / "product" / "candidate-manifest.json"
    receipt_path = checkout / "build" / "r3" / "product" / "product-block-receipt.json"
    composition_path = checkout / "build" / "bytecode" / "dialect-v2" / "workbench-library-composition-budget.json"
    product_manifest = load(manifest_path, "fresh candidate manifest")
    product_receipt = load(receipt_path, "fresh product receipt")
    composition = load(composition_path, "fresh composition report")
    rows = product_manifest.get("artifacts")
    if not isinstance(rows, list) or len(rows) != 13:
        raise ReproError("fresh candidate manifest must enumerate 13 product artifacts")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"role", "name", "path", "bytes", "sha256"}:
            raise ReproError(f"fresh artifact {index} schema drift")
        path = checkout / row["path"]
        if (
            path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"]
            or sha(path) != row["sha256"]
        ):
            raise ReproError(f"fresh artifact binding drift: {row['role']}")
        normalized.append(dict(row))
    observed_set = artifact_set_sha(normalized)
    if observed_set != expected_set:
        raise ReproError(f"sealed product identity drift: expected {expected_set}, got {observed_set}")
    if (
        product_manifest.get("artifact_set_sha256") != observed_set
        or product_receipt.get("product_identity", {}).get("artifact_set_sha256") != observed_set
    ):
        raise ReproError("fresh product manifest/receipt identity drift")
    epoch = int(axis["SOURCE_DATE_EPOCH"])
    return {
        "id": axis["id"],
        "clone": "fresh-no-local-detached-lfs-smudge-disabled",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": axis["PYTHONHASHSEED"],
            "SOURCE_DATE_EPOCH": axis["SOURCE_DATE_EPOCH"],
            "TZ": axis["TZ"],
            "calendar_date": datetime.fromtimestamp(epoch, ZoneInfo(axis["TZ"])).date().isoformat(),
        },
        "artifact_set_sha256": observed_set,
        "product_build_id": product_manifest.get("product_build_id"),
        "candidate_manifest_sha256": sha(manifest_path),
        "product_receipt_sha256": sha(receipt_path),
        "composition": {
            "ext_headroom_bytes": composition.get("ext_code", {}).get("post_headroom"),
            "symbols_free": composition.get("symbols", {}).get("headroom"),
            "namepool_free_bytes": composition.get("namepool", {}).get("headroom"),
            "directory_free_entries": composition.get("directory", {}).get("post_align_headroom"),
        },
        "artifacts": normalized,
        "log_lines": sum(len(output.splitlines()) for output in outputs),
    }


def build_receipt(source_commit: str, measured_on: str, tool_root: Path) -> dict[str, Any]:
    commit = full_commit(source_commit)
    manifest = load(MANIFEST, "toolchain manifest")
    expected_set = lower_sha(
        manifest.get("product_baseline", {}).get("product_set_sha256"),
        "product_baseline.product_set_sha256",
    )
    verification = verify_external_toolchain(tool_root, manifest)
    manifest_sha256 = sha(MANIFEST)
    with tempfile.TemporaryDirectory(prefix="lisp65-toolchain-product-repro-") as raw:
        builds = [
            build_one(Path(raw), commit, axis, tool_root, manifest_sha256, expected_set)
            for axis in AXES
        ]
    first, second = builds
    for key in (
        "artifact_set_sha256", "product_build_id", "candidate_manifest_sha256",
        "product_receipt_sha256", "composition", "artifacts",
    ):
        if first[key] != second[key]:
            raise ReproError(f"varied fresh-clone product builds diverged: {key}")
    archive_rows = []
    for name, package in manifest["packages"].items():
        archive = package["exact_archive"]
        archive_rows.append({
            "package": name,
            "name": archive["name"],
            "bytes": archive["bytes"],
            "sha256": archive["sha256"],
            "installed_tree_sha256": package["installed_tree"]["sha256"],
        })
    return {
        "format": FORMAT,
        "version": 1,
        "id": "v1.1-k-external-toolchain-product-reproduction",
        "status": "passed",
        "measured_on": measured_on,
        "source_commit": commit,
        "generator": {
            "path": GENERATOR.relative_to(ROOT).as_posix(),
            "bytes": GENERATOR.stat().st_size,
            "sha256": sha(GENERATOR),
        },
        "toolchain_manifest": {
            "path": MANIFEST.relative_to(ROOT).as_posix(),
            "bytes": MANIFEST.stat().st_size,
            "sha256": manifest_sha256,
        },
        "external_toolchain": {
            "verification": verification,
            "archives": archive_rows,
        },
        "variation_axes": [
            "fresh-clone", "manifest-fetched-external-tool-root", "PYTHONHASHSEED",
            "SOURCE_DATE_EPOCH", "timezone-and-calendar-date",
        ],
        "builds": [
            {key: build[key] for key in (
                "id", "clone", "commands", "environment", "artifact_set_sha256",
                "product_build_id", "candidate_manifest_sha256", "product_receipt_sha256",
                "composition",
            )}
            for build in builds
        ],
        "artifact_set_sha256": first["artifact_set_sha256"],
        "product_build_id": first["product_build_id"],
        "candidate_manifest_sha256": first["candidate_manifest_sha256"],
        "product_receipt_sha256": first["product_receipt_sha256"],
        "composition": first["composition"],
        "product_artifacts": first["artifacts"],
        "result": "manifest-fetched-toolchain-reproduced-13-of-13-sealed-product-artifacts",
        "historical_snapshot_adapter": {
            "receipt": "tests/bytecode/dialect-v2/evidence/r3/post-capture-planning-capacity-probe-receipt.json",
            "sha256": SEALED_PLANNING_RECEIPT_SHA256,
            "reason": "sealed-receipt-byte-binding-replaces-pre-snapshot-live-archive-revalidation",
            "product_identity_still_checked_independently": True,
        },
        "claims": {
            "product_sha_changed": False,
            "hardware_receipts_affected": False,
            "toolchain_upgrade": False,
        },
    }


def validate(receipt: dict[str, Any]) -> None:
    required = {
        "format", "version", "id", "status", "measured_on", "source_commit", "generator",
        "toolchain_manifest", "external_toolchain", "variation_axes", "builds",
        "artifact_set_sha256", "product_build_id", "candidate_manifest_sha256",
        "product_receipt_sha256", "composition", "product_artifacts", "result",
        "historical_snapshot_adapter", "claims",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise ReproError("toolchain reproduction receipt schema drift")
    if (
        receipt["format"] != FORMAT or receipt["version"] != 1
        or receipt["id"] != "v1.1-k-external-toolchain-product-reproduction"
        or receipt["status"] != "passed"
        or receipt["result"] != "manifest-fetched-toolchain-reproduced-13-of-13-sealed-product-artifacts"
        or receipt["claims"] != {
            "product_sha_changed": False,
            "hardware_receipts_affected": False,
            "toolchain_upgrade": False,
        }
    ):
        raise ReproError("toolchain reproduction identity/result drift")
    for binding_name, path in (("generator", GENERATOR), ("toolchain_manifest", MANIFEST)):
        binding = receipt[binding_name]
        if not isinstance(binding, dict) or set(binding) != {"path", "bytes", "sha256"}:
            raise ReproError(f"{binding_name} binding schema drift")
        lower_sha(binding["sha256"], f"{binding_name}.sha256")
        if type(binding["bytes"]) is not int or binding["bytes"] <= 0:
            raise ReproError(f"{binding_name} size drift")
        if binding["path"] != path.relative_to(ROOT).as_posix():
            raise ReproError(f"{binding_name} path drift")
    artifact_set = lower_sha(receipt["artifact_set_sha256"], "artifact_set_sha256")
    lower_sha(receipt["candidate_manifest_sha256"], "candidate_manifest_sha256")
    lower_sha(receipt["product_receipt_sha256"], "product_receipt_sha256")
    external = receipt["external_toolchain"]
    if not isinstance(external, dict) or set(external) != {"verification", "archives"}:
        raise ReproError("external toolchain evidence drift")
    if len(external["verification"]) != 2 or len(external["archives"]) != 2:
        raise ReproError("external toolchain package count drift")
    for row in external["verification"]:
        if row.get("status") != "exact-binary-match":
            raise ReproError("external toolchain was not an exact binary match")
    for index, row in enumerate(external["archives"]):
        if set(row) != {"package", "name", "bytes", "sha256", "installed_tree_sha256"}:
            raise ReproError(f"archive row {index} schema drift")
        lower_sha(row["sha256"], f"archives[{index}].sha256")
        lower_sha(row["installed_tree_sha256"], f"archives[{index}].installed_tree_sha256")
    if receipt["variation_axes"] != [
        "fresh-clone", "manifest-fetched-external-tool-root", "PYTHONHASHSEED",
        "SOURCE_DATE_EPOCH", "timezone-and-calendar-date",
    ]:
        raise ReproError("variation axes drift")
    if receipt["historical_snapshot_adapter"] != {
        "receipt": "tests/bytecode/dialect-v2/evidence/r3/post-capture-planning-capacity-probe-receipt.json",
        "sha256": SEALED_PLANNING_RECEIPT_SHA256,
        "reason": "sealed-receipt-byte-binding-replaces-pre-snapshot-live-archive-revalidation",
        "product_identity_still_checked_independently": True,
    }:
        raise ReproError("historical snapshot adapter drift")
    rows = receipt["product_artifacts"]
    if not isinstance(rows, list) or len(rows) != 13 or artifact_set_sha(rows) != artifact_set:
        raise ReproError("13-artifact product identity drift")
    builds = receipt["builds"]
    if not isinstance(builds, list) or len(builds) != 2:
        raise ReproError("exactly two fresh builds are required")
    environments = []
    for index, build in enumerate(builds):
        if build.get("clone") != "fresh-no-local-detached-lfs-smudge-disabled":
            raise ReproError(f"build {index} isolation drift")
        for key in (
            "artifact_set_sha256", "product_build_id", "candidate_manifest_sha256",
            "product_receipt_sha256", "composition",
        ):
            if build.get(key) != receipt[key]:
                raise ReproError(f"build {index} result drift: {key}")
        environments.append(build.get("environment", {}))
    for key in ("PYTHONHASHSEED", "SOURCE_DATE_EPOCH", "TZ", "calendar_date"):
        if environments[0].get(key) == environments[1].get(key):
            raise ReproError(f"reproduction axis did not vary: {key}")


def selftest() -> None:
    artifact = {
        "role": "workbench-prg", "name": "lisp65.prg", "path": "build/lisp65.prg",
        "bytes": 1, "sha256": "1" * 64,
    }
    composition = {
        "ext_headroom_bytes": 16385, "symbols_free": 120,
        "namepool_free_bytes": 2160, "directory_free_entries": 32,
    }
    build = {
        "id": "a", "clone": "fresh-no-local-detached-lfs-smudge-disabled",
        "commands": [" ".join(command) for command in BUILD_COMMANDS],
        "environment": {
            "PYTHONHASHSEED": "1", "SOURCE_DATE_EPOCH": "1", "TZ": "A",
            "calendar_date": "2001-01-01",
        },
        "artifact_set_sha256": artifact_set_sha([artifact]), "product_build_id": "12345678",
        "candidate_manifest_sha256": "2" * 64, "product_receipt_sha256": "3" * 64,
        "composition": composition,
    }
    fixture = {
        "format": FORMAT, "version": 1,
        "id": "v1.1-k-external-toolchain-product-reproduction", "status": "passed",
        "measured_on": "2001-01-01", "source_commit": "0" * 40,
        "generator": {
            "path": GENERATOR.relative_to(ROOT).as_posix(), "bytes": 1, "sha256": "4" * 64,
        },
        "toolchain_manifest": {
            "path": MANIFEST.relative_to(ROOT).as_posix(), "bytes": 1, "sha256": "5" * 64,
        },
        "external_toolchain": {
            "verification": [
                {"package": "llvm_mos", "status": "exact-binary-match"},
                {"package": "mega65_tools", "status": "exact-binary-match"},
            ],
            "archives": [
                {"package": "llvm_mos", "name": "a", "bytes": 1, "sha256": "6" * 64, "installed_tree_sha256": "7" * 64},
                {"package": "mega65_tools", "name": "b", "bytes": 1, "sha256": "8" * 64, "installed_tree_sha256": "9" * 64},
            ],
        },
        "variation_axes": [
            "fresh-clone", "manifest-fetched-external-tool-root", "PYTHONHASHSEED",
            "SOURCE_DATE_EPOCH", "timezone-and-calendar-date",
        ],
        "builds": [build, deepcopy(build)],
        "artifact_set_sha256": artifact_set_sha([artifact]), "product_build_id": "12345678",
        "candidate_manifest_sha256": "2" * 64, "product_receipt_sha256": "3" * 64,
        "composition": composition, "product_artifacts": [artifact],
        "result": "manifest-fetched-toolchain-reproduced-13-of-13-sealed-product-artifacts",
        "historical_snapshot_adapter": {
            "receipt": "tests/bytecode/dialect-v2/evidence/r3/post-capture-planning-capacity-probe-receipt.json",
            "sha256": SEALED_PLANNING_RECEIPT_SHA256,
            "reason": "sealed-receipt-byte-binding-replaces-pre-snapshot-live-archive-revalidation",
            "product_identity_still_checked_independently": True,
        },
        "claims": {
            "product_sha_changed": False, "hardware_receipts_affected": False,
            "toolchain_upgrade": False,
        },
    }
    fixture["product_artifacts"] = [deepcopy(artifact) for _ in range(13)]
    for index, row in enumerate(fixture["product_artifacts"]):
        row["role"] = f"role-{index}"
        row["name"] = f"artifact-{index}"
        row["sha256"] = f"{index + 1:064x}"
    fixture["artifact_set_sha256"] = artifact_set_sha(fixture["product_artifacts"])
    for build_row in fixture["builds"]:
        build_row["artifact_set_sha256"] = fixture["artifact_set_sha256"]
    fixture["builds"][1]["id"] = "b"
    fixture["builds"][1]["environment"] = {
        "PYTHONHASHSEED": "2", "SOURCE_DATE_EPOCH": "2", "TZ": "B",
        "calendar_date": "2031-01-01",
    }
    validate(fixture)
    survivors = []
    mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        ("status", lambda x: x.update(status="failed")),
        ("same-seed", lambda x: x["builds"][1]["environment"].update(PYTHONHASHSEED="1")),
        ("artifact-set", lambda x: x.update(artifact_set_sha256="f" * 64)),
        ("one-build", lambda x: x["builds"].pop()),
        ("claim", lambda x: x["claims"].update(product_sha_changed=True)),
    )
    for name, mutate in mutations:
        changed = deepcopy(fixture)
        mutate(changed)
        try:
            validate(changed)
        except ReproError:
            continue
        survivors.append(name)
    if survivors:
        raise ReproError(f"selftest accepted mutations: {survivors}")
    print(f"toolchain-product-reproducibility: SELFTEST PASS mutations={len(mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--source-commit", required=True)
    generate.add_argument("--measured-on", required=True)
    generate.add_argument("--tool-root", type=Path, required=True)
    generate.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    check = sub.add_parser("check")
    check.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    sub.add_parser("selftest")
    sub.add_parser("materialize")
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            selftest()
            return 0
        if args.command == "materialize":
            materialize_product()
            return 0
        receipt_path = args.output if args.command == "generate" else args.receipt
        if not receipt_path.is_absolute():
            receipt_path = ROOT / receipt_path
        if args.command == "generate":
            receipt = build_receipt(args.source_commit, args.measured_on, args.tool_root.resolve())
            validate(receipt)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_bytes(canonical(receipt))
            print(
                "toolchain-product-reproducibility: WROTE builds=2 artifacts=13 "
                f"set={receipt['artifact_set_sha256']} output={receipt_path.relative_to(ROOT)}"
            )
        else:
            receipt = load(receipt_path, "toolchain product reproduction receipt")
            validate(receipt)
            for binding_name, path in (("generator", GENERATOR), ("toolchain_manifest", MANIFEST)):
                binding = receipt[binding_name]
                if path.stat().st_size != binding["bytes"] or sha(path) != binding["sha256"]:
                    raise ReproError(f"live {binding_name} binding drift")
            print(
                "toolchain-product-reproducibility: PASS builds=2 artifacts=13 "
                f"set={receipt['artifact_set_sha256']}"
            )
        return 0
    except (
        ReproError, toolchain_external.ToolchainError, OSError, ValueError, TypeError,
        KeyError, json.JSONDecodeError,
    ) as exc:
        print(f"toolchain-product-reproducibility: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
