#!/usr/bin/env python3
"""Validate the fail-closed AP6 persistence transaction contract."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable


FORMAT = "lisp65-persistence-contract-v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config" / "persistence-contract.json"
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")

ROOT_KEYS = {
    "format",
    "scope",
    "name_contract",
    "directory_contract",
    "allocation_contract",
    "transaction_contract",
    "fault_contract",
    "write_latch",
    "media_policy",
    "external_integrity_oracle",
    "status_contract",
}
SCOPE_KEYS = {
    "operations",
    "mutation_model",
    "min_payload_bytes",
    "max_payload_bytes",
    "writer_model",
}
NAME_KEYS = {
    "encoding",
    "min_bytes",
    "max_bytes",
    "printable_byte_min",
    "printable_byte_max",
    "case_mapping",
    "forbidden_bytes",
    "invalid_status",
}
DIRECTORY_KEYS = {
    "start_track",
    "start_sector",
    "root_sector_role",
    "first_entry_sector_min",
    "scan",
    "growth",
    "upsert_commit",
    "create_commit",
    "create_existing_status",
    "no_free_entry_status",
    "invalid_chain_status",
}
INTEGRITY_ORACLE_KEYS = {
    "authority",
    "implementations",
    "fixture_classes",
    "header_invariant",
    "directory_invariant",
    "bam_invariants",
    "two_media_invariant",
}
ALLOCATION_KEYS = {
    "source_of_truth",
    "candidate_sectors",
    "directory_track_excluded",
    "new_chain_excludes_old_chain",
    "new_chain_single_bam_half",
    "claim_granularity",
    "halves",
    "insufficient_single_half_status",
}
HALF_KEYS = {"id", "first_track", "last_track", "bam_track", "bam_sector"}
TRANSACTION_KEYS = {
    "ordered_steps",
    "commit_point",
    "data_verify",
    "directory_commit",
    "old_chain_untouched_before_commit",
    "old_chain_release",
    "create_release_step",
    "precommit_visibility",
    "postcommit_release_failure_status",
}
FAULT_KEYS = {
    "injection_model",
    "operation_unit",
    "mid_operation_faults",
    "planning_read_guard",
    "command_guard",
    "publish_guard",
    "residual_window",
    "freezer_atomicity",
    "residual_window_policy",
    "residual_damage_bound",
    "residual_detection",
    "power_loss",
    "rollback",
    "precommit_safety",
    "postcommit_safety",
    "write_verify_failure",
    "recovery",
}
LATCH_KEYS = {
    "initial_state",
    "latched_state",
    "triggers",
    "mutation_while_latched",
    "status_while_latched",
    "clear_event",
    "remount_validation",
    "cross_file_sector_ownership_validation",
    "automatic_retry",
}
MEDIA_KEYS = {
    "writable_media",
    "product_identity",
    "product_disk_name",
    "product_disk_id",
    "product_boot_signature",
    "mount_write_protect",
    "transaction_identity",
    "pretransaction_identity_change",
    "midtransaction_identity_change",
    "post_capture_planning_read_change",
    "invalid_status",
    "product_status",
    "retired_status",
}
STATUS_CONTRACT_KEYS = {"namespace", "dense", "stable_across_builds", "codes"}
STATUS_KEYS = {"code", "id", "outcome"}

OPERATIONS = ["upsert", "create-new"]
TRANSACTION_STEPS = [
    "plan",
    "write-data-verify",
    "claim-new-chain-bam",
    "commit-directory",
    "release-old-chain",
]
EXPECTED_STATUSES = [
    (0, "ok", "committed"),
    (1, "bad-name", "rejected"),
    (2, "duplicate", "rejected"),
    (3, "too-large", "rejected"),
    (4, "no-space", "rejected"),
    (5, "directory-full", "rejected"),
    (6, "read-invalid", "failed"),
    (7, "write-verify-failed", "failed-needs-remount"),
    (8, "needs-remount", "latched"),
    (9, "committed-with-leak", "committed-warning"),
    (10, "product-media-read-only", "rejected"),
    (11, "wrong-work-media", "retired-never-emitted"),
    (12, "media-changed-during-transaction", "failed-terminal-explicit-restart-after-remount"),
]


class ContractError(RuntimeError):
    """The persistence contract is malformed or weakens a pinned invariant."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"contract must be a regular non-symlink file: {path}")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object
        )
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read persistence contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("contract root must be an object")
    return value


def _exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    missing = sorted(keys - set(value))
    unknown = sorted(set(value) - keys)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise ContractError(f"{label} has " + "; ".join(details))
    return value


def _require(value: Any, expected: Any, label: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ContractError(f"{label} must be {expected!r}, got {value!r}")


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ContractError(f"{label} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ContractError(f"{label} contains duplicates")
    return value


def validate_contract(raw: dict[str, Any]) -> None:
    _exact_object(raw, ROOT_KEYS, "contract")
    _require(raw["format"], FORMAT, "format")

    scope = _exact_object(raw["scope"], SCOPE_KEYS, "scope")
    _require(scope["operations"], OPERATIONS, "scope.operations")
    _require(scope["mutation_model"], "copy-on-write", "scope.mutation_model")
    _require(scope["min_payload_bytes"], 1, "scope.min_payload_bytes")
    _require(scope["max_payload_bytes"], 8192, "scope.max_payload_bytes")
    _require(
        scope["writer_model"],
        "exclusive-single-writer-mounted-d81",
        "scope.writer_model",
    )

    name = _exact_object(raw["name_contract"], NAME_KEYS, "name_contract")
    _require(name["encoding"], "ascii", "name_contract.encoding")
    _require(name["min_bytes"], 1, "name_contract.min_bytes")
    _require(name["max_bytes"], 16, "name_contract.max_bytes")
    _require(name["printable_byte_min"], 33, "name_contract.printable_byte_min")
    _require(name["printable_byte_max"], 126, "name_contract.printable_byte_max")
    _require(name["case_mapping"], "ascii-upper", "name_contract.case_mapping")
    _require(
        name["forbidden_bytes"],
        [34, 42, 47, 58, 63, 92],
        "name_contract.forbidden_bytes",
    )
    _require(name["invalid_status"], "bad-name", "name_contract.invalid_status")

    directory = _exact_object(
        raw["directory_contract"], DIRECTORY_KEYS, "directory_contract"
    )
    directory_expected = {
        "start_track": 40,
        "start_sector": 0,
        "root_sector_role": "link-and-header-only-no-directory-entries",
        "first_entry_sector_min": 3,
        "scan": "full-existing-directory-chain",
        "growth": "forbidden",
        "upsert_commit": "reuse-single-match-or-free-entry",
        "create_commit": "free-entry-in-existing-chain",
        "create_existing_status": "duplicate",
        "no_free_entry_status": "directory-full",
        "invalid_chain_status": "read-invalid",
    }
    for key, expected in directory_expected.items():
        _require(directory[key], expected, f"directory_contract.{key}")

    allocation = _exact_object(
        raw["allocation_contract"], ALLOCATION_KEYS, "allocation_contract"
    )
    allocation_expected = {
        "source_of_truth": "validated-bam",
        "candidate_sectors": "free-data-sectors-only",
        "directory_track_excluded": 40,
        "new_chain_excludes_old_chain": True,
        "new_chain_single_bam_half": True,
        "claim_granularity": "one-bam-sector-image-for-new-chain",
        "insufficient_single_half_status": "no-space",
    }
    for key, expected in allocation_expected.items():
        _require(allocation[key], expected, f"allocation_contract.{key}")
    halves = allocation["halves"]
    if not isinstance(halves, list) or len(halves) != 2:
        raise ContractError("allocation_contract.halves must contain exactly two halves")
    expected_halves = [
        {"id": "low", "first_track": 1, "last_track": 39, "bam_track": 40, "bam_sector": 1},
        {"id": "high", "first_track": 41, "last_track": 80, "bam_track": 40, "bam_sector": 2},
    ]
    for index, (half, expected) in enumerate(zip(halves, expected_halves)):
        half = _exact_object(half, HALF_KEYS, f"allocation_contract.halves[{index}]")
        for key, expected_value in expected.items():
            _require(
                half[key], expected_value, f"allocation_contract.halves[{index}].{key}"
            )

    transaction = _exact_object(
        raw["transaction_contract"], TRANSACTION_KEYS, "transaction_contract"
    )
    transaction_expected = {
        "ordered_steps": TRANSACTION_STEPS,
        "commit_point": "commit-directory",
        "data_verify": "every-logical-sector-before-bam-claim",
        "directory_commit": "publish-create-or-switch-upsert",
        "old_chain_untouched_before_commit": True,
        "old_chain_release": "upsert-replacement-only-after-directory-commit",
        "create_release_step": "not-applicable",
        "precommit_visibility": "none",
        "postcommit_release_failure_status": "committed-with-leak",
    }
    for key, expected in transaction_expected.items():
        _require(transaction[key], expected, f"transaction_contract.{key}")

    fault = _exact_object(raw["fault_contract"], FAULT_KEYS, "fault_contract")
    fault_expected = {
        "injection_model": "operation-boundaries-plus-mounted-image-token-at-F011-command",
        "operation_unit": "completed-and-verified-logical-or-metadata-sector-operation",
        "mid_operation_faults": "mounted-image-change-detected-before-command-or-after-completion",
        "planning_read_guard": "after-token-capture-status-6-is-reclassified-to-terminal-status-12-iff-D68B-D68F-changed-stable-token-preserves-status-6-zero-writes-in-both-cases",
        "command_guard": "D68B-drive0-media-bits-plus-D68C-D68F-token-final-check-before-D081-trigger-postcheck-after-BUSY-and-after-readback",
        "publish_guard": "BAM-and-directory-writes-guarded-before-command-after-completion-and-before-next-transaction-step",
        "residual_window": "per-sector-30-cycles-including-final-D68F-read-and-D081-store-26-after-read-completion-740.741ns-nominal-at-40.5MHz",
        "freezer_atomicity": "not-claimed-RESTORE-hypervisor-trap-can-interpose-at-an-instruction-boundary",
        "residual_window_policy": "owner-accepted-stock-core-contract-limit-no-atomicity-claim",
        "residual_damage_bound": "at-most-one-data-BAM-or-directory-sector-can-hit-newly-mounted-medium-source-unchanged-by-that-command-then-status-12-stops-all-writes",
        "residual_detection": "post-command-token-check-terminal-status-12-check-both-media-before-any-explicit-restart",
        "power_loss": "not-claimed",
        "rollback": "none",
        "precommit_safety": "leak-safe-no-visible-partial-file",
        "postcommit_safety": "new-version-visible-old-allocation-may-leak",
        "write_verify_failure": "medium-state-indeterminate-latch-required",
        "recovery": "explicit-remount-and-validate",
    }
    for key, expected in fault_expected.items():
        _require(fault[key], expected, f"fault_contract.{key}")

    latch = _exact_object(raw["write_latch"], LATCH_KEYS, "write_latch")
    latch_expected = {
        "initial_state": "ready",
        "latched_state": "needs-remount",
        "triggers": [
            "write-verify-failed",
            "read-invalid-after-first-write",
            "media-changed-during-transaction",
        ],
        "mutation_while_latched": "forbidden",
        "status_while_latched": "needs-remount",
        "clear_event": "explicit-remount",
        "remount_validation": "both-bam-halves-count-bitmaps-full-directory-link-chain-and-used-entry-structure",
        "cross_file_sector_ownership_validation": "not-claimed",
        "automatic_retry": "forbidden-for-terminal-or-latched-status; one-remount-retry-only-for-pretransaction-status-8",
    }
    for key, expected in latch_expected.items():
        _require(latch[key], expected, f"write_latch.{key}")

    media = _exact_object(raw["media_policy"], MEDIA_KEYS, "media_policy")
    media_expected = {
        "writable_media": "any-valid-non-product-1581",
        "product_identity": "disk-name-plus-id-plus-packer-verified-boot-structure-marker",
        "product_disk_name": "L65SYS",
        "product_disk_id": "65",
        "product_boot_signature": {
            "format": "l65sys-boot-marker-v1", "header_offset": 29,
            "ascii": "L65B",
            "bound_entries": ["autoboot.c65", "boot.id", "lisp65.prg"],
        },
        "mount_write_protect": "independent-second-line-of-defense-when-the-active-profile-provides-physical-or-virtual-read-only-media-stock-core-SD-D81-profile-explicitly-does-not",
        "transaction_identity": "complete-canonical-disk-name-plus-exact-id-plus-fresh-mount-generation-plus-D68B-D68F-mounted-image-token",
        "pretransaction_identity_change": "status-8-needs-remount-one-automatic-remount-retry-allowed-before-any-transaction-write",
        "midtransaction_identity_change": "status-12-terminal-no-automatic-remount-or-retry-user-must-explicitly-restart-save",
        "post_capture_planning_read_change": "status-6-with-D68B-D68F-mismatch-reclassified-to-status-12-before-retry-or-write-stable-token-status-6-preserved",
        "invalid_status": "read-invalid",
        "product_status": "product-media-read-only",
        "retired_status": "wrong-work-media",
    }
    for key, expected in media_expected.items():
        _require(media[key], expected, f"media_policy.{key}")

    integrity = _exact_object(
        raw["external_integrity_oracle"],
        INTEGRITY_ORACLE_KEYS,
        "external_integrity_oracle",
    )
    integrity_expected = {
        "authority": "independent-full-d81-parser-never-m65d-self-readback",
        "implementations": [
            "tools/host-lisp/d81_persistence_fault.py",
            "tools/host-lisp/d81_bam_sanity.py",
        ],
        "fixture_classes": [
            "blank-create",
            "blank-create-replace",
            "blank-multisector-create",
            "blank-multisector-replace",
            "two-media-swap-before-data-write",
            "two-media-swap-before-bam-write",
            "two-media-swap-before-directory-write",
        ],
        "two_media_invariant": "independent-full-image-oracle-for-source-and-target-at-each-injected-phase-target-never-mutated",
        "header_invariant": "T40-S0-never-written-and-byte-identical-link-and-header-only",
        "directory_invariant": "entries-only-in-linked-sectors-T40-S3-or-later",
        "bam_invariants": [
            "allocated-data-sectors-equal-visible-file-chains",
            "no-orphan-allocation",
            "no-double-allocation",
            "directory-block-count-equals-visible-chain-blocks",
            "free-data-plus-visible-file-blocks-equals-3160",
        ],
    }
    for key, expected in integrity_expected.items():
        _require(integrity[key], expected, f"external_integrity_oracle.{key}")

    status_contract = _exact_object(
        raw["status_contract"], STATUS_CONTRACT_KEYS, "status_contract"
    )
    _require(
        status_contract["namespace"],
        "lisp65-persistence-status-v1",
        "status_contract.namespace",
    )
    _require(status_contract["dense"], True, "status_contract.dense")
    _require(
        status_contract["stable_across_builds"],
        True,
        "status_contract.stable_across_builds",
    )
    codes = status_contract["codes"]
    if not isinstance(codes, list):
        raise ContractError("status_contract.codes must be a list")
    actual_statuses: list[tuple[int, str, str]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(codes):
        item = _exact_object(item, STATUS_KEYS, f"status_contract.codes[{index}]")
        code, ident, outcome = item["code"], item["id"], item["outcome"]
        if type(code) is not int or not 0 <= code <= 255:
            raise ContractError(f"status_contract.codes[{index}].code must be u8")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
            raise ContractError(f"status_contract.codes[{index}].id is not canonical")
        if ident in seen_ids:
            raise ContractError(f"duplicate persistence status id: {ident}")
        if not isinstance(outcome, str) or not outcome:
            raise ContractError(f"status_contract.codes[{index}].outcome is empty")
        seen_ids.add(ident)
        actual_statuses.append((code, ident, outcome))
    if actual_statuses != EXPECTED_STATUSES:
        raise ContractError("stable persistence status table changed")

    status_ids = {ident for _, ident, _ in actual_statuses}
    references = {
        name["invalid_status"],
        directory["create_existing_status"],
        directory["no_free_entry_status"],
        directory["invalid_chain_status"],
        allocation["insufficient_single_half_status"],
        transaction["postcommit_release_failure_status"],
        latch["status_while_latched"],
        media["invalid_status"],
        media["product_status"],
        media["retired_status"],
    }
    missing_references = sorted(references - status_ids)
    if missing_references:
        raise ContractError(
            "contract references unknown statuses: " + ", ".join(missing_references)
        )


def _expect_rejected(raw: dict[str, Any], mutate: Callable[[dict[str, Any]], None]) -> None:
    candidate = deepcopy(raw)
    mutate(candidate)
    try:
        validate_contract(candidate)
    except ContractError:
        return
    raise ContractError("selftest mutation was accepted")


def run_selftest(raw: dict[str, Any]) -> int:
    validate_contract(raw)
    mutations: list[Callable[[dict[str, Any]], None]] = [
        lambda c: c["scope"].__setitem__("mutation_model", "in-place"),
        lambda c: c["scope"].__setitem__("max_payload_bytes", 8193),
        lambda c: c["name_contract"].__setitem__("printable_byte_min", 32),
        lambda c: c["name_contract"].__setitem__("forbidden_bytes", [34, 42, 47, 58, 92]),
        lambda c: c["directory_contract"].__setitem__("scan", "first-sector-only"),
        lambda c: c["directory_contract"].__setitem__("growth", "allowed"),
        lambda c: c["allocation_contract"].__setitem__("new_chain_single_bam_half", False),
        lambda c: c["transaction_contract"]["ordered_steps"].reverse(),
        lambda c: c["transaction_contract"].__setitem__("old_chain_untouched_before_commit", False),
        lambda c: c["fault_contract"].__setitem__("command_guard", "header-check-only"),
        lambda c: c["fault_contract"].__setitem__("freezer_atomicity", "guaranteed"),
        lambda c: c["fault_contract"].__setitem__("residual_window_policy", "safe"),
        lambda c: c["fault_contract"].__setitem__("residual_damage_bound", "none"),
        lambda c: c["fault_contract"].__setitem__("power_loss", "guaranteed"),
        lambda c: c["fault_contract"].__setitem__("rollback", "best-effort"),
        lambda c: c["write_latch"].__setitem__("mutation_while_latched", "allowed"),
        lambda c: c["write_latch"].__setitem__("remount_validation", "bam-headers-only"),
        lambda c: c["write_latch"].__setitem__("automatic_retry", "always"),
        lambda c: c["media_policy"].__setitem__("writable_media", "L65WORK-only"),
        lambda c: c["media_policy"]["product_boot_signature"].__setitem__("ascii", "L65X"),
        lambda c: c["media_policy"].__setitem__("midtransaction_identity_change", "automatic-retry"),
        lambda c: c["status_contract"]["codes"][7].__setitem__("code", 17),
        lambda c: c["status_contract"]["codes"].pop(9),
        lambda c: c.__setitem__("unknown", True),
    ]
    for mutate in mutations:
        _expect_rejected(raw, mutate)

    with tempfile.TemporaryDirectory(prefix="lisp65-persistence-contract-") as tmp:
        duplicate_path = Path(tmp) / "duplicate.json"
        duplicate_path.write_text('{"format":"a","format":"b"}', encoding="utf-8")
        try:
            load_json(duplicate_path)
        except ContractError:
            pass
        else:
            raise ContractError("selftest accepted duplicate JSON keys")

    cases = 1 + len(mutations) + 1
    print(f"persistence-contract: PASS selftest cases={cases}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        raw = load_json(args.contract)
        if args.selftest:
            return run_selftest(raw)
        validate_contract(raw)
        print(
            "persistence-contract: PASS format=%s max_payload=%d statuses=%d"
            % (
                raw["format"],
                raw["scope"]["max_payload_bytes"],
                len(raw["status_contract"]["codes"]),
            )
        )
        return 0
    except ContractError as exc:
        print(f"persistence-contract: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
