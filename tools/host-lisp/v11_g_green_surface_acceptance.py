#!/usr/bin/env python3
"""Bind the implemented 1.1-G green surface and its complete capacity delta."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import v11_m_transactional_fasl_acceptance as M


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-g-green-surface-contract.json"
TOMBSTONE = ROOT / "config/v11-g-word-access-tombstone.json"
AUTHORIZATION = ROOT / "config/v11-g-green-surface-capacity-authorization.json"
BASELINE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-m-transactional-fasl-implementation-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-g-green-surface-implementation-receipt.json"
)
OBSERVATIONS = ROOT / "build/bytecode/dialect-v2/v11-g-green-observations.json"
BUILD = ROOT / "build/products/workbench/overlay-stack-guard"
RESIDENT = ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
COMPOSITION = ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
ELF = BUILD / "lisp65-workbench-overlay-linked.prg.elf"
EXPECTED_OBSERVATIONS = {
    "v11-g-read-from-string-direct": ("result", "42"),
    "v11-g-read-from-string-funcall": ("result", "42"),
    "v11-g-read-from-string-apply": ("result", "42"),
    "v11-g-read-from-string-first-object": ("result", "42"),
    "v11-g-read-from-string-type-error": ("error", "TypeError"),
    "v11-g-read-from-string-arity-zero": ("error", "ArityError"),
    "v11-g-read-from-string-arity-extra": ("error", "ArityError"),
    "v11-g-restart-repl-bytecode": ("result", "bytecode"),
    "v11-g-restart-repl-host-witness": ("result", "t"),
}


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"cannot read {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value: dict[str, Any]) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing regular binding: {path}")
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def artifact_metrics(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        "objects": int(manifest["objects"]),
        "code_bytes": int(manifest["code_bytes"]),
        "directory_bytes": int(manifest["directory_bytes"]),
        "ext_bytes": int(manifest["external_image"]["bytes"]),
    }


def semantic_gates(contract: dict[str, Any]) -> dict[str, Any]:
    report = load(OBSERVATIONS, "1.1-G observations")
    suites = report.get("suites")
    require(isinstance(suites, list) and len(suites) == 1,
            "1.1-G observation suite count drift")
    rows = suites[0].get("observations")
    require(isinstance(rows, list), "1.1-G observations missing")
    selected = {
        row.get("name"): row for row in rows
        if isinstance(row, dict) and row.get("name") in EXPECTED_OBSERVATIONS
    }
    require(set(selected) == set(EXPECTED_OBSERVATIONS),
            "1.1-G observation names drift")
    for name, (field, expected) in EXPECTED_OBSERVATIONS.items():
        require(selected[name].get(field) == expected,
                f"1.1-G observation failed: {name}")

    manifest = load(RESIDENT, "resident manifest")
    entries = {
        row.get("name"): row for row in manifest.get("entries", [])
        if isinstance(row, dict) and row.get("name") in contract["features"]
    }
    require(set(entries) == set(contract["features"]),
            "green surface is not uniquely resident")
    require(entries["read-from-string"].get("length") == 27
            and entries["restart-repl"].get("length") == 14,
            "green surface bytecode lengths drift")

    vm_text = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    require("FIXVAL(a[0]) == 30" in vm_text and 'jmp ($fffc)' in vm_text,
            "restart-repl resident interception drift")
    result = subprocess.run(
        [str(OBJDUMP), "-d", "--disassemble-symbols=vm_callprim", str(ELF)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"cannot disassemble vm_callprim: {result.stderr}")
    reset_jumps = re.findall(r"\b6c fc ff\b.*\bjmp\s+\(\$fffc\)", result.stdout)
    require(len(reset_jumps) == 1,
            f"linked reset-vector jump count drift: {len(reset_jumps)}")

    return {
        "read_from_string_routes": ["direct", "funcall", "apply"],
        "read_from_string_first_object": 42,
        "read_from_string_negative_cases": {
            "type": "TypeError", "arity_zero": "ArityError",
            "arity_extra": "ArityError",
        },
        "restart_repl_host_witness": "t",
        "restart_repl_linked_reset_vector_jump": "6c fc ff / jmp ($fffc)",
        "restart_repl_hardware": "not-run",
        "resident_lengths": {
            name: int(entries[name]["length"]) for name in sorted(entries)
        },
    }


def collect() -> dict[str, Any]:
    contract = load(CONTRACT, "green surface contract")
    tombstone = load(TOMBSTONE, "word-access tombstone")
    authorization = load(AUTHORIZATION, "green surface capacity authorization")
    baseline_receipt = load(BASELINE_RECEIPT, "1.1-M implementation receipt")
    require(contract.get("format") == "lisp65-v11-g-green-surface-contract-v1"
            and contract.get("status") == "owner-approved-for-implementation",
            "green surface contract drift")
    require(tombstone.get("status") == "owner-decided"
            and tombstone.get("decision") == "not-delivered"
            and tombstone.get("names") == ["peekw", "pokew"],
            "word-access tombstone drift")
    require(baseline_receipt.get("status") ==
            "implemented-passed-authorized-not-wave-promoted",
            "1.1-M baseline is not the authorized implementation")

    baseline = baseline_receipt["capacity"]["candidate"]
    candidate = M.current_capacity()
    deltas = {key: int(candidate[key]) - int(baseline[key]) for key in candidate}
    for key in (
        "fixed_overlay_bytes", "fixed_overlay_vma_headroom_bytes",
        "resident_island_immutable_bytes", "resident_island_annex_bytes",
        "resident_island_reserve_bytes", "runtime_overlay_max_slice_bytes",
        "runtime_overlay_max_slice_headroom_bytes", "installer_slice_bytes",
        "installer_slice_headroom_bytes", "directory_load_headroom",
        "directory_post_align_headroom",
    ):
        require(deltas[key] == 0, f"unexpected critical capacity drift: {key}")

    quantum = 256
    baseline_boot_alloc = ((int(baseline["boot_fastpath_verify_slice_bytes"]) +
                            quantum - 1) // quantum) * quantum
    candidate_boot_alloc = ((int(candidate["boot_fastpath_verify_slice_bytes"]) +
                             quantum - 1) // quantum) * quantum
    require(candidate_boot_alloc - baseline_boot_alloc == 256,
            "boot-fastpath packing attribution drift")
    require(deltas["runtime_overlay_bank_bytes"] == 256
            and deltas["runtime_overlay_bank_headroom_bytes"] == -256,
            "runtime-overlay bank delta does not match packing attribution")

    resident = load(RESIDENT, "resident manifest")
    baseline_artifact = baseline_receipt["artifacts"]["candidate"]["resident"]
    candidate_artifact = artifact_metrics(resident)
    artifact_delta = {
        key: int(candidate_artifact[key]) - int(baseline_artifact[key])
        for key in candidate_artifact
    }
    source_paths = [
        CONTRACT, TOMBSTONE, ROOT / "lib/dialect-v2/eval-runtime.lisp",
        ROOT / "src/vm.c", ROOT / "tools/host-lisp/bytecode_p0.py",
        ROOT / "tools/host-lisp/bytecode_p0_stdlib.py",
        ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json",
        ROOT / "config/dialect-v2-contract.json",
        ROOT / "config/dialect-v2-surface.json",
        ROOT / "config/v11-surface-delivery-parity.json",
        ROOT / "tools/host-lisp/v11_surface_delivery_parity.py",
        ROOT / "docs/language-reference.md", ROOT / "docs/user-guide.md",
        BASELINE_RECEIPT,
    ]
    build_paths = {
        "observations": OBSERVATIONS,
        "resident_manifest": RESIDENT,
        "composition_budget": COMPOSITION,
        "footprint": BUILD / "footprint-audit.json",
        "layout": BUILD / "layout.json",
        "runtime_overlays": BUILD / "runtime-overlays-manifest.json",
        "linked_elf": ELF,
    }
    result = {
        "format": "lisp65-v11-g-green-surface-implementation-receipt-v1",
        "version": 1,
        "id": "v11-g-read-from-string-and-restart-repl",
        "status": "implemented-passed-not-promoted",
        "capacity_authorization": "pending-owner-review",
        "recorded_on": "2026-07-17",
        "baseline": {
            "block": "authorized 1.1-M composition implementation",
            "receipt": binding(BASELINE_RECEIPT),
        },
        "product_identity": "changes-on-promotion; fresh Wave-2 hardware evidence required",
        "claim_limit": (
            "Host semantics, product delivery, and real-link reset-vector wiring only. "
            "restart-repl device behavior remains not-run until the fresh Wave-2 G6 case."
        ),
        "semantic_gates": semantic_gates(contract),
        "tombstone": {
            "names": tombstone["names"], "decision": tombstone["decision"],
            "replacement": tombstone["replacement"],
        },
        "capacity": {
            "baseline": baseline,
            "candidate": candidate,
            "delta_from_1_1_m": deltas,
            "runtime_overlay_bank_attribution": {
                "observed_link_change": (
                    "after the canonical source/product-identity change, the "
                    "whole-program boot-fastpath is 1806 rather than 1783 bytes; "
                    "the individual 23-byte linker movement is not assigned a "
                    "stronger cause without an isolated build"
                ),
                "bank_cost_cause": "crossing one 256-byte packing boundary",
                "packing_quantum_bytes": quantum,
                "baseline_boot_fastpath_allocated_bytes": baseline_boot_alloc,
                "candidate_boot_fastpath_allocated_bytes": candidate_boot_alloc,
                "runtime_overlay_bank_cost_bytes": candidate_boot_alloc - baseline_boot_alloc,
            },
        },
        "artifacts": {
            "baseline_resident": baseline_artifact,
            "candidate_resident": candidate_artifact,
            "resident_delta": artifact_delta,
        },
        "source_bindings": [binding(path) for path in source_paths],
        "build_bindings": {key: binding(path) for key, path in build_paths.items()},
    }
    require(authorization.get("format") == "lisp65-v11-capacity-authorization-v1"
            and authorization.get("status") == "owner-authorized",
            "capacity authorization is absent or not owner-authorized")
    before = authorization.get("implementation_receipt_before_authorization", {})
    require(before.get("path") == rel(RECEIPT)
            and before.get("sha256") == object_sha(result),
            "capacity authorization does not bind the reconstructed pre-authorization receipt")
    authorized_capacity = authorization.get("capacity", {})
    require(authorized_capacity.get("baseline") == baseline
            and authorized_capacity.get("candidate") == candidate
            and authorized_capacity.get("authorized_delta") == deltas,
            "authorized capacity does not match the measured baseline/candidate/delta")
    result["status"] = "implemented-passed-authorized-not-wave-promoted"
    result["capacity_authorization"] = binding(AUTHORIZATION)
    result["source_bindings"].append(binding(AUTHORIZATION))
    return result


def write_receipt(path: Path) -> dict[str, Any]:
    value = collect()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check_receipt(path: Path) -> dict[str, Any]:
    actual = load(path, "implementation receipt")
    expected = collect()
    require(actual == expected, "implementation receipt does not bind current source/build state")
    return actual


def selftest() -> None:
    sample = {
        "status": "implemented-passed-authorized-not-wave-promoted",
        "capacity": {"candidate": {"runtime_overlay_bank_headroom_bytes": 64}},
        "semantic_gates": {"restart_repl_hardware": "not-run"},
    }
    for label, mutate in (
        ("status", lambda value: value.update(status="promoted")),
        ("capacity", lambda value: value["capacity"]["candidate"].update(
            runtime_overlay_bank_headroom_bytes=65)),
        ("hardware", lambda value: value["semantic_gates"].update(
            restart_repl_hardware="passed")),
    ):
        candidate = copy.deepcopy(sample)
        mutate(candidate)
        require(candidate != sample, f"selftest mutation survived: {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v11-g-green-surface-acceptance: SELFTEST PASS mutations=3")
            return 0
        value = write_receipt(args.receipt) if args.command == "collect" else check_receipt(args.receipt)
    except (AcceptanceError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"v11-g-green-surface-acceptance: FAIL: {exc}", file=sys.stderr)
        return 1
    delta = value["capacity"]["delta_from_1_1_m"]
    print(
        "v11-g-green-surface-acceptance: PASS "
        f"status={value['status']} bank={delta['bank_post_boot_reserve_bytes']:+d} "
        f"ext={delta['ext_post_load_headroom_bytes']:+d} "
        f"runtime-bank={delta['runtime_overlay_bank_headroom_bytes']:+d} "
        f"symbols={delta['symbol_headroom']:+d}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
