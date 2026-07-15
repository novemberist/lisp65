#!/usr/bin/env python3
"""Validate the measured Workbench-v2 de-residentization audit."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/v2-workbench-de-residentization-audit.json"
FORMAT = "lisp65-v2-workbench-de-residentization-audit-v2"
REPORT_FORMAT = "lisp65-workbench-removable-class-sweep-v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class AuditError(RuntimeError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise AuditError(f"contract must be a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except AuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError("JSON root must be an object")
    return value


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise AuditError(f"{label} keys drift: {actual}")
    return value


def _hex(value: Any, label: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-f]+", value):
        raise AuditError(f"{label} must be lowercase hexadecimal")
    return int(value, 16)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(value: Any, label: str) -> None:
    item = _exact(value, {"path", "sha256"}, label)
    if not isinstance(item["path"], str) or item["path"].startswith("/"):
        raise AuditError(f"{label} path must be repository-relative")
    if not isinstance(item["sha256"], str) or not SHA_RE.fullmatch(item["sha256"]):
        raise AuditError(f"{label} SHA drift")
    path = ROOT / item["path"]
    if path.is_symlink() or not path.is_file() or _sha_file(path) != item["sha256"]:
        raise AuditError(f"{label} binding mismatch")


def _validate_report(report: dict[str, Any]) -> None:
    if report.get("format") != REPORT_FORMAT or report.get("version") != 1:
        raise AuditError("sweep report identity drift")
    if report.get("status") != "measurement-complete-no-promotion":
        raise AuditError("sweep report status drift")
    if report.get("source_commit") != "bb889020ec5a401db8344e17a85b169d7103757d":
        raise AuditError("sweep source commit drift")
    method = report.get("method", {})
    if method != {
        "build": "real-mos-lto-icf-relaxed-workbench-link",
        "isolation": "temporary-detached-worktrees",
        "metric": "marginal-runtime-overlay-vma-and-heap-start-drop",
        "candidate_values": "upper-bounds-before-semantic-replacement",
        "product_tree_modified": False,
        "layout_modified": False,
    }:
        raise AuditError("sweep method drift")

    baseline = report.get("accepted_baseline", {})
    if (
        baseline.get("elf_sha256") != "4ea8f1169988c1e83335ed0b3ba104d0f9a50bdf54a47201ba5bc1a07b292322"
        or baseline.get("elf_bytes") != 119340
        or _hex(baseline.get("bss_end"), "baseline bss") != 0xC9CE
        or _hex(baseline.get("heap_start"), "baseline heap") != 0xC9CE
        or _hex(baseline.get("runtime_overlay_vma"), "baseline VMA") != 0xC9D0
        or _hex(baseline.get("runtime_overlay_vma_limit"), "baseline limit") != 0xC356
        or baseline.get("post_boot_reserve_bytes") != 136
        or baseline.get("post_boot_reserve_target_bytes") != 1536
    ):
        raise AuditError("sweep baseline drift")

    candidates = report.get("candidates")
    if not isinstance(candidates, list) or [item.get("id") for item in candidates] != [
        "string-builders-prim-26-27",
        "interactive-lcc-install-coordinator",
        "repl-comfort-leaves",
        "boot-lifetime-cluster",
    ]:
        raise AuditError("sweep candidate inventory drift")
    string, lcc, repl, boot = candidates
    if (
        string.get("vma_reclaim_bytes") != 2542
        or string.get("heap_reclaim_bytes") != 2540
        or string.get("product_call_inventory") != {"prim_26": 0, "prim_27": 0, "prim_28": 48, "prim_29": 27}
        or string.get("promotion") is not False
        or string.get("hard_link", {}).get("passed") is not True
        or string.get("hard_link", {}).get("vma_headroom_below_limit_bytes") != 884
        or string.get("hard_link", {}).get("post_boot_reserve_bytes") != 2676
    ):
        raise AuditError("string-builder measurement drift")
    if (
        lcc.get("vma_reclaim_bytes") != 1058
        or lcc.get("heap_reclaim_bytes") != 1056
        or lcc.get("closes_current_budget") is not False
        or lcc.get("promotion") is not False
    ):
        raise AuditError("LCC ceiling drift")
    if (
        repl.get("vma_reclaim_bytes") != 460
        or repl.get("heap_reclaim_bytes") != 458
        or repl.get("promotion") is not False
    ):
        raise AuditError("REPL ceiling drift")
    if (
        boot.get("old_nonfunctional_ceiling_bytes") != 1371
        or boot.get("functional_diagnostic_vma_reclaim_bytes") != 110
        or boot.get("promotable_planning_bytes") != 0
        or boot.get("status") != "rejected-non-independent"
    ):
        raise AuditError("boot correction drift")

    layout = report.get("layout_context", {})
    if (
        layout.get("resident_island_capacity_bytes") != 2048
        or layout.get("resident_island_code_bytes") != 1108
        or layout.get("resident_island_annex_bytes") != 260
        or layout.get("resident_island_free_bytes") != 680
        or 2048 - 1108 - 260 != 680
        or layout.get("proposed_1024_byte_cap") != "not-an-independent-reclaim-and-does-not-fit-current-payload"
    ):
        raise AuditError("sweep layout correction drift")
    recommendation = report.get("recommendation", {})
    if (
        recommendation.get("decision_status") != "architecture-approval-required"
        or recommendation.get("retain_prim_ids") != [28, 29]
        or recommendation.get("retire_to_permanent_tombstones_if-approved") != [26, 27]
        or recommendation.get("new_runtime_slots") != 0
        or recommendation.get("permanent_island_bytes") != 0
        or recommendation.get("slice_cap_change") is not False
        or recommendation.get("v1_1_reserve_preserved") is not True
    ):
        raise AuditError("sweep recommendation drift")


def validate(contract: dict[str, Any]) -> None:
    _exact(
        contract,
        {
            "format", "version", "id", "status", "scope", "provenance", "gap",
            "accepted_burn_down", "corrected_findings", "sweep", "recommendation",
            "acceptance",
        },
        "contract",
    )
    if (
        contract["format"] != FORMAT
        or contract["version"] != 2
        or contract["id"] != "cp5-workbench-de-residentization"
        or contract["status"] != "removable-class-sweep-complete"
    ):
        raise AuditError("contract identity/status drift")
    if contract["scope"] != {
        "release_path": "workbench-v2",
        "runtime_core": "internal-proof-only",
        "new_language_families": False,
        "new_ap8_blocks": False,
        "implementation_included": True,
        "sweep_implementation_included": False,
        "architecture_decision_pending": True,
    }:
        raise AuditError("scope drift")

    provenance = contract["provenance"]
    if (
        provenance.get("source_commit") != "bb889020ec5a401db8344e17a85b169d7103757d"
        or not COMMIT_RE.fullmatch(provenance.get("source_commit", ""))
        or provenance.get("metric") != "real-mos-lto-icf-marginal-runtime-overlay-vma-drop"
        or provenance.get("candidate_values") != "upper-bounds-before-semantic-replacement"
    ):
        raise AuditError("provenance drift")
    bindings = provenance.get("durable_bindings")
    if not isinstance(bindings, list) or len(bindings) != 5:
        raise AuditError("durable binding inventory drift")
    for index, item in enumerate(bindings):
        _binding(item, f"durable binding {index}")

    gap = contract["gap"]
    vma = _hex(gap.get("candidate_runtime_overlay_vma"), "candidate VMA")
    limit = _hex(gap.get("runtime_overlay_vma_limit"), "VMA limit")
    if (
        _hex(gap.get("candidate_bss_end"), "candidate BSS") != 0xC9CE
        or _hex(gap.get("candidate_heap_start"), "candidate heap") != 0xC9CE
        or vma != 0xC9D0
        or limit != 0xC356
        or vma - limit != gap.get("vma_reclaim_required_bytes")
        or gap.get("post_boot_reserve_bytes") != 136
        or gap.get("post_boot_reserve_min_bytes") != 1536
        or 1536 - 136 != gap.get("reserve_reclaim_required_bytes")
    ):
        raise AuditError("gap arithmetic drift")

    if contract["accepted_burn_down"] != [
        {"id": "cp5-start", "net_reclaim_bytes": 0, "vma_gap_bytes": 2338, "reserve_gap_bytes": 2082},
        {"id": "number-to-string", "net_reclaim_bytes": 80, "vma_gap_bytes": 2258, "reserve_gap_bytes": 2000},
        {"id": "fasl-save", "net_reclaim_bytes": 600, "vma_gap_bytes": 1658, "reserve_gap_bytes": 1400},
    ]:
        raise AuditError("accepted burn-down drift")

    corrected = contract["corrected_findings"]
    if corrected.get("boot_lifetime", {}).get("promotable_planning_bytes") != 0:
        raise AuditError("boot planning correction drift")
    island = corrected.get("island", {})
    if island.get("free_bytes") != 680 or island.get("capacity_bytes") - island.get("code_bytes") - island.get("annex_bytes") != 680:
        raise AuditError("island arithmetic drift")
    slice_cap = corrected.get("slice_cap", {})
    if slice_cap.get("independent_reclaim_bytes") != 0 or slice_cap.get("status") != "not-an-independent-lever":
        raise AuditError("slice-cap correction drift")

    sweep = contract["sweep"]
    report_path = sweep.get("report")
    if report_path != "tests/bytecode/dialect-v2/evidence/capability-carrier/workbench-removable-class-sweep-report.json":
        raise AuditError("sweep report path drift")
    report = _load(ROOT / report_path)
    _validate_report(report)
    expected_sweep = [(2542, 2540, True), (1058, 1056, False), (460, 458, False), (110, 108, False)]
    if sweep.get("timebox_complete") is not True or not isinstance(sweep.get("candidates"), list):
        raise AuditError("sweep completion drift")
    actual_sweep = [
        (item.get("vma_reclaim_bytes"), item.get("heap_reclaim_bytes"), item.get("closes_current_budget"))
        for item in sweep["candidates"]
    ]
    if actual_sweep != expected_sweep or sweep["candidates"][3].get("promotable_planning_bytes") != 0:
        raise AuditError("sweep summary drift")

    recommendation = contract["recommendation"]
    if recommendation != {
        "id": "split-string-builders-from-codecs",
        "decision_status": "architecture-approval-required",
        "retain_prim_ids": [28, 29],
        "retire_to_permanent_tombstones_if_approved": [26, 27],
        "defer_atomic_builder_contract_to": "buffer-and-string-construction-block",
        "expected_vma_headroom_bytes": 884,
        "expected_post_boot_reserve_bytes": 2676,
        "expected_reserve_headroom_above_target_bytes": 1140,
        "new_runtime_slots": 0,
        "permanent_island_bytes": 0,
        "slice_cap_change": False,
        "v1_1_layout_reserve_preserved": True,
    }:
        raise AuditError("recommendation drift")
    acceptance = contract["acceptance"]
    if acceptance != {
        "runtime_overlay_vma_max": "0xc356",
        "post_boot_reserve_min_bytes": 1536,
        "runtime_slot_delta": 0,
        "permanent_island_bytes_delta": 0,
        "strict_arity_preserved": True,
        "current_product_string_atomicity_unchanged": True,
        "recommended_contract_change_pending": True,
        "full_workbench_g5_required": True,
        "ship_remains_blocked": True,
    }:
        raise AuditError("acceptance drift")


def selftest(contract: dict[str, Any]) -> None:
    validate(contract)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("format", lambda x: x.__setitem__("format", "bad")),
        ("extra-key", lambda x: x.__setitem__("unexpected", True)),
        ("scope", lambda x: x["scope"].__setitem__("architecture_decision_pending", False)),
        ("binding", lambda x: x["provenance"]["durable_bindings"][4].__setitem__("sha256", "0" * 64)),
        ("gap", lambda x: x["gap"].__setitem__("vma_reclaim_required_bytes", 1657)),
        ("boot", lambda x: x["corrected_findings"]["boot_lifetime"].__setitem__("promotable_planning_bytes", 110)),
        ("island", lambda x: x["corrected_findings"]["island"].__setitem__("free_bytes", 932)),
        ("slice", lambda x: x["corrected_findings"]["slice_cap"].__setitem__("independent_reclaim_bytes", 372)),
        ("string", lambda x: x["sweep"]["candidates"][0].__setitem__("vma_reclaim_bytes", 2541)),
        ("promotion", lambda x: x["recommendation"].__setitem__("decision_status", "approved")),
        ("tombstone", lambda x: x["recommendation"].__setitem__("retire_to_permanent_tombstones_if_approved", [26])),
        ("slot", lambda x: x["acceptance"].__setitem__("runtime_slot_delta", 1)),
        ("ship", lambda x: x["acceptance"].__setitem__("ship_remains_blocked", False)),
    ]
    passed = 0
    for label, mutate in mutations:
        value = copy.deepcopy(contract)
        mutate(value)
        try:
            validate(value)
        except AuditError:
            passed += 1
            continue
        raise AuditError(f"selftest accepted mutation: {label}")
    print(f"v2-workbench-deresidentization-audit: SELFTEST PASS mutations={passed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        contract = _load(args.contract)
        if args.selftest:
            selftest(contract)
        else:
            validate(contract)
            print("v2-workbench-deresidentization-audit: PASS status=sweep-complete vma_gap=1658 reserve_gap=1400 decision=pending")
        return 0
    except (AuditError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"v2-workbench-deresidentization-audit: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
