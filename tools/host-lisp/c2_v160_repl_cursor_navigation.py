#!/usr/bin/env python3
"""Permanent source/artifact/parity/capacity gate for v1.6 REPL navigation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

sys.setrecursionlimit(max(sys.getrecursionlimit(), 4096))


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_stdlib as P  # noqa: E402
import c2_ship_input_wait_gate as OLD  # noqa: E402
import evidence_era as ERA  # noqa: E402
import v11_l_lite_keymap as KEYMAP  # noqa: E402


CONTRACT = ROOT / "config/c2-v160-repl-cursor-navigation-contract.json"
COMFORT_CONTRACT = ROOT / "config/c2-v160-comfort-repl-implementation-contract.json"
KEYMAP_CONTRACT = ROOT / "config/v11-l-lite-keymap.json"
READ_LINE = ROOT / "lib/stdlib-read-line.lisp"
WAIT = ROOT / "lib/stdlib-wait.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-time-base.json"
PRIOR_CAPACITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-release-preflight-receipt.json"
)
BUILD = ROOT / "build/c2.3/v1.6-repl-cursor-navigation"
LIMIT_SUITE = BUILD / "limit/suite.json"
LIMIT_PREFIX = BUILD / "limit/stdlib-p0"
LIMIT_OBSERVATIONS = BUILD / "limit/observations.json"
PUBLIC_SUITE = BUILD / "public-only/suite.json"
PUBLIC_SOURCE = BUILD / "public-only/stdlib-read-line.lisp"
PUBLIC_PREFIX = BUILD / "public-only/stdlib-p0"
PUBLIC_OBSERVATIONS = BUILD / "public-only/observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-repl-cursor-navigation-host-first-receipt.json"
)
COMMISSION_COMMIT = "fc627e57"

FUNCTIONS = [
    "%rl-render", "%rl-cut", "%rl-move", "%rl-put", "%rl-dispatch",
    "%read-line-loop", "read-line", "%wait-until", "wait",
]
REGISTERED_SUCCESSOR_FUNCTIONS = ["%rl-screen-tail"]
PRIVATE_MODE2 = "(key-event 2)"
PRIVATE_DRAIN = "(if (= (car s4) 250) nil (key-event 3))"
NAVIGATION_CASES = {
    "read-line-delete-legacy-127": "ac",
    "read-line-insert-middle-cursor-left": "abc",
    "read-line-insert-middle-control-b": "abc",
    "read-line-control-f-right": "acb",
    "read-line-line-start-end": "xabcy",
    "read-line-delete-forward": "ac",
    "read-line-boundary-noops": "a",
    "read-line-ignore-cursor-up-without-history": "a",
}
OLD_PRIVATE_NAMES = [
    "%read-line-clear-from", "%read-line-render-reverse",
    "%read-line-finish", "%read-line-loop", "read-line",
]
NEW_PRIVATE_NAMES = FUNCTIONS[:7]


class CursorGateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CursorGateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def public_only_source(source: str) -> str:
    """Project the v1.6 public editor from the canonical Comfort-capable source."""
    require(source.count(PRIVATE_MODE2) == 1
            and source.count(PRIVATE_DRAIN) == 1,
            "private input-mode projection source drift")
    projected = source.replace(PRIVATE_MODE2, "nil", 1).replace(
        PRIVATE_DRAIN, "(if (= (car s4) 250) nil nil)", 1)
    require("(key-event 2)" not in projected and "(key-event 3)" not in projected,
            "public-only projection retained a private key-event mode")
    return projected


def generated_block(source: str) -> str:
    require(source.count(KEYMAP.REPL_BLOCK_BEGIN) == 1
            and source.count(KEYMAP.REPL_BLOCK_END) == 1,
            "generated REPL keymap boundary drift")
    _before, tail = source.split(KEYMAP.REPL_BLOCK_BEGIN, 1)
    body, _after = tail.split(KEYMAP.REPL_BLOCK_END, 1)
    return body.strip()


def source_gate(contract: dict[str, Any], keymap: dict[str, Any], source: str,
                suite: dict[str, Any]) -> dict[str, Any]:
    KEYMAP.validate(keymap)
    capacity = contract.get("capacity", {})
    allocation = contract.get("allocation", {})
    editor = contract.get("editor", {})
    require(
        contract.get("format") == "lisp65-c2-v160-repl-cursor-navigation-v1"
        and contract.get("status") == "owner-commissioned-host-first"
        and contract.get("commission_commit") == COMMISSION_COMMIT,
        "v1.6 cursor contract identity drift",
    )
    historical_bindings = [
        "return", "delete-backward", "cursor-left", "cursor-right",
        "control-d", "control-f", "control-b", "control-a", "control-e",
    ]
    successor_bindings = [
        "return", "delete-backward", "cursor-left", "cursor-right",
        "cursor-up", "cursor-down", "control-d", "control-f", "control-b",
        "control-a", "control-e",
    ]
    require(contract["keymap"]["bindings"] == historical_bindings,
            "accepted cursor-era keymap authority drift")
    require(COMFORT_CONTRACT.is_file(),
            "Comfort successor authority absent for Up/Down projection")
    comfort = load(COMFORT_CONTRACT)
    require(
        comfort.get("format") == "lisp65-c2-v160-comfort-repl-implementation-v1"
        and comfort.get("status") == "owner-authorized-host-first"
        and comfort["semantics"]["maximum_history_lines"] == 10
        and keymap["repl_line_projection"]["binding_ids"] == successor_bindings
        and generated_block(source) == KEYMAP.render_repl_expression(keymap).strip(),
        "authorized Comfort keymap successor/parity drift",
    )
    before, tail = source.split(KEYMAP.REPL_BLOCK_BEGIN, 1)
    _body, after = tail.split(KEYMAP.REPL_BLOCK_END, 1)
    outside = before + after
    for raw in ("(13 . 1109)", "(20 . 1101)", "(157 . 1106)",
                "(29 . 1107)", "(145 . 1108)", "(17 . 1003)",
                "(4 . 1102)", "(6 . 1107)",
                "(2 . 1106)", "(1 . 1104)", "(5 . 1103)"):
        require(raw not in outside, f"REPL binding escaped generated block: {raw}")
    for code in (1, 2, 4, 5, 6, 13, 17, 20, 29, 127, 145, 157):
        require(f"(= code {code})" not in outside,
                f"hard-coded REPL key escaped generated block: {code}")
    for token in (
        "(state (list head head head 0 0 0 columns row))",
        "(rplacd cursor inserted)",
        "(rplacd before (cdr removed))",
        "(rplaca (nthcdr 3 state) next-position)",
        "(if at-cursor 129 1)",
        "(%rl-move state (car state) 0)",
        "(%rl-move state (car (nthcdr 2 state)) length)",
        "(if (< (car (nthcdr 4 state)) 250)",
        PRIVATE_DRAIN,
        "(%string-from-codes codes)",
    ):
        require(token in source, f"REPL cursor/editor invariant drift: {token}")
    require(source.count("(rplaca (nthcdr 3 state) next-position)") == 2
            and source.count("(rplaca s3 next-position)") == 1,
            "not every edit/motion path publishes cursor position")
    require("native" not in editor["cursor_render"].lower()
            and editor["native_cursor_dependency"] is False,
            "native cursor dependency reintroduced")
    require(
        allocation == {
            "nursery_cells": 192,
            "initial_state_cells_before_first_key": 9,
            "maximum_cells_per_input_key": 4,
            "maximum_collections_on_one_key_for_any_incoming_phase": 1,
            "line_start_end_allocate_per_key": 0,
        },
        "cursor allocation contract drift",
    )
    require(
        capacity["resident_code_delta_bytes"] == 0
        and capacity["resident_state_delta_bytes"] == 0
        and capacity["native_primitive_delta"] == 0
        and capacity["d5_before"] == {"symbol_slots": 34, "namepool_bytes": 545}
        and capacity["d5_minimum"] == {"symbol_slots": 32, "namepool_bytes": 384}
        and capacity["d5_projected"] == {"symbol_slots": 32, "namepool_bytes": 562},
        "cursor placement/D5 contract drift",
    )
    projected_slots = (capacity["d5_before"]["symbol_slots"]
                       - (len(NEW_PRIVATE_NAMES) - len(OLD_PRIVATE_NAMES)))
    projected_names = (capacity["d5_before"]["namepool_bytes"]
                       + sum(len(name) + 1 for name in OLD_PRIVATE_NAMES)
                       - sum(len(name) + 1 for name in NEW_PRIVATE_NAMES))
    require(projected_slots == capacity["d5_projected"]["symbol_slots"] == 32
            and projected_names == capacity["d5_projected"]["namepool_bytes"] == 562,
            "D5 cursor projection arithmetic drift")
    cases = {row["name"]: row for row in suite.get("cases", [])}
    require(
        suite.get("extends") == "p0-stdlib-time-base.json"
        and suite.get("sources") == [
            "lib/stdlib-read-line.lisp", "lib/stdlib-wait.lisp"]
        and [name for name in suite.get("functions", [])
             if name not in REGISTERED_SUCCESSOR_FUNCTIONS] == FUNCTIONS
        and [name for name in suite.get("functions", [])
             if name in REGISTERED_SUCCESSOR_FUNCTIONS]
                == REGISTERED_SUCCESSOR_FUNCTIONS
        and set(NAVIGATION_CASES).issubset(cases),
        "cursor execution suite shape drift",
    )
    for name, expected in NAVIGATION_CASES.items():
        require(cases[name].get("expect") == json.dumps(expected),
                f"cursor case oracle drift: {name}")
    return {
        "status": "PASS: generated keymap, mutable line editor and Comfort successor",
        "generated_bindings": len(KEYMAP.repl_projection(keymap)),
        "functions": len(FUNCTIONS),
        "new_private_function_slots": 2,
        "namepool_bytes_reclaimed": 17,
        "resident_delta_bytes": 0,
        "native_delta": 0,
        "d5_projected": capacity["d5_projected"],
    }


def source_mutations(contract: dict[str, Any], keymap: dict[str, Any], source: str,
                     suite: dict[str, Any]) -> dict[str, str]:
    rows: list[tuple[str, dict[str, Any], dict[str, Any], str, dict[str, Any]]] = []

    def src(label: str, old: str, new: str) -> None:
        require(old in source, f"mutation anchor absent: {label}")
        rows.append((label, contract, keymap, source.replace(old, new, 1), suite))

    src("repl-generated-binding-drift", "(157 . 1106)", "(157 . 1107)")
    src("insert-does-not-link", "(rplacd cursor inserted)", "(rplacd cursor (cdr cursor))")
    src("delete-does-not-link", "(rplacd before (cdr removed))", "(cdr removed)")
    src("cursor-not-visible", "(if at-cursor 129 1)", "(if at-cursor 1 1)")
    src("cursor-position-not-stored",
        "(rplaca (nthcdr 3 state) next-position)",
        "(rplaca (nthcdr 3 state) position)")
    src("hardcoded-binding-outside-generator", "(defun %rl-render",
        "(if (= code 157) 1107 nil)\n(defun %rl-render")
    changed = copy.deepcopy(keymap)
    changed["repl_line_projection"]["legacy_aliases"][0]["command"] = 1102
    rows.append(("legacy-alias-parity", contract, changed, source, suite))
    changed_contract = copy.deepcopy(contract)
    changed_contract["allocation"]["maximum_cells_per_input_key"] = 5
    rows.append(("allocation-ceiling-drift", changed_contract, keymap, source, suite))
    changed_contract = copy.deepcopy(contract)
    changed_contract["capacity"]["resident_code_delta_bytes"] = 1
    rows.append(("resident-byte", changed_contract, keymap, source, suite))
    changed_contract = copy.deepcopy(contract)
    changed_contract["capacity"]["d5_projected"]["symbol_slots"] = 31
    rows.append(("D5-symbol-headroom", changed_contract, keymap, source, suite))
    changed_suite = copy.deepcopy(suite)
    changed_suite["cases"] = [row for row in changed_suite["cases"]
                              if row["name"] != "read-line-delete-forward"]
    rows.append(("forward-delete-case-absent", contract, keymap, source, changed_suite))
    changed_suite = copy.deepcopy(suite)
    changed_suite["functions"] = changed_suite["functions"][:-1]
    rows.append(("function-not-built", contract, keymap, source, changed_suite))
    require(len(rows) == 12, "cursor source mutation family count drift")
    rejected: dict[str, str] = {}
    for label, c, k, r, s in rows:
        try:
            source_gate(c, k, r, s)
        except (CursorGateError, KEYMAP.KeymapError) as error:
            rejected[label] = str(error)
        else:
            raise CursorGateError(f"cursor source mutation survived: {label}")
    return rejected


def run_suite(suite: Path, prefix: Path, observation: Path,
              *, expect_green: bool = True) -> dict[str, Any] | None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    bootstrap = (
        "import sys;"
        f"sys.path.insert(0,{str(HOST)!r});"
        "sys.setrecursionlimit(4096);"
        "import bytecode_p0_stdlib as m;"
        "raise SystemExit(m.main(sys.argv[1:]))"
    )
    process = subprocess.run([
        sys.executable, "-c", bootstrap, "--check", "--emit-artifacts",
        str(prefix.relative_to(ROOT)), "--observation-report",
        str(observation.relative_to(ROOT)), str(suite.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if expect_green:
        require(process.returncode == 0, "cursor suite red:\n" + process.stdout)
        return load(prefix.with_suffix(".manifest.json"))
    require(process.returncode != 0 and "read-line-insert-middle-cursor-left" in process.stdout,
            "executable Cursor-Left mutation did not reach/fail its real case")
    return None


def baseline_suite() -> Path:
    root = BUILD / "baseline"
    root.mkdir(parents=True, exist_ok=True)
    read_line = root / "stdlib-read-line.lisp"
    read_line.write_bytes(ERA.era_blob(COMMISSION_COMMIT, "lib/stdlib-read-line.lisp"))
    suite = json.loads(ERA.era_blob(
        COMMISSION_COMMIT,
        "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json").decode())
    suite["extends"] = str(BASE_SUITE.resolve())
    suite["sources"] = [
        read_line.relative_to(ROOT).as_posix(), "lib/stdlib-wait.lisp"]
    path = root / "suite.json"
    write(path, suite)
    return path


def executable_mutation(suite: dict[str, Any], source: str) -> str:
    root = BUILD / "mutation"
    root.mkdir(parents=True, exist_ok=True)
    changed = source.replace("(157 . 1106)", "(157 . 1107)", 1)
    require(changed != source, "executable mutation anchor absent")
    source_path = root / "stdlib-read-line.lisp"
    source_path.write_text(changed, encoding="utf-8")
    case = next(row for row in suite["cases"]
                if row["name"] == "read-line-insert-middle-cursor-left")
    mutation_suite = {
        "extends": str(BASE_SUITE.resolve()),
        "private_key_event_modes": True,
        "sources": [source_path.relative_to(ROOT).as_posix(), "lib/stdlib-wait.lisp"],
        "functions": FUNCTIONS + REGISTERED_SUCCESSOR_FUNCTIONS,
        "tailcall_self": ["%rl-render", "%wait-until"],
        "cases": [case],
    }
    suite_path = root / "suite.json"
    write(suite_path, mutation_suite)
    run_suite(suite_path, root / "stdlib-p0", root / "observations.json",
              expect_green=False)
    return "rejected-by-real-source-and-emitted-artifact-case"


def allocation_gate(suite_path: Path) -> dict[str, Any]:
    suite = P._read_suite(str(suite_path))
    (heap, _names, _code_by_name, _entry_flags, resident_flags,
     _bundle, directory, cases, entry_names, _inliner) = P._compile_suite(suite)
    macro_symbols = P._macro_symbol_objs(heap, {}, resident_flags)
    abi_profile, abi_ledger = P._suite_abi(suite)
    priced = {row["name"] for row in suite["cases"]
              if row["name"].startswith("read-line-")}
    rows: list[dict[str, Any]] = []
    for case, entry in zip(cases, entry_names):
        if case["name"] not in priced:
            continue
        case_heap = heap.clone()
        for tag in ("key", "shift", "control", "meta"):
            case_heap.intern(tag)
        vm = OLD.AllocationVM(
            heap=case_heap, directory=directory, macro_symbols=macro_symbols,
            max_steps=case.get("max_steps", 400000),
            max_call_args=suite.get("max_call_args"),
            key_events=case.get("key_events"), private_key_event_modes=True,
            abi_profile=abi_profile,
            abi_ledger=abi_ledger,
        )
        expected_error = case.get("expect_vm_error")
        try:
            vm.run(directory[case_heap.intern(entry)], [])
        except B.VMError as error:
            require(error.status == expected_error,
                    f"allocation lane error drift: {case['name']}: {error.status}")
        else:
            require(not expected_error, f"allocation lane missed error: {case['name']}")
        vm.finish_keys()
        rows.append({"case": case["name"], "keys": vm.key_rows})
    require({row["case"] for row in rows} == priced,
            "allocation case execution witness drift")
    keys = [key for row in rows for key in row["keys"]]
    maximum = max(key["cells"] for key in keys)
    require(maximum <= 4, f"cursor key allocates {maximum} cells (>4)")
    for code in (1, 2, 4, 5, 6, 17, 20, 29, 127, 145, 157):
        relevant = [key["cells"] for key in keys if key["code"] == code]
        require(relevant and max(relevant) <= 3,
                f"navigation/delete key allocation drift: {code}")
    return {
        "status": "PASS: per-key allocation contract",
        "cases": len(rows), "keys": len(keys),
        "maximum_cells_per_key": maximum,
        "navigation_maximum_cells": 3,
        "initial_state_cells_before_first_key": 9,
        "nursery_cells": 192,
    }


def artifact_gate() -> dict[str, Any]:
    baseline = run_suite(
        baseline_suite(), BUILD / "baseline/stdlib-p0",
        BUILD / "baseline/observations.json")
    candidate = run_suite(
        SUITE, BUILD / "candidate/stdlib-p0",
        BUILD / "candidate/observations.json")
    assert baseline is not None and candidate is not None
    delta = {
        "bank2_code_bytes": int(candidate["code_bytes"]) - int(baseline["code_bytes"]),
        "directory_bytes": int(candidate["directory_bytes"])
            - int(baseline["directory_bytes"]),
        "objects": int(candidate["objects"]) - int(baseline["objects"]),
        "resident_bytes": 0,
        "native_bytes": 0,
    }
    contract = load(CONTRACT)
    prior = load(PRIOR_CAPACITY)
    before = int(prior["geometry"]["bank2_headroom_bytes"])
    require(before == contract["capacity"]["bank2_headroom_before_bytes"] == 19493,
            "Bank-2 v1.5 authority drift")
    require(0 < delta["bank2_code_bytes"]
            <= contract["capacity"]["maximum_bank2_delta_bytes"]
            and delta["objects"] == 2 + len(REGISTERED_SUCCESSOR_FUNCTIONS),
            "cursor Bank-2/object price drift")
    observations = load(BUILD / "candidate/observations.json")["suites"][0]["observations"]
    observed = {row["name"]: row for row in observations}
    require(set(NAVIGATION_CASES).issubset(observed),
            "navigation observations absent")
    write(PUBLIC_SUITE, {
        "extends": str(SUITE.relative_to(ROOT)),
        "sources": [PUBLIC_SOURCE.relative_to(ROOT).as_posix()],
        "remove_sources": [READ_LINE.relative_to(ROOT).as_posix()],
        "private_key_event_modes": False,
        "description": (
            "Final-product lane: public read-line executes with only public "
            "key-event modes 0/1; private Comfort modes are unavailable."),
    })
    PUBLIC_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_SOURCE.write_text(
        public_only_source(READ_LINE.read_text(encoding="utf-8")),
        encoding="utf-8")
    run_suite(PUBLIC_SUITE, PUBLIC_PREFIX, PUBLIC_OBSERVATIONS)
    public_rows = load(PUBLIC_OBSERVATIONS)["suites"][0]["observations"]
    require({row["name"] for row in public_rows}.issuperset(NAVIGATION_CASES),
            "public-only navigation observations absent")
    long_text = "a" * 250
    viewport_text = "x" + ("a" * 82) + "y"
    left_scroll_text = "abcde" + ("a" * 77)
    write(LIMIT_SUITE, {
        "extends": str(SUITE.relative_to(ROOT)),
        "cases": [
            {
                "name": "read-line-exact-250-cursor-window",
                "expr": "(read-line)",
                "expect": json.dumps(long_text),
                "key_events": ([97] * 250) + [98, 13],
                "expect_key_events_remaining": 0,
                "expect_output_codes": [10],
                "expect_screen_rows": {"24": ("a" * 79) + " "},
                "max_steps": 3000000,
            },
            {
                "name": "read-line-cursor-window-start-end",
                "expr": "(read-line)",
                "expect": json.dumps(viewport_text),
                "key_events": ([97] * 82) + [1, 120, 5, 121, 13],
                "expect_key_events_remaining": 0,
                "expect_output_codes": [10],
                "expect_screen_rows": {"24": ("a" * 78) + "y "},
                "max_steps": 1000000,
            },
            {
                "name": "read-line-cursor-window-left-scroll",
                "expr": "(read-line)",
                "expect": json.dumps(left_scroll_text),
                "key_events": ([ord(ch) for ch in left_scroll_text]
                               + ([157] * 80) + [13]),
                "expect_key_events_remaining": 0,
                "expect_output_codes": [10],
                "expect_screen_rows": {"24": "cdeaaaaa"},
                "max_steps": 3000000,
            },
        ],
    })
    run_suite(LIMIT_SUITE, LIMIT_PREFIX, LIMIT_OBSERVATIONS)
    limit_rows = {
        row["name"]: row
        for row in load(LIMIT_OBSERVATIONS)["suites"][0]["observations"]
    }
    require(
        limit_rows["read-line-exact-250-cursor-window"]["result"]
            == json.dumps(long_text)
        and limit_rows["read-line-cursor-window-start-end"]["result"]
            == json.dumps(viewport_text)
        and limit_rows["read-line-cursor-window-left-scroll"]["result"]
            == json.dumps(left_scroll_text),
        "250-character/cursor viewport execution witness drift",
    )
    return {
        "baseline_manifest": bind(BUILD / "baseline/stdlib-p0.manifest.json"),
        "candidate_manifest": bind(BUILD / "candidate/stdlib-p0.manifest.json"),
        "observations": bind(BUILD / "candidate/observations.json"),
        "public_only_observations": bind(PUBLIC_OBSERVATIONS),
        "public_only_source": bind(PUBLIC_SOURCE),
        "limit_observations": bind(LIMIT_OBSERVATIONS),
        "delta": delta,
        "bank2_headroom_before_bytes": before,
        "bank2_headroom_after_bytes": before - delta["bank2_code_bytes"],
        "execution_lanes": 3,
        "public_only_key_event_modes": [0, 1],
        "navigation_cases": len(NAVIGATION_CASES) + 3,
    }


def run_selftest() -> dict[str, Any]:
    contract = load(CONTRACT)
    keymap = load(KEYMAP_CONTRACT)
    source = READ_LINE.read_text(encoding="utf-8")
    suite = load(SUITE)
    source_gate(contract, keymap, source, suite)
    rejected = source_mutations(contract, keymap, source, suite)
    executable = executable_mutation(suite, source)
    projection = public_only_source(source)
    changed = projection.replace("(if (= (car s4) 250) nil nil)",
                                 PRIVATE_DRAIN, 1)
    try:
        require(changed == public_only_source(source),
                "public projection reintroduced private mode 3")
    except CursorGateError as error:
        projection_mutation = str(error)
    else:
        raise CursorGateError("public projection mutation survived")
    return {"source_mutations": rejected, "executable_mutation": executable,
            "public_projection_mutation": projection_mutation}


def run_check() -> dict[str, Any]:
    selftest = run_selftest()
    source = source_gate(
        load(CONTRACT), load(KEYMAP_CONTRACT),
        READ_LINE.read_text(encoding="utf-8"), load(SUITE))
    artifacts = artifact_gate()
    allocation = allocation_gate(LIMIT_SUITE)
    value = {
        "format": "lisp65-c2-v160-repl-cursor-navigation-host-first-v1",
        "recorded_on": "2026-08-18",
        "status": "PASS: v1.6 REPL cursor navigation host-qualified",
        "promotable": False,
        "product_links": 0,
        "hardware_runs": 0,
        "source_contract": source,
        "mutations_rejected": selftest,
        "allocation": allocation,
        "artifacts": artifacts,
        "authority": {
            "contract": bind(CONTRACT), "keymap": bind(KEYMAP_CONTRACT),
            "comfort_successor_contract": bind(COMFORT_CONTRACT),
            "read_line": bind(READ_LINE), "suite": bind(SUITE),
            "keymap_generator": bind(ROOT / "tools/host-lisp/v11_l_lite_keymap.py"),
            "prior_capacity": bind(PRIOR_CAPACITY), "gate": bind(Path(__file__)),
        },
        "claim_limit": "host source/artifact semantics and capacity; no device claim",
        "next": "owner review closes cursor card; Comfort REPL remains unopened until then",
    }
    write(RECEIPT, value)
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            value = run_selftest()
            print("c2-v160-repl-cursor-navigation: SELFTEST PASS "
                  f"mutations={len(value['source_mutations'])}+2")
        else:
            value = run_check()
            delta = value["artifacts"]["delta"]
            print("c2-v160-repl-cursor-navigation: PASS "
                  f"cases={value['artifacts']['navigation_cases']}x3 "
                  f"mutations={len(value['mutations_rejected']['source_mutations'])}+2 "
                  f"max-cells/key={value['allocation']['maximum_cells_per_key']} "
                  f"bank2=+{delta['bank2_code_bytes']} "
                  f"headroom={value['artifacts']['bank2_headroom_after_bytes']} "
                  "D5=32/562 resident=+0 native=+0")
        return 0
    except (CursorGateError, KEYMAP.KeymapError, ERA.EraError, KeyError,
            OSError, ValueError, P.StdlibCheckError) as error:
        print(f"c2-v160-repl-cursor-navigation: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
