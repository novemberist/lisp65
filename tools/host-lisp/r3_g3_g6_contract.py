#!/usr/bin/env python3
"""Validate the fail-closed R3 G3/G6 cold-start contract and case matrix."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Callable

import workbench_product_reproducibility as REPRO
import block_capacity_delta_policy as CAPACITY
import r3_g3_harness as G3_HARNESS
import r3_product_reproducibility as R3_REPRO


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "r3-g3-g6-contract.json"
FORMAT = "lisp65-r3-g3-g6-contract-v1"
MATRIX_FORMAT = "lisp65-r3-boot-case-matrix-v1"
FIDELITY = {"emulator-valid", "hardware-only"}
EXPECTED_CASES = {
    "artifact-preflight-exact-set": ("emulator-valid", "G3", "emulator-stack"),
    "catalog-crc-reject-restage": ("emulator-valid", "G3", "emulator-stack"),
    "catalog-missing-restage": ("emulator-valid", "G3", "emulator-stack"),
    "catalog-valid-stage-chain": ("emulator-valid", "G3", "emulator-stack"),
    "disk-swap-resident-composition": ("hardware-only", "G6", "hardware-receipt"),
    "drive9-rejected": ("emulator-valid", "G3", "emulator-stack"),
    "mid-write-media-swap-abort": ("hardware-only", "G6", "hardware-receipt"),
    "power-cycle-autoboot-restage-repl": ("hardware-only", "G6", "hardware-receipt"),
    "product-media-identity-write-reject": ("emulator-valid", "G3", "emulator-stack"),
    "product-medium-physical-write-protect": ("hardware-only", "G6", "hardware-receipt"),
    "product-prg-byte-identity": ("emulator-valid", "G3", "emulator-stack"),
    "stager-entry-chain-control": ("emulator-valid", "G3", "emulator-stack"),
    "warm-reset-valid-catalog-fastpath": ("hardware-only", "G6", "hardware-receipt"),
    "work-media-save-remount-read": ("hardware-only", "G6", "hardware-receipt"),
    "arbitrary-user-media-save-remount-read": ("emulator-valid", "G3", "emulator-stack"),
}


class ContractError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"{label} must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object,
        )
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ContractError(f"{label} keys drift: {actual}")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a nonempty string")
    return value


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ContractError(f"{label} must be a string list")
    return value


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str) or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ContractError(f"{label} must be a lowercase SHA-256")
    return value


def _repo_path(value: Any, label: str) -> Path:
    raw = _string(value, label)
    pure = PurePosixPath(raw)
    if pure.is_absolute() or pure.as_posix() != raw or ".." in pure.parts:
        raise ContractError(f"{label} must be repository-relative")
    return ROOT / pure


def _binding(value: Any, label: str) -> Path:
    item = _exact(value, {"path", "sha256"}, label)
    path = _repo_path(item["path"], f"{label}.path")
    digest = _sha(item["sha256"], f"{label}.sha256")
    if path.is_symlink() or not path.is_file() or _sha_file(path) != digest:
        raise ContractError(f"{label} binding drift")
    return path


def _generated_output(value: Any, label: str) -> Path:
    item = _exact(value, {"path", "binding"}, label)
    if item["binding"] != "generated-output-sealed-by-r4":
        raise ContractError(f"{label}.binding drift")
    path = _repo_path(item["path"], f"{label}.path")
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"{label} output is absent")
    return path


def _external_binding(value: Any, label: str, verify: bool) -> None:
    item = _exact(value, {"path", "sha256", "bytes"}, label)
    path = Path(_string(item["path"], f"{label}.path"))
    digest = _sha(item["sha256"], f"{label}.sha256")
    if not path.is_absolute() or type(item["bytes"]) is not int or item["bytes"] <= 0:
        raise ContractError(f"{label} path/size is invalid")
    if verify and (
        path.is_symlink() or not path.is_file()
        or path.stat().st_size != item["bytes"] or _sha_file(path) != digest
    ):
        raise ContractError(f"{label} external binding drift")


def _container_binding(value: Any, label: str, verify: bool) -> None:
    item = _exact(value, {"container", "path", "sha256", "bytes"}, label)
    container = _string(item["container"], f"{label}.container")
    path = _string(item["path"], f"{label}.path")
    digest = _sha(item["sha256"], f"{label}.sha256")
    size = item["bytes"]
    if not path.startswith("/") or type(size) is not int or size <= 0:
        raise ContractError(f"{label} path/size is invalid")
    if not verify:
        return
    result = subprocess.run(
        ["distrobox-enter", container, "--", "sha256sum", path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    measured = result.stdout.split()[0] if result.returncode == 0 and result.stdout.split() else ""
    size_result = subprocess.run(
        ["distrobox-enter", container, "--", "stat", "-c", "%s", path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    measured_size = size_result.stdout.strip() if size_result.returncode == 0 else ""
    if measured != digest or measured_size != str(size):
        raise ContractError(f"{label} container binding drift")


def validate_matrix(value: dict[str, Any]) -> dict[str, int]:
    _exact(value, {"format", "version", "contract_id", "cases"}, "boot matrix")
    if (
        value["format"] != MATRIX_FORMAT or value["version"] != 1
        or value["contract_id"] != "workbench-r3-g3-g6"
    ):
        raise ContractError("boot matrix identity drift")
    cases = value["cases"]
    if not isinstance(cases, list) or len(cases) != len(EXPECTED_CASES):
        raise ContractError("boot matrix case count drift")
    observed: dict[str, tuple[str, str, str]] = {}
    counts = {tag: 0 for tag in sorted(FIDELITY)}
    previous = ""
    keys = {
        "id", "fidelity", "required_gate", "phase", "setup", "action",
        "expected", "oracle", "core_binding",
    }
    for index, raw in enumerate(cases):
        case = _exact(raw, keys, f"boot matrix cases[{index}]")
        case_id = _string(case["id"], f"boot matrix cases[{index}].id")
        for key in ("phase", "setup", "action", "expected", "oracle"):
            _string(case[key], f"boot matrix {case_id}.{key}")
        if case_id <= previous:
            raise ContractError("boot matrix cases must be sorted and unique")
        previous = case_id
        fidelity = case["fidelity"]
        gate = case["required_gate"]
        core = case["core_binding"]
        if fidelity not in FIDELITY:
            raise ContractError(f"boot matrix {case_id} fidelity drift")
        if (
            (fidelity == "emulator-valid" and (gate, core) != ("G3", "emulator-stack"))
            or (fidelity == "hardware-only" and (gate, core) != ("G6", "hardware-receipt"))
        ):
            raise ContractError(f"boot matrix {case_id} authority drift")
        counts[fidelity] += 1
        observed[case_id] = (fidelity, gate, core)
    if observed != EXPECTED_CASES:
        raise ContractError("boot matrix coverage/assignment drift")
    return counts


def validate(contract: dict[str, Any], *, verify_environment: bool = False) -> dict[str, int]:
    _exact(
        contract,
        {
            "format", "version", "id", "status", "release_effect", "sequence",
            "authority", "baseline_identity", "toolchain_bindings", "media_model", "stager_architecture",
            "hardware_profile", "boot_matrix", "gate_contracts", "hardware_receipt", "capacity_policy",
            "product_block", "probe",
        },
        "R3 contract",
    )
    if (
        contract["format"] != FORMAT or contract["version"] != 1
        or contract["id"] != "workbench-r3-g3-g6"
        or contract["status"] != "product-implemented-g3-not-run"
        or contract["release_effect"] != "none"
    ):
        raise ContractError("R3 contract identity/status drift")
    if contract["sequence"] != [
        "contract", "harness-skeleton", "stager-product-block", "G3",
        "R4-candidate-seal", "G5", "G6",
    ]:
        raise ContractError("R3 sequence drift")

    authority = _exact(
        contract["authority"],
        {"emulator", "hardware", "fidelity_tags", "G3_claim", "G6_claim"},
        "authority",
    )
    if authority != {
        "emulator": "prefilter-only",
        "hardware": "arbiter",
        "fidelity_tags": ["emulator-valid", "hardware-only"],
        "G3_claim": "all-and-only-emulator-valid-cases-pass",
        "G6_claim": "bound-G3-plus-all-profile-applicable-hardware-only-cases-pass-on-one-product-set-plus-explicit-profile-bound-not-applicable-cases",
    }:
        raise ContractError("emulator/hardware authority drift")

    baseline = _exact(
        contract["baseline_identity"],
        {
            "historical_r2_product_sha256", "r3_product_sha256",
            "banked_headroom_bytes", "bank_delta_bytes", "transition",
            "reproducibility",
        },
        "baseline_identity",
    )
    historical_product = _sha(
        baseline["historical_r2_product_sha256"],
        "baseline_identity.historical_r2_product_sha256",
    )
    r3_product = _sha(
        baseline["r3_product_sha256"], "baseline_identity.r3_product_sha256",
    )
    if (
        historical_product != "01fcdddd96ff898f9a4206703f40a2ae8699a21245bf6f33e35bcdb69b5d1110"
        or r3_product != "d1fd7402879409c25217afbfc076ae7e6e94fa8bcbb76b938abe01918a9c8a99"
        or baseline["banked_headroom_bytes"] != 313
        or baseline["bank_delta_bytes"] != 44
    ):
        raise ContractError("R2-to-R3 baseline identity transition drift")
    transition_path = _binding(baseline["transition"], "baseline_identity.transition")
    reproducibility_path = _binding(
        baseline["reproducibility"], "baseline_identity.reproducibility",
    )
    transition = _load(transition_path, "baseline identity transition")
    if (
        transition.get("format") != "lisp65-r3-product-identity-transition-v1"
        or transition.get("status") != "accepted"
        or transition.get("historical_r2_identity", {}).get("product_sha256") != historical_product
        or transition.get("r3_baseline_identity", {}).get("product_sha256") != r3_product
        or transition.get("bank_delta", {}).get("delta_bytes") != 44
        or transition.get("release_effect") != "none"
    ):
        raise ContractError("baseline identity transition receipt drift")
    reproducibility = _load(reproducibility_path, "product reproducibility receipt")
    try:
        REPRO.validate(reproducibility)
    except REPRO.ReproError as exc:
        raise ContractError(f"product reproducibility receipt drift: {exc}") from exc
    if (
        reproducibility["product_sha256"] != r3_product
        or reproducibility["metrics"].get("banked_headroom_bytes") != 313
        or transition.get("r3_baseline_identity", {}).get("artifact_set_sha256")
        != reproducibility["artifact_set_sha256"]
    ):
        raise ContractError("reproducible R3 baseline identity drift")

    tooling = _exact(
        contract["toolchain_bindings"],
        {"xmega65", "rom", "sd_base", "compiler", "c1541"},
        "toolchain_bindings",
    )
    xmega = _exact(tooling["xmega65"], {"artifact", "inner_artifact", "build_id"}, "xmega65")
    _external_binding(xmega["artifact"], "xmega65.artifact", verify_environment)
    _container_binding(xmega["inner_artifact"], "xmega65.inner_artifact", verify_environment)
    _string(xmega["build_id"], "xmega65.build_id")
    _external_binding(tooling["rom"], "rom", verify_environment)
    _external_binding(tooling["sd_base"], "sd_base", verify_environment)
    compiler = _exact(
        tooling["compiler"], {"invocation", "resolved_binary", "configuration", "version"},
        "compiler",
    )
    invocation = _repo_path(compiler["invocation"], "compiler.invocation")
    resolved_binary = _binding(compiler["resolved_binary"], "compiler.resolved_binary")
    if not invocation.is_symlink() or invocation.resolve() != resolved_binary.resolve():
        raise ContractError("compiler invocation symlink drift")
    _binding(compiler["configuration"], "compiler.configuration")
    _string(compiler["version"], "compiler.version")
    c1541 = _exact(tooling["c1541"], {"artifact", "version"}, "c1541")
    _external_binding(c1541["artifact"], "c1541.artifact", verify_environment)
    _string(c1541["version"], "c1541.version")

    media = _exact(
        contract["media_model"],
        {"drive_scope", "product", "work", "swap_flow", "write_defense", "transaction_context"},
        "media_model",
    )
    if media["drive_scope"] != {
        "verified_drive": 8,
        "drive_9": "out-of-scope-explicitly-rejected",
        "simultaneous_drives_required": False,
    }:
        raise ContractError("drive scope drift")
    product = _exact(
        media["product"],
        {
            "disk_name", "disk_id", "role", "mount_write_protect", "package_mode",
            "write_protect_carrier", "mutable_entries", "identity", "boot_signature",
        },
        "product media",
    )
    work = _exact(
        media["work"],
        {
            "disk_name", "disk_id", "role", "mount_write_protect", "identity",
            "provisioning", "on_device_formatter", "additional_work_media",
            "same_identity_media", "name_policy",
        },
        "work media",
    )
    if product != {
        "disk_name": "L65SYS",
        "disk_id": "65",
        "role": "read-only-product",
        "mount_write_protect": "required-only-for-physical-floppy-profile-unavailable-for-stock-core-SD-D81",
        "package_mode": "0444",
        "write_protect_carrier": "physical-floppy-tab-when-present-package-mode-is-host-side-only-for-SD-D81",
        "mutable_entries": "forbidden",
        "identity": "disk-name-plus-id-plus-packer-verified-boot-structure-marker",
        "boot_signature": {
            "format": "l65sys-boot-marker-v1", "header_offset": 29,
            "ascii": "L65B",
            "bound_entries": ["autoboot.c65", "boot.id", "lisp65.prg"],
        },
    } or work != {
        "disk_name": "arbitrary-valid-1581-name",
        "disk_id": "arbitrary-valid-1581-id",
        "role": "mutable-user-work",
        "mount_write_protect": "forbidden",
        "identity": "disk-name-plus-id",
        "provisioning": "shipped-preformatted-blank-L65WORK.D81",
        "on_device_formatter": "excluded-from-1.0",
        "additional_work_media": "any-valid-1581-media-no-rename-required",
        "same_identity_media": "distinguished-by-fresh-mount-generation-token",
        "name_policy": "no-allowlist-product-denylist-only",
    }:
        raise ContractError("two-media identity/role drift")
    if media["swap_flow"] != [
        "boot-product-on-drive-8", "stage-bank5-and-attic", "chain-workbench",
        "load-ide-idex-m65d", "prompt-one-time-swap", "validate-non-product-1581-media",
        "clear-swap-latch", "user-session-on-work-media",
    ]:
        raise ContractError("single-drive swap flow drift")
    if media["write_defense"] != {
        "identity_check": "complete-media-classification-plus-name-id-generation-and-D68B-D68F-token-before-every-write-and-directory-publish",
        "product_identity_result": "reject-product-media-read-only-before-mutation",
        "writable_identity_result": "allow-any-valid-non-product-1581-media",
        "invalid_media_result": "reject-disk-invalid-before-mutation",
        "retired_status_11": "wrong-work-media-tombstone-never-emitted",
        "transaction_latch": "fresh-mount-generation-token-plus-disk-name-plus-id-plus-D68B-D68F-mounted-image-token",
        "pre_transaction_change": "status-8-one-remount-retry-before-any-write",
        "mid_transaction_change": "status-12-terminal-no-automatic-retry-explicit-user-restart",
        "planning_read_guard": "post-capture-status-6-plus-D68B-D68F-mismatch-becomes-terminal-status-12-stable-token-preserves-status-6-zero-writes",
        "mount_token_guard": "final-check-before-D081-trigger-postcheck-after-BUSY-and-guarded-readback",
        "residual_window": "30-cycles-including-last-D68F-read-through-D081-store-non-atomic-Freezer-reachable",
        "residual_window_policy": "owner-accepted-stock-core-contract-limit-no-atomicity-claim-at-most-one-foreign-sector-then-status-12",
        "phase_oracles": "three-normal-token-change-rejections-plus-three-after-guard-one-sector-boundary-characterizations-not-safety-passes-plus-one-real-Freezer-boundary-confirmation",
        "physical_write_protect": "independent-second-line-of-defense-only-for-physical-media-profile-explicitly-not-applicable-for-stock-core-SD-D81",
        "directory_root": "T40-S0-link-and-header-only-first-entry-sector-at-least-3",
        "external_integrity_oracle": "blank-create-replace-and-multisector-full-D81-two-witness-BAM-check",
    }:
        raise ContractError("media write-defense drift")
    transaction_context_path = _binding(media["transaction_context"], "media_model.transaction_context")
    transaction_context = _load(transaction_context_path, "F011 transaction context")
    if (
        transaction_context.get("format") != "lisp65-f011-transaction-context-v1"
        or transaction_context.get("status") != "permanent-product-contract"
        or transaction_context.get("permanent_hardware_case", {}).get("id")
        != "work-media-save-remount-read"
        or transaction_context.get("permanent_hardware_case", {}).get("precondition")
        != "write-0x80-to-D689-immediately-before-save"
        or transaction_context.get("mount_token_guard", {}).get("window_classification")
        != "non-atomic-and-therefore-principally-Freezer-reachable"
        or transaction_context.get("mount_token_guard", {}).get("owner_residual_risk_decision")
        != {
            "accepted": True,
            "date": "2026-07-14",
            "stock_core_required": True,
            "atomicity_claim": False,
            "damage_bound": "one-sector-maximum-on-newly-mounted-medium-then-terminal-status-12",
            "user_message": "medium changed during write; check both disks",
            "upstream_candidate": "official-mega65-core-drive0-mount-lock-no-project-fork",
            "promotion_effect": "not-blocking-after-three-boundary-characterizations-and-normal-phase-oracles-pass",
        }
    ):
        raise ContractError("F011 transaction-context contract drift")

    profile_path = _binding(contract["hardware_profile"], "hardware_profile")
    profile = _load(profile_path, "G6 hardware profile")
    if (
        profile.get("format") != "lisp65-g6-hardware-profile-v1"
        or profile.get("id") != "stock-core-sd-d81"
        or profile.get("status") != "owner-approved"
        or profile.get("G6", {}).get("not_applicable", {}).get("case_id")
        != "product-medium-physical-write-protect"
        or len(profile.get("G6", {}).get("applicable_hardware_cases", [])) != 5
        or profile.get("product_code_path_audit", {}).get("physical_write_protect_signal_branches") != []
    ):
        raise ContractError("G6 hardware profile drift")

    stager = _exact(
        contract["stager_architecture"],
        {
            "artifact_id", "role", "implementation_status", "linked_into_workbench_prg",
            "product_artifact_set_membership", "build_identity",
            "workbench_bank0_delta_expected", "boot_overlay_delta_expected",
            "workbench_artifact_sha_policy", "ram_authority", "chain", "catalog_recovery",
        },
        "stager_architecture",
    )
    if stager != {
        "artifact_id": "lisp65-workbench-cold-stager",
        "role": "AUTOBOOT.C65-separate-chained-artifact",
        "implementation_status": "product-implemented-g3-not-run",
        "linked_into_workbench_prg": False,
        "product_artifact_set_membership": "required",
        "build_identity": "compiled-stager-id-equals-descriptor-record-CRC-and-binds-exact-product-PRG-catalog-and-libraries",
        "workbench_bank0_delta_expected": 0,
        "boot_overlay_delta_expected": 0,
        "workbench_artifact_sha_policy": "all-existing-product-artifacts-byte-identical",
        "ram_authority": "pre-product-may-use-unreserved-machine-ram",
        "chain": [
            "AUTOBOOT", "stager", "validate-or-restage-bank5",
            "validate-or-restage-attic", "exact-product-prg",
        ],
        "catalog_recovery": {
            "valid": "skip-restage",
            "missing": "full-restage-from-product-media",
            "crc-invalid": "full-restage-from-product-media",
            "after_restage": "reverify-bank5-and-attic-before-chain",
            "retry_limit": 2,
            "retry_exhausted": "halt",
            "user_error": "L65SYS DISK ERROR - CHECK MEDIA",
            "partial-restage": "forbidden",
            "chain-before-valid": "forbidden",
        },
    }:
        raise ContractError("separate stager architecture drift")

    matrix_binding = _exact(contract["boot_matrix"], {"path", "sha256", "counts"}, "boot_matrix")
    matrix_path = _repo_path(matrix_binding["path"], "boot_matrix.path")
    matrix_sha = _sha(matrix_binding["sha256"], "boot_matrix.sha256")
    if matrix_path.is_symlink() or not matrix_path.is_file() or _sha_file(matrix_path) != matrix_sha:
        raise ContractError("boot matrix SHA binding drift")
    counts = validate_matrix(_load(matrix_path, "boot matrix"))
    if matrix_binding["counts"] != {"emulator-valid": 9, "hardware-only": 6, "total": 15}:
        raise ContractError("boot matrix count binding drift")

    gates = _exact(contract["gate_contracts"], {"G3", "G6"}, "gate_contracts")
    if gates["G3"] != {
        "status": "static-preflight-passed-not-run",
        "preflight": "static-exact-15-case-matrix-before-launch",
        "required_fidelity": "emulator-valid",
        "forbidden_claims": ["F011-timing", "SD-buffer-address", "DMA-timing", "physical-reset-semantics"],
    } or gates["G6"] != {
        "status": "contract-only-not-run",
        "requires": ["bound-G3-receipt", "R4-candidate", "G5-receipt"],
        "required_fidelity": "hardware-only-and-profile-applicable",
        "not_applicable_policy": "manifest-bound-profile-receipt-no-synthetic-PASS",
        "core_policy": "same-bound-core-ROM-product-set-for-all-hardware-cases",
        "pc_free": True,
    }:
        raise ContractError("G3/G6 gate contract drift")

    hardware = _exact(
        contract["hardware_receipt"],
        {"required_bindings", "physical_cycle_policy", "product_identity"},
        "hardware_receipt",
    )
    required = _strings(hardware["required_bindings"], "hardware_receipt.required_bindings")
    if required != [
        "machine-serial", "core-id", "core-version", "rom-sha256",
        "product-artifact-set-sha256", "product-d81-sha256", "work-d81-sha256",
        "physical-cycle-id", "raw-evidence-sha256",
    ] or hardware["physical_cycle_policy"] != "nonempty-unique-per-power-or-reset-case" or hardware["product_identity"] != "one-artifact-SHA-set":
        raise ContractError("hardware core/receipt binding drift")

    capacity_path = _binding(contract["capacity_policy"], "capacity_policy")
    try:
        CAPACITY.validate_policy(capacity_path)
    except CAPACITY.CapacityDeltaError as exc:
        raise ContractError(f"capacity policy drift: {exc}") from exc

    block = _exact(
        contract["product_block"],
        {
            "receipt", "reproducibility", "harness", "artifact_set_sha256",
            "status", "release_effect",
        },
        "product_block",
    )
    receipt_path = _generated_output(block["receipt"], "product_block.receipt")
    product_repro_path = _generated_output(
        block["reproducibility"], "product_block.reproducibility",
    )
    harness_path = _generated_output(block["harness"], "product_block.harness")
    receipt = _load(receipt_path, "R3 product block receipt")
    if (
        receipt.get("format") != "lisp65-r3-product-block-receipt-v1"
        or receipt.get("id") != "r3-cold-start-two-media-product-block"
        or receipt.get("status") != "product-implemented-g3-not-run"
        or receipt.get("contract_id") != contract["id"]
        or receipt.get("release_effect") != "none"
    ):
        raise ContractError("product block receipt identity/status drift")
    try:
        CAPACITY.validate_capacity_delta(receipt["capacity_delta"])
    except (CAPACITY.CapacityDeltaError, KeyError) as exc:
        raise ContractError(f"product block capacity delta drift: {exc}") from exc
    identity = receipt.get("product_identity")
    if not isinstance(identity, dict):
        raise ContractError("product block identity missing")
    artifact_set = _sha(block["artifact_set_sha256"], "product_block.artifact_set_sha256")
    product_repro = _load(product_repro_path, "R3 product reproducibility receipt")
    try:
        R3_REPRO.validate(product_repro)
    except R3_REPRO.ReproError as exc:
        raise ContractError(f"R3 product reproducibility drift: {exc}") from exc
    if (
        product_repro.get("artifact_set_sha256") != artifact_set
        or product_repro.get("product_receipt_sha256") != _sha_file(receipt_path)
        or product_repro.get("claims")
        != {"G3": "not-run", "G6": "not-run", "release_effect": "none"}
    ):
        raise ContractError("R3 reproducibility/product-block parity drift")
    null_deltas = _exact(
        receipt.get("null_deltas"),
        {"workbench_bank_bytes", "boot_overlay_bytes", "boot_overlay"},
        "product_block.null_deltas",
    )
    boot_overlay = _exact(
        null_deltas["boot_overlay"], {"name", "path", "role", "bytes", "sha256"},
        "product_block.null_deltas.boot_overlay",
    )
    overlay_path = _repo_path(boot_overlay["path"], "product_block.boot_overlay.path")
    if (
        block["status"] != "product-implemented-g3-not-run"
        or block["release_effect"] != "none"
        or identity.get("artifact_set_sha256") != artifact_set
        or null_deltas["workbench_bank_bytes"] != 0
        or null_deltas["boot_overlay_bytes"] != 0
        or boot_overlay["role"] != "boot-overlay"
        or type(boot_overlay["bytes"]) is not int or boot_overlay["bytes"] <= 0
        or _sha(boot_overlay["sha256"], "product_block.boot_overlay.sha256")
        != boot_overlay["sha256"]
        or overlay_path.is_symlink() or not overlay_path.is_file()
        or overlay_path.stat().st_size != boot_overlay["bytes"]
        or _sha_file(overlay_path) != boot_overlay["sha256"]
    ):
        raise ContractError("product block claim/null-delta drift")
    verification = receipt.get("verification")
    chain_walkers = verification.get("chain_walker_inventory") if isinstance(verification, dict) else None
    if (
        not isinstance(verification, dict)
        or verification.get("emulator_started") is not False
        or verification.get("l_lite_generated_keymap")
        != "41-bindings-5-M-x-6-outputs-pass"
        or verification.get("l_lite_ide_host_oracle") != "87/87-pass"
        or verification.get("l_lite_p0_differential")
        != "2-suites-187-functions-163-cases-350-objects-pass"
        or verification.get("l_lite_hardware") != "not-run"
        or verification.get("product_d81_inventory") != "exact"
        or verification.get("work_d81_blank") is not True
        or not isinstance(chain_walkers, dict)
        or chain_walkers.get("walkers") != 18
        or chain_walkers.get("shared_negative_classes") != 3
        or chain_walkers.get("deviations") != 0
        or any(
            not isinstance(verification.get(gate), dict)
            or set(verification[gate].values()) != {"not-run"}
            for gate in ("G3", "G6")
        )
    ):
        raise ContractError("product block evidence boundary drift")
    media_receipt = receipt.get("media")
    if (
        not isinstance(media_receipt, dict)
        or media_receipt.get("product", {}).get("identity")
        != {"disk_name": "L65SYS", "disk_id": "65"}
        or media_receipt.get("product", {}).get("package_mode") != "0444"
        or media_receipt.get("work", {}).get("identity")
        != {"disk_name": "L65WORK", "disk_id": "65"}
        or media_receipt.get("work", {}).get("entries") != []
        or media_receipt.get("work", {}).get("provisioning")
        != "shipped-preformatted-blank"
        or media_receipt.get("write_defense") != {
            "boot_signature": {
                "format": "l65sys-boot-marker-v1", "header_offset": 29,
                "ascii": "L65B",
                "bound_entries": ["autoboot.c65", "boot.id", "lisp65.prg"],
            },
            "generation": "fresh-latch-token-per-successful-remount",
            "identity": "complete-canonical-name-plus-exact-id-plus-D68B-D68F-token-bound-per-transaction",
            "invalid_status": 6,
            "product_status": 10,
            "retired_status_11": "never-emitted",
            "midtransaction_status": 12,
            "automatic_retry": "pretransaction-status-8-only",
            "planning_read_guard": "post-capture-status-6-plus-D68B-D68F-mismatch-becomes-terminal-status-12-stable-token-preserves-status-6-zero-writes",
            "residual_window": "owner-accepted-at-most-one-foreign-sector-not-a-safety-pass",
            "writable_media": "any-valid-non-product-1581",
        }
    ):
        raise ContractError("product media receipt drift")
    capacity_watch = receipt.get("capacity_watch")
    if capacity_watch != {
        "bank": {
            "post_boot_reserve": 1907,
            "release_floor": 1536,
            "banked_reserve": 371,
            "status": "target-met-wave-3-aggregate-credit",
        },
        "ext": {
            "post_headroom": 26232,
            "release_floor": 16384,
            "margin": 9848,
            "status": "wave-1-structural-relief-preserved-through-wave-3",
            "next_debit": "normal-block-authorization-required",
            "relief_rule": "16-KiB-user-capacity-floor-remains-binding",
        },
        "overlay": {
            "headroom": 0,
            "color_scroll_rider": "deferred-to-C2-after-final-authorized-attempt",
            "status": "frozen-zero-headroom-C2-runtime-layout-cure-required",
        },
        "resident_island": {
            "payload_bytes": 1668,
            "annex_bytes": 260,
            "reserve_bytes": 120,
            "status": "owner-authorized-watch-listed",
            "next_debit": "explicit-island-capacity-delta-and-prior-authorization-required",
            "wave_1_1_m": "must-measure-and-report-resident-island-demand",
        },
        "structural_relief": "1.1-C1-complete; compiler tier retired after compilation",
    }:
        raise ContractError("product capacity watch drift")
    stager_receipt = receipt.get("stager")
    sector_budget = stager_receipt.get("sector_chain_budget") if isinstance(stager_receipt, dict) else None
    if (
        not isinstance(stager_receipt, dict)
        or stager_receipt.get("linked_into_workbench_prg") is not False
        or stager_receipt.get("error_message") != "L65SYS DISK ERROR - CHECK MEDIA"
        or stager_receipt.get("descriptor", {}).get("retry_limit") != 2
        or stager_receipt.get("model_verification", {}).get("restage_then_reverify") != "pass"
        or stager_receipt.get("model_verification", {}).get("retry_exhaustion") != "halt"
        or stager_receipt.get("model_verification", {}).get("mixed_build") != "fail-closed"
        or not isinstance(sector_budget, dict)
        or sector_budget.get("payload_bytes_per_sector") != 254
        or sector_budget.get("fuel_type") != "uint16_t"
        or sector_budget.get("bound") != "ceil(expected_length/254)-with-819200-byte-media-cap"
        or sector_budget.get("greater_than_255_sector_cases") != ["overlays.bin", "shelf.bin"]
    ):
        raise ContractError("product stager receipt drift")

    harness = _load(harness_path, "R3 G3 harness")
    try:
        state = G3_HARNESS.validate(harness)
    except G3_HARNESS.HarnessError as exc:
        raise ContractError(f"G3 harness drift: {exc}") from exc
    if (
        state["counts"] != {"emulator-valid": 9, "hardware-only": 6}
        or _sha_file(state["product"]) != _sha_file(receipt_path)
        or state["product_value"].get("product_identity", {}).get("artifact_set_sha256")
        != artifact_set
    ):
        raise ContractError("product block/harness parity drift")

    probe = _exact(
        contract["probe"],
        {"validator", "runner", "stager_source", "expected_status", "claims"},
        "probe",
    )
    _binding(probe["validator"], "probe.validator")
    _binding(probe["runner"], "probe.runner")
    _binding(probe["stager_source"], "probe.stager_source")
    if probe["expected_status"] != "passed-not-implemented" or probe["claims"] != {
        "separate_artifact": True,
        "product_bank0_delta": 0,
        "media_loader_implemented": False,
        "G3": "not-run",
        "G6": "not-run",
    }:
        raise ContractError("probe claim boundary drift")
    return counts


def selftest(contract: dict[str, Any]) -> None:
    validate(contract)
    matrix_path = _repo_path(contract["boot_matrix"]["path"], "boot_matrix.path")
    matrix = _load(matrix_path, "boot matrix")
    failures = 0
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("release claim", lambda x: x.update(release_effect="release")),
        ("authority", lambda x: x["authority"].update(hardware="peer")),
        ("baseline identity", lambda x: x["baseline_identity"].update(r3_product_sha256="f" * 64)),
        ("drive 9", lambda x: x["media_model"]["drive_scope"].update(drive_9="verified")),
        ("single disk", lambda x: x["media_model"]["work"].update(disk_name="L65SYS")),
        ("write check", lambda x: x["media_model"]["write_defense"].update(identity_check="once")),
        ("linked stager", lambda x: x["stager_architecture"].update(linked_into_workbench_prg=True)),
        ("bank delta", lambda x: x["stager_architecture"].update(workbench_bank0_delta_expected=1)),
        (
            "partial restage",
            lambda x: x["stager_architecture"]["catalog_recovery"].__setitem__(
                "partial-restage", "allowed",
            ),
        ),
        ("G3 timing claim", lambda x: x["gate_contracts"]["G3"].update(forbidden_claims=[])),
        ("core receipt", lambda x: x["hardware_receipt"].update(required_bindings=[])),
        ("capacity policy", lambda x: x.update(capacity_policy={})),
        ("product block", lambda x: x["product_block"].update(artifact_set_sha256="f" * 64)),
        ("probe claim", lambda x: x["probe"]["claims"].update(media_loader_implemented=True)),
    ]
    for name, mutate in mutations:
        candidate = deepcopy(contract)
        mutate(candidate)
        try:
            validate(candidate)
        except ContractError:
            continue
        print(f"r3-g3-g6-contract selftest: mutation survived: {name}", file=sys.stderr)
        failures += 1
    matrix_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("fidelity", lambda x: x["cases"][0].update(fidelity="hardware-only")),
        ("gate", lambda x: x["cases"][0].update(required_gate="G6")),
        ("core", lambda x: x["cases"][0].update(core_binding="hardware-receipt")),
        ("missing case", lambda x: x["cases"].pop()),
    ]
    for name, mutate in matrix_mutations:
        candidate = deepcopy(matrix)
        mutate(candidate)
        try:
            validate_matrix(candidate)
        except ContractError:
            continue
        print(f"r3-g3-g6-contract selftest: matrix mutation survived: {name}", file=sys.stderr)
        failures += 1
    if failures:
        raise ContractError(f"selftest failures={failures}")
    print(f"r3-g3-g6-contract: SELFTEST PASS mutations={len(mutations) + len(matrix_mutations)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "environment-check", "selftest"))
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args(argv)
    path = args.contract if args.contract.is_absolute() else ROOT / args.contract
    try:
        contract = _load(path, "R3 contract")
        if args.command == "selftest":
            selftest(contract)
        else:
            counts = validate(contract, verify_environment=args.command == "environment-check")
            print(
                "r3-g3-g6-contract: PASS "
                f"status={contract['status']} emulator={counts['emulator-valid']} "
                f"hardware={counts['hardware-only']} release={contract['release_effect']}"
            )
        return 0
    except (ContractError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"r3-g3-g6-contract: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
