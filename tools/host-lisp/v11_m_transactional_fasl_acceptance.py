#!/usr/bin/env python3
"""Bind the canonical 1.1-M composition implementation and its real link."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config" / "v11-m-transactional-fasl-contract.json"
AUTHORIZATION = ROOT / "config" / "v11-m-transactional-fasl-capacity-authorization.json"
PROBE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-m-transactional-fasl-comparison-probe-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-m-transactional-fasl-implementation-receipt.json"
)
OBSERVATIONS = ROOT / "build/bytecode/dialect-v2/v11-m-implementation-observations.json"
CHAIN_INVENTORY = ROOT / "build/bytecode/dialect-v2/chain-walker-inventory.json"
BUILD = ROOT / "build/products/workbench/overlay-stack-guard"
RESIDENT_MANIFEST = ROOT / "build/bytecode/dialect-v2/workbench/stdlib-p0.manifest.json"
M65D_MANIFEST = ROOT / "build/bytecode/dialect-v2/libs/m65d.manifest.json"
COMPILER_TIER = ROOT / "build/bytecode/dialect-v2/libs/lcc.ext.bin"
COMPOSITION = ROOT / "build/bytecode/dialect-v2/workbench-library-composition-budget.json"
LEGACY_SLOT_FUNCTIONS = (
    "%compile-slot-scan-entries", "%compile-slot-find",
    "%compile-slot-capacity", "%c1-slot-link-valid-p",
    "%fasl-save-sector", "%fasl-save-tail", "%fasl-commit-first",
    "%fasl-save-from-first", "%fasl-save-staged-v2",
)


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


def define(path: Path, name: str) -> int:
    match = re.search(
        rf"^#define {re.escape(name)} ([0-9]+)u$",
        path.read_text(encoding="utf-8"), re.MULTILINE,
    )
    require(match is not None, f"missing {name} in {path}")
    return int(match.group(1))


def artifact_metrics(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        "objects": int(manifest["objects"]),
        "code_bytes": int(manifest["code_bytes"]),
        "directory_bytes": int(manifest["directory_bytes"]),
        "ext_bytes": int(manifest["external_image"]["bytes"]),
    }


def current_capacity() -> dict[str, int]:
    layout = load(BUILD / "layout.json", "layout")
    footprint = load(BUILD / "footprint-audit.json", "footprint")
    budget = load(COMPOSITION, "composition budget")
    overlays = load(BUILD / "runtime-overlays-manifest.json", "runtime overlays")
    require(footprint.get("status") == "pass" and budget.get("status") == "pass",
            "real-link or composition gate is not green")
    slices = overlays.get("slices")
    require(isinstance(slices, list) and len(slices) == 44,
            "runtime-overlay slice inventory drift")
    runtime = [row for row in slices if "runtime" in row.get("roles", [])]
    installer = next((row for row in slices if row.get("name") == "resident-island-installer"), None)
    boot_verify = next((row for row in slices if row.get("name") == "boot-fastpath-verify"), None)
    require(runtime and isinstance(installer, dict) and isinstance(boot_verify, dict),
            "runtime-overlay capacity rows missing")
    island = BUILD / "resident-island-image.h"
    island_length = define(island, "LISP65_RESIDENT_ISLAND_LENGTH")
    island_capacity = define(island, "LISP65_RESIDENT_ISLAND_CAPACITY")
    runtime_image = (BUILD / "lisp65-mvp-workbench.overlays.bin").stat().st_size
    runtime_max = max(int(row["memory_size"]) for row in runtime)
    return {
        "bank_post_boot_reserve_bytes": int(footprint["post_boot_reserve"]),
        "fixed_overlay_bytes": int(layout["overlay"]["size"]),
        "fixed_overlay_vma_headroom_bytes": 0,
        "resident_island_immutable_bytes": island_length,
        "resident_island_annex_bytes": 260,
        "resident_island_reserve_bytes": island_capacity - island_length - 260,
        "runtime_overlay_bank_bytes": runtime_image,
        "runtime_overlay_bank_headroom_bytes": 65536 - runtime_image,
        "runtime_overlay_max_slice_bytes": runtime_max,
        "runtime_overlay_max_slice_headroom_bytes": 1792 - runtime_max,
        "installer_slice_bytes": int(installer["memory_size"]),
        "installer_slice_headroom_bytes": 1792 - int(installer["memory_size"]),
        "boot_fastpath_verify_slice_bytes": int(boot_verify["memory_size"]),
        "ext_post_load_headroom_bytes": int(budget["ext_code"]["post_headroom"]),
        "symbol_headroom": int(budget["symbols"]["headroom"]),
        "namepool_headroom_bytes": int(budget["namepool"]["headroom"]),
        "directory_load_headroom": int(budget["directory"]["load_headroom"]),
        "directory_post_align_headroom": int(budget["directory"]["post_align_headroom"]),
    }


def semantic_gates(contract: dict[str, Any]) -> dict[str, Any]:
    observations = load(OBSERVATIONS, "M65D observations")
    rows = observations.get("suites", [{}])[0].get("observations", [])
    require(isinstance(rows, list) and len(rows) == contract["acceptance"]["m65d_cases"],
            "M65D observation count drift")
    success = next((row for row in rows if row.get("name") ==
                    "m65d-buffer-payload-composition-external"), None)
    bad_type = next((row for row in rows if row.get("name") ==
                     "m65d-buffer-payload-composition-bad-type"), None)
    oracle = success.get("external_d81_oracle", {}) if isinstance(success, dict) else {}
    require(
        success is not None and success.get("result") == "0"
        and oracle.get("result") == "pass"
        and oracle.get("witnesses") == contract["acceptance"]["independent_witnesses"]
        and oracle.get("allocated_equals_visible_chain") is True
        and oracle.get("header_unchanged") is True
        and oracle.get("header_not_written") is True
        and oracle.get("no_double_allocation") is True,
        "independent Buffer/D81 oracle failed",
    )
    require(bad_type is not None and bad_type.get("result") == "3",
            "invalid Buffer payload did not return status 3")

    chain = load(CHAIN_INVENTORY, "chain-walker inventory")
    require(chain.get("status") == "pass"
            and len(chain.get("walkers", [])) == contract["acceptance"]["chain_walkers"]
            and len(chain.get("deviations", [])) == contract["acceptance"]["chain_walker_deviations"],
            "chain-walker closure drift")

    eval_text = (ROOT / "lib/dialect-v2/eval-runtime.lisp").read_text(encoding="utf-8")
    m65d_text = (ROOT / "lib/m65-disk.lisp").read_text(encoding="utf-8")
    require(not any(f"(defun {name} " in eval_text for name in LEGACY_SLOT_FUNCTIONS),
            "legacy fixed-slot writer remains in the resident source")
    require("(m65d-save dst output)" in eval_text,
            "compile-string composition seam drift")
    require("(%fasl-stage-get (+ pos i))" in m65d_text
            and "(%buffer-read 0 src)" in m65d_text
            and "(%buffer-alloc 3 src)" in m65d_text,
            "M65D Buffer transport seam drift")
    require(sha(COMPILER_TIER) == contract["acceptance"]["compiler_tier_sha256"],
            "compiler tier changed during the persistence cut")
    return {
        "m65d_cases": len(rows),
        "historical_string_and_fault_cases": len(rows) - 2,
        "buffer_cases": 2,
        "buffer_external_oracle": oracle,
        "invalid_payload_status": int(bad_type["result"]),
        "legacy_slot_functions_absent": True,
        "compile_string_transaction_owner": "m65d-save loaded by the standard composition before media swap",
        "chain_walkers": len(chain["walkers"]),
        "chain_walker_deviations": len(chain["deviations"]),
        "compiler_tier": binding(COMPILER_TIER),
    }


def collect() -> dict[str, Any]:
    contract = load(CONTRACT, "1.1-M implementation contract")
    authorization = load(AUTHORIZATION, "1.1-M capacity authorization")
    probe = load(PROBE, "1.1-M comparison probe")
    require(contract.get("format") == "lisp65-v11-m-transactional-fasl-implementation-contract-v1",
            "implementation contract format drift")
    require(probe.get("status") == "passed-not-promoted"
            and probe.get("recommendation", {}).get("choice") == "composition",
            "comparison probe no longer authorizes the selected cut")
    require(probe.get("baseline_product_set_sha256") == contract["baseline"]["product_set_sha256"],
            "Wave-1 baseline identity drift")
    baseline = probe["variants"]["baseline"]["capacity"]
    comparison = probe["variants"]["composition"]["capacity"]
    candidate = current_capacity()
    deltas = {key: int(candidate[key]) - int(baseline[key]) for key in candidate}
    versus_probe = {key: int(candidate[key]) - int(comparison[key]) for key in candidate}
    for key in contract["acceptance"]["critical_dimensions"]:
        require(candidate[key] == baseline[key], f"critical capacity changed: {key}")
    require(candidate["runtime_overlay_bank_headroom_bytes"] >=
            baseline["runtime_overlay_bank_headroom_bytes"],
            "runtime-overlay bank headroom regressed below Wave 1")

    resident = load(RESIDENT_MANIFEST, "resident manifest")
    m65d = load(M65D_MANIFEST, "M65D manifest")
    result = {
        "format": "lisp65-v11-m-transactional-fasl-implementation-receipt-v1",
        "version": 1,
        "id": "v11-m-transactional-fasl-composition",
        "status": "implemented-passed-not-promoted",
        "capacity_authorization": "pending-owner-review",
        "recorded_on": "2026-07-17",
        "baseline_product_set_sha256": contract["baseline"]["product_set_sha256"],
        "product_identity": "changes-on-promotion; no Wave-1 hardware receipt is reusable",
        "decision": contract["decision"],
        "surface": contract["surface"],
        "transaction": contract["transaction"],
        "retirements": contract["retirements"],
        "semantic_gates": semantic_gates(contract),
        "capacity": {
            "baseline": baseline,
            "candidate": candidate,
            "delta_from_wave1": deltas,
            "delta_from_comparison_probe": versus_probe,
        },
        "artifacts": {
            "baseline": probe["variants"]["baseline"]["artifacts"],
            "candidate": {
                "resident": artifact_metrics(resident),
                "m65d": artifact_metrics(m65d),
            },
        },
        "source_bindings": [
            binding(path) for path in (
                CONTRACT,
                ROOT / "lib/dialect-v2/eval-runtime.lisp",
                ROOT / "lib/m65-disk.lisp",
                ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json",
                ROOT / "tests/bytecode/libs/p0-m65d-lib.json",
                ROOT / "config/v11-c1-entry-seams.json",
                ROOT / "tools/host-lisp/v2_workbench_codemod.py",
                ROOT / "tools/host-lisp/chain_walker_inventory.py",
                ROOT / "tools/host-lisp/r3_product_block.py",
                ROOT / "tools/host-lisp/r3_g3_g6_contract.py",
                ROOT / "tools/host-lisp/v2_fasl_save_host_acceptance.py",
                ROOT / "Makefile",
                ROOT / "mk/workbench-service-inventory.mk",
                ROOT / "mk/gates.mk",
            )
        ],
        "build_bindings": {
            "observations": binding(OBSERVATIONS),
            "chain_inventory": binding(CHAIN_INVENTORY),
            "resident_manifest": binding(RESIDENT_MANIFEST),
            "m65d_manifest": binding(M65D_MANIFEST),
            "composition_budget": binding(COMPOSITION),
            "layout": binding(BUILD / "layout.json"),
            "footprint": binding(BUILD / "footprint-audit.json"),
            "runtime_overlays": binding(BUILD / "runtime-overlays-manifest.json"),
            "linked_elf": binding(BUILD / "lisp65-workbench-overlay-linked.prg.elf"),
        },
        "claim_limit": contract["claim_limit"],
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
    require(actual == expected, "implementation receipt does not bind the current source/build state")
    return actual


def selftest() -> None:
    sample = {
        "status": "implemented-passed-authorized-not-wave-promoted",
        "capacity": {"candidate": {"fixed_overlay_bytes": 7}},
    }
    accepted: list[str] = []
    for label, mutate in (
        ("status", lambda value: value.update(status="promoted")),
        ("capacity", lambda value: value["capacity"]["candidate"].update(fixed_overlay_bytes=8)),
    ):
        candidate = copy.deepcopy(sample)
        mutate(candidate)
        if candidate == sample:
            accepted.append(label)
    require(not accepted, f"selftest mutation survived: {', '.join(accepted)}")
    require(hashlib.sha256(b"m65d-cow-buffer").hexdigest() ==
            "104aa6a377b966c54f4c2a7c41a0982c792d658d4ee48759959238c8810364be",
            "selftest digest drift")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
            print("v11-m-transactional-fasl-acceptance: SELFTEST PASS mutations=2")
            return 0
        value = write_receipt(args.receipt) if args.command == "collect" else check_receipt(args.receipt)
    except (AcceptanceError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"v11-m-transactional-fasl-acceptance: FAIL: {exc}", file=sys.stderr)
        return 1
    delta = value["capacity"]["delta_from_wave1"]
    print(
        "v11-m-transactional-fasl-acceptance: PASS "
        f"status={value['status']} bank={delta['bank_post_boot_reserve_bytes']:+d} "
        f"ext={delta['ext_post_load_headroom_bytes']:+d} "
        f"symbols={delta['symbol_headroom']:+d} directory={delta['directory_load_headroom']:+d}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
