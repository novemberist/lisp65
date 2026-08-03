#!/usr/bin/env python3
"""Host-first accounting for the released editor's per-key hot path.

This lane executes the generated Workbench IDE composition through the same
P0 host VM that backs the IDE bytecode reports.  It counts dynamic VM
instructions and Lisp heap-cell allocations separately for `ide-step` and
`ide-render`.  Target collection *placement* is then derived from the bound
192-allocation nursery rule for every possible incoming nursery phase.

It is not a target timer.  In particular, screen I/O and collection phase
costs remain external target measurements.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
from ide_bytecode_dynamic_report import Runtime, TraceCollector  # noqa: E402


DEFAULT_SUITE = (
    ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
)
DEFAULT_OUT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/post-release/"
    "v125-editor-input-latency-host-accounting-receipt.json"
)
FORMAT = "lisp65-v1.2.5-editor-input-latency-host-accounting-v1"
BURST = (
    "(defun editor-latency-sample (x) "
    "(while (< x 100) (setq x (+ x 1))) x) "
    "(editor-latency-sample 0) "
)
# One complete 79-column fill cycle plus the first wrapped character.  Longer
# monotonic host runs would exceed the P0 model's 15-bit pointer domain because
# that model deliberately does not collect; a fresh second run covers the
# coalesced schedule independently.
BURST_TEXT = (BURST * 2)[:80]
NURSERY_THRESHOLD = 192
TARGET_COLLECTION_FRAMES = 89
TARGET_FRAME_US = 20_000
HISTORICAL_CYCLES_PER_VM_INSTRUCTION = 1_100
TARGET_CPU_HZ = 40_000_000


class AccountingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AccountingError(message)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "bytes": len(data), "sha256": sha_bytes(data)}


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def summary(values: list[int]) -> dict[str, int | float]:
    require(bool(values), "cannot summarize an empty vector")
    ordered = sorted(values)
    return {
        "count": len(values),
        "sum": sum(values),
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
        "mean": sum(values) / len(values),
    }


def allocation_types(heap: B.Heap, start: int, end: int) -> dict[str, int]:
    counts = Counter(cell.type for cell in heap.cells[start:end])
    return dict(sorted(counts.items()))


def run_call(
    runtime: Runtime, name: str, args: list[int], label: str,
) -> tuple[int, TraceCollector, dict[str, int]]:
    trace = TraceCollector(label, runtime.heap)
    before = len(runtime.heap.cells)
    result = runtime.run_named(name, args, trace=trace)
    after = len(runtime.heap.cells)
    return result, trace, allocation_types(runtime.heap, before, after)


def allocation_count(types: dict[str, int]) -> int:
    return sum(types.values())


def add_types(left: Counter[str], values: dict[str, int]) -> None:
    left.update(values)


def simulate_collections(
    allocations_per_key: list[int], initial_phase: int,
) -> list[int]:
    """Place collections under mem.c's pre-allocation threshold check."""
    require(
        0 <= initial_phase < NURSERY_THRESHOLD,
        "nursery phase outside threshold",
    )
    phase = initial_phase
    per_key: list[int] = []
    for count in allocations_per_key:
        collections = 0
        for _ in range(count):
            if phase >= NURSERY_THRESHOLD:
                collections += 1
                phase = 0
            phase += 1
        per_key.append(collections)
    return per_key


def collection_envelope(allocations_per_key: list[int]) -> dict[str, Any]:
    lanes = [
        simulate_collections(allocations_per_key, phase)
        for phase in range(NURSERY_THRESHOLD)
    ]
    totals = [sum(lane) for lane in lanes]
    keys = [sum(value > 0 for value in lane) for lane in lanes]
    maxima = [max(lane) for lane in lanes]
    normalized = lanes[0]
    distribution = Counter(normalized)
    return {
        "incoming_phases_exhaustively_checked": NURSERY_THRESHOLD,
        "total_collections": summary(totals),
        "keys_with_at_least_one_collection": summary(keys),
        "maximum_collections_on_one_key": summary(maxima),
        "normalized_phase_zero": {
            "total_collections": sum(normalized),
            "keys_with_at_least_one_collection": sum(
                value > 0 for value in normalized
            ),
            "per_key_distribution": {
                str(key): value for key, value in sorted(distribution.items())
            },
            "per_key": normalized,
        },
        "steady_state_collections_per_key": (
            sum(allocations_per_key)
            / NURSERY_THRESHOLD
            / len(allocations_per_key)
        ),
    }


def warm_state(runtime: Runtime) -> int:
    """Enter the ordinary modified-buffer steady state before accounting."""
    state = runtime.make_state([""], rendered=True)
    event = runtime.key_event(ord("w"))
    state = runtime.run_named("ide-step", [state, event])
    state = runtime.run_named("ide-render", [state])
    return state


def run_schedule(
    suite: Path, batch_size: int, max_steps: int,
) -> dict[str, Any]:
    runtime = Runtime(suite, max_steps=max_steps)
    state = warm_state(runtime)
    rows: list[dict[str, Any]] = []
    pending: list[int] = []

    for index, character in enumerate(BURST_TEXT):
        event_start = len(runtime.heap.cells)
        event = runtime.key_event(ord(character))
        event_types = allocation_types(
            runtime.heap, event_start, len(runtime.heap.cells)
        )
        state, step_trace, step_types = run_call(
            runtime, "ide-step", [state, event], f"key-{index}-step"
        )
        row = {
            "index": index,
            "character_code": ord(character),
            "column_before_wrap_model": (index % 79) + 1,
            "event_allocations": allocation_count(event_types),
            "event_allocation_types": event_types,
            "step_instructions": step_trace.steps,
            "step_symfn_resolutions": sum(
                count
                for (kind, _target, _argc), count
                in step_trace.call_counts.items()
                if kind in ("CALL", "TAILCALL")
            ),
            "step_allocations": allocation_count(step_types),
            "step_allocation_types": step_types,
            "step_max_call_depth": step_trace.max_depth,
            "rendered_after_key": False,
            "render_instructions": 0,
            "render_symfn_resolutions": 0,
            "render_allocations": 0,
            "render_allocation_types": {},
            "render_max_call_depth": 0,
        }
        rows.append(row)
        pending.append(index)

        if len(pending) == batch_size or index == len(BURST_TEXT) - 1:
            state, render_trace, render_types = run_call(
                runtime, "ide-render", [state], f"key-{index}-render"
            )
            row["rendered_after_key"] = True
            row["render_instructions"] = render_trace.steps
            row["render_symfn_resolutions"] = sum(
                count
                for (kind, _target, _argc), count
                in render_trace.call_counts.items()
                if kind in ("CALL", "TAILCALL")
            )
            row["render_allocations"] = allocation_count(render_types)
            row["render_allocation_types"] = render_types
            row["render_max_call_depth"] = render_trace.max_depth
            pending.clear()

    for row in rows:
        row["total_instructions"] = (
            row["step_instructions"] + row["render_instructions"]
        )
        row["total_allocations"] = (
            row["event_allocations"]
            + row["step_allocations"]
            + row["render_allocations"]
        )

    allocations = [row["total_allocations"] for row in rows]
    instructions = [row["total_instructions"] for row in rows]
    step_instructions = [row["step_instructions"] for row in rows]
    render_instructions = [row["render_instructions"] for row in rows]
    event_allocations = [row["event_allocations"] for row in rows]
    step_allocations = [row["step_allocations"] for row in rows]
    render_allocations = [row["render_allocations"] for row in rows]
    alloc_types: Counter[str] = Counter()
    for row in rows:
        add_types(alloc_types, row["event_allocation_types"])
        add_types(alloc_types, row["step_allocation_types"])
        add_types(alloc_types, row["render_allocation_types"])

    collection_model = collection_envelope(allocations)
    collections_per_key = collection_model["steady_state_collections_per_key"]
    step_mean = sum(step_instructions) / len(rows)
    render_mean = sum(render_instructions) / len(rows)
    instruction_us = (
        HISTORICAL_CYCLES_PER_VM_INSTRUCTION * 1_000_000 / TARGET_CPU_HZ
    )
    return {
        "batch_size": batch_size,
        "keys": len(rows),
        "renders": sum(row["rendered_after_key"] for row in rows),
        "dynamic_instructions": {
            "step": summary(step_instructions),
            "render_charged_to_batch_terminal_key": summary(
                render_instructions
            ),
            "total_charged_to_key": summary(instructions),
        },
        "allocations": {
            "event": summary(event_allocations),
            "step": summary(step_allocations),
            "render_charged_to_batch_terminal_key": summary(
                render_allocations
            ),
            "total_charged_to_key": summary(allocations),
            "types": dict(sorted(alloc_types.items())),
        },
        "call_depth": {
            "step_maximum": max(row["step_max_call_depth"] for row in rows),
            "render_maximum": max(
                row["render_max_call_depth"] for row in rows
            ),
        },
        "target_nursery_collection_model": collection_model,
        "bounded_time_projection": {
            "historical_vm_instruction_microseconds": instruction_us,
            "mean_step_microseconds_excluding_native_io_and_gc": (
                step_mean * instruction_us
            ),
            "mean_render_microseconds_excluding_native_io_and_gc": (
                render_mean * instruction_us
            ),
            "mean_vm_microseconds_per_key_excluding_native_io_and_gc": (
                (step_mean + render_mean) * instruction_us
            ),
            "collection_frames": TARGET_COLLECTION_FRAMES,
            "collection_microseconds": (
                TARGET_COLLECTION_FRAMES * TARGET_FRAME_US
            ),
            "steady_state_projected_collection_frames_per_key": (
                collections_per_key * TARGET_COLLECTION_FRAMES
            ),
            "steady_state_projected_collection_microseconds_per_key": (
                collections_per_key
                * TARGET_COLLECTION_FRAMES
                * TARGET_FRAME_US
            ),
            "claim_limit": (
                "VM and GC time figures combine host counts with historical "
                "target constants. Native screen I/O is excluded; this is a "
                "cost projection, not a target timing measurement."
            ),
        },
        "per_key": rows,
    }


def build_receipt(suite: Path, max_steps: int) -> dict[str, Any]:
    require(
        len(BURST_TEXT) == 80
        and all(32 <= ord(character) <= 126 for character in BURST_TEXT),
        "representative burst drift",
    )
    serial = run_schedule(suite, batch_size=1, max_steps=max_steps)
    coalesced = run_schedule(suite, batch_size=10, max_steps=max_steps)

    serial_gc = serial["target_nursery_collection_model"][
        "steady_state_collections_per_key"
    ]
    coalesced_gc = coalesced["target_nursery_collection_model"][
        "steady_state_collections_per_key"
    ]
    serial_alloc = serial["allocations"]["total_charged_to_key"]["mean"]
    coalesced_alloc = coalesced["allocations"][
        "total_charged_to_key"
    ]["mean"]
    require(
        serial["keys"] == 80
        and coalesced["keys"] == 80
        and serial["renders"] == 80
        and coalesced["renders"] == 8
        and serial["allocations"]["event"]["minimum"] == 3
        and serial["allocations"]["event"]["maximum"] == 3
        and serial["allocations"]["step"]["minimum"] > 0
        and serial["dynamic_instructions"]["step"]["minimum"] > 0
        and serial_gc > coalesced_gc
        and serial_alloc > coalesced_alloc,
        "editor accounting witness drift",
    )

    return {
        "format": FORMAT,
        "recorded_on": "2026-07-31",
        "status": "passed-host-attribution",
        "scope": {
            "product_bytes_changed": 0,
            "product_links_created": 0,
            "hardware_contacts": 0,
            "target_timing_claimed": False,
        },
        "inputs": {
            "measurement_tool": bind(Path(__file__)),
            "generated_product_ide_suite": bind(suite),
            "owner_report": bind(
                ROOT
                / "docs/planning/"
                "editor-input-latency-owner-report-2026-07-30.md"
            ),
            "editor_buffer": bind(ROOT / "lib/ide-buffer.lisp"),
            "editor_ui": bind(ROOT / "lib/ide-ui.lisp"),
            "editor_syntax": bind(ROOT / "lib/ide-syntax.lisp"),
            "editor_keymap": bind(ROOT / "lib/ide-keymap-generated.lisp"),
            "p0_vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
            "dynamic_runner": bind(
                ROOT / "tools/host-lisp/ide_bytecode_dynamic_report.py"
            ),
            "workbench_geometry": bind(ROOT / "config/workbench.mk"),
            "collector": bind(ROOT / "src/mem.c"),
            "target_gc_authority": bind(
                ROOT
                / "tests/bytecode/dialect-v2/evidence/"
                "architecture-blocks/"
                "c2.2-v1.2.2-g2-gc-work-attribution-receipt.json"
            ),
            "released_product_receipt": bind(
                ROOT
                / "tests/bytecode/dialect-v2/evidence/post-release/"
                "v125-public-publication-receipt-20260731.json"
            ),
        },
        "workload": {
            "characters": len(BURST_TEXT),
            "sha256": sha_bytes(BURST_TEXT.encode("ascii")),
            "text": BURST_TEXT,
            "warmup": (
                "cold render plus one unmeasured printable edit/render; "
                "accounting begins with a modified warm buffer"
            ),
            "serial_route": "one ide-step plus one ide-render per key",
            "coalesced_route": (
                "ten ide-step calls followed by one ide-render, matching the "
                "KERNAL buffer capacity and %ide-drain-pending policy"
            ),
        },
        "bound_constants": {
            "hot_cells": 48,
            "extended_cells": 1024,
            "nursery_allocation_threshold": NURSERY_THRESHOLD,
            "target_collection_frames": TARGET_COLLECTION_FRAMES,
            "target_frame_microseconds": TARGET_FRAME_US,
            "historical_cycles_per_vm_instruction": (
                HISTORICAL_CYCLES_PER_VM_INSTRUCTION
            ),
            "target_cpu_hz": TARGET_CPU_HZ,
        },
        "measurements": {
            "serial_render_every_key": serial,
            "coalesced_ten_keys_per_render": coalesced,
        },
        "answer": {
            "distribution": (
                "fast-with-large-periodic-pauses, not uniformly slow: "
                "ordinary VM work is bounded, while temporary redisplay "
                "allocations cross the 192-allocation nursery threshold "
                "repeatedly; coalescing reduces but does not remove crossings"
            ),
            "dominant_mechanism": (
                "redisplay allocation churn induces target collections; "
                "the 89-frame collection envelope dominates the historical "
                "VM-step projection"
            ),
            "serial_allocations_per_key": serial_alloc,
            "serial_steady_state_collections_per_key": serial_gc,
            "coalesced_allocations_per_key": coalesced_alloc,
            "coalesced_steady_state_collections_per_key": coalesced_gc,
            "reopening_condition": (
                "met: the host accounting confirms periodic GC pauses as a "
                "credible dropped-input mechanism; reopen the parked "
                "gc/room/error instrument lane with room first"
            ),
        },
        "priced_levers": [
            {
                "priority": 1,
                "lever": "remove per-render typed-line materialization",
                "evidence": (
                    "render allocations rise with cursor column; the serial "
                    "route's allocation mean and GC projection quantify the "
                    "direct lever"
                ),
                "product_shape": "Bank-2/IDE-library change",
            },
            {
                "priority": 2,
                "lever": "retain and strengthen render coalescing",
                "evidence": (
                    "ten-key batches lower allocations and projected "
                    "collections per key, but pauses remain batch-clustered"
                ),
                "product_shape": "existing Lisp orchestration",
            },
            {
                "priority": 3,
                "lever": "instrument GC with room before collector changes",
                "evidence": (
                    "89 frames dominate the projection, but the dominant "
                    "collector phase remains unattributed on target"
                ),
                "product_shape": "parked cold overlay instrument",
            },
            {
                "priority": 4,
                "lever": "reduce VM dispatch/call depth",
                "evidence": (
                    "step/render instruction counts price the residual "
                    "non-GC floor; it is secondary to the collection envelope"
                ),
                "product_shape": "future bytecode/compiler work",
            },
        ],
        "execution_witness": {
            "schedules": 2,
            "keys_per_schedule": 80,
            "total_keys": 160,
            "nursery_phases_per_schedule": NURSERY_THRESHOLD,
            "positive": True,
        },
        "claim_limit": (
            "Dynamic instruction and allocation counts are exact for the "
            "generated product IDE composition in the host P0 VM. Collection "
            "placement is derived from the product's 192-allocation nursery "
            "rule for every incoming phase. The host does not execute target "
            "DMA, screen timing, or GC phase timing; 89 frames is an external "
            "accepted whole-collection observation."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-steps", type=int, default=4_000_000)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        require(
            simulate_collections([192], 0) == [0]
            and simulate_collections([193], 0) == [1]
            and simulate_collections([1], 191) == [0]
            and simulate_collections([2], 191) == [1]
            and simulate_collections([400], 0) == [2],
            "nursery placement selftest red",
        )
        print("c2-v1.2.5-editor-latency-accounting: SELFTEST PASS cases=5")
        return 0
    suite = args.suite if args.suite.is_absolute() else ROOT / args.suite
    out = args.out if args.out.is_absolute() else ROOT / args.out
    try:
        receipt = build_receipt(suite, args.max_steps)
        atomic_json(out, receipt)
        serial = receipt["measurements"]["serial_render_every_key"]
        coalesced = receipt["measurements"][
            "coalesced_ten_keys_per_render"
        ]
        print(
            "c2-v1.2.5-editor-latency-accounting: PASS "
            f"keys={receipt['execution_witness']['total_keys']} "
            f"serial_alloc={serial['allocations']['total_charged_to_key']['mean']:.2f} "
            f"serial_gc={serial['target_nursery_collection_model']['steady_state_collections_per_key']:.3f}/key "
            f"coalesced_alloc={coalesced['allocations']['total_charged_to_key']['mean']:.2f} "
            f"coalesced_gc={coalesced['target_nursery_collection_model']['steady_state_collections_per_key']:.3f}/key"
        )
    except (OSError, UnicodeError, json.JSONDecodeError, AccountingError) as exc:
        print(f"c2-v1.2.5-editor-latency-accounting: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
