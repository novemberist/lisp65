#!/usr/bin/env python3
"""Measure the exact Link-75 require workload without claiming target timing.

The existing real-resolver fixture deliberately models no target garbage
collector.  This driver therefore separates three kinds of evidence:

* exact semantic workload counts from the compiled Link-75 bytecode;
* instrumented Python-host timings, useful only for locating host work;
* already accepted hardware wall-clock observations, quoted as coarse totals.

It never reports the append-only Python heap's lack of collection as "zero
collections".  Target GC attribution belongs to the separate Phase-M2 receipt.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_link75_real_require_resolver_host as R  # noqa: E402


BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
SESSION = BASE / "bundled-completion-session"
MEDIA = (
    SESSION
    / "library-media-successor"
    / "require-defstruct-link75-bound.d81"
)
FIRST_HW = (
    SESSION
    / "hardware-symbol-read-session-v2"
    / "retry-require-first-timing.json"
)
REPEAT_HW = (
    SESSION
    / "hardware-symbol-read-session-v2"
    / "retry-require-repeat-timing.json"
)
OUT = BASE / "phase-m/require-latency"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-phase-m1-require-latency-measurement-receipt.json"
)
FORMAT = "lisp65-c2.2-phase-m1-require-latency-v1"


class MeasurementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MeasurementError(message)


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


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def summary(values: list[float], digits: int = 6) -> dict[str, float]:
    require(bool(values), "cannot summarize an empty sample")
    return {
        "min": round(min(values), digits),
        "median": round(statistics.median(values), digits),
        "p90": round(percentile(values, 0.90), digits),
        "max": round(max(values), digits),
    }


class WorkTrace:
    """Attribute direct VM work by dynamic resolver phase."""

    PHASES = ("parse", "resolve", "load_publish", "control")

    def __init__(self) -> None:
        self.stack: list[str] = []
        self.active = False
        self.last_ns = 0
        self.wall_ns: Counter[str] = Counter()
        self.instructions: Counter[str] = Counter()
        self.function_instructions: Counter[str] = Counter()
        self.function_wall_ns: Counter[str] = Counter()
        self.calls: Counter[str] = Counter()
        self.primitive_calls: Counter[int] = Counter()
        self.primitive_wall_ns: Counter[int] = Counter()
        self.allocations: Counter[str] = Counter()

    @staticmethod
    def classify(stack: list[str]) -> str:
        # The parser is a named sub-computation of resolve; give the more
        # specific phase precedence.  Publication similarly owns its load
        # subtree even though it is entered from the resolver.
        if "%require-run-plan" in stack:
            return "load_publish"
        if "%l65i-parse" in stack:
            return "parse"
        if "%require-resolve" in stack:
            return "resolve"
        return "control"

    def phase(self) -> str:
        return self.classify(self.stack)

    def _book(self) -> None:
        if not self.active:
            return
        now = time.perf_counter_ns()
        delta = now - self.last_ns
        phase = self.phase()
        self.wall_ns[phase] += delta
        if self.stack:
            self.function_wall_ns[self.stack[-1]] += delta
        self.last_ns = now

    def start(self) -> None:
        require(not self.active and not self.stack, "trace lane already active")
        self.active = True
        self.last_ns = time.perf_counter_ns()

    def finish(self) -> None:
        self._book()
        require(not self.stack, f"unbalanced trace stack: {self.stack}")
        self.active = False

    def enter(self, name: str, _code: Any, _args: Any) -> None:
        self._book()
        self.stack.append(name)

    def exit(self, name: str, _code: Any) -> None:
        self._book()
        require(self.stack and self.stack[-1] == name,
                f"trace exit mismatch: {name}")
        self.stack.pop()

    def instruction(
        self, name: str, _code: Any, _pc: int, _spec: Any, _operand: Any
    ) -> None:
        self._book()
        phase = self.phase()
        self.instructions[phase] += 1
        self.function_instructions[name] += 1

    def call(
        self,
        _caller: str,
        kind: str,
        target: Any,
        _argc: int,
        **_kwargs: Any,
    ) -> None:
        self._book()
        self.calls[f"{kind}:{target}"] += 1

    def native_frame(self, *_args: Any, **_kwargs: Any) -> None:
        self._book()

    def native_stack(self, *_args: Any, **_kwargs: Any) -> None:
        self._book()

    def allocation(self) -> None:
        if self.active:
            self.allocations[self.phase()] += 1

    def primitive(self, prim_id: int, elapsed_ns: int) -> None:
        self.primitive_calls[prim_id] += 1
        self.primitive_wall_ns[prim_id] += elapsed_ns

    def result(self) -> dict[str, Any]:
        total_instructions = sum(self.instructions.values())
        total_wall_ns = sum(self.wall_ns.values())
        top = self.function_instructions.most_common(16)
        return {
            "vm_instructions": total_instructions,
            "phase_instructions": {
                phase: self.instructions[phase] for phase in self.PHASES
            },
            "phase_instruction_percent": {
                phase: round(
                    100.0 * self.instructions[phase] / total_instructions, 4
                )
                for phase in self.PHASES
            },
            "instrumented_host_seconds": round(total_wall_ns / 1e9, 6),
            "phase_host_seconds": {
                phase: round(self.wall_ns[phase] / 1e9, 6)
                for phase in self.PHASES
            },
            "phase_host_percent": {
                phase: round(100.0 * self.wall_ns[phase] / total_wall_ns, 4)
                for phase in self.PHASES
            },
            "runtime_allocations": sum(self.allocations.values()),
            "phase_allocations": {
                phase: self.allocations[phase] for phase in self.PHASES
            },
            "primitive_calls": {
                str(ident): count
                for ident, count in sorted(self.primitive_calls.items())
            },
            "primitive_host_seconds_nonadditive": {
                str(ident): round(value / 1e9, 6)
                for ident, value in sorted(self.primitive_wall_ns.items())
            },
            "top_functions_by_instruction": [
                {
                    "name": name,
                    "instructions": count,
                    "percent": round(100.0 * count / total_instructions, 4),
                    "direct_instrumented_host_seconds": round(
                        self.function_wall_ns[name] / 1e9, 6
                    ),
                }
                for name, count in top
            ],
        }


class MeasuredResolverVM(R.ResolverVM):
    def _callprim(
        self,
        prim_id: int,
        argc: int,
        stack: list[int],
        pc: int | None = None,
        native_base: int = 0,
        frame_slots: int = 0,
    ) -> int:
        started = time.perf_counter_ns()
        try:
            return super()._callprim(
                prim_id, argc, stack, pc, native_base, frame_slots
            )
        finally:
            if isinstance(self.trace, WorkTrace):
                self.trace.primitive(
                    prim_id, time.perf_counter_ns() - started
                )


def classifier_selftest() -> dict[str, Any]:
    cases = {
        "control": (["require"], "control"),
        "resolve": (["require", "%require-resolve"], "resolve"),
        "parse_over_resolve": (
            ["require", "%require-resolve", "%l65i-parse"],
            "parse",
        ),
        "publish_over_resolve": (
            ["require", "%require-resolve", "%require-run-plan"],
            "load_publish",
        ),
        "publish_over_parse": (
            [
                "require",
                "%require-resolve",
                "%l65i-parse",
                "%require-run-plan",
            ],
            "load_publish",
        ),
    }
    for label, (stack, expected) in cases.items():
        require(
            WorkTrace.classify(stack) == expected,
            f"phase classifier selftest failed: {label}",
        )
    # A plausible regression ("resolve always wins") must be observable.
    mutant = lambda stack: (
        "resolve" if "%require-resolve" in stack
        else WorkTrace.classify(stack)
    )
    rejected = sum(mutant(stack) != expected
                   for stack, expected in cases.values())
    require(rejected == 3, "phase classifier mutation was not rejected")
    return {
        "cases_passed": len(cases),
        "mutated_precedence_cases_rejected": rejected,
    }


def execute_lane(
    vm: MeasuredResolverVM,
    bound: R.BoundStdlib,
    plane: R.LivePlane,
    *,
    required_phases: tuple[str, ...] = WorkTrace.PHASES,
    library: str = "defstruct",
    expected_result: str = "t",
) -> dict[str, Any]:
    trace = WorkTrace()
    vm.trace = trace
    original_alloc = bound.heap.alloc

    def measured_alloc(*args: Any, **kwargs: Any) -> int:
        trace.allocation()
        return original_alloc(*args, **kwargs)

    bound.heap.alloc = measured_alloc  # type: ignore[method-assign]
    reads_before = len(vm.prim67_reads)
    loads_before = len(vm.loader_attempts)
    disk_before = vm.io_counters["disk_read"]
    snapshot = bytes(plane.data), bytes(plane.host.plane.code)
    trace.start()
    outer_started = time.perf_counter_ns()
    try:
        result = vm.run(
            bound.directory[bound.require_symbol],
            [bound.heap.intern(library)],
        )
    finally:
        outer_elapsed = time.perf_counter_ns() - outer_started
        trace.finish()
        bound.heap.alloc = original_alloc  # type: ignore[method-assign]
    row = trace.result()
    row.update({
        "result": bound.heap.obj_to_text(result),
        "outer_instrumented_host_seconds": round(outer_elapsed / 1e9, 6),
        "prim67_reads": len(vm.prim67_reads) - reads_before,
        "loader_attempts": len(vm.loader_attempts) - loads_before,
        "disk_sector_reads": vm.io_counters["disk_read"] - disk_before,
        "c2d_and_code_changed": snapshot
            != (bytes(plane.data), bytes(plane.host.plane.code)),
    })
    require(row["vm_instructions"] == vm.steps,
            "trace instruction total diverges from VM step counter")
    require(
        row["result"] == expected_result,
        "measured require returned an unexpected value",
    )
    require(
        all(row["phase_instructions"][phase] > 0
            for phase in required_phases),
        "one or more named resolver phases were not exercised",
    )
    return row


def execute_sample() -> dict[str, Any]:
    bound = R.BoundStdlib()
    media = MEDIA.read_bytes()
    locators, payloads = R.media_locators(media)
    require(payloads["l65index"][:4] == b"L65I",
            "successor media index identity drift")
    plane = R.LivePlane()
    vm = MeasuredResolverVM(bound, plane, media, locators)
    first = execute_lane(vm, bound, plane)
    second = execute_lane(vm, bound, plane)
    require(
        first["vm_instructions"] == 136765
        and first["prim67_reads"] == 399
        and first["loader_attempts"] == 2
        and first["disk_sector_reads"] == 2
        and first["c2d_and_code_changed"],
        "first require semantic workload drift",
    )
    require(
        second["vm_instructions"] == 134788
        and second["prim67_reads"] == 384
        and second["loader_attempts"] == 0
        and second["disk_sector_reads"] == 2
        and not second["c2d_and_code_changed"],
        "idempotent require semantic workload drift",
    )
    return {"first": first, "idempotent_repeat": second}


def stable_semantics(samples: list[dict[str, Any]], lane: str) -> dict[str, Any]:
    rows = [sample[lane] for sample in samples]
    exact_keys = (
        "vm_instructions",
        "phase_instructions",
        "runtime_allocations",
        "phase_allocations",
        "prim67_reads",
        "loader_attempts",
        "disk_sector_reads",
        "c2d_and_code_changed",
        "primitive_calls",
    )
    for key in exact_keys:
        require(
            all(row[key] == rows[0][key] for row in rows[1:]),
            f"{lane} semantic sample drift: {key}",
        )
    return {
        key: rows[0][key] for key in exact_keys
    } | {
        "phase_instruction_percent": rows[0]["phase_instruction_percent"],
        "top_functions_by_instruction":
            rows[0]["top_functions_by_instruction"],
        "instrumented_host_seconds": summary([
            row["instrumented_host_seconds"] for row in rows
        ]),
        "outer_instrumented_host_seconds": summary([
            row["outer_instrumented_host_seconds"] for row in rows
        ]),
        "phase_host_seconds_median": {
            phase: round(statistics.median([
                row["phase_host_seconds"][phase] for row in rows
            ]), 6)
            for phase in WorkTrace.PHASES
        },
        "phase_host_percent_median": {
            phase: round(statistics.median([
                row["phase_host_percent"][phase] for row in rows
            ]), 4)
            for phase in WorkTrace.PHASES
        },
    }


def hardware_truth() -> dict[str, Any]:
    first, repeat = load(FIRST_HW), load(REPEAT_HW)
    require(
        first.get("status") == repeat.get("status") == "pass"
        and first.get("elapsed_seconds") == 12
        and repeat.get("elapsed_seconds") == 9,
        "accepted Link-75 hardware timing truth drift",
    )
    return {
        "current_valid_full_reset_product_bound_media": {
            "first_require_seconds": 12,
            "idempotent_repeat_seconds": 9,
            "resolution_seconds": 1,
            "first_receipt": bind(FIRST_HW),
            "repeat_receipt": bind(REPEAT_HW),
        },
        "historical_30_second_observation": {
            "status": "superseded-coarse-observation",
            "used_as_current_baseline": False,
            "reason": (
                "The later full-reset run against product-bound successor "
                "media measured 12 s first and 9 s repeat."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    try:
        require(3 <= args.samples <= 15,
                "samples must be between 3 and 15")
        media_binding = bind(MEDIA)
        selftest = classifier_selftest()
        samples = [execute_sample() for _ in range(args.samples)]
        first = stable_semantics(samples, "first")
        repeat = stable_semantics(samples, "idempotent_repeat")
        common_step_ratio = (
            repeat["vm_instructions"] / first["vm_instructions"]
        )
        common_read_ratio = (
            repeat["prim67_reads"] / first["prim67_reads"]
        )
        value = {
            "format": FORMAT,
            "recorded_on": "2026-07-28",
            "status": "passed-exact-workload-host-timing-target-GC-unmodeled",
            "promotable": False,
            "product_delta_bytes": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "sample_count": args.samples,
            "hardware_wall_truth": hardware_truth(),
            "host_measurement": {
                "first_require": first,
                "idempotent_repeat": repeat,
                "repeat_over_first": {
                    "vm_instruction_ratio": round(common_step_ratio, 6),
                    "prim67_read_ratio": round(common_read_ratio, 6),
                    "first_only_vm_instructions":
                        first["vm_instructions"] - repeat["vm_instructions"],
                    "first_only_prim67_reads":
                        first["prim67_reads"] - repeat["prim67_reads"],
                    "first_only_loader_attempts":
                        first["loader_attempts"] - repeat["loader_attempts"],
                },
            },
            "target_gc_collections": {
                "status": "not-modeled-by-bytecode_p0_heap",
                "count": None,
                "reason": (
                    "bytecode_p0.Heap is append-only and has no target GC, "
                    "heap ceiling, roots, mark, sweep, or external-cell DMA."
                ),
                "false_claim_rejected": "zero collections",
            },
            "attribution": {
                "measured": [
                    "exact compiled-VM instruction counts",
                    "exact Prim-67 call/read counts",
                    "exact disk/load operations",
                    "runtime host-heap allocation operations",
                    "instrumented Python-host phase timings",
                ],
                "not_measured": [
                    "target GC collection count during require",
                    "target phase wall time",
                    "target DMA latency",
                    "target CPU or IRQ behavior",
                ],
                "decision_relevant_result": (
                    "The idempotent repeat performs "
                    f"{100.0 * common_step_ratio:.2f}% of first-run VM "
                    "instructions and "
                    f"{100.0 * common_read_ratio:.2f}% of first-run Prim-67 "
                    "reads while doing no publication. The accepted target "
                    "wall totals are 12 s first and 9 s repeat. Thus most "
                    "observed require work is common parse/validation/"
                    "resolution work, not the two first-run library loads. "
                    "This does not attribute any remainder to GC."
                ),
            },
            "classifier_gate": selftest,
            "authority": {
                "media": media_binding,
                "stdlib": bind(R.STDLIB),
                "static_c2d": bind(R.STATIC_C2D),
                "static_bank2": bind(R.STATIC_CODE),
                "driver": bind(Path(__file__).resolve()),
                "resolver_fixture": bind(Path(R.__file__).resolve()),
            },
            "claim_limit": (
                "Phase timings are Python-host measurements with tracing "
                "overhead and are not target timing estimates. Semantic "
                "counts are exact for the bound bytecode fixture. The host "
                "heap does not implement the target garbage collector, so "
                "this receipt makes no target collection-count claim."
            ),
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        OUT.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (OUT / "latest.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "c2-phase-m-require-latency: PASS "
            f"samples={args.samples} "
            f"first={first['vm_instructions']}/{first['prim67_reads']} "
            f"repeat={repeat['vm_instructions']}/{repeat['prim67_reads']} "
            "target=12s/9s gc=not-modeled"
        )
        return 0
    except (MeasurementError, R.ResolverError, B.VMError, ValueError) as error:
        print(
            "c2-phase-m-require-latency: FIRST RED: " + str(error),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
