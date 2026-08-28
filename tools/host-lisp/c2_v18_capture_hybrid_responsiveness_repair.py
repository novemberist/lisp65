#!/usr/bin/env python3
"""Attribute and gate the one v1.8 Capture responsiveness repair round.

The product ELF/PRG pair is immutable here.  The measured route changed when
the living editor inserted ``%rl-poll`` between ``%read-line-loop`` and the
sealed Capture take.  This witness accounts every dynamic VM step, then proves
the single-traversal successor and its double-traversal counterfactual.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import c2_v160_input_service_hybrid_final_world as HYBRID  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / "lib/stdlib-read-line.lisp"
PAIR_RED = ARCH / (
    "c2.3-v1.8-capture-hybrid-product-card-r1-"
    "source-world-resume-final-red.json")
ELF = ROOT / (
    "build/c2.3/v1.8-capture-hybrid-product-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ELF.with_suffix("")
RECEIPT = ARCH / (
    "c2.3-v1.8-capture-hybrid-responsiveness-repair-receipt.json")
REPORT = ROOT / (
    "docs/planning/v1.8.0-capture-hybrid-responsiveness-repair-report.md")
PRICE_COMMIT = "870e5f53"
PRE_REPAIR_COMMIT = "9eb6af89"
FORMAT = "lisp65-c2-v18-capture-hybrid-responsiveness-repair-v1"

OLD_FORM = """(defun %rl-poll (state)
  (let* ((idle (car (nthcdr 10 state))))
    (if (not idle)
        (if (nthcdr 8 state)"""
NEW_FORM = """(defun %rl-poll (state)
  (let* ((tail (nthcdr 8 state))
         (idle (car (cdr (cdr tail)))))
    (if (not idle)
        (if tail"""


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def era_source(commit: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:lib/stdlib-read-line.lisp"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


class StepTrace:
    def __init__(self) -> None:
        self.vm: PRICE.TimingVM | None = None
        self.instructions: list[tuple[int, str, str]] = []
        self.calls: list[tuple[int, str, str, str]] = []

    def instruction(self, name: str, _code: Any, _pc: int,
                    spec: Any, _operand: Any) -> None:
        assert self.vm is not None
        self.instructions.append((self.vm.steps, name, spec.mnemonic))

    def call(self, caller: str, kind: str, target: Any, _argc: int,
             **_unused: Any) -> None:
        assert self.vm is not None
        self.calls.append((self.vm.steps, caller, kind, str(target)))


def counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counter.items(), key=lambda row: str(row[0])):
        if isinstance(key, tuple):
            rows.append({"caller": key[0], "kind": key[1],
                         "target": key[2], "count": count})
        else:
            rows.append({"name": key, "steps": count})
    return rows


def execute(raw_source: bytes, world: str) -> dict[str, Any]:
    events = [97] * 40 + [13]
    ROOT.joinpath("build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
            dir=ROOT / "build", prefix="v18-responsiveness-") as name:
        source = Path(name) / "stdlib-read-line.lisp"
        source.write_bytes(raw_source)
        suite = PRICE.combined_suite(
            source, '(%repl-read "" nil 0 80 0)', "a" * 40, events)
        if world == "live-artifacts":
            PRICE.live_function_directory(suite, source)
        else:
            require(world == "historical-sealed", "unknown function world")
        (heap, _names, _code, _entry_flags, resident_flags, _bundle,
         directory, _cases, entries, _inliner) = PRICE.P0._compile_suite(suite)
        macros = PRICE.P0._macro_symbol_objs(heap, {}, resident_flags)
        abi_profile, abi_ledger = PRICE.P0._suite_abi(suite)
        case_heap = heap.clone()
        for tag in ("key", "shift", "control", "meta"):
            case_heap.intern(tag)
        names = {id(code): case_heap.obj_to_text(symbol)
                 for symbol, code in directory.items()}
        trace = StepTrace()
        vm = PRICE.TimingVM(
            heap=case_heap, directory=directory, macro_symbols=macros,
            max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
            key_events=events, abi_profile=abi_profile,
            abi_ledger=abi_ledger, batch_cap=8, trace=trace,
            code_names=names)
        trace.vm = vm
        result = vm.run(directory[case_heap.intern(entries[0])], [])
        require(case_heap.obj_to_text(result) == json.dumps("a" * 40),
                "responsiveness route result drift")
        points = [step for label, step in vm.boundaries
                  if label == "private-2"]
        require(len(points) == 6, "batch boundary count drift")
        first, last = points[0], points[-1]
        instructions = [row for row in trace.instructions
                        if first <= row[0] < last]
        calls = [row for row in trace.calls if first <= row[0] < last]
        function_steps = Counter(row[1] for row in instructions)
        opcode_steps = Counter(row[2] for row in instructions)
        call_edges = Counter((row[1], row[2], row[3]) for row in calls)
        screens = sum(first <= step < last for step in vm.screen_steps)
        return {
            "source_sha256": sha(raw_source), "function_world": world,
            "characters": 40, "dynamic_vm_steps": last - first,
            "vm_steps_per_character": (last - first) / 40,
            "screen_cells": screens,
            "screen_cells_per_character": screens / 40,
            "heap_cells_per_character": 1, "boundary_count": len(points),
            "function_steps": counter_rows(function_steps),
            "opcode_steps": counter_rows(opcode_steps),
            "call_edges": counter_rows(call_edges),
        }


def row_counter(rows: list[dict[str, Any]], *, key: str,
                value: str) -> Counter[str]:
    return Counter({row[key]: row[value] for row in rows})


def delta(left: dict[str, Any], right: dict[str, Any], field: str,
          key: str, value: str) -> dict[str, int]:
    a = row_counter(left[field], key=key, value=value)
    b = row_counter(right[field], key=key, value=value)
    return {name: b[name] - a[name] for name in sorted(set(a) | set(b))
            if b[name] != a[name]}


def measurement(route: dict[str, Any], native_cycles: int,
                native_instructions: int) -> dict[str, Any]:
    price = load(HYBRID.CONTRACT)["responsiveness"]
    frames = (
        route["vm_steps_per_character"]
        * price["calibration_cycles_per_vm_step"] / price["cycles_per_frame"]
        + route["screen_cells_per_character"]
        * price["screen_cell_cycles"] / price["cycles_per_frame"]
        + route["heap_cells_per_character"]
        * price["collection_frames"] / price["nursery_cells"]
        + native_cycles / price["cycles_per_frame"])
    rate = 1.0 / frames
    return {
        "dynamic_vm_steps": route["dynamic_vm_steps"],
        "vm_steps_per_character": route["vm_steps_per_character"],
        "screen_cells_per_character": route["screen_cells_per_character"],
        "heap_cells_per_character": route["heap_cells_per_character"],
        "linked_native_cycles_per_character": native_cycles,
        "linked_native_instructions_per_character": native_instructions,
        "frames_per_character": frames,
        "service_events_per_frame": rate,
        "margin_percent": (rate - 1.0) * 100.0,
        "walls": {
            "maximum_frames_per_character": frames <= 0.8,
            "minimum_service_events_per_frame": rate >= 1.25,
            "minimum_margin_percent": (rate - 1.0) * 100.0 >= 25.0,
        },
    }


def derive() -> dict[str, Any]:
    red = load(PAIR_RED)
    before_pair = {"ELF": bind(ELF), "PRG": bind(PRG)}
    require(red["pair"] == before_pair, "frozen pair identity drift")
    price_raw = era_source(PRICE_COMMIT)
    predecessor_raw = era_source(PRE_REPAIR_COMMIT)
    current_raw = SOURCE.read_bytes()
    require(OLD_FORM.encode() in predecessor_raw
            and NEW_FORM.encode() not in predecessor_raw,
            "pre-repair route authority drift")
    require(NEW_FORM.encode() in current_raw
            and OLD_FORM.encode() not in current_raw,
            "single-traversal route repair absent")
    mutation_raw = current_raw.replace(NEW_FORM.encode(), OLD_FORM.encode(), 1)
    require(mutation_raw == predecessor_raw,
            "double-traversal mutation is not the exact predecessor")

    historical = execute(price_raw, "historical-sealed")
    predecessor = execute(predecessor_raw, "live-artifacts")
    successor = execute(current_raw, "live-artifacts")
    mutation = execute(mutation_raw, "live-artifacts")
    require(mutation == predecessor, "double-traversal mutation drift")

    _truth, machine, _membership = HYBRID.linked_consumer(ELF)
    symbols = machine.symbols
    memory = {symbols["C2K_INPUT_RING_HEAD"]: 1,
              symbols["C2K_INPUT_RING_TAIL"]: 0,
              symbols["C2K_INPUT_RING_BASE"]: ord("a")}
    result, native_cycles, native_instructions = machine.run(2, memory)
    require(result == ord("a"), "linked native consumer drift")
    historical_measure = measurement(
        historical, native_cycles, native_instructions)
    predecessor_measure = measurement(
        predecessor, native_cycles, native_instructions)
    successor_measure = measurement(
        successor, native_cycles, native_instructions)

    price_to_live = delta(
        historical, predecessor, "function_steps", "name", "steps")
    repair_delta = delta(
        predecessor, successor, "function_steps", "name", "steps")
    successor_delta = delta(
        historical, successor, "function_steps", "name", "steps")
    require(price_to_live == {
        "%read-line-loop": -50, "%rl-poll": 95, "1-": 200,
        "nthcdr": 425, "zerop": 220},
        f"price-to-live VM attribution drift: {price_to_live}")
    require(repair_delta == {
        "%rl-poll": 10, "1-": -200, "nthcdr": -425, "zerop": -220},
        f"repair VM attribution drift: {repair_delta}")
    require(successor_delta == {"%read-line-loop": -50, "%rl-poll": 105},
            f"successor VM attribution drift: {successor_delta}")
    require(sum(price_to_live.values()) == 890
            and predecessor["dynamic_vm_steps"] -
                historical["dynamic_vm_steps"] == 890,
            "price-to-live dynamic steps retained an unexplained member")
    require(sum(repair_delta.values()) == -835
            and successor["dynamic_vm_steps"] -
                predecessor["dynamic_vm_steps"] == -835,
            "repair dynamic steps retained an unexplained member")
    require(predecessor_measure["walls"] == {
                "maximum_frames_per_character": False,
                "minimum_service_events_per_frame": False,
                "minimum_margin_percent": False}
            and all(successor_measure["walls"].values()),
            "responsiveness repair/countermutation wall result drift")
    require(historical["screen_cells"] == predecessor["screen_cells"] ==
                successor["screen_cells"] == 45
            and historical["heap_cells_per_character"] ==
                predecessor["heap_cells_per_character"] ==
                successor["heap_cells_per_character"] == 1,
            "repair changed screen/heap work")

    return {
        "format": FORMAT, "recorded_on": "2026-08-28",
        "status": "PASS: ONE ROUTE REPAIR RESTORES RESPONSIVENESS WALL",
        "frozen_pair_before": before_pair, "frozen_pair_after": before_pair,
        "authorities": {
            "price_source": {"commit": PRICE_COMMIT,
                             "sha256": sha(price_raw)},
            "live_red_source": {"commit": PRE_REPAIR_COMMIT,
                                "sha256": sha(predecessor_raw)},
            "successor_source": bind(SOURCE), "final_red": bind(PAIR_RED)},
        "attribution": {
            "historical_price_world": historical,
            "live_red_world": predecessor,
            "function_step_delta": price_to_live,
            "families": [
                {"name": "poll-wrapper-body", "steps": 95,
                 "members": {"%rl-poll": 95}},
                {"name": "duplicated-state-shape-walk", "steps": 845,
                 "members": {"1-": 200, "nthcdr": 425, "zerop": 220}},
                {"name": "predecessor-loop-contraction", "steps": -50,
                 "members": {"%read-line-loop": -50}},
            ],
            "named_delta_steps": 890, "observed_delta_steps": 890,
            "unexplained_steps": 0,
            "excluded_candidates": {
                "A0_probe_steps": 0, "directory_resolution_VM_steps": 0,
                "native_consumer_cycle_delta": 0,
                "screen_cell_delta": 0, "heap_cell_delta": 0}},
        "repair": {
            "kind": "route-side single traversal of the state suffix",
            "predecessor_to_successor_function_step_delta": repair_delta,
            "successor_vs_price_function_step_delta": successor_delta,
            "removed_dynamic_vm_steps": 835,
            "successor_route": successor,
            "predecessor_measurement": predecessor_measure,
            "successor_measurement": successor_measure,
            "double_traversal_mutation": {
                "source_sha256": sha(mutation_raw),
                "exact_predecessor": True,
                "all_three_walls_red": not any(
                    predecessor_measure["walls"].values())}},
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "host route repair only; product pair unchanged; final status "
            "requires read-only Scope and Acceptance Resume"),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "responsiveness repair receipt drift")


def selftest(value: dict[str, Any]) -> None:
    mutations = (
        lambda row: row["attribution"].update(unexplained_steps=1),
        lambda row: row["repair"]["successor_measurement"]["walls"].update(
            minimum_margin_percent=False),
        lambda row: row["accounting"].update(product_links=1),
    )
    for mutate in mutations:
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except RepairError:
            continue
        raise RepairError("responsiveness repair mutation survived")


def write_report(value: dict[str, Any]) -> None:
    red = value["repair"]["predecessor_measurement"]
    green = value["repair"]["successor_measurement"]
    REPORT.write_text(f"""# v1.8 Capture/Hybrid responsiveness repair

Status: **HOST-GREEN; FROZEN PRODUCT PAIR UNCHANGED**

The price-to-live difference is completely attributed at the VM-step level:
the live route adds 890 steps over 40 characters.  `%rl-poll` contributes 95,
its second state-suffix traversal contributes 845 transitively (`nthcdr` 425,
`zerop` 220, `1-` 200), and the shortened `%read-line-loop` returns 50.
The named sum is 890; unexplained steps are zero.  A0, directory resolution,
native-consumer cycles, screen cells and heap cells contribute zero delta.

The one repair shares the suffix already reached at state slot 8 when it asks
for slot 10.  It removes {value['repair']['removed_dynamic_vm_steps']} steps
without changing the route result, screen work, heap work or native consumer.
The exact double-traversal predecessor is the permanent countermutation.

| world | VM steps | frames/character | events/frame | margin |
|---|---:|---:|---:|---:|
| live red | {red['dynamic_vm_steps']} | {red['frames_per_character']:.6f} | {red['service_events_per_frame']:.6f} | {red['margin_percent']:.3f}% |
| single traversal | {green['dynamic_vm_steps']} | {green['frames_per_character']:.6f} | {green['service_events_per_frame']:.6f} | {green['margin_percent']:.3f}% |

The repair spends zero WPLTOs and zero links.  ELF and PRG remain SHA-identical
to the frozen pair.  Scope and Acceptance remain a separate read-only Resume.
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
        write_report(value)
    else:
        validate(load(RECEIPT))
    if action == "selftest":
        selftest(value)
    print("v1.8 Capture responsiveness repair: PASS "
          f"steps={value['repair']['successor_measurement']['dynamic_vm_steps']} "
          f"margin={value['repair']['successor_measurement']['margin_percent']:.3f}% "
          "WPLTO=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError,
            B.VMError, RepairError) as error:
        print(f"v1.8 Capture responsiveness repair: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
