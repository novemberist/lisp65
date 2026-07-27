#!/usr/bin/env python3
"""Artifact-only completion of the CPU-to-Chip WPLTO First Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_matrix_addenda_wplto_first_red as MAPS  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PROVISIONAL = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-product-shaped-wplto-receipt.json")
INTERNAL = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-product-shaped-wplto-internal.json")
SOURCE = ROOT / (
    "build/c2.2/cpu-chip-write-completion/source-gate-wplto-receipt.json")
BASE_MAP = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto/"
    "resident-island-seed.prg.map")
PROBE_DIR = ROOT / (
    "build/c2.2/substitution/cpu-chip-write-completion-product-shaped-wplto")
PROBE_MAP = PROBE_DIR / "resident-island-seed.prg.map"
STDERR = PROBE_DIR / "resident-island-seed.prg.link.stderr.txt"
RECEIPT = EVIDENCE / (
    "c2.2-cpu-chip-write-completion-capacity-first-red-receipt.json")


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    require(not RECEIPT.exists(), "First-Red completion is one-shot")
    provisional = json.loads(PROVISIONAL.read_text(encoding="utf-8"))
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    before = MAPS.map_rows(BASE_MAP)
    after = MAPS.map_rows(PROBE_MAP)
    stderr = STDERR.read_text(encoding="utf-8")
    names = (
        "stage_copy", "header", "journal_prepare", "publish_clear",
        "rollback_unpublish", "rollback_finalize")
    phases = []
    payload_delta = 0
    packed_delta = 0
    for name in names:
        section = f".lisp65_rt_c2append_{name}"
        old = before[section]["bytes"]
        new = after[section]["bytes"]
        old_packed = (old + 255) & ~255
        new_packed = (new + 255) & ~255
        phases.append({
            "name": name.replace("_", "-"),
            "before_bytes": old,
            "after_bytes": new,
            "delta_bytes": new - old,
            "slice_cap_bytes": 1792,
            "over_cap_bytes": max(0, new - 1792),
            "before_packed_bytes": old_packed,
            "minimum_after_packed_bytes": new_packed,
            "minimum_pack_delta_bytes": new_packed - old_packed,
        })
        payload_delta += new - old
        packed_delta += new_packed - old_packed
    require(
        provisional["status"].startswith("FIRST RED")
        and source["mutation_count"] == 14
        and internal["execution_accounting"]["product_closure_links"] == 0
        and "journal_prepare exceeds its stack-safe window" in stderr
        and "publish_clear exceeds its stack-safe window" in stderr
        and "rollback_finalize exceeds its stack-safe window" in stderr
        and "overflowed by 109 bytes" in stderr
        and payload_delta == 3296
        and packed_delta == 3840,
        "WPLTO First-Red evidence drift")

    old_text = before[".text"]
    new_text = after[".text"]
    text_delta = new_text["bytes"] - old_text["bytes"]
    old_bss = before[".bss"]
    new_bss = after[".bss"]
    old_bss_headroom = 215
    bss_start_delta = new_bss["address"] - old_bss["address"]
    e000_old = before[".lisp65_c2_kernal_window.c2_resident"]
    e000_new = after[".lisp65_c2_kernal_window.c2_resident"]
    fixed_old = before[".lisp65_c2_fixed_bank0_code"]
    fixed_new = after[".lisp65_c2_fixed_bank0_code"]
    island_old = before[".lisp65_resident_island"]
    island_new = after[".lisp65_resident_island"]
    baseline_session = 65438
    minimum_session = baseline_session + packed_delta

    value = {
        "format": "lisp65-c2-cpu-chip-write-completion-capacity-first-red-v1",
        "recorded_on": "2026-07-24",
        "status": "FIRST RED: three cold slices, text-noise wall and Session aggregate exceed their contracts",
        "promotable": False,
        "authority": {
            "contract_source_model": bind(SOURCE),
            "provisional_WPLTO_receipt": bind(PROVISIONAL),
            "WPLTO_internal": bind(INTERNAL),
            "baseline_map": bind(BASE_MAP),
            "probe_map": bind(PROBE_MAP),
            "linker_stderr": bind(STDERR),
            "completion_driver": bind(Path(__file__)),
        },
        "semantic_probe": {
            "status": source["status"],
            "mutations_rejected": source["mutation_count"],
            "same_buffer_readbacks_remaining": 0,
            "cutpoint4_model_delta_bytes":
                source["interleaving_fixture"][
                    "cutpoint4_freezer_delta_bytes"],
            "exact_abort_model": {
                "bank2": source["interleaving_fixture"][
                    "bank2_exact_after_abort"],
                "bank5": source["interleaving_fixture"][
                    "bank5_exact_after_abort"],
                "pending_jobs": source["interleaving_fixture"][
                    "pending_jobs_after_abort"],
            },
        },
        "slice_attribution": phases,
        "slice_first_reds": [
            {"name": "journal-prepare", "bytes": 1898,
             "cap": 1792, "over_bytes": 106},
            {"name": "publish-clear", "bytes": 1949,
             "cap": 1792, "over_bytes": 157},
            {"name": "rollback-finalize", "bytes": 3351,
             "cap": 1792, "over_bytes": 1559},
        ],
        "session_aggregate": {
            "baseline_bytes": baseline_session,
            "baseline_headroom_bytes": 98,
            "raw_changed_slice_payload_delta_bytes": payload_delta,
            "minimum_pack_delta_bytes": packed_delta,
            "minimum_product_shaped_bytes_before_added_catalog_cost":
                minimum_session,
            "minimum_overflow_bytes_before_added_catalog_cost":
                minimum_session - 65536,
            "note":
                "The three over-cap bodies require semantic splits; extra "
                "catalog entries fit below the current 1792-byte payload "
                "offset but cannot reduce this lower bound.",
        },
        "walls_from_failed_WPLTO_map": {
            "bank0_text": {
                "baseline_headroom_bytes": 37,
                "delta_bytes": text_delta,
                "measured_headroom_bytes": 37 - text_delta,
                "required_noise_headroom_bytes": 32,
                "deficit_bytes": 32 - (37 - text_delta),
            },
            "ordinary_bank0_bss": {
                "baseline_headroom_bytes": old_bss_headroom,
                "section_size_delta_bytes":
                    new_bss["bytes"] - old_bss["bytes"],
                "section_start_delta_bytes": bss_start_delta,
                "projected_headroom_bytes":
                    old_bss_headroom - bss_start_delta,
            },
            "fixed_hot_block": {
                "baseline_headroom_bytes": 4,
                "section_geometry_unchanged": fixed_old == fixed_new,
            },
            "resident_island": {
                "baseline_headroom_bytes": 5,
                "section_size_unchanged":
                    island_old["bytes"] == island_new["bytes"],
            },
            "E000": {
                "baseline_headroom_bytes": 55,
                "required_floor_bytes": 54,
                "section_geometry_unchanged": e000_old == e000_new,
                "byteidentity_claimed": False,
                "reason":
                    "the cap failure prevented a final ELF; source and map "
                    "prove zero seam/geometry movement, not final bytes",
            },
        },
        "linker_first_red": {
            "completed_final_ELF": False,
            "physical_ram_region_overflow_bytes": 109,
            "completed_product_closure_links": 0,
            "whole_program_LTO_attempts": 1,
        },
        "triage_boundaries": [
            "journal-prepare: split C2J write-completion from rollback preparation",
            "publish-clear: restore the semantic separation of publication and scratch/C2J clearing",
            "rollback-finalize: split Bank-5 suffix wipe, Bank-2 suffix wipe and final restoration fence",
            "aggregate: recover at least 3742 packed bytes after those splits; splitting alone cannot close it",
            "ordinary text: recover 28 bytes to restore the standing 32-byte LTO-noise reserve",
        ],
        "execution_accounting": {
            "whole_program_LTO_attempts": 1,
            "completed_product_closure_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
        },
        "verdict": {
            "C1": "OPEN",
            "matrix_gate": "blocked",
            "acceptance_chain": "blocked",
            "next_action": "Class-C placement/aggregate triage; no second WPLTO authorized",
        },
        "claim_limit":
            "Semantic/source and failed-WPLTO capacity evidence only. No "
            "product link, hardware, C1 closure, matrix-gate or acceptance claim.",
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-cpu-chip-write-completion-first-red-complete: PASS "
        f"payload_delta={payload_delta} packed_delta={packed_delta} "
        f"aggregate_over={minimum_session - 65536}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-cpu-chip-write-completion-first-red-complete: FIRST RED: "
            + str(error),
            file=sys.stderr)
        raise SystemExit(2)
