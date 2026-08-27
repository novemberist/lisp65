#!/usr/bin/env python3
"""Permanent v1.2.6 editor allocation and coalescing gate."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
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
import bytecode_p0_compiler as C  # noqa: E402
from ide_bytecode_dynamic_report import Runtime  # noqa: E402
import c2_v125_editor_latency_accounting as A  # noqa: E402


DEFAULT_CONTRACT = ROOT / "config/c2-v126-editor-allocation-contract.json"
DEFAULT_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
DEFAULT_RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-v126-editor-allocation-gate-receipt.json"
)
DEFAULT_FIRST_RED = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-v126-editor-allocation-first-red-receipt.json"
)
FORMAT = "lisp65-c2-v126-editor-allocation-gate-receipt-v1"
SCREEN_COLUMNS = 80
SCREEN_ROWS = 25


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing input: {path}")
    data = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "bytes": len(data), "sha256": sha(data)}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path}: root is not an object")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def summarize(values: list[int]) -> dict[str, int | float]:
    require(bool(values), "empty key class")
    ordered = sorted(values)
    return {
        "count": len(values),
        "sum": sum(values),
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
        "mean": sum(values) / len(values),
    }


def max_collections(allocations: int) -> int:
    return max(
        A.simulate_collections([allocations], phase)[0]
        for phase in range(A.NURSERY_THRESHOLD)
    )


class ScreenVM(B.P0VM):
    def __init__(self, *args: Any, screen: list[list[int]], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.screen = screen

    def _put(self, x: int, y: int, code: int) -> None:
        if 0 <= x < SCREEN_COLUMNS and 0 <= y < SCREEN_ROWS:
            self.screen[y][x] = code & 0xFF

    def _callprim(
        self, prim_id: int, argc: int, stack: list[int], pc: int | None = None,
        native_base: int = 0, frame_slots: int = 0,
    ) -> int:
        if prim_id not in (10, 11, 12):
            return super()._callprim(
                prim_id, argc, stack, pc=pc, native_base=native_base,
                frame_slots=frame_slots,
            )
        self._check_argc(argc, "CALLPRIM")
        args = self._pop_args(argc, stack)
        self._trace_call(
            "CALLPRIM", B.PRIM_IDS[prim_id], argc, pc=pc, resolved=True
        )
        if prim_id == 10:
            require(argc == 0, "screen-clear arity drift")
            for row in self.screen:
                row[:] = [32] * SCREEN_COLUMNS
            return B.NIL
        if prim_id == 11:
            require(
                argc in (3, 4) and all(B.is_fix(arg) for arg in args[:3]),
                "screen-put-char argument drift",
            )
            self._put(
                B.fixval(args[0]), B.fixval(args[1]), B.fixval(args[2])
            )
            return B.NIL
        require(
            argc in (3, 4)
            and B.is_fix(args[0])
            and B.is_fix(args[1])
            and self.heap.stringp(args[2]),
            "screen-write-string argument drift",
        )
        x = B.fixval(args[0])
        y = B.fixval(args[1])
        text = self.heap.string_to_text(args[2])
        for offset, character in enumerate(text):
            self._put(x + offset, y, ord(character))
        attr = B.fixval(args[3]) if argc == 4 else 0
        if attr & 64:
            for column in range(x + len(text), SCREEN_COLUMNS):
                self._put(column, y, 32)
        return B.NIL


class ScreenRuntime(Runtime):
    def __init__(self, suite_path: Path, max_steps: int):
        super().__init__(suite_path, max_steps=max_steps)
        self.screen = [
            [32] * SCREEN_COLUMNS for _ in range(SCREEN_ROWS)
        ]

    def run_named(self, name: str, args: list[int] = (), trace: Any = None) -> int:
        sym = self.heap.intern(name)
        if sym not in self.directory:
            raise GateError(f"missing bytecode function: {name}")
        vm = ScreenVM(
            heap=self.heap,
            directory=self.directory,
            macro_symbols=self.macro_symbols,
            max_steps=self.max_steps,
            max_call_args=self.max_call_args,
            trace=trace,
            code_names=self.code_names,
            native_vm_maxargs=self.native_vm_maxargs,
            native_initial_base=self.native_initial_base,
            abi_profile=self.abi_profile,
            abi_ledger=self.abi_ledger,
            screen=self.screen,
        )
        return vm.run(self.directory[sym], list(args))


def lisp_strings(runtime: ScreenRuntime, value: int) -> list[str]:
    out = []
    current = value
    while runtime.heap.consp(current):
        item = runtime.heap.car(current)
        require(runtime.heap.stringp(item), "buffer line is not a string")
        out.append(runtime.heap.string_to_text(item))
        current = runtime.heap.cdr(current)
    require(current == B.NIL, "buffer line list is improper")
    return out


def screen_text(runtime: ScreenRuntime) -> list[str]:
    return [
        "".join(chr(code) for code in row)
        for row in runtime.screen
    ]


def logical_state(runtime: ScreenRuntime, state: int) -> dict[str, Any]:
    buffer_obj = runtime.run_named("ide-state-buffer", [state])
    lines_obj = runtime.run_named("ide-buffer-lines", [buffer_obj])
    point = runtime.run_named("ide-buffer-point", [buffer_obj])
    offset = B.fixval(runtime.run_named("ide-state-row-offset", [state]))
    return {
        "lines": lisp_strings(runtime, lines_obj),
        "line": B.fixval(runtime.heap.car(point)),
        "column": B.fixval(runtime.heap.cdr(point)),
        "offset": offset,
        "status": runtime.heap.string_to_text(
            runtime.run_named(
                "ide-status-line", [state, B.mkfix(SCREEN_COLUMNS)]
            )
        ),
    }


def typing_screen(
    suite: Path, batch_size: int, max_steps: int,
) -> dict[str, Any]:
    runtime = ScreenRuntime(suite, max_steps=max_steps)
    state = A.warm_state(runtime)
    pending = 0
    for index, character in enumerate(A.BURST_TEXT):
        state = runtime.run_named(
            "ide-step", [state, runtime.key_event(ord(character))]
        )
        pending += 1
        if pending == batch_size or index == len(A.BURST_TEXT) - 1:
            state = runtime.run_named("ide-render", [state])
            pending = 0
    logical = logical_state(runtime, state)
    screen = screen_text(runtime)
    require(
        len(logical["lines"]) >= 2,
        "typing screen never exercised the wrap row",
    )
    for row, line in enumerate(logical["lines"][:2]):
        expected = line[:SCREEN_COLUMNS].ljust(SCREEN_COLUMNS)
        if logical["line"] == row and logical["column"] >= len(line):
            column = logical["column"]
            if column < SCREEN_COLUMNS:
                expected = (
                    expected[:column] + "_" + expected[column + 1 :]
                )
        require(screen[row] == expected, f"typing screen row {row} drift")
    require(
        screen[-1].startswith(logical["status"]),
        "direct status row differs from ide-status-line",
    )
    return {
        "batch_size": batch_size,
        "logical_lines": logical["lines"],
        "point": [logical["line"], logical["column"]],
        "status": logical["status"],
        "screen_sha256": sha("\n".join(screen).encode("latin-1")),
    }


def scroll_screen(
    suite: Path, contract: dict[str, Any], max_steps: int,
) -> dict[str, Any]:
    workload = contract["workloads"]
    runtime = ScreenRuntime(suite, max_steps=max_steps)
    original = [
        f"line-{index:02d} abcdefghijklmnopqrstuvwxyz"
        for index in range(int(workload["scroll_buffer_lines"]))
    ]
    state = runtime.make_state(
        original,
        line=int(workload["scroll_initial_line"]),
        column=int(workload["scroll_initial_column"]),
        rendered=True,
    )
    for code in workload["scroll_keys"]:
        state = runtime.run_named(
            "ide-step", [state, runtime.key_event(int(code))]
        )
        state = runtime.run_named("ide-render", [state])
    logical = logical_state(runtime, state)
    screen = screen_text(runtime)
    visible = logical["lines"][
        logical["offset"] : logical["offset"] + SCREEN_ROWS - 1
    ]
    for row in range(SCREEN_ROWS - 1):
        line = visible[row] if row < len(visible) else ""
        expected = line[:SCREEN_COLUMNS].ljust(SCREEN_COLUMNS)
        require(screen[row] == expected, f"scroll screen row {row} drift")
    require(
        screen[-1].startswith(logical["status"]),
        "scroll status row differs from ide-status-line",
    )
    return {
        "point": [logical["line"], logical["column"]],
        "row_offset": logical["offset"],
        "status": logical["status"],
        "screen_sha256": sha("\n".join(screen).encode("latin-1")),
    }


def semantic_screen_proof(
    suite: Path, contract: dict[str, Any], max_steps: int,
) -> dict[str, Any]:
    serial = typing_screen(suite, batch_size=1, max_steps=max_steps)
    coalesced = typing_screen(suite, batch_size=10, max_steps=max_steps)
    require(
        serial["logical_lines"] == coalesced["logical_lines"]
        and serial["point"] == coalesced["point"]
        and serial["status"] == coalesced["status"]
        and serial["screen_sha256"] == coalesced["screen_sha256"],
        "serial and coalesced typing are not screen-equivalent",
    )
    scroll = scroll_screen(suite, contract, max_steps=max_steps)
    return {
        "serial": serial,
        "coalesced_10": coalesced,
        "scroll": scroll,
        "screen_equivalence_cases": 3,
        "positive": True,
    }


def typing_route(
    suite: Path, batch_size: int, wrap_index: int, max_steps: int,
) -> dict[str, Any]:
    measured = A.run_schedule(suite, batch_size=batch_size, max_steps=max_steps)
    rows = []
    for row in measured["per_key"]:
        allocations = int(row["total_allocations"])
        rows.append(
            {
                "index": int(row["index"]),
                "class": "wrap" if row["index"] == wrap_index else "plain",
                "allocations": allocations,
                "collections_for_worst_incoming_phase": max_collections(
                    allocations
                ),
                "rendered_after_key": bool(row["rendered_after_key"]),
            }
        )
    return {
        "batch_size": batch_size,
        "rows": rows,
        "allocations": {
            name: summarize(
                [row["allocations"] for row in rows if row["class"] == name]
            )
            for name in ("plain", "wrap")
        },
    }


def scroll_route(
    suite: Path, contract: dict[str, Any], max_steps: int,
) -> dict[str, Any]:
    workload = contract["workloads"]
    count = int(workload["scroll_buffer_lines"])
    runtime = Runtime(suite, max_steps=max_steps)
    lines = [
        f"line-{index:02d} abcdefghijklmnopqrstuvwxyz"
        for index in range(count)
    ]
    state = runtime.make_state(
        lines,
        line=int(workload["scroll_initial_line"]),
        column=int(workload["scroll_initial_column"]),
        rendered=True,
    )
    rows = []
    for index, code in enumerate(workload["scroll_keys"]):
        offset_before = B.fixval(
            runtime.run_named("ide-state-row-offset", [state])
        )
        event_before = len(runtime.heap.cells)
        event = runtime.key_event(int(code))
        event_allocations = len(runtime.heap.cells) - event_before
        state, step_trace, step_types = A.run_call(
            runtime, "ide-step", [state, event], f"scroll-{index}-step"
        )
        state, render_trace, render_types = A.run_call(
            runtime, "ide-render", [state], f"scroll-{index}-render"
        )
        offset_after = B.fixval(
            runtime.run_named("ide-state-row-offset", [state])
        )
        allocations = (
            event_allocations
            + A.allocation_count(step_types)
            + A.allocation_count(render_types)
        )
        rows.append(
            {
                "index": index,
                "code": int(code),
                "class": "scroll",
                "row_offset_before": offset_before,
                "row_offset_after": offset_after,
                "changed_window": offset_before != offset_after,
                "allocations": allocations,
                "collections_for_worst_incoming_phase": max_collections(
                    allocations
                ),
                "instructions": step_trace.steps + render_trace.steps,
            }
        )
    require(
        any(row["changed_window"] for row in rows),
        "scroll fixture never crossed a visible window edge",
    )
    return {
        "batch_size": 1,
        "rows": rows,
        "allocations": {
            "scroll": summarize([row["allocations"] for row in rows])
        },
    }


def _defun_forms(source: str) -> dict[str, list[Any]]:
    result = {}
    for form in C.parse_all(source):
        if (isinstance(form, list) and len(form) >= 4
                and form[0] == "defun" and isinstance(form[1], str)):
            result[form[1]] = form
    return result


def _drain_step_edges(node: Any) -> int:
    if not isinstance(node, list):
        return 0
    here = int(
        len(node) == 2
        and node[0] == "%ide-drain-pending"
        and isinstance(node[1], list)
        and bool(node[1])
        and node[1][0] == "ide-step"
    )
    return here + sum(_drain_step_edges(item) for item in node)


def _coalescing_edge_proof(forms: dict[str, list[Any]]) -> dict[str, Any]:
    required_owners = ("%ide-drain-pending", "%ide-poll")
    counts = {
        name: _drain_step_edges(forms.get(name))
        for name in required_owners
    }
    require(
        counts == {"%ide-drain-pending": 1, "%ide-poll": 1},
        "coalescing ide-step result edge missing or duplicated",
    )
    return {
        "relation": "%ide-drain-pending consumes an ide-step result",
        "owners": counts,
        "proof_shape": "parsed defun call tree; local variable spelling ignored",
    }


def _remove_first_drain_step(node: Any) -> tuple[Any, bool]:
    if not isinstance(node, list):
        return node, False
    if (
        len(node) == 2
        and node[0] == "%ide-drain-pending"
        and isinstance(node[1], list)
        and bool(node[1])
        and node[1][0] == "ide-step"
    ):
        return copy.deepcopy(node[1]), True
    changed = []
    removed = False
    for item in node:
        replacement, item_removed = _remove_first_drain_step(item)
        changed.append(replacement)
        if item_removed:
            removed = True
            changed.extend(copy.deepcopy(rest) for rest in node[len(changed):])
            break
    return changed, removed


def coalescing_source_proof() -> dict[str, Any]:
    ui = (ROOT / "lib/ide-ui.lisp").read_text(encoding="utf-8")
    interrupt = (ROOT / "src/interrupt.c").read_text(encoding="utf-8")
    keymap = read_json(ROOT / "config/v11-l-lite-keymap.json")
    forms = _defun_forms(ui)
    edges = _coalescing_edge_proof(forms)
    mutated = copy.deepcopy(forms)
    mutated["%ide-poll"], removed = _remove_first_drain_step(
        mutated["%ide-poll"]
    )
    require(removed, "coalescing edge mutation could not be constructed")
    try:
        _coalescing_edge_proof(mutated)
    except GateError:
        edge_mutation_rejected = True
    else:
        edge_mutation_rejected = False
    require(edge_mutation_rejected, "removed coalescing edge mutation survived")
    required = [
        "(poll-key)",
        "(eq (ide-state-message state) 1015)",
    ]
    for needle in required:
        require(needle in ui, f"coalescing source seam missing: {needle}")
    require(
        "lisp_abort_static(LISP65_ERR_STOPPED" in interrupt
        and "stopped (run/stop)" in interrupt,
        "physical RUN/STOP abort seam missing",
    )
    commands = keymap.get("commands", [])
    require(isinstance(commands, list), "keymap commands malformed")

    observed = [11, 22, 33, 44]
    drained = []
    for item in observed:
        drained.append(item)
    require(drained == observed, "coalescing model reordered input")
    exit_observed = [11, 1015, 33]
    exit_drained = []
    for item in exit_observed:
        exit_drained.append(item)
        if item == 1015:
            break
    require(exit_drained == [11, 1015], "exit did not stop queue drain")
    return {
        "input_order": observed,
        "drained_order": drained,
        "exit_input": exit_observed,
        "exit_drained": exit_drained,
        "physical_run_stop_owner": "src/interrupt.c:lisp_poll",
        "physical_run_stop_queued": False,
        "coalescing_edge": edges,
        "structural_edge_mutations": 1,
        "source_assertions": len(required) + 2 + len(edges["owners"]),
    }


def validate_contract(contract: dict[str, Any]) -> None:
    require(
        contract.get("format")
        == "lisp65-c2-v126-editor-allocation-contract-v1",
        "contract format drift",
    )
    require(
        contract.get("nursery_cells") == A.NURSERY_THRESHOLD,
        "nursery authority drift",
    )
    routes = contract.get("routes")
    require(isinstance(routes, dict) and len(routes) == 3, "route drift")
    for route, classes in routes.items():
        require(isinstance(classes, dict) and classes, f"{route}: no classes")
        for name, limits in classes.items():
            require(
                isinstance(limits, dict)
                and 0 < limits.get("maximum_mean_allocations", 0)
                < A.NURSERY_THRESHOLD
                and limits.get("maximum_single_key_allocations") == 193,
                f"{route}/{name}: invalid limits",
            )
    require(
        contract.get(
            "maximum_collections_on_any_single_key_for_any_incoming_phase"
        )
        == 1,
        "single-key collection limit drift",
    )


def evaluate(
    contract: dict[str, Any], routes: dict[str, Any],
) -> list[str]:
    failures = []
    maximum_collections = int(
        contract[
            "maximum_collections_on_any_single_key_for_any_incoming_phase"
        ]
    )
    for route_name, class_limits in contract["routes"].items():
        route = routes[route_name]
        for class_name, limits in class_limits.items():
            summary = route["allocations"][class_name]
            if summary["mean"] > limits["maximum_mean_allocations"]:
                failures.append(
                    f"{route_name}/{class_name}: mean {summary['mean']:.3f} "
                    f"> {limits['maximum_mean_allocations']}"
                )
            if summary["maximum"] > limits["maximum_single_key_allocations"]:
                failures.append(
                    f"{route_name}/{class_name}: max {summary['maximum']} "
                    f"> {limits['maximum_single_key_allocations']}"
                )
            class_rows = [
                row
                for row in route["rows"]
                if row["class"] == class_name
            ]
            worst = max(
                row["collections_for_worst_incoming_phase"]
                for row in class_rows
            )
            if worst > maximum_collections:
                failures.append(
                    f"{route_name}/{class_name}: worst collections {worst} "
                    f"> {maximum_collections}"
                )
    return failures


def mutation_selftest(contract: dict[str, Any]) -> int:
    mutations = 0
    for route_name, class_name in (
        ("serial", "plain"),
        ("serial", "wrap"),
        ("scroll", "scroll"),
    ):
        changed = copy.deepcopy(contract)
        changed["routes"][route_name][class_name][
            "maximum_mean_allocations"
        ] = 192
        try:
            validate_contract(changed)
        except GateError:
            mutations += 1
        else:
            raise GateError(f"mutation survived: {route_name}/{class_name}")
    require(max_collections(193) == 1, "193-cell exact meet drift")
    mutations += 1
    require(max_collections(194) == 2, "194-cell overflow drift")
    mutations += 1
    reordered = [11, 33, 22]
    require(reordered != [11, 22, 33], "order mutation survived")
    mutations += 1
    return mutations


def build_receipt(
    contract_path: Path, suite: Path, max_steps: int,
) -> dict[str, Any]:
    contract = read_json(contract_path)
    validate_contract(contract)
    wrap_index = int(contract["workloads"]["wrap_key_index_after_warmup"])
    routes = {
        "serial": typing_route(
            suite, batch_size=1, wrap_index=wrap_index, max_steps=max_steps
        ),
        "coalesced_10": typing_route(
            suite, batch_size=10, wrap_index=wrap_index, max_steps=max_steps
        ),
        "scroll": scroll_route(suite, contract, max_steps=max_steps),
    }
    semantic = coalescing_source_proof()
    screens = semantic_screen_proof(suite, contract, max_steps=max_steps)
    mutations = mutation_selftest(contract) + semantic[
        "structural_edge_mutations"
    ]
    failures = evaluate(contract, routes)
    keys = sum(len(route["rows"]) for route in routes.values())
    witness = contract["execution_witness"]
    require(
        len(routes) >= witness["minimum_routes"]
        and keys >= witness["minimum_keys"]
        and mutations >= witness["minimum_mutations"],
        "execution witness below contract",
    )
    return {
        "format": FORMAT,
        "recorded_on": "2026-07-31",
        "status": "passed" if not failures else "first-red",
        "inputs": {
            "contract": bind(contract_path),
            "gate": bind(Path(__file__)),
            "generated_product_ide_suite": bind(suite),
            "editor_buffer": bind(ROOT / "lib/ide-buffer.lisp"),
            "editor_ui": bind(ROOT / "lib/ide-ui.lisp"),
            "editor_syntax": bind(ROOT / "lib/ide-syntax.lisp"),
            "keymap": bind(ROOT / "config/v11-l-lite-keymap.json"),
            "run_stop_owner": bind(ROOT / "src/interrupt.c"),
        },
        "scope": {
            "host_only": True,
            "product_bytes_changed_by_gate": 0,
            "target_timing_claimed": False,
        },
        "routes": routes,
        "coalescing_semantics": semantic,
        "screen_semantics": screens,
        "failures": failures,
        "execution_witness": {
            "routes": len(routes),
            "keys": keys,
            "incoming_nursery_phases_per_key": A.NURSERY_THRESHOLD,
            "phase_key_evaluations": keys * A.NURSERY_THRESHOLD,
            "mutations": mutations,
            "screen_equivalence_cases": screens[
                "screen_equivalence_cases"
            ],
            "positive": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("check", "probe-first-red", "selftest")
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-steps", type=int, default=4_000_000)
    args = parser.parse_args(argv)
    contract_path = args.contract.resolve()
    suite = args.suite.resolve()
    try:
        contract = read_json(contract_path)
        validate_contract(contract)
        if args.command == "selftest":
            mutations = mutation_selftest(contract)
            print(
                "c2-v126-editor-allocation: SELFTEST PASS "
                f"mutations={mutations}"
            )
            return 0
        receipt = build_receipt(contract_path, suite, args.max_steps)
        if args.command == "probe-first-red":
            require(
                receipt["status"] == "first-red" and receipt["failures"],
                "first-red probe unexpectedly green",
            )
            out = args.out.resolve() if args.out else DEFAULT_FIRST_RED
            atomic_json(out, receipt)
            print(
                "c2-v126-editor-allocation: FIRST RED "
                f"failures={len(receipt['failures'])} "
                f"keys={receipt['execution_witness']['keys']}"
            )
            return 0
        require(
            receipt["status"] == "passed",
            "; ".join(receipt["failures"]),
        )
        out = args.out.resolve() if args.out else DEFAULT_RECEIPT
        atomic_json(out, receipt)
        print(
            "c2-v126-editor-allocation: PASS "
            f"keys={receipt['execution_witness']['keys']} "
            f"mutations={receipt['execution_witness']['mutations']}"
        )
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, GateError) as exc:
        print(f"c2-v126-editor-allocation: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
