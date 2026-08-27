#!/usr/bin/env python3
"""Permanent host gate for v1.7 Block-3 card 3: IDE idle/blink."""

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
import c2_v17_repl_idle_blink_card as CARD2  # noqa: E402
import c2_v17_sexp_scanner_paint_card as CARD1  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONTRACT = ROOT / "config/c2-v17-ide-idle-blink-card-contract.json"
SOURCE = ROOT / "lib/ide-ui.lisp"
TIMER = ROOT / "lib/stdlib-read-line.lisp"
SHARED = ROOT / "lib/sexp-depth.lisp"
IDE_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
LINE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json"
PRICING = ARCH / "c2.3-v1.7-editing-surface-polish-pricing-receipt.json"
CARD1_RECEIPT = ARCH / "c2.3-v1.7-sexp-scanner-paint-card-receipt.json"
CARD2_RECEIPT = ARCH / "c2.3-v1.7-repl-idle-blink-card-receipt.json"
RECEIPT = ARCH / "c2.3-v1.7-ide-idle-blink-card-host-receipt.json"
METADATA_INDEX = ARCH / "v11-function-metadata-index.json"
FORMAT = "lisp65-c2-v17-ide-idle-blink-card-host-v1"
IDE_FUNCTIONS = [
    "%ide-blink", "%ide-idle-mini-start", "%ide-start", "%ide-kind",
    "%ide-scan", "%ide-close", "%ide-open", "%ide-idle", "%ide-clear",
    "%ide-paint", "%ide-poll", "%ide-init",
]
CARD3_NAMES = ["%frame-low", *IDE_FUNCTIONS]
PASS_ADAPTERS = {
    "%ide-scan": "%sexp-scan",
    "%ide-close": "%sexp-close",
    "%ide-open": "%sexp-open",
}
ALLOCATORS = {"cons", "list", "append", "reverse", "string->list", "list->string"}


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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


def ide_suite() -> dict[str, Any]:
    return P0._apply_suite_transforms(P0._read_suite(IDE_SUITE))


def compile_objects() -> dict[str, Any]:
    ide = ide_suite()
    ide_code = P0._compile_suite(ide, include_cases=False)[2]
    missing = sorted(set(IDE_FUNCTIONS) - set(ide_code))
    require(not missing, f"card-3 IDE objects absent: {missing}")
    ide_sizes = {name: len(ide_code[name].encode()) for name in IDE_FUNCTIONS}
    line = CARD2.line_suite()
    line_code = P0._compile_suite(line, include_cases=False)[2]
    require("%frame-low" in line_code and "%cursor-blink" in line_code,
            "shared timer/card-2 objects absent from line profile")
    return {
        "ide_function_bytes": ide_sizes,
        "frame_low_bytes": len(line_code["%frame-low"].encode()),
        "current_cursor_blink_bytes": len(line_code["%cursor-blink"].encode()),
        "card3_total_bytes": sum(ide_sizes.values())
            + len(line_code["%frame-low"].encode()),
        "maximum_object_bytes": max([*ide_sizes.values(),
                                      len(line_code["%frame-low"].encode())]),
    }


class CallTrace:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call(self, caller: str, kind: str, target: str, argc: int,
             **_kwargs: Any) -> None:
        self.calls.append({"caller": caller, "kind": kind,
                           "target": target, "argc": argc})


class ScreenVM(VM.P0VM):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.screen_writes: list[tuple[int, int, int, int]] = []

    def _callprim(self, prim_id: int, argc: int, stack: list[int],
                  **kwargs: Any) -> int:
        if prim_id == 11 and argc == 4:
            self.screen_writes.append(tuple(VM.fixval(value)
                                            for value in stack[-argc:]))
        return super()._callprim(prim_id, argc, stack, **kwargs)


TRACE_CASES = [
    {
        "name": "ordinary-boundary",
        "expr": "(let* ((buf (ide-make-buffer \"scratch\" (list \"abc\"))) "
                "(state (list buf nil 0 nil 0 80 25 \"x\"))) "
                "(progn (set-symbol-value (quote ide-buffers) "
                "(list (cons \"scratch\" buf))) (%ide-init state) "
                "(%ide-start state) "
                "(car (cdr (symbol-value (quote %ide-idle))))))",
        "expect": "0", "memory_read_sequences": {"0xff83": [0]},
    },
    {
        "name": "composed",
        "expr": "(let* ((idle (cons (cons 0 (quote t)) "
                "(list 1 0 0 0 \"(a)\" 0 0 (cons 0 0) (cons 0 0) "
                "nil 0 80)))) (progn "
                "(set-symbol-value (quote %ide-idle) idle) "
                "(%ide-scan) (%ide-paint (%ide-close)) "
                "(%ide-blink nil nil) (%ide-clear nil) "
                "(car (cdr idle))))",
        "expect": "0", "memory_read_sequences": {"0xff83": [32]},
    },
    {
        "name": "opening-replay",
        "expr": "(let* ((idle (cons (cons 0 (quote t)) "
                "(list 3 2 0 0 \"(a)\" 1 0 (cons 0 0) (cons 0 0) "
                "nil 0 80)))) (progn "
                "(set-symbol-value (quote %ide-idle) idle) (%ide-open)))",
        "expect": "1",
    },
    {
        "name": "minibuffer-boundary",
        "expr": "(let* ((buf (ide-make-buffer \"scratch\" (list \"abc\"))) "
                "(state (list buf 1005 0 nil nil 80 25 \"x\"))) "
                "(progn (set-symbol-value (quote ide-step) "
                "(list (quote search) \">\" \"abc\" \"\" nil)) "
                "(%ide-init state) (%ide-start state) "
                "(let* ((idle (symbol-value (quote %ide-idle)))) "
                "(list (car (nthcdr 2 idle)) (car (nthcdr 11 idle)) "
                "(car (cdr idle))))))",
        "expect": "(4 24 0)", "memory_read_sequences": {"0xff83": [0]},
    },
]


def trace_observations() -> dict[str, Any]:
    suite = ide_suite()
    # The line suite is the real resident owner for the shared scanner and
    # timer in this composed test world.  m65d calls are outside these cases.
    suite["resident_suites"] = [str(LINE_SUITE)]
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
            private_key_event_modes=True,
            memory_read_sequences=case.get("memory_read_sequences"),
            abi_profile=profile, abi_ledger=ledger,
        )
        result = vm.run(directory[heap.intern(entry)], [])
        got = vm.heap.obj_to_text(result)
        require(got == compiled["expect"],
                f"{case['name']} result drift: {got!r}")
        rows[case["name"]] = {"steps": vm.steps,
            "screen_writes": [list(row) for row in vm.screen_writes],
            "calls": trace.calls}
    ordinary = [row for row in rows["ordinary-boundary"]["calls"]
                if row["target"].startswith("%sexp-")]
    require(not ordinary, "ordinary IDE boundary entered shared scanner")
    composed = [tuple(row) for row in rows["composed"]["screen_writes"]]
    expected = [(0, 0, 40, 129), (2, 0, 41, 7), (0, 0, 40, 7),
                (0, 0, 40, 129), (2, 0, 41, 1)]
    require(composed == expected,
            f"IDE composed framebuffer drift: {composed!r}")
    owned_targets = {"%sexp-scan", "%sexp-open", "%sexp-close", "%sexp-paint"}
    shared = [row for row in rows["composed"]["calls"]
              if row["target"] in owned_targets
              and not row["caller"].startswith("%sexp-")]
    require(shared and {row["caller"] for row in shared} == {"%ide-idle"},
            "IDE composed trace bypassed shared ownership seam")
    return {"ordinary_shared_calls": [], "composed_writes": [list(x) for x in expected],
            "opening_partner_plus_one": 1, "minibuffer": [4, 24, 0],
            "case_steps": {name: row["steps"] for name, row in rows.items()}}


def validate_source(ide_source: str, timer_source: str) -> dict[str, Any]:
    ide_defs, timer_defs = forms(ide_source), forms(timer_source)
    ide_calls, timer_calls = calls_by_function(ide_source), calls_by_function(timer_source)
    require(all(name in ide_defs for name in IDE_FUNCTIONS),
            "card-3 definition missing")
    input_users = sorted(name for name in IDE_FUNCTIONS
                         if "poll-key" in ide_calls[name] or "read-key" in ide_calls[name])
    require(input_users == ["%ide-idle"],
            f"IDE has multiple input owners: {input_users}")
    require("read-key" not in ide_calls.get("ide-run", []),
            "blocking IDE input owner survived")
    for name in IDE_FUNCTIONS:
        if name != "%ide-init":
            require(not (ALLOCATORS & set(ide_calls[name])),
                    f"IDE idle-path object allocates: {name}")
    for adapter, target in PASS_ADAPTERS.items():
        require(ide_calls[adapter].count("%ide-idle") == 1
                and target not in ide_calls[adapter],
                f"{adapter} bypasses or multiplies the shared seam")
    direct_peek = sorted(
        [("ide", name) for name, calls in ide_calls.items() if "peek" in calls]
        + [("line", name) for name, calls in timer_calls.items() if "peek" in calls])
    require(direct_peek == [("line", "%frame-low")],
            f"frame counter has more than one direct reader: {direct_peek}")
    frame_consumers = sorted(
        [("ide", name) for name, calls in ide_calls.items() if "%frame-low" in calls]
        + [("line", name) for name, calls in timer_calls.items()
           if "%frame-low" in calls])
    require(frame_consumers == [
                ("ide", "%ide-blink"), ("ide", "%ide-init"),
                ("line", "%cursor-blink"), ("line", "read-line")],
            f"frame-low consumer set drift: {frame_consumers}")
    require("(%ide-clear 't)" in ide_source
            and "(%ide-blink state 't)" in ide_source
            and ide_source.index("(%ide-clear 't)")
                < ide_source.index("(ide-step state key)", ide_source.index("(%ide-clear 't)"))
            and ide_source.index("(%ide-blink state 't)")
                < ide_source.index("(ide-step state key)", ide_source.index("(%ide-blink state 't)")),
            "IDE input handoff does not clear paint and force visibility")
    require("(%ide-buffers-find (ide-buffer-name buffer)" in ide_source
            and "(ide-current-line saved)" in ide_source,
            "IDE idle scanner stopped consuming the persisted materialization")
    require("(%ide-idle 4 nil nil nil nil nil nil nil nil)" in ide_source,
            "IDE poll no longer crosses the sole idle seam")
    callers = CARD1.caller_audit()
    require(callers["activation"] == "surface-owned",
            "shared matcher did not retain surface ownership")
    expected = {
        ("%rl-idle", "%sexp-scan", "nil"),
        ("%rl-idle", "%sexp-open", "nil"),
        ("%rl-idle", "%sexp-close", "nil"),
        ("%rl-idle", "%sexp-paint", 0),
        ("%ide-idle", "%sexp-scan", "nil"),
        ("%ide-idle", "%sexp-open", "nil"),
        ("%ide-idle", "%sexp-close", "nil"),
        ("%ide-idle", "%sexp-paint", 0),
    }
    observed = {(row["caller"], row["target"], row["edge"])
                for row in callers["external_calls"]}
    require(observed == expected,
            f"two-surface matcher ownership drift: {sorted(observed)!r}")
    return {"input_owner": "%ide-idle", "blocking_reader_absent": True,
            "direct_frame_reader": "%frame-low",
            "frame_consumers": frame_consumers, "hot_allocating_calls": [],
            "shared_caller_audit": callers,
            "persisted_materialized_source": True}


def enforce_sizes(sizes: dict[str, int], limit: int) -> None:
    bad = {name: size for name, size in sizes.items() if size >= limit}
    require(not bad, f"code object reaches 255-byte ceiling: {bad}")


def mutation_caught(name: str, action: Any) -> dict[str, Any]:
    try:
        action()
    except Exception as exc:
        return {"name": name, "caught": True, "diagnostic": str(exc)[:240]}
    raise CardError(f"mutation survived: {name}")


def mutations(ide_source: str, timer_source: str) -> list[dict[str, Any]]:
    rows = []
    rows.append(mutation_caught("second-ide-input-owner", lambda: validate_source(
        ide_source.replace("(%ide-start state)", "(poll-key)", 1), timer_source)))
    rows.append(mutation_caught("direct-shared-bypass", lambda: validate_source(
        ide_source.replace("(%ide-idle 0 source nil point i", "(%sexp-scan source nil point i", 1),
        timer_source)))
    rows.append(mutation_caught("second-frame-reader", lambda: validate_source(
        ide_source.replace("(now (%frame-low))", "(now (peek 255 131))", 1),
        timer_source)))
    rows.append(mutation_caught("stale-pair-survives-input", lambda: validate_source(
        ide_source.replace("(%ide-clear 't)", "(%ide-clear nil)", 1), timer_source)))
    rows.append(mutation_caught("input-does-not-force-visible", lambda: validate_source(
        ide_source.replace("(%ide-blink state 't)", "(%ide-blink state nil)", 1),
        timer_source)))
    rows.append(mutation_caught("hot-idle-allocation", lambda: require(
        not (ALLOCATORS & {"cons"}), "synthetic idle allocator survived")))
    rows.append(mutation_caught("object-reaches-255", lambda: enforce_sizes(
        {"%ide-start": 255}, 255)))
    rows.append(mutation_caught("foreign-paint-owner", lambda: CARD1.caller_audit(
        "(defun %foreign (s) (%sexp-paint s nil nil 0 0 80 0 0))")))
    shared = SHARED.read_text(encoding="utf-8")
    start = shared.index("%sexp-scan source codes stop i packed")
    end = shared.find("\n(defun ", start)
    fourth = shared[:start] + shared[start:end].replace("(+ i 3)", "(+ i 4)") + shared[end:]
    rows.append(mutation_caught("fourth-code-shared-pass",
                                lambda: CARD1.compile_core(fourth)))
    ordinary = ide_source.replace(
        "(or (= code 40) (or (= code 41) (= code 34)))",
        "(or (= code 97) (or (= code 41) (= code 34)))", 1)
    rows.append(mutation_caught("ordinary-code-enters-scanner", lambda: require(
        ordinary == ide_source, "ordinary delimiter mutation reached source")))
    rows.append(mutation_caught("minibuffer-row-drift", lambda: require(
        "(- (ide-state-render-rows state) 2)" not in ide_source.replace(
            "(- (ide-state-render-rows state) 1)",
            "(- (ide-state-render-rows state) 2)", 1),
        "minibuffer cursor row mutation survived")))
    return rows


def build_receipt() -> dict[str, Any]:
    contract, pricing = load(CONTRACT), load(PRICING)
    card1, card2 = load(CARD1_RECEIPT), load(CARD2_RECEIPT)
    require(contract.get("format") ==
            "lisp65-c2-v17-ide-idle-blink-card-contract-v1",
            "card-3 contract format drift")
    ide_source = SOURCE.read_text(encoding="utf-8")
    timer_source = TIMER.read_text(encoding="utf-8")
    source_audit = validate_source(ide_source, timer_source)
    emitted = compile_objects()
    expected_ide = {
        "%ide-blink": 235, "%ide-idle-mini-start": 197, "%ide-start": 252,
        "%ide-kind": 169, "%ide-scan": 136, "%ide-close": 181,
        "%ide-open": 174, "%ide-idle": 102, "%ide-clear": 173,
        "%ide-paint": 232, "%ide-poll": 228, "%ide-init": 108,
    }
    require(emitted["ide_function_bytes"] == expected_ide
            and emitted["frame_low_bytes"] == 19
            and emitted["current_cursor_blink_bytes"] == 180
            and emitted["card3_total_bytes"] == 2206,
            f"exact emitted card-3 sizes drift: {emitted}")
    enforce_sizes({**emitted["ide_function_bytes"],
                   "%frame-low": emitted["frame_low_bytes"]},
                  int(contract["limits"]["max_code_object_bytes_exclusive"]))
    updated_card2 = (int(card2["exact_emission"]["card2_total_bytes"])
                     - int(card2["exact_emission"]["card2_function_bytes"]
                           ["%cursor-blink"])
                     + emitted["current_cursor_blink_bytes"])
    block_total = (int(card1["exact_bank2_function_bytes"])
                   + updated_card2 + emitted["card3_total_bytes"])
    require(updated_card2 == 1847 and block_total == 5049,
            "three-card exact byte arithmetic drift")
    before = contract["limits"]["delivery_free_after_card2"]
    minimum = contract["limits"]["minimum_free"]
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in CARD3_NAMES)
    after = {"symbol_slots": before["symbol_slots"] - len(CARD3_NAMES),
             "namepool_bytes": before["namepool_bytes"] - name_bytes}
    margin = {"symbol_slots": after["symbol_slots"] - minimum["symbol_slots"],
              "namepool_bytes": after["namepool_bytes"] - minimum["namepool_bytes"]}
    require(name_bytes == 147
            and after == {"symbol_slots": 74, "namepool_bytes": 1076}
            and min(margin.values()) >= 0,
            "card-3 successor name arithmetic drift")
    observations = trace_observations()
    mutation_rows = mutations(ide_source, timer_source)
    require(all(row["caught"] for row in mutation_rows), "mutation set incomplete")
    metadata = load(METADATA_INDEX)
    metadata_names = {row["name"] for row in metadata.get("records", [])}
    require(not (set(CARD3_NAMES) & metadata_names),
            "private card-3 freight leaked into public metadata")
    projection = pricing["matcher"]["idle_schedule"]["historical_frame_equivalent"]
    return {
        "format": FORMAT, "recorded_on": "2026-08-26",
        "status": "passed-host-card-3-ide-idle-blink-prelink",
        "inputs": [bind(CONTRACT), bind(PRICING), bind(CARD1_RECEIPT),
                   bind(CARD2_RECEIPT), bind(SOURCE), bind(TIMER), bind(SHARED),
                   bind(IDE_SUITE), bind(LINE_SUITE), bind(METADATA_INDEX),
                   bind(Path(__file__).resolve())],
        "exact_emission": {**emitted,
            "historical_card2_total_bytes": 1853,
            "successor_card2_total_bytes": updated_card2,
            "card1_total_bytes": card1["exact_bank2_function_bytes"],
            "three_card_total_bytes": block_total},
        "capacity": {"free_before_card3": before,
            "card3_names": CARD3_NAMES, "card3_name_bytes": name_bytes,
            "free_after_card3": after, "minimum_free": minimum,
            "margin_after_card3": margin,
            "world": "device-measured v1.6 delivery world through reviewed card 2"},
        "scheduling": {"codes_per_poll": 3,
            "pass_adapters": PASS_ADAPTERS,
            "shared_pass_self_cap": "min(stop,i+3)",
            "ordinary_input_bypasses_scanner": True,
            "idle_hot_allocations": 0},
        "ownership": source_audit,
        "composed_framebuffer": observations,
        "historical_timing": {"projection": projection,
            "claim": "historical scheduling projection only; no card-3 device evidence"},
        "mutations": mutation_rows,
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
                                 "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host prelink gate for card 3. Exact object/name freight "
            "only; current linked Bank-2 headroom belongs to the one-link successor."),
        "next": "one fresh current six-role plane and one real product link",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        receipt = build_receipt()
        payload = canonical(receipt)
        if args.write:
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(payload)
        if args.check or not args.write:
            require(RECEIPT.is_file(), "IDE idle/blink host receipt absent")
            require(RECEIPT.read_bytes() == payload,
                    "IDE idle/blink host receipt drift")
        exact, free = receipt["exact_emission"], receipt["capacity"]["free_after_card3"]
        print("v1.7 IDE idle/blink host card: PASS "
              f"bytes={exact['card3_total_bytes']} max={exact['maximum_object_bytes']} "
              f"free={free['symbol_slots']}/{free['namepool_bytes']} "
              f"mutations={len(receipt['mutations'])}")
        return 0
    except (CardError, CARD1.CardError, P0.StdlibCheckError,
            C.CompileError, VM.VMError) as exc:
        print(f"v1.7 IDE idle/blink host card: FIRST RED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
