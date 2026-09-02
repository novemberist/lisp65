#!/usr/bin/env python3
"""Build and verify the immutable R5 global-G5 hardware-acceptance seal."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
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

import block_capacity_delta_policy as CAPACITY  # noqa: E402
import history_transport_rewrite as TRANSPORT  # noqa: E402
import r5_g5_case_receipts as CASES  # noqa: E402
import r5_g5_seal_offline as OFFLINE  # noqa: E402


CONTRACT = ROOT / "config/r5-g5-seal-contract.json"
CANDIDATE = ROOT / "build/r5-global-g5/candidate.json"
MATRIX = ROOT / "config/dialect-v2-g5-matrix.json"
PREFLIGHT = ROOT / "tests/bytecode/dialect-v2/evidence/r5/global-g5-static-preflight-receipt.json"
MATERIALIZATION = ROOT / "build/r5-global-g5/product/materialization.json"
TEST_CLOSURE = ROOT / "build/r5-global-g5/test-closure.json"
OFFLINE_VERIFIER = ROOT / "tools/host-lisp/r5_g5_seal_offline.py"
RECEIPT_FORMAT = "lisp65-r5-global-g5-hardware-receipt-v1"
ARCHIVE_FORMAT = "lisp65-r5-global-g5-archive-v1"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

# Imports and subprocess helpers needed by the exact case verifier but not all
# present as first-class rows in the historical test-closure manifest.
OFFLINE_SUPPORT = (
    "tools/host-lisp/d81_bam_sanity.py",
    "tools/host-lisp/d81_persistence_fault.py",
    "tools/host-lisp/dialect_ship_guard.py",
    "tools/host-lisp/r5_g5_seal_offline.py",
)


class SealError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SealError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SealError(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SealError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SealError(f"{label} must be an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise SealError(f"{label} keys drift: {actual}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def repo_relative(path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise SealError(f"{label} must be inside the repository: {path}") from exc


def repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SealError(f"{label} must be a repository-relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or ".." in pure.parts:
        raise SealError(f"{label} escapes repository: {value!r}")
    return ROOT / Path(*pure.parts)


def regular(path: Path, label: str, digest: str | None = None, size: int | None = None) -> Path:
    if path.is_symlink() or not path.is_file():
        raise SealError(f"{label} must be a regular non-symlink file: {path}")
    if digest is not None and (not SHA_RE.fullmatch(digest) or sha(path) != digest):
        raise SealError(f"{label} SHA binding drift")
    if size is not None and path.stat().st_size != size:
        raise SealError(f"{label} size binding drift")
    return path


def bound_repo_bytes(path: Path, digest: str, size: int, label: str) -> bytes:
    """Materialize historical closure bytes without trusting the moving live tree."""
    if path.is_file() and not path.is_symlink():
        data = path.read_bytes()
        if len(data) == size and sha_bytes(data) == digest:
            return data
    relative = repo_relative(path, label)
    history = subprocess.run(
        ["git", "log", "--all", "--format=%H", "--", relative], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if history.returncode:
        raise SealError(f"cannot inspect historical binding for {label}: {relative}")
    for commit in history.stdout.splitlines():
        result = subprocess.run(
            ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if result.returncode == 0 and len(result.stdout) == size and sha_bytes(result.stdout) == digest:
            return result.stdout
    raise SealError(f"cannot materialize SHA-bound historical bytes for {label}: {relative}")


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_text(encoding="ascii") != data:
            raise SealError(f"refusing to overwrite differing immutable receipt: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="ascii")


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    )


def closure_set_sha(rows: list[dict[str, Any]]) -> str:
    values = [
        {key: row[key] for key in ("id", "path", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: row["id"])
    ]
    return sha_bytes(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    )


def contract() -> dict[str, Any]:
    value = load(CONTRACT, "R5 seal contract")
    exact(
        value,
        {
            "format", "version", "id", "status", "kind", "input",
            "receipt", "archive", "ceremony", "claims", "capacity_delta",
        },
        "R5 seal contract",
    )
    if (
        value["format"] != "lisp65-r5-global-g5-seal-contract-v1"
        or value["version"] != 1
        or value["id"] != "r5-global-g5-hardware-acceptance"
        or value["status"] != "authorized"
        or value["kind"] != "hardware-acceptance"
        or value["receipt"] != {
            "format": RECEIPT_FORMAT,
            "case_coverage": "exactly-once",
            "cases": 14,
            "physical_power_cycles": 4,
        }
        or value["archive"] != {
            "format": ARCHIVE_FORMAT,
            "self_contained": True,
            "immutability": "append-only-never-amend",
            "offline_verification": "archive-alone-no-repository-no-network",
        }
        or value["ceremony"] != {
            "final_one_ceremony_rerun": "permanently-unnecessary",
            "reason": "sha-bound-case-receipts-with-cycle-ids-are-the-evidence-object",
        }
    ):
        raise SealError("R5 seal contract semantic drift")
    try:
        CAPACITY.validate_policy()
        CAPACITY.validate_capacity_delta(value["capacity_delta"])
    except CAPACITY.CapacityDeltaError as exc:
        raise SealError(f"R5 seal capacity delta drift: {exc}") from exc
    return value


def canonical_commit(value: str) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise SealError("source commit must be a full lowercase Git commit")
    transport_commit = TRANSPORT.resolve_commit(value)
    completed = subprocess.run(
        ["git", "rev-parse", f"{transport_commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode or completed.stdout.strip() != transport_commit:
        raise SealError("source commit is not canonical in this repository")
    return value


def matrix_specs(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for domain in value.get("domains", []):
        for case in domain.get("cases", []):
            case_id = f"{domain['id']}/{case['id']}"
            if case_id in result:
                raise SealError(f"duplicate matrix case: {case_id}")
            result[case_id] = case
    if len(result) != 14:
        raise SealError("R5 matrix must contain exactly 14 cases")
    return result


def verify_materialization() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = load(MATERIALIZATION, "R5 product materialization")
    rows = value.get("artifacts")
    artifact_count = value.get("artifact_count")
    if (
        value.get("format") != "lisp65-r5-product-materialization-v1"
        or value.get("input_authority") != "sealed-r4-product-candidate-archive"
        or value.get("live_tree_product_authority") is not False
        or type(artifact_count) is not int
        or artifact_count <= 0
        or value.get("result") != "passed"
        or not isinstance(rows, list)
        or len(rows) != artifact_count
    ):
        raise SealError("R5 product materialization identity drift")
    roles: list[str] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"role", "name", "path", "bytes", "sha256"}, f"product[{index}]")
        regular(repo_path(row["path"], f"product[{index}].path"), f"product[{index}]", row["sha256"], row["bytes"])
        roles.append(row["role"])
    if len(set(roles)) != artifact_count or artifact_set_sha(rows) != value.get("product_artifact_set_sha256"):
        raise SealError("R5 product artifact-set recomputation drift")
    return value, rows


def verify_closure() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = load(TEST_CLOSURE, "R5 test closure")
    rows = value.get("artifacts")
    if (
        value.get("format") != "lisp65-r5-global-g5-test-closure-v1"
        or value.get("version") != 1
        or value.get("product_membership") != "forbidden"
        or value.get("product_artifact_overlap") != 0
        or value.get("runtime_core_role") != "internal-proof-only-test-carrier"
        or not isinstance(rows, list)
        or not rows
    ):
        raise SealError("R5 test-closure boundary drift")
    ids: list[str] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"id", "path", "bytes", "sha256"}, f"closure[{index}]")
        bound_repo_bytes(
            repo_path(row["path"], f"closure[{index}].path"),
            row["sha256"], row["bytes"], f"closure[{index}]",
        )
        ids.append(row["id"])
    if len(ids) != len(set(ids)) or closure_set_sha(rows) != value.get("closure_set_sha256"):
        raise SealError("R5 test-closure set recomputation drift")
    return value, rows


def evidence_paths(case: dict[str, Any], receipt_path: Path) -> list[Path]:
    paths = [receipt_path]
    native = regular(
        repo_path(case["native_receipt"], "native receipt"), "native receipt",
        case["native_receipt_sha256"],
    )
    paths.append(native)
    for row in case["raw_artifacts"]:
        paths.append(regular(repo_path(row["path"], "raw artifact"), "raw artifact", row["sha256"]))
    for row in case["verifier_inputs"]:
        paths.append(regular(repo_path(row["path"], "verifier input"), "verifier input", row["sha256"]))
    native_value = load(native, "native receipt")
    for row in native_value.get("evidence", []):
        name = row.get("path") if isinstance(row, dict) else None
        if name is None and isinstance(row, dict):
            name = row.get("file")
        if not isinstance(name, str):
            raise SealError("native receipt evidence path drift")
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts:
            raise SealError("native receipt evidence escapes its directory")
        paths.append(regular(native.parent / Path(*pure.parts), "native raw evidence"))
    return paths


def collect_cases(
    run_dir: Path, candidate: dict[str, Any], candidate_sha: str,
    matrix: dict[str, Any], closure_set: str,
) -> tuple[list[dict[str, Any]], list[Path], list[str]]:
    specs = matrix_specs(matrix)
    pattern = f"receipt-chain/{closure_set}/case-receipt.json"
    receipts = sorted(
        (path for path in run_dir.rglob("case-receipt.json") if path.as_posix().endswith(pattern)),
        key=lambda path: path.as_posix(),
    )
    if len(receipts) != 14:
        raise SealError(f"R5 run must contain exactly 14 current-closure receipts: {len(receipts)}")
    rows: list[dict[str, Any]] = []
    files: list[Path] = []
    runtime_cycles: list[str] = []
    seen: set[str] = set()
    for receipt_path in receipts:
        try:
            value = CASES.verify_case(receipt_path.resolve(), CANDIDATE.resolve())
        except (CASES.ReceiptError, OSError, ValueError, KeyError, TypeError) as exc:
            raise SealError(f"R5 case receipt failed offline verification: {receipt_path}: {exc}") from exc
        case_id = value["case_id"]
        spec = specs.get(case_id)
        if (
            spec is None
            or case_id in seen
            or value["candidate_manifest_sha256"] != candidate_sha
            or value["build_id"] != candidate["build_id"]
            or value["target"] != spec["target"]
            or value["result"] != spec["expected"]
        ):
            raise SealError(f"R5 case identity/result drift: {case_id}")
        row = {
            "id": case_id,
            "target": value["target"],
            "result": value["result"],
            "cycle_id": value["cycle_id"],
            "receipt": repo_relative(receipt_path, "case receipt"),
            "receipt_sha256": sha(receipt_path),
        }
        rows.append(row)
        files.extend(evidence_paths(value, receipt_path))
        if case_id.startswith("runtime-export/"):
            runtime_cycles.append(value["cycle_id"])
        seen.add(case_id)
    rows.sort(key=lambda row: row["id"])
    if [row["id"] for row in rows] != sorted(specs):
        raise SealError("R5 case coverage is not exactly once")
    runtime_cycles.sort()
    if len(runtime_cycles) != 4 or len(set(runtime_cycles)) != 4:
        raise SealError("R5 Runtime cases require four distinct physical cycle IDs")
    return rows, files, runtime_cycles


def add_file(files: dict[str, bytes], path: Path, label: str) -> None:
    regular(path, label)
    relative = repo_relative(path, label)
    data = path.read_bytes()
    previous = files.get(relative)
    if previous is not None and previous != data:
        raise SealError(f"conflicting archive payload bytes: {relative}")
    files[relative] = data


def add_bound_file(
    files: dict[str, bytes], path: Path, digest: str, size: int, label: str,
) -> None:
    relative = repo_relative(path, label)
    data = bound_repo_bytes(path, digest, size, label)
    previous = files.get(relative)
    if previous is not None and previous != data:
        raise SealError(f"conflicting archive payload bytes: {relative}")
    files[relative] = data


def tar_member(name: str, data: bytes) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info, io.BytesIO(data)


def build_top_receipt(
    source_commit: str, sealed_on: str, run_id: str,
    seal_contract: dict[str, Any], candidate: dict[str, Any], candidate_sha: str,
    matrix: dict[str, Any], materialization: dict[str, Any], product_rows: list[dict[str, Any]],
    closure: dict[str, Any], case_rows: list[dict[str, Any]], runtime_cycles: list[str],
) -> dict[str, Any]:
    if not DATE_RE.fullmatch(sealed_on) or not SAFE_ID_RE.fullmatch(run_id):
        raise SealError("R5 seal date/run id drift")
    product_set = materialization["product_artifact_set_sha256"]
    r4_archive_name = PurePosixPath(materialization["archive"]).name
    if not r4_archive_name.endswith(".tar.gz"):
        raise SealError("R4 materialization archive name drift")
    r4_promotion_id = r4_archive_name.removesuffix(".tar.gz")
    if not r4_promotion_id.startswith("r4-product-candidate-"):
        raise SealError("R4 materialization promotion id drift")
    if seal_contract["input"] != {
        "run_id": run_id,
        "candidate_sha256": candidate_sha,
        "product_artifact_set_sha256": product_set,
        "test_closure_set_sha256": closure["closure_set_sha256"],
    }:
        raise SealError("R5 seal contract input binding drift")
    return {
        "format": RECEIPT_FORMAT,
        "version": 1,
        "status": "passed",
        "profile": "dialect-v2",
        "source_commit": source_commit,
        "sealed_on": sealed_on,
        "run_id": run_id,
        "seal_contract": repo_relative(CONTRACT, "seal contract"),
        "seal_contract_sha256": sha(CONTRACT),
        "candidate": repo_relative(CANDIDATE, "candidate"),
        "candidate_sha256": candidate_sha,
        "matrix": repo_relative(MATRIX, "matrix"),
        "matrix_sha256": sha(MATRIX),
        "preflight": repo_relative(PREFLIGHT, "preflight"),
        "preflight_sha256": sha(PREFLIGHT),
        "product": {
            "input_authority": materialization["input_authority"],
            "r4_promotion_id": r4_promotion_id,
            "r4_archive": materialization["archive"],
            "r4_archive_sha256": materialization["archive_sha256"],
            "artifact_set_sha256": product_set,
            "product_build_id": materialization["product_build_id"],
            "artifact_count": len(product_rows),
            "materialization": repo_relative(MATERIALIZATION, "materialization"),
            "materialization_sha256": sha(MATERIALIZATION),
            "artifacts": product_rows,
            "product_sha_changes": 0,
        },
        "test_closure": {
            "manifest": repo_relative(TEST_CLOSURE, "test closure"),
            "manifest_sha256": sha(TEST_CLOSURE),
            "closure_set_sha256": closure["closure_set_sha256"],
            "artifact_count": len(closure["artifacts"]),
            "product_membership": closure["product_membership"],
            "product_artifact_overlap": closure["product_artifact_overlap"],
            "runtime_core_role": closure["runtime_core_role"],
        },
        "cases": case_rows,
        "runtime_cycle_ids": runtime_cycles,
        "case_coverage": "exactly-once",
        "physical_power_cycles": 4,
        "ceremony": seal_contract["ceremony"],
        "capacity_delta": seal_contract["capacity_delta"],
        "claims": seal_contract["claims"],
        "result": "passed",
    }


def create_archive(
    *, archive_id: str, source_commit: str, sealed_on: str, run_id: str, run_dir: Path,
    top_receipt: Path, output: Path,
) -> tuple[str, int]:
    if not SAFE_ID_RE.fullmatch(archive_id):
        raise SealError("R5 archive id is not canonical")
    canonical_commit(source_commit)
    seal_contract = contract()
    candidate, candidate_sha = CASES.candidate_context(CANDIDATE)
    matrix = load(MATRIX, "R5 matrix")
    materialization, product_rows = verify_materialization()
    closure, closure_rows = verify_closure()
    if (
        candidate["product"]["artifact_set_sha256"] != materialization["product_artifact_set_sha256"]
        or candidate["test_closure"]["closure_set_sha256"] != closure["closure_set_sha256"]
        or candidate["test_closure"]["manifest_sha256"] != sha(TEST_CLOSURE)
    ):
        raise SealError("R5 candidate/product/test-closure binding drift")
    preflight = load(PREFLIGHT, "R5 static preflight")
    if (
        preflight.get("result") != "passed"
        or preflight.get("case_count") != 14
        or preflight.get("hardware_side_effects") != "none"
        or preflight.get("claims") != {
            "G5": "not-run",
            "G6": "not-run",
            "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
            "release": "not-release-capable",
        }
    ):
        raise SealError("R5 static preflight claim boundary drift")
    case_rows, evidence_files, runtime_cycles = collect_cases(
        run_dir.resolve(), candidate, candidate_sha, matrix, closure["closure_set_sha256"]
    )
    top = build_top_receipt(
        source_commit, sealed_on, run_id, seal_contract, candidate, candidate_sha,
        matrix, materialization, product_rows, closure, case_rows, runtime_cycles,
    )
    write_json_exclusive(top_receipt, top)

    files: dict[str, bytes] = {}
    for path, label in (
        (CONTRACT, "seal contract"),
        (CANDIDATE, "candidate"),
        (MATRIX, "matrix"),
        (PREFLIGHT, "preflight"),
        (MATERIALIZATION, "materialization"),
        (TEST_CLOSURE, "test closure"),
        (top_receipt, "top receipt"),
        (CAPACITY.DEFAULT_POLICY, "capacity policy"),
    ):
        add_file(files, path, label)
    for row in product_rows:
        add_file(files, repo_path(row["path"], "product artifact"), "product artifact")
    for row in closure_rows:
        add_bound_file(
            files, repo_path(row["path"], "test-closure artifact"),
            row["sha256"], row["bytes"], "test-closure artifact",
        )
    for path in evidence_files:
        add_file(files, path, "R5 case evidence")
    for relative in OFFLINE_SUPPORT:
        add_file(files, ROOT / relative, "offline verifier support")

    file_rows = [
        {"path": path, "bytes": len(data), "sha256": sha_bytes(data)}
        for path, data in sorted(files.items())
    ]
    manifest = {
        "format": ARCHIVE_FORMAT,
        "version": 1,
        "id": archive_id,
        "kind": "hardware-acceptance",
        "status": "sealed",
        "source_commit": source_commit,
        "sealed_on": sealed_on,
        "immutability": "append-only-never-amend",
        "offline_verifier_sha256": sha(OFFLINE_VERIFIER),
        "claims": top["claims"],
        "product": {
            "artifact_set_sha256": materialization["product_artifact_set_sha256"],
            "artifact_count": len(product_rows),
            "product_sha_changes": 0,
        },
        "test_closure": {
            "closure_set_sha256": closure["closure_set_sha256"],
            "artifact_count": len(closure_rows),
            "product_artifact_overlap": 0,
        },
        "candidate": {"path": top["candidate"], "sha256": top["candidate_sha256"]},
        "matrix": {"path": top["matrix"], "sha256": top["matrix_sha256"], "cases": 14},
        "top_receipt": {"path": repo_relative(top_receipt, "top receipt"), "sha256": sha(top_receipt)},
        "files": file_rows,
    }
    manifest_data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("ascii")
    verifier_data = OFFLINE_VERIFIER.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise SealError(f"archive output must be fresh: {output}")
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for name, data in (("manifest.json", manifest_data), ("verify.py", verifier_data)):
                    info, stream = tar_member(name, data)
                    archive.addfile(info, stream)
                for path, data in sorted(files.items()):
                    info, stream = tar_member(f"payload/{path}", data)
                    archive.addfile(info, stream)
    digest = sha(output)
    print(
        f"r5-g5-seal: WROTE cases=14 cycles=4 files={len(files)} "
        f"bytes={output.stat().st_size} sha256={digest}"
    )
    return digest, output.stat().st_size


def safe_extract(archive_path: Path, directory: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise SealError("unsafe/non-file R5 archive member")
        archive.extractall(directory)


def run_extracted_verifier(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "verify.py"], cwd=directory,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


def verify_archive(archive_path: Path) -> None:
    regular(archive_path, "R5 archive")
    with tempfile.TemporaryDirectory(prefix="r5-g5-seal-offline-") as raw:
        directory = Path(raw)
        safe_extract(archive_path, directory)
        completed = run_extracted_verifier(directory)
        if completed.returncode:
            raise SealError(f"isolated R5 archive verification failed:\n{completed.stdout}")
        print(completed.stdout.strip())


def negative_test(archive_path: Path) -> None:
    mutations = ("product-byte", "case-receipt", "top-receipt")
    for mutation in mutations:
        with tempfile.TemporaryDirectory(prefix=f"r5-g5-seal-negative-{mutation}-") as raw:
            directory = Path(raw)
            safe_extract(archive_path, directory)
            manifest = load(directory / "manifest.json", "negative manifest")
            top_path = directory / "payload" / manifest["top_receipt"]["path"]
            top = load(top_path, "negative top receipt")
            if mutation == "product-byte":
                target = directory / "payload" / top["product"]["artifacts"][0]["path"]
                data = bytearray(target.read_bytes())
                data[0] ^= 1
                target.write_bytes(data)
            elif mutation == "case-receipt":
                target = directory / "payload" / top["cases"][0]["receipt"]
                data = bytearray(target.read_bytes())
                data[-2] ^= 1
                target.write_bytes(data)
            else:
                data = bytearray(top_path.read_bytes())
                data[-2] ^= 1
                top_path.write_bytes(data)
            completed = run_extracted_verifier(directory)
            if completed.returncode == 0:
                raise SealError(f"R5 archive verifier accepted mutation: {mutation}")
    print("r5-g5-seal: NEGATIVE PASS mutations=3 product-byte+case-receipt+top-receipt")


def selftest() -> None:
    value = contract()
    matrix = load(MATRIX, "R5 matrix")
    if len(matrix_specs(matrix)) != 14:
        raise SealError("R5 seal selftest matrix drift")
    for relative in OFFLINE_SUPPORT:
        regular(ROOT / relative, f"offline support {relative}")
    if value["claims"].get("G5") != "passed-for-product-artifact-set":
        raise SealError("R5 seal selftest claim drift")
    print(
        "r5-g5-seal: SELFTEST PASS kind=hardware-acceptance cases=14 cycles=4 "
        "ceremony=permanently-unnecessary"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    pack = sub.add_parser("pack")
    pack.add_argument("--id", required=True)
    pack.add_argument("--source-commit", required=True)
    pack.add_argument("--sealed-on", required=True)
    pack.add_argument("--run-id", required=True)
    pack.add_argument("--run-dir", type=Path, required=True)
    pack.add_argument("--top-receipt", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    negative = sub.add_parser("negative-test")
    negative.add_argument("archive", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "pack":
            create_archive(
                archive_id=args.id,
                source_commit=args.source_commit,
                sealed_on=args.sealed_on,
                run_id=args.run_id,
                run_dir=(args.run_dir if args.run_dir.is_absolute() else ROOT / args.run_dir),
                top_receipt=(args.top_receipt if args.top_receipt.is_absolute() else ROOT / args.top_receipt),
                output=(args.output if args.output.is_absolute() else ROOT / args.output),
            )
        elif args.command == "verify":
            verify_archive(args.archive if args.archive.is_absolute() else ROOT / args.archive)
        else:
            negative_test(args.archive if args.archive.is_absolute() else ROOT / args.archive)
        return 0
    except (
        SealError, OFFLINE.VerifyError, CASES.ReceiptError, CAPACITY.CapacityDeltaError,
        OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, tarfile.TarError,
    ) as exc:
        print(f"r5-g5-seal: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
