#!/usr/bin/env python3
"""Bind the accepted GC envelope to an operation-level source attribution.

This is intentionally not a target phase timer.  The accepted hardware runs
record only collection count and whole-workload frame endpoints.  The driver
therefore rejects an invented mark/sweep time split, but binds every exact or
bounded work term that can be derived from the linked product geometry,
captured counters, and the current collector source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / "src/mem.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
WORKBENCH = ROOT / "config/workbench.mk"
LINK57 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json"
)
LINK66 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link66-bundled-hardware-measurements-receipt.json"
)
G5 = ROOT / (
    "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/"
    "g5-hardware-receipt.json"
)
G5_COUNTERS = ROOT / (
    "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/"
    "g5/counters/after_gc_envelope.txt"
)
G5_C2D = ROOT / (
    "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/"
    "g5/runstop/c2d-before.bin"
)
SYMBOL_HOST = ROOT / "build/reports/workbench/gc-symbol-scan-timing.json"
OUT = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/"
    "phase-m/gc-envelope/latest.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-phase-m2-gc-envelope-attribution-receipt.json"
)
FORMAT = "lisp65-c2.2-phase-m2-gc-envelope-attribution-v1"

HEAP_CELLS = 48
EXT_CELLS = 1024
GC_ROOTS = 128
MAX_SYM = 752
C2_ROOT_CAP = 1536
C2_ROOTS_PER_BLOCK = 16


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def hardware_truth() -> dict[str, Any]:
    link57 = load(LINK57)["rows"]["gc_blockreads_and_frames"]
    link66 = load(LINK66)["measurements"]["gc_envelope_informative"]
    g5_case = next(
        row for row in load(G5)["cases"]
        if row["id"] == "runtime/gc-envelope-informative"
    )
    require(
        link57["workload_envelope_frames"] == 82
        and link57["collections"] == 2
        and link57["blockreads_executed"] == 192
        and link57["isolated_frames_per_collection_claim"] == "not-made",
        "Link-57 GC evidence drift",
    )
    require(
        link66["frames"] == 88
        and link66["collections"] == 1
        and link66["blockreads_per_collection"] == 96,
        "Link-66 GC evidence drift",
    )
    require(
        "frames=89" in g5_case["value_string"]
        and "collections=1" in g5_case["value_string"]
        and "blockreads=96" in g5_case["value_string"],
        "final G5 GC evidence drift",
    )
    return {
        "premise_correction": {
            "rejected": "82 frames per collection with 192 block reads",
            "reason": (
                "Link 57 measured an 82-frame workload envelope containing "
                "two collections and explicitly made no isolated "
                "frames-per-collection claim."
            ),
            "current_product_observation":
                "89 frames; one collection; 96 contract block reads",
        },
        "observations": [
            {
                "identity": "Link57",
                "workload_frames": 82,
                "collections": 2,
                "contract_block_reads_total": 192,
                "isolated_collection_frames": None,
                "status": "informative-no-isolated-claim",
            },
            {
                "identity": "Link66",
                "workload_frames": 88,
                "collections": 1,
                "contract_block_reads_total": 96,
                "isolated_collection_frames": 88,
                "status": "informative-no-limit",
            },
            {
                "identity": "final-G5",
                "workload_frames": 89,
                "collections": 1,
                "contract_block_reads_total": 96,
                "isolated_collection_frames": 89,
                "status": "informative-no-limit",
            },
        ],
    }


def captured_geometry() -> dict[str, Any]:
    counters = G5_COUNTERS.read_text(encoding="utf-8")
    match = re.search(r"^nsym=(\d+)$", counters, re.MULTILINE)
    require(match is not None, "G5 symbol count absent")
    symbols = int(match.group(1))
    c2d = G5_C2D.read_bytes()
    require(len(c2d) == 33840 and c2d[:4] == b"C2D\0",
            "G5 C2D identity drift")
    committed_roots = struct.unpack_from("<H", c2d, 24)[0]
    root_capacity = struct.unpack_from("<H", c2d, 26)[0]
    require(
        symbols == 480
        and committed_roots == 283
        and root_capacity == C2_ROOT_CAP,
        "G5 captured geometry drift",
    )
    return {
        "hot_cells": HEAP_CELLS,
        "hot_usable_cells": HEAP_CELLS - 1,
        "external_cells": EXT_CELLS,
        "total_cell_slots": HEAP_CELLS + EXT_CELLS,
        "mark_bitmap_bytes": (HEAP_CELLS + EXT_CELLS + 7) // 8,
        "shadow_root_capacity": GC_ROOTS,
        "symbols_at_G5_measurement": symbols,
        "symbol_capacity": MAX_SYM,
        "committed_C2D_roots_in_captured_plane": committed_roots,
        "C2D_root_capacity": root_capacity,
        "measurement_contract_root_scan": {
            "roots": C2_ROOT_CAP,
            "roots_per_32_byte_block": C2_ROOTS_PER_BLOCK,
            "blocks": C2_ROOT_CAP // C2_ROOTS_PER_BLOCK,
            "bytes": C2_ROOT_CAP * 2,
            "why_capacity_not_committed_count": (
                "The accepted workload observes the high-edge pending-root "
                "contract during transient evaluation; its receipt binds 96 "
                "blocks. The quiescent captured header has 283 committed roots."
            ),
        },
    }


def source_gate() -> dict[str, Any]:
    mem = MEM.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")
    required_defines = (
        "WORKBENCH_HEAP_CELLS := 48",
        "-DGC_ROOTS=128",
        "-DEXT_CELLS=1024",
        "-DLISP65_NURSERY_HYSTERESIS=192",
        "-DLISP65_STRING_ARENA",
        "-DLISP65_SYMVAL_EXT",
        "-DLISP65_SYMFN_EXT",
        "-DMAX_SYM=752",
    )
    require(all(token in workbench for token in required_defines),
            "Workbench GC geometry define drift")
    phase_tokens = (
        "HB(3); LA(17);",
        "MARK_CLEAR();",
        "c2_product_gc_mark_roots();",
        "LA(18);",
        "n = sym_count();",
        "gc_mark1(sym_value(sym));",
        "gc_mark1(sym_function(sym));",
        "LA(19);",
        "gc_mark_children_hot(i)",
        "gc_mark_children_ext(i)",
        "str_arena_compact();",
        "for (i = alloc_high; i > lo; i--)",
        "LA(20);",
    )
    positions = [mem.find(token) for token in phase_tokens]
    require(all(position >= 0 for position in positions)
            and positions == sorted(positions),
            "collector phase order/source seam drift")
    root_tokens = (
        "uint8_t b[32];",
        "scan = c2_committed_roots",
        "if (c2_pending_roots > scan) scan = c2_pending_roots;",
        "if (n > (uint16_t)(sizeof b / 2u))",
        "c2_stream_c2d_read(",
        "c2_facade_gc_mark(",
    )
    require(all(token in runtime for token in root_tokens),
            "C2D root block walker drift")
    return {
        "collector_phase_order": [
            "Q/17 entry-and-mark-clear",
            "shadow-plus-C2D-roots",
            "R/18 roots-marked",
            "symbol-roots",
            "S/19 symbols-marked",
            "fixed-point-hot-and-external-trace",
            "string-arena-compaction",
            "hot-and-allocated-external-sweep",
            "T/20 sweep-finished",
        ],
        "phase_markers_present": [17, 18, 19, 20],
        "compile_defines_bound": list(required_defines),
    }


def operation_ledger(geometry: dict[str, Any]) -> dict[str, Any]:
    symbols = geometry["symbols_at_G5_measurement"]
    root_blocks = geometry["measurement_contract_root_scan"]["blocks"]
    root_values = geometry["measurement_contract_root_scan"]["roots"]
    exact_min_jobs = root_blocks + symbols
    return {
        "entry_and_root_scan": {
            "mark_bitmap_clear_bytes": geometry["mark_bitmap_bytes"],
            "shadow_roots_marked": {
                "minimum": 0,
                "maximum": GC_ROOTS,
                "actual": None,
            },
            "C2D_root_block_reads": root_blocks,
            "C2D_root_bytes": root_values * 2,
            "C2D_root_values_marked": root_values,
            "classification": (
                "Exact for the accepted high-edge workload contract. Reads "
                "are already amortized at sixteen obj values per DMA."
            ),
        },
        "symbol_root_scan": {
            "symbols_visited": symbols,
            "symval_two_byte_DMA_reads": symbols,
            "symfn_two_byte_DMA_reads": {
                "minimum": 0,
                "maximum": symbols,
                "actual": None,
                "condition": "only entries selected by the Bank-0 symfnptr bitmap",
            },
            "minimum_symbol_DMA_payload_bytes": symbols * 2,
            "classification": (
                "The 480 symval jobs are source-forced and exact for the G5 "
                "symbol count. Function-cell jobs remain unmeasured."
            ),
        },
        "fixed_point_trace": {
            "hot_slots_examined_per_pass": HEAP_CELLS - 1,
            "passes": None,
            "external_interval_per_pass": "[ext_mark_lo, ext_mark_hi]",
            "external_type_child_DMA_jobs": None,
            "classification": (
                "Bounds and loop form are proven; live graph, interval and "
                "pass count were not captured."
            ),
        },
        "string_arena_compaction": {
            "mark_slots_considered": HEAP_CELLS + EXT_CELLS - 1,
            "frozen_prefix_copy_bytes": None,
            "live_runtime_string_copy_bytes": None,
            "external_cell_metadata_DMA_jobs": None,
            "classification": (
                "The full mark-slot loop and mandatory frozen-prefix copy "
                "are source-proven; runtime byte volume was not captured."
            ),
        },
        "sweep": {
            "hot_slots_considered": HEAP_CELLS - 1,
            "external_allocated_interval": "(max(gc_frozen,47), alloc_high]",
            "external_dead_cell_two_byte_writes": None,
            "classification": (
                "Hot sweep width is exact. External high-water, frozen "
                "floor and dead-cell count were not captured."
            ),
        },
        "DMA_lower_bound_for_measured_collection": {
            "jobs": exact_min_jobs,
            "composition": {
                "C2D_32_byte_root_reads": root_blocks,
                "Bank5_2_byte_symval_reads": symbols,
            },
            "payload_bytes": root_values * 2 + symbols * 2,
            "not_included": [
                "pointer-valued symfn reads",
                "external heap traversal reads",
                "string-arena copies and external metadata reads/writes",
                "external sweep writes",
                "active export-journal roots",
            ],
            "interpretation": (
                "The familiar 96 block reads are not total collector DMA. "
                "The current source and captured symbol count prove at least "
                f"{exact_min_jobs} DMA jobs before graph traversal, arena "
                "movement, or sweep writes."
            ),
        },
    }


def host_symbol_gate() -> dict[str, Any]:
    row = load(SYMBOL_HOST)
    require(
        row.get("status") == "pass"
        and row["linear_fit"]["r_squared"] >= 0.97
        and row["build"]["max_symbols"] == MAX_SYM,
        "host symbol-scan linearity gate drift",
    )
    return {
        "status": "passed-linear-work-term-only",
        "r_squared": row["linear_fit"]["r_squared"],
        "scope": row["scope"],
        "target_timing_claim": False,
        "authority": bind(SYMBOL_HOST),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        hardware = hardware_truth()
        geometry = captured_geometry()
        source = source_gate()
        operations = operation_ledger(geometry)
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-28",
            "status":
                "passed-operation-attribution-phase-time-split-unmeasured",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "hardware_truth": hardware,
            "captured_geometry": geometry,
            "source_phase_model": source,
            "operation_ledger": operations,
            "host_symbol_scan_gate": host_symbol_gate(),
            "inherent_vs_addressable": {
                "inherent_semantics": [
                    "mark every live shadow/C2D/symbol root",
                    "trace the live object graph",
                    "reclaim unreachable runtime cells",
                    "preserve or relocate live runtime string bytes",
                ],
                "geometry_bound_work": [
                    "47 hot slots per fixed-point pass and hot sweep",
                    "up to 128 live shadow-root slots",
                    "1536 high-edge C2D roots in 96 already-batched reads",
                    "480 symbol rows in the measured final-G5 state",
                ],
                "addressable_work_terms_not_yet_mechanisms": [
                    (
                        "480 separate two-byte symval reads, plus an "
                        "unmeasured number of separate symfn reads"
                    ),
                    (
                        "full 1071-slot arena mark scan and unconditional "
                        "frozen-prefix copy"
                    ),
                    (
                        "runtime-dependent repeated external-cell reads in "
                        "the fixed-point trace"
                    ),
                    (
                        "one two-byte write per dead allocated external cell "
                        "during sweep"
                    ),
                ],
            },
            "phase_time_attribution": {
                "mark_seconds": None,
                "root_scan_seconds": None,
                "symbol_scan_seconds": None,
                "fixed_point_seconds": None,
                "arena_compaction_seconds": None,
                "sweep_seconds": None,
                "reason": (
                    "Accepted hardware receipts contain only whole-workload "
                    "frame endpoints and collection counters. LA(17..20) "
                    "source markers prove phase order but were not timestamped "
                    "in those runs. Assigning the 88/89 frames to phases would "
                    "be an invented measurement."
                ),
                "existing_future_measurement_seam":
                    "LA(17), LA(18), LA(19), LA(20)",
            },
            "halt_recommendation": {
                "require_seam": (
                    "Commission a bounded host-first idempotence cut: preserve "
                    "all first-load validation, but target at least 90% fewer "
                    "VM instructions and Prim-67 reads on an already-loaded "
                    "generation/identity. Keep it Bank-2-only; no resident "
                    "capacity negotiation."
                ),
                "GC": (
                    "Do not commission a collector mechanism yet. First bind "
                    "target phase deltas at the existing 17/18/19/20 seam in "
                    "the final bundled device session; include symfn pointer "
                    "count, ext_mark interval/pass count, arena copied bytes "
                    "and dead-ext writes. Then choose one measured work term."
                ),
                "why": (
                    "M1 measures duplicated resolver work directly. M2 proves "
                    "several large GC work terms but cannot assign target "
                    "frames among them from existing evidence."
                ),
            },
            "authority": {
                "collector_source": bind(MEM),
                "C2_root_walker_source": bind(RUNTIME),
                "workbench_geometry": bind(WORKBENCH),
                "Link57": bind(LINK57),
                "Link66": bind(LINK66),
                "final_G5": bind(G5),
                "final_G5_counters": bind(G5_COUNTERS),
                "final_G5_C2D": bind(G5_C2D),
                "driver": bind(Path(__file__).resolve()),
            },
            "claim_limit": (
                "Whole-envelope target observations plus source- and "
                "capture-derived operation counts only. No mark/root/sweep "
                "target time split, GC bottleneck claim, optimization choice, "
                "product edit, link, or new hardware result is claimed."
            ),
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
        args.receipt.write_text(encoded, encoding="utf-8")
        OUT.write_text(encoded, encoding="utf-8")
        print(
            "c2-phase-m-gc-envelope: PASS "
            "target=89f/1gc roots=96x32B symbols=480 "
            f"min_dma_jobs={operations['DMA_lower_bound_for_measured_collection']['jobs']} "
            "phase_time=unmeasured"
        )
        return 0
    except (AttributionError, ValueError, StopIteration) as error:
        print(
            "c2-phase-m-gc-envelope: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
