#!/usr/bin/env python3
"""Stdlib-only verifier for a sealed R5 global-G5 hardware archive."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any


BASE = Path(__file__).resolve().parent
PAYLOAD = BASE / "payload"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ARCHIVE_FORMAT = "lisp65-r5-global-g5-archive-v1"
RECEIPT_FORMAT = "lisp65-r5-global-g5-hardware-receipt-v1"
SEAL_CONTRACT_FORMAT = "lisp65-r5-global-g5-seal-contract-v1"


class VerifyError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerifyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"{label} must be a regular non-symlink file: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must be an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise VerifyError(f"{label} keys drift: {actual}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise VerifyError(f"{label} must be a lowercase SHA-256")
    return value


def relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerifyError(f"{label} must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise VerifyError(f"{label} escapes the payload: {value!r}")
    return value


def payload_file(path_value: Any, digest: Any, label: str) -> Path:
    relative = relative_path(path_value, label)
    path = PAYLOAD / Path(*PurePosixPath(relative).parts)
    if (
        path.is_symlink()
        or not path.is_file()
        or sha(path) != lower_sha(digest, f"{label} SHA")
    ):
        raise VerifyError(f"{label} SHA binding drift")
    return path


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


def verify_capacity_delta(value: Any, product_set: str) -> None:
    delta = exact(
        value,
        {"baseline_identity_sha256", "candidate_identity_sha256", "dimensions"},
        "capacity_delta",
    )
    if (
        delta["baseline_identity_sha256"] != product_set
        or delta["candidate_identity_sha256"] != product_set
    ):
        raise VerifyError("R5 capacity delta changed product identity")
    dimensions = exact(
        delta["dimensions"], {"bank", "ext", "symbols", "namepool", "directory"},
        "capacity_delta.dimensions",
    )
    for name, raw in dimensions.items():
        row = exact(raw, {"baseline", "candidate", "delta", "authorization"}, f"capacity {name}")
        if (
            type(row["baseline"]) is not int
            or row["candidate"] != row["baseline"]
            or row["delta"] != 0
            or row["authorization"] is not None
        ):
            raise VerifyError(f"R5 hardware acceptance has nonzero capacity drift: {name}")


def verify_inventory(manifest: dict[str, Any]) -> None:
    rows = manifest["files"]
    if not isinstance(rows, list) or not rows:
        raise VerifyError("archive payload inventory is empty")
    expected: list[str] = []
    for index, raw in enumerate(rows):
        row = exact(raw, {"path", "bytes", "sha256"}, f"archive file[{index}]")
        relative = relative_path(row["path"], f"archive file[{index}].path")
        path = PAYLOAD / Path(*PurePosixPath(relative).parts)
        if (
            type(row["bytes"]) is not int
            or row["bytes"] < 0
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha(path) != lower_sha(row["sha256"], f"archive file[{index}].sha256")
        ):
            raise VerifyError(f"archive payload file drift: {relative}")
        expected.append(relative)
    if expected != sorted(set(expected)):
        raise VerifyError("archive payload paths must be sorted and unique")
    actual: list[str] = []
    for path in PAYLOAD.rglob("*"):
        if path.is_symlink():
            raise VerifyError(f"archive payload contains symlink: {path}")
        if path.is_file():
            actual.append(path.relative_to(PAYLOAD).as_posix())
    if sorted(actual) != expected:
        raise VerifyError("archive payload inventory is not exact")


def verify_product(top: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    product = exact(
        top["product"],
        {
            "input_authority", "r4_promotion_id", "r4_archive", "r4_archive_sha256",
            "artifact_set_sha256", "product_build_id", "artifact_count",
            "materialization", "materialization_sha256", "artifacts",
            "product_sha_changes",
        },
        "top receipt product",
    )
    product_set = lower_sha(product["artifact_set_sha256"], "product artifact set")
    r4_archive_sha = lower_sha(product["r4_archive_sha256"], "R4 archive SHA")
    if (
        product["input_authority"] != "sealed-r4-product-candidate-archive"
        or not isinstance(product["r4_promotion_id"], str)
        or not product["r4_promotion_id"]
        or not isinstance(product["r4_archive"], str)
        or r4_archive_sha == product_set
        or not isinstance(product["product_build_id"], str)
        or not re.fullmatch(r"[0-9a-f]{8}", product["product_build_id"])
        or type(product["artifact_count"]) is not int
        or product["artifact_count"] <= 0
        or product["product_sha_changes"] != 0
        or not isinstance(product["artifacts"], list)
        or len(product["artifacts"]) != product["artifact_count"]
    ):
        raise VerifyError("top receipt product identity drift")
    materialization_path = payload_file(
        product["materialization"], product["materialization_sha256"],
        "product materialization",
    )
    materialization = load(materialization_path, "product materialization")
    if (
        materialization.get("format") != "lisp65-r5-product-materialization-v1"
        or materialization.get("input_authority") != product["input_authority"]
        or materialization.get("live_tree_product_authority") is not False
        or materialization.get("archive") != product["r4_archive"]
        or materialization.get("archive_sha256") != product["r4_archive_sha256"]
        or materialization.get("product_artifact_set_sha256") != product_set
        or materialization.get("product_build_id") != product["product_build_id"]
        or materialization.get("artifact_count") != product["artifact_count"]
        or materialization.get("artifacts") != product["artifacts"]
        or materialization.get("result") != "passed"
    ):
        raise VerifyError("product materialization receipt drift")
    roles: list[str] = []
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(product["artifacts"]):
        row = exact(
            raw, {"role", "name", "path", "bytes", "sha256"},
            f"product artifact[{index}]",
        )
        artifact = payload_file(row["path"], row["sha256"], f"product artifact[{index}]")
        if artifact.stat().st_size != row["bytes"]:
            raise VerifyError(f"product artifact size drift: {row['role']}")
        roles.append(row["role"])
        rows.append(row)
    if len(set(roles)) != product["artifact_count"] or artifact_set_sha(rows) != product_set:
        raise VerifyError("product artifact-set recomputation drift")
    return product_set, rows


def verify_test_closure(top: dict[str, Any], product_set: str) -> str:
    binding = exact(
        top["test_closure"],
        {
            "manifest", "manifest_sha256", "closure_set_sha256", "artifact_count",
            "product_membership", "product_artifact_overlap", "runtime_core_role",
        },
        "top receipt test closure",
    )
    manifest_path = payload_file(
        binding["manifest"], binding["manifest_sha256"], "test-closure manifest"
    )
    manifest = load(manifest_path, "test-closure manifest")
    rows = manifest.get("artifacts")
    if (
        manifest.get("format") != "lisp65-r5-global-g5-test-closure-v1"
        or manifest.get("version") != 1
        or manifest.get("product_artifact_set_sha256") != product_set
        or manifest.get("product_membership") != "forbidden"
        or manifest.get("product_artifact_overlap") != 0
        or manifest.get("runtime_core_role") != "internal-proof-only-test-carrier"
        or not isinstance(rows, list)
        or type(binding["artifact_count"]) is not int
        or binding["artifact_count"] <= 0
        or len(rows) != binding["artifact_count"]
        or binding["product_membership"] != "forbidden"
        or binding["product_artifact_overlap"] != 0
        or binding["runtime_core_role"] != "internal-proof-only-test-carrier"
    ):
        raise VerifyError("test-closure identity/boundary drift")
    ids: list[str] = []
    normalized: list[dict[str, Any]] = []
    product_shas = {row["sha256"] for row in top["product"]["artifacts"]}
    for index, raw in enumerate(rows):
        row = exact(raw, {"id", "path", "bytes", "sha256"}, f"closure artifact[{index}]")
        artifact = payload_file(row["path"], row["sha256"], f"closure artifact[{index}]")
        if artifact.stat().st_size != row["bytes"] or row["sha256"] in product_shas:
            raise VerifyError(f"test-closure artifact boundary drift: {row['id']}")
        ids.append(row["id"])
        normalized.append(row)
    observed = closure_set_sha(normalized)
    if (
        len(ids) != len(set(ids))
        or observed != manifest.get("closure_set_sha256")
        or observed != binding["closure_set_sha256"]
    ):
        raise VerifyError("test-closure set recomputation drift")
    return observed


def matrix_cases(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for domain in matrix.get("domains", []):
        if not isinstance(domain, dict) or not isinstance(domain.get("id"), str):
            raise VerifyError("matrix domain drift")
        for case in domain.get("cases", []):
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                raise VerifyError("matrix case drift")
            case_id = f"{domain['id']}/{case['id']}"
            if case_id in result:
                raise VerifyError(f"duplicate matrix case: {case_id}")
            result[case_id] = case
    if len(result) != 14:
        raise VerifyError("matrix must contain exactly 14 cases")
    return result


def verify_cases(
    top: dict[str, Any], candidate_path: Path, candidate_sha: str,
    matrix: dict[str, Any],
) -> None:
    specs = matrix_cases(matrix)
    rows = top["cases"]
    if not isinstance(rows, list) or len(rows) != 14:
        raise VerifyError("top receipt must bind exactly 14 case receipts")
    ids: list[str] = []
    runtime_cycles: list[str] = []
    verifier = PAYLOAD / "tools/host-lisp/r5_g5_case_receipts.py"
    for index, raw in enumerate(rows):
        row = exact(
            raw, {"id", "target", "result", "cycle_id", "receipt", "receipt_sha256"},
            f"case receipt[{index}]",
        )
        case_id = row["id"]
        if case_id not in specs or row["target"] != specs[case_id]["target"] or row["result"] != specs[case_id]["expected"]:
            raise VerifyError(f"case receipt differs from matrix: {case_id}")
        if not isinstance(row["cycle_id"], str) or not SAFE_ID_RE.fullmatch(row["cycle_id"]):
            raise VerifyError(f"invalid case cycle id: {case_id}")
        receipt_path = payload_file(row["receipt"], row["receipt_sha256"], f"case receipt {case_id}")
        receipt = load(receipt_path, f"case receipt {case_id}")
        if (
            receipt.get("case_id") != case_id
            or receipt.get("target") != row["target"]
            or receipt.get("result") != row["result"]
            or receipt.get("cycle_id") != row["cycle_id"]
            or receipt.get("candidate_manifest_sha256") != candidate_sha
        ):
            raise VerifyError(f"case receipt identity drift: {case_id}")
        completed = subprocess.run(
            [
                sys.executable, verifier.relative_to(PAYLOAD).as_posix(), "verify-case",
                "--candidate", candidate_path.relative_to(PAYLOAD).as_posix(),
                "--receipt", receipt_path.relative_to(PAYLOAD).as_posix(),
            ],
            cwd=PAYLOAD,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode:
            raise VerifyError(
                f"semantic case verification failed: {case_id}:\n{completed.stdout}"
            )
        if case_id.startswith("runtime-export/"):
            runtime_cycles.append(row["cycle_id"])
        ids.append(case_id)
    if ids != sorted(specs) or len(set(ids)) != 14:
        raise VerifyError("case receipt coverage must be sorted and exactly once")
    if sorted(runtime_cycles) != top["runtime_cycle_ids"] or len(set(runtime_cycles)) != 4:
        raise VerifyError("Runtime receipts do not bind four distinct power cycles")


def verify() -> dict[str, Any]:
    manifest = load(BASE / "manifest.json", "R5 archive manifest")
    exact(
        manifest,
        {
            "format", "version", "id", "kind", "status", "source_commit",
            "sealed_on", "immutability", "offline_verifier_sha256", "claims",
            "product", "test_closure", "candidate", "matrix", "top_receipt",
            "files",
        },
        "R5 archive manifest",
    )
    if (
        manifest["format"] != ARCHIVE_FORMAT
        or manifest["version"] != 1
        or manifest["kind"] != "hardware-acceptance"
        or manifest["status"] != "sealed"
        or not isinstance(manifest["id"], str)
        or not SAFE_ID_RE.fullmatch(manifest["id"])
        or not isinstance(manifest["source_commit"], str)
        or not COMMIT_RE.fullmatch(manifest["source_commit"])
        or not isinstance(manifest["sealed_on"], str)
        or not DATE_RE.fullmatch(manifest["sealed_on"])
        or manifest["immutability"] != "append-only-never-amend"
        or manifest["offline_verifier_sha256"] != sha(BASE / "verify.py")
    ):
        raise VerifyError("R5 archive identity drift")
    verify_inventory(manifest)
    top_path = payload_file(
        manifest["top_receipt"]["path"], manifest["top_receipt"]["sha256"],
        "top receipt",
    )
    top = load(top_path, "R5 top receipt")
    exact(
        top,
        {
            "format", "version", "status", "profile", "source_commit", "sealed_on",
            "run_id", "seal_contract", "seal_contract_sha256", "candidate",
            "candidate_sha256", "matrix", "matrix_sha256", "preflight",
            "preflight_sha256", "product", "test_closure", "cases",
            "runtime_cycle_ids", "case_coverage", "physical_power_cycles",
            "ceremony", "capacity_delta", "claims", "result",
        },
        "R5 top receipt",
    )
    if (
        top["format"] != RECEIPT_FORMAT
        or top["version"] != 1
        or top["status"] != "passed"
        or top["profile"] != "dialect-v2"
        or top["source_commit"] != manifest["source_commit"]
        or top["sealed_on"] != manifest["sealed_on"]
        or not isinstance(top["run_id"], str)
        or not SAFE_ID_RE.fullmatch(top["run_id"])
        or top["case_coverage"] != "exactly-once"
        or top["physical_power_cycles"] != 4
        or top["result"] != "passed"
    ):
        raise VerifyError("R5 top receipt identity/result drift")
    contract_path = payload_file(
        top["seal_contract"], top["seal_contract_sha256"], "R5 seal contract"
    )
    seal_contract = load(contract_path, "R5 seal contract")
    if (
        seal_contract.get("format") != SEAL_CONTRACT_FORMAT
        or seal_contract.get("version") != 1
        or seal_contract.get("id") != "r5-global-g5-hardware-acceptance"
        or seal_contract.get("status") != "authorized"
        or seal_contract.get("ceremony") != top["ceremony"]
        or seal_contract.get("claims") != top["claims"]
        or seal_contract.get("capacity_delta") != top["capacity_delta"]
    ):
        raise VerifyError("R5 seal contract drift")
    product_set, _product_rows = verify_product(top)
    closure_set = verify_test_closure(top, product_set)
    candidate_path = payload_file(top["candidate"], top["candidate_sha256"], "R5 candidate")
    candidate = load(candidate_path, "R5 candidate")
    if (
        candidate.get("format") != "lisp65-r5-global-g5-candidate-v1"
        or candidate.get("status") != "preflight-candidate-g5-none"
        or candidate.get("product", {}).get("artifact_set_sha256") != product_set
        or candidate.get("test_closure", {}).get("closure_set_sha256") != closure_set
    ):
        raise VerifyError("R5 candidate identity drift")
    matrix_path = payload_file(top["matrix"], top["matrix_sha256"], "G5 matrix")
    matrix = load(matrix_path, "G5 matrix")
    if matrix.get("format") != "lisp65-dialect-v2-g5-matrix-v1":
        raise VerifyError("G5 matrix identity drift")
    preflight_path = payload_file(
        top["preflight"], top["preflight_sha256"], "R5 static preflight"
    )
    preflight = load(preflight_path, "R5 static preflight")
    if (
        preflight.get("format") != "lisp65-r5-global-g5-static-preflight-v1"
        or preflight.get("result") != "passed"
        or preflight.get("case_count") != 14
        or preflight.get("physical_power_cycles_required") != 4
        or preflight.get("product_materialization", {}).get("artifact_set_sha256") != product_set
        or preflight.get("test_closure", {}).get("closure_set_sha256") != closure_set
        or preflight.get("claims") != {
            "G5": "not-run",
            "G6": "not-run",
            "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
            "release": "not-release-capable",
        }
    ):
        raise VerifyError("R5 static preflight boundary drift")
    expected_claims = {
        "G5": "passed-for-product-artifact-set",
        "product_artifact_set_sha256": product_set,
        "G6": "not-run",
        "hardware_boot_cases": (
            "not-run(5/5-applicable); execution=single-device; "
            "n/a(1/1-profile-bound)"
        ),
        "function_metadata": "101-exact/34-unresolved-no-complete-help-claim",
        "release": "not-release-capable",
    }
    expected_ceremony = {
        "final_one_ceremony_rerun": "permanently-unnecessary",
        "reason": "sha-bound-case-receipts-with-cycle-ids-are-the-evidence-object",
    }
    if top["claims"] != expected_claims or manifest["claims"] != expected_claims:
        raise VerifyError("R5 sealed claim boundary drift")
    if top["ceremony"] != expected_ceremony:
        raise VerifyError("R5 final-ceremony doctrine drift")
    verify_capacity_delta(top["capacity_delta"], product_set)
    verify_cases(top, candidate_path, top["candidate_sha256"], matrix)
    if manifest["product"] != {
        "artifact_set_sha256": product_set,
        "artifact_count": top["product"]["artifact_count"],
        "product_sha_changes": 0,
    } or manifest["test_closure"] != {
        "closure_set_sha256": closure_set,
        "artifact_count": top["test_closure"]["artifact_count"],
        "product_artifact_overlap": 0,
    } or manifest["candidate"] != {
        "path": top["candidate"], "sha256": top["candidate_sha256"]
    } or manifest["matrix"] != {
        "path": top["matrix"], "sha256": top["matrix_sha256"], "cases": 14
    }:
        raise VerifyError("R5 archive/top receipt summary drift")
    return top


def main() -> int:
    try:
        value = verify()
        print(
            "r5-g5-seal-offline: PASS cases=14 cycles=4 "
            f"product={value['product']['artifact_set_sha256']} "
            "G5=passed G6=not-run boot-hardware=not-run(5/5-applicable) "
            "execution=single-device n/a(1/1-profile-bound) release=no"
        )
        return 0
    except (VerifyError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"r5-g5-seal-offline: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
