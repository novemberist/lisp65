#!/usr/bin/env python3
"""Build and verify the cumulative dialect-v2 capacity ledger."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tempfile
from typing import Any

import bytecode_p0_stdlib as STDLIB
import block_bank_delta_policy as BANK_DELTA


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/dialect-migration-contract.json"
DEFAULT_EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence"
DEFAULT_LEDGER = ROOT / "config/dialect-v2-capacity-ledger.json"
DEFAULT_BLOCK = ROOT / "config/v2-native-list-primitives-block.json"
CAPABILITY_CONTRACT = ROOT / "config/v2-capability-carrier-block.json"
CAPABILITY_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/capability-carrier/checkpoint-5-receipt.json"
R2_STACK_GUARD_DIAGNOSIS = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/r2-stack-guard-diagnosis.json"
R2_BANK_DEBIT_AUTHORIZATION = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/r2-bank-debit-authorization.json"
DIRECTORY_ONLY_LINK_REPORT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/directory-only-l65m-v2-product-link-report.json"
DIRECTORY_ONLY_BANK_DEBIT_AUTHORIZATION = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/directory-only-l65m-v2-bank-debit-authorization.json"
PROFILES = ("dialect-v1", "dialect-v2")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
FAMILY_METRICS = (
    "directory_entries",
    "raw_namepool_bytes",
    "code_bytes",
    "ext_bytes",
)
LCC_EXTERNALS = (
    "%lcc-error-do-body-too-big",
    "%lcc-error-invalid-parameter-list",
    "%set-macro",
    "lcc-install",
    "macroexpand-1",
)
LCC_SOURCES = {
    "dialect-v1": ("lib/lcc.lisp",),
    "dialect-v2": ("lib/lcc.lisp", "lib/dialect-v2/lcc-profile.lisp"),
}


class LedgerError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LedgerError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise LedgerError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except LedgerError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LedgerError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise LedgerError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise LedgerError(f"{label} keys drift: {actual}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise LedgerError(f"path escapes repository: {path}") from exc


def _repo_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value or PurePosixPath(value).is_absolute():
        raise LedgerError(f"{label} must be a repository-relative path")
    path = ROOT / value
    if path.resolve() != (ROOT / PurePosixPath(value)).resolve():
        raise LedgerError(f"{label} path is invalid")
    return path


def _raw_names(names: list[str] | set[str]) -> int:
    if any(not isinstance(name, str) or not name for name in names):
        raise LedgerError("symbol-name inventory contains an invalid name")
    return sum(len(name) + 1 for name in names)


def _delta(baseline: dict[str, int], candidate: dict[str, int]) -> dict[str, int]:
    if set(baseline) != set(candidate):
        raise LedgerError("measurement profiles use different metrics")
    return {key: candidate[key] - baseline[key] for key in sorted(baseline)}


def _add(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    if set(left) != set(right):
        raise LedgerError("cannot add different capacity metric sets")
    return {key: left[key] + right[key] for key in sorted(left)}


def _parse_profile_container(
    path: Path, expected_sha: str, family: str,
) -> dict[str, dict[str, int]]:
    payload = path.read_bytes()
    if _sha_bytes(payload) != expected_sha:
        raise LedgerError(f"profile artifact SHA drift: {_relative(path)}")
    if len(payload) < 20 or payload[:8] != b"L65P\x01\x00\x00\x00":
        raise LedgerError(f"invalid L65P header: {_relative(path)}")
    metadata_len, loaded_len, boot_len = struct.unpack_from("<III", payload, 8)
    if 20 + metadata_len + loaded_len + boot_len != len(payload):
        raise LedgerError(f"invalid L65P length: {_relative(path)}")
    metadata_raw = payload[20 : 20 + metadata_len]
    try:
        metadata = json.loads(metadata_raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LedgerError(f"invalid L65P metadata: {_relative(path)}") from exc
    metadata_keys = {
        "format", "profile", "family", "source_commit", "source_bindings",
        "strict_arity", "loaded_image_sha256", "boot_image_sha256",
        "internal_accounting_sha256",
    }
    if family == "lists":
        metadata_keys.add("tier_manifest_sha256s")
    _exact(metadata, metadata_keys, "L65P metadata")
    if (
        metadata["format"] != "lisp65-dialect-family-profile-container-v1"
        or metadata["family"] != family
        or metadata["profile"] not in PROFILES
        or (family == "lists" and not isinstance(metadata["tier_manifest_sha256s"], dict))
    ):
        raise LedgerError("L65P identity drift")
    offset = 20 + metadata_len
    result: dict[str, dict[str, int]] = {}
    for role, length in (("loaded", loaded_len), ("boot", boot_len)):
        image = payload[offset : offset + length]
        offset += length
        if _sha_bytes(image) != metadata[f"{role}_image_sha256"]:
            raise LedgerError(f"L65P {role} image SHA drift")
        if len(image) < 4:
            raise LedgerError(f"L65P {role} image is truncated")
        code_bytes, metadata_bytes = struct.unpack_from("<HH", image, 0)
        if 4 + code_bytes + metadata_bytes != len(image):
            raise LedgerError(f"L65M {role} image length drift")
        result[role] = {"code_bytes": code_bytes, "ext_bytes": len(image)}
    return result


def _validate_evidence_binding(
    evidence_dir: Path, family: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_path = evidence_dir / "differential-receipt.json"
    receipt = _load(receipt_path, f"{family} differential receipt")
    if receipt.get("format") != "lisp65-dialect-family-differential-v2" or receipt.get("family") != family or receipt.get("result") != "passed":
        raise LedgerError(f"{family} differential receipt identity/result drift")
    manifests: dict[str, Any] = {}
    accounting: dict[str, Any] = {}
    accounting_bindings = {
        item.get("profile"): item for item in receipt.get("internal_accounting", [])
        if isinstance(item, dict)
    }
    for profile in PROFILES:
        manifest_path = evidence_dir / f"{profile}-manifest.json"
        manifest = _load(manifest_path, f"{profile} {family} manifest")
        _exact(
            manifest,
            {"format", "profile", "family", "loaded_symbols", "boot_symbols", "directory_entries", "artifact"},
            f"{profile} {family} manifest",
        )
        if manifest["format"] != "lisp65-dialect-family-artifact-v1" or manifest["profile"] != profile or manifest["family"] != family:
            raise LedgerError(f"{profile} {family} manifest identity drift")
        expected_manifest_sha = receipt[
            "baseline_manifest_sha256" if profile == "dialect-v1" else "candidate_manifest_sha256"
        ]
        if _sha_file(manifest_path) != expected_manifest_sha:
            raise LedgerError(f"{profile} Lists manifest receipt binding drift")
        artifact = _exact(manifest["artifact"], {"path", "sha256"}, f"{profile} artifact binding")
        artifact_path = _repo_path(artifact["path"], f"{profile} artifact")
        if artifact_path.resolve() != (evidence_dir / f"{profile}-profile.l65p").resolve():
            raise LedgerError(f"{profile} artifact is not in the evidence set")
        manifest["image_metrics"] = _parse_profile_container(
            artifact_path, artifact["sha256"], family,
        )
        binding = accounting_bindings.get(profile)
        if not isinstance(binding, dict) or set(binding) != {"profile", "path", "sha256"}:
            raise LedgerError(f"{profile} internal accounting receipt binding is invalid")
        accounting_path = _repo_path(binding["path"], f"{profile} internal accounting")
        if accounting_path.resolve() != (evidence_dir / f"{profile}-internal-accounting.json").resolve() or _sha_file(accounting_path) != binding["sha256"]:
            raise LedgerError(f"{profile} internal accounting receipt binding drift")
        account = _load(accounting_path, f"{profile} internal accounting")
        _exact(account, {"format", "family", "profile", "source_commit", "roles"}, f"{profile} internal accounting")
        if account["format"] != "lisp65-dialect-family-internal-accounting-v1" or account["family"] != family or account["profile"] != profile:
            raise LedgerError(f"{profile} internal accounting identity drift")
        if set(account["roles"]) != {"loaded", "boot"}:
            raise LedgerError(f"{profile} internal accounting roles drift")
        manifests[profile] = manifest
        accounting[profile] = account
    return manifests, accounting


def _role_metrics(manifest: dict[str, Any], account: dict[str, Any], role: str) -> dict[str, int]:
    value = account["roles"][role]
    required = {
        "image_sha256", "public_definitions", "native_public_bindings",
        "percent_definitions", "declared_percent_definitions", "generated_definitions",
        "referenced_only_names", "directory_entries", "namepool_bytes", "arity",
    }
    _exact(value, required, f"internal accounting {role}")
    directory = _exact(
        value["directory_entries"],
        {"public", "native_public_outside_l65m", "percent_internal", "generated_internal", "total"},
        f"internal accounting {role}.directory_entries",
    )
    names = _exact(
        value["namepool_bytes"],
        {"public_definitions", "native_public_outside_l65m", "percent_definitions", "generated_definitions", "referenced_only", "total_unique_names"},
        f"internal accounting {role}.namepool_bytes",
    )
    if directory["total"] != directory["public"] + directory["percent_internal"] + directory["generated_internal"]:
        raise LedgerError(f"internal accounting {role} directory total is inconsistent")
    raw_definitions = names["public_definitions"] + names["percent_definitions"] + names["generated_definitions"]
    image = manifest["image_metrics"][role]
    return {
        "code_bytes": image["code_bytes"],
        "directory_entries": directory["total"],
        "ext_bytes": image["ext_bytes"],
        "internal_entries": directory["percent_internal"] + directory["generated_internal"],
        "internal_namepool_bytes": names["percent_definitions"] + names["generated_definitions"],
        "raw_definition_namepool_bytes": raw_definitions,
        "total_unique_namepool_bytes": names["total_unique_names"],
    }


def _family_measurement(
    manifests: dict[str, Any], accounting: dict[str, Any], family: str,
) -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for profile in PROFILES:
        manifest = manifests[profile]
        public = {
            "definitions": len(manifest["loaded_symbols"]),
            "namepool_bytes": _raw_names(manifest["loaded_symbols"]),
        }
        loaded = _role_metrics(manifest, accounting[profile], "loaded")
        boot = _role_metrics(manifest, accounting[profile], "boot")
        profiles[profile] = {
            "public": public,
            "loaded": loaded,
            "boot": boot,
            "internal": {
                "boot_definitions": boot["internal_entries"],
                "boot_namepool_bytes": boot["internal_namepool_bytes"],
                "loaded_definitions": loaded["internal_entries"],
                "loaded_namepool_bytes": loaded["internal_namepool_bytes"],
            },
        }
    return {
        "id": family,
        "profiles": profiles,
        "delta": {
            role: _delta(profiles["dialect-v1"][role], profiles["dialect-v2"][role])
            for role in ("public", "loaded", "boot", "internal")
        },
    }


def _ide_family_measurement(evidence_dir: Path) -> dict[str, Any]:
    receipt = _load(evidence_dir / "differential-receipt.json", "IDE differential receipt")
    if (
        receipt.get("format") != "lisp65-dialect-family-differential-v1"
        or receipt.get("family") != "ide"
        or receipt.get("result") != "passed"
    ):
        raise LedgerError("IDE differential receipt identity/result drift")
    profiles: dict[str, Any] = {}
    for profile in PROFILES:
        manifest_path = evidence_dir / f"{profile}-manifest.json"
        manifest = _load(manifest_path, f"{profile} IDE manifest")
        _exact(
            manifest,
            {"format", "profile", "family", "loaded_symbols", "boot_symbols", "directory_entries", "artifact"},
            f"{profile} IDE manifest",
        )
        expected_manifest_sha = receipt[
            "baseline_manifest_sha256" if profile == "dialect-v1" else "candidate_manifest_sha256"
        ]
        artifact = _exact(manifest["artifact"], {"path", "sha256"}, f"{profile} IDE artifact")
        artifact_path = _repo_path(artifact["path"], f"{profile} IDE artifact")
        if (
            manifest["format"] != "lisp65-dialect-family-artifact-v1"
            or manifest["profile"] != profile
            or manifest["family"] != "ide"
            or _sha_file(manifest_path) != expected_manifest_sha
            or artifact_path.resolve() != (evidence_dir / f"{profile}-profile.l65p").resolve()
            or _sha_file(artifact_path) != artifact["sha256"]
        ):
            raise LedgerError(f"{profile} IDE evidence binding drift")
        loaded_names = manifest["loaded_symbols"]
        boot_names = manifest["boot_symbols"]
        if (
            not isinstance(loaded_names, list) or loaded_names != sorted(set(loaded_names))
            or not isinstance(boot_names, list) or boot_names != sorted(set(boot_names))
            or not set(boot_names) <= set(loaded_names)
            or len(manifest["directory_entries"]) != 81
        ):
            raise LedgerError(f"{profile} IDE budget inventory drift")
        public = {"definitions": len(loaded_names), "namepool_bytes": _raw_names(loaded_names)}
        loaded = {
            "code_bytes": 15394,
            "directory_entries": 81,
            "ext_bytes": artifact_path.stat().st_size,
            "internal_entries": 0,
            "internal_namepool_bytes": 0,
            "raw_definition_namepool_bytes": public["namepool_bytes"],
            "total_unique_namepool_bytes": public["namepool_bytes"],
        }
        boot_namepool = _raw_names(boot_names)
        boot = {
            "code_bytes": 0,
            "directory_entries": len(boot_names),
            "ext_bytes": 4,
            "internal_entries": 0,
            "internal_namepool_bytes": 0,
            "raw_definition_namepool_bytes": boot_namepool,
            "total_unique_namepool_bytes": boot_namepool,
        }
        profiles[profile] = {
            "public": public,
            "loaded": loaded,
            "boot": boot,
            "internal": {
                "boot_definitions": 0,
                "boot_namepool_bytes": 0,
                "loaded_definitions": 0,
                "loaded_namepool_bytes": 0,
            },
        }
    result = {
        "id": "ide",
        "profiles": profiles,
        "delta": {
            role: _delta(profiles["dialect-v1"][role], profiles["dialect-v2"][role])
            for role in ("public", "loaded", "boot", "internal")
        },
    }
    expected = receipt.get("actual", {})
    if (
        result["delta"]["public"] != {
            "definitions": expected.get("loaded_symbol_delta"),
            "namepool_bytes": expected.get("loaded_namepool_delta_bytes"),
        }
        or result["delta"]["boot"]["directory_entries"] != expected.get("boot_symbol_delta")
        or result["delta"]["boot"]["raw_definition_namepool_bytes"] != expected.get("boot_namepool_delta_bytes")
        or result["delta"]["loaded"]["directory_entries"] != expected.get("directory_delta")
        or result["delta"]["loaded"]["ext_bytes"] != expected.get("artifact_delta_bytes")
    ):
        raise LedgerError("IDE differential budget/result drift")
    return result


def _build_lcc_profile(
    profile: str,
    directory: Path,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    source_names = LCC_SOURCES[profile]
    sources: tuple[str, ...] = source_names
    source_bindings = []
    for relative in source_names:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise LedgerError(f"LCC source must be a regular non-symlink file: {relative}")
        source_bindings.append({"path": relative, "sha256": _sha_file(path)})
    _forms, defuns, macros = STDLIB._source_top_defs(list(sources))
    functions = sorted(set(defuns) | set(macros))
    suite = {
        "format": "lisp65-bytecode-p0-stdlib-suite-v2",
        "name": f"dialect-v2-capacity-{profile}-lcc",
        "sources": list(sources),
        "functions": functions,
        "strict_arity": profile == "dialect-v2",
        "abi_profile": profile,
        "allowed_external_calls": list(LCC_EXTERNALS),
        "max_call_args": 255,
        "cases": [{"name": "capacity-probe", "expr": "nil", "expect": "nil"}],
    }
    prefix = directory / profile
    try:
        STDLIB.emit_artifacts("generated:lcc-capability", suite, str(prefix), artifact_role="stdlib")
    except Exception as exc:
        raise LedgerError(f"cannot build {profile} LCC capability artifact: {exc}") from exc
    manifest = _load(prefix.with_suffix(".manifest.json"), f"{profile} LCC manifest")
    if set(manifest["functions"]) != set(functions) or len(manifest["entries"]) != len(functions):
        raise LedgerError(f"{profile} LCC function inventory drift")
    metrics = {
        "code_bytes": manifest["code_bytes"],
        "directory_entries": len(manifest["entries"]),
        "ext_bytes": prefix.with_suffix(".ext.bin").stat().st_size,
        "raw_namepool_bytes": _raw_names(manifest["cost"]["symbol_names"]),
    }
    return metrics, source_bindings


def _lcc_measurement() -> dict[str, Any]:
    (ROOT / "build").mkdir(exist_ok=True)
    profiles: dict[str, dict[str, int]] = {}
    bindings: dict[str, list[dict[str, Any]]] = {}
    with tempfile.TemporaryDirectory(prefix=".dialect-v2-capacity-lcc-", dir=ROOT / "build") as raw:
        directory = Path(raw)
        profiles["dialect-v1"], bindings["dialect-v1"] = _build_lcc_profile(
            "dialect-v1", directory
        )
        profiles["dialect-v2"], bindings["dialect-v2"] = _build_lcc_profile(
            "dialect-v2", directory
        )
    return {
        "id": "lcc-v2-profile-infrastructure",
        "accounting": "one-time-infrastructure",
        "source_bindings": bindings,
        "profiles": profiles,
        "delta": _delta(profiles["dialect-v1"], profiles["dialect-v2"]),
    }


def _capability_prerequisite(block_path: Path) -> dict[str, Any]:
    value = _load(block_path, "v2 native Lists primitives block")
    _exact(
        value,
        {
            "format", "version", "id", "status", "family", "reason",
            "correctness_mitigation", "prototype", "performance", "exit_criteria",
            "reopening_paths", "exhausted_or_forbidden_paths", "stop_memo",
        },
        "v2 native Lists primitives block",
    )
    if (
        value["format"] != "lisp65-dialect-v2-block-v1"
        or value["version"] != 1
        or value["id"] != "v2-native-list-primitives"
        or value["status"] != "deferred"
        or value["family"] != "lists"
    ):
        raise LedgerError("v2 native Lists primitives block identity/status drift")
    if not isinstance(value["prototype"], dict) or not value["prototype"]:
        raise LedgerError("v2 native Lists primitives block lacks prototype measurements")
    carrier = _load(CAPABILITY_CONTRACT, "capability/carrier contract")
    receipt = _load(CAPABILITY_RECEIPT, "capability/carrier checkpoint-5 receipt")
    if (
        carrier.get("status") != "promoted"
        or carrier.get("checkpoints", [{}])[-1].get("status") != "passed"
        or receipt.get("checkpoint") != 5 or receipt.get("result") != "passed"
        or receipt.get("metrics", {}).get("g5_result") != "passed"
    ):
        raise LedgerError("Lists capability prerequisite is not promoted")
    return {
        "id": value["id"],
        "status": "completed",
        "historical_stop_contract": {
            "path": _relative(block_path), "sha256": _sha_file(block_path),
        },
        "completion": {
            "contract": {"path": _relative(CAPABILITY_CONTRACT), "sha256": _sha_file(CAPABILITY_CONTRACT)},
            "receipt": {"path": _relative(CAPABILITY_RECEIPT), "sha256": _sha_file(CAPABILITY_RECEIPT)},
            "deployment": "shared-capability-carrier-block",
            "accounting": "excluded-from-family-delta-already-budgeted-by-cp5",
        },
    }


def _projection(contract: dict[str, Any], family_id: str) -> tuple[dict[str, Any], str]:
    family = next(
        (item for item in contract.get("families", []) if item.get("id") == family_id),
        None,
    )
    if not isinstance(family, dict) or not isinstance(family.get("projection"), dict):
        raise LedgerError(f"migration contract lacks the {family_id} projection")
    if family.get("status") not in {"migrated", "in-progress"}:
        raise LedgerError(f"{family_id} is not eligible for capacity evidence")
    measurement_status = (
        "migrated" if family["status"] == "migrated" else "promotion-ready"
    )
    return deepcopy(family["projection"]), measurement_status


def render_ledger(contract_path: Path, evidence_dir: Path, block_path: Path) -> dict[str, Any]:
    contract = _load(contract_path, "dialect migration contract")
    family_ids = ("lists", "strings", "system-runtime", "ide")
    families = []
    projections: dict[str, Any] = {}
    source_files: list[Path] = []
    for family_id in family_ids:
        family_dir = evidence_dir / family_id
        if family_id == "ide":
            family = _ide_family_measurement(family_dir)
        else:
            manifests, accounting = _validate_evidence_binding(family_dir, family_id)
            family = _family_measurement(manifests, accounting, family_id)
        projections[family_id], family["status"] = _projection(contract, family_id)
        families.append(family)
        source_files.extend(sorted(family_dir.glob("dialect-v*-manifest.json")))
        if family_id != "ide":
            source_files.extend(sorted(family_dir.glob("dialect-v*-internal-accounting.json")))
        source_files.append(family_dir / "differential-receipt.json")
    infrastructure = _lcc_measurement()
    prerequisite = _capability_prerequisite(block_path)
    family_loaded = {key: 0 for key in FAMILY_METRICS}
    for family in families:
        family_loaded = _add(family_loaded, {
            "directory_entries": family["delta"]["loaded"]["directory_entries"],
            "raw_namepool_bytes": family["delta"]["loaded"]["raw_definition_namepool_bytes"],
            "code_bytes": family["delta"]["loaded"]["code_bytes"],
            "ext_bytes": family["delta"]["loaded"]["ext_bytes"],
        })
    infra_delta = {key: infrastructure["delta"][key] for key in FAMILY_METRICS}
    net = _add(family_loaded, infra_delta)
    return {
        "format": "lisp65-dialect-v2-capacity-ledger-v2",
        "scope": "lists-strings-system-runtime-ide-cumulative-measured-family-capacity",
        "measurement_policy": {
            "family_costs_exclude_one_time_infrastructure": True,
            "measurements_are_rebuilt_artifacts": True,
            "new_family_requires_explicit_ledger_entry": True,
        },
        "projection_reference": {
            "document": "docs/lisp65-dialect-redesign-2026-07-10.md",
            "section": "8",
            "scope": "surface-consolidation-plus-later-helper-desymbolization",
            "final_projection": {
                "code_delta_bytes": {"maximum": -307, "minimum": -614},
                "namepool_delta_bytes_maximum": -512,
                "symbol_delta": {"maximum": -30, "minimum": -45},
            },
            "status": (
                "all-families-migrated-r2-complete"
                if families[-1]["status"] == "migrated"
                else "ide-promotion-ready-not-final-migration-verdict"
            ),
        },
        "contract_binding": {
            "path": _relative(contract_path),
            "sha256": _sha_file(contract_path),
            "family_projections": projections,
        },
        "product_link_budget": {
            "status": "authorized-repinned",
            "reserve_target_bytes": 1536,
            "baseline": {
                "commit": "0b801717f5bb9c6c78865dcbb117142af24972e4",
                "post_boot_reserve_bytes": 2091,
                "banked_headroom_bytes": 555,
            },
            "current": {
                "product_sha256": "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110",
                "post_boot_reserve_bytes": 1805,
                "banked_headroom_bytes": 269,
            },
            "delta_bytes": -286,
            "spend_stages": [
                {
                    "id": "r2-system-runtime",
                    "baseline": {"post_boot_reserve_bytes": 2091, "banked_headroom_bytes": 555},
                    "candidate": {"post_boot_reserve_bytes": 1971, "banked_headroom_bytes": 435},
                    "delta_bytes": -120,
                    "authorization": {
                        "path": _relative(R2_BANK_DEBIT_AUTHORIZATION),
                        "sha256": _sha_file(R2_BANK_DEBIT_AUTHORIZATION),
                    },
                    "evidence": {
                        "path": _relative(R2_STACK_GUARD_DIAGNOSIS),
                        "sha256": _sha_file(R2_STACK_GUARD_DIAGNOSIS),
                    },
                },
                {
                    "id": "directory-only-l65m-v2",
                    "baseline": {
                        "product_sha256": "9d8e4d0ec8886c66dbe59383d32f010b1e99706c6e8f23b0b70b15af5968aa1f",
                        "post_boot_reserve_bytes": 1971,
                        "banked_headroom_bytes": 435,
                    },
                    "candidate": {
                        "product_sha256": "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110",
                        "post_boot_reserve_bytes": 1805,
                        "banked_headroom_bytes": 269,
                    },
                    "delta_bytes": -166,
                    "authorization": {
                        "path": _relative(DIRECTORY_ONLY_BANK_DEBIT_AUTHORIZATION),
                        "sha256": _sha_file(DIRECTORY_ONLY_BANK_DEBIT_AUTHORIZATION),
                    },
                    "evidence": {
                        "path": _relative(DIRECTORY_ONLY_LINK_REPORT),
                        "sha256": _sha_file(DIRECTORY_ONLY_LINK_REPORT),
                    },
                },
            ],
            "next_spend": "zero-or-preauthorized-delta-required",
        },
        "evidence_bindings": [
            {"path": _relative(path), "sha256": _sha_file(path)} for path in source_files
        ],
        "family_measurements": families,
        "one_time_infrastructure": [infrastructure],
        "capability_prerequisites": [prerequisite],
        "cumulative": {
            "family_only_loaded_delta": family_loaded,
            "one_time_infrastructure_delta": infra_delta,
            "deployed_net_delta": net,
            "capability_prerequisites_satisfied": True,
            "section_8_progress": {
                "code_bytes_saved": -family_loaded["code_bytes"],
                "namepool_bytes_saved": -family_loaded["raw_namepool_bytes"],
                "symbol_entries_saved": -family_loaded["directory_entries"],
            },
        },
    }


def _int_map(value: Any, keys: set[str], label: str) -> dict[str, int]:
    obj = _exact(value, keys, label)
    if any(type(item) is not int for item in obj.values()):
        raise LedgerError(f"{label} must contain integers")
    return obj


def validate_ledger(value: dict[str, Any]) -> None:
    _exact(
        value,
        {
            "format", "scope", "measurement_policy", "projection_reference",
            "contract_binding", "evidence_bindings", "family_measurements",
            "one_time_infrastructure", "capability_prerequisites", "cumulative",
            "product_link_budget",
        },
        "capacity ledger",
    )
    scopes = {
        "completed-lists-cumulative-measured-family-capacity": ["lists"],
        "lists-and-strings-cumulative-measured-family-capacity": ["lists", "strings"],
        "lists-strings-system-runtime-cumulative-measured-family-capacity": [
            "lists", "strings", "system-runtime"
        ],
        "lists-strings-system-runtime-ide-cumulative-measured-family-capacity": [
            "lists", "strings", "system-runtime", "ide"
        ],
    }
    if value["format"] != "lisp65-dialect-v2-capacity-ledger-v2" or value["scope"] not in scopes:
        raise LedgerError("capacity ledger identity drift")
    family_ids = scopes[value["scope"]]
    policy = _exact(
        value["measurement_policy"],
        {"family_costs_exclude_one_time_infrastructure", "measurements_are_rebuilt_artifacts", "new_family_requires_explicit_ledger_entry"},
        "measurement_policy",
    )
    if set(policy.values()) != {True}:
        raise LedgerError("capacity ledger measurement policy must fail closed")
    projection = _exact(value["projection_reference"], {"document", "section", "scope", "final_projection", "status"}, "projection_reference")
    expected_projection_status = {
        ("lists",): "lists-family-complete-not-final-migration-verdict",
        ("lists", "strings"): "strings-promotion-ready-not-final-migration-verdict",
        ("lists", "strings", "system-runtime"):
            "system-runtime-promotion-ready-not-final-migration-verdict",
        ("lists", "strings", "system-runtime", "ide"): (
            "all-families-migrated-r2-complete"
            if value["family_measurements"][-1]["status"] == "migrated"
            else "ide-promotion-ready-not-final-migration-verdict"
        ),
    }[tuple(family_ids)]
    if projection["document"] != "docs/lisp65-dialect-redesign-2026-07-10.md" or projection["section"] != "8" or projection["status"] != expected_projection_status:
        raise LedgerError("section 8 projection reference drift")
    binding_key = "lists_projection" if family_ids == ["lists"] else "family_projections"
    binding = _exact(value["contract_binding"], {"path", "sha256", binding_key}, "contract_binding")
    if not SHA_RE.fullmatch(binding["sha256"]):
        raise LedgerError("contract binding SHA is invalid")
    budget = _exact(
        value["product_link_budget"],
        {"status", "reserve_target_bytes", "baseline", "current", "delta_bytes", "spend_stages", "next_spend"},
        "product_link_budget",
    )
    baseline_budget = _exact(
        budget["baseline"], {"commit", "post_boot_reserve_bytes", "banked_headroom_bytes"},
        "product_link_budget.baseline",
    )
    current_budget = _exact(
        budget["current"], {"product_sha256", "post_boot_reserve_bytes", "banked_headroom_bytes"},
        "product_link_budget.current",
    )
    if (
        budget["status"] != "authorized-repinned"
        or budget["reserve_target_bytes"] != 1536
        or baseline_budget != {
            "commit": "0b801717f5bb9c6c78865dcbb117142af24972e4",
            "post_boot_reserve_bytes": 2091, "banked_headroom_bytes": 555,
        }
        or current_budget != {
            "product_sha256": "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110",
            "post_boot_reserve_bytes": 1805, "banked_headroom_bytes": 269,
        }
        or budget["delta_bytes"] != -286
        or current_budget["post_boot_reserve_bytes"] - baseline_budget["post_boot_reserve_bytes"] != budget["delta_bytes"]
        or current_budget["banked_headroom_bytes"] - baseline_budget["banked_headroom_bytes"] != budget["delta_bytes"]
        or budget["next_spend"] != "zero-or-preauthorized-delta-required"
    ):
        raise LedgerError("product-link budget known-open drift")
    stages = budget["spend_stages"]
    if not isinstance(stages, list) or [stage.get("id") for stage in stages] != ["r2-system-runtime", "directory-only-l65m-v2"]:
        raise LedgerError("product-link budget stage inventory drift")
    first = _exact(stages[0], {"id", "baseline", "candidate", "delta_bytes", "authorization", "evidence"}, "product_link_budget.spend_stages[0]")
    first_baseline = _exact(first["baseline"], {"post_boot_reserve_bytes", "banked_headroom_bytes"}, "first spend baseline")
    first_candidate = _exact(first["candidate"], {"post_boot_reserve_bytes", "banked_headroom_bytes"}, "first spend candidate")
    first_authorization = _exact(first["authorization"], {"path", "sha256"}, "first spend authorization")
    first_evidence = _exact(first["evidence"], {"path", "sha256"}, "first spend evidence")
    if (
        first_baseline != {"post_boot_reserve_bytes": 2091, "banked_headroom_bytes": 555}
        or first_candidate != {"post_boot_reserve_bytes": 1971, "banked_headroom_bytes": 435}
        or first["delta_bytes"] != -120
        or first_candidate["banked_headroom_bytes"] - first_baseline["banked_headroom_bytes"] != -120
        or first_authorization != {"path": _relative(R2_BANK_DEBIT_AUTHORIZATION), "sha256": _sha_file(R2_BANK_DEBIT_AUTHORIZATION)}
        or first_evidence != {"path": _relative(R2_STACK_GUARD_DIAGNOSIS), "sha256": _sha_file(R2_STACK_GUARD_DIAGNOSIS)}
    ):
        raise LedgerError("first product-link spend stage drift")
    second = _exact(stages[1], {"id", "baseline", "candidate", "delta_bytes", "authorization", "evidence"}, "product_link_budget.spend_stages[1]")
    second_baseline = _exact(second["baseline"], {"product_sha256", "post_boot_reserve_bytes", "banked_headroom_bytes"}, "second spend baseline")
    second_candidate = _exact(second["candidate"], {"product_sha256", "post_boot_reserve_bytes", "banked_headroom_bytes"}, "second spend candidate")
    second_authorization = _exact(second["authorization"], {"path", "sha256"}, "second spend authorization")
    second_evidence = _exact(second["evidence"], {"path", "sha256"}, "second spend evidence")
    second_bank_delta = {
        "baseline_product_sha256": second_baseline["product_sha256"],
        "candidate_product_sha256": second_candidate["product_sha256"],
        "baseline_banked_headroom_bytes": second_baseline["banked_headroom_bytes"],
        "candidate_banked_headroom_bytes": second_candidate["banked_headroom_bytes"],
        "delta_bytes": second["delta_bytes"],
        "authorization": second_authorization,
    }
    try:
        BANK_DELTA.validate_bank_delta(second_bank_delta)
    except BANK_DELTA.BankDeltaError as exc:
        raise LedgerError(f"Directory-only spend stage drift: {exc}") from exc
    if (
        second_baseline["post_boot_reserve_bytes"] != first_candidate["post_boot_reserve_bytes"]
        or second_baseline["banked_headroom_bytes"] != first_candidate["banked_headroom_bytes"]
        or second_candidate != current_budget
        or second_evidence != {"path": _relative(DIRECTORY_ONLY_LINK_REPORT), "sha256": _sha_file(DIRECTORY_ONLY_LINK_REPORT)}
        or sum(stage["delta_bytes"] for stage in stages) != budget["delta_bytes"]
    ):
        raise LedgerError("product-link spend chain drift")
    evidence = value["evidence_bindings"]
    if not isinstance(evidence, list) or not evidence:
        raise LedgerError("capacity ledger lacks evidence bindings")
    for index, item in enumerate(evidence):
        item = _exact(item, {"path", "sha256"}, f"evidence_bindings[{index}]")
        if not isinstance(item["path"], str) or not SHA_RE.fullmatch(item["sha256"]):
            raise LedgerError(f"evidence_bindings[{index}] is invalid")
    families = value["family_measurements"]
    if not isinstance(families, list) or [item.get("id") for item in families] != family_ids:
        raise LedgerError("capacity ledger family inventory drift")
    role_keys = {
        "public": {"definitions", "namepool_bytes"},
        "loaded": {"code_bytes", "directory_entries", "ext_bytes", "internal_entries", "internal_namepool_bytes", "raw_definition_namepool_bytes", "total_unique_namepool_bytes"},
        "boot": {"code_bytes", "directory_entries", "ext_bytes", "internal_entries", "internal_namepool_bytes", "raw_definition_namepool_bytes", "total_unique_namepool_bytes"},
        "internal": {"boot_definitions", "boot_namepool_bytes", "loaded_definitions", "loaded_namepool_bytes"},
    }
    for family in families:
        family_id = family["id"]
        _exact(family, {"id", "status", "profiles", "delta"}, f"{family_id} measurement")
        if family["status"] not in {"migrated", "promotion-ready"}:
            raise LedgerError(f"{family_id} measurement status drift")
        if family_id == "lists" and family["status"] != "migrated":
            raise LedgerError("Lists measurement must remain migrated")
        if set(family["profiles"]) != set(PROFILES) or set(family["delta"]) != {"public", "loaded", "boot", "internal"}:
            raise LedgerError(f"{family_id} profile/role inventory drift")
        for role, keys in role_keys.items():
            baseline = _int_map(family["profiles"]["dialect-v1"][role], keys, f"{family_id} v1 {role}")
            candidate = _int_map(family["profiles"]["dialect-v2"][role], keys, f"{family_id} v2 {role}")
            observed = _int_map(family["delta"][role], keys, f"{family_id} {role} delta")
            if observed != _delta(baseline, candidate):
                raise LedgerError(f"{family_id} {role} delta is inconsistent")
    infrastructure = value["one_time_infrastructure"]
    if not isinstance(infrastructure, list) or [item.get("id") for item in infrastructure] != ["lcc-v2-profile-infrastructure"]:
        raise LedgerError("one-time infrastructure inventory drift")
    lcc_keys = set(FAMILY_METRICS)
    lcc_deltas: list[dict[str, int]] = []
    profile_pairs = (("dialect-v1", "dialect-v2"),)
    for index, (baseline_profile, candidate_profile) in enumerate(profile_pairs):
        item = _exact(
            infrastructure[index],
            {"id", "accounting", "source_bindings", "profiles", "delta"},
            f"infrastructure[{index}]",
        )
        if item["accounting"] != "one-time-infrastructure" or set(item["profiles"]) != {baseline_profile, candidate_profile}:
            raise LedgerError(f"infrastructure[{index}] identity drift")
        baseline_lcc = _int_map(item["profiles"][baseline_profile], lcc_keys, f"infrastructure[{index}] baseline")
        candidate_lcc = _int_map(item["profiles"][candidate_profile], lcc_keys, f"infrastructure[{index}] candidate")
        item_delta = _int_map(item["delta"], lcc_keys, f"infrastructure[{index}] delta")
        if item_delta != _delta(baseline_lcc, candidate_lcc):
            raise LedgerError(f"infrastructure[{index}] delta is inconsistent")
        lcc_deltas.append(item_delta)
    expected_lcc_delta = (
        {"code_bytes": 1109, "directory_entries": 21, "ext_bytes": 3215, "raw_namepool_bytes": 833}
        if len(family_ids) >= 3
        else {"code_bytes": 1054, "directory_entries": 21, "ext_bytes": 3034, "raw_namepool_bytes": 787}
    )
    if lcc_deltas[0] != expected_lcc_delta:
        raise LedgerError("LCC v2 capability cost drift")
    prerequisites = value["capability_prerequisites"]
    if not isinstance(prerequisites, list) or len(prerequisites) != 1:
        raise LedgerError("capability prerequisite inventory drift")
    prerequisite = _exact(
        prerequisites[0], {"id", "status", "historical_stop_contract", "completion"},
        "capability prerequisite",
    )
    historical = _exact(
        prerequisite["historical_stop_contract"], {"path", "sha256"},
        "historical stop contract",
    )
    completion = _exact(
        prerequisite["completion"], {"contract", "receipt", "deployment", "accounting"},
        "capability completion",
    )
    completion_contract = _exact(completion["contract"], {"path", "sha256"}, "capability completion contract")
    completion_receipt = _exact(completion["receipt"], {"path", "sha256"}, "capability completion receipt")
    if (
        prerequisite["id"] != "v2-native-list-primitives"
        or prerequisite["status"] != "completed"
        or completion["deployment"] != "shared-capability-carrier-block"
        or completion["accounting"] != "excluded-from-family-delta-already-budgeted-by-cp5"
        or any(not SHA_RE.fullmatch(item["sha256"]) for item in (historical, completion_contract, completion_receipt))
    ):
        raise LedgerError("capability prerequisite identity/binding drift")
    cumulative = _exact(value["cumulative"], {"family_only_loaded_delta", "one_time_infrastructure_delta", "deployed_net_delta", "capability_prerequisites_satisfied", "section_8_progress"}, "cumulative")
    if cumulative["capability_prerequisites_satisfied"] is not True:
        raise LedgerError("Lists capability prerequisite must remain satisfied")
    family_loaded = _int_map(cumulative["family_only_loaded_delta"], lcc_keys, "family-only cumulative")
    infra = _int_map(cumulative["one_time_infrastructure_delta"], lcc_keys, "infrastructure cumulative")
    net = _int_map(cumulative["deployed_net_delta"], lcc_keys, "deployed net")
    expected_family = {key: 0 for key in FAMILY_METRICS}
    for family in families:
        expected_family = _add(expected_family, {
            "code_bytes": family["delta"]["loaded"]["code_bytes"],
            "directory_entries": family["delta"]["loaded"]["directory_entries"],
            "ext_bytes": family["delta"]["loaded"]["ext_bytes"],
            "raw_namepool_bytes": family["delta"]["loaded"]["raw_definition_namepool_bytes"],
        })
    expected_infra = {key: 0 for key in FAMILY_METRICS}
    for item_delta in lcc_deltas:
        expected_infra = _add(expected_infra, item_delta)
    if family_loaded != expected_family or infra != expected_infra or net != _add(family_loaded, infra):
        raise LedgerError("cumulative capacity separation is inconsistent")
    progress = _int_map(cumulative["section_8_progress"], {"code_bytes_saved", "namepool_bytes_saved", "symbol_entries_saved"}, "section 8 progress")
    if progress != {
        "code_bytes_saved": -family_loaded["code_bytes"],
        "namepool_bytes_saved": -family_loaded["raw_namepool_bytes"],
        "symbol_entries_saved": -family_loaded["directory_entries"],
    }:
        raise LedgerError("section 8 progress is inconsistent")


def _selftest() -> int:
    with tempfile.TemporaryDirectory(prefix="dialect-v2-capacity-selftest-") as raw:
        root = Path(raw)
        evidence = root / "evidence.json"
        evidence.write_text("{}\n", encoding="utf-8")
        sample = {
            "format": "lisp65-dialect-v2-capacity-ledger-v2",
            "scope": "completed-lists-cumulative-measured-family-capacity",
            "measurement_policy": {
                "family_costs_exclude_one_time_infrastructure": True,
                "measurements_are_rebuilt_artifacts": True,
                "new_family_requires_explicit_ledger_entry": True,
            },
            "projection_reference": {
                "document": "docs/lisp65-dialect-redesign-2026-07-10.md", "section": "8",
                "scope": "surface-consolidation-plus-later-helper-desymbolization",
                "final_projection": {}, "status": "lists-family-complete-not-final-migration-verdict",
            },
            "contract_binding": {"path": "config/x.json", "sha256": "0" * 64, "lists_projection": {}},
            "product_link_budget": {
                "status": "authorized-repinned", "reserve_target_bytes": 1536,
                "baseline": {"commit": "0b801717f5bb9c6c78865dcbb117142af24972e4", "post_boot_reserve_bytes": 2091, "banked_headroom_bytes": 555},
                "current": {
                    "product_sha256": "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110",
                    "post_boot_reserve_bytes": 1805, "banked_headroom_bytes": 269,
                },
                "delta_bytes": -286,
                "spend_stages": [
                    {
                        "id": "r2-system-runtime",
                        "baseline": {"post_boot_reserve_bytes": 2091, "banked_headroom_bytes": 555},
                        "candidate": {"post_boot_reserve_bytes": 1971, "banked_headroom_bytes": 435},
                        "delta_bytes": -120,
                        "authorization": {"path": _relative(R2_BANK_DEBIT_AUTHORIZATION), "sha256": _sha_file(R2_BANK_DEBIT_AUTHORIZATION)},
                        "evidence": {"path": _relative(R2_STACK_GUARD_DIAGNOSIS), "sha256": _sha_file(R2_STACK_GUARD_DIAGNOSIS)},
                    },
                    {
                        "id": "directory-only-l65m-v2",
                        "baseline": {
                            "product_sha256": "9d8e4d0ec8886c66dbe59383d32f010b1e99706c6e8f23b0b70b15af5968aa1f",
                            "post_boot_reserve_bytes": 1971, "banked_headroom_bytes": 435,
                        },
                        "candidate": {
                            "product_sha256": "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110",
                            "post_boot_reserve_bytes": 1805, "banked_headroom_bytes": 269,
                        },
                        "delta_bytes": -166,
                        "authorization": {"path": _relative(DIRECTORY_ONLY_BANK_DEBIT_AUTHORIZATION), "sha256": _sha_file(DIRECTORY_ONLY_BANK_DEBIT_AUTHORIZATION)},
                        "evidence": {"path": _relative(DIRECTORY_ONLY_LINK_REPORT), "sha256": _sha_file(DIRECTORY_ONLY_LINK_REPORT)},
                    },
                ],
                "next_spend": "zero-or-preauthorized-delta-required",
            },
            "evidence_bindings": [{"path": "build/evidence.json", "sha256": "1" * 64}],
            "family_measurements": [{
                "id": "lists",
                "status": "migrated",
                "profiles": {
                    "dialect-v1": {
                        "public": {"definitions": 4, "namepool_bytes": 20},
                        "loaded": {"code_bytes": 100, "directory_entries": 6, "ext_bytes": 200, "internal_entries": 2, "internal_namepool_bytes": 12, "raw_definition_namepool_bytes": 32, "total_unique_namepool_bytes": 40},
                        "boot": {"code_bytes": 80, "directory_entries": 5, "ext_bytes": 160, "internal_entries": 1, "internal_namepool_bytes": 6, "raw_definition_namepool_bytes": 26, "total_unique_namepool_bytes": 30},
                        "internal": {"boot_definitions": 1, "boot_namepool_bytes": 6, "loaded_definitions": 2, "loaded_namepool_bytes": 12},
                    },
                    "dialect-v2": {
                        "public": {"definitions": 3, "namepool_bytes": 15},
                        "loaded": {"code_bytes": 90, "directory_entries": 4, "ext_bytes": 180, "internal_entries": 1, "internal_namepool_bytes": 7, "raw_definition_namepool_bytes": 22, "total_unique_namepool_bytes": 28},
                        "boot": {"code_bytes": 60, "directory_entries": 3, "ext_bytes": 120, "internal_entries": 0, "internal_namepool_bytes": 0, "raw_definition_namepool_bytes": 15, "total_unique_namepool_bytes": 18},
                        "internal": {"boot_definitions": 0, "boot_namepool_bytes": 0, "loaded_definitions": 1, "loaded_namepool_bytes": 7},
                    },
                },
                "delta": {},
            }],
            "one_time_infrastructure": [{
                "id": "lcc-v2-profile-infrastructure", "accounting": "one-time-infrastructure",
                "source_bindings": {},
                "profiles": {
                    "dialect-v1": {"code_bytes": 6340, "directory_entries": 86, "ext_bytes": 16780, "raw_namepool_bytes": 1874},
                    "dialect-v2": {"code_bytes": 7394, "directory_entries": 107, "ext_bytes": 19814, "raw_namepool_bytes": 2661},
                },
                "delta": {"code_bytes": 1054, "directory_entries": 21, "ext_bytes": 3034, "raw_namepool_bytes": 787},
            }],
            "capability_prerequisites": [{
                "id": "v2-native-list-primitives", "status": "completed",
                "historical_stop_contract": {"path": "config/block.json", "sha256": "2" * 64},
                "completion": {
                    "contract": {"path": "config/carrier.json", "sha256": "3" * 64},
                    "receipt": {"path": "tests/cp5.json", "sha256": "4" * 64},
                    "deployment": "shared-capability-carrier-block",
                    "accounting": "excluded-from-family-delta-already-budgeted-by-cp5",
                },
            }],
            "cumulative": {},
        }
        family = sample["family_measurements"][0]
        family["delta"] = {
            role: _delta(family["profiles"]["dialect-v1"][role], family["profiles"]["dialect-v2"][role])
            for role in ("public", "loaded", "boot", "internal")
        }
        family_loaded = {"code_bytes": -10, "directory_entries": -2, "ext_bytes": -20, "raw_namepool_bytes": -10}
        infra = sample["one_time_infrastructure"][0]["delta"]
        sample["cumulative"] = {
            "family_only_loaded_delta": family_loaded,
            "one_time_infrastructure_delta": infra,
            "deployed_net_delta": _add(family_loaded, infra),
            "capability_prerequisites_satisfied": True,
            "section_8_progress": {"code_bytes_saved": 10, "namepool_bytes_saved": 10, "symbol_entries_saved": 2},
        }
        validate_ledger(sample)
        mutations = []
        for mutator in (
            lambda x: x.pop("measurement_policy"),
            lambda x: x.update(format="wrong"),
            lambda x: x["measurement_policy"].update(family_costs_exclude_one_time_infrastructure=False),
            lambda x: x["projection_reference"].update(section="7"),
            lambda x: x["contract_binding"].update(sha256="bad"),
            lambda x: x["family_measurements"][0]["delta"]["loaded"].update(code_bytes=-9),
            lambda x: x["one_time_infrastructure"][0]["delta"].update(code_bytes=688),
            lambda x: x["one_time_infrastructure"][0].update(accounting="family"),
            lambda x: x["capability_prerequisites"][0].update(status="deferred"),
            lambda x: x["cumulative"].update(capability_prerequisites_satisfied=False),
            lambda x: x["cumulative"]["family_only_loaded_delta"].update(raw_namepool_bytes=0),
            lambda x: x["cumulative"]["deployed_net_delta"].update(directory_entries=99),
            lambda x: x["cumulative"]["section_8_progress"].update(symbol_entries_saved=0),
            lambda x: x.update(unexpected=True),
        ):
            candidate = deepcopy(sample)
            mutator(candidate)
            mutations.append(candidate)
        accepted = 0
        for candidate in mutations:
            try:
                validate_ledger(candidate)
            except LedgerError:
                continue
            accepted += 1
        if accepted:
            raise LedgerError(f"selftest accepted {accepted} invalid ledger mutations")
    print(f"dialect-v2-capacity-ledger-selftest: PASS mutations={len(mutations)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--blocked-capability", type=Path, default=DEFAULT_BLOCK)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("selftest")
    generate = subparsers.add_parser("generate")
    generate.add_argument("--output", type=Path, default=DEFAULT_LEDGER)
    check = subparsers.add_parser("check")
    check.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    check.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            return _selftest()
        rendered = render_ledger(args.contract, args.evidence_dir, args.blocked_capability)
        validate_ledger(rendered)
        if args.command == "generate":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(_canonical(rendered))
            print(f"dialect-v2-capacity-ledger: WROTE {_relative(args.output)}")
            return 0
        expected = _load(args.ledger, "pinned capacity ledger")
        validate_ledger(expected)
        if _canonical(expected) != _canonical(rendered):
            raise LedgerError("pinned capacity ledger differs from rebuilt artifacts")
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_bytes(_canonical(rendered))
        net = rendered["cumulative"]["deployed_net_delta"]
        print(
            "dialect-v2-capacity-ledger: PASS "
            f"families={len(rendered['family_measurements'])} "
            f"net_dir={net['directory_entries']:+d} "
            f"net_names={net['raw_namepool_bytes']:+d} "
            f"net_code={net['code_bytes']:+d} net_ext={net['ext_bytes']:+d}"
        )
        return 0
    except (LedgerError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"dialect-v2-capacity-ledger: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
