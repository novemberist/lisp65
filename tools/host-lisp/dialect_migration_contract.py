#!/usr/bin/env python3
"""Validate the fail-closed dialect-v1 to dialect-v2 migration policy."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_abi_ledger as ABI  # noqa: E402
import code_object_arity_contract as ARITY  # noqa: E402
import dialect_contract as V1  # noqa: E402
import runtime_export_hw_oracle as RUNTIME_HW  # noqa: E402
import v2_capability_carrier_contract as CAPABILITY_CARRIER  # noqa: E402
import dialect_v2_r2_decisions as R2_DECISIONS  # noqa: E402
import block_bank_delta_policy as BANK_DELTA  # noqa: E402


DEFAULT_CONTRACT = ROOT / "config" / "dialect-migration-contract.json"
DEFAULT_SELECTION = ROOT / "config" / "dialect-profile-selection.json"
PROMOTION_REGISTER = ROOT / "config" / "promotion-register.json"
FORMAT = "lisp65-dialect-migration-contract-v1"
SELECTION_FORMAT = "lisp65-dialect-profile-selection-v1"
FAMILY_ORDER = ["prelude-control", "lists", "strings", "system-runtime", "ide"]
DISPOSITIONS = {"keep", "move-library", "internalize", "redefine", "replace", "remove-v2"}
ROLES = {"core", "workbench", "library", "internal", "removed"}
DELIVERIES = {
    "unchanged", "bank0-native", "bank5-preload", "disk-on-demand",
    "runtime-local", "build-only", "none",
}
FROZEN_SYNTAX = [
    "and", "case", "cond", "defmacro", "defun", "dolist", "dotimes", "function",
    "if", "lambda", "let", "let*", "or", "progn", "quasiquote", "quote", "setq",
    "unless", "unquote", "unquote-splicing", "when",
]
FROZEN_LAMBDA_MARKERS = ["&rest"]
TARGET_LAMBDA_MARKERS = ["&optional", "&rest"]
FROZEN_LAMBDA_LIST_FORMS = ["dotted", "fixed", "rest-marker", "variadic-symbol"]
TARGET_LAMBDA_LIST_FORMS = ["fixed", "optional-marker", "rest-marker"]
FROZEN_READER_TOKENS = ["#'", "'", ",", ",@", ".", "`"]
FROZEN_DEFERRED_CONTROL_FORMS = ["catch", "on-error", "throw"]
FROZEN_RETAINED_MACROS = [
    "and", "case", "cond", "defun", "dolist", "dotimes", "let", "let*",
    "or", "unless", "when",
]
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
DECISION_ANCHOR = re.compile(r"^decision:([a-z][a-z0-9-]*)$")
DECISION_ALIASES = {
    "string-character-list-removal": "string-list-conversion-removal",
}
MATRIX_CASES = {
    "runtime-export": {
        "bitflip": ("r5-global-g5-runtime-bitflip", "terminal-preload-error-detail-3", "lisp65-dialect-v2-runtime-g5-case-evidence-v1"),
        "build-id-mismatch": ("r5-global-g5-runtime-build-id-mismatch", "terminal-preload-error-detail-2", "lisp65-dialect-v2-runtime-g5-case-evidence-v1"),
        "clean": ("r5-global-g5-runtime-clean", "result-42", "lisp65-dialect-v2-runtime-g5-case-evidence-v1"),
        "truncated": ("r5-global-g5-runtime-truncated", "terminal-preload-error-detail-1", "lisp65-dialect-v2-runtime-g5-case-evidence-v1"),
    },
    "workbench-persistence": {
        "bam-alloc": ("r5-global-g5-workbench-bam-alloc", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "bam-read": ("r5-global-g5-workbench-bam-read", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "chain-write": ("r5-global-g5-workbench-chain-write", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "dir-write": ("r5-global-g5-workbench-dir-write", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "save-new": ("r5-global-g5-workbench-save-new", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "save-new-scan": ("r5-global-g5-workbench-save-new-scan", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "save-new-var": ("r5-global-g5-workbench-save-new-var", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
    },
    "workbench-ux": {
        "overlay-stack-guard": ("r5-global-g5-workbench-overlay-stack-guard", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "stdlib-runtime": ("r5-global-g5-workbench-stdlib-runtime", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
        "ux-complete": ("r5-global-g5-workbench-ux-complete", "pass", "lisp65-dialect-v2-workbench-g5-case-evidence-v1"),
    },
}


class MigrationError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MigrationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise MigrationError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except MigrationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MigrationError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        raise MigrationError(f"{label} keys drift: missing={missing} unknown={unknown}")
    return value


def _string(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise MigrationError(f"{label} must be a non-empty string")
    return value


def _path(value: Any, label: str, *, nullable: bool = False) -> Path | None:
    text = _string(value, label, nullable=nullable)
    if text is None:
        return None
    path = PurePosixPath(text)
    if path.is_absolute() or path.as_posix() != text or ".." in path.parts:
        raise MigrationError(f"{label} must be a canonical repository path")
    return ROOT / text


def _strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise MigrationError(f"{label} must be a string list")
    if nonempty and not value:
        raise MigrationError(f"{label} must not be empty")
    if value != sorted(set(value)):
        raise MigrationError(f"{label} must be sorted and duplicate-free")
    return value


def _decision_contract(value: Any) -> set[str]:
    path = _bound_sha(
        _exact(value, {"path", "sha256"}, "decision_contract")["path"],
        value["sha256"],
        "decision contract",
    )
    contract = load_json(path, "R2 decision contract")
    try:
        R2_DECISIONS.validate(contract)
    except R2_DECISIONS.DecisionError as exc:
        raise MigrationError(f"R2 decision contract is invalid: {exc}") from exc
    return {item["id"] for item in contract["decisions"]}


def _open_decisions(
    value: Any, decided_ids: set[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise MigrationError("open_decisions must be a list")
    decisions: dict[str, dict[str, Any]] = {}
    decision_ids: list[str] = []
    for index, raw in enumerate(value):
        keys = {"id", "status", "blocks_profile_switch"}
        if isinstance(raw, dict) and raw.get("status") == "decided":
            keys.add("contract_ref")
        item = _exact(raw, keys, f"open_decisions[{index}]")
        decision_id = _string(item["id"], f"open_decisions[{index}].id") or ""
        if not re.fullmatch(r"[a-z][a-z0-9-]*", decision_id):
            raise MigrationError(f"open_decisions[{index}].id is not canonical")
        if item["status"] not in {"pending", "resolved", "decided"} or type(item["blocks_profile_switch"]) is not bool:
            raise MigrationError("open decision status/switch flag is invalid")
        if item["status"] == "decided":
            expected_ref = f"dialect-v2-r2-decisions:{decision_id}"
            if decision_id not in decided_ids or item["contract_ref"] != expected_ref:
                raise MigrationError("decided migration decision reference drift")
        decision_ids.append(decision_id)
        decisions[decision_id] = item
    if decision_ids != sorted(set(decision_ids)):
        raise MigrationError("open decisions must be sorted and unique")
    return decisions


def _decision_anchor(
    value: Any,
    decisions: dict[str, dict[str, Any]],
    label: str,
) -> str | None:
    anchor = _string(value, label, nullable=True)
    if anchor is None:
        return None
    match = DECISION_ANCHOR.fullmatch(anchor)
    if match is None:
        raise MigrationError(f"{label} must be null or decision:<id>")
    decision_id = DECISION_ALIASES.get(match.group(1), match.group(1))
    decision = decisions.get(decision_id)
    if decision is None:
        raise MigrationError(f"{label} references an unknown decision")
    if decision["status"] not in {"resolved", "decided"}:
        raise MigrationError(f"{label} references an unresolved decision")
    return anchor


def _artifact_arity_contract(
    value: Any,
    decisions: dict[str, dict[str, Any]],
) -> None:
    item = _exact(
        value,
        {"decision", "path", "sha256", "source_lowering"},
        "artifact_arity_contract",
    )
    _decision_anchor(item["decision"], decisions, "artifact_arity_contract.decision")
    path = _bound_sha(item["path"], item["sha256"], "artifact_arity_contract")
    try:
        contract = ARITY._load(path)
        ARITY._contract_values(contract)
        ARITY._validate_contract_sections(contract)
    except ARITY.ContractError as exc:
        raise MigrationError(f"artifact arity contract is invalid: {exc}") from exc
    lowering = _exact(
        item["source_lowering"],
        {"optional", "syntax_snapshot", "omitted_value", "explicit_nil_distinguishable"},
        "artifact_arity_contract.source_lowering",
    )
    semantics = contract["semantics"]
    profiles = contract["profiles"]
    if (
        item["decision"] != "decision:strict-arity-codeobject"
        or semantics["required_count"] != "nargs - optional_count"
        or semantics["strict_fixed"] != "required_count <= actual_count <= nargs"
        or semantics["strict_rest"] != "required_count <= actual_count"
        or profiles["dialect-v1"]["emits_strict_arity"] is not False
        or profiles["dialect-v2"]["emits_strict_arity"] is not True
        or lowering != {
            "optional": "dialect-v2-bare-symbols",
            "syntax_snapshot": "required* [&optional optional*] [&rest rest]",
            "omitted_value": "nil",
            "explicit_nil_distinguishable": False,
        }
    ):
        raise MigrationError("artifact arity contract drift")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_value(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or len(value) != 64:
        raise MigrationError(f"{label} must be a lowercase SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise MigrationError(f"{label} must be a lowercase SHA-256") from exc
    if value != value.lower():
        raise MigrationError(f"{label} must be lowercase")
    return value


def _bound_sha(path_value: Any, sha_value: Any, label: str) -> Path:
    path = _path(path_value, f"{label}.path")
    expected = _sha_value(sha_value, f"{label}.sha256")
    if path is None or not path.is_file() or _sha(path) != expected:
        raise MigrationError(f"{label} SHA binding drift")
    return path


def _sealed_snapshot_contains(path_text: str, expected: str) -> bool:
    """Resolve historical evidence only through an intact registered archive."""
    register = load_json(PROMOTION_REGISTER, "promotion register")
    promotions = register.get("promotions")
    if not isinstance(promotions, list):
        raise MigrationError("promotion register lacks promotions")
    member_name = f"payload/{path_text}"
    for index, raw in enumerate(promotions):
        if not isinstance(raw, dict):
            raise MigrationError(f"promotion register item {index} must be an object")
        archive_text = raw.get("archive")
        archive_sha = raw.get("archive_sha256")
        if not isinstance(archive_text, str) or not isinstance(archive_sha, str):
            raise MigrationError(f"promotion register item {index} archive binding drift")
        archive = _path(archive_text, f"promotion register item {index}.archive")
        bound_archive_sha = _sha_value(
            archive_sha, f"promotion register item {index}.archive_sha256"
        )
        if (
            archive is None or archive.is_symlink() or not archive.is_file()
            or _sha(archive) != bound_archive_sha
        ):
            raise MigrationError(f"promotion register archive drift: {raw.get('id', index)}")
        try:
            with tarfile.open(archive, mode="r:gz") as bundle:
                try:
                    member = bundle.getmember(member_name)
                except KeyError:
                    continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise MigrationError(
                        f"promotion archive evidence is not a regular file: {member_name}"
                    )
                stream = bundle.extractfile(member)
                if stream is None:
                    raise MigrationError(
                        f"promotion archive evidence is unreadable: {member_name}"
                    )
                if hashlib.sha256(stream.read()).hexdigest() == expected:
                    return True
        except (OSError, tarfile.TarError) as exc:
            raise MigrationError(f"cannot read promotion archive {archive}: {exc}") from exc
    return False


def _historical_evidence_sha(path_value: Any, sha_value: Any, label: str) -> None:
    path_text = _string(path_value, f"{label}.path")
    path = _path(path_text, f"{label}.path")
    expected = _sha_value(sha_value, f"{label}.sha256")
    if path is not None and path.is_file() and _sha(path) == expected:
        return
    if path_text is not None and expected is not None and _sealed_snapshot_contains(path_text, expected):
        return
    raise MigrationError(f"{label} SHA binding drift in live tree and sealed snapshots")


def _commit(value: Any, label: str) -> str:
    commit = _string(value, label)
    if commit is None or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise MigrationError(f"{label} must be a full lowercase commit id")
    result = subprocess.run(
        ["git", "cat-file", "-e", commit + "^{commit}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise MigrationError(f"{label} does not resolve to a commit")
    return commit


def _git_blob_sha(commit: str, repository_path: str, label: str) -> str:
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{repository_path}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"").decode("utf-8", "replace").strip()
        raise MigrationError(f"cannot read {label} from frozen commit: {detail or exc}") from exc
    return hashlib.sha256(result.stdout).hexdigest()


def _git_binding_sha_at_contract_commit(
    contract_path: Path, repository_path: str, label: str,
) -> str:
    """Read a historical binding from the commit that last changed its contract.

    Migration evidence predates the sealed-archive rule and binds the G5 matrix
    at the contract's own Git snapshot.  Later harness-only matrix changes must
    not force that historical contract (and all family evidence derived from
    it) to move.  The fallback is intentionally limited to the single commit
    that last changed the contract, rather than accepting any matching blob in
    repository history.
    """
    try:
        contract_relative = contract_path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise MigrationError("migration contract must be inside the repository") from exc
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", contract_relative],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "").strip()
        raise MigrationError(
            f"cannot resolve {label} contract snapshot: {detail or exc}"
        ) from exc
    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise MigrationError(f"cannot resolve {label} contract snapshot commit")
    return _git_blob_sha(commit, repository_path, label)


def _g5_matrix(
    path: Path, *, allow_unbound_verifiers: bool,
) -> tuple[dict[str, tuple[str, str, str, str, str | None]], set[str]]:
    value = load_json(path, "dialect-v2 G5 matrix")
    _exact(value, {"format", "version", "id", "domains", "receipt"}, "G5 matrix")
    if (
        value["format"] != "lisp65-dialect-v2-g5-matrix-v1"
        or value["version"] != 1
        or value["id"] != "dialect-v2-product-switch"
    ):
        raise MigrationError("G5 matrix identity drift")
    domains = value["domains"]
    if not isinstance(domains, list) or [item.get("id") for item in domains] != sorted(MATRIX_CASES):
        raise MigrationError("G5 matrix domain order/coverage drift")
    flattened: dict[str, tuple[str, str, str, str, str | None]] = {}
    for index, raw in enumerate(domains):
        domain = _exact(
            raw, {"id", "verifier", "verifier_sha256", "cases"},
            f"G5 matrix domains[{index}]",
        )
        domain_id = domain["id"]
        verifier_path = _path(domain["verifier"], f"G5 matrix domain {domain_id}.verifier")
        verifier_sha = _sha_value(
            domain["verifier_sha256"], f"G5 matrix domain {domain_id}.verifier_sha256",
            nullable=True,
        )
        if verifier_path is None:
            raise MigrationError(f"G5 matrix domain {domain_id} verifier path is missing")
        if verifier_sha is None:
            if not allow_unbound_verifiers:
                raise MigrationError(f"G5 matrix domain {domain_id} verifier is not implementation-bound")
        elif not verifier_path.is_file() or _sha(verifier_path) != verifier_sha:
            raise MigrationError(f"G5 matrix domain {domain_id} verifier SHA binding drift")
        cases = domain["cases"]
        expected = MATRIX_CASES[domain_id]
        if not isinstance(cases, list) or [item.get("id") for item in cases] != sorted(expected):
            raise MigrationError(f"G5 matrix domain {domain_id} case coverage/order drift")
        for case_index, case_raw in enumerate(cases):
            case = _exact(
                case_raw,
                {"id", "target", "expected", "evidence_format"},
                f"G5 matrix {domain_id}[{case_index}]",
            )
            case_id = case["id"]
            if (case["target"], case["expected"], case["evidence_format"]) != expected[case_id]:
                raise MigrationError(f"G5 matrix case {domain_id}/{case_id} drift")
            flattened[f"{domain_id}/{case_id}"] = (
                *expected[case_id], domain["verifier"], verifier_sha,
            )
    receipt = _exact(
        value["receipt"],
        {
            "format", "required_bindings", "case_coverage", "physical_cycle_ids",
            "case_evidence", "runtime_cycle_ids",
        },
        "G5 matrix receipt",
    )
    bindings = [
        "candidate-build-id", "candidate-manifest-sha256", "dialect-v2-contract-sha256",
        "family-measurement-report-sha256s", "matrix-contract-sha256",
        "migration-contract-sha256", "physical-cycle-ids", "profile-id",
    ]
    if receipt != {
        "format": "lisp65-dialect-v2-g5-receipt-v1",
        "required_bindings": bindings,
        "case_coverage": "exactly-once",
        "physical_cycle_ids": "nonempty-unique-safe-identifiers",
        "case_evidence": "path-sha-format-native-receipt-verifier-and-raw-artifact-bound",
        "runtime_cycle_ids": "distinct-per-runtime-case",
    }:
        raise MigrationError("G5 matrix receipt policy drift")
    return flattened, set(MATRIX_CASES)


def _public_inventory(v1: dict[str, Any]) -> tuple[set[str], dict[str, set[str]], dict[str, str]]:
    names: set[str] = set()
    surfaces: dict[str, set[str]] = {}
    deliveries: dict[str, str] = {}
    for surface in v1["current_surfaces"]:
        deliveries[surface["id"]] = surface["delivery"]
        for name in surface["public_names"]:
            names.add(name)
            surfaces.setdefault(name, set()).add(surface["id"])
    return names, surfaces, deliveries


def _classification(
    value: Any,
    public: set[str],
    surfaces: dict[str, set[str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    item = _exact(
        value,
        {"policy", "internal_rules", "new_names", "pattern_groups", "name_groups", "replacements", "removals"},
        "classification",
    )
    expected_policy = {
        "scope": "all-resolved-v1-public-names",
        "public_coverage": "exactly-once",
        "new_public_definition": "explicit-classification-required",
        "unclassified": "fail",
        "ambiguous": "fail",
        "catch_all": "forbidden",
        "replacement_aliases_at_runtime": "forbidden",
    }
    if item["policy"] != expected_policy:
        raise MigrationError("classification policy drift")
    if item["internal_rules"] != [
        "descriptor-non-export", "percent-prefix", "private-inline-manifest"
    ]:
        raise MigrationError("internal classification rules drift")

    new_names: dict[str, dict[str, Any]] = {}
    new_keys = {"name", "family", "target_role", "target_delivery", "target_library"}
    if not isinstance(item["new_names"], list):
        raise MigrationError("classification.new_names must be a list")
    previous = ""
    for index, raw in enumerate(item["new_names"]):
        record = _exact(raw, new_keys, f"classification.new_names[{index}]")
        name = _string(record["name"], f"classification.new_names[{index}].name")
        if name is None or name <= previous or name in public or name in new_names:
            raise MigrationError("new v2 names must be sorted, unique, and absent from v1")
        if record["family"] not in FAMILY_ORDER:
            raise MigrationError(f"new v2 name {name} uses an unknown family")
        role = record["target_role"]
        delivery = record["target_delivery"]
        library = record["target_library"]
        if role not in {"core", "workbench", "library"}:
            raise MigrationError(f"new v2 name {name} has an invalid target")
        if role == "core":
            if delivery not in {"bank0-native", "bank5-preload"} or library is not None:
                raise MigrationError(f"new v2 core name {name} has an invalid delivery/library")
        elif (
            delivery not in {"bank5-preload", "disk-on-demand"}
            or not isinstance(library, str)
            or not library
        ):
            raise MigrationError(f"new v2 library/workbench name {name} lacks a runtime library")
        new_names[name] = record
        previous = name

    resolved: dict[str, dict[str, Any]] = {}
    group_keys = {
        "id", "family", "disposition", "target_role", "target_delivery", "target_library", "names",
    }
    ids: set[str] = set()
    if not isinstance(item["name_groups"], list) or not item["name_groups"]:
        raise MigrationError("classification.name_groups must be non-empty")
    for index, raw in enumerate(item["name_groups"]):
        group = _exact(raw, group_keys, f"classification.name_groups[{index}]")
        group_id = _string(group["id"], f"classification.name_groups[{index}].id")
        names = _strings(group["names"], f"classification.name_groups[{index}].names", nonempty=True)
        if group_id in ids:
            raise MigrationError(f"duplicate classification group: {group_id}")
        ids.add(group_id)
        if group["disposition"] not in DISPOSITIONS or group["target_role"] not in ROLES:
            raise MigrationError(f"classification group {group_id} uses an invalid disposition/role")
        if group["family"] not in FAMILY_ORDER:
            raise MigrationError(f"classification group {group_id} uses an unknown family")
        if group["target_delivery"] not in DELIVERIES:
            raise MigrationError(f"classification group {group_id} uses an invalid delivery")
        library = group["target_library"]
        if library is not None and (not isinstance(library, str) or not library):
            raise MigrationError(f"classification group {group_id} target_library is invalid")
        if group["disposition"] == "move-library" and (
            group["target_role"] != "library" or group["target_delivery"] != "disk-on-demand" or library is None
        ):
            raise MigrationError(f"classification group {group_id} has an invalid library move")
        if group["disposition"] in {"replace", "remove-v2"} and (
            group["target_role"] != "removed" or group["target_delivery"] != "none" or library is not None
        ):
            raise MigrationError(f"classification group {group_id} has an invalid removal target")
        if group["disposition"] == "redefine" and (
            group["target_role"] in {"removed", "internal"}
            or group["target_delivery"] in {"none", "runtime-local", "build-only"}
        ):
            raise MigrationError(f"classification group {group_id} has an invalid redefine target")
        if group["disposition"] == "internalize" and group["target_role"] != "internal":
            raise MigrationError(f"classification group {group_id} must target internal")
        if group["disposition"] == "keep" and (
            group["target_role"] in {"internal", "removed"}
            or group["target_delivery"] in {"none", "runtime-local", "build-only"}
        ):
            raise MigrationError(f"classification group {group_id} has an invalid keep target")
        if group["target_role"] in {"library", "workbench"} and library is None:
            raise MigrationError(f"classification group {group_id} lacks target_library")
        if group["target_role"] not in {"library", "workbench"} and library is not None:
            raise MigrationError(f"classification group {group_id} has a spurious target_library")
        for name in names:
            if name in resolved:
                raise MigrationError(f"public name classified more than once: {name}")
            resolved[name] = group

    pattern_keys = {
        "id", "family", "surface_ids", "prefix", "except_names", "disposition",
        "target_role", "target_delivery", "target_library",
    }
    if not isinstance(item["pattern_groups"], list):
        raise MigrationError("classification.pattern_groups must be a list")
    for index, raw in enumerate(item["pattern_groups"]):
        pattern = _exact(raw, pattern_keys, f"classification.pattern_groups[{index}]")
        pattern_id = _string(pattern["id"], f"classification.pattern_groups[{index}].id")
        surface_ids = set(_strings(pattern["surface_ids"], f"pattern {pattern_id}.surface_ids", nonempty=True))
        exceptions = set(_strings(pattern["except_names"], f"pattern {pattern_id}.except_names"))
        prefix = _string(pattern["prefix"], f"pattern {pattern_id}.prefix")
        if (
            pattern_id in ids
            or pattern["family"] not in FAMILY_ORDER
            or pattern["disposition"] != "internalize"
            or pattern["target_role"] != "internal"
            or pattern["target_delivery"] != "runtime-local"
            or not isinstance(pattern["target_library"], str)
            or not pattern["target_library"]
        ):
            raise MigrationError(f"pattern group {pattern_id} is duplicate or invalid")
        ids.add(pattern_id)
        matched = {
            name for name in public
            if name.startswith(prefix or "") and surfaces[name] & surface_ids and name not in exceptions
        }
        if not matched:
            raise MigrationError(f"pattern group {pattern_id} is stale")
        stale_exceptions = exceptions - public
        if stale_exceptions:
            raise MigrationError(f"pattern group {pattern_id} has stale exceptions")
        for name in matched:
            if name in resolved:
                raise MigrationError(f"public name has exact and pattern classifications: {name}")
            resolved[name] = pattern

    missing = sorted(public - set(resolved))
    extra = sorted(set(resolved) - public)
    if missing or extra:
        raise MigrationError(f"public classification coverage drift: missing={missing} extra={extra}")

    replace_names = {
        name for name, group in resolved.items()
        if group["disposition"] in {"replace", "redefine"}
    }
    replacements: set[str] = set()
    replacement_targets: dict[str, str] = {}
    replacement_keys = {"name", "target", "rewrite", "semantic_status"}
    previous = ""
    for index, raw in enumerate(item["replacements"]):
        record = _exact(raw, replacement_keys, f"classification.replacements[{index}]")
        name = _string(record["name"], f"classification.replacements[{index}].name")
        target = _string(record["target"], f"classification.replacements[{index}].target")
        _string(record["rewrite"], f"classification.replacements[{index}].rewrite")
        if name is None or name <= previous or name in replacements:
            raise MigrationError("replacement records must be sorted and unique")
        if target not in public | set(new_names) | {"cond", "lambda"}:
            raise MigrationError(f"replacement target is not declared: {name}->{target}")
        if record["semantic_status"] not in {"specified", "pending"}:
            raise MigrationError(f"replacement {name} semantic_status is invalid")
        replacements.add(name)
        replacement_targets[name] = target
        previous = name
    if replacements != replace_names:
        raise MigrationError("replacement records do not exactly cover replace dispositions")
    surviving_targets = {
        name for name, group in resolved.items()
        if group["disposition"] in {"keep", "move-library", "redefine"}
    } | set(new_names) | {"cond", "lambda"}
    invalid_targets = sorted(
        f"{name}->{target}" for name, target in replacement_targets.items()
        if target not in surviving_targets
    )
    if invalid_targets:
        raise MigrationError(f"replacement targets are absent from dialect-v2: {invalid_targets}")

    remove_names = {name for name, group in resolved.items() if group["disposition"] == "remove-v2"}
    removals: set[str] = set()
    removal_keys = {"name", "reason", "replacement", "semantic_status"}
    previous = ""
    for index, raw in enumerate(item["removals"]):
        record = _exact(raw, removal_keys, f"classification.removals[{index}]")
        name = _string(record["name"], f"classification.removals[{index}].name")
        _string(record["reason"], f"classification.removals[{index}].reason")
        replacement = record["replacement"]
        if replacement is not None and replacement not in public | set(new_names):
            raise MigrationError(f"removal {name} replacement is not declared")
        if name is None or name <= previous or record["semantic_status"] not in {"specified", "pending"}:
            raise MigrationError("removal records must be sorted and valid")
        removals.add(name)
        previous = name
    if removals != remove_names:
        raise MigrationError("removal records do not exactly cover remove-v2 dispositions")
    return resolved, new_names, replacement_targets


def _syntax(value: Any) -> dict[str, Any]:
    item = _exact(
        value,
        {
            "coverage", "special_forms_current", "special_forms_target", "macro_migrations",
            "retained_macros", "lambda_list_forms_current", "lambda_list_forms_target",
            "lambda_markers_current", "lambda_markers_target", "reader_tokens",
            "deferred_control_forms",
        },
        "syntax",
    )
    if item["coverage"] != "explicit-v1-snapshot":
        raise MigrationError("syntax coverage policy drift")
    current = _strings(item["special_forms_current"], "syntax.special_forms_current", nonempty=True)
    target = _strings(item["special_forms_target"], "syntax.special_forms_target", nonempty=True)
    if current != FROZEN_SYNTAX or target != FROZEN_SYNTAX:
        raise MigrationError("AP8.3 must not change special forms")
    if (
        _strings(item["lambda_markers_current"], "syntax.lambda_markers_current", nonempty=True)
        != FROZEN_LAMBDA_MARKERS
        or _strings(item["lambda_markers_target"], "syntax.lambda_markers_target", nonempty=True)
        != TARGET_LAMBDA_MARKERS
    ):
        raise MigrationError("lambda-marker profile inventory drift")
    if (
        _strings(item["lambda_list_forms_current"], "syntax.lambda_list_forms_current", nonempty=True)
        != FROZEN_LAMBDA_LIST_FORMS
        or _strings(item["lambda_list_forms_target"], "syntax.lambda_list_forms_target", nonempty=True)
        != TARGET_LAMBDA_LIST_FORMS
    ):
        raise MigrationError("lambda-list form profile inventory drift")
    if _strings(item["reader_tokens"], "syntax.reader_tokens", nonempty=True) != FROZEN_READER_TOKENS:
        raise MigrationError("reader-token inventory drift")
    if (
        _strings(item["deferred_control_forms"], "syntax.deferred_control_forms", nonempty=True)
        != FROZEN_DEFERRED_CONTROL_FORMS
    ):
        raise MigrationError("deferred control-form inventory drift")
    retained_macros = _strings(item["retained_macros"], "syntax.retained_macros", nonempty=True)
    if retained_macros != FROZEN_RETAINED_MACROS:
        raise MigrationError("retained macro inventory drift")
    macros = item["macro_migrations"]
    if not isinstance(macros, list) or not macros:
        raise MigrationError("syntax.macro_migrations must be non-empty")
    names: list[str] = []
    target_macros = set(retained_macros)
    macro_projection = {
        family: {
            "loaded_symbol_delta": 0,
            "loaded_namepool_delta_bytes": 0,
            "boot_symbol_delta": 0,
            "boot_namepool_delta_bytes": 0,
            "directory_delta": 0,
        }
        for family in FAMILY_ORDER
    }
    for index, raw in enumerate(macros):
        record = _exact(
            raw,
            {
                "name", "disposition", "family", "source_delivery", "target_delivery",
                "target_library", "semantic_status",
            },
            f"macro[{index}]",
        )
        name = _string(record["name"], f"macro[{index}].name") or ""
        names.append(name)
        if record["disposition"] not in {"keep", "move-library", "remove-v2"}:
            raise MigrationError("macro disposition is invalid")
        family = record["family"]
        if family not in macro_projection or record["source_delivery"] != "bank5-preload":
            raise MigrationError("macro family/source delivery is invalid")
        expected_target = {
            "keep": ("bank5-preload", None),
            "move-library": ("disk-on-demand", record["target_library"]),
            "remove-v2": ("none", None),
        }[record["disposition"]]
        if (
            record["target_delivery"] != expected_target[0]
            or record["target_library"] != expected_target[1]
            or (record["disposition"] == "move-library" and not record["target_library"])
        ):
            raise MigrationError("macro target delivery/library is invalid")
        if record["semantic_status"] not in {"specified", "pending"}:
            raise MigrationError("macro semantic_status is invalid")
        if record["disposition"] != "remove-v2":
            target_macros.add(name)
        if record["disposition"] == "remove-v2":
            macro_projection[family]["loaded_symbol_delta"] -= 1
            macro_projection[family]["loaded_namepool_delta_bytes"] -= len(name) + 1
            macro_projection[family]["directory_delta"] -= 1
        if record["target_delivery"] != "bank5-preload":
            macro_projection[family]["boot_symbol_delta"] -= 1
            macro_projection[family]["boot_namepool_delta_bytes"] -= len(name) + 1
    if names != sorted(set(names)):
        raise MigrationError("macro migrations must be sorted and unique")
    compile_text = (ROOT / "src" / "compile.c").read_text(encoding="utf-8")
    match = re.search(r"static const char \*sf\[\]\s*=\s*\{(.*?)\};", compile_text, re.S)
    if not match:
        raise MigrationError("cannot resolve native compiler special-form inventory")
    native_forms = sorted(re.findall(r'"([^"]+)"', match.group(1)))
    expected_native = sorted(
        ["if", "when", "unless", "and", "or", "cond", "case", "let", "let*", "progn", "setq", "quote", "lambda", "function", "dotimes", "dolist"]
    )
    if native_forms != expected_native or not set(native_forms) <= set(current):
        raise MigrationError("native compiler special-form binding drift")
    macro_sources = [
        ROOT / "lib" / "prelude-m1.lisp",
        ROOT / "lib" / "stdlib-control.lisp",
        ROOT / "lib" / "stdlib-places.lisp",
    ]
    defined_macros: set[str] = set()
    for source in macro_sources:
        defined_macros.update(re.findall(r"^\(defmacro\s+([^\s()]+)", source.read_text(encoding="utf-8"), re.M))
    if set(names) & set(retained_macros):
        raise MigrationError("macro migration/retention partition overlaps")
    if set(names) | set(retained_macros) != defined_macros:
        raise MigrationError("macro migration/retention partition is not source-complete")
    reader_text = (ROOT / "src" / "reader.c").read_text(encoding="utf-8")
    for marker in ("quasiquote", "unquote", "unquote-splicing", "function"):
        if f'"{marker}"' not in reader_text:
            raise MigrationError(f"reader syntax binding missing marker {marker}")
    for source_token in (
        "c == '#' && rd_peek2() == '\\''", "c == '\\''", "c == '`'", "c == ','",
        "rd_peek() == '.' && is_delim(rd_peek2())",
    ):
        if source_token not in reader_text:
            raise MigrationError(f"reader syntax binding missing token implementation {source_token}")
    return {"target_public_macros": target_macros, "projection": macro_projection}


def _project(
    resolved: dict[str, dict[str, Any]],
    new_names: dict[str, dict[str, Any]],
    replacement_targets: dict[str, str],
    surfaces: dict[str, set[str]],
    macro_projection: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    result = {
        family: {
            "loaded_symbol_delta": 0,
            "loaded_namepool_delta_bytes": 0,
            "boot_symbol_delta": 0,
            "boot_namepool_delta_bytes": 0,
            "directory_delta": 0,
        }
        for family in FAMILY_ORDER
    }
    for name, group in resolved.items():
        family = group["family"]
        if family not in result:
            raise MigrationError(f"public name uses an unbudgeted family: {name}/{family}")
        disposition = group["disposition"]
        target_name = replacement_targets.get(name)
        drops_public_name = disposition in {"internalize", "remove-v2"} or (
            disposition == "replace" and target_name != name
        )
        current_directory = any(
            surface != "native-eval-and-p0-primitives" for surface in surfaces[name]
        )
        target_directory = current_directory
        if disposition == "remove-v2" or (disposition == "replace" and target_name != name):
            target_directory = False
        if drops_public_name:
            result[family]["loaded_symbol_delta"] -= 1
            result[family]["loaded_namepool_delta_bytes"] -= len(name) + 1
        current_boot = bool(
            surfaces[name]
            & {"native-eval-and-p0-primitives", "workbench-preload"}
        )
        drops_boot_name = disposition in {"move-library", "internalize", "remove-v2"} or (
            disposition == "replace" and target_name != name
        ) or group["target_delivery"] == "disk-on-demand"
        if current_boot and drops_boot_name:
            result[family]["boot_symbol_delta"] -= 1
            result[family]["boot_namepool_delta_bytes"] -= len(name) + 1
        result[family]["directory_delta"] += int(target_directory) - int(current_directory)
    for name, record in new_names.items():
        family = record["family"]
        if family not in result:
            raise MigrationError(f"new v2 name uses an unbudgeted family: {name}/{family}")
        result[family]["loaded_symbol_delta"] += 1
        result[family]["loaded_namepool_delta_bytes"] += len(name) + 1
        if record["target_delivery"] in {"bank0-native", "bank5-preload"}:
            result[family]["boot_symbol_delta"] += 1
            result[family]["boot_namepool_delta_bytes"] += len(name) + 1
        if record["target_delivery"] in {"bank5-preload", "runtime-local"}:
            result[family]["directory_delta"] += 1
    for family in FAMILY_ORDER:
        for key, delta in macro_projection[family].items():
            result[family][key] += delta
    return result


def _semantic_contract_registry() -> dict[str, dict[str, Any]]:
    registry = load_json(ROOT / "config" / "semantic-contracts.json", "semantic contract registry")
    contracts = registry.get("contracts")
    if not isinstance(contracts, list):
        raise MigrationError("semantic contract registry has no contracts")
    return {
        item["id"]: item for item in contracts
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _verify_family_semantics(family: str, contract_ids: list[str], registry: dict[str, dict[str, Any]]) -> None:
    expected_id = f"dialect-v2-{family}"
    if contract_ids != [expected_id] or expected_id not in registry:
        raise MigrationError(f"family {family} requires its exact namespaced semantic contract")
    contract = registry[expected_id]
    fixture = contract.get("fixture")
    engines = contract.get("required_engines")
    adapters = contract.get("adapters")
    if (
        contract.get("status") != "normative"
        or "host" not in contract.get("claims", [])
        or not isinstance(fixture, dict)
        or fixture.get("format") != f"lisp65-dialect-v2-{family}-cases-v1"
        or not isinstance(engines, list)
        or len(set(engines)) < 2
        or not isinstance(adapters, list)
    ):
        raise MigrationError(f"family {family} semantic contract is not a v2 differential contract")
    cases_engines = {
        adapter.get("engine") for adapter in adapters
        if isinstance(adapter, dict) and adapter.get("mode") == "cases"
    }
    if not set(engines) <= cases_engines:
        raise MigrationError(f"family {family} semantic contract lacks cases adapters")


def _budget_artifact_manifest(
    path_value: Any,
    sha_value: Any,
    family: str,
    profile: str,
    label: str,
) -> tuple[str, dict[str, int]]:
    path = _bound_sha(path_value, sha_value, label)
    manifest_sha = _sha(path)
    value = load_json(path, label)
    _exact(
        value,
        {
            "format", "profile", "family", "loaded_symbols", "boot_symbols",
            "directory_entries", "artifact",
        },
        label,
    )
    if (
        value["format"] != "lisp65-dialect-family-artifact-v1"
        or value["profile"] != profile
        or value["family"] != family
    ):
        raise MigrationError(f"{label} identity drift")
    loaded_symbols = _strings(value["loaded_symbols"], f"{label}.loaded_symbols")
    boot_symbols = _strings(value["boot_symbols"], f"{label}.boot_symbols")
    if not set(boot_symbols) <= set(loaded_symbols):
        raise MigrationError(f"{label} boot symbols must be a subset of loaded symbols")
    directory_entries = _strings(value["directory_entries"], f"{label}.directory_entries")
    artifact = _exact(value["artifact"], {"path", "sha256"}, f"{label}.artifact")
    artifact_path = _bound_sha(artifact["path"], artifact["sha256"], f"{label}.artifact")
    metrics = {
        "loaded_symbols": len(loaded_symbols),
        "loaded_namepool_bytes": sum(len(name) + 1 for name in loaded_symbols),
        "boot_symbols": len(boot_symbols),
        "boot_namepool_bytes": sum(len(name) + 1 for name in boot_symbols),
        "directory_entries": len(directory_entries),
        "artifact_bytes": artifact_path.stat().st_size,
    }
    return manifest_sha, metrics


def _family_verdict_cases(
    path_value: Any,
    sha_value: Any,
    family: str,
    profile: str,
    engine_id: str,
    fixture_sha: str,
    fixture_cases: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _bound_sha(path_value, sha_value, f"family {family} engine {engine_id} {profile} verdict")
    verdict = load_json(path, f"family {family} engine {engine_id} {profile} verdict")
    _exact(
        verdict,
        {"format", "family", "profile", "engine", "fixture_sha256", "provenance", "cases"},
        f"family {family} engine {engine_id} {profile} verdict",
    )
    if (
        verdict["format"] != "lisp65-dialect-v2-family-verdict-v1"
        or verdict["family"] != family
        or verdict["profile"] != profile
        or verdict["engine"] != engine_id
        or verdict["fixture_sha256"] != fixture_sha
        or not isinstance(verdict["cases"], list)
        or not verdict["cases"]
    ):
        raise MigrationError(f"family {family} engine {engine_id} {profile} verdict drift")
    provenance = _exact(
        verdict["provenance"],
        {"source_commit", "binary_sha256", "build_profile_sha256", "preload_sha256"},
        f"family {family} engine {engine_id} {profile} provenance",
    )
    source_commit = provenance["source_commit"]
    if source_commit is not None and (
        not isinstance(source_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
    ):
        raise MigrationError(f"family {family} engine {engine_id} {profile} source commit is invalid")
    for key in ("binary_sha256", "build_profile_sha256", "preload_sha256"):
        _sha_value(provenance[key], f"family {family} engine {engine_id} {profile} {key}")
    case_ids: list[str] = []
    for case_index, raw_case in enumerate(verdict["cases"]):
        case = _exact(
            raw_case, {"id", "verdict", "result_sha256", "decision"},
            f"family {family} engine {engine_id} {profile} cases[{case_index}]",
        )
        case_id = _string(case["id"], f"family {family} verdict case id") or ""
        case_ids.append(case_id)
        result_sha = _sha_value(
            case["result_sha256"], f"family {family} verdict case result SHA"
        )
        anchor = _decision_anchor(
            case["decision"], decisions,
            f"family {family} engine {engine_id} {profile} cases[{case_index}].decision",
        )
        if case_id in fixture_cases:
            expected = fixture_cases[case_id]["observations"][profile][engine_id]
            expected_sha = _family_observation_sha(expected)
            if (
                case["verdict"] != "accept"
                or result_sha != expected_sha
                or anchor != fixture_cases[case_id]["migration_anchor"]
            ):
                raise MigrationError(
                    f"family {family} engine {engine_id} {profile} case {case_id} observation binding drift"
                )
    if case_ids != list(fixture_cases):
        raise MigrationError(f"family {family} verdict cases do not exactly cover the fixture")
    return verdict["cases"], provenance


def _family_observation_sha(observation: str) -> str:
    return hashlib.sha256(observation.encode("utf-8")).hexdigest()


def _family_fixture_cases(
    fixture: dict[str, Any],
    family: str,
    required_engines: list[str],
    decisions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    _exact(
        fixture,
        {"format", "profile", "family", "cases"},
        f"family {family} semantic fixture",
    )
    if (
        fixture["format"] != f"lisp65-dialect-v2-{family}-cases-v1"
        or fixture["profile"] != "dialect-v1-v2-differential"
        or fixture["family"] != family
        or not isinstance(fixture["cases"], list)
        or not fixture["cases"]
    ):
        raise MigrationError(f"family {family} semantic fixture identity drift")
    cases: dict[str, dict[str, Any]] = {}
    case_ids: list[str] = []
    for index, raw_case in enumerate(fixture["cases"]):
        case_keys = {"id", "forms", "migration_anchor", "observations"}
        if family == "lists":
            case_keys.add("tier")
        case = _exact(
            raw_case, case_keys,
            f"family {family} fixture case {index}",
        )
        case_id = _string(case["id"], f"family {family} fixture case {index}.id") or ""
        if family == "lists" and case["tier"] not in {"core", "library"}:
            raise MigrationError(f"family {family} fixture case {case_id}.tier is invalid")
        forms = case["forms"]
        if not isinstance(forms, list) or not forms or any(
            not isinstance(form, str) or not form.strip() or form != form.strip()
            for form in forms
        ):
            raise MigrationError(f"family {family} fixture case {case_id}.forms is invalid")
        anchor = _decision_anchor(
            case["migration_anchor"], decisions,
            f"family {family} fixture case {index}.migration_anchor",
        )
        observations = _exact(
            case["observations"], {"dialect-v1", "dialect-v2"},
            f"family {family} fixture case {case_id}.observations",
        )
        normalized: dict[str, dict[str, str]] = {}
        for profile in ("dialect-v1", "dialect-v2"):
            engine_observations = _exact(
                observations[profile], set(required_engines),
                f"family {family} fixture case {case_id}.{profile}",
            )
            normalized[profile] = {}
            for engine_id in required_engines:
                observation = _string(
                    engine_observations[engine_id],
                    f"family {family} fixture case {case_id}.{profile}.{engine_id}",
                ) or ""
                if observation != observation.strip():
                    raise MigrationError(
                        f"family {family} fixture case {case_id}.{profile}.{engine_id} is not canonical"
                    )
                normalized[profile][engine_id] = observation
        differs = any(
            normalized["dialect-v1"][engine_id]
            != normalized["dialect-v2"][engine_id]
            for engine_id in required_engines
        )
        if not differs and anchor is not None:
            raise MigrationError(
                f"family {family} fixture case {case_id} has an anchor without an observation difference"
            )
        if differs and anchor is None:
            raise MigrationError(
                f"family {family} fixture case {case_id} differs without a resolved decision anchor"
            )
        case_ids.append(case_id)
        cases[case_id] = {
            "migration_anchor": anchor,
            "observations": normalized,
        }
    if case_ids != sorted(set(case_ids)):
        raise MigrationError(f"family {family} fixture cases must be sorted and unique")
    return cases


def _require_conformant_family_verdicts(
    baseline_path: Any,
    baseline_sha: Any,
    candidate_path: Any,
    candidate_sha: Any,
    family: str,
    engine_id: str,
    fixture_sha: str,
    fixture_cases: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _baseline_cases, baseline = _family_verdict_cases(
        baseline_path, baseline_sha, family, "dialect-v1", engine_id, fixture_sha,
        fixture_cases, decisions,
    )
    _candidate_cases, candidate = _family_verdict_cases(
        candidate_path, candidate_sha, family, "dialect-v2", engine_id, fixture_sha,
        fixture_cases, decisions,
    )
    return baseline, candidate


def _validate_family_internal_accounting(
    records: Any, family: str
) -> None:
    if not isinstance(records, list) or len(records) != 2:
        raise MigrationError(f"family {family} internal accounting coverage drift")
    profiles: list[str] = []
    role_keys = {
        "image_sha256", "public_definitions", "native_public_bindings",
        "percent_definitions", "declared_percent_definitions",
        "generated_definitions", "referenced_only_names", "directory_entries",
        "namepool_bytes", "arity",
    }
    for index, raw in enumerate(records):
        record = _exact(
            raw, {"profile", "path", "sha256"},
            f"family {family} internal_accounting[{index}]",
        )
        profile = _string(record["profile"], f"family {family} accounting profile") or ""
        profiles.append(profile)
        path = _bound_sha(
            record["path"], record["sha256"],
            f"family {family} {profile} internal accounting",
        )
        value = load_json(path, f"family {family} {profile} internal accounting")
        _exact(
            value, {"format", "family", "profile", "source_commit", "roles"},
            f"family {family} {profile} internal accounting",
        )
        if (
            value["format"] != "lisp65-dialect-family-internal-accounting-v1"
            or value["family"] != family
            or value["profile"] != profile
        ):
            raise MigrationError(f"family {family} {profile} internal accounting identity drift")
        source_commit = value["source_commit"]
        if (
            (profile == "dialect-v1" and (
                not isinstance(source_commit, str)
                or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
            ))
            or (profile == "dialect-v2" and source_commit is not None)
        ):
            raise MigrationError(
                f"family {family} {profile} internal accounting source binding drift"
            )
        roles = _exact(
            value["roles"], {"loaded", "boot"},
            f"family {family} {profile} internal accounting roles",
        )
        for role_name, role in roles.items():
            role = _exact(
                role, role_keys,
                f"family {family} {profile} internal accounting {role_name}",
            )
            _sha_value(
                role["image_sha256"],
                f"family {family} {profile} internal accounting {role_name} image",
            )
            name_sets: dict[str, set[str]] = {}
            for key in (
                "public_definitions", "native_public_bindings", "percent_definitions",
                "declared_percent_definitions", "generated_definitions",
                "referenced_only_names",
            ):
                name_sets[key] = set(_strings(
                    role[key],
                    f"family {family} {profile} internal accounting {role_name}.{key}",
                ))
            if any(name.startswith("%") for name in role["referenced_only_names"]):
                raise MigrationError(
                    f"family {family} {profile} {role_name} leaks a private dependency"
                )
            if not isinstance(role["directory_entries"], dict) or not isinstance(
                role["namepool_bytes"], dict
            ) or not isinstance(role["arity"], list):
                raise MigrationError(
                    f"family {family} {profile} {role_name} accounting payload drift"
                )
            directory = _exact(
                role["directory_entries"],
                {
                    "public", "native_public_outside_l65m", "percent_internal",
                    "generated_internal", "total",
                },
                f"family {family} {profile} {role_name} directory accounting",
            )
            namepool = _exact(
                role["namepool_bytes"],
                {
                    "public_definitions", "native_public_outside_l65m",
                    "percent_definitions", "generated_definitions",
                    "referenced_only", "total_unique_names",
                },
                f"family {family} {profile} {role_name} namepool accounting",
            )
            if any(not isinstance(value, int) or value < 0 for value in directory.values()):
                raise MigrationError(
                    f"family {family} {profile} {role_name} directory accounting drift"
                )
            if any(not isinstance(value, int) or value < 0 for value in namepool.values()):
                raise MigrationError(
                    f"family {family} {profile} {role_name} namepool accounting drift"
                )
            if directory["total"] != (
                directory["public"] + directory["percent_internal"]
                + directory["generated_internal"]
            ):
                raise MigrationError(
                    f"family {family} {profile} {role_name} directory total drift"
                )
            if (
                name_sets["percent_definitions"]
                != name_sets["declared_percent_definitions"]
                or any(
                    left & right
                    for left_index, left in enumerate(
                        (
                            name_sets["public_definitions"],
                            name_sets["percent_definitions"],
                            name_sets["generated_definitions"],
                            name_sets["referenced_only_names"],
                        )
                    )
                    for right in (
                        name_sets["public_definitions"],
                        name_sets["percent_definitions"],
                        name_sets["generated_definitions"],
                        name_sets["referenced_only_names"],
                    )[left_index + 1:]
                )
                or name_sets["native_public_bindings"] & (
                    name_sets["public_definitions"]
                    | name_sets["percent_definitions"]
                    | name_sets["generated_definitions"]
                )
            ):
                raise MigrationError(
                    f"family {family} {profile} {role_name} accounting classes overlap"
                )
            if (
                directory["public"] != len(name_sets["public_definitions"])
                or directory["native_public_outside_l65m"]
                != len(name_sets["native_public_bindings"])
                or directory["percent_internal"] != len(name_sets["percent_definitions"])
                or directory["generated_internal"] != len(name_sets["generated_definitions"])
            ):
                raise MigrationError(
                    f"family {family} {profile} {role_name} directory class count drift"
                )
            expected_namepool = {
                "public_definitions": sum(
                    len(name) + 1 for name in name_sets["public_definitions"]
                ),
                "native_public_outside_l65m": sum(
                    len(name) + 1 for name in name_sets["native_public_bindings"]
                ),
                "percent_definitions": sum(
                    len(name) + 1 for name in name_sets["percent_definitions"]
                ),
                "generated_definitions": sum(
                    len(name) + 1 for name in name_sets["generated_definitions"]
                ),
                "referenced_only": sum(
                    len(name) + 1 for name in name_sets["referenced_only_names"]
                ),
            }
            expected_namepool["total_unique_names"] = sum(
                expected_namepool[key]
                for key in (
                    "public_definitions", "percent_definitions",
                    "generated_definitions", "referenced_only",
                )
            )
            if namepool != expected_namepool:
                raise MigrationError(
                    f"family {family} {profile} {role_name} namepool accounting drift"
                )
            arity_names: list[str] = []
            for arity_index, raw_arity in enumerate(role["arity"]):
                arity = _exact(
                    raw_arity,
                    {
                        "name", "class", "nargs", "nlocals", "flags",
                        "strict_arity", "optional_count", "rest",
                    },
                    f"family {family} {profile} {role_name} arity[{arity_index}]",
                )
                arity_names.append(
                    _string(
                        arity["name"],
                        f"family {family} {profile} {role_name} arity name",
                    ) or ""
                )
                if (
                    arity["class"] not in {
                        "public", "percent-internal", "generated-internal"
                    }
                    or any(
                        not isinstance(arity[key], int) or arity[key] < 0
                        for key in ("nargs", "nlocals", "flags", "optional_count")
                    )
                    or not isinstance(arity["strict_arity"], bool)
                    or not isinstance(arity["rest"], bool)
                ):
                    raise MigrationError(
                        f"family {family} {profile} {role_name} arity accounting drift"
                    )
            if arity_names != sorted(set(arity_names)):
                raise MigrationError(
                    f"family {family} {profile} {role_name} arity inventory drift"
                )
            if set(arity_names) != (
                name_sets["public_definitions"]
                | name_sets["percent_definitions"]
                | name_sets["generated_definitions"]
            ):
                raise MigrationError(
                    f"family {family} {profile} {role_name} arity coverage drift"
                )
    if profiles != ["dialect-v1", "dialect-v2"]:
        raise MigrationError(f"family {family} internal accounting profile order drift")


def _validate_family_tier_artifacts(records: Any, family: str) -> None:
    if family != "lists":
        if records != []:
            raise MigrationError(f"family {family} must not publish tier artifacts")
        return
    if not isinstance(records, list) or len(records) != 2:
        raise MigrationError(f"family {family} tier artifact coverage drift")
    tiers: list[str] = []
    manifest_keys = {
        "format", "profile", "family", "tier", "descriptor", "descriptor_sha256",
        "source", "source_sha256", "provides", "requires", "private_definitions",
        "image_sha256", "image_bytes", "directory_entries", "code_bytes",
        "strict_arity",
    }
    for index, raw in enumerate(records):
        record = _exact(
            raw, {"tier", "image", "image_sha256", "manifest", "manifest_sha256"},
            f"family {family} tier_artifacts[{index}]",
        )
        tier = _string(record["tier"], f"family {family} tier id") or ""
        tiers.append(tier)
        image = _bound_sha(
            record["image"], record["image_sha256"],
            f"family {family} {tier} image",
        )
        manifest_path = _bound_sha(
            record["manifest"], record["manifest_sha256"],
            f"family {family} {tier} manifest",
        )
        manifest = load_json(manifest_path, f"family {family} {tier} manifest")
        _exact(manifest, manifest_keys, f"family {family} {tier} manifest")
        if (
            manifest["format"] != "lisp65-dialect-v2-family-tier-artifact-v1"
            or manifest["profile"] != "dialect-v2"
            or manifest["family"] != family
            or manifest["tier"] != tier
            or manifest["strict_arity"] is not True
            or manifest["image_sha256"] != record["image_sha256"]
            or manifest["image_bytes"] != image.stat().st_size
        ):
            raise MigrationError(f"family {family} {tier} manifest binding drift")
        descriptor_path = _bound_sha(
            manifest["descriptor"], manifest["descriptor_sha256"],
            f"family {family} {tier} descriptor",
        )
        _bound_sha(
            manifest["source"], manifest["source_sha256"],
            f"family {family} {tier} source",
        )
        provides = _strings(manifest["provides"], f"family {family} {tier}.provides")
        requires = _strings(manifest["requires"], f"family {family} {tier}.requires")
        private = _strings(
            manifest["private_definitions"], f"family {family} {tier}.private_definitions"
        )
        if (
            set(provides) & set(requires)
            or any(name.startswith("%") for name in requires)
            or any(not name.startswith("%") for name in private)
        ):
            raise MigrationError(f"family {family} {tier} public artifact boundary drift")
        descriptor = load_json(descriptor_path, f"family {family} {tier} descriptor")
        _exact(
            descriptor,
            {"format", "profile", "family", "tier", "source", "provides", "requires"},
            f"family {family} {tier} descriptor",
        )
        if (
            descriptor["format"] != "lisp65-dialect-v2-family-tier-v1"
            or descriptor["profile"] != "dialect-v2"
            or descriptor["family"] != family
            or descriptor["tier"] != tier
            or descriptor["source"] != manifest["source"]
            or descriptor["provides"] != provides
            or descriptor["requires"] != requires
        ):
            raise MigrationError(f"family {family} {tier} descriptor binding drift")
    if tiers != ["core", "library"]:
        raise MigrationError(f"family {family} tier artifact order drift")


def _measurement(
    value: Any,
    family: str,
    acceptance: dict[str, int],
    semantic_contract_id: str,
    semantic_registry: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, int]]:
    item = _exact(
        value,
        {
            "differential_receipt", "differential_receipt_sha256",
            "baseline_manifest", "baseline_manifest_sha256",
            "candidate_manifest", "candidate_manifest_sha256",
        },
        f"family {family}.measurement",
    )
    baseline_sha, baseline = _budget_artifact_manifest(
        item["baseline_manifest"], item["baseline_manifest_sha256"],
        family, "dialect-v1", f"family {family}.measurement.baseline_manifest",
    )
    candidate_sha, candidate = _budget_artifact_manifest(
        item["candidate_manifest"], item["candidate_manifest_sha256"],
        family, "dialect-v2", f"family {family}.measurement.candidate_manifest",
    )
    actual = {
        "loaded_symbol_delta": candidate["loaded_symbols"] - baseline["loaded_symbols"],
        "loaded_namepool_delta_bytes": candidate["loaded_namepool_bytes"] - baseline["loaded_namepool_bytes"],
        "boot_symbol_delta": candidate["boot_symbols"] - baseline["boot_symbols"],
        "boot_namepool_delta_bytes": candidate["boot_namepool_bytes"] - baseline["boot_namepool_bytes"],
        "directory_delta": candidate["directory_entries"] - baseline["directory_entries"],
        "artifact_delta_bytes": candidate["artifact_bytes"] - baseline["artifact_bytes"],
    }
    if -actual["loaded_symbol_delta"] < acceptance["min_symbol_savings"]:
        raise MigrationError(f"family {family} measured symbol savings miss acceptance")
    if -actual["loaded_namepool_delta_bytes"] < acceptance["min_namepool_savings_bytes"]:
        raise MigrationError(f"family {family} measured namepool savings miss acceptance")
    receipt_path = _bound_sha(
        item["differential_receipt"], item["differential_receipt_sha256"],
        f"family {family}.measurement.differential_receipt",
    )
    receipt = load_json(receipt_path, f"family {family} differential receipt")
    receipt_format = receipt.get("format")
    receipt_keys = {
        "format", "family", "baseline_profile", "candidate_profile",
        "baseline_manifest_sha256", "candidate_manifest_sha256", "actual",
        "semantic_contract_id", "fixture_sha256", "engine_results",
        "verdicts_conform_to_decisions", "result",
    }
    if receipt_format == "lisp65-dialect-family-differential-v1":
        receipt_keys.add("profile_builds")
    elif receipt_format == "lisp65-dialect-family-differential-v2":
        receipt_keys.update({"engine_builds", "internal_accounting", "tier_artifacts"})
    else:
        raise MigrationError(f"family {family} differential receipt format drift")
    _exact(
        receipt,
        receipt_keys,
        f"family {family} differential receipt",
    )
    semantic_contract = semantic_registry[semantic_contract_id]
    fixture_path = _path(
        semantic_contract["fixture"]["path"], f"family {family} semantic fixture"
    )
    if fixture_path is None or not fixture_path.is_file():
        raise MigrationError(f"family {family} semantic fixture is missing")
    fixture = load_json(fixture_path, f"family {family} semantic fixture")
    engines = semantic_contract["required_engines"]
    fixture_cases = _family_fixture_cases(fixture, family, engines, decisions)
    engine_results = receipt["engine_results"]
    if not isinstance(engine_results, list):
        raise MigrationError(f"family {family} differential engine results must be a list")
    fixture_sha = _sha(fixture_path)
    seen_engines: list[str] = []
    observed_builds: dict[str, dict[str, Any]] = {}
    observed_engine_builds: list[dict[str, Any]] = []
    for index, raw in enumerate(engine_results):
        engine = _exact(
            raw,
            {
                "engine", "baseline_verdict", "baseline_verdict_sha256",
                "candidate_verdict", "candidate_verdict_sha256",
                "baseline_preload_sha256", "candidate_preload_sha256", "result",
            },
            f"family {family} differential engine_results[{index}]",
        )
        engine_id = _string(engine["engine"], f"family {family} differential engine") or ""
        seen_engines.append(engine_id)
        baseline_provenance, candidate_provenance = _require_conformant_family_verdicts(
            engine["baseline_verdict"], engine["baseline_verdict_sha256"],
            engine["candidate_verdict"], engine["candidate_verdict_sha256"],
            family, engine_id, fixture_sha, fixture_cases, decisions,
        )
        if (
            engine["baseline_preload_sha256"] != baseline_provenance["preload_sha256"]
            or engine["candidate_preload_sha256"] != candidate_provenance["preload_sha256"]
        ):
            raise MigrationError(f"family {family} differential engine preload binding drift")
        for profile, provenance in (
            ("dialect-v1", baseline_provenance),
            ("dialect-v2", candidate_provenance),
        ):
            build = {
                "profile": profile,
                "source_commit": provenance["source_commit"],
                "binary_sha256": provenance["binary_sha256"],
                "build_profile_sha256": provenance["build_profile_sha256"],
            }
            if receipt_format == "lisp65-dialect-family-differential-v1":
                if profile in observed_builds and observed_builds[profile] != build:
                    raise MigrationError(f"family {family} build provenance differs between engines")
                observed_builds[profile] = build
            else:
                observed_engine_builds.append({"engine": engine_id, **build})
        if engine["result"] != "passed":
            raise MigrationError(f"family {family} differential engine verdict failed")
    if seen_engines != sorted(engines):
        raise MigrationError(f"family {family} differential receipt engine coverage drift")
    if receipt_format == "lisp65-dialect-family-differential-v1":
        if receipt["profile_builds"] != [
            observed_builds[profile] for profile in ("dialect-v1", "dialect-v2")
        ]:
            raise MigrationError(f"family {family} differential receipt build provenance drift")
    else:
        if receipt["engine_builds"] != observed_engine_builds:
            raise MigrationError(
                f"family {family} differential receipt engine build provenance drift"
            )
        _validate_family_internal_accounting(receipt["internal_accounting"], family)
        _validate_family_tier_artifacts(receipt["tier_artifacts"], family)
    if (
        receipt["family"] != family
        or receipt["baseline_profile"] != "dialect-v1"
        or receipt["candidate_profile"] != "dialect-v2"
        or receipt["semantic_contract_id"] != semantic_contract_id
        or receipt["fixture_sha256"] != fixture_sha
        or receipt["verdicts_conform_to_decisions"] is not True
        or receipt["result"] != "passed"
    ):
        raise MigrationError(f"family {family} differential receipt identity drift")
    if (
        receipt["baseline_manifest_sha256"] != baseline_sha
        or receipt["candidate_manifest_sha256"] != candidate_sha
        or receipt["actual"] != actual
    ):
        raise MigrationError(f"family {family} differential receipt binding drift")
    return _sha(receipt_path), actual


def _families(
    value: Any,
    projections: dict[str, dict[str, int]],
    blocks: dict[str, str],
    decisions: dict[str, dict[str, Any]],
    allow_missing: bool,
) -> dict[str, tuple[str, dict[str, int]]]:
    if not isinstance(value, list) or len(value) != len(FAMILY_ORDER):
        raise MigrationError("families must contain every ordered migration family")
    statuses: list[str] = []
    semantic_registry = _semantic_contract_registry()
    promotion_register = load_json(PROMOTION_REGISTER, "promotion register")
    sealed_subjects = {
        item.get("subject")
        for item in promotion_register.get("promotions", [])
        if isinstance(item, dict) and item.get("kind") == "family"
    }
    evidence: dict[str, tuple[str, dict[str, int]]] = {}
    for index, raw in enumerate(value):
        item = _exact(
            raw,
            {"id", "order", "status", "depends_on", "requires_blocks", "semantic_contracts", "projection", "acceptance", "measurement"},
            f"families[{index}]",
        )
        family = FAMILY_ORDER[index]
        if item["id"] != family or item["order"] != index + 1:
            raise MigrationError("family order drift")
        expected_dependencies = [] if index == 0 else [FAMILY_ORDER[index - 1]]
        if item["depends_on"] != expected_dependencies:
            raise MigrationError(f"family {family} dependency drift")
        required_blocks = _strings(item["requires_blocks"], f"family {family}.requires_blocks")
        if not set(required_blocks) <= set(blocks):
            raise MigrationError(f"family {family} references an unknown architecture block")
        if family in {"lists", "strings"} and required_blocks != ["v2-capability-carrier"]:
            raise MigrationError(
                f"{family} must remain blocked on the atomic capability/carrier promotion"
            )
        if family == "system-runtime" and set(required_blocks) != {
            "lists-malformed-type-errors", "public-error-channel",
        }:
            raise MigrationError(
                "system-runtime must complete the public error channel and lists type-error upgrade"
            )
        if item["status"] not in {"planned", "in-progress", "migrated"}:
            raise MigrationError(f"family {family} status is invalid")
        statuses.append(item["status"])
        contracts = _strings(item["semantic_contracts"], f"family {family}.semantic_contracts")
        acceptance = _exact(item["acceptance"], {"min_symbol_savings", "min_namepool_savings_bytes"}, f"family {family}.acceptance")
        if any(type(acceptance[key]) is not int or acceptance[key] < 0 for key in acceptance):
            raise MigrationError(f"family {family} acceptance is invalid")
        if item["projection"] is None:
            if not allow_missing:
                raise MigrationError(f"family {family} projection missing; expected {projections[family]}")
        else:
            projection = _exact(
                item["projection"],
                {
                    "loaded_symbol_delta", "loaded_namepool_delta_bytes",
                    "boot_symbol_delta", "boot_namepool_delta_bytes", "directory_delta",
                },
                f"family {family}.projection",
            )
            if projection != projections[family]:
                raise MigrationError(f"family {family} projection drift: expected {projections[family]}")
            if -projection["loaded_symbol_delta"] < acceptance["min_symbol_savings"]:
                raise MigrationError(f"family {family} symbol acceptance exceeds projection")
            if -projection["loaded_namepool_delta_bytes"] < acceptance["min_namepool_savings_bytes"]:
                raise MigrationError(f"family {family} namepool acceptance exceeds projection")
        if item["status"] == "migrated":
            if family != "prelude-control" and family not in sealed_subjects:
                raise MigrationError(
                    f"migrated family {family} lacks its sealed promotion register entry"
                )
            if not contracts or not isinstance(item["measurement"], dict):
                raise MigrationError(f"migrated family {family} lacks contracts or measurement")
            _verify_family_semantics(family, contracts, semantic_registry)
            if any(blocks[block_id] != "completed" for block_id in required_blocks):
                raise MigrationError(f"migrated family {family} depends on unfinished architecture work")
            if family != "prelude-control" and family in sealed_subjects:
                measurement = _exact(
                    item["measurement"],
                    {
                        "differential_receipt", "differential_receipt_sha256",
                        "baseline_manifest", "baseline_manifest_sha256",
                        "candidate_manifest", "candidate_manifest_sha256",
                    },
                    f"sealed family {family}.measurement pointer",
                )
                for key in (
                    "differential_receipt_sha256", "baseline_manifest_sha256",
                    "candidate_manifest_sha256",
                ):
                    _sha_value(measurement[key], f"sealed family {family}.{key}")
                evidence[family] = (
                    measurement["differential_receipt_sha256"],
                    {**projection, "artifact_delta_bytes": 0},
                )
            else:
                evidence[family] = _measurement(
                    item["measurement"], family, acceptance, contracts[0], semantic_registry,
                    decisions,
                )
        elif item["measurement"] is not None:
            raise MigrationError(f"unmigrated family {family} cannot carry a measurement")
    if statuses.count("in-progress") > 1:
        raise MigrationError("at most one family may be in progress")
    seen_open = False
    for status in statuses:
        if status != "migrated":
            seen_open = True
        elif seen_open:
            raise MigrationError("migrated families must form a completed prefix")
    for index, status in enumerate(statuses):
        if status == "in-progress" and any(previous != "migrated" for previous in statuses[:index]):
            raise MigrationError("an in-progress family requires every predecessor to be migrated")
    return evidence


def _sum_budget_rows(rows: dict[str, dict[str, int]]) -> dict[str, int]:
    keys = {
        "loaded_symbol_delta", "loaded_namepool_delta_bytes", "boot_symbol_delta",
        "boot_namepool_delta_bytes", "directory_delta",
    }
    result = {key: 0 for key in sorted(keys)}
    artifact_total = 0
    has_artifact = False
    for row in rows.values():
        for key in keys:
            result[key] += row[key]
        if "artifact_delta_bytes" in row:
            artifact_total += row["artifact_delta_bytes"]
            has_artifact = True
    if has_artifact:
        result["artifact_delta_bytes"] = artifact_total
    return result


def _budget_comparison(
    path_value: Any,
    sha_value: Any,
    source: str,
    projections: dict[str, dict[str, int]],
    family_evidence: dict[str, tuple[str, dict[str, int]]],
) -> None:
    path = _bound_sha(path_value, sha_value, "historical_forecast.comparison_report")
    report = load_json(path, "dialect-v2 budget comparison report")
    _exact(
        report,
        {
            "format", "historical_source", "family_differential_receipt_sha256s",
            "projections", "actual", "projection_totals", "actual_totals",
        },
        "dialect-v2 budget comparison report",
    )
    actual = {family: family_evidence[family][1] for family in FAMILY_ORDER}
    receipt_shas = [family_evidence[family][0] for family in FAMILY_ORDER]
    if (
        report["format"] != "lisp65-dialect-v2-budget-comparison-v1"
        or report["historical_source"] != source
        or report["family_differential_receipt_sha256s"] != receipt_shas
        or report["projections"] != projections
        or report["actual"] != actual
        or report["projection_totals"] != _sum_budget_rows(projections)
        or report["actual_totals"] != _sum_budget_rows(actual)
    ):
        raise MigrationError("dialect-v2 budget comparison report drift")


def _block_completion(value: Any, block_id: str) -> None:
    item = _exact(
        value,
        {"contract", "contract_sha256", "receipt", "receipt_sha256"},
        f"architecture block {block_id}.completion",
    )
    if block_id == "v2-capability-carrier":
        contract_path = _path(
            item["contract"], "architecture block v2-capability-carrier.contract"
        )
        _sha_value(
            item["contract_sha256"],
            "architecture block v2-capability-carrier.contract_sha256",
        )
    else:
        contract_path = _bound_sha(
            item["contract"], item["contract_sha256"],
            f"architecture block {block_id}.contract",
        )
    if contract_path is None:
        raise MigrationError(f"architecture block {block_id} contract path is missing")
    contract = load_json(contract_path, f"architecture block {block_id} contract")
    if block_id == "v2-capability-carrier":
        try:
            CAPABILITY_CARRIER.validate(contract)
        except CAPABILITY_CARRIER.ContractError as exc:
            raise MigrationError(
                f"architecture block {block_id} contract is invalid: {exc}"
            ) from exc
        if contract.get("status") != "promoted":
            raise MigrationError(
                "capability/carrier completion requires the single promoted state"
            )
        _path(item["receipt"], "architecture block v2-capability-carrier.receipt")
        _sha_value(
            item["receipt_sha256"],
            "architecture block v2-capability-carrier.receipt_sha256",
        )
        return
    _exact(contract, {"format", "id", "status", "gate"}, f"architecture block {block_id} contract")
    if contract != {
        "format": "lisp65-architecture-block-contract-v1",
        "id": block_id,
        "status": "implemented",
        "gate": "G2",
    }:
        raise MigrationError(f"architecture block {block_id} contract drift")
    receipt_path = _bound_sha(
        item["receipt"], item["receipt_sha256"], f"architecture block {block_id}.receipt"
    )
    receipt = load_json(receipt_path, f"architecture block {block_id} receipt")
    historical = block_id in {"public-error-channel", "lists-malformed-type-errors"}
    receipt_keys = {"format", "block_id", "contract_sha256", "gate", "result", "evidence"}
    if not historical:
        receipt_keys.add("bank_delta")
    _exact(receipt, receipt_keys, f"architecture block {block_id} receipt")
    if (
        receipt["format"] != (
            "lisp65-architecture-block-receipt-v1" if historical
            else "lisp65-architecture-block-receipt-v2"
        )
        or receipt["block_id"] != block_id
        or receipt["contract_sha256"] != item["contract_sha256"]
        or receipt["gate"] != "G2"
        or receipt["result"] != "passed"
        or not isinstance(receipt["evidence"], list)
        or not receipt["evidence"]
    ):
        raise MigrationError(f"architecture block {block_id} receipt drift")
    if not historical:
        try:
            BANK_DELTA.validate_bank_delta(receipt["bank_delta"])
        except BANK_DELTA.BankDeltaError as exc:
            raise MigrationError(
                f"architecture block {block_id} bank delta is invalid: {exc}"
            ) from exc
    evidence_paths: set[str] = set()
    for index, raw in enumerate(receipt["evidence"]):
        evidence = _exact(raw, {"path", "sha256"}, f"architecture block {block_id} evidence[{index}]")
        path_text = _string(evidence["path"], f"architecture block {block_id} evidence[{index}].path")
        if path_text in evidence_paths:
            raise MigrationError(f"architecture block {block_id} duplicates evidence")
        evidence_paths.add(path_text or "")
        _historical_evidence_sha(
            evidence["path"], evidence["sha256"],
            f"architecture block {block_id} evidence[{index}]",
        )


def _deferred_native_list_contract(path_value: Any, sha_value: Any) -> None:
    path = _bound_sha(
        path_value, sha_value, "deferred block v2-native-list-primitives contract"
    )
    value = load_json(path, "deferred block v2-native-list-primitives contract")
    _exact(
        value,
        {
            "format", "version", "id", "status", "family", "reason",
            "correctness_mitigation", "prototype", "performance",
            "exit_criteria", "reopening_paths", "exhausted_or_forbidden_paths",
            "stop_memo",
        },
        "deferred native-list block contract",
    )
    if (
        value["format"] != "lisp65-dialect-v2-block-v1"
        or value["version"] != 1
        or value["id"] != "v2-native-list-primitives"
        or value["status"] != "deferred"
        or value["family"] != "lists"
    ):
        raise MigrationError("deferred native-list block identity drift")
    mitigation = _exact(
        value["correctness_mitigation"],
        {"treewalk_exact_arity", "covers", "runtime_core_portability", "profile_switch"},
        "deferred native-list correctness mitigation",
    )
    if (
        mitigation["treewalk_exact_arity"] != {"nreverse": 1, "rplaca": 2, "rplacd": 2}
        or mitigation["covers"] != ["apply", "direct", "funcall"]
        or mitigation["runtime_core_portability"] != "blocked"
        or mitigation["profile_switch"] != "blocked"
    ):
        raise MigrationError("deferred native-list correctness mitigation drift")
    prototype = _exact(
        value["prototype"],
        {"v1", "three_native_primitives", "bytecode_nreverse_two_native_setters"},
        "deferred native-list prototype",
    )
    if (
        prototype["v1"] != {
            "runtime_overlay_vma": "0xc350", "post_boot_reserve_bytes": 1800,
        }
        or prototype["three_native_primitives"] != {
            "runtime_overlay_vma": "0xc4da", "vma_deficit_bytes": 388,
            "hypothetical_post_boot_reserve_bytes": 1406,
        }
        or prototype["bytecode_nreverse_two_native_setters"] != {
            "runtime_overlay_vma": "0xc46a", "vma_deficit_bytes": 276,
            "hypothetical_post_boot_reserve_bytes": 1518,
            "reserve_target_deficit_bytes": 18,
        }
    ):
        raise MigrationError("deferred native-list prototype measurements drift")
    performance = _exact(
        value["performance"], {"filter_100", "direct_nreverse_100"},
        "deferred native-list performance",
    )
    if (
        performance["filter_100"] != {
            "copy_reverse_steps": 2365, "bytecode_nreverse_steps": 2520,
            "step_delta": 155, "copy_reverse_cons_allocations": 100,
            "bytecode_nreverse_cons_allocations": 50,
        }
        or performance["direct_nreverse_100"] != {
            "native_visible_vm_steps": 2, "bytecode_visible_vm_steps": 1310,
            "classification": "diagnostic-only",
        }
    ):
        raise MigrationError("deferred native-list benchmark measurements drift")
    exit_criteria = _exact(
        value["exit_criteria"],
        {
            "workbench_vma_max", "workbench_post_boot_reserve_min_bytes",
            "runtime_core_hard_minimum", "cross_engine_semantics",
            "portable_artifact_semantics", "evidence",
        },
        "deferred native-list exit criteria",
    )
    if (
        exit_criteria["workbench_vma_max"] != "0xc356"
        or exit_criteria["workbench_post_boot_reserve_min_bytes"] != 1536
        or exit_criteria["runtime_core_hard_minimum"] != "must-pass-existing-gate"
        or exit_criteria["cross_engine_semantics"] != "direct-funcall-apply-equivalent"
        or exit_criteria["portable_artifact_semantics"] != "workbench-and-runtime-core"
        or exit_criteria["evidence"] != "regenerated-after-product-links-pass"
    ):
        raise MigrationError("deferred native-list exit criteria drift")
    if value["reopening_paths"] != [
        "combined-lists-strings-native-capability-budget",
        "user-approved-colour-ram-attic-rebalance",
    ]:
        raise MigrationError("deferred native-list reopening path drift")
    paths = value["exhausted_or_forbidden_paths"]
    if (
        not isinstance(paths, list)
        or [item.get("id") for item in paths if isinstance(item, dict)]
        != ["primitive-name-table-relocation", "resident-island", "layout-relaxation"]
        or paths[0].get("status") != "exhausted"
        or "0 resident bytes" not in paths[0].get("measurement", "")
        or paths[1].get("status") != "forbidden"
        or paths[2] != {
            "id": "layout-relaxation", "status": "requires-new-user-scope",
        }
    ):
        raise MigrationError("deferred native-list excluded path drift")
    stop_memo = _path(value["stop_memo"], "deferred native-list stop memo")
    if stop_memo is None or not stop_memo.is_file():
        raise MigrationError("deferred native-list stop memo is missing")


def _deferred_capability_carrier_contract(path_value: Any, sha_value: Any) -> None:
    path = _path(path_value, "deferred block v2-capability-carrier contract")
    _sha_value(sha_value, "deferred block v2-capability-carrier contract SHA")
    if path is None:
        raise MigrationError("deferred capability/carrier contract path is missing")
    value = load_json(path, "deferred block v2-capability-carrier contract")
    try:
        CAPABILITY_CARRIER.validate(value)
    except CAPABILITY_CARRIER.ContractError as exc:
        raise MigrationError(
            f"deferred capability/carrier seal is invalid: {exc}"
        ) from exc


def _deferred(value: Any) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        raise MigrationError("deferred_blocks must be non-empty")
    blocks: dict[str, set[str]] = {}
    statuses: dict[str, str] = {}
    for index, raw in enumerate(value):
        keys = {"id", "status", "requires", "completion"}
        if isinstance(raw, dict) and raw.get("id") == "v2-capability-carrier":
            keys.update({"contract", "contract_sha256"})
        item = _exact(raw, keys, f"deferred_blocks[{index}]")
        block_id = _string(item["id"], f"deferred_blocks[{index}].id")
        if block_id in blocks or item["status"] not in {"deferred", "completed"}:
            raise MigrationError("deferred block ids/status drift")
        blocks[block_id or ""] = set(_strings(item["requires"], f"deferred block {block_id}.requires"))
        statuses[block_id or ""] = item["status"]
        if item["status"] == "completed":
            if not isinstance(item["completion"], dict):
                raise MigrationError(f"completed block {block_id} lacks completion evidence")
            _block_completion(item["completion"], block_id or "")
        elif item["completion"] is not None:
            raise MigrationError(f"deferred block {block_id} must not carry completion evidence")
        if block_id == "v2-capability-carrier":
            _deferred_capability_carrier_contract(
                item["contract"], item["contract_sha256"]
            )
    for block_id, requirements in blocks.items():
        if not requirements <= set(blocks) or block_id in requirements:
            raise MigrationError(f"deferred block {block_id} has invalid dependencies")
    if "first-class-buffer" not in blocks.get("lifo-unload", set()):
        raise MigrationError("lifo-unload must depend on first-class-buffer")
    if blocks.get("lists-malformed-type-errors") != {"public-error-channel"}:
        raise MigrationError("lists malformed-input upgrade must depend on public-error-channel")
    if blocks.get("lists-v2-expansion") != set():
        raise MigrationError("lists-v2-expansion must remain an independent post-migration block")
    if blocks.get("buffer-and-string-construction-block") != {"first-class-buffer"}:
        raise MigrationError(
            "buffer/string construction must remain a named ABI-1.1 block after first-class-buffer"
        )
    if blocks.get("v2-capability-carrier") != set():
        raise MigrationError("v2-capability-carrier must remain an independent atomic block")

    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(block_id: str) -> None:
        if block_id in visiting:
            raise MigrationError("deferred block dependency cycle")
        if block_id in visited:
            return
        visiting.add(block_id)
        for requirement in blocks[block_id]:
            visit(requirement)
        visiting.remove(block_id)
        visited.add(block_id)
    for block_id in blocks:
        visit(block_id)
    for block_id, requirements in blocks.items():
        if statuses[block_id] == "completed" and any(statuses[dependency] != "completed" for dependency in requirements):
            raise MigrationError(f"completed block {block_id} has an unfinished dependency")
    return statuses


def _target_public_names(
    classified: dict[str, dict[str, Any]],
    new_names: dict[str, dict[str, Any]],
    replacement_targets: dict[str, str],
    target_public_macros: set[str],
) -> set[str]:
    target = {
        name for name, group in classified.items()
        if group["disposition"] in {"keep", "move-library", "redefine"}
    }
    target.update(new_names)
    target.update(
        replacement for replacement in replacement_targets.values()
        if replacement in classified or replacement in new_names
    )
    target.update(target_public_macros)
    return target


def _v2_surface_public_names(
    path_value: Any,
    sha_value: Any,
    surface_id: str,
    migration_sha: str,
    source_commit: str,
) -> set[str]:
    path = _bound_sha(path_value, sha_value, f"dialect-v2 surface {surface_id}.manifest")
    manifest = load_json(path, f"dialect-v2 surface {surface_id} manifest")
    _exact(
        manifest,
        {"format", "profile", "surface_id", "migration_contract_sha256", "source_commit", "definitions"},
        f"dialect-v2 surface {surface_id} manifest",
    )
    if (
        manifest["format"] != "lisp65-dialect-v2-surface-manifest-v1"
        or manifest["profile"] != "dialect-v2"
        or manifest["surface_id"] != surface_id
        or manifest["migration_contract_sha256"] != migration_sha
        or manifest["source_commit"] != source_commit
    ):
        raise MigrationError(f"dialect-v2 surface {surface_id} identity/provenance drift")
    definitions = manifest["definitions"]
    if not isinstance(definitions, list) or not definitions:
        raise MigrationError(f"dialect-v2 surface {surface_id} definitions must be non-empty")
    names: list[str] = []
    public: set[str] = set()
    for index, raw in enumerate(definitions):
        definition = _exact(
            raw, {"name", "visibility", "kind"},
            f"dialect-v2 surface {surface_id}.definitions[{index}]",
        )
        name = _string(definition["name"], f"dialect-v2 surface {surface_id}.definitions[{index}].name")
        if definition["visibility"] not in {"public", "internal", "private-inline"}:
            raise MigrationError(f"dialect-v2 surface {surface_id} definition visibility drift")
        if definition["kind"] not in {"primitive", "function", "macro", "application-entry"}:
            raise MigrationError(f"dialect-v2 surface {surface_id} definition kind drift")
        names.append(name or "")
        if definition["visibility"] == "public":
            public.add(name or "")
    if names != sorted(set(names)):
        raise MigrationError(f"dialect-v2 surface {surface_id} definitions must be sorted and unique")
    return public


def _validate_v2_contract(
    path: Path,
    expected_sha: str,
    migration_sha: str,
    expected_names: set[str],
    source_commit: str,
) -> None:
    if _sha(path) != expected_sha:
        raise MigrationError("dialect-v2 contract SHA binding drift")
    value = load_json(path, "dialect-v2 contract")
    _exact(
        value,
        {
            "format", "version", "profile", "migration_contract_sha256", "source_commit",
            "public_names", "surfaces",
        },
        "dialect-v2 contract",
    )
    if (
        value["format"] != "lisp65-dialect-v2-contract-v1"
        or value["version"] != 1
        or value["profile"] != "dialect-v2"
        or value["migration_contract_sha256"] != migration_sha
        or value["source_commit"] != source_commit
    ):
        raise MigrationError("dialect-v2 contract identity/policy binding drift")
    public_names = set(_strings(value["public_names"], "dialect-v2 contract public_names", nonempty=True))
    if public_names != expected_names:
        raise MigrationError("dialect-v2 contract public surface drift from migration decisions")
    surfaces = value["surfaces"]
    if not isinstance(surfaces, list) or not surfaces:
        raise MigrationError("dialect-v2 contract surfaces must be non-empty")
    resolved: set[str] = set()
    ids: list[str] = []
    for index, raw in enumerate(surfaces):
        surface = _exact(raw, {"id", "manifest", "manifest_sha256"}, f"dialect-v2 surfaces[{index}]")
        surface_id = _string(surface["id"], f"dialect-v2 surfaces[{index}].id") or ""
        ids.append(surface_id)
        names = _v2_surface_public_names(
            surface["manifest"], surface["manifest_sha256"], surface_id,
            migration_sha, source_commit,
        )
        if not names:
            raise MigrationError(f"dialect-v2 canonical surface {surface_id} exposes no public names")
        if resolved & names:
            raise MigrationError("dialect-v2 public name appears in multiple canonical surfaces")
        resolved.update(names)
    if ids != sorted(set(ids)) or resolved != public_names:
        raise MigrationError("dialect-v2 canonical surface coverage/order drift")


def _validate_candidate_manifest(
    path: Path,
    migration_sha: str,
    dialect_sha: str,
    source_commit: str,
    build_id: int,
) -> None:
    manifest = load_json(path, "dialect-v2 promotion candidate manifest")
    _exact(
        manifest,
        {
            "format", "profile", "build_id", "migration_contract_sha256",
            "dialect_contract_sha256", "source_commit", "artifacts",
        },
        "dialect-v2 promotion candidate manifest",
    )
    if (
        manifest["format"] != "lisp65-dialect-v2-candidate-manifest-v1"
        or manifest["profile"] != "dialect-v2"
        or manifest["build_id"] != build_id
        or manifest["migration_contract_sha256"] != migration_sha
        or manifest["dialect_contract_sha256"] != dialect_sha
        or manifest["source_commit"] != source_commit
        or not isinstance(manifest["artifacts"], list)
        or not manifest["artifacts"]
    ):
        raise MigrationError("dialect-v2 promotion candidate provenance drift")
    names: list[str] = []
    for index, raw in enumerate(manifest["artifacts"]):
        artifact = _exact(raw, {"id", "path", "sha256"}, f"candidate artifact[{index}]")
        artifact_id = _string(artifact["id"], f"candidate artifact[{index}].id") or ""
        names.append(artifact_id)
        _bound_sha(artifact["path"], artifact["sha256"], f"candidate artifact[{index}]")
    if names != sorted(set(names)):
        raise MigrationError("candidate artifacts must be sorted and unique")


def _validate_case_evidence(
    path_value: Any,
    sha_value: Any,
    evidence_format: str,
    case_id: str,
    target: str,
    result: str,
    cycle_id: str,
    migration_sha: str,
    dialect_sha: str,
    manifest_sha: str,
    build_id: int,
    verifier_path: str,
    verifier_sha: str,
) -> None:
    path = _bound_sha(path_value, sha_value, f"promotion case {case_id}.evidence")
    evidence = load_json(path, f"promotion case {case_id} evidence")
    _exact(
        evidence,
        {
            "format", "profile", "migration_contract_sha256", "dialect_contract_sha256",
            "candidate_manifest_sha256", "build_id", "case_id", "target", "result",
            "cycle_id", "native_receipt", "native_receipt_sha256",
            "verifier_inputs", "raw_artifacts",
        },
        f"promotion case {case_id} evidence",
    )
    if (
        evidence["format"] != evidence_format
        or evidence["profile"] != "dialect-v2"
        or evidence["migration_contract_sha256"] != migration_sha
        or evidence["dialect_contract_sha256"] != dialect_sha
        or evidence["candidate_manifest_sha256"] != manifest_sha
        or evidence["build_id"] != build_id
        or evidence["case_id"] != case_id
        or evidence["target"] != target
        or evidence["result"] != result
        or evidence["cycle_id"] != cycle_id
        or not isinstance(evidence["raw_artifacts"], list)
        or not evidence["raw_artifacts"]
    ):
        raise MigrationError(f"promotion case {case_id} evidence binding drift")
    raw_paths: list[str] = []
    for index, raw in enumerate(evidence["raw_artifacts"]):
        artifact = _exact(raw, {"path", "sha256"}, f"promotion case {case_id}.raw_artifacts[{index}]")
        raw_path = _string(artifact["path"], f"promotion case {case_id}.raw_artifacts[{index}].path") or ""
        raw_paths.append(raw_path)
        _bound_sha(artifact["path"], artifact["sha256"], f"promotion case {case_id}.raw_artifacts[{index}]")
    if raw_paths != sorted(set(raw_paths)):
        raise MigrationError(f"promotion case {case_id} raw artifacts must be sorted and unique")
    native_receipt = _bound_sha(
        evidence["native_receipt"], evidence["native_receipt_sha256"],
        f"promotion case {case_id}.native_receipt",
    )
    verifier_inputs = evidence["verifier_inputs"]
    if not isinstance(verifier_inputs, list):
        raise MigrationError(f"promotion case {case_id} verifier_inputs must be a list")
    inputs: dict[str, Path] = {}
    for index, raw in enumerate(verifier_inputs):
        item = _exact(raw, {"id", "path", "sha256"}, f"promotion case {case_id}.verifier_inputs[{index}]")
        input_id = _string(item["id"], f"promotion case {case_id}.verifier_inputs[{index}].id") or ""
        if input_id in inputs:
            raise MigrationError(f"promotion case {case_id} duplicates verifier input {input_id}")
        inputs[input_id] = _bound_sha(
            item["path"], item["sha256"], f"promotion case {case_id}.verifier_inputs[{index}]"
        )
    if evidence_format == "lisp65-dialect-v2-runtime-g5-case-evidence-v1":
        expected_inputs = {"package", "oracle"}
        if verifier_path != "tools/host-lisp/runtime_export_hw_oracle.py" or set(inputs) != expected_inputs:
            raise MigrationError(f"promotion case {case_id} runtime verifier contract drift")
        package_manifest = inputs["package"]
        if package_manifest.name != "manifest.json":
            raise MigrationError(f"promotion case {case_id} Runtime package binding is not manifest.json")
        try:
            verified = RUNTIME_HW.verify_receipt(
                package_manifest.parent, inputs["oracle"], native_receipt, None,
            )
        except (RUNTIME_HW.HardwareContractError, OSError, ValueError, KeyError, TypeError) as exc:
            raise MigrationError(f"promotion case {case_id} native Runtime G5 verification failed: {exc}") from exc
        if verified != 0:
            raise MigrationError(f"promotion case {case_id} native Runtime G5 verifier failed")
        native = load_json(native_receipt, f"promotion case {case_id} native Runtime receipt")
        expected_phase = case_id.split("/", 1)[1]
        operator = native.get("operator")
        if (
            native.get("phase") != expected_phase
            or not isinstance(operator, dict)
            or operator.get("cycle_id") != cycle_id
        ):
            raise MigrationError(f"promotion case {case_id} native Runtime phase/cycle drift")
    elif evidence_format == "lisp65-dialect-v2-workbench-g5-case-evidence-v1":
        if verifier_path != "tools/host-lisp/dialect_v2_workbench_g5_verify.py" or inputs:
            raise MigrationError(f"promotion case {case_id} workbench verifier contract drift")
        verifier = _bound_sha(verifier_path, verifier_sha, f"promotion case {case_id}.verifier")
        command = [
            sys.executable, str(verifier), "verify", "--receipt", str(native_receipt),
            "--target", target, "--result", result, "--cycle-id", cycle_id,
            "--candidate-manifest-sha256", manifest_sha, "--build-id", str(build_id),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()
            raise MigrationError(f"promotion case {case_id} native Workbench verifier failed: {detail}")
    else:
        raise MigrationError(f"promotion case {case_id} has no format-specific verifier")


def _validate_promotion_receipt(
    path: Path,
    expected_sha: str,
    migration_sha: str,
    dialect_sha: str,
    matrix_sha: str,
    manifest_sha: str,
    build_id: int,
    cycle_ids: list[str],
    family_report_shas: list[str],
    matrix_cases: dict[str, tuple[str, str, str, str, str | None]],
) -> None:
    if _sha(path) != expected_sha:
        raise MigrationError("promotion receipt SHA binding drift")
    receipt = load_json(path, "dialect-v2 G5 receipt")
    _exact(
        receipt,
        {
            "format", "profile", "migration_contract_sha256", "dialect_contract_sha256",
            "matrix_contract_sha256", "candidate_manifest_sha256", "build_id", "cycle_ids",
            "family_measurement_report_sha256s", "cases",
        },
        "dialect-v2 G5 receipt",
    )
    expected = {
        "format": "lisp65-dialect-v2-g5-receipt-v1",
        "profile": "dialect-v2",
        "migration_contract_sha256": migration_sha,
        "dialect_contract_sha256": dialect_sha,
        "matrix_contract_sha256": matrix_sha,
        "candidate_manifest_sha256": manifest_sha,
        "build_id": build_id,
        "cycle_ids": cycle_ids,
        "family_measurement_report_sha256s": family_report_shas,
    }
    for key, value in expected.items():
        if receipt[key] != value:
            raise MigrationError(f"promotion receipt binding drift: {key}")
    cases = receipt["cases"]
    if not isinstance(cases, list):
        raise MigrationError("promotion receipt cases must be a list")
    seen: dict[str, tuple[str, str, str]] = {}
    runtime_cycles: list[str] = []
    for index, raw in enumerate(cases):
        case = _exact(
            raw,
            {
                "id", "target", "result", "cycle_id", "evidence", "evidence_sha256",
                "evidence_format",
            },
            f"promotion receipt cases[{index}]",
        )
        case_id = _string(case["id"], f"promotion receipt cases[{index}].id")
        target = _string(case["target"], f"promotion receipt cases[{index}].target")
        result = _string(case["result"], f"promotion receipt cases[{index}].result")
        cycle_id = _string(case["cycle_id"], f"promotion receipt cases[{index}].cycle_id")
        if cycle_id not in cycle_ids:
            raise MigrationError(f"promotion receipt case {case_id} uses an unbound cycle id")
        expected = matrix_cases.get(case_id or "")
        if expected is None or case["evidence_format"] != expected[2] or expected[4] is None:
            raise MigrationError(f"promotion receipt case {case_id} evidence format drift")
        _validate_case_evidence(
            case["evidence"], case["evidence_sha256"], expected[2], case_id or "",
            target or "", result or "", cycle_id or "", migration_sha, dialect_sha,
            manifest_sha, build_id, expected[3], expected[4],
        )
        seen[case_id or ""] = (target or "", result or "", expected[2])
        if (case_id or "").startswith("runtime-export/"):
            runtime_cycles.append(cycle_id or "")
    expected_seen = {case_id: value[:3] for case_id, value in matrix_cases.items()}
    if seen != expected_seen or len(seen) != len(cases):
        raise MigrationError("promotion receipt does not exactly cover the G5 matrix")
    used_cycles = {case["cycle_id"] for case in cases}
    if used_cycles != set(cycle_ids):
        raise MigrationError("promotion receipt cycle id inventory has unused or missing ids")
    if len(runtime_cycles) != len(set(runtime_cycles)):
        raise MigrationError("runtime-export G5 cases require distinct physical cycle ids")


def _selection(
    value: dict[str, Any],
    migration_path: Path,
    v1_sha: str,
    v1_commit: str,
    ready_for_g5: bool,
    target_names: set[str],
    family_report_shas: list[str],
    matrix_path: Path,
    matrix_sha: str,
    matrix_cases: dict[str, tuple[str, str, str, str, str | None]],
) -> None:
    item = _exact(value, {"format", "version", "active_profile", "profiles", "promotion"}, "profile selection")
    if item["format"] != SELECTION_FORMAT or item["version"] != 1:
        raise MigrationError("profile selection format/version drift")
    profiles = item["profiles"]
    if not isinstance(profiles, list) or len(profiles) != 2:
        raise MigrationError("profile selection must contain v1 and v2")
    resolved: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(profiles):
        profile = _exact(raw, {"id", "state", "contract", "contract_sha256", "source_commit"}, f"selection.profiles[{index}]")
        profile_id = _string(profile["id"], f"selection.profiles[{index}].id")
        if profile_id in resolved:
            raise MigrationError("duplicate selected profile")
        resolved[profile_id or ""] = profile
    if set(resolved) != {"dialect-v1", "dialect-v2"}:
        raise MigrationError("profile selection ids drift")
    v1 = resolved["dialect-v1"]
    if v1["contract"] != "config/dialect-contract.json" or v1["contract_sha256"] != v1_sha:
        raise MigrationError("selected v1 contract binding drift")
    if _commit(v1["source_commit"], "selection dialect-v1 source_commit") != v1_commit:
        raise MigrationError("selected v1 source commit drift")
    promotion = _exact(item["promotion"], {"status", "migration_contract", "migration_contract_sha256", "evidence"}, "selection.promotion")
    if promotion["migration_contract"] != migration_path.relative_to(ROOT).as_posix():
        raise MigrationError("selection migration contract path drift")
    if item["active_profile"] == "dialect-v1":
        if v1["state"] != "frozen-evidence" or resolved["dialect-v2"]["state"] != "planning":
            raise MigrationError("active v1 selection state drift")
        if promotion != {
            "status": "not-requested",
            "migration_contract": migration_path.relative_to(ROOT).as_posix(),
            "migration_contract_sha256": None,
            "evidence": None,
        }:
            raise MigrationError("active v1 must not carry promotion evidence")
    elif item["active_profile"] == "dialect-v2":
        if not ready_for_g5:
            raise MigrationError("dialect-v2 cannot activate before every migration blocker is closed")
        if v1["state"] != "archived" or resolved["dialect-v2"]["state"] != "current":
            raise MigrationError("active v2 requires archived v1 and current v2")
        migration_sha = _sha(migration_path)
        if promotion["status"] != "passed-g5" or promotion["migration_contract_sha256"] != migration_sha:
            raise MigrationError("active v2 lacks an exact migration-policy G5 binding")
        v2 = resolved["dialect-v2"]
        v2_contract = _path(v2["contract"], "selection dialect-v2 contract")
        v2_sha = _sha_value(v2["contract_sha256"], "selection dialect-v2 contract_sha256")
        v2_commit = _commit(v2["source_commit"], "selection dialect-v2 source_commit")
        if v2_contract is None or v2_sha is None:
            raise MigrationError("active v2 requires a bound dialect-v2 contract")
        _validate_v2_contract(v2_contract, v2_sha, migration_sha, target_names, v2_commit)
        evidence = _exact(
            promotion["evidence"],
            {
                "profile", "candidate_manifest", "candidate_manifest_sha256", "build_id",
                "cycle_ids", "receipt", "receipt_sha256", "dialect_contract_sha256",
                "matrix_contract_sha256", "family_measurement_report_sha256s",
            },
            "selection.promotion.evidence",
        )
        manifest_path = _bound_sha(
            evidence["candidate_manifest"], evidence["candidate_manifest_sha256"],
            "selection promotion candidate manifest",
        )
        build_id = evidence["build_id"]
        cycle_ids = _strings(evidence["cycle_ids"], "selection promotion cycle_ids", nonempty=True)
        if (
            evidence["profile"] != "dialect-v2"
            or type(build_id) is not int or not 0 <= build_id <= 0xFFFFFFFF
            or any(not SAFE_ID.fullmatch(cycle_id) for cycle_id in cycle_ids)
            or evidence["dialect_contract_sha256"] != v2_sha
            or evidence["matrix_contract_sha256"] != matrix_sha
            or evidence["family_measurement_report_sha256s"] != family_report_shas
        ):
            raise MigrationError("active v2 promotion evidence drift")
        _validate_candidate_manifest(
            manifest_path, migration_sha, v2_sha, v2_commit, build_id,
        )
        receipt_path = _bound_sha(
            evidence["receipt"], evidence["receipt_sha256"], "selection promotion receipt"
        )
        _validate_promotion_receipt(
            receipt_path, evidence["receipt_sha256"], migration_sha, v2_sha, matrix_sha,
            evidence["candidate_manifest_sha256"], build_id, cycle_ids, family_report_shas,
            matrix_cases,
        )
    else:
        raise MigrationError("active_profile must be dialect-v1 or dialect-v2")


def validate(
    contract: dict[str, Any],
    selection: dict[str, Any],
    contract_path: Path,
    *,
    allow_missing_projection: bool = False,
) -> dict[str, Any]:
    _exact(
        contract,
        {"format", "version", "status", "release_policy", "source_profile", "target_profile", "artifact_arity_contract", "decision_contract", "classification", "syntax", "families", "historical_forecast", "open_decisions", "deferred_blocks", "switch_criteria"},
        "migration contract",
    )
    if (
        contract["format"] != FORMAT
        or contract["version"] != 1
        or contract["status"] not in {"planning", "r2-complete", "ready-for-g5"}
    ):
        raise MigrationError("migration contract format/version/status drift")
    release_policy = _exact(
        contract["release_policy"],
        {
            "only_product", "release_authority", "dialect_v1", "runtime_core",
            "runtime_core_receipt_effect", "family_advancement", "ap8_advancement",
            "active_work_lines", "family_status_hold",
        },
        "release_policy",
    )
    if release_policy != {
        "only_product": "lisp65-workbench-v2",
        "release_authority": "workbench-v2-link-plus-full-g5",
        "dialect_v1": "frozen-evidence-never-release",
        "runtime_core": "internal-proof-only",
        "runtime_core_receipt_effect": "none",
        "family_advancement": "sequential-after-capability-carrier",
        "ap8_advancement": "explicit-block-after-capability-carrier",
        "active_work_lines": ["dialect-v2-family-migration"],
        "family_status_hold": {
            "prelude-control": "migrated",
            "lists": "migrated",
            "strings": "migrated",
            "system-runtime": "migrated",
            "ide": "migrated",
        },
    }:
        raise MigrationError("release policy/profile-split hold drift")
    source = _exact(
        contract["source_profile"],
        {"id", "dialect_contract", "dialect_contract_sha256", "source_commit", "lifecycle", "allowed_operations", "features", "backports", "evidence", "sunset"},
        "source_profile",
    )
    if source["id"] != "dialect-v1" or source["lifecycle"] != "frozen-evidence":
        raise MigrationError("source profile must be frozen dialect-v1 evidence")
    if source["allowed_operations"] != ["reproducibility-rebuild"] or source["features"] != "forbidden" or source["backports"] != "forbidden":
        raise MigrationError("dialect-v1 lifecycle permits more than reproducibility rebuilds")
    v1_path = _path(source["dialect_contract"], "source_profile.dialect_contract")
    v1_sha = _sha_value(source["dialect_contract_sha256"], "source_profile.dialect_contract_sha256")
    if v1_path is None or _sha(v1_path) != v1_sha:
        raise MigrationError("frozen dialect-v1 contract SHA drift")
    v1_commit = _commit(source["source_commit"], "source_profile.source_commit")
    v1_repository_path = PurePosixPath(source["dialect_contract"]).as_posix()
    if _git_blob_sha(v1_commit, v1_repository_path, "dialect-v1 contract") != v1_sha:
        raise MigrationError("frozen source commit does not contain the bound dialect-v1 contract")
    evidence = source["evidence"]
    if not isinstance(evidence, list) or [item.get("id") for item in evidence] != ["workbench-g5", "runtime-export-g5"]:
        raise MigrationError("source evidence ids/order drift")
    for index, raw in enumerate(evidence):
        item = _exact(raw, {"id", "path", "sha256"}, f"source_profile.evidence[{index}]")
        _bound_sha(item["path"], item["sha256"], f"source_profile.evidence[{index}]")
        evidence_path = PurePosixPath(item["path"]).as_posix()
        if _git_blob_sha(v1_commit, evidence_path, f"source evidence {item['id']}") != item["sha256"]:
            raise MigrationError(f"frozen source commit does not contain source evidence {item['id']}")
    sunset = _exact(source["sunset"], {"target_state", "requires_profile", "requires_gate", "requires_matrix"}, "source_profile.sunset")
    if sunset != {
        "target_state": "archived", "requires_profile": "dialect-v2",
        "requires_gate": "G5", "requires_matrix": "dialect-v2-product-switch",
    }:
        raise MigrationError("dialect-v1 sunset policy drift")

    v1 = V1.load_json(v1_path, "frozen dialect-v1 contract")
    V1.validate_schema(v1)
    V1.validate_frozen_commit(v1_commit, v1_repository_path, v1_sha)
    public, surfaces, _deliveries = _public_inventory(v1)

    target = _exact(
        contract["target_profile"],
        {"id", "lifecycle", "runtime_compatibility_layer", "legacy_source_aliases", "p0_decode_compatibility", "abi_ledger", "abi_ledger_sha256"},
        "target_profile",
    )
    if target["id"] != "dialect-v2" or target["lifecycle"] != "migration-candidate":
        raise MigrationError("target profile identity/lifecycle drift")
    if target["runtime_compatibility_layer"] != "forbidden" or target["legacy_source_aliases"] != "forbidden" or target["p0_decode_compatibility"] != "permanent":
        raise MigrationError("target compatibility policy drift")
    ledger_path = _path(target["abi_ledger"], "target_profile.abi_ledger")
    ledger_sha = _sha_value(target["abi_ledger_sha256"], "target_profile.abi_ledger_sha256")
    if ledger_path is None or _sha(ledger_path) != ledger_sha:
        raise MigrationError("ABI ledger SHA binding drift")
    try:
        ABI.validate(ABI.load_json(ledger_path))
    except ABI.LedgerError as exc:
        raise MigrationError(f"ABI ledger invalid: {exc}") from exc

    resolved, new_names, replacement_targets = _classification(contract["classification"], public, surfaces)
    syntax = _syntax(contract["syntax"])
    projections = _project(
        resolved, new_names, replacement_targets, surfaces, syntax["projection"]
    )
    blocks = _deferred(contract["deferred_blocks"])
    decided_ids = _decision_contract(contract["decision_contract"])
    decisions = _open_decisions(contract["open_decisions"], decided_ids)
    _artifact_arity_contract(contract["artifact_arity_contract"], decisions)
    actual_family_status = {item["id"]: item["status"] for item in contract["families"]}
    if actual_family_status != release_policy["family_status_hold"]:
        raise MigrationError("family status changed while Workbench-v2 release hold is active")
    completed_r2_blocks = {
        "v2-capability-carrier",
        "public-error-channel",
        "lists-malformed-type-errors",
        "directory-only-l65m-v2",
    }
    expected_block_status = {
        block_id: "completed" if block_id in completed_r2_blocks else "deferred"
        for block_id in blocks
    }
    if blocks != expected_block_status:
        raise MigrationError(
            "R2 architecture-block completion set drift"
        )
    family_evidence = _families(
        contract["families"], projections, blocks, decisions, allow_missing_projection
    )

    forecast = _exact(
        contract["historical_forecast"],
        {
            "source", "status", "already_realized", "comparison_report",
            "comparison_report_sha256",
        },
        "historical_forecast",
    )
    if forecast["status"] != "non-normative-rebase-input":
        raise MigrationError("historical forecast must remain non-normative")
    _strings(forecast["already_realized"], "historical_forecast.already_realized", nonempty=True)
    comparison_path = _path(
        forecast["comparison_report"], "historical_forecast.comparison_report", nullable=True
    )
    comparison_sha = _sha_value(
        forecast["comparison_report_sha256"],
        "historical_forecast.comparison_report_sha256",
        nullable=True,
    )
    if (comparison_path is None) != (comparison_sha is None):
        raise MigrationError("historical forecast comparison path/SHA must be both null or both bound")

    switch = _exact(
        contract["switch_criteria"],
        {"authority", "matrix_contract", "matrix_contract_sha256", "release_effect"},
        "switch_criteria",
    )
    if switch["authority"] != "hardware-G5" or switch["release_effect"] != "none-without-G6":
        raise MigrationError("profile switch authority/effect drift")
    matrix_path = _path(switch["matrix_contract"], "switch_criteria.matrix_contract")
    matrix_sha = _sha_value(switch["matrix_contract_sha256"], "switch_criteria.matrix_contract_sha256")
    if matrix_path is None or matrix_sha is None:
        raise MigrationError("profile switch matrix SHA binding drift")
    if _sha(matrix_path) != matrix_sha:
        snapshot_sha = _git_binding_sha_at_contract_commit(
            contract_path,
            PurePosixPath(switch["matrix_contract"]).as_posix(),
            "profile switch matrix",
        )
        if snapshot_sha != matrix_sha:
            raise MigrationError("profile switch matrix SHA binding drift")
    matrix_cases, _matrix_domains = _g5_matrix(
        matrix_path, allow_unbound_verifiers=contract["status"] != "ready-for-g5"
    )

    semantic_pending = any(
        record.get("semantic_status") == "pending"
        for key in ("replacements", "removals")
        for record in contract["classification"][key]
    ) or any(
        record.get("semantic_status") == "pending"
        for record in contract["syntax"]["macro_migrations"]
    )
    blocking_decisions = any(
        item["status"] == "pending" and item["blocks_profile_switch"]
        for item in decisions.values()
    )
    all_migrated = all(item["status"] == "migrated" for item in contract["families"])
    r2_complete = all_migrated and not semantic_pending and not blocking_decisions
    if all_migrated:
        if comparison_path is None or comparison_sha is None:
            raise MigrationError("completed migration lacks the measured-vs-forecast budget report")
        _budget_comparison(
            forecast["comparison_report"], forecast["comparison_report_sha256"],
            forecast["source"], projections, family_evidence,
        )
    elif comparison_path is not None:
        raise MigrationError("incomplete migration must not publish a final budget comparison")
    if contract["status"] in {"r2-complete", "ready-for-g5"} and not r2_complete:
        raise MigrationError("advanced migration contract still has R2 blockers")
    if r2_complete and contract["status"] == "planning":
        raise MigrationError("completed migration must advance contract status to r2-complete")
    family_report_shas = [
        family_evidence[family][0] for family in FAMILY_ORDER if family in family_evidence
    ]
    _selection(
        selection, contract_path, v1_sha or "", v1_commit,
        contract["status"] == "ready-for-g5",
        _target_public_names(
            resolved, new_names, replacement_targets, syntax["target_public_macros"]
        ),
        family_report_shas,
        matrix_path, matrix_sha, matrix_cases,
    )
    dispositions: dict[str, int] = {}
    for group in resolved.values():
        dispositions[group["disposition"]] = dispositions.get(group["disposition"], 0) + 1
    return {
        "public_names": len(public), "new_names": len(new_names), "dispositions": dispositions,
        "projections": projections,
    }


def emit_v2_contract(
    contract_path: Path,
    source_commit: str,
    contract_out: Path,
    surface_out: Path,
) -> None:
    """Materialize the already-decided v2 public surface for G5 identity binding."""
    contract = load_json(contract_path, "migration contract")
    source_commit = _commit(source_commit, "dialect-v2 source commit")
    source = contract["source_profile"]
    v1_path = _path(source["dialect_contract"], "source_profile.dialect_contract")
    if v1_path is None:
        raise MigrationError("source dialect contract is missing")
    v1 = V1.load_json(v1_path, "frozen dialect-v1 contract")
    V1.validate_schema(v1)
    public, current_surfaces, _deliveries = _public_inventory(v1)
    classified, new_names, replacement_targets = _classification(
        contract["classification"], public, current_surfaces,
    )
    syntax = _syntax(contract["syntax"])
    target_macros = syntax["target_public_macros"]
    target_names = _target_public_names(
        classified, new_names, replacement_targets, target_macros,
    )
    registry = load_json(
        ROOT / "config" / "v2-native-function-registry.json",
        "dialect-v2 native function registry",
    )
    primitive_names = {
        row["name"] for row in registry.get("entries", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }

    definitions = []
    for name in sorted(target_names):
        if name in target_macros:
            kind = "macro"
        elif name in primitive_names:
            kind = "primitive"
        else:
            record = new_names.get(name) or classified.get(name)
            if record is None:
                raise MigrationError(f"cannot derive v2 definition kind/delivery: {name}")
            kind = "function"
        definitions.append({"name": name, "visibility": "public", "kind": kind})

    migration_sha = _sha(contract_path)
    surface = {
        "format": "lisp65-dialect-v2-surface-manifest-v1",
        "profile": "dialect-v2",
        "surface_id": "canonical-public",
        "migration_contract_sha256": migration_sha,
        "source_commit": source_commit,
        "definitions": definitions,
    }
    surface_out.parent.mkdir(parents=True, exist_ok=True)
    surface_out.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n", encoding="ascii")
    try:
        surface_rel = surface_out.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise MigrationError("dialect-v2 surface output must be inside the repository") from exc
    value = {
        "format": "lisp65-dialect-v2-contract-v1",
        "version": 1,
        "profile": "dialect-v2",
        "migration_contract_sha256": migration_sha,
        "source_commit": source_commit,
        "public_names": sorted(target_names),
        "surfaces": [{
            "id": "canonical-public",
            "manifest": surface_rel,
            "manifest_sha256": _sha(surface_out),
        }],
    }
    contract_out.parent.mkdir(parents=True, exist_ok=True)
    contract_out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    _validate_v2_contract(
        contract_out, _sha(contract_out), migration_sha, target_names, source_commit,
    )
    print(
        "dialect-v2 contract: PASS "
        f"public={len(target_names)} sha256={_sha(contract_out)} source={source_commit}"
    )


def _expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except MigrationError:
        return
    raise MigrationError(f"selftest mutation was accepted: {label}")


def selftest() -> None:
    base = load_json(DEFAULT_CONTRACT, "migration contract")
    selection = load_json(DEFAULT_SELECTION, "profile selection")
    validate(base, selection, DEFAULT_CONTRACT)

    def mutation(change: Callable[[dict[str, Any], dict[str, Any]], None]) -> Callable[[], None]:
        def run() -> None:
            contract = deepcopy(base)
            selected = deepcopy(selection)
            change(contract, selected)
            validate(contract, selected, DEFAULT_CONTRACT)
        return run

    _expect_failure("v1 hash", mutation(lambda contract, _selection: contract["source_profile"].update(dialect_contract_sha256="0" * 64)))
    _expect_failure("v1 features", mutation(lambda contract, _selection: contract["source_profile"].update(features="allowed")))
    _expect_failure("runtime release", mutation(lambda contract, _selection: contract["release_policy"].update(runtime_core="release")))
    _expect_failure("runtime receipt", mutation(lambda contract, _selection: contract["release_policy"].update(runtime_core_receipt_effect="family-advance")))
    _expect_failure("third work line", mutation(lambda contract, _selection: contract["release_policy"]["active_work_lines"].append("buffer")))
    _expect_failure("family hold", mutation(lambda contract, _selection: contract["release_policy"]["family_status_hold"].update({"ide": "planned"})))
    _expect_failure("coverage", mutation(lambda contract, _selection: contract["classification"]["name_groups"][0]["names"].pop()))
    _expect_failure("duplicate", mutation(lambda contract, _selection: contract["classification"]["name_groups"][1]["names"].append("abs")))
    _expect_failure("stale pattern", mutation(lambda contract, _selection: contract["classification"]["pattern_groups"][0].update(prefix="missing-")))
    _expect_failure("replacement", mutation(lambda contract, _selection: contract["classification"]["replacements"].pop()))
    _expect_failure("removal reason", mutation(lambda contract, _selection: contract["classification"]["removals"][0].update(reason="")))
    _expect_failure("family order", mutation(lambda contract, _selection: contract["families"].reverse()))
    _expect_failure("unload dependency", mutation(lambda contract, _selection: contract["deferred_blocks"][3].update(requires=["export-only-interning-require"])))
    _expect_failure(
        "buffer/string block dependency",
        mutation(
            lambda contract, _selection: next(
                item for item in contract["deferred_blocks"]
                if item["id"] == "buffer-and-string-construction-block"
            ).update(requires=[])
        ),
    )
    _expect_failure(
        "Lists capability/carrier dependency",
        mutation(lambda contract, _selection: contract["families"][1].update(requires_blocks=[])),
    )
    def missing_carrier_seal_pointer(
        contract: dict[str, Any], _selection: dict[str, Any],
    ) -> None:
        block = next(
            item for item in contract["deferred_blocks"]
            if item["id"] == "v2-capability-carrier"
        )
        block["contract"] = "config/missing-capability-carrier-seal.json"
        block["completion"]["contract"] = block["contract"]

    _expect_failure(
        "capability/carrier live seal pointer",
        mutation(missing_carrier_seal_pointer),
    )
    _expect_failure("v2 without G5", mutation(lambda _contract, selection_value: selection_value.update(active_profile="dialect-v2")))
    _expect_failure("unknown family", mutation(lambda contract, _selection: contract["classification"]["name_groups"][0].update(family="typo")))
    _expect_failure("fake family evidence", mutation(lambda contract, _selection: contract["families"][0].update(status="migrated", semantic_contracts=["does-not-exist"], measurement={})))
    _expect_failure(
        "ready with blockers",
        mutation(
            lambda contract, _selection: (
                contract.update(status="ready-for-g5"),
                contract["open_decisions"][0].update(status="pending"),
            )
        ),
    )
    _expect_failure(
        "artifact arity range drift",
        mutation(
            lambda contract, _selection: contract["artifact_arity_contract"].update(
                sha256="0" * 64
            )
        ),
    )
    _expect_failure("syntax snapshot drift", mutation(lambda contract, _selection: (contract["syntax"]["special_forms_current"].pop(), contract["syntax"]["special_forms_target"].pop())))
    _expect_failure("matrix binding", mutation(lambda contract, _selection: contract["switch_criteria"].update(matrix_contract_sha256="0" * 64)))
    _expect_failure("selection source commit", mutation(lambda _contract, selection_value: selection_value["profiles"][0].update(source_commit="0" * 40)))
    _expect_failure("pattern target", mutation(lambda contract, _selection: contract["classification"]["pattern_groups"][0].update(target_delivery="none")))
    _expect_failure(
        "bogus reader vocabulary",
        mutation(lambda contract, _selection: contract["syntax"].update(reader_tokens=["garbage"])),
    )
    _expect_failure(
        "lambda-list snapshot drift",
        mutation(lambda contract, _selection: contract["syntax"]["lambda_list_forms_target"].pop()),
    )
    _expect_failure(
        "overlapping macro partition",
        mutation(
            lambda contract, _selection: contract["syntax"]["macro_migrations"].insert(
                0,
                {
                    "name": "and", "disposition": "keep", "family": "prelude-control",
                    "source_delivery": "bank5-preload", "target_delivery": "bank5-preload",
                    "target_library": None, "semantic_status": "specified",
                }
            )
        ),
    )
    _expect_failure(
        "invalid new-name target",
        mutation(
            lambda contract, _selection: contract["classification"]["new_names"][0].update(
                target_role="removed", target_delivery="none"
            )
        ),
    )
    _expect_failure(
        "out-of-order in-progress family",
        mutation(lambda contract, _selection: contract["families"][3].update(status="in-progress")),
    )
    _expect_failure(
        "completed block without receipt",
        mutation(
            lambda contract, _selection: next(
                item for item in contract["deferred_blocks"]
                if item["status"] == "deferred"
            ).update(status="completed")
        ),
    )

    def wrong_frozen_commit(contract: dict[str, Any], selected: dict[str, Any]) -> None:
        commit = "78083d6b79df189e97c617577f7b89d62d4a3219"
        contract["source_profile"]["source_commit"] = commit
        selected["profiles"][0]["source_commit"] = commit

    _expect_failure("frozen commit blob binding", mutation(wrong_frozen_commit))
    _expect_failure(
        "unrelated semantic contract",
        lambda: _verify_family_semantics(
            "lists", ["reader"], _semantic_contract_registry()
        ),
    )

    with tempfile.TemporaryDirectory(prefix=".dialect-migration-selftest-", dir=ROOT) as directory:
        temp = Path(directory)

        def write_json(name: str, value: Any) -> Path:
            path = temp / name
            path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
            return path

        def relative(path: Path) -> str:
            return path.relative_to(ROOT).as_posix()

        artifact = temp / "artifact.bin"
        artifact.write_bytes(b"abcd")
        budget_manifest = write_json(
            "budget.json",
            {
                "format": "lisp65-dialect-family-artifact-v1",
                "profile": "dialect-v2",
                "family": "strings",
                "loaded_symbols": ["a", "bb"],
                "boot_symbols": ["a"],
                "directory_entries": ["a"],
                "artifact": {"path": relative(artifact), "sha256": _sha(artifact)},
            },
        )
        _, metrics = _budget_artifact_manifest(
            relative(budget_manifest), _sha(budget_manifest), "strings", "dialect-v2",
            "selftest budget manifest",
        )
        if metrics != {
            "loaded_symbols": 2, "loaded_namepool_bytes": 5,
            "boot_symbols": 1, "boot_namepool_bytes": 2,
            "directory_entries": 1, "artifact_bytes": 4,
        }:
            raise MigrationError("selftest budget manifest was not recomputed")

        migration_sha = "1" * 64
        source_commit = base["source_profile"]["source_commit"]
        surface_manifest = write_json(
            "surface.json",
            {
                "format": "lisp65-dialect-v2-surface-manifest-v1",
                "profile": "dialect-v2",
                "surface_id": "core",
                "migration_contract_sha256": migration_sha,
                "source_commit": source_commit,
                "definitions": [
                    {"name": "%private", "visibility": "internal", "kind": "function"},
                    {"name": "visible", "visibility": "public", "kind": "function"},
                ],
            },
        )
        if _v2_surface_public_names(
            relative(surface_manifest), _sha(surface_manifest), "core",
            migration_sha, source_commit,
        ) != {"visible"}:
            raise MigrationError("selftest v2 surface did not derive public definitions")

        decisions = _open_decisions(
            base["open_decisions"], set(R2_DECISIONS.DECISION_IDS)
        )
        required_engines = ["engine-a", "engine-b"]
        fixture = {
            "format": "lisp65-dialect-v2-lists-cases-v1",
            "profile": "dialect-v1-v2-differential",
            "family": "lists",
            "cases": [
                {
                    "id": "case-a", "tier": "core", "forms": ["(car '(1))"],
                    "migration_anchor": None,
                    "observations": {
                        "dialect-v1": {"engine-a": "1", "engine-b": "1"},
                        "dialect-v2": {"engine-a": "1", "engine-b": "1"},
                    },
                },
                {
                    "id": "case-b", "tier": "core", "forms": ["(car 1)"],
                    "migration_anchor": None,
                    "observations": {
                        "dialect-v1": {"engine-a": "!error", "engine-b": "nil"},
                        "dialect-v2": {"engine-a": "!error", "engine-b": "nil"},
                    },
                },
            ],
        }
        fixture_cases = _family_fixture_cases(
            fixture, "lists", required_engines, decisions
        )
        resolved_fixture = deepcopy(fixture)
        resolved_fixture["cases"][0]["forms"] = ["(/= 1)"]
        resolved_fixture["cases"][0]["migration_anchor"] = "decision:not-equal-binary-arity"
        resolved_fixture["cases"][0]["observations"]["dialect-v1"]["engine-a"] = "t"
        resolved_fixture["cases"][0]["observations"]["dialect-v2"]["engine-a"] = "!error"
        resolved_fixture_cases = _family_fixture_cases(
            resolved_fixture, "lists", required_engines, decisions
        )
        equal_anchored_fixture = deepcopy(fixture)
        equal_anchored_fixture["cases"][0]["migration_anchor"] = "decision:not-equal-binary-arity"
        _expect_failure(
            "equal fixture observation with decision anchor",
            lambda: _family_fixture_cases(
                equal_anchored_fixture, "lists", required_engines, decisions
            ),
        )
        unanchored_difference_fixture = deepcopy(resolved_fixture)
        unanchored_difference_fixture["cases"][0]["migration_anchor"] = None
        _expect_failure(
            "different fixture observation without decision anchor",
            lambda: _family_fixture_cases(
                unanchored_difference_fixture, "lists", required_engines, decisions
            ),
        )
        pending_fixture = deepcopy(resolved_fixture)
        pending_fixture["cases"][0]["migration_anchor"] = "decision:edit-autoload"
        pending_decisions = deepcopy(decisions)
        pending_decisions["edit-autoload"] = {
            "id": "edit-autoload", "status": "pending",
            "blocks_profile_switch": True,
        }
        _expect_failure(
            "fixture observation anchored to pending decision",
            lambda: _family_fixture_cases(
                pending_fixture, "lists", required_engines, pending_decisions
            ),
        )
        unknown_fixture = deepcopy(resolved_fixture)
        unknown_fixture["cases"][0]["migration_anchor"] = "decision:not-in-contract"
        _expect_failure(
            "fixture observation anchored to unknown decision",
            lambda: _family_fixture_cases(
                unknown_fixture, "lists", required_engines, decisions
            ),
        )
        incomplete_observations_fixture = deepcopy(fixture)
        del incomplete_observations_fixture["cases"][0]["observations"]["dialect-v2"]["engine-b"]
        _expect_failure(
            "fixture profile without complete engine observations",
            lambda: _family_fixture_cases(
                incomplete_observations_fixture, "lists", required_engines, decisions
            ),
        )

        def verdict_cases_for(
            cases: dict[str, dict[str, Any]], profile: str, engine_id: str
        ) -> list[dict[str, Any]]:
            return [
                {
                    "id": case_id,
                    "verdict": "accept",
                    "result_sha256": _family_observation_sha(
                        case["observations"][profile][engine_id]
                    ),
                    "decision": case["migration_anchor"],
                }
                for case_id, case in cases.items()
            ]

        baseline_cases = verdict_cases_for(fixture_cases, "dialect-v1", "engine-a")
        candidate_cases = verdict_cases_for(fixture_cases, "dialect-v2", "engine-a")
        def test_provenance(profile: str) -> dict[str, Any]:
            digit = "8" if profile == "dialect-v1" else "9"
            return {
                "source_commit": None,
                "binary_sha256": digit * 64,
                "build_profile_sha256": digit * 64,
                "preload_sha256": digit * 64,
            }

        baseline_verdict = write_json(
            "baseline-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v1", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v1"),
                "cases": baseline_cases,
            },
        )
        candidate_verdict = write_json(
            "candidate-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": candidate_cases,
            },
        )
        _require_conformant_family_verdicts(
            relative(baseline_verdict), _sha(baseline_verdict),
            relative(candidate_verdict), _sha(candidate_verdict),
            "lists", "engine-a", "4" * 64, fixture_cases, decisions,
        )
        _expect_failure(
            "verdict artifact SHA",
            lambda: _require_conformant_family_verdicts(
                relative(baseline_verdict), "0" * 64,
                relative(candidate_verdict), _sha(candidate_verdict),
                "lists", "engine-a", "4" * 64, fixture_cases, decisions,
            ),
        )
        incomplete = write_json(
            "incomplete-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": candidate_cases[:1],
            },
        )
        _expect_failure(
            "incomplete fixture verdict",
            lambda: _require_conformant_family_verdicts(
                relative(baseline_verdict), _sha(baseline_verdict),
                relative(incomplete), _sha(incomplete), "lists", "engine-a", "4" * 64,
                fixture_cases, decisions,
            ),
        )
        missing_decision_cases = deepcopy(candidate_cases)
        del missing_decision_cases[0]["decision"]
        missing_decision = write_json(
            "missing-decision-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": missing_decision_cases,
            },
        )
        _expect_failure(
            "verdict case without explicit decision field",
            lambda: _require_conformant_family_verdicts(
                relative(baseline_verdict), _sha(baseline_verdict),
                relative(missing_decision), _sha(missing_decision),
                "lists", "engine-a", "4" * 64, fixture_cases, decisions,
            ),
        )
        wrong_observation_cases = deepcopy(candidate_cases)
        wrong_observation_cases[0]["result_sha256"] = _family_observation_sha("wrong")
        wrong_observation = write_json(
            "divergent-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": wrong_observation_cases,
            },
        )
        _expect_failure(
            "verdict result not bound to engine/profile expectation",
            lambda: _require_conformant_family_verdicts(
                relative(baseline_verdict), _sha(baseline_verdict),
                relative(wrong_observation), _sha(wrong_observation), "lists", "engine-a", "4" * 64,
                fixture_cases, decisions,
            ),
        )

        anchored_baseline_cases = verdict_cases_for(
            resolved_fixture_cases, "dialect-v1", "engine-a"
        )
        anchored_candidate_cases = verdict_cases_for(
            resolved_fixture_cases, "dialect-v2", "engine-a"
        )
        anchored_baseline = write_json(
            "anchored-baseline-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v1", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v1"),
                "cases": anchored_baseline_cases,
            },
        )
        anchored_candidate = write_json(
            "anchored-candidate-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": anchored_candidate_cases,
            },
        )
        _require_conformant_family_verdicts(
            relative(anchored_baseline), _sha(anchored_baseline),
            relative(anchored_candidate), _sha(anchored_candidate),
            "lists", "engine-a", "4" * 64, resolved_fixture_cases, decisions,
        )
        wrong_profile_observation_cases = deepcopy(anchored_candidate_cases)
        wrong_profile_observation_cases[0]["result_sha256"] = anchored_baseline_cases[0]["result_sha256"]
        wrong_profile_observation = write_json(
            "wrong-profile-observation-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": wrong_profile_observation_cases,
            },
        )
        _expect_failure(
            "verdict bound to other profile observation",
            lambda: _require_conformant_family_verdicts(
                relative(anchored_baseline), _sha(anchored_baseline),
                relative(wrong_profile_observation), _sha(wrong_profile_observation),
                "lists", "engine-a", "4" * 64, resolved_fixture_cases, decisions,
            ),
        )
        pending_candidate_cases = deepcopy(anchored_candidate_cases)
        pending_candidate_cases[0]["decision"] = "decision:edit-autoload"
        pending_candidate = write_json(
            "pending-anchored-candidate-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": pending_candidate_cases,
            },
        )
        _expect_failure(
            "verdict observation anchored to pending decision",
            lambda: _require_conformant_family_verdicts(
                relative(anchored_baseline), _sha(anchored_baseline),
                relative(pending_candidate), _sha(pending_candidate),
                "lists", "engine-a", "4" * 64, resolved_fixture_cases, pending_decisions,
            ),
        )
        mismatched_candidate_cases = deepcopy(anchored_candidate_cases)
        mismatched_candidate_cases[0]["decision"] = "decision:remainder-v2-surface"
        mismatched_candidate = write_json(
            "mismatched-anchored-candidate-verdict.json",
            {
                "format": "lisp65-dialect-v2-family-verdict-v1", "family": "lists",
                "profile": "dialect-v2", "engine": "engine-a", "fixture_sha256": "4" * 64,
                "provenance": test_provenance("dialect-v2"),
                "cases": mismatched_candidate_cases,
            },
        )
        _expect_failure(
            "verdict decision does not match fixture decision",
            lambda: _require_conformant_family_verdicts(
                relative(anchored_baseline), _sha(anchored_baseline),
                relative(mismatched_candidate), _sha(mismatched_candidate),
                "lists", "engine-a", "4" * 64, resolved_fixture_cases, decisions,
            ),
        )

        block_evidence = temp / "block-evidence.txt"
        block_evidence.write_text("passed\n", encoding="ascii")
        block_contract = write_json(
            "block-contract.json",
            {"format": "lisp65-architecture-block-contract-v1", "id": "x", "status": "implemented", "gate": "G2"},
        )
        block_receipt = write_json(
            "block-receipt.json",
            {
                "format": "lisp65-architecture-block-receipt-v2", "block_id": "x",
                "contract_sha256": _sha(block_contract), "gate": "G2", "result": "passed",
                "bank_delta": {
                    "baseline_product_sha256": "1" * 64,
                    "candidate_product_sha256": "1" * 64,
                    "baseline_banked_headroom_bytes": 435,
                    "candidate_banked_headroom_bytes": 435,
                    "delta_bytes": 0,
                    "authorization": None,
                },
                "evidence": [{"path": relative(block_evidence), "sha256": _sha(block_evidence)}],
            },
        )
        _block_completion(
            {
                "contract": relative(block_contract), "contract_sha256": _sha(block_contract),
                "receipt": relative(block_receipt), "receipt_sha256": _sha(block_receipt),
            },
            "x",
        )
        legacy_block_receipt = write_json(
            "legacy-block-receipt.json",
            {
                "format": "lisp65-architecture-block-receipt-v1", "block_id": "x",
                "contract_sha256": _sha(block_contract), "gate": "G2", "result": "passed",
                "evidence": [{"path": relative(block_evidence), "sha256": _sha(block_evidence)}],
            },
        )
        _expect_failure(
            "future architecture receipt lacks bank delta",
            lambda: _block_completion(
                {
                    "contract": relative(block_contract), "contract_sha256": _sha(block_contract),
                    "receipt": relative(legacy_block_receipt), "receipt_sha256": _sha(legacy_block_receipt),
                },
                "x",
            ),
        )
        unauthorized_block_receipt = write_json(
            "unauthorized-block-receipt.json",
            {
                "format": "lisp65-architecture-block-receipt-v2", "block_id": "x",
                "contract_sha256": _sha(block_contract), "gate": "G2", "result": "passed",
                "bank_delta": {
                    "baseline_product_sha256": "1" * 64,
                    "candidate_product_sha256": "2" * 64,
                    "baseline_banked_headroom_bytes": 435,
                    "candidate_banked_headroom_bytes": 434,
                    "delta_bytes": -1,
                    "authorization": None,
                },
                "evidence": [{"path": relative(block_evidence), "sha256": _sha(block_evidence)}],
            },
        )
        _expect_failure(
            "future architecture receipt has unauthorized bank debit",
            lambda: _block_completion(
                {
                    "contract": relative(block_contract), "contract_sha256": _sha(block_contract),
                    "receipt": relative(unauthorized_block_receipt), "receipt_sha256": _sha(unauthorized_block_receipt),
                },
                "x",
            ),
        )



def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--show-projections", action="store_true")
    parser.add_argument("--emit-v2-contract", action="store_true")
    parser.add_argument("--v2-source-commit")
    parser.add_argument("--v2-contract-out", type=Path, default=Path("config/dialect-v2-contract.json"))
    parser.add_argument("--v2-surface-out", type=Path, default=Path("config/dialect-v2-surface.json"))
    args = parser.parse_args(argv)
    contract_path = args.contract if args.contract.is_absolute() else ROOT / args.contract
    selection_path = args.selection if args.selection.is_absolute() else ROOT / args.selection
    try:
        if args.emit_v2_contract:
            if args.v2_source_commit is None:
                raise MigrationError("--emit-v2-contract requires --v2-source-commit")
            contract_out = args.v2_contract_out if args.v2_contract_out.is_absolute() else ROOT / args.v2_contract_out
            surface_out = args.v2_surface_out if args.v2_surface_out.is_absolute() else ROOT / args.v2_surface_out
            emit_v2_contract(contract_path, args.v2_source_commit, contract_out, surface_out)
            return 0
        if args.selftest:
            selftest()
            print("dialect-migration-contract: SELFTEST PASS mutations=40")
            return 0
        result = validate(
            load_json(contract_path, "migration contract"),
            load_json(selection_path, "profile selection"),
            contract_path,
            allow_missing_projection=args.show_projections,
        )
    except (MigrationError, V1.DialectContractError) as exc:
        print(f"dialect-migration-contract: FAIL: {exc}", file=sys.stderr)
        return 1
    if args.show_projections:
        print(json.dumps(result["projections"], indent=2, sort_keys=True))
    print(
        "dialect-migration-contract: PASS public={public_names} new={new_names} dispositions={dispositions}".format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
