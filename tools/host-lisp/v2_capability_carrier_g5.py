#!/usr/bin/env python3
"""Validate and plan the non-shippable internal capability/carrier G5 candidate."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "host-lisp"))

import v2_g5_domain_verifiers as DOMAINS  # noqa: E402
DEFAULT_CONTRACT = ROOT / "config/v2-capability-carrier-g5-candidate.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

PROFILE_ID = "dialect-v2-capability-carrier"
CONTRACT_FORMAT = "lisp65-v2-capability-carrier-g5-contract-v1"
CANDIDATE_FORMAT = "lisp65-v2-capability-carrier-g5-candidate-v1"
PLAN_FORMAT = "lisp65-v2-capability-carrier-g5-plan-v1"
RECEIPT_FORMAT = "lisp65-v2-capability-carrier-g5-receipt-v1"
HW_PACKAGE_FORMAT = "lisp65-v2-capability-carrier-hw-package-v1"
PREFLIGHT_FORMAT = "lisp65-v2-capability-carrier-g5-preflight-v1"
DOMAIN_VERIFIER_PATH = "tools/host-lisp/v2_g5_domain_verifiers.py"

EXPECTED_CASES = {
    "runtime-export": (
        ("bitflip", "v2-capability-carrier-g5-runtime-bitflip", "terminal-preload-error-detail-3"),
        ("build-id-mismatch", "v2-capability-carrier-g5-runtime-build-id-mismatch", "terminal-preload-error-detail-2"),
        ("clean", "v2-capability-carrier-g5-runtime-clean", "result-42"),
        ("truncated", "v2-capability-carrier-g5-runtime-truncated", "terminal-preload-error-detail-1"),
    ),
    "workbench-persistence": (
        ("bam-alloc", "v2-capability-carrier-g5-workbench-bam-alloc", "pass"),
        ("bam-read", "v2-capability-carrier-g5-workbench-bam-read", "pass"),
        ("chain-write", "v2-capability-carrier-g5-workbench-chain-write", "pass"),
        ("dir-write", "v2-capability-carrier-g5-workbench-dir-write", "pass"),
        ("save-new", "v2-capability-carrier-g5-workbench-save-new", "pass"),
        ("save-new-scan", "v2-capability-carrier-g5-workbench-save-new-scan", "pass"),
        ("save-new-var", "v2-capability-carrier-g5-workbench-save-new-var", "pass"),
    ),
    "workbench-ux": (
        ("overlay-stack-guard", "v2-capability-carrier-g5-workbench-overlay-stack-guard", "pass"),
        ("stdlib-runtime", "v2-capability-carrier-g5-workbench-stdlib-runtime", "pass"),
        ("ux-complete", "v2-capability-carrier-g5-workbench-ux-complete", "pass"),
    ),
}

REQUIRED_ARTIFACT_IDS = (
    "product-link-budget-report",
    "g5-domain-verifier",
    "runtime-hardware-verifier",
    "runtime-preload-verifier",
    "runtime-ship-verifier",
    "runtime-core-audit",
    "runtime-core-elf",
    "runtime-core-footprint",
    "runtime-core-preload",
    "runtime-core-prg",
    "runtime-hw-manifest",
    "runtime-hw-oracle",
    "runtime-stage-clean",
    "runtime-stage-truncated",
    "runtime-effective-truncated",
    "runtime-clear-truncated",
    "runtime-stage-bitflip",
    "runtime-stage-build-id-mismatch",
    "runtime-foreign-profile",
    "workbench-attic-catalog",
    "workbench-d81",
    "workbench-elf",
    "workbench-footprint",
    "workbench-preload",
    "workbench-prg",
    "persistence-bam-alloc-prg",
    "persistence-chain-write-prg",
    "persistence-dir-write-prg",
    "persistence-save-new-prg",
    "persistence-save-new-scan-prg",
    "persistence-save-new-var-prg",
)

POLICY_ARTIFACT_IDS = (
    "product-link-budget-report",
    "g5-domain-verifier",
    "runtime-hardware-verifier",
    "runtime-preload-verifier",
    "runtime-ship-verifier",
    "runtime-core-audit",
    "runtime-core-footprint",
    "workbench-footprint",
)

PRODUCT_ARTIFACT_IDS = (
    "runtime-core-preload",
    "runtime-core-prg",
    "workbench-attic-catalog",
    "workbench-d81",
    "workbench-preload",
    "workbench-prg",
)

RUNTIME_BASE_ARTIFACTS = (
    "runtime-core-elf", "runtime-core-preload", "runtime-core-prg",
    "runtime-hw-manifest", "runtime-hw-oracle",
)
WORKBENCH_BASE_ARTIFACTS = (
    "workbench-attic-catalog", "workbench-d81", "workbench-preload", "workbench-prg",
)
EXPECTED_CASE_ARTIFACTS = {
    "runtime-export/bitflip": RUNTIME_BASE_ARTIFACTS + ("runtime-stage-bitflip",),
    "runtime-export/build-id-mismatch": RUNTIME_BASE_ARTIFACTS + (
        "runtime-stage-build-id-mismatch", "runtime-foreign-profile",
    ),
    "runtime-export/clean": RUNTIME_BASE_ARTIFACTS + ("runtime-stage-clean",),
    "runtime-export/truncated": RUNTIME_BASE_ARTIFACTS + (
        "runtime-stage-truncated", "runtime-effective-truncated", "runtime-clear-truncated",
    ),
    "workbench-ux/overlay-stack-guard": WORKBENCH_BASE_ARTIFACTS + ("workbench-elf",),
    "workbench-ux/stdlib-runtime": WORKBENCH_BASE_ARTIFACTS,
    "workbench-ux/ux-complete": WORKBENCH_BASE_ARTIFACTS,
    "workbench-persistence/bam-read": WORKBENCH_BASE_ARTIFACTS,
    "workbench-persistence/bam-alloc": WORKBENCH_BASE_ARTIFACTS + ("persistence-bam-alloc-prg",),
    "workbench-persistence/chain-write": WORKBENCH_BASE_ARTIFACTS + ("persistence-chain-write-prg",),
    "workbench-persistence/dir-write": WORKBENCH_BASE_ARTIFACTS + ("persistence-dir-write-prg",),
    "workbench-persistence/save-new": WORKBENCH_BASE_ARTIFACTS + ("persistence-save-new-prg",),
    "workbench-persistence/save-new-scan": WORKBENCH_BASE_ARTIFACTS + ("persistence-save-new-scan-prg",),
    "workbench-persistence/save-new-var": WORKBENCH_BASE_ARTIFACTS + ("persistence-save-new-var-prg",),
}


class G5ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise G5ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise G5ContractError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except G5ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise G5ContractError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise G5ContractError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise G5ContractError(f"{label} keys drift: {actual}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _product_identity(artifacts: list[dict[str, Any]]) -> str:
    by_id = {item.get("id"): item for item in artifacts if isinstance(item, dict)}
    if set(PRODUCT_ARTIFACT_IDS) - set(by_id):
        raise G5ContractError("candidate lacks product identity artifacts")
    value = [
        {"id": artifact_id, "sha256": _sha_value(by_id[artifact_id].get("sha256"), artifact_id)}
        for artifact_id in PRODUCT_ARTIFACT_IDS
    ]
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _sha_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise G5ContractError(f"{label} must be a lowercase SHA-256")
    return value


def _safe_path(root: Path, value: Any, label: str) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or PurePosixPath(value).is_absolute()
        or ".." in PurePosixPath(value).parts
    ):
        raise G5ContractError(f"{label} must be a safe relative path")
    return root / value


def _binding(root: Path, value: Any, label: str) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    path = _safe_path(root, item["path"], f"{label}.path")
    expected = _sha_value(item["sha256"], f"{label}.sha256")
    if path.is_symlink() or not path.is_file() or _sha(path) != expected:
        raise G5ContractError(f"{label} SHA binding drift")
    return path


def validate_contract(value: dict[str, Any], *, root: Path = ROOT) -> None:
    _exact(
        value,
        {
            "format", "version", "id", "status", "profile", "separation",
            "candidate", "matrix", "receipt", "retry_policy", "dry_run",
        },
        "internal G5 contract",
    )
    if (
        value["format"] != CONTRACT_FORMAT
        or value["version"] != 1
        or value["id"] != "v2-capability-carrier-internal-g5"
        or value["status"] != "verifier-bound"
    ):
        raise G5ContractError("internal G5 contract identity/status drift")

    profile = _exact(
        value["profile"],
        {"id", "scope", "shippable", "selection_effect", "global_g5_effect"},
        "profile",
    )
    if profile != {
        "id": PROFILE_ID,
        "scope": "internal-hardware-acceptance-only",
        "shippable": False,
        "selection_effect": "none",
        "global_g5_effect": "none",
    }:
        raise G5ContractError("internal profile isolation drift")

    separation = _exact(
        value["separation"],
        {
            "global_matrix", "normal_ship_guard", "global_profile_switch",
            "normal_ship_packaging", "global_matrix_reuse",
        },
        "separation",
    )
    global_matrix = _binding(root, separation["global_matrix"], "global matrix")
    ship_guard = _binding(root, separation["normal_ship_guard"], "normal Ship guard")
    if (
        global_matrix.relative_to(root).as_posix() != "config/dialect-v2-g5-matrix.json"
        or ship_guard.relative_to(root).as_posix() != "tools/host-lisp/dialect_ship_guard.py"
        or separation["global_profile_switch"] != "forbidden"
        or separation["normal_ship_packaging"] != "forbidden"
        or separation["global_matrix_reuse"] != "forbidden"
    ):
        raise G5ContractError("internal/global G5 separation drift")

    candidate = _exact(
        value["candidate"],
        {
            "manifest_format", "status", "seal", "g5_claim_before_receipts",
            "required_artifact_ids", "policy_artifact_ids", "artifact_completeness",
            "product_artifact_ids", "receipt_identity",
        },
        "candidate",
    )
    if (
        candidate["manifest_format"] != CANDIDATE_FORMAT
        or candidate["status"] != "hardware-candidate"
        or candidate["seal"] != "sha256-all-artifacts-and-policy"
        or candidate["g5_claim_before_receipts"] != "none"
        or tuple(candidate["required_artifact_ids"]) != REQUIRED_ARTIFACT_IDS
        or tuple(candidate["policy_artifact_ids"]) != POLICY_ARTIFACT_IDS
        or candidate["artifact_completeness"] != "case-union-plus-policy-equals-candidate-artifacts"
        or tuple(candidate["product_artifact_ids"]) != PRODUCT_ARTIFACT_IDS
        or candidate["receipt_identity"] != "product-artifact-sha-set"
    ):
        raise G5ContractError("candidate sealing policy drift")

    matrix = _exact(value["matrix"], {"id", "case_coverage", "domains"}, "matrix")
    if (
        matrix["id"] != "v2-capability-carrier-internal-hardware"
        or matrix["case_coverage"] != "exactly-once"
        or not isinstance(matrix["domains"], list)
        or [domain.get("id") for domain in matrix["domains"]] != sorted(EXPECTED_CASES)
    ):
        raise G5ContractError("internal matrix identity/domain drift")
    for index, raw in enumerate(matrix["domains"]):
        domain = _exact(
            raw, {"id", "verifier", "verifier_sha256", "status", "cases"},
            f"matrix.domains[{index}]",
        )
        domain_id = domain["id"]
        verifier = domain["verifier"]
        if (
            not isinstance(verifier, str)
            or verifier != "tools/host-lisp/v2_g5_domain_verifiers.py"
            or not isinstance(domain["verifier_sha256"], str)
            or not SHA_RE.fullmatch(domain["verifier_sha256"])
            or domain["status"] != "implemented"
            or not isinstance(domain["cases"], list)
        ):
            raise G5ContractError(f"matrix domain {domain_id} verifier binding drift")
        verifier_path = root / verifier
        if verifier_path.is_symlink() or not verifier_path.is_file() or _sha(verifier_path) != domain["verifier_sha256"]:
            raise G5ContractError(f"matrix domain {domain_id} verifier SHA binding drift")
        actual_cases = []
        for case_index, case_raw in enumerate(domain["cases"]):
            case = _exact(
                case_raw, {"id", "target", "expected", "artifact_ids"},
                f"{domain_id}[{case_index}]",
            )
            actual_cases.append((case["id"], case["target"], case["expected"]))
            key = f"{domain_id}/{case['id']}"
            if tuple(case["artifact_ids"]) != EXPECTED_CASE_ARTIFACTS[key]:
                raise G5ContractError(f"matrix case {key} artifact coverage drift")
        if tuple(actual_cases) != EXPECTED_CASES[domain_id]:
            raise G5ContractError(f"matrix domain {domain_id} case drift")

    receipt = _exact(
        value["receipt"],
        {
            "format", "verification_status", "hardware_required",
            "dry_run_may_pass_g5", "product_identity_required",
            "case_evidence_required", "preflight_required",
            "harness_fixes_preserve_case_receipts", "full_rerun_trigger",
        },
        "receipt",
    )
    if receipt != {
        "format": RECEIPT_FORMAT,
        "verification_status": "verifier-bound-hardware-required",
        "hardware_required": True,
        "dry_run_may_pass_g5": False,
        "product_identity_required": True,
        "case_evidence_required": True,
        "preflight_required": True,
        "harness_fixes_preserve_case_receipts": True,
        "full_rerun_trigger": "product-artifact-sha-change-only",
    }:
        raise G5ContractError("receipt fail-closed policy drift")

    retry = _exact(
        value["retry_policy"],
        {
            "allowed_scope", "semantic_execution", "media_content_mutation",
            "retry_limit", "fresh_evidence", "fresh_throwaway_media",
            "receipt_requirement",
        },
        "retry_policy",
    )
    if retry != {
        "allowed_scope": "transport-before-semantic-execution-only",
        "semantic_execution": "must-be-false",
        "media_content_mutation": "must-be-false",
        "retry_limit": 1,
        "fresh_evidence": True,
        "fresh_throwaway_media": True,
        "receipt_requirement": "both-attempts-recorded",
    }:
        raise G5ContractError("presemantic transport retry policy drift")

    dry_run = _exact(value["dry_run"], {"format", "side_effects", "hardware_claim", "g5_claim"}, "dry_run")
    if dry_run != {
        "format": PLAN_FORMAT,
        "side_effects": "forbidden",
        "hardware_claim": "none",
        "g5_claim": "none",
    }:
        raise G5ContractError("dry-run non-claim policy drift")


def validate_candidate(
    manifest: dict[str, Any], contract: dict[str, Any], contract_path: Path, *, root: Path = ROOT,
) -> dict[str, Any]:
    _exact(
        manifest,
        {
            "format", "version", "profile", "status", "shippable",
            "release_authorization", "g5_claim", "build_id", "source_commit",
            "contract", "contract_sha256", "global_matrix_sha256",
            "normal_ship_guard_sha256", "product_identity_sha256", "artifacts",
        },
        "internal G5 candidate",
    )
    relative_contract = contract_path.relative_to(root).as_posix()
    if (
        manifest["format"] != CANDIDATE_FORMAT
        or manifest["version"] != 1
        or manifest["profile"] != PROFILE_ID
        or manifest["status"] != "hardware-candidate"
        or manifest["shippable"] is not False
        or manifest["release_authorization"] != "none"
        or manifest["g5_claim"] != "none"
        or type(manifest["build_id"]) is not int
        or not 0 <= manifest["build_id"] <= 0xFFFFFFFF
        or not isinstance(manifest["source_commit"], str)
        or not COMMIT_RE.fullmatch(manifest["source_commit"])
        or manifest["contract"] != relative_contract
        or manifest["contract_sha256"] != _sha(contract_path)
        or manifest["global_matrix_sha256"] != contract["separation"]["global_matrix"]["sha256"]
        or manifest["normal_ship_guard_sha256"] != contract["separation"]["normal_ship_guard"]["sha256"]
    ):
        raise G5ContractError("internal G5 candidate identity/provenance drift")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list):
        raise G5ContractError("candidate artifacts must be a list")
    ids: list[str] = []
    for index, raw in enumerate(artifacts):
        item = _exact(raw, {"id", "path", "sha256"}, f"candidate.artifacts[{index}]")
        artifact_id = item["id"]
        if not isinstance(artifact_id, str) or not SAFE_ID_RE.fullmatch(artifact_id):
            raise G5ContractError(f"candidate artifact {index} has an unsafe id")
        ids.append(artifact_id)
        _binding(root, {"path": item["path"], "sha256": item["sha256"]}, f"artifact {artifact_id}")
    if tuple(ids) != REQUIRED_ARTIFACT_IDS:
        raise G5ContractError("candidate artifact coverage/order drift")
    if manifest["product_identity_sha256"] != _product_identity(artifacts):
        raise G5ContractError("candidate product identity drift")
    referenced = set(POLICY_ARTIFACT_IDS)
    for values in EXPECTED_CASE_ARTIFACTS.values():
        referenced.update(values)
    if referenced != set(ids):
        raise G5ContractError(
            "candidate artifact completeness parity failed: "
            f"missing={sorted(set(ids) - referenced)} foreign={sorted(referenced - set(ids))}"
        )
    artifact_by_id = {item["id"]: item for item in artifacts}
    verifier_binding = artifact_by_id["g5-domain-verifier"]
    for domain in contract["matrix"]["domains"]:
        if (
            verifier_binding["path"] != domain["verifier"]
            or verifier_binding["sha256"] != domain["verifier_sha256"]
        ):
            raise G5ContractError(f"candidate/domain verifier parity failed: {domain['id']}")
    return manifest


def build_plan(contract: dict[str, Any], manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    artifact_by_id = {item["id"]: item for item in manifest["artifacts"]}
    cases = []
    for domain in contract["matrix"]["domains"]:
        for case in domain["cases"]:
            cases.append({
                "id": f"{domain['id']}/{case['id']}",
                "target": case["target"],
                "expected": case["expected"],
                "artifacts": [artifact_by_id[artifact_id] for artifact_id in case["artifact_ids"]],
                "verifier": {
                    "path": domain["verifier"],
                    "sha256": domain["verifier_sha256"],
                },
                "status": "awaiting-hardware",
            })
    return {
        "format": PLAN_FORMAT,
        "profile": PROFILE_ID,
        "candidate_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": _sha(manifest_path),
        "product_identity_sha256": manifest["product_identity_sha256"],
        "build_id": manifest["build_id"],
        "side_effects": "none",
        "hardware_claim": "none",
        "g5_claim": "none",
        "cases": cases,
    }


def verify_receipt(contract_path: Path, contract: dict[str, Any], receipt_path: Path) -> None:
    receipt = _load(receipt_path, "internal G5 receipt")
    _exact(
        receipt,
        {
            "format", "profile", "contract", "contract_sha256", "candidate_manifest",
            "candidate_manifest_sha256", "build_id", "verifier", "verifier_sha256",
            "runtime_cycle_ids", "domains", "result",
        },
        "internal G5 receipt",
    )
    candidate_path = _safe_path(ROOT, receipt["candidate_manifest"], "receipt.candidate_manifest")
    candidate = _load(candidate_path, "receipt candidate")
    validate_candidate(candidate, contract, contract_path)
    verifier_sha = _sha(ROOT / DOMAIN_VERIFIER_PATH)
    if (
        receipt["format"] != RECEIPT_FORMAT
        or receipt["profile"] != PROFILE_ID
        or receipt["contract"] != contract_path.relative_to(ROOT).as_posix()
        or receipt["contract_sha256"] != _sha(contract_path)
        or receipt["candidate_manifest_sha256"] != _sha(candidate_path)
        or receipt["build_id"] != candidate["build_id"]
        or receipt["verifier"] != DOMAIN_VERIFIER_PATH
        or receipt["verifier_sha256"] != verifier_sha
        or receipt["result"] != "passed"
        or not isinstance(receipt["runtime_cycle_ids"], list)
        or len(receipt["runtime_cycle_ids"]) != 4
        or len(set(receipt["runtime_cycle_ids"])) != 4
    ):
        raise G5ContractError("internal G5 receipt provenance/result drift")
    domains = receipt["domains"]
    if not isinstance(domains, list) or [item.get("id") for item in domains] != sorted(EXPECTED_CASES):
        raise G5ContractError("internal G5 receipt domain coverage/order drift")
    runtime_cycles: list[str] | None = None
    for index, raw in enumerate(domains):
        item = _exact(raw, {"id", "receipt", "receipt_sha256"}, f"receipt.domains[{index}]")
        domain_path = _binding(
            ROOT, {"path": item["receipt"], "sha256": item["receipt_sha256"]},
            f"receipt domain {item['id']}",
        )
        try:
            verified = DOMAINS.verify_domain(candidate_path, domain_path, item["id"])
        except (DOMAINS.DomainError, OSError, ValueError, KeyError, TypeError) as exc:
            raise G5ContractError(f"domain verifier failed for {item['id']}: {exc}") from exc
        if item["id"] == "runtime-export":
            runtime_cycles = verified["cycle_ids"]
    if runtime_cycles != receipt["runtime_cycle_ids"]:
        raise G5ContractError("top-level/runtime physical cycle inventory drift")
    print(
        "v2-capability-carrier-internal-g5-receipt: PASS "
        f"cases={sum(len(value) for value in EXPECTED_CASES.values())} "
        "physical_power_cycles=4 g5=passed"
    )


def pack_receipt(
    contract_path: Path, contract: dict[str, Any], candidate_path: Path,
    domain_args: list[str], out: Path,
) -> None:
    candidate_path = candidate_path.resolve()
    candidate = _load(candidate_path, "internal G5 candidate")
    validate_candidate(candidate, contract, contract_path)
    parsed: dict[str, Path] = {}
    for raw in domain_args:
        if "=" not in raw:
            raise G5ContractError(f"domain receipt must be id=path: {raw}")
        domain_id, path_text = raw.split("=", 1)
        if domain_id in parsed or domain_id not in EXPECTED_CASES:
            raise G5ContractError(f"domain receipt id is duplicate/unknown: {domain_id}")
        path = Path(path_text).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError as exc:
            raise G5ContractError(f"domain receipt escapes repository: {path}") from exc
        parsed[domain_id] = path
    if list(parsed) != sorted(EXPECTED_CASES):
        raise G5ContractError("domain receipt coverage/order drift")
    domains = []
    runtime_cycles: list[str] | None = None
    for domain_id, path in parsed.items():
        try:
            verified = DOMAINS.verify_domain(candidate_path, path, domain_id)
        except (DOMAINS.DomainError, OSError, ValueError, KeyError, TypeError) as exc:
            raise G5ContractError(f"domain verifier failed for {domain_id}: {exc}") from exc
        domains.append({
            "id": domain_id,
            "receipt": path.relative_to(ROOT).as_posix(),
            "receipt_sha256": _sha(path),
        })
        if domain_id == "runtime-export":
            runtime_cycles = verified["cycle_ids"]
    if runtime_cycles is None:
        raise G5ContractError("runtime domain did not provide physical cycle IDs")
    receipt = {
        "format": RECEIPT_FORMAT,
        "profile": PROFILE_ID,
        "contract": contract_path.relative_to(ROOT).as_posix(),
        "contract_sha256": _sha(contract_path),
        "candidate_manifest": candidate_path.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": _sha(candidate_path),
        "build_id": candidate["build_id"],
        "verifier": DOMAIN_VERIFIER_PATH,
        "verifier_sha256": _sha(ROOT / DOMAIN_VERIFIER_PATH),
        "runtime_cycle_ids": runtime_cycles,
        "domains": domains,
        "result": "passed",
    }
    if out.exists() or out.is_symlink():
        raise G5ContractError(f"receipt output must be fresh: {out}")
    _write_json(out, receipt)
    try:
        verify_receipt(contract_path, contract, out)
    except Exception:
        out.unlink(missing_ok=True)
        raise


def pack_candidate(
    contract_path: Path, contract: dict[str, Any], artifacts: list[str],
    build_id: int, source_commit: str, out: Path,
) -> None:
    if out.exists() or out.is_symlink():
        raise G5ContractError(f"candidate output must not exist: {out}")
    if not 0 <= build_id <= 0xFFFFFFFF:
        raise G5ContractError("candidate build id must fit in 32 bits")
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise G5ContractError("candidate source commit is invalid")
    parsed: dict[str, Path] = {}
    for raw in artifacts:
        if "=" not in raw:
            raise G5ContractError(f"candidate artifact must be id=path: {raw}")
        artifact_id, path_text = raw.split("=", 1)
        if artifact_id in parsed or artifact_id not in REQUIRED_ARTIFACT_IDS:
            raise G5ContractError(f"candidate artifact id is duplicate/unknown: {artifact_id}")
        path = Path(path_text).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError as exc:
            raise G5ContractError(f"candidate artifact is outside the repository: {path}") from exc
        if path.is_symlink() or not path.is_file():
            raise G5ContractError(f"candidate artifact is not a regular file: {path}")
        parsed[artifact_id] = path
    if tuple(parsed) != REQUIRED_ARTIFACT_IDS:
        raise G5ContractError(
            "candidate pack artifact order/coverage drift: "
            f"expected={list(REQUIRED_ARTIFACT_IDS)} actual={list(parsed)}"
        )
    records = [
        {
            "id": artifact_id,
            "path": parsed[artifact_id].relative_to(ROOT).as_posix(),
            "sha256": _sha(parsed[artifact_id]),
        }
        for artifact_id in REQUIRED_ARTIFACT_IDS
    ]
    manifest = {
        "format": CANDIDATE_FORMAT,
        "version": 1,
        "profile": PROFILE_ID,
        "status": "hardware-candidate",
        "shippable": False,
        "release_authorization": "none",
        "g5_claim": "none",
        "build_id": build_id,
        "source_commit": source_commit,
        "contract": contract_path.relative_to(ROOT).as_posix(),
        "contract_sha256": _sha(contract_path),
        "global_matrix_sha256": contract["separation"]["global_matrix"]["sha256"],
        "normal_ship_guard_sha256": contract["separation"]["normal_ship_guard"]["sha256"],
        "product_identity_sha256": _product_identity(records),
        "artifacts": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out, manifest)
    validate_candidate(manifest, contract, contract_path)
    print(
        "v2-capability-carrier-internal-g5-candidate: WROTE "
        f"build_id={build_id} artifacts={len(records)} out={out}"
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def pack_hw_package(
    manifest_path: Path,
    manifest: dict[str, Any],
    runtime_manifest_path: Path,
    out: Path,
) -> None:
    artifact_paths = {
        item["id"]: _safe_path(ROOT, item["path"], f"artifact {item['id']}.path")
        for item in manifest["artifacts"]
    }
    required = {
        "workbench-prg", "workbench-preload", "workbench-attic-catalog",
        "workbench-d81", "workbench-elf",
    }
    if not required <= artifact_paths.keys():
        raise G5ContractError("candidate lacks the Workbench hardware package inputs")
    runtime = _load(runtime_manifest_path, "runtime overlay manifest")
    if (
        runtime.get("schema") != "lisp65-runtime-overlay-package-v2"
        or runtime.get("profile_build_id") != manifest["build_id"]
    ):
        raise G5ContractError("runtime overlay manifest build/profile binding drift")
    if out.exists() and (out.is_symlink() or not out.is_dir() or any(out.iterdir())):
        raise G5ContractError(f"hardware package output must be an empty directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    package_inputs = (
        ("workbench-prg", "workbench-prg", "lisp65-mvp-workbench.prg"),
        ("workbench-stdlib-blob", "workbench-preload", "lisp65-mvp-workbench.blob.bin"),
        ("workbench-runtime-overlays", "workbench-attic-catalog", "lisp65-mvp-workbench.overlays.bin"),
        ("workbench-d81", "workbench-d81", "lisp65-mvp-workbench.d81"),
        ("workbench-elf", "workbench-elf", "lisp65-workbench-overlay-linked.prg.elf"),
        ("persistence-bam-alloc-prg", "persistence-bam-alloc-prg", "persistence-bam-alloc.prg"),
        ("persistence-chain-write-prg", "persistence-chain-write-prg", "persistence-chain-write.prg"),
        ("persistence-dir-write-prg", "persistence-dir-write-prg", "persistence-dir-write.prg"),
        ("persistence-save-new-prg", "persistence-save-new-prg", "persistence-save-new.prg"),
        ("persistence-save-new-scan-prg", "persistence-save-new-scan-prg", "persistence-save-new-scan.prg"),
        ("persistence-save-new-var-prg", "persistence-save-new-var-prg", "persistence-save-new-var.prg"),
    )
    names = {package_id: filename for package_id, _, filename in package_inputs}
    records = []
    for package_id, candidate_id, filename in package_inputs:
        source = artifact_paths[candidate_id]
        target = out / filename
        shutil.copyfile(source, target)
        records.append({
            "id": package_id,
            "path": filename,
            "size": target.stat().st_size,
            "sha256": _sha(target),
        })
    candidate_copy = out / "candidate.json"
    shutil.copyfile(manifest_path, candidate_copy)
    attic = out / names["workbench-runtime-overlays"]
    bank5 = out / names["workbench-stdlib-blob"]
    attic_data = attic.read_bytes()
    runtime = deepcopy(runtime)
    runtime["elf"]["file"] = names["workbench-elf"]
    runtime["storage"]["file"] = names["workbench-runtime-overlays"]
    package = {
        "manifest_format": HW_PACKAGE_FORMAT,
        "profile": PROFILE_ID,
        "shippable": False,
        "release_authorization": "none",
        "g5_claim": "none",
        "candidate": {"path": candidate_copy.name, "sha256": _sha(candidate_copy)},
        "artifacts": records,
        "preloads": [
            {
                "role": "runtime-overlays",
                "artifact": "workbench-runtime-overlays",
                "file": names["workbench-runtime-overlays"],
                "kind": "attic-ram",
                "address": 0x08000000,
                "address_bits": 28,
                "length": len(attic_data),
                "crc16": _crc16_ccitt_false(attic_data),
                "crc16_algorithm": "crc-16-ccitt-false",
                "sha256": _sha(attic),
                "build_id": manifest["build_id"],
                "persistence": "reset-stable-power-volatile",
                "recovery": "redeploy-required",
            },
            {
                "role": "workbench-stdlib-boot",
                "artifact": "workbench-stdlib-blob",
                "file": names["workbench-stdlib-blob"],
                "bank": 5,
                "address": 0x00050000,
                "size": bank5.stat().st_size,
                "sha256": _sha(bank5),
            },
        ],
        "runtime_overlays": runtime,
    }
    _write_json(out / "manifest.json", package)
    print(
        "v2-capability-carrier-internal-g5-hw-package: WROTE "
        f"build_id={manifest['build_id']} artifacts={len(records)} out={out}"
    )


def verify_hw_package(manifest_path: Path, manifest: dict[str, Any], package_dir: Path) -> None:
    package_dir = package_dir.resolve()
    package = _load(package_dir / "manifest.json", "internal G5 hardware package")
    _exact(
        package,
        {
            "manifest_format", "profile", "shippable", "release_authorization",
            "g5_claim", "candidate", "artifacts", "preloads", "runtime_overlays",
        },
        "internal G5 hardware package",
    )
    candidate_copy = _binding(package_dir, package["candidate"], "hardware package candidate")
    if (
        package["manifest_format"] != HW_PACKAGE_FORMAT
        or package["profile"] != PROFILE_ID
        or package["shippable"] is not False
        or package["release_authorization"] != "none"
        or package["g5_claim"] != "none"
        or candidate_copy.read_bytes() != manifest_path.read_bytes()
    ):
        raise G5ContractError("internal G5 hardware package identity/candidate drift")
    expected = {
        "workbench-prg": "workbench-prg",
        "workbench-stdlib-blob": "workbench-preload",
        "workbench-runtime-overlays": "workbench-attic-catalog",
        "workbench-d81": "workbench-d81",
        "workbench-elf": "workbench-elf",
        "persistence-bam-alloc-prg": "persistence-bam-alloc-prg",
        "persistence-chain-write-prg": "persistence-chain-write-prg",
        "persistence-dir-write-prg": "persistence-dir-write-prg",
        "persistence-save-new-prg": "persistence-save-new-prg",
        "persistence-save-new-scan-prg": "persistence-save-new-scan-prg",
        "persistence-save-new-var-prg": "persistence-save-new-var-prg",
    }
    source = {item["id"]: item for item in manifest["artifacts"]}
    records = package["artifacts"]
    if not isinstance(records, list) or [item.get("id") for item in records] != list(expected):
        raise G5ContractError("hardware package artifact coverage/order drift")
    for index, raw in enumerate(records):
        item = _exact(raw, {"id", "path", "size", "sha256"}, f"hardware package artifact[{index}]")
        path = _safe_path(package_dir, item["path"], f"hardware package artifact {item['id']}")
        if (
            path.is_symlink() or not path.is_file()
            or path.stat().st_size != item["size"]
            or _sha(path) != item["sha256"]
            or item["sha256"] != source[expected[item["id"]]]["sha256"]
        ):
            raise G5ContractError(f"hardware package artifact binding drift: {item['id']}")
    print(
        "v2-capability-carrier-internal-g5-hw-package: PASS "
        f"build_id={manifest['build_id']} artifacts={len(records)}"
    )


def _case_recipe_markers(domain: str, case_id: str) -> tuple[str, ...]:
    workbench = {
        "overlay-stack-guard": ("scripts/hw-workbench-overlay-stack-smoke.sh --no-readback",),
        "stdlib-runtime": ("scripts/hw-smoke-vm-stdlib.sh", "scripts/hw-jtag-repl.sh"),
        "ux-complete": ("scripts/hw-workbench-ux-smoke.sh",),
        "bam-read": ("scripts/hw-workbench-bam-read-smoke.sh",),
        "bam-alloc": ("scripts/hw-workbench-bam-alloc-smoke.sh", "persistence-bam-alloc.prg"),
        "chain-write": ("scripts/hw-workbench-chain-write-smoke.sh", "persistence-chain-write.prg"),
        "dir-write": ("scripts/hw-workbench-dir-write-smoke.sh", "persistence-dir-write.prg"),
        "save-new": ("scripts/hw-workbench-save-new-smoke.sh", "persistence-save-new.prg"),
        "save-new-scan": ("scripts/hw-workbench-save-new-smoke.sh", "persistence-save-new-scan.prg"),
        "save-new-var": (
            "scripts/hw-workbench-save-new-smoke.sh", "persistence-save-new-var.prg",
            "--wait 45 --timeout 40",
        ),
    }
    if domain == "runtime-export":
        return ("tools/host-lisp/runtime_export_hw_oracle.py deploy", f"--phase '{case_id}'")
    return workbench[case_id]


def _preflight_value(
    contract_path: Path, contract: dict[str, Any], manifest_path: Path,
    manifest: dict[str, Any], hw_package: Path, runtime_package: Path,
) -> dict[str, Any]:
    validate_candidate(manifest, contract, contract_path)
    verify_hw_package(manifest_path, manifest, hw_package)
    DOMAINS.verify_runtime_package(runtime_package)
    cases = []
    for domain in contract["matrix"]["domains"]:
        domain_id = domain["id"]
        for case in domain["cases"]:
            target = case["target"]
            command = [
                "make", "-n", target,
                "V2_CAPABILITY_CARRIER_G5_POWER_CYCLE_TOKEN=POWER-CYCLED",
                "V2_CAPABILITY_CARRIER_G5_CYCLE_ID=static-preflight-only",
            ]
            completed = subprocess.run(
                command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            recipe = completed.stdout.decode("utf-8", "replace")
            error = completed.stderr.decode("utf-8", "replace").strip()
            if completed.returncode != 0:
                raise G5ContractError(f"preflight target does not resolve: {target}: {error}")
            common = (
                "verify-candidate", "verify-hw", "verify-runtime-package",
                manifest_path.relative_to(ROOT).as_posix(),
            )
            markers = common + _case_recipe_markers(domain_id, case["id"])
            if domain_id == "runtime-export":
                markers += (runtime_package.relative_to(ROOT).as_posix(),)
            else:
                markers += (hw_package.relative_to(ROOT).as_posix(),)
            missing = [marker for marker in markers if marker not in recipe]
            if missing:
                raise G5ContractError(f"preflight target {target} lacks bindings: {missing}")
            if "build/ship/" in recipe or "build/products/runtime-export" in recipe:
                raise G5ContractError(f"preflight target {target} references a foreign product package")
            cases.append({
                "id": f"{domain_id}/{case['id']}",
                "target": target,
                "recipe_sha256": hashlib.sha256(recipe.encode("utf-8")).hexdigest(),
                "status": "ready",
            })
    return {
        "format": PREFLIGHT_FORMAT,
        "product_identity_sha256": manifest["product_identity_sha256"],
        "candidate_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "candidate_manifest_sha256": _sha(manifest_path),
        "contract": contract_path.relative_to(ROOT).as_posix(),
        "contract_sha256": _sha(contract_path),
        "verifier": DOMAIN_VERIFIER_PATH,
        "verifier_sha256": _sha(ROOT / DOMAIN_VERIFIER_PATH),
        "makefile": "Makefile",
        "makefile_sha256": _sha(ROOT / "Makefile"),
        "cases": cases,
        "side_effects": "none",
        "result": "passed",
    }


def write_preflight(
    contract_path: Path, contract: dict[str, Any], manifest_path: Path,
    manifest: dict[str, Any], hw_package: Path, runtime_package: Path, out: Path,
) -> None:
    if out.exists() or out.is_symlink():
        raise G5ContractError(f"preflight output must be fresh: {out}")
    value = _preflight_value(
        contract_path, contract, manifest_path, manifest, hw_package, runtime_package,
    )
    _write_json(out, value)
    print(
        "v2-capability-carrier-internal-g5-preflight: PASS "
        f"cases={len(value['cases'])} product={value['product_identity_sha256'][:12]} side_effects=none"
    )


def verify_preflight(
    contract_path: Path, contract: dict[str, Any], manifest_path: Path,
    manifest: dict[str, Any], hw_package: Path, runtime_package: Path, receipt: Path,
) -> None:
    actual = _load(receipt, "internal G5 preflight receipt")
    expected = _preflight_value(
        contract_path, contract, manifest_path, manifest, hw_package, runtime_package,
    )
    if actual != expected:
        raise G5ContractError("internal G5 preflight receipt drift")
    print(
        "v2-capability-carrier-internal-g5-preflight: PASS "
        f"cases={len(actual['cases'])} product={actual['product_identity_sha256'][:12]} verified=true"
    )


def _candidate_fixture(root: Path, contract_path: Path, contract: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    artifacts = []
    for artifact_id in REQUIRED_ARTIFACT_IDS:
        if artifact_id == "g5-domain-verifier":
            path = root / DOMAIN_VERIFIER_PATH
        else:
            path = root / "artifacts" / artifact_id
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((artifact_id + "\n").encode("ascii"))
        artifacts.append({
            "id": artifact_id,
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha(path),
        })
    manifest = {
        "format": CANDIDATE_FORMAT,
        "version": 1,
        "profile": PROFILE_ID,
        "status": "hardware-candidate",
        "shippable": False,
        "release_authorization": "none",
        "g5_claim": "none",
        "build_id": 0x65C50001,
        "source_commit": "1" * 40,
        "contract": contract_path.relative_to(root).as_posix(),
        "contract_sha256": _sha(contract_path),
        "global_matrix_sha256": contract["separation"]["global_matrix"]["sha256"],
        "normal_ship_guard_sha256": contract["separation"]["normal_ship_guard"]["sha256"],
        "product_identity_sha256": _product_identity(artifacts),
        "artifacts": artifacts,
    }
    manifest_path = root / "candidate.json"
    _write_json(manifest_path, manifest)
    return manifest_path, manifest


def selftest(contract_path: Path) -> None:
    contract = _load(contract_path, "internal G5 contract")
    validate_contract(contract)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("profile", lambda x: x["profile"].__setitem__("id", "dialect-v2")),
        ("shippable", lambda x: x["profile"].__setitem__("shippable", True)),
        ("selection", lambda x: x["profile"].__setitem__("selection_effect", "activate")),
        ("global-g5", lambda x: x["profile"].__setitem__("global_g5_effect", "passed")),
        ("ship-guard", lambda x: x["separation"]["normal_ship_guard"].__setitem__("sha256", "0" * 64)),
        ("global-reuse", lambda x: x["separation"].__setitem__("global_matrix_reuse", "allowed")),
        ("candidate-claim", lambda x: x["candidate"].__setitem__("g5_claim_before_receipts", "passed")),
        ("verifier", lambda x: x["matrix"]["domains"][0].__setitem__("verifier", "unbound.py")),
        ("case", lambda x: x["matrix"]["domains"][1]["cases"].pop()),
        ("case-artifacts", lambda x: x["matrix"]["domains"][1]["cases"][0]["artifact_ids"].pop()),
        ("product-artifacts", lambda x: x["candidate"]["product_artifact_ids"].pop()),
        ("receipt-identity", lambda x: x["candidate"].__setitem__("receipt_identity", "manifest-sha")),
        ("retry-semantic", lambda x: x["retry_policy"].__setitem__("semantic_execution", "allowed")),
        ("receipt-dry", lambda x: x["receipt"].__setitem__("dry_run_may_pass_g5", True)),
        ("receipt-rerun", lambda x: x["receipt"].__setitem__("full_rerun_trigger", "any-source-change")),
        ("dry-claim", lambda x: x["dry_run"].__setitem__("g5_claim", "passed")),
    ]
    accepted = []
    for name, mutate in mutations:
        candidate = deepcopy(contract)
        mutate(candidate)
        try:
            validate_contract(candidate)
        except G5ContractError:
            continue
        accepted.append(name)
    if accepted:
        raise G5ContractError(f"contract selftest accepted mutations: {accepted}")

    with tempfile.TemporaryDirectory(prefix="lisp65-v2-cp5-g5-") as raw:
        test_root = Path(raw)
        for binding in ("global_matrix", "normal_ship_guard"):
            source = ROOT / contract["separation"][binding]["path"]
            target = test_root / contract["separation"][binding]["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        verifier_target = test_root / DOMAIN_VERIFIER_PATH
        verifier_target.parent.mkdir(parents=True, exist_ok=True)
        verifier_target.write_bytes((ROOT / DOMAIN_VERIFIER_PATH).read_bytes())
        local_contract_path = test_root / "config/v2-capability-carrier-g5-candidate.json"
        local_contract_path.parent.mkdir(parents=True, exist_ok=True)
        local_contract_path.write_bytes(contract_path.read_bytes())
        local_contract = _load(local_contract_path, "selftest contract")
        validate_contract(local_contract, root=test_root)
        manifest_path, manifest = _candidate_fixture(test_root, local_contract_path, local_contract)
        validate_candidate(manifest, local_contract, local_contract_path, root=test_root)

        candidate_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
            ("candidate-profile", lambda x: x.__setitem__("profile", "dialect-v2")),
            ("candidate-shippable", lambda x: x.__setitem__("shippable", True)),
            ("candidate-release", lambda x: x.__setitem__("release_authorization", "passed-g5")),
            ("candidate-g5", lambda x: x.__setitem__("g5_claim", "passed")),
            ("candidate-contract", lambda x: x.__setitem__("contract_sha256", "0" * 64)),
            ("candidate-artifact-drop", lambda x: x["artifacts"].pop()),
            ("candidate-artifact-sha", lambda x: x["artifacts"][0].__setitem__("sha256", "0" * 64)),
            ("candidate-product-identity", lambda x: x.__setitem__("product_identity_sha256", "0" * 64)),
            ("candidate-verifier-path", lambda x: x["artifacts"][1].__setitem__("path", "artifacts/runtime-hardware-verifier")),
        ]
        accepted = []
        for name, mutate in candidate_mutations:
            changed = deepcopy(manifest)
            mutate(changed)
            try:
                validate_candidate(changed, local_contract, local_contract_path, root=test_root)
            except G5ContractError:
                continue
            accepted.append(name)
        if accepted:
            raise G5ContractError(f"candidate selftest accepted mutations: {accepted}")
    print(
        "v2-capability-carrier-internal-g5: SELFTEST PASS "
        f"contract_mutations={len(mutations)} candidate_mutations={len(candidate_mutations)} "
        "artifact_parity=exact receipt_verifiers=bound"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    subparsers.add_parser("selftest")
    verify = subparsers.add_parser("verify-candidate")
    verify.add_argument("--manifest", type=Path, required=True)
    pack = subparsers.add_parser("pack-candidate")
    pack.add_argument("--artifact", action="append", default=[], required=True)
    pack.add_argument("--build-id", type=lambda value: int(value, 0), required=True)
    pack.add_argument("--source-commit", required=True)
    pack.add_argument("--out", type=Path, required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--out", type=Path)
    receipt = subparsers.add_parser("verify-receipt")
    receipt.add_argument("--receipt", type=Path, required=True)
    pack_receipt_parser = subparsers.add_parser("pack-receipt")
    pack_receipt_parser.add_argument("--manifest", type=Path, required=True)
    pack_receipt_parser.add_argument("--domain", action="append", default=[], required=True)
    pack_receipt_parser.add_argument("--out", type=Path, required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--manifest", type=Path, required=True)
    preflight.add_argument("--hw-package", type=Path, required=True)
    preflight.add_argument("--runtime-package", type=Path, required=True)
    preflight.add_argument("--out", type=Path, required=True)
    verify_pre = subparsers.add_parser("verify-preflight")
    verify_pre.add_argument("--manifest", type=Path, required=True)
    verify_pre.add_argument("--hw-package", type=Path, required=True)
    verify_pre.add_argument("--runtime-package", type=Path, required=True)
    verify_pre.add_argument("--receipt", type=Path, required=True)
    pack_hw = subparsers.add_parser("pack-hw")
    pack_hw.add_argument("--manifest", type=Path, required=True)
    pack_hw.add_argument("--runtime-overlays-manifest", type=Path, required=True)
    pack_hw.add_argument("--out", type=Path, required=True)
    verify_hw = subparsers.add_parser("verify-hw")
    verify_hw.add_argument("--manifest", type=Path, required=True)
    verify_hw.add_argument("--package", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        contract_path = args.contract.resolve()
        contract = _load(contract_path, "internal G5 contract")
        validate_contract(contract)
        if args.command == "selftest":
            selftest(contract_path)
        elif args.command == "check":
            cases = sum(len(domain["cases"]) for domain in contract["matrix"]["domains"])
            print(
                "v2-capability-carrier-internal-g5: PASS "
                f"status=verifier-bound profile={PROFILE_ID} cases={cases} "
                "shippable=false artifact_parity=exact receipt_verifiers=3"
            )
        elif args.command == "pack-candidate":
            pack_candidate(
                contract_path, contract, args.artifact, args.build_id,
                args.source_commit, args.out.resolve(),
            )
        elif args.command == "pack-receipt":
            pack_receipt(
                contract_path, contract, args.manifest,
                args.domain, args.out.resolve(),
            )
        elif args.command in {
            "verify-candidate", "plan", "pack-hw", "verify-hw", "preflight", "verify-preflight",
        }:
            manifest_path = args.manifest.resolve()
            manifest = _load(manifest_path, "internal G5 candidate")
            validate_candidate(manifest, contract, contract_path)
            if args.command == "verify-candidate":
                print(
                    "v2-capability-carrier-internal-g5-candidate: PASS "
                    f"build_id={manifest['build_id']} artifacts={len(manifest['artifacts'])} "
                    "shippable=false g5_claim=none"
                )
            elif args.command == "plan":
                value = build_plan(contract, manifest_path, manifest)
                if args.out is not None:
                    _write_json(args.out, value)
                    print(f"v2-capability-carrier-internal-g5-plan: WROTE {args.out}")
                else:
                    print(json.dumps(value, indent=2, sort_keys=True))
            elif args.command == "pack-hw":
                pack_hw_package(
                    manifest_path,
                    manifest,
                    args.runtime_overlays_manifest.resolve(),
                    args.out.resolve(),
                )
            elif args.command == "verify-hw":
                verify_hw_package(manifest_path, manifest, args.package.resolve())
            elif args.command == "preflight":
                write_preflight(
                    contract_path, contract, manifest_path, manifest,
                    args.hw_package.resolve(), args.runtime_package.resolve(), args.out.resolve(),
                )
            else:
                verify_preflight(
                    contract_path, contract, manifest_path, manifest,
                    args.hw_package.resolve(), args.runtime_package.resolve(), args.receipt.resolve(),
                )
        else:
            verify_receipt(contract_path, contract, args.receipt.resolve())
        return 0
    except (G5ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"v2-capability-carrier-internal-g5: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
