#!/usr/bin/env python3
"""Validate the atomic dialect-v2 capability/carrier architecture block."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/v2-capability-carrier-block.json"
DEFAULT_FIXTURE = ROOT / "tests/bytecode/dialect-v2/capability-carrier/surface.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CHECKPOINT_IDS = (
    "contract-surface-fixtures",
    "registry-null-miss-target",
    "internal-native-capabilities",
    "zero-miss-carrier-removal",
    "product-links-g5-promotion",
)
CHECKPOINT_ACCEPTANCE = (
    ("contract-validated", "surface-fixtures-bound", "carrier-baseline-active"),
    ("link-time-registry-linked", "null-miss-target-gate-ready", "carrier-still-active"),
    ("prim-1-2-26-27-v2-tombstoned", "native-lists-string-codecs-internal", "carrier-still-active"),
    ("registry-null-miss-zero", "carrier-removed-after-zero", "string-codec-atomicity-gates-pass", "native-designator-dispatch-parity", "native-three-route-four-engine-matrix-pass", "workbench-library-composition-gate"),
    ("workbench-budget-pass", "runtime-budget-pass", "deployed-bank0-net-negative", "g5-pass", "single-promotion-ready"),
)
REQUIRED_RECEIPT_EVIDENCE = {
    1: {
        "config/dialect-v2-eval-apply-funcall-block.json",
        "docs/archive/pre-1.0/contracts/v2-capability-carrier-block.md",
        "tests/bytecode/dialect-v2/capability-carrier/surface.json",
        "tests/bytecode/dialect-v2/eval-apply-funcall/cases.json",
        "tools/host-lisp/dialect_v2_prelude_control.py",
        "tools/host-lisp/v2_capability_carrier_contract.py",
    },
    2: {
        "config/workbench-native-service-registry.json",
        "docs/archive/pre-1.0/contracts/v2-capability-carrier-registry.md",
        "mk/workbench-service-inventory.mk",
        "tools/host-lisp/workbench_service_call_inventory.py",
    },
    3: {
        "Makefile",
        "config/bytecode-abi-ledger.json",
        "lib/dialect-v2/strings-core.lisp",
        "mk/gates.mk",
        "mk/v2-callprim-runtime.mk",
        "mk/v2-string-caps.mk",
        "scripts/v2-runtime-callprim-main.c",
        "scripts/v2-string-caps-main.c",
        "src/mem.c",
        "src/mem.h",
        "src/vm.c",
        "tests/bytecode/dialect-v2/lists/cases.json",
        "tests/bytecode/dialect-v2/strings/cases.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-26-string-slice.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/abi-retirements/prim-27-string-concat-list.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/string-codec-workload-receipt.json",
        "tools/host-lisp/v2_carrier_state.py",
        "tools/host-lisp/v2_prim_lowering.py",
        "tools/host-lisp/v2_string_codec_workloads.py",
    },
    4: {
        "config/bytecode-abi-ledger.json",
        "config/v2-native-function-registry.json",
        "config/v2-workbench-artifact-closure.json",
        "config/workbench-native-service-registry.json",
        "config/workbench.mk",
        "lib/dialect-v2/eval-runtime.lisp",
        "scripts/dialect-v2-lcc-manifest-main.c",
        "scripts/v2-carrier-cut-check.sh",
        "scripts/v2-carrier-cut-main.c",
        "scripts/v2-workbench-services-check.sh",
        "scripts/v2-workbench-services-main.c",
        "src/v2_native_function_dispatch.h",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/carrier-cut-verdict.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/invalid-parameter-list-verdict.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/native-function-route-matrix.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-artifact-differential-receipt.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/gc-symbol-scan-timing-receipt.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-library-composition-capacity-receipt.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-private-inline-composition-probe.json",
        "tools/host-lisp/dialect_v2_lcc_compile_error.py",
        "tools/host-lisp/v2_capability_carrier_receipt.py",
        "tools/host-lisp/v2_carrier_state.py",
        "tools/host-lisp/v2_native_function_matrix.py",
        "tools/host-lisp/v2_native_function_registry.py",
        "tools/host-lisp/v2_workbench_codemod.py",
        "tools/host-lisp/v2_workbench_differential.py",
        "tools/host-lisp/workbench_service_call_inventory.py",
        "tools/host-lisp/gc_symbol_scan_timing.py",
        "tools/host-lisp/workbench_disklib_budget.py",
        "tools/host-lisp/workbench_private_inline_probe.py",
    },
    5: {
        "tests/bytecode/dialect-v2/evidence/capability-carrier/cp5-g5-67400c05/evidence.tar.gz",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/cp5-g5-67400c05/manifest.json",
        "tests/bytecode/dialect-v2/evidence/capability-carrier/string-caps-cp5-product-link-report.json",
        "tools/host-lisp/v2_cp5_g5_archive.py",
    },
}
EXPECTED_SURFACE = {
    "carrier-active-through-checkpoint-3": ("carrier", "active", "active-through-checkpoint-3"),
    "carrier-removed-only-after-zero-miss": ("carrier", "active", "remove-at-checkpoint-4-after-zero-miss"),
    "prim-id-1-string-to-list": ("prim-id-1", "legacy-decodable", "tombstone-reject-bad-primitive"),
    "prim-id-2-list-to-string": ("prim-id-2", "legacy-decodable", "tombstone-reject-bad-primitive"),
    "prim-id-26-string-slice": ("prim-id-26", "reserved", "tombstone-reject-bad-primitive"),
    "prim-id-27-string-concat-list": ("prim-id-27", "reserved", "tombstone-reject-bad-primitive"),
    "prim-id-28-string-codes": ("prim-id-28", "reserved", "internal-nondesignator-exact-arity-1"),
    "prim-id-29-string-from-codes": ("prim-id-29", "reserved", "internal-nondesignator-exact-arity-1"),
    "registry-uninstalled-null-miss": ("service-registry", "not-applicable", "null-miss-before-carrier-fallback"),
    "string-codec-code-list-materialization": ("string-codec", "not-applicable", "code-list-materialization"),
    "string-codec-success-only-result": ("string-codec", "not-applicable", "vm-error-prevents-partial-result-publication"),
    "string-codec-failure-atomic": ("string-codec", "not-applicable", "failure-has-no-observable-partial-string"),
    "string-codec-span-dma-deferred": ("string-codec", "not-applicable", "span-dma-deferred-to-buffer-and-string-construction-block"),
}
for _name, _arity in (("nreverse", 1), ("rplaca", 2), ("rplacd", 2)):
    for _route in ("apply", "direct", "funcall"):
        EXPECTED_SURFACE[f"{_name}-{_route}"] = (
            _name, "legacy-carrier", f"native-capability-exact-arity-{_arity}"
        )


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must contain an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ContractError(f"{label} keys drift: {actual}")
    return value


def _strings(value: Any, label: str, expected: tuple[str, ...] | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ContractError(f"{label} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ContractError(f"{label} contains duplicates")
    if expected is not None and tuple(value) != expected:
        raise ContractError(f"{label} drift: {value}")
    return value


def _repo_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        raise ContractError(f"{label} must be a safe repository-relative path")
    return ROOT / value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy_sha(contract: dict[str, Any]) -> str:
    normalized = deepcopy(contract)
    for checkpoint in normalized["checkpoints"]:
        checkpoint["status"] = "pending"
        checkpoint["receipt"] = None
    payload = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _binding(value: Any, label: str, *, verify: bool = True) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    path = _repo_path(item["path"], f"{label}.path")
    if not isinstance(item["sha256"], str) or not SHA_RE.fullmatch(item["sha256"]):
        raise ContractError(f"{label}.sha256 is invalid")
    if verify:
        if path.is_symlink() or not path.is_file() or _sha(path) != item["sha256"]:
            raise ContractError(f"{label} SHA binding drift")
    return path


def _validate_receipt(contract: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    binding = checkpoint["receipt"]
    if binding is None:
        raise ContractError(f"checkpoint {checkpoint['number']} passed without receipt")
    path = _binding(binding, f"checkpoint {checkpoint['number']}.receipt")
    receipt = _load(path, f"checkpoint {checkpoint['number']} receipt")
    _exact(
        receipt,
        {
            "format", "block_id", "checkpoint", "checkpoint_id", "gate",
            "contract_policy_sha256", "result", "assertions", "evidence", "metrics",
        },
        f"checkpoint {checkpoint['number']} receipt",
    )
    if receipt != {
        **receipt,
        "format": "lisp65-v2-capability-carrier-checkpoint-receipt-v1",
        "block_id": contract["id"],
        "checkpoint": checkpoint["number"],
        "checkpoint_id": checkpoint["id"],
        "gate": checkpoint["make_target"],
        "contract_policy_sha256": _policy_sha(contract),
        "result": "passed",
        "assertions": checkpoint["acceptance"],
    }:
        raise ContractError(f"checkpoint {checkpoint['number']} receipt identity/assertion drift")
    evidence = receipt["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ContractError(f"checkpoint {checkpoint['number']} receipt lacks evidence")
    paths = []
    for index, item in enumerate(evidence):
        evidence_path = _binding(item, f"checkpoint {checkpoint['number']}.evidence[{index}]")
        paths.append(evidence_path.relative_to(ROOT).as_posix())
    if paths != sorted(set(paths)):
        raise ContractError(f"checkpoint {checkpoint['number']} evidence must be sorted and unique")
    required_evidence = REQUIRED_RECEIPT_EVIDENCE.get(checkpoint["number"])
    if required_evidence is not None and set(paths) != required_evidence:
        raise ContractError(
            f"checkpoint {checkpoint['number']} evidence set drift: {paths}"
        )
    if not isinstance(receipt["metrics"], dict):
        raise ContractError(f"checkpoint {checkpoint['number']} metrics must be an object")
    if checkpoint["number"] == 3:
        metrics = _exact(
            receipt["metrics"],
            {
                "active_prim_ids", "lists_cases", "strings_cases",
                "strings_observations", "native_treewalk_carrier_blockers",
                "lcc_carrier_blockers", "runtime_treewalk_hooks_null",
                "codec_atomic", "v1_active_prim_ids",
            },
            "checkpoint 3 metrics",
        )
        if metrics != {
            "active_prim_ids": [23, 24, 25, 28, 29],
            "lists_cases": 35,
            "strings_cases": 36,
            "strings_observations": 288,
            "native_treewalk_carrier_blockers": 15,
            "lcc_carrier_blockers": 2,
            "runtime_treewalk_hooks_null": True,
            "codec_atomic": True,
            "v1_active_prim_ids": 23,
        }:
            raise ContractError("checkpoint 3 native capability metrics drift")
    if checkpoint["number"] == 4:
        metrics = _exact(
            receipt["metrics"],
            {
                "artifact_cases", "artifact_observation_differences",
                "callprim_calls", "carrier_forbidden_definitions",
                "classified_service_targets", "code59_full_path_engines",
                "directory_calls", "error_service_targets",
                "native_service_targets", "runtime_function_pointer_registry",
                "native_function_registry_entries", "native_function_dispatch_entries",
                "native_function_explicit_exclusions", "native_function_routes",
                "native_function_engines", "native_function_evaluations", "boundp_prim_id",
                "composition_libraries", "composition_directory_used",
                "composition_directory_post_align_headroom", "composition_symbols",
                "composition_symbol_headroom", "composition_namepool_bytes",
                "composition_namepool_headroom_bytes", "additional_private_symbols",
                "tombstone_callprim_calls", "unresolved_calls",
                "unresolved_targets",
            },
            "checkpoint 4 metrics",
        )
        if metrics != {
            "artifact_cases": 335,
            "artifact_observation_differences": 0,
            "callprim_calls": 465,
            "carrier_forbidden_definitions": 0,
            "classified_service_targets": 28,
            "code59_full_path_engines": 4,
            "directory_calls": 1801,
            "error_service_targets": 11,
            "native_service_targets": 14,
            "native_function_registry_entries": 15,
            "native_function_dispatch_entries": 15,
            "native_function_explicit_exclusions": 2,
            "native_function_routes": 3,
            "native_function_engines": 4,
            "native_function_evaluations": 180,
            "boundp_prim_id": 57,
            "composition_libraries": 3,
            "composition_directory_used": 571,
            "composition_directory_post_align_headroom": 32,
            "composition_symbols": 713,
            "composition_symbol_headroom": 39,
            "composition_namepool_bytes": 9718,
            "composition_namepool_headroom_bytes": 490,
            "additional_private_symbols": 0,
            "runtime_function_pointer_registry": False,
            "tombstone_callprim_calls": 0,
            "unresolved_calls": 0,
            "unresolved_targets": 0,
        }:
            raise ContractError("checkpoint 4 zero-miss/carrier metrics drift")
    if checkpoint["number"] == 5:
        metrics = _exact(
            receipt["metrics"],
            {"workbench_runtime_overlay_vma", "workbench_post_boot_reserve_bytes", "runtime_core_post_boot_reserve_bytes", "deployed_bank0_net_delta_bytes", "g5_result", "layout_change", "slot_delta", "island_bytes_delta"},
            "checkpoint 5 metrics",
        )
        if (
            int(metrics["workbench_runtime_overlay_vma"], 0) > 0xC356
            or type(metrics["workbench_post_boot_reserve_bytes"]) is not int
            or metrics["workbench_post_boot_reserve_bytes"] < 2091
            or type(metrics["runtime_core_post_boot_reserve_bytes"]) is not int
            or metrics["runtime_core_post_boot_reserve_bytes"] < 8192
            or type(metrics["deployed_bank0_net_delta_bytes"]) is not int
            or metrics["deployed_bank0_net_delta_bytes"] >= 0
            or metrics["g5_result"] != "passed"
            or metrics["layout_change"] is not False
            or metrics["slot_delta"] != 0
            or metrics["island_bytes_delta"] != 0
        ):
            raise ContractError("checkpoint 5 product/G5 budget metrics fail")


def validate_surface_fixture(value: dict[str, Any]) -> None:
    _exact(value, {"format", "block_id", "stage", "cases"}, "surface fixture")
    if (
        value["format"] != "lisp65-v2-capability-carrier-surface-v1"
        or value["block_id"] != "v2-capability-carrier"
        or value["stage"] != 1
        or not isinstance(value["cases"], list)
    ):
        raise ContractError("surface fixture identity drift")
    observed: dict[str, tuple[str, str, str]] = {}
    ids = []
    for index, raw in enumerate(value["cases"]):
        case = _exact(raw, {"id", "checkpoint", "surface", "dialect_v1", "dialect_v2"}, f"surface cases[{index}]")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case["checkpoint"] != 1:
            raise ContractError(f"surface case {index} identity/checkpoint drift")
        ids.append(case_id)
        observed[case_id] = (case["surface"], case["dialect_v1"], case["dialect_v2"])
    if ids != sorted(set(ids)) or observed != EXPECTED_SURFACE:
        raise ContractError("surface fixture coverage/observation drift")


def _validate_promoted_seal(value: dict[str, Any]) -> None:
    """Validate only the live seal pointer; historical contents live in the archive."""
    checkpoints = value["checkpoints"]
    if not isinstance(checkpoints, list) or len(checkpoints) != 5:
        raise ContractError("promoted block must retain five checkpoint identities")
    for index, raw in enumerate(checkpoints):
        checkpoint = _exact(
            raw,
            {"number", "id", "status", "requires", "make_target", "acceptance", "receipt"},
            f"checkpoints[{index}]",
        )
        number = index + 1
        expected_requires = [] if number == 1 else [CHECKPOINT_IDS[index - 1]]
        if (
            checkpoint["number"] != number
            or checkpoint["id"] != CHECKPOINT_IDS[index]
            or checkpoint["status"] != "passed"
            or checkpoint["requires"] != expected_requires
            or checkpoint["make_target"] != f"v2-capability-carrier-check-host-{number}"
            or tuple(checkpoint["acceptance"]) != CHECKPOINT_ACCEPTANCE[index]
        ):
            raise ContractError(f"promoted checkpoint {number} identity drift")
        _binding(checkpoint["receipt"], f"checkpoint {number}.receipt", verify=False)
    try:
        import promotion_archive

        promotion_archive.register_check(announce=False)
        register = _load(
            ROOT / "config" / "promotion-register.json", "promotion register"
        )
    except (promotion_archive.ArchiveError, OSError, ValueError) as exc:
        raise ContractError(f"promotion register is invalid: {exc}") from exc
    entries = [
        item for item in register.get("promotions", [])
        if isinstance(item, dict) and item.get("subject") == "v2-capability-carrier"
    ]
    if (
        len(entries) != 1
        or entries[0].get("kind") != "capability-carrier"
        or entries[0].get("id") != "v2-capability-carrier-8ef473c"
    ):
        raise ContractError("capability/carrier sealed promotion register entry drift")


def validate(value: dict[str, Any], *, verify_bindings: bool = True) -> None:
    _exact(
        value,
        {"format", "version", "id", "status", "atomic_scope", "promotion", "release_convergence", "runtime_core_proof", "checkpoints", "registry", "native_function_registry", "carrier", "primitive_id_policy", "string_codecs", "budgets", "cp5_measurement", "rollback_levels", "durability_levels", "frozen_layout"},
        "capability/carrier contract",
    )
    if (
        value["format"] != "lisp65-v2-capability-carrier-block-v1"
        or value["version"] != 1
        or value["id"] != "v2-capability-carrier"
        or value["status"] not in {"approved-plan", "in-progress", "promotion-ready", "promoted"}
    ):
        raise ContractError("capability/carrier contract identity/status drift")
    if value["status"] == "promoted":
        _validate_promoted_seal(value)
        return
    scope = _exact(value["atomic_scope"], {"families", "components", "partial_deployment"}, "atomic_scope")
    _strings(scope["families"], "atomic_scope.families", ("lists", "strings"))
    _strings(scope["components"], "atomic_scope.components", ("surface-fixtures", "link-time-registry", "resident-c-semantics-carrier", "v2-prim-tombstones", "native-list-primitives", "native-string-codecs"))
    if scope["partial_deployment"] != "forbidden":
        raise ContractError("partial capability deployment must remain forbidden")

    promotion = _exact(value["promotion"], {"count", "mode", "source_profile", "target_profile", "requires_checkpoint", "g5_before_promotion", "rollback_target"}, "promotion")
    if promotion != {
        "count": 1,
        "mode": "atomic",
        "source_profile": "dialect-v1",
        "target_profile": "dialect-v2-capability-carrier",
        "requires_checkpoint": 5,
        "g5_before_promotion": True,
        "rollback_target": "last-verified-dialect-v1-evidence",
    }:
        raise ContractError("single atomic promotion policy drift")

    convergence = _exact(
        value["release_convergence"],
        {
            "release_product", "runtime_core_role", "runtime_core_release_effect",
            "runtime_core_receipt_effect", "dialect_v1_release",
            "cp5_completion_requires", "active_work_lines",
            "new_language_families", "new_ap8_blocks",
        },
        "release_convergence",
    )
    if convergence != {
        "release_product": "lisp65-workbench-v2",
        "runtime_core_role": "internal-proof-only",
        "runtime_core_release_effect": "none",
        "runtime_core_receipt_effect": "evidence-only",
        "dialect_v1_release": "forbidden",
        "cp5_completion_requires": [
            "workbench-v2-link-budget",
            "runtime-core-proof",
            "full-workbench-plus-runtime-g5",
        ],
        "active_work_lines": ["dialect-v2-family-migration"],
        "new_language_families": "allowed-after-cp5-sequential-contracts",
        "new_ap8_blocks": "allowed-after-cp5-explicit-block",
    }:
        raise ContractError("release convergence/profile-split policy drift")

    runtime_proof = _exact(
        value["runtime_core_proof"],
        {
            "status", "contract", "make_target", "receipt", "effect",
            "cp5_completion_effect", "family_advancement_effect",
            "release_effect", "hardware_status",
        },
        "runtime_core_proof",
    )
    proof_contract = _binding(
        runtime_proof["contract"], "runtime_core_proof.contract",
        verify=verify_bindings,
    )
    if (
        proof_contract.relative_to(ROOT).as_posix() != "config/v2-runtime-core-proof.json"
        or runtime_proof != {
            **runtime_proof,
            "status": "hardware-proof-passed",
            "make_target": "v2-capability-carrier-runtime-proof-check",
            "effect": "evidence-only",
            "cp5_completion_effect": "supporting-evidence-satisfied",
            "family_advancement_effect": "none",
            "release_effect": "none",
            "hardware_status": "passed-four-power-cycles",
        }
    ):
        raise ContractError("runtime-core proof binding/effect drift")
    proof_receipt = _binding(
        runtime_proof["receipt"], "runtime_core_proof.receipt",
        verify=verify_bindings,
    )
    if proof_receipt.relative_to(ROOT).as_posix() != (
        "tests/bytecode/dialect-v2/evidence/capability-carrier/"
        "cp5-g5-67400c05/manifest.json"
    ):
        raise ContractError("runtime-core proof receipt path drift")

    checkpoints = value["checkpoints"]
    if not isinstance(checkpoints, list) or len(checkpoints) != 5:
        raise ContractError("exactly five checkpoints are required")
    seen_pending = False
    for index, raw in enumerate(checkpoints):
        checkpoint = _exact(raw, {"number", "id", "status", "requires", "make_target", "acceptance", "receipt"}, f"checkpoints[{index}]")
        number = index + 1
        expected_requires = [] if number == 1 else [CHECKPOINT_IDS[index - 1]]
        if (
            checkpoint["number"] != number
            or checkpoint["id"] != CHECKPOINT_IDS[index]
            or checkpoint["requires"] != expected_requires
            or checkpoint["make_target"] != f"v2-capability-carrier-check-host-{number}"
            or tuple(checkpoint["acceptance"]) != CHECKPOINT_ACCEPTANCE[index]
            or checkpoint["status"] not in {"pending", "passed"}
        ):
            raise ContractError(f"checkpoint {number} definition drift")
        if checkpoint["status"] == "pending":
            seen_pending = True
            if checkpoint["receipt"] is not None:
                raise ContractError(f"pending checkpoint {number} carries a receipt")
        else:
            if seen_pending:
                raise ContractError("checkpoints may only pass as a contiguous prefix")
            if verify_bindings:
                _validate_receipt(value, checkpoint)
    passed = sum(item["status"] == "passed" for item in checkpoints)
    expected_status = "approved-plan" if passed == 0 else "promotion-ready" if passed == 5 else "in-progress"
    if value["status"] == "promoted":
        if passed != 5:
            raise ContractError("promoted block lacks all five checkpoint receipts")
    elif value["status"] != expected_status:
        raise ContractError("block status does not match checkpoint prefix")

    registry = _exact(value["registry"], {"construction", "dispatch", "per_call_function_pointers", "lookup_before_carrier", "unknown_capability", "fallback_until_checkpoint", "zero_miss_required_before_carrier_removal"}, "registry")
    if registry != {
        "construction": "link-time", "dispatch": "direct-static-branch",
        "per_call_function_pointers": False, "lookup_before_carrier": "null-miss",
        "unknown_capability": "null-miss", "fallback_until_checkpoint": 4,
        "zero_miss_required_before_carrier_removal": True,
    }:
        raise ContractError("link-time registry/null-miss policy drift")
    native_registry = _exact(
        value["native_function_registry"],
        {"construction", "source", "dispatch", "parity", "routes", "engines", "native_primitive_count", "generated_dispatch_count", "explicit_exclusion_count", "excluded_designator_error"},
        "native_function_registry",
    )
    native_source = _binding(native_registry["source"], "native_function_registry.source", verify=verify_bindings)
    native_dispatch = _binding(native_registry["dispatch"], "native_function_registry.dispatch", verify=verify_bindings)
    if (
        native_source.relative_to(ROOT).as_posix() != "config/v2-native-function-registry.json"
        or native_dispatch.relative_to(ROOT).as_posix() != "src/v2_native_function_dispatch.h"
        or native_registry != {
            **native_registry,
            "construction": "generated-single-source",
            "parity": "native-primitive-registry-entries-equal-generated-apply-dispatch-entries",
            "routes": ["direct", "funcall", "apply"],
            "engines": ["native-c-treewalk", "native-c-compiler-vm", "python-p0-compiler-vm", "lisp-lcc"],
            "native_primitive_count": 15,
            "generated_dispatch_count": 15,
            "explicit_exclusion_count": 2,
            "excluded_designator_error": "LISP65_ERR_VM_PRIMITIVE_NOT_DESIGNATOR",
        }
    ):
        raise ContractError("generated native function registry policy drift")
    carrier = _exact(value["carrier"], {"kind", "symbols", "role", "active_through_checkpoint", "removal_checkpoint", "new_loadable_artifact", "transport", "publication_protocol"}, "carrier")
    _strings(carrier["symbols"], "carrier.symbols", ("apply", "eval_vm_apply", "eval_vm_bridge"))
    if carrier != {
        "kind": "existing-resident-c-semantics",
        "symbols": ["apply", "eval_vm_apply", "eval_vm_bridge"],
        "role": "registry-miss-fallback-through-checkpoint-3",
        "active_through_checkpoint": 3,
        "removal_checkpoint": 4,
        "new_loadable_artifact": False,
        "transport": "none",
        "publication_protocol": "none",
    }:
        raise ContractError("resident C semantics carrier policy drift")

    primitive = _exact(value["primitive_id_policy"], {"namespace", "opcode_namespace_separate", "v2_tombstones", "v2_allocations"}, "primitive_id_policy")
    if primitive["namespace"] != "prim-id" or primitive["opcode_namespace_separate"] is not True:
        raise ContractError("Prim-ID namespace policy drift")
    tombstones = primitive["v2_tombstones"]
    if not isinstance(tombstones, list) or len(tombstones) != 6:
        raise ContractError("Prim-ID 1/2/26/27/34/40 tombstones are required")
    for index, expected_name in enumerate(("string->list", "list->string"), 1):
        item = _exact(tombstones[index - 1], {"id", "canonical_name", "v1", "v2", "runtime", "reuse"}, f"v2_tombstones[{index - 1}]")
        if item != {"id": index, "canonical_name": expected_name, "v1": "legacy-decodable", "v2": "tombstone", "runtime": "reject-bad-primitive", "reuse": "forbidden"}:
            raise ContractError(f"Prim-ID {index} tombstone drift")
    for index, prim_id, canonical_name, v1_state in (
        (2, 26, "%string-slice", "reserved"),
        (3, 27, "%string-concat-list", "reserved"),
        (4, 34, "%save-staged", "active"),
        (5, 40, "number->string", "reserved"),
    ):
        retired = _exact(
            tombstones[index],
            {"id", "canonical_name", "v1", "v2", "runtime", "reuse", "evidence"},
            f"v2_tombstones[{index}]",
        )
        expected_retired = {
            "id": prim_id,
            "canonical_name": canonical_name,
            "v1": v1_state,
            "v2": "tombstone",
            "runtime": "reject-bad-primitive",
            "reuse": "forbidden",
        }
        if {key: retired[key] for key in expected_retired} != expected_retired:
            raise ContractError(f"Prim-ID {prim_id} retirement drift")
        retirement_path = _binding(retired["evidence"], f"v2_tombstones[{index}].evidence")
        retirement = _load(retirement_path, f"Prim-ID {prim_id} retirement evidence")
        if (
            retirement.get("format") != "lisp65-prim-id-retirement-evidence-v1"
            or retirement.get("prim_id") != prim_id
            or retirement.get("canonical_name") != canonical_name
            or retirement.get("transition") != "active-to-tombstone"
        ):
            raise ContractError(f"Prim-ID {prim_id} retirement evidence identity drift")
    allocations = primitive["v2_allocations"]
    expected_allocations = (
        (23, "nreverse", 1, "public", True),
        (24, "rplaca", 2, "public", True),
        (25, "rplacd", 2, "public", True),
        (28, "%string-codes", 1, "internal", False),
        (29, "%string-from-codes", 1, "internal", False),
        (57, "boundp", 1, "public", True),
    )
    if not isinstance(allocations, list) or len(allocations) != len(expected_allocations):
        raise ContractError("v2 Prim-ID allocation inventory drift")
    for index, expected in enumerate(expected_allocations):
        item = _exact(
            allocations[index],
            {"id", "canonical_name", "arity", "visibility", "function_designator"},
            f"v2_allocations[{index}]",
        )
        actual = (item["id"], item["canonical_name"], item["arity"], item["visibility"], item["function_designator"])
        if actual != expected:
            raise ContractError(f"Prim-ID {expected[0]} allocation drift")

    codecs = _exact(
        value["string_codecs"],
        {
            "promotion_unit", "internal_enable_checkpoint", "profile_visibility",
            "active_prim_ids", "retired_prim_ids", "construction_path",
            "failure_atomicity", "arena_publication", "transport",
            "span_dma_guarantee", "required_gates",
        },
        "string_codecs",
    )
    if codecs != {
        "promotion_unit": "atomic-with-capability-block",
        "internal_enable_checkpoint": 3,
        "profile_visibility": "promotion-only",
        "active_prim_ids": [28, 29],
        "retired_prim_ids": [26, 27],
        "construction_path": "retained-code-list-materialization",
        "failure_atomicity": "vm-error-prevents-result-publication",
        "arena_publication": "streaming-internal-result-returned-only-on-vm-ok",
        "transport": "existing-streaming-codec-path",
        "span_dma_guarantee": "deferred-to-buffer-and-string-construction-block",
        "required_gates": [
            "four-engine-differential", "gc-and-oom-atomicity",
            "heap-and-latency-receipt", "tombstone-emission-drift",
        ],
    }:
        raise ContractError("string codec policy drift")

    budgets = _exact(value["budgets"], {"workbench", "runtime_core", "deployed_bank0_net_delta_bytes", "measurement", "estimates_may_promote"}, "budgets")
    if (
        budgets["workbench"] != {
            "runtime_overlay_vma_max": "0xc356",
            "post_boot_reserve_min_bytes": 2091,
            "banked_abi_1_1_headroom_bytes": 555,
            "headroom_status": "reserved-for-abi-1.1-after-g5",
            "release_blocker_spend_bytes": 84,
            "spend_policy": "release-blocker-exception-recorded;one-abi-1-1-item-per-probe-after-g5",
        }
        or budgets["runtime_core"] != {"post_boot_reserve_min_bytes": 8192}
        or budgets["deployed_bank0_net_delta_bytes"] != {"comparison": "strictly-less-than", "limit": 0}
        or budgets["measurement"] != "real-linked-product-elfs"
        or budgets["estimates_may_promote"] is not False
    ):
        raise ContractError("hard product budget policy drift")

    cp5 = _exact(value["cp5_measurement"], {"status", "report"}, "cp5_measurement")
    report_path = _binding(cp5["report"], "cp5_measurement.report", verify=verify_bindings)
    report = _load(report_path, "CP5 product-link report")
    if (
        cp5["status"] != "g5-passed"
        or report.get("format") != "lisp65-v2-string-caps-cp5-product-link-report-v1"
        or report.get("status") != "g5-pending-fresh"
        or report.get("profile") != "dialect-v2-capability-carrier-workbench-staging"
        or report.get("measurement") != {
            "kind": "full-stack-guarded-workbench-product-link",
            "runtime_overlay_vma": "0xc22c",
            "runtime_overlay_vma_max": "0xc356",
            "runtime_overlay_vma_headroom_bytes": 298,
            "runtime_overlay_vma_delta_vs_2397_baseline_bytes": 306,
            "runtime_overlay_vma_delta_vs_2175_candidate_bytes": 84,
            "post_boot_reserve_bytes": 2091,
            "post_boot_reserve_hard_min_bytes": 1536,
            "post_boot_reserve_hard_headroom_bytes": 555,
            "post_boot_reserve_cp5_target_bytes": 2091,
            "post_boot_reserve_cp5_shortfall_bytes": 0,
            "post_boot_reserve_delta_vs_2397_baseline_bytes": -306,
            "post_boot_reserve_delta_vs_2175_candidate_bytes": -84,
            "boot_stack_gap_bytes": 1952,
            "deployed_bank0_delta_vs_accepted_v2_fasl_baseline_bytes": -1956,
            "slot_delta": 0,
            "island_bytes_delta": 0,
            "layout_change": False,
        }
        or report.get("verdict") != {
            "physical_link": "passed",
            "runtime_overlay_vma_budget": "passed",
            "post_boot_hard_minimum": "passed",
            "deployed_bank0_net_negative": "passed",
            "banked_abi_1_1_headroom": "release-blocker-spent-84-bytes-555-bytes-remain-banked",
            "checkpoint_4": "reclosed-with-generated-designator-dispatch-and-composition-construction-gate",
            "checkpoint_5": "pending-fresh-g5",
            "g5": "must-run-completely-from-start-on-this-binary",
        }
        or report.get("cp4_reclosure") != {
            "registry": "config/v2-native-function-registry.json",
            "native_primitive_count": 15,
            "generated_dispatch_count": 15,
            "explicit_exclusion_count": 2,
            "routes": ["direct", "funcall", "apply"],
            "engines": 4,
            "evaluations": 180,
            "boundp_prim_id": 57,
        }
        or report.get("interpretation", {}).get("release_blocker_capacity_cost_bytes") != 84
        or report.get("interpretation", {}).get("banking_policy")
        != "84-bytes-were-spent-as-an-explicit-release-blocker-exception;the-remaining-555-bytes-stay-banked-until-g5-and-then-require-one-probe-per-abi-1-1-item"
    ):
        raise ContractError("CP5 product-link measurement drift")
    prior_failure = report.get("prior_g5_failure")
    if not isinstance(prior_failure, dict) or prior_failure.get("effect") != "historical-trigger-only-no-evidence-reuse":
        raise ContractError("prior G5 failure disposition drift")
    failure_path = _binding(
        {"path": prior_failure.get("path"), "sha256": prior_failure.get("sha256")},
        "cp5_measurement.prior_g5_failure",
    )
    failure = _load(failure_path, "CP5 G5 failure receipt")
    if (
        failure.get("format") != "lisp65-v2-capability-carrier-g5-failure-v1"
        or failure.get("status") != "failed"
        or failure.get("profile") != "dialect-v2-capability-carrier"
        or failure.get("build_id") != 2581576524
        or failure.get("matrix_case", {}).get("id") != "workbench-ux/ux-complete"
        or failure.get("diagnosis", {}).get("kind")
        != "workbench-library-composition-symbol-capacity"
        or failure.get("gate_effect", {}).get("checkpoint_5") != "blocked"
        or failure.get("gate_effect", {}).get("remaining_639_bytes") != "still-banked"
    ):
        raise ContractError("CP5 G5 failure evidence drift")
    composition = _exact(
        report.get("composition_capacity"),
        {"path", "sha256", "required_libraries", "post_composition_user_symbol_margin", "post_composition_user_directory_margin", "post_composition_user_namepool_margin_bytes"},
        "cp5_measurement.composition_capacity",
    )
    composition_path = _binding(
        {"path": composition["path"], "sha256": composition["sha256"]},
        "cp5_measurement.composition_capacity",
        verify=verify_bindings,
    )
    composition_receipt = _load(composition_path, "Workbench composition capacity receipt")
    if (
        composition["required_libraries"] != ["ide", "idex", "m65d"]
        or composition["post_composition_user_symbol_margin"] < 32
        or composition["post_composition_user_directory_margin"] < 32
        or composition["post_composition_user_namepool_margin_bytes"] < 384
        or composition_receipt.get("format") != "lisp65-workbench-library-composition-capacity-v1"
        or composition_receipt.get("status") != "pass-host-and-link-g5-pending"
        or composition_receipt.get("gate_effect", {}).get("checkpoint_5") != "pending-fresh-g5"
    ):
        raise ContractError("Workbench composition capacity evidence drift")
    artifacts = report.get("artifacts")
    if (
        not isinstance(artifacts, list)
        or len(artifacts) != 7
        or any(
            not isinstance(item, dict)
            or set(item) != {"id", "path", "sha256"}
            or not isinstance(item["id"], str)
            or not isinstance(item["path"], str)
            or not isinstance(item["sha256"], str)
            or not SHA_RE.fullmatch(item["sha256"])
            for item in artifacts
        )
    ):
        raise ContractError("CP5 artifact binding inventory drift")

    for field, ids in (("rollback_levels", ("checkpoint-1", "checkpoint-2", "checkpoint-3", "checkpoint-4")), ("durability_levels", ("checkpoint-1", "checkpoint-2", "checkpoint-3", "checkpoint-4"))):
        levels = value[field]
        if not isinstance(levels, list) or len(levels) != 4:
            raise ContractError(f"{field} must contain levels 1-4")
        for index, item in enumerate(levels):
            item = _exact(item, {"level", "id", "guarantee"}, f"{field}[{index}]")
            if item["level"] != index + 1 or item["id"] != ids[index] or not isinstance(item["guarantee"], str) or not item["guarantee"]:
                raise ContractError(f"{field} level {index + 1} drift")

    layout = _exact(value["frozen_layout"], {"slot_delta", "island_bytes_delta", "layout_change", "forbidden", "bindings"}, "frozen_layout")
    if layout["slot_delta"] != 0 or layout["island_bytes_delta"] != 0 or layout["layout_change"] is not False:
        raise ContractError("layout/island/slot delta is forbidden")
    _strings(layout["forbidden"], "frozen_layout.forbidden", ("new-overlay-slot", "resident-island-use", "bank0-address-rebalance", "cap-reduction-as-financing"))
    bindings = layout["bindings"]
    if not isinstance(bindings, list) or [item.get("path") for item in bindings] != ["config/workbench.mk", "config/bank0-island-workbench.json", "config/runtime-core.mk"]:
        raise ContractError("frozen layout binding inventory drift")
    for index, item in enumerate(bindings):
        _binding(item, f"frozen_layout.bindings[{index}]", verify=verify_bindings)


def selftest(contract_path: Path, fixture_path: Path) -> None:
    contract = _load(contract_path, "capability/carrier contract")
    validate(contract)
    fixture = _load(fixture_path, "capability/carrier surface fixture")
    validate_surface_fixture(fixture)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("format", lambda x: x.__setitem__("format", "wrong")),
        ("partial", lambda x: x["atomic_scope"].__setitem__("partial_deployment", "allowed")),
        ("promotion-count", lambda x: x["promotion"].__setitem__("count", 2)),
        ("promotion-g5", lambda x: x["promotion"].__setitem__("g5_before_promotion", False)),
        ("runtime-release", lambda x: x["release_convergence"].__setitem__("runtime_core_release_effect", "release")),
        ("v1-release", lambda x: x["release_convergence"].__setitem__("dialect_v1_release", "allowed")),
        ("family-unlock", lambda x: x["release_convergence"].__setitem__("new_language_families", "allowed")),
        ("work-line", lambda x: x["release_convergence"]["active_work_lines"].append("buffer")),
        ("proof-release", lambda x: x["runtime_core_proof"].__setitem__("release_effect", "release")),
        ("proof-cp5", lambda x: x["runtime_core_proof"].__setitem__("cp5_completion_effect", "complete")),
        ("proof-receipt", lambda x: x["runtime_core_proof"].__setitem__("receipt", {"path": "x", "sha256": "0" * 64})),
        ("checkpoint-count", lambda x: x["checkpoints"].pop()),
        ("checkpoint-order", lambda x: x["checkpoints"][1].__setitem__("number", 3)),
        ("checkpoint-dependency", lambda x: x["checkpoints"][2].__setitem__("requires", [])),
        ("pending-receipt", lambda x: x["checkpoints"][0].__setitem__("receipt", {"path": "x", "sha256": "0" * 64})),
        ("registry-runtime", lambda x: x["registry"].__setitem__("construction", "runtime")),
        ("registry-fnptr", lambda x: x["registry"].__setitem__("per_call_function_pointers", True)),
        ("registry-miss", lambda x: x["registry"].__setitem__("lookup_before_carrier", "error")),
        ("carrier-artifact", lambda x: x["carrier"].__setitem__("new_loadable_artifact", True)),
        ("tombstone-id", lambda x: x["primitive_id_policy"]["v2_tombstones"][0].__setitem__("id", 3)),
        ("tombstone-reuse", lambda x: x["primitive_id_policy"]["v2_tombstones"][1].__setitem__("reuse", "allowed")),
        ("retirement-evidence", lambda x: x["primitive_id_policy"]["v2_tombstones"][2]["evidence"].__setitem__("sha256", "0" * 64)),
        ("allocation-id", lambda x: x["primitive_id_policy"]["v2_allocations"][0].__setitem__("id", 28)),
        ("internal-export", lambda x: x["primitive_id_policy"]["v2_allocations"][3].__setitem__("function_designator", True)),
        ("codec-atomicity", lambda x: x["string_codecs"].__setitem__("failure_atomicity", "best-effort")),
        ("codec-publish", lambda x: x["string_codecs"].__setitem__("arena_publication", "before-fill")),
        ("codec-span", lambda x: x["string_codecs"].__setitem__("span_dma_guarantee", "active")),
        ("vma", lambda x: x["budgets"]["workbench"].__setitem__("runtime_overlay_vma_max", "0xc400")),
        ("reserve", lambda x: x["budgets"]["workbench"].__setitem__("post_boot_reserve_min_bytes", 1024)),
        ("runtime", lambda x: x["budgets"]["runtime_core"].__setitem__("post_boot_reserve_min_bytes", 4096)),
        ("net-zero", lambda x: x["budgets"]["deployed_bank0_net_delta_bytes"].__setitem__("comparison", "less-than-or-equal")),
        ("rollback", lambda x: x["rollback_levels"].pop()),
        ("durability", lambda x: x["durability_levels"][3].__setitem__("level", 3)),
        ("slot", lambda x: x["frozen_layout"].__setitem__("slot_delta", 1)),
        ("island", lambda x: x["frozen_layout"].__setitem__("island_bytes_delta", 1)),
        ("binding", lambda x: x["frozen_layout"]["bindings"][0].__setitem__("sha256", "0" * 64)),
        ("cp5-report", lambda x: x["cp5_measurement"]["report"].__setitem__("sha256", "0" * 64)),
        ("unexpected", lambda x: x.__setitem__("unexpected", True)),
    ]
    accepted = []
    for name, mutate in mutations:
        candidate = deepcopy(contract)
        candidate["status"] = "promotion-ready"
        mutate(candidate)
        try:
            validate(candidate)
        except ContractError:
            continue
        accepted.append(name)
    if accepted:
        raise ContractError(f"selftest accepted mutations: {accepted}")
    fixture_mutations = []
    for mutate in (
        lambda x: x.__setitem__("format", "wrong"),
        lambda x: x["cases"].pop(),
        lambda x: x["cases"][0].__setitem__("checkpoint", 2),
        lambda x: x["cases"][7].__setitem__("dialect_v2", "active"),
    ):
        candidate = deepcopy(fixture)
        mutate(candidate)
        fixture_mutations.append(candidate)
    for candidate in fixture_mutations:
        try:
            validate_surface_fixture(candidate)
        except ContractError:
            continue
        raise ContractError("selftest accepted a surface fixture mutation")
    print(f"v2-capability-carrier-contract-selftest: PASS mutations={len(mutations) + len(fixture_mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    subparsers.add_parser("selftest")
    subparsers.add_parser("surface-check")
    subparsers.add_parser("policy-hash")
    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("--number", type=int, choices=range(1, 6), required=True)
    args = parser.parse_args(argv)
    try:
        contract = _load(args.contract, "capability/carrier contract")
        if args.command == "selftest":
            selftest(args.contract, args.fixture)
            return 0
        if args.command == "policy-hash":
            print(_policy_sha(contract))
            return 0
        validate(contract)
        if args.command == "surface-check":
            fixture = _load(args.fixture, "capability/carrier surface fixture")
            validate_surface_fixture(fixture)
            checkpoint_one = contract["checkpoints"][0]
            print(
                "v2-capability-carrier-surface-check: PASS "
                f"cases={len(fixture['cases'])} checkpoint_status={checkpoint_one['status']}"
            )
            return 0
        if args.command == "checkpoint":
            item = contract["checkpoints"][args.number - 1]
            if item["status"] != "passed":
                raise ContractError(f"checkpoint {args.number} is pending; implementation receipt required")
            print(f"v2-capability-carrier-check-host-{args.number}: PASS id={item['id']}")
            return 0
        passed = sum(item["status"] == "passed" for item in contract["checkpoints"])
        print(f"v2-capability-carrier-contract: PASS status={contract['status']} checkpoints={passed}/5")
        return 0
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"v2-capability-carrier-contract: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
