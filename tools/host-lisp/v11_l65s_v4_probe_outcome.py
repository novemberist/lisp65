#!/usr/bin/env python3
"""Bind the one permitted L65S-v4 real-link result and automatic fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-l65s-v4-probe-contract.json"
AUDIT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-shelf-metadata-audit-receipt.json"
)
MODEL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l65s-v4-layout-model-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l65s-v4-one-attempt-outcome-receipt.json"
)
BUILD_LOG = ROOT / "build/probes/v11-l65s-v4/real-link/build.log"
FAILED_MAP = ROOT / (
    "build/probes/v11-l65s-v4/real-link/"
    "failed-resident-island-seed-linked.prg.map"
)
SHELF = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf.bin"
SHELF_MANIFEST = ROOT / "build/bytecode/dialect-v2/shelf/library-shelf-manifest.json"
ROLLBACK_SOURCES = (
    "tools/host-lisp/v11_attic_library_shelf.py",
    "src/attic_library_shelf.c",
    "src/attic_library_shelf.h",
    "scripts/attic-library-shelf-smoke-main.c",
    "src/io.c",
)


class OutcomeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OutcomeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing regular binding: {path}")
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def git_head_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT)


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    audit = load(AUDIT)
    model = load(MODEL)
    log = BUILD_LOG.read_text(encoding="utf-8")
    map_text = FAILED_MAP.read_text(encoding="utf-8")
    require(contract["status"] == "owner-authorized-one-attempt",
            "one-attempt contract is not owner-authorized")
    require(audit["totals"]["metadata"] == 36260
            and audit["totals"]["literal_machinery"] == 27744,
            "receipt-confirmed audit arithmetic drift")
    selected = model["variants"]["catalog-widening-plus-metadata-regions"]
    require(selected["selected_for_real_link"] is True
            and selected["projection"]["remaining_combined_future_region_bytes"] == 458793,
            "selected model or Wave-3 projection drift")
    require("runtime overlay L65S shelf loader exceeds its stack-safe window" in log,
            "failed real link lacks the hard slice-gate verdict")
    require("section '.lisp65_rt_l65s' will not fit in region 'ram': overflowed by 84 bytes" in log,
            "failed real link lacks the VMA-overflow verdict")
    match = re.search(r"^\s*c356\s+\S+\s+([0-9a-f]+)\s+1\s+\.lisp65_rt_l65s$",
                      map_text, re.MULTILINE)
    require(match is not None, "failed map lacks L65S stage section")
    stage_bytes = int(match.group(1), 16)
    name_match = re.search(
        r"^\s*c356\s+\S+\s+([0-9a-f]+)\s+1\s+\.lisp65_rt_l65s_name$",
        map_text, re.MULTILINE,
    )
    require(name_match is not None, "failed map lacks L65S name section")
    name_bytes = int(name_match.group(1), 16)
    require(stage_bytes == 3326 and stage_bytes - 1792 == 1534,
            "failed stage-slice arithmetic drift")
    require(name_bytes == 1326 and name_bytes <= 1792,
            "failed name-slice arithmetic drift")

    rollback = []
    for raw in ROLLBACK_SOURCES:
        path = ROOT / raw
        worktree = path.read_bytes()
        head = git_head_bytes(raw)
        require(worktree == head, f"product rollback differs from HEAD: {raw}")
        rollback.append({"path": raw, "bytes": len(worktree), "sha256": sha(worktree)})
    shelf = load(SHELF_MANIFEST)
    require(SHELF.stat().st_size == shelf.get("shelf_bytes") == 65368,
            "restored L65S-v3 shelf length drift")
    require(shelf.get("shelf_sha256") == sha(SHELF.read_bytes()),
            "restored L65S-v3 shelf SHA drift")

    return {
        "format": "lisp65-v11-l65s-v4-one-attempt-outcome-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "hard-gate-failed-auto-fallback-to-l-lite-active",
        "claim_limit": (
            "This is a negative architecture-probe receipt. It proves the two v4 "
            "layouts and current-container reconstruction on the host, and it binds "
            "the one failed product link. It does not promote L65S-v4, authorize any "
            "capacity, or claim that unbuilt Wave-3 modules fit individually."
        ),
        "inputs": {
            "owner_contract": binding(CONTRACT),
            "metadata_audit": binding(AUDIT),
            "layout_model": binding(MODEL),
        },
        "audit_confirmation": {
            "metadata_bytes": 36260,
            "metadata_percent_of_payload_region": 55.634,
            "metadata_percent_of_whole_shelf": 55.4706,
            "literal_nodes_bytes": 17370,
            "literal_patches_bytes": 6900,
            "literal_index_bytes": 3474,
            "literal_machinery_bytes": 27744,
            "raw_string_pool_bytes": 5347,
            "string_regions_with_alignment_bytes": 5350,
        },
        "variant_assessment": {
            "catalog_widening_only_bytes": model["variants"]["catalog-widening-only"]
                ["artifact"]["bytes"],
            "widening_plus_metadata_regions_bytes": selected["artifact"]["bytes"],
            "selected": "catalog-widening-plus-metadata-regions",
            "selection_reason": (
                "It cost no shelf byte over pure widening, retained one reset-persistent "
                "identity-bound artifact, and established the C2.0 code/metadata boundary."
            ),
            "four_role_probe_envelope_remaining_bytes": selected["projection"]
                ["remaining_combined_future_region_bytes"],
        },
        "host_result": {
            "status": "passed",
            "containers_reconstructed_byteidentically": 5,
            "strict_version_and_mutation_matrix": "passed before real link",
        },
        "single_real_link": {
            "status": "failed",
            "log": binding(BUILD_LOG),
            "map": binding(FAILED_MAP),
            "hard_gates": {
                "maximum_runtime_slice": {
                    "limit_bytes": 1792,
                    "candidate_stage_bytes": stage_bytes,
                    "deficit_bytes": stage_bytes - 1792,
                    "result": "failed",
                },
                "fixed_runtime_overlay_vma": {
                    "candidate_end": "0xd054",
                    "link_region_overflow_bytes": 84,
                    "result": "failed",
                },
                "name_slice": {
                    "limit_bytes": 1792,
                    "candidate_bytes": name_bytes,
                    "headroom_bytes": 1792 - name_bytes,
                    "result": "passed",
                },
                "remaining_capacity_gates": {
                    "result": "not-reached",
                    "reason": "The seed link stopped fail-closed at the first two hard gates."
                },
            },
        },
        "automatic_fallback": {
            "selected": "Wave-3 L-lite; H/I/J and metadata shelf delivery move behind C2",
            "second_format_attempt": "forbidden",
            "reclaim_or_tuning_round": "forbidden",
            "v4_status": "design input for C2.0 only; not a product format",
            "restored_v3_shelf": binding(SHELF),
            "restored_v3_manifest": binding(SHELF_MANIFEST),
            "restored_v3_headroom_bytes": 167,
        },
        "product_source_rollback": {
            "status": "byteidentical-to-HEAD",
            "files": rollback,
        },
        "separate_owner_authorization": {
            "work": "Anonymize the 16 immediately eligible public-until-revoked names; keep bytecode on the 1.1-G kind contract.",
            "timing": "bundle with the Wave-2 repin after Wave 2; not part of the failed v4 attempt",
        },
    }


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def validate_recorded(value: dict[str, Any]) -> None:
    """Validate the archived negative result without requiring /build.

    The failed candidate was deliberately rolled back, so its full link can
    never be reconstructed from the live tree.  The receipt is the archive:
    it carries the complete log/map hashes and the exact extracted hard-gate
    measurements.  When the original ignored build captures are still
    present, check them too; a fresh checkout must not depend on them.
    """
    require(value.get("format") ==
            "lisp65-v11-l65s-v4-one-attempt-outcome-receipt-v1",
            "wrong recorded outcome format")
    require(value.get("status") ==
            "hard-gate-failed-auto-fallback-to-l-lite-active",
            "recorded fallback status drift")
    expected_inputs = {
        "owner_contract": binding(CONTRACT),
        "metadata_audit": binding(AUDIT),
        "layout_model": binding(MODEL),
    }
    require(value.get("inputs") == expected_inputs,
            "recorded outcome input binding drift")
    gates = value["single_real_link"]["hard_gates"]
    require(gates["maximum_runtime_slice"] == {
        "limit_bytes": 1792,
        "candidate_stage_bytes": 3326,
        "deficit_bytes": 1534,
        "result": "failed",
    }, "recorded stage-slice result drift")
    require(gates["fixed_runtime_overlay_vma"] == {
        "candidate_end": "0xd054",
        "link_region_overflow_bytes": 84,
        "result": "failed",
    }, "recorded fixed-VMA result drift")
    require(gates["name_slice"] == {
        "limit_bytes": 1792,
        "candidate_bytes": 1326,
        "headroom_bytes": 466,
        "result": "passed",
    }, "recorded name-slice result drift")
    for key in ("log", "map"):
        captured = value["single_real_link"][key]
        require(isinstance(captured.get("bytes"), int) and captured["bytes"] > 0,
                f"invalid archived {key} length")
        require(re.fullmatch(r"[0-9a-f]{64}", captured.get("sha256", "")) is not None,
                f"invalid archived {key} SHA")
    if BUILD_LOG.is_file():
        require(value["single_real_link"]["log"] == binding(BUILD_LOG),
                "available failed-link log differs from archive")
    if FAILED_MAP.is_file():
        require(value["single_real_link"]["map"] == binding(FAILED_MAP),
                "available failed-link map differs from archive")

    rollback = value["product_source_rollback"]
    require(rollback.get("status") == "byteidentical-to-HEAD",
            "recorded rollback status drift")
    current_rollback = []
    for raw in ROLLBACK_SOURCES:
        path = ROOT / raw
        worktree = path.read_bytes()
        require(worktree == git_head_bytes(raw),
                f"product source now differs from HEAD: {raw}")
        current_rollback.append({
            "path": raw,
            "bytes": len(worktree),
            "sha256": sha(worktree),
        })
    require(rollback.get("files") == current_rollback,
            "recorded rollback binding drift")
    if SHELF.is_file() and SHELF_MANIFEST.is_file():
        require(value["automatic_fallback"]["restored_v3_shelf"] == binding(SHELF),
                "available restored v3 shelf differs from archive")
        require(value["automatic_fallback"]["restored_v3_manifest"] ==
                binding(SHELF_MANIFEST),
                "available restored v3 manifest differs from archive")


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    validate_recorded(actual)
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args()
    value = write() if args.command == "collect" else check()
    link = value["single_real_link"]["hard_gates"]
    print("v11-l65s-v4-outcome: PASS negative-result "
          f"stage={link['maximum_runtime_slice']['candidate_stage_bytes']} "
          f"vma-overflow={link['fixed_runtime_overlay_vma']['link_region_overflow_bytes']} "
          "fallback=L-lite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
