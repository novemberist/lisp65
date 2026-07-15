#!/usr/bin/env python3
"""Emit SHA-bound receipts for completed capability/carrier checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

import v2_capability_carrier_contract as Contract
import v2_cp5_g5_archive as CP5Archive


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/v2-capability-carrier-block.json"
CP4_DIFFERENTIAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-artifact-differential-receipt.json"
)
CP4_CODE59 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "invalid-parameter-list-verdict.json"
)
CP4_CARRIER = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "carrier-cut-verdict.json"
)
CP4_INVENTORY = ROOT / "build/bytecode/dialect-v2/workbench-service-call-inventory.json"
CP4_NATIVE_MATRIX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "native-function-route-matrix.json"
)
CP4_COMPOSITION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-library-composition-capacity-receipt.json"
)
CP5_ARCHIVE_MANIFEST = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "cp5-g5-67400c05/manifest.json"
)
CP5_LINK_REPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "string-caps-cp5-product-link-report.json"
)


class ReceiptError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptError(f"{label} must contain an object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _old_metrics(contract: dict[str, object], number: int) -> dict[str, object]:
    if number == 3:
        return {
            "active_prim_ids": [23, 24, 25, 28, 29],
            "lists_cases": 35,
            "strings_cases": 36,
            "strings_observations": 288,
            "native_treewalk_carrier_blockers": 15,
            "lcc_carrier_blockers": 2,
            "runtime_treewalk_hooks_null": True,
            "codec_atomic": True,
            "v1_active_prim_ids": 23,
        }
    checkpoint = contract["checkpoints"][number - 1]
    binding = checkpoint.get("receipt")
    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str):
        raise ReceiptError(f"checkpoint {number} has no prior receipt metrics")
    receipt = _load(ROOT / binding["path"], f"checkpoint {number} receipt")
    metrics = receipt.get("metrics")
    if not isinstance(metrics, dict):
        raise ReceiptError(f"checkpoint {number} prior metrics are invalid")
    return metrics


def _cp4_metrics() -> dict[str, object]:
    differential = _load(CP4_DIFFERENTIAL, "v2 artifact differential")
    diff_summary = differential.get("summary")
    if (
        differential.get("status") != "passed"
        or not isinstance(diff_summary, dict)
        or diff_summary != {
            "artifacts": 4, "cases": 335, "observation_differences": 0,
        }
    ):
        raise ReceiptError("v2 artifact differential is not the pinned 335/335 pass")

    inventory = _load(CP4_INVENTORY, "v2 service inventory")
    summary = inventory.get("summary")
    expected_classes = {"callprim": 3, "native-service": 14, "error-service": 11}
    if (
        inventory.get("mode") != "staging"
        or inventory.get("runtime_function_pointer_registry") is not False
        or not isinstance(summary, dict)
        or summary.get("classified_targets") != expected_classes
        or summary.get("unresolved_calls") != 0
        or summary.get("unresolved_targets") != 0
        or summary.get("tombstone_callprim_calls") != 0
        or summary.get("zero_miss_ready") is not True
    ):
        raise ReceiptError("v2 service inventory is not the pinned zero-miss closure")

    code59 = _load(CP4_CODE59, "Code59 differential")
    engines = code59.get("full_invalid_parameter_path_engines")
    expected_engines = [
        "native-c-treewalk", "native-c-compiler-vm",
        "python-p0-compiler-vm", "lisp-lcc",
    ]
    if (
        code59.get("verdict") != "pass"
        or code59.get("evidence_gap") is not None
        or engines != expected_engines
        or any(
            not isinstance(record, dict)
            or record.get("observation")
            != "!error:code=59:symbol=%lcc-error-invalid-parameter-list"
            for record in code59.get("engines", {}).values()
        )
        or len(code59.get("engines", {})) != 4
    ):
        raise ReceiptError("Code59 differential lacks four complete engine paths")

    carrier = _load(CP4_CARRIER, "carrier-cut verdict")
    if (
        carrier.get("format") != "lisp65-v2-carrier-cut-verdict-v1"
        or carrier.get("state") != "removed"
        or carrier.get("forbidden_definitions") != []
        or carrier.get("required_definitions") != ["vm_native_apply", "vm_run"]
    ):
        raise ReceiptError("carrier-cut ELF verdict is incomplete")

    native_matrix = _load(CP4_NATIVE_MATRIX, "native function route matrix")
    if (
        native_matrix.get("status") != "passed"
        or native_matrix.get("registry_entries") != 15
        or native_matrix.get("routes") != ["direct", "funcall", "apply"]
        or native_matrix.get("evaluations") != 180
        or native_matrix.get("parity") != {
            "registry_entries": 15,
            "generated_dispatch_entries": 15,
            "generated_cases": 45,
            "status": "passed",
        }
        or len(native_matrix.get("engines", [])) != 4
        or any(row.get("status") != "passed" or row.get("cases") != 45
               for row in native_matrix.get("engines", []))
    ):
        raise ReceiptError("native function matrix lacks generated 15x3x4 closure")

    composition = _load(CP4_COMPOSITION, "Workbench composition capacity")
    composition_result = composition.get("permanent_manifest_gate", {}).get("result")
    privacy = composition.get("privacy_first_probe")
    if (
        composition.get("status") != "pass-host-and-link-g5-pending"
        or not isinstance(composition_result, dict)
        or not isinstance(privacy, dict)
    ):
        raise ReceiptError("Workbench composition capacity evidence is invalid")

    return {
        "artifact_cases": 335,
        "artifact_observation_differences": 0,
        "callprim_calls": summary.get("callprim_calls"),
        "carrier_forbidden_definitions": 0,
        "classified_service_targets": 28,
        "code59_full_path_engines": 4,
        "directory_calls": summary.get("directory_calls"),
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
        "composition_directory_used": composition_result["directory_entries"],
        "composition_directory_post_align_headroom": composition_result[
            "directory_post_align_headroom"
        ],
        "composition_symbols": composition_result["symbols"],
        "composition_symbol_headroom": composition_result["symbol_headroom"],
        "composition_namepool_bytes": composition_result["namepool_bytes"],
        "composition_namepool_headroom_bytes": composition_result[
            "namepool_headroom_bytes"
        ],
        "additional_private_symbols": privacy["additional_private_symbols"],
        "runtime_function_pointer_registry": False,
        "tombstone_callprim_calls": 0,
        "unresolved_calls": 0,
        "unresolved_targets": 0,
    }


def _cp5_metrics() -> dict[str, object]:
    CP5Archive.verify(CP5_ARCHIVE_MANIFEST)
    archive_manifest = _load(CP5_ARCHIVE_MANIFEST, "CP5/G5 archive manifest")
    archive_path = ROOT / archive_manifest["archive"]["path"]
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.extractfile(
            "build/cp5-g5-v2-bound/runtime-package/proof-manifest.json"
        )
        if member is None:
            raise ReceiptError("CP5 archive lacks the Runtime proof manifest")
        runtime = json.loads(member.read().decode("utf-8"))
        member = archive.extractfile("build/cp5-g5-v2-bound/receipts/g5.json")
        if member is None:
            raise ReceiptError("CP5 archive lacks the top G5 receipt")
        g5 = json.loads(member.read().decode("utf-8"))
    report = _load(CP5_LINK_REPORT, "CP5 product-link report")
    measurement = report.get("measurement")
    runtime_metrics = runtime.get("metrics")
    if not isinstance(measurement, dict) or not isinstance(runtime_metrics, dict):
        raise ReceiptError("CP5 archived metrics are invalid")
    if g5.get("result") != "passed":
        raise ReceiptError("CP5 archive lacks a passing G5 result")
    return {
        "workbench_runtime_overlay_vma": measurement["runtime_overlay_vma"],
        "workbench_post_boot_reserve_bytes": measurement["post_boot_reserve_bytes"],
        "runtime_core_post_boot_reserve_bytes": runtime_metrics["post_boot_reserve_bytes"],
        "deployed_bank0_net_delta_bytes": measurement[
            "deployed_bank0_delta_vs_accepted_v2_fasl_baseline_bytes"
        ],
        "g5_result": g5["result"],
        "layout_change": measurement["layout_change"],
        "slot_delta": measurement["slot_delta"],
        "island_bytes_delta": measurement["island_bytes_delta"],
    }


def emit(contract_path: Path, number: int, output: Path) -> None:
    if not contract_path.is_absolute():
        contract_path = ROOT / contract_path
    if not output.is_absolute():
        output = ROOT / output
    contract = _load(contract_path, "capability/carrier contract")
    Contract.validate(contract, verify_bindings=False)
    checkpoint = contract["checkpoints"][number - 1]
    evidence_paths = sorted(Contract.REQUIRED_RECEIPT_EVIDENCE[number])
    for relative in evidence_paths:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise ReceiptError(f"missing receipt evidence: {relative}")
    if number == 5:
        metrics = _cp5_metrics()
    elif number == 4:
        metrics = _cp4_metrics()
    else:
        metrics = _old_metrics(contract, number)
    receipt = {
        "format": "lisp65-v2-capability-carrier-checkpoint-receipt-v1",
        "block_id": contract["id"],
        "checkpoint": number,
        "checkpoint_id": checkpoint["id"],
        "gate": checkpoint["make_target"],
        "contract_policy_sha256": Contract._policy_sha(contract),
        "result": "passed",
        "assertions": checkpoint["acceptance"],
        "evidence": [
            {"path": relative, "sha256": _sha(ROOT / relative)}
            for relative in evidence_paths
        ],
        "metrics": metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        f"v2-capability-carrier-receipt: WROTE checkpoint={number} "
        f"evidence={len(evidence_paths)} output={output.relative_to(ROOT)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--number", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        emit(args.contract, args.number, args.output)
        return 0
    except (ReceiptError, Contract.ContractError, KeyError, TypeError, ValueError) as exc:
        print(f"v2-capability-carrier-receipt: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
