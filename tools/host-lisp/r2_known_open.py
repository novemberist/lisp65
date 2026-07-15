#!/usr/bin/env python3
"""Validate the R2 product-link known opens and Directory-only draft."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable

import block_bank_delta_policy as BANK_DELTA


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "config/r2-known-open.json"
DEFAULT_DRAFT = ROOT / "config/directory-only-l65m-v2-contract-draft.json"


class ContractError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"{label} must be a regular file")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} must contain an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ContractError(f"{label} keys drift: {actual}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strings(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list) or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise ContractError(f"{label} must be a non-empty unique string list")
    return value


def commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ContractError(f"{label} is not a full commit id")
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ContractError(f"{label} does not exist")
    return value


def validate_evidence(value: dict[str, Any]) -> None:
    exact(
        value,
        {"format", "id", "status", "observed_on", "toolchain_sha256", "default_target", "bound_v2_target", "conclusion"},
        "diagnosis",
    )
    if (
        value["format"] != "lisp65-r2-stack-guard-diagnosis-v1"
        or value["id"] != "r2-stack-guard-baseline"
        or value["status"] != "diagnosed-open"
        or value["observed_on"] != "2026-07-13"
        or value["toolchain_sha256"] != "2a831e2abeabb9c6e0605a197ff39903c1326b528f82a7f787bc353ef652309c"
    ):
        raise ContractError("diagnosis identity/toolchain drift")
    default = exact(
        value["default_target"],
        {"command", "profile", "baseline_commit", "current_commit", "result", "errors", "metrics", "diagnosis"},
        "default_target",
    )
    commit(default["baseline_commit"], "default baseline")
    commit(default["current_commit"], "default current")
    if (
        default["command"] != "make workbench-overlay-stack-guard"
        or default["profile"] != "mvp-vm-stdlib-einsuite-core-workbench"
        or default["result"] != "failed-identically"
        or len(strings(default["errors"], "default errors")) != 4
        or "pre-v2" not in default["diagnosis"]
    ):
        raise ContractError("default target diagnosis drift")
    metrics = exact(
        default["metrics"],
        {"runtime_overlay_vma", "runtime_overlay_vma_limit", "vma_deficit_bytes", "transport_deficit_bytes", "l65m_16_deficit_bytes", "l65c_03_deficit_bytes"},
        "default metrics",
    )
    if metrics != {
        "runtime_overlay_vma": "0xc3a6", "runtime_overlay_vma_limit": "0xc356",
        "vma_deficit_bytes": 80, "transport_deficit_bytes": 80,
        "l65m_16_deficit_bytes": 17, "l65c_03_deficit_bytes": 36,
    }:
        raise ContractError("default target metrics drift")

    bound = exact(
        value["bound_v2_target"],
        {"command", "profile", "baseline", "current", "delta", "attribution"},
        "bound_v2_target",
    )
    if (
        bound["command"] != "make v2-capability-carrier-internal-g5-workbench-link"
        or bound["profile"] != "dialect-v2-capability-carrier-workbench-staging"
    ):
        raise ContractError("bound v2 target identity drift")
    state_keys = {"commit", "result", "runtime_overlay_vma", "post_boot_reserve_bytes", "banked_headroom_bytes", "boot_stack_gap_bytes"}
    baseline = exact(bound["baseline"], state_keys, "bound baseline")
    current = exact(bound["current"], state_keys, "bound current")
    commit(baseline["commit"], "bound baseline commit")
    commit(current["commit"], "bound current commit")
    if baseline["result"] != "passed" or current["result"] != "passed":
        raise ContractError("bound v2 target must pass in both states")
    delta = exact(
        bound["delta"],
        {"runtime_overlay_vma_bytes", "post_boot_reserve_bytes", "banked_headroom_bytes", "boot_stack_gap_bytes", "resident_text_bytes", "resident_rodata_bytes", "boot_overlay_bytes"},
        "bound delta",
    )
    if (
        int(current["runtime_overlay_vma"], 0) - int(baseline["runtime_overlay_vma"], 0) != delta["runtime_overlay_vma_bytes"]
        or current["post_boot_reserve_bytes"] - baseline["post_boot_reserve_bytes"] != delta["post_boot_reserve_bytes"]
        or current["banked_headroom_bytes"] - baseline["banked_headroom_bytes"] != delta["banked_headroom_bytes"]
        or current["boot_stack_gap_bytes"] - baseline["boot_stack_gap_bytes"] != delta["boot_stack_gap_bytes"]
        or delta["resident_text_bytes"] + delta["resident_rodata_bytes"] != delta["runtime_overlay_vma_bytes"]
        or delta["runtime_overlay_vma_bytes"] + delta["boot_overlay_bytes"] != -delta["boot_stack_gap_bytes"]
    ):
        raise ContractError("bound v2 target delta arithmetic drift")
    attribution = exact(
        bound["attribution"],
        {"vm_callprim_text_bytes", "eval_init_overlay_bytes", "new_boot_name_helpers_bytes", "apply_dispatch_rodata_bytes", "classification"},
        "bound attribution",
    )
    if attribution["classification"] != "system-runtime-candidate-product-cost-not-measured-before-promotion":
        raise ContractError("bank delta classification drift")
    conclusion = exact(
        value["conclusion"],
        {"system_runtime_default_target_delta_bytes", "default_target_owner_class", "bank_delta_owner_class", "directory_only_probe_baseline", "bank_555_claim"},
        "conclusion",
    )
    if conclusion["system_runtime_default_target_delta_bytes"] != 0 or conclusion["bank_555_claim"] != "withdrawn-pending-explicit-resolution":
        raise ContractError("diagnosis conclusion drift")


def validate_stack_resolution(value: dict[str, Any]) -> None:
    exact(
        value,
        {"format", "id", "status", "resolved_on", "source_commit", "targets", "bank_delta", "conclusion"},
        "stack-guard resolution",
    )
    if (
        value["format"] != "lisp65-r2-canonical-stack-guard-resolution-v1"
        or value["id"] != "r2-canonical-stack-guard-profile-binding"
        or value["status"] != "resolved"
        or value["resolved_on"] != "2026-07-13"
    ):
        raise ContractError("stack-guard resolution identity drift")
    source_commit = commit(value["source_commit"], "stack-guard resolution source commit")
    for path, required in (
        ("Makefile", "V2_CAPABILITY_CARRIER_G5_WORKBENCH_DIR := build/products/workbench/overlay-stack-guard"),
        ("mk/workbench.mk", "workbench-overlay-stack-guard: v2-workbench-artifacts"),
    ):
        result = subprocess.run(
            ["git", "show", f"{source_commit}:{path}"], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode or required not in result.stdout:
            raise ContractError(f"stack-guard source binding drift: {path}")
    targets = value["targets"]
    commands = [
        "make workbench-overlay-stack-guard",
        "make v2-capability-carrier-internal-g5-workbench-link",
    ]
    if not isinstance(targets, list) or len(targets) != 2:
        raise ContractError("stack-guard target inventory drift")
    normalized = []
    for index, target in enumerate(targets):
        exact(
            target,
            {"command", "artifact_root", "profile", "result", "resolved_profile_sha256", "artifact_set_sha256", "artifacts", "metrics"},
            f"stack-guard target[{index}]",
        )
        if (
            target["command"] != commands[index]
            or target["artifact_root"] != "build/products/workbench/overlay-stack-guard"
            or target["profile"] != "dialect-v2-capability-carrier-workbench-staging"
            or target["result"] != "passed"
        ):
            raise ContractError("stack-guard target binding drift")
        artifacts = target["artifacts"]
        ids = ["product-elf", "resident-prg", "runtime-overlays", "stdlib-preload"]
        if not isinstance(artifacts, list) or [item.get("id") for item in artifacts] != ids:
            raise ContractError("stack-guard artifact inventory drift")
        lines = []
        for artifact_index, artifact in enumerate(artifacts):
            exact(artifact, {"id", "sha256"}, f"stack artifact[{artifact_index}]")
            if len(artifact["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in artifact["sha256"]):
                raise ContractError("stack-guard artifact SHA drift")
            lines.append(f"{artifact['id']}:{artifact['sha256']}\n")
        aggregate = hashlib.sha256("".join(lines).encode("ascii")).hexdigest()
        metrics = exact(target["metrics"], {"runtime_overlay_vma", "post_boot_reserve_bytes", "banked_headroom_bytes", "boot_stack_gap_bytes"}, f"stack metrics[{index}]")
        if (
            aggregate != target["artifact_set_sha256"]
            or metrics != {
                "runtime_overlay_vma": "0xc2a4", "post_boot_reserve_bytes": 1971,
                "banked_headroom_bytes": 435, "boot_stack_gap_bytes": 1751,
            }
        ):
            raise ContractError("stack-guard artifact aggregate/metrics drift")
        normalized.append({key: target[key] for key in target if key != "command"})
    if normalized[0] != normalized[1]:
        raise ContractError("default/bound stack-guard artifact identity drift")
    try:
        BANK_DELTA.validate_bank_delta(value["bank_delta"])
    except BANK_DELTA.BankDeltaError as exc:
        raise ContractError(f"stack-guard bank delta drift: {exc}") from exc
    if value["conclusion"] != {
        "artifact_identity": "exact",
        "canonical_profile_binding": "closed",
        "r4_deadline": "met-before-r4-sealing",
    }:
        raise ContractError("stack-guard conclusion drift")


def validate_registry(value: dict[str, Any], evidence_path: Path) -> None:
    exact(value, {"format", "version", "status", "evidence", "resolutions", "issues"}, "registry")
    if value["format"] != "lisp65-r2-known-open-v1" or value["version"] != 1 or value["status"] != "resolved":
        raise ContractError("registry identity drift")
    binding = exact(value["evidence"], {"path", "sha256"}, "evidence binding")
    if binding["path"] != evidence_path.relative_to(ROOT).as_posix() or binding["sha256"] != sha(evidence_path):
        raise ContractError("diagnosis evidence binding drift")
    resolutions = value["resolutions"]
    if not isinstance(resolutions, list) or len(resolutions) != 2:
        raise ContractError("known-open resolution inventory drift")
    resolution = exact(
        resolutions[0],
        {"id", "status", "authorization", "accepted_bank_bytes", "precedent"},
        "resolution[0]",
    )
    authorization = exact(resolution["authorization"], {"path", "sha256"}, "resolution authorization")
    try:
        BANK_DELTA.validate_authorization(authorization, expected_debit=120, prospective=False)
    except BANK_DELTA.BankDeltaError as exc:
        raise ContractError(f"bank resolution authorization drift: {exc}") from exc
    if resolution != {
        "id": "r2-banked-headroom-drift",
        "status": "resolved-authorized",
        "authorization": authorization,
        "accepted_bank_bytes": 435,
        "precedent": "none",
    }:
        raise ContractError("bank resolution decision drift")
    stack_resolution = exact(
        resolutions[1],
        {"id", "status", "receipt", "accepted_bank_bytes", "deadline"},
        "resolution[1]",
    )
    receipt_binding = exact(stack_resolution["receipt"], {"path", "sha256"}, "stack resolution receipt")
    receipt_path = ROOT / receipt_binding["path"]
    if receipt_binding["sha256"] != sha(receipt_path):
        raise ContractError("stack resolution receipt SHA drift")
    validate_stack_resolution(load(receipt_path, "stack-guard resolution receipt"))
    if stack_resolution != {
        "id": "r2-canonical-stack-guard-profile-binding",
        "status": "resolved-exact-artifact-identity",
        "receipt": receipt_binding,
        "accepted_bank_bytes": 435,
        "deadline": "met-before-r4-sealing",
    }:
        raise ContractError("stack resolution registry drift")
    issues = value["issues"]
    if issues != []:
        raise ContractError("known-open issue inventory/order drift")


def validate_draft(value: dict[str, Any]) -> None:
    exact(
        value,
        {"format", "version", "id", "status", "prerequisites", "scope", "format_contract", "validator_contract", "diagnostics_contract", "measurement_contract", "promotion_gate"},
        "directory-only draft",
    )
    if (
        value["format"] != "lisp65-directory-only-l65m-v2-contract-draft-v1"
        or value["version"] != 1 or value["id"] != "directory-only-l65m-v2"
        or value["status"] != "approved-for-implementation"
        or value["prerequisites"] != []
    ):
        raise ContractError("directory-only draft identity/prerequisite drift")
    scope = exact(value["scope"], {"includes", "excludes"}, "draft scope")
    strings(scope["includes"], "draft includes"); excludes = strings(scope["excludes"], "draft excludes")
    if "export-only interning for require" not in excludes or "library unload policy" not in excludes:
        raise ContractError("directory-only scope boundary drift")
    fmt = exact(value["format_contract"], {"magic", "new_version", "v1_decoder_in_v2_profile", "v2_decoder_in_v1_profile", "unknown_versions", "v1_reinterpretation", "anonymous_entry", "local_reference", "late_bound_export", "version_strictness"}, "format contract")
    if fmt["magic"] != "L65M" or fmt["new_version"] != 2 or fmt["v1_decoder_in_v2_profile"] != "required-unchanged" or fmt["v1_reinterpretation"] != "forbidden":
        raise ContractError("format compatibility/tombstone rule drift")
    anonymous = exact(fmt["anonymous_entry"], {"name_off", "legal_name_off_range", "sentinel_capacity_invariant", "identity", "macro_flag", "global_symbol_install", "directory_slot"}, "anonymous entry")
    local = exact(fmt["local_reference"], {"representation", "target", "commit_result", "vm_call_rule", "function_designator_rule", "cross_artifact_reference", "cross_container_call"}, "local reference")
    late = exact(fmt["late_bound_export"], {"purpose", "publication", "local_call_binding", "declaration", "parity_gates", "hook_audit", "current_hooks", "extension_rule"}, "late-bound export")
    strictness = exact(fmt["version_strictness"], {"v1_entry_with_anonymous_sentinel", "v1_emitter_output", "v2_emitter_output", "decoder_policy"}, "version strictness")
    if anonymous["name_off"] != "0xffff" or anonymous["legal_name_off_range"] != "0x0000-through-0xfffe-and-within-decoded-string-table" or "fail-before" not in anonymous["sentinel_capacity_invariant"] or anonymous["identity"] != "zero-based-entry-ordinal-within-artifact" or anonymous["global_symbol_install"] != "forbidden" or local["function_designator_rule"] != "entry-ref-materializes-BCODE-and-native-apply-funcall-accept-BCODE" or local["cross_artifact_reference"] != "forbidden" or local["cross_container_call"] != "named-export-reference-only" or strictness["v1_entry_with_anonymous_sentinel"] != "reject-with-L65M_ERR_ENTRIES" or strictness["v1_emitter_output"] != "version-1-only-never-v2" or strictness["decoder_policy"] != "version-bound-never-feature-sniffing":
        raise ContractError("anonymous entry/local reference rule drift")
    if (
        late["local_call_binding"]
        != "symbolic-only; entry-ref conversion is forbidden in providers and overriders"
        or late["current_hooks"] != ["%ide-x"]
        or late["parity_gates"] != [
            "exports-intersect-anonymous-is-empty",
            "override-exports-are-named-in-provider-and-overrider",
            "late-bound-exports-have-zero-entry-ref-edges",
        ]
        or "override_exports is a subset" not in late["declaration"]
        or "undeclared duplicate definitions fail" not in late["hook_audit"]
    ):
        raise ContractError("late-bound export contract drift")
    validators = exact(value["validator_contract"], {"named_entry_duplicates", "anonymous_entry_duplicates", "mixed_named_anonymous_entries", "entry_ref_range", "entry_ref_to_named_entry", "entry_ref_to_macro", "phase_05_rule", "anonymous_ordinal_validation", "host_device_parity", "transactionality"}, "validator contract")
    if "only-named-entries" not in validators["phase_05_rule"] or validators["anonymous_ordinal_validation"] != "phase-05-enumerates-every-entry-index-exactly-once-and-validates-every-entry-ref-against-entry-count" or validators["transactionality"] != "any-v2-validation-or-commit-error-publishes-no-directory-or-symbol-state":
        raise ContractError("phase-05/transactionality rule drift")
    diagnostics = exact(value["diagnostics_contract"], {"product_device_names_for_anonymous_entries", "stable_runtime_address", "host_manifest_map", "receipt_binding", "diagnostic_build", "support_rule", "runtime_message_format", "deferred_device_attribution"}, "diagnostics contract")
    if (
        diagnostics["stable_runtime_address"] != "artifact-sha256-plus-entry-ordinal-plus-code-object-offset"
        or diagnostics["product_device_names_for_anonymous_entries"] != "absent"
        or diagnostics["runtime_message_format"] != "entry #{zero-based-global-directory-index}"
        or diagnostics["support_rule"] != "product-diagnostic-build-reports-global-directory-index-resolved-by-product-receipt-and-sha-bound-host-map"
        or not diagnostics["deferred_device_attribution"].startswith("lib-{artifact-id}-entry-local-ordinal-is-1.1")
    ):
        raise ContractError("anonymous diagnostics rule drift")
    measurement = exact(value["measurement_contract"], {"baseline_artifacts", "provisional_census", "promotion_projection", "required_probe_outputs"}, "measurement contract")
    if measurement["baseline_artifacts"] != ["IDE", "IDEX"]:
        raise ContractError("measurement baseline drift")
    census = exact(measurement["provisional_census"], {"ide_percent_directory_entries", "idex_percent_directory_entries", "directory_only_candidates", "already_private_inline_helpers", "combined_private_helpers", "candidate_namepool_bytes"}, "provisional census")
    if census["ide_percent_directory_entries"] + census["idex_percent_directory_entries"] != census["directory_only_candidates"] or census["directory_only_candidates"] + census["already_private_inline_helpers"] != census["combined_private_helpers"]:
        raise ContractError("private helper census arithmetic drift")
    projection = exact(measurement["promotion_projection"], {"directory_only_entries", "additional_inline_entries", "gross_symbol_intern_savings", "gross_namepool_savings_bytes", "directory_entry_delta", "ide_family_net_projection_source"}, "promotion projection")
    if projection["directory_only_entries"] != census["directory_only_candidates"] or projection["gross_symbol_intern_savings"] != census["directory_only_candidates"] or projection["gross_namepool_savings_bytes"] != census["candidate_namepool_bytes"] or projection["directory_entry_delta"] != 0:
        raise ContractError("directory-only projection drift")
    if len(strings(measurement["required_probe_outputs"], "required probe outputs")) < 6:
        raise ContractError("directory-only probe output inventory is incomplete")
    gate = exact(value["promotion_gate"], {"required_profiles", "required_validators", "required_negative_classes", "hardware_effect", "promotion_requires_r2_known_open_count", "required_known_open_resolution", "bank_delta_receipt"}, "promotion gate")
    if len(strings(gate["required_profiles"], "required profiles")) != 3 or len(strings(gate["required_validators"], "required validators")) != 3 or len(strings(gate["required_negative_classes"], "required negative classes")) < 8 or gate["promotion_requires_r2_known_open_count"] != 0 or gate["required_known_open_resolution"] != ["r2-canonical-stack-guard-profile-binding"] or gate["bank_delta_receipt"] != "required-zero-or-preauthorized":
        raise ContractError("directory-only promotion gate drift")


def validate(registry_path: Path, draft_path: Path) -> None:
    registry = load(registry_path, "R2 known-open registry")
    binding = registry.get("evidence", {})
    relative = binding.get("path") if isinstance(binding, dict) else None
    if not isinstance(relative, str):
        raise ContractError("registry lacks evidence path")
    evidence_path = ROOT / relative
    evidence = load(evidence_path, "stack-guard diagnosis")
    validate_evidence(evidence)
    validate_registry(registry, evidence_path)
    validate_draft(load(draft_path, "Directory-only draft"))


def selftest(registry_path: Path, draft_path: Path) -> None:
    validate(registry_path, draft_path)
    registry = load(registry_path, "selftest registry")
    draft = load(draft_path, "selftest draft")
    mutations: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None]]] = [
        ("registry-status", lambda r, _d: r.update(status="active")),
        ("open-issue", lambda r, _d: r["issues"].append({"id": "stale"})),
        ("resolution", lambda r, _d: r["resolutions"][0].update(accepted_bank_bytes=555)),
        ("stack-resolution", lambda r, _d: r["resolutions"][1].update(accepted_bank_bytes=555)),
        ("stack-receipt-sha", lambda r, _d: r["resolutions"][1]["receipt"].update(sha256="0" * 64)),
        ("evidence-sha", lambda r, _d: r["evidence"].update(sha256="0" * 64)),
        ("v1-compat", lambda _r, d: d["format_contract"].update(v1_decoder_in_v2_profile="drop")),
        ("sentinel-range", lambda _r, d: d["format_contract"]["anonymous_entry"].update(legal_name_off_range="all-u16")),
        ("v1-sentinel", lambda _r, d: d["format_contract"]["version_strictness"].update(v1_entry_with_anonymous_sentinel="accept")),
        ("cross-container", lambda _r, d: d["format_contract"]["local_reference"].update(cross_container_call="ordinal")),
        ("designator-entry-ref", lambda _r, d: d["format_contract"]["local_reference"].update(function_designator_rule="symbols-only")),
        ("late-bound-entry-ref", lambda _r, d: d["format_contract"]["late_bound_export"].update(local_call_binding="entry-ref-allowed")),
        ("scope-growth", lambda _r, d: d["scope"]["excludes"].remove("export-only interning for require")),
        ("phase-05", lambda _r, d: d["validator_contract"].update(phase_05_rule="skip")),
        ("ordinal-validation", lambda _r, d: d["validator_contract"].update(anonymous_ordinal_validation="skip")),
        ("diagnostics", lambda _r, d: d["diagnostics_contract"].update(product_device_names_for_anonymous_entries="resident")),
        ("diagnostic-format", lambda _r, d: d["diagnostics_contract"].update(runtime_message_format="implementation-defined")),
        ("projection", lambda _r, d: d["measurement_contract"]["promotion_projection"].update(directory_only_entries=99)),
        ("known-open-gate", lambda _r, d: d["promotion_gate"].update(promotion_requires_r2_known_open_count=1)),
        ("bank-delta-gate", lambda _r, d: d["promotion_gate"].update(bank_delta_receipt="optional")),
    ]
    accepted = []
    with tempfile.TemporaryDirectory(prefix="r2-known-open-selftest-") as raw:
        root = Path(raw)
        for name, mutate in mutations:
            r = deepcopy(registry); d = deepcopy(draft); mutate(r, d)
            try:
                validate_registry(r, ROOT / registry["evidence"]["path"])
                validate_draft(d)
            except ContractError:
                continue
            accepted.append(name)
    if accepted:
        raise ContractError(f"selftest accepted mutations: {accepted}")
    print(f"r2-known-open: SELFTEST PASS mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "selftest"))
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest(args.registry, args.draft)
        else:
            validate(args.registry, args.draft)
            registry = load(args.registry, "R2 known-open registry")
            print(
                "r2-known-open: PASS "
                f"known_open={len(registry['issues'])} "
                "directory_only=implemented banked_headroom=269"
            )
        return 0
    except (ContractError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"r2-known-open: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
