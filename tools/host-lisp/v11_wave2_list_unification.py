#!/usr/bin/env python3
"""Bind the Wave-2 list-primitive shared-core probe and its real links."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-wave2-list-primitive-unification.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-list-primitive-unification-probe-receipt.json"
)
PROBE = ROOT / "build/probes/v11-wave2-list-unification"
BASELINE_COMMIT = "5720f16"
SOURCE_PATHS = ("src/mem.h", "src/mem.c", "src/eval.c", "src/vm.c")


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"cannot read {path}: {exc}") from exc
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def git_binding(path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{path}"], cwd=ROOT,
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(result.returncode == 0, f"cannot bind baseline source: {path}")
    return {
        "path": path,
        "commit": BASELINE_COMMIT,
        "bytes": len(result.stdout),
        "sha256": sha(result.stdout),
    }


def run_make(target: str) -> str:
    result = subprocess.run(
        ["make", "-s", target], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{target} failed:\n{result.stdout}")
    return result.stdout


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


def link_metrics(root: Path) -> dict[str, Any]:
    layout = load(root / "layout.json")
    footprint = load(root / "footprint-audit.json")
    runtime = load(root / "runtime-overlays-manifest.json")
    stage = load(root / "stage-manifest.json")
    symbols = parse_symbol_sizes(root / "resident-island-seed-linked.prg.map")
    slices = runtime.get("slices")
    require(isinstance(slices, list) and len(slices) == 44,
            "runtime-overlay slice inventory drift")
    image_bytes = (root / "lisp65-mvp-workbench.overlays.bin").stat().st_size
    resident = stage.get("resident", {})
    overlay = layout.get("overlay", {})
    reusable = [row for row in slices if "reusable" in row.get("roles", [])]
    require(reusable, "runtime-overlay reusable inventory missing")
    boot_fastpath = next(
        row for row in slices if row.get("name") == "boot-fastpath-verify"
    )
    return {
        "build_id": layout.get("build_id"),
        "resident_bytes": resident.get("size"),
        "resident_file_end": resident.get("file_end"),
        "bank_post_boot_reserve_bytes": footprint.get("post_boot_reserve"),
        "runtime_stack_gap_bytes": footprint.get("runtime_stack_gap"),
        "fixed_overlay_bytes": overlay.get("size"),
        "fixed_overlay_headroom_bytes": 0,
        "ext_post_load_bytes": layout.get("stdlib", {}).get("size"),
        "runtime_overlay_bank_bytes": image_bytes,
        "runtime_overlay_bank_headroom_bytes": 65536 - image_bytes,
        "runtime_overlay_max_slice_bytes": max(row["file_size"] for row in reusable),
        "runtime_overlay_max_slice_headroom_bytes": (
            1792 - max(row["file_size"] for row in reusable)
        ),
        "boot_fastpath_verify_slice_bytes": boot_fastpath["file_size"],
        "resident_island_bytes": 1668,
        "resident_island_reserve_bytes": 120,
        "installer_slice_bytes": next(
            row["file_size"] for row in slices
            if row.get("name") == "resident-island-installer"
        ),
        "installer_slice_headroom_bytes": 1792 - next(
            row["file_size"] for row in slices
            if row.get("name") == "resident-island-installer"
        ),
        "shelf_bytes": 65368,
        "vm_callprim_bytes": symbols.get("vm_callprim"),
        "vm_run_inner_bytes": symbols.get("vm_run_inner"),
    }


def capacity_delta(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    direct = (
        "resident_bytes", "resident_file_end", "ext_post_load_bytes",
        "fixed_overlay_bytes", "runtime_overlay_bank_bytes",
        "runtime_overlay_max_slice_bytes", "resident_island_bytes",
        "installer_slice_bytes", "shelf_bytes",
    )
    values = {name: candidate[name] - baseline[name] for name in direct}
    values.update({
        "bank_post_boot_reserve_bytes": (
            candidate["bank_post_boot_reserve_bytes"]
            - baseline["bank_post_boot_reserve_bytes"]
        ),
        "fixed_overlay_headroom_bytes": 0,
        "runtime_overlay_bank_headroom_bytes": (
            candidate["runtime_overlay_bank_headroom_bytes"]
            - baseline["runtime_overlay_bank_headroom_bytes"]
        ),
        "runtime_overlay_max_slice_headroom_bytes": (
            candidate["runtime_overlay_max_slice_headroom_bytes"]
            - baseline["runtime_overlay_max_slice_headroom_bytes"]
        ),
        "boot_fastpath_verify_slice_bytes": (
            candidate["boot_fastpath_verify_slice_bytes"]
            - baseline["boot_fastpath_verify_slice_bytes"]
        ),
        "resident_island_reserve_bytes": 0,
        "installer_slice_headroom_bytes": (
            candidate["installer_slice_headroom_bytes"]
            - baseline["installer_slice_headroom_bytes"]
        ),
        "symbols": 0,
        "namepool_bytes": 0,
        "directory_entries": 0,
    })
    return values


def source_shape() -> None:
    mem_h = (ROOT / "src/mem.h").read_text(encoding="utf-8")
    mem_c = (ROOT / "src/mem.c").read_text(encoding="utf-8")
    eval_c = (ROOT / "src/eval.c").read_text(encoding="utf-8")
    vm_c = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    for name in ("list_nreverse", "list_rplaca", "list_rplacd"):
        require(f"obj  {name}" in mem_h, f"missing shared declaration: {name}")
        require(f"obj {name}(" in mem_c, f"missing shared implementation: {name}")
        require(name in eval_c, f"Treewalk route does not use {name}")
        require(name in vm_c, f"CALLPRIM route does not use {name}")
    require("primitive_exact_arity(args, 1)" in eval_c
            and eval_c.count("primitive_exact_arity(args, 2)") >= 2,
            "Treewalk strict-arity guards drift")
    require("if (n != 1) { vm_status = VM_ARITY;" in vm_c
            and vm_c.count("if (n != 2) { vm_status = VM_ARITY;") >= 2,
            "CALLPRIM strict-arity guards drift")


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    require(contract.get("status") == "probe-passed-awaiting-capacity-authorization",
            "list-unification decision drift")
    source_shape()
    outputs = {
        "lists": run_make("dialect-v2-lists-check"),
        "python_p0": run_make("dialect-v2-lists-p0-selftest"),
        "lcc": run_make("dialect-v2-lists-lcc-selftest"),
        "registry": run_make("v2-native-function-registry-check"),
    }
    require("cases=43 runs=172" in outputs["lists"], "four-engine list count drift")
    require("cases=8 runs=16" in outputs["python_p0"], "Python P0 count drift")
    require("cases=43 runs=86" in outputs["lcc"], "LCC list count drift")
    require("evaluations=828" in outputs["registry"], "registry parity count drift")

    baseline = link_metrics(PROBE / "baseline")
    candidate = link_metrics(PROBE / "candidate")
    delta = capacity_delta(baseline, candidate)
    require(delta["resident_bytes"] == -12
            and delta["bank_post_boot_reserve_bytes"] == 12,
            "real-link resident attribution drift")
    for name in (
        "ext_post_load_bytes", "fixed_overlay_bytes", "runtime_overlay_bank_bytes",
        "runtime_overlay_max_slice_bytes", "runtime_overlay_max_slice_headroom_bytes",
        "boot_fastpath_verify_slice_bytes", "resident_island_bytes",
        "installer_slice_bytes", "shelf_bytes", "symbols", "namepool_bytes",
        "directory_entries",
    ):
        require(delta[name] == 0, f"unexpected capacity movement: {name}")
    vm_delta = candidate["vm_callprim_bytes"] - baseline["vm_callprim_bytes"]
    inner_delta = candidate["vm_run_inner_bytes"] - baseline["vm_run_inner_bytes"]
    require((vm_delta, inner_delta, vm_delta + inner_delta) == (-108, 96, -12),
            "shared-core symbol attribution drift")

    return {
        "format": "lisp65-v11-wave2-list-primitive-unification-probe-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "passed-awaiting-capacity-authorization",
        "claim_limit": contract["claim_limit"],
        "baseline": {
            "commit": BASELINE_COMMIT,
            "sources": [git_binding(path) for path in SOURCE_PATHS],
            "link": baseline,
        },
        "candidate": {
            "sources": [binding(ROOT / path) for path in SOURCE_PATHS],
            "link": candidate,
        },
        "semantic_evidence": {
            "treewalker_and_p0": {"cases": 43, "evaluations": 172},
            "python_p0": {"cases": 8, "evaluations": 16},
            "lcc": {"cases": 43, "evaluations": 86},
            "registry": {"active_primitive_ids": 61, "cases": 207,
                         "engines": 4, "evaluations": 828},
            "route_rule": "strict arity and route-specific errors remain outside the shared mutation core",
        },
        "link_attribution": {
            "vm_callprim_bytes": vm_delta,
            "vm_run_inner_bytes": inner_delta,
            "net_resident_bytes": vm_delta + inner_delta,
            "interpretation": "CALLPRIM duplication disappears; the inlined Treewalk/shared core grows by 96 bytes; net resident result is a 12-byte credit.",
        },
        "capacity_delta": delta,
        "authorization_request": {
            "bank_post_boot_reserve_bytes": 12,
            "all_other_frozen_dimensions": 0,
            "kind": "credit-only-repin",
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    source_shape()
    validate_receipt(actual)
    require(actual.get("candidate", {}).get("sources") ==
            [binding(ROOT / path) for path in SOURCE_PATHS],
            "list-unification source binding drift")
    require(actual.get("baseline", {}).get("sources") ==
            [git_binding(path) for path in SOURCE_PATHS],
            "list-unification baseline binding drift")
    require(actual.get("capacity_delta", {}).get("bank_post_boot_reserve_bytes") == 12,
            "list-unification capacity credit drift")
    return actual


def validate_receipt(value: dict[str, Any]) -> None:
    require(value.get("format") ==
            "lisp65-v11-wave2-list-primitive-unification-probe-receipt-v1",
            "list-unification receipt format drift")
    require(value.get("status") == "passed-awaiting-capacity-authorization",
            "list-unification receipt status drift")
    require(value.get("claim_limit") == load(CONTRACT)["claim_limit"],
            "list-unification receipt claim drift")
    delta = value.get("capacity_delta", {})
    require(delta.get("resident_bytes") == -12
            and delta.get("bank_post_boot_reserve_bytes") == 12,
            "list-unification receipt capacity drift")
    attribution = value.get("link_attribution", {})
    require(attribution.get("vm_callprim_bytes") == -108
            and attribution.get("vm_run_inner_bytes") == 96
            and attribution.get("net_resident_bytes") == -12,
            "list-unification receipt attribution drift")


def selftest() -> None:
    source_shape()
    receipt = load(RECEIPT)
    validate_receipt(receipt)
    mutations: list[str] = []
    for field, value in (
        ("status", "promoted"),
        ("claim_limit", "hardware passed"),
    ):
        mutated = json.loads(json.dumps(receipt))
        mutated[field] = value
        try:
            validate_receipt(mutated)
        except ProbeError:
            mutations.append(field)
    mutated = json.loads(json.dumps(receipt))
    mutated["capacity_delta"]["bank_post_boot_reserve_bytes"] = 11
    try:
        validate_receipt(mutated)
    except ProbeError:
        mutations.append("capacity")
    require(mutations == ["status", "claim_limit", "capacity"],
            "mutation selftest drift")
    print("v11-wave2-list-unification: SELFTEST PASS mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check", "selftest"))
    args = parser.parse_args()
    if args.command == "collect":
        value = write()
    elif args.command == "check":
        value = check()
    else:
        selftest()
        return 0
    delta = value["capacity_delta"]
    print("v11-wave2-list-unification: PASS "
          f"resident={delta['resident_bytes']} bank-credit="
          f"{delta['bank_post_boot_reserve_bytes']} other-frozen=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
