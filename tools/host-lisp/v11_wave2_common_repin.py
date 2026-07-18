#!/usr/bin/env python3
"""Bind the owner-authorized Wave-2 common repin and all capacity currencies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "5720f16"
PROBE = ROOT / "build/v11-wave2-common-repin"
BASELINE_PRODUCTS = PROBE / "baseline/products"
BASELINE_REPORTS = PROBE / "baseline/reports"
CANDIDATE_PRODUCTS = ROOT / "build/products/workbench/overlay-stack-guard"
CANDIDATE_REPORTS = ROOT / "build/bytecode/dialect-v2"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-scope-corrected-repin-receipt.json"
)
PRODUCT_SOURCES = tuple(ROOT / path for path in (
    "src/mem.h", "src/mem.c", "src/eval.c", "src/vm.c",
    "lib/ide-buffer.lisp", "lib/ide-ui.lisp", "lib/ide-disk.lisp",
))
EVIDENCE_INPUTS = tuple(ROOT / path for path in (
    "config/v11-wave2-list-primitive-unification-capacity-authorization.json",
    "config/v11-wave2-policy-name-revocation.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-m-transactional-fasl-implementation-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-g-green-surface-implementation-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-error-text-library-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-list-primitive-unification-probe-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-function-metadata-contract-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-policy-name-implementation-receipt.json",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-restart-repl-wave2-scope-correction-receipt.json",
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-artifact-differential-receipt.json",
))


class RepinError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepinError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RepinError(f"cannot read {path}: {exc}") from exc
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def parse_symbol_sizes(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+(.+?)\s*$",
            line,
        )
        if match is None:
            continue
        name = match.group(2)
        if any(part in name for part in ("build/", ".o:", "<internal>")):
            continue
        values[name] = int(match.group(1), 16)
    return values


def metrics(products: Path, reports: Path) -> dict[str, Any]:
    layout = load(products / "layout.json")
    footprint = load(products / "footprint-audit.json")
    runtime = load(products / "runtime-overlays-manifest.json")
    stage = load(products / "stage-manifest.json")
    composition_path, shelf = report_paths(reports)
    composition = load(composition_path)
    symbols = parse_symbol_sizes(products / "resident-island-seed-linked.prg.map")
    slices = runtime.get("slices")
    require(isinstance(slices, list) and len(slices) == 44,
            "runtime-overlay slice inventory drift")
    reusable = [row for row in slices if "reusable" in row.get("roles", [])]
    require(reusable, "runtime-overlay reusable inventory missing")
    boot_fastpath = next(
        row for row in slices if row.get("name") == "boot-fastpath-verify"
    )
    installer = next(
        row for row in slices if row.get("name") == "resident-island-installer"
    )
    image_bytes = (products / "lisp65-mvp-workbench.overlays.bin").stat().st_size
    shelf_bytes = shelf.stat().st_size
    resident = stage["resident"]
    overlay = layout["overlay"]
    return {
        "build_id": layout["build_id"],
        "resident_bytes": resident["size"],
        "resident_file_end": resident["file_end"],
        "bank_post_boot_reserve_bytes": footprint["post_boot_reserve"],
        "runtime_stack_gap_bytes": footprint["runtime_stack_gap"],
        "ext_post_load_bytes": layout["stdlib"]["size"],
        "fixed_overlay_bytes": overlay["size"],
        "fixed_overlay_headroom_bytes": 0,
        "runtime_overlay_bank_bytes": image_bytes,
        "runtime_overlay_bank_headroom_bytes": 65536 - image_bytes,
        "runtime_overlay_max_slice_bytes": max(row["file_size"] for row in reusable),
        "runtime_overlay_max_slice_headroom_bytes": (
            1792 - max(row["file_size"] for row in reusable)
        ),
        "boot_fastpath_verify_slice_bytes": boot_fastpath["file_size"],
        "resident_island_bytes": 1668,
        "resident_island_reserve_bytes": 120,
        "installer_slice_bytes": installer["file_size"],
        "installer_slice_headroom_bytes": 1792 - installer["file_size"],
        "shelf_bytes": shelf_bytes,
        "shelf_headroom_bytes": 65535 - shelf_bytes,
        "symbol_headroom": composition["symbols"]["headroom"],
        "namepool_headroom_bytes": composition["namepool"]["headroom"],
        "directory_load_headroom": composition["directory"]["load_headroom"],
        "directory_post_align_headroom":
            composition["directory"]["post_align_headroom"],
        "ext_code_peak_headroom": composition["ext_code"]["worst_peak_headroom"],
        "ext_code_post_headroom": composition["ext_code"]["post_headroom"],
        "codebuf_headroom": composition["codebuf"]["headroom"],
        "vm_callprim_bytes": symbols["vm_callprim"],
        "vm_run_inner_bytes": symbols["vm_run_inner"],
    }


def report_paths(root: Path) -> tuple[Path, Path]:
    if root == CANDIDATE_REPORTS:
        return (
            root / "workbench-library-composition-budget.json",
            root / "shelf/library-shelf.bin",
        )
    return (
        root / "workbench-library-composition-budget.json",
        root / "library-shelf.bin",
    )


def artifact_bindings(products: Path, reports: Path) -> list[dict[str, Any]]:
    composition, shelf = report_paths(reports)
    paths = (
        products / "lisp65-workbench-overlay-linked.prg",
        products / "lisp65-workbench-resident.prg",
        products / "lisp65-workbench-overlay.bin",
        products / "lisp65-mvp-workbench.overlays.bin",
        products / "layout.json",
        products / "stage-manifest.json",
        products / "runtime-overlays-manifest.json",
        products / "footprint-audit.json",
        composition,
        shelf,
    )
    return [binding(path) for path in paths]


def delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(after[key]) - int(before[key])
        for key in before
        if key != "build_id"
    }


EXPECTED_DELTA = {
    "resident_bytes": -58,
    "resident_file_end": -58,
    "bank_post_boot_reserve_bytes": 58,
    "runtime_stack_gap_bytes": 58,
    "ext_post_load_bytes": -36,
    "fixed_overlay_bytes": 0,
    "fixed_overlay_headroom_bytes": 0,
    "runtime_overlay_bank_bytes": 0,
    "runtime_overlay_bank_headroom_bytes": 0,
    "runtime_overlay_max_slice_bytes": 0,
    "runtime_overlay_max_slice_headroom_bytes": 0,
    "boot_fastpath_verify_slice_bytes": 0,
    "resident_island_bytes": 0,
    "resident_island_reserve_bytes": 0,
    "installer_slice_bytes": 0,
    "installer_slice_headroom_bytes": 0,
    "shelf_bytes": -200,
    "shelf_headroom_bytes": 200,
    "symbol_headroom": 17,
    "namepool_headroom_bytes": 195,
    "directory_load_headroom": 0,
    "directory_post_align_headroom": 0,
    "ext_code_peak_headroom": 214,
    "ext_code_post_headroom": 16,
    "codebuf_headroom": 0,
    "vm_callprim_bytes": -154,
    "vm_run_inner_bytes": 96,
}


def verify_inputs() -> None:
    authorization = load(EVIDENCE_INPUTS[0])
    harvest = load(EVIDENCE_INPUTS[7])
    scope_correction = load(EVIDENCE_INPUTS[8])
    differential = load(EVIDENCE_INPUTS[-1])
    require(authorization["status"] == "owner-authorized-for-common-wave2-repin",
            "owner common-repin authorization drift")
    require(harvest["summary"] == {
        "echo_cases": 18, "passed": 18, "recovered_namepool_bytes": 182,
        "recovered_symbols": 16, "revoked_names_remaining": 0,
    }, "16-name harvest receipt drift")
    require(
        scope_correction.get("status") ==
        "implemented-passed-credit-only-awaiting-capacity-repin-review"
        and scope_correction.get("capacity_delta", {}).get(
            "bank_post_boot_reserve_bytes"
        ) == 46,
        "restart-repl scope-correction receipt drift",
    )
    require(differential["status"] == "passed"
            and differential["summary"] == {
                "artifacts": 4, "cases": 376, "observation_differences": 0,
            }, "four-artifact differential receipt drift")


def collect() -> dict[str, Any]:
    verify_inputs()
    require(BASELINE_PRODUCTS.is_dir() and BASELINE_REPORTS.is_dir(),
            "isolated baseline build is missing")
    before = metrics(BASELINE_PRODUCTS, BASELINE_REPORTS)
    after = metrics(CANDIDATE_PRODUCTS, CANDIDATE_REPORTS)
    measured = delta(before, after)
    require(measured == EXPECTED_DELTA,
            f"common-repin capacity delta drift: {measured}")
    require(before["bank_post_boot_reserve_bytes"] == 1849
            and after["bank_post_boot_reserve_bytes"] == 1907,
            "Bank reserve pin drift")
    require(after["symbol_headroom"] == 320
            and after["namepool_headroom_bytes"] == 4897,
            "composition headroom pin drift")
    require(after["shelf_headroom_bytes"] == 367,
            "shelf headroom pin drift")
    head = git_output("rev-parse", "HEAD")
    require(git_output("rev-parse", BASELINE_COMMIT) ==
            "5720f16379251caec7cadf7323dc83ca7bc7b39b",
            "baseline commit identity drift")

    base_ide = load(BASELINE_REPORTS / "ide.manifest.json")
    candidate_ide = load(CANDIDATE_REPORTS / "libs/ide.manifest.json")
    removed = sorted(
        set(base_ide["cost"]["symbol_names"])
        - set(candidate_ide["cost"]["symbol_names"])
    )
    require(len(removed) == 16, "IDE manifest did not remove exactly 16 names")
    require(candidate_ide["external_image"]["bytes"]
            - base_ide["external_image"]["bytes"] == -200,
            "IDE external-image recovery drift")

    return {
        "format": "lisp65-v11-wave2-common-repin-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "passed-owner-authorized-ready-for-wave2-promotion",
        "claim_limit": (
            "This receipt binds the common Wave-2 host/product link and all pinned "
            "capacity dimensions. It does not claim fresh G5/G6 hardware acceptance or "
            "a Wave-2 seal."
        ),
        "baseline": {
            "commit": BASELINE_COMMIT,
            "commit_sha256": "5720f16379251caec7cadf7323dc83ca7bc7b39b",
            "metrics": before,
            "artifacts": artifact_bindings(BASELINE_PRODUCTS, BASELINE_REPORTS),
        },
        "candidate": {
            "source_commit": head,
            "metrics": after,
            "product_sources": [binding(path) for path in PRODUCT_SOURCES],
            "evidence_inputs": [binding(path) for path in EVIDENCE_INPUTS],
            "artifacts": artifact_bindings(CANDIDATE_PRODUCTS, CANDIDATE_REPORTS),
        },
        "capacity_delta": measured,
        "attribution": {
            "list_core": {
                "vm_callprim_bytes": -108,
                "vm_run_inner_bytes": 96,
                "resident_bytes": -12,
                "bank_reserve_bytes": 12,
            },
            "policy_name_harvest": {
                "removed_names": removed,
                "symbols_recovered": 16,
                "namepool_bytes_recovered": 182,
                "ide_code_bytes": -2,
                "ide_metadata_bytes": -198,
                "ide_external_image_bytes": -200,
                "literal_nodes": -1,
                "literal_patches": -1,
                "shelf_bytes": -200,
                "metadata_explanation": (
                    "182 name-pool bytes plus one 10-byte literal node, one 4-byte "
                    "literal patch and one 2-byte literal-index record"
                ),
            },
            "restart_repl_scope_correction": {
                "resident_bytes": -46,
                "bank_reserve_bytes": 46,
                "resident_ext_bytes": -36,
                "ext_code_headroom_bytes": 14,
                "symbols_recovered": 1,
                "namepool_bytes_recovered": 13,
                "frozen_structural_containers": "unchanged",
            },
        },
        "gates": {
            "policy_echo_cases": "18/18 passed",
            "workbench_differential": "4 artifacts / 376 cases / 0 differences",
            "all_frozen_dimensions_reported": True,
            "negative_unattributed_capacity_drift": False,
            "hardware": "not-run; fresh Wave-2 G5/G6 required after promotion",
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    verify_inputs()
    require(actual.get("format") == "lisp65-v11-wave2-common-repin-receipt-v1"
            and actual.get("status") ==
            "passed-owner-authorized-ready-for-wave2-promotion",
            "common-repin receipt identity drift")
    git_output(
        "merge-base", "--is-ancestor", actual["candidate"]["source_commit"], "HEAD"
    )
    current = metrics(CANDIDATE_PRODUCTS, CANDIDATE_REPORTS)
    require(current == actual["candidate"]["metrics"],
            "common-repin candidate metrics drift")
    require([binding(path) for path in PRODUCT_SOURCES] ==
            actual["candidate"]["product_sources"],
            "common-repin product-source binding drift")
    require([binding(path) for path in EVIDENCE_INPUTS] ==
            actual["candidate"]["evidence_inputs"],
            "common-repin evidence-input binding drift")
    require(artifact_bindings(CANDIDATE_PRODUCTS, CANDIDATE_REPORTS) ==
            actual["candidate"]["artifacts"],
            "common-repin product artifact drift")
    require(actual["capacity_delta"] == EXPECTED_DELTA,
            "common-repin capacity delta receipt drift")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args()
    try:
        value = write() if args.command == "collect" else check()
    except (RepinError, OSError, ValueError) as exc:
        print(f"v11-wave2-common-repin: FAIL: {exc}", file=sys.stderr)
        return 1
    after = value["candidate"]["metrics"]
    print(
        "v11-wave2-common-repin: PASS "
        f"bank={after['bank_post_boot_reserve_bytes']} "
        f"symbols={after['symbol_headroom']} "
        f"namepool={after['namepool_headroom_bytes']} "
        f"shelf={after['shelf_headroom_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
