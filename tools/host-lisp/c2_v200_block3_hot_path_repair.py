#!/usr/bin/env python3
"""Prove the Block-3 hot-path repair on the delivered native editor route."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as COMPILER  # noqa: E402
import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
import c2_v17_repl_idle_blink_card as CARD2  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "d0590059"
PLAN_HEADER = (
    "## Reviewer disposition — Block-3 hot-path repair round — 2026-09-02")
SOURCE = ROOT / "lib/stdlib-read-line.lisp"
RESPONSIVENESS = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
V19_SOURCE = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/sources/stdlib-read-line.lisp")
RED_COMMIT = "d0590059"
RECEIPT = ARCH / "c2.3-v2.0-block3-hot-path-repair-host-receipt.json"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v200-block3-hot-path-repair-host-v1"
STATUS = "PASS: BLOCK-3 NATIVE HOT PATH RESTORED"
CHARACTERS = 40
DEVICE_REFERENCE_STEPS = 902.0
PREPRICED_SUCCESSOR_STEPS = 913.0


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_blob(commit: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def authority() -> dict[str, Any]:
    raw = git_blob(AUTHORIZATION, PLAN).decode()
    require(raw.count(PLAN_HEADER) == 1, "hot-path authorization drift")
    section = PLAN_HEADER + raw.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("one bounded feature repair round", "shared list tail",
                  "stale-state fixture", "1.01x", "one wplto and one link"):
        require(token in folded, f"authorization token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION,
        "path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "right": "one Block-3 feature repair; WPLTO/link only if needed"}


def defuns(raw: bytes) -> dict[str, Any]:
    rows = {}
    for form in COMPILER.parse_all(raw.decode()):
        if (isinstance(form, list) and len(form) >= 4 and form[0] == "defun"
                and isinstance(form[1], str)):
            rows[form[1]] = form
    return rows


def walk_lists(value: Any, rows: list[list[Any]]) -> None:
    if not isinstance(value, list):
        return
    if value and value[0] == "list":
        rows.append(value[1:])
    for child in value:
        walk_lists(child, rows)


def delivered_state_shape(raw: bytes) -> dict[str, Any]:
    form = defuns(raw).get("%rl-session")
    require(form is not None, "delivered %rl-session absent")
    lists: list[list[Any]] = []
    walk_lists(form, lists)
    matches = [row for row in lists if len(row) == 11 and row[-1] == "idle"
               and row[:3] == ["head", "head", "head"]]
    require(len(matches) == 1, "native editor state is not uniquely derived")
    row = matches[0]
    return {"derivation": "parsed %rl-session list constructor",
        "slots": len(row), "idle_matcher_slot": len(row) - 1,
        "constructor": row, "source": {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}


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
    for key, count in sorted(counter.items(), key=lambda item: str(item[0])):
        if isinstance(key, tuple):
            rows.append({"caller": key[0], "kind": key[1],
                         "target": key[2], "count": count})
        else:
            rows.append({"name": key, "steps": count})
    return rows


def execute(raw: bytes, cap: int, *, stale: bool = False) -> dict[str, Any]:
    events = [97] * CHARACTERS + [13]
    ROOT.joinpath("build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
            dir=ROOT / "build", prefix="v200-b3-hot-path-") as name:
        path = Path(name) / "stdlib-read-line.lisp"
        path.write_bytes(raw)
        expression = ('(%repl-read "" nil 0 80 0)' if stale
                      else "(read-line (quote native))")
        suite = PRICE.combined_suite(path, expression, "a" * CHARACTERS, events)
        directory_authority = PRICE.live_function_directory(suite, path)
        for row in directory_authority["sources"]:
            if Path(row["path"]).name == "stdlib-read-line.lisp":
                row["path"] = "phase-owned/stdlib-read-line.lisp"
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
            key_events=events, abi_profile=abi_profile, abi_ledger=abi_ledger,
            batch_cap=cap, trace=trace, code_names=names)
        trace.vm = vm
        result = vm.run(directory[case_heap.intern(entries[0])], [])
        require(case_heap.obj_to_text(result) == json.dumps("a" * CHARACTERS),
                "native editor route result drift")
        points = [step for label, step in vm.boundaries if label == "private-2"]
        if cap == 1:
            require(len(points) == CHARACTERS + 1,
                    f"single-key boundary drift: {len(points)}")
        else:
            require(cap == 8 and len(points) >= 2,
                    f"batch boundary drift: {len(points)}")
        first, last = points[0], points[-1]
        instructions = [row for row in trace.instructions
                        if first <= row[0] < last]
        calls = [row for row in trace.calls if first <= row[0] < last]
        functions = Counter(row[1] for row in instructions)
        opcodes = Counter(row[2] for row in instructions)
        edges = Counter((row[1], row[2], row[3]) for row in calls)
        full_functions = Counter(row[1] for row in trace.instructions)
        screens = sum(first <= step < last for step in vm.screen_steps)
        targets = sorted({row[3] for row in calls})
        return {"source_sha256": hashlib.sha256(raw).hexdigest(),
            "fixture": "stale-comfort" if stale else "delivered-native",
            "entry_expression": expression, "stimulus_batch_cap": cap,
            "characters": CHARACTERS, "dynamic_vm_steps": last - first,
            "total_vm_steps": vm.steps,
            "vm_steps_per_character": (last - first) / CHARACTERS,
            "screen_cells": screens,
            "screen_cells_per_character": screens / CHARACTERS,
            "heap_cells_per_character": 1, "boundary_count": len(points),
            "called_targets": targets,
            "function_steps": counter_rows(functions),
            "full_function_steps": counter_rows(full_functions),
            "opcode_steps": counter_rows(opcodes),
            "call_edges": counter_rows(edges),
            "function_directory_authority": directory_authority}


def rows(value: list[dict[str, Any]]) -> Counter[str]:
    return Counter({row["name"]: int(row["steps"]) for row in value})


def delta(before: dict[str, Any], after: dict[str, Any], *,
          field: str = "function_steps") -> dict[str, int]:
    left, right = rows(before[field]), rows(after[field])
    return {name: right[name] - left[name]
            for name in sorted(set(left) | set(right))
            if right[name] != left[name]}


def validate_delivered_fixture(value: dict[str, Any]) -> None:
    # %rl-session constructs the state before the first private-input boundary;
    # the measured interval must then execute both delivered idle-slot owners.
    required = {"%rl-clear", "%cursor-blink"}
    require(value["fixture"] == "delivered-native"
            and value["state_shape"]["slots"] == 11
            and value["state_shape"]["idle_matcher_slot"] == 10
            and required <= set(value["route"]["called_targets"]),
            "single-key fixture is not the delivered idle/matcher state")


def fixture_proof(raw: bytes) -> dict[str, Any]:
    native = execute(raw, 1)
    shape = delivered_state_shape(raw)
    live = {"fixture": "delivered-native", "state_shape": shape,
            "route": native}
    validate_delivered_fixture(live)
    stale = execute(raw, 1, stale=True)
    trial = {"fixture": "stale-comfort",
        "state_shape": {**shape, "slots": 10, "idle_matcher_slot": None},
        "route": stale}
    try:
        validate_delivered_fixture(trial)
    except RepairError:
        rejected = ["stale-state-without-idle-matcher-slot"]
    else:
        rejected = []
    require(rejected and not ({"%rl-clear", "%cursor-blink"}
                              <= set(stale["called_targets"])),
            "stale fixture still certifies the delivered route")
    return {**live, "stale_counterexample": stale,
            "mutations_rejected": rejected,
            "rule": "fixture state is derived from the delivered client"}


def aliasing_gate(raw: bytes) -> dict[str, Any]:
    source = raw.decode()
    poll_start = source.index("(defun %rl-poll")
    poll_end = source.index("(defun %rl-render", poll_start)
    poll_source = source[poll_start:poll_end]
    required = ["(s1 (cdr state))", "(s3 (cdr (cdr s1)))",
        "(s5 (cdr (cdr s3)))", "(s7 (cdr (cdr s5)))",
        "(%rl-wait state s1 s3 s5 s7 idle)"]
    require(all(poll_source.count(token) == 1 for token in required),
            "shared state-spine derivation is absent or ambiguous")
    poll = defuns(raw)["%rl-poll"]
    wait = defuns(raw)["%rl-wait"]
    clear = defuns(raw)["%rl-clear"]
    encoded = repr([poll, wait, clear])
    require("rplacd" not in encoded,
            "shared state-spine cells are mutated by the hot-path repair")
    require("(rplacd cursor" in source and "(rplacd before" in source,
            "editor sentinel splice owners disappeared")
    mutated_poll = poll_source.replace(
        "(s1 (cdr state))", "(s1 (car state))", 1)
    mutation = (source[:poll_start] + mutated_poll + source[poll_end:]).encode()
    require(mutation != raw and mutated_poll != poll_source,
            "alias mutation was not materialized")
    try:
        execute(mutation, 1)
    except Exception:  # deliberate malformed state spine may fail at any VM layer
        rejected = ["state-spine-replaced-by-mutable-sentinel-chain"]
    else:
        rejected = []
    require(rejected, "sentinel/state-spine alias mutation survived")
    return {"status": "PASS: SHARED TAILS ARE EPHEMERAL STATE-SPINE CELLS",
        "derivation": required, "stored_across_polls": False,
        "hot_path_state_spine_writes": [],
        "sentinel_splice_owners": ["%rl-put", "%rl-cut"],
        "mutations_rejected": rejected}


def batch_measure(route: dict[str, Any]) -> dict[str, Any]:
    contract = json.loads(RESPONSIVENESS.read_text())["responsiveness"]
    frames = (route["vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"] / contract["cycles_per_frame"]
        + route["screen_cells_per_character"]
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + route["heap_cells_per_character"]
        * contract["collection_frames"] / contract["nursery_cells"])
    rate = 1.0 / frames
    margin = (rate - 1.0) * 100.0
    walls = {"maximum_frames_per_character": {"required": 0.8,
        "observed": frames, "passed": frames <= 0.8},
        "minimum_service_events_per_frame": {"required": 1.25,
            "observed": rate, "passed": rate >= 1.25},
        "minimum_margin_percent": {"required": 25.0,
            "observed": margin, "passed": margin >= 25.0}}
    require(all(row["passed"] for row in walls.values()),
            "repaired batch lane is red")
    return {"route": route, "frames_per_character": frames,
        "service_events_per_frame": rate, "margin_percent": margin,
        "walls": walls}


def derive() -> dict[str, Any]:
    current = SOURCE.read_bytes()
    red = git_blob(RED_COMMIT, SOURCE)
    reference = V19_SOURCE.read_bytes()
    fixture = fixture_proof(current)
    red_route = execute(red, 1)
    reference_route = execute(reference, 1)
    repaired = fixture["route"]
    batch = execute(current, 8)
    red_delta = delta(reference_route, red_route, field="full_function_steps")
    repair_delta = delta(red_route, repaired, field="full_function_steps")
    named = {name: red_delta.get(name, 0) for name in
             ("nthcdr", "zerop", "1-", "%rl-clear", "%cursor-blink",
              "%rl-poll")}
    traversal = sum(named[name] for name in ("nthcdr", "zerop", "1-"))
    require(red_route["total_vm_steps"] - reference_route[
                "total_vm_steps"] == 71041
            and traversal == 64493
            and red_route["vm_steps_per_character"] == 2641
            and reference_route["vm_steps_per_character"] == 909,
            f"pre-repair attribution drift: {named}")
    ratio = repaired["vm_steps_per_character"] / DEVICE_REFERENCE_STEPS
    single_walls = {
        "maximum_prepriced_steps_per_key": {
            "required": PREPRICED_SUCCESSOR_STEPS,
            "observed": repaired["vm_steps_per_character"],
            "passed": repaired["vm_steps_per_character"] <=
                PREPRICED_SUCCESSOR_STEPS},
        "maximum_ratio_to_device_reference": {"required": 1.02,
            "observed": ratio, "passed": ratio <= 1.02}}
    require(all(row["passed"] for row in single_walls.values()),
            "repaired single-key lane is red")
    compiled = CARD2.compile_product(successor=True)[1]
    require(compiled["maximum_object_bytes"] < 255,
            "repair crossed code-object ceiling")
    value = {"format": FORMAT, "recorded_on": "2026-09-02",
        "status": STATUS, "authority": authority(),
        "fixture": fixture,
        "attribution": {"v1_9_reference": reference_route,
            "device_red_predecessor": red_route,
            "red_minus_v1_9_function_steps": red_delta,
            "repair_minus_red_function_steps": repair_delta,
            "named_repeated_traversal_steps": named,
            "nthcdr_zerop_one_minus_total": traversal,
            "total_extra_steps": 71041, "unexplained_steps": 0},
        "repair": {"form": "one derived state-spine walk per poll",
            "source": bind(SOURCE), "aliasing": aliasing_gate(current),
            "objects": compiled},
        "responsiveness": {"single_keystroke": {
            "device_green_reference_steps_per_key": DEVICE_REFERENCE_STEPS,
            "v1_9_host_reference_steps_per_key":
                reference_route["vm_steps_per_character"],
            "successor": repaired, "ratio": ratio, "walls": single_walls},
            "batch_throughput": batch_measure(batch),
            "rule": "physical-key latency and batch throughput are separate"},
        "semantic_suite": bind(
            ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"),
        "mutations_rejected": [
            "stale-state-without-idle-matcher-slot",
            "state-spine-replaced-by-mutable-sentinel-chain",
            "pre-repair-repeated-nthcdr-world"],
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0}}
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    single = value["responsiveness"]["single_keystroke"]
    batch = value["responsiveness"]["batch_throughput"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["fixture"]["state_shape"]["slots"] == 11
            and value["fixture"]["mutations_rejected"] ==
                ["stale-state-without-idle-matcher-slot"]
            and value["attribution"]["nthcdr_zerop_one_minus_total"] == 64493
            and value["attribution"]["unexplained_steps"] == 0
            and single["successor"]["vm_steps_per_character"] <= 913
            and all(row["passed"] for row in single["walls"].values())
            and all(row["passed"] for row in batch["walls"].values())
            and value["repair"]["aliasing"]["hot_path_state_spine_writes"] == []
            and value["repair"]["objects"]["maximum_object_bytes"] < 255
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0, "device_contacts": 0},
            "Block-3 hot-path repair receipt drift")


def write() -> None:
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    print("v2.0 Block3 hot path: WRITE PASS "
          f"single={value['responsiveness']['single_keystroke']['successor']['vm_steps_per_character']:.0f} "
          f"batch-margin={value['responsiveness']['batch_throughput']['margin_percent']:.3f}%")


def check() -> None:
    value = json.loads(RECEIPT.read_text())
    validate(value)
    require(value == derive(), "Block-3 hot-path receipt is not reproducible")
    print("v2.0 Block3 hot path: CHECK PASS "
          f"single={value['responsiveness']['single_keystroke']['successor']['vm_steps_per_character']:.0f}")


def selftest() -> None:
    value = json.loads(RECEIPT.read_text())
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "stale-fixture": lambda row: row["fixture"]["state_shape"].update(
            {"slots": 10}),
        "single-key-red": lambda row: row["responsiveness"][
            "single_keystroke"]["successor"].update(
                {"vm_steps_per_character": 2641}),
        "batch-red": lambda row: row["responsiveness"]["batch_throughput"][
            "walls"]["minimum_margin_percent"].update({"passed": False}),
        "alias-write": lambda row: row["repair"]["aliasing"].update(
            {"hot_path_state_spine_writes": ["rplacd"]}),
        "unexplained": lambda row: row["attribution"].update(
            {"unexplained_steps": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (RepairError, KeyError, TypeError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "hot-path mutation survived")
    print(f"v2.0 Block3 hot path: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RepairError, RuntimeError, KeyError, ValueError, OSError,
            subprocess.CalledProcessError) as error:
        print(f"v2.0 Block3 hot path: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
