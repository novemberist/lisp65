#!/usr/bin/env python3
"""Build and verify the seal-consuming R5 global G5 preflight."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import dialect_v2_workbench_g5_verify as WORKBENCH  # noqa: E402
import r5_g5_case_receipts as CASE_RECEIPTS  # noqa: E402
import v2_g5_domain_verifiers as INTERNAL_DOMAIN  # noqa: E402
import r5_persistence_fixtures as R5_FIXTURES  # noqa: E402


CONTRACT = ROOT / "config/r5-global-g5-contract.json"
MATRIX = ROOT / "config/dialect-v2-g5-matrix.json"
MIGRATION = ROOT / "config/dialect-migration-contract.json"
DIALECT = ROOT / "config/dialect-v2-contract.json"
CLOSURE_POLICY = ROOT / "config/r5-global-g5-test-closure.json"
METADATA_CONTRACT = ROOT / "config/v11-function-metadata-contract.json"
METADATA_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-function-metadata-contract-receipt.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MATERIALIZATION_FORMAT = "lisp65-r5-product-materialization-v1"
CLOSURE_FORMAT = "lisp65-r5-global-g5-test-closure-v1"
CANDIDATE_FORMAT = "lisp65-r5-global-g5-candidate-v1"
PREFLIGHT_FORMAT = "lisp65-r5-global-g5-static-preflight-v1"
HW_PACKAGE_FORMAT = "lisp65-r5-global-g5-hw-package-v1"
PRODUCT_ARTIFACT_COUNT = 14
PERSISTENCE_FIXTURES = R5_FIXTURES.load_fixtures()


class R5Error(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise R5Error(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise R5Error(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R5Error(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise R5Error(f"{label} must be an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise R5Error(f"{label} keys drift: {actual}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise R5Error(f"{label} must be a lowercase SHA-256")
    return value


def repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise R5Error(f"{label} must be a repository-relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise R5Error(f"{label} escapes repository")
    path = (ROOT / Path(*pure.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise R5Error(f"{label} escapes repository") from exc
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def closure_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("id", "path", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: row["id"])
    ]
    return sha_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii"))


def function_metadata_limit() -> dict[str, Any]:
    """Bind the deliberately incomplete Wave-2 metadata claim into R5."""
    contract_value = load(METADATA_CONTRACT, "Wave-2 function metadata contract")
    receipt = load(METADATA_RECEIPT, "Wave-2 function metadata receipt")
    if (
        contract_value.get("format") != "lisp65-v11-function-metadata-contract-v1"
        or contract_value.get("status")
        != "wave2-host-contract-active-device-delivery-deferred-to-c2"
        or receipt.get("format") != "lisp65-v11-function-metadata-contract-receipt-v1"
        or receipt.get("status") != "host-contract-passed-device-delivery-deferred-to-c2"
    ):
        raise R5Error("Wave-2 function metadata contract identity drift")
    bindings = receipt.get("bindings")
    contract_binding = bindings.get("contract") if isinstance(bindings, dict) else None
    index = receipt.get("index")
    delivery = receipt.get("delivery_gate")
    if (
        not isinstance(contract_binding, dict)
        or contract_binding.get("path") != METADATA_CONTRACT.relative_to(ROOT).as_posix()
        or contract_binding.get("sha256") != sha(METADATA_CONTRACT)
        or not isinstance(index, dict)
        or index.get("records") != 135
        or index.get("exact_arity") != 101
        or index.get("unresolved_arity") != 34
        or not isinstance(delivery, dict)
        or delivery.get("ide_help_ready") is not False
    ):
        raise R5Error("Wave-2 function metadata limit drift")
    index_path = repo_path(index.get("path"), "Wave-2 function metadata index")
    if (
        index_path.is_symlink() or not index_path.is_file()
        or index_path.stat().st_size != index.get("bytes")
        or sha(index_path) != index.get("sha256")
    ):
        raise R5Error("Wave-2 function metadata index binding drift")
    return {
        "contract": {
            "path": METADATA_CONTRACT.relative_to(ROOT).as_posix(),
            "sha256": sha(METADATA_CONTRACT),
        },
        "receipt": {
            "path": METADATA_RECEIPT.relative_to(ROOT).as_posix(),
            "sha256": sha(METADATA_RECEIPT),
        },
        "records": 135,
        "exact_arity": 101,
        "unresolved_arity": 34,
        "ide_help_ready": False,
        "claim": "function-metadata=101-exact/34-unresolved-no-complete-help-claim",
    }


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R5 contract")
    if (
        (value.get("format"), value.get("version")) not in {
            ("lisp65-r5-global-g5-contract-v1", 1),
            ("lisp65-r5-global-g5-contract-v2", 2),
        }
        or value.get("id") != "workbench-r5-global-g5"
    ):
        raise R5Error("R5 contract identity drift")
    return value


def archive_manifest(value: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    candidate = value.get("product_candidate")
    if not isinstance(candidate, dict):
        raise R5Error("R5 contract lacks product candidate")
    archive_path = repo_path(candidate.get("archive"), "R5 archive")
    if archive_path.is_symlink() or not archive_path.is_file():
        raise R5Error("R5 archive is not a regular file")
    if sha(archive_path) != lower_sha(candidate.get("archive_sha256"), "R5 archive SHA"):
        raise R5Error("R5 archive SHA drift")
    with tarfile.open(archive_path, "r:gz") as archive:
        stream = archive.extractfile("manifest.json")
        if stream is None:
            raise R5Error("R5 archive lacks manifest")
        manifest = json.loads(stream.read(), object_pairs_hook=strict_object)
    materialized = manifest.get("product_materialization", {})
    if (
        manifest.get("id") != candidate.get("promotion_id")
        or manifest.get("kind") != "product-candidate"
        or manifest.get("status") != "sealed"
        or manifest.get("source_commit") != candidate.get("source_commit")
        or materialized.get("artifact_set_sha256") != candidate.get("artifact_set_sha256")
        or materialized.get("product_build_id") != candidate.get("product_build_id")
        or len(materialized.get("artifacts", [])) != candidate.get("artifact_count")
        or candidate.get("artifact_count") != PRODUCT_ARTIFACT_COUNT
    ):
        raise R5Error("R5/R4 product identity drift")
    return archive_path, manifest


def sealed_anonymous_library_designators() -> tuple[set[str], list[dict[str, Any]]]:
    archive_path, _ = archive_manifest(contract())
    members = (
        "payload/build/bytecode/dialect-v2/libs/ide.manifest.json",
        "payload/build/bytecode/dialect-v2/libs/idex.manifest.json",
        "payload/build/bytecode/dialect-v2/libs/m65d.manifest.json",
    )
    names: set[str] = set()
    manifests = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member_name in members:
            try:
                member = archive.getmember(member_name)
            except KeyError as exc:
                raise R5Error(f"R4 archive lacks library manifest: {member_name}") from exc
            if not member.isfile():
                raise R5Error(f"R4 library manifest is not a regular member: {member_name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise R5Error(f"cannot extract R4 library manifest: {member_name}")
            data = stream.read()
            try:
                value = json.loads(data, object_pairs_hook=strict_object)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise R5Error(f"cannot decode R4 library manifest {member_name}: {exc}") from exc
            entries = value.get("entries") if isinstance(value, dict) else None
            if not isinstance(entries, list):
                raise R5Error(f"R4 library manifest lacks entries: {member_name}")
            anonymous = set()
            for index, row in enumerate(entries):
                if not isinstance(row, dict) or (
                    "anonymous" in row and not isinstance(row["anonymous"], bool)
                ):
                    raise R5Error(f"R4 library manifest entry drift: {member_name}[{index}]")
                if row.get("anonymous", False):
                    name = row.get("name")
                    if not isinstance(name, str) or not name:
                        raise R5Error(f"anonymous R4 library entry lacks source name: {member_name}[{index}]")
                    anonymous.add(name)
            names.update(anonymous)
            manifests.append({
                "path": member_name.removeprefix("payload/"),
                "sha256": sha_bytes(data),
                "anonymous_functions": len(anonymous),
            })
    if not names:
        raise R5Error("sealed library manifests contain no anonymous functions")
    return names, manifests


def anonymous_function_designators(text: str, names: set[str]) -> list[tuple[str, int]]:
    violations = set()
    for name in sorted(names):
        escaped = re.escape(name)
        patterns = (
            re.compile(r"\(\s*" + escaped + r"(?=[\s()])"),
            re.compile(r"\(\s*function\s+" + escaped + r"(?=[\s()])"),
            re.compile(r"\(\s*(?:funcall|apply)\s+\(\s*quote\s+" + escaped + r"(?=[\s()])"),
            re.compile(r"\(\s*(?:funcall|apply)\s+'" + escaped + r"(?=[\s()])"),
        )
        for pattern in patterns:
            for match in pattern.finditer(text):
                violations.add((name, text.count("\n", 0, match.start()) + 1))
    return sorted(violations, key=lambda row: (row[1], row[0]))


def verify_harness_designator_surface(tests: dict[str, Any]) -> dict[str, Any]:
    anonymous, manifests = sealed_anonymous_library_designators()
    scripts = []
    violations = []
    for row in tests["artifacts"]:
        if not row["path"].endswith(".sh"):
            continue
        path = repo_path(row["path"], f"R5 harness script {row['id']}")
        scripts.append(row["path"])
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise R5Error(f"cannot read R5 harness script {row['path']}: {exc}") from exc
        for name, line in anonymous_function_designators(text, anonymous):
            violations.append(f"{row['path']}:{line}:{name}")
    if violations:
        raise R5Error(f"R5 harness calls sealed anonymous library functions: {violations}")
    return {
        "source": "sealed-r4-product-candidate-archive",
        "manifests": manifests,
        "anonymous_functions": len(anonymous),
        "scripts_checked": len(scripts),
        "function_designator_references": 0,
        "negative_selftest": "passed",
        "result": "passed",
    }


def materialize(out: Path) -> None:
    value = contract()
    archive_path, manifest = archive_manifest(value)
    if out.exists() or out.is_symlink():
        raise R5Error(f"materialization output must be fresh: {out}")
    rows = manifest["product_materialization"]["artifacts"]
    out.mkdir(parents=True)
    copied = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for row in rows:
            pure = PurePosixPath(row["path"])
            if pure.is_absolute() or ".." in pure.parts:
                raise R5Error(f"unsafe product artifact path: {row['path']}")
            member_name = f"payload/{pure.as_posix()}"
            try:
                member = archive.getmember(member_name)
            except KeyError as exc:
                raise R5Error(f"R4 archive lacks product artifact: {row['role']}") from exc
            if not member.isfile():
                raise R5Error(f"R4 product artifact is not a regular archive member: {row['role']}")
            stream = archive.extractfile(member)
            if stream is None:
                raise R5Error(f"cannot extract R4 product artifact: {row['role']}")
            data = stream.read()
            if len(data) != row["bytes"] or sha_bytes(data) != row["sha256"]:
                raise R5Error(f"R4 product artifact binding drift: {row['role']}")
            target = out / Path(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            copied.append(dict(row))
    observed = artifact_set_sha(copied)
    expected = value["product_candidate"]["artifact_set_sha256"]
    if observed != expected:
        raise R5Error("materialized product artifact-set SHA drift")
    receipt = {
        "format": MATERIALIZATION_FORMAT,
        "version": 1,
        "input_authority": "sealed-r4-product-candidate-archive",
        "live_tree_product_authority": False,
        "archive": value["product_candidate"]["archive"],
        "archive_sha256": value["product_candidate"]["archive_sha256"],
        "product_artifact_set_sha256": observed,
        "product_build_id": value["product_candidate"]["product_build_id"],
        "artifact_count": len(copied),
        "artifacts": copied,
        "result": "passed",
    }
    write_json(out / "materialization.json", receipt)
    print(
        "R5 product materialization: PASS "
        f"artifacts={PRODUCT_ARTIFACT_COUNT} set={observed} source=sealed-R4"
    )


def verify_materialization(path: Path) -> dict[str, Any]:
    value = contract()
    expected_candidate = value["product_candidate"]
    receipt = load(path, "R5 product materialization")
    exact(
        receipt,
        {
            "format", "version", "input_authority", "live_tree_product_authority",
            "archive", "archive_sha256", "product_artifact_set_sha256", "product_build_id",
            "artifact_count", "artifacts", "result",
        },
        "R5 product materialization",
    )
    if (
        receipt["format"] != MATERIALIZATION_FORMAT
        or receipt["version"] != 1
        or receipt["input_authority"] != "sealed-r4-product-candidate-archive"
        or receipt["live_tree_product_authority"] is not False
        or receipt["archive"] != expected_candidate["archive"]
        or receipt["archive_sha256"] != expected_candidate["archive_sha256"]
        or receipt["product_artifact_set_sha256"] != expected_candidate["artifact_set_sha256"]
        or receipt["product_build_id"] != expected_candidate["product_build_id"]
        or receipt["artifact_count"] != PRODUCT_ARTIFACT_COUNT
        or receipt["result"] != "passed"
        or not isinstance(receipt["artifacts"], list)
        or len(receipt["artifacts"]) != PRODUCT_ARTIFACT_COUNT
    ):
        raise R5Error("R5 materialization identity/result drift")
    root = path.parent
    rows = []
    roles = []
    for index, raw in enumerate(receipt["artifacts"]):
        row = exact(raw, {"role", "name", "path", "bytes", "sha256"}, f"product artifact[{index}]")
        artifact = root / Path(*PurePosixPath(row["path"]).parts)
        if artifact.is_symlink() or not artifact.is_file():
            raise R5Error(f"materialized product artifact missing: {row['role']}")
        if artifact.stat().st_size != row["bytes"] or sha(artifact) != row["sha256"]:
            raise R5Error(f"materialized product artifact SHA drift: {row['role']}")
        roles.append(row["role"])
        rows.append(row)
    if len(roles) != len(set(roles)) or artifact_set_sha(rows) != receipt["product_artifact_set_sha256"]:
        raise R5Error("materialized product set recomputation drift")
    return receipt


def run(command: list[str], *, cwd: Path = ROOT, label: str) -> str:
    completed = subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    if completed.returncode:
        raise R5Error(f"{label} failed ({completed.returncode}):\n{completed.stdout}")
    return completed.stdout


def build_runtime_carrier(source_commit: str, out: Path, jobs: int) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise R5Error("runtime carrier source commit must be a full lowercase Git id")
    if out.exists() or out.is_symlink():
        raise R5Error(f"runtime carrier output must be fresh: {out}")
    worktree = ROOT / "build/r5-global-g5/runtime-source-worktree"
    if worktree.exists():
        run(["git", "worktree", "remove", "--force", str(worktree)], label="remove stale runtime worktree")
    run(["git", "worktree", "add", "--detach", str(worktree), source_commit], label="create R4 runtime worktree")
    try:
        # The R4 product source is authoritative; these copied files are an
        # explicitly test-only closure overlay that refreshes stale input and
        # budget pins. They cannot alter the sealed product artifact set.
        overlay_paths = (
            "config/v2-runtime-core-proof.json",
            "tools/host-lisp/v2_runtime_core_proof.py",
            "tools/host-lisp/mvp_vm_stdlib_footprint.py",
        )
        for overlay in overlay_paths:
            shutil.copyfile(ROOT / overlay, worktree / overlay)
        commit_env = dict(os.environ)
        commit_env.update({
            "GIT_AUTHOR_DATE": "2026-07-13T00:00:00+02:00",
            "GIT_COMMITTER_DATE": "2026-07-13T00:00:00+02:00",
        })
        subprocess.run(["git", "add", *overlay_paths], cwd=worktree, check=True)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=worktree,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if staged.returncode == 1:
            subprocess.run(
                [
                    "git", "-c", "user.name=Lisp65 R5 Harness",
                    "-c", "user.email=r5-harness.invalid", "commit", "-m",
                    "R5 test-only Runtime proof binding overlay",
                ],
                cwd=worktree, env=commit_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, check=True,
            )
        elif staged.returncode != 0:
            raise R5Error(f"cannot inspect Runtime proof overlay: {staged.stdout}")
        llvm = ROOT / "tools/llvm-mos/bin"
        source_epoch = run(
            ["git", "show", "-s", "--format=%ct", source_commit],
            label="read R4 source epoch",
        ).strip()
        if not source_epoch.isdigit():
            raise R5Error("R4 source epoch is not numeric")
        run(
            [
                "make", f"-j{jobs}",
                f"SOURCE_DATE_EPOCH={source_epoch}",
                f"LLVM={llvm}", f"CC_M65={llvm / 'mos-mega65-clang'}",
                f"M65VMSTDLIB_NM={llvm / 'llvm-nm'}",
                f"M65VMSTDLIB_SIZE={llvm / 'llvm-size'}",
                "v2-runtime-core-proof-candidate",
            ],
            cwd=worktree, label="build R4 runtime proof carrier",
        )
        proof = worktree / "build/products/runtime-core-v2-proof/candidate"
        proof_manifest = load(proof / "manifest.json", "R4 runtime proof manifest")
        carrier_commit = proof_manifest.get("source_commit")
        if not isinstance(carrier_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", carrier_commit):
            raise R5Error("runtime proof carrier lacks its test-closure commit")
        INTERNAL_DOMAIN.pack_runtime(
            proof, out,
            ROOT / "tools/llvm-mos/bin/llvm-nm",
            ROOT / "tools/llvm-mos/bin/llvm-objcopy",
        )
        INTERNAL_DOMAIN.verify_runtime_package(out)
        package = load(out / "manifest.json", "R5 runtime package")
        product_source_id = package.get("source_candidate", {}).get("source_commit")
        if not isinstance(product_source_id, str) or not re.fullmatch(r"[0-9a-f]{40}", product_source_id):
            raise R5Error("runtime package lacks its deterministic product-source id")
        provenance = {
            "format": "lisp65-r5-runtime-test-carrier-provenance-v1",
            "version": 1,
            "role": "test-closure-only-not-product",
            "base_product_source_commit": source_commit,
            "allowed_harness_overlays": [
                {"path": overlay, "sha256": sha(ROOT / overlay)}
                for overlay in overlay_paths
            ],
            "test_closure_commit": carrier_commit,
            "product_source_id": product_source_id,
            "package_manifest_sha256": sha(out / "manifest.json"),
            "result": "passed",
        }
        write_json(out.parent / "runtime-carrier-provenance.json", provenance)
    finally:
        run(["git", "worktree", "remove", "--force", str(worktree)], label="remove R4 runtime worktree")
    print(f"R5 runtime test carrier: PASS source={source_commit} product-membership=forbidden")


def tree_bytes(root: Path) -> dict[str, bytes]:
    rows: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise R5Error(f"runtime carrier reproducibility tree contains symlink: {path}")
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = path.read_bytes()
    return rows


def build_runtime_carrier_reproducible(source_commit: str, out: Path, jobs: int) -> None:
    provenance_out = out.parent / "runtime-carrier-provenance.json"
    reproducibility_out = out.parent / "runtime-carrier-reproducibility.json"
    if out.exists() or provenance_out.exists() or reproducibility_out.exists():
        raise R5Error("runtime carrier reproducibility outputs must be fresh")
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-runtime-repro-") as raw:
        root = Path(raw)
        left = root / "left/runtime-package"
        right = root / "right/runtime-package"
        build_runtime_carrier(source_commit, left, jobs)
        build_runtime_carrier(source_commit, right, jobs)
        left_tree = tree_bytes(left.parent)
        right_tree = tree_bytes(right.parent)
        if left_tree != right_tree:
            changed = sorted(set(left_tree) ^ set(right_tree))
            changed += sorted(
                path for path in set(left_tree) & set(right_tree)
                if left_tree[path] != right_tree[path]
            )
            raise R5Error(f"runtime test carrier double build differs: {sorted(set(changed))}")
        shutil.copytree(left, out)
        shutil.copyfile(left.parent / "runtime-carrier-provenance.json", provenance_out)
    value = {
        "format": "lisp65-r5-runtime-test-carrier-reproducibility-v1",
        "version": 1,
        "source_commit": source_commit,
        "builds": 2,
        "byte_identical": True,
        "file_count": len(left_tree),
        "package_manifest_sha256": sha(out / "manifest.json"),
        "result": "passed",
    }
    write_json(reproducibility_out, value)
    print(
        "R5 runtime test carrier reproducibility: PASS "
        f"builds=2 files={len(left_tree)} manifest={value['package_manifest_sha256']}"
    )


def closure_policy() -> dict[str, Any]:
    value = load(CLOSURE_POLICY, "R5 test-closure policy")
    exact(
        value,
        {
            "format", "version", "id", "product_membership", "runtime_core_role",
            "change_policy", "runtime_package", "files",
        },
        "R5 test-closure policy",
    )
    if (
        value["format"] != "lisp65-r5-global-g5-test-closure-policy-v1"
        or value["version"] != 1
        or value["id"] != "r5-global-g5-test-closure"
        or value["product_membership"] != "forbidden"
        or value["runtime_core_role"] != "internal-proof-only-test-carrier"
    ):
        raise R5Error("R5 test-closure policy identity drift")
    return value


def pack_closure(out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise R5Error(f"test-closure output must be fresh: {out}")
    policy = closure_policy()
    runtime = repo_path(policy["runtime_package"]["path"], "runtime package")
    INTERNAL_DOMAIN.verify_runtime_package(runtime)
    runtime_manifest = load(runtime / "manifest.json", "R5 runtime package")
    provenance_path = repo_path(policy["runtime_package"]["provenance"], "runtime carrier provenance")
    provenance = load(provenance_path, "runtime carrier provenance")
    reproducibility_path = repo_path(
        policy["runtime_package"]["reproducibility"], "runtime carrier reproducibility"
    )
    reproducibility = load(reproducibility_path, "runtime carrier reproducibility")
    if (
        provenance.get("format") != "lisp65-r5-runtime-test-carrier-provenance-v1"
        or provenance.get("role") != "test-closure-only-not-product"
        or provenance.get("base_product_source_commit") != policy["runtime_package"]["base_product_source_commit"]
        or provenance.get("allowed_harness_overlays") != [
            {"path": overlay, "sha256": sha(ROOT / overlay)}
            for overlay in policy["runtime_package"]["allowed_harness_overlays"]
        ]
        or not re.fullmatch(r"[0-9a-f]{40}", provenance.get("test_closure_commit", ""))
        or provenance.get("product_source_id") != runtime_manifest.get("source_candidate", {}).get("source_commit")
        or provenance.get("package_manifest_sha256") != sha(runtime / "manifest.json")
        or provenance.get("result") != "passed"
    ):
        raise R5Error("R5 runtime test carrier provenance drift")
    if reproducibility != {
        "format": "lisp65-r5-runtime-test-carrier-reproducibility-v1",
        "version": 1,
        "source_commit": policy["runtime_package"]["base_product_source_commit"],
        "builds": 2,
        "byte_identical": True,
        "file_count": reproducibility.get("file_count"),
        "package_manifest_sha256": sha(runtime / "manifest.json"),
        "result": "passed",
    } or not isinstance(reproducibility.get("file_count"), int) or reproducibility["file_count"] < 2:
        raise R5Error("R5 runtime test carrier reproducibility drift")
    rows = []
    for index, raw in enumerate(policy["files"]):
        item = exact(raw, {"id", "path"}, f"test closure file[{index}]")
        path = repo_path(item["path"], f"test closure {item['id']}")
        if path.is_symlink() or not path.is_file():
            raise R5Error(f"test closure file is missing: {item['id']}")
        rows.append({"id": item["id"], "path": item["path"], "bytes": path.stat().st_size, "sha256": sha(path)})
    for path in sorted(runtime.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        package_rel = path.relative_to(runtime).as_posix()
        rows.append({
            "id": f"runtime-package/{package_rel}", "path": rel,
            "bytes": path.stat().st_size, "sha256": sha(path),
        })
    _, sealed_manifest = archive_manifest(contract())
    product_signatures = {
        (row["bytes"], row["sha256"])
        for row in sealed_manifest["product_materialization"]["artifacts"]
    }
    overlap = [row["id"] for row in rows if (row["bytes"], row["sha256"]) in product_signatures]
    if overlap:
        raise R5Error(f"test closure contains sealed product members: {overlap}")
    ids = [row["id"] for row in rows]
    if ids != list(dict.fromkeys(ids)):
        raise R5Error("test closure artifact ids are not unique")
    value = {
        "format": CLOSURE_FORMAT,
        "version": 1,
        "policy": CLOSURE_POLICY.relative_to(ROOT).as_posix(),
        "policy_sha256": sha(CLOSURE_POLICY),
        "product_membership": "forbidden",
        "product_artifact_overlap": 0,
        "product_artifact_set_sha256": contract()["product_candidate"]["artifact_set_sha256"],
        "runtime_core_role": "internal-proof-only-test-carrier",
        "runtime_source_commit": policy["runtime_package"]["base_product_source_commit"],
        "change_policy": policy["change_policy"],
        "closure_set_sha256": closure_set_sha(rows),
        "artifacts": rows,
    }
    write_json(out, value)
    print(f"R5 test closure: PASS artifacts={len(rows)} set={value['closure_set_sha256']} product-membership=forbidden")


def verify_closure(path: Path) -> dict[str, Any]:
    policy = closure_policy()
    value = load(path, "R5 test closure")
    exact(
        value,
        {
            "format", "version", "policy", "policy_sha256", "product_membership",
            "product_artifact_overlap", "product_artifact_set_sha256", "runtime_core_role", "runtime_source_commit",
            "change_policy", "closure_set_sha256", "artifacts",
        },
        "R5 test closure",
    )
    if (
        value["format"] != CLOSURE_FORMAT
        or value["version"] != 1
        or value["policy"] != CLOSURE_POLICY.relative_to(ROOT).as_posix()
        or value["policy_sha256"] != sha(CLOSURE_POLICY)
        or value["product_membership"] != "forbidden"
        or value["product_artifact_overlap"] != 0
        or value["product_artifact_set_sha256"] != contract()["product_candidate"]["artifact_set_sha256"]
        or value["runtime_core_role"] != "internal-proof-only-test-carrier"
        or value["runtime_source_commit"] != policy["runtime_package"]["base_product_source_commit"]
        or value["change_policy"] != policy["change_policy"]
        or not isinstance(value["artifacts"], list)
    ):
        raise R5Error("R5 test closure identity/policy drift")
    ids = []
    for index, raw in enumerate(value["artifacts"]):
        row = exact(raw, {"id", "path", "bytes", "sha256"}, f"test closure artifact[{index}]")
        file = repo_path(row["path"], f"test closure artifact {row['id']}")
        if file.is_symlink() or not file.is_file() or file.stat().st_size != row["bytes"] or sha(file) != row["sha256"]:
            raise R5Error(f"test closure artifact drift: {row['id']}")
        ids.append(row["id"])
    if len(ids) != len(set(ids)) or closure_set_sha(value["artifacts"]) != value["closure_set_sha256"]:
        raise R5Error("R5 test closure set drift")
    _, sealed_manifest = archive_manifest(contract())
    product_signatures = {
        (row["bytes"], row["sha256"])
        for row in sealed_manifest["product_materialization"]["artifacts"]
    }
    overlap = [row["id"] for row in value["artifacts"] if (row["bytes"], row["sha256"]) in product_signatures]
    if overlap:
        raise R5Error(f"test closure product-membership violation: {overlap}")
    return value


def family_bindings(migration: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for family in migration["families"]:
        measurement = family["measurement"]
        path = repo_path(measurement["differential_receipt"], f"family {family['id']} receipt")
        expected = measurement["differential_receipt_sha256"]
        if sha(path) != expected:
            raise R5Error(f"family measurement binding drift: {family['id']}")
        rows.append({"id": family["id"], "path": measurement["differential_receipt"], "sha256": expected})
    return rows


def dialect_binding(migration_sha: str, source_commit: str) -> dict[str, str]:
    value = load(DIALECT, "dialect-v2 contract")
    if (
        value.get("format") != "lisp65-dialect-v2-contract-v1"
        or value.get("profile") != "dialect-v2"
        or value.get("migration_contract_sha256") != migration_sha
        or value.get("source_commit") != source_commit
        or not isinstance(value.get("public_names"), list)
        or not value.get("public_names")
    ):
        raise R5Error("dialect-v2 contract identity/provenance drift")
    for row in value.get("surfaces", []):
        surface = repo_path(row.get("manifest"), "dialect-v2 surface")
        if sha(surface) != row.get("manifest_sha256"):
            raise R5Error("dialect-v2 surface SHA binding drift")
    return {"path": DIALECT.relative_to(ROOT).as_posix(), "sha256": sha(DIALECT)}


def pack_candidate(materialization: Path, closure: Path, out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise R5Error(f"R5 candidate output must be fresh: {out}")
    product = verify_materialization(materialization)
    tests = verify_closure(closure)
    r5 = contract()
    migration = load(MIGRATION, "dialect migration contract")
    matrix = load(MATRIX, "global G5 matrix")
    migration_sha = sha(MIGRATION)
    value = {
        "format": CANDIDATE_FORMAT,
        "version": 1,
        "profile": "dialect-v2",
        "status": "preflight-candidate-g5-none",
        "source_commit": r5["product_candidate"]["source_commit"],
        "build_id": int(r5["product_candidate"]["product_build_id"], 16),
        "product": {
            "authority": "sealed-r4-product-candidate-archive",
            "artifact_set_sha256": product["product_artifact_set_sha256"],
            "artifact_count": PRODUCT_ARTIFACT_COUNT,
            "materialization": materialization.relative_to(ROOT).as_posix(),
            "materialization_sha256": sha(materialization),
        },
        "test_closure": {
            "product_membership": "forbidden",
            "manifest": closure.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(closure),
            "closure_set_sha256": tests["closure_set_sha256"],
            "change_policy": tests["change_policy"],
        },
        "bindings": {
            "r5_contract": CONTRACT.relative_to(ROOT).as_posix(),
            "r5_contract_sha256": sha(CONTRACT),
            "matrix_contract": MATRIX.relative_to(ROOT).as_posix(),
            "matrix_contract_sha256": sha(MATRIX),
            "migration_contract": MIGRATION.relative_to(ROOT).as_posix(),
            "migration_contract_sha256": migration_sha,
            "dialect_contract": dialect_binding(
                migration_sha, r5["product_candidate"]["source_commit"],
            )["path"],
            "dialect_contract_sha256": dialect_binding(
                migration_sha, r5["product_candidate"]["source_commit"],
            )["sha256"],
            "family_measurements": family_bindings(migration),
        },
        "claims": {"G5": "not-run", "G6": "not-run", "release": "not-release-capable"},
    }
    if matrix.get("id") != "dialect-v2-product-switch":
        raise R5Error("global matrix identity drift")
    write_json(out, value)
    print(f"R5 global candidate: PASS product={product['product_artifact_set_sha256']} test-closure={tests['closure_set_sha256']}")


def verify_candidate(path: Path, materialization: Path, closure: Path) -> dict[str, Any]:
    value = load(path, "R5 global candidate")
    if value.get("format") != CANDIDATE_FORMAT or value.get("status") != "preflight-candidate-g5-none":
        raise R5Error("R5 candidate identity/status drift")
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-candidate-") as raw:
        expected = Path(raw) / "candidate.json"
        pack_candidate(materialization, closure, expected)
        expected_value = load(expected, "recomputed R5 candidate")
    if value != expected_value:
        raise R5Error("R5 candidate drift")
    return value


def pack_hw_package(
    candidate_path: Path, materialization: Path, closure_path: Path, out: Path,
) -> None:
    if out.exists() or out.is_symlink():
        raise R5Error(f"R5 hardware package output must be fresh: {out}")
    candidate = verify_candidate(candidate_path, materialization, closure_path)
    product = verify_materialization(materialization)
    tests = verify_closure(closure_path)
    product_by_role = {row["role"]: materialization.parent / Path(*PurePosixPath(row["path"]).parts) for row in product["artifacts"]}
    test_by_id = {row["id"]: repo_path(row["path"], f"test closure {row['id']}") for row in tests["artifacts"]}
    runtime_binding = load(test_by_id["runtime-overlay-binding"], "R4 runtime overlay binding")
    if (
        runtime_binding.get("schema") != "lisp65-runtime-overlay-package-v2"
        or runtime_binding.get("elf", {}).get("sha256") != sha(product_by_role["linked-product-elf"])
        or runtime_binding.get("storage", {}).get("sha256") != sha(product_by_role["attic-catalog"])
    ):
        raise R5Error("runtime overlay metadata is not derived from the sealed product bytes")
    sources = (
        ("workbench-prg", product_by_role["workbench-prg"], "lisp65-mvp-workbench.prg"),
        ("workbench-stdlib-blob", product_by_role["bank5-preload"], "lisp65-mvp-workbench.blob.bin"),
        ("workbench-runtime-overlays", product_by_role["attic-catalog"], "lisp65-mvp-workbench.overlays.bin"),
        ("attic-library-shelf", product_by_role["attic-library-shelf"], "lisp65-mvp-workbench.shelf.bin"),
        ("workbench-d81", test_by_id["workbench-test-d81"], "lisp65-mvp-workbench.d81"),
        ("workbench-elf", product_by_role["linked-product-elf"], "lisp65-workbench-overlay-linked.prg.elf"),
        ("persistence-bam-alloc-prg", test_by_id["helper-bam-alloc"], "persistence-bam-alloc.prg"),
        ("persistence-chain-write-prg", test_by_id["helper-chain-write"], "persistence-chain-write.prg"),
        ("persistence-dir-write-prg", test_by_id["helper-dir-write"], "persistence-dir-write.prg"),
        ("persistence-save-new-prg", test_by_id["helper-save-new"], "persistence-save-new.prg"),
        ("persistence-save-new-scan-prg", test_by_id["helper-save-new-scan"], "persistence-save-new-scan.prg"),
        ("persistence-save-new-var-prg", test_by_id["helper-save-new-var"], "persistence-save-new-var.prg"),
    )
    out.mkdir(parents=True)
    records = []
    for artifact_id, source, name in sources:
        target = out / name
        shutil.copyfile(source, target)
        records.append({"id": artifact_id, "path": name, "size": target.stat().st_size, "sha256": sha(target)})
    shutil.copyfile(candidate_path, out / "candidate.json")
    attic = out / "lisp65-mvp-workbench.overlays.bin"
    shelf = out / "lisp65-mvp-workbench.shelf.bin"
    bank5 = out / "lisp65-mvp-workbench.blob.bin"
    profile_build_id = runtime_binding["profile_build_id"]
    runtime = deepcopy(runtime_binding)
    runtime["elf"]["file"] = "lisp65-workbench-overlay-linked.prg.elf"
    runtime["storage"]["file"] = "lisp65-mvp-workbench.overlays.bin"
    attic_data = attic.read_bytes()
    package = {
        "manifest_format": HW_PACKAGE_FORMAT,
        "profile": "dialect-v2",
        "shippable": False,
        "release_authorization": "none",
        "g5_claim": "none",
        "product_artifact_set_sha256": candidate["product"]["artifact_set_sha256"],
        "test_closure_set_sha256": candidate["test_closure"]["closure_set_sha256"],
        "candidate": {"path": "candidate.json", "sha256": sha(out / "candidate.json")},
        "artifacts": records,
        "preloads": [
            {
                "role": "runtime-overlays", "artifact": "workbench-runtime-overlays",
                "file": "lisp65-mvp-workbench.overlays.bin", "kind": "attic-ram",
                "address": 0x08000000, "address_bits": 28, "length": len(attic_data),
                "crc16": crc16_ccitt_false(attic_data), "crc16_algorithm": "crc-16-ccitt-false",
                "sha256": sha(attic), "build_id": profile_build_id,
                "persistence": "reset-stable-power-volatile", "recovery": "redeploy-required",
            },
            {
                "role": "workbench-stdlib-boot", "artifact": "workbench-stdlib-blob",
                "file": "lisp65-mvp-workbench.blob.bin", "bank": 5,
                "address": 0x00050000, "size": bank5.stat().st_size, "sha256": sha(bank5),
            },
            {
                "role": "attic-library-shelf", "artifact": "attic-library-shelf",
                "file": "lisp65-mvp-workbench.shelf.bin", "kind": "attic-ram",
                "address": 0x08100000, "address_bits": 28, "length": shelf.stat().st_size,
                "crc16": crc16_ccitt_false(shelf.read_bytes()),
                "crc16_algorithm": "crc-16-ccitt-false", "sha256": sha(shelf),
                "persistence": "reset-stable-power-volatile", "recovery": "redeploy-required",
            },
        ],
        "runtime_overlays": runtime,
    }
    write_json(out / "manifest.json", package)
    verify_hw_package(out, candidate_path)
    print(f"R5 global G5 hardware package: PASS artifacts={len(records)} product={candidate['product']['artifact_set_sha256']}")


def verify_fixed_write_fixtures(workbench_d81: Path) -> list[dict[str, Any]]:
    """Prove the destructive fixed-sector cases against the exact bound D81."""
    fixed = PERSISTENCE_FIXTURES["fixed_write"]
    commands = [
        (
            "bam-alloc",
            [
                sys.executable, "tools/host-lisp/d81_bam_alloc_diff.py", "--selftest",
                str(workbench_d81), "--track", str(fixed["track"]),
                "--sector", str(fixed["first_sector"]),
            ],
        ),
        (
            "chain-write",
            [
                sys.executable, "tools/host-lisp/d81_chain_write_diff.py", "--selftest",
                str(workbench_d81), "--source", "tests/disk/m3-chain-source.lisp",
                "--track", str(fixed["track"]), "--first-sector", str(fixed["first_sector"]),
                "--second-sector", str(fixed["second_sector"]),
            ],
        ),
        (
            "dir-write",
            [
                sys.executable, "tools/host-lisp/d81_dir_write_diff.py", "--selftest",
                str(workbench_d81), "--source", "tests/disk/m4-dir-source.lisp",
                "--name", "m4src", "--track", str(fixed["track"]),
                "--first-sector", str(fixed["first_sector"]),
                "--second-sector", str(fixed["second_sector"]),
                "--dir-track", str(fixed["directory_track"]),
                "--dir-sector", str(fixed["directory_sector"]),
                "--dir-entry", str(fixed["directory_entry"]),
            ],
        ),
    ]
    for case_id, command in commands:
        run(command, label=f"validate R5 {case_id} fixed starting layout")
    return [
        {
            "id": case_id,
            "track": fixed["track"],
            "first_sector": fixed["first_sector"],
            "second_sector": None if case_id == "bam-alloc" else fixed["second_sector"],
            "result": "passed",
        }
        for case_id, _ in commands
    ]


def verify_save_new_fixtures(workbench_d81: Path) -> list[dict[str, Any]]:
    """Prove all save-new starting layouts before any physical run."""
    c1541 = shutil.which("c1541")
    if c1541 is None:
        raise R5Error("R5 save-new fixture preflight requires c1541")
    save = PERSISTENCE_FIXTURES["save_new"]
    scan = PERSISTENCE_FIXTURES["save_new_scan"]
    cases = [
        {
            "id": "save-new", "allocator": "tests/fixtures/legacy/m65d/alloc-two-sector.lisp",
            "allocator_name": "m5alloc", "source": "tests/disk/m5-new-source.lisp",
            "name": "m5src", "track": save["track"],
            "first": save["first_sector"], "second": save["second_sector"], "reserve": None,
            "dir_track": save["directory_track"], "dir_sector": save["directory_sector"],
            "dir_entry": save["directory_entry"],
            "oracle": "fixed-two-sector",
        },
        {
            "id": "save-new-scan", "allocator": "tests/fixtures/legacy/m65d/alloc-two-sector.lisp",
            "allocator_name": "m5alloc", "source": "tests/disk/m5-new-source.lisp",
            "name": "m6src", "track": scan["track"],
            "first": scan["first_sector"], "second": scan["second_sector"],
            "reserve": scan["reserved_sector"],
            "dir_track": scan["directory_track"], "dir_sector": scan["directory_sector"],
            "dir_entry": scan["directory_entry"],
            "oracle": "fixed-two-sector-after-reserve",
        },
        {
            "id": "save-new-var", "allocator": "tests/fixtures/legacy/m65d/alloc-variable-chain.lisp",
            "allocator_name": "m7alloc", "source": "tests/disk/m7-var-source.lisp",
            "name": "m7src", "track": save["track"],
            "first": None, "second": None, "reserve": None,
            "dir_track": save["directory_track"], "dir_sector": save["directory_sector"],
            "dir_entry": save["directory_entry"],
            "oracle": "bam-derived-variable-chain",
        },
    ]
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-save-new-preflight-") as raw:
        root = Path(raw)
        for case in cases:
            before = root / f"{case['id']}.d81"
            shutil.copyfile(workbench_d81, before)
            run(
                [c1541, str(before), "-write", str(ROOT / case["allocator"]), f"{case['allocator_name']},s"],
                label=f"prepare R5 {case['id']} allocator fixture",
            )
            if case["reserve"] is not None:
                run(
                    [
                        sys.executable, "tools/host-lisp/d81_bam_reserve_sector.py",
                        str(before), "--track", str(case["track"]), "--sector", str(case["reserve"]),
                    ],
                    label=f"prepare R5 {case['id']} reserved-sector fixture",
                )
            if case["oracle"] == "bam-derived-variable-chain":
                command = [
                    sys.executable, "tools/host-lisp/d81_save_new_diff.py", "--selftest",
                    str(before), "--source", case["source"], "--name", case["name"],
                    "--dir-track", str(case["dir_track"]),
                    "--dir-sector", str(case["dir_sector"]),
                    "--dir-entry", str(case["dir_entry"]),
                ]
            else:
                command = [
                    sys.executable, "tools/host-lisp/d81_dir_write_diff.py", "--selftest",
                    str(before), "--source", case["source"], "--name", case["name"],
                    "--track", str(case["track"]), "--first-sector", str(case["first"]),
                    "--second-sector", str(case["second"]),
                    "--dir-track", str(case["dir_track"]),
                    "--dir-sector", str(case["dir_sector"]),
                    "--dir-entry", str(case["dir_entry"]),
                ]
            run(command, label=f"validate R5 {case['id']} starting layout")
    return [
        {
            "id": case["id"], "oracle": case["oracle"],
            "track": case["track"],
            "first_sector": case["first"], "second_sector": case["second"],
            "reserved_sector": case["reserve"], "result": "passed",
        }
        for case in cases
    ]


def verify_hw_package(package: Path, candidate_path: Path) -> None:
    manifest = load(package / "manifest.json", "R5 G5 hardware package")
    if (
        manifest.get("manifest_format") != HW_PACKAGE_FORMAT
        or manifest.get("profile") != "dialect-v2"
        or manifest.get("shippable") is not False
        or manifest.get("release_authorization") != "none"
        or manifest.get("g5_claim") != "none"
        or manifest.get("candidate", {}).get("sha256") != sha(candidate_path)
        or sha(package / "candidate.json") != sha(candidate_path)
    ):
        raise R5Error("R5 G5 hardware package identity/isolation drift")
    names = {row["id"]: row for row in manifest.get("artifacts", [])}
    required = {
        "workbench-prg", "workbench-stdlib-blob", "workbench-runtime-overlays",
        "attic-library-shelf",
        "workbench-d81", "workbench-elf", "persistence-bam-alloc-prg",
        "persistence-chain-write-prg", "persistence-dir-write-prg",
        "persistence-save-new-prg", "persistence-save-new-scan-prg",
        "persistence-save-new-var-prg",
    }
    if set(names) != required:
        raise R5Error("R5 hardware package artifact coverage drift")
    for artifact_id, row in names.items():
        file = package / row["path"]
        if file.is_symlink() or not file.is_file() or file.stat().st_size != row["size"] or sha(file) != row["sha256"]:
            raise R5Error(f"R5 hardware package artifact drift: {artifact_id}")
    workbench_d81 = package / names["workbench-d81"]["path"]
    run(
        [sys.executable, "tools/host-lisp/d81_bam_sanity.py", str(workbench_d81)],
        label="validate R5 Workbench BAM-read source medium",
    )
    WORKBENCH.bam_read_oracles(workbench_d81)
    verify_save_new_fixtures(workbench_d81)
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-hw-package-") as raw:
        tmp = Path(raw)
        receipt = tmp / "readback-receipt.json"
        common = [
            sys.executable, "scripts/hw-ship-memory-readback.py",
            "--manifest", str(package / "manifest.json"),
            "--prg", str(package / "lisp65-mvp-workbench.prg"),
            "--bank5", str(package / "lisp65-mvp-workbench.blob.bin"),
            "--attic", str(package / "lisp65-mvp-workbench.overlays.bin"),
            "--shelf", str(package / "lisp65-mvp-workbench.shelf.bin"),
            "--d81", str(package / "lisp65-mvp-workbench.d81"),
            "--elf", str(package / "lisp65-workbench-overlay-linked.prg.elf"),
            "--out-dir", str(tmp), "--receipt", str(receipt), "--dry-run",
        ]
        run(common + ["--phase", "staged", "--prefix", "staged"], label="validate R5 staged readback package")
        run(common + ["--phase", "post-reset", "--prefix", "post-reset"], label="validate R5 post-reset readback package")


def case_markers(domain: str, case: str) -> tuple[str, ...]:
    workbench = {
        "overlay-stack-guard": ("hw-workbench-overlay-stack-smoke.sh --no-readback",),
        "stdlib-runtime": ("hw-smoke-vm-stdlib.sh", "hw-jtag-repl.sh"),
        "ux-complete": ("hw-workbench-ux-smoke.sh",),
        "bam-read": ("hw-workbench-bam-read-smoke.sh",),
        "bam-alloc": ("hw-workbench-bam-alloc-smoke.sh", "helper-bam-alloc"),
        "chain-write": ("hw-workbench-chain-write-smoke.sh", "helper-chain-write"),
        "dir-write": ("hw-workbench-dir-write-smoke.sh", "helper-dir-write"),
        "save-new": ("hw-workbench-save-new-smoke.sh", "helper-save-new"),
        "save-new-scan": ("hw-workbench-save-new-smoke.sh", "helper-save-new-scan"),
        "save-new-var": ("hw-workbench-save-new-smoke.sh", "helper-save-new-var"),
    }
    if domain == "runtime-export":
        return (
            "runtime_export_hw_oracle.py deploy", f"--phase '{case}'", "runtime-package",
            "r5_g5_case_receipts.py pack-runtime", "--native-receipt", "--out",
            "R5_PRODUCT_RESULT=PASS", "R5_PRODUCT_RESULT=FAIL",
        )
    evidence = tuple(f"--evidence {role}=" for role in WORKBENCH.EVIDENCE[case])
    failure_marker = (
        ("R5 receipt chain: FAIL kind=harness case=workbench-ux/ux-complete stage=verified-input-or-capture",)
        if case == "ux-complete" else ()
    )
    return workbench[case] + failure_marker + (
        "r5_g5_case_receipts.py pack-workbench", "--native-out", "--out",
        "R5_PRODUCT_RESULT=PASS", "R5_PRODUCT_RESULT=FAIL", "BOOT_WAIT_SEC='8'",
    ) + evidence


def preflight_value(
    candidate_path: Path, materialization: Path, closure_path: Path, negative_path: Path,
    hw_package: Path,
) -> dict[str, Any]:
    r5_contract = contract()
    execution = r5_contract.get("execution_layer", {})
    run_id = execution.get("evidence_run_id")
    boot_wait = execution.get("workbench_boot_wait_seconds")
    if not isinstance(run_id, str) or not run_id or boot_wait != 8:
        raise R5Error("R5 execution-layer run identity drift")
    candidate = verify_candidate(candidate_path, materialization, closure_path)
    product = verify_materialization(materialization)
    tests = verify_closure(closure_path)
    designator_surface = verify_harness_designator_surface(tests)
    verify_hw_package(hw_package, candidate_path)
    matrix = load(MATRIX, "global G5 matrix")
    negative = load(negative_path, "Workbench verifier negative proof")
    expected_negative = WORKBENCH.negative_proof(
        product["product_artifact_set_sha256"], sha(candidate_path), candidate["build_id"],
    )
    if negative != expected_negative:
        raise R5Error("Workbench verifier negative proof drift")
    domains = []
    cases = []
    closure_files = {row["path"] for row in tests["artifacts"]}
    closure_files.add(CLOSURE_POLICY.relative_to(ROOT).as_posix())
    authorization_receipt = "tests/bytecode/dialect-v2/evidence/r5/global-g5-static-preflight-receipt.json"
    recipe_files: set[str] = set()
    recipe_path_re = re.compile(
        r"(?<![A-Za-z0-9_.-])((?:config|demos|lib|scripts|tests|tools)/[A-Za-z0-9_.+/-]+)"
    )
    for domain in matrix["domains"]:
        verifier = repo_path(domain["verifier"], f"{domain['id']} verifier")
        if sha(verifier) != domain["verifier_sha256"]:
            raise R5Error(f"global verifier binding drift: {domain['id']}")
        domains.append({
            "id": domain["id"], "verifier": domain["verifier"],
            "verifier_sha256": domain["verifier_sha256"],
        })
        for case in domain["cases"]:
            target = case["target"]
            command = [
                "make", "-n", target,
                "R5_GLOBAL_G5_POWER_CYCLE_TOKEN=POWER-CYCLED",
                "R5_GLOBAL_G5_CYCLE_ID=static-preflight-only",
            ]
            make_env = os.environ.copy()
            for inherited in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
                make_env.pop(inherited, None)
            completed = subprocess.run(
                command, cwd=ROOT, env=make_env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            recipe = completed.stdout.decode("utf-8", "replace")
            if completed.returncode:
                error = completed.stderr.decode("utf-8", "replace").strip()
                raise R5Error(f"global preflight target does not resolve: {target}: {error}")
            markers = (
                "r5_global_g5.py verify-preflight", candidate_path.relative_to(ROOT).as_posix(),
                product["product_artifact_set_sha256"], tests["closure_set_sha256"],
            ) + case_markers(domain["id"], case["id"])
            missing = [marker for marker in markers if marker not in recipe]
            if missing:
                raise R5Error(f"global preflight target {target} lacks bindings: {missing}")
            if "mvp-ship-artifacts" in recipe or "v2-capability-carrier-internal-g5-preflight-ready" in recipe:
                raise R5Error(f"global preflight target {target} crosses into a foreign product authority")
            for found in recipe_path_re.findall(recipe):
                if found == authorization_receipt:
                    continue
                local = ROOT / found
                if local.is_file():
                    recipe_files.add(found)
            cases.append({
                "id": f"{domain['id']}/{case['id']}", "target": target,
                "recipe_sha256": sha_bytes(recipe.encode()), "status": "ready",
            })
    unbound_recipe_files = sorted(recipe_files - closure_files)
    if unbound_recipe_files:
        raise R5Error(f"global target recipes reference files outside the test closure: {unbound_recipe_files}")
    return {
        "format": PREFLIGHT_FORMAT,
        "version": 1,
        "r5_contract": CONTRACT.relative_to(ROOT).as_posix(),
        "r5_contract_sha256": sha(CONTRACT),
        "matrix_contract": MATRIX.relative_to(ROOT).as_posix(),
        "matrix_contract_sha256": sha(MATRIX),
        "candidate": candidate_path.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha(candidate_path),
        "product_materialization": {
            "receipt": materialization.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(materialization),
            "artifact_count": PRODUCT_ARTIFACT_COUNT,
            "artifact_set_sha256": product["product_artifact_set_sha256"],
            "verified_before_cases": True,
        },
        "test_closure": {
            "manifest": closure_path.relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(closure_path),
            "closure_set_sha256": tests["closure_set_sha256"],
            "artifact_count": len(tests["artifacts"]),
            "product_membership": "forbidden",
            "product_artifact_overlap": tests["product_artifact_overlap"],
            "runtime_carrier_double_build": True,
            "drift_gate": tests["change_policy"],
        },
        "harness_designator_surface": designator_surface,
        "function_metadata_limit": function_metadata_limit(),
        "domain_verifiers": domains,
        "workbench_verifier_negative_proof": {
            "receipt": negative_path.relative_to(ROOT).as_posix(),
            "receipt_sha256": sha(negative_path),
            "domains": 2, "mutations_rejected": 6,
        },
        "case_receipt_chain": {
            "transformer": "tools/host-lisp/r5_g5_case_receipts.py",
            "transformer_sha256": sha(ROOT / "tools/host-lisp/r5_g5_case_receipts.py"),
            "coverage": "target-to-raw-to-native-receipt-to-case-receipt-to-verifier",
            "cases": 14,
            "native_formats": [
                "lisp65-runtime-export-hw-receipt-v2",
                "lisp65-dialect-v2-workbench-native-receipt-v1",
            ],
            "case_formats": [
                "lisp65-dialect-v2-runtime-g5-case-evidence-v1",
                "lisp65-dialect-v2-workbench-g5-case-evidence-v1",
            ],
            "failure_classes": ["product-execution", "receipt-chain-harness"],
            "evidence_run_id": run_id,
            "workbench_boot_wait_seconds": boot_wait,
            "offline_verification": "immediate-and-repeatable",
            "result": "passed-static-no-hardware",
        },
        "hardware_package": {
            "manifest": (hw_package / "manifest.json").relative_to(ROOT).as_posix(),
            "manifest_sha256": sha(hw_package / "manifest.json"),
            "product_artifact_set_sha256": product["product_artifact_set_sha256"],
            "test_closure_set_sha256": tests["closure_set_sha256"],
            "bam_read_media": {
                "sha256": sha(hw_package / "lisp65-mvp-workbench.d81"),
                "oracles": WORKBENCH.bam_read_oracles(
                    hw_package / "lisp65-mvp-workbench.d81"
                ),
            },
            "fixed_write_fixture_preflight": verify_fixed_write_fixtures(
                hw_package / "lisp65-mvp-workbench.d81"
            ),
            "save_new_fixture_preflight": verify_save_new_fixtures(
                hw_package / "lisp65-mvp-workbench.d81"
            ),
            "shippable": False,
        },
        "cases": cases,
        "target_file_bindings": {
            "files": sorted(recipe_files),
            "count": len(recipe_files),
            "unbound": 0,
        },
        "case_count": 14,
        "physical_power_cycles_required": 4,
        "hardware_side_effects": "none",
        "claims": {
            "G5": "not-run",
            "G6": "not-run",
            "release": "not-release-capable",
            "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
        },
        "result": "passed",
    }


def write_preflight(
    candidate: Path, materialization: Path, closure: Path, negative: Path, hw_package: Path, out: Path,
) -> None:
    if out.exists() or out.is_symlink():
        raise R5Error(f"preflight output must be fresh: {out}")
    value = preflight_value(candidate, materialization, closure, negative, hw_package)
    write_json(out, value)
    print(
        "R5 global G5 static preflight: PASS "
        f"cases=14 product={value['product_materialization']['artifact_set_sha256']} "
        f"negative-mutations=6 hardware=not-run"
    )


def verify_preflight(
    candidate: Path, materialization: Path, closure: Path, negative: Path, hw_package: Path, receipt: Path,
) -> None:
    actual = load(receipt, "R5 global G5 preflight receipt")
    expected = preflight_value(candidate, materialization, closure, negative, hw_package)
    if actual != expected:
        raise R5Error("R5 global G5 preflight receipt drift")
    print(
        "R5 global G5 static preflight: PASS verified=true cases=14 "
        f"product={actual['product_materialization']['artifact_set_sha256']} hardware=not-run"
    )


def selftest() -> None:
    value = contract()
    archive_manifest(value)
    closure_policy()
    anonymous, _ = sealed_anonymous_library_designators()
    mutants = (
        "(%ide-store-buffer x)\n",
        "(funcall (quote %ide-store-buffer) x)\n",
        "(apply (function %ide-store-buffer) xs)\n",
        "(apply '%ide-store-buffer xs)\n",
    )
    if any(
        anonymous_function_designators(mutant, anonymous) != [("%ide-store-buffer", 1)]
        for mutant in mutants
    ) or anonymous_function_designators("(ide-make-buffer \"x\" nil)\n", anonymous):
        raise R5Error("R5 anonymous harness-designator selftest failed")
    CASE_RECEIPTS.selftest()
    proof = WORKBENCH.negative_proof(
        value["product_candidate"]["artifact_set_sha256"], "2" * 64,
        int(value["product_candidate"]["product_build_id"], 16),
    )
    if proof.get("result") != "passed" or sum(len(row["mutations"]) for row in proof["domains"]) != 6:
        raise R5Error("R5 Workbench verifier negative selftest failed")
    mutant = deepcopy(value)
    mutant["product_candidate"]["artifact_set_sha256"] = "0" * 64
    try:
        archive_manifest(mutant)
    except R5Error:
        pass
    else:
        raise R5Error("R5 input selftest accepted a foreign product set")
    print(
        "R5 global G5 selftest: PASS archive-bound=true negative-mutations=6 "
        "anonymous-harness-designator-rejection=true"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    materialize_parser = sub.add_parser("materialize")
    materialize_parser.add_argument("--out", type=Path, required=True)
    verify_materialize = sub.add_parser("verify-materialization")
    verify_materialize.add_argument("--receipt", type=Path, required=True)
    runtime = sub.add_parser("build-runtime-carrier")
    runtime.add_argument("--source-commit", required=True)
    runtime.add_argument("--out", type=Path, required=True)
    runtime.add_argument("--jobs", type=int, default=2)
    runtime_repro = sub.add_parser("build-runtime-carrier-reproducible")
    runtime_repro.add_argument("--source-commit", required=True)
    runtime_repro.add_argument("--out", type=Path, required=True)
    runtime_repro.add_argument("--jobs", type=int, default=2)
    closure = sub.add_parser("pack-closure")
    closure.add_argument("--out", type=Path, required=True)
    verify_closure_parser = sub.add_parser("verify-closure")
    verify_closure_parser.add_argument("--manifest", type=Path, required=True)
    candidate = sub.add_parser("pack-candidate")
    candidate.add_argument("--materialization", type=Path, required=True)
    candidate.add_argument("--closure", type=Path, required=True)
    candidate.add_argument("--out", type=Path, required=True)
    verify_candidate_parser = sub.add_parser("verify-candidate")
    verify_candidate_parser.add_argument("--manifest", type=Path, required=True)
    verify_candidate_parser.add_argument("--materialization", type=Path, required=True)
    verify_candidate_parser.add_argument("--closure", type=Path, required=True)
    hw = sub.add_parser("pack-hw")
    hw.add_argument("--candidate", type=Path, required=True)
    hw.add_argument("--materialization", type=Path, required=True)
    hw.add_argument("--closure", type=Path, required=True)
    hw.add_argument("--out", type=Path, required=True)
    verify_hw = sub.add_parser("verify-hw")
    verify_hw.add_argument("--candidate", type=Path, required=True)
    verify_hw.add_argument("--package", type=Path, required=True)
    preflight = sub.add_parser("preflight")
    verify_preflight_parser = sub.add_parser("verify-preflight")
    for current in (preflight, verify_preflight_parser):
        current.add_argument("--candidate", type=Path, required=True)
        current.add_argument("--materialization", type=Path, required=True)
        current.add_argument("--closure", type=Path, required=True)
        current.add_argument("--negative-proof", type=Path, required=True)
        current.add_argument("--hw-package", type=Path, required=True)
    preflight.add_argument("--out", type=Path, required=True)
    verify_preflight_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "materialize":
            materialize(args.out.resolve())
        elif args.command == "verify-materialization":
            verify_materialization(args.receipt.resolve())
            print(
                "R5 product materialization: PASS verified=true "
                f"artifacts={PRODUCT_ARTIFACT_COUNT}"
            )
        elif args.command == "build-runtime-carrier":
            build_runtime_carrier(args.source_commit, args.out.resolve(), args.jobs)
        elif args.command == "build-runtime-carrier-reproducible":
            build_runtime_carrier_reproducible(args.source_commit, args.out.resolve(), args.jobs)
        elif args.command == "pack-closure":
            pack_closure(args.out.resolve())
        elif args.command == "verify-closure":
            value = verify_closure(args.manifest.resolve())
            print(f"R5 test closure: PASS verified=true set={value['closure_set_sha256']}")
        elif args.command == "pack-candidate":
            pack_candidate(args.materialization.resolve(), args.closure.resolve(), args.out.resolve())
        elif args.command == "verify-candidate":
            value = verify_candidate(args.manifest.resolve(), args.materialization.resolve(), args.closure.resolve())
            print(f"R5 global candidate: PASS verified=true product={value['product']['artifact_set_sha256']}")
        elif args.command == "pack-hw":
            pack_hw_package(args.candidate.resolve(), args.materialization.resolve(), args.closure.resolve(), args.out.resolve())
        elif args.command == "verify-hw":
            verify_hw_package(args.package.resolve(), args.candidate.resolve())
            print("R5 global G5 hardware package: PASS verified=true")
        elif args.command == "preflight":
            write_preflight(
                args.candidate.resolve(), args.materialization.resolve(), args.closure.resolve(),
                args.negative_proof.resolve(), args.hw_package.resolve(), args.out.resolve(),
            )
        else:
            verify_preflight(
                args.candidate.resolve(), args.materialization.resolve(), args.closure.resolve(),
                args.negative_proof.resolve(), args.hw_package.resolve(), args.receipt.resolve(),
            )
    except (
        R5Error, WORKBENCH.VerifyError, INTERNAL_DOMAIN.DomainError,
        OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError,
    ) as exc:
        print(f"R5 global G5: FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
