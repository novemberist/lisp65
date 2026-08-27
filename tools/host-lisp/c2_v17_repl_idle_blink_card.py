#!/usr/bin/env python3
"""Permanent host gate for v1.7 Block-3 card 2: REPL idle/blink."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

import bytecode_p0 as VM  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_v17_sexp_scanner_paint_card as CARD1  # noqa: E402
import evidence_era as ERA  # noqa: E402


CONTRACT = ROOT / "config/c2-v17-repl-idle-blink-card-contract.json"
SOURCE = ROOT / "lib/stdlib-read-line.lisp"
SHARED = ROOT / "lib/sexp-depth.lisp"
LINE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
WORKBENCH_SUITE = ROOT / "tests/bytecode/stdlib/p0-stdlib-einsuite-core-workbench-subset.json"
IDE_SUITE = ROOT / "tests/bytecode/libs/p0-ide-core-lib.json"
PRICING = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.7-editing-surface-polish-pricing-receipt.json")
CARD1_RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                       "c2.3-v1.7-sexp-scanner-paint-card-receipt.json")
RECEIPT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                  "c2.3-v1.7-repl-idle-blink-card-receipt.json")
METADATA_INDEX = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                         "v11-function-metadata-index.json")
FORMAT = "lisp65-c2-v17-repl-idle-blink-card-receipt-v1"
SEALED_COMMIT = "9fe443da"
CARD3_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-ide-idle-blink-card-host-receipt.json")
FUNCTIONS = [
    "%cursor-blink", "%rl-start", "%rl-kind", "%rl-scan", "%rl-close",
    "%rl-open", "%rl-idle", "%rl-clear", "%rl-paint", "%rl-poll",
]
PASS_ADAPTERS = {
    "%rl-scan": "%sexp-scan",
    "%rl-close": "%sexp-close",
    "%rl-open": "%sexp-open",
}
ALLOCATORS = {"cons", "list", "append", "reverse", "string->list", "list->string"}


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def forms(source: str) -> dict[str, Any]:
    result = {}
    for form in C.parse_all(source):
        if (isinstance(form, list) and len(form) >= 4 and form[0] == "defun"
                and isinstance(form[1], str)):
            result[form[1]] = form
    return result


def _walk_calls(form: Any, found: list[str]) -> None:
    if not isinstance(form, list) or not form:
        return
    if isinstance(form[0], str):
        found.append(form[0])
    for item in form:
        _walk_calls(item, found)


def calls_by_function(source: str) -> dict[str, list[str]]:
    result = {}
    for name, form in forms(source).items():
        calls: list[str] = []
        for body in form[3:]:
            _walk_calls(body, calls)
        result[name] = calls
    return result


def line_suite(source_override: Path | None = None) -> dict[str, Any]:
    suite = P0._apply_suite_transforms(P0._read_suite(LINE_SUITE))
    if source_override is not None:
        sources = []
        for item in suite["sources"]:
            if item.replace("\\", "/") == "lib/stdlib-read-line.lisp":
                sources.append(str(source_override))
            else:
                sources.append(item)
        suite["sources"] = sources
    return suite


def compile_product(source_override: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = line_suite(source_override)
    code = P0._compile_suite(suite, include_cases=False)[2]
    missing = sorted(set(FUNCTIONS) - set(code))
    require(not missing, f"card-2 objects absent from product profile: {missing}")
    sizes = {name: len(code[name].encode()) for name in FUNCTIONS}
    return suite, {"function_bytes": sizes, "total_function_bytes": sum(sizes.values()),
                   "maximum_object_bytes": max(sizes.values())}


class CallTrace:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call(self, caller: str, kind: str, target: str, argc: int, **_kwargs: Any) -> None:
        self.calls.append({"caller": caller, "kind": kind,
                           "target": target, "argc": argc})


class ScreenVM(VM.P0VM):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.screen_writes: list[tuple[int, int, int, int]] = []

    def _callprim(self, prim_id: int, argc: int, stack: list[int], **kwargs: Any) -> int:
        if prim_id == 11 and argc == 4:
            args = stack[-argc:]
            self.screen_writes.append(tuple(VM.fixval(value) for value in args))
        return super()._callprim(prim_id, argc, stack, **kwargs)


TRACE_CASES = [
    {
        "name": "ordinary",
        "expr": "(read-line)", "expect": '"abc"',
        "key_events": [97, {"empty_polls": 3}, 98, 99, 13],
        "memory_read_sequences": {"0xff83": [0] * 20},
    },
    {
        "name": "composed",
        "expr": "(read-line)", "expect": '"(a)"',
        "key_events": [40, 97, 41, {"empty_polls": 3}, 157,
                       {"empty_polls": 3}, 13],
        "memory_read_sequences": {"0xff83": [0] * 30},
    },
    {
        "name": "marked-hidden",
        "expr": "(let* ((head (cons 0 (quote (41)))) "
                "(blink (cons 0 't)) "
                "(idle (list blink 0 0 0 0 nil 0 0 "
                "(cons 0 0) (cons 0 0) 't)) "
                "(state (list head head head 0 1 0 80 24 nil nil idle))) "
                "(%cursor-blink state nil))",
        "expect": "nil", "memory_read_sequences": {"0xff83": [32]},
    },
    {
        "name": "forced-visible",
        "expr": "(let* ((head (cons 0 (quote (41)))) "
                "(blink (cons 0 nil)) "
                "(idle (list blink 0 0 0 0 nil 0 0 "
                "(cons 0 0) (cons 0 0) nil)) "
                "(state (list head head head 0 1 0 80 24 nil nil idle))) "
                "(%cursor-blink state 't))",
        "expect": "nil", "memory_read_sequences": {"0xff83": [0]},
    },
]


def trace_observations(source_override: Path | None = None) -> dict[str, Any]:
    suite = line_suite(source_override)
    suite["cases"] = copy.deepcopy(TRACE_CASES)
    (heap, _names, _code, entry_flags, resident_flags, _bundle, directory,
     compiled_cases, entries, _inliner) = P0._compile_suite(suite)
    profile, ledger = P0._suite_abi(suite)
    rows = {}
    for case, compiled, entry in zip(TRACE_CASES, compiled_cases, entries):
        trace = CallTrace()
        vm = ScreenVM(
            heap=heap.clone(), directory=directory,
            macro_symbols=P0._macro_symbol_objs(heap, entry_flags, resident_flags),
            max_steps=500_000, max_call_args=12, trace=trace,
            key_events=case.get("key_events"), private_key_event_modes=True,
            memory_read_sequences=case.get("memory_read_sequences"),
            abi_profile=profile, abi_ledger=ledger,
            delivered_callprims=suite.get("delivered_callprims"),
        )
        result = vm.run(directory[heap.intern(entry)], [])
        got = vm.heap.obj_to_text(result)
        require(got == compiled["expect"],
                f"{case['name']} result drift: expected {compiled['expect']!r}, got {got!r}")
        rows[case["name"]] = {
            "steps": vm.steps,
            "screen_writes": [list(row) for row in vm.screen_writes],
            "calls": trace.calls,
        }
    ordinary_targets = [row["target"] for row in rows["ordinary"]["calls"]]
    require(not any(target.startswith("%sexp-") for target in ordinary_targets),
            "ordinary input entered the matcher")
    composed = [tuple(row) for row in rows["composed"]["screen_writes"]]
    highlight = (0, 24, 40, 7)
    cursor = (2, 24, 41, 129)
    restored = (0, 24, 40, 1)
    require(highlight in composed and cursor in composed and restored in composed,
            "composed framebuffer omitted highlight, cursor or restoration")
    require(any(index > composed.index(highlight) and row == restored
                for index, row in enumerate(composed)),
            "old delimiter pair was not restored after the cursor moved")
    require(rows["marked-hidden"]["screen_writes"] == [[0, 24, 41, 7]],
            "hidden cursor erased a delimiter highlight")
    require(rows["forced-visible"]["screen_writes"] == [[0, 24, 41, 129]],
            "input handoff did not force the cursor visible")
    return {
        "ordinary_shared_calls": [],
        "composed_required_writes": [list(highlight), list(cursor), list(restored)],
        "marked_hidden_write": rows["marked-hidden"]["screen_writes"][0],
        "forced_visible_write": rows["forced-visible"]["screen_writes"][0],
        "case_steps": {name: row["steps"] for name, row in rows.items()},
    }


def validate_source(source: str) -> dict[str, Any]:
    defs = forms(source)
    calls = calls_by_function(source)
    require(all(name in defs for name in FUNCTIONS), "card-2 definition missing")
    require("%ide-idle" not in defs, "card 3 activated prematurely")
    input_users = sorted(name for name in FUNCTIONS if "key-event" in calls[name])
    require(input_users == ["%rl-poll"],
            f"line editor has multiple input owners: {input_users}")
    frame_users = sorted(name for name in FUNCTIONS if "peek" in calls[name])
    require(frame_users == ["%cursor-blink"],
            f"frame counter has multiple card-2 consumers: {frame_users}")
    for name in FUNCTIONS:
        require(not (ALLOCATORS & set(calls[name])),
                f"idle-path object allocates: {name}")
    for adapter, target in PASS_ADAPTERS.items():
        require(calls[adapter].count("%rl-idle") == 1,
                f"{adapter} does not schedule exactly one pass")
        require(target not in calls[adapter],
                f"{adapter} bypasses the sole shared seam")
    require(source.count("(peek 255 131)") == 2,
            "frame-low authority drift (setup plus blink expected)")
    require("(>= elapsed 32)" in source, "32-frame half-period drift")
    require("(%cursor-blink state 't)\n                event" in source,
            "cursor is not forced visible before event dispatch")
    require("(if (car (nthcdr 10 idle)) 7 1)" in source,
            "hidden cursor no longer preserves delimiter paint")
    require("(%rl-clear state 't)" in source,
            "input handoff no longer clears the stale pair")
    require("(list head head head 0 0 0 columns row nil nil idle)" in source,
            "native line state no longer owns the idle extension")
    require("(if (nthcdr 8 state)" in source,
            "parked Comfort fallback disappeared")
    callers = CARD1.caller_audit()
    require(callers["activation"] == "surface-owned",
            "shared core remains inactive after card 2")
    return {"surface_input_owner": "native read-line",
            "card2_idle_input_boundary": "%rl-poll",
            "existing_append_drain_same_surface": "%rl-put/key-event mode 3",
            "frame_owner": "%cursor-blink",
            "hot_allocating_calls": [], "card3_activation": False,
            "shared_caller_audit": callers}


def suite_ownership() -> dict[str, Any]:
    line = P0._apply_suite_transforms(P0._read_suite(LINE_SUITE))
    ide = P0._apply_suite_transforms(P0._read_suite(IDE_SUITE))
    require(all(name in line.get("functions", []) for name in FUNCTIONS),
            "line-library profile omits card-2 freight")
    duplicates = sorted(set(FUNCTIONS) & set(ide.get("functions", [])))
    require(not duplicates, f"IDE emits card-2 duplicates: {duplicates}")
    return {"line_library_owner": LINE_SUITE.relative_to(ROOT).as_posix(),
            "ide_emitted_duplicates": [], "ide_activation_deferred": True}


def enforce_sizes(sizes: dict[str, int], limit: int) -> None:
    bad = {name: size for name, size in sizes.items() if size >= limit}
    require(not bad, f"code object reaches 255-byte ceiling: {bad}")


def mutation_caught(name: str, action: Any) -> dict[str, Any]:
    try:
        action()
    except Exception as exc:
        return {"name": name, "caught": True, "diagnostic": str(exc)[:240]}
    raise CardError(f"mutation survived: {name}")


def _with_source(source: str, action: Any) -> Any:
    with tempfile.NamedTemporaryFile("w", suffix=".lisp", delete=False) as handle:
        path = Path(handle.name)
        handle.write(source)
    try:
        return action(path)
    finally:
        path.unlink()


def mutations(source: str) -> list[dict[str, Any]]:
    rows = []
    ordinary = source.replace("(or (= code 40) (or (= code 41) (= code 34)))",
                              "(or (= code 97) (or (= code 41) (= code 34)))", 1)
    rows.append(mutation_caught(
        "ordinary-code-enters-scanner",
        lambda: _with_source(ordinary, trace_observations)))
    rows.append(mutation_caught(
        "frame-authority-moved",
        lambda: validate_source(source.replace("(peek 255 131)", "(peek 255 132)", 1))))
    rows.append(mutation_caught(
        "event-dispatch-does-not-force-visible",
        lambda: validate_source(source.replace("(%cursor-blink state 't)\n                event",
                                               "(%cursor-blink state nil)\n                event", 1))))
    stale = source.replace("(%rl-clear state 't)", "(%rl-clear state nil)", 1)
    rows.append(mutation_caught("stale-pair-survives-input",
                                lambda: validate_source(stale)))
    marked = source.replace("(if (car (nthcdr 10 idle)) 7 1)",
                            "(if (car (nthcdr 10 idle)) 1 1)", 1)
    rows.append(mutation_caught("hidden-cursor-erases-delimiter",
                                lambda: validate_source(marked)))
    rows.append(mutation_caught(
        "second-line-input-owner",
        lambda: validate_source(source.replace(
            "(car (nthcdr 10 state))", "(key-event 0)", 1))))
    rows.append(mutation_caught(
        "foreign-paint-owner",
        lambda: CARD1.caller_audit(
            "(defun %foreign (s) (%sexp-paint s nil nil 0 0 80 0 0))")))
    rows.append(mutation_caught(
        "object-reaches-255",
        lambda: enforce_sizes({"%cursor-blink": 255}, 255)))
    rows.append(mutation_caught(
        "ide-idle-activated-in-card2",
        lambda: validate_source(source + "\n(defun %ide-idle () nil)\n")))
    shared = SHARED.read_text(encoding="utf-8")
    start = shared.index("%sexp-scan source codes stop i packed")
    end = shared.find("\n(defun ", start)
    body = shared[start:end]
    fourth = shared[:start] + body.replace("(+ i 3)", "(+ i 4)") + shared[end:]
    rows.append(mutation_caught("fourth-code-shared-pass",
                                lambda: CARD1.compile_core(fourth)))
    return rows


def build_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    pricing = load(PRICING)
    card1 = load(CARD1_RECEIPT)
    require(contract.get("format") ==
            "lisp65-c2-v17-repl-idle-blink-card-contract-v1",
            "card-2 contract format drift")
    source = SOURCE.read_text(encoding="utf-8")
    source_audit = validate_source(source)
    _suite, compiled = compile_product()
    limit = int(contract["limits"]["max_code_object_bytes_exclusive"])
    enforce_sizes(compiled["function_bytes"], limit)
    expected_sizes = {
        "%cursor-blink": 186, "%rl-start": 208, "%rl-kind": 182,
        "%rl-scan": 168, "%rl-close": 208, "%rl-open": 199,
        "%rl-idle": 92, "%rl-clear": 187, "%rl-paint": 228,
        "%rl-poll": 195,
    }
    require(compiled["function_bytes"] == expected_sizes,
            f"exact emitted card-2 sizes drift: {compiled['function_bytes']}")
    observations = trace_observations()
    live_suite = P0.check_suite(
        "v1.7-card2-native-line-successor", line_suite())
    ownership = suite_ownership()
    before = contract["limits"]["delivery_free_after_card1"]
    minimum = contract["limits"]["minimum_free"]
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in FUNCTIONS)
    after = {"symbol_slots": before["symbol_slots"] - len(FUNCTIONS),
             "namepool_bytes": before["namepool_bytes"] - name_bytes}
    margin = {"symbol_slots": after["symbol_slots"] - minimum["symbol_slots"],
              "namepool_bytes": after["namepool_bytes"] - minimum["namepool_bytes"]}
    require(name_bytes == 99 and after == {"symbol_slots": 87, "namepool_bytes": 1223},
            "successor name pricing arithmetic drift")
    require(margin["symbol_slots"] >= 0 and margin["namepool_bytes"] >= 0,
            "card-2 successor price crosses release floor")
    block_total = int(card1["exact_bank2_function_bytes"]) + compiled["total_function_bytes"]
    require(block_total == 2849, "exact card-1 plus card-2 byte total drift")
    mutation_rows = mutations(source)
    require(all(row["caught"] for row in mutation_rows), "mutation set incomplete")
    metadata = load(METADATA_INDEX)
    metadata_names = {row["name"] for row in metadata.get("records", [])}
    require(not (set(FUNCTIONS) & metadata_names),
            "private idle/blink freight leaked into public metadata")
    pricing_projection = pricing["matcher"]["idle_schedule"]["historical_frame_equivalent"]
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-26",
        "status": "passed-host-card-2-native-line-idle-blink",
        "inputs": [bind(CONTRACT), bind(PRICING), bind(CARD1_RECEIPT), bind(SOURCE),
                   bind(SHARED), bind(LINE_SUITE), bind(WORKBENCH_SUITE),
                   bind(IDE_SUITE), bind(METADATA_INDEX),
                   bind(Path(__file__).resolve()),
                   bind(ROOT / "tools/host-lisp/c2_v17_sexp_scanner_paint_card.py")],
        "exact_emission": {
            "card2_function_bytes": compiled["function_bytes"],
            "card2_total_bytes": compiled["total_function_bytes"],
            "maximum_object_bytes": compiled["maximum_object_bytes"],
            "card1_total_bytes": card1["exact_bank2_function_bytes"],
            "card1_plus_card2_total_bytes": block_total,
            "original_conservative_block3_envelope_bytes": 1684,
            "successor_repricing_required": True,
            "reason": ("the accepted two-name prototype could not express the "
                       "resumable state machine below the 255-byte object ceiling"),
        },
        "capacity": {
            "free_before_card2": before, "card2_names": list(FUNCTIONS),
            "card2_name_bytes": name_bytes, "free_after_card2": after,
            "minimum_free": minimum, "margin_after_card2": margin,
            "world": "device-measured v1.6 delivery world after accepted card 1",
        },
        "scheduling": {
            "codes_per_poll": 3,
            "pass_adapters": PASS_ADAPTERS,
            "shared_pass_self_cap": "min(stop,i+3)",
            "ordinary_input_bypasses_scanner": True,
            "idle_hot_allocations": 0,
        },
        "blink": {
            "frame_counter_low": "0xff83", "half_period_frames": 32,
            "single_timer_owner": source_audit["frame_owner"],
            "forced_visible_before_dispatch": True,
            "delimiter_attribute_preserved_while_hidden": True,
        },
        "ownership": {**ownership, **source_audit},
        "composed_framebuffer": observations,
        "live_line_suite": {
            "functions": live_suite["functions"],
            "cases": live_suite["cases"],
            "steps": live_suite["steps"],
            "includes_all_historical_navigation_cases": True,
        },
        "historical_timing": {
            "projection": pricing_projection,
            "claim": "historical scheduling projection only; no card-2 device evidence",
        },
        "mutations": mutation_rows,
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Host-only card 2. Activates the native line editor only. Claims no "
            "IDE or Comfort activation, current product link, device timing, "
            "medium or hardware acceptance. The 2,849-byte combined total is "
            "exact Bank-2 object freight, not a current linked-plane claim."
        ),
        "next": "review card 2; card 3 remains closed",
    }


def check_sealed_successor() -> tuple[dict[str, Any], dict[str, Any]]:
    """Retain card 2's reviewed world while card 3 owns live evolution."""
    require(RECEIPT.is_file() and not RECEIPT.is_symlink(),
            "REPL idle/blink receipt absent")
    raw = RECEIPT.read_bytes()
    require(raw == ERA.era_blob(
        SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix()),
        "sealed REPL idle/blink receipt was rewritten")
    value = json.loads(raw)
    require(value.get("format") == FORMAT
            and value["exact_emission"]["card2_total_bytes"] == 1853
            and value["exact_emission"]["maximum_object_bytes"] == 228,
            "sealed card-2 identity drift")
    successor = load(CARD3_RECEIPT)
    require(successor.get("status") ==
            "passed-host-card-3-ide-idle-blink-prelink"
            and bind(RECEIPT) in successor.get("inputs", []),
            "card-3 successor does not bind reviewed card 2")
    source = SOURCE.read_text(encoding="utf-8")
    calls = calls_by_function(source)
    require("%frame-low" in forms(source)
            and calls["%cursor-blink"].count("%frame-low") == 1
            and "peek" not in calls["%cursor-blink"]
            and calls["%rl-poll"].count("key-event") == 2,
            "live card-3 successor weakened card-2 timer/input ownership")
    observations = trace_observations()
    compiled = compile_product()[1]
    require(compiled["function_bytes"]["%cursor-blink"] == 180
            and compiled["maximum_object_bytes"] < 255,
            "live card-3 successor crossed card-2 object ceiling")
    return value, {"observations": observations, "emission": compiled}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if not args.write and CARD3_RECEIPT.is_file():
            receipt, live = check_sealed_successor()
            free = receipt["capacity"]["free_after_card2"]
            print("v1.7 REPL idle/blink card: PASS sealed=9fe443da "
                  f"free={free['symbol_slots']}/{free['namepool_bytes']} "
                  f"live_cursor={live['emission']['function_bytes']['%cursor-blink']}")
            return 0
        receipt = build_receipt()
        payload = canonical(receipt)
        if args.write:
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(payload)
        if args.check or not args.write:
            require(RECEIPT.is_file(), "REPL idle/blink receipt absent")
            require(RECEIPT.read_bytes() == payload, "REPL idle/blink receipt drift")
        exact = receipt["exact_emission"]
        free = receipt["capacity"]["free_after_card2"]
        print("v1.7 REPL idle/blink card: PASS "
              f"bytes={exact['card2_total_bytes']} max={exact['maximum_object_bytes']} "
              f"free={free['symbol_slots']}/{free['namepool_bytes']} "
              f"mutations={len(receipt['mutations'])}")
        return 0
    except (CardError, CARD1.CardError, P0.StdlibCheckError,
            C.CompileError, VM.VMError) as exc:
        print(f"v1.7 REPL idle/blink card: FIRST RED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
